"""`output/<stage>/<date>/run.json` -- the machine-readable record of a run.

PRD 4.4 defines a run's outputs as `digest.md` plus packet folders, but a
digest is prose for a human. Every 7.1 metric needs structured facts instead:
what label each JD got, whether the H-1B filter dropped it, which gap questions
were asked, tokens and seconds. The digest is unchanged; this sits beside it.

Written by the baseline (step 8) and the pipeline (step 9+), read by every
scorer. Neither side imports the other -- this file is the whole contract.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from jobpilot.config import REPO_ROOT

OUTPUT_DIR = REPO_ROOT / "output"
RUN_RECORD_NAME = "run.json"

TriageLabel = Literal["most_matched", "less_matched", "skip"]


class JDRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jd_id: str = Field(pattern=r"^jd_\d{2}$")
    label: TriageLabel | None = None
    """None when the JD never reached triage -- dropped, or the run errored."""
    dropped_by_h1b: bool = False
    sponsors: bool | None = None
    """Legacy, written by runs before 2026-08-30. Superseded by `sponsorship`
    when the H-1B node stopped answering a yes/no question.

    Kept because `run.json` is a *persisted artifact*: the baseline's record was
    written under the old schema, and `extra="forbid"` would otherwise make a
    schema change retroactively invalidate every run already measured. Read,
    never written."""
    sponsorship: Literal["likely", "unlikely", "unknown"] | None = None
    """None when this stage ran no H-1B node at all -- distinct from
    "unknown", which is the node's answer when it ran and found nothing."""
    h1b_confidence: Literal["high", "medium", "low"] | None = None
    matched_employer: str | None = None
    h1b_searches: int = 0
    """How many index queries the agent issued. 0 means the name-similarity
    shortlist was enough; >0 means it had to go looking."""
    revision_rounds: int = 0
    """Verify -> tailor revisions this posting needed (PRD 5.1, max 2)."""
    dropped_lines: int = 0
    """Lines removed in code after the revision budget was exhausted. Non-zero
    means the tailor could not fix it and the packet was cut rather than shipped
    with a rejected claim."""
    packet: str | None = None
    """Path to the packet folder, relative to the run directory."""
    gap_questions: list[str] = Field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    wall_clock_s: float = 0.0
    error: str | None = None
    """Set when this JD failed. It still appears in per_jd.md -- PRD 7.1 asks
    for every case including failures, and a silently dropped JD would make the
    denominator lie."""


class RunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: str
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    model: str
    flags: dict[str, bool] = Field(default_factory=dict)
    offline: bool = True
    jds: list[JDRecord]

    def by_id(self) -> dict[str, JDRecord]:
        return {jd.jd_id: jd for jd in self.jds}


def run_dir(stage: str, date: str) -> Path:
    return OUTPUT_DIR / stage / date


def write_run_record(record: RunRecord, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / RUN_RECORD_NAME
    path.write_text(record.model_dump_json(indent=2) + "\n")
    return path


def read_run_record(directory: Path) -> RunRecord:
    path = directory / RUN_RECORD_NAME
    if not path.is_file():
        raise FileNotFoundError(f"no {RUN_RECORD_NAME} in {directory}")
    return RunRecord.model_validate(json.loads(path.read_text()))


def latest_run(stage: str, root: Path | None = None) -> Path | None:
    """The newest dated run directory for a stage, or None."""
    base = (root or OUTPUT_DIR) / stage
    if not base.is_dir():
        return None
    dated = sorted(
        (p for p in base.iterdir() if p.is_dir() and (p / RUN_RECORD_NAME).is_file()),
        reverse=True,
    )
    return dated[0] if dated else None


def previous_run(stage: str, root: Path | None = None) -> Path | None:
    """The run before the newest one -- the run-1 to run-2 comparison needs it."""
    base = (root or OUTPUT_DIR) / stage
    if not base.is_dir():
        return None
    dated = sorted(
        (p for p in base.iterdir() if p.is_dir() and (p / RUN_RECORD_NAME).is_file()),
        reverse=True,
    )
    return dated[1] if len(dated) > 1 else None
