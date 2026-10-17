# Secure API Gateway for Self-Hosted LLMs (FastAPI + Ollama)

A small authenticated gateway that sits in front of an [Ollama](https://ollama.com) server
so a self-hosted LLM can be exposed safely. Ollama itself has no authentication, so it is
kept on the private Docker network and only the gateway is published.

## Features

- Transparent proxy for every Ollama route (`/api/chat`, `/api/generate`, `/api/tags`, ...)
- API-key authentication through the `X-API-Key` header (multiple keys supported)
- Streaming support (`text/event-stream`) for real-time chat
- `GET /health` endpoint and automatic Swagger/OpenAPI docs at `/docs`
- Docker Compose stack with optional NVIDIA GPU reservation for Ollama

## Architecture

```
client ──► FastAPI gateway :8005  (X-API-Key check)
                  │
                  ▼   private Docker network
            Ollama :11434  (not exposed to the host)
```

## Run it

```bash
cp .env.example .env
# edit .env: set API_KEYS to one or more long random keys, separated by commas
docker compose up -d --build
```

Call it:

```bash
curl http://localhost:8005/api/tags -H "X-API-Key: <your key>"
```

The gateway refuses to start without `API_KEYS`, so there is no default key.

## Configuration

| Variable | Description |
|---|---|
| `API_KEYS` | Comma-separated list of accepted API keys (required) |
| `OLLAMA_HOST` | Ollama base URL (default `http://ollama:11434`) |

## Roadmap

- [ ] Per-key rate limiting (`slowapi` is already a dependency)
- [ ] Request logging and usage metrics
- [ ] Automated tests

## Author

**Márcio Belloni**, AI/ML Engineer.
[LinkedIn](https://www.linkedin.com/in/marcio-belloni/) · [GitHub](https://github.com/devbelloni)
