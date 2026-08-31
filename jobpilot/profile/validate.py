"""Cross-field checks Pydantic cannot express.

Pydantic validates one field at a time. Everything here spans fields: does this
bullet's tool have a receipt, does this evidence entry point at a role that
exists, are two bullets sharing an id.
"""

from __future__ import annotations

from jobpilot.profile.claims import (
    SELF_STUDY,
    classify_claim,
    declined_tools,
    iter_bullets,
)
from jobpilot.profile.schema import Profile


def validate_profile(profile: Profile) -> list[str]:
    """Returns human-readable problems; empty means valid.

    A list rather than an exception: `profile validate` should report every
    problem at once, not stop at the first.
    """
    problems: list[str] = []
    declined = declined_tools(profile)

    # Every id a bullet or evidence entry can point at.
    container_ids = (
        {edu.id for edu in profile.education}
        | {exp.id for exp in profile.experience}
        | {proj.id for proj in profile.projects}
    )

    _check_unique_ids(profile, container_ids, problems)

    # The core rule: a tool is claimable only via tool_evidence, and only in
    # the place its evidence supports. Bullet `tools` is a claim;
    # tool_evidence is the receipt. Same predicate the verifier runs on
    # generated text, so the profile is held to the standard it enforces.
    for container_id, bullet in iter_bullets(profile):
        for tool in bullet.tools:
            verdict = classify_claim(profile, tool, container_id)
            if verdict.status != "supported":
                problems.append(
                    f"{bullet.id}: claims tool {tool!r} "
                    f"[{verdict.status}] -- {verdict.reason}"
                )
        if not bullet.id.startswith(f"{container_id}_"):
            problems.append(
                f"{bullet.id}: bullet id is not prefixed by its parent {container_id!r}"
            )

    # Role-level `tools` is a looser summary than a bullet claim, but it still
    # must not contradict not_experienced.
    for container in (*profile.experience, *profile.projects):
        for tool in container.tools:
            if tool.strip().lower() in declined:
                problems.append(
                    f"{container.id}: lists tool {tool!r}, which is in not_experienced"
                )

    for entry in profile.tool_evidence:
        if entry.where != SELF_STUDY and entry.where not in container_ids:
            problems.append(
                f"tool_evidence[{entry.tool!r}]: where={entry.where!r} "
                f"matches no experience, project, or education id"
            )
        if entry.tool.strip().lower() in declined:
            problems.append(
                f"tool_evidence[{entry.tool!r}]: also listed in not_experienced"
            )

    return problems


def _check_unique_ids(
    profile: Profile, container_ids: set[str], problems: list[str]
) -> None:
    declared = [
        *(edu.id for edu in profile.education),
        *(exp.id for exp in profile.experience),
        *(proj.id for proj in profile.projects),
    ]
    if len(declared) != len(container_ids):
        problems.append(f"duplicate container ids among {sorted(declared)}")

    bullet_ids = [bullet.id for _, bullet in iter_bullets(profile)]  # type: ignore[attr-defined]
    if len(bullet_ids) != len(set(bullet_ids)):
        duplicates = sorted({b for b in bullet_ids if bullet_ids.count(b) > 1})
        problems.append(f"duplicate bullet ids: {duplicates}")

    tools = [entry.tool.strip().lower() for entry in profile.tool_evidence]
    if len(tools) != len(set(tools)):
        duplicates = sorted({t for t in tools if tools.count(t) > 1})
        problems.append(f"duplicate tool_evidence entries: {duplicates}")
