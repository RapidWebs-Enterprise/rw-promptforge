"""Layered configuration for rw-promptforge.

Public API:

    from rw_promptforge.configs import load_config, RootConfig
    config = load_config()  # merged from all 6 layers

Precedence (low → high):
1. Pydantic defaults in models.py
2. User TOML     ~/.config/rw-promptforge/config.toml
3. Project TOML  ./config.toml or ./config/rw-promptforge.toml (walk-up to .git)
4. .env file     ./.env with raw-key mapping
5. Env vars      RW_PROMPTFORGE_*
6. CLI overrides (passed explicitly to load_config)

See docs/specs/spec-layered-config.md and ADR-013 (+amendment) for rationale.
"""

from rw_promptforge.configs.core import get_provenance, load_config
from rw_promptforge.configs.models import (
    LLMConfig,
    MLConfig,
    OptimizerConfig,
    RootConfig,
    SessionDBConfig,
)

__all__ = [
    "LLMConfig",
    "MLConfig",
    "OptimizerConfig",
    "RootConfig",
    "SessionDBConfig",
    "get_provenance",
    "load_config",
]
