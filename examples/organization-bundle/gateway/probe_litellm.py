#!/usr/bin/env python3
"""Opt-in integration check: real LiteLLM, loopback provider fixture, no paid model."""

import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import tempfile
import threading

import managed
import prepare
from test_managed import call, response

MODEL = "claude-sonnet-4-6"


class Provider(BaseHTTPRequestHandler):
    requests = []
    plain_reply = False

    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.requests.append(body)
        selecting = body.get("tool_choice", {}).get("name") == managed.TOOL
        result = response(["aiscb:llm-agents"])
        result["model"] = body["model"]
        if not selecting:
            result["content"] = [
                {
                    "type": "tool_use",
                    "id": "tool_client",
                    "name": "read_file",
                    "input": {"path": "app.py"},
                }
            ]
            if self.plain_reply:
                result["content"] = [
                    {"type": "text", "text": "Gateway fixture completed."}
                ]
                result["stop_reason"] = "end_turn"
        if body.get("stream"):
            block = result["content"][0]
            start = dict(result, content=[], stop_reason=None)
            initial_block = (
                dict(block, input={})
                if block["type"] == "tool_use"
                else dict(block, text="")
            )
            delta = (
                {"type": "input_json_delta", "partial_json": json.dumps(block["input"])}
                if block["type"] == "tool_use"
                else {"type": "text_delta", "text": block["text"]}
            )
            frames = [
                ("message_start", {"type": "message_start", "message": start}),
                (
                    "content_block_start",
                    {
                        "type": "content_block_start",
                        "index": 0,
                        "content_block": initial_block,
                    },
                ),
                (
                    "content_block_delta",
                    {"type": "content_block_delta", "index": 0, "delta": delta},
                ),
                ("content_block_stop", {"type": "content_block_stop", "index": 0}),
                (
                    "message_delta",
                    {
                        "type": "message_delta",
                        "delta": {
                            "stop_reason": result["stop_reason"],
                            "stop_sequence": None,
                        },
                        "usage": {"output_tokens": 10},
                    },
                ),
                ("message_stop", {"type": "message_stop"}),
            ]
            raw = "".join(
                f"event: {name}\ndata: {json.dumps(value)}\n\n"
                for name, value in frames
            ).encode()
        else:
            raw = json.dumps(result).encode()
        self.send_response(200)
        self.send_header(
            "Content-Type",
            "text/event-stream" if body.get("stream") else "application/json",
        )
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


async def check(root, port):
    # Artificial credentials exist only in this isolated process and fixture.
    key = "sk-" + secrets.token_hex(24)
    config = root / "litellm.yaml"
    config.write_text(
        f"model_list:\n  - model_name: {MODEL}\n    litellm_params:\n"
        "      model: anthropic/claude-sonnet-4-20250514\n"
        f"      api_base: http://127.0.0.1:{port}\n"
        "      api_key: os.environ/AISCB_FIXTURE_PROVIDER_KEY\n"
        "general_settings:\n  master_key: os.environ/LITELLM_MASTER_KEY\n"
        "litellm_settings:\n  turn_off_message_logging: true\n"
    )
    policy = root / "policy"
    digest = prepare.prepare(policy)
    os.environ.update(
        CONFIG_FILE_PATH=str(config),
        LITELLM_MASTER_KEY=key,
        AISCB_FIXTURE_PROVIDER_KEY=secrets.token_hex(24),
        AISCB_POLICY_ROOT=str(policy),
        AISCB_POLICY_SHA256=digest,
        LITELLM_LOCAL_MODEL_COST_MAP="True",
    )
    gateway = managed.create_app()
    from litellm.proxy.proxy_server import app

    headers = [
        (b"authorization", ("Bearer " + key).encode()),
        (b"content-type", b"application/json"),
        (b"anthropic-version", b"2023-06-01"),
    ]
    async with app.router.lifespan_context(app):
        for stream in (False, True):
            request = {
                "model": MODEL,
                "max_tokens": 100,
                "stream": stream,
                "messages": [{"role": "user", "content": "Build an agent"}],
                "tools": [
                    {
                        "name": "read_file",
                        "description": "Read a file",
                        "input_schema": {
                            "type": "object",
                            "properties": {"path": {"type": "string"}},
                            "required": ["path"],
                        },
                    }
                ],
            }
            before = len(Provider.requests)
            events = await call(gateway, request, headers=headers)
            assert events[0]["status"] == 200, events[0]["status"]
            raw = b"".join(e.get("body", b"") for e in events)
            assert b"read_file" in raw and managed.TOOL.encode() not in raw
            selected, final = Provider.requests[before:]
            assert managed.TOOL == selected["tools"][0]["name"]
            assert "[aiscb-AGENTAUTH-001]" not in str(selected["system"])
            assert "[aiscb-AGENTAUTH-001]" in str(final["system"])
            assert "[aiscb-LLM-001]" in str(final["system"])
            assert final["tools"] == request["tools"]
            assert final["messages"] == request["messages"]
            assert bool(final.get("stream")) == stream
            print("PASS real LiteLLM selection + client tool, stream=" + str(stream))
        before = len(Provider.requests)
        denied = await call(
            gateway,
            headers=[
                (b"authorization", b"Bearer isolated-invalid-key"),
                (b"content-type", b"application/json"),
            ],
        )
        # Without a DB LiteLLM can return a server error for unknown virtual keys;
        # the required property is refusal without a provider request.
        assert denied[0]["status"] in (401, 403, 502), denied[0]["status"]
        assert len(Provider.requests) == before
        print("PASS real LiteLLM rejects invalid identity before provider call")
        if shutil.which("claude"):
            await check_cli(gateway, root, key)
    from litellm.llms.custom_httpx.async_client_cleanup import (
        close_litellm_async_clients,
    )

    await close_litellm_async_clients()


async def check_cli(gateway, root, key):
    import uvicorn

    Provider.plain_reply = True
    home, work = root / "home", root / "work"
    home.mkdir()
    work.mkdir()
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(gateway, lifespan="off", log_level="error"))
    task = asyncio.create_task(server.serve(sockets=[sock]))
    process = None
    try:
        while not server.started:
            if task.done():
                await task
            await asyncio.sleep(0.01)
        env = {
            "PATH": os.environ["PATH"],
            "HOME": str(home),
            "LANG": "C.UTF-8",
            "CI": "true",
            "CLAUDE_CONFIG_DIR": str(home / ".claude"),
            "ANTHROPIC_API_KEY": key,
            "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{port}",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        }
        process = await asyncio.create_subprocess_exec(
            "claude",
            "-p",
            "Reply with a short sentence.",
            "--model",
            MODEL,
            "--tools",
            "",
            "--strict-mcp-config",
            "--no-session-persistence",
            env=env,
            cwd=work,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), 45)
        assert process.returncode == 0 and b"Gateway fixture completed." in stdout, (
            process.returncode,
            stderr.decode(),
            stdout.decode(),
        )
        print("PASS real Claude Code through gateway + LiteLLM + loopback provider")
    finally:
        if process and process.returncode is None:
            process.kill()
            await process.wait()
        server.should_exit = True
        await task
        sock.close()


def main():
    from importlib.metadata import version

    print("LiteLLM " + version("litellm"))
    with tempfile.TemporaryDirectory(prefix="aiscb-litellm-probe-") as tmp:
        path = os.environ["PATH"]
        os.environ.clear()
        os.environ.update(
            PATH=path,
            HOME=tmp,
            LANG="C.UTF-8",
            DO_NOT_TRACK="1",
            LITELLM_TELEMETRY="False",
            LITELLM_LOCAL_MODEL_COST_MAP="True",
        )
        server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            asyncio.run(check(Path(tmp), server.server_port))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    main()
