"""What the author may claim, and where.

`classify_claim` is the operational definition of "fabricated" -- the predicate
the primary metric counts. Three callers share it: the verifier node inside the
pipeline, the harness scorer, and `validate_profile`, so the profile is held to
the same standard it enforces on generated text.
"""

from __future__ import annotations

from typing import Literal, NamedTuple

from jobpilot.profile.schema import Profile, ToolEvidence

SELF_STUDY = "self_study"

# How a single tool claim stands up. Only `supported` may reach a rendered
# document; the rest map to `unsupported` in the verification report, and the
# distinction between them is what tells the pipeline whether a gap question
# would fix it (`unplaced`) or nothing would (`declined`).
ClaimStatus = Literal["supported", "unplaced", "misplaced", "declined", "unsupported"]


class ClaimVerdict(NamedTuple):
    status: ClaimStatus
    tool: str
    """Canonical name when the tool is known, otherwise the name as claimed."""
    reason: str


def claimable_tools(profile: Profile) -> set[str]:
    """The verifier's whitelist: every canonical name and alias, lowercased.

    Only `tool_evidence` feeds this. `skills` deliberately does not -- a skills
    line is a summary, not evidence, and letting it grant claims would blunt the
    fabrication metric.
    """
    claimable: set[str] = set()
    for entry in profile.tool_evidence:
        claimable.add(entry.tool.strip().lower())
        claimable.update(alias.strip().lower() for alias in entry.aliases)
    return claimable


def declined_tools(profile: Profile) -> set[str]:
    """Tools the author has explicitly said they have not used."""
    return {entry.tool.strip().lower() for entry in profile.not_experienced}


def evidence_index(profile: Profile) -> dict[str, ToolEvidence]:
    """Every canonical name and alias, lowercased, mapped to its evidence."""
    index: dict[str, ToolEvidence] = {}
    for entry in profile.tool_evidence:
        index[entry.tool.strip().lower()] = entry
        for alias in entry.aliases:
            index[alias.strip().lower()] = entry
    return index


def classify_claim(
    profile: Profile, tool: str, container_id: str | None = None
) -> ClaimVerdict:
    """Judges one tool claim, in the place it is being made.

    Membership in the whitelist is not enough. A tool the author has used
    somewhere can still be claimed in the wrong place -- writing "configured
    Kafka pipelines at Amazon" when the Amazon work used SQS invents an
    *attachment*, not a tool, and every word of it traces to the profile. That
    is the failure this function exists to catch.

    `container_id` is the experience or project the claim sits in, or None for
    a claim that names no employer (a skills line, or a general sentence in a
    cover letter), where placement cannot be wrong.
    """
    key = tool.strip().lower()

    if key in declined_tools(profile):
        return ClaimVerdict("declined", tool, "listed in not_experienced")

    entry = evidence_index(profile).get(key)
    if entry is None:
        return ClaimVerdict("unsupported", tool, "no tool_evidence entry")

    if container_id is None:
        return ClaimVerdict("supported", entry.tool, f"evidence: {entry.where}")

    if entry.where == SELF_STUDY:
        return ClaimVerdict(
            "unplaced",
            entry.tool,
            "evidence is a skills-line mention with no role or project behind "
            "it; a gap answer must supply one before it can sit in a bullet",
        )

    if entry.where == container_id:
        return ClaimVerdict("supported", entry.tool, f"evidence: {entry.where}")

    # `where` holds a single id, so a tool used in several places is sanctioned
    # by the container's own `tools` list -- the author's own statement that it
    # belongs to that role or project.
    if key in container_tools(profile, container_id):
        return ClaimVerdict("supported", entry.tool, f"listed in {container_id}.tools")

    return ClaimVerdict(
        "misplaced",
        entry.tool,
        f"evidence points at {entry.where}, not {container_id}",
    )


def container_tools(profile: Profile, container_id: str) -> set[str]:
    """The tool names a role or project claims at the container level."""
    for container in (*profile.experience, *profile.projects):
        if container.id == container_id:
            return {tool.strip().lower() for tool in container.tools}
    return set()


def iter_bullets(profile: Profile) -> list[tuple[str, object]]:
    """Every bullet with the id of the experience or project that owns it."""
    pairs: list[tuple[str, object]] = []
    for container in (*profile.experience, *profile.projects):
        pairs.extend((container.id, bullet) for bullet in container.bullets)
    return pairs  # type: ignore[return-value]
