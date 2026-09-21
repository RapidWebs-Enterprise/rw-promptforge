# Layered Configuration

`rw-promptforge` reads configuration from a 6-layer chain, lowest to highest precedence:

1. **Pydantic defaults** (shipped in `src/rw_promptforge/configs/models.py`)
2. **User TOML** — `~/.config/rw-promptforge/config.toml`
3. **Project TOML** — `./config.toml` or `./config/rw-promptforge.toml` (walk-up from cwd to first `.git` root)
4. **`.env`** at cwd (raw keys, e.g., `OPENAI_API_KEY`)
5. **Environment variables** prefixed with `RW_PROMPTFORGE_` (nested keys separated by `__`)
6. **CLI flags** (highest)

## Quick Start

```bash
# Scaffold a user-level config
rw-promptforge config init

# Edit it
nano ~/.config/rw-promptforge/config.toml

# See the merged result with provenance
rw-promptforge config show

# Or as JSON
rw-promptforge config show --json

# Export sanitized TOML (no secrets) for sharing
rw-promptforge config show --export > shared-config.toml
```

## Sections

```toml
# ~/.config/rw-promptforge/config.toml
version = 1

[optimizer]
max_rounds = 5
semantic_threshold = 0.95
gain_threshold = 0.02
stability_threshold = 0.05
min_rounds = 2
beam_size = 1
frontier_size = 5
convergence_threshold = 0.01
max_growth = 1.5
metric = "llm"          # llm | exact_match | rouge_l | rouge_2 | bleu | tool_call_valid

[ml]
enabled = false         # --ml-mode toggles this
endpoint = "http://srv1:8300"
embedding_model = "bge-small-en-v1.5"
rerank_model = "ms-marco-MiniLM-L-6-v2"
min_traces = 10
cache_maxsize = 10000
# api_key is read from env; do NOT commit

[llm]
provider = "openai"     # openai | openrouter | custom
endpoint = ""           # Or set OPENAI_ENDPOINT env var
model = "gpt-4o-mini"
# api_key via env

[session_db]
path = "~/.rw-promptforge/session.db"   # ~ is expanded at load
```

## Environment Variables

Prefixed `RW_PROMPTFORGE_`, nested keys split on `__`:

```bash
export RW_PROMPTFORGE_ML__ENABLED=true
export RW_PROMPTFORGE_ML__ENDPOINT=http://custom:8300
export RW_PROMPTFORGE_OPTIMIZER__MAX_ROUNDS=10
export RW_PROMPTFORGE_LLM__MODEL=claude-haiku-4-5
```

## Project Overrides

`rw-promptforge` walks up from the current working directory looking for either:

- `./config.toml`
- `./config/rw-promptforge.toml`

It stops at the first directory containing a `.git/` directory (with a `HEAD` file inside) or when a `.git` worktree file is resolved. **Worktrees are transparent** — the walk continues past them to the main repo root.

## Programmatic Use

```python
from rw_promptforge.configs import load_config
from rw_promptforge.optimizer import Optimizer

cfg = load_config()
opt = Optimizer(
    provider=my_provider,
    reflector=my_reflector,
    optimizer_config=cfg.optimizer,   # consumes all optimizer.* fields
)
```

## Deprecated Environment Variables

These still work but emit a `DeprecationWarning` once per process and will be removed in v0.3.0:

| Old | New |
|-----|-----|
| `RW_IE_ENDPOINT` | `RW_PROMPTFORGE_ML__ENDPOINT` |
| `RW_IE_API_KEY` | `RW_PROMPTFORGE_ML__API_KEY` |
| `RW_IE_RERANK_MODEL` | `RW_PROMPTFORGE_ML__RERANK_MODEL` |
| `RW_PROMPTFORGE_EMBEDDING_MODEL` | `RW_PROMPTFORGE_ML__EMBEDDING_MODEL` (same length, flagged for migration) |

## Security Notes

- All secret fields (`api_key`, `bot_token`) are `pydantic.SecretStr`. They're never printed by `config show` (use `config show --export` to explicitly write them out, which strips secrets anyway).
- All models use `extra="forbid"` — unknown keys in any config source fail fast with a clear error.
- `config init` writes atomically (temp + rename) — safe under concurrent invocations.
- `.env` is read with `dotenv_values()` (not `load_dotenv()`), so it does NOT pollute `os.environ`.

## Schema Export

Tooling can generate validation hints from the live schema:

```bash
rw-promptforge config schema --json > rw-promptforge.schema.json
```

Fields marked as `writeOnly: true` are secrets.
