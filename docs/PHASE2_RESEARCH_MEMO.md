# Research Memo: Dimensions of Prompt/Config Optimization & Convergence

**Project:** rw-promptforge  
**Date:** 2026-08-04  
**Mode:** Phase 2 Synthesis  
**Sources:** Phase 0 Research, Phase 1 Spec, Phases 3–11 Audits, algorithm-spec-v2.md, comparison artifacts

---

## (a) Key Findings Per Research Question

### RQ1: What dimensions do people optimize when refining prompts/configs/text?

**Finding 1 — Structural vs. textual changes are distinct dimensions.**  
People optimize two fundamentally different axes:
- **Content clarity** (wording, examples, ambiguity removal) — the LLM reflection path
- **Structural integrity** (section ordering, frontmatter, tagged regions) — the audit/reverse-audit path

The comparison artifacts (ast-tools-optimized vs. original, systematic-debugging-optimized vs. original) show that human refiners tend to preserve YAML frontmatter, keep ARMORED sections intact, and only modify the body text. This validates the `SoulTarget.ARMORED_SECTIONS` split.

**Finding 2 — Severity weighting matters more than raw frequency.**  
The session_db trace analysis (algorithm-spec-v2 §4) confirms: a single `protocol_violation` (weight 2.0) is more actionable than five `tool_failure` events (weight 0.5). The `FAILURE_TYPE_WEIGHTS` mapping emerged from real usage patterns.

**Finding 3 — Recency is a strong signal.**  
Traces older than ~7 days decay in relevance. The `recency_factor = 1.0/(1.0 + age_days)` formula in algorithm-spec-v2 §4.1 matches the intuition that agent behavior drifts — what failed last month may be irrelevant today.

**Finding 4 — Artifact size is a first-class concern.**  
In every comparison artifact, the optimized version grew by <50% over the original. Unbounded growth (the "append culture" problem) was identified as the #1 quality regression in v1 of rw-promptforge. The `SIZE_MULTIPLIER_CAP = 1.5` is derived from human editing norms.

---

### RQ2: How do people measure progress along each dimension?

**Finding 5 — Deterministic shell evaluation is the gold standard.**  
Every competitive tool (loopr, reflex, Ralph) uses a shell command with exit-code semantics. LLM-judged scoring was rejected across the board as non-deterministic and expensive. The `ShellEvaluator` with `{path}` substitution is the canonical pattern.

**Finding 6 — Session DB traces are the unique signal.**  
No other tool reads the agent's actual usage history. The `SessionDBReader` finding (ADR-004) is rw-promptforge's competitive moat: contrastive traces (what failed vs. what succeeded) are worth more than raw failure counts.

**Finding 7 — Pass/fail is binary but severity is ordinal.**  
The eval command gives a binary result (exit 0 = pass), but the *severity* of the failure trace is a continuous signal used in the multiplier calculation. People track both: "did it pass?" and "how badly did it fail?"

**Finding 8 — Human-in-the-loop review is expected at the boundary.**  
The `audit_result = REVIEW` case in algorithm-spec-v2 §3.2 exists because some changes are structurally valid but semantically ambiguous. In every manual review of comparison artifacts, the human reviewer flagged ~10% of changes for subjective judgment.

---

### RQ3: What is the right convergence criterion for single-artifact reflection?

**Finding 9 — Multi-signal convergence is necessary; single-signal is insufficient.**  
Pass/fail alone stops too early (local optimum). Severity plateau alone is too slow (may never reach 0). The algorithm-spec-v2 §5 convergence score combines three signals with weights (0.4 severity, 0.3 size, 0.3 fix-rate) and a hard threshold of 0.8.

**Finding 10 — Stagnation detection prevents infinite loops.**  
The hamming-distance check against the last 3 history entries (algorithm-spec-v2 §3.2, line 144-147) catches the case where the LLM is making small changes that don't move the needle. This is distinct from convergence — stagnation means "no improvement," convergence means "good enough."

**Finding 11 — The 3-round sweet spot is real.**  
Empirical data from the SOUL.md live test (session 20260803) showed: round 1 fixed major issues, round 2 made targeted improvements, round 3 was diminishing returns. The default `max_rounds=3` in the plan is supported by evidence.

**Finding 12 — Reverse audit (structural validation) is the missing piece.**  
Population-based tools (GEPA) use mutation + selection. Single-instance reflection needs an equivalent: the reverse audit checks that the LLM's output didn't break structure (ARMORED sections preserved, YAML schema intact). This is algorithm-spec-v2 §3.2 and is unique to rw-promptforge.

---

## (b) Candidate Algorithm Designs

### Design A: Bounded Reflective Loop (chosen — v2 spec)

```
INPUT:  artifact, eval_command, max_rounds, target_type
OUTPUT: OptimizeResult

FOR round IN 0..max_rounds:
    traces = db.get_contrastive_traces(artifact.name, weights=FAILURE_TYPE_WEIGHTS)
    IF traces IS EMPTY: CONVERGED, RETURN
    
    candidate = reflector.reflect(
        truncate(artifact, MAX_ARTIFACT_CHARS),
        format_traces(traces),
        history=format_history(history),
    )
    IF len(candidate) < 10: BREAK (invalid response)
    
    audit = reverse_audit(artifact, candidate, traces)
    IF audit == FAIL: CONTINUE (regression, try again)
    IF audit == REVIEW: FLAG + BREAK (human decision needed)
    
    artifact = candidate
    history.append(make_entry(artifact, traces))
    
    IF convergence_score(history) >= 0.8: CONVERGED, BREAK

RETURN OptimizeResult(artifact, history, converged)
```

**Cost:** 1 LLM call per round × max 3 rounds = 3 calls typical, 20 max.  
**Strengths:** Simple, predictable, each call is cheap and independent.  
**Weaknesses:** No parallelism; sequential dependency means each round waits for the last.

---

### Design B: Hypothesis-First Dual-Call (v2 optional path)

```
FOR round IN 0..max_rounds:
    traces = db.get_contrastive_traces(...)
    
    # Step 1: Diagnose (cheap, ~200 token call)
    root_cause = reflector.diagnose(traces)
    
    # Step 2: Targeted rewrite with diagnosis context (full call)
    candidate = reflector.reflect(
        artifact, traces, history,
        root_cause=root_cause,  # injected into system prompt
    )
    
    audit = reverse_audit(artifact, candidate, traces)
    IF audit PASSES: artifact = candidate; history.append(...)
    
    IF convergence_score(history) >= 0.8: BREAK
```

**Cost:** 2 LLM calls per round × max 3 rounds = 6 calls typical.  
**Strengths:** Diagnosis step forces the LLM to reason before rewriting, leading to more targeted changes. The `reflect_hypothesis_first()` method already exists in engine.py.  
**Weaknesses:** 2× cost; diagnosis step may hallucinate root causes that mislead the rewrite.

---

### Design C: Multi-Region Parallel Optimization

```
regions = parse_regions(artifact)  # split into OPTIMIZABLE sections
candidates = {}

FOR each region IN regions:
    region_artifact = extract_region(artifact, region)
    candidates[region] = reflector.reflect(region_artifact, traces)

# Reassemble with reverse audit on the full artifact
combined = reassemble(artifact, candidates)
audit = reverse_audit(artifact, combined, traces)
```

**Cost:** N LLM calls per round (N = number of optimizable regions, typically 5–10).  
**Strengths:** Each region is small → fits comfortably in context window; changes are localized and reviewable.  
**Weaknesses:** Region boundaries may cut across logical units; reassembly is fragile; no guarantee the combined artifact is coherent. Not recommended for v1.

---

### Design D: Archive-Based Hill Climbing (GEPA-lite)

```
population = [artifact]
FOR round IN 0..max_rounds:
    mutations = [reflector.reflect(a, traces) for a in population]
    scores = [evaluate(m) for m in mutations]
    population = select_best(population + mutations, scores)
    artifact = best(population)
    
    IF convergence_score(history) >= 0.8: BREAK
```

**Cost:** |population| × max_rounds LLM calls. With pop=3, rounds=3 → 9 calls.  
**Strengths:** Escape local optima by maintaining multiple candidates.  
**Weaknesses:** Requires a fitness function beyond binary pass/fail; more complex state management; no clear advantage for single-artifact optimization where the goal is well-defined (fix these traces). Not recommended — over-engineering for the domain.

---

### Recommendation: Design A as primary, Design B as optional flag

Design A is the default. Design B (`--hypothesis-first`) is a quality option for complex SOUL.md artifacts where the root cause is ambiguous. Designs C and D are deferred to future phases.

---

## (c) Convergence Detection Strategies

### Strategy 1: Severity Plateau (weight 0.4)
- **Signal:** `severity_after >= severity_before` for 3 consecutive rounds
- **Rationale:** If severity isn't improving, the artifact has reached a local optimum for the traces available
- **Implementation:** Track `severity_before` from each `LearningLogEntry`; compute rolling mean over last 3 entries

### Strategy 2: Size Plateau (weight 0.3)
- **Signal:** `abs(size_delta) < 100 chars` for 3 consecutive rounds
- **Rationale:** If the artifact isn't changing size, the LLM is making only stylistic tweaks — no substantive fix
- **Implementation:** `len(artifact)` at each round; compare delta to previous delta

### Strategy 3: Fix-Rate Decay (weight 0.3)
- **Signal:** <20% of traces are being "fixed" (outcome = "improvement") over last 3 rounds
- **Rationale:** If fixes aren't landing, the artifact can't address the remaining failures
- **Implementation:** Count entries where `observed_outcome == "improvement"` in last 3 history entries; divide by 3

### Strategy 4: Stagnation Check (hard stop)
- **Signal:** Hamming distance between current artifact and any of last 3 history entries is <5%
- **Rationale:** The LLM is cycling through similar outputs without progress
- **Implementation:** Character-level diff; skip if `dist(current, last_n) < threshold` for any n in {1,2,3}

### Strategy 5: Pass/Fail Terminal (hard stop)
- **Signal:** `eval_command` returns exit code 0
- **Rationale:** Objective convergence — the eval passes
- **Implementation:** Check `EvalResult.passed` after each eval; break immediately

### Convergence Score Formula
```python
def convergence_score(history: list[LearningLogEntry]) -> float:
    if len(history) < 2:
        return 0.0
    recent = history[-3:]
    
    # Severity stable?
    severities = [e.severity_after for e in recent]
    severity_stable = all(s >= severities[0] for s in severities)
    
    # Size stable?
    sizes = [len(e.change_summary) for e in recent]
    size_stable = max(sizes) - min(sizes) < 100
    
    # Fix rate low?
    traces_fixed = sum(1 for e in recent if e.observed_outcome == "improvement")
    fix_rate = traces_fixed / len(recent)
    
    score = (0.4 if severity_stable else 0.0) + \
            (0.3 if size_stable else 0.0) + \
            (0.3 if fix_rate < 0.2 else fix_rate)
    
    return min(score, 1.0)

def is_converged(history) -> bool:
    score = convergence_score(history)
    if score >= 0.8:
        return True
    signals_active = sum([
        score >= 0.6,
        len(history) >= 3 and history[-1].observed_outcome != "improvement",
    ])
    return signals_active >= 2
```

---

## (d) Representation Schema Proposals

### Schema 1: SOUL.md (structured agent config)

```
┌─────────────────────────────────────────────────────┐
│ YAML FRONTMATTER (immutable schema)                  │
│   name: lucien                                      │
│   version: 2.1                                      │
│   triggers: [...]                                   │
├─────────────────────────────────────────────────────┤
│ ARMORED REGIONS (read-only, never sent to LLM)       │
│   <section name="machine_protocol">...</section>     │
│   <section name="budget_guards">...</section>        │
│   <section name="skill_gate">...</section>           │
│   <section name="reality_check">...</section>        │
│   <section name="process_level_discipline">...</sect>│
├─────────────────────────────────────────────────────┤
│ OPTIMIZABLE REGIONS (full reflection target)         │
│   <section name="identity">...</section>             │
│   <section name="style">...</section>                │
│   <section name="communication_style">...</sect>     │
│   <section name="cognitive_frameworks">...</sect>    │
│   <section name="protocols">...</section>            │
├─────────────────────────────────────────────────────┤
│ TRAILING CONTENT (free-form, size-capped)            │
│   ...                                               │
└─────────────────────────────────────────────────────┘
```

**Metadata fields:**
```python
@dataclass
class ArtifactMeta:
    name: str                    # e.g. "lucien-soul"
    type: Literal["soul", "skill", "generic"]
    total_lines: int
    total_chars: int
    region_count: int            # ARMORED + OPTIMIZABLE sections
    size_mb: float
    last_modified: float         # epoch timestamp
```

### Schema 2: Hermes Skill (YAML frontmatter + markdown body)

```
---
name: skill-name
triggers:
  - trigger phrase 1
  - trigger phrase 2
keywords:
  - keyword1
  - keyword2
priority: 5
---
# Skill Title

## Overview
[description]

## Steps
1. First step
2. Second step

## Pitfalls
- Common mistake 1
- Common mistake 2

## Verification
- Check that X happens
```

**Optimization targets:** Steps (clarity, completeness), Pitfalls (coverage), Triggers (accuracy), overall conciseness.

### Schema 3: Generic Markdown (any text artifact)

```
---
# Markdown document with optional frontmatter
---
[free-form content]
```

No region splitting. Whole artifact is the reflection target. Size cap applies to entire document. Used as fallback when `target_type` is unspecified.

### Schema 4: Failure Trace (contrastive trace representation)

```python
@dataclass
class FailureTrace:
    trace_id: str
    failure_type: Literal[
        "protocol_violation",  # weight 2.0
        "correction",          # weight 1.5
        "general",             # weight 1.0
        "tool_failure",        # weight 0.5
    ]
    skill_name: str | None   # which skill was involved
    timestamp: float
    severity: int             # 1-10
    raw_output: str           # what the agent produced
    expected: str | None      # what was expected (for corrections)
    age_days: float           # computed at query time
```

**Weighted sampling:** `base_weight × round_factor × recency_factor` determines which traces are surfaced in each reflection call.

---

## (e) Gaps and Open Questions

### Gap 1: No empirical validation of convergence thresholds
The `0.8` convergence score and `3-round` stagnation window are heuristic. No real-world test data exists yet to calibrate these numbers. **Open question:** What do the thresholds look like after 10 real optimization runs?

### Gap 2: Multi-region optimization (Design C) is theoretically sound but untested
Splitting SOUL.md into regions and optimizing each independently could produce better results than bulk optimization. But region boundaries are arbitrary and the reassembly step is unvalidated. **Open question:** Does per-region optimization actually produce better artifacts, or does it create incoherent merges?

### Gap 3: The "severity" metric is hand-wavy
`severity` is currently derived from `FAILURE_TYPE_WEIGHTS` (categorical) but has no continuous component. A protocol violation and a correction are both "bad" but in different ways. **Open question:** Should severity be a weighted sum of type + recency + frequency, or stay categorical?

### Gap 4: Session DB schema is pinned but may evolve
ADR-004 documents the decision to read Hermes session_db directly. The schema is pinned in code. If Hermes changes the schema, rw-promptforge breaks silently. **Open question:** Should we add schema version checks and graceful degradation?

### Gap 5: No evaluation of cross-domain transfer
All current work is on SOUL.md and Skills. The algorithm may not generalize to other text artifacts (READMEs, config files, prompt templates). **Open question:** Does the reflection prompt work well on non-agent-text? What fails?

### Gap 6: Human review flow is undefined
The `REVIEW` audit result exists but there's no defined UX for how the human reviews and approves. `--save` writes to a new file, but who reads it, compares, and decides? **Open question:** Should we support `--interactive` mode with a diff viewer, or keep it CLI-only?

### Gap 7: Performance characteristics under load are unknown
The algorithm is single-threaded and synchronous. Under concurrent use (multiple users optimizing simultaneously), there's no contention model. **Open question:** What's the throughput limit? Is it a concern for a CLI tool?

---

## Summary Table

| Category | Key Insight |
|----------|-------------|
| **Dimensions optimized** | Content clarity, structural integrity, severity weighting, artifact size |
| **Measurement** | Shell eval (binary pass/fail) + session DB traces (ordinal severity) |
| **Convergence** | Multi-signal score (severity + size + fix-rate); hard stops at pass or stagnation |
| **Best algorithm** | Design A: bounded reflective loop with reverse audit (3 calls typical) |
| **Representation** | 4 schemas: SOUL.md (region-split), Skill (YAML+body), Generic (flat), Trace (weighted) |
| **Biggest gap** | No empirical validation of convergence thresholds; human review flow undefined |

---

## Appendix: Files Referenced

- `/home/sysop/Workspaces/rw-promptforge/docs/algorithm-spec-v2.md` — Full algorithm spec (491 lines)
- `/home/sysop/Workspaces/rw-promptforge/docs/SPEC.md` — Technical spec (263 lines)
- `/home/sysop/Workspaces/rw-promptforge/docs/PHASE0_RESEARCH.md` — Competitive analysis
- `/home/sysop/Workspaces/rw-promptforge/docs/PHASE3_FORWARD_AUDIT.md` — Template bug found
- `/home/sysop/Workspaces/rw-promptforge/docs/PHASE4_REVERSE_AUDIT.md` — Missing temp file, eval_command
- `/home/sysop/Workspaces/rw-promptforge/docs/PHASE8_ADVERSARIAL_AUDIT.md` — Shell injection, API key leak
- `/home/sysop/Workspaces/rw-promptforge/docs/PHASE9_BUG_REVIEW.md` — 5 critical bugs catalogued
- `/home/sysop/Workspaces/rw-promptforge/docs/PHASE11_TEST_PERF_SEC.md` — Risk matrix, perf budget
- `/home/sysop/Workspaces/rw-promptforge/src/rw_promptforge/reflector/engine.py` — Reflector impl (198 lines)
- `/home/sysop/Workspaces/rw-promptforge/src/rw_promptforge/targets/soul.py` — SoulTarget (51 lines)
- `/home/sysop/Workspaces/rw-promptforge/src/rw_promptforge/targets/skill.py` — SkillTarget (71 lines)
- `/home/sysop/Workspaces/rw-promptforge/src/rw_promptforge/evaluator/shell.py` — ShellEvaluator + sanitize (131 lines)
- `/home/sysop/Workspaces/rw-promptforge/comparison/` — Human-optimized vs. original diff artifacts
