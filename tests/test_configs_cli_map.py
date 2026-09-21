"""Tests for CLI→config wiring via cli_overrides_from_locals."""

from __future__ import annotations

import pytest

from rw_promptforge.configs.cli_loader import CLI_OVERRIDE_MAP, cli_overrides_from_locals
from rw_promptforge.configs import load_config


def test_cli_override_map_shape():
    # Sanity: every mapping has a valid 2-tuple shape
    for key, (section, field) in CLI_OVERRIDE_MAP.items():
        assert isinstance(key, str)
        assert section in {"llm", "optimizer", "ml"}
        assert isinstance(field, str)


def test_cli_override_map_no_none_values_allowed():
    # The MAP itself should have no None entries (None is a runtime value, not a key)
    assert all(v[0] is not None for v in CLI_OVERRIDE_MAP.items())


@pytest.mark.parametrize(
    "click_args,expected",
    [
        # No flags → empty overrides
        ({}, {}),
        # Single flag
        ({"max_rounds": 5}, {"optimizer": {"max_rounds": 5}}),
        # Multiple sections
        (
            {"max_rounds": 5, "ml_mode": True, "ml_endpoint": "http://x:1"},
            {
                "optimizer": {"max_rounds": 5},
                "ml": {"enabled": True, "endpoint": "http://x:1"},
            },
        ),
        # Non-allowlisted keys ignored
        (
            {"path": "/x", "target_type": "soul", "max_rounds": 5},
            {"optimizer": {"max_rounds": 5}},
        ),
        # None is dropped (means "user didn't pass")
        (
            {"max_rounds": None, "min_rounds": 2},
            {"optimizer": {"min_rounds": 2}},
        ),
    ],
)
def test_cli_overrides_from_locals(click_args, expected):
    got = cli_overrides_from_locals(click_args)
    assert got == expected


def test_cli_overrides_integrate_with_load_config():
    """CLI overrides land at the top of the precedence chain."""
    cfg = load_config(cli_overrides={"optimizer": {"max_rounds": 99}, "ml": {"enabled": True}})
    assert cfg.optimizer.max_rounds == 99
    assert cfg.ml.enabled is True


def test_cli_overrides_beat_env_and_toml(tmp_path, monkeypatch):
    """CLI > env > TOML > defaults for the same key."""
    import os

    monkeypatch.setenv("RW_PROMPTFORGE_ML__ENDPOINT", "http://env")
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("RW_IE_ENDPOINT=http://dotenv\n")
    (tmp_path / ".config" / "rw-promptforge").mkdir(parents=True)
    (tmp_path / ".config" / "rw-promptforge" / "config.toml").write_text(
        "[ml]\nendpoint = 'http://toml'\n"
    )
    # Note: the user TOML location uses Path.home(). We need to patch it.
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    cfg = load_config(cli_overrides={"ml": {"endpoint": "http://cli-wins"}})
    assert cfg.ml.endpoint == "http://cli-wins"
