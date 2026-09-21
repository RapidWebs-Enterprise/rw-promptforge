"""Optimizer consumes RootConfig.optimizer via optimizer_config kwarg."""

from __future__ import annotations

from rw_promptforge.configs.models import OptimizerConfig
from rw_promptforge.optimizer import Optimizer
from rw_promptforge.reflector.engine import Reflector


def test_optimizer_uses_optimizer_config_when_provided(stub_provider):
    cfg = OptimizerConfig(
        max_rounds=15,
        semantic_threshold=0.5,
        beam_size=4,
    )
    opt = Optimizer(
        provider=stub_provider,
        reflector=Reflector(stub_provider),
        optimizer_config=cfg,
    )
    assert opt.max_rounds == 15
    assert opt.semantic_threshold == 0.5
    assert opt.beam_size == 4


def test_optimizer_config_overrides_kwargs(stub_provider):
    """optimizer_config wins over individual kwargs."""
    cfg = OptimizerConfig(max_rounds=12)
    opt = Optimizer(
        provider=stub_provider,
        reflector=Reflector(stub_provider),
        max_rounds=1,  # should be ignored
        optimizer_config=cfg,
    )
    assert opt.max_rounds == 12


def test_optimizer_kwargs_still_work_without_config(stub_provider):
    """Backward-compat: no config → kwargs behave as before."""
    opt = Optimizer(
        provider=stub_provider,
        reflector=Reflector(stub_provider),
        max_rounds=7,
        beam_size=3,
    )
    assert opt.max_rounds == 7
    assert opt.beam_size == 3
