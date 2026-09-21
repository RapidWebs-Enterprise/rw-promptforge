# rw-promptforge: Simplify-Reflect-Evolve

**rw-promptforge** is a standalone CLI that iteratively optimizes prompts and skills
by reflecting on execution traces. It's a lightweight alternative to DSPy/GEPA for
the specific use case of refining text artifacts that control LLM agent behavior.

**Principle:** One reflection call per iteration. No population tournaments.
The LLM reads what went wrong → proposes a targeted fix → we verify.

## Status

🟡 Pre-alpha (`rw_` prefix per RapidWebs naming convention)

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Basic optimization
rw-promptforge optimize skill skills/systematic-debugging/SKILL.md
rw-promptforge optimize soul /path/to/SOUL.md

# With ML enhancements (clustering, classification, reranking via RW_InferenceEngine)
rw-promptforge optimize skill skills/foo/SKILL.md --ml-mode
```

## Configuration System

`rw-promptforge` uses a **6-layer configuration chain** (lowest to highest priority):

1. **Pydantic defaults** (shipped in `src/rw_promptforge/configs/models.py`)
2. **User TOML** — `~/.config/rw-promptforge/config.toml`
3. **Project TOML** — `./config.toml` or `./config/rw-promptforge.toml` (walk-up from cwd to first `.git` root)
4. **`.env`** at cwd (raw keys, e.g., `OPENAI_API_KEY`)
5. **Environment variables** prefixed with `RW_PROMPTFORGE_` (nested keys separated by `__`)
6. **CLI flags** (highest)

### Quick Config Commands

```bash
# Scaffold a user-level config
rw-promptforge config init

# See the merged result with provenance
rw-promptforge config show

# Or as JSON
rw-promptforge config show --json

# Export sanitized TOML (no secrets) for sharing
rw-promptforge config show --export > shared-config.toml

# Set a value (JSON-parsed, dot notation)
rw-promptforge config set optimizer.max_rounds 7
rw-promptforge config set ml.endpoint "http://custom:8300"

# Validate config + test RW_InferenceEngine connectivity
rw-promptforge config doctor

# Print JSON Schema for tooling
rw-promptforge config schema --json > rw-promptforge.schema.json
```

### Profiles

Named profiles in `~/.config/rw-promptforge/config.toml`:

```toml
version = 1

[optimizer]
max_rounds = 3

[ml]
enabled = false
endpoint = "http://srv1:8300"

[profiles.dev]
optimizer = { max_rounds = 10 }
ml = { enabled = true, endpoint = "http://dev:8300" }

# Activate profile
active_profile = "dev"
```

Profiles override only the fields they specify; other fields fall back to the base config.
CLI flags always win over profiles.

### ML Enhancements (Optional)

```bash
pip install "rw-promptforge[ml]"  # numpy, scikit-learn, hdbscan, imbalanced-learn
```

When `--ml-mode` is enabled (or `ml.enabled = true` in config):

- **Embedding recall** via RW_InferenceEngine `/v1/embeddings` (BGE 384-dim)
- **HDBSCAN clustering** of failure traces → systemic/recurring/new_pattern labels
- **HistGradientBoosting** classifier for failure pattern prediction
- **Cross-encoder reranking** via RW_InferenceEngine `/v1/rerank`

All ML components gracefully fall back to token-based methods if dependencies or endpoints are unavailable.

### Environment Variables

Prefixed `RW_PROMPTFORGE_`, nested keys split on `__`:

```bash
export RW_PROMPTFORGE_ML__ENABLED=true
export RW_PROMPTFORGE_ML__ENDPOINT=http://custom:8300
export RW_PROMPTFORGE_OPTIMIZER__MAX_ROUNDS=10
export RW_PROMPTFORGE_LLM__MODEL=claude-3-haiku
```

## Architecture

```
CLI (click) → Target (SOUL/Skill) → Evaluator → Datastore → Reflector
                                                                ↓
                                                         Provider (OpenAI-compat)
```

## License

MIT — RapidWebs Enterprise LLC