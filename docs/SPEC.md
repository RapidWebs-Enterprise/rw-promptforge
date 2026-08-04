# rw-promptforge — Technical Specification

> **Version:** 0.1.0 | **Stage:** Pre-alpha | **Status:** Draft
>
> Simplify-Reflect-Evolve: iterative prompt and skill optimization CLI
> for the Hermes Agent ecosystem and beyond.

---

## 1. Purpose

rw-promptforge optimizes text artifacts that control LLM agent behavior —
SOUL.md system prompts and Hermes skill files — through a minimal
"evaluate → reflect → improve" loop. It replaces population-based
evolutionary search (GEPA) with single-instance reflective iteration
for this narrower domain.

**Core principle:** For prompt/skill optimization, a single reflective LLM
call per iteration that *reads the failure trace* is more effective than
a population tournament — and dramatically cheaper (1–3 calls vs. 150).

---

## 2. Target Artifacts

### 2.1 SOUL.md

A structured agent configuration file (~19KB for Lucien), containing:
- XML-tagged sections with `<section_map>` priority weights
- ARMORED sections (safety gates, budget guards, process discipline) — NEVER modified
- OPTIMIZABLE sections (identity, style, communication, cognitive frameworks, protocols)

Optimization goals: clarity, conciseness, compaction survival, reduced drift.

### 2.2 Hermes Skills

Markdown files (~500–3000 words) with YAML frontmatter, structured as:
- Triggers + keywords for auto-loading
- Numbered procedural steps with exact commands
- Pitfalls section
- Verification steps

Optimization goals: fill missing steps, update outdated commands/tool names,
tighten ambiguous instructions, add triggers for missed load patterns.

---

## 3. Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        CLI (click)                                │
│  rw-promptforge optimize <target> --target-type=soul|skill        │
│    --provider=openai|openrouter|custom                            │
│    --endpoint=<url> --model=<name>                                │
│    --max-rounds=N --eval-command="..." --save                     │
└──────────────┬───────────────────────────────────────────────────┘
               │
┌──────────────▼──────────┐
│     Optimizer           │  ← Orchestrates the loop
│  (optimizer.py)         │
│                         │
│  for r in 1..max_rounds:│
│    eval = evaluator.run │
│    if eval.passed:      │
│      break              │
│    artifact = reflector │
│               .reflect  │
│       (artifact, trace, │
│       session_history)  │
└──┬───────────┬──────────┘
   │           │
   ▼           ▼
┌──────────┐ ┌──────────────────┐
│Evaluator │ │ Reflector         │
│          │ │ (engine.py)      │
│ Shell    │ │                  │
│ EvalResult │ LLM reads trace  │
│ (exit,   │ → proposes fix    │
│ std/err) │ → returns improved │
│          │   artifact          │
└──────────┘ └──────┬───────────┘
                    │
                    ▼
              ┌──────────┐
              │ Provider  │
              │(provider  │
              │  .py)     │
              │ Any       │
              │OpenAI-    │
              │compatible │
              │ endpoint  │
              └──────────┘
```

### 3.1 Core Loop (Pseudo)

```
optimize(target_path, max_rounds=3, eval_command="..."):
    artifact = read(target_path)

    for round in 1..max_rounds:
        # Step 1: Evaluate
        temp_path = write_temp(artifact)
        result = ShellEvaluator(eval_command).evaluate(temp_path)

        # Step 2: Check
        if result.passed:
            print("✅ Converged in {round} rounds")
            save_if_requested(artifact)
            return

        # Step 3: Reflect
        session_context = fetch_session_context(artifact_name)
        artifact = Reflector(provider).reflect(
            artifact=artifact,
            trace=result.format_trace(),
            session_context=session_context,
            history=history_log,
        )
        history_log.append((round, result))

        # Step 4: Continue
        print(f"🔁 Round {round}: FAIL → reflecting...")

    print("⚠️  Did not converge. Best artifact saved as draft.")
```

---

## 4. Components

| Component | File | Responsibility |
|-----------|------|----------------|
| **CLI** | `cli.py` | Click-based entry point, param parsing |
| **Optimizer** | `optimizer.py` | Loop orchestration (to be built after TDD phase) |
| **Provider** | `provider.py` | OpenAI-compatible /chat/completions client |
| **Reflector** | `reflector/engine.py` | Reflection prompt construction + LLM call |
| **ShellEvaluator** | `evaluator/shell.py` | Execute shell command, capture exit+output |
| **SessionDBReader** | `datastore/session_db.py` | Read Hermes session_db for failure traces |
| **SoulTarget** | `targets/soul.py` | SOUL.md reader + section classifier |
| **SkillTarget** | `targets/skill.py` | Skill reader + frontmatter/body parser |

---

## 5. LLM Call Budget

| Call # | Purpose | Required? |
|--------|---------|-----------|
| **1** | Reflection — "read this failure trace, fix the artifact" | ✅ Always |
| 2 | Verification — "does this candidate look correct?" (optional) | ❌ Skip if in round-1 fast mode |
| 3 | Polish — minor wording cleanup | ❌ Only if requested |

**Maximum per optimization session:** 3 × max_rounds calls.
For max_rounds=3: at most 9 LLM calls. Typical expected: 2–4.

Comparison: GEPA's `optimize_anything` default = 100–150 metric calls × 1
reflection call each = 100–300 LLM calls. rw-promptforge is 25–100× cheaper.

---

## 6. Provider Support

Any endpoint that serves `/v1/chat/completions`:

| Provider | Endpoint | Auth |
|----------|----------|------|
| **OpenAI** | `https://api.openai.com/v1` | `OPENAI_API_KEY` |
| **OpenRouter** | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` |
| **agentgateway** | `http://infra:8010/v1` | `x-api-key` header |
| **Groq** | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` |
| **Gemini (compat)** | `https://generativelanguage.googleapis.com/v1beta/openai` | `GEMINI_API_KEY` |
| **NVIDIA** | `https://integrate.api.nvidia.com/v1` | `NVIDIA_API_KEY` |
| **Custom** | Any URL passed via `--endpoint` | `--api-key` flag |

---

## 7. Evaluation Model

### 7.1 Shell Evaluator

The user provides a `--eval-command` template. `{path}` is replaced at
runtime with the target's temporary file path.

```
# Exit 0 = pass. Anything else = fail.
rw-promptforge optimize skill ~/.hermes/skills/.../SKILL.md \
  --eval-command "hermes skill_view test --skill-path {path} 2>&1 | grep -q PASS"
```

### 7.2 Session Data Enrichment (v0.2+)

The eval trace is supplemented with historical data from Hermes session_db:
- Tasks where this skill was loaded
- Whether they succeeded or failed
- User corrections after skill usage
- Compaction-related context loss (via LCM db)

This gives the reflector rich Actionable Side Information at NO extra LLM cost.

---

## 8. Safety Constraints

### 8.1 SOUL.md Armored Sections

These sections are **never** passed to the reflector for modification:
- `machine_protocol` — machine ID verification
- `project_registry` — what we own vs. don't touch
- `skill_gate` — mandatory pre-flight
- `budget_guards` — API spend safety
- `reality_check` — verification protocol
- `process_level_discipline` — external review mandates

### 8.2 Skill Safety

- Only the body text is optimized (frontmatter preserved, triggers
  may be updated)
- Changes are proposed — never applied automatically
- `--save` flag required to write output file

### 8.3 Provider Safety

- API keys read from environment variables only
- Never hardcoded
- Never written to temp files, session logs, or output

---

## 9. Phased Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| **Phase 0** | Scaffold + SPEC + ADRs | ✅ Draft |
| **Phase 1** | TDD: Provider + Reflector + ShellEvaluator | 🔲 |
| **Phase 2** | Main loop (optimizer.py) + CLI wired | 🔲 |
| **Phase 3** | session_db integration + Skills → optimizer | 🔲 |
| **Phase 4** | SOUL.md target + armored section protection | 🔲 |
| **Phase 5** | `--save`, `--dry-run`, Rich progress UI | 🔲 |
| **Phase 6** | Examples + integration tests + OSS prep | 🔲 |

---

## 10. Dependencies

```
click       — CLI framework
rich        — beautiful terminal output
httpx       — HTTP client for Provider
pyyaml      — YAML frontmatter parsing
```

Optional: `pytest`, `pytest-asyncio`, `ruff`, `mypy` (dev)

No dependency on: DSPy, GEPA, TensorFlow, PyTorch, CUDA.

---

## 11. Open Questions

1. **Should the reflector be allowed to restructure sections?** (Currently: preserve layout, fix content only)
2. **How do we verify that an optimized artifact is actually *better*?** Run the eval command against the new version too — the loop handles this.
3. **Session DB: read directly or use an API?** Direct SQLite read is simpler and avoids Hermes dependency. The schema may change — we pin the query.
4. **SOUL.md: do we optimize the whole file or per-section?** Per-section for safety (armored sections immutable). Bull-heavy artifact could be overwhelming for one reflection call anyway.