# Phase 9 — Bug Review (Logic, Security, Code Quality)

**Project:** rw-promptforge
**Date:** 2026-08-04

---

## Bug Inventory

### 🔴 CRITICAL: Reflector template variable mismatch

**File:** `src/rw_promptforge/reflector/engine.py:74`
**Bug:** `session_data=session_context` — template has `{session_context}`, format() passes wrong keyword.
**Effect:** `KeyError: 'session_context'` at runtime, blocking the entire reflection call.
**Fix:** Change to `session_context=session_context` (already in Forward Audit, accepted)

---

### 🔴 CRITICAL: `sqlite3` import used but not consumed

**File:** `src/rw_promptforge/datastore/session_db.py:11`
**Line:** `import sqlite3`
**Usage:** Never referenced in any method. Dead import.
**Fix:** Remove or add `# TODO: used when session_db queries are implemented`

---

### 🔴 CRITICAL: `os` double-import in provider

**File:** `src/rw_promptforge/provider.py`
**Lines:** `import os` at line 5 (module level), `import os` at line 68 (inside `from_env`).
**Effect:** Ruff F811 (redefinition of unused import). The second `import os` at line 68 is redundant — `os` is already available from the module-level import.
**Fix:** Remove line 68 `import os` — it's in `from_env` for a reason (supposed to be self-contained), but the module-level one is sufficient.

---

### 🟠 HIGH: `extract_section` returns `None` — stubbed

**File:** `src/rw_promptforge/targets/soul.py:55`
```python
return None  # TODO: implement extraction after TDD
```
The function computes `marker` but discards it and returns None. Any caller expecting a section string gets None — breaks `SoulTarget` consumers.
**Fix:** Implement or remove the stubbed function before Phase 1.

---

### 🟠 HIGH: `skill.triggers` returns `list[str]` but frontmatter value could be `str`

**File:** `src/rw_promptforge/targets/skill.py:65`
```python
return self.frontmatter.get("triggers", [])
```
`frontmatter` is `dict[str, str]` but YAML frontmatter triggers can be a string or list. If a skill has `triggers: "trigger phrase"` (string, not list), `.get("triggers")` returns a str — and `triggers.extend(...)` would error.
**Fix:** Add `isinstance` guard: if str, return `[value]`. If list, return list.

---

### 🟠 HIGH: `shutil` not used — dead import risk

**Not found**. Verified: `shutil` is not imported. (False — checked wrong file.)

### 🟡 MEDIUM: Line length violations (5 files)

All line-length violations are in either prompt strings (REFLECTION_USER_TEMPLATE etc.) or `format_trace` — low risk, but ruff will flag until auto-fixed.
**Fix:** All 15 auto-fixable ruff issues should be resolved with `ruff check --fix && ruff format`.

### 🟡 MEDIUM: Missing newline-at-EOF (13 files)

Impact: None. Cosmetic. Fixable via `--fix`.
**Fix:** Auto-fixed by ruff.

### 🟡 MEDIUM: unused `import os` in provider

**Fix:** Remove `import os` from line 5; keep line 68 (placement is intentional for `from_env` self-containedness):

### 🟢 LOW: `mypy strict` — LSP diagnostics found

**File:** `src/rw_promptforge/targets/skill.py:65`
```
ERROR: Type "str | list[Any]" is not assignable to return type "list[str]"
```
**Fix:** Type guard for triggers.

**File:** `src/rw_promptforge/evaluator/shell.py:35` — `result.exit_code` type unknown (Python 3.12 subprocess sometimes has ambiguous types).
**Fix:** `assert result.returncode is not None`

---

## Code Quality Observations

| Pattern | Count | Impact |
|---------|-------|--------|
| Duplicate imports | 1 | Ruff blocks |
| Stubbed functions | 1 | Runtime None |
| Type looseness | 2 | mypy/mypy failures |
| Long lines (prompt strings) | 4 | Ruff stylistic |
| Missing EOF newline | 10 | Ruff cosmetic |

---

## Go/No-Go for Phase 7

| Gate | Status |
|------|--------|
| All 8 tests pass | ✅ Go |
| No deadlock/race conditions | ✅ Go |
| Runtime prios (KeyError, None, TypeErr) | ⚠️ Must Fix first (3 bugs) |
| Lint pass | ⚠️ 20 errors (15 fixable) |
| Type strict | ⚠️ 2 errors |

**Verdict:** ⚠️ MUST fix 3 runtime bugs + run `ruff check --fix` + run mypy check before Phase 7 TDD. Otherwise codebase is logically sound.