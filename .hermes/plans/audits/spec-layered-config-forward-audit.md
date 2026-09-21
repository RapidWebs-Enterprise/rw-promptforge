# Forward Audit: spec-layered-config.md & plan-layered-config.md

**Audit Date:** 2026-09-20
**Auditor:** Subagent (automated verification)
**Mode:** FORWARD — validates spec/plan claims against actual codebase

---

## Executive Summary

| Category | Claims Verified | CONFIRM | DENY | PARTIAL | GAPS |
|----------|-----------------|---------|------|---------|------|
| Spec §1 (Current State) | 5 | 4 | 0 | 1 | 1 |
| Spec §4 (Design) / rw_telebot ref | 4 | 3 | 0 | 1 | 0 |
| Plan Implementability | 3 | 2 | 0 | 1 | 2 |
| **Total** | **12** | **9** | **0** | **3** | **3** |

**Overall:** Spec is largely accurate. Plan is implementable but has gaps in CLI flag coverage and missing dependency declarations.

---

## 1. Spec Accuracy: Current State of rw-promptforge

### 1.1 "CLI flags (25+)" — Table row in §1

| Spec Claim | Actual Code | Verdict |
|------------|-------------|---------|
| "CLI flags (25+)" | 26 `@click.option` decorators in `cli.py` | **CONFIRM** |

**Details:** Counted 26 click options via regex. Spec says "25+" which is accurate.

---

### 1.2 "Hardcoded defaults: `Provider.embedding_model = \"bge-small-en-v1.5\"`" — Table row in §1

| Spec Claim | Actual Code | Verdict |
|------------|-------------|---------|
| `embedding_model` default = `"bge-small-en-v1.5"` | `self.embedding_model = embedding_model or os.environ.get("RW_PROMPTFORGE_EMBEDDING_MODEL", "bge-small-en-v1.5")` | **CONFIRM** |
| `rerank_model` default = `"ms-marco-MiniLM-L-6-v2"` | In `__init__`: `self.rerank_model = rerank_model` (no default). In `from_ml_env()`: `os.environ.get("RW_IE_RERANK_MODEL", "ms-marco-MiniLM-L-6-v2")` | **PARTIAL** |

**Discrepancy:** The spec presents both as simple hardcoded class-level defaults. In reality:
- `embedding_model` has a default in `__init__` (with env override)
- `rerank_model` has **no default in `__init__`** — only in `from_ml_env()` classmethod
- This matters for the migration: `RootConfig.ml.rerank_model` default in spec (`"ms-marco-MiniLM-L-6-v2"`) won't match current behavior unless `from_ml_env()` path is taken

---

### 1.3 "Ad-hoc env vars: `RW_IE_ENDPOINT`, `RW_PROMPTFORGE_EMBEDDING_MODEL`" — Table row in §1

| Spec Claim | Actual Code | Verdict |
|------------|-------------|---------|
| These env vars exist and are read | Both found in `provider.py` (`from_ml_env()` and `__init__`) | **CONFIRM** |
| They are "ad-hoc" with "prefix inconsistent" | `RW_IE_ENDPOINT` (prefix `RW_IE_`) vs `RW_PROMPTFORGE_EMBEDDING_MODEL` (prefix `RW_PROMPTFORGE_`) — inconsistent indeed | **CONFIRM** |
| Not read in `cli.py` | Verified: neither appears in `cli.py` | **CONFIRM** |

---

### 1.4 "No configs/ directory exists" — Implied by §4.1 file layout

| Spec Claim | Actual Code | Verdict |
|------------|-------------|---------|
| No `src/rw_promptforge/configs/` directory | Verified: does not exist | **CONFIRM** |
| No root `configs/` directory | Verified: does not exist | **CONFIRM** |

---

### 1.5 "Pydantic v2... clean add to `[project.dependencies]`" — §7 Decisions

| Spec Claim | Actual Code | Verdict |
|------------|-------------|---------|
| Pydantic not in dependencies | `pyproject.toml` deps: `click`, `rich`, `httpx`, `pyyaml` only | **CONFIRM** |
| python-dotenv not in dependencies | Verified: absent | **CONFIRM** |

**Gap in Plan:** Plan §22 row for `pyproject.toml` says "Add `pydantic>=2.0`, `python-dotenv>=1.0` to core deps" — correct, but the plan doesn't mention adding them to `[project.dependencies]` vs `[project.optional-dependencies]`. Spec §7 says "clean add to `[project.dependencies]`" — should be core, not optional.

---

## 2. rw_telebot Reference Claims

### 2.1 "5-layer order matches what spec says" — §7 Decision referencing rw_telebot

| Spec Design (§4.1) — 6 layers | rw_telebot core.py — 5 layers | Match? |
|-------------------------------|-------------------------------|--------|
| 1. Pydantic defaults | 1. Hardcoded minimal safe defaults (Pydantic models) | ✅ Yes |
| 2. User TOML `~/.config/rw-promptforge/config.toml` | 2. User-level `~/.config/rw_telebot/config.toml` | ✅ Yes (adapted name) |
| 3. Project TOML `./config.toml` or `./config/rw-promptforge.toml` | 3. Project-level `./config.toml` or `./config/rw_telebot.toml` | ✅ Yes (adapted name) |
| 4. `.env` file mapped keys | 4. `.env` file (raw keys → config paths via `map_dotenv_to_config`) | ✅ Yes |
| 5. Env vars `RW_PROMPTFORGE_` | 5. Env vars `RW_TELEBOT_` | ✅ Yes (adapted prefix) |
| 6. CLI flags (highest) | **Not in `load_config()`** — handled separately in `cli_loader.py` | **PARTIAL** |

**Verdict:** **PARTIAL CONFIRM**. The spec correctly adapts the 5-layer rw_telebot pattern to a 6-layer chain by explicitly adding CLI as layer 6. rw_telebot's `load_config()` stops at layer 5; CLI overrides are applied later via `cli_loader.py` + `map_cli_to_config()`. The spec's unified `load_config(cli_overrides=...)` is a cleaner design.

---

### 2.2 "_deep_merge semantics" — §4.3

| Spec Claim | rw_telebot Implementation | Verdict |
|------------|---------------------------|---------|
| "Deep-merge semantics for nested tables (same helper rw_telebot uses)" | `_deep_merge(base, override)` recursively merges dicts; override leaf values win | **CONFIRM** |

**Implementation matches exactly:** Both do recursive dict merge with override precedence.

---

### 2.3 Env var mapping: double-underscore separator

| Spec Claim (§4.3) | rw_telebot Implementation | Verdict |
|-------------------|---------------------------|---------|
| "Nested keys split on `__` (double underscore)" | `env_to_config_key()`: `key.replace("__", ".")` after prefix strip | **CONFIRM** |
| Prefix: `RW_PROMPTFORGE_` | rw_telebot uses `RW_TELEBOT_` | **CONFIRM** (adapted) |

---

### 2.4 `.env` loading via `dotenv_values()` not `load_dotenv()`

| Spec Claim (§4.3) | rw_telebot Implementation | Verdict |
|-------------------|---------------------------|---------|
| "`.env` file: same key format, loaded via `dotenv_values()` (not `load_dotenv`) to avoid polluting `os.environ`" | `_load_dotenv_file()` in core.py uses `dotenv_values(str(dotenv_path))` | **CONFIRM** |

---

## 3. Plan Implementability

### 3.1 "Proposed model sketch field names are all referenced in cli.py" — Plan §36 Model Sketch

| Model Field (Plan §36) | In cli.py? | Notes |
|------------------------|------------|-------|
| **MLConfig** | | |
| `enabled` | ❌ MISSING | No `--ml-enabled` flag; only `--ml-mode` (flag) exists |
| `endpoint` | ✅ | `--ml-endpoint` |
| `embedding_model` | ❌ MISSING | No CLI flag |
| `rerank_model` | ❌ MISSING | No CLI flag |
| `min_traces` | ✅ | `--min-traces` |
| `cache_maxsize` | ❌ MISSING | No CLI flag |
| **OptimizerConfig** | | |
| `max_rounds` | ✅ | `--max-rounds` |
| `semantic_threshold` | ✅ | `--semantic-threshold` |
| `gain_threshold` | ✅ | `--gain-threshold` |
| `stability_threshold` | ✅ | `--stability-threshold` |
| `min_rounds` | ✅ | `--min-rounds` |
| `beam_size` | ✅ | `--beam-size` |
| `frontier_size` | ✅ | `--frontier-size` |
| `convergence_threshold` | ✅ | `--convergence-threshold` |
| `max_growth` | ✅ | `--max-growth` |
| **LLMConfig** | | |
| `provider` | ✅ | `--provider` |
| `model` | ✅ | `--model` |
| `endpoint` (in LLMConfig) | ✅ | `--endpoint` |
| **SessionDBConfig** | | |
| `path` | ✅ | Positional `path` arg |

**Verdict:** **PARTIAL CONFIRM** — 4 fields in the model sketch have no corresponding CLI flags:
- `ml.enabled` (spec has `--ml-mode` flag but model has `enabled: bool`)
- `ml.embedding_model`
- `ml.rerank_model`
- `ml.cache_maxsize`

**Gap in Plan:** The plan says "Existing 25+ CLI flags keep working — they map onto the same schema, not replaced" (§4.4). But the proposed schema *adds* 4 new fields that have no CLI representation. Either:
1. Add 4 new CLI flags (increases surface area), or
2. Document that these are TOML/env-only (behavior change from "all fields CLI-accessible")

---

### 3.2 "Check pyproject.toml for conflicts (e.g., pydantic already present?)"

| Dependency | Present? | Conflict? | Verdict |
|------------|----------|-----------|---------|
| `pydantic>=2.0` | ❌ No | No conflict | **CONFIRM** — safe to add |
| `python-dotenv>=1.0` | ❌ No | No conflict | **CONFIRM** — safe to add |
| `tomli` / `tomllib` | ❌ No | Need for TOML parsing | **GAP** — Plan doesn't declare TOML parser dependency |

**Gap in Plan:** The plan (§22, §76) mentions TOML loading but doesn't declare a TOML parser dependency. Python 3.11+ has `tomllib` in stdlib (read-only); for writing TOML (`config init`), need `tomli-w` or `tomlkit`. Since `requires-python = ">=3.10"`, and `tomllib` is 3.11+, the project needs an explicit TOML library (e.g., `tomli` for reading, `tomli-w` for writing, or `tomlkit` for both).

---

### 3.3 Plan Phase 1 file list vs Spec §4.1 file layout

| Spec §4.1 File | Plan §22 File | Match? |
|----------------|---------------|--------|
| `__init__.py` | `__init__.py` | ✅ |
| `layered_models.py` | `layered_models.py` | ✅ |
| `core.py` | `core.py` | ✅ |
| `file_loader.py` | `file_loader.py` | ✅ |
| `env_loader.py` | `env_loader.py` | ✅ |
| `cli_loader.py` | `cli_loader.py` | ✅ |
| `schema_export.py` | *missing from plan* | **GAP** |

**Gap in Plan:** `schema_export.py` (for `config schema --json`) is in spec but missing from Plan Phase 1 file list.

---

## 4. Discrepancies Summary

| # | Location | Spec/Plan Claim | Reality | Severity |
|---|----------|-----------------|---------|----------|
| 1 | Spec §1 Table | `rerank_model` hardcoded default | No default in `Provider.__init__`; only in `from_ml_env()` | Medium — migration must handle both paths |
| 2 | Spec §4.2 Model | `MLConfig.rerank_model` default `"ms-marco-MiniLM-L-6-v2"` | Matches `from_ml_env()` but not `Provider.__init__` | Medium — decide which is "current behavior" |
| 3 | Spec §4.4 | "Existing 25+ CLI flags keep working — they map onto the same schema" | 4 schema fields lack CLI flags | Medium — schema extends beyond current CLI |
| 4 | Plan §22 | `pyproject.toml` add pydantic, python-dotenv | Missing TOML parser dependency | High — `config init` writes TOML |
| 5 | Plan §22 | File list matches spec | `schema_export.py` missing | Low — easy add |
| 6 | Spec §6 Step 6 | "Delete ad-hoc env reads from `provider.py` (`RW_IE_ENDPOINT`, `RW_PROMPTFORGE_EMBEDDING_MODEL`)" | Also `RW_IE_RERANK_MODEL`, `RW_IE_API_KEY` in `from_ml_env()` | Low — incomplete list |

---

## 5. Gaps in Plan Not Caught by Spec

| Gap | Description | Impact |
|-----|-------------|--------|
| **TOML writer dependency** | Plan uses `config init` to write TOML but no TOML write lib declared | Build fails at Phase 2 |
| **Schema export module** | Spec §4.1 lists `schema_export.py`; Plan Phase 1 omits it | `config schema --json` not implementable |
| **4 CLI-unmapped model fields** | `enabled`, `embedding_model`, `rerank_model`, `cache_maxsize` in model but no click options | Users can't set via CLI; only TOML/env |
| **`session_db.path` type** | Spec uses `Path` default `Path("~/.rw-promptforge/session.db")`; Plan uses `Field(default=Path(...))` — Pydantic v2 needs `default_factory` for mutable defaults | Potential shared-instance bug |
| **Deprecation warning mechanism** | Plan §4 mentions `UserWarning` but no spec for *where* emitted (provider.py? config loader?) | Inconsistent UX |
| **Backward-compat `Provider.from_env()`** | Spec §6 says wrapper around `load_config().llm`; but `load_config()` returns `RootConfig` with `llm: LLMConfig`, while `Provider.from_env()` returns `Provider` with different fields | Type mismatch — needs adapter |

---

## 6. Recommendations

1. **Add TOML dependency** to Plan Phase 1: `tomli>=2.0` (read) + `tomli-w>=1.0` (write) or `tomlkit>=0.12` (both). Since `requires-python >=3.10`, cannot rely on `tomllib`.

2. **Add `schema_export.py`** to Plan Phase 1 file list.

3. **Decide on 4 unmapped fields**: Either add CLI flags (extending surface area) or explicitly document as TOML/env-only in spec.

4. **Fix `rerank_model` default**: Spec should clarify which code path is "current behavior" for byte-for-byte default matching (§4 Non-Goals).

5. **Add `RW_IE_RERANK_MODEL`, `RW_IE_API_KEY`** to deprecation list in Spec §6 Step 6.

6. **Fix `SessionDBConfig.path` default** in Plan model sketch to use `default_factory=lambda: Path("~/.rw-promptforge/session.db")`.

7. **Clarify `Provider.from_env()` shim**: Spec §6 needs a concrete signature — e.g., `Provider.from_env(model) -> Provider` that internally calls `load_config()` and maps `LLMConfig` → `Provider` args.

---

## 7. Final Verdicts

| Check | Result |
|-------|--------|
| Spec accurately describes current rw-promptforge state? | **MOSTLY YES** — 1 material discrepancy (rerank_model default) |
| rw_telebot 5-layer claim holds? | **YES** — spec correctly adapts pattern to 6 layers |
| _deep_merge semantics match? | **YES** |
| Plan implementable as-written? | **NO** — 3 gaps block implementation (TOML writer, schema_export, 4 unmapped fields) |
| Plan dependencies complete? | **NO** — missing TOML parser |

---

## 8. Suggested Plan Patches

```diff
# Phase 1 — pyproject.toml MODIFY
- Add `pydantic>=2.0`, `python-dotenv>=1.0` to core deps
+ Add `pydantic>=2.0`, `python-dotenv>=1.0`, `tomli>=2.0`, `tomli-w>=1.0` to core deps

# Phase 1 — File list
+ `src/rw_promptforge/configs/schema_export.py` | CREATE | JSON Schema export for `config schema --json`

# Phase 3 — CLI migration
+ Add 4 new flags: `--ml-enabled`, `--embedding-model`, `--rerank-model`, `--cache-maxsize`
  (or update spec to mark these as TOML/env-only)

# Phase 4 — Deprecation
- Emit UserWarning on `RW_IE_ENDPOINT`, `RW_PROMPTFORGE_EMBEDDING_MODEL`
+ Emit UserWarning on `RW_IE_ENDPOINT`, `RW_PROMPTFORGE_EMBEDDING_MODEL`, `RW_IE_RERANK_MODEL`, `RW_IE_API_KEY`

# Model sketch fix
- path: Path = Field(default=Path("~/.rw-promptforge/session.db"))
+ path: Path = Field(default_factory=lambda: Path("~/.rw-promptforge/session.db"))
```

---

*End of Forward Audit*