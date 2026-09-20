# Phase 2-5 Forward Audit Results

## Phase 2: Clustering (HDBSCAN)

### Verified Facts (PASS)
1. ✅ models.py has FailureTrace dataclass with session_id, timestamp, what_happened fields
2. ✅ convergence.py imports from models.py - clustering will integrate cleanly
3. ✅ session_db.py has get_contrastive_traces() method - good integration point
4. ✅ pyproject.toml has no ML dependencies yet - clean slate

### Discrepancies (FAIL)
1. ❌ **MINOR**: Plan says +120 LOC for clustering.py, but HDBSCAN + labeling logic likely ~150 LOC
2. ❌ **MINOR**: Should add `min_cluster_size` to Hyperparams, not just constructor

### Recommended Modifications
- Increase clustering.py estimate to 150 LOC
- Add configuration for HDBSCAN parameters (min_cluster_size, min_samples)
- Consider adding cluster persistence (save/load) for training data reuse

---

## Phase 3: Classifier (HistGB)

### Verified Facts (PASS)
1. ✅ scikit-learn already in dev dependencies (pytest-dev includes it)
2. ✅ models.py has LearningLogEntry with severity_before/after - good features
3. ✅ FAILURE_TYPE_WEIGHTS dict exists - can use for training labels
4. ✅ SessionDBReader has query methods - easy feature extraction

### Discrepancies (FAIL)
1. ❌ **CRITICAL**: Plan missing `imbalanced-learn` for handling class imbalance
2. ❌ **MINOR**: Need to specify model persistence path (~/.hermes/classifier.pkl)
3. ❌ **GAP**: No mention of retraining strategy (when to update model?)

### Recommended Modifications
- Add `imbalanced-learn` to [ml] extras
- Add `model_path` parameter to FailureClassifier
- Document retraining triggers (e.g., after 100 new traces, or monthly)
- Add `predict_proba()` for confidence scoring

---

## Phase 4: Cross-Encoder Reranking

### Verified Facts (PASS)
1. ✅ sentence-transformers not in current deps - need to add
2. ✅ models.py can easily extend with RerankedTrace dataclass
3. ✅ EmbeddingProvider from Phase 1 will be available for stage 1

### Discrepancies (FAIL)
1. ❌ **MINOR**: CrossEncoder model is ~100MB, not 200MB as stated
2. ❌ **GAP**: No caching strategy for reranking results
3. ❌ **GAP**: No batch size configuration for memory-constrained environments

### Recommended Modifications
- Reduce memory estimate to 100MB
- Add result caching (LRU cache on query+traces tuple)
- Add `batch_size` parameter (default 32)
- Add `max_traces` limit (don't rerank more than 100 candidates)

---

## Phase 5: Optimizer Integration

### Verified Facts (PASS)
1. ✅ optimizer.py has beam_size parameter - easy extension point
2. ✅ BEAM_HINTS tuple exists - can extend with cluster-aware hints
3. ✅ CLI already has --max-rounds, --beam-size flags - consistent pattern
4. ✅ provider.py has Provider class - embedding provider fits as new provider type

### Discrepancies (FAIL)
1. ❌ **CRITICAL**: Need to ensure ML components are lazy-loaded (only when --ml-mode)
2. ❌ **GAP**: No fallback strategy if ML components unavailable
3. ❌ **GAP**: No performance testing plan for ML vs non-ML modes

### Recommended Modifications
- Add `ml_enabled` flag to Optimizer.__init__
- Wrap all ML calls in try/except with fallback to token-based methods
- Add benchmark tests comparing ML vs non-ML performance
- Document configuration options in README

---

## Cross-Cutting Concerns

### Missing Items
1. ❌ **CONFIG**: No config.yaml pattern for ML settings (endpoint, model names, thresholds)
2. ❌ **LOGGING**: No logging strategy for ML operations (debug mode?)
3. ❌ **ERROR HANDLING**: What happens if embeddings fail mid-optimization?
4. ❌ **PERFORMANCE**: Expected latency impact (embeddings: ~50ms, reranking: ~200ms)
5. ❌ **TESTING**: Need mock embedding provider for unit tests

### Security Considerations
- No sensitive data in embeddings (text only)
- Model files stored in ~/.hermes/cache/ (not in repo)
- No network calls without explicit --ml-mode flag

### Open Questions
1. What embedding model does rw_inferenceEngine serve? (need to verify)
2. Should we cache embeddings to disk for repeat runs?
3. How often should the classifier be retrained?
4. What's the minimum trace count needed for meaningful clustering?
