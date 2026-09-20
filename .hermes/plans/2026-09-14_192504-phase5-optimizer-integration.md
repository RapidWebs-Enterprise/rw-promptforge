---
name: Phase 5 - Optimizer Integration
description: Integrate ML components into optimizer loop for cluster-aware beam sampling
status: proposed
created: 2026-09-14
related_spec: spec-ml-integration.md
related_adrs: [005, 006, 007, 008]
---

# Plan: Phase 5 — Optimizer Integration

## Goal
Integrate ML components (embeddings, clustering, classifier, reranker) into optimizer loop. Add cluster-aware beam sampling per C-MOP research.

## Files to Create/Modify

| File | Action | Lines | Purpose |
|------|--------|-------|---------|
| `src/rw_promptforge/optimizer.py` | MODIFY | ~50 | Add ML-aware beam sampling |
| `src/rw_promptforge/cli.py` | MODIFY | +30 | Add --ml-mode flag |
| `src/rw_promptforge/provider.py` | MODIFY | +20 | Add embedding provider config |
| `tests/test_optimizer_ml.py` | CREATE | ~40 | Integration tests |

## Step-by-Step Plan

### Step 1: Update optimizer.py
- Add `MLBeamSampler` class
- Modify `_optimize()` to use cluster-aware sampling when ML mode enabled
- Add `_select_traces_for_beam()` method

### Step 2: Update cli.py
- Add `--ml-mode` flag
- Add `--embedding-endpoint` flag
- Pass ML config to Optimizer

### Step 3: Update provider.py
- Add `EmbeddingProvider` initialization
- Wire through config

### Step 4: Add tests
- Test ML mode enabled
- Test cluster-aware beam selection
- Test graceful degradation when ML unavailable

## Test Plan
```
test_optimizer_uses_ml_when_enabled()
test_cluster_aware_beam_selects_diverse_traces()
test_optimizer_falls_back_to_token_matching()
test_cli_ml_mode_flag_works()
```

## Risks
| Risk | Mitigation |
|------|------------|
| Breaking existing behavior | ML mode opt-in via flag |
| Performance impact | Only when --ml-mode enabled |
| Config complexity | Sensible defaults |

## Verification
```bash
PYTHONPATH=src:. python3 -m pytest tests/test_optimizer_ml.py -v
PYTHONPATH=src:. python3 -m pytest tests/test_optimizer.py -v  # Ensure no regression
```
