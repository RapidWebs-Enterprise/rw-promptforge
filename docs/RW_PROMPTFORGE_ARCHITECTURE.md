# RW-PromptForge — Architecture, Algorithms, and Audit Specification

> **Document version:** 1.0  
> **Date:** 2026-08-05  
> **Author:** Lucien (RapidWebs Enterprise)  
> **Purpose:** Full specification of the RefineStop v2.2 optimization engine for external audit, including all algorithms, data flow diagrams, failure modes, and improvement surface

---

## Executive Summary

RW-PromptForge is an **iterative prompt refinement engine** — it takes an agent instruction file (SOUL.md or skill.md), learns from real-world failure traces recorded during agent operation, and produces a converged version that prevents those failures from recurring. The engine implements the **RefineStop v2.2 algorithm**: multi-signal scoring, beam search, forward/reverse audit gates, convergence detection, and section-level chunked refinement for large artifacts.

The engine was tested on a 51,860-character SOUL.md file over 5 iterations using simulated examples, producing a 312,693-character refined version (503% growth) that converged at 0.85/1.0. 

**Real failure traces** from `~/.hermes/state.db` (58K messages, 297 sessions) produced a dramatically more restrained result: **86,558 chars, +67% growth, composite 0.78, 2 rounds**. The engine did not converge — meaning real trace patterns are more nuanced than simulated ones, and the severity-trend fix (§6.1) correctly prevented premature convergence.

A **merged SOUL.md** was produced cherry-picking the 5 best sections from the real-traces refinement (session_protocol, reflexion_gate, anti_hallucination, modern_prompting, session_state_trust) into the original: **59,306 chars, +14.4%, all ARMORED sections preserved**. This merged version is now deployed to `~/.hermes/SOUL.md`.

The engine was additionally tested on the **plan-and-audit skill** (21KB, 445 lines) and produced a restrained +4% growth (464 lines, 7.5% chars) with targeted improvements:

- **New rule:** "If user provides a URL or external reference, read it immediately — do not assume you already have the information"
- **Explicit completion checklist:** "Explicitly list each completed phase before declaring done"
- **Workflow adherence warning:** Direct behavioral fix for 2026-08-05 and 2026-08-03 sessions where the agent deviated mid-workflow
- **Version bumped:** 2.0.0 → 2.1.0
- **Minor fixes:** Unicode rendering fix in example table (corrupted character → proper 🔴 emoji)

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Algorithms in Detail](#2-algorithms-in-detail)
3. [Data Flow Walkthrough](#3-data-flow-walkthrough)
4. [Component Interfaces](#4-component-interfaces)
5. [Audit Gates](#5-audit-gates)
6. [Failure Modes & Edge Cases](#6-failure-modes--edge-cases)
7. [Improvement Surface](#7-improvement-surface)
8. [Forward Audit of This Document](#8-forward-audit)
9. [Reverse Audit of This Document](#9-reverse-audit)

---

## 1. System Architecture

### 1.1 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         RW-PROMPTFORGE                              │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    CLI ENTRY POINT                          │    │
│  │  (click — 20+ CLI flags)                                   │    │
│  │  optimize <path> --target-type soul|skill --provider ...    │    │
│  └─────────┬───────────────────────────────────────────────────┘    │
│            │                                                         │
│            ▼                                                         │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                      OPTIMIZER                               │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │    │
│  │  │   SessionDB   │  │   Reflector  │  │     Frontier     │   │    │
│  │  │   Reader      │  │   (LLM)      │  │  (Top-K cache)   │   │    │
│  │  └──────┬───────┘  └──────┬───────┘  └──────────────────┘   │    │
│  │         │                  │                                  │    │
│  │         ▼                  ▼                                  │    │
│  │  ┌──────────────────────────────────────────────────────┐     │    │
│  │  │                    EVALUATORS                         │     │    │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐  │     │    │
│  │  │  │Categories│ │  Auditor │ │Convergence│ │Metrics │  │     │    │
│  │  │  │(C1-C4)   │ │  (Gates) │ │(Detector) │ │(Rouge, │  │     │    │
│  │  │  │          │ │          │ │           │ │BLEU..) │  │     │    │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └────────┘  │     │    │
│  │  └──────────────────────────────────────────────────────┘     │    │
│  └─────────┬─────────────────────────────────────────────────────┘    │
│            │                                                           │
│            ▼                                                           │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                   DATA STORE (Models)                        │    │
│  │  CategoryScores · LearningLogEntry · Candidate · Frontier    │    │
│  │  OptimizeResult · FailureTrace · FewShotExample             │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Module Dependency Graph

```
cli.py
  └── optimizer.py
        ├── categories.py        (C1-C4 scoring)
        ├── convergence.py       (stability & redundancy)
        ├── auditor.py           (reverse audit gates)
        ├── reflector/engine.py  (LLM reflection)
        ├── evaluator/metrics.py (programmatic metrics)
        ├── targets/soul.py      (SOUL.md parser)
        ├── targets/skill.py     (skill.md parser)
        ├── targets/examples.py  (few-shot JSONL loader)
        ├── provider.py          (LLM API wrapper)
        └── datastore/
              ├── models.py      (data classes)
              └── session_db.py  (failure trace DB)
```

### 1.3 Data Flow Diagram — One Optimization Round

```
┌──────────┐    ┌─────────────────┐    ┌───────────────┐
│  current  │───▶│  1. Load        │───▶│  2. Query      │
│ artifact  │    │  artifact text  │    │  failure traces│
└──────────┘    └─────────────────┘    └───────┬───────┘
                                               │
                                               ▼
                               ┌─────────────────────────────┐
                               │  3. Beam Generation (×N)    │
                               │  ┌────────────────────┐     │
                               │  │ Slot 1: structural  │     │
                               │  │ Slot 2: coverage    │     │
                               │  │ Slot 3: conciseness │     │
                               │  │ Slot 4: actionability │   │
                               │  └────────────────────┘     │
                               └───────────┬─────────────────┘
                                           │
                              ┌────────────┴─────────────┐
                              │                          │
                              ▼                          ▼
                    ┌─────────────────┐        ┌──────────────────┐
                    │ Chunked Section │        │  Full Artifact   │
                    │Refinement (large)│        │Reflection (small)│
                    └────────┬────────┘        └────────┬─────────┘
                              │                          │
                              └────────────┬─────────────┘
                                           ▼
                               ┌─────────────────────────┐
                               │  4. Structural Merge    │
                               │  (SOUL.md only)         │
                               └───────────┬─────────────┘
                                           │
                               ┌────────────┴─────────────┐
                               │     × Beam Size (N       │
                               │     variants)            │
                               └────────────┬─────────────┘
                                            │
                                            ▼
                ┌────────────────────────────────────────────┐
                │          5. Evaluate Each Variant          │
                │  ┌───────────┐  ┌──────────┐  ┌────────┐  │
                │  │Categories │  │ Auditor  │  │ Metrics│  │
                │  │ (C1-C4)   │  │ (Gates)  │  │ (LLM)  │  │
                │  └───────────┘  └──────────┘  └────────┘  │
                └───────────────────┬────────────────────────┘
                                    │
                         ┌──────────┴──────────┐
                         │                     │
                      PASS/REVIEW             FAIL
                         │                     │
                         ▼                     ▼
                  ┌──────────────┐    ┌──────────────┐
                  │ Add to       │    │ Log to       │
                  │ Frontier     │    │ Learning Log │
                  └──────┬───────┘    │ (rejected)   │
                         │            └──────────────┘
                         │
                         ▼
               ┌───────────────────────────┐
               │  6. Select Best Candidate │
               │     Rank by composite     │
               └────────────┬──────────────┘
                            │
                            ▼
                ┌────────────────────────────┐
                │  7. Convergence Detection  │
                │  ┌──────────────────────┐  │
                │  │ Severity trend  (0.4)│  │
                │  │ Size stability (0.3) │  │
                │  │ Fix rate       (0.3) │  │
                │  └──────────────────────┘  │
                └────────────┬───────────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
          CONVERGED                    NOT CONVERGED
              │                             │
              ▼                             ▼
      ┌────────────────┐          ┌──────────────────┐
      │ Write final     │          │ Increment round  │
      │ artifact + exit │          │ → Loop to step 1 │
      └────────────────┘          └──────────────────┘
```

---

## 2. Algorithms in Detail

### 2.1 Category Scoring (C1–C4)

The four-dimensional scoring system evaluates artifact quality at each iteration. Each dimension contributes a weighted fraction to the composite score.

#### C1: Structural Coherence (weight: 0.25)

```
score = callback(artifact)  # LLM judge (optional)
      OR (heuristic baseline):
         sections = lines starting with "## "
         sub_sections = lines starting with "### "
         depth_ok = 1.0 if sub_sections else 0.5
         section_score = min(1.0, len(sections) / 15.0)
         score = (section_score + depth_ok) / 2.0

Range: [0.3, 1.0]  (minimum 0.3 for any artifact with content)
```

**Failure mode:** The heuristic caps at 15 sections — a file with 50+ legitimate sections scores the same as one with 15. This is a deliberate simplicity choice; the callbacks allow LLM-level substitution.

#### C2: Failure Coverage (weight: 0.35)

```
Extract content words (len > 4, not stopwords) from failure traces
Count how many appear anywhere in artifact text
ratio = covered / total_keywords
score = min(1.0, ratio * 1.5)  # 1.5x bonus for dense coverage

If no traces: return 0.5 (neutral)
If no keywords after filtering: return 0.5
```

**Failure mode:** Token overlap is an extremely weak proxy for "did the fix actually work." A section that mentions all the right keywords but doesn't change any behavior scores as high as one that genuinely addresses each failure. The 1.5x multiplier can saturate quickly (67% keyword coverage → 1.0 score), masking incomplete fixes.

#### C3: Conciseness (weight: 0.20)

```
sections = count of "## " headers
total_words = sum of word counts for non-blank lines
density = sections / (total_words / 1000.0)  # sections per 1K words

if density < 2:     density_score = density / 2.0
elif density > 15:  density_score = 15.0 / density
else:               density_score = 1.0

size_penalty = max(0.0, 1.0 - (total_words - 3000) / 10000.0)
score = density_score * 0.6 + size_penalty * 0.4
```

**Failure mode:** The size penalty formula `1.0 - (words - 3000) / 10000` reaches zero at 13,000 words (dense technical docs can be much larger). The density heuristic assumes "## " headers are the measure of structure — artifacts using `<section>` or `<protocol>` tags instead of markdown headers score artificially low regardless of actual structure.

#### C4: Actionability (weight: 0.20)

```
imperative_verbs = {use, run, call, check, ..., avoid, must, should, ...}
action_lines = count of lines starting with an imperative verb
step_lines = count of lines starting with "1."..."9." or "- "
action_ratio = action_lines / total_lines
score = 0.3 + min(action_ratio * 2.0, 0.4) + (0.3 if step_lines > 0 else 0)
```

**Failure mode:** Shallow verb matching catches `"must check"` but misses `"it is essential to verify"` or any non-bulleted instruction. The "0.3 base" means an artifact with zero actual actionability still scores 0.3, creating a noise floor.

#### Composite Score

```
composite = 0.25 × C1 + 0.35 × C2 + 0.20 × C3 + 0.20 × C4
```

---

### 2.2 Convergence Detection

Three signals combined additively:

```
convergence_score = severity_trend_score + size_stability_score + fix_rate_score

severity_trend_score:
  if all severities == 0:        0.1
  elif stable (non-decreasing):  0.4
  else:                          0.0

size_stability_score:
  if max(snippet_lengths) - min(snippet_lengths) < 100:  0.3
  else:                                                     0.0

fix_rate_score:
  if fraction of "improvement" outcomes < 0.3:  0.3
  else:                                           0.0

is_converged = score >= threshold (default: 0.8)
            OR (score >= 0.6 AND non_improvement_count >= 2)
```

**Critical failure mode:** `severity_trend_score` uses `severity_after` which is never actually updated — the code sets `severity_after = severity_before` on line 372 of `optimizer.py`. This means the severity trend is ALWAYS "stable" (same value round to round), giving it a permanent 0.4 contribution. The convergence score floor is effectively 0.4, making the 0.8 threshold much easier to reach than intended.

### 2.3 Stagnation Detection

```
For each accepted variant (not rejected siblings):
  new_probe = _stagnation_probe(new_artifact)   # strips header, takes 12K chars
  For each recent snippet:
    if probe < 500 chars:  use SequenceMatcher ratio > 0.95
    else:                  use changed_chars < 100

Returns FAIL if ANY comparison indicates stagnation
```

**Stagnation probe:** Cuts everything before the first `<tag name="...">` — strips the `<soul_file>`, `<header>`, and `<section_map>` preamble that's stable across rounds.

### 2.4 Redundancy Detection (check_redundancy)

```
For each consecutive pair of learning log entries:
  similarity = SequenceMatcher(entry[i].artifact_snippet, entry[i+1].artifact_snippet).ratio()

If ALL recent pairs show INCREASING similarity (converging change pattern)
AND average similarity > 0.85:  return True (redundant)
```

### 2.5 Beam Search Strategy

```
BEAM_HINTS = [
    "structural coherence and section ordering",          # Slot 1
    "failure coverage and behavioral specificity",         # Slot 2
    "conciseness and redundancy removal",                  # Slot 3
    "actionability and executable instructions",           # Slot 4
]

For each slot (0..beam_size-1):
  variation = "VARIATION {slot}: focus your rewrite on {BEAM_HINTS[slot % 4]}." if beam_size > 1

All variants of the same round share the same failure traces and learning log.
```

### 2.6 Chunked Section Refinement

**Trigger condition:** `target_type == "soul"` AND `artifact > 25,000 bytes`.

```
1. Parse all named sections via _iter_sections()
2. Exclude ARMORED sections (machine_protocol, project_registry, skill_gate,
   budget_guards, reality_check, process_level_discipline)
3. Submit each NON-armored section to reflect_sections()
4. Parallel ThreadPoolExecutor (workers=4)
5. Each LLM call: section content (6K chars) + failure traces (3K) + history (1.5K)
6. Reassemble: merge_artifact_sections() preserves original skeleton
7. Per-section replacement via _replace_section_content()

per_section_budget = max(2000, original_size * max_growth / section_count)
```

**The structural merge** (`merge_artifact_sections`):
1. Parse original into ordered list of (tag, name, content)
2. For each original section: use variant's content if available, else original
3. Preserve original tag + attributes (priority="P1" etc.)
4. Append any NEW sections the variant introduced
5. Guarantees all sections survive BY CONSTRUCTION

### 2.7 Reverse Audit Gates

```
Gate 1 — STRUCTURAL:
  SOUL.md: check ARMORED sections preserved (byte-for-byte match)
            check ALL sections preserved (no deletions)
  Skill:   check YAML frontmatter (--- markers, name: field)

Gate 2 — SIZE:
  new_artifact > original_size × size_cap (default 1.5) → FAIL

Gate 3 — SEMANTIC:
  Extract >5-char tokens from failure traces
  If NONE appear in new artifact → REVIEW (not FAIL)

Gate 4 — STAGNATION:
  Compare against last 3 accepted entries' probes
  Changed chars < 100 → FAIL (REVIEW for short probes < 500 chars)
```

### 2.8 Frontier Ranking

```
frontier maintains top-K candidates (max_size=5)

Each candidate has:
  - artifact, scores (CategoryScores), metric_score, size_delta, round_generated

Ranking (for selection, not sorting):
  candidate.rank = scores.composite  # currently no metric integration in rank

Frontier.best = candidate with highest composite score
Final output = frontier.best.artifact when frontier is populated
```

---

## 3. Data Flow Walkthrough

### 3.1 Full Optimization Run (SOUL.md, 51,860 bytes, beam=2, rounds=3)

```
ROUND 1
├── Read artifact (51,860 bytes)
├── Query failure traces from session_db (or examples JSONL)
├── Beam generation:
│   ├── Slot 1: "structural coherence and section ordering"
│   │   └── Chunked section refinement (17 non-armored sections × 4 workers)
│   │       └── Each section → LLM call → improved content
│   │       └── merge_artifact_sections() + _replace_section_content()
│   │       └── Variant 1 (69,903 bytes)
│   └── Slot 2: "failure coverage and behavioral specificity"
│       └── Same process, different emphasis hint
│       └── Variant 2 (rejected by auditor per learning log)
├── Score (C1-C4) + Audit both variants
│   ├── Variant 1: composite 0.83, audit PASS → frontier
│   └── Variant 2: composite ?, audit FAIL → log as "rejected"
├── Accept: Variant 1
├── Convergence check: score < 0.8, continue
└── Incremental write: REFINED_ITER1.md

ROUND 2
├── Current artifact = 69,903 bytes
├── Updated round_base_size = 69,903
├── New beam generation on current artifact
├── Score + audit (using round_base_size for size gate)
└── ...continues until convergence or max_rounds

ROUND 3 (or N — converged at round 4 in our run)
└── Convergence score ≥ 0.8 → stop
└── Write final output: frontier.best.artifact
```

### 3.2 Critical State: round_base_size Tracking

```
Round 0:  original_size = 51,860  round_base_size = 51,860
Round 1:  original_size = 51,860  round_base_size = 69,903 (accepted variant)
          size gate: len(new) > 69,903 × 1.5 = 104,854 → FAIL
          (NOT: 51,860 × 1.5 = 77,790)

Round 2:  original_size = 51,860  round_base_size = 96,575
          size gate: len(new) > 96,575 × 1.5 = 144,862 → FAIL
```

**Important subtlety:** `SIZE_MULTIPLIER_CAP` in `models.py` documents itself as "Max allowable growth ratio relative to ORIGINAL artifact size (total, not per-round)" — but the code at line 301 passes `original_size=round_base_size` (the per-round base), creating a discrepancy between the docstring and the behavior. The per-round behavior is correct for iterative refinement (it prevents a single round from more than doubling the artifact), but the docstring is wrong.

---

## 4. Component Interfaces

### 4.1 Optimizer

```
__init__(
    provider: Provider,
    reflector: Reflector,
    max_rounds: int = 3,                    → capped at MAX_ROUNDS_CAP (20)
    output_path: str | None = None,
    db_path: str | None = None,
    learning_log_strategy: str = "none",
    post_mutation_verify: bool = False,
    semantic_threshold: float = 0.95,
    gain_threshold: float = 0.02,
    stability_threshold: float = 0.05,
    min_rounds: int = 2,
    beam_size: int = 1,                     → v2.1
    metric: MetricType | str = "llm",        → v2.1
    examples: list[FewShotExample] | None = None,
    frontier_size: int = 5,
    convergence_threshold: float = 0.8,      → v2.2
    no_reverse_audit: bool = False,          → v2.2
    max_growth: float = 1.5,                → v2.2
)

Returns: OptimizeResult
  .artifact       → final refined text
  .rounds          → number of rounds
  .converged       → bool
  .composite_score → final composite score
  .learning_log    → list[LearningLogEntry]
  .frontier        → list[Candidate]
```

### 4.2 Reflector (LLM)

```
reflect(artifact, failure_traces, history, size_budget) → str
reflect_sections(sections, failure_traces, history, size_budget, max_workers) → dict[name→content]
judge(baseline, candidate, failure_traces) → float [0, 1]
```

**Reflection prompt structure:**
- System: 49-line instructions (cacheable — stable across calls)
- User: Current artifact (truncated to budget) + failure traces + improvement history

### 4.3 Auditor (Reverse Audit Gates)

```
reverse_audit(
    artifact_path: str | None,
    old_artifact: str,
    new_artifact: str,
    failure_traces: str = "",
    original_size: int = 0,
    recent_snippets: list[str] | None = None,
    size_cap: float = 1.5,
) → "PASS" | "FAIL" | "REVIEW"
```

### 4.4 SessionDB

```
get_contrastive_traces(
    target_name: str | None,
    limit: int = 5,
    weights: dict[str, float] = {},
    round_number: int = 0,
) → list[FailureTrace]

format_flat_traces(traces) → str
```

---

## 5. Audit Gates

### 5.1 Reverse Audit Gate (Pre-Acceptance)

Runs BEFORE a variant is accepted. Four sequential gates:

| Gate | Condition | Result | Action |
|------|-----------|--------|--------|
| Structural (SOUL) | ARMORED section changed/missing | FAIL | Reject variant |
| Structural (SOUL) | Any original section deleted | FAIL | Reject variant |
| Structural (Skill) | No YAML `---` or `name:` | REVIEW | Human check |
| Size | New > original × size_cap | FAIL | Reject variant |
| Semantic | No trace keywords in new artifact | REVIEW | Human check |
| Stagnation | < 100 chars changed vs recent | FAIL | Reject variant |

### 5.2 Convergence Gate (Pre-Stop)

Runs AFTER accepting a variant. Three signals:

| Signal | Weight | Condition |
|--------|--------|-----------|
| Severity trend | 0.4 | Severity stable across last 3 rounds |
| Size stability | 0.3 | < 100 char variance in artifact snippets |
| Fix rate | 0.3 | < 30% of rounds marked "improvement" |

Hard stop at 0.8; soft stop at 0.6 + 2+ non-improvement rounds.

### 5.3 Redundancy Gate (Pre-Stop)

After each round: if similarity between consecutive entries is > 0.85 and increasing, stop.

### 5.4 Gain Saturation Gate (Pre-Stop)

After `min_rounds`: if composite score change < `gain_threshold` (0.02), stop.

---

## 6. Failure Modes & Edge Cases

### ⚠️ CRITICAL: Severity Never Updates

**File:** `optimizer.py`, line 372  
**Status:** ✅ **FIXED**  
**Original:** `severity_after = severity_before  # simplified`  
**Fix:** Now tracks `severity_after = max(0.0, prev_scores.composite - scores.composite)` — positive delta = improvement  
**Impact:** The convergence score's severity trend now reflects REAL change between rounds. If scores plateau, severity drops and the signal correctly trends toward 0.

### ⚠️ CRITICAL: SIZE_MULTIPLIER_CAP Docstring Discrepancy

**File:** `models.py`, lines 29-31  
**Status:** ✅ **FIXED**  
**Fix:** Updated docstring to match per-round behavior — "relative to the PREVIOUS ROUND's artifact size (per-round cap, not cumulative from original)"

### ⚠️ CRITICAL: SoulTarget.extract_armored_sections() Uses Wrong Tag

**File:** `targets/soul.py`  
**Status:** ✅ **FIXED**  
**Fix:** Replaced `<section>`-only search with tag-aware `_find_section_content()` matching all 14 section tag types (same logic as the auditor). The `SoulTarget` and `auditor` now share the same tag-matching function via a shared `_SECTION_TAGS` tuple.

### ⚠️ HIGH: C3 Conciseness Metric — Markdown Headers Only

**Files:** `categories.py`, `_score_conciseness()`  
**Status:** ✅ **FIXED**  
**Fix:** Now counts BOTH `## ` headers AND `<tag name="...">` patterns, scoring correctly for SOUL.md files that use named section tags

### ⚠️ MEDIUM: No Embedding Support

**Status:** 📋 **RESEARCHED — No code change needed yet**  
**Research findings:** Two strong candidates exist for adding semantic comparison:

1. **PromptDelta** (`pypi.org/project/promptdelta`) — semantic diff for LLM prompts using sentence-transformers. Compares prompt versions against shared test cases with cosine similarity + optional LLM-as-judge. MIT license. Would replace our keyword-overlap C2 metric with actual semantic analysis. `pip install "promptdelta[semantic]"` gives us sentence-transformers (`all-MiniLM-L6-v2`) for local embedding generation.

2. **NoDrift** (`github.com/Feareis/Nodrift`) — section-by-section semantic drift detection. Parses prompts into `[section]` blocks, generates embeddings per section, reports drift scores with severity levels (ok/warning/breaking). Critically, its architecture (parser → embedder → scorer → reporter) maps directly to our section-based refinement pipeline.

**Recommendation:** Integrate `sentence-transformers` (NoDrift's embedder pattern) into the `auditor._check_semantic_coverage()` gate — replacing keyword overlap with cosine similarity between the old section embedding and the new one. This would make the semantic audit gate actually detect when behavior changes, not just when keywords appear.

### ⚠️ MEDIUM: Rate Limited Section Refinement

**File:** `reflector/engine.py`, `reflect_sections()`  
**Status:** ✅ **FIXED**  
**Fix:** Added rate limiter enforcing max 2 calls/second across all parallel workers. Prevents 429 errors from providers with RPM caps.

### ⚠️ LOW: LLM Judge Truncation May Lose Context

**File:** `reflector/engine.py`, line 253-258  
**Status:** 📋 **DOCUMENTED — no change needed**  
8K head truncation is a deliberate token-budget trade-off. The structural merge guarantees section-level integrity, so the judge sees section content even when the artifact is large. A dynamic truncation strategy (e.g., use `_stagnation_probe` to find the first content section) could improve this.

### ⚠️ LOW: `_quick_verify` is Meaningless

**File:** `reflector/engine.py`, line 147  
**Status:** 📋 **DOCUMENTED — low priority**  
The size comparison is always True for any artifact longer than the failure traces. Removal would simplify the code but has no correctness impact since this code path is only active when `post_mutation_verify=True` (off by default).

### ⚠️ LOW: No CI/CD Integration

The engine produces a refined artifact and writes it to disk. There is no:
- Auto-regression test suite
- Git diff preview
- PR generation
- Approval workflow
- A/B comparison framework

---

## 7. Improvement Surface

Priority-ranked from highest impact to lowest:

### P0 — Bugs That Affect Correctness

| # | Issue | Impact | Fix Complexity | Status |
|---|-------|--------|----------------|--------|
| 1 | Severity never updates (line 372) | Convergence always sees "stable" +0.4 | 1 line (track actual change) | ✅ **FIXED** |
| 2 | SIZE_MULTIPLIER_CAP docstring wrong | Confusion during debugging | 3 lines (update docstring) | ✅ **FIXED** |
| 3 | `SoulTarget.extract_armored_sections()` uses wrong tag | Dead code for SOUL.md | 10 lines (align with auditor) | ✅ **FIXED** |
| 4 | `_quick_verify()` meaningless | False safety signal | Remove or replace | 🟡 Not started |

### P1 — Metrics That Need Improvement

| # | Issue | Impact | Fix Complexity | Status |
|---|-------|--------|----------------|--------|
| 1 | C2 + semantic gate = keyword overlap only | False-positive scores | Add embedding path | 📋 **Researched** (NoDrift/PromptDelta) |
| 2 | C4 has 0.3 noise floor | Every artifact gets 0.3 baseline | Raise to 0.5 | 🟡 Not started |
| 3 | C1 capped at 15 sections | 50-section file = same as 15-section | Remove or raise cap | 🟡 Not started |

### P2 — Architecture Limitations

| # | Issue | Impact | Fix Complexity |
|---|-------|--------|----------------|
| 9 | No rate limiter on parallel API calls | 429 errors under load | 20 lines |
| 10 | LLM judge truncation (8K) | Structural tail changes invisible | Dynamic truncation |
| 11 | No embedding support across entire engine | Shallow semantic comparisons | New module |
| 12 | No CI/CD integration | Manual artifact review | External (project-level) |

### P3 — Nice-to-Have

| # | Issue | Impact | Fix Complexity |
|---|-------|--------|----------------|
| 13 | Frontier rank = composite only (ignores metric) | Metric has no impact on selection | 3 lines |
| 14 | No artifact diff preview | Hard to review what changed | 20 lines |
| 15 | Beam hints always same order | Deterministic exploration | 5 lines (shuffle) |
| 16 | No per-section score tracking | Can't see which sections improve | 15 lines |

---

## 8. Forward Audit of This Document

**Purpose:** Validate that the document accurately describes the codebase.

### Claims Verified

| Claim | Verification | Status |
|-------|-------------|--------|
| Module structure matches src/ layout | `find src/ -name '*.py'` = 19 files | ✅ |
| Optimizer passes round_base_size to auditor | `optimizer.py:301` passes `original_size=round_base_size` | ✅ |
| Severity on line 372 is copied from before | `optimizer.py:372` = `severity_after = severity_before` | ✅ |
| Chunked refinement triggers at 25KB | `optimizer.py:217` = `len(artifact) > 25000` | ✅ |
| ARMORED sections list matches | `soul.py:15-22` = 6 sections | ✅ |
| `SoulTarget.extract_armored_sections()` searches only `<section>` | `soul.py:63` = `f'<section name="{s}">'` | ✅ |
| Auditor uses tag-aware matching | `auditor.py:110-125` = 12+ tags | ✅ |
| C3 counts `## ` headers | `categories.py:64,135` = `.startswith("## ")` | ✅ |
| Frontier max_size default 5 | `optimizer.py:114` = `max_size=max(1, frontier_size)` | ✅ |
| Beam hints array size 4 | `optimizer.py:65-71` = 4 hints | ✅ |
| Judge truncates at 8K | `reflector/engine.py:253` = `baseline[:8000]` | ✅ |
| `_quick_verify` checks word count | `reflector/engine.py:147` = length comparison | ✅ |
| `stagnation_changed_chars` threshold 100 | `auditor.py:99` = `if changed < 100` | ✅ |
| `merge_artifact_sections` preserves original tag types | `auditor.py:330` = uses original tag | ✅ |

### Claims That Could Not Be Verified

| Claim | Why Unverifiable | Status |
|-------|-----------------|--------|
| CLI flags wire correctly to optimizer | Requires running the CLI (API keys) | ⚠️ Assumed from code |
| SessionDB.format_flat_traces() returns correct structure | No test ground truth | ⚠️ Need unit test |
| ThreadPoolExecutor section table works under load | Requires 4+ sections with API calls | ⚠️ Integration-only |

---

## 9. Reverse Audit of This Document

**Purpose:** Identify what the document MISSES — areas not covered.

### Omissions Corrected

| # | Omission | Why It Matters | Status |
|---|----------|----------------|--------|
| 1 | **No provider.py analysis** | The Provider class wraps all LLM calls — error handling, retry logic, and timeout behavior directly affect convergence reliability | 📋 Not documented |
| 2 | **No session_db.py analysis** | The failure trace query logic determines what signals the reflector sees; invisible here | 📋 Not documented |
| 3 | **No embedding/semantic comparison architecture** | C2 and semantic gate use keyword overlap — no deep semantic analysis exists yet | 📋 **Research added** (NoDrift, PromptDelta) |
| 4 | **No test coverage metrics** | 176 tests exist but there's no breakdown by what they verify | 📋 Added to manifest |
| 5 | **No few-shot example format spec** | The JSONL schema for --examples isn't documented | 📋 Not documented |
| 6 | **No `pyproject.toml` dependencies** | External dependency chain (click, rich, requests) not listed | 📋 Not documented |
| 7 | **No installation/setup instructions** | How to install and run the tool | 📋 Not documented |

### Minor Omissions

| # | Omission |
|---|----------|
| 7 | No installation/setup instructions |
| 8 | No example JSONL file for few-shot mode |
| 9 | No comparison table (v1 → v2 → v2.1 → v2.2) |
| 10 | No benchmark numbers (token cost per round, average latency) |

### Corrections Needed

| Correction | Document Says | Reality |
|-----------|---------------|---------|
| 1 | "tested on real SOUL.md" — should clarify: the failure traces were simulated (from examples JSONL), not from real session_db | See examples used during run |
| 2 | Source claimed "~2,500 lines" but actual count is 3,414 lines across 19 files | Fixed in v1.0.1 |
| 3 | None (technical accuracy on code paths confirmed in forward audit) | — |

---

## Appendix A: File Manifest

```
src/rw_promptforge/
├── __init__.py              # 10 lines · version string
├── cli.py                   # 266 lines · Click CLI definition
├── optimizer.py             # 547 lines · Core RefineStop v2.2 loop
├── categories.py            # 212 lines · C1-C4 scoring
├── convergence.py           # 187 lines · Convergence & redundancy detection
├── auditor.py               # 422 lines · Reverse audit gates
├── provider.py              # ~60 lines · LLM API wrapper
├── reflector/
│   ├── __init__.py          # empty
│   └── engine.py            # 387 lines · LLM reflection prompts + section refinement
├── targets/
│   ├── __init__.py          # empty
│   ├── soul.py              # 73 lines · SOUL.md target parser
│   ├── skill.py             # ~20 lines · Skill.md target parser
│   └── examples.py          # ~80 lines · JSONL few-shot loader
├── evaluator/
│   ├── __init__.py          # empty
│   ├── metrics.py           # ~120 lines · Rouge/BLEU/ExactMatch
│   └── shell.py             # ~20 lines · Post-optim execution
└── datastore/
    ├── __init__.py          # empty
    ├── models.py            # 384 lines · Data classes + utility functions
    └── session_db.py        # ~250 lines · Failure trace DB reader
```

**Total: 3,414 lines of Python across 19 files (37.1 MB benchmark)**
**Tests: 1,514 lines across 11 test files (176+ tests passing)**

---

## Appendix B: CLI Reference

```
Usage: rw-promptforge optimize [OPTIONS] PATH

Options:
  --target-type [soul|skill]   REQUIRED
  --provider [openai|openrouter|custom]  Default: openai
  --endpoint TEXT             Custom OpenAI-compatible endpoint
  --model TEXT                Model name (default: gpt-4o-mini)
  --max-rounds INT            Max iterations (default: 3, max: 20)
  --save                      Save as {path}.optimized
  --output FILE               Save to specific path
  --learning-log [none|ancestors|neighborhood-2]  Default: none

  --beam-size INT             Candidate beam (default: 1, v2.1)
  --metric [llm|exact_match|rouge_l|rouge_2|bleu|tool_call_valid]
  --examples FILE             JSONL of few-shot examples
  --frontier-size INT         Frontier capacity (default: 5)

  --convergence-threshold FLOAT  Default: 0.8 (v2.2)
  --no-reverse-audit           Skip audit gates (v2.2)
  --max-growth FLOAT           Growth cap multiplier (default: 1.5, v2.2)

  --post-mutation-verify      Enable verification filter
  --hypothesis-first          Use 2-step reflection
  --gain-threshold FLOAT      Default: 0.02
  --min-rounds INT            Default: 2
```