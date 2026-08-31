"""Loads `config.yaml` and builds the one model every stage shares.

`run`, `baseline`, and `eval` all go through `load_config` + `build_model`, which
is what makes the "one model for the baseline and every stage" guarantee (PRD
7.2) real rather than aspirational: a stage comparison is only attributable to
the feature it added if nothing else moved.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from google.adk.models import BaseLlm
from pydantic import BaseModel, ConfigDict, Field

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "config.yaml"


class ModelConfig(BaseModel):
    """The model block of `config.yaml`."""

    model_config = ConfigDict(extra="forbid")

    # `provider` is not redundant with `id`: a bare "claude-*" string resolves
    # through ADK's registry to the Vertex-served `Claude` class, which needs
    # GOOGLE_CLOUD_PROJECT/LOCATION. Naming the provider lets `build_model`
    # bypass the registry and construct the direct-API class instead.
    provider: Literal["anthropic"]
    id: str = Field(min_length=1)
    max_tokens: int = Field(gt=0)


class Config(BaseModel):
    """The whole of `config.yaml`.

    `extra="forbid"` everywhere: a typo'd or stale key is a loud error, never a
    setting that silently does nothing.
    """

    model_config = ConfigDict(extra="forbid")

    model: ModelConfig


def load_config(path: Path | None = None) -> Config:
    """Reads and validates `config.yaml`."""
    path = path or DEFAULT_CONFIG_PATH
    if not path.is_file():
        raise FileNotFoundError(f"config not found: {path}")
    raw = yaml.safe_load(path.read_text()) or {}
    return Config.model_validate(raw)


def build_model(cfg: Config) -> BaseLlm:
    """Builds the shared model instance.

    Returns a `BaseLlm` *instance* rather than a model-name string. `LlmAgent`
    accepts both, but only an instance skips the registry lookup described on
    `ModelConfig.provider`.
    """
    if cfg.model.provider == "anthropic":
        # Not exported from google.adk.models; the direct-API class must be
        # imported from its own module. Reads ANTHROPIC_API_KEY from the env.
        from google.adk.models.anthropic_llm import AnthropicLlm

        return AnthropicLlm(model=cfg.model.id, max_tokens=cfg.model.max_tokens)

    # Unreachable while `provider` is a single-value Literal, but this is the
    # seam where a second provider would land.
    raise ValueError(f"unsupported model provider: {cfg.model.provider!r}")
