# ADR-007: Cross-Encoder Reranking for Failure Traces

**Date:** 2026-09-14  
**Status:** Proposed

## Context

When rw-promptforge selects failure traces for optimization feedback, it currently uses
token-level similarity (Jaccard) to find "related" traces. This is insufficient because:

1. **Lexical bias**: Traces with similar words but different meanings score high
2. **No query awareness**: Same traces selected regardless of optimization goal
3. **Ranking quality**: No notion of "most relevant to current problem"

Research (Sentence Transformers docs, MS MARCO benchmarks) shows that **two-stage
retrieve-and-rerank** is the state-of-the-art for information retrieval:

1. **Retrieve**: Fast embedding search → top-K candidates
2. **Rerank**: Slow but accurate CrossEncoder → refined ranking

## Decision

**Use CrossEncoder reranking for trace selection.**

Implementation:
- Primary model: `cross-encoder/ms-marco-MiniLM-L-6-v2` (local, no GPU needed)
- Two-stage pipeline: Embedding retrieval → CrossEncoder reranking
- Configurable via `RW_PROMPTFORGE_RERANKER_MODEL` env var

## Rationale

### Why CrossEncoder instead of just embeddings?

CrossEncoders process query + passage jointly through transformer attention, producing
more accurate relevance scores than bi-encoder cosine similarity:

| Method | Speed | Accuracy | Use Case |
|--------|-------|----------|----------|
| Jaccard | Fast | Low | Token overlap only |
| Bi-encoder (embeddings) | Medium | Medium | Recall, broad search |
| Cross-encoder | Slow | High | Precision, final ranking |

From SBERT documentation:
> "CrossEncoder models generally provide superior performance compared to Sentence 
> Transformer models... however they are slower as they process every possible pair."

### Why not fine-tune our own reranker?

- Need labeled relevance data (expensive to create)
- Pre-trained MS MARCO model already good for semantic relevance
- Fine-tuning can come later if we have feedback loop

### Why MiniLM-L-6-v2?

- Small ( ~100MB), fast inference
- No GPU required
- Good balance of speed/accuracy for our scale (<1000 traces)

## Consequences

### Positive
- Better trace selection → higher-quality optimization feedback
- Query-aware: different goals get different trace sets
- Research-backed approach (CASPER, C-MOP use similar patterns)

### Negative
- Slower: ~10ms per query-trace pair vs ~1ms for embeddings
- Memory: ~200MB for model weights
- Added dependency: `sentence-transformers` (optional extra)

### Mitigation
- Cache reranker results for repeated queries
- Use embeddings for recall, reranker only for precision
- Configurable top_k (default 5, can increase for more context)

## Implementation

```python
# src/rw_promptforge/reranker.py
from sentence_transformers import CrossEncoder
from typing import Optional

class PromptReranker:
    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        batch_size: int = 32,
    ):
        self.model = CrossEncoder(model_name)
        self.batch_size = batch_size
    
    def rerank(
        self,
        query: str,
        traces: list[FailureTrace],
        top_k: int = 5,
    ) -> list[FailureTrace]:
        # Two-stage:
        # 1. Embed query + traces, find top-20 by cosine
        # 2. Rerank top-20 with CrossEncoder, return top-5
        
        candidates = self._embed_recall(query, traces, k=20)
        scores = self.model.predict(
            [(query, t.text) for t in candidates]
        )
        
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        return [t for t, _ in ranked[:top_k]]
    
    def _embed_recall(self, query, traces, k):
        # Use EmbeddingProvider from ADR-005
        pass
```

## Related

- ADR-005: Embedding Integration (required for first stage)
- Spec: spec-ml-integration.md, Section R5
- SBERT CrossEncoder docs: https://sbert.net/docs/cross_encoder/
