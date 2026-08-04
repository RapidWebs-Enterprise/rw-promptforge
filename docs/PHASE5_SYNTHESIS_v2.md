# Phase 5 — Synthesis v2 (ALL Audits Integrated)

**Project:** rw-promptforge
**Date:** 2026-08-04
**Sources:** Forward (P3) + Reverse (P4) + Adversarial (P8) + Bug Review (P9) + Lint (P10) + Test/Perf/Sec (P11)

---

## Consolidated Findings — All 6 Audits

### 🔴 Critical (5 — MUST fix before Phase 7)

| # | Finding | Source | Fix |
|---|---------|--------|-----|
| C1 | `session_data` → `session_context` template KeyError | P3 | Rename in reflect() line 74 |
| C2 | Shell injection via unescaped `{path}` in evaluator | P8 | `shlex.quote(artifact_path)` before substitution |
| C3 | API keys leaked to reflection LLM via eval traces | P8 | Add `--sanitize` flag + scrub KEY/TOKEN/Bearer patterns |
| C4 | `SoulTarget.extract_section()` stubbed returns None | P9 | Implement or remove |
| C5 | `SkillTarget.triggers` may return str, not list — type mismatch | P9 | isinstance guard: if str → [value] |

### 🟠 High (3)

| # | Finding | Fix |
|---|---------|-----|
| H1 | No tempfile management (needed by optimizer) | Add tempfile.NamedTemporaryFile to optimizer code |
| H2 | `--eval-command` not validated as required | Make required in cli.py |
| H3 | No max_rounds cap | Cap at 20 |

### 🟡 Medium (7)

| # | Finding | Fix |
|---|---------|-----|
| M1 | Large artifact overflow (>60K chars) | Truncate with head+tail |
| M2 | Empty reflect response from LLM | Guard: reject if len < 10 |
| M3 | Binary file read → UnicodeDecodeError | Add try/except on read |
| M4 | No progress reporting during LLM calls | Rich spin after reflect() |
| M5 | Mypy errors on skill.py + shell.py | Fix type annotations |
| M6 | Path traversal (assumed workspace) | verify under a configured base directory |
| M7 | RLS not closed on error | `__enter__`/`__exit__` or atexit |

### 🟢 Low (8 — auto-fix)

| # | Finding | Fix |
|---|---------|-----|
| L1 | 0 EOF newlines (13 files) | `ruff check --fix` |
| L2 | F401 unused import `os` provider.py:5 | Remove line 5 (keep line in from_env) |
| L3 | F401 unused import `sqlite3` session_db.py:11 | Remove (add back when queries implemented) |
| L4 | E501 line length (5 spots) | Split prompt strings |

---

## Revised Task Plan (v3)

### Pre-Task 0: Lint + Fix (immediate)
```bash
ruff check src/ tests/ --fix && ruff format src/ tests/
```
Resolves 15/20 issues. Leaves 5 E501 unchecked.

### Task 0-A: Fix All 5 Critical Bugs
1. Rename `session_data` → `session_context` in engine.py:74
2. Add `shlex.quote` in evaluator/shell.py:23
3. Add `--sanitize` flag to EvalResult (scrub key/token patterns)
4. Remove or implement SoulTarget.extract_section
5. Type guard on SkillTarget.triggers

### Task 1: Stub Provider + Test Fixtures (unchanged)

### Task 2: Optimizer Core Loop — REVISED
**Adds from audits:**
- Tempfile management (P4)
- `eval_command` validation (P4)
- `max_rounds` cap (P8)
- `artifact_toochars` guard (P8)
- Rich progress spinner (P3)
- Shell quote in temp path substitution (P8)

### Task 3: CLI Wiring (unchanged)

### Task 4: Tests — 14 tests (was 8 → 10 → now 14)
**Added from audits:**
- `test_shell_injection_prevented` (C2 verification)
- `test_binary_file_rejection`
- `test_empty_artifact_warning`
- `test_reflector_output_too_short_rejected` (<10 chars)
- `test_max_rounds_capped_at_20`
- `test_path_resolved_symlink`

---

## Acceptance Criteria (Revised)

| Criterion | Verification |
|-----------|-------------|
| 5 critical bugs fixed | ruff clean post-fix |
| 15 lint issues resolved | `ruff check src/` ≤ 5 lines |
| 3 MyPy issues resolved | `mypy src/rw_promptforge` clean |
| Optimizer loop tested | `tests/test_optimizer: 10 pass` |
| Bootstrap tests remain 8/8 | `pytest -q` output confirmed |
| Shell injection fixed | Test verifies shlex.quote |
| Tempfile clean | Verify temp dir empty after run |

---

## Sign-off Request

🛑 **Phase 6 pending.** All 6 audit phases (P3+P4+P8+P9+P10+P11) now complete.
The synthesis document integrates all findings.

User, please approve the new V2 plan before Phase 7 (TDD) begins.