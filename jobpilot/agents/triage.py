"""The triage node: one JD in, a label out.

PRD §5.5. `iter1`'s whole claim is that a node which can read the profile and a
stated rubric labels postings better than one prompt holding a raw resume. The
only number that tests it is agreement with the author's labels.

The rubric in `instructions/triage.md` states the two labelling rules recorded
in CLAUDE.md, because the ground truth was written under them -- if the
instruction and the labels disagree about the rules, the metric measures a
rules dispute rather than a judgement one.
"""

from __future__ import annotations

from typing import Literal

from google.adk import Agent
from google.adk.models import BaseLlm
from pydantic import BaseModel, ConfigDict, Field

from jobpilot.agents import load_instruction
from jobpilot.ingest import JD
from jobpilot.profile.claims import claimable_tools
from jobpilot.profile.schema import Profile

INSTRUCTION = "triage"

TriageLabel = Literal["most_matched", "less_matched", "skip"]


class TriageResult(BaseModel):
    """Exactly PRD §5.5. `jd_id` is attached by the caller, not the model."""

    model_config = ConfigDict(extra="forbid")

    label: TriageLabel
    score: int = Field(ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)


def profile_summary(profile: Profile) -> str:
    """The "compact profile summary" §5.5 asks for.

    Deliberately not the whole profile: triage judges fit, and bullet-level
    evidence is the tailor's material and the verifier's whitelist. Sending
    everything would also make the cheapest node in the graph the most
    expensive.
    """
    identity, constraints = profile.identity, profile.constraints
    lines = [
        f"Name: {identity.name}",
        f"Location: {identity.location}"
        f"{' (open to relocation)' if identity.open_to_relocation else ''}",
        f"Target roles: {', '.join(constraints.target_roles)}",
        f"Needs visa sponsorship: {'yes' if constraints.needs_sponsorship else 'no'}",
        f"Will not consider: {', '.join(constraints.excluded_locations) or 'nothing'}",
        f"Earliest start: {constraints.earliest_start}",
        "",
        "Experience:",
    ]
    for exp in profile.experience:
        lines.append(
            f"- {exp.title}, {exp.company} ({exp.start} to {exp.end or 'present'})"
        )
    lines.append("")
    lines.append("Projects:")
    lines.extend(f"- {p.name}: {p.one_liner}" for p in profile.projects)
    lines.append("")
    lines.append("Education:")
    lines.extend(
        f"- {e.degree} {e.field}, {e.school} ({e.start} to {e.end or 'present'})"
        for e in profile.education
    )
    lines.append("")
    lines.append(
        "Tools the candidate can evidence: "
        + ", ".join(sorted({e.tool for e in profile.tool_evidence}))
    )
    if profile.not_experienced:
        lines.append(
            "Has explicitly NOT used: "
            + ", ".join(sorted(e.tool for e in profile.not_experienced))
        )
    return "\n".join(lines)


class UsageMeter:
    """Accumulates token usage the graph would otherwise never see.

    `ctx.run_node` returns a node's output, not its events, so
    `usage_metadata` is unreachable from the calling node. An
    `after_model_callback` is handed the LlmResponse directly, which is how
    cost per JD stays a measured number rather than an estimate.
    """

    def __init__(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0

    def __call__(self, callback_context: object, llm_response: object) -> None:
        usage = getattr(llm_response, "usage_metadata", None)
        if usage:
            self.input_tokens += usage.prompt_token_count or 0
            self.output_tokens += usage.candidates_token_count or 0
        return None


def build_agent(model: BaseLlm, meter: UsageMeter | None = None) -> Agent:
    return Agent(
        name="triage",
        model=model,
        instruction=load_instruction(INSTRUCTION),
        after_model_callback=meter,
    )


def h1b_block(assessment: object | None) -> str:
    """The H-1B node's finding, as evidence for triage.

    Deliberately states what the finding is *not*. The employer-level fact and
    the role-level bar point in opposite directions on exactly the postings
    that matter most -- SpaceX files 13 petitions and still cannot staff
    Starshield with a non-US-person -- so handing triage "likely sponsors: yes"
    without that caveat would argue against the `skip` those postings require.
    """
    if assessment is None:
        return ""
    entity = getattr(assessment, "matched_entity", None)
    likelihood = getattr(assessment, "likelihood", "unknown")
    if entity:
        found = (
            f"Likely sponsors: {likelihood} — filed as {entity}, "
            f"{getattr(assessment, 'approvals', 0)} approvals in FY2026."
        )
    else:
        found = (
            f"Likely sponsors: {likelihood} — this employer does not appear in "
            "the USCIS data. That may mean it has never filed, not that it "
            "refuses to sponsor."
        )
    return (
        "## Employer H-1B history (public USCIS Employer Data Hub)\n\n"
        f"{found}\n\n"
        "This is employer filing history only. It does not say whether this "
        "candidate can be hired into this particular role, and it must not "
        "soften an export-control, clearance or citizenship requirement.\n\n"
    )


def triage_prompt(jd: JD, summary: str, assessment: object | None = None) -> str:
    return (
        f"## Candidate\n\n{summary}\n\n"
        f"{h1b_block(assessment)}"
        f"## Job posting\n\n"
        f"{jd.company} — {jd.title}\nLocation: {jd.location}\n\n{jd.text}\n"
    )


def whitelist_size(profile: Profile) -> int:
    """Used only for the trajectory record, to show what the node was given."""
    return len(claimable_tools(profile))
