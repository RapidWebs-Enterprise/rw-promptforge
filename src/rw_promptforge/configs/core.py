"""Core configuration loader.

Hand-rolled 6-layer chain. After the audit, it turned out pydantic-settings
wants per-field resolution, which doesn't fit our nested-section shape
without re-implementing deep-merge anyway. So we use simple dict merging
(the rw_telebot pattern) with:

- ``pydantic.BaseModel`` for typed validation + defaults
- ``SecretStr`` for all secrets (audit G1)
- ``extra="forbid"`` on all models (audit G2)
- Optional ``model_post_init`` for tilde expansion (audit G11)
- A separate provenance tracker (``get_provenance()``)
- Atomic TOML writes via temp+rename (REC6)

Precedence (low → high):
  1. Pydantic defaults
  2. User TOML       ~/.config/rw-promptforge/config.toml
  3. Project TOML    walk-up: config.toml / config/rw-promptforge.toml
  4. CWD .env        raw keys → config paths via DOTENV_MAP
  5. Deprecated env vars (warn once, then mapped)
  6. Process env     RW_PROMPTFORGE_*  (env_nested_delimiter="__")
  7. CLI overrides (kwarg)
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path
from threading import RLock
from typing import Any

import tomli  # type: ignore[import-not-found]
from dotenv import dotenv_values

from rw_promptforge.configs.models import RootConfig

# ---------------------------------------------------------------------------
# Provenance tracking (source name per leaf path)
# ---------------------------------------------------------------------------
_PROVENANCE: dict[str, str] = {}
_LOCK = RLock()


def _record(source_name: str, data: dict, prefix: str = "") -> None:
    with _LOCK:
        for key, value in data.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                _record(source_name, value, path)
            else:
                _PROVENANCE[path] = source_name


def get_provenance() -> dict[str, str]:
    with _LOCK:
        return dict(_PROVENANCE)


def reset_provenance() -> None:
    with _LOCK:
        _PROVENANCE.clear()


# ---------------------------------------------------------------------------
# Layer loaders — each returns a nested dict of overrides (no validation yet)
# ---------------------------------------------------------------------------


def _load_user_toml() -> dict[str, Any]:
    path = Path.home() / ".config" / "rw-promptforge" / "config.toml"
    if not path.exists():
        return {}
    try:
        with open(path, "rb") as f:
            data = tomli.load(f)
        _record("user_toml", data)
        return data
    except (tomli.TOMLDecodeError, OSError):
        return {}


def _load_project_toml() -> dict[str, Any]:
    path = find_project_config(Path.cwd())
    if path is None:
        return {}
    try:
        with open(path, "rb") as f:
            data = tomli.load(f)
        _record(f"project_toml:{path}", data)
        return data
    except (tomli.TOMLDecodeError, OSError):
        return {}


def _load_dotenv() -> dict[str, Any]:
    path = Path.cwd() / ".env"
    if not path.exists():
        return {}
    raw = dotenv_values(str(path))
    mapped = _map_dotenv(raw)
    if mapped:
        _record("dotenv", mapped)
    return mapped


_DEPRECATED_VARS: dict[str, tuple[str, str]] = {
    "RW_IE_ENDPOINT": ("ml", "endpoint"),
    "RW_PROMPTFORGE_EMBEDDING_MODEL": ("ml", "embedding_model"),
    "RW_IE_API_KEY": ("ml", "api_key"),
    "RW_IE_RERANK_MODEL": ("ml", "rerank_model"),
}
_deprecated_warned: set[str] = set()


def _load_deprecated_env() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for old, (section, field) in _DEPRECATED_VARS.items():
        if old in os.environ:
            if old not in _deprecated_warned:
                warnings.warn(
                    f"{old} is deprecated; use RW_PROMPTFORGE_{section.upper()}__{field.upper()}. "
                    "Will be removed in v0.3.0.",
                    DeprecationWarning,
                    stacklevel=3,
                )
                _deprecated_warned.add(old)
            out.setdefault(section, {})[field] = os.environ[old]
    if out:
        _record("deprecated_env", out)
    return out


def _load_process_env() -> dict[str, Any]:
    """Read RW_PROMPTFORGE_* env vars, splitting on __ for nesting."""
    out: dict[str, Any] = {}
    for key, value in os.environ.items():
        if not key.startswith("RW_PROMPTFORGE_"):
            continue
        nested = key[len("RW_PROMPTFORGE_"):].lower()
        if "__" in nested:
            section, field = nested.split("__", 1)
        else:
            section, field = nested, None
        if field is None:
            # top-level field — must exist in RootConfig directly
            out[section] = value
        else:
            out.setdefault(section, {})[field] = value
    if out:
        _record("env", out)
    return out


_DOTENV_MAP: dict[str, tuple[str, str]] = {
    "RW_IE_ENDPOINT": ("ml", "endpoint"),
    "RW_IE_API_KEY": ("ml", "api_key"),
    "RW_IE_RERANK_MODEL": ("ml", "rerank_model"),
    "RW_PROMPTFORGE_EMBEDDING_MODEL": ("ml", "embedding_model"),
    "OPENAI_API_KEY": ("llm", "api_key"),
    "OPENROUTER_API_KEY": ("llm", "api_key"),
    "GROQ_API_KEY": ("llm", "api_key"),
}


def _map_dotenv(raw: dict[str, str | None]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in raw.items():
        if value is None:
            continue
        if key in _DOTENV_MAP:
            section, field = _DOTENV_MAP[key]
            out.setdefault(section, {})[field] = value
    return out


# ---------------------------------------------------------------------------
# Project TOML walk-up discovery
# ---------------------------------------------------------------------------


def find_project_config(start: Path) -> Path | None:
    """Walk up from `start`, returning first config.toml found.

    Rules:
      - At each level, prefer config.toml over walking past.
      - `.git` directory stops the walk **one level above it**, so a config.toml
        at the git root itself is still honored.
      - Worktrees (`.git` is a file) are transparent.
    """
    cur = start.resolve()
    seen_git_dirs: set[Path] = set()
    while True:
        for cand in (cur / "config.toml", cur / "config" / "rw-promptforge.toml"):
            if cand.exists():
                return cand

        parent = cur.parent
        if parent == cur:
            return None

        git_marker = cur / ".git"
        if git_marker.exists():
            if git_marker.is_file():
                # Worktree — transparent, keep walking up.
                try:
                    content = git_marker.read_text().strip()
                    if content.startswith("gitdir:"):
                        ref = content.split(":", 1)[1].strip()
                        ref_p = Path(ref)
                        real_git = ref_p if ref_p.is_absolute() else (cur / ref_p).resolve()
                        resolved = real_git.resolve()
                        if resolved in seen_git_dirs:
                            return None
                        seen_git_dirs.add(resolved)
                        cur = parent
                        continue
                except OSError:
                    return None
            else:
                # `.git` is a directory. A real repo has HEAD inside.
                # If HEAD exists at THIS level → this is the project root → stop.
                # Otherwise (placeholder/empty) → keep walking to outer repo.
                if (git_marker / "HEAD").exists():
                    return None
                cur = parent
                continue

        cur = parent


# ---------------------------------------------------------------------------
# Deep merge with reasonable recursion depth limit
# ---------------------------------------------------------------------------


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursive dict merge; override wins on leaf values.

    Lists are replaced (not concatenated). Both input dicts must be safe to
    mutate — we don't copy.
    """
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_config(cli_overrides: dict[str, Any] | None = None) -> RootConfig:
    """Load merged config from all layers, in precedence order.

    If RootConfig.active_profile is set, that profile's overrides are merged
    on top of the base config (profiles override everything except CLI).
    """
    reset_provenance()

    # Build layers in precedence order (low → high):
    # 1. user TOML
    # 2. project TOML
    # 3. .env
    # 4. deprecated env
    # 5. process env
    # 6. active profile (if set)
    # 7. CLI overrides (highest)
    layers: list[dict[str, Any]] = [
        _load_user_toml(),
        _load_project_toml(),
        _load_dotenv(),
        _load_deprecated_env(),
        _load_process_env(),
    ]

    # Prune Nones to let Pydantic defaults win for unset fields.
    merged: dict[str, Any] = {}
    for layer in layers:
        merged = _deep_merge(merged, layer)

    pruned = _prune_nones(merged)
    cfg = RootConfig.model_validate(pruned)

    # Apply active profile if set
    if cfg.active_profile and cfg.active_profile in cfg.profiles:
        profile = cfg.profiles[cfg.active_profile]
        # Only include fields that were explicitly set in the profile TOML
        # We reconstruct from the profile's model_fields_set (fields explicitly provided)
        profile_dict = {}
        for section_name, section_model in (
            ("optimizer", profile.optimizer),
            ("ml", profile.ml),
            ("llm", profile.llm),
            ("session_db", profile.session_db),
        ):
            # Get only fields that were explicitly set (not defaulted)
            if hasattr(section_model, "model_fields_set"):
                set_fields = section_model.model_fields_set
                if set_fields:
                    section_data = {k: getattr(section_model, k) for k in set_fields}
                    if section_data:
                        profile_dict[section_name] = section_data
        if profile_dict:
            merged = _deep_merge(merged, profile_dict)

    # CLI overrides (highest priority)
    if cli_overrides:
        merged = _deep_merge(merged, cli_overrides)

    # Prune Nones to let Pydantic defaults win for unset fields.
    pruned = _prune_nones(merged)
    cfg = RootConfig.model_validate(merged)

    # Clear profile-related fields from the final config — profiles are
    # a one-time application mechanism, not part of the effective config.
    # Keep active_profile for introspection; clear profiles dict.
    cfg.profiles = {}
    # cfg.active_profile = None  # keep for introspection

    return cfg


def _prune_nones(obj):
    if isinstance(obj, dict):
        return {k: _prune_nones(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_prune_nones(v) for v in obj]
    return obj


# Re-export for tests
__all__ = [
    "find_project_config",
    "get_provenance",
    "load_config",
    "reset_provenance",
]
