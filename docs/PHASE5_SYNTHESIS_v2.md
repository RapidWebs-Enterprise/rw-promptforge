# rw-promptforge v2 — Final Implementation Plan (Synthesized)

**Project:** rw-promptforge  
**Date:** 2026-08-04  
**Mode:** LOW  
**Status:** POST-AUDIT SYNTHESIS  
**Sources:** SPECMERGED_v2.md + Forward Audit + Reverse Audit  

---

## Audit Summary

### Forward Audit: ✅ PASS (with conditions met)
- 18/18 claims verified against actual source code
- 12 issues found, all addressed in this plan
- Key resolution: Added ArtifactMeta, truncate_artifact, hamming_distance to Step 1

### Reverse Audit: ⚠️ FAIL → PATCHED
- **CRITICAL**: 6 mathematical errors in convergence logic (fixed below)
- **HIGH**: 21 edge cases identified (all addressed)
- **Recommendation**: Fix P0 math errors before any implementation

---

## Fixed: Convergence Math Errors (P0 — Blocks Implementation)

### Error 1: Inverted fix_rate logic
**Bug**: Low fix rate (few improvements) was giving HIGH convergence score.  
**Fix**: Invert the condition — low fix rate = converged (nothing left to fix).

```python
# BEFORE (wrong):
fix_score = 0.3 if fix_rate < 0.2 else fix_rate  # low fix rate = high score

# AFTER (correct):
fix_score = 0.3 if fix_rate < 0.3 else 0.0  # low fix rate = convergence signal
```

### Error 2: Hamming distance on variable-length strings
**Bug**: `hamming_distance()` requires equal-length strings. Artifacts change size.  
**Fix**: Use `difflib.SequenceMatcher.ratio()` (Jaccard-like on character level).

```python
import difflib

def sequence_similarity(a: str, b: str) -> float:
    """Return similarity ratio [0.0, 1.0] between two strings."""
    return difflib.SequenceMatcher(None, a, b).ratio()
```

### Error 3: Cosine similarity without embeddings
**Bug**: Spec calls `cosine_sim(current, proposed)` but no embedding model.  
**Fix**: Use Jaccard token similarity as fallback (spec already mentioned this).

```python
def jaccard_similarity(a: str, b: str) -> float:
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union) if union else 0.0
```

### Error 4: Wrong size stability metric
**Bug**: `len(e.change_summary)` measures description length, not artifact size.  
**Fix**: Store artifact hash in LearningLogEntry, compute size from artifact.

```python
@dataclass
class LearningLogEntry:
    # ... existing fields ...
    artifact_hash: str = field(default="")  # NEW: for size/stability tracking
```

### Error 5: Per-round vs. total size cap
**Bug**: `new.size <= old.size × 1.5` per-round allows exponential growth (1.5^20 ≈ 33,000×).  
**Fix**: Track original size, enforce `current.size <= original_size × 1.5` TOTAL.

```python
# In optimizer loop:
original_size = len(artifact)  # captured at start
# ...
if len(candidate) > original_size * SIZE_MULTIPLIER_CAP:
    audit_result = "FAIL"  # not REVIEW — hard reject
```

### Error 6: Stagnation check requires artifact storage
**Bug**: Spec compares against "last 3 history entries" but entries don't store artifacts.  
**Fix**: Store artifact hash (or first/last 200 chars) in LearningLogEntry.

---

## Implementation Steps (Revised)

### Step 1: Core Data Structures + Utilities (45 min)
- Add `ArtifactMeta` dataclass to `models.py`
- Add `artifact_hash` and `artifact_snippet` fields to `LearningLogEntry`
- Add `truncate_artifact()` utility function
- Add `sequence_similarity()` utility (replaces hamming_distance)
- Add `jaccard_similarity()` utility (replaces cosine_sim)
- Commit: `feat: add v2 data structures and similarity utilities`

### Step 2: Categories Module (45 min)
- Create `src/rw_promptforge/categories.py`
- C1: Structural coherence (LLM judge)
- C2: Failure coverage (trace matching)
- C3: Conciseness (token efficiency)
- C4: Actionability (imperative verb density)
- `compute_composite()` and `compute_multipliers()`
- Commit: `feat: add 4-category scoring with composite score`

### Step 3: Convergence Module (45 min)
- Create `src/rw_promptforge/convergence.py`
- Fix all 6 math errors from reverse audit
- Use Jaccard for semantic stability, SequenceMatcher for stagnation
- Track original artifact size for total cap
- Commit: `feat: add convergence detection with fixed math`

### Step 4: Auditor Module (45 min)
- Create `src/rw_promptforge/auditor.py`
- Structural check: ARMORED sections preserved
- Semantic check: changes address failure traces
- Size check: TOTAL cap (not per-round)
- Stagnation check: SequenceMatcher against last 3 entries
- Commit: `feat: add reverse audit with structural + semantic checks`

### Step 5: Refactor Optimizer Loop (60 min)
- Replace `optimize()` with v2 forward/reverse loop
- Add convergence check after each accepted round
- Add multiplier tracking to LearningLogEntry
- Store artifact_hash in history entries
- Keep existing 18 tests passing
- Commit: `refactor: replace v1 loop with RefineStop forward/reverse audit`

### Step 6: SessionDB Trace API (20 min)
- Add `get_contrastive_traces(name, weights, limit)` method
- Return flat list (not wrapped object) to match spec
- Apply FAILURE_TYPE_WEIGHTS × round_factor × recency_factor
- Commit: `feat: add multiplier-aware trace sampling`

### Step 7: Reflector Size Budget (15 min)
- Add `size_budget` param to `Reflector.reflect()`
- Reject outputs > 2× artifact size
- Commit: `fix: add size budget to reflector output validation`

### Step 8: Evaluator Output Truncation (10 min)
- Cap eval output at 4000 chars before sending to LLM
- Commit: `fix: cap eval output to prevent context overflow`

### Step 9: ARMORED Section Parsing (30 min)
- Add `extract_armored_sections(artifact)` to `targets/soul.py`
- Parse `<section name="...">` tags with error handling
- Fallback: treat whole artifact as optimizable if no tags found
- Commit: `feat: add ARMORED section extraction for SOUL.md targets`

### Step 10: Tests (60 min)
- `tests/test_categories.py` — 8 tests
- `tests/test_convergence.py` — 8 tests (including fixed math)
- `tests/test_auditor.py` — 8 tests
- `tests/test_utilities.py` — 6 tests (truncate, jaccard, sequence_similarity)
- Run full suite: `uv run pytest tests/ -q`
- Commit: `test: add v2 unit tests`

### Step 11: Integration Test (20 min)
- Run on test artifact, verify convergence
- Verify ARMORED sections preserved
- Verify size cap enforced
- Commit: `test: integration test for RefineStop v2 loop`

### Step 12: CLI Wiring (15 min)
- Add `--hypothesis-first`, `--semantic-threshold`, `--gain-threshold`, `--stability-threshold`, `--min-rounds`, `--output`
- Commit: `feat: add v2 CLI flags`

---

## Risk Matrix (Post-Audit)

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| LLM judge scores noisy | Medium | Low | Run 3x, take median; use temperature 0.0 for scoring |
| ARMORED parsing breaks on malformed input | Low | Medium | Graceful fallback: whole artifact = optimizable |
| Convergence threshold too aggressive | Medium | Low | Make thresholds configurable; default conservative |
| Multiplier computation NaN | Low | Low | Cap multipliers at ±5.0; validate scores before compute |
| SessionDB schema changes | Medium | Medium | Add version check + fallback to empty traces |
| Jaccard similarity too coarse | Medium | Low | Add token n-gram option; fallback to character-level |

---

## Success Criteria

- [ ] All 18 existing tests pass
- [ ] 30+ new tests pass
- [ ] Live test: converges within 3-5 rounds on SOUL.md section
- [ ] Artifact size never exceeds 1.5× original (total, not per-round)
- [ ] ARMORED sections preserved across all rounds
- [ ] Shell injection patched (shlex.quote)
- [ ] Eval output capped at 4000 chars
- [ ] Multiplier output shows directional signal per category
- [ ] Convergence score formula mathematically sound (reverse audit verified)

---

## Files Changed

| File | Action | Lines (est) |
|------|--------|-------------|
| `src/rw_promptforge/models.py` | Modify | +30 |
| `src/rw_promptforge/categories.py` | Create | ~150 |
| `src/rw_promptforge/convergence.py` | Create | ~120 |
| `src/rw_promptforge/auditor.py` | Create | ~200 |
| `src/rw_promptforge/optimizer.py` | Modify | +80 |
| `src/rw_promptforge/reflector/engine.py` | Modify | +20 |
| `src/rw_promptforge/evaluator/shell.py` | Modify | +10 |
| `src/rw_promptforge/datastore/session_db.py` | Modify | +30 |
| `src/rw_promptforge/targets/soul.py` | Modify | +40 |
| `tests/test_categories.py` | Create | ~80 |
| `tests/test_convergence.py` | Create | ~80 |
| `tests/test_auditor.py` | Create | ~80 |
| `tests/test_utilities.py` | Create | ~60 |

**Total: ~1050 lines added/modified**

---

## Dual Audit Sign-Off

### Forward Audit: ✅ PASS (with conditions)
- All file paths verified
- All class/function references verified
- 18/18 tests passing baseline confirmed
- Blocking issues addressed in revised plan

### Reverse Audit: ⚠️ FAIL → PATCHED
- 6 critical math errors fixed
- 21 edge cases addressed
- Jaccard/SequenceMatcher substitutions implemented
- Total size cap clarified
- Artifact storage in history entries added

**Plan is ready for sign-off.**
