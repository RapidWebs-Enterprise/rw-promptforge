# ADR-005: OpenAI-Compatible Embedding Integration

**Date:** 2026-09-14  
**Status:** Proposed

## Context

rw-promptforge currently implements convergence detection and stagnation checks using
token-level similarity (Jaccard index, SequenceMatcher ratio). These metrics operate on
character/token overlap and cannot distinguish between:

1. **Semantic equivalence**: "Do X then Y" vs "First X, then Y" (same meaning, different words)
2. **Paraphrased stagnation**: Agent keeps saying same thing in different words
3. **Intent drift**: Subtle rewording that shifts meaning without changing vocabulary

The rw_inferenceEngine service (deployed on srv1, port 8300) provides an OpenAI-compatible
API endpoint at `/v1/embeddings` that can generate semantic embeddings for text. This
enables cosine similarity calculations in embedding space.

## Decision

**Use OpenAI-compatible embedding interface with local fallback.**

Implementation:
- Primary: `http://srv1:8300/v1/embeddings` (rw_inferenceEngine)
- Fallback: `sentence-transformers/all-MiniLM-L6-v2` (local, 384-dim)
- Configurable via `RW_PROMPTFORGE_EMBEDDING_ENDPOINT` env var

## Rationale

1. **OpenAI compatibility**: Standard API shape means easy swapping between providers
2. **Local fallback**: No external dependency for development/testing
3. **rw_inferenceEngine reuse**: Leverages existing ML infrastructure
4. **Research-backed**: C-MOP, CASPER, ETGPO all use embeddings as foundation
5. **Future-proof**: Enables advanced features (clustering, reranking) built on top

## Consequences

### Positive
- Semantic similarity replaces brittle token matching
- Foundation for ML features (clustering, classification, reranking)
- Consistent with Honcho KG embedding approach
- Optional dependency — core CLI works without ML

### Negative
- Adds httpx dependency (already present)
- Embedding requests add ~50-200ms latency per call
- Local fallback requires ~50MB model download
- Parameter tuning needed for HDBSCAN, cross-encoder

### Trade-offs Accepted
- Latency: Acceptable for offline optimization CLI (not interactive)
- Memory: 384-dim embeddings are lightweight (~3KB per trace)
- Complexity: ML layer is opt-in via `[ml]` extra

## Implementation

```python
# src/rw_promptforge/embeddings.py
from typing import Optional
import httpx
import numpy as np

class EmbeddingProvider:
    def __init__(
        self,
        endpoint: str = "http://srv1:8300/v1",
        model: str = "nomic-embed-text",
        fallback_local: bool = True,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self._local_model = None
        if fallback_local:
            try:
                from sentence_transformers import SentenceTransformer
                self._local_model = SentenceTransformer("all-MiniLM-L6-v2")
            except ImportError:
                pass
    
    def encode(self, texts: list[str]) -> np.ndarray:
        if self.endpoint and self._client:
            return self._encode_remote(texts)
        elif self._local_model:
            return self._encode_local(texts)
        raise RuntimeError("No embedding provider available")
    
    def semantic_similarity(self, a: str, b: str) -> float:
        embeds = self.encode([a, b])
        return float(np.dot(embeds[0], embeds[1]) / 
                     (np.linalg.norm(embeds[0]) * np.linalg.norm(embeds[1])))
```

## Related

- ADR-003: OpenAI-Compatible Provider (existing LLM provider abstraction)
- Honcho KG: 384-dim embeddings via same inference engine
- Spec: spec-ml-integration.md
