# ADR-003: Any OpenAI-Compatible Endpoint

**Date:** 2026-08-03
**Status:** Accepted

## Context

We need an LLM for the reflection step. The user explicitly requested
support for "any OpenAI-compatible endpoint." This is a smart constraint:
it means no vendor lock-in, independence from any single API key, and
the ability to run against agentgateway (which already routes all of our
providers) as well as local vLLM/Ollama for no-network scenarios.

## Decision

**httpx-based `/v1/chat/completions` client using environment variables for API key.**

The `Provider` class:
- Accepts any endpoint URL
- Sends standard `POST /v1/chat/completions` payload
- Authenticates via `Authorization: Bearer` header (detected from env)
- Automatically prioritizes: `OPENROUTER_API_KEY` → `OPENAI_API_KEY` → `CUSTOM_API_KEY` → none (if endpoint doesn't require auth)

## Why

1. **Universality:** Every major provider now supports OpenAI-compatible
   endpoints: OpenRouter, Groq, Gemma OpenID-compat layer, Mistral,
   Together, NVIDIA, local vLLM/Ollama. No special adapters needed.
2. **Agent gateway passthrough:** `rw-agentgateway` already routes all
   our providers and handles rate limiting. The endpoint becomes
   `http://infra:8010/v1`.
3. **No dependency:** We don't need `openai` Python SDK (heavy), just
   `httpx` (already standard for modern Python HTTP).
4. **Walk-away freedom:** if a provider rate-limits or goes down, we
   switch the endpoint flag.

## Implementation

```python
Provider(endpoint="https://api.openai.com/v1", model="gpt-4o-mini")
    # reads OPENAI_API_KEY
Provider(endpoint="https://openrouter.ai/api/v1", model="anthropic/claude-sonnet-4")
    # reads OPENROUTER_API_KEY
Provider(endpoint="http://infra:8010/v1", model="gemini/gemini-2.5-pro")
    # agentgateway provider routing, x-api-key header
```

The user either passes `--provider=openai|openrouter|custom` or
explicit `--endpoint` + `--model`. The cli resolves the key
from env vars.

## Rejected

- **Dedicated per-provider clients** (openai.Client, anthropic.Client,
  etc.) — multiple deps, maintenance burden, no advantage for this
  simple request/response pattern.
- **Bundling with an LLM framework** (LangChain, DSPy) — heavyweight,
  unnecessary dependencies for a single chat-completions post.