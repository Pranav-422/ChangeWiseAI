"""The real Google Gen AI SDK against a local HTTP server: request format, retries, failures. No live call is made."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from member3.ai.provider import GeminiProvider, ProviderError


def reply(text):
    return 200, {"id": "int_1", "status": "completed", "model": "some-model", "usage": {"total_tokens": 42},
                 "steps": [{"type": "model_output", "content": [{"type": "text", "text": text}]}]}


@pytest.fixture
def server():
    state = {"answers": [], "requests": []}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["requests"].append((self.path, dict(self.headers.items()), body))
            status, content = state["answers"].pop(0) if len(state["answers"]) > 1 else state["answers"][0]
            data = content.encode() if isinstance(content, str) else json.dumps(content).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_):
            pass
    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=http.serve_forever, daemon=True).start()
    state["url"] = f"http://127.0.0.1:{http.server_port}"
    yield state
    http.shutdown()


def provider(server, timeout=5):
    return GeminiProvider("secret-key", "some-model", timeout, base_url=server["url"])


def test_request_follows_the_documented_structured_output_format(server):
    server["answers"] = [reply('{"a": 1}')]
    schema = {"type": "object", "properties": {"a": {"type": "integer"}}}
    assert provider(server).complete_json("hello", schema) == {"a": 1}
    path, headers, body = server["requests"][0]
    assert path.split("?")[0].endswith("/interactions") and "secret-key" not in path
    assert {k.lower(): v for k, v in headers.items()}["x-goog-api-key"] == "secret-key"
    assert body["model"] == "some-model" and body["input"] == "hello" and body["store"] is False
    wanted = body["response_format"]
    wanted = wanted[0] if isinstance(wanted, list) else wanted
    assert wanted == {"type": "text", "mime_type": "application/json", "schema": schema}


def test_temporary_failure_is_retried_once(server):
    server["answers"] = [(503, {"error": {"message": "busy"}}), reply('{"ok": true}')]
    assert provider(server).complete_json("x") == {"ok": True}


@pytest.mark.parametrize("answer", [
    (429, {"error": {"message": "quota"}}), (400, {"error": {"message": "bad schema secret-key"}}),
    (403, {"error": {"message": "no"}}), reply("not json"), reply("[1, 2]"), reply(""), (200, "garbage"), (200, {})])
def test_every_failure_becomes_a_provider_error_without_the_key(server, answer):
    server["answers"] = [answer]
    with pytest.raises(ProviderError) as raised:
        provider(server).complete_json("x")
    assert "secret-key" not in str(raised.value)
    assert len(server["requests"]) <= GeminiProvider.ATTEMPTS


def test_unreachable_server(server):
    with pytest.raises(ProviderError):
        GeminiProvider("secret-key", "some-model", 2, base_url="http://127.0.0.1:9").complete_json("x")
