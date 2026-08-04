# rw-promptforge v2 — Final Algorithm Specification

**Version:** 2.0.0  
**Status:** Merged Design (final)  
**Date:** 2026-08-04  
**Sources:** algorithm-spec-v2.md + PHASE2_RESEARCH_MEMO.md + research_iterative_refinement_convergence.md

---

## 1. Problem Statement

v1 has three critical deficiencies:

| Problem | Manifestation | Root Cause |
|---------|---------------|------------|
| **Non-convergence** | 100→290 lines (190% growth), never stops | Reflection prompt biased toward expansion |
| **Timeout risk** | Single round exceeds 90s on large artifacts | No output cap, no convergence detection |
| **No improvement signal** | "neutral" outcomes, 9 failures, no direction | Single binary eval, no multi-dimensional scoring |

Additionally: shell injection (unquoted path), API key exfiltration (eval STDERR to LLM), unbounded `max_rounds`.

---

## 2. Representation Schema: 4-Region Artifact Model

```
┌─────────────────────────────────────────────────────────────┐
│ YAML FRONTMATTER (immutable schema)                         │
│   name: lucien                                              │
│   triggers: [...]    ← can be appended, not reordered       │
│   keywords: [...]    ← can be appended                      │
├─────────────────────────────────────────────────────────────┤
│ ARMORED REGIONS (read-only — NEVER sent to reflector)       │
│   <section name="machine_protocol">...</section>            │
│   <section name="budget_guards">...</section>               │
│   <section name="skill_gate">...</section>                  │
│   <section name="reality_check">...</section>               │
│   <section name="process_level_discipline">...</section>    │
│   ← Structural integrity preserved across all iterations    │
├─────────────────────────────────────────────────────────────┤
│ OPTIMIZABLE REGIONS (full reflection target)                │
│   <section name="identity">...</section>                    │
│   <section name="communication_style">...</section>         │
│   <section name="cognitive_frameworks">...</section>        │
│   <section name="protocols">...</section>                   │
│   ← Only these regions are passed to reflector              │
├─────────────────────────────────────────────────────────────┤
│ TRAILING CONTENT (free-form, size-capped)                   │
│   ← Subject to size multiplier cap                          │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 Artifact Metadata

```python
@dataclass
class ArtifactMeta:
    name: str                    # e.g. "lucien-soul", "hermes-agent"
    type: Literal["soul", "skill", "generic"]
    total_lines: int
    total_chars: int
    region_count: int            # ARMORED + OPTIMIZABLE sections
    size_mb: float
    last_modified: float         # epoch timestamp
```

### 2.2 Failure Trace Types

```python
FAILURE_TYPE_WEIGHTS: dict[str, float] = {
    "protocol_violation": 2.0,   # agent ignored explicit instruction
    "correction": 1.5,           # user corrected agent
    "tool_failure": 0.5,         # tool error (less actionable for prompts)
    "general": 1.0,              # default
}
```

---

## 3. Multi-Dimensional Scoring: 4 Representation Categories

Each optimization round scores the artifact across 4 categories. Multipliers track directional change.

| Category | Weight | Measures |
|----------|--------|----------|
| **C1: Structural Coherence** | 0.25 | Logical section ordering, cross-references valid, hierarchy clear |
| **C2: Failure Pattern Coverage** | 0.35 | Match between documented anti-patterns and real session_db failures |
| **C3: Conciseness/Density** | 0.20 | Information packed per token; anti-bloat, anti-expansion |
| **C4: Actionability** | 0.20 | Can the agent execute instructions without ambiguity? |

### 3.1 Multiplier Formula

```python
multiplier[k] = (score_t - score_{t-1}) / max(score_{t-1}, ε)

# Interpretation:
# multiplier = 0.15 → 15% improvement in this category
# multiplier = -0.05 → 5% regression
# multiplier ≈ 0 → stagnant
```

### 3.2 Composite Score

```python
composite_score = Σ(w_k * score_k)
# where w_k = category weights (must sum to 1.0)

# Thresholds:
# composite < 0.5 → poor quality
# 0.5 ≤ composite < 0.7 → adequate
# 0.7 ≤ composite < 0.9 → good
# composite ≥ 0.9 → excellent
```

---

## 4. Forward/Reverse Audit Loop (Design A — Chosen)

### 4.1 Forward Pass

```
FORWARD PASS
─────────────────────────────────────────────────────────
Input:  artifact, failure_traces, history
Output: improved_artifact, category_scores

1. TRUNCATE artifact to MAX_ARTIFACT_CHARS (60000)
   - Preserve head (first N chars) and tail (last N chars)
   - Insert "... [TRUNCATED] ..." marker

2. QUERY session_db for contrastive traces
   - find_corrections(skill_name) → severity-weighted
   - find_protocol_violations() → HIGH severity
   - find_tool_failures() → LOW severity
   - Sample with FAILURE_TYPE_WEIGHTS
   - Cap at MAX_EFFECTIVE_TRACES (5)

3. CONSTRUCT reflection prompt
   - System: immutable ARMORED sections (cache key: stable prefix)
   - User: optimizable regions + failure_traces + history + size_budget

4. CALL reflector.reflect(prompt, system)
   - Reject if output < 10 chars or > 2× artifact size
   - Track token count for budget

5. SCORE candidate across 4 categories
   - C1: LLM judge on structural coherence
   - C2: Measure failure trace coverage match
   - C3: LLM judge on conciseness/density
   - C4: LLM judge on actionability
   - Return composite score + per-category scores

6. UPDATE history log
   - Record: round, scores, multipliers, size_delta, outcome
```

### 4.2 Reverse Pass (Structural Audit)

```
REVERSE PASS
─────────────────────────────────────────────────────────
Input:  old_artifact, new_artifact, failure_traces
Output: audit_result (PASS | FAIL | REVIEW)

1. STRUCTURAL CHECK
   - new_artifact preserves ARMORED regions intact?
   - new_artifact preserves YAML frontmatter schema?
   - If NO: audit_result = FAIL

2. SEMANTIC CHECK
   - Parse both artifacts into region maps
   - For each OPTIMIZABLE region:
     - If content identical → skip
     - If changed:
       - Does change address ANY failure trace?
       - Does change introduce NEW ambiguity?
       - If no failure addressed AND ambiguity introduced → FAIL

3. SIZE CHECK
   - new_artifact.size <= old_artifact.size × SIZE_MULTIPLIER_CAP (1.5×)
   - If exceeded: audit_result = REVIEW (flag for human)

4. STAGNATION CHECK
   - Compare new_artifact against last 3 history entries
   - If hamming_distance(new, last_3) < 5%:
     - Flag as stagnant; do NOT accept

5. Return audit_result
```

### 4.3 Loop Control

```python
for round_num in range(max_rounds):
    # Forward
    candidate, scores = forward_pass(artifact, traces, history)
    multipliers = compute_multipliers(scores, prev_scores)
    
    # Reverse
    audit = reverse_audit(old_artifact, candidate, traces)
    
    if audit == PASS:
        artifact = candidate
        prev_scores = scores
        history.append(entry)
    elif audit == FAIL:
        log_regression(round_num)
        continue  # try next round with same artifact
    else:  # REVIEW
        flag_for_human_review(candidate, multipliers)
        break  # don't auto-apply
    
    # Convergence check (Section 5)
    if is_converged(history, multipliers):
        break
```

---

## 5. Convergence Detection: 97% Confidence Gate

Stop when **ALL** of the following are true:

| Signal | Condition | Weight | Rationale |
|--------|-----------|--------|-----------|
| **Semantic stability** | cosine_sim(current, proposed) > 0.95 for 2 consecutive rounds | 0.3 | Content no longer changing meaningfully |
| **Gain saturation** | expected_one_step_gain < 0.02 for 2 consecutive rounds | 0.3 | Improvement negligible |
| **Category stability** | abs(multiplier[k]) < 0.05 for all 4 categories for 2 rounds | 0.2 | No category moving |
| **Hard floor** | round >= min_rounds (default 2) | terminal | Need baseline before stopping |

### 5.1 Convergence Score Formula

```python
def convergence_score(history: list[LearningLogEntry]) -> float:
    if len(history) < 2:
        return 0.0
    
    recent = history[-3:]
    
    # Signal 1: severity/quality trend
    severities = [e.severity_after for e in recent]
    severity_stable = all(s >= severities[0] for s in severities)
    
    # Signal 2: size trend
    sizes = [len(e.change_summary) for e in recent]
    size_stable = max(sizes) - min(sizes) < 100
    
    # Signal 3: fix rate
    traces_fixed = sum(1 for e in recent if e.observed_outcome == "improvement")
    fix_rate = traces_fixed / len(recent)
    
    score = (0.4 if severity_stable else 0.0) + \
            (0.3 if size_stable else 0.0) + \
            (0.3 if fix_rate < 0.2 else fix_rate)
    
    return min(score, 1.0)

def is_converged(history) -> bool:
    score = convergence_score(history)
    
    # Hard stop at 0.8
    if score >= 0.8:
        return True
    
    # Soft stop: 2+ signals active
    signals_active = sum([
        score >= 0.6,
        len(history) >= 3 and history[-1].observed_outcome != "improvement",
    ])
    return signals_active >= 2
```

### 5.2 Redundancy Detection (Diminishing Returns)

```python
def check_redundancy(history) -> bool:
    """Detect when improvements become redundant."""
    if len(history) < 4:
        return False
    
    # Compute edit magnitudes
    magnitudes = []
    for i in range(len(history) - 1):
        Δ_t = hamming_distance(history[i].artifact, history[i+1].artifact)
        magnitudes.append(Δ_t)
    
    # Check exponential decay pattern
    if len(magnitudes) >= 3:
        recent = magnitudes[-3:]
        # If each round is <30% of previous, we're in diminishing returns
        if all(recent[i] < recent[i-1] * 0.3 for i in range(1, len(recent))):
            return True  # REDUNDANT — stop
    
    return False
```

### 5.3 Three Failure Modes to Detect

| Mode | Signal | Action |
|------|--------|--------|
| **Oscillation** | Output alternates between 2+ versions | Restart, don't continue |
| **Expansion** | Output grows each pass (>1.5× cap) | Abort, flag for human |
| **Low-quality plateau** | All signals converge but composite < 0.5 | Redesign, not more passes |

---

## 6. Safety Constraints

### 6.1 Input Sanitization

```python
CREDENTIAL_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password|authorization)[=:\s]\s*\S+"),
    re.compile(r"Bearer\s+\S+"),
    re.compile(r"-----BEGIN.*?-----", re.DOTALL),
]

def sanitize(text: str) -> str:
    for pattern in CREDENTIAL_PATTERNS:
        text = pattern.sub(r"[REDACTED]", text)
    return text
```

### 6.2 Shell Injection Prevention

```python
# Use shlex.quote before substitution
safe_path = shlex.quote(artifact_path)
command = eval_command_template.replace("{path}", safe_path)
```

### 6.3 Artifact Size Budget

```python
MAX_ARTIFACT_CHARS = 60000
SIZE_MULTIPLIER_CAP = 1.5  # new artifact can be at most 1.5× old size
MAX_ROUNDS_CAP = 20        # hard ceiling on iterations
MAX_EFFECTIVE_TRACES = 5   # traces surfaced per round

def truncate_artifact(text: str, max_chars: int = MAX_ARTIFACT_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    head = max_chars // 2
    tail = max_chars // 2
    return text[:head] + "\n... [TRUNCATED] ...\n" + text[-tail:]
```

### 6.4 ARMORED Section Protection

```python
ARMORED_SECTIONS = {
    "machine_protocol",
    "project_registry",
    "skill_gate",
    "budget_guards",
    "reality_check",
    "process_level_discipline",
}

def extract_armored(artifact: str) -> dict[str, str]:
    """Parse and return only ARMORED sections for validation."""
    # Implementation: regex or XML parser to extract <section name="...">
    ...
```

---

## 7. Design Options

### Design A: Bounded Reflective Loop (CHOSEN — v2 default)

```python
FOR round IN 0..max_rounds:
    traces = db.get_contrastive_traces(artifact.name, weights=FAILURE_TYPE_WEIGHTS)
    IF traces IS EMPTY: CONVERGED, RETURN
    
    candidate = reflector.reflect(
        truncate(artifact, MAX_ARTIFACT_CHARS),
        format_traces(traces),
        history=format_history(history),
    )
    IF len(candidate) < 10: BREAK
    
    audit = reverse_audit(artifact, candidate, traces)
    IF audit == FAIL: CONTINUE
    IF audit == REVIEW: FLAG + BREAK
    
    artifact = candidate
    history.append(make_entry(artifact, traces))
    
    IF is_converged(history): BREAK

RETURN OptimizeResult(artifact, history, converged)
```

**Cost:** 1 LLM call/round × max 3 rounds typical, 20 max  
**Strengths:** Simple, predictable, each call independent  
**Weaknesses:** No parallelism

### Design B: Hypothesis-First Dual-Call (optional `--hypothesis-first`)

```python
FOR round IN 0..max_rounds:
    traces = db.get_contrastive_traces(...)
    
    # Step 1: Diagnose (cheap, ~200 token call)
    root_cause = reflector.diagnose(traces)
    
    # Step 2: Targeted rewrite with diagnosis context
    candidate = reflector.reflect(
        artifact, traces, history,
        root_cause=root_cause,
    )
    
    audit = reverse_audit(artifact, candidate, traces)
    IF audit PASSES: artifact = candidate
    
    IF is_converged(history): BREAK
```

**Cost:** 2 LLM calls/round × max 3 rounds = 6 calls typical  
**Strengths:** Diagnosis forces targeted changes  
**Weaknesses:** 2× cost; diagnosis may hallucinate

### Design C: Multi-Region Parallel (deferred)

Split artifact into regions, optimize each independently, reassemble. **Not recommended for v2** — region boundaries are arbitrary, reassembly is fragile.

### Design D: Archive Hill-Climbing (deferred)

Maintain population of candidates, select best. **Not recommended** — over-engineering for single-artifact optimization.

---

## 8. Pseudocode: Complete Algorithm

```
ALGORITHM: optimize_artifact
INPUT:  artifact_path, target_type, eval_command, max_rounds, save
OUTPUT: OptimizeResult

1. INIT
   artifact ← read_file(artifact_path)
   meta ← parse_artifact_meta(artifact, target_type)
   history ← empty list
   db ← SessionDBReader()
   
   IF max_rounds > MAX_ROUNDS_CAP:
       max_rounds ← MAX_ROUNDS_CAP

2. MAIN LOOP
   FOR round_num FROM 0 TO max_rounds - 1:
   
     # -- Forward: get failure traces --
     traces ← db.get_contrastive_traces(
         artifact.name,
         limit=MAX_EFFECTIVE_TRACES,
         weights=FAILURE_TYPE_WEIGHTS
     )
     
     IF traces.is_empty():
         RETURN OptimizeResult(artifact, rounds=round_num, converged=True)
     
     # -- Forward: reflect --
     history_text ← format_history(history)
     truncated_artifact ← truncate_artifact(artifact, MAX_ARTIFACT_CHARS)
     
     candidate ← reflector.reflect(
         artifact=truncated_artifact,
         failure_traces=format_traces(traces),
         history=history_text,
         size_budget=meta.size_mb * SIZE_MULTIPLIER_CAP
     )
     
     IF candidate.is_empty() OR len(candidate) < 10:
         log_error("Reflector returned empty output")
         BREAK
     
     # -- Score candidate --
     scores ← score_categories(candidate, traces)
     multipliers ← compute_multipliers(scores, prev_scores)
     
     # -- Reverse: audit candidate --
     audit ← reverse_audit(meta, candidate, traces)
     
     IF audit == FAIL:
         log_regression(round_num, candidate)
         CONTINUE
     
     IF audit == REVIEW:
         flag_for_human_review(candidate, multipliers)
         BREAK
     
     # -- Accept candidate --
     artifact ← candidate
     entry ← LearningLogEntry(
         attempted_change="reflection_round_" + round_num,
         observed_outcome=detect_outcome(history, entry),
         severity_before=traces.max_severity,
         severity_after=scores.composite,
         categories=scores,
         multipliers=multipliers,
     )
     history.append(entry)
     prev_scores ← scores
     
     # -- Check redundancy --
     IF check_redundancy(history):
         log_info("Diminishing returns detected, stopping")
         BREAK
     
     # -- Check convergence --
     IF is_converged(history):
         BREAK
   
   # -- Post-loop --
   IF save:
       write_file(artifact_path, artifact)
   
   RETURN OptimizeResult(
       artifact=artifact,
       rounds=len(history),
       failures_found=sum(t.count for t in traces),
       converged=is_converged(history) OR traces.is_empty(),
       failure_summary=format_history_summary(history),
       learning_log=history,
       composite_score=history[-1].severity_after if history else 0.0,
   )
```

---

## 9. Component Responsibilities

| Component | File | v1 Status | v2 Change |
|-----------|------|-----------|-----------|
| **Optimizer** | `optimizer.py` | Loop with no convergence | Add reverse audit, multiplier, convergence signals |
| **Reflector** | `reflector/engine.py` | Single LLM call | Add `size_budget`, `hypothesis_first` mode |
| **Evaluator** | `evaluator/shell.py` | Basic eval | Add output truncation, keep sanitize |
| **SessionDB** | `datastore/session_db.py` | Basic queries | Add multiplier-aware sampling |
| **Targets** | `targets/soul.py`, `targets/skill.py` | Stubs | Implement ARMORED region parsing |
| **Categories** | `categories.py` (NEW) | N/A | 4-category scoring logic |
| **Convergence** | `convergence.py` (NEW) | N/A | Multi-signal convergence detection |
| **Multiplier** | `multiplier.py` (NEW) | N/A | Directional improvement tracking |
| **Auditor** | `auditor.py` (NEW) | N/A | Reverse audit: structural + semantic + size checks |

---

## 10. Performance Characteristics

| Metric | v1 | v2 |
|--------|----|----|
| Max LLM calls | Unbounded | `max_rounds × 1` (capped at 20) |
| Eval output size | Unbounded | Capped at 4000 chars per trace |
| Artifact growth | Unbounded | Capped at 1.5× per round |
| Convergence | None | Multi-signal (severity, size, fix rate, redundancy) |
| Security | Shell injection risk | `shlex.quote` + output sanitization |
| Stagnation detection | None | 3-round rolling window + redundancy check |
| Improvement signal | Binary (pass/fail) | 4-category scores + multipliers |

---

## 11. CLI Interface

```bash
# Basic usage
rw-promptforge optimize <path> --target-type soul --max-rounds 3 --save

# With hypothesis-first (Design B)
rw-promptforge optimize <path> --target-type skill --hypothesis-first

# Custom convergence thresholds
rw-promptforge optimize <path> --target-type soul \
  --semantic-threshold 0.95 \
  --gain-threshold 0.02 \
  --stability-threshold 0.05

# Save to separate file (don't overwrite)
rw-promptforge optimize <path> --target-type soul --save --output optimized.md
```

### New CLI Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--max-rounds` | 3 | Maximum optimization rounds (hard cap: 20) |
| `--min-rounds` | 2 | Minimum rounds before convergence can trigger |
| `--hypothesis-first` | false | Use Design B (2 LLM calls per round) |
| `--semantic-threshold` | 0.95 | Cosine similarity threshold for convergence |
| `--gain-threshold` | 0.02 | Minimum expected gain to continue |
| `--stability-threshold` | 0.05 | Max multiplier magnitude before stable |
| `--output` | null | Save to separate file instead of overwrite |

---

## 12. Open Design Decisions

| Decision | Options | Recommendation |
|----------|---------|----------------|
| **Hypothesis-first** | Single call vs. two-step | Two-step for complex SOUL.md; single for skills |
| **Convergence threshold** | Fixed (0.8 score) vs. adaptive | Fixed for predictability; adaptive for edge cases |
| **Size budget unit** | Characters vs. tokens vs. MB | Characters (simpler, no tokenizer dependency) |
| **Audit parallelism** | Sequential vs. parallel | Sequential (reverse depends on forward output) |
| **Learning log persistence** | In-memory vs. disk | In-memory (CLI runs once per invocation) |

---

## 13. Appendix: Key Research Citations

1. **Textual Relaxation** — Do Language Models Converge to Themselves? (arXiv:2607.22653)
2. **GainNet** — Optimal Stopping for Iterative Self-Refinement (arXiv:2604.02035)
3. **SHP** — Semantic Early-Stopping for Iterative LLM Agent Loops (arXiv:2606.27009)
4. **GEPA** — Reflective Prompt Evolution (Agrawal et al., 2025)
5. **Self-Bias** — LLM Self-Bias in Self-Refinement (2025)
6. **LoopGain** — Control-Theoretic Loop Convergence (2026)
7. **AgentPatterns** — Convergence Detection in Iterative Agent Refinement (2026)
8. **Microsoft Foundry** — Agent Optimizer (Build 2026)

---

## 14. Implementation Priority

1. **P0 — Core loop**: Forward pass + reverse audit + convergence detection
2. **P1 — Scoring**: 4-category scoring + multiplier calculation
3. **P2 — Safety**: Shell injection fix, credential sanitization, size caps
4. **P3 — Region parsing**: ARMORED section extraction for SOUL.md
5. **P4 — Design B**: Hypothesis-first optional path
6. **P5 — CLI flags**: New thresholds and options
