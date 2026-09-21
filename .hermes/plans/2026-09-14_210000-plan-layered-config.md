---
name: Layered Configuration System
description: 6-layer Pydantic/Pydantic-settings config chain per ADR-013
status: proposed
created: 2026-09-14
related_spec: docs/specs/spec-layered-config.md
related_adrs: [013]
---

# Plan — Layered Config System

## Deliverables

| Phase | Artifact | LOC |
|-------|----------|-----|
| P1 | `configs/` package skeleton (models, loaders, core) | ~450 |
| P2 | `cli_config.py` + `config show/init/schema` subcommands | ~150 |
| P3 | `optimize` CLI migration (one-flag first, then sweep) | ~80 |
| P4 | Env-var deprecation shim + ADR-013 follow-ups | ~60 |
| P5 | Tests for every layer, merge logic, provenance | ~250 |

## Phase 1 — configs/ package skeleton

### Files

| File | Action | Purpose |
|------|--------|---------|
| `src/rw_promptforge/configs/__init__.py` | CREATE | Export `load_config`, `get_settings`, `RootConfig` |
| `src/rw_promptforge/configs/layered_models.py` | CREATE | `MLConfig`, `OptimizerConfig`, `LLMConfig`, `SessionDBConfig`, `RootConfig` |
| `src/rw_promptforge/configs/file_loader.py` | CREATE | TOML discovery + parsing + walk-up search |
| `src/rw_promptforge/configs/env_loader.py` | CREATE | `RW_PROMPTFORGE_` prefix → nested dict; `.env` mapper |
| `src/rw_promptforge/configs/cli_loader.py` | CREATE | argparse → nested dict |
| `src/rw_promptforge/configs/core.py` | CREATE | `load_config(cli_overrides=None) -> RootConfig` |
| `pyproject.toml` | MODIFY | Add `pydantic>=2.0`, `python-dotenv>=1.0` to core deps |

### Model sketch

```python
from pydantic import BaseModel, Field, PositiveInt, field_validator
from pathlib import Path

class MLConfig(BaseModel):
    enabled: bool = False
    endpoint: str = "http://srv1:8300"
    embedding_model: str = "bge-small-en-v1.5"
    rerank_model: str = "ms-marco-MiniLM-L-6-v2"
    min_traces: PositiveInt = 10
    cache_maxsize: PositiveInt = 10_000

class OptimizerConfig(BaseModel):
    max_rounds: PositiveInt = 3
    semantic_threshold: float = Field(default=0.95, ge=0.0, le=1.0)
    gain_threshold: float = Field(default=0.02, ge=0.0)
    stability_threshold: float = Field(default=0.05, ge=0.0)
    min_rounds: PositiveInt = 2
    beam_size: PositiveInt = 1
    frontier_size: PositiveInt = 5
    convergence_threshold: float = Field(default=0.01, ge=0.0)
    max_growth: float = Field(default=1.5, ge=1.0)

class LLMConfig(BaseModel):
    provider: Literal["openai", "openrouter", "custom"] = "openai"
    endpoint: str | None = None
    model: str = "gpt-4o-mini"

class SessionDBConfig(BaseModel):
    path: Path = Field(default=Path("~/.rw-promptforge/session.db"))

class RootConfig(BaseModel):
    optimizer: OptimizerConfig = Field(default_factory=OptimizerConfig)
    ml: MLConfig = Field(default_factory=MLConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    session_db: SessionDBConfig = Field(default_factory=SessionDBConfig)
```

### Core loader sketch

```python
def load_config(cli_overrides: dict | None = None) -> RootConfig:
    layers: list[tuple[str, dict]] = []
    layers.append(("defaults", RootConfig().model_dump()))
    if user := load_user_toml():  layers.append(("user_toml", user))
    if proj := load_project_toml():  layers.append(("project_toml", proj))
    if dotenv := load_dotenv():  layers.append(("dotenv", map_dotenv(dotenv)))
    if env := load_env_vars(): layers.append(("env", map_env(env)))
    if cli_overrides: layers.append(("cli", cli_overrides))
    merged = deep_merge_chain(layers)
    return RootConfig(**merged)
```

### Walk-up discovery (project TOML)

```python
def find_project_config(start: Path) -> Path | None:
    cur = start.resolve()
    while True:
        for cand in (cur / "config.toml", cur / "config" / "rw-promptforge.toml"):
            if cand.exists(): return cand
        if (cur / ".git").exists(): return None  # stop at project root
        if cur.parent == cur: return None        # filesystem root
        cur = cur.parent
```

## Phase 2 — config subcommand

`rw-promptforge config show [--json]` — prints each leaf with source tag.
`rw-promptforge config init` — writes scaffold TOML to `~/.config/rw-promptforge/`.
`rw-promptforge config schema --json` — dumps `RootConfig.model_json_schema()`.

## Phase 3 — CLI migration

| Step | Flag | Risk |
|------|------|------|
| 1 | `--ml-endpoint` | Low — new feature, no existing users |
| 2 | Sweep remaining 24 flags | Medium — regression risk |

For each flag: keep click decorator, but the *default* becomes `None`, and click only produces an override dict entry when user passed it.

## Phase 4 — Deprecation

- Emit `UserWarning` on `RW_IE_ENDPOINT`, `RW_PROMPTFORGE_EMBEDDING_MODEL` for v0.2.x
- Remove in v0.3.0

## Phase 5 — Tests (~250 LOC)

- defaults equivalence test
- per-layer loading tests
- deep-merge + provenance tests
- CLI override priority tests
- TOML malformed file graceful handling
- walk-up boundary cases (cwd = root, cwd deep inside, no `.git` present)

## Risks

| Risk | Mitigation |
|------|------------|
| Phase 3 regression | Snapshot current behavior, diff against config-driven output on fixed args |
| Pydantic dependency weight | Justify: single-source truth is worth ~10MB install |
| Walk-up threading | Path resolution is synchronously scoped to `load_config`; no caching |
| Timezone/system POSIX vs Windows | TOML loader uses `pathlib.Path` — no platform-specific concerns |

## Verification

```bash
pip install -e .  # installs pydantic etc.
pytest tests/configs/ -v
rw-promptforge config show --json | jq .ml.endpoint
rw-promptforge config init && cat ~/.config/rw-promptforge/config.toml
```
