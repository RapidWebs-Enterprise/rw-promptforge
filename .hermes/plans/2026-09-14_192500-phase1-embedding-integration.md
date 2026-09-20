---
name: Phase 1 - Embedding Integration
description: Add OpenAI-compatible embedding provider with semantic similarity
status: proposed
created: 2026-09-14
related_spec: spec-ml-integration.md
related_adrs: [005, 006]
---

# Plan: Phase 1 — Embedding Integration

## Goal
Add OpenAI-compatible embedding provider backed by rw_inferenceEngine (primary) or sentence-transformers (fallback). Replace token-level Jaccard with semantic cosine similarity in convergence detection.

## Files to Create/Modify

| File | Action | Lines | Purpose |
|------|--------|-------|---------|
| `src/rw_promptforge/embeddings.py` | CREATE | ~150 | EmbeddingProvider class |
| `src/rw_promptforge/datastore/models.py` | MODIFY | +10 | Add semantic_similarity helper |
| `src/rw_promptforge/convergence.py` | MODIFY | ~30 | Use embeddings for staleness |
| `tests/test_embeddings.py` | CREATE | ~80 | Unit tests |
| `pyproject.toml` | MODIFY | +3 | Add optional [ml] extra |

## Step-by-Step Plan

### Step 1: Create embeddings.py
```python
class EmbeddingProvider:
    def __init__(self, endpoint=None, model="nomic-embed-text", fallback_local=True):
        # Read env vars, initialize httpx client or local model
        pass
    
    def encode(self, texts: list[str]) -> np.ndarray:
        # Batch encode via OpenAI API or local model
        pass
    
    def semantic_similarity(self, a: str, b: str) -> float:
        # Cosine similarity on embeddings
        pass
```

### Step 2: Update models.py
- Add `semantic_similarity` function that wraps EmbeddingProvider
- Keep Jaccard as fallback when no provider available

### Step 3: Update convergence.py
- Modify `check_semantic_stability()` to use embeddings when available
- Add `_embedding_similarity()` helper with graceful degradation

### Step 4: Add tests
- Test local fallback
- Test remote endpoint
- Test cosine similarity math
- Test graceful degradation

### Step 5: Update pyproject.toml
```toml
[project.optional-dependencies]
ml = ["numpy", "scikit-learn", "sentence-transformers"]
```

## Test Plan
```
test_embed_provider_local_fallback()
test_embed_provider_remote_endpoint()
test_semantic_similarity_same_meaning()
test_semantic_similarity_different_meaning()
test_convergence_uses_embeddings_when_available()
test_convergence_falls_back_to_jaccard()
```

## Risks
| Risk | Mitigation |
|------|------------|
| rw_inferenceEngine unavailable | Local fallback via sentence-transformers |
| Embedding dimension mismatch | Auto-detect from response, store dim |
| Network latency | Batch encode, cache results |
| Missing dependencies | Optional extras, try/except import |

## Verification
```bash
PYTHONPATH=src:. python3 -m pytest tests/test_embeddings.py -v
PYTHONPATH=src:. python3 -m pytest tests/test_convergence.py -v
```
