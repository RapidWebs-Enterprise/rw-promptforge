---
name: Phase 4 - Cross-Encoder Reranking
description: Two-stage retrieve-and-rerank for failure trace selection
status: proposed
created: 2026-09-14
related_spec: spec-ml-integration.md
related_adrs: [007]
---

# Plan: Phase 4 — Cross-Encoder Reranking

## Goal
Implement two-stage retrieval: embeddings for recall (top-20), CrossEncoder for precision (top-5). Improves trace selection quality for optimization feedback.

## Files to Create/Modify

| File | Action | Lines | Purpose |
|------|--------|-------|---------|
| `src/rw_promptforge/reranker.py` | CREATE | ~100 | PromptReranker class |
| `src/rw_promptforge/datastore/models.py` | MODIFY | +10 | Add RerankedTrace dataclass |
| `tests/test_reranker.py` | CREATE | ~50 | Unit tests |

## Step-by-Step Plan

### Step 1: Create reranker.py
```python
class PromptReranker:
    def __init__(self, cross_encoder_model="cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model = CrossEncoder(cross_encoder_model)
    
    def rerank(self, query: str, traces: list[FailureTrace], top_k: int = 5) -> list[FailureTrace]:
        # Stage 1: Embedding recall (top-20)
        candidates = self._embed_recall(query, traces, k=20)
        # Stage 2: CrossEncoder rerank
        scores = self.model.predict([(query, t.text) for t in candidates])
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        return [t for t, _ in ranked[:top_k]]
    
    def _embed_recall(self, query, traces, k):
        # Use EmbeddingProvider from Phase 1
        pass
```

### Step 2: Update models.py
- Add `RerankedTrace` dataclass

### Step 3: Add tests
- Test two-stage retrieval
- Test reranking scores
- Test empty input handling

## Test Plan
```
test_rerank_two_stage_pipeline()
test_rerank_returns_top_k()
test_rerank_empty_traces()
test_embed_recall_finds_candidates()
```

## Risks
| Risk | Mitigation |
|------|------------|
| Model memory (~200MB) | Optional dependency |
| Latency (~10ms/pair) | Cache results, batch processing |
| Dependency availability | Try/except import, fail gracefully |

## Verification
```bash
PYTHONPATH=src:. python3 -m pytest tests/test_reranker.py -v
```
