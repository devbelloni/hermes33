import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

KEY = "test-key-1"


def reply(status: int, body: bytes, content_type: str = "application/json") -> httpx.Response:
    """Build a response that behaves like a real network stream (``json=`` is pre-read by MockTransport)."""
    return httpx.Response(status, headers={"content-type": content_type}, stream=httpx.ByteStream(body))


def make_client(handler):
    upstream = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://ollama:11434")
    app = create_app(Settings(api_keys=frozenset({KEY, "other-key"})), client=upstream)
    return TestClient(app)


def echo(request: httpx.Request) -> httpx.Response:
    payload = {
        "method": request.method,
        "path": request.url.path,
        "query": request.url.query.decode(),
        "body": request.content.decode(),
        "has_api_key_header": "x-api-key" in request.headers,
    }
    return reply(200, json.dumps(payload).encode())


def test_health_is_public():
    with make_client(echo) as client:
        body = client.get("/health").json()
    assert body["status"] == "online"


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "wrong"}, {"X-API-Key": ""}])
def test_rejects_missing_or_wrong_key(headers):
    with make_client(echo) as client:
        assert client.get("/api/tags", headers=headers).status_code == 401


def test_accepts_any_configured_key():
    with make_client(echo) as client:
        for key in (KEY, "other-key"):
            assert client.get("/api/tags", headers={"X-API-Key": key}).status_code == 200


def test_forwards_method_path_query_and_body_but_not_the_key():
    with make_client(echo) as client:
        r = client.post("/api/chat?stream=false", content='{"model":"llama3"}', headers={"X-API-Key": KEY})
    data = r.json()
    assert data == {
        "method": "POST",
        "path": "/api/chat",
        "query": "stream=false",
        "body": '{"model":"llama3"}',
        "has_api_key_header": False,
    }


def test_streams_response_chunks():
    def stream(_request):
        return reply(200, b'{"a":1}\n{"a":2}\n', "application/x-ndjson")

    with make_client(stream) as client:
        r = client.post("/api/generate", headers={"X-API-Key": KEY})
    assert r.text.splitlines() == ['{"a":1}', '{"a":2}']


def test_upstream_status_is_preserved():
    with make_client(lambda _r: reply(404, b'{"error": "model not found"}')) as client:
        r = client.post("/api/chat", headers={"X-API-Key": KEY})
    assert r.status_code == 404 and r.json()["error"] == "model not found"


def test_unreachable_backend_returns_502():
    def boom(_request):
        raise httpx.ConnectError("down")

    with make_client(boom) as client:
        assert client.get("/api/tags", headers={"X-API-Key": KEY}).status_code == 502


def test_settings_require_api_keys():
    with pytest.raises(RuntimeError, match="API_KEYS"):
        Settings.from_env({})
    assert Settings.from_env({"API_KEYS": " a, b ,,"}).api_keys == frozenset({"a", "b"})
