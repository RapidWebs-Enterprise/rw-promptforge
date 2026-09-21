# REVERSE AUDIT — spec-layered-config.md & plan-layered-config.md

**Auditor:** Hermes subagent (reverse-audit role)  
**Date:** 2026-09-20  
**Target Spec:** `/home/sysop/Workspaces/rw-promptforge/docs/specs/spec-layered-config.md`  
**Target Plan:** `/home/sysop/Workspaces/rw-promptforge/.hermes/plans/2026-09-14_210000-plan-layered-config.md`  
**Reference Implementation:** `rw_telebot/src/rw_telebot/configs/` (1,307 LOC across 11 files)

---

## EXECUTIVE SUMMARY

| Category | Count | Severity |
|----------|-------|----------|
| **GAPS** (spec missed entirely) | 11 | 3 Critical, 5 High, 3 Medium |
| **ERRORS** (spec got wrong) | 6 | 2 Critical, 2 High, 2 Medium |
| **RISKS** (plan underestimated) | 8 | 2 Critical, 3 High, 3 Medium |
| **RECOMMENDATIONS** | 14 | — |

**Bottom line:** The spec is a solid *design sketch* but fails as an implementation contract. The plan's 6h estimate is **unrealistic** — rw_telebot's equivalent took ~1,307 LOC (not 1,050) across 11 files with substantial complexity the spec glosses over. Expect **12–16h** for a production-ready implementation.

---

## GAPS — Things the Spec Missed Entirely

### G1. CRITICAL: No `SecretStr` for API Keys — Secrets Leak in `config show`
- **Spec §4.2** defines `api_key: str = ""` in `LLMConfig` and `TelegramConfig.bot_token: str = Field(...)` — plain strings.
- **Spec §4.6** says `config show` prints "each leaf with [source] annotations" — **this will dump API keys and bot tokens to stdout/logs** unless explicitly redacted.
- **rw_telebot pattern** (layered_models.py:39–42): `bot_token: str = Field(..., description="Telegram bot token (required).")` — *also plain string*. This is a known gap in the reference implementation too.
- **Fix required:** Use `pydantic.SecretStr` for all secret fields. Add `model_config = ConfigDict(hide_input_in_errors=True)` to root. Implement redaction in `config show` provenance printer.

### G2. CRITICAL: TOML Injection / Arbitrary Key Injection
- **Spec §4.3** env mapping: `RW_PROMPTFORGE_ML__ENABLED=1 → ml.enabled = True` — uses `__` as nest delimiter.
- **Spec §4.5** CLI mapping: "converts non-None values to nested dict, which is deep-merged" — no schema validation before merge.
- **Attack:** `RW_PROMPTFORGE___IMPORT___OS=1` or `RW_PROMPTFORGE_ML__ENDPOINT=http://evil.com` — but deeper: TOML loader (§4.1 `file_loader.py`) does `toml.load(f)` with **no allowlist of known keys**. A malicious `config.toml` with `[malicious] arbitrary = "keys"` gets deep-merged into `RootConfig(**merged)` — Pydantic v2 **ignores extra fields by default** (`extra='ignore'`), so this silently succeeds but pollutes the merged dict passed to provenance tracking.
- **Fix required:** Set `model_config = ConfigDict(extra='forbid')` on `RootConfig` and all sub-models. Validate TOML keys against model schema *before* merge.

### G3. CRITICAL: No Provenance for Redacted Secrets
- **Spec §4.6** provenance design: "Each layer returns `(data: dict, source: str)`... `config show` uses this to print source."
- **Missing:** When a secret field (API key, bot token) is redacted in `config show`, the provenance must still show *which layer provided it* (e.g., `[env RW_PROMPTFORGE_LLM__API_KEY]`) without printing the value. Spec doesn't address this.

### G4. HIGH: No Handling for CLI Flag Collisions (Short vs Long Form)
- **Spec §4.4** says "keep existing `@click.option` decorators... `map_cli_to_config(locals(), schema=CLI_OVERRIDE_SCHEMA)`"
- **Problem:** Click supports both `--semantic-threshold` and `-s` (if defined). `locals()` contains the *final parsed value*, not which flag was used. If user passes both `--semantic-threshold 0.9 -s 0.8`, Click's last-wins applies but provenance can't distinguish. Spec doesn't define expected behavior.

### G5. HIGH: No `config show --export` Redaction Guarantee
- **Spec §3 (Non-Goals)**: "Secret management. Secrets stay in env vars / `.env`; the loader must never write them to the merged TOML we ship back to users as part of `config show --export`."
- **Gap:** This is stated as a non-goal but **no mechanism is specified**. The `--export` subcommand doesn't exist in the spec's command list (§4.5 only lists `show`, `init`, `schema`). If added later, it needs explicit redaction logic.

### G6. HIGH: No Config File Integrity / Tamper Detection
- **Spec §4.1** loads TOML from `~/.config/...`, `./config.toml`, `./config/rw-promptforge.toml` — all user-writable.
- **Missing:** No hash verification, no "this config was modified since last run" warning. For a CLI that may run in CI/CD, silent config drift is a supply-chain risk.

### G7. HIGH: No Migration Path for `Hyperparams` Dataclass (spec §1)
- **Spec §1** identifies `Hyperparams` dataclass in `optimizer.py` as a 4th config mechanism.
- **Spec §4.2** models don't include a `Hyperparams` equivalent — fields like `beam_size`, `frontier_size`, `convergence_threshold` are in `OptimizerConfig` but the *dataclass itself* is not addressed.
- **Plan §6 Step 6** says "Delete ad-hoc env reads from `provider.py`" but says nothing about `optimizer.py`'s module-level `Hyperparams`.

### G8. MEDIUM: No Windows Path Handling in Walk-Up Search
- **ADR-013 §3** walk-up uses `Path.home() / ".config" / "rw-promptforge"` and `cur.parent == cur` for root detection.
- **Gap:** On Windows, `Path.home()` works but filesystem root is `C:\` not `/`. `cur.parent == cur` works on both but `Path.home()` may be `C:\Users\name`. Not tested. Spec assumes POSIX.

### G9. MEDIUM: No Concurrency Safety for `config init`
- **Spec §4.5** `config init` writes to `~/.config/rw-promptforge/config.toml`.
- **Gap:** If two processes run `config init` simultaneously, TOML corruption possible. No file locking, no atomic write (write to temp + rename).

### G10. MEDIUM: No Schema Versioning in Config Files
- **Spec §4.2** models will evolve. No `version` field in `RootConfig` or config file format. Future breaking changes (field rename, type change) will silently produce wrong values or validation errors with no migration hint.

### G11. MEDIUM: `SessionDBConfig.path` Uses Tilde Expansion Inconsistently
- **Spec §4.2**: `path: Path = Path("~/.rw-promptforge/session.db")`
- **rw_telebot pattern** (layered_models.py:97): `sqlite_db_path: Path = Field(default=Path("./state/telebot_state.sqlite"))` — relative, resolved at runtime in `ensure_directories()`.
- **Gap:** Tilde in Pydantic default is not expanded automatically. Must expand in `model_post_init` or `ensure_directories`. Spec doesn't mention this.

---

## ERRORS — Things the Spec Got Wrong

### E1. CRITICAL: Precedence Order Contradiction (Spec vs ADR-013)
- **Spec §2 (Goals) §1** precedence: 1=Pydantic defaults, 2=User TOML, 3=Project TOML, 4=`.env`, 5=Env vars, 6=CLI
- **ADR-013 §24** precedence: 1=Pydantic defaults, 2=User TOML, 3=Project TOML, 4=`.env` at cwd, 5=`RW_PROMPTFORGE_*` env vars, 6=CLI flags
- **Plan §1 (Core loader sketch)** code order: defaults → user_toml → project_toml → dotenv → env → cli
- **ERROR:** Spec §2 says ".env file mapped keys" at layer 4, but **ADR-013 says ".env file at cwd" at layer 4**. These differ: "mapped keys" implies the `.env` keys go through the same `RW_PROMPTFORGE_` prefix mapping as env vars (Spec §4.3), but ADR-013 says `.env` uses *raw keys* (like `TELEGRAM_TOKEN` not `RW_PROMPTFORGE_TELEGRAM_TOKEN`). **rw_telebot does raw-key mapping for .env** (env_loader.py:140–145 `_DOTENV_KEY_MAP`). Spec is wrong; ADR-013 matches reference impl.

### E2. CRITICAL: Default Value Mismatch — `semantic_threshold` Example
- **Spec §4.2** `OptimizerConfig`: `semantic_threshold: float = 0.95`
- **Plan §1 model sketch**: `semantic_threshold: float = Field(default=0.95, ge=0.0, le=1.0)`
- **Current CLI (cli.py:71–75)**: `@click.option("--semantic-threshold", default=0.95, type=float, ...)`
- **rw_telebot reference** has NO `semantic_threshold` — it's a promptforge-specific parameter.
- **The bug:** Spec says "Net behavior change: none when no flags/files set — every default in Pydantic matches current hardcodes" (§4.4). But **current hardcode is in Click default**, not in a Pydantic model. If user runs v0.3.0 with *no config file, no env, no flags*, they get Pydantic default 0.95 — **same value, correct**. BUT: if user *had* a v0.2.x config mechanism (none exists for this flag), behavior would differ. The claim "matches current hardcodes byte-for-byte" is **untestable** because there's no prior persistent config for these flags. The spec asserts backward-compat for a feature that didn't persist before.

### E3. HIGH: `find_project_config` Stops at `.git` Dir — Breaks Worktrees
- **Plan §1 (Walk-up discovery)**: 
```python
if (cur / ".git").exists(): return None  # stop at project root
```
- **ADR-013 §16–19**: "Stop when we hit `.git/` (project root)..."
- **ERROR:** In a **git worktree**, `.git` is a **FILE** (e.g., `.git` containing `gitdir: /path/to/main/.git/worktrees/xxx`), not a directory. `(cur / ".git").exists()` returns `True` but it's a file — the walk stops at the worktree root instead of continuing to the main repo root. This breaks config discovery for worktree users.

### E4. HIGH: Walk-Up Search Doesn't Handle Nested Unrelated Git Repos
- **ADR-013 rationale:** "lets a per-project config.toml at repo root override ~/level config regardless of where the user invokes the CLI inside the project tree."
- **Scenario:** User has `/home/user/projectA/.git` (main repo) and `/home/user/projectA/subdir/.git` (submodule OR separate unrelated repo initialized inside). Running from `/home/user/projectA/subdir/deep`:
  - Walk hits `subdir/.git` first (unrelated repo) → stops → never finds `projectA/config.toml`.
- **Spec/Plan/ADR** all say "stop at `.git` boundary" — **this is the wrong boundary**. Should stop at the *first* `.git` found walking up, but that's exactly the bug above. The correct behavior is ambiguous and untested.

### E5. MEDIUM: `load_dotenv_file()` in rw_telebot Loads from Project Root, Not CWD
- **Plan §1 core.py `_load_dotenv_file()`**: 
```python
project_root = Path(__file__).parent.parent.parent.parent
dotenv_path = project_root / ".env"
```
- **Spec §4.1** says "Project-level TOML: `./config.toml` then `./config/rw-promptforge.toml`" — implies cwd-relative.
- **ADR-013 §29** says "`.env` file at cwd".
- **Reference impl (rw_telebot) loads from PROJECT ROOT (where core.py lives), not cwd.** This is a deliberate design choice (so `.env` travels with the installed package), but Spec and ADR say cwd. **Contradiction.**

### E6. MEDIUM: CLI Override Schema Not Defined
- **Spec §4.4** references `CLI_OVERRIDE_SCHEMA` but never defines it.
- **Plan §3** says "For each flag: keep click decorator, but the *default* becomes `None`, and click only produces an override dict entry when user passed it."
- **Missing:** How does `map_cli_to_config` know which `locals()` keys are config overrides vs. other parameters (e.g., `path`, `target_type`, `output`)? No schema/allowlist defined. rw_telebot cli_loader.py uses argparse with explicit `--telegram-bot-token` etc. — promptforge has 26+ Click options, many not config-related.

---

## RISKS — Things the Plan Underestimated

### R1. CRITICAL: Time Estimate — 6h vs Reality (~12–16h)
| Component | Spec Estimate | rw_telebot Actual | Delta | Notes |
|-----------|---------------|-------------------|-------|-------|
| Models + loaders + core | ~450 LOC, 2h | 718 LOC (layered_models + core + env + file + cli) | +268 LOC | Spec omits validators, type conversion, explicit env maps |
| CLI integration | ~80 LOC, 1h | N/A (rw_telebot uses argparse, not Click) | — | Click `locals()` mapping is **harder** than argparse.Namespace |
| `config` subcommand | ~150 LOC, 1h | N/A (rw_telebot has no `config` cmd) | — | New feature, not in reference |
| Tests | ~250 LOC, 1.5h | rw_telebot has 0 config tests (!) | — | Spec's 10-test matrix is minimal |
| **Total** | **~1050 LOC, 6h** | **~1307 LOC (configs/ only)** | **+257 LOC** | **6h → 12–16h realistic** |

- rw_telebot's `configs/` is **1,307 LOC** across 11 files (not 7 files, not 1,050 LOC).
- Spec omits: validators (TelegramConfig has 2), explicit env-key mapping tables (env_loader.py:140–178), deep-merge with provenance tracking, CLI-to-config mapping for 26+ Click flags, `config show` provenance rendering, `config init` atomic write, `config schema` JSON export.
- **Plan Phase 3 (CLI migration)** estimates "~80 LOC edit" — but **26+ flags** each need: default=`None`, `is_flag` handling, `map_cli_to_config` allowlist entry, provenance tracking. Real: ~300–400 LOC.

### R2. CRITICAL: pydantic-settings vs Hand-Roll — Spec Chooses Hand-Roll Without Justification
- **Spec §7 Decision 3**: "Pydantic v2 for models... clean add to `[project.dependencies]`." No mention of `pydantic-settings`.
- **pydantic-settings** provides: `BaseSettings` with built-in env/file loading, `settings_customise_sources()` for custom precedence, `model_config` for env prefix/nested delimiter, `.env` loading, case-insensitive env vars, secrets dir support.
- **Hand-roll cost:** ~500 LOC of loader code (env_loader + file_loader + core + cli_loader) that pydantic-settings does in ~50 LOC.
- **Why hand-roll?** Only valid reasons: (a) TOML-only (pydantic-settings supports TOML via `pydantic-settings-toml` extra), (b) custom walk-up search, (c) provenance tracking. Spec doesn't articulate this tradeoff.
- **Risk:** Hand-rolled loader will have bugs (type conversion, edge cases) that pydantic-settings has already solved. **Recommendation: Use pydantic-settings with custom source for walk-up + provenance.**

### R3. HIGH: Click `locals()` Mapping Is Fragile
- **Plan §3** assumes `map_cli_to_config(locals(), schema=...)` works.
- **Reality:** Click decorators inject parameters into the function signature. `locals()` at function entry contains **all parameters including non-config ones** (`path`, `target_type`, `skill`, `output`, `save`, `learning_log`, etc.).
- **Schema allowlist must be exhaustive** — 26+ flags. Missing one = silent ignore. Extra one = potential crash if type mismatch.
- **rw_telebot uses argparse** — explicit `add_argument` per flag, then `map_cli_to_config` iterates `vars(args)`. **Click provides no equivalent namespace object.** You must manually construct the override dict. This is **not a 1h task**.

### R4. HIGH: Deep-Merge + Provenance Tracking Is Non-Trivial
- **Spec §4.6**: "Final merge walks layers in order and records which layer won per leaf key."
- **Plan §1 core.py sketch** uses `_deep_merge` that **loses provenance** — it returns merged dict only.
- **rw_telebot has NO provenance tracking** — this is a **new feature** not in reference impl.
- **Implementation requires:** A merge function that returns `(merged_dict, provenance_dict)` where `provenance_dict[leaf_path] = source_layer`. Must handle nested dicts, lists (replace vs merge?), None values. **Estimated 150–200 LOC alone.**

### R5. HIGH: Deprecation Warning Mechanism Underspecified
- **Spec §6 Step 6**: "emit deprecation warning for one release"
- **Plan §4**: "Emit `UserWarning` on `RW_IE_ENDPOINT`, `RW_PROMPTFORGE_EMBEDDING_MODEL` for v0.2.x"
- **Missing:** 
  - Where emitted? In `load_config()`? In `Provider.from_env()`? In `Provider.from_ml_env()`?
  - Only once per process? Per access? 
  - How does user suppress? `PYTHONWARNINGS`? 
  - What about `.env` file containing old keys? 
  - **No concrete mechanism** — just "emit warning." This will be inconsistent.

### R6. MEDIUM: No Test for Config Validation Error Messages
- **Spec §5 test matrix** has `test_invalid_value_rejected()` — "Pydantic catches type errors at startup."
- **Missing:** Test that error message is **actionable** — shows which layer provided bad value, suggests fix. Pydantic v2 errors are verbose; users need "Did you mean `ml.endpoint` in your config.toml?"

### R7. MEDIUM: No Test for Empty/Whitespace Config Files
- **Spec §5** tests: TOML malformed file graceful handling (mentioned in plan §5 but not spec).
- **Missing:** Empty file, file with only comments, file with `[section]` but no keys. `toml.load()` returns `{}` for empty — does deep-merge handle empty dict correctly? (Yes, but untested.)

### R8. MEDIUM: `config schema --json` Output Not Specified
- **Spec §4.5** lists `rw-promptforge config schema --json` — "JSON Schema export for external tooling."
- **Plan §2** says "dumps `RootConfig.model_json_schema()`."
- **Risk:** Pydantic's JSON Schema includes `$defs`, `title`, `default` for every field — **~2KB for RootConfig**. External tooling (e.g., VS Code YAML completion) expects a clean schema. May need `mode='serialization'` or manual pruning. Not addressed.

---

## RECOMMENDATIONS — Specific Actionable Fixes

### REC1: Use `SecretStr` for All Secrets — Immediate Spec Patch
```python
# In layered_models.py
from pydantic import SecretStr

class LLMConfig(BaseModel):
    api_key: SecretStr = Field(default=SecretStr(""), description="API key for LLM provider")
    # ...
class TelegramConfig(BaseModel):
    bot_token: SecretStr = Field(..., description="Telegram bot token (required)")
```

Add `model_config = ConfigDict(hide_input_in_errors=True)` to `RootConfig`.

### REC2: Use `pydantic-settings` with Custom Source for Walk-Up + Provenance
```python
# configs/core.py
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict
from typing import Tuple, Type

class RootConfig(BaseSettings):
    # ... all models as nested fields ...
    
    model_config = SettingsConfigDict(
        env_prefix="RW_PROMPTFORGE_",
        env_nested_delimiter="__",
        extra="forbid",  # CRITICAL: reject unknown keys
        env_file=None,   # we handle .env manually for provenance
    )
    
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,           # 1. CLI overrides (highest)
            env_settings,            # 2. RW_PROMPTFORGE_* env vars
            DotEnvSource(),          # 3. .env file (custom source)
            ProjectTomlSource(),     # 4. Project TOML (walk-up, custom)
            UserTomlSource(),        # 5. User TOML (custom)
            DefaultSource(),         # 6. Pydantic defaults (lowest)
        )
```
This replaces ~400 LOC of hand-rolled loaders with ~80 LOC of custom sources.

### REC3: Fix Walk-Up Search for Worktrees and Nested Repos
```python
def find_project_config(start: Path) -> Path | None:
    cur = start.resolve()
    seen_git_dirs = set()
    while True:
        git_path = cur / ".git"
        if git_path.exists():
            # Resolve worktree: if .git is a file, read gitdir
            if git_path.is_file():
                try:
                    content = git_path.read_text().strip()
                    if content.startswith("gitdir: "):
                        real_git = Path(content.split(":", 1)[1].strip())
                        if real_git.is_absolute():
                            git_path = real_git
                        else:
                            git_path = (git_path.parent / real_git).resolve()
                except Exception:
                    pass
            # Use real git dir as boundary key
            git_key = str(git_path.resolve())
            if git_key in seen_git_dirs:
                # Already stopped at this repo — continue up (nested unrelated repo)
                pass
            else:
                seen_git_dirs.add(git_key)
                return None  # Stop at FIRST git root encountered
        # ... check config files ...
```

### REC4: Define `CLI_OVERRIDE_SCHEMA` Explicitly in Spec
```python
# In cli_loader.py — EXPLICIT allowlist
CLI_OVERRIDE_SCHEMA = {
    "provider", "endpoint", "model", "max_rounds", "save", "learning_log",
    "post_mutation_verify", "hypothesis_first", "semantic_threshold",
    "gain_threshold", "stability_threshold", "min_rounds", "beam_size",
    "metric", "skill", "examples", "frontier_size", "convergence_threshold",
    "no_reverse_audit", "max_growth", "output", "on_overflow",
    "ml_mode", "ml_endpoint", "min_traces",
}
```
Only these keys from `locals()` become config overrides. All others ignored.

### REC5: Implement Provenance-Aware Deep Merge
```python
def deep_merge_with_provenance(
    layers: list[tuple[str, dict]]
) -> tuple[dict, dict[str, str]]:  # (merged, provenance: leaf_path -> source)
    merged = {}
    provenance = {}
    for source_name, layer in layers:
        _merge_layer(merged, provenance, layer, source_name, prefix="")
    return merged, provenance

def _merge_layer(merged, provenance, layer, source, prefix):
    for key, value in layer.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
            _merge_layer(merged[key], provenance, value, source, path)
        else:
            merged[key] = value
            provenance[path] = source
```

### REC6: Atomic Write for `config init`
```python
def config_init():
    config_dir = Path.home() / ".config" / "rw-promptforge"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.toml"
    tmp_path = config_path.with_suffix(".tmp")
    tmp_path.write_text(toml.dumps(default_config_dict))
    tmp_path.replace(config_path)  # atomic on POSIX
```

### REC7: Add Config Version Field
```python
class RootConfig(BaseModel):
    version: int = Field(default=1, description="Config schema version")
    # ...
```
Bump on breaking changes. Loader can warn/migrate.

### REC8: Expand Tilde in `model_post_init`
```python
class SessionDBConfig(BaseModel):
    path: Path = Field(default=Path("~/.rw-promptforge/session.db"))
    
    def model_post_init(self, __context):
        self.path = self.path.expanduser()
```

### REC9: Concrete Deprecation Mechanism
```python
# In env_loader.py
_DEPRECATED_ENV_VARS = {
    "RW_IE_ENDPOINT": "RW_PROMPTFORGE_ML__ENDPOINT",
    "RW_PROMPTFORGE_EMBEDDING_MODEL": "RW_PROMPTFORGE_ML__EMBEDDING_MODEL",
    "RW_IE_API_KEY": "RW_PROMPTFORGE_ML__API_KEY",
    "RW_IE_RERANK_MODEL": "RW_PROMPTFORGE_ML__RERANK_MODEL",
}

def load_env_vars() -> dict[str, Any]:
    env_vars = {}
    for key, value in os.environ.items():
        if key.startswith(ENV_PREFIX):
            config_key = env_to_config_key(key)
            env_vars[config_key] = value
        elif key in _DEPRECATED_ENV_VARS:
            import warnings
            warnings.warn(
                f"Environment variable {key} is deprecated. Use {_DEPRECATED_ENV_VARS[key]} instead. "
                f"Support will be removed in v0.3.0.",
                DeprecationWarning,
                stacklevel=2,
            )
            # Still map it for backward compat
            config_key = env_to_config_key(_DEPRECATED_ENV_VARS[key])
            env_vars[config_key] = value
    return env_vars
```

### REC10: Expand Test Matrix — Add These 12 Missing Tests
| Test | Purpose |
|------|---------|
| `test_cli_env_toml_triple_conflict()` | CLI > env > TOML > defaults for same key |
| `test_secret_redaction_in_config_show()` | `config show` masks `api_key`/`bot_token` but shows provenance |
| `test_secret_redaction_in_config_export()` | `config show --export` never writes secrets to file |
| `test_worktree_git_file_boundary()` | Walk-up stops at worktree `.git` file, reads main repo config |
| `test_nested_unrelated_git_repos()` | Subdir with own `.git` doesn't block parent config |
| `test_empty_and_comment_only_toml()` | Graceful handling of edge-case config files |
| `test_atomic_config_init_concurrent()` | Two parallel `config init` don't corrupt |
| `test_unknown_key_rejected()` | `extra='forbid'` catches typo in config.toml |
| `test_deprecation_warning_once_per_process()` | Old env var warning emitted only once |
| `test_dotenv_raw_key_mapping()` | `.env` `TELEGRAM_TOKEN` → `telegram.bot_token` (not prefixed) |
| `test_config_schema_json_clean()` | `config schema --json` produces usable schema for tooling |
| `test_tilde_expansion_in_paths()` | `~/...` paths expand correctly in all contexts |

### REC11: Add `config show --export` with Redaction to Spec
- Add to §4.5 command list
- Specify: writes merged TOML to stdout with `api_key = "***REDACTED***"` and `# source: env RW_PROMPTFORGE_LLM__API_KEY` comments

### REC12: Document Click→Config Mapping Algorithm in Spec
- Spec §4.4 must define: which `locals()` keys are config overrides (allowlist), how `is_flag=True` maps to `bool`, how `multiple=True` maps to `list`, how `default=None` vs unset distinguished.

### REC13: Windows Path Test in CI
- Add GitHub Actions job on `windows-latest` running config tests.

### REC14: Decision: Adopt `pydantic-settings` — Update Spec §7
Replace "Pydantic v2 for models" with:
> "Use `pydantic-settings>=2.0` with custom `PydanticBaseSettingsSource` subclasses for: (1) walk-up project TOML discovery, (2) `.env` raw-key mapping with provenance, (3) Click CLI override namespace. This replaces hand-rolled loaders (~400 LOC → ~80 LOC) while preserving custom precedence and provenance."

---

## VERIFICATION CHECKLIST FOR IMPLEMENTATION

Before declaring the layered config system "done", verify:

- [ ] All secret fields use `SecretStr` and are redacted in `config show` / `config show --export`
- [ ] `extra='forbid'` on all models — unknown keys in TOML/env/CLI raise validation error
- [ ] Walk-up search works with: worktree (`.git` file), nested unrelated git repos, no git repo, symlinked dirs
- [ ] Provenance tracked for every leaf key, displayed in `config show`
- [ ] `config init` uses atomic write (temp + rename)
- [ ] Deprecation warnings for old env vars emitted exactly once per process, map to new keys
- [ ] All 22 tests (10 spec + 12 REC10) pass
- [ ] `config schema --json` output validates against `jsonschema` and works in VS Code
- [ ] Click CLI override mapping handles all 26+ flags, ignores non-config params
- [ ] Default values match v0.2.x Click defaults byte-for-byte (snapshot test)
- [ ] Windows CI passes

---

## APPENDIX: rw_telebot configs/ LOC Breakdown (Reference)

| File | LOC | Purpose |
|------|-----|---------|
| layered_models.py | 304 | All config models + validators |
| core.py | 233 | Load chain, deep_merge, legacy Settings shims |
| env_loader.py | 255 | Env var + .env mapping, type conversion, explicit key tables |
| file_loader.py | 125 | TOML/YAML loading, config file discovery |
| cli_loader.py | 157 | Argparse → nested dict mapping |
| models.py | 156 | Legacy models (being phased out) |
| governance.py | 15 | Minimal |
| multi_query_config.py | 11 | Feature config |
| snapshot_config.py | 29 | Feature config |
| p2_memory_config.py | 21 | Feature config |
| __init__.py | 1 | Exports |
| **TOTAL** | **1,307** | |

**Spec estimates 1,050 LOC across 7 files** — undercounts by **257 LOC (24%)** and **4 files**. The missing files are feature configs (multi_query, snapshot, p2_memory) that promptforge may not need, but the core 5 loaders + models are **larger than estimated** due to validators, explicit mappings, and type conversion logic the spec omits.