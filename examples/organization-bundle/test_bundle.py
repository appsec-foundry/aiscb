#!/usr/bin/env python3
"""Check that the bundle example builds, verifies, installs, and refuses correctly.

Everything runs against throwaway directories. The build uses the repository's
own secure-coding-baseline.md as the approved aiscb file, so the example
stays in step with the baseline release the overlay names.
"""

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
AISCB = REPO / "secure-coding-baseline.md"

sys.path.insert(0, str(HERE))
import build  # noqa: E402
import install  # noqa: E402

failures = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global failures
    print(f"{'ok  ' if condition else 'FAIL'} {name}")
    if not condition:
        failures += 1
        if detail:
            print(f"     {detail}")


def fails_build(source: Path, root: Path, fragment: str) -> str | None:
    out = root / "out"
    shutil.rmtree(out, ignore_errors=True)
    try:
        build.build(source, AISCB, out, root / "install")
    except build.BuildError as exc:
        return None if fragment in str(exc) else f"unexpected message: {exc}"
    return "build succeeded"


def fails_install(bundle: Path, digest: str, root: Path, fragment: str) -> str | None:
    try:
        install.install(bundle, digest, root)
    except install.InstallError as exc:
        return None if fragment in str(exc) else f"unexpected message: {exc}"
    return "install succeeded"


def copy_source(root: Path, name: str) -> Path:
    target = root / name
    shutil.copytree(HERE, target, ignore=shutil.ignore_patterns("__pycache__", "*.py", ".*"))
    return target


def edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} not in {path}"
    path.write_text(text.replace(old, new), encoding="utf-8")


with tempfile.TemporaryDirectory() as tmp:
    work = Path(tmp)
    root = work / "install"
    out = work / "bundle"
    manifest, digest = build.build(HERE, AISCB, out, root)
    aiscb_id = build.single(build.ID_RE, AISCB.read_text(encoding="utf-8"), "id")
    release_dir = root.resolve() / "releases" / manifest["bundle"]

    # ---- build output -------------------------------------------------------
    check("manifest names the repository baseline", manifest["aiscb"] == aiscb_id)
    check("manifest release dir is the versioned directory",
          manifest["release_dir"] == str(release_dir))
    listed = set(manifest["files"])
    on_disk = {str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()} - {"manifest.json"}
    check("manifest lists every built file and nothing else", listed == on_disk,
          f"listed-only {sorted(listed - on_disk)}, disk-only {sorted(on_disk - listed)}")
    mismatched = [rel for rel, entry in manifest["files"].items()
                  if (out / rel).stat().st_size != entry["size"]
                  or hashlib.sha256((out / rel).read_bytes()).hexdigest() != entry["sha256"]]
    check("recorded sizes and digests match the files", not mismatched, str(mismatched))
    check("manifest digest is the digest of manifest.json",
          hashlib.sha256((out / "manifest.json").read_bytes()).hexdigest() == digest)
    leftovers = [rel for rel in listed
                 if build.PLACEHOLDER in (out / rel).read_text(encoding="utf-8", errors="ignore")]
    check("no bundle-dir placeholder survives the build", not leftovers, str(leftovers))
    claude = (out / "adapters/claude-code/CLAUDE.md").read_text(encoding="utf-8")
    check("Claude Code adapter imports the versioned aiscb file",
          claude.startswith(f"@{release_dir}/secure-coding-baseline.md\n\n# Acme"))
    codex = (out / "adapters/codex/AGENTS.md").read_text(encoding="utf-8")
    check("Codex adapter is aiscb followed by the overlay without the marker",
          codex.startswith("# AI Secure Coding Baseline") and "@<bundle-dir>" not in codex
          and "# Acme Secure Coding Overlay" in codex and codex.count("baseline-id:") == 2)
    check("gateway block equals the combined adapter",
          (out / "adapters/gateway/system-block.md").read_bytes() == codex.encode("utf-8"))
    for tool in build.ADAPTERS:
        skill = out / f"adapters/{tool}/skills/acme-authentication/SKILL.md"
        text = skill.read_text(encoding="utf-8") if skill.is_file() else ""
        check(f"{tool} gets the pack as a skill with frontmatter",
              text.startswith("---\nname: acme-authentication\ndescription: ")
              and f"{release_dir}/blueprints/spa/1.0.0.json" in text)
    check("blueprint ships unchanged",
          (out / "blueprints/spa/1.0.0.json").read_bytes()
          == (HERE / "blueprints/spa/1.0.0.json").read_bytes())
    try:
        build.build(HERE, AISCB, out, root)
        reused = True
    except build.BuildError as exc:
        reused = "not empty" not in str(exc)
    check("a non-empty output directory is refused", not reused)

    # ---- build refusals -----------------------------------------------------
    broken = copy_source(work, "src-extends")
    edit(broken / "overlay.md", f"Extends aiscb (`{aiscb_id}`)", "Extends aiscb (`aiscb-0.0.1`)")
    check("overlay naming another aiscb release is refused",
          fails_build(broken, work, "overlay extends aiscb-0.0.1") is None)

    broken = copy_source(work, "src-field")
    edit(broken / "blueprints/spa/1.0.0.json", '"version": "1.0.0",',
         '"version": "1.0.0",\n  "debug": true,')
    check("blueprint with an unknown field is refused",
          fails_build(broken, work, "unknown fields ['debug']") is None)

    broken = copy_source(work, "src-version")
    edit(broken / "blueprints/spa/1.0.0.json", '"version": "1.0.0"', '"version": "1.1.0"')
    check("blueprint version disagreeing with its path is refused",
          fails_build(broken, work, "does not match the file name") is None)

    broken = copy_source(work, "src-rule")
    edit(broken / "catalog.json", '"aiscb-ERRORS-001"', '"aiscb-NOPE-001"')
    check("catalog narrowing an unknown aiscb rule is refused",
          fails_build(broken, work, "unknown aiscb rules ['aiscb-NOPE-001']") is None)

    broken = copy_source(work, "src-stray")
    (broken / "packs/orphan.md").write_text("# orphan\n", encoding="utf-8")
    check("a pack missing from the catalog is refused",
          fails_build(broken, work, "packs/orphan.md") is None)

    broken = copy_source(work, "src-missing-req")
    edit(broken / "packs/authentication.md", "[ACME-IAM-AUDIT-001]", "[ACME-IAM-AUDIT-002]")
    check("a catalog requirement the pack does not define is refused",
          fails_build(broken, work, "does not define ACME-IAM-AUDIT-001") is None)

    try:
        build.build(HERE, AISCB, work / "out-digest", root, "0" * 64)
        digest_refused = False
    except build.BuildError as exc:
        digest_refused = "approved digest" in str(exc)
    check("an aiscb file that misses the approved digest is refused", digest_refused)

    # ---- install ------------------------------------------------------------
    check("a wrong manifest digest installs nothing",
          fails_install(out, "f" * 64, root, "does not match the expected digest") is None
          and not root.exists())

    tampered = work / "tampered"
    shutil.copytree(out, tampered)
    (tampered / "overlay.md").write_bytes(
        (tampered / "overlay.md").read_bytes().replace(b"never relax it", b"may relax it"))
    check("a tampered file installs nothing",
          fails_install(tampered, digest, root, "overlay.md") is None
          and not root.exists())

    check("a bundle built for another root is refused",
          fails_install(out, digest, work / "elsewhere", "would not resolve") is None)

    real_copy = shutil.copyfile
    calls = {"n": 0}

    def flaky(src, dst, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 3:
            raise OSError("disk full")
        return real_copy(src, dst, *args, **kwargs)

    install.shutil.copyfile = flaky
    try:
        install.install(out, digest, root)
        interrupted = False
    except OSError:
        interrupted = True
    finally:
        install.shutil.copyfile = real_copy
    check("an interrupted install leaves no release and no staging directory",
          interrupted and not (root / "releases" / manifest["bundle"]).exists()
          and not list((root / "releases").glob(".staging-*")) and not (root / "current").exists())

    record = install.install(out, digest, root)
    link = root / "current"
    check("install places the release and points current at it",
          record["current"] == manifest["bundle"] and link.is_symlink()
          and (link / "overlay.md").is_file()
          and os.readlink(link) == f"releases/{manifest['bundle']}")
    check("the installed adapter resolves the versioned import path",
          (release_dir / "secure-coding-baseline.md").is_file()
          and (link / "adapters/claude-code/CLAUDE.md").read_text(encoding="utf-8")
          .startswith(f"@{release_dir}/secure-coding-baseline.md"))
    lines, healthy = install.status(root)
    check("status reports a healthy install", healthy and any("match" in l for l in lines))
    check("an installed release is never overwritten",
          fails_install(out, digest, root, "already installed") is None)

    newer_src = copy_source(work, "src-next")
    edit(newer_src / "overlay.md", "acme-sec-1.0.0", "acme-sec-1.0.1")
    newer_out = work / "bundle-next"
    newer_manifest, newer_digest = build.build(newer_src, AISCB, newer_out, root)
    install.install(newer_out, newer_digest, root)
    check("update switches current to the new release and keeps the old one",
          os.readlink(link) == "releases/acme-sec-1.0.1"
          and (root / "releases/acme-sec-1.0.0/overlay.md").is_file())
    rolled = install.rollback(root)
    check("rollback is one switch back to the previous release",
          rolled["current"] == "acme-sec-1.0.0" and os.readlink(link) == "releases/acme-sec-1.0.0")

    (root / "releases/acme-sec-1.0.0/overlay.md").write_bytes(b"edited on the machine\n")
    lines, healthy = install.status(root)
    check("status detects drift in the current release",
          not healthy and any("overlay.md" in l for l in lines))

    unrelated = root / "notes.txt"
    unrelated.write_text("keep\n", encoding="utf-8")
    install.uninstall(root)
    check("uninstall removes the recorded releases and leaves unrelated files",
          not (root / "releases").exists() and not link.is_symlink()
          and not (root / install.RECORD).exists() and unrelated.is_file())

    # ---- command line -------------------------------------------------------
    proc = subprocess.run([sys.executable, str(HERE / "install.py"), "--root", str(root),
                           "install", str(out), "--manifest-sha256", "0" * 64],
                          capture_output=True, text=True, timeout=60)
    check("the command line reports a refused install on stderr and exits 1",
          proc.returncode == 1 and "does not match" in proc.stderr and proc.stdout == "")
    proc = subprocess.run([sys.executable, str(HERE / "build.py"), "--aiscb", str(AISCB),
                           "--out", str(work / "cli-out"), "--install-root", str(root)],
                          capture_output=True, text=True, timeout=60)
    check("the build command prints the manifest digest for out-of-band delivery",
          proc.returncode == 0 and "manifest:" in proc.stdout and digest in proc.stdout)

    # ---- gateway hook -------------------------------------------------------
    litellm = types.ModuleType("litellm")
    integrations = types.ModuleType("litellm.integrations")
    custom_logger = types.ModuleType("litellm.integrations.custom_logger")

    class CustomLogger:  # stand-in for the real base class
        pass

    custom_logger.CustomLogger = CustomLogger
    sys.modules.update({"litellm": litellm, "litellm.integrations": integrations,
                        "litellm.integrations.custom_logger": custom_logger})
    block_path = out / "adapters/gateway/system-block.md"
    block_digest = manifest["files"]["adapters/gateway/system-block.md"]["sha256"]
    os.environ["AISCB_GATEWAY_BLOCK"] = str(block_path)
    os.environ["AISCB_GATEWAY_SHA256"] = "1" * 64
    sys.path.insert(0, str(HERE / "gateway"))
    try:
        import custom_callbacks  # noqa: F401
        wrong_digest_refused = False
    except SystemExit as exc:
        wrong_digest_refused = "pinned digest" in str(exc)
    check("the gateway refuses to start on a digest mismatch", wrong_digest_refused)

    os.environ["AISCB_GATEWAY_SHA256"] = block_digest
    sys.modules.pop("custom_callbacks", None)
    import custom_callbacks  # noqa: E402

    hook = custom_callbacks.proxy_handler_instance.async_pre_call_hook
    attribution = {"type": "text", "text": "x-anthropic-attribution: claude-code"}
    original = {"type": "text", "text": "You are Claude Code.", "cache_control": {"type": "ephemeral"}}
    data = {"system": [attribution, original], "messages": [], "max_tokens": 8}
    result = asyncio.run(hook(None, None, data, "anthropic_messages"))
    system = result["system"]
    check("the block is appended as its own last system block",
          len(system) == 3 and system[0] is attribution and system[1] is original
          and system[2]["text"] == block_path.read_text(encoding="utf-8"))
    again = asyncio.run(hook(None, None, result, "anthropic_messages"))
    check("a retried request is not injected twice", len(again["system"]) == 3)
    as_string = asyncio.run(hook(None, None, {"system": "plain", "messages": []}, "x"))
    check("a string system prompt becomes a block list with the block last",
          [b["text"] for b in as_string["system"]][0] == "plain" and len(as_string["system"]) == 2)
    other = {"messages": [{"role": "user", "content": "hi"}]}
    check("requests without a system field pass through unchanged",
          asyncio.run(hook(None, None, dict(other), "completion")) == other)

if failures:
    print(f"organization bundle: {failures} failure(s)")
    sys.exit(1)
print("organization bundle: ok")
