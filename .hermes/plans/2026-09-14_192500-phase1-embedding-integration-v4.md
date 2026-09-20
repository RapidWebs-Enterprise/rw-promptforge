---
name: Phase 1 - Embedding Integration (REVISED)
description: Add embedding support via RW_InferenceEngine with caching
status: proposed
created: 2026-09-14
revision: 4
---

# Plan: Phase 1 — Embedding Integration (Revised)

## Goal
Extend existing Provider class with embed() and rerank() methods using RW_InferenceEngine. Add embedding cache for performance.

## Files to Create/Modify

| File | Action | Lines | Purpose |
|------|--------|-------|---------|
| `src/rw_promptforge/provider.py` | MODIFY | +50 | Add embed() and rerank() methods |
| `src/rw_promptforge/cache.py` | CREATE | ~70 | EmbeddingCache with LRU eviction |
| `src/rw_promptforge/datastore/models.py` | MODIFY | +15 | Add TraceEmbedding dataclass |
| `tests/test_provider_embed.py` | CREATE | ~90 | Test embed/rerank methods |
| `tests/test_cache.py` | CREATE | ~60 | Test caching behavior |
| `pyproject.toml` | MODIFY | +10 | Add [ml] optional extra |

## Step-by-Step Plan

### Step 1: Add embed() and rerank() to Provider
```python
def embed(self, texts: list[str], cache: EmbeddingCache | None = None) -> np.ndarray:
    """Get embeddings via /v1/embeddings endpoint."""
    # 1. Check cache
    # 2. Call endpoint
    # 3. Parse response
    # 4. Update cache
    # 5. Return np.ndarray

def rerank(self, query: str, documents: list[str]) -> list[float]:
    """Rerank documents via /v1/rerank endpoint."""
    # 1. Call endpoint
    # 2. Parse results
    # 3. Return relevance scores
```

### Step 2: Create EmbeddingCache
```python
class EmbeddingCache:
    def __init__(self, maxsize: int = 10000):
        self._cache: dict[str, tuple[float, ...]] = {}
        self._maxsize = maxsize
    
    def get(self, text: str) -> tuple[float, ...] | None:
        # Return cached embedding or None
    
    def set(self, text: str, embedding: np.ndarray):
        # Store embedding, evict if over maxsize
    
    def save(self, path: Path):
        # Persist to disk
    
    def load(self, path: Path):
        # Restore from disk
```

### Step 3: Add TraceEmbedding to models.py
```python
@dataclass
class TraceEmbedding:
    trace_id: str
    embedding: np.ndarray
    model: str
    dimension: int
    created_at: datetime
```

### Step 4: Add [ml] extra to pyproject.toml
```toml
[project.optional-dependencies]
ml = [
    "numpy>=1.24",
    "scikit-learn>=1.3",
    "hdbscan>=0.8",
    "imbalanced-learn>=0.12",
]
```

### Step 5: Add CLI flags
```python
@click.option("--embedding-endpoint", default=None, help="Override embedding endpoint")
@click.option("--rerank-endpoint", default=None, help="Override rerank endpoint")
@click.option("--ml-mode", is_flag=True, help="Enable ML-enhanced optimization")
```

## Test Plan
```
test_provider_embed_calls_endpoint()
test_provider_embed_caches_results()
test_provider_rerank_calls_endpoint()
test_cache_get_missing_returns_none()
test_cache_set_and_get()
test_cache_evicts_when_full()
test_trace_embedding_serialization()
```

## Risks
| Risk | Mitigation |
|------|------------|
| RW_IE unavailable | Catch exception, log warning, skip ML |
| Cache corruption | Validate on load, rebuild if malformed |
| Endpoint mismatch | Health check on startup |

## Verification
```bash
PYTHONPATH=src:. python3 -m pytest tests/test_provider_embed.py -v
PYTHONPATH=src:. python3 -m pytest tests/test_cache.py -v
PYTHONPATH=src:. python3 -m pytest tests/test_models.py -v
```
