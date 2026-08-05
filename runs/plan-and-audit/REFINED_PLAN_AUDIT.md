---
name: plan-and-audit
description: "Multi-mode workflow engine for systematic implementation with escalating rigor: low/medium/high. Enforces research-first, spec+plan, forward+reverse audits, synthesis, sign-off, TDD, and CI/CD integration."
version: "2.1.0"
author: Lucien
license: MIT
platforms: [linux, macos, windows]
triggers:
  - "create implementation plan"
  - "audit code"
  - "forward audit"
  - "reverse audit"
  - "plan and audit"
  - "systematic implementation"
  - "escalating rigor"
metadata:
  hermes:
    tags: [planning, audit, workflow, implementation, quality, tdd, security]
    related_skills: [writing-plans, subagent-driven-development, requesting-code-review, test-driven-development, security-hardening-sprint, kanban-review-workflow, mcp-tool-discovery]
---

# plan-and-audit — Multi-Mode Workflow Engine

## Overview

A structured workflow engine that enforces systematic implementation across three modes of escalating rigor. Every mode begins with mandatory research, proceeds through spec+plan with audit cycles, and ends with signed-off execution and documentation.

**Core principle:** Never build without a verified plan. Never claim done without verified evidence.

## When to Use

- Implementing features touching 3+ files
- Security hardening sprints
- Architecture refactoring
- Any work requiring audit trail and verification

**Do NOT use for:** throwaway spikes, config tweaks, documentation-only changes

## Mode Architecture

| Phase | Low | Medium | High |
|-------|-----|--------|------|
| **0. Research** | ✅ All KGs (skills, TokRepo, Context7, GitHub MCP, web) | ✅ Same | ✅ Same |
| **1. Spec** | ✅ Interface contracts + impact analysis | ✅ Same | ✅ Same |
| **2. Plan** | ✅ Roadmap + task breakdown + dependencies | ✅ Same | ✅ Same |
| **3. Forward Audit** | ✅ Validates spec→implementation | ✅ Same | ✅ Same |
| **4. Reverse Audit** | ✅ Reviews for gaps/issues | ✅ Same | ✅ Same |
| **5. Synthesis** | ✅ Combine audits into final plan | ✅ Same | ✅ Same |
| **6. Sign-off** | ✅ User approval before execution | ✅ Same | ✅ Same |
| **7. TDD Implement** | ❌ | ✅ Full red-green-refactor | ✅ Same |
| **8. Adversarial Audit** | ❌ | ✅ Security + edge cases | ✅ Same |
| **9. Bug Review** | ❌ | ✅ Logic, security, code quality | ✅ Same |
| **10. Lint + Dead Code** | ❌ | ✅ Syntax, lint, dead code detection | ✅ Same |
| **11. Test/Perf/Sec Docs** | ❌ | ✅ Coverage metrics, perf, risk assessment | ✅ Same |
| **12. CI/CD Integration** | ❌ | ❌ | ✅ Pipeline integration + repo validation |

## Operational Requirements

1. **Mode Selection**: Prompt for mode (low/medium/high) before processing
   - **MEDIUM** (default for new capabilities): 5+ files, database/caching/MCP, reusable feature
   - **HIGH**: Security-critical, public API, multi-phase sprint (20+ files), compliance requirements
   - **LOW**: Internal refactoring, 2-3 files, well-understood pattern, speed > rigor

2. **Momentum Priority**: When user says "lets get to work", "great work! whats next?", or shows momentum — push through quick wins immediately. Don't offer to stop after every small win. User prefers **continuous execution over cautious pausing**. (2026-06-28 NexusAgent session: user rejected offer to "call it a session" after config check, wanted to keep working)

3. **Mandatory Research**: All required research completed before any skill creation. If user provides a URL or external reference, read it immediately — do not assume you already have the information. (2026-07-28 session: user expected agent to have info from URL, but agent stopped instead of reading it.)

4. **Documentation Standards**: All outputs saved to `/docs/` with descriptive filenames

5. **Review Process**: Plans must undergo specified audit cycles per mode

6. **Parallel Audits**: Forward + reverse audits can (and should) run in parallel via `delegate_task` — they're independent

7. **Medium Mode Parallel Phase Execution**: For medium-mode multi-phase sprints, independent phases can be dispatched simultaneously via `delegate_task(tasks=[...])`. Example: Phase 3 (multi-language support) + Phase 4 (watcher daemon) both dispatched in parallel while Phase 5 (LSP bridge) built inline. Both completed successfully. Requires: phases touch completely different file sets, no shared dependencies.

### ⚠️ CRITICAL: Complete ALL Required Phases Before Declaring Done

**2026-07-30 NexusAgent session — user caught incomplete audit:**

The mode architecture table lists phases per mode. MEDIUM requires phases 3-11 (forward audit, reverse audit, adversarial audit, bug review, lint, test/perf/sec). **Do NOT stop after only doing bug review + lint + test/perf and declare "audit complete."** That's only 3 of 6 required audit phases.

**Checklist before declaring audit complete:**
- [ ] Forward audit (validate claims against code)
- [ ] Reverse audit (find what was missed)
- [ ] Adversarial audit (security + edge cases)
- [ ] Bug review (logic, security, code quality)
- [ ] Lint + dead code detection
- [ ] Test/perf/sec documentation

**User will ask "did you do all 6?" if you skip phases. Don't make them ask.**

**Mandatory output before declaring done:** Explicitly list each completed phase. Example: "All required phases complete: Forward audit ✅, Reverse audit ✅, Adversarial audit ✅, Bug review ✅, Lint ✅, Test/perf/sec docs ✅." If any phase is missing, do not claim completion.

### ⚠️ CRITICAL: Ignore Documentation When User Says So

**2026-07-30 NexusAgent session — user repeatedly corrected:**

When the user says "ignore the documentation" or "the docs are old/stale":
- **DO NOT read AGENTS.md, CODEBASE_MAP.md, SEMANTIC_INDEX.md, or any docs/ files for audit purposes**
- **DO NOT trust bug lists, feature descriptions, or architecture docs**
- **Audit ONLY the source code under src/ and tests/**
- **Verify everything against actual code, not documentation**

The Hermes context window auto-injects AGENTS.md. You must actively ignore it when the user has flagged docs as stale. The code is the only truth during a fresh audit.

### ⚠️ CRITICAL: Don't Run Full Test Suite on Constrained Hardware

**2026-07-30 NexusAgent session:**

Workstation has 4GB RAM, i3 CPU. Full `pytest tests/` takes 4+ minutes and can hang. **Always run targeted tests:**
```bash
# Targeted — fast
PYTHONPATH=src:. python3 -m pytest tests/test_session.py -q --tb=short

# Full suite only when explicitly asked (takes 4+ min)
PYTHONPATH=src:. python3 -m pytest tests/ -q --tb=line --no-header
```

### ⚠️ CRITICAL: Workflow Adherence — Stay on Task

**2026-08-05 session — agent deviated to unrelated document analysis; 2026-08-03 session — agent modified other artifacts instead of following workflow.**

When triggered by a plan-and-audit trigger (e.g., "create implementation plan", "audit code"), you MUST follow the full workflow for the selected mode. **Do NOT switch to unrelated tasks** (e.g., analyzing documents, modifying other skills, editing SOUL.md, or generating anti-pattern lists) unless the user explicitly redirects you.

**If the user gives instructions that seem to deviate from the workflow:**
- Pause and clarify: "I'm currently in plan-and-audit mode for [task]. Do you want me to continue with that, or switch to a new task?"
- Do not assume the user wants to abandon the current workflow.

**Do NOT modify files outside the scope of the current task** (e.g., other skills, SOUL.md, reference files) unless explicitly instructed. The plan-and-audit workflow operates on the target codebase, not on the agent's own configuration.

## Worked Example

See `references/worked-example-semantic-database.md` for a complete end-to-end example:
- Research dispatch (7 min subagent)
- Spec + Plan structure (13 min)
- Parallel audit dispatch (forward + reverse simultaneously)
- Synthesis + sign-off workflow
- Mode selection rationale (why MEDIUM)

## Reference Files

- `references/step-templates.md` — Research, Spec, Plan templates
- `references/audit-templates.md` — Forward, Reverse, Adversarial, Birdseye, Compliance, Competitor audit templates
- `references/execution-templates.md` — Synthesis, Implementation, Review, Documentation, Kanban, CI/CD templates
- `references/medium-mode-parallel-phases.md` — Parallel phase execution pattern for medium-mode sprints
- `references/context-injection-patterns.md` — Multi-factor relevance scoring, token budget management, Hermes hook integration (Phase 8 ast-tools)
- `references/path-traversal-mcp-tools.md` — Path traversal vulnerability pattern in MCP tools accepting file_path params (discovered 2026-06-28)
- `references/incremental-indexing-pattern.md` — Symbol-level diff engine, database ops, FK cascade, pitfalls (2026-06-30)
- `references/path-traversal-mcp-tools.md` — Path traversal vulnerability pattern in MCP tools accepting file_path params (discovered 2026-06-28)
- `references/code-only-audit-pattern.md` — Code-only audit checklist for when docs are stale (2026-07-30)

## Further Reading

When orchestrating complex sprints or needing specific disciplines, load these references:
- `references/verify-before-plan.md` (in `writing-plans`) — Case study: 40% plan inflation from unverified claims
- `references/multi-audit-dispatch.md` (in `subagent-driven-development`) — 6-audit parallel dispatch pattern
- `references/security-fix-patterns.md` (in `security-hardening-sprint`) — Wave-based remediation patterns
- `references/ruff-violation-patterns.md` (in `requesting-code-review`) — Common lint violations and fixes
- `references/parallel-security-sprint.md` (in `security-hardening-sprint`) — Parallel execution protocol
- `references/local-transformer-embedding-integration.md` — Local embedding integration pattern (CPU-only, sqlite-vec, RRF)
- `.github/agents/code_review_agent.agent.md` — Specialized audit agent definition
- `.github/agents/security_specialist.agent.md` — Security-focused agent definition

## Execution Mode: Inline vs Subagent Dispatch

**Updated 2026-06-28 based on NexusAgent HIGH mode audit execution:**

### When to Execute Inline (NOT subagent)

**Rule of thumb (2026-06-28 NexusAgent session):**
- Projects with **>30 files in src/**: Inline execution for ALL audits
- Security wave remediation: Inline for context-heavy fixes
- Server dispatch via worktree: Inline fallback when `hermes` CLI not in SSH PATH
- Worktree operations: Use inline when collect fails due to path mismatches (`.hermes/worktrees/` not `.nexusagent/worktrees/`)

**What happened:**
- HIGH mode audit: 11 steps, 125 Python files in src/
- Adversarial + bug review subagents timed out at 900s after ~20 API calls
- Narrow-scope retries completed in ~3 min
- Inline lint audit completed successfully
- **Lesson:** For >30 file projects, inline execution is faster and more reliable

**Inline execution benefits:**
1. Full context retention (no token budget limits)
2. No timeout risk
3. Cascading fixes: Fix one file, immediately propagate to imports
4. Real-timeruff check --fix` after each wave
5. No SSH PATH/worktree complications

### Wave-Based Inline Execution (MODIFIED GO Pattern)

When executing waves inline:
1. **Wave 0:** `ruff check --fix && ruff format` first (auto-fixes reduce noise)
2. **Waves 1-N:** Implement fixes file-by-file, run `ruff check` after each
3. **Commit each wave** for rollback safety
4. **Test baseline:** Record pass/fail count BEFORE starting
5. **Verify after each wave:** No new failures allowed

```bash
# Post-wave verification
ruff check src/ --fix && ruff format src/
git add -A && git commit -m "fix: Wave N <description>"
PYTHONPATH=src pytest tests/ -x -q --tb=short | tail -5
```

### Parallel Phase Execution (Still Valid for Independent Work)

**When parallel subagent dispatch still makes sense:**
- Research phase (focused queries, completes in ~7 min)
- Lint audits (ruff is fast, isolated)
- Independent phases (no shared files, no dependencies)

See `references/medium-mode-parallel-phases.md` for the successful Phases 3+4 parallel dispatch pattern.

---

## Subagent Audit Output Reliability (2026-06-30)

**Problem:** Dispatched 5 parallel audits via `delegate_task` for incremental indexing spec. All 5 subagents completed, but **none wrote results to disk**. Results were returned in messages that compaction fired.

**Root cause:** Subagent `goal` descriptions focused on producing output but did not include explicit file-write instructions. The subagent summarized in its response instead.

**Mitigation:**
1. **For narrow/focused audits**: Run inline and write results to `docs/specs/audits/` immediately
2. **If dispatching as subagent**: Include explicit save instruction in goal:
   ```
   "Write findings to docs/specs/audits/adversarial-audit-<feature>.md using write_file tool. Do NOT just summarize in your response."
   ```
3. **Verify file exists**: After dispatch, check `docs/specs/audits/` for output files before proceeding to synthesis
4. **Inline fallback**: For critical audits (adversarial, bug review), inline execution with `read_file` + analysis + `write_file` is more reliable

**Revised rule of thumb:**
| Audit Type | Subagent | Inline |
|------------|----------|--------|
| Forward (>30 files) | ❌ Unreliable | ✅ Must inline |
| Reverse (>30 files) | ❌ Unreliable | ✅ Must inline |
| Adversarial | ⚠️ Risky (use narrow scope + explicit save) | ✅ Preferred |
| Bug Review | ⚠️ Risky (use narrow scope + explicit save) | ✅ Preferred |
| Lint | ✅ Subagent OK | ✅ Either |
| Research | ✅ Subagent OK | ✅ Either |

---

## Database Commit Pattern (2026-06-30)

**Context:** When writing tests or tools that use `database_context`, remember it does NOT auto-commit.

```python
# Pattern for tests that need persistence across connections
with database_context(db_path) as conn:
    init_schema(conn)
    insert_symbols_batch(conn, symbols)
    conn.commit()  # REQUIRED for data to persist
    
# Now a new connection can see the data
with database_context(db_path) as conn:
    stored = get_symbols_by_file(conn, "src/module.py")
    assert len(stored) > 0
```

This applies to ALL database operations: insert, update, delete. Always call `conn.commit()` before the context manager exits.

---

## FK Cascade Requirement (2026-06-30)

**CRITICAL:** When implementing features that delete records from tables with relationships, you MUST add `FOREIGN KEY ... ON DELETE CASCADE` to the schema — otherwise orphaned records accumulate and corrupt queries.

```sql
-- REQUIRED for any table referencing symbols(id)
CREATE TABLE edges (
    ...
    FOREIGN KEY (source_id) REFERENCES symbols(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES symbols(id) ON DELETE CASCADE
);
```

And ensure `PRAGMA foreign_keys = ON` is set in the connection (already done in `configure_connection`).

Full pattern reference: `references/incremental-indexing-pattern.md`

---

## HIGH Mode Audit Timeout Mitigation (2026-06-28 NexusAgent Session)

**Context:** 11-step HIGH mode audit on NexusAgent (125 Python files in src/)

**What happened:** 
- Steps 7-9 (adversarial, bug review, lint) dispatched as parallel subagents
- Broad-scope audits timed out at 900s (15 min) after ~20 API calls
- Narrow-scope retries completed in ~3 min

**Solution applied:**
1. **Forward/Reverse audits: Inline for >30 file projects** — not worth timeout risk
2. **Adversarial/Bug Review: Narrow scope + retry** — dispatch with specific file lists, 3 min timeout
3. **Lint audit: Subagent worked** — ruff check is fast and isolated

**Rule of thumb for future HIGH mode audits:**
| Project Size | Forward/Reverse | Adversarial/Bug Review | Lint |
|--------------|----------------|------------------------|------|
| <10 files | Subagent OK | Subagent OK | Subagent OK |
| 10-30 files | Inline preferred | Narrow subagent OK | Subagent OK |
| >30 files | **Must inline** | Narrow subagent (3 min max) | Subagent OK |

**Session outcome:** Completed 11/11 HIGH mode steps in ~2 hours total (vs estimated 14-16h with proper parallel execution).

---

## Context Injection Pattern (Phase 8 Learnings)

**Session:** 2026-07-24 — Phase 8 Context Injection Hooks for ast-tools

**Key Design Patterns:**

### Multi-Factor Relevance Scoring
```
score = (
    semantic_similarity * 0.40 +    # Cosine distance (embedding)
    recency_score * 0.15 +          # exp(-days / 30)
    usage_frequency * 0.15 +        # log(1 + refs) / log(1 + max_refs)
    kind_boost * 0.10 +             # class/function=1.0, method=0.7, var=0.4
    file_proximity * 0.10 +         # same=1.0, imported=0.5, unrelated=0.0
    callgraph_depth * 0.10          # direct=1.0, 2-hop=0.5, none=0.0
)
```

### Token Budget Management
- **8K models:** 5 symbols (~1.5K tokens)
- **32K models:** 10 symbols (~3K tokens)
- **128K+ models:** 20 symbols (~6K tokens)
- **Diversity limit:** Max 3 symbols per file
- **Token estimation:** Use `tiktoken` with caching (don't recompute)

### Staleness Prevention
- **Temporal decay:** 10% per day after 7 days
- **Repetition decay:** 20% reduction if injected 3+ times in session
- **Diversity forcing:** Hard cap enforcement during selection

### Fallback Behavior
- If sqlite-vec unavailable → degrade to FTS5-only search
- If embeddings missing → use keyword + recency + usage scoring
- Never fail loud; graceful degradation always

### Hermes Hook Integration
- **Event:** `pre_tool_call` on `semantic_search`
- **Script:** Must use `set -euo pipefail`, NO logging to stdout, NO temp files
- **Permissions:** `chmod 700`
- **Allowlist:** Required in `~/.hermes/shell-hooks-allowlist.json`

**Security Checklist for Hook Scripts:**
- [ ] No logging to stdout (stderr for errors only)
- [ ] No temp files written
- [ ] Strict mode: `set -euo pipefail`
- [ ] Restrictive permissions (700)
- [ ] Input sanitization on all user-provided data
- [ ] Graceful failure (exit 0, don't break Hermes flow)

**Reference:** `references/context-injection-patterns.md` (this session)

---

## HIGH Mode Implementation Checklist

When running in HIGH mode (security-critical, public API, 20+ files):

- [ ] Spec written with interface contracts + impact analysis
- [ ] Forward audit complete (inline for complex features)
- [ ] Reverse audit complete (can be subagent)
- [ ] Synthesis document with implementation plan
- [ ] **User sign-off obtained before coding**
- [ ] TDD: Tests written FIRST
- [ ] Adversarial audit (security + edge cases)
- [ ] Lint + dead code check
- [ ] Documentation updated
- [ ] Manual validation on target environment
- [ ] Rollback plan documented

**Sign-off required:** User must explicitly approve before TDD implementation begins.

**Critical (2026-06-28 Discovery):** Always verify CODE against actual `git log` and read source files BEFORE trusting old plans or audit documents. Refactoring plans get outdated as code evolves faster than documentation. (NexusAgent session: "remaining" Phases 8-14 were already done in Waves 1-5, just not documented)

---

## MEDIUM Mode Security Hardening Sprint — Worked Example (2026-06-29)

**Context:** 6 security tasks (SEC-01 through SEC-06) across ast-tools codebase (95 Python files, 35+ tools).

### Phase 0: Research (Complete)
- Loaded competitive analysis (COMPETITIVE_FEATURE_PARITY_20260628.md)
- Audited existing codebase for security gaps
- Identified 6 critical security issues (8 total across all audits)

### Phase 1: Spec (EASY_WINS_SPEC_20260628.md)
- Documented 6 security tasks with effort estimates
- Defined acceptance criteria per task

### Phase 2: Plan (EASY_WINS_PLAN_v1.md)
- File manifest with line counts
- TDD test plans
- Rollback plan per phase

### Phase 3-4: Forward + Reverse Audits (Parallel Dispatch)
- Forward audit: Validated feasibility against actual codebase
- Reverse audit: Found 15 gaps (2 critical: path traversal, false positives)
- Adversarial audit: 18 security vulns (3 critical: SQL injection, path traversal, recursion)
- Bug review: 14 code quality issues (3 critical: connection leaks, silent failures, races)
- Lint audit: 7 minor errors (baseline)

### Phase 5-6: Synthesis + Sign-off
- Combined all audits into EASY_WINS_SYNTHESIS_v2.md
- User approved revised 69h plan (was 25h, +176% for security)

### Phase 7-11: TDD Implementation (15h total)
**SEC-01: FTS5 SQL Injection (2h)**
- Added `sanitize_fts5_query()` to queries.py
- Removes boolean operators, escapes special chars, limits 500 chars
- Applied to `search_symbols()` FTS5 call

**SEC-02: Path Traversal (3h)**
- Created `validate_project_path()` in security.py
- Blocks `..`, symlinks escaping root, paths outside allowlist
- Includes temp dirs for testing
- 29 security tests pass

**SEC-03: Recursion Limits (2h)**
- Added `max_depth=50`, `max_files=100` to `_walk_calls()`
- Applied to references/callers analysis

**SEC-04: Consistent Path Validation (4h)**
- Centralized `validate_file_path()` in file_utils.py
- Applied to `ast_read`, `ast_edit` (replaced inline validation)
- Proper error codes: NOT_FOUND, PATH_TRAVERSAL, INVALID_PATH

**SEC-05: Error Sanitization (2h)**
- Added `sanitize_error_message()` to queries.py
- Generic user messages, detailed sanitized logs

**SEC-06: Input Limits/DoS (2h)**
- `validate_limit(max=1000)`, `validate_timeout(max=300s)`
- Query length capped at 500 chars

**Result:** All 402 tests pass. Phase 0 complete (15h).

### Key Patterns Learned

1. **Kanban board per phase** — Track security tasks with DONE/IN_PROGRESS/TODO
2. **Parallel audits work** — Forward + reverse dispatched simultaneously
3. **TDD mandatory** — Tests written first, then implementation
4. **Centralized utilities** — Security functions in shared modules (security.py, file_utils.py)
4. **Error code standardization** — NOT_FOUND, PATH_TRAVERSAL, INVALID_PATH consistently
5. **All 402 tests must pass** after each security task

### Kanban Template for Security Sprints

```markdown
| Task ID | Title | Effort | Priority | Status |
|---------|-------|--------|----------|--------|
| SEC-01  | SQL Injection Fix | 2h | 🔴 P0 | ✅ DONE |
| SEC-02  | Path Traversal | 3h | 🔴 P0 | ✅ DONE |
| SEC-03  | Recursion Limits | 2h | 🔴 P0 | ✅ DONE |
| SEC-04  | Consistent Path Validation | 4h | 🟠 P1 | ✅ DONE |
| SEC-05  | Error Sanitization | 2h | 🟠 P1 | ✅ DONE |
| SEC-06  | Input Limits/DoS | 2h | 🟠 P1 | ✅ DONE |
```