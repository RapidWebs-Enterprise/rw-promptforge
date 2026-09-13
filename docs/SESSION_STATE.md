# rw-promptforge — Session State

**Last updated**: 2026-09-12
**Status**: ACTIVE (CLI installed, DB connector verified, `skill_name` scoping FIXED)

---

## ✅ FIXED: `skill_name` now scopes traces by parsing skill_view/skill_manage tool calls

**File**: `src/rw_promptforge/datastore/session_db.py`
**Commit**: `a2459f9` on `master`
**Status**: FIXED — committed and verified

### What was wrong

`find_corrections(skill_name, limit)` and `find_tool_failures(skill_name, limit)` accepted a `skill_name` argument but **never used it in SQL**. Both queries ran against the global message pool — every skill optimization drew from the same 72,856-message corpus regardless of which skill was being optimized.

### The fix (v2 — tool-call-based)

Instead of modifying the Hermes DB schema, the fix parses the existing `tool_calls` JSON column. Every time a skill is loaded, the assistant invokes `skill_view(name="<skill-name>")` or `skill_manage(action="...", name="<skill-name>")`. The `tool_calls` column stores these as a JSON array of `{"function": {"name": "...", "arguments": "{\"name\":\"<skill>\"}"}}`.

`_skill_filter_sql()` now builds a subquery that:
1. Uses `json_tree()` to walk the `tool_calls` JSON
2. Matches `jt.key = 'function'` with `json_extract(jt.value, '$.name') IN ('skill_view', 'skill_manage')`
3. Filters arguments JSON for the skill name

The subquery runs against a **different message row** (`m2`) than the correction row (`m`) — critical because `tool_calls` only exists on assistant messages, not user messages.

### Verification

```
COMPILE OK
Global: 10 traces
Scoped (ast-tools-usage): 5 traces     ← correctly filtered
Scoped (nonexistent): 0 traces          ← correct
Scoped (spectral-clustering): 1 trace   ← different skill, different results
Tool failures scoped: 5
```

### Remaining limitations

- **`find_protocol_violations` not scoped**: doesn't accept a `skill_name` parameter.
- **`find_successes` not scoped**: same.
- **No `--skill` CLI flag**: callers can pass scoping through the Python API.
- **Approximate name matching**: `LIKE '%"<skill>%"'` could match a skill name appearing in unrelated tool arguments.

---

## What Was Done This Session (rw-promptforge)

| Action | Detail |
|--------|--------|
| CLI installed | `uv tool install --editable .` from `~/Workspaces/rw-promptforge/` |
| Read-only contract verified | `optimize` without `--save`/`--output` does not modify the target file |
| NVIDIA NIM route validated | `--endpoint https://integrate.api.nvidia.com/v1 --model deepseek-ai/deepseek-v4-pro-0813` |
| Empirical pass run | 3 rounds against a `/tmp` copy of `critic-refinement/SKILL.md` |
| Result consumed | +16/−1 surgical diff: 6 anti-patterns (AP-1..AP-6) merged into live skill, version 1.0.0 → 1.2.0 |
| `skill_name` no-op | **FIXED** — `_skill_filter_sql` helper added, committed `6e894eb` |

## Provider Notes

- `provider.py` reads keys from `OPENAI_API_KEY` + `OPENAI_ENDPOINT`, or `OPENROUTER_API_KEY`. **No config file mechanism exists** — keys must be exported into the environment.
- NVIDIA NIM routed by exporting the NVIDIA key as `OPENAI_API_KEY` and passing `--endpoint https://integrate.api.nvidia.com/v1`.
- Correct deepseek slug: `deepseek-ai/deepseek-v4-pro-0813` (NOT `deepseek-v4-pro-0831` — that slug doesn't exist on build.nvidia.com).
- NVIDIA keys are in `~/.secure/keys/nvidia_nim` (two `nvapi-` keys).