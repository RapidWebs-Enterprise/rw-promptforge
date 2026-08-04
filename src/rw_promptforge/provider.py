"""Provider abstraction — any OpenAI-compatible endpoint."""

from __future__ import annotations

import os
import time
from typing import Any

import httpx


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
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key or ""
        self.model = model
        self.max_retries = max_retries
        self._client = httpx.Client(timeout=httpx.Timeout(120.0))

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
                        "max_tokens": 4000,
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