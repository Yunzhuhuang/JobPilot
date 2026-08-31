"""What each JD asks for -- extracted once, then frozen.

`fixture/requirements/<jd_id>.json` is ground truth, not pipeline output. It is
produced by `scripts/extract_requirements.py` and never regenerated during a
stage run: a moving target would make two stages incomparable, and comparability
is the one thing the whole ablation rests on.

Two consumers, neither of them eval-only, which is why this is a top-level
module: the JD keyword coverage scorer (PRD 7.1) and the gap-diff node (5.6).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from jobpilot.config import REPO_ROOT

REQUIREMENTS_DIR = REPO_ROOT / "fixture" / "requirements"

# The first six mirror the profile's skills buckets, so a requirement and a
# tool_evidence entry can be compared without a translation layer. The last
# three cover what a skills bucket cannot hold -- and `credential` is not
# decoration: SpaceX's US-person rule and Mach's export-control language are
# requirements, and they are precisely what the H-1B filter has to reason about.
RequirementType = Literal[
    "language",
    "framework",
    "cloud_infra",
    "data",
    "ai_ml",
    "testing",
    "concept",
    "experience",
    "credential",
]


class Requirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    type: RequirementType
    required: bool
    """True only for a must-have. A 'nice to have' is False -- coverage is
    scored against the must-haves, so widening this would flatter every run."""
    aliases: list[str] = Field(default_factory=list)
    """Other names a resume might use, so matching needs no LLM."""


class RequirementSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jd_id: str = Field(pattern=r"^jd_\d{2}$")
    extracted_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    model: str
    """Recorded per file: the README must state which model wrote the ground
    truth, and hand-typing that later is how a reproducibility claim goes
    stale."""
    requirements: list[Requirement]

    def required_only(self) -> list[Requirement]:
        return [r for r in self.requirements if r.required]

    def match_keys(self, required_only: bool = True) -> list[set[str]]:
        """One lowercased name-and-alias set per requirement, for matching."""
        source = self.required_only() if required_only else self.requirements
        return [
            {r.name.strip().lower(), *(a.strip().lower() for a in r.aliases)}
            for r in source
        ]


def requirements_path(jd_id: str, directory: Path | None = None) -> Path:
    return (directory or REQUIREMENTS_DIR) / f"{jd_id}.json"


def write_requirements(rs: RequirementSet, directory: Path | None = None) -> Path:
    target = directory or REQUIREMENTS_DIR
    target.mkdir(parents=True, exist_ok=True)
    path = requirements_path(rs.jd_id, target)
    path.write_text(json.dumps(rs.model_dump(), indent=2) + "\n")
    return path


def read_requirements(path: Path) -> RequirementSet:
    return RequirementSet.model_validate(json.loads(path.read_text()))


def load_requirements(directory: Path | None = None) -> dict[str, RequirementSet]:
    """Every extracted requirement set, keyed by `jd_id`."""
    target = directory or REQUIREMENTS_DIR
    if not target.is_dir():
        return {}
    sets = (read_requirements(p) for p in sorted(target.glob("jd_*.json")))
    return {rs.jd_id: rs for rs in sets}
