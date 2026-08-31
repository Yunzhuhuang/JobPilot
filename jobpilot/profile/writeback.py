"""Applying a gap answer to `profile.json` (PRD §5.6 steps 3-4).

The only place the pipeline writes to its own source of truth, so it is
deliberately narrow: append `tool_evidence` for a yes, append `not_experienced`
for a no, show a diff, validate, write. It never edits or deletes anything that
was already there.

`fixture/profile.json` is never touched. Every score is computed against that
frozen copy, so a run that rewrites the working profile cannot move a metric by
moving the goalposts -- after `iter4` the two files legitimately differ, and
REPRODUCE.md says so.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from jobpilot.answers import GapAnswer, UsedTool
from jobpilot.profile.claims import claimable_tools, declined_tools
from jobpilot.profile.loader import DEFAULT_PROFILE_PATH, load_profile
from jobpilot.profile.schema import NotExperienced, Profile, ToolEvidence
from jobpilot.profile.validate import validate_profile

SELF_STUDY = "self_study"


def _container_ids(profile: Profile) -> set[str]:
    return (
        {e.id for e in profile.experience}
        | {p.id for p in profile.projects}
        | {SELF_STUDY}
    )


def apply_answer(
    profile: Profile,
    answer: GapAnswer,
    asked: list[str],
    jd_id: str,
    *,
    today: str | None = None,
) -> tuple[Profile, list[str]]:
    """Returns the updated profile and a human-readable diff.

    Everything in `asked` that the answer does not confirm becomes
    `not_experienced`. That is what makes a "no" durable and stops the same
    question coming back next run -- the behaviour the run-1 -> run-2 metric
    exists to detect.
    """
    stamp = today or date.today().isoformat()
    containers = _container_ids(profile)
    known = claimable_tools(profile)
    refused = declined_tools(profile)

    evidence = list(profile.tool_evidence)
    not_experienced = list(profile.not_experienced)
    diff: list[str] = []

    confirmed: dict[str, UsedTool] = {u.tool.strip().lower(): u for u in answer.used}

    for tool in asked:
        key = tool.strip().lower()
        if key in known or key in refused:
            continue  # already settled; never re-record

        used = confirmed.get(key)
        if used is None:
            not_experienced.append(
                NotExperienced(tool=tool, asked_at=stamp, context_jd=jd_id)
            )
            diff.append(f"  - not_experienced += {tool!r}  (asked for {jd_id})")
            continue

        where = used.where.strip()
        if where not in containers:
            # Never guess a placement. An unrecognised location degrades to
            # self_study, which is claimable on a skills line and barred from
            # every role bullet -- the safe direction to be wrong in.
            diff.append(
                f"  ! {tool!r}: unknown location {where!r}, recorded as {SELF_STUDY}"
            )
            where = SELF_STUDY
        evidence.append(
            ToolEvidence(
                tool=used.tool,
                where=where,
                evidence=used.evidence,
                source="gap_question",
                added_at=stamp,
            )
        )
        diff.append(f"  + tool_evidence += {used.tool!r} @ {where}")

    updated = profile.model_copy(
        update={"tool_evidence": evidence, "not_experienced": not_experienced}
    )
    return updated, diff


def write_profile(profile: Profile, path: Path | None = None) -> Path:
    """Validate, then write. A profile that fails validation is never persisted."""
    problems = validate_profile(profile)
    if problems:
        raise ValueError(f"refusing to write an invalid profile: {problems}")
    target = path or DEFAULT_PROFILE_PATH
    target.write_text(profile.model_dump_json(indent=2) + "\n")
    return target


def reload_profile(path: Path | None = None) -> Profile:
    return load_profile(path or DEFAULT_PROFILE_PATH)
