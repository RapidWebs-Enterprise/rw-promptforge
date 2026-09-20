# Phase 2-5 Reverse Audit Results

## Phase 2: Clustering

### Missed Items (GAP)
1. **HDBSCAN import**: Need `import hdbscan` - not in standard lib
2. **Memory management**: HDBSCAN can be memory-intensive for large trace sets
3. **Cluster validation**: No silhouette score or stability validation mentioned
4. **Label consistency**: How to ensure same traces get same labels across runs?

### Incorrect Assumptions (ERROR)
1. **NONE** - Plan assumptions about HDBSCAN usage are correct

### Suggested Additions
- Add `stability_threshold` parameter for cluster validation
- Add `random_state` for reproducibility
- Consider additive clustering for overlapping patterns
- Add `core_dist_n_jobs` for parallel computation

---

## Phase 3: Classifier

### Missed Items (GAP)
1. **Feature engineering**: Need document how to extract features from FailureTrace
2. **Model evaluation**: No CV score or holdout set mentioned
3. **Pipeline**: Should wrap in sklearn Pipeline for reproducibility
4. **Persistence**: Need joblib/pickle for model serialization

### Incorrect Assumptions (ERROR)
1. **NONE** - HistGB choice is well-justified

### Suggested Additions
- Add sklearn Pipeline: `steps=[('scaler', StandardScaler()), ('clf', HistGB)]`
- Add `train_test_split` for internal validation
- Add `cross_val_score` for performance estimation
- Save model to `~/.hermes/models/promptforge_classifier.pkl`

---

## Phase 4: Reranking

### Missed Items (GAP)
1. **Query construction**: How to build query from optimization goal?
2. **Score normalization**: CrossEncoder scores need min-max normalization
3. **Timeout handling**: What if CrossEncoder is slow?
4. **Parallel processing**: Can process multiple queries in parallel

### Incorrect Assumptions (ERROR)
1. **NONE** - Two-stage pipeline is correct approach

### Suggested Additions
- Add query builder: combine failure types + skills + severity into query
- Add score normalization: `(score - min) / (max - min)`
- Add timeout: `timeout=5.0` seconds per rerank call
- Consider async for multiple rerank calls

---

## Phase 5: Integration

### Missed Items (GAP)
1. **CLI integration**: Need to wire ML flags through click decorators
2. **Config loading**: Where do ML settings come from? (env vars? config file?)
3. **Graceful degradation**: What if only some ML components available?
4. **Progress reporting**: ML operations should show progress bars

### Incorrect Assumptions (ERROR)
1. **MEDIUM**: Plan assumes all ML components available - need fallback matrix

### Suggested Additions
- Add fallback matrix:
  - All ML: Use full pipeline
  - Embeddings only: Use clustering + token-based reranking
  - None: Fall back to existing token-based methods
- Add progress reporting with `tqdm`
- Add `--ml-config` flag for JSON config file
- Document migration path from token-based to ML-based

---

## Critical Findings Across All Phases

### Architecture Concerns
1. **Stateless vs Stateful**: ML components should be stateless (recreate per run) or stateful (persist between runs)?
2. **Thread safety**: Are ML models thread-safe for concurrent optimization runs?
3. **Memory leaks**: Long-running processes may accumulate embedding caches

### Testing Strategy Gaps
1. **Integration tests**: Need end-to-end test with real rw_inferenceEngine
2. **Mock strategy**: How to mock embeddings without network calls?
3. **Performance tests**: Baseline vs ML-enhanced performance comparison
4. **Regression tests**: Ensure ML mode doesn't break non-ML mode

### Documentation Gaps
1. **README update**: Need ML section with setup instructions
2. **Config reference**: Document all ML-related config options
3. **Troubleshooting guide**: Common issues with ML components
4. **Migration guide**: How to transition from token-based to ML-based
