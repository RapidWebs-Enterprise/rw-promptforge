## Forward Audit: FAIL (with conditions)

### Verified Claims

- **File paths exist** → All 6 source files confirmed present at stated paths via `find` + `wc -l`
- **optimizer.py: 267 lines** → `wc -l` reports 267 lines ✅
- **reflector/engine.py: 198 lines** → `wc -l` reports 198 lines ✅
- **evaluator/shell.py: 131 lines** → `wc -l` reports 131 lines ✅
- **session_db.py: 326 lines** → `wc -l` reports 326 lines ✅
- **targets/soul.py: 51 lines** → `wc -l` reports 51 lines ✅
- **targets/skill.py: 71 lines** → `wc -l` reports 71 lines ✅
- **18 existing tests passing** → `uv run pytest tests/ -q` reports "18 passed in 0.16s" ✅
- **`Reflector.reflect()` accepts (artifact, failure_traces, history)** → Confirmed at engine.py:62-67 ✅
- **`Reflector.reflect_with_verification()` exists** → Confirmed at engine.py:88-111 ✅
- **`Reflector.reflect_hypothesis_first()` exists** → Confirmed at engine.py:128-172 ✅
- **`SessionDBReader.get_contrastive_summary()` exists** → Confirmed at session_db.py:265-284 ✅
- **`SessionDBReader.sample_failure_cases()` exists with weight logic** → Confirmed at session_db.py:241-263 ✅
- **`SessionDBReader.find_protocol_violations()` exists** → Confirmed at session_db.py:146-180 ✅
- **`SessionDBReader.find_corrections()` exists** → Confirmed at session_db.py:97-144 ✅
- **`SessionDBReader.find_tool_failures()` exists** → Confirmed at session_db.py:182-221 ✅
- **`SoulTarget.ARMORED_SECTIONS` set matches spec** → Both contain: machine_protocol, project_registry, skill_gate, budget_guards, reality_check, process_level_discipline ✅
- **`DEFAULT_FAILURE_TYPE_WEIGHTS` in models.py matches spec** → protocol_violation: 2.0, general: 1.0, tool_failure: 0.5 ✅
- **`shlex.quote` already used in evaluator/shell.py** → Line 54: `safe_path = shlex.quote(artifact_path)` ✅
- **Credential sanitization already in evaluator/shell.py** → `_sanitize()` with 3 patterns at lines 12-24 ✅
- **`MAX_ROUNDS_CAP = 20` already in optimizer.py** → Line 20 ✅
- **`LearningLogEntry` fields match spec** → attempted_change, observed_outcome, severity_before, severity_after, change_summary all present ✅
- **`OptimizeResult` fields in spec (artifact, rounds, failures_found, converged, failure_summary, learning_log)** → Confirmed at optimizer.py:24-43 ✅
- **`SoulTarget` class exists with `content` property** → Confirmed at soul.py:8-51 ✅
- **`SkillTarget` class exists with `content`, `frontmatter`, `body`, `name`, `triggers`** → Confirmed at skill.py:8-71 ✅

### Found Issues

1. **`multiplier.py` not listed as a new file — `compute_multipliers()` is in spec but plan omits it**
   - The spec (Section 3.1) defines `multiplier[k] = (score_t - score_{t-1}) / max(score_{t-1}, ε)`. The plan's Step 2 says to add `compute_multipliers()` inside `categories.py`, but the plan's file list only creates `categories.py`, `convergence.py`, and `auditor.py`. There is no `multiplier.py` in the plan's "New Files" table.
   - Impact: Medium. The multiplier function either needs to live in `categories.py` (plan's Step 2 implies this) or the plan is incomplete. The spec's pseudocode in Section 4 references `multipliers = compute_multipliers(scores, prev_scores)` but the plan doesn't explicitly assign ownership.

2. **`ArtifactMeta` dataclass referenced in spec does not exist in codebase**
   - Spec Section 2.1 defines `ArtifactMeta` with fields: name, type, total_lines, total_chars, region_count, size_mb, last_modified. No such class exists in `datastore/models.py` or anywhere else.
   - Impact: Medium. The plan's Step 5 (optimizer refactor) references `meta = parse_artifact_meta()` and `meta.size_mb`, but there's no model to support this. Must be created.

3. **`get_contrastive_traces()` method does not exist — only `get_contrastive_summary()` exists**
   - The spec's pseudocode (Section 8, line 455) references `db.get_contrastive_traces(artifact.name, limit=MAX_EFFECTIVE_TRACES, weights=FAILURE_TYPE_WEIGHTS)`. The actual code has `get_contrastive_summary(skill_name=None, limit=5)` which returns a `ContrastiveTraces` object, not a list of traces.
   - The plan's Step 6 says to "Add `get_contrastive_traces(name, weights, limit)` method" — this would be a new method. But the spec pseudocode already uses this name. The current `get_contrastive_summary` returns the wrapped object; the spec expects a direct list-returning method.
   - Impact: High. This is the primary API surface between optimizer and session_db. The plan creates it but the spec pseudocode assumes it already exists.

4. **`EvalResult` is not imported in optimizer.py but is referenced in spec as part of evaluator contract**
   - The spec Section 4.1 step 5 references `score_categories(candidate, traces)` returning scores — but the actual evaluator returns `EvalResult` objects. The plan says evaluator needs "output truncation" but doesn't explain how `EvalResult` integrates with the new scoring.
   - Impact: Low. The evaluator is a supporting component; the plan's Step 8 just adds a 4000-char cap.

5. **`hamming_distance` referenced in spec does not exist in codebase**
   - Spec Section 4.2 (reverse pass) and Section 5.2 (redundancy detection) reference `hamming_distance()`. Neither function exists in the current codebase. The plan's Step 4 mentions "hamming distance against last 3 entries" but doesn't call out that this function must be implemented.
   - Impact: Medium. The convergence/redundancy modules need this utility. It's a non-trivial function that must be written.

6. **`categories.py`, `convergence.py`, `multiplier.py`, `auditor.py` do not yet exist**
   - Plan correctly identifies these as new files to create. Verified: `find` over `src/rw_promptforge/` returns no matches for these files.
   - Impact: Expected — these are the deliverables of the plan, not a bug. But worth noting the spec claims these will be created.

7. **`truncate_artifact()` function not present in codebase**
   - Spec Section 6.3 defines `truncate_artifact(text, max_chars=60000)`. This function does not exist anywhere in the codebase. The plan's Step 5 references `truncate_artifact(artifact, MAX_ARTIFACT_CHARS)` but doesn't call out that it must be implemented.
   - Impact: Medium. This is a core utility the optimizer loop depends on.

8. **`sanitize()` function in spec (Section 6.1) differs from `_sanitize()` in evaluator**
   - Spec defines a module-level `sanitize()` with 3 regex patterns in a public function. The evaluator has `_sanitize()` (private, leading underscore) with similar but not identical patterns. The spec's version is public; the code's is private.
   - Impact: Low. Functionality is equivalent; the name difference is cosmetic but the spec pseudocode may reference `sanitize()` externally.

9. **`extract_armored()` in spec (Section 6.4) does not exist**
   - Spec defines `extract_armored(artifact: str) -> dict[str, str]`. This function does not exist in `targets/soul.py` or anywhere else. The plan's Step 9 creates it there.
   - Impact: Medium. The auditor's structural check depends on this to verify ARMORED sections are preserved.

10. **Plan says `cli.py` is "already updated (v1 → v2 wiring)" but new flags are missing**
    - The plan's Step 12 says to "Add new flags to `cli.py` (already partially done)" and lists `--hypothesis-first`, `--semantic-threshold`, `--gain-threshold`. The current `cli.py` has none of these flags. The existing flags are: `--target-type`, `--provider`, `--endpoint`, `--model`, `--max-rounds`, `--save`, `--learning-log`, `--post-mutation-verify`.
    - Impact: Low. This is expected — the plan is a forward plan. But the "already partially done" claim is slightly misleading; nothing v2-specific is wired yet.

11. **`OptimizeResult` in spec (Section 8, line 520-528) has extra fields not in current code**
    - Spec's final `OptimizeResult` includes: `composite_score` and `categories`. Current `optimizer.py:24-43` has: `artifact`, `rounds`, `failures_found`, `converged`, `failure_summary`, `learning_log`. Missing: `composite_score`, `categories`, `multipliers`.
    - Impact: Medium. The v2 result schema is incomplete in the current code; the plan must extend `OptimizeResult`.

12. **`is_converged()` in spec uses `history[-1].observed_outcome != "improvement"` but `LearningLogEntry.observed_outcome` can be "neutral" too**
    - Spec line 268: `len(history) >= 3 and history[-1].observed_outcome != "improvement"` — this treats "neutral" as a convergence signal. The current `create_learning_log_entry()` in engine.py sets outcome based on severity comparison. A "neutral" outcome means severity didn't change, which could indicate stagnation or plateau. The spec's logic conflates "not improvement" with "convergence signal", which could cause premature stopping.
    - Impact: Low-Medium. This is a design concern in the spec, not a code issue, but the plan inherits it.

### Recommendation

**FAIL with conditions.** The plan is structurally sound and most claims check out against the codebase. However, three items block implementation:

1. **`ArtifactMeta` must be created** before the optimizer loop can reference `meta.size_mb` and `meta.total_lines`. The plan's Step 1 should explicitly include this dataclass.
2. **`get_contrastive_traces()` must be added to `SessionDBReader`** (or the spec pseudocode must be reconciled with the existing `get_contrastive_summary()`). The plan's Step 6 addresses this but the spec pseudocode assumes it exists — a naming/return-type mismatch must be resolved before implementation begins.
3. **`truncate_artifact()` and `hamming_distance()` are missing utilities** that the plan's Steps 4 and 5 depend on. These should be called out explicitly in Step 1 (core utilities) or Step 4/5.

**Conditional PASS** if:
- Step 1 is expanded to include `ArtifactMeta` dataclass + `truncate_artifact()` + `hamming_distance()` utilities
- Step 6 either renames `get_contrastive_summary()` to match spec or adds a new `get_contrastive_traces()` method that returns a flat list
- `OptimizeResult` is extended with `composite_score` and `categories` fields per spec Section 8
- `extract_armored()` is added to `SoulTarget` (or a standalone utility) as the plan's Step 9 intends

**Critical gap not in plan:** The spec's `convergence.py` uses `cosine_sim(current, proposed)` (Section 5, Signal 1) but the plan says "Token overlap (Jaccard) as fallback, embeddings if available" in Open Questions. The plan does not commit to an implementation for this signal. This should be resolved before coding begins.
