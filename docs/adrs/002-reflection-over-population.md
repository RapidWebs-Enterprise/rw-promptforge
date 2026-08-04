# ADR-002: Single Reflection Loop over Population Search

**Date:** 2026-08-03
**Status:** Accepted

## Context

We could use GEPA's `optimize_anything` (population-based Pareto
evolution) or DSPy's MIPROv2 compiler for prompt optimization. Both
require 100-500 evaluation runs per problem, each triggering full agent
invocations.

For our domain — refining a single SOUL.md or skill file — the search
space is narrow. The artifact is mostly correct; we need targeted fixes,
not from-scratch reconstruction. A population tournament optimizes for
global search breadth; we need depth on a single known artifact.

## Decision

**Single-instance reflective loop:** evaluate → reflect on failure trace
→ propose fix → evaluate again. 1 LLM call per iteration. No population.

## Why

1. **Domain-specific efficiency:** An LLM reading a failure trace and
   the original artifact can diagnose the root cause in a single call.
   "Step 3 says `skill_manage(action='create')` but it should be
   `skill_manage(action='patch')`" — trivially diagnosed by an LLM,
   but requires multiple evolutionary generations without trace
   reflection.
2. **Actionable side information is free:** The eval trace IS the
   diagnostic gradient. We don't need ASI provided by the evaluator as
   metadata (GEPA's approach) because the evaluator IS the process
   — any error output is diagnostic.
3. **Gradual convergence, not global search:** Skills/prompts improve
   incrementally as bugs surface. This maps to a linear refinement
   pattern, not a search over generational diversity.

## Cost comparison

| Approach | LLM calls per outcome | Config |
|----------|----------------------|--------|
| GEPA `optimize_anything` | 150–300 | max_metric_calls=150, one reflect per metric call |
| DSPy MIPROv2 | 50–200 | depends on trials, width, depth |
| **rw-promptforge (Ours)** | **2–9** | max_rounds=3, one reflect per round |

The speed difference is glowingly large enough that we can stroke
completing optimization workstations in minutes rather than hours.

## Consequences

- The tool is useful only for *targeted refinement* of existing
  artifacts — not for generating them from zero
- We trade GEPA's "37% better" global optimum finding for "fast
  targeted fix" — which suits our operational need
- Evaluation command must produce diagnostic output (not just a
  pass/fail score) to feed the reflector — good evaluations produce
  rich traces naturally