"""Provider abstraction — any OpenAI-compatible endpoint."""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from rw_promptforge.cache import EmbeddingCache


class Provider:
    """Minimal OpenAI-compatible chat-completions client.

    Works with: OpenAI API, OpenRouter, Groq, agentgateway, local vLLM, Ollama, etc.
    Any endpoint that serves /v1/chat/completions.
    """

    RETRY_STATUSES = {429, 500, 502, 503}

    def __init__(
        self,
        endpoint: str = "https://api.openai.com/v1",
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        max_retries: int = 3,
        embedding_model: str | None = None,
        rerank_model: str = "ms-marco-MiniLM-L-6-v2",
        cache: "EmbeddingCache | None" = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key or ""
        self.model = model
        self.max_retries = max_retries
        # bge-small-en-v1.5 is what RW_InferenceEngine serves locally (384-dim).
        # See ADR-010/012. On hard failure raise; caller catches and skips ML.
        self.embedding_model = embedding_model or os.environ.get(
            "RW_PROMPTFORGE_EMBEDDING_MODEL", "bge-small-en-v1.5"
        )
        self.rerank_model = rerank_model
        self._client = httpx.Client(timeout=httpx.Timeout(120.0))
        # Lazy import — numpy + cache only needed when ML mode is used.
        self._cache = cache

    def reflect(self, prompt: str, system: str | None = None) -> str:
        """Send a single reflection call with retry on transient errors."""
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        last_error: httpx.HTTPStatusError | None = None
        for attempt in range(self.max_retries):
            try:
                response = self._client.post(
                    f"{self.endpoint}/chat/completions",
                    headers=headers,
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": 0.3,
                        "max_tokens": 8000,
                    },
                )
                response.raise_for_status()
                data: dict[str, Any] = response.json()
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code in self.RETRY_STATUSES:
                    # Exponential backoff: 2s, 4s, 8s...
                    wait = 2 ** (attempt + 1)
                    print(f"  ⏳ Rate limited/error ({e.response.status_code}), retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                raise
        raise last_error  # type: ignore[misc]

    # ------------------------------------------------------------------
    # ML enhancement endpoints (OpenAI-compatible) — see ADR-010/012
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def embed(self, texts: list[str]):
        """Return embeddings for texts via ``POST /embeddings``.

        Uses the configured cache (if any) to avoid recomputing embeddings
        for identical (model, text) pairs. Returns an np.ndarray of shape
        ``(len(texts), dim)``. Raises on HTTP failure — callers in ML mode
        catch and fall back to token-based similarity.
        """
        import numpy as np  # noqa: PLC0415 — lazy: ML-only dependency

        if not texts:
            return np.zeros((0, 0), dtype=np.float32)

        results: list[tuple[float, ...] | None] = [None] * len(texts)
        missing_idx: list[int] = list(range(len(texts)))

        if self._cache is not None:
            cached, missing_idx = self._cache.get_many(self.embedding_model, texts)
            results = cached

        if missing_idx:
            response = self._client.post(
                f"{self.endpoint}/embeddings",
                headers=self._headers(),
                json={
                    "model": self.embedding_model,
                    "input": [texts[i] for i in missing_idx],
                },
            )
            response.raise_for_status()
            data = response.json()
            vectors = sorted(data["data"], key=lambda d: d["index"])
            if self._cache is not None:
                self._cache.set_many(
                    self.embedding_model,
                    [texts[i] for i in missing_idx],
                    [v["embedding"] for v in vectors],
                )
                self._cache.save()
            for i, v in zip(missing_idx, vectors):
                results[i] = tuple(v["embedding"])

        return np.array(results, dtype=np.float32)

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        """Return relevance scores for (query, document) pairs via ``POST /rerank``.

        Scores are returned in the same order as ``documents``. Raises on
        HTTP failure — callers catch and fall back to embedding similarity.
        """
        if not documents:
            return []
        response = self._client.post(
            f"{self.endpoint}/rerank",
            headers=self._headers(),
            json={
                "model": self.rerank_model,
                "query": query,
                "documents": documents,
            },
        )
        response.raise_for_status()
        data = response.json()
        # Support both {"results": [...]} and bare-list response shapes.
        items = data.get("results", data if isinstance(data, list) else [])
        ordered = sorted(items, key=lambda r: r.get("index", 0))
        return [float(r.get("relevance_score", r.get("score", 0.0))) for r in ordered]

    def close(self) -> None:
        self._client.close()

    @classmethod
    def from_env(cls, model: str = "gpt-4o-mini") -> Provider:
        """Build a Provider from environment variables.

        Reads from:
          - OPENAI_API_KEY (for https://api.openai.com/v1)
          - OPENAI_ENDPOINT (for custom endpoints)
          - OPENROUTER_API_KEY (for https://openrouter.ai/api/v1)
        """
        api_key = os.environ.get("OPENAI_API_KEY", "")
        endpoint = os.environ.get("OPENAI_ENDPOINT")
        if not endpoint:
            if os.environ.get("OPENROUTER_API_KEY"):
                api_key = os.environ["OPENROUTER_API_KEY"]
                endpoint = "https://openrouter.ai/api/v1"
            else:
                endpoint = "https://api.openai.com/v1"
        return cls(endpoint=endpoint, api_key=api_key, model=model)

    @classmethod
    def from_ml_env(cls) -> Provider:
        """Build a Provider pointed at the ML-capable endpoint (RW_InferenceEngine).

        Env vars:
          - ``RW_IE_ENDPOINT`` (default ``http://srv1:8300``)
          - ``RW_PROMPTFORGE_EMBEDDING_MODEL`` (default ``bge-small-en-v1.5``)
          - ``RW_IE_API_KEY`` (optional)
        """
        endpoint = os.environ.get("RW_IE_ENDPOINT", "http://srv1:8300")
        api_key = os.environ.get("RW_IE_API_KEY", "")
        provider = cls.__new__(cls)
        provider.endpoint = endpoint.rstrip("/") + "/v1"
        provider.api_key = api_key
        provider.model = ""  # not used for embed/rerank
        provider.max_retries = 3
        provider.embedding_model = os.environ.get(
            "RW_PROMPTFORGE_EMBEDDING_MODEL", "bge-small-en-v1.5"
        )
        provider.rerank_model = os.environ.get(
            "RW_IE_RERANK_MODEL", "ms-marco-MiniLM-L-6-v2"
        )
        provider._client = httpx.Client(timeout=httpx.Timeout(120.0))
        provider._cache = None
        return provider