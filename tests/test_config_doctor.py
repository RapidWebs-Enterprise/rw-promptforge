"""Tests for `config doctor` command."""

from __future__ import annotations

from click.testing import CliRunner

from rw_promptforge.cli import main


def test_config_doctor_basic():
    runner = CliRunner()
    res = runner.invoke(main, ["config", "doctor"])
    assert res.exit_code == 0
    assert "Config validation passed" in res.output
    assert "Required fields present" in res.output
    assert "ML mode disabled" in res.output


def test_config_doctor_with_endpoint_override(tmp_path):
    from click.testing import CliRunner
    from rw_promptforge.cli import main

    runner = CliRunner()
    # Enable ML mode via env so doctor runs connectivity test
    import os
    os.environ["RW_PROMPTFORGE_ML__ENABLED"] = "true"
    try:
        res = runner.invoke(main, ["config", "doctor", "--endpoint", "http://fake:9999"])
        assert res.exit_code == 0
        assert "RW_IE unreachable" in res.output or "timeout" in res.output.lower()
    finally:
        os.environ.pop("RW_PROMPTFORGE_ML__ENABLED", None)