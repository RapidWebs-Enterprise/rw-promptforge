"""Phase 5 integration tests — CLI --ml-mode flag and Optimizer ml_context."""

from __future__ import annotations

import pytest

from rw_promptforge.optimizer import Optimizer


def test_optimizer_without_ml_context_is_token_only(stub_provider):
    """Default optimizer has ml_context=None → token-based path unchanged."""
    from rw_promptforge.reflector.engine import Reflector

    opt = Optimizer(provider=stub_provider, reflector=Reflector(stub_provider))
    assert opt.ml_context is None


def test_optimizer_accepts_ml_context(stub_provider):
    """ml_context passes through; optimizer stores it for future ML hooks."""
    from rw_promptforge.reflector.engine import Reflector

    ml = {"provider": stub_provider, "min_traces": 5}
    opt = Optimizer(provider=stub_provider, reflector=Reflector(stub_provider), ml_context=ml)
    assert opt.ml_context is ml
    assert opt.ml_context is not None
    assert opt.ml_context["min_traces"] == 5


def test_cli_ml_mode_flag_parseable():
    """CLI accepts --ml-mode without crashing on missing [ml] deps."""
    from click.testing import CliRunner

    from rw_promptforge.cli import main

    runner = CliRunner()
    # Should print ML-mode warning or proceed gracefully; not exit with parse error
    result = runner.invoke(
        main, ["optimize", "--ml-mode", "--target-type", "soul", "/nonexistent"],
    )
    # Path doesn't exist → click errors with Invalid Path (exit 2),
    # not a missing-deps crash
    assert result.exit_code == 2
    assert "Invalid value" in result.output or "does not exist" in result.output
