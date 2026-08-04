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
pip install -e ".[dev]"
rw-promptforge optimize skill skills/systematic-debugging/SKILL.md
rw-promptforge optimize soul /path/to/SOUL.md
```

## Architecture

```
CLI (click) → Target (SOUL/Skill) → Evaluator → Datastore → Reflector
                                                                ↓
                                                         Provider (OpenAI-compat)
```

## License

MIT — RapidWebs Enterprise LLC