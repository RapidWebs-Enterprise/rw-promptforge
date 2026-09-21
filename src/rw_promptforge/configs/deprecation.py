"""Deprecation warnings for old env variables.

Called by the DeprecatedEnvSource during config loading.
Each var warns at most once per process.
"""

from __future__ import annotations

import os
import warnings

_WARNED: set[str] = set()

# old env var → (new_section, new_field)
_DEPRECATED_VARS: dict[str, tuple[str, str]] = {
    "RW_IE_ENDPOINT": ("ml", "endpoint"),
    "RW_PROMPTFORGE_EMBEDDING_MODEL": ("ml", "embedding_model"),
    "RW_IE_API_KEY": ("ml", "api_key"),
    "RW_IE_RERANK_MODEL": ("ml", "rerank_model"),
}


def load_deprecated_env() -> dict[str, dict[str, str]]:
    """Return a nested dict of deprecated env-vars mapped to new keys.

    Emits a DeprecationWarning once per process per key.
    """
    out: dict[str, dict[str, str]] = {}
    for old, (section, field) in _DEPRECATED_VARS.items():
        if old in os.environ:
            if old not in _WARNED:
                warnings.warn(
                    f"{old} is deprecated; use RW_PROMPTFORGE_{section.upper()}__{field.upper()}. "
                    "Will be removed in v0.3.0.",
                    DeprecationWarning,
                    stacklevel=3,
                )
                _WARNED.add(old)
            out.setdefault(section, {})[field] = os.environ[old]
    return out


def reset_warnings() -> None:
    """Clear the warned set (used by tests)."""
    _WARNED.clear()
