# Synthesis v4: ML Integration for rw-promptforge (FINAL)

**Date:** 2026-09-14  
**Status:** Ready for Implementation  
**Revision:** Incorporates RW_InferenceEngine dual-endpoint support

---

## Key Discovery: RW_InferenceEngine Serves Both Endpoints

**Confirmed:** RW_IE provides OpenAI-compatible API for:
- `POST /v1/embeddings` — BGE embeddings (384-dim)
- `POST /v1/rerank` — Cross-encoder reranking

**Impact:** Phase 4 simplifies dramatically — no separate CrossEncoder model needed.

---

## Final Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    rw-promptforge CLI                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Optimizer│  │Auditor   │  │Converge  │  │Analyze  │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │             │             │             │          │
│  ┌────▼─────────────▼─────────────▼─────────────▼─────┐   │
│  │              ML Enhancement Layer                   │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐         │   │
│  │  │Embedding │  │Cluster  │  │Classifier│         │   │
│  │  │ Provider │  │(HDBSCAN)│  │(HistGB)  │         │   │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘         │   │
│  └───────┼──────────────┼──────────────┼──────────────┘   │
│          │              │              │                   │
│  ┌───────▼──────────────▼──────────────▼──────────────┐   │
│  │              RW_InferenceEngine                     │   │
│  │  http://srv1:8300                                   │   │
│  │  ├─ POST /v1/embeddings  (BGE 384-dim)             │   │
│  │  └─ POST /v1/rerank      (CrossEncoder)            │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Revised Implementation Plan

### Phase 1: Embedding Support (Provider Extension)

**Files:**
| File | Action | LOC | Purpose |
|------|--------|-----|---------|
| `src/rw_promptforge/provider.py` | MODIFY | +40 | Add `embed()` method |
| `src/rw_promptforge/cache.py` | CREATE | ~60 | EmbeddingCache class |
| `src/rw_promptforge/datastore/models.py` | MODIFY | +15 | Add TraceEmbedding dataclass |
| `tests/test_provider_embed.py` | CREATE | ~80 | 6 test cases |
| `tests/test_cache.py` | CREATE | ~50 | 4 test cases |
| `pyproject.toml` | MODIFY | +10 | Add [ml] extra |

**Key additions to Provider:**
```python
def embed(self, texts: list[str]) -> np.ndarray:
    """Get embeddings via OpenAI-compatible /v1/embeddings endpoint."""
    # Reuse existing httpx client
    # Call: {endpoint}/v1/embeddings
    # Parse: data[].embedding
    # Cache results
    pass

def rerank(self, query: str, documents: list[str]) -> list[float]:
    """Rerank documents using /v1/rerank endpoint."""
    # Call: {endpoint}/v1/rerank
    # Parse: results[].relevance_score
    # Return: sorted relevance scores
    pass
```

---

### Phase 2: Trace Clustering (HDBSCAN)

**Unchanged** — uses embeddings from Phase 1.

---

### Phase 3: Failure Classifier (HistGB)

**Unchanged** — trains on cluster labels from Phase 2.

---

### Phase 4: Cross-Encoder Reranking (SIMPLIFIED)

**Files:**
| File | Action | LOC | Purpose |
|------|--------|-----|---------|
| `src/rw_promptforge/reranker.py` | CREATE | ~80 | Use RW_IE rerank endpoint |
| `tests/test_reranker.py` | CREATE | ~50 | Test reranking |

**Implementation:**
```python
class PromptReranker:
    def __init__(self, provider: Provider):
        self.provider = provider
    
    def rerank(self, query: str, traces: list[FailureTrace], top_k: int = 5) -> list[FailureTrace]:
        # Stage 1: Embedding recall (top-20 candidates)
        candidates = self._embed_recall(query, traces, k=20)
        
        # Stage 2: Cross-encoder rerank via RW_IE
        docs = [t.text for t in candidates]
        scores = self.provider.rerank(query, docs)
        
        # Return top_k by relevance score
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        return [t for t, _ in ranked[:top_k]]
```

**No new dependencies!** Reuses existing httpx client.

---

### Phase 5: Optimizer Integration

**Modified:** Wire ML flags through CLI.

**CLI flags:**
```bash
rw-promptforge optimize --ml-mode                    # Enable ML enhancements
rw-promptforge optimize --ml-mode --retrain         # Force classifier retrain
rw-promptforge optimize --ml-mode --min-traces 30   # Override minimum traces
rw-promptforge optimize --ml-mode --embedding-endpoint http://custom:8300  # Custom endpoint
```

---

## Final Dependency List

### Core (already present)
- `click>=8.0`
- `rich>=13.0`
- `httpx>=0.27`
- `pyyaml>=6.0`

### Optional [ml] extra
```toml
[project.optional-dependencies]
ml = [
    "numpy>=1.24",           # For embedding arrays
    "scikit-learn>=1.3",     # For classifier
    "hdbscan>=0.8",          # For clustering
    "imbalanced-learn>=0.12", # For SMOTE
]
```

**Removed from list:**
- ❌ `sentence-transformers` — Not needed (using RW_IE)
- ❌ `cross-encoder` — Not needed (using RW_IE)

---

## Verification Plan

```bash
# Phase 1
PYTHONPATH=src:. python3 -m pytest tests/test_provider_embed.py -v
PYTHONPATH=src:. python3 -m pytest tests/test_cache.py -v

# Phase 2
PYTHONPATH=src:. python3 -m pytest tests/test_clustering.py -v

# Phase 3
PYTHONPATH=src:. python3 -m pytest tests/test_classifier.py -v

# Phase 4
PYTHONPATH=src:. python3 -m pytest tests/test_reranker.py -v

# Phase 5
PYTHONPATH=src:. python3 -m pytest tests/test_optimizer_ml.py -v
PYTHONPATH=src:. python3 -m pytest tests/test_optimizer.py -v  # Regression

# Full suite
PYTHONPATH=src:. python3 -m pytest tests/ -q --tb=short
```

---

## Final Estimates

| Metric | Original | Revised (v4) |
|--------|----------|--------------|
| New files | 5 | 4 (no CrossEncoder dep) |
| Modified files | 6 | 6 |
| Total new code | ~700 LOC | ~640 LOC |
| Test code | ~280 LOC | ~260 LOC |
| Optional deps | 5 packages | 4 packages |
| External deps | 1 (RW_IE) | 1 (RW_IE) |

---

## Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| RW_IE unavailable | Medium | High | Graceful fallback: skip ML, log warning, continue with token methods |
| Insufficient traces | High | Low | Skip ML phase, log warning |
| Cache corruption | Low | Low | Auto-rebuild from endpoint |
| Breaking existing behavior | Low | High | ML opt-in via `--ml-mode`, full regression tests |
| Endpoint mismatch | Medium | Medium | Configurable `--embedding-endpoint`, health check on startup |

---

## Open Questions (Resolved)

| Question | Decision |
|----------|----------|
| Embedding model? | `bge-small-en-v1.5` via RW_IE (port 8300) |
| Cache location? | `~/.cache/rw-promptforge/embeddings.pkl` (XDG compliant) |
| Retraining trigger? | Lazy + explicit `--retrain` flag |
| Min traces threshold? | Configurable: cluster=10, classify=30, rerank=5 |
| Reranker model? | Use RW_IE `/v1/rerank` (no separate dependency) |

---

## Next Steps

1. ✅ **Await user sign-off** on v4 plan
2. Implement Phase 1 (Provider extension + cache)
3. Run Phase 1 tests
4. Implement Phases 2-5 sequentially
5. Final integration test + README update

**Estimated implementation time:** 6-8 hours (reduced by eliminating CrossEncoder dependency)
