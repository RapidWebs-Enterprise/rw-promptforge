"""Tests for profile support in layered config."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
import tomli_w

from rw_promptforge.configs import load_config
from rw_promptforge.configs.models import RootConfig


def test_profile_applies_overrides():
    """active_profile merges profile overrides on top of base config."""
    cfg_data = {
        "version": 1,
        "optimizer": {"max_rounds": 3},
        "ml": {"enabled": False, "endpoint": "http://base:8300"},
        "profiles": {
            "dev": {"optimizer": {"max_rounds": 99}, "ml": {"endpoint": "http://dev:1"}}
        },
        "active_profile": "dev",
    }

    with tempfile.TemporaryDirectory() as td:
        home = Path(tempfile.mkdtemp())
        (home / ".config" / "rw-promptforge").mkdir(parents=True)
        (home / ".config" / "rw-promptforge" / "config.toml").write_text(tomli_w.dumps(cfg_data))

        old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(home)
        try:
            cfg = load_config()
            assert cfg.active_profile == "dev"
            assert cfg.optimizer.max_rounds == 99
            assert cfg.ml.endpoint == "http://dev:1"
        finally:
            if old_home:
                os.environ["HOME"] = old_home


def test_profile_only_overrides_specified_fields():
    """Profile overrides only the fields it specifies; other fields stay from base."""
    cfg_data = {
        "version": 1,
        "optimizer": {"max_rounds": 3, "beam_size": 2},
        "ml": {"enabled": False, "endpoint": "http://base:8300"},
        "profiles": {
            "test": {"optimizer": {"max_rounds": 99}}  # only overrides max_rounds
        },
        "active_profile": "test",
    }

    with tempfile.TemporaryDirectory() as td:
        home = Path(tempfile.mkdtemp())
        (home / ".config" / "rw-promptforge").mkdir(parents=True)
        (home / ".config" / "rw-promptforge" / "config.toml").write_text(tomli_w.dumps(cfg_data))

        old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(home)
        try:
            cfg = load_config()
            assert cfg.optimizer.max_rounds == 99  # overridden
            assert cfg.optimizer.beam_size == 2   # preserved from base
        finally:
            if old_home:
                os.environ["HOME"] = old_home


def test_profile_does_not_persist_internal_fields():
    """active_profile, profiles, version are not carried from profile to final config."""
    cfg_data = {
        "version": 1,
        "optimizer": {"max_rounds": 5},
        "profiles": {
            "p1": {
                "version": 2,
                "optimizer": {"max_rounds": 99},
                "active_profile": "nested",  # should be ignored
                "profiles": {"p2": {}},      # should be ignored
            }
        },
        "active_profile": "p1",
    }

    with tempfile.TemporaryDirectory() as td:
        home = Path(tempfile.mkdtemp())
        (home / ".config" / "rw-promptforge").mkdir(parents=True)
        (home / ".config" / "rw-promptforge" / "config.toml").write_text(tomli_w.dumps(cfg_data))

        old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(home)
        try:
            cfg = load_config()
            # Profile's internal fields must not leak
            assert cfg.active_profile is None or cfg.active_profile == "p1"  # base active_profile
            assert cfg.profiles == {}  # profiles dict should be empty in final
            assert cfg.version == 1  # version from base
        finally:
            if old_home:
                os.environ["HOME"] = old_home


def test_no_active_profile_uses_base_config():
    """When active_profile is None/unset, profiles dict is ignored."""
    cfg_data = {
        "version": 1,
        "optimizer": {"max_rounds": 3},
        "profiles": {"dev": {"optimizer": {"max_rounds": 99}}},
        # no active_profile
    }

    with tempfile.TemporaryDirectory() as td:
        home = Path(tempfile.mkdtemp())
        (home / ".config" / "rw-promptforge").mkdir(parents=True)
        (home / ".config" / "rw-promptforge" / "config.toml").write_text(tomli_w.dumps(cfg_data))

        old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(home)
        try:
            cfg = load_config()
            assert cfg.optimizer.max_rounds == 3  # base, not profile
        finally:
            if old_home:
                os.environ["HOME"] = old_home


def test_cli_overrides_beat_profile():
    """CLI overrides should win even when profile is active."""
    cfg_data = {
        "version": 1,
        "optimizer": {"max_rounds": 3},
        "profiles": {"dev": {"optimizer": {"max_rounds": 99}}},
        "active_profile": "dev",
    }

    with tempfile.TemporaryDirectory() as td:
        home = Path(tempfile.mkdtemp())
        (home / ".config" / "rw-promptforge").mkdir(parents=True)
        (home / ".config" / "rw-promptforge" / "config.toml").write_text(tomli_w.dumps(cfg_data))

        old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(home)
        try:
            cfg = load_config(cli_overrides={"optimizer": {"max_rounds": 77}})
            assert cfg.optimizer.max_rounds == 77  # CLI wins
        finally:
            if old_home:
                os.environ["HOME"] = old_home


def test_profile_nonexistent_active_falls_back():
    """Nonexistent active_profile name falls back to base config silently."""
    cfg_data = {
        "version": 1,
        "optimizer": {"max_rounds": 3},
        "profiles": {"dev": {"optimizer": {"max_rounds": 99}}},
        "active_profile": "nonexistent",
    }

    with tempfile.TemporaryDirectory() as td:
        home = Path(tempfile.mkdtemp())
        (home / ".config" / "rw-promptforge").mkdir(parents=True)
        (home / ".config" / "rw-promptforge" / "config.toml").write_text(tomli_w.dumps(cfg_data))

        old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(home)
        try:
            cfg = load_config()
            assert cfg.optimizer.max_rounds == 3  # falls back to base
        finally:
            if old_home:
                os.environ["HOME"] = old_home