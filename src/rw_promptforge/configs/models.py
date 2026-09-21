"""Pydantic models for the layered configuration tree.

All secrets use SecretStr (ADR-013-amendment / audit G1).
All models forbid extra keys (audit G2).

Field defaults MUST match the pre-config hardcoded values byte-for-byte
so that v0.2.x → v0.3.0 migration is behavior-preserving.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, SecretStr


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class MLConfig(_Base):
    """RW_InferenceEngine integration (ADR-010/012)."""

    enabled: bool = False  # was --ml-mode
    endpoint: str = "http://srv1:8300"  # was --ml-endpoint
    embedding_model: str = "bge-small-en-v1.5"
    rerank_model: str = "ms-marco-MiniLM-L-6-v2"
    min_traces: PositiveInt = 10  # was --min-traces
    cache_maxsize: PositiveInt = 10_000
    api_key: SecretStr = SecretStr("")  # RW_IE_API_KEY


class OptimizerConfig(_Base):
    """Optimizer hyperparameters — defaults match optimizer.py.Hyperparams."""

    max_rounds: PositiveInt = 3
    semantic_threshold: float = Field(default=0.95, ge=0.0, le=1.0)
    gain_threshold: float = Field(default=0.02, ge=0.0)
    stability_threshold: float = Field(default=0.05, ge=0.0)
    min_rounds: PositiveInt = 2
    beam_size: PositiveInt = 1
    frontier_size: PositiveInt = 5
    convergence_threshold: float = Field(default=0.01, ge=0.0)
    max_growth: float = Field(default=1.5, ge=1.0)
    metric: Literal["llm", "exact_match", "rouge_l", "rouge_2", "bleu", "tool_call_valid"] = "llm"


class LLMConfig(_Base):
    """Provider + model used for the LLM reflection step."""

    provider: Literal["openai", "openrouter", "custom"] = "openai"
    endpoint: str | None = None
    model: str = "gpt-4o-mini"
    api_key: SecretStr = SecretStr("")


class SessionDBConfig(_Base):
    """Session DB location. Tilde is expanded at load time."""

    path: Path = Field(default_factory=lambda: Path("~/.rw-promptforge/session.db"))

    def model_post_init(self, __context, /) -> None:
        self.path = self.path.expanduser()


from pydantic_settings import SettingsConfigDict


class RootConfig(_Base):
    """Top of the configuration tree (plain Pydantic; layered in core.py)."""

    model_config = SettingsConfigDict(
        extra="forbid",
        hide_input_in_errors=True,
        # Exclude None values so model_dump(mode='json') is TOML-serializable
        json_schema_extra={"exclude_none": True},
    )

    version: int = 1  # schema version — bump on breaking changes
    active_profile: str | None = None  # name of active profile (None = use top-level)

    optimizer: OptimizerConfig = Field(default_factory=OptimizerConfig)
    ml: MLConfig = Field(default_factory=MLConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    session_db: SessionDBConfig = Field(default_factory=SessionDBConfig)

    # Named profiles — each can override any subset of the top-level sections
    profiles: dict[str, "RootConfig"] = Field(default_factory=dict)
