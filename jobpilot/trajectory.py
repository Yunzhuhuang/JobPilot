"""Trajectory recording -- what each node was told, did, and returned.

CLAUDE.md requires every node to append to `trajectory.json`, and PRD §9
deliverable 4 asks for a representative trajectory per agent node, readable from
instruction through tool calls to result, including retries and human
checkpoints.

Built with the first node rather than after six exist: retrofitting a recorder
means touching every node, adding it now means one parameter.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node: str
    instruction: str | None = None
    """The instruction file that drove the node, e.g. `triage.md`. None for a
    deterministic node -- and that absence is itself informative."""
    inputs: dict = Field(default_factory=dict)
    output: object = None
    tool_calls: list[dict] = Field(default_factory=list)
    retries: int = 0
    human_checkpoint: dict | None = None
    """The question put to the user and the answer they gave."""
    error: str | None = None
    wall_clock_s: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0


class Trajectory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: str
    scope: str
    """`run` for graph-level nodes, or a jd_id for per-JD work."""
    steps: list[Step] = Field(default_factory=list)


class Recorder:
    """Collects steps per scope and writes them beside the packets."""

    def __init__(self, stage: str) -> None:
        self.stage = stage
        self._by_scope: dict[str, Trajectory] = {}

    def add(self, scope: str, step: Step) -> None:
        self._by_scope.setdefault(
            scope, Trajectory(stage=self.stage, scope=scope)
        ).steps.append(step)

    def scopes(self) -> list[str]:
        return sorted(self._by_scope)

    def get(self, scope: str) -> Trajectory | None:
        return self._by_scope.get(scope)

    def write(self, run_dir: Path) -> list[Path]:
        """`run` goes at the run root; a jd_id goes in that JD's packet."""
        written: list[Path] = []
        for scope, trajectory in self._by_scope.items():
            if scope == "run":
                path = run_dir / "trajectory.json"
            else:
                folder = run_dir / "packets" / scope
                folder.mkdir(parents=True, exist_ok=True)
                path = folder / "trajectory.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(trajectory.model_dump(), indent=2, default=str) + "\n"
            )
            written.append(path)
        return written
