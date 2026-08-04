# Reverse Audit: rw-promptforge v2 Implementation Plan

**Audit Date:** 2026-08-04  
**Auditor:** Subagent reverse audit  
**Scope:** SPECMERGED_v2.md + PHASE2_PLAN_v2.md vs. actual source code  
**Verdict:** **FAIL** — Core v2 features are entirely unimplemented

---

## Summary

The v2 specification and implementation plan describe a sophisticated multi-dimensional scoring system, convergence detection, reverse audit loop, ARMORED section parsing, and safety constraints. **None of these features exist in the current codebase.** The optimizer still contains the v1 loop. All new modules (categories.py, convergence.py, multiplier.py, auditor.py) are absent. All new tests are absent.

This is a **spec-to-code gap audit**, not a code-quality audit. The plan is sound in theory but has significant mathematical, security, and edge-case gaps that would cause failures if implemented as written.

---

## Reverse Audit: FAIL

### Missed Items (Spec/Plan vs. Implementation)

- [gap] **categories.py module does not exist** → [severity: critical]
  - C1-C4 scoring logic, composite score, multiplier calculation all absent
  - Plan Step 2 (45 min) not started

- [gap] **convergence.py module does not exist** → [severity: critical]
  - `convergence_score()`, `is_converged()`, `check_redundancy()` all absent
  - Plan Step 3 (30 min) not started

- [gap] **auditor.py module does not exist** → [severity: critical]
  - `reverse_audit()` with structural/semantic/size/stagnation checks absent
  - Plan Step 4 (45 min) not started

- [gap] **multiplier.py module does not exist** → [severity: high]
  - `compute_multipliers()` for directional improvement tracking absent
  - Plan Step 2 references it but no separate file created

- [gap] **ARMORED section parsing not implemented** → [severity: high]
  - `SoulTarget.ARMORED_SECTIONS` is a hardcoded set constant
  - No `extract_armored_sections()` function exists
  - No regex/XML parser to actually extract sections from artifact text
  - Plan Step 9 (30 min) not started

- [gap] **truncate_artifact() function not implemented** → [severity: high]
  - `MAX_ARTIFACT_CHARS = 60000` defined in spec but not in code
  - No truncation logic exists anywhere
  - Plan Step 8 (evaluator truncation) mentions 4000 char cap but not implemented

- [gap] **Reflector size_budget param not added** → [severity: high]
  - `reflector/engine.py` has no `size_budget` parameter
  - No output length validation (>2× artifact size rejection)
  - Plan Step 7 (15 min) not started

- [gap] **Eval output truncation not implemented** → [severity: medium]
  - Spec says 4000 char cap per trace
  - `evaluator/shell.py` sends full stdout/stderr to LLM unbounded
  - Plan Step 8 (10 min) not started

- [gap] **v2 CLI flags not wired** → [severity: medium]
  - `--hypothesis-first`, `--semantic-threshold`, `--gain-threshold`, `--stability-threshold`, `--min-rounds`, `--output` all absent
  - `cli.py` still has v1 flag set
  - Plan Step 12 (15 min) not started

- [gap] **Optimizer loop not refactored** → [severity: critical]
  - `optimizer.py` still has v1 `optimize_skill()` and `optimize_soul()` methods
  - No forward/reverse audit loop
  - No convergence check after accepted rounds
  - No multiplier tracking in LearningLogEntry
  - Plan Step 5 (60 min) not started

- [gap] **Test files not created** → [severity: high]
  - `tests/test_categories.py` absent
  - `tests/test_convergence.py` absent
  - `tests/test_auditor.py` absent
  - Plan Step 10 (45 min) not started

- [gap] **SessionDB multiplier-aware sampling not implemented** → [severity: medium]
  - `DEFAULT_FAILURE_TYPE_WEIGHTS` exists in models.py
  - `sample_failure_cases()` uses simplistic weight*10 copies approach
  - No round_factor or recency_factor applied
  - Queries don't consume the weights dict
  - Plan Step 6 (20 min) not started

- [gap] **shell injection fix incomplete** → [severity: high]
  - `shlex.quote` used in `evaluator/shell.py:54` ✓
  - But `provider.py` exposes API key in Authorization header with no sanitization
  - No redaction of keys in logs or error output
  - Plan mentions fix but doesn't address provider header leakage

- [gap] **Credential sanitization inconsistent** → [severity: medium]
  - `_SANITIZE_PATTERNS` in `evaluator/shell.py` differs from spec's `CREDENTIAL_PATTERNS`
  - Spec has 3 patterns; code has 3 patterns but different regex
  - `Bearer \S+` pattern in code doesn't match spec's `Bearer\s+\S+` (space handling)
  - No sanitization of provider request/response logging

### Edge Cases

- [case] **Malformed ARMORED section tags** → [impact: high]
  - What if artifact has `<section name="machine_protocol"` (missing closing `>`)?
  - What if sections use HTML entities or encoded characters?
  - What if there are nested `<section>` tags?
  - No error handling defined in spec for parsing failures

- [case] **YAML frontmatter with invalid syntax** → [impact: medium]
  - `SkillTarget._parse()` calls `yaml.safe_load()` without try/except
  - Malformed YAML will raise `yaml.YAMLError` and crash optimizer
  - No graceful fallback defined

- [case] **Session DB schema changes** → [impact: high]
  - Queries assume specific table/column structure (`messages`, `session_id`, `timestamp`, `content`, `role`)
  - No version check or schema validation
  - If Hermes updates schema, all queries fail silently (returns empty list)
  - Spec acknowledges this risk but has no mitigation

- [case] **Concurrent DB access** → [impact: medium]
  - `SessionDBReader._query()` opens/closes connection per call
  - No locking or WAL mode enforcement
  - If multiple optimizer instances run simultaneously, SQLite may fail with "database is locked"

- [case] **LLM returns non-text content** → [impact: medium]
  - `Provider.reflect()` assumes `data["choices"][0]["message"]["content"]` exists
  - No validation that response has expected structure
  - Malformed JSON or empty choices will raise `KeyError`

- [case] **Artifact with no XML sections** → [impact: medium]
  - `SoulTarget` assumes artifact has `<section>` tags
  - If artifact is plain markdown, ARMORED/OPTIMIZABLE classification fails
  - No fallback to treat entire artifact as optimizable

- [case] **Empty or whitespace-only LLM response** → [impact: low]
  - Guard exists: `if not artifact or len(artifact.strip()) < 10: break`
  - But what if response is exactly 9 chars? Edge case handled but arbitrary threshold

- [case] **Provider returns HTTP error after retries** → [impact: medium]
  - `Provider.reflect()` raises last error after max_retries
  - No graceful degradation (e.g., return original artifact)
  - Caller (optimizer) doesn't catch provider errors

- [case] **Hamming distance on strings is undefined** → [impact: high]
  - Spec references `hamming_distance(new, last_3)` in convergence check
  - Hamming distance requires equal-length strings
  - Artifacts will have different lengths after reflection
  - Should use edit distance (Levenshtein) or Jaccard similarity

- [case] **Cosine similarity without embeddings** → [impact: high]
  - Spec mentions `cosine_sim(current, proposed) > 0.95`
  - No embedding model specified or implemented
  - Token overlap (Jaccard) suggested as fallback in Open Questions but not chosen
  - This signal cannot be computed as specified

- [case] **Size stability metric is wrong** → [impact: medium]
  - Spec uses `len(e.change_summary)` for size stability check
  - `change_summary` is a text description like "Modified artifact from X to Y lines"
  - This measures summary length, not artifact size
  - Should use `len(e.artifact)` or `e.size_delta`

- [case] **Fix rate < 0.2 triggers convergence** → [impact: high]
  - Spec: `fix_rate = traces_fixed / len(recent)` then `0.3 if fix_rate < 0.2 else fix_rate`
  - This means LOW fix rate (few improvements) gives HIGHER score
  - Inverted logic: converging when nothing is improving?
  - Should be `fix_rate > 0.8` for high score, or negate the condition

- [case] **Stagnation check compares against last 3 entries** → [impact: medium]
  - Spec says `hamming_distance(new, last_3) < 5%`
  - But `LearningLogEntry` doesn't store artifact text, only change_summary
  - Cannot compute distance without artifact reference

- [case] **Size multiplier cap applied per-round vs. total** → [impact: medium]
  - Spec: `new_artifact.size <= old_artifact.size × 1.5`
  - Is this per-round (each round can grow 1.5×) or total (final ≤ 1.5× original)?
  - Per-round allows exponential growth: 1.5^20 ≈ 33,000× original
  - Should be total cap from original size

- [case] **LLM judge scoring non-deterministic** → [impact: high]
  - C1, C3, C4 use "LLM judge" prompts
  - Same input can produce different scores across runs
  - Spec mentions "Average over 3 runs; use consensus" in risks but doesn't implement it
  - Multiplier computation based on noisy scores will be unstable

- [case] **No temperature variation handling** → [impact: low]
  - Provider hardcodes `temperature: 0.3`
  - No way to adjust for scoring vs. reflection (scoring might need lower temp)
  - Judge model should use temperature 0.0 for determinism

- [case] **Error paths in optimizer not handled** → [impact: medium]
  - If `reflector.reflect()` raises exception, loop breaks silently
  - No try/except around LLM call
  - No recovery strategy (e.g., retry with fallback model)

- [case] **History overflow not bounded** → [impact: low]
  - `history.append()` grows unbounded
  - Spec says "Compare against last 3 history entries" but doesn't trim
  - Memory leak for long-running optimizations

- [case] **Artifact path with spaces/special chars** → [impact: medium]
  - `shlex.quote` used for eval command ✓
  - But `Path(artifact_path).read_text()` doesn't validate path
  - Symlinks, relative paths, permission errors not handled

### Recommendations

#### P0 — Fix Mathematical Errors in Convergence (Blocks Implementation)

1. **Rewrite `convergence_score()` logic** — The fix_rate inversion is backwards. Low fix rate should NOT indicate convergence. Proposed formula:
   ```python
   def convergence_score(history):
       if len(history) < 2:
           return 0.0
       recent = history[-3:]
       
       # Signal 1: Severity trend (improving or stable)
       severities = [e.severity_after for e in recent]
       severity_stable = all(s >= severities[0] for s in severities)
       
       # Signal 2: Size stability (artifact size not fluctuating)
       sizes = [len(e.artifact) for e in recent]  # Fix: use artifact length, not change_summary
       size_stable = max(sizes) - min(sizes) < 100
       
       # Signal 3: Fix rate (HIGH rate = still improving, LOW rate = converged)
       traces_fixed = sum(1 for e in recent if e.observed_outcome == "improvement")
       fix_rate = traces_fixed / len(recent)
       
       # Fixed: High fix rate = NOT converged, low fix rate = converged
       score = (0.4 if severity_stable else 0.0) + \
               (0.3 if size_stable else 0.0) + \
               (0.3 if fix_rate < 0.3 else 0.0)  # Inverted: low fix rate = convergence
       
       return min(score, 1.0)
   ```

2. **Replace hamming_distance with edit_distance or Jaccard** — Hamming distance requires equal-length strings. Use `difflib.SequenceMatcher` or Levenshtein distance.

3. **Implement Jaccard similarity for semantic stability** — Cosine similarity requires embeddings. Jaccard on token sets is a reasonable fallback:
   ```python
   def jaccard_similarity(a: str, b: str) -> float:
       tokens_a = set(a.lower().split())
       tokens_b = set(b.lower().split())
       intersection = tokens_a & tokens_b
       union = tokens_a | tokens_b
       return len(intersection) / len(union) if union else 0.0
   ```

4. **Store artifact in LearningLogEntry** — Need to store artifact hash or full text to compute distance metrics.

#### P1 — Implement Core v2 Modules

5. **Create `categories.py`** — Implement C1-C4 scoring:
   - C1: Structural coherence (LLM judge prompt)
   - C2: Failure coverage (trace matching via keyword overlap)
   - C3: Conciseness (token efficiency ratio)
   - C4: Actionability (imperative verb density)

6. **Create `convergence.py`** — Implement fixed convergence detection with Jaccard similarity.

7. **Create `auditor.py`** — Implement reverse audit with:
   - ARMORED section preservation check
   - Semantic change validation
   - Size cap enforcement (TOTAL, not per-round)
   - Stagnation detection using edit distance

8. **Create `multiplier.py`** — Implement directional improvement tracking.

#### P2 — Fix Security Gaps

9. **Add API key redaction in Provider** — Sanitize Authorization header in logs:
   ```python
   import re
   _KEY_PATTERN = re.compile(r"Bearer\s+\S+")
   def _redact_auth(header: str) -> str:
       return _KEY_PATTERN.sub("Bearer [REDACTED]", header)
   ```

10. **Add try/except around LLM calls** — Catch provider errors and return original artifact:
    ```python
    try:
        artifact = self.reflector.reflect(...)
    except Exception as e:
        log.warning(f"Reflection failed: {e}")
        break
    ```

11. **Validate YAML parsing** — Wrap `yaml.safe_load()` in try/except with fallback.

#### P3 — Add Missing Safety Constraints

12. **Implement `truncate_artifact()`** — Head+tail truncation at 60000 chars.

13. **Add eval output truncation** — Cap at 4000 chars before sending to LLM.

14. **Add size_budget to reflector** — Reject outputs > 2× artifact size.

15. **Implement ARMORED section extraction** — Regex parser for `<section name="...">` tags with error handling for malformed input.

16. **Add total size cap** — Track original artifact size, enforce final ≤ 1.5× original (not per-round).

#### P4 — Fix Edge Cases

17. **Add DB schema validation** — Check for required tables/columns on init, log warning if missing.

18. **Add SQLite WAL mode** — Enable WAL for concurrent access safety.

19. **Bounded history** — Trim history to last N entries to prevent memory leak.

20. **Handle empty/whitespace responses** — Already has 10-char guard, but add explicit check for None.

21. **Path validation** — Check for symlinks, permissions, and special characters before processing.

#### P5 — Add Tests

22. **Test categories.py** — 6-8 tests for scoring logic, composite calculation, edge cases.

23. **Test convergence.py** — 6-8 tests for convergence detection, redundancy check, edge cases.

24. **Test auditor.py** — 6-8 tests for structural check, semantic check, size check, stagnation.

25. **Test ARMORED parsing** — Valid sections, malformed tags, missing sections, nested tags.

26. **Test truncation** — Head+tail split, exact boundary, under-limit artifacts.

27. **Test shell injection** — Paths with spaces, special chars, shell metacharacters.

28. **Test credential sanitization** — API keys, tokens, Bearer headers in eval output.

29. **Test provider error handling** — HTTP errors, malformed responses, timeouts.

#### P6 — CLI and UX

30. **Wire v2 CLI flags** — `--hypothesis-first`, `--semantic-threshold`, `--gain-threshold`, `--stability-threshold`, `--min-rounds`, `--output`.

31. **Add progress output** — Show round number, scores, multipliers, convergence signals.

32. **Add REVIEW result handling** — Write diff to `{path}.review.md`, print summary.

33. **Add dry-run mode** — Show proposed changes without writing.

#### P7 — Determinism and Reliability

34. **Add LLM judge consensus** — Run scoring 3 times, take median score.

35. **Fix temperature for scoring** — Use temperature 0.0 for judge calls, 0.3 for reflection.

36. **Add scoring prompt caching** — Stable system prompt prefix for provider cache hit.

37. **Document non-determinism risk** — Add warning that multi-dimensional scores are estimates.

---

## Appendix: Implementation Status Matrix

| Spec Feature | Status | Files | Tests |
|--------------|--------|-------|-------|
| 4-category scoring | ❌ NOT STARTED | categories.py (missing) | test_categories.py (missing) |
| Convergence detection | ❌ NOT STARTED | convergence.py (missing) | test_convergence.py (missing) |
| Reverse audit | ❌ NOT STARTED | auditor.py (missing) | test_auditor.py (missing) |
| Multiplier tracking | ❌ NOT STARTED | multiplier.py (missing) | N/A |
| ARMORED parsing | ❌ NOT STARTED | targets/soul.py (partial) | N/A |
| Artifact truncation | ❌ NOT STARTED | N/A | N/A |
| Eval output cap | ❌ NOT STARTED | evaluator/shell.py (missing) | N/A |
| Size budget | ❌ NOT STARTED | reflector/engine.py (missing) | N/A |
| v2 CLI flags | ❌ NOT STARTED | cli.py (missing) | N/A |
| Optimizer refactor | ❌ NOT STARTED | optimizer.py (v1 only) | N/A |
| Shell injection fix | ⚠️ PARTIAL | evaluator/shell.py (shlex.quote only) | N/A |
| Credential sanitization | ⚠️ PARTIAL | evaluator/shell.py (inconsistent patterns) | N/A |
| SessionDB weights | ⚠️ PARTIAL | session_db.py (weights exist, not used) | N/A |

**Overall: 0% implemented, 100% remaining**

---

## Mathematical Soundness Review

### Convergence Detection Issues

1. **Inverted fix_rate logic** — Low fix rate should indicate convergence (nothing left to fix), but the formula gives HIGH score for low fix rate. This is correct in direction but the threshold interpretation is unclear.

2. **Hamming distance on variable-length strings** — Mathematically undefined. Must use edit distance or Jaccard.

3. **Cosine similarity without embeddings** — Cannot be computed as specified. Jaccard on token sets is the practical fallback.

4. **Size stability metric** — Uses `len(change_summary)` which measures description length, not artifact size. Must use `len(artifact)`.

5. **Per-round vs. total size cap** — Ambiguous. Per-round allows exponential growth. Must be total from original.

6. **Stagnation check requires artifact storage** — LearningLogEntry doesn't store artifact, only summary. Must add artifact hash or full text.

### LLM Judge Determinism Issues

1. **Non-deterministic scoring** — LLM judges produce different scores on repeated calls. Must use consensus (3 runs, median).

2. **Temperature not adjustable** — Hardcoded 0.3 for all calls. Scoring should use 0.0.

3. **No prompt stability** — Judge prompts change with each call (dynamic content). System prompt is stable but user prompt varies.

4. **Weight normalization** — C1-C4 weights sum to 1.0 ✓, but no validation that weights are positive.

### Multiplier Computation Issues

1. **Division by zero** — `max(score_{t-1}, ε)` where ε is undefined. Should be explicit epsilon (e.g., 1e-6).

2. **NaN handling** — If score is NaN (e.g., from LLM returning non-numeric), multiplier becomes NaN. Must validate.

3. **Extreme values** — Multiplier can be arbitrarily large if previous score is near zero. Must cap at reasonable bounds (e.g., ±5.0).

---

## Conclusion

The v2 spec is well-designed in theory but contains several mathematical errors that would cause incorrect convergence behavior if implemented as written. The most critical issues are:

1. **Inverted fix_rate logic** in convergence score
2. **Undefined hamming distance** on variable-length strings
3. **Unimplementable cosine similarity** without embedding model
4. **Wrong size stability metric** (summary length vs. artifact size)
5. **Ambiguous size cap** (per-round vs. total)

Additionally, **zero percent of the v2 features are implemented**. The codebase is still entirely v1. The plan is viable but requires corrections to the mathematical formulas before implementation begins.

**Recommendation:** Fix the convergence math, then implement modules in priority order: P0 (math fixes) → P1 (core modules) → P2 (security) → P3 (safety) → P4 (edge cases) → P5 (tests) → P6 (CLI) → P7 (determinism).
