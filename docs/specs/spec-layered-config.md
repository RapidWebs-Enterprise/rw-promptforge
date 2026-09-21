# SPEC — Layered Configuration for rw-promptforge

**Status:** DRAFT — awaiting sign-off
**Date:** 2026-09-14
**Pattern reference:** `rw_telebot/src/rw_telebot/configs/` (layered_models.py, core.py, cli_loader.py)

---

## 1. Problem

Configuration is currently scattered across four unrelated mechanisms with no single precedence story:

| Where | Examples | Pain |
|-------|----------|------|
| CLI flags (25+) | `--semantic-threshold`, `--min-traces`, `--ml-endpoint` | No persistence — retype every run |
| Hardcoded defaults | `Provider.embedding_model = "bge-small-en-v1.5"` | Can't override without code edit |
| Ad-hoc env vars | `RW_IE_ENDPOINT`, `RW_PROMPTFORGE_EMBEDDING_MODEL` | Prefix inconsistent, no schema |
| `Hyperparams` dataclass | `optimizer.py` module-level | Not user-reachable |

None of the four knows about the others. There is no validation, no `--show-config` debugging, and no way for a user to persist "my defaults" in a file.

## 2. Goals

1. Single fixed **precedence chain** (lower loses to higher):
   1. Pydantic default values in `configs/layered_models.py`
   2. User-level TOML: `~/.config/rw-promptforge/config.toml`
   3. Project-level TOML: `./config.toml` then `./config/rw-promptforge.toml`
   4. `.env` file mapped keys
   5. Environment variables prefixed `RW_PROMPTFORGE_`
   6. CLI flags (highest)
2. **One root model** — `RootConfig` — validated once at startup with Pydantic; component code reads attributes, never env vars.
3. **Deep-merge semantics** for nested tables (same helper rw_telebot uses).
4. **`rw-promptforge config show`** — prints merged config with per-value provenance.
5. **`rw-promptforge config init`** — writes skeleton TOML to user-level path.
6. Existing 25+ CLI flags keep working — they map onto the same schema, not replaced.

## 3. Non-Goals

- Nested profile switching (`[profiles.dev]`) — out of scope for v1.
- Runtime config reload / file watching — rw-promptforge is a CLI, not a daemon.
- Secret management. Secrets stay in env vars / `.env`; the loader must never write them to the merged TOML we ship back to users as part of `config show --export`.
- Backward-incompatible behavior change. Default values must match today's hardcoded values byte-for-byte.

## 4. Design

### 4.1 File Layout

```
src/rw_promptforge/configs/
├── __init__.py             # public: load_config(), get_settings()
├── layered_models.py       # Pydantic BaseModel tree (ProviderConfig, MLConfig, ...)
├── core.py                 # load_config() — 6-layer merge + validate
├── file_loader.py          # find_config_file(), load_toml_config()
├── env_loader.py           # load_env_vars(), map_env_to_config(), PREFIX="RW_PROMPTFORGE_"
├── cli_loader.py           # parse_cli_args(), map_cli_to_config()
└── schema_export.py        # render JSON Schema for `config schema --json`
```

### 4.2 Model Tree

```python
class MLConfig(BaseModel):
    enabled: bool = False                    # was --ml-mode
    endpoint: str = "http://srv1:8300"       # was --ml-endpoint
    embedding_model: str = "bge-small-en-v1.5"
    rerank_model: str = "ms-marco-MiniLM-L-6-v2"
    min_traces: int = 10                     # was --min-traces
    cache_maxsize: int = 10_000

class OptimizerConfig(BaseModel):
    max_rounds: int = 3
    semantic_threshold: float = 0.95
    gain_threshold: float = 0.02
    stability_threshold: float = 0.05
    min_rounds: int = 2
    beam_size: int = 1
    frontier_size: int = 5
    convergence_threshold: float = 0.01
    max_growth: float = 1.5

class LLMConfig(BaseModel):
    provider: Literal["openai", "openrouter", "custom"] = "openai"
    endpoint: str | None = None
    model: str = "gpt-4o-mini"

class SessionDBConfig(BaseModel):
    path: Path = Path("~/.rw-promptforge/session.db")

class RootConfig(BaseModel):
    optimizer: OptimizerConfig = Field(default_factory=OptimizerConfig)
    ml: MLConfig = Field(default_factory=MLConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    session_db: SessionDBConfig = Field(default_factory=SessionDBConfig)
```

### 4.3 Env-Var Mapping (env_loader)

Prefix: `RW_PROMPTFORGE_`. Nested keys split on `__` (double underscore) to avoid collision with field names containing underscores.

```
RW_PROMPTFORGE_ML__ENABLED=1               → ml.enabled = True
RW_PROMPTFORGE_ML__ENDPOINT=http://x:8300  → ml.endpoint = "http://x:8300"
RW_PROMPTFORGE_OPTIMIZER__MAX_ROUNDS=5     → optimizer.max_rounds = 5
```

`.env` file: same key format, loaded via `dotenv_values()` (not `load_dotenv`) to avoid polluting `os.environ`.

### 4.4 CLI Integration

**Mechanism:** keep existing `@click.option` decorators. After click parses, a new step `map_cli_to_config(namespace)` converts non-None values to nested dict, which is deep-merged as the final (highest-priority) layer.

```python
# In cli.py, at top of optimize()
cli_overrides = map_cli_to_config(locals(), schema=CLI_OVERRIDE_SCHEMA)
config = load_config(cli_overrides=cli_overrides)
```

Then replace `semantic_threshold=semantic_threshold` with `config.optimizer.semantic_threshold`, etc.

**Net behavior change:** none when no flags/files set — every default in Pydantic matches current hardcodes.

### 4.5 New subcommands

```
rw-promptforge config show           # merged, human-readable with [source] annotations
rw-promptforge config show --json    # machine-readable
rw-promptforge config init           # scaffolds ~/.config/rw-promptforge/config.toml
rw-promptforge config schema --json  # JSON Schema export for external tooling
```

### 4.6 Provenance Attribution

Each layer returns `(data: dict, source: str)`. Final merge walks layers in order and records which layer won per leaf key. `config show` uses this to print:

```
optimizer.max_rounds = 5        [user TOML]
ml.endpoint = http://srv1:8300  [env RW_PROMPTFORGE_ML__ENDPOINT]
```

## 5. Testing

| Test | Purpose |
|------|---------|
| `test_defaults_root_config()` | No external input → matches current hardcodes |
| `test_toml_user_level_only()` | User file overrides defaults |
| `test_project_beats_user()` | Project TOML layered on top |
| `test_env_beats_files()` | `RW_PROMPTFORGE_*` wins over TOML |
| `test_cli_beats_env()` | CLI namespace wins final |
| `test_dotenv_mapped()` | `.env` keys reach the right fields |
| `test_nested_deep_merge()` | `[ml]` in TOML doesn't clobber `[optimizer]` from env |
| `test_provenance_attribution()` | Each leaf reports correct source |
| `test_config_init_writes_valid_toml()` | Round-trip: init → load equals default |
| `test_invalid_value_rejected()` | Pydantic catches type errors at startup |

## 6. Migration Plan

| Step | Action | Risk |
|------|--------|------|
| 1 | Add `configs/` package, no call sites | None |
| 2 | Add tests for the chain | None |
| 3 | Switch ONE CLI flag (`--ml-endpoint`) to read via config | Small |
| 4 | Switch remaining 24 flags in one sweep | Medium — requires careful regression test |
| 5 | Add `config show|init|schema` subcommands | None |
| 6 | Delete ad-hoc env reads from `provider.py` (`RW_IE_ENDPOINT`, `RW_PROMPTFORGE_EMBEDDING_MODEL`) | Breaking for anyone who set them — emit deprecation warning for one release |

**Backward-compat shim:** `Provider.from_env()` static constructor remains as a one-line wrapper around `load_config().llm`, so any external caller keeps working.

## 7. Decisions Referenced

- ADR-009 through ADR-012 (ML-mode, RW_IE endpoints) — env vars referenced there must migrate; timeline in §6 step 6.
- rw_telebot layered config pattern (`src/rw_telebot/configs/`) is the template; we adapt names/keys for promptforge.
- Pydantic v2 for models (already an indirect dep via rw_telebot pattern; clean add to `[project.dependencies]`).

## 8. Estimated Effort

| Phase | Files | LOC | Effort |
|-------|-------|-----|--------|
| Models + loaders + core | `configs/*.py` | ~450 | 2h |
| CLI integration | `cli.py` | ~80 (edit) | 1h |
| `config` subcommand | `cli_config.py` | ~150 | 1h |
| Tests | `tests/test_configs*.py` | ~250 | 1.5h |
| Docs + ADR-013 | `docs/` | ~120 | 0.5h |
| **Total** | **7 new, 3 modified** | **~1050** | **~6h** |
