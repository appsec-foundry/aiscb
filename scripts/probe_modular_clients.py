#!/usr/bin/env python3
"""Opt-in real CLI loading probe with isolated homes and a loopback API fixture.

No real credentials or model calls. This proves initial-context delivery, not
semantic module selection or IDE behavior. Existing CLIs must already be installed.
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading

import build_baseline
import install
from probe_session_switch import CaptureServer


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def probe(tool, scope, server, nested, claude_entry=None, mixed=False):
    with tempfile.TemporaryDirectory(prefix="aiscb-modular-client-") as directory:
        root = Path(directory)
        home, work = root / "home", root / "project"
        home.mkdir()
        work.mkdir()
        config = home / ("." + tool)
        config.mkdir()
        subprocess.run(["git", "init", "-q", str(work)], check=True, capture_output=True, timeout=10)
        env = {"PATH": os.environ["PATH"], "HOME": str(home), "LANG": "C.UTF-8", "CI": "true"}
        env.update({var: str(home / ("." + t)) for t, var in install.CONFIG_HOME_ENV.items()})
        args = ["--user"] if scope == "user" else ["--into", str(work)]
        if claude_entry:
            args += ["--claude-entry", claude_entry]
        selected = [tool, "codex"] if mixed else [tool]
        setup = subprocess.run([sys.executable, str(install.INSTALLER_SOURCE), *selected, *args],
                               env=env, cwd=work, capture_output=True, text=True, timeout=20)
        if setup.returncode:
            raise RuntimeError(setup.stderr)
        url = f"http://127.0.0.1:{server.server_port}"
        if tool == "claude":
            env.update(ANTHROPIC_BASE_URL=url, ANTHROPIC_API_KEY="isolated-test-only",
                       CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1")
            argv = [tool, "-p", "aiscb?", "--model", "claude-sonnet-4-6", "--tools", "",
                    "--strict-mcp-config", "--no-session-persistence"]
        elif tool == "codex":
            (config / "config.toml").write_text(
                'model="probe"\nmodel_provider="probe"\n'
                '[model_providers.probe]\nname="probe"\nbase_url=' + json.dumps(url) +
                '\nwire_api="responses"\nrequires_openai_auth=false\n'
                '[projects.' + json.dumps(str(work)) + ']\ntrust_level="trusted"\n')
            argv = [tool, "exec", "--ephemeral", "--sandbox", "read-only", "aiscb?"]
        else:
            env.update(COPILOT_PROVIDER_BASE_URL=url, COPILOT_PROVIDER_TYPE="anthropic",
                       COPILOT_PROVIDER_API_KEY="isolated-test-only",
                       COPILOT_MODEL="claude-sonnet-4-6")
            argv = [tool, "-p", "aiscb?", "--disable-builtin-mcps", "--no-auto-update",
                    "--no-remote", "--no-remote-export", "--log-level", "none"]
        cwd = work
        if nested:
            cwd = work / "nested"
            cwd.mkdir()
        server.requests.clear()
        try:
            result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True,
                                    text=True, timeout=45)
            exit_code = result.returncode
        except subprocess.TimeoutExpired:
            exit_code = "timeout"
        # Check each captured request separately: retries must not look like
        # duplicate instruction delivery within a single model context.
        contexts = ["\n".join(strings(request)) for request in server.requests]
        context = "\n".join(contexts)
        core = build_baseline.SOURCE_ROOT.joinpath("aiscb-core.md").read_text().strip()
        catalog = build_baseline.load_catalog()
        core_present = core in context
        discovery = all(m["id"] in context for m in catalog["modules"])
        bodies = any(f"[{rule}]" in context for m in catalog["modules"] for rule in m["rules"])
        copies = max((request.count(core) for request in contexts), default=0)
        passed = exit_code == 0 and core_present and discovery and not bodies and copies == 1
        print(json.dumps({"tool": tool, "scope": scope, "nested": nested,
                          "claude_entry": claude_entry or "auto", "mixed": mixed,
                          "exit": exit_code, "requests": len(server.requests),
                          "core": core_present, "core_copies": copies, "catalog": discovery,
                          "module_bodies": bodies, "passed": passed}), flush=True)
        return passed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools", nargs="+", choices=install.TOOLS, default=list(install.TOOLS))
    parser.add_argument("--claude-entries", nargs="+", choices=("auto", "rules", "claude-md"),
                        default=["auto"], help="Claude entry modes to verify")
    parser.add_argument("--mixed", action="store_true", help="also install Codex when probing Claude")
    args = parser.parse_args()
    if any(shutil.which(tool) is None for tool in args.tools):
        parser.error("selected CLIs must already be installed")
    passed = True
    with CaptureServer() as server:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            for tool in args.tools:
                version = subprocess.run([tool, "--version"], capture_output=True, text=True, timeout=10)
                print(json.dumps({"tool": tool, "version": version.stdout.strip()}), flush=True)
                for scope in ("project", "user"):
                    for nested in (False, True):
                        entries = args.claude_entries if tool == "claude" else ["auto"]
                        for entry in entries:
                            passed = probe(tool, scope, server, nested,
                                           None if entry == "auto" else entry,
                                           args.mixed and tool == "claude") and passed
        finally:
            server.shutdown()
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
