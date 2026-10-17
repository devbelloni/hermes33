"""FastAPI application factory."""

from __future__ import annotations

import hmac
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader
from starlette.background import BackgroundTask

from . import __version__
from .config import Settings

HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers",
    "transfer-encoding", "upgrade", "host", "content-length",
}
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

DESCRIPTION = """
Authenticated gateway for a self-hosted [Ollama](https://ollama.com) server.

- Proxies every Ollama route (`/api/chat`, `/api/generate`, `/api/tags`, ...)
- Authenticates with the `X-API-Key` header (several keys supported)
- Streams responses without buffering them
"""


def create_app(settings: Settings | None = None, client: httpx.AsyncClient | None = None) -> FastAPI:
    """Build the app. ``settings`` and ``client`` can be injected, which keeps tests offline."""
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.client = client or httpx.AsyncClient(
            base_url=settings.ollama_host, timeout=settings.timeout
        )
        yield
        await app.state.client.aclose()

    app = FastAPI(title="Ollama Secure Gateway", description=DESCRIPTION, version=__version__, lifespan=lifespan)

    def require_api_key(api_key: str | None = Security(API_KEY_HEADER)) -> str:
        provided = (api_key or "").strip().encode()
        # Compare against every key in constant time to avoid leaking key prefixes via timing.
        matched = [hmac.compare_digest(provided, key.encode()) for key in settings.api_keys]
        if not provided or not any(matched):
            raise HTTPException(status_code=401, detail="Invalid or missing API key (header: X-API-Key)")
        return "ok"

    @app.get("/health", tags=["Status"])
    async def health() -> dict[str, str]:
        return {"status": "online", "ollama_backend": settings.ollama_host}

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"], dependencies=[Depends(require_api_key)])
    async def proxy(request: Request, path: str) -> StreamingResponse:
        headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP | {"x-api-key"}}
        upstream_request = request.app.state.client.build_request(
            request.method,
            f"/{path}",
            params=request.query_params,
            headers=headers,
            content=await request.body(),  # request bodies are small JSON; only responses are streamed
        )
        try:
            upstream = await request.app.state.client.send(upstream_request, stream=True)
        except httpx.RequestError as exc:
            detail = f"Ollama backend unreachable: {exc.__class__.__name__}"
            raise HTTPException(status_code=502, detail=detail) from exc
        response_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in HOP_BY_HOP}
        return StreamingResponse(
            upstream.aiter_raw(),
            status_code=upstream.status_code,
            headers=response_headers,
            background=BackgroundTask(upstream.aclose),
        )

    return app
