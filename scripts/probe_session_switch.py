#!/usr/bin/env python3
"""Opt-in CLI integration probe: isolated homes and a loopback API dummy.

No real credentials, model calls, package installs or actual user settings.
Requires installed Claude/Codex CLIs and permission to bind a loopback socket.
"""

import argparse
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading

import install


class CaptureServer(http.server.ThreadingHTTPServer):
    def __init__(self):
        super().__init__(("127.0.0.1", 0), CaptureHandler)
        self.requests = []


class CaptureHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 2 * 1024 * 1024:
                raise ValueError("size")
            data = json.loads(self.rfile.read(size))
        except (ValueError, OSError):
            self.send_error(400)
            return
        if self.path.split("?", 1)[0] not in {"/responses", "/v1/messages"}:
            self.send_error(404)
            return
        self.server.requests.append(data)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        if self.path.startswith("/v1/messages"):
            message = {"id": "msg_probe", "type": "message", "role": "assistant",
                       "model": "claude-sonnet-4-6", "content": [], "stop_reason": None,
                       "usage": {"input_tokens": 1, "output_tokens": 1}}
            events = [
                {"type": "message_start", "message": message},
                {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
                {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "probe"}},
                {"type": "content_block_stop", "index": 0},
                {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None}, "usage": {"output_tokens": 1}},
                {"type": "message_stop"},
            ]
        else:
            item = {"type": "message", "id": "msg_probe", "role": "assistant",
                    "content": [{"type": "output_text", "text": "probe", "annotations": []}]}
            events = [
                {"type": "response.created", "response": {"id": "resp_probe"}},
                {"type": "response.output_item.done", "output_index": 0, "item": item},
                {"type": "response.completed", "response": {"id": "resp_probe", "status": "completed", "output": [item], "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}}},
            ]
        try:
            for event in events:
                self.wfile.write(("event: " + event["type"] + "\ndata: " + json.dumps(event) + "\n\n").encode())
        except BrokenPipeError:
            pass


def probe(tool, user, server):
    with tempfile.TemporaryDirectory(prefix="aiscb-cli-probe-") as directory:
        root = Path(directory)
        home, work = root / "home", root / "project"
        home.mkdir()
        work.mkdir()
        subprocess.run(["git", "init", "-q", str(work)], check=True, capture_output=True, timeout=10)
        config = home / f".{tool}"
        config.mkdir()
        user_instructions = config / ("CLAUDE.md" if tool == "claude" else "AGENTS.md")
        project_instructions = work / ("CLAUDE.md" if tool == "claude" else "AGENTS.md")
        if tool == "claude" or not user:
            user_instructions.write_text("OTHER_USER_MARKER\n")
        if tool == "claude" or user:
            project_instructions.write_text("OTHER_PROJECT_MARKER\nSEPARATE_OVERLAY_MARKER\n")
        # The project Codex loader occupies root AGENTS.md; nested rules remain additive.
        cwd = work
        if tool == "codex" and not user:
            cwd = work / "nested"
            cwd.mkdir()
            (cwd / "AGENTS.md").write_text("OTHER_PROJECT_MARKER\nSEPARATE_OVERLAY_MARKER\n")
        report = install.install_session_switch([tool], work, home if user else None)
        if any(line.startswith("blocked") for line in report):
            raise RuntimeError("fixture installation failed: " + str(report))
        url = f"http://127.0.0.1:{server.server_port}"
        env = {"PATH": os.environ["PATH"], "HOME": str(home), "LANG": "C.UTF-8"}
        if tool == "claude":
            env.update(CLAUDE_CONFIG_DIR=str(config), ANTHROPIC_BASE_URL=url,
                       ANTHROPIC_API_KEY="isolated-test-only", CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1")
            argv = ["claude", "-p", "Reply probe.", "--model", "claude-sonnet-4-6", "--tools", ""]
        else:
            env["CODEX_HOME"] = str(config)
            content = ('model="probe"\nmodel_provider="probe"\n'
                       + ('developer_instructions="OTHER_USER_MARKER"\n' if user else '')
                       + '[model_providers.probe]\nname="probe"\nbase_url=' + json.dumps(url)
                       + '\nwire_api="responses"\nrequires_openai_auth=false\n'
                       + '[projects.' + json.dumps(str(work)) + ']\ntrust_level="trusted"\n')
            (config / "config.toml").write_text(content)
            # Only this probe's reviewed, generated hooks exist in the isolated home/repo.
            # Production setup never bypasses Codex hook trust.
            argv = ["codex", "--dangerously-bypass-hook-trust", "exec", "Reply probe."]
        baseline = install.SOURCE.read_text()
        source = install.user_source(home) if user else work / install.BASELINE
        for value in ("0", "1", "invalid", "missing"):
            server.requests.clear()
            env["AISCB_DISABLE"] = "0" if value == "missing" else value
            if value == "missing":
                source.unlink()
            result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, timeout=35)
            request = json.dumps(server.requests)
            complete = all(json.dumps(baseline[i * 7000:(i + 1) * 7000])[1:-1] in request for i in range(4))
            other = all(marker in request for marker in ("OTHER_USER_MARKER", "OTHER_PROJECT_MARKER", "SEPARATE_OVERLAY_MARKER"))
            if value in {"invalid", "missing"}:
                ok = not server.requests
            elif value == "0":
                ok = result.returncode == 0 and complete and other
            else:
                ok = result.returncode == 0 and other and "aiscb-session-disabled" in request and "aiscb-ACCESS-001" not in request
            print(json.dumps({"tool": tool, "scope": "user" if user else "project",
                              "AISCB_DISABLE": value, "requests": len(server.requests),
                              "complete_baseline": complete, "other_instructions": other, "passed": ok}), flush=True)
            if not ok:
                raise RuntimeError("CLI context check failed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools", nargs="+", choices=("claude", "codex"), default=["claude", "codex"])
    args = parser.parse_args()
    for tool in args.tools:
        if shutil.which(tool) is None:
            parser.error(f"{tool} must already be installed")
    with CaptureServer() as server:
        server.timeout = 5
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            for tool in args.tools:
                version = subprocess.run([tool, "--version"], capture_output=True, text=True, timeout=10)
                print(version.stdout.strip(), flush=True)
                for user in (True, False):
                    probe(tool, user, server)
        finally:
            server.shutdown()


if __name__ == "__main__":
    main()
