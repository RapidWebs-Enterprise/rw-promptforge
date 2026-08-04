# Phase 1 — Interface Contracts + Impact Analysis

**Project:** rw-promptforge
**Date:** 2026-08-04
**Mode:** MEDIUM

---

## 1. Interface Contracts

### 1.1 Provider

```
Contract: Provider refines ─ (endpoint URL, model name) → text response
  Input:  reflect(prompt: str, system: str | None) 
  Output: str (LLM response, plain text)
  Side effects: None (pure HTTP → text)
  Error handling: httpx.HTTPError raised (caller handles), .close() for cleanup
```

### 1.2 ShellEvaluator

```
Contract: Shell evaluator evaluates ─ (command_template, artifact path) → EvalResult
  Input:  evaluate(artifact_path: str) → EvalResult
  Output: EvalResult { exit_code, stdout, stderr, command, elapsed, passed, failed, timed_out }
  Side effects: Executes shell command (subprocess)
  Error handling: subprocess.TimeoutExpired → EvalResult(ex=-1, timed_out=true)
```

### 1.3 Reflector

```
Contract: Reflector reflects ─ (artifact text, trace text, history, session context) → improved artifact text
  Input:  reflect(artifact: str, trace: str, session_context: str = "(none)", history: str = "(none)") → str
  Output: text (the LLM's improved version of the artifact)
  Side effects: ONE LLM call
  Error handling: Provider.reflect() errors bubble up
```

### 1.4 Targets

```
Contract: SkillTarget ─ (path to SKILL.md) → parsed frontmatter + body text
  Input:  SkillTarget(path)
  Output: .content, .frontmatter, .body, .name, .triggers
  Side effects: None (read-only)

Contract: SoulTarget ─ (path to SOUL.md) → extracted sections
  Input:  SoulTarget(path)
  Output: .content, ARMORED_SECTIONS set, OPTIMIZABLE_SECTIONS set
  Side effects: None (read-only)
```

### 1.5 SessionDBReader

```
Contract: SessionDBReader identifies ─ (db_path) → sqlite3 queries
  Input:  SessionDBReader(db_path=None)
  Output: .exists(), .find_sessions_with_skill(name, limit) → [SessionMatch]
  Side effects: None (read-only, separate SQLite connection)
  Error handling: Missing DB → exists()=False → empty lists
```

### 1.6 CLI

```
Contract: optimize command ─ (path, target_type, provider, endpoint, model, max_rounds, eval_command, save) → exit 0/1
  Input: CLI flags + positional args
  Output: terminal output (Rich-console), optional file write (if --save)
  Side effects: May shell out (eval_command), LLM calls (Provider), file write (temp files, output)
```

---

## 2. Impact Analysis — What Phase 1 Changes

### 2.1 optimizer.py (TO BE CREATED)

New file: `src/rw_promptforge/optimizer.py`

Impact: None on existing code — new module. Will import from:
- `rw_promptforge.provider.Provider`
- `rw_promptforge.evaluator.shell.ShellEvaluator`
- `rw_promptforge.reflector.engine.Reflector`
- `rw_promptforge.targets.skill.SkillTarget` (phase 2+)
- `rw_promptforge.targets.soul.SoulTarget` (phase 4+)

### 2.2 cli.py — WIRING CHANGE

Current: Optimizer prints "[yellow]Core loop not yet implemented[/]" and ends.
After: Calls `optimizer.Optimizer(...)` with parsed CLI flags. No other files changed.

### 2.3 provider.py — NO CHANGE

Provider is complete and tested. Works for anything we need.

### 2.4 reflector/engine.py — NO CHANGE

Reflector prompt system is already correct. Might refine token budget later.

### 2.5 evaluator/shell.py — NO CHANGE

ShellEvaluator is ready. Works for any command.

## 3. File Manifest

| File | Action | LOC (est) |
|------|--------|-----------|
| `src/rw_promptforge/optimizer.py` | **CREATE** | ~150 |
| `src/rw_promptforge/cli.py` | MODIFY | +5/-5 |
| `tests/test_optimizer.py` | **CREATE** | ~200 |
| `tests/test_bootstrap.py` | NO CHANGE | — |

## 4. Dependency Graph

```
optimizer.py
├── provider.Provider (reflect LLM)
├── evaluator.shell.ShellEvaluator (run eval_command)
├── reflector.engine.Reflector (construct + make reflection call)
├── targets.skill.SkillTarget (read + parse SKILL.md)
└── targets.soul.SoulTarget (read + extract SOUL sections)

cli.py
└── optimizer.optimize() (wire CLI → loop)
```