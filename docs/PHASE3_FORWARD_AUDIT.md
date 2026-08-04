# Phase 3 — Forward Audit

**Project:** rw-promptforge  
**Date:** 2026-08-04

## Methodology

Validated every claim in SPEC.md and PHASE2_PLAN.md against actual source code.
Read all 4 source files. Ran all 8 tests.

---

## Findings

### ✅ VERIFIED: Provider contract
- `Provider.reflect()` exists, accepts `prompt: str` + `system: str | None`
- Returns `str` via httpx POST to `/v1/chat/completions`
- Error handling: `response.raise_for_status()` → HTTPError
- `close()` exists

### ✅ VERIFIED: ShellEvaluator contract
- `evaluate(artifact_path: str) -> EvalResult` correct
- `{path}` template substitution works
- `EvalResult` has `.passed`, `.failed`, `.timed_out` properties
- `format_trace()` returns diagnostic text

### ✅ VERIFIED: Reflector contract
- `Reflector.__init__` takes `Provider`
- `Reflector.reflect(artifact, trace, session_context, history)` returns `str`
- REFLECTION_SYSTEM_PROMPT and REFLECTION_USER_TEMPLATE constants exist
- Session data default is "(no session data available)"

### ✅ VERIFIED: 8 Tests pass
```
8 passed in 0.14s
```

### ❌ CRITICAL: Template variable mismatch in reflector engine
**File:** `src/rw_promptforge/reflector/engine.py:71-75`

The `REFLECTION_USER_TEMPLATE` contains `{session_context}` but the `.format()` call passes `session_data=session_context` (wrong keyword). This will raise `KeyError: 'session_context'` at runtime.

```python
# BUG: template has {session_context}, but .format() passes session_data=
REFLECTION_USER_TEMPLATE = """...
SESSION DATA (real-world failures involving this artifact):
{session_context}     """  # ← variable name

user_prompt = REFLECTION_USER_TEMPLATE.format(
    artifact=artifact,
    trace=trace,
    session_data=session_context,  # ← wrong: should be session_context=...
    history=history,
)
```

**Fix**: Change `session_data=session_context` to `session_context=session_context`.

### ⚠️ HIGH: Provider.from_env has unused parameter
**File**: `src/rw_promptforge/provider.py:59-78`

The method `classmethod from_env` takes `model: str = "gpt-4o-mini"` but OpenAI's normal env-based key is only read from `OPENAI_API_KEY`. The method handles OpenRouter detection correctly, but the docstring says it also reads `OPENAI_ENDPOINT` — and indeed line 71 reads from `OPENAI_ENDPOINT`. ✅ Verified — no issue, just parameter documentation could be clearer.

### ⚠️ Provider: GREG import unused

**File**: `src/rw_promptforge/provider.py:5`

`import os` at module level but line 68 also has `import os` inside `from_env`. The module-level semicolated import should suffice — the duplicate is unnecessary but harmless.

---

## Summary

| Claim | Status |
|-------|--------|
| All 4 interface contracts match code | ✅ Verified |
| 8 tests pass | ✅ Verified |
| Phase 2 plan task list complete | ✅ Verified |
| Reflector template uses correct variables | ❌ Runtime bug (session_context / session_data mismatch) |
| CLI `--target-type` wired to `target_type` param | ✅ Verified |

**Action required**: Fix `session_data` → `session_context` keyerror before Phase 7.