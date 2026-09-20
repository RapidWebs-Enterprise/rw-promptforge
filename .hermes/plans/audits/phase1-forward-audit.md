# Phase 1 Forward Audit: Embedding Integration for rw-promptforge

**Date**: 2026-09-14
**Auditor**: Agnes (subagent)
**Plan**: `.hermes/plans/2026-09-14_192500-phase1-embedding-integration.md`
**Status**: COMPLETE

---

## Executive Summary

| Check | Status | Notes |
|-------|--------|-------|
| convergence.py Jaccard/SequenceMatcher | ✅ PASS | Confirmed in use |
| models.py structures | ✅ PASS | All expected dataclasses present |
| httpx dependency | ✅ PASS | Already included in pyproject.toml |
| test structure | ✅ PASS | pytest convention confirmed |
| no existing embeddings.py | ✅ PASS | Clean slate |
| provider.py embedding infra | ⚠️ FAIL | No embedding methods exist |

**Overall**: Plan is **valid** with minor adjustments needed. Key recommendation: leverage existing `Provider` class pattern rather than creating redundant abstraction. No blocking issues found.

---

## Verified Facts (PASS)

### 1. Convergence.py Jaccard/SequenceMatcher Usage ✅
- `convergence.py` imports `jaccard_similarity` and `sequence_similarity` from `datastore.models` (lines 15-16)
- `check_semantic_stability()` uses `jaccard_similarity()` at line 152
- `check_redundancy()` uses `sequence_similarity()` at line 123
- Both functions properly implemented in `models.py` (lines 58-75)

### 2. Existing Datastore Models ✅
- `LearningLogEntry` dataclass exists with fields: attempted_change, observed_outcome, severity_before, severity_after, change_summary, artifact_snippet, categories, multiplier
- `CategoryScores` dataclass exists with structural_coherence, failure_coverage, conciseness, actionability
- `MultiplierEntry` dataclass exists with multipliers dict
- Convergence constants defined: `CONVERGENCE_THRESHOLD=0.95`, `GAIN_THRESHOLD=0.02`, `STABILITY_WINDOW=2`, `REDUNDANCY_THRESHOLD=0.3`
- `Candidate` and `Frontier` dataclasses exist (v2.1 extensions)

### 3. Dependencies (pyproject.toml) ✅
- `httpx>=0.27` already present in dependencies
- No numpy/scikit-learn/sentence-transformers currently installed
- No `[project.optional-dependencies]` section exists yet (plan correctly identifies this gap)

### 4. Test Structure ✅
- Tests directory exists at `tests/` with 14 test files
- Existing tests include: test_convergence.py, test_categories.py, test_optimizer.py, test_auditor.py
- Test conventions use pytest with async auto mode
- No `test_embeddings.py` exists yet (needs creation per plan)

### 5. No Existing Embeddings Module ✅
- No `embeddings.py` or similar module exists in `src/rw_promptforge/`
- Only plan file found: `.hermes/plans/2026-09-14_192500-phase1-embedding-integration.md`
- ADR-005 exists at `docs/adrs/005-embedding-integration.md`

---

## Discrepancies Found (FAIL)

### 1. Provider.py Lacks Embedding Infrastructure ⚠️
- **Issue**: Plan assumes embedding provider needs to be created, but doesn't account for existing `Provider` class
- **Reality**: `provider.py` has working `Provider` class with httpx client, but only has `reflect()` method for chat completions
- **Impact**: Could extend existing Provider or create separate embeddings module - plan unclear on this choice

### 2. Model Name Assumption
- **Issue**: Plan mentions `nomic-embed-text` as default model
- **Reality**: No ML dependencies currently in project
- **Impact**: Plan correctly identifies need for optional `[ml]` extra with numpy, scikit-learn, sentence-transformers

### 3. Missing Test File
- **Issue**: Plan references `test_embeddings.py` but it doesn't exist yet
- **Reality**: This is expected for new feature - no conflict

---

## Recommended Modifications to Plan

### 1. Leverage Existing Provider Infrastructure
Instead of creating standalone `EmbeddingProvider`, consider:
- **Option A**: Add `embed()` method to existing `Provider` class (OpenAI-compatible endpoints support `/v1/embeddings`)
- **Option B**: Create minimal `embeddings.py` module that imports from `Provider` for consistency
- **Recommendation**: Option B - keeps separation of concerns while reusing httpx client pattern

### 2. Update models.py Semantic Similarity
Add to existing similarity functions:
```python
def semantic_similarity(a: str, b: str, provider: Provider | None = None) -> float:
    """Cosine similarity using embeddings when available, fallback to Jaccard."""
    if provider:
        # Use embedding-based cosine similarity
        pass
    return jaccard_similarity(a, b)  # fallback
```

### 3. Add Optional ML Dependencies
Update pyproject.toml:
```toml
[project.optional-dependencies]
ml = ["numpy>=1.24", "scikit-learn>=1.3"]
torch = ["torch>=2.0", "sentence-transformers>=2.2"]
```

### 4. Convergence Integration
Modify `check_semantic_stability()` to accept optional provider:
```python
def check_semantic_stability(
    current: str,
    proposed: str,
    threshold: float = 0.95,
    provider: Provider | None = None,
) -> bool:
    if provider:
        return semantic_similarity(current, proposed, provider) >= threshold
    return jaccard_similarity(current, proposed) >= threshold
```

### 5. Test Coverage Additions
Create `tests/test_embeddings.py` with:
- `test_embed_provider_local_fallback()` - Mock embedding response
- `test_embed_provider_remote_endpoint()` - Test with OpenAI-compatible endpoint
- `test_semantic_similarity_same_meaning()` - Verify cosine similarity
- `test_semantic_similarity_different_meaning()` - Verify low similarity
- `test_convergence_uses_embeddings_when_available()` - Integration test
- `test_convergence_falls_back_to_jaccard()` - Fallback test

---

## Files Examined

| File | Status | Notes |
|------|--------|-------|
| `src/rw_promptforge/convergence.py` | ✅ Read | 187 lines, imports from models.py confirmed |
| `src/rw_promptforge/datastore/models.py` | ✅ Read | 386 lines, all dataclasses confirmed |
| `src/rw_promptforge/provider.py` | ✅ Read | 91 lines, no embedding methods |
| `pyproject.toml` | ✅ Read | httpx present, no ML deps |
| `tests/` directory | ✅ Listed | 14 test files, no embeddings test yet |
| `src/rw_promptforge/embeddings.py` | ❌ Not found | Needs creation |

---

**Audit completed**: 2026-09-14T19:30:00Z
**Next step**: Proceed with implementation per plan with recommended modifications
