"""Provider abstraction — any OpenAI-compatible endpoint."""

from __future__ import annotations

import os
from typing import Any

import httpx


class Provider:
    """Minimal OpenAI-compatible chat-completions client.

    Works with: OpenAI API, OpenRouter, Groq, agentgateway, local vLLM, Ollama, etc.
    Any endpoint that serves /v1/chat/completions.
    """

    def __init__(
        self,
        endpoint: str = "https://api.openai.com/v1",
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key or ""
        self.model = model
        self._client = httpx.Client(timeout=httpx.Timeout(120.0))

    def reflect(self, prompt: str, system: str | None = None) -> str:
        """Send a single reflection call and return the text response."""
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

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
        import os

        api_key = os.environ.get("OPENAI_API_KEY", "")
        endpoint = os.environ.get("OPENAI_ENDPOINT")
        if not endpoint:
            if os.environ.get("OPENROUTER_API_KEY"):
                api_key = os.environ["OPENROUTER_API_KEY"]
                endpoint = "https://openrouter.ai/api/v1"
            else:
                endpoint = "https://api.openai.com/v1"
        return cls(endpoint=endpoint, api_key=api_key, model=model)