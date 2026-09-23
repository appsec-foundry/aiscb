#!/usr/bin/env python3
"""Compare installed baseline arms on CWEval Python tasks.

CWEval supplies tasks and the evaluator. This adapter supplies paired assistant
responses in CWEval's generated_N/*_raw.py format; it never runs generated code
on the host. Evaluation runs in a bounded, offline container.
"""

import argparse
from contextlib import contextmanager
import json
import os
import re
import signal
import shutil
import subprocess
import sys
import tarfile
import tempfile
import uuid
from pathlib import Path

import run as baseline_run


DEFAULT_CASES = ("cwe_020_0", "cwe_022_0", "cwe_079_0")
CASE_NAME = re.compile(r"cwe_[0-9]+_[0-9]+\Z")
REVISION = re.compile(r"[0-9a-f]{40}\Z")
IMAGE = re.compile(r"[a-z0-9./_-]+@sha256:[0-9a-f]{64}\Z")
MODEL = re.compile(r"[A-Za-z0-9._/:+-]{1,150}\Z")
SOLUTION = re.compile(r"(?m)^\s*# BEGIN SOLUTION\s*$")
CODE_BLOCK = re.compile(r"(?m)^```(?:python|py)?[ \t]*\n(?P<code>.*?)^```[ \t]*$",
                        re.DOTALL)
MAX_CODE_BYTES = 200_000
MAX_TASK_BYTES = 50_000
MAX_SCORE_BYTES = 1_000_000
RESULTS = baseline_run.RESULTS_DIR / "cweval"
LOCAL_CONFIG = Path(__file__).with_name("cweval.local.json")
CONTAINER_ROOT = "/home/ubuntu/CWEval"
CONTAINER_UID = 1000
CONTAINER_GID = 1000
CONFIG_OPTIONS = {
    "cweval_root": str, "revision": str, "image": str,
    "tool": str, "model": str, "cases": str,
    "repeats": int, "timeout": int, "eval_timeout": int,
}


def local_config_args(path: Path = LOCAL_CONFIG) -> list[str]:
    if path.is_symlink():
        raise ValueError("CWEval local config must be a regular file")
    if not path.exists():
        return []
    if not path.is_file():
        raise ValueError("CWEval local config must be a regular file")
    with path.open("rb") as stream:
        raw = stream.read(4097)
    if len(raw) > 4096:
        raise ValueError("CWEval local config exceeds 4096 bytes")
    try:
        config = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("CWEval local config is not valid JSON") from exc
    if not isinstance(config, dict) or set(config) - set(CONFIG_OPTIONS):
        raise ValueError("CWEval local config must contain only supported options")
    result = []
    for key, value in config.items():
        if type(value) is not CONFIG_OPTIONS[key]:
            raise ValueError(f"CWEval local config has an invalid {key}")
        result.extend(("--" + key.replace("_", "-"), str(value)))
    return result


def checked_checkout(root: Path, revision: str) -> Path:
    if not REVISION.fullmatch(revision):
        raise ValueError("--revision must be a full lowercase Git commit ID")
    root = root.resolve(strict=True)
    for rel in ("cweval/evaluate.py", "benchmark/core/py"):
        if not (root / rel).exists():
            raise ValueError(f"CWEval checkout lacks {rel}")
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()
    if head != revision:
        raise ValueError(f"CWEval checkout is at {head}, expected {revision}")
    dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain"],
                           capture_output=True, text=True, check=True).stdout
    if dirty:
        raise ValueError("CWEval checkout must be clean for a reproducible run")
    return root


def task_prompt(root: Path, name: str) -> str:
    if not CASE_NAME.fullmatch(name):
        raise ValueError(f"invalid CWEval case: {name}")
    task = root / "benchmark" / "core" / "py" / f"{name}_task.py"
    test = root / "benchmark" / "core" / "py" / f"{name}_test.py"
    if task.is_symlink() or test.is_symlink() or not task.is_file() or not test.is_file():
        raise ValueError(f"missing or linked CWEval task/test: {name}")
    if task.stat().st_size > MAX_TASK_BYTES:
        raise ValueError(f"CWEval task exceeds size limit: {name}")
    source = task.read_text(encoding="utf-8")
    parts = SOLUTION.split(source, maxsplit=1)
    if len(parts) != 2 or not parts[0].strip():
        raise ValueError(f"no valid solution boundary in {name}")
    prompt = parts[0].split("BEGIN PROMPT")[-1].strip()
    if not prompt:
        raise ValueError(f"empty task prompt in {name}")
    return prompt


def generation_prompt(code_prompt: str) -> str:
    return (
        "Implement the following Python function. Return the complete, directly "
        "usable Python source, including imports and the function declaration, "
        "in exactly one fenced Python code block. Do not call or test it. "
        "Do not use tools or inspect other files.\n\n"
        f"```python\n{code_prompt}\n```"
    )


def extract_code(reply: str) -> str:
    matches = list(CODE_BLOCK.finditer(reply))
    if len(matches) != 1 or reply.count("```") != 2:
        raise ValueError("response must contain exactly one Python code block")
    code = matches[0].group("code").strip() + "\n"
    if len(code.encode("utf-8")) > MAX_CODE_BYTES or not code.strip():
        raise ValueError("response code is empty or exceeds size limit")
    return code


def assistant_reply(tool: str, workdir: Path, prompt: str,
                    model: str, timeout: int) -> str:
    if tool == "claude":
        # Project rules are still loaded; model tools are disabled for generation.
        cmd = ["claude", "-p", prompt, "--tools", "",
               "--strict-mcp-config", "--disable-slash-commands",
               "--no-chrome", "--setting-sources", "project",
               "--model", model]
    else:
        # Disable command execution and external tools; read-only is a second
        # boundary if a future CLI version offers another write-capable tool.
        cmd = ["codex", "exec", "--skip-git-repo-check", "--ephemeral",
               "--ignore-user-config", "--strict-config",
               "--disable", "shell_tool", "--disable", "unified_exec",
               "--disable", "apps", "--disable", "multi_agent",
               "--disable", "remote_plugin", "-c", 'web_search="disabled"',
               "-C", str(workdir), "--sandbox", "read-only", "-m", model, "-o",
               str(workdir / "_agent_reply.txt"), prompt]
    rc, out, err = baseline_run.run_capture(cmd, workdir, timeout)
    if rc != 0:
        if baseline_run.LIMIT_PATTERNS.search(out + err):
            raise baseline_run.QuotaExhausted("assistant quota exhausted")
        raise RuntimeError("assistant timed out" if rc == -1 else f"assistant exited {rc}")
    if tool == "codex":
        reply_file = workdir / "_agent_reply.txt"
        if not reply_file.is_file():
            raise RuntimeError("Codex returned no final response file")
        return reply_file.read_text(encoding="utf-8")
    return out


@contextmanager
def isolated_codex_home(tool: str):
    """Keep a user-level AGENTS.md out of both comparison arms.

    Codex reads authentication from CODEX_HOME/auth.json even when its user
    configuration is ignored. Link only that file, never the user's rules or
    other configuration, and leave the existing installation untouched.
    """
    if tool != "codex":
        yield
        return
    previous = os.environ.get("CODEX_HOME")
    source = Path(previous) if previous else Path.home() / ".codex"
    with tempfile.TemporaryDirectory(prefix="aiscb-cweval-codex-") as temp:
        auth = source / "auth.json"
        if auth.is_file():
            (Path(temp) / "auth.json").symlink_to(auth.resolve())
        os.environ["CODEX_HOME"] = temp
        try:
            yield
        finally:
            if previous is None:
                os.environ.pop("CODEX_HOME", None)
            else:
                os.environ["CODEX_HOME"] = previous


def preflight(tool: str, model: str, timeout: int, result_dir: Path) -> list[dict]:
    expected = baseline_run.baseline_identifier()
    family = baseline_run.id_family(expected)
    probes = []
    for arm in ("control", "baseline"):
        workdir = Path(tempfile.mkdtemp(prefix=f"cweval-probe-{arm}-", dir=result_dir))
        try:
            if arm == "baseline":
                baseline_run.ADAPTERS[tool]["install"](workdir)
            reply = assistant_reply(tool, workdir, "aiscb?", model, timeout)
            found = sorted(set(family.findall(reply)))
            probes.append({"tool": tool, "arm": arm,
                           "ok": not found if arm == "control" else expected in found,
                           "found": found,
                           "expected": expected if arm == "baseline" else None,
                           "reply": reply.strip()[:400]})
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
    return probes


def generate(cases: dict[str, str], tool: str, model: str,
             repeats: int, timeout: int, result_dir: Path) -> list[dict]:
    runs = []
    for index in range(repeats):
        for name, code_prompt in cases.items():
            for arm in ("control", "baseline"):
                run = {"case": name, "sample": index, "arm": arm,
                       "status": "incomplete"}
                runs.append(run)
                workdir = Path(tempfile.mkdtemp(prefix="cweval-agent-", dir=result_dir))
                try:
                    if arm == "baseline":
                        baseline_run.ADAPTERS[tool]["install"](workdir)
                    reply = assistant_reply(tool, workdir,
                                            generation_prompt(code_prompt),
                                            model, timeout)
                    code = extract_code(reply)
                    output = (result_dir / arm / f"generated_{index}" / "core" /
                              "py" / f"{name}_raw.py")
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_text(code, encoding="utf-8")
                    run["status"] = "complete"
                except (OSError, ValueError, RuntimeError) as exc:
                    run["reason"] = str(exc)[:200]
                finally:
                    shutil.rmtree(workdir, ignore_errors=True)
                print(f"{arm} {name} sample {index}: {run['status']}", flush=True)
    return runs


def docker_command(root: Path, arm_dir: Path, image: str, name: str) -> list[str]:
    if not IMAGE.fullmatch(image):
        raise ValueError("--image must be an immutable name@sha256:<64 hex> reference")
    return [
        "docker", "run", "--rm", "-i", "--pull=never", "--name", name,
        "--network=none", "--read-only", "--cap-drop=ALL",
        "--security-opt=no-new-privileges", "--pids-limit=128",
        "--memory=2g", "--cpus=2", "--ulimit=nofile=1024:1024",
        "--user", f"{CONTAINER_UID}:{CONTAINER_GID}",
        "--tmpfs", "/tmp:rw,nosuid,noexec,size=512m",
        "--tmpfs", f"{CONTAINER_ROOT}/evals/aiscb:rw,nosuid,noexec,"
                   f"size=512m,uid={CONTAINER_UID},gid={CONTAINER_GID},mode=0700",
        "--env", "HOME=/tmp", "--env", "TMPDIR=/tmp",
        "--env", "PYTHONDONTWRITEBYTECODE=1",
        "--env", f"PYTHONPATH={CONTAINER_ROOT}",
        "--env", "PATH=/home/ubuntu/miniforge3/envs/cweval/bin:"
                 "/usr/local/go/bin:/usr/local/bin:/usr/bin:/bin",
        "--mount", f"type=bind,src={root / 'cweval'},dst={CONTAINER_ROOT}/cweval,readonly",
        "--mount", f"type=bind,src={root / 'benchmark'},dst={CONTAINER_ROOT}/benchmark,readonly",
        "--workdir", CONTAINER_ROOT, image,
        "/bin/sh", "-c",
        "tar -xf - -C evals/aiscb && "
        "/home/ubuntu/miniforge3/envs/cweval/bin/python cweval/evaluate.py "
        "pipeline --eval_path evals/aiscb --num_proc 1 --docker False "
        ">/tmp/aiscb-eval.log 2>&1 || { tail -c 2000 /tmp/aiscb-eval.log >&2; exit 1; }; "
        f"test $(wc -c < evals/aiscb/res_all.json) -le {MAX_SCORE_BYTES} && "
        "cat evals/aiscb/res_all.json",
    ]


def evaluation_archive(stream, arm_dir: Path, names: list[str], repeats: int) -> None:
    """Send only generated Python files to the container through stdin."""
    with tarfile.open(fileobj=stream, mode="w") as archive:
        for index in range(repeats):
            for name in names:
                relative = Path(f"generated_{index}/core/py/{name}_raw.py")
                source = arm_dir / relative
                if source.is_symlink() or not source.is_file():
                    raise ValueError(f"missing or linked generated file: {relative}")
                size = source.stat().st_size
                if size < 1 or size > MAX_CODE_BYTES:
                    raise ValueError(f"invalid generated file size: {relative}")
                info = tarfile.TarInfo(relative.as_posix())
                info.size = size
                info.mode = 0o600
                info.uid = CONTAINER_UID
                info.gid = CONTAINER_GID
                with source.open("rb") as content:
                    archive.addfile(info, content)
    stream.seek(0)


def run_docker_with_archive(cmd: list[str], stream, cwd: Path,
                            timeout: int) -> tuple[int, str, str]:
    proc = subprocess.Popen(cmd, cwd=cwd, stdin=stream,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, start_new_session=True)
    try:
        out, err = proc.communicate(timeout=timeout)
        return proc.returncode, out, err
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        try:
            out, err = proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            out, err = "", ""
        return -1, out, err


def evaluate(root: Path, result_dir: Path, image: str, timeout: int,
             names: list[str], repeats: int) -> None:
    if shutil.which("docker") is None:
        raise RuntimeError("Docker is required to evaluate generated code")
    for arm in ("control", "baseline"):
        name = f"aiscb-cweval-{uuid.uuid4().hex[:12]}"
        cmd = docker_command(root, result_dir / arm, image, name)
        try:
            with tempfile.TemporaryFile(dir=result_dir) as archive:
                evaluation_archive(archive, result_dir / arm, names, repeats)
                rc, out, err = run_docker_with_archive(cmd, archive,
                                                       result_dir, timeout)
            if rc != 0:
                raise RuntimeError(f"CWEval evaluation for {arm} "
                                   + ("timed out" if rc == -1 else
                                      f"exited {rc}: {err.strip()[-500:]}"))
            if len(out.encode("utf-8")) > MAX_SCORE_BYTES:
                raise ValueError(f"CWEval result for {arm} exceeds size limit")
            (result_dir / arm / "res_all.json").write_text(out, encoding="utf-8")
        finally:
            # Only this invocation's uniquely named container can be removed.
            subprocess.run(["docker", "rm", "-f", name], capture_output=True,
                           timeout=20, check=False)


def read_scores(arm_dir: Path, names: list[str], repeats: int) -> dict:
    result = json.loads((arm_dir / "res_all.json").read_text(encoding="utf-8"))
    if not isinstance(result, dict) or any(not isinstance(k, str) or
                                           not isinstance(v, dict)
                                           for k, v in result.items()):
        raise ValueError("invalid CWEval result structure")
    expected = {f"{name}_test.py" for name in names}
    if {Path(key).name for key in result} != expected or len(result) != len(names):
        raise ValueError("CWEval result cases differ from selected cases")
    scores = {}
    for name in names:
        matches = [v for key, v in result.items()
                   if Path(key).name == f"{name}_test.py"]
        if len(matches) != 1:
            raise ValueError(f"missing or duplicate evaluation for {name}")
        values = matches[0]
        functional = values.get("functional")
        secure = values.get("secure")
        if (not isinstance(functional, list) or not isinstance(secure, list)
                or len(functional) != repeats or len(secure) != repeats
                or any(type(v) is not bool for v in functional + secure)):
            raise ValueError(f"invalid evaluation data for {name}")
        scores[name] = {"functional": sum(functional),
                        "func_secure": sum(a and b for a, b in zip(functional, secure)),
                        "samples": repeats}
    return scores


def overall_scores(scores: dict) -> dict:
    totals = {}
    for arm in ("control", "baseline"):
        samples = sum(case["samples"] for case in scores[arm].values())
        if samples < 1:
            raise ValueError("CWEval comparison has no samples")
        functional = sum(case["functional"] for case in scores[arm].values())
        func_secure = sum(case["func_secure"] for case in scores[arm].values())
        totals[arm] = {
            "samples": samples,
            "functional": functional,
            "func_secure": func_secure,
            "functional_percent": round(100 * functional / samples, 1),
            "func_secure_percent": round(100 * func_secure / samples, 1),
        }
    if totals["control"]["samples"] != totals["baseline"]["samples"]:
        raise ValueError("CWEval comparison arms have different sample counts")
    totals["delta_percentage_points"] = round(
        100 * (totals["baseline"]["func_secure"] / totals["baseline"]["samples"]
               - totals["control"]["func_secure"] / totals["control"]["samples"]), 1)
    return totals


def write_report(result_dir: Path, scores: dict, runs: list[dict],
                 model: str, revision: str, image: str) -> dict:
    overall = overall_scores(scores)
    document = {"model": model, "cweval_revision": revision, "image": image,
                "baseline_id": baseline_run.baseline_identifier(),
                "runs": runs, "scores": scores, "overall": overall}
    (result_dir / "report.json").write_text(json.dumps(document, indent=2) + "\n")
    lines = ["# CWEval baseline comparison", "",
             f"Model: `{model}` · CWEval: `{revision}` · Baseline: "
             f"`{document['baseline_id']}`", "",
             "| Arm | Functional | Functional + secure |",
             "| --- | ---: | ---: |"]
    for arm in ("control", "baseline"):
        total = overall[arm]
        lines.append(f"| {arm} | {total['functional']}/{total['samples']} "
                     f"({total['functional_percent']:.1f}%) | "
                     f"{total['func_secure']}/{total['samples']} "
                     f"({total['func_secure_percent']:.1f}%) |")
    lines.extend(["", "Functional + secure difference (baseline − control): "
                  f"{overall['delta_percentage_points']:+.1f} percentage points.", "",
                  "| Case | Arm | func@1 | func-sec@1 |", "| --- | --- | ---: | ---: |"])
    for case in scores["control"]:
        for arm in ("control", "baseline"):
            score = scores[arm][case]
            n = score["samples"]
            lines.append(f"| {case} | {arm} | {score['functional']}/{n} | "
                         f"{score['func_secure']}/{n} |")
    lines.append("")
    (result_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return overall


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cweval-root", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--tool", choices=("claude", "codex"), default="claude")
    parser.add_argument("--model", required=True)
    parser.add_argument("--cases", default=",".join(DEFAULT_CASES))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--eval-timeout", type=int, default=1800)
    parser.add_argument("--dry-run", action="store_true")
    supplied = list(sys.argv[1:] if argv is None else argv)
    try:
        defaults = [] if any(flag in supplied for flag in ("-h", "--help")) \
            else local_config_args()
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    args = parser.parse_args(defaults + supplied)
    if args.repeats < 1 or args.repeats > 50 or args.timeout < 1 or args.eval_timeout < 1:
        parser.error("repeats must be 1..50 and timeouts must be positive")
    try:
        root = checked_checkout(args.cweval_root, args.revision)
        if not MODEL.fullmatch(args.model):
            raise ValueError("--model must be a short model identifier")
        if not IMAGE.fullmatch(args.image):
            raise ValueError("--image must be an immutable name@sha256:<64 hex> reference")
        names = args.cases.split(",")
        if len(names) != len(set(names)) or not names or len(names) > 30:
            raise ValueError("select 1..30 distinct CWEval cases")
        cases = {name: task_prompt(root, name) for name in names}
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    if args.dry_run:
        print(f"{len(cases)} cases × {args.repeats} repeats × 2 arms = "
              f"{len(cases) * args.repeats * 2} assistant runs")
        print("Cases: " + ", ".join(cases))
        return 0
    if shutil.which(args.tool) is None:
        parser.error(f"{args.tool} is not on PATH")
    if shutil.which("docker") is None:
        parser.error("Docker is required before starting assistant runs")
    RESULTS.mkdir(parents=True, exist_ok=True)
    result_dir = Path(tempfile.mkdtemp(prefix="run-", dir=RESULTS))
    try:
        with isolated_codex_home(args.tool):
            probes = preflight(args.tool, args.model, args.timeout, result_dir)
            (result_dir / "preflight.json").write_text(json.dumps(probes, indent=2) + "\n")
            for probe in probes:
                if not probe["ok"]:
                    raise RuntimeError(baseline_run.preflight_problem(probe))
            runs = generate(cases, args.tool, args.model, args.repeats,
                            args.timeout, result_dir)
            (result_dir / "runs.json").write_text(json.dumps(runs, indent=2) + "\n")
            if any(run["status"] != "complete" for run in runs):
                raise RuntimeError("generation incomplete; evaluation skipped")
            evaluate(root, result_dir, args.image, args.eval_timeout,
                     names, args.repeats)
        scores = {arm: read_scores(result_dir / arm, names, args.repeats)
                  for arm in ("control", "baseline")}
        overall = write_report(result_dir, scores, runs, args.model,
                               args.revision, args.image)
        print("Functional + secure: "
              f"control {overall['control']['func_secure_percent']:.1f}%, "
              f"baseline {overall['baseline']['func_secure_percent']:.1f}%, "
              f"difference {overall['delta_percentage_points']:+.1f} percentage points")
        print(f"Report: {result_dir / 'report.md'}")
        return 0
    except (OSError, ValueError, RuntimeError, baseline_run.QuotaExhausted) as exc:
        print(f"Incomplete CWEval run: {exc}; evidence: {result_dir}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
