# Phase 5 — Synthesis (Final Plan v2)

**Project:** rw-promptforge  
**Date:** 2026-08-04  
**Sources:** Forward Audit (Phase 3) + Reverse Audit (Phase 4)

---

## Audit Disposition

| Finding | Source | Severity | Action |
|---------|--------|----------|--------|
| `session_data` → `session_context` template mismatch | Forward | 🔴 Critical | Fix in reflector/engine.py line 74 |
| No tempfile management | Reverse | 🔴 Critical | Add `tempfile` context manager to Task 2 |
| `--eval-command` not validated | Reverse | 🔴 Critical | Add `click` validation in CLI |
| `import os` duplicate | Reverse | 🟢 Info | Clean up (non-blocking) |

All items accepted. Two critical gaps found, plan revised.

---

## Revised Task Plan (v2)

### Task 0 (NEW): Fix reflector engine template bug
- File: `src/rw_promptforge/reflector/engine.py:74`
- Change: `session_data=session_context` → `session_context=session_context`
- Test: existing bootstrap test catches no key errors
- **Immediate — fix now before any other work**

### Task 1: Stub Provider for Tests (unchanged)

### Task 2: Optimizer Core Loop — REVISED
**Adds from audits:**
- Tempfile context manager: `with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=True) as f:`
- `eval_command` required validation (bubble up from CLI)

**Revised signature:**
```python
class Optimizer:
    def __init__(self, provider, evaluator, reflector, max_rounds=3, save=False):
        ...
    
    def optimize(self, artifact_path: str) -> OptimizeResult:
        artifact = Path(artifact_path).read_text()
        history = []
        
        for r in range(self.max_rounds):
            with tempfile.NamedTemporaryFile(...) as tf:
                tf.write(artifact)
                tf.flush()
                result = self.evaluator.evaluate(tf.name)
            
            history.append((r, result))
            
            if result.passed:
                break
            
            session_db_context = self.datastore.read(artifact_path)
            artifact = self.reflector.reflect(
                artifact, result.format_trace(), 
                session_context=session_db_context,
                history=history)
        
        if self.save and self.output_path:
            self.output_path.write_text(artifact)
        
        return OptimizeResult(...)
```

### Task 3: CLI Wiring — REVISED
**Adds:**
- `--eval-command` now **required** (was optional)
- Provider resolution: builds from provider flag + endpoint + model
- PUT error for missing eval_command with helpful message

### Task 4: Tests — REVISED  
**Added:**
- `test_eval_command_required` — CLI exits with error when missing
- `test_tempfile_cleaned` — verify temp files removed after loop
- `test_uses_artifact_from_previous_round` — reflector output becomes next input

Revised: 10 tests (was 8).

---

## Acceptance Criteria

| Criterion | Verification |
|-----------|-------------|
| Template bug fixed | `bootstrap test passes` |
| Optimizer core loop works | `tests/test_optimizer.py: 10 passed` |
| CLI fully wired | `rw-promptforge optimize` does real work |
| All 3 audit items resolved | Forward audit re-verifies |
| Lint clean | `ruff check src/` clean |
| Mypy strict | `mypy src/rw_promptforge` clean |

---

## Sign-off Request

🛑 **Phase 6 pending.** User: please review and approve the revised v2 plan before Phase 7 (TDD implementation) begins.