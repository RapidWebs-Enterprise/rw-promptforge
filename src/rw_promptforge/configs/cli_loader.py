"""Click CLI arguments → config overrides.

Explicit allowlist. Only flags in this table become config overrides.
Everything else (path, target_type, save, etc.) is a CLI concern and ignored.
"""

from __future__ import annotations

from typing import Any

# click param name → (section, config_field)
CLI_OVERRIDE_MAP: dict[str, tuple[str, str]] = {
    # LLM (was --provider/--endpoint/--model)
    "provider": ("llm", "provider"),
    "endpoint": ("llm", "endpoint"),
    "model": ("llm", "model"),
    # Optimizer (was --max-rounds etc.)
    "max_rounds": ("optimizer", "max_rounds"),
    "semantic_threshold": ("optimizer", "semantic_threshold"),
    "gain_threshold": ("optimizer", "gain_threshold"),
    "stability_threshold": ("optimizer", "stability_threshold"),
    "min_rounds": ("optimizer", "min_rounds"),
    "beam_size": ("optimizer", "beam_size"),
    "frontier_size": ("optimizer", "frontier_size"),
    "convergence_threshold": ("optimizer", "convergence_threshold"),
    "max_growth": ("optimizer", "max_growth"),
    "metric": ("optimizer", "metric"),
    # ML (was --ml-mode/--ml-endpoint/--min-traces)
    "ml_mode": ("ml", "enabled"),
    "ml_endpoint": ("ml", "endpoint"),
    "min_traces": ("ml", "min_traces"),
}


def cli_overrides_from_locals(local_args: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Convert click-injected kwargs into nested override dict.

    Only keys present in CLI_OVERRIDE_MAP and not-None are included.
    Type conversions:
      - ``bool`` stays as-is (ml_mode=bool → ml.enabled)
      - ``str`` stays as-is (provider, endpoint, etc.)
      - ``int``/``float`` stay as-is
      - None → dropped (means "user didn't pass this flag")
    """
    out: dict[str, dict[str, Any]] = {}
    for click_key, value in local_args.items():
        if click_key not in CLI_OVERRIDE_MAP or value is None:
            continue
        section, field = CLI_OVERRIDE_MAP[click_key]
        out.setdefault(section, {})[field] = value
    return out
