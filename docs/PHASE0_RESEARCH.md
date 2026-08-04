# Phase 0 — Research: Competitive Landscape

**Project:** rw-promptforge
**Date:** 2026-08-04
**Mode:** MEDIUM (plan-and-audit pipeline)

---

## 1. Landscape Summary

Prompt optimization in 2026 is dominated by two approaches:

| Approach | Mechanism | LLM Calls | Representative Tools |
|----------|-----------|-----------|---------------------|
| **Population evolution** | LLM-guided mutation + Pareto/beam search over a population of candidates | 100-500+ | GEPA, DSPy MIPROv2, apo-adk-cli |
| **Iterative reflection** | Single-instance evaluate→reflect→improve loop | 2-50 | loopr, reflex, rw-promptforge |

rw-promptforge sits in the **iterative reflection** category — the leanest, fastest approach for single-artifact refinement.

---

## 2. Competitive Analysis

### 2.1 `loopr` (Rohit Raj, 2026)
- **Identity:** Local-first, zero-account, `pip install` + YAML task definition
- **Flow:** seed prompt → run on eval cases → score → reflect (GEPA-lite) → rewrite
- **Strengths:** Deterministic scoring, YAML task files, fast convergence (~1 iter), stub-LLM testability
- **Weaknesses:** Prompt-only (no skill/SOUL.md targets), no session_db, no armored sections
- **Key insight:** 28 tests with stub LLM — we should adopt the same pattern for **rw-promptforge**.

### 2.2 aevyra-reflex (Aevyra AI, 2026)
- **Identity:** Full-featured prompt optimization agent with dashboard
- **Flow:** eval → diagnose failure → rewrite → repeat, with `pipeline` mode for multi-step agent systems
- **Strengths:** Crash-safe resumption, interrupt/resume, MLflow + W&B integration, branch runs, 4 strategy axes
- **Weaknesses:** Dependency heavy (numpy, multiple strategies), no SOUL.md domain knowledge
- **Key insight:** Their pipeline mode re-runs full agent pipeline per candidate — **our ShellEvaluator does the same thing** but simpler (just a shell command, no Python pipeline DSL).

### 2.3 gepars (HyperFrequency, 2026)
- **Identity:** Rust implementation of GEPA algorithm
- **Flow:** Full population-based GEPA with Pareto frontier, reflective mutation
- **Strength:** 35× fewer rollouts vs RL, +6% over GRPO
- **Weakness:** Requires 150-500 metric calls, not designed for single-instance refinement
- **Key insight:** **35× fewer rollouts than RL is the benchmark to cite** — rw-promptforge is another ~15× cheaper than GEPA (2-9 calls vs 150).

### 2.4 apo-adk-cli (Microsoft/Google, 2023/2026)
- **Identity:** APO algorithm (textual gradients + beam search) via Google ADK + LiteLLM
- **Flow:** Evaluate → critique → edit → select (beam search over prompt variants)
- **Strength:** Proven algorithm (Pryzant et al., 2023); beam search diversity
- **Weakness:** Requires Google ADK ⊋ AgentLightning; batch/metric on datasets (not shell eval)

### 2.5 Ralph Loop Optimizer (2026)
- **Identity:** All-purpose optimizer for any git repo with an evaluation command
- **Flow:** init harness repo → seed config → coding agent (Codex/Claude) makes one improvement → run eval → commit iteration → repeat
- **Strength:** Works for any domain (ML policy, architecture), not just prompts
- **Weakness:** Dep on Codex/Claude; not lightweight (full git cycle per iteration)
- **Key insight:** They use "one harness, one eval command" pattern — exactly our `ShellEvaluator` approach.

---

## 3. Key Design Decisions from Research

### 3.1 Deterministic scoring (loopr pattern)
We should adopt the pattern: scoring is always done programmatically (exit code + output analysis), not LLM-judged. LLM is only used for reflection.

### 3.2 Stub LLM for tests (loopr pattern)
The deterministic loop core (convergence, plateau, budget) should be fully testable with an injected stub LLM. Reflector can take a fake provider.

### 3.3 Crash-safe resumption (reflex pattern)
`--resume` with find artifact and history from disk is non-trivial for our first version BUT the pattern of "save iteration state to disk per round" is correct.

### 3.4 Open-source tool-like (not platform-like)
loopr's "just pip install and go" model beats GEPA's "you need an adapter + metric + trainset" model for the setup. We follow the former.

---

## 4. Our Positioning

| Metric | Our Approach | Competitive Advantage |
|--------|-------------|----------------------|
| **Domain** | SOUL.md + Skills (not generic prompts) | Unique — no tool optimizes agent configuration artifacts |
| **Cost** | 2-9 LLM calls per session | 25-100× cheaper than population search |
| **Evaluation** | Shell command (exit 0 = pass) | No framework, no Python DSL — just any CLI command |
| **Enrichment** | Session DB traces (what skilled failed?) | No other tool reads agents actual usage history |
| **Provider** | Any OpenAI-compatible endpoint | No vendor lock-in — works with agentgateway |
| **Size** | ~200 LOC target | Loopr ~500 LOC, reflex ~3K LOC, GEPA ~15K LOC |
| **Simplicity** | 1 reflection call per round, 3 rounds max | KISS principle — debugging is predictable |
| **License** | MIT | All tools tested are OSS (MIT/Apache 2.0), ours lands in RapidWebs ecosystem |

---

## 5. References

- [GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning](https://arxiv.org/abs/2507.19457) — ICLR 2026 Oral
- [APO: Automatic Prompt Optimization with "Gradient Descent" and Beam Search](https://arxiv.org/abs/2305.03495)
- [Loopr: https://github.com/rohitguta2432/loopr](https://github.com/rohitguta2432/loopr) — 2026, local-first prompt optimizer
- [Aevyra Reflex: https://github.com/aevyraai/reflex](https://github.com/aevyraai/reflex) — 2026, agentic prompt optimization
- [GEPA-RS: https://github.com/HyperFrequency/gepars](https://github.com/HyperFrequency/gepars) — Rust implementation of GEPA
- [Ralph Loop Optimizer: https://github.com/haoran-ni/ralph-loop-optimizer](https://github.com/haoran-ni/ralph-loop-optimizer) — 2026, git repo optimization loop