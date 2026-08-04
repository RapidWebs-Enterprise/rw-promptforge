# rw-promptforge v2 — Algorithm Specification

> **Version:** 2.0.0 | **Status:** Design Spec | **Date:** 2026-08-04  
> Replaces v1 speculative loop with bounded, convergent, secure algorithm.

---

## 1. Problem Statement

v1 has three critical deficiencies:

| Problem | Manifestation | Root Cause |
|---------|---------------|------------|
| **Timeout** | `EvalResult` can hold MB of eval output; reflection LLM hits context limit or returns partial text | No output cap on eval traces |
| **Non-convergence** | Loop spins for `max_rounds` even when artifact stagnates | No stagnation detection; severity monotonicity not enforced |
| **Growth** | Artifact size monotonically increases across iterations | No size guard; LLMs append fixes rather than replace |

Additionally: shell injection (unquoted path), API key exfiltration (eval STDERR to LLM), and unbounded `max_rounds` (default 3, but user can pass 1000).

---

## 2. Representation Categories

The algorithm treats artifacts as structured text with **regions** that have different optimization semantics.

### 2.1 Region Types

```
┌─────────────────────────────────────────────────────────────┐
│ YAML FRONTMATTER (immutable schema)                         │
│   triggers: [...]     ← can be appended, not reordered      │
│   keywords: [...]     ← can be appended                     │
├─────────────────────────────────────────────────────────────┤
│ ARMORED REGIONS (read-only)                                 │
│   <section name="machine_protocol">...</section>            │
│   <section name="budget_guards">...</section>               │
│   ← NEVER passed to reflector for modification              │
├─────────────────────────────────────────────────────────────┤
│ OPTIMIZABLE REGIONS (reflect-eligible)                      │
│   <section name="identity">...</section>                    │
│   <section name="cognitive_frameworks">...</section>        │
│   <section name="protocols">...</section>                   │
│   ← full reflection target                                  │
├─────────────────────────────────────────────────────────────┤
│ TRAILING CONTENT (free-form)                                │
│   ← subject to size cap                                     │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Artifact Metadata

Each artifact carries structural metadata used by the algorithm:

```python
@dataclass
class ArtifactMeta:
    name: str                    # e.g. "lucien-soul", "hermes-agent"
    type: Literal["soul", "skill", "generic"]
    total_lines: int
    total_chars: int
    region_count: int            # number of ARMORED + OPTIMIZABLE regions
    size_mb: float               # for growth tracking
    last_modified: float         # epoch timestamp
```

### 2.3 Failure Trace Types

```python
FAILURE_TYPE_WEIGHTS: dict[str, float] = {
    "protocol_violation": 2.0,   # agent ignored explicit instruction
    "correction": 1.5,           # user corrected agent
    "tool_failure": 0.5,         # tool error (less actionable for prompts)
    "general": 1.0,              # default
}
```

Weights affect **multiplier calculation** (Section 4).

---

## 3. Forward/Reverse Audit Loop

The v2 algorithm runs a **bidirectional audit loop**: forward optimization with real failure traces, and reverse audit to validate that proposed changes don't introduce regressions.

### 3.1 Forward Pass (Optimize)

```
FORWARD PASS
─────────────────────────────────────────────────────────
Input:  artifact, failure_traces, history
Output: improved_artifact, audit_report

1. TRUNCATE artifact to max_artifact_chars (default 60000)
   - Preserve head (first N chars) and tail (last N chars)
   - Insert "..." marker in middle

2. QUERY session_db for contrastive traces
   - find_corrections(skill_name) → severity-weighted
   - find_protocol_violations() → HIGH severity
   - find_tool_failures() → LOW severity
   - Sample with FAILURE_TYPE_WEIGHTS

3. CONSTRUCT reflection prompt
   - System: immutable instructions (cache key: stable prefix)
   - User: artifact + failure_traces + history + size_budget

4. CALL reflector.reflect(prompt, system)
   - Capture output; reject if < 10 chars or > 2× artifact size

5. RUN reverse audit on candidate (Section 3.2)
   - If audit FAILS: keep old artifact, log regression
   - If audit PASSES: accept candidate

6. UPDATE history log
   - Record: round, severity_before, severity_after, size_delta
```

### 3.2 Reverse Pass (Audit)

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
     - If region content identical → skip
     - If region content changed:
       - Does change address ANY failure trace?
       - Does change introduce NEW ambiguity?
       - If no failure addressed AND ambiguity introduced → FAIL

3. SIZE CHECK
   - new_artifact.size <= old_artifact.size × size_multiplier_cap (1.5×)
   - If exceeded: audit_result = REVIEW (flag for human)

4. STAGNATION CHECK
   - Compare new_artifact against last 3 history entries
   - If hamming_distance(new, last_3) < threshold:
     - Flag as stagnant; do NOT accept

5. Return audit_result
```

### 3.3 Loop Control

```python
for round_num in range(max_rounds):
    # Forward
    candidate = forward_pass(artifact, traces, history)
    
    # Reverse
    audit = reverse_pass(old_artifact, candidate, traces)
    
    if audit == PASS:
        artifact = candidate
        history.append(entry)
    elif audit == FAIL:
        log_regression(round_num)
        continue  # try next round with same artifact
    else:  # REVIEW
        flag_for_human()
        break  # stop, don't auto-apply
    
    # Convergence check (Section 5)
    if converged(artifact, history):
        break
```

---

## 4. Multiplier Calculation

The algorithm uses a **dynamic failure multiplier** to weight which traces to surface in each iteration. This prevents the reflector from being overwhelmed by low-severity noise while ensuring critical failures remain prominent.

### 4.1 Multiplier Formula

```
multiplier(trace, round) = base_weight × round_factor × recency_factor

where:
  base_weight      = FAILURE_TYPE_WEIGHTS[trace.type]
  round_factor     = 1.0 + (round_num × 0.1)  # escalate critical over rounds
  recency_factor   = 1.0 / (1.0 + age_days)   # prefer recent failures
```

### 4.2 Effective Trace Count

```python
def effective_trace_count(traces: list[FailureTrace], round_num: int) -> int:
    """Return number of traces after multiplier weighting and capping."""
    weighted = []
    for t in traces:
        age_days = (time.now() - t.timestamp) / 86400
        m = FAILURE_TYPE_WEIGHTS.get(t.failure_type, 1.0)
        m *= 1.0 + (round_num * 0.1)
        m /= (1.0 + age_days)
        weighted.append((t, m))
    
    # Sort by multiplier descending, take top N
    weighted.sort(key=lambda x: x[1], reverse=True)
    return min(len(weighted), MAX_EFFECTIVE_TRACES)  # default 5
```

### 4.3 Severity Budget

Each round has a **severity budget** — the sum of multipliers for all traces surfaced. If budget exceeded, downgrade lower-severity traces.

```python
SEVERITY_BUDGET_PER_ROUND = 10.0

def apply_severity_budget(traces, budget=SEVERITY_BUDGET_PER_ROUND):
    """Trim traces so total multiplier sum <= budget."""
    total = sum(m for _, m in traces)
    if total <= budget:
        return traces
    # Scale down multipliers proportionally
    scale = budget / total
    return [(t, m * scale) for t, m in traces]
```

---

## 5. Convergence Detection

v2 introduces **multi-signal convergence detection** to stop the loop when improvement plateaus, preventing wasted LLM calls and artifact growth.

### 5.1 Convergence Signals

| Signal | Condition | Weight |
|--------|-----------|--------|
| **PASS** | eval passes (exit 0) | terminal |
| **Stagnation** | `severity_after >= severity_before` for 3 consecutive rounds | 0.4 |
| **Size plateau** | `abs(size_delta) < 50 chars` for 3 consecutive rounds | 0.3 |
| **Diminishing returns** | Each round fixes < 20% of remaining traces | 0.3 |
| **Max rounds** | `round_num == max_rounds` | terminal |

### 5.2 Convergence Score

```python
def convergence_score(history: list[LearningLogEntry]) -> float:
    """Return 0.0 (not converged) to 1.0 (converged)."""
    if len(history) < 2:
        return 0.0
    
    recent = history[-3:]
    
    # Signal 1: severity trend
    severities = [e.severity_after for e in recent]
    severity_stable = all(s >= severities[0] for s in severities)
    
    # Signal 2: size trend
    sizes = [len(e.change_summary) for e in recent]
    size_stable = max(sizes) - min(sizes) < 100
    
    # Signal 3: trace fix rate
    traces_fixed = sum(1 for e in recent if e.observed_outcome == "improvement")
    fix_rate = traces_fixed / len(recent)
    
    score = (0.4 if severity_stable else 0.0) + \
            (0.3 if size_stable else 0.0) + \
            (0.3 if fix_rate < 0.2 else fix_rate)
    
    return min(score, 1.0)
```

### 5.3 Convergence Decision

```python
def is_converged(history: list[LearningLogEntry]) -> bool:
    """True when algorithm should stop."""
    if len(history) < 2:
        return False
    
    score = convergence_score(history)
    
    # Hard stops
    if score >= 0.8:
        return True
    
    # Soft stop: 2+ signals active
    signals_active = sum([
        score >= 0.6,
        len(history) >= 3 and history[-1].observed_outcome != "improvement",
    ])
    return signals_active >= 2
```

---

## 6. Safety Constraints

### 6.1 Input Sanitization

```python
# Eval output sanitization (prevents credential leakage to LLM)
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

## 7. Pseudocode

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
       max_rounds ← MAX_ROUNDS_CAP  # default 20

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
     
     # -- Reverse: audit candidate --
     audit ← reverse_audit(meta, candidate, traces)
     
     IF audit == FAIL:
         log_regression(round_num, candidate)
         CONTINUE  # try again next round
     
     IF audit == REVIEW:
         flag_for_human_review(candidate)
         BREAK  # don't auto-apply
     
     # -- Accept candidate --
     artifact ← candidate
     entry ← LearningLogEntry(
         attempted_change="reflection_round_" + round_num,
         observed_outcome=detect_outcome(history, entry),
         severity_before=traces.max_severity,
         severity_after=0  # TBD by next eval
     )
     history.append(entry)
     
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
       learning_log=history
   )
```

---

## 8. Component Responsibilities

| Component | File | v1 Status | v2 Change |
|-----------|------|-----------|-----------|
| **Optimizer** | `optimizer.py` | Loop with no convergence | Add reverse audit, multiplier, convergence signals |
| **Reflector** | `reflector/engine.py` | Single LLM call | Add size_budget param, hypothesis-first mode |
| **Evaluator** | `evaluator/shell.py` | Basic eval | Add output truncation, keep sanitize |
| **SessionDB** | `datastore/session_db.py` | Basic queries | Add multiplier-aware sampling |
| **Targets** | `targets/soul.py`, `targets/skill.py` | Stubs | Implement ARMORED region parsing |
| **Audit** | `auditor.py` (NEW) | N/A | Reverse audit logic |

---

## 9. Performance Characteristics

| Metric | v1 | v2 |
|--------|----|----|
| Max LLM calls | Unbounded | `max_rounds × 1` (capped at 20) |
| Eval output size | Unbounded | Capped at 4000 chars per trace |
| Artifact growth | Unbounded | Capped at 1.5× per round |
| Convergence | None | Multi-signal (severity, size, fix rate) |
| Security | Shell injection risk | `shlex.quote` + output sanitization |
| Stagnation detection | None | 3-round rolling window |

---

## 10. Open Design Decisions

| Decision | Options | Recommendation |
|----------|---------|----------------|
| **Hypothesis-first reflection** | Single call vs. two-step (diagnose → fix) | Two-step for complex SOUL.md; single for skills |
| **Convergence threshold** | Fixed (0.8 score) vs. adaptive | Fixed for predictability; adaptive for edge cases |
| **Size budget unit** | Characters vs. tokens vs. MB | Characters (simpler, no tokenizer dependency) |
| **Audit parallelism** | Sequential (forward then reverse) vs. parallel | Sequential (reverse depends on forward output) |
| **Learning log persistence** | In-memory only vs. disk | In-memory (CLI runs once per invocation) |

---

## 11. Appendix: v1 → v2 Migration Map

| v1 Artifact | v2 Replacement | Notes |
|-------------|----------------|-------|
| `optimizer.Optimizer.optimize_skill()` | `optimize_artifact()` with type dispatch | Unified interface |
| `optimizer.Optimizer.optimize_soul()` | Same function, `target_type="soul"` | ARMORED protection via target parser |
| `SessionDBReader.get_contrastive_summary()` | `get_contrastive_traces()` with weights | Multiplier-aware sampling |
| `Reflector.reflect()` | `reflect()` + `size_budget` | Prevents context overflow |
| No convergence detection | `convergence_score()` + `is_converged()` | Multi-signal |
| No reverse audit | `Auditor.reverse_audit()` | Structural + semantic checks |
| `EvalResult` raw trace | Sanitized + truncated trace | Security + bounded context |
