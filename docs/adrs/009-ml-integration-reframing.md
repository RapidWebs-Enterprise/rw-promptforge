# ADR-009: ML Integration Reframing

**Date:** 2026-09-14  
**Status:** Accepted  
**Context:** Reverse audit identified architectural conflict

## Decision

Reframe ML integration as **additive enhancement** rather than replacement of existing token-based methods.

## Rationale

1. **Architectural consistency:** Previous reverse audit deliberately chose Jaccard over cosine (convergence.py line 4)
2. **Minimal risk:** Existing behavior unchanged when --ml-mode disabled
3. **Progressive enhancement:** ML features available when infrastructure present, fallback to token methods otherwise
4. **Clear boundaries:** 
   - Convergence detection: Token-based (Jaccard/SequenceMatcher) - UNCHANGED
   - Failure clustering: Embedding-based (HDBSCAN) - NEW
   - Trace reranking: Two-stage (embeddings + CrossEncoder) - NEW
   - Pattern classification: ML-based (HistGB) - NEW

## Consequences

- **Positive:** No breaking changes to existing optimization loop
- **Positive:** Clear separation between legacy and ML paths
- **Negative:** Slightly more complex codebase (two paths for trace selection)
- **Negative:** Need to maintain both token-based and embedding-based logic

## Alternatives Considered

1. **Replace Jaccard with embeddings:** Rejected (contradicts prior audit, adds complexity without clear benefit)
2. **Embeddings-only mode:** Rejected (removes fallback, increases risk)
3. **Hybrid approach (current):** Adopted (best of both worlds)
