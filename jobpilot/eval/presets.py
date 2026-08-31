"""Stage presets: the flags that make each changelog row re-runnable.

A stage is the graph with one capability switched on. `iter2` is `iter1` with
`h1b_filter: true` -- nothing else moves, which is the only reason a delta
between them can be attributed to the H-1B filter.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from jobpilot.config import REPO_ROOT

STAGES_DIR = REPO_ROOT / "eval" / "stages"

# Capabilities that exist in code today. A preset may only enable what is
# built; enabling anything else fails loudly (PRD 7.2). Grows by one entry per
# build step, which makes it a checklist that cannot drift from reality.
IMPLEMENTED: set[str] = {
    "profile_context",
    "triage",
    "h1b_filter",
    "tailor",
    "self_verify",
    "verifier_node",
    "gap_memory",
}

# Which build step delivers each capability, so the failure message can say
# what to do rather than only what went wrong.
DELIVERED_BY = {
    "profile_context": "step 9 (graph + triage node)",
    "triage": "step 9 (graph + triage node)",
    "tailor": "step 11 (tailoring node)",
    "h1b_filter": "step 10 (H-1B lookup + filter node)",
    "self_verify": "step 11 (iter3a, built to be removed)",
    "verifier_node": "step 12 (verifier node + revision loop)",
    "gap_memory": "step 13 (gap questions + write-back)",
    "style_exemplars": "step 14 (style exemplars)",
}


class StageFlags(BaseModel):
    """One flag per capability. `extra="forbid"` so a typo is an error, not a
    setting that silently does nothing."""

    model_config = ConfigDict(extra="forbid")

    profile_context: bool = False
    triage: bool = False
    tailor: bool = False
    h1b_filter: bool = False
    self_verify: bool = False
    verifier_node: bool = False
    gap_memory: bool = False
    style_exemplars: bool = False

    def enabled(self) -> list[str]:
        return [name for name, on in self.model_dump().items() if on]


class Stage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str
    flags: StageFlags


class UnbuiltCapabilityError(RuntimeError):
    """A preset enables a node that does not exist yet."""


def stage_path(name: str) -> Path:
    return STAGES_DIR / f"{name}.yaml"


def available_stages() -> list[str]:
    """The real stages. A leading underscore marks a test preset, which
    must not appear in compare.md alongside the eight measured ones."""
    return sorted(
        p.stem for p in STAGES_DIR.glob("*.yaml") if not p.stem.startswith("_")
    )


def load_preset(name: str, *, require_built: bool = False) -> Stage:
    """Reads and validates one preset.

    `require_built` is on when a stage is about to be *run*, and off when its
    results are merely being read -- `--all-stages` must be able to describe a
    stage nobody can execute yet.
    """
    path = stage_path(name)
    if not path.is_file():
        raise FileNotFoundError(
            f"no stage preset {name!r}; available: {', '.join(available_stages())}"
        )
    stage = Stage.model_validate(yaml.safe_load(path.read_text()) or {})
    if stage.name != name:
        raise ValueError(f"{path} declares name={stage.name!r}, expected {name!r}")

    if require_built:
        missing = [f for f in stage.flags.enabled() if f not in IMPLEMENTED]
        if missing:
            detail = "; ".join(
                f"{f} -- arrives with {DELIVERED_BY.get(f, 'a later step')}"
                for f in missing
            )
            raise UnbuiltCapabilityError(
                f"stage {name!r} enables capabilities that are not built: {detail}"
            )
    return stage
