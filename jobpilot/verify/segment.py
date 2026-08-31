"""Split a document into claim units -- deterministically, in code.

This was an LLM pass first, and it moved between runs: one run emitted nine
units, the next six, silently dropping the employer headings and with them a
fabricated employer. A primary metric whose unit boundaries wander is not
reproducible, and the fix is to take the judgement out of segmentation
entirely. Markdown structure decides the units; the LLM only labels what each
one asserts.

`container_id` is resolved by matching a role heading against the profile's own
company and project names, so a generated document needs no ids embedded in it.
"""

from __future__ import annotations

import re

from jobpilot.profile.schema import Profile
from jobpilot.verify.rules import normalize
from jobpilot.verify.schema import ClaimUnit

SECTION_WORDS = {
    "experience": "experience",
    "employment": "experience",
    "work": "experience",
    "projects": "projects",
    "project": "projects",
    "skills": "skills",
    "education": "education",
    "summary": "summary",
    "profile": "summary",
    "objective": "summary",
}

# Contact lines, page furniture, and other non-claims.
_NOISE = re.compile(
    r"^\s*$|^[-*_]{3,}$|@|linkedin\.com|github\.com|^\|", re.I
)


def segment(document: str, profile: Profile) -> list[ClaimUnit]:
    containers = _container_names(profile)
    units: list[ClaimUnit] = []
    section = "other"
    container_id: str | None = None
    counter = 0

    for line_no, line in enumerate(document.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            heading = stripped.lstrip("# ").strip()
            if level <= 2:
                section = _section_of(heading)
                container_id = None
                continue
            # A role or project heading: resolve it, and emit it as a unit so
            # an invented employer is itself a checkable claim.
            container_id = _match_container(heading, containers)
            counter += 1
            units.append(
                ClaimUnit(
                    unit_id=f"u{counter:02d}",
                    text=heading,
                    section=section,
                    container_id=container_id,
                    line_index=line_no,
                    line_end=line_no,
                )
            )
            continue

        starts_bullet = bool(re.match(r"^[-*+]\s+", stripped))
        if _NOISE.search(stripped) and not starts_bullet:
            continue

        text = re.sub(r"^[-*+]\s+", "", stripped)
        if len(text) < 12:
            continue

        # A soft-wrapped bullet continues the one above it. Deciding that by
        # capitalization was wrong -- "Alexa-owned, third-party, ..." is a
        # continuation that happens to start with a capital.
        if (
            not starts_bullet
            and units
            and units[-1].section == section
            and units[-1].container_id == container_id
            and _continues(units[-1].text)
        ):
            units[-1] = units[-1].model_copy(
                update={"text": f"{units[-1].text} {text}", "line_end": line_no}
            )
            continue

        counter += 1
        units.append(
            ClaimUnit(
                unit_id=f"u{counter:02d}",
                text=text,
                section=section,
                container_id=container_id,
                line_index=line_no,
                line_end=line_no,
            )
        )

    return [
        u.model_copy(update={"unit_id": f"u{i:02d}"})
        for i, u in enumerate(units, start=1)
    ]


def _continues(previous: str) -> bool:
    """True when the previous unit reads as an unfinished sentence."""
    return not previous.rstrip().endswith((".", ":", "!", "?"))


def _section_of(heading: str) -> str:
    for word in normalize(heading).split():
        if word in SECTION_WORDS:
            return SECTION_WORDS[word]
    return "other"


def _container_names(profile: Profile) -> list[tuple[str, str]]:
    names = [(normalize(e.company), e.id) for e in profile.experience]
    names += [(normalize(p.name), p.id) for p in profile.projects]
    return names


def _match_container(heading: str, containers: list[tuple[str, str]]) -> str | None:
    words = set(normalize(heading).split())
    for name, container_id in containers:
        name_words = set(name.split())
        if name_words and name_words <= words:
            return container_id
    return None
