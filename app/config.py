"""Settings read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    api_keys: frozenset[str]
    ollama_host: str = "http://ollama:11434"
    timeout: float = 300.0

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        env = dict(os.environ) if env is None else env
        keys = frozenset(k.strip() for k in env.get("API_KEYS", "").split(",") if k.strip())
        if not keys:
            raise RuntimeError("API_KEYS is required: a comma-separated list of accepted keys")
        return cls(
            api_keys=keys,
            ollama_host=env.get("OLLAMA_HOST", cls.ollama_host).rstrip("/"),
            timeout=float(env.get("UPSTREAM_TIMEOUT", cls.timeout)),
        )


__all__ = ["Settings", "field"]
