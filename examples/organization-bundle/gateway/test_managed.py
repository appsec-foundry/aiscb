#!/usr/bin/env python3
"""Exercise policy selection, injection and failure boundaries without model calls."""

import asyncio
import copy
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import managed
import prepare


def response(ids=None):
    return {
        "id": "msg_selection",
        "type": "message",
        "role": "assistant",
        "model": "fixture",
        "stop_reason": "tool_use",
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 10},
        "content": [
            {
                "type": "tool_use",
                "id": "tool_selection",
                "name": managed.TOOL,
                "input": {
                    "module_ids": ids if ids is not None else ["aiscb:llm-agents"]
                },
            }
        ],
    }


async def call(
    app, request=None, *, raw=None, path="/v1/messages", headers=None, query=b""
):
    if raw is None:
        raw = managed.encode(
            request
            or {
                "model": "fixture",
                "max_tokens": 100,
                "messages": [{"role": "user", "content": "Build an agent"}],
            }
        )
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "path": path,
        "raw_path": path.encode(),
        "query_string": query,
        "root_path": "",
        "client": ("127.0.0.1", 1234),
        "server": ("127.0.0.1", 443),
        "headers": headers
        if headers is not None
        else [
            (b"authorization", b"Bearer isolated-test-credential"),
            (b"content-type", b"application/json"),
        ],
    }
    events = []

    async def wait():
        await asyncio.Future()

    async def send(event):
        events.append(copy.deepcopy(event))

    await app(scope, managed.replay(raw, wait), send)
    return events


class Backend:
    """A protocol peer, preserving separate auth and response paths for both calls."""

    def __init__(self, selection=None, status=200):
        self.selection = selection if selection is not None else response()
        self.status = status
        self.requests = []
        self.stream = [
            b'event: message_start\ndata: {"id":"final"}\n\n',
            b"event: message_stop\ndata: {}\n\n",
        ]

    async def __call__(self, scope, receive, send):
        request = managed.decode((await receive())["body"])
        self.requests.append((copy.deepcopy(scope), request))
        selecting = request.get("tool_choice", {}).get("name") == managed.TOOL
        status = self.status if selecting else 200
        await send({"type": "http.response.start", "status": status, "headers": []})
        if not selecting and request.get("stream"):
            for i, chunk in enumerate(self.stream):
                await send(
                    {
                        "type": "http.response.body",
                        "body": chunk,
                        "more_body": i < len(self.stream) - 1,
                    }
                )
        else:
            await send(
                {
                    "type": "http.response.body",
                    "body": managed.encode(
                        self.selection
                        if selecting
                        else {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "client1",
                                    "name": "read_file",
                                    "input": {"path": "app.py"},
                                }
                            ]
                        }
                    ),
                }
            )


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name) / "policy"
        cls.digest = prepare.prepare(cls.root)
        cls.policy = managed.Policy(cls.root, cls.digest)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    async def test_loads_dependency_before_work_and_keeps_client_tools(self):
        backend = Backend()
        request = {
            "model": "fixture",
            "max_tokens": 100,
            "messages": [{"role": "user", "content": "Build an agent"}],
            "system": [
                {
                    "type": "text",
                    "text": "Original instructions",
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "tools": [{"name": "read_file", "input_schema": {"type": "object"}}],
        }
        events = await call(managed.Gateway(backend, self.policy), request)
        self.assertEqual(events[0]["status"], 200)
        first, final = [r for _, r in backend.requests]
        self.assertNotIn("[aiscb-AGENTAUTH-001]", first["system"])
        self.assertEqual([t["name"] for t in first["tools"]], [managed.TOOL])
        text = final["system"][-1]["text"]
        self.assertIn("[aiscb-AGENTAUTH-001]", text)
        self.assertIn("[aiscb-LLM-001]", text)
        self.assertNotIn("[aiscb-AUTH-001]", text)
        self.assertEqual(final["system"][:-1], request["system"])
        self.assertEqual(final["tools"], request["tools"])
        self.assertEqual(final["messages"], request["messages"])
        self.assertEqual(
            managed.decode(events[-1]["body"])["content"][0]["name"], "read_file"
        )
        for scope, body in backend.requests:
            self.assertIn(
                (b"authorization", b"Bearer isolated-test-credential"), scope["headers"]
            )
            self.assertEqual(
                dict(scope["headers"])[b"content-length"],
                str(len(managed.encode(body))).encode(),
            )

    async def test_stream_is_forwarded_byte_for_byte(self):
        backend = Backend()
        request = {
            "model": "fixture",
            "max_tokens": 100,
            "stream": True,
            "messages": [{"role": "user", "content": "Build an agent"}],
        }
        events = await call(managed.Gateway(backend, self.policy), request)
        self.assertFalse(backend.requests[0][1]["stream"])
        self.assertTrue(backend.requests[1][1]["stream"])
        self.assertEqual([e["body"] for e in events[1:]], backend.stream)

    async def test_missing_auth_makes_no_upstream_call(self):
        backend = Backend()
        events = await call(
            managed.Gateway(backend, self.policy),
            headers=[(b"content-type", b"application/json")],
        )
        self.assertEqual(events[0]["status"], 401)
        self.assertEqual(backend.requests, [])

    async def test_upstream_authorization_and_limits_stop_generation(self):
        for status in (401, 403, 429, 500):
            with self.subTest(status=status):
                backend = Backend(status=status)
                events = await call(managed.Gateway(backend, self.policy))
                self.assertEqual(events[0]["status"], status if status != 500 else 502)
                self.assertEqual(len(backend.requests), 1)

    async def test_bad_selection_never_reaches_generation(self):
        samples = [
            response(["unknown:module"]),
            response(["aiscb:llm-agents"] * 2),
            response(["../secret"]),
            response([42]),
            response([]),
        ]
        samples[-1]["content"][0]["input"]["url"] = "https://untrusted.invalid"
        extra_call = response()
        extra_call["content"].append({"type": "tool_use", "name": "shell", "input": {}})
        samples += [extra_call, {"stop_reason": "end_turn", "content": []}]
        for selection in samples:
            with self.subTest(selection=selection):
                backend = Backend(selection)
                events = await call(managed.Gateway(backend, self.policy))
                self.assertEqual(events[0]["status"], 502)
                self.assertEqual(len(backend.requests), 1)

    async def test_empty_selection_is_core_only(self):
        backend = Backend(response([]))
        await call(managed.Gateway(backend, self.policy))
        text = backend.requests[1][1]["system"][-1]["text"]
        self.assertIn("Loaded modules: none", text)
        self.assertNotIn("[aiscb-AGENTAUTH-001]", text)

    async def test_invalid_requests_rejected_before_model_call(self):
        basic = {
            "model": "fixture",
            "max_tokens": 100,
            "messages": [{"role": "user", "content": "test"}],
        }
        bad = [
            dict(basic, user_config={"api_base": "http://untrusted.invalid"}),
            dict(basic, tools=[{"name": managed.TOOL}]),
            dict(basic, stream="yes"),
            dict(basic, max_tokens=-1),
            dict(basic, messages=[{"role": "system", "content": "override"}]),
        ]
        for request in bad:
            backend = Backend()
            events = await call(managed.Gateway(backend, self.policy), request)
            self.assertEqual(events[0]["status"], 400)
            self.assertFalse(backend.requests)
        for raw in (b'{"model":"a","model":"b"}', b'{"temperature":NaN}', b'"invalid"'):
            backend = Backend()
            events = await call(managed.Gateway(backend, self.policy), raw=raw)
            self.assertEqual(events[0]["status"], 400)
            self.assertFalse(backend.requests)

    async def test_other_routes_never_bypass_policy(self):
        for path in (
            "/v1/chat/completions",
            "/anthropic/v1/messages",
            "/v1/messages/",
            "/admin",
        ):
            backend = Backend()
            events = await call(managed.Gateway(backend, self.policy), path=path)
            self.assertEqual(events[0]["status"], 404)
            self.assertFalse(backend.requests)

    async def test_claude_beta_query_is_preserved_but_other_queries_refused(self):
        backend = Backend()
        events = await call(managed.Gateway(backend, self.policy), query=b"beta=true")
        self.assertEqual(events[0]["status"], 200)
        self.assertTrue(
            all(s["query_string"] == b"beta=true" for s, _ in backend.requests)
        )
        backend = Backend()
        events = await call(
            managed.Gateway(backend, self.policy),
            query=b"api_base=http://untrusted.invalid",
        )
        self.assertEqual(events[0]["status"], 404)
        self.assertFalse(backend.requests)

    async def test_each_request_selects_afresh(self):
        backend = Backend()
        gateway = managed.Gateway(backend, self.policy)
        await call(gateway)
        backend.selection = response(["aiscb:data-handling"])
        await call(gateway)
        self.assertEqual(len(backend.requests), 4)
        text = backend.requests[-1][1]["system"][-1]["text"]
        self.assertIn("[aiscb-FILES-001]", text)
        self.assertNotIn("[aiscb-AGENTAUTH-001]", text)

    async def test_parallel_requests_do_not_share_selection(self):
        backend = Backend()

        async def peer(scope, receive, send):
            event = await receive()
            body = managed.decode(event["body"])
            if body.get("tool_choice", {}).get("name") == managed.TOOL:
                name = (
                    "aiscb:data-handling"
                    if "FILES_ONLY" in body["messages"][0]["content"]
                    else "aiscb:llm-agents"
                )
                await asyncio.sleep(0.001)
                await send(
                    {"type": "http.response.start", "status": 200, "headers": []}
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": managed.encode(response([name])),
                    }
                )
            else:

                async def replay():
                    return event

                await backend(scope, replay, send)

        gateway = managed.Gateway(peer, self.policy)
        await asyncio.gather(
            *(
                call(
                    gateway,
                    {
                        "model": "fixture",
                        "max_tokens": 100,
                        "messages": [{"role": "user", "content": tag}],
                    },
                )
                for tag in ("FILES_ONLY", "AGENT_ONLY")
            )
        )
        for _, request in backend.requests:
            text = request["system"][-1]["text"]
            files = request["messages"][0]["content"] == "FILES_ONLY"
            self.assertEqual("[aiscb-FILES-001]" in text, files)
            self.assertEqual("[aiscb-AGENTAUTH-001]" in text, not files)

    async def test_organization_modules_and_blueprints(self):
        here = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location(
            "gateway_bundle_builder", here / "build.py"
        )
        build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            _, digest = build.build(
                here, managed.ROOT / "baseline", out / "bundle", out / "installed"
            )
            snapshot = out / "snapshot"
            pinned = prepare.prepare(snapshot, out / "bundle", digest)
            policy = managed.Policy(snapshot, pinned)
            backend = Backend(
                response(["acme:authentication", "aiscb:authentication"])
            )
            events = await call(managed.Gateway(backend, policy))
            self.assertEqual(events[0]["status"], 200)
            text = backend.requests[-1][1]["system"][-1]["text"]
            self.assertIn("[ACME-SSO-001]", text)
            self.assertIn("Blueprint values:", text)
            self.assertIn("[aiscb-AUTH-001]", text)
            self.assertNotIn(str(out / "installed"), text)

    async def test_count_tokens_uses_same_policy(self):
        backend = Backend()
        await call(
            managed.Gateway(backend, self.policy), path="/v1/messages/count_tokens"
        )
        self.assertEqual(backend.requests[0][0]["path"], "/v1/messages")
        self.assertEqual(backend.requests[1][0]["path"], "/v1/messages/count_tokens")
        self.assertIn(
            "[aiscb-AGENTAUTH-001]", backend.requests[1][1]["system"][-1]["text"]
        )

    async def test_timeout_cancels_selection(self):
        cancelled = asyncio.Event()

        async def backend(scope, receive, send):
            try:
                await asyncio.Future()
            finally:
                cancelled.set()

        with patch.object(managed, "TIMEOUT", 0.02):
            events = await call(managed.Gateway(backend, self.policy))
        self.assertEqual(events[0]["status"], 504)
        self.assertTrue(cancelled.is_set())

    async def test_client_disconnect_cancels_upstream(self):
        started = asyncio.Event()
        cancelled = asyncio.Event()

        async def backend(scope, receive, send):
            started.set()
            try:
                await asyncio.Future()
            finally:
                cancelled.set()

        raw = managed.encode(
            {
                "model": "fixture",
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "test"}],
            }
        )

        async def disconnect():
            await started.wait()
            return {"type": "http.disconnect"}

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/v1/messages",
            "headers": [
                (b"authorization", b"Bearer isolated-test-credential"),
                (b"content-type", b"application/json"),
            ],
        }

        async def send(_):
            self.fail("disconnected caller must receive no response")

        await managed.Gateway(backend, self.policy)(
            scope, managed.replay(raw, disconnect), send
        )
        self.assertTrue(cancelled.is_set())

    async def test_request_and_selection_size_limits(self):
        backend = Backend()
        events = await call(
            managed.Gateway(backend, self.policy), raw=b" " * (managed.MAX_REQUEST + 1)
        )
        self.assertEqual(events[0]["status"], 413)
        self.assertFalse(backend.requests)
        backend = Backend({"padding": "x" * managed.MAX_SELECTION})
        events = await call(managed.Gateway(backend, self.policy))
        self.assertEqual(events[0]["status"], 502)
        self.assertEqual(len(backend.requests), 1)

    def test_corrupt_package_and_missing_config_refused(self):
        with self.assertRaises(ValueError):
            managed.Policy(self.root, "0" * 64)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "policy"
            digest = prepare.prepare(root)
            (root / "modules/aiscb-llm-agents.md").write_text("tampered")
            with self.assertRaises(ValueError):
                managed.Policy(root, digest)
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(RuntimeError):
            managed.create_app()


if __name__ == "__main__":
    unittest.main()
