# Ollama Secure Gateway

![CI](https://github.com/devbelloni/hermes33/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)

An authenticated API gateway for a self-hosted [Ollama](https://ollama.com) server.
Ollama has no authentication of its own, so exposing it directly is unsafe. This gateway
keeps Ollama on a private Docker network and publishes only an API-key-protected FastAPI
proxy.

```
client ──► FastAPI gateway :8005  (X-API-Key check)
                 │
                 ▼   private Docker network
           Ollama :11434  (never published to the host)
```

## Features

- **Transparent proxy** for every Ollama route (`/api/chat`, `/api/generate`, `/api/tags`, ...),
  preserving method, path, query string, body and upstream status code.
- **API-key authentication** with the `X-API-Key` header; several keys are supported, which
  makes rotation easy. Keys are compared in **constant time** (`hmac.compare_digest`).
- **True response streaming**: chunks are forwarded as they arrive instead of being buffered,
  so chat tokens reach the client in real time.
- **Safe forwarding**: the client's key is never sent upstream, and hop-by-hop headers are
  removed in both directions.
- **Clear failure modes**: `401` for bad keys, `502` when the backend is unreachable.
- **No default secret**: the service refuses to start without `API_KEYS`.
- `GET /health` (public) and OpenAPI docs at `/docs`.
- Runs as a non-root user in Docker with a health check.

## Run it

```bash
cp .env.example .env
# edit .env: set API_KEYS to one or more long random keys, comma-separated
docker compose up -d --build
```

```bash
curl http://localhost:8005/api/tags -H "X-API-Key: <your key>"
```

Generate a strong key with `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

## Configuration

| Variable | Description | Default |
|---|---|---|
| `API_KEYS` | Comma-separated accepted keys (**required**) | none |
| `OLLAMA_HOST` | Ollama base URL | `http://ollama:11434` |
| `UPSTREAM_TIMEOUT` | Seconds to wait for Ollama | `300` |

## Development

```bash
pip install -r requirements.txt pytest ruff
pytest -q && ruff check .
uvicorn app.main:create_app --factory --reload     # needs API_KEYS in the environment
```

The test suite (10 tests) injects a fake upstream through `httpx.MockTransport`, so it needs
neither Ollama nor network access. It covers authentication, forwarding, streaming,
status propagation and the failure modes.

## Layout

```
app/
├── main.py     # application factory and proxy
└── config.py   # settings from environment
tests/
Dockerfile · docker-compose.yml · .env.example
```

## Roadmap

- [ ] Per-key rate limiting and usage metrics
- [ ] Structured request logging

## Author

**Márcio Belloni**, AI/ML Engineer.
[LinkedIn](https://www.linkedin.com/in/marcio-belloni/) · [GitHub](https://github.com/devbelloni)
