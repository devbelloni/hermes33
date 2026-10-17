from fastapi import FastAPI, Request, HTTPException, Depends, Security
from fastapi.security import APIKeyHeader
from fastapi.responses import StreamingResponse
import httpx
import os
from typing import Optional

# ====================== CONFIGURAÇÃO DO SWAGGER ======================
app = FastAPI(
    title="GRD Infinity Artificial Intelitgence Secure API Gateway",
    description=""" 
    API segura para acessar a Inteligência Artificial da GRD Infinity com controle de autenticação.

    **Funcionalidades:**
    - Proxy completo para todas as rotas (`/api/chat`, `/api/generate`, `/api/models`, etc.)
    - Autenticação via API Key no header `X-API-Key`
    - Suporte a streaming
    - Rate limiting (pode ser adicionado depois)
    """,
    version="1.0.0",
    docs_url="/docs",           # Swagger UI → http://seu-ip:8000/docs
    redoc_url="/redoc",         # Documentação alternativa (Redoc)
    openapi_url="/openapi.json"
)

# Configurações do Ollama
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")

# API Keys permitidas (pode vir de variável de ambiente ou .env)
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
ALLOWED_API_KEYS = {k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()}
if not ALLOWED_API_KEYS:
    raise RuntimeError("API_KEYS environment variable is required (comma-separated list of keys)")

async def get_api_key(api_key: Optional[str] = Security(API_KEY_HEADER)):
    if not api_key or api_key.strip() not in ALLOWED_API_KEYS:
        raise HTTPException(
            status_code=401,
            detail="API Key inválida ou ausente. Use o header: X-API-Key"
        )
    return api_key


# ====================== PROXY PARA OLLAMA ======================
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_to_ollama(
    request: Request, 
    path: str, 
    api_key: str = Depends(get_api_key)
):
    """
    Proxy genérico que repassa todas as requisições para o Ollama.
    Funciona com chat, generate, models, tags, etc.
    """
    url = f"{OLLAMA_HOST}/{path.lstrip('/')}"
    
    # Remove headers desnecessários
    headers = {
        k: v for k, v in request.headers.items() 
        if k.lower() not in ["host", "x-api-key", "content-length"]
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=await request.body(),
        )

        # Suporte a streaming (importante para chat em tempo real)
        if "text/event-stream" in resp.headers.get("content-type", ""):
            return StreamingResponse(
                resp.aiter_bytes(),
                status_code=resp.status_code,
                headers=dict(resp.headers)
            )

        # Resposta normal (JSON ou texto)
        if resp.headers.get("content-type", "").startswith("application/json"):
            return resp.json()
        return resp.text


@app.get("/health", tags=["Status"])
async def health_check():
    """Verifica se a API está funcionando"""
    return {
        "status": "online",
        "ollama_backend": OLLAMA_HOST,
        "swagger": "/docs"
    }
