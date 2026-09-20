# Synthesis v2: ML Integration for rw-promptforge (REVISED)

**Date:** 2026-09-14  
**Status:** Ready for Sign-off  
**Revision:** Addresses reverse audit findings

---

## Critical Audit Finding: Architectural Conflict

**Issue:** Original plan proposed replacing Jaccard similarity with embeddings in convergence detection. This directly contradicts a previous reverse audit decision documented in `convergence.py`:

```python
# Line 4: "Jaccard similarity for semantic change (NOT cosine — no embeddings needed)"
# Line 149-152: check_semantic_stability() uses Jaccard, not cosine
```

**Previous rationale:** Cosine similarity was deemed "unimplementable" without embedding infrastructure.

**Resolution:** Reframe embeddings as **additive enhancement** for NEW features (clustering, reranking), NOT replacement for convergence detection.

---

## Revised Implementation Plan

### Phase 1: Embedding Support (Provider Extension)

**Change:** Extend existing `Provider` class instead of creating `EmbeddingProvider`.

**Files Modified:**
| File | Action | Lines | Purpose |
|------|--------|-------|---------|
| `src/rw_promptforge/provider.py` | MODIFY | +30 | Add `embed()` method, reuse httpx client |
| `src/rw_promptforge/datastore/models.py` | MODIFY | +15 | Add TraceEmbedding dataclass |
| `pyproject.toml` | MODIFY | +8 | Add `[project.optional-dependencies] ml = [...]` |

**New Provider method:**
```python
def embed(self, texts: list[str]) -> np.ndarray:
    """Get embeddings via OpenAI-compatible /v1/embeddings endpoint."""
    # Reuse existing httpx client
    # Follow existing retry patterns
    # Return numpy array of shape (len(texts), dim)
```

**Environmental variables:**
- `OPENAI_API_KEY` (existing)
- `OPENAI_ENDPOINT` (existing, or use `/v1/embeddings` path)
- `EMBEDDING_MODEL` (new, default: "nomic-embed-text")

**Caching:** Add `@lru_cache(maxsize=1000)` for repeated embeddings.

**Tests:** 5 tests (embed method, caching, env var loading, fallback handling)

---

### Phase 2: Trace Clustering (HDBSCAN)

**Unchanged from original plan** — uses embeddings from Phase 1 for cluster formation.

**Files:** clustering.py (new), models.py (modify), session_db.py (modify), tests/test_clustering.py (new)

**Key insight:** Cluster based on EMBEDDING similarity, not Jaccard. This is a NEW feature, not replacement.

---

### Phase 3: Failure Classifier (HistGB)

**Unchanged** — trains on cluster labels from Phase 2.

**Files:** classifier.py (new), models.py (modify), tests/test_classifier.py (new)

**Add:** `imbalanced-learn` for SMOTE (class imbalance handling)

---

### Phase 4: Cross-Encoder Reranking

**Unchanged** — two-stage retrieval using embeddings + CrossEncoder.

**Files:** reranker.py (new), tests/test_reranker.py (new)

---

### Phase 5: Optimizer Integration

**Modified:** Add `--ml-mode` flag (opt-in). When enabled:
- Use clustering (Phase 2) for failure trace selection
- Use classifier (Phase 3) for pattern prediction
- Use reranking (Phase 4) for trace prioritization

When disabled: **zero behavior change** — existing token-based methods used.

---

## Revised Dependencies

```toml
[project.optional-dependencies]
ml = [
    "numpy>=1.24",
    "scikit-learn>=1.3",
    "hdbscan>=0.8",
    "imbalanced-learn>=0.12",
    "sentence-transformers>=2.0",  # Local fallback only
]
```

**Note:** `httpx` is already core dependency (line 25 of pyproject.toml). No change needed.

---

## Verification Plan

```bash
# Phase 1
PYTHONPATH=src:. python3 -m pytest tests/test_provider_embed.py -v

# Phase 2-5
PYTHONPATH=src:. python3 -m pytest tests/ -k "clustering or classifier or reranker or ml" -v

# Regression (ensure no behavior change without --ml-mode)
PYTHONPATH=src:. python3 -m pytest tests/test_optimizer.py -v
PYTHONPATH=src:. python3 -m pytest tests/test_convergence.py -v
```

---

## Total Estimates (Revised)

| Metric | Original | Revised |
|--------|----------|---------|
| New files | 5 | 4 (no embeddings.py) |
| Modified files | 6 | 6 (provider.py instead of new class) |
| Total new code | ~720 LOC | ~680 LOC |
| Test code | ~270 LOC | ~250 LOC |

---

## Open Questions (Pre-Sign-off)

1. **Embedding model:** What model does rw_inferenceEngine serve? (verify at `http://srv1:8300/v1/models`)
2. **Cache location:** `~/.hermes/cache/embeddings.pkl` or in-memory LRU only?
3. **Retraining trigger:** After N traces or time-based?
4. **Minimum traces:** HDBSCAN needs ~10+ for meaningful clusters?

---

## Next Steps

1. ✅ **Await user sign-off** on revised plan
2. Implement Phase 1 (Provider extension)
3. Run Phase 1 tests
4. Implement Phases 2-5 sequentially
5. Final integration test + documentation

**Estimated total implementation time:** 8-10 hours (reduced by ~50 LOC from architecture fix)
