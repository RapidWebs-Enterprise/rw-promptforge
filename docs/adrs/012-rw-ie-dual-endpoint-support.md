# ADR-012: Leveraging RW_InferenceEngine for Both Embeddings and Reranking

**Date:** 2026-09-14  
**Status:** Accepted  
**Context:** Need embedding and reranking capabilities for ML-enhanced optimization

## Decision

Use RW_InferenceEngine (already deployed at `http://srv1:8300`) as the sole provider for both:
- `POST /v1/embeddings` — Semantic vector embeddings (BGE 384-dim)
- `POST /v1/rerank` — Cross-encoder relevance scoring

Do NOT add separate sentence-transformers or cross-encoder dependencies.

## Rationale

1. **Already deployed:** RW_IE runs on infra VM, serves both endpoints
2. **OpenAI-compatible:** Same API contract, easy to integrate
3. **Zero marginal cost:** No additional API calls, no new infrastructure
4. **Simpler dependency tree:** Remove `sentence-transformers` and `cross-encoder` from optional deps
5. **Consistent with architecture:** Follows existing pattern of leveraging shared infrastructure

## Architecture

```
rw-promptforge → Provider.embed() → http://srv1:8300/v1/embeddings
rw-promptforge → Provider.rerank() → http://srv1:8300/v1/rerank
```

## Implementation

### Provider Extension

```python
class Provider:
    def embed(self, texts: list[str]) -> np.ndarray:
        """Get embeddings via /v1/embeddings endpoint."""
        response = self._client.post(
            f"{self.endpoint}/v1/embeddings",
            headers=self._headers(),
            json={"model": self.embedding_model, "input": texts},
        )
        data = response.json()
        return np.array([d["embedding"] for d in data["data"]])
    
    def rerank(self, query: str, documents: list[str]) -> list[float]:
        """Rerank documents via /v1/rerank endpoint."""
        response = self._client.post(
            f"{self.endpoint}/v1/rerank",
            headers=self._headers(),
            json={"model": self.reranker_model, "query": query, "documents": documents},
        )
        data = response.json()
        return [r["relevance_score"] for r in data.get("results", [])]
```

### Configuration

```python
# Default endpoints (configurable via CLI flags)
EMBEDDING_ENDPOINT = os.getenv("RW_IE_EMBEDDING_ENDPOINT", "http://srv1:8300")
EMBEDDING_MODEL = os.getenv("RW_IE_EMBEDDING_MODEL", "bge-small-en-v1.5")
RERANKER_ENDPOINT = os.getenv("RW_IE_RERANK_ENDPOINT", "http://srv1:8300")
RERANKER_MODEL = os.getenv("RW_IE_RERANK_MODEL", "ms-marco-MiniLM-L-6-v2")
```

### CLI Flags

```bash
--embedding-endpoint  Override embedding endpoint (default: http://srv1:8300)
--embedding-model     Override embedding model name
--rerank-endpoint     Override reranking endpoint
--rerank-model        Override reranking model name
```

## Consequences

- **Positive:** Simpler dependency tree (4 packages vs 6)
- **Positive:** No model downloads (~200MB saved)
- **Positive:** Centralized model management via RW_IE
- **Negative:** Dependency on RW_IE availability
- **Negative:** Limited to models served by RW_IE (can't easily swap models)

## Fallback Strategy

If RW_IE is unavailable:
1. Log warning: `⚠️ RW_InferenceEngine unavailable, skipping ML enhancement`
2. Continue with token-based methods (Jaccard + SequenceMatcher)
3. Do NOT fail the optimization run

## References

- [RW_InferenceEngine README](../../RW_InferenceEngine/README.md)
- [OpenAI Embeddings API](https://platform.openai.com/docs/api-reference/embeddings)
- [OpenAI Compatible Reranking](https://python.langchain.com/docs/integrations/text_embedding/)
