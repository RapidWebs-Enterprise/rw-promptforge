# Phase 4 — Reverse Audit

**Project:** rw-promptforge  
**Date:** 2026-08-04

## Methodology

Systematically searched for everything the SPEC + PLAN + ADRs MISSED.
Read all source files, scanned for: dead code, missing tests, security gaps,
incomplete interfaces, missing documentation, and hidden edge cases.

---

## Findings

### 🔴 CRITICAL: No temp file management

The optimizer loop needs to write the current artifact to a temporary file
before calling `ShellEvaluator.evaluate()`. Nowhere in the plan or existing
code is there:

- A function to write the artifact to a temp file
- Any tempfile cleanup logic
- Any guard against the temp file being leaked

**Missed in plan**: Needs `tempfile.NamedTemporaryFile` or similar. Add to Task 2
(optimizer core loop) or create `evaluator/tempfile.py` with `with temp_artifact(text):` context manager.

### 🔴 HIGH: No `eval_command` validation

The CLI accepts `--eval-command` optional but the optimizer needs it.
If user passes `None` they'll get `subprocess.run(None, shell=True)` which
either crashes or is a security issue.

**Missed in plan**: Add `if not eval_command: raise click.UsageError(...)`.

### 🟠 HIGH: Provider `close()` is handled, but `__del__` not guaranteed

If the HTTPX client is created and an exception occurs before `close()`,
the transport won't be cleaned up. Not critical for CLI that exits quickly,
but correct pattern would be `__enter__`/`__exit__` or `atexit`.

**Severity**: Low priority for this codebase (CLI, runs once).

### 🟠 MEDIUM: Error messages not sanitized

`EvalResult.stderr` is passed directly to the reflection LLM. If the eval
command outputs sensitive information (API keys, tokens, paths), they
go to whichever LLM provider you're using for reflection.

**Mitigation**: Document that `--eval-command` output is visible to the LLM.
Should add `validate_command` or a `--scrub-eval-output` flag for security.

### 🟡 MEDIUM: No progress reporting

The optimizer loop currently prints nothing to console while running.
User might think the tool is frozen during the 2-120 second LLM calls.

**Add to plan**: Rich progress indicator per round.

### 🟡 MEDIUM: Provider tests use internet

`test_provider_import` and `test_provider_from_env` don't make HTTP calls,
but if someone tests Provider.reflect() it makes real API calls.

**Add to plan**: Mark tests as needing `stub_reflector` or provide `--mock-provider`
in tests to avoid accidental API calls.

### 🟡 LOW: Module-level unused import in provider.py

Change line 5 `import os` (can be dropped in `from_env` only).

### 🟢 INFO: 4 files missing standard `__all__` exports

Not required for CLI code, but good practice. Low priority.

### 🟢 INFO: No type-stub testing

Mypy `--strict` is configured but never actually run. Add `make typecheck` to build.

### 🟢 INFO: Makefile references `make check` but `uv run mypy src/rw_promptforge` may fail

Not yet verified — will validate in Phase 10 (lint).

---

## Missing from Spec

| Missing Item | Severity | 
|-------------|----------|
| Tempfile management (write + cleanup) | 🔴 Critical |
| `--eval-command` required validation | 🔴 Critical |
| CLI arg for `--api-key` env override (currently only reads from ENV) | 🟠 High |
| Provider close lifecycle (context manager) | 🟠 Low |
| Test stubs for reflection reflector | 🟡 Medium |
| Progress indicators in optimizer loop | 🟡 Medium |
| Security: eval output sanitization before sending to LLM | 🟡 Medium |

---

## Checklist

- [x] Missing files found
- [x] Incomplete interface checked
- [x] Test gaps identified
- [x] Security surface audited
- [x] Dead code found (import os duplicate)
- [x] Missing infrastructure (temp files)

**Verdict**: ⚠️ Plan has 2 critical gaps. Continue to Phase 5 synthesis with fixes.