# Phase 10 — Lint + Dead Code Detection

**Project:** rw-promptforge
**Date:** 2026-08-04

---

## Ruff Output

```
20 errors found (15 auto-fixable)
```

### Breakdown

| Code | Count | Description | Severity |
|------|-------|-------------|----------|
| W292 | 13 | No newline at end of file | 🟢 Cosmetic (auto-fix) |
| E501 | 4 | Line too long (>100 chars) | 🟡 Stylistic |
| F401 | 2 | Unused import | 🔴 Functional |
| F811 | 1 | Redefinition of unused import | 🔴 Functional |

### Per-file:

| File | Issues |
|------|--------|
| `provider.py` | F401 (os unused), F811 (os redefined), W292 |
| `session_db.py` | F401 (sqlite3 unused), E501 (line too long), W292 |
| `reflector/engine.py` | E501×2, W292 |
| `evaluator/shell.py` | E501, W292 |
| `cli.py` | E501, W292 |
| `targets/soul.py` | W292 |
| `targets/skill.py` | W292 |
| `datastore/__init__.py` | W292 |
| `evaluator/__init__.py` | W292 |
| `reflector/__init__.py` | W292 |
| `targets/__init__.py` | W292 |

---

## Dead Code Scan

### Unused imports:

| Line | File | Import | Status |
|------|------|--------|--------|
| 5 | `provider.py` | `import os` | Unused (function-level reimports) |
| 11 | `session_db.py` | `import sqlite3` | Unused (no queries yet) |

### Unused functions (visual scan):

| Function | Status |
|----------|--------|
| `SoulTarget.extract_section()` | Stubbed (returns None) → dead |
| `SessionDBReader.find_sessions_with_skill()` | Stubbed (returns []) → pending |
| `SessionDBReader.find_corrections_after_skill_use()` | Stubbed (returns []) → pending |

### Files with zero references:
- None. All modules are import-linked from tests or stubs.

---

## Fix Command

```bash
uv run ruff check src/ tests/ --fix && uv run ruff format src/ tests/
```

**Auto-fix resolves:** 15/20 issues (all W292 + unused-import reorg)
**Manual fixes:** 5 issues (E501 line lengths — split prompt strings)

---

## Verdict

Lint is 20% actionable (4 functional), 75% cosmetic (auto-fixable), and 5% stub-related (the 3 stubbed functions will be implemented in Phase 7, removing some unused imports).

**Pre-Phase 7 fix**: ruff --fix + ruff format → clean build expected.