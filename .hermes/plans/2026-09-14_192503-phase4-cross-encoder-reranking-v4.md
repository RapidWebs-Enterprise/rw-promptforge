---
name: Phase 4 - Cross-Encoder Reranking (REVISED)
description: Use RW_InferenceEngine /v1/rerank endpoint instead of local CrossEncoder
status: proposed
created: 2026-09-14
revision: 4
---

# Plan: Phase 4 — Cross-Encoder Reranking (Revised)

## Goal
Implement two-stage retrieval using RW_InferenceEngine's /v1/rerank endpoint. No local model loading required.

## Files to Create/Modify

| File | Action | Lines | Purpose |
|------|--------|-------|---------|
| `src/rw_promptforge/reranker.py` | CREATE | ~80 | Two-stage reranking using Provider |
| `tests/test_reranker.py` | CREATE | ~60 | Test reranking pipeline |
| `src/rw_promptforge/datastore/models.py` | MODIFY | +10 | Add RerankedTrace dataclass |

## Step-by-Step Plan

### Step 1: Create reranker.py
```python
class PromptReranker:
    def __init__(self, provider: Provider, top_k: int = 5, recall_k: int = 20):
        self.provider = provider
        self.top_k = top_k
        self.recall_k = recall_k
    
    def rerank(self, query: str, traces: list[FailureTrace]) -> list[FailureTrace]:
        # Stage 1: Embedding recall (top-20)
        candidates = self._embed_recall(query, traces)
        
        # Stage 2: Cross-encoder rerank (via RW_IE)
        docs = [t.text for t in candidates]
        scores = self.provider.rerank(query, docs)
        
        # Return top_k by relevance
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        return [t for t, _ in ranked[:self.top_k]]
    
    def _embed_recall(self, query: str, traces: list[FailureTrace]) -> list[FailureTrace]:
        # Use Provider.embed() for candidate selection
        pass
```

### Step 2: Add RerankedTrace to models.py
```python
@dataclass
class RerankedTrace:
    trace: FailureTrace
    score: float
    rank: int
```

### Step 3: Add tests
- Test two-stage pipeline
- Test top_k selection
- Test empty input handling
- Test provider integration

## Test Plan
```
test_rerank_two_stage_pipeline()
test_rerank_returns_top_k()
test_rerank_empty_traces()
test_embed_recall_finds_candidates()
test_reranker_uses_provider_rerank()
```

## Risks
| Risk | Mitigation |
|------|------------|
| RW_IE rerank endpoint unavailable | Catch exception, fall back to embedding similarity ranking |
| Large document count | Limit to recall_k=20 candidates before reranking |
| Network latency | Cache reranking results (optional) |

## Verification
```bash
PYTHONPATH=src:. python3 -m pytest tests/test_reranker.py -v
```
