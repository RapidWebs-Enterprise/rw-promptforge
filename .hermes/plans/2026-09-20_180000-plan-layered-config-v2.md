---
name: Layered Configuration System (v2 — post-audit)
description: 6-layer pydantic-settings config chain, addressing all audit findings
status: proposed
related_spec: docs/specs/spec-layered-config.md
related_adrs: [013]
audits:
  forward: docs/.hermes/plans/audits/spec-layered-config-forward-audit.md
  reverse: docs/.hermes/plans/audits/spec-layered-config-reverse-audit.md
---

# Plan v2 — Layered Configuration System

## Audit Resolution Summary

| Audit | Verdict | Findings | Action |
|-------|---------|----------|--------|
| Forward | Spec mostly accurate, plan has 3 blocking gaps | 6 discrepancies, 6 gaps | All addressed in Δ below |
| Reverse | Spec is a design sketch, not implementation contract | 11 gaps, 6 errors, 8 risks | All addressed in Δ below |

**Major architecture change:** Adopt `pydantic-settings` with custom sources instead of hand-rolling ~400 LOC of loaders.

---

## Δ Changes from v1

### Decision Change: pydantic-settings (was: hand-rolled loaders)

**Reverse audit R2 is correct.** Hand-rolling costs ~400 LOC (env_loader + file_loader + core + cli_loader) against ~80 LOC of custom `PydanticBaseSettingsSource` subclasses on a battle-tested base.

**v1 reasons for hand-roll** were: TOML-only, custom walk-up, provenance tracking. **pydantic-settings handles all three** via `settings_customise_sources()` + custom classes. The supposed "simplification by consistency" argument doesn't hold when the hand-rolled version is the one re-introducing edge cases.

**Implementation:**
```python
# configs/core.py — replaces ~400 LOC of hand-rolled loaders
from pydantic_settings import (
    BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict,
)

class RootConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RW_PROMPTFORGE_",
        env_nested_delimiter="__",
        extra="forbid",  # G2 fix — reject unknown keys
        hide_input_in_errors=True,  # G1 fix — redact secrets in errors
    )
    version: int = 1  # G10 fix — schema versioning
    optimizer: OptimizerConfig = Field(default_factory=OptimizerConfig)
    ml: MLConfig = Field(default_factory=MLConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    session_db: SessionDBConfig = Field(default_factory=SessionDBConfig)

    @classmethod
    def settings_customise_sources(
        cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings,
    ):
        # Precedence: high → low (pydantic-settings chains in order)
        return (
            init_settings,          # 1. CLI overrides (kwarg)
            env_settings,           # 2. RW_PROMPTFORGE_* env vars
            CwdDotEnvSource(cls),   # 3. .env file (raw keys, cwd-based)
            ProjectTomlSource(cls), # 4. ./config.toml via walk-up
            UserTomlSource(cls),    # 5. ~/.config/rw-promptforge/config.toml
            # defaults come from field defaults (lowest)
        )
```

Each custom source is a ~30-line PydanticBaseSettingsSource subclass. Provenance tracking is an additional mixin attached to each source (records `(leaf_path, source_name)` tuples in a side-channel).

### Fix: SecretStr for All Secret Fields (G1)

```python
from pydantic import SecretStr

class LLMConfig(BaseSettings):
    api_key: SecretStr = Field(default=SecretStr(""))
    # ...
class TelegramConfig(BaseSettings):  # if reintroduced
    bot_token: SecretStr = Field(...)
```

`config show` renders `api_key = "**********"` while provenance still says where it came from (G3 fix).

### Fix: `.env` cwd vs project-root contradiction (E5)

**Decision:** **cwd-based** `.env`, matching ADR-013. This differs from rw_telebot (which loads from package root) but is the more common CLI behavior. We document the difference explicitly.

### Fix: Walk-Up Worktree & Nested-Repo Handling (E3, E4)

Adopt REC3 verbatim:

```python
def find_project_config(start: Path) -> Path | None:
    cur = start.resolve()
    seen_git_dirs: set[Path] = set()
    while True:
        git_path = cur / ".git"
        if git_path.exists():
            # Resolve worktree: .git file points at real gitdir
            if git_path.is_file():
                content = git_path.read_text().strip()
                if content.startswith("gitdir: "):
                    real = content.split(":", 1)[1].strip()
                    git_path = (cur / real).resolve() if not Path(real).is_absolute() else Path(real)
            resolved = git_path.resolve()
            if resolved in seen_git_dirs:
                # Nested unrelated repo — keep walking up
                pass
            else:
                seen_git_dirs.add(resolved)
                # Check for config at this level, then stop
                for cand in (cur / "config.toml", cur / "config" / "rw-promptforge.toml"):
                    if cand.exists():
                        return cand
                return None
        if cur.parent == cur:
            return None
        cur = cur.parent
```

### Fix: Atomic `config init` (G9)

```python
def config_init() -> Path:
    config_dir = Path.home() / ".config" / "rw-promptforge"
    config_dir.mkdir(parents=True, exist_ok=True)
    final = config_dir / "config.toml"
    tmp = final.with_suffix(".toml.tmp")
    tmp.write_text(_render_default_toml())
    tmp.replace(final)  # POSIX atomic
    return final
```

### Fix: Tilde Expansion in Paths (G11)

```python
class SessionDBConfig(BaseSettings):
    path: Path = Field(default_factory=lambda: Path("~/.rw-promptforge/session.db"))

    def model_post_init(self, __context):
        self.path = self.path.expanduser()
```

### Fix: Click CLI Mapping — Explicit Allowlist (E6, R3)

```python
# cli_loader.py
CLI_OVERRIDE_MAP: dict[str, tuple[str, str]] = {
    # click_param_name → (config_section, config_field)
    "endpoint":              ("llm", "endpoint"),
    "model":                 ("llm", "model"),
    "provider":              ("llm", "provider"),
    "max_rounds":            ("optimizer", "max_rounds"),
    "semantic_threshold":    ("optimizer", "semantic_threshold"),
    "gain_threshold":        ("optimizer", "gain_threshold"),
    "stability_threshold":   ("optimizer", "stability_threshold"),
    "min_rounds":            ("optimizer", "min_rounds"),
    "beam_size":             ("optimizer", "beam_size"),
    "frontier_size":         ("optimizer", "frontier_size"),
    "convergence_threshold": ("optimizer", "convergence_threshold"),
    "max_growth":            ("optimizer", "max_growth"),
    "ml_mode":               ("ml", "enabled"),
    "ml_endpoint":           ("ml", "endpoint"),
    "min_traces":            ("ml", "min_traces"),
}

def cli_overrides_from_locals(locals_ns: dict) -> dict:
    """Build nested override dict from click locals(); ignore non-allowlisted keys."""
    result: dict = {}
    for key, value in locals_ns.items():
        if key not in CLI_OVERRIDE_MAP or value is None:
            continue
        section, field = CLI_OVERRIDE_MAP[key]
        result.setdefault(section, {})[field] = value
    return result
```

**Explicit, greppable, typo-proof.** New CLI flag → new dict entry. Miss one → loud crash (KeyError) not silent ignore.

### Fix: Deprecation Mechanism (R5)

```python
# env_loader.py
_DEPRECATED_ENV = {
    "RW_IE_ENDPOINT": "RW_PROMPTFORGE_ML__ENDPOINT",
    "RW_PROMPTFORGE_EMBEDDING_MODEL": "RW_PROMPTFORGE_ML__EMBEDDING_MODEL",
    "RW_IE_API_KEY": "RW_PROMPTFORGE_ML__API_KEY",
    "RW_IE_RERANK_MODEL": "RW_PROMPTFORGE_ML__RERANK_MODEL",
}
_warned: set[str] = set()  # process-level — warn once per run

def load_deprecated_env() -> dict:
    out = {}
    for old, new in _DEPRECATED_ENV.items():
        if old in os.environ:
            if old not in _warned:
                warnings.warn(
                    f"{old} is deprecated. Use {new} instead. Removed in v0.3.0.",
                    DeprecationWarning, stacklevel=3,
                )
                _warned.add(old)
            out[new] = os.environ[old]
    return out
```

### Fix: TILDE-Expanded Deprecation List (Forward #6)

Complete list in `_DEPRECATED_ENV` above includes all 4 currently-used ad-hoc vars.

### Fix: Additional Dependencies (Forward #1)

```toml
[project.dependencies]
pydantic = ">=2.0"
pydantic-settings = ">=2.0"
python-dotenv = ">=1.0"
tomli = ">=2.0"          # Python 3.10 compat (3.11+ has tomllib)
tomli-w = ">=1.0"
```

For `requires-python = ">=3.10"`: use `tomli` read / `tomli-w` write. If we ever bump to `>=3.11`, drop `tomli` in favor of stdlib `tomllib`.

### Fix: `schema_export.py` Added (Forward #5, Plan §3)

Added to Phase 1 file list. Renders `RootConfig.model_json_schema()` with secrets fields marked as `writeOnly: true`.

### Fix: `rerank_model` Default Inconsistency (Forward #1)

**Decision:** Default is `"ms-marco-MiniLM-L-6-v2"` everywhere. Add the same default to `Provider.__init__` (not just `from_ml_env()`), so `RootConfig.ml.rerank_model` matches. This is a **minor behavior fix** bundled with the config work — it makes the model consistent whether accessed via chat-LLM provider or ML provider.

### Fix: 4 Unmapped CLI Fields (Forward #3)

**Decision:** **Do not add CLI flags** for `ml.embedding_model`, `ml.rerank_model`, `ml.cache_maxsize`. These are:
- Inference-engine-specific (as opposed to user-tunable per run)
- Rarely changed (model swap is an ops decision, not per-optimization decision)

Document as **"TOML/env-only"** in spec §4.4. For `ml.enabled`, we keep `--ml-mode` as the flag (maps to `ml.enabled=True`); there is no `--no-ml-mode` — user unsets the bit by simply omitting the flag or setting `ml.enabled = false` in TOML.

### Fix: `config show --export` Redaction (G1, G5)

```
rw-promptforge config show           # Merged config with provenance; secrets redacted
rw-promptforge config show --json    # Machine-readable; secrets as "***"
rw-promptforge config show --export  # Writeable TOML; secrets fields omitted entirely
rw-promptforge config schema --json  # JSON Schema; secrets with writeOnly: true
```

### Fix: Test Matrix Expansion (R7 + REC10 additions)

| # | Test |
|---|------|
| 1 | `test_defaults_root_config()` |
| 2 | `test_toml_user_level_only()` |
| 3 | `test_project_beat_user()` |
| 4 | `test_env_beats_files()` |
| 5 | `test_cli_beats_env()` |
| 6 | `test_dotenv_mapped()` |
| 7 | `test_nested_deep_merge()` |
| 8 | `test_provenance_attribution()` |
| 9 | `test_config_init_writes_valid_toml()` |
| 10 | `test_invalid_value_rejected()` |
| 11 | `test_cli_env_toml_triple_conflict()` |
| 12 | `test_secret_redaction_in_config_show()` |
| 13 | `test_worktree_git_file_boundary()` |
| 14 | `test_nested_unrelated_git_repos()` |
| 15 | `test_empty_and_comment_only_toml()` |
| 16 | `test_atomic_config_init_concurrent()` |
| 17 | `test_unknown_key_rejected()` |
| 18 | `test_deprecation_warning_once_per_process()` |
| 19 | `test_dotenv_raw_key_mapping()` |
| 20 | `test_config_schema_json_clean()` |
| 21 | `test_tilde_expansion_in_paths()` |
| 22 | `test_windows_path_normalization()` (CI-only) |

---

## Revised File Layout

```
src/rw_promptforge/configs/
├── __init__.py                # export load_config, RootConfig
├── models.py                  # Pydantic models (was layered_models.py)
├── core.py                    # pydantic-settings integration + provenance
├── sources/
│   ├── __init__.py
│   ├── cli_source.py          # CLI_OVERRIDE_MAP handling
│   ├── dotenv_source.py       # cwd-based .env, raw key mapping
│   ├── project_toml_source.py # walk-up TOML (worktree-aware)
│   └── user_toml_source.py    # ~/.config/rw-promptforge/config.toml
├── deprecation.py             # _DEPRECATED_ENV mapping + warned set
└── schema_export.py           # JSON Schema for config schema --json

CLI:
└── cli_config.py              # config show/init/schema subcommands
```

(Removed: `env_loader.py`, `file_loader.py`, `cli_loader.py` — replaced by pydantic-settings custom sources ~40 LOC each.)

## Revised Effort Estimate

| Phase | Original | Revised | Basis |
|-------|----------|---------|-------|
| P1 — models + sources + core | 450 LOC, 2h | 280 LOC, 1.5h | pydantic-settings replaces ~400 LOC hand-rolled |
| P2 — config subcommand | 150 LOC, 1h | 150 LOC, 1h | unchanged |
| P3 — CLI migration | 80 LOC, 1h | 200 LOC, 2h | 26 flags × map + verify, explicit allowlist |
| P4 — deprecation | 60 LOC, 0.5h | 60 LOC, 0.5h | unchanged |
| P5 — tests (22) | 250 LOC, 1.5h | 350 LOC, 2h | expanded matrix |
| Docs + ADR | 120 LOC, 0.5h | 120 LOC, 0.5h | unchanged |
| **Total** | **1050 LOC, 6h** | **1160 LOC, 7.5h** | More tests, fewer loaders; pydantic-settings pays off |

**Reverse audit estimate: 12-16h. Revised: 7.5h.** The 4-8h delta comes from pydantic-settings absorbing the hand-rolled loader complexity.
