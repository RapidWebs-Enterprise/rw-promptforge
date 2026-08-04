# rw-promptforge v2 — Implementation Plan (LOW Mode)

**Project:** rw-promptforge  
**Date:** 2026-08-04  
**Mode:** LOW (internal refactoring, speed > rigor)  
**Source:** docs/SPECMERGED_v2.md  
**Target:** Add convergence detection, multi-dimensional scoring, and safety to v1 optimizer

---

## 1. Goal

Transform rw-promptforge v1 (unbounded expansion, no convergence) into v2 with:
- 4-category multi-dimensional scoring
- Forward/reverse audit loop
- Convergence detection (97% confidence gate)
- Redundancy/diminishing-returns detection
- Artifact size caps and ARMORED section protection
- Shell injection fix

---

## 2. Current State

```
src/rw_promptforge/
├── __init__.py
├── cli.py                 # CLI entry — already updated (v1 → v2 wiring)
├── optimizer.py           # Core loop — needs convergence + reverse audit
├── reflector/
│   └── engine.py          # LLM reflection — needs size_budget param
├── evaluator/
│   └── shell.py           # Eval runner — needs output truncation
├── datastore/
│   └── session_db.py      # Failure trace queries — needs multiplier sampling
├── targets/
│   ├── soul.py            # SOUL.md target — needs ARMORED parsing
│   └── skill.py           # Skill target — needs region parsing
└── (NEW)
    ├── categories.py      # 4-category scoring
    ├── convergence.py     # Convergence detection
    ├── multiplier.py      # Multiplier calculation
    └── auditor.py         # Reverse audit logic
```

**Existing tests:** 18 passing in `tests/test_optimizer.py` + `tests/test_bootstrap.py`

---

## 3. Files to Create/Modify

### New Files (4)

| File | Lines (est) | Purpose |
|------|-------------|---------|
| `src/rw_promptforge/categories.py` | ~150 | 4-category scoring logic |
| `src/rw_promptforge/convergence.py` | ~120 | Convergence detection + redundancy check |
| `src/rw_promptforge/multiplier.py` | ~80 | Directional improvement tracking |
| `src/rw_promptforge/auditor.py` | ~200 | Reverse audit: structural + semantic + size checks |

### Modified Files (5)

| File | Changes |
|------|---------|
| `src/rw_promptforge/optimizer.py` | Add convergence loop, reverse audit call, multiplier tracking |
| `src/rw_promptforge/reflector/engine.py` | Add `size_budget` param, cap output length |
| `src/rw_promptforge/evaluator/shell.py` | Add output truncation (4000 char cap), keep sanitize |
| `src/rw_promptforge/datastore/session_db.py` | Add multiplier-aware sampling (FAILURE_TYPE_WEIGHTS) |
| `src/rw_promptforge/targets/soul.py` | Add ARMORED section extraction |

### Test Files (3)

| File | Purpose |
|------|---------|
| `tests/test_categories.py` | Unit tests for 4-category scoring |
| `tests/test_convergence.py` | Unit tests for convergence detection |
| `tests/test_auditor.py` | Unit tests for reverse audit logic |

---

## 4. Step-by-Step Plan

### Step 1: Core Data Structures (30 min)
- Add `CategoryScores`, `MultiplierEntry`, `ConvergenceState` dataclasses to `models.py`
- Add `FAILURE_TYPE_WEIGHTS` and `ARMORED_SECTIONS` constants
- Commit: `feat: add v2 data structures for multi-dimensional scoring`

### Step 2: Categories Module (45 min)
- Implement `score_categories(artifact, traces)` → `CategoryScores`
- C1: Structural coherence (LLM judge prompt)
- C2: Failure coverage (trace matching)
- C3: Conciseness (token efficiency ratio)
- C4: Actionability (imperative verb density)
- Add `compute_composite()` and `compute_multipliers()`
- Commit: `feat: add 4-category scoring with composite score`

### Step 3: Convergence Module (30 min)
- Implement `convergence_score(history)` → float [0,1]
- Implement `is_converged(history)` → bool
- Implement `check_redundancy(history)` → bool
- Commit: `feat: add convergence detection with multi-signal scoring`

### Step 4: Auditor Module (45 min)
- Implement `reverse_audit(old, new, traces)` → `PASS | FAIL | REVIEW`
- Structural check: ARMORED sections preserved
- Semantic check: changes address failure traces
- Size check: new <= old × 1.5
- Stagnation check: hamming distance against last 3 entries
- Commit: `feat: add reverse audit with structural + semantic checks`

### Step 5: Refactor Optimizer Loop (60 min)
- Replace `optimize()` with `optimize_artifact()` using forward/reverse loop
- Add convergence check after each accepted round
- Add multiplier tracking to LearningLogEntry
- Add size budget to reflector call
- Keep existing test suite passing
- Commit: `refactor: replace v1 loop with RefineStop forward/reverse audit`

### Step 6: SessionDB Multiplier Sampling (20 min)
- Add `get_contrastive_traces(name, weights, limit)` method
- Weight samples by FAILURE_TYPE_WEIGHTS × round_factor × recency_factor
- Commit: `feat: add multiplier-aware trace sampling`

### Step 7: Reflector Size Budget (15 min)
- Add `size_budget` param to `Reflector.reflect()`
- Reject outputs > 2× artifact size
- Commit: `fix: add size budget to reflector output validation`

### Step 8: Evaluator Output Truncation (10 min)
- Cap eval output at 4000 chars before sending to LLM
- Commit: `fix: cap eval output to prevent context overflow`

### Step 9: Target ARMORED Parsing (30 min)
- Add `extract_armored_sections(artifact)` to `targets/soul.py`
- Parse `<section name="...">` XML-like tags
- Return dict of armored section names → content
- Commit: `feat: add ARMORED section extraction for SOUL.md targets`

### Step 10: Tests (45 min)
- `tests/test_categories.py` — 6-8 tests for scoring + composite
- `tests/test_convergence.py` — 6-8 tests for convergence detection
- `tests/test_auditor.py` — 6-8 tests for reverse audit
- Run full suite: `uv run pytest tests/ -q`
- Commit: `test: add v2 unit tests for categories, convergence, auditor`

### Step 11: Integration Test (20 min)
- Run `rw-promptforge optimize` on a test artifact
- Verify convergence triggers correctly
- Verify ARMORED sections preserved
- Verify size cap enforced
- Commit: `test: integration test for RefineStop v2 loop`

### Step 12: CLI Wiring (15 min)
- Add new flags to `cli.py` (already partially done)
- Wire `--hypothesis-first`, `--semantic-threshold`, `--gain-threshold`
- Commit: `feat: add v2 CLI flags for convergence and scoring`

---

## 5. Estimated Timeline

| Step | Time | Cumulative |
|------|------|------------|
| 1. Core data structures | 30 min | 30 min |
| 2. Categories module | 45 min | 1h 15m |
| 3. Convergence module | 30 min | 1h 45m |
| 4. Auditor module | 45 min | 2h 30m |
| 5. Refactor optimizer loop | 60 min | 3h 30m |
| 6. SessionDB sampling | 20 min | 3h 50m |
| 7. Reflector size budget | 15 min | 4h 05m |
| 8. Evaluator truncation | 10 min | 4h 15m |
| 9. ARMORED parsing | 30 min | 4h 45m |
| 10. Tests | 45 min | 5h 30m |
| 11. Integration test | 20 min | 5h 50m |
| 12. CLI wiring | 15 min | 6h 05m |

**Total: ~6 hours** (can be parallelized across 2-3 subagents)

---

## 6. Verification Strategy

### Unit Tests (automated)
```bash
uv run pytest tests/test_categories.py tests/test_convergence.py tests/test_auditor.py -v
```

### Integration Test (manual)
```bash
# Test convergence on a small artifact
export OPENROUTER_API_KEY="sk-or-v1-..."
uv run rw-promptforge optimize \
  ~/Workspaces/rw-promptforge/soul-test/soul-part1.md \
  --target-type soul \
  --provider openrouter \
  --endpoint https://openrouter.ai/api/v1 \
  --model deepseek/deepseek-v4-flash \
  --max-rounds 5 \
  --save 2>&1 | tee /tmp/v2-test.log

# Check: converged? size capped? ARMORED preserved?
grep -E "(Converged|rounds|size_delta|ARMORED)" /tmp/v2-test.log
```

### Regression Tests
```bash
uv run pytest tests/ -q  # All 18 existing tests must pass
```

---

## 7. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| LLM judge scores are noisy | Medium | Low | Average over 3 runs; use consensus |
| ARMORED section parsing breaks on malformed input | Low | Medium | Graceful fallback: treat whole artifact as optimizable |
| Convergence threshold too aggressive | Medium | Low | Make thresholds configurable; default to conservative |
| Multiplier computation causes infinite loop | Low | Low | Hard cap on rounds; redundancy check catches this |
| SessionDB schema changes break trace queries | Medium | Medium | Add version check + graceful degradation |

---

## 8. Open Questions

1. **Judge model for C1/C3/C4**: Use same reflection LM or separate? → Separate (cheaper LM for scoring)
2. **Embedding for semantic similarity**: Sentence transformers or token overlap? → Token overlap (Jaccard) as fallback, embeddings if available
3. **Human review UX**: How does `REVIEW` result surface to user? → Write diff to `{path}.review.md`, print summary to stdout
4. **Cross-artifact learning**: Should failure patterns from one skill inform another? → Not in v2; deferred

---

## 9. Success Criteria

- [ ] All 18 existing tests pass
- [ ] 18+ new tests pass (categories, convergence, auditor)
- [ ] Live test on SOUL.md section: converges within 3-5 rounds
- [ ] Artifact size never exceeds 1.5× original
- [ ] ARMORED sections preserved across all rounds
- [ ] Shell injection vector patched (shlex.quote)
- [ ] Eval output capped at 4000 chars
- [ ] Multiplier output shows directional signal per category
