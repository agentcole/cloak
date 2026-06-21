"""Round-trip masking reverse proxy.

Sits between your app and an LLM provider. On the way out it masks PII in the
request body (chat ``messages``, ``system``, ``prompt``/``input``); on the way
back it restores the original values in the response — including streamed SSE —
so the caller transparently gets real data while the provider only ever saw
tokens.

This is a privacy boundary, not a compression layer: point your client's base
URL at this proxy and set ``--upstream`` to the real provider.

Requires the ``proxy`` extra: ``pip install "cloak-llm[proxy]"``.
"""

# NOTE: intentionally NOT using ``from __future__ import annotations`` here.
# FastAPI resolves the route handler's annotations against this module's
# globals, but ``Request``/``Response`` are imported lazily inside ``build_app``
# (to keep fastapi an optional dependency). Stringized annotations would make
# FastAPI fail to find ``Request`` and treat it as a query parameter.

import json
from collections.abc import Callable

from ..engine import Cloak
from ..policy import CloakPolicy
from ..vault import Vault
from .streaming import StreamRestorer

# Headers we must not blindly forward.
_DROP_REQUEST_HEADERS = {"host", "content-length", "accept-encoding", "connection"}
_DROP_RESPONSE_HEADERS = {"content-length", "content-encoding", "transfer-encoding", "connection"}

# Body fields whose string values we mask, by API shape.
_STRING_FIELDS = ("prompt", "input", "suffix")


def _mask_body(cloak: Cloak, raw: bytes, content_type: str) -> tuple[bytes, Vault]:
    vault = Vault(salt=cloak._salt())
    if not raw or "json" not in (content_type or ""):
        return raw, vault
    try:
        body = json.loads(raw)
    except (ValueError, TypeError):
        return raw, vault
    if not isinstance(body, dict):
        return raw, vault

    acc: list = []
    if isinstance(body.get("messages"), list):
        body["messages"] = cloak.mask_messages(body["messages"], vault).messages
    if "system" in body:
        body["system"] = cloak._mask_content(body["system"], vault, acc)
    for field in _STRING_FIELDS:
        if isinstance(body.get(field), str):
            body[field] = cloak.mask_text(body[field], vault).text

    return json.dumps(body).encode(), vault


def _filter_headers(headers: dict[str, str], drop: set[str]) -> dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() not in drop}


def build_app(
    upstream: str,
    cloak_factory: Callable[[], Cloak],
    restore: bool = True,
    connect_timeout: float = 10.0,
):  # pragma: no cover - exercised via integration, not unit tests
    """Build the FastAPI proxy app.

    ``connect_timeout`` bounds how long we wait to reach the upstream; the read
    timeout is intentionally unbounded so long LLM streams aren't cut off.
    """
    import httpx
    from fastapi import FastAPI, Request, Response
    from fastapi.responses import JSONResponse, StreamingResponse
    from starlette.concurrency import run_in_threadpool

    upstream = upstream.rstrip("/")
    app = FastAPI(title="cloak-proxy")
    # read=None keeps streaming responses alive; connect/write/pool are bounded.
    timeout = httpx.Timeout(None, connect=connect_timeout, write=30.0, pool=30.0)
    client = httpx.AsyncClient(timeout=timeout)

    @app.api_route(
        "/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )
    async def proxy(request: Request, path: str) -> Response:
        raw = await request.body()
        cloak = cloak_factory()
        content_type = request.headers.get("content-type", "")
        # Detection (regex/NER) is CPU-bound and sync — run it off the event
        # loop so one request can't stall the whole proxy.
        masked, vault = await run_in_threadpool(_mask_body, cloak, raw, content_type)

        req_headers = _filter_headers(dict(request.headers), _DROP_REQUEST_HEADERS)
        req_headers["accept-encoding"] = "identity"  # keep bytes restorable

        url = f"{upstream}/{path}"
        upstream_req = client.build_request(
            request.method,
            url,
            params=dict(request.query_params),
            content=masked,
            headers=req_headers,
        )
        try:
            resp = await client.send(upstream_req, stream=True)
        except httpx.RequestError as exc:
            return JSONResponse(
                {"error": {"type": "upstream_unreachable", "message": str(exc)}},
                status_code=502,
            )
        resp_ctype = resp.headers.get("content-type", "")
        resp_headers = _filter_headers(dict(resp.headers), _DROP_RESPONSE_HEADERS)

        if restore and "event-stream" in resp_ctype:
            restorer = StreamRestorer(vault)

            async def stream():
                try:
                    async for chunk in resp.aiter_bytes():
                        out = restorer.feed(chunk.decode("utf-8", errors="replace"))
                        if out:
                            yield out.encode()
                    tail = restorer.flush()
                    if tail:
                        yield tail.encode()
                finally:
                    # Always release the upstream connection, even on client
                    # disconnect or mid-stream error.
                    await resp.aclose()

            return StreamingResponse(
                stream(),
                status_code=resp.status_code,
                headers=resp_headers,
                media_type=resp_ctype,
            )

        body = await resp.aread()
        await resp.aclose()
        if restore and ("json" in resp_ctype or "text" in resp_ctype):
            body = vault.restore(body.decode("utf-8", errors="replace")).encode()
        return Response(
            content=body,
            status_code=resp.status_code,
            headers=resp_headers,
            media_type=resp_ctype,
        )

    return app


def run(
    host: str = "127.0.0.1",
    port: int = 8788,
    upstream: str = "https://api.openai.com",
    strategy: str = "placeholder",
    detectors: list[str] | None = None,
    restore: bool = True,
    connect_timeout: float = 10.0,
) -> None:
    """Run the proxy with uvicorn."""
    import uvicorn

    dets = detectors or ["regex"]
    # One shared engine so heavy detectors (e.g. NER) load their model once.
    # Each request still gets its own Vault, so masking stays request-isolated.
    shared = Cloak(CloakPolicy(detectors=dets, strategy=strategy))

    app = build_app(upstream, lambda: shared, restore=restore, connect_timeout=connect_timeout)
    print(f"[cloak] proxy on http://{host}:{port}  ->  {upstream}  (restore={restore})")
    uvicorn.run(app, host=host, port=port)
