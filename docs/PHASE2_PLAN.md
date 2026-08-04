# Phase 2 — Implementation Plan

**Project:** rw-promptforge  
**Date:** 2026-08-04  
**Mode:** MEDIUM  
**Total estimated LOC:** ~350 (optimizer.py + test_optimizer.py + cli wiring)

---

## Roadmap

### Task 1: Stub Provider for Tests

**Objective:** Create a stub/fake LLM provider so all optimizer tests run with no network.

**Files:**
- CREATE: `tests/conftest.py` — fixture returning fake Provider
- MODIFY: `tests/test_bootstrap.py` — no change needed (bootstrap tests use real Provider instantiation with no network call)

**Approach:** The `Provider` class already exists. Tests need a mock/fake that returns canned text without any HTTP call. We'll use `pytest.MonkeyPatch` to replace `Provider.reflect()` with a testable stub that returns a predetermined string. The simplest approach: `unittest.mock.patch` on the Provider's `reflect` method.

Specifically for optimizer tests: create a fake provider that returns a slightly different artifact each call, so the loop converges after 2-3 iterations.

**Test:**
```python
def test_fake_provider_returns_improved_prompt():
    from unittest.mock import patch
    from rw_promptforge.provider import Provider
    
    with patch.object(Provider, 'reflect', return_value="improved: " + caller_prompt):
        provider = Provider()
        result = provider.reflect("original", "system")
        assert "improved:" in result
```

### Task 2: Optimizer Core Loop

**What:** Build `optimizer.Optimizer` — the core evaluate → reflect → improve loop.

**File:**
- CREATE: `src/rw_promptforge/optimizer.py`

**Signature:**
```python
class Optimizer:
    def __init__(self, provider, evaluator, reflector, max_rounds=3, save=False):
        ...
    
    def optimize(self, artifact_path: str) -> OptimizeResult:
        # Returns: final artifact, rounds used, history [(round_num, EvalResult)]
```

**Flow:**
```
artifact = file.read(artifact_path)
history = []

for r in range(max_rounds):
    temp_path = write_temp_file(artifact)
    result = evaluator.evaluate(temp_path)
    history.append((r, result))
    
    if result.passed:
        break  # converged
    
    session_context = datastore.read(artifact_path / skill_name)
    artifact = reflector.reflect(artifact, result.format_trace(), session_context, history)
    # continue loop

if save_configured:
    write_final_artifact(artifact)
return OptimizeResult(artifact, history, converged)
```

**Data class:**
```python
@dataclass
class OptimizeResult:
    artifact: str
    history: list[tuple[int, EvalResult]]
    converged: bool
    rounds: int
```

### Task 3: CLI Wiring

**File:** MODIFY `src/rw_promptforge/cli.py`

**Changes:** Wire the `optimize` function to build Provider, Evaluator, Reflector, and call Optimizer.optimize(). Output results via Rich.

```python
def optimize(path, target_type, provider_name, endpoint, model, max_rounds, eval_command, save):
    provider = resolve_provider(provider_name, endpoint, model)
    evaluator = ShellEvaluator(eval_command)
    reflector = Reflector(provider)
    optimizer = Optimizer(provider, evaluator, reflector, max_rounds=max_rounds)
    
    result = optimizer.optimize(path)
    
    console.print(f"[green]Converged[/] in {result.rounds} rounds")
    if save:
        write_file(path + ".optimized", result.artifact)
```

### Task 4: Tests — Full Optimizer Loop

**File:** CREATE `tests/test_optimizer.py`

**Tests (estimated 6-8):**

| Test | Description |
|------|-------------|
| `test_converges_first_round` | Evaluator passes immediately → 1 round |
| `test_iterates_fixed_echo` | Shell command `echo FAIL; exit 1` → reflector generates "improved: ..."; loop converges |
| `test_respects_max_rounds` | Always-failing eval → stops at max_rounds |
| `test_history_stored` | Check history has correct length after run |
| `test_no_modify_original` | Verify source file is unchanged unless --save given |
| `test_save_writes_output` | --save writes {path}.optimized |
| `test_target_not_found` | Pass path that doesn't exist → graceful error |
| `test_reflector_output_is_used` | Verify reflector output becomes next artifact for evaluation |

## Task Schedule

| Task | Priority | Estimate |
|------|----------|----------|
| Task 1: Test fixtures (stub provider) | P0 | 15 min |
| Task 2: optimizer.py core loop | P0 | 45 min |
| Task 3: CLI wiring | P1 | 15 min |
| Task 4: Full test suite | P0 | 30 min |
| **Total** | | **~1.5 h** |

## Phase 1 Completion Checklist

- [ ] `optimizer.py` exists with `Optimizer` class + `OptimizeResult` dataclass
- [ ] Tests cover: convergence, max rounds, history tracking, save, error paths
- [ ] CLI `optimize` command calls Optimizer (not stub)
- [ ] All 8 bootstrap tests still pass
- [ ] Lint: `uv run ruff check src/` clean