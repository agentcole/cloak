"""End-to-end proxy round trip against a mock upstream.

Skipped unless the proxy extra (fastapi/httpx/uvicorn) is installed. Verifies
that the provider only ever sees masked tokens (reported via booleans the proxy
won't rewrite) and that responses — sync and streamed — are restored.
"""

import importlib.util
import threading
import time

import pytest

_HAS_PROXY = all(importlib.util.find_spec(m) for m in ("fastapi", "httpx", "uvicorn", "starlette"))
pytestmark = pytest.mark.skipif(not _HAS_PROXY, reason="proxy extra not installed")


@pytest.fixture(scope="module")
def upstream_port():
    import uvicorn
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, StreamingResponse

    app = FastAPI()

    @app.post("/v1/chat/completions")
    async def chat(request: Request):
        body = await request.json()
        user = body["messages"][-1]["content"]
        return JSONResponse(
            {
                # Booleans — the proxy restores tokens, not these, so they
                # faithfully report what the upstream actually received.
                "saw_token": "[EMAIL_" in user,
                "saw_plain": "jane@acme.com" in user,
                "choices": [{"message": {"role": "assistant", "content": f"Reply about {user}"}}],
            }
        )

    @app.post("/v1/messages")
    async def messages(request: Request):
        # Anthropic-style: top-level `system` + message content blocks.
        body = await request.json()
        system = body.get("system", "")
        content = body["messages"][-1]["content"]
        if isinstance(content, list):
            content = " ".join(b.get("text", "") for b in content)
        combined = f"{system} {content}"
        return JSONResponse(
            {
                "saw_token": "[EMAIL_" in combined,
                "saw_plain": "jane@acme.com" in combined,
                "content": [{"type": "text", "text": f"Reply about {content}"}],
            }
        )

    @app.post("/v1/stream")
    async def stream(request: Request):
        body = await request.json()
        user = body["messages"][-1]["content"]

        async def gen():
            # Deliberately split the token across chunk boundaries.
            for piece in ["data: Re", f"ply {user[:4]}", f"{user[4:]}\n\n", "data: [DONE]\n\n"]:
                yield piece.encode()

        return StreamingResponse(gen(), media_type="text/event-stream")

    port = 8803
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield port
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def client(upstream_port):
    from starlette.testclient import TestClient

    from cloak import Cloak, CloakPolicy
    from cloak.proxy.server import build_app

    app = build_app(
        f"http://127.0.0.1:{upstream_port}",
        lambda: Cloak(CloakPolicy(detectors=["regex"])),
        restore=True,
    )
    return TestClient(app)


def _payload():
    return {"model": "gpt-4o", "messages": [{"role": "user", "content": "email jane@acme.com"}]}


def test_upstream_sees_only_masked_and_response_is_restored(client):
    data = client.post("/v1/chat/completions", json=_payload()).json()
    assert data["saw_token"] is True  # provider received the token
    assert data["saw_plain"] is False  # provider never saw the real email
    # ...but the caller gets the original back.
    assert data["choices"][0]["message"]["content"] == "Reply about email jane@acme.com"


def test_streaming_response_is_restored(client):
    resp = client.post("/v1/stream", json=_payload())
    assert "jane@acme.com" in resp.text
    assert "[EMAIL_1]" not in resp.text


def test_anthropic_system_and_content_blocks(client):
    payload = {
        "model": "claude-x",
        "system": "contact jane@acme.com",
        "messages": [{"role": "user", "content": [{"type": "text", "text": "and jane@acme.com"}]}],
    }
    data = client.post("/v1/messages", json=payload).json()
    assert data["saw_token"] is True  # both system + block masked upstream
    assert data["saw_plain"] is False
    assert "jane@acme.com" in data["content"][0]["text"]  # restored for the caller


def test_unreachable_upstream_returns_502():
    from starlette.testclient import TestClient

    from cloak import Cloak, CloakPolicy
    from cloak.proxy.server import build_app

    app = build_app(
        "http://127.0.0.1:9",  # discard port: connection refused
        lambda: Cloak(CloakPolicy(detectors=["regex"])),
        restore=True,
        connect_timeout=1.0,
    )
    resp = TestClient(app).post(
        "/v1/chat/completions", json={"messages": [{"role": "user", "content": "hi a@b.com"}]}
    )
    assert resp.status_code == 502
    assert resp.json()["error"]["type"] == "upstream_unreachable"
