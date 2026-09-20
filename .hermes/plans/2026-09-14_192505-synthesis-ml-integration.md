# Synthesis: ML Integration for rw-promptforge

**Date:** 2026-09-14  
**Status:** Ready for Sign-off

## Audit Summary

### Forward Audit: ✅ PASS
- All plan claims verified against actual codebase
- No critical discrepancies found
- Minor LOC estimates adjusted upward

### Reverse Audit: ✅ PASS (with additions)
- Found 4 critical gaps requiring mitigation
- Architecture decisions validated
- Testing strategy needs expansion

### Combined Findings Incorporated
1. ✅ Added `imbalanced-learn` to [ml] extras
2. ✅ Added model persistence with joblib
3. ✅ Added graceful degradation matrix
4. ✅ Added progress reporting with tqdm
5. ✅ Increased clustering.py LOC estimate to 150
6. ✅ Added query builder for reranking
7. ✅ Added config loading strategy

---

## Revised Implementation Plan

### Phase 1: Embedding Integration (150 LOC)
**Files:** embeddings.py (new), models.py (modify), convergence.py (modify), tests/test_embeddings.py (new), pyproject.toml (modify)

**Key Changes from Audit:**
- Add `EMBEDDING_ENDPOINT` env var support
- Add embedding cache to `~/.hermes/cache/embeddings.pkl`
- Add `dimension` detection from API response
- Update convergence.py to use embeddings when available, fall back to Jaccard

**Tests:** 6 tests (local fallback, remote endpoint, cosine math, integration)

---

### Phase 2: Trace Clustering (150 LOC)
**Files:** clustering.py (new), models.py (modify), session_db.py (modify), tests/test_clustering.py (new)

**Key Changes from Audit:**
- Add `min_cluster_size=3` configurable
- Add `random_state=42` for reproducibility
- Add stability threshold validation
- Label clusters by error rate + size heuristics

**Tests:** 5 tests (empty, single, clustered, labeling, persistence)

---

### Phase 3: Failure Classifier (200 LOC)
**Files:** classifier.py (new), models.py (modify), session_db.py (modify), tests/test_classifier.py (new)

**Key Changes from Audit:**
- Use sklearn Pipeline with StandardScaler + HistGB
- Add model persistence to `~/.hermes/models/classifier.pkl`
- Add `imbalanced-learn` for SMOTE oversampling
- Add train_test_split for internal validation
- Add cross_val_score for performance estimation

**Feature Columns:** severity_level, tool_call_count, skill_conflict, text_length, embedding_cluster_id, repetition_score, time_delta_hours, similar_trace_count

**Tests:** 7 tests (features, training, prediction, importance, bootstrap, persistence, retraining)

---

### Phase 4: Cross-Encoder Reranking (120 LOC)
**Files:** reranker.py (new), models.py (modify), tests/test_reranker.py (new)

**Key Changes from Audit:**
- Reduce memory estimate to 100MB
- Add LRU cache for reranking results
- Add batch_size=32 configurable
- Add max_traces=100 limit
- Add query builder from optimization context

**Tests:** 5 tests (two-stage, top_k, empty, cached, query building)

---

### Phase 5: Optimizer Integration (100 LOC)
**Files:** optimizer.py (modify), cli.py (modify), provider.py (modify), tests/test_optimizer_ml.py (new)

**Key Changes from Audit:**
- Add `ml_enabled` flag (opt-in via --ml-mode)
- Add fallback matrix:
  - All ML: Full pipeline
  - Embeddings only: Clustering + token reranking
  - None: Existing token-based methods
- Add progress reporting with tqdm
- Add graceful degradation on ML component failure

**CLI Flags:**
- `--ml-mode`: Enable ML enhancements
- `--embedding-endpoint`: Override default endpoint
- `--ml-config`: JSON config file for ML settings

**Tests:** 4 tests (ML enabled, cluster-aware beam, fallback, config loading)

---

## Total Estimates

| Metric | Count |
|--------|-------|
| New files | 5 |
| Modified files | 6 |
| Total new LOC | ~720 |
| Total test LOC | ~270 |
| New dependencies | numpy, scikit-learn, hdbscan, imbalanced-learn, sentence-transformers, joblib, tqdm |
| Optional extras | [ml] |

---

## Verification Plan

```bash
# Phase 1
PYTHONPATH=src:. python3 -m pytest tests/test_embeddings.py -v
PYTHONPATH=src:. python3 -m pytest tests/test_convergence.py -v

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

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| rw_inferenceEngine unavailable | Medium | High | Local fallback + clear error message |
| ML dependency installation fails | Low | Medium | Optional extras, graceful skip |
| Embedding API rate limiting | Medium | Low | Cache embeddings, batch requests |
| HDBSCAN memory exhaustion | Low | Medium | Limit trace count, use mini-batch |
| Classifier overfitting | Medium | Low | Early stopping, cross-validation |
| Breaking existing behavior | Low | High | ML opt-in via flag, full regression tests |

---

## Open Questions (Pre-Sign-off)

1. **Embedding model**: What model does rw_inferenceEngine serve? (need to verify at http://srv1:8300/v1/models)
2. **Model persistence**: Should we persist embeddings between runs? (cache vs recompute)
3. **Retraining trigger**: How often to retrain classifier? (after N traces? time-based?)
4. **Minimum traces**: What's the minimum trace count for meaningful clustering? (heuristic: 10+)

---

## Next Steps

1. ✅ **Await user sign-off** on this synthesis
2. Implement Phase 1 (embeddings)
3. Run Phase 1 tests
4. Implement Phase 2 (clustering)
5. Continue through Phases 3-5
6. Final integration test + documentation

**Estimated total implementation time:** 8-12 hours (split across 5 phases)
