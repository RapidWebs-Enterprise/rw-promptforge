# Synthesis v3: ML Integration for rw-promptforge (FINAL)

**Date:** 2026-09-14  
**Status:** Ready for Implementation  
**Revision:** Addresses all audit findings + user feedback

---

## Critical Audit Resolutions

### 1. Architectural Conflict ✅ RESOLVED
**Issue:** Original plan proposed replacing Jaccard with embeddings (contradicts prior audit)
**Resolution:** Reframe as **additive enhancement** via `--ml-mode` flag. Jaccard untouched.

### 2. Provider Class Extension ✅ RESOLVED
**Issue:** Plan proposed new `EmbeddingProvider` class
**Resolution:** Extend existing `Provider` class with `embed()` method. Reuse httpx client.

### 3. Cache Location ✅ RESOLVED
**Issue:** Plan mentioned `~/.hermes/cache/`
**Resolution:** Use XDG standard: `~/.cache/rw-promptforge/embeddings.pkl`

---

## Final Design Decisions

### Decision 1: Embedding Model
**Primary:** `bge-small-en-v1.5` via RW_InferenceEngine (`http://srv1:8300/v1/embeddings`)
- 384 dimensions, 128MB ONNX model
- Already deployed, zero API cost
- Local inference, no network dependency beyond Tailscale

**Fallback:** OpenAI-compatible endpoint via `--embedding-endpoint` flag
- Configurable: `OPENAI_API_KEY` + `OPENAI_ENDPOINT`
- Supports: OpenAI, Groq, Anyscale, etc.

**Model Selection Rationale:**
| Model | Dimensions | Context | Performance | Cost |
|-------|------------|---------|-------------|------|
| bge-small-en-v1.5 | 384 | 512 | Good | Free |
| nomic-embed-text | 768 | 8192 | Better | Free (local) |
| text-embedding-3-small | 1536 | 8192 | Best | $0.02/1M tokens |

**Decision:** Start with bge-small-en-v1.5 (already deployed). Make model configurable for future upgrades.

---

### Decision 2: Cache Strategy
**Location:** `~/.cache/rw-promptforge/embeddings.pkl`
- XDG_CACHE_HOME compliant
- Auto-purged by system cleaners
- Fast local filesystem access

**Implementation:**
```python
import pickle
from pathlib import Path

CACHE_DIR = Path.home() / ".cache" / "rw-promptforge"
CACHE_FILE = CACHE_DIR / "embeddings.pkl"

class EmbeddingCache:
    def __init__(self):
        self._cache = self._load()
    
    def get(self, text: str) -> np.ndarray | None:
        return self._cache.get(text)
    
    def set(self, text: str, embedding: np.ndarray):
        self._cache[text] = embedding
        if len(self._cache) > 10000:  # LRU eviction
            self._cache.pop(next(iter(self._cache)))
    
    def save(self):
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, 'wb') as f:
            pickle.dump(self._cache, f)
```

**TTL:** None (embeddings are deterministic, no staleness)

---

### Decision 3: Retraining Strategy
**Approach:** **Lazy + explicit trigger**

**Triggers:**
1. Manual: `rw-promptforge optimize --ml-mode --retrain`
2. Automatic: When trace count > 100 AND last retrained > 7 days ago
3. Error-based: If classifier confidence < 0.3 for 5+ consecutive predictions

**Implementation:**
```python
class Classifier:
    def should_retrain(self, trace_count: int) -> bool:
        if trace_count < 30:
            return False
        if self.last_retrained is None:
            return True
        if (datetime.now() - self.last_retrained).days > 7:
            return True
        if self.low_confidence_count >= 5:
            return True
        return False
```

---

### Decision 4: Minimum Traces Threshold
**Configurable via CLI:**

```bash
rw-promptforge optimize --ml-mode \
  --min-traces-cluster 10 \
  --min-traces-classify 30 \
  --min-traces-rerank 5
```

**Default values:**
| Phase | Min Traces | Rationale |
|-------|------------|-----------|
| Clustering (HDBSCAN) | 10 | min_cluster_size=3, need ~3x for stability |
| Classification (HistGB) | 30 | 3 classes × 10 samples each |
| Reranking (CrossEncoder) | 5 | Works on small sets |

**Behavior when below threshold:**
- Log warning: `⚠️ Insufficient traces for ML clustering (need 10, have 3)`
- Skip ML phase, continue with token-based fallback
- Do NOT fail the optimization run

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

**Provider.embed() signature:**
```python
def embed(self, texts: list[str]) -> np.ndarray:
    """Get embeddings via /v1/embeddings endpoint."""
    # 1. Check cache first
    # 2. Call endpoint with httpx
    # 3. Parse response (data[].embedding)
    # 4. Cache results
    # 5. Return np.ndarray
```

**CLI flags added:**
```python
@click.option("--embedding-endpoint", default=None, help="Override embedding endpoint")
@click.option("--embedding-model", default=None, help="Override embedding model name")
@click.option("--ml-mode", is_flag=True, help="Enable ML-enhanced optimization")
@click.option("--min-traces-cluster", default=10, type=int, help="Min traces for clustering")
@click.option("--min-traces-classify", default=30, type=int, help="Min traces for classification")
```

---

### Phase 2: Trace Clustering (HDBSCAN)

**Unchanged from v2** — uses embeddings from Phase 1.

**Add:** Cache integration for cluster assignments
**Add:** Min traces check before clustering

---

### Phase 3: Failure Classifier (HistGB)

**Unchanged** — adds lazy retraining logic.

---

### Phase 4: Cross-Encoder Reranking

**Modified:** Add config for batch_size, max_traces
**Add:** Timeout handling (5s per batch)

---

### Phase 5: Optimizer Integration

**Modified:** Wire all ML flags through CLI
**Add:** Progress reporting with tqdm
**Add:** Graceful degradation on component failure

---

## Verification Plan

```bash
# Phase 1
PYTHONPATH=src:. python3 -m pytest tests/test_provider_embed.py -v
PYTHONPATH=src:. python3 -m pytest tests/test_cache.py -v

# Phase 2-5
PYTHONPATH=src:. python3 -m pytest tests/ -k "clustering or classifier or reranker or ml" -v

# Regression (no behavior change without --ml-mode)
PYTHONPATH=src:. python3 -m pytest tests/test_optimizer.py -v
PYTHONPATH=src:. python3 -m pytest tests/test_convergence.py -v

# Full suite
PYTHONPATH=src:. python3 -m pytest tests/ -q --tb=short
```

---

## Final Estimates

| Metric | Value |
|--------|-------|
| New files | 5 |
| Modified files | 6 |
| Total new code | ~700 LOC |
| Test code | ~280 LOC |
| New deps (optional) | numpy, scikit-learn, hdbscan, imbalanced-learn, sentence-transformers |
| New deps (core) | None (httpx already present) |

---

## Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| RW_InferenceEngine unavailable | Medium | High | Graceful fallback to local sentence-transformers |
| Insufficient traces | High | Low | Skip ML, log warning, continue with token methods |
| Cache corruption | Low | Low | Auto-rebuild from endpoint on missing/malformed |
| Breaking existing behavior | Low | High | ML opt-in via --ml-mode, full regression tests |
| Dependency installation fails | Medium | Medium | Optional [ml] extra, clear error message |

---

## Next Steps

1. ✅ **Await user sign-off** on v3 plan
2. Implement Phase 1 (Provider extension + cache)
3. Run Phase 1 tests
4. Implement Phases 2-5 sequentially
5. Final integration test + README update

**Estimated implementation time:** 8-10 hours (split across 5 phases)
