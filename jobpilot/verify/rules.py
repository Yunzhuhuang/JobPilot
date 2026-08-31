"""The deterministic adjudicator -- the primary metric's path.

No LLM. The same document always scores the same, which is the whole argument
for this path existing alongside the judge: a stage-to-stage delta has to be
caused by the stage, not by a judge having a different day.
"""

from __future__ import annotations

import re

from jobpilot.profile.claims import classify_claim
from jobpilot.profile.schema import Profile
from jobpilot.verify.schema import ClaimElement, ClaimUnit, UnitVerdict

# Kinds a profile can actually settle. `other` is deliberately excluded: a unit
# asserting only uncheckable things is `softened`, not `supported`.
CHECKABLE = {"tool", "company", "title", "metric", "date", "credential"}

# Sections where a title or company name is *attached* to something, so
# naming the wrong one is a claim about where the work happened. Elsewhere
# -- a summary line, a skills line -- the same words are self-description.
CONTAINER_SECTIONS = {"experience", "projects"}

_MULTIPLIERS = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}


def adjudicate(units: list[ClaimUnit], profile: Profile) -> list[UnitVerdict]:
    numbers = _profile_numbers(profile)
    names = _profile_names(profile)
    return [_judge_unit(unit, profile, numbers, names) for unit in units]


def _judge_unit(
    unit: ClaimUnit,
    profile: Profile,
    numbers: set[float],
    names: dict[str, set[str]],
) -> UnitVerdict:
    reasons: list[str] = []
    evidence: list[str] = []
    checked = 0

    for element in unit.elements:
        if element.kind not in CHECKABLE:
            continue
        checked += 1
        ok, reason, ids = _check(element, unit, profile, numbers, names)
        if ok:
            evidence.extend(ids)
        else:
            reasons.append(reason)

    if reasons:
        status = "unsupported"
    elif checked:
        status = "supported"
    elif unit.container_id:
        # A role or project heading that resolved against the profile. The
        # match is itself the evidence -- nothing was asserted beyond "this
        # employer exists in my history", and it does.
        status = "supported"
        evidence.append(unit.container_id)
    else:
        # Nothing to check. Not fabricated, not evidence either.
        status = "softened"
        reasons.append("asserts nothing checkable against the profile")

    return UnitVerdict(
        unit_id=unit.unit_id,
        status=status,
        reasons=reasons,
        evidence_ids=sorted(set(evidence)),
    )


def _check(
    element: ClaimElement,
    unit: ClaimUnit,
    profile: Profile,
    numbers: set[float],
    names: dict[str, set[str]],
) -> tuple[bool, str, list[str]]:
    value = element.value.strip()

    if element.kind == "tool":
        # Reuses the placement rule: a tool used at one employer is not
        # supported at a different one, and a self_study tool cannot sit in a
        # bullet at all.
        verdict = classify_claim(profile, value, unit.container_id)
        if verdict.status == "unsupported":
            # A vendor prefix is not a different tool. The profile says
            # "Amazon API Gateway"; a resume writing "AWS API Gateway" is
            # naming the same service, and rejecting it would be a false
            # reject rather than a caught fabrication.
            for variant in _tool_variants(value):
                retry = classify_claim(profile, variant, unit.container_id)
                if retry.status != "unsupported":
                    verdict = retry
                    break
        if verdict.status == "supported":
            return True, "", [unit.container_id] if unit.container_id else []

        # Last resort: the author's own words, in the right place. `Alexa` and
        # `GSI` are named in exp_2's real bullets but are not tools anyone would
        # write a tool_evidence entry for, and rejecting them would flag a line
        # copied verbatim from the profile. Scoped to the unit's own container,
        # so a tool swapped into the wrong job (Kafka for SQS at Amazon) is
        # still caught.
        source = _bullet_naming(profile, value, unit.container_id)
        if source:
            return True, "", [source]

        return False, f"tool {value!r} [{verdict.status}] -- {verdict.reason}", []

    if element.kind == "metric":
        found = _numbers_in(value)
        if not found:
            return True, "", []
        missing = [n for n in found if not _matches_any(n, numbers)]
        if missing:
            shown = ", ".join(_fmt(n) for n in missing)
            return False, f"metric {value!r}: {shown} is not in the profile", []
        return True, "", []

    if element.kind in {"company", "title"}:
        # Scoped to where a title is *attached* to an employer. In a summary
        # line, "Backend engineer building public-facing APIs" describes what
        # the candidate is, not a job title held at a company, and rejecting it
        # rejects an ordinary true sentence. `iter3a` surfaced exactly that
        # case: the rules path called it unsupported, the LLM judge called it
        # supported, and the judge was right.
        #
        # This narrows the rule, it does not weaken it. Inflation inside an
        # experience or project heading -- "Senior Staff Engineer" at a company
        # where the profile says "Software Development Engineer" -- is still
        # caught, which `tests/test_rules_scope.py` pins.
        if unit.section not in CONTAINER_SECTIONS:
            return True, "", []
        # Token-subset, not equality: a resume that shortens "Software
        # Development Engineer - Alexa Kitchen" to "Software Development
        # Engineer" is abbreviating, not inventing. Inflation still fails --
        # "Senior Software Engineer" adds a token the profile does not have.
        if _covered(value, names[element.kind]):
            return True, "", []
        return False, f"{element.kind} {value!r} matches no profile entry", []

    if element.kind == "date":
        # A resume writes "May 2025 to Aug 2025"; the profile stores "2025-05".
        # Comparing the strings rejected every employment heading in every
        # document -- a false reject that swamped the real findings.
        claimed = _dates_in(value)
        if not claimed:
            return True, "", []
        missing = [d for d in claimed if d not in names["date"]]
        if missing:
            shown = ", ".join(missing)
            return False, f"date {value!r}: {shown} is not in the profile", []
        return True, "", []

    if element.kind == "credential":
        if _covered(value, names["credential"]):
            return True, "", []
        return False, f"credential {value!r} matches no profile entry", []

    return True, "", []


def _bullet_naming(
    profile: Profile, value: str, container_id: str | None
) -> str | None:
    """The id of a profile bullet that names this term in its own words.

    Scoped to `container_id` when the claim sits under a role or project, so
    this can never rescue a tool moved to the wrong employer.
    """
    pattern = re.compile(rf"\b{re.escape(value.strip())}\b", re.I)
    for container in (*profile.experience, *profile.projects):
        if container_id and container.id != container_id:
            continue
        for bullet in container.bullets:
            if pattern.search(bullet.text):
                return bullet.id
    return None


_VENDORS = ("aws", "amazon", "google", "google cloud", "gcp", "apache",
            "microsoft", "azure")


def _tool_variants(value: str) -> list[str]:
    """Other names for the same tool: vendor prefixes and parentheticals.

    A resume writes "Kubernetes (EKS)" or "MySQL (RDS)" -- one string naming
    two things the profile holds separately. Splitting it is not leniency; the
    claim is supported if either name is.
    """
    text = value.strip()
    variants: list[str] = []

    if "(" in text and ")" in text:
        outer = re.sub(r"\s*\([^)]*\)", "", text).strip()
        inner = re.findall(r"\(([^)]*)\)", text)
        variants.extend(v for v in [outer, *inner] if v)

    if text.lower().endswith("s"):
        variants.append(text[:-1])
    for tail in (" protocol", " protocols", " apis", " api"):
        if text.lower().endswith(tail):
            variants.append(text[: -len(tail)])

    if "/" in text:
        variants.extend(part.strip() for part in text.split("/") if part.strip())

    lowered = text.lower()
    for vendor in _VENDORS:
        if lowered.startswith(f"{vendor} "):
            variants.append(text[len(vendor) + 1 :])
    variants.extend(f"{vendor} {text}" for vendor in ("Amazon", "AWS"))
    return variants


_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _dates_in(text: str) -> set[str]:
    """Every date a claim states, as `YYYY-MM` (or `YYYY` when only a year).

    "Present" and "Current" assert no date and are ignored rather than
    rejected.
    """
    found: set[str] = set()
    lowered = text.lower()

    for month, year in re.findall(
        r"\b(jan|feb|mar|apr|may|jun|jul|aug|sept|sep|oct|nov|dec)[a-z]*\.?\s+(\d{4})\b",
        lowered,
    ):
        found.add(f"{year}-{_MONTHS[month]:02d}")

    for year, month in re.findall(r"\b(\d{4})-(\d{2})\b", lowered):
        found.add(f"{year}-{month}")

    if not found:
        # A bare year, when no month is given anywhere in the value.
        found.update(re.findall(r"\b(19|20)\d{2}\b", lowered) and
                     re.findall(r"\b((?:19|20)\d{2})\b", lowered))
    return found


def _covered(value: str, known: set[str]) -> bool:
    """True when every word of the claim appears in one known name."""
    words = set(normalize(value).split())
    if not words:
        return False
    return any(words <= set(name.split()) for name in known)


def _profile_numbers(profile: Profile) -> set[float]:
    """Every number the profile states -- in its prose *and* its typed fields.

    The typed half was missing until 2026-08-30, and it cost the primary metric
    its meaning for one stage: `education.gpa` is a float field rather than
    prose, so a resume line reading "GPA 3.8" was adjudicated `unsupported`
    against a profile that literally stores 3.8. Ten of `iter3`'s eleven
    flagged claims were that one bug, which would have been reported as the
    tailor fabricating.

    This is the same class of false reject that walked the baseline down
    8.13 -> 1.6, and the lesson is the one CLAUDE.md already records: a number
    the profile knows must be reachable however the schema happens to hold it.
    """
    found: set[float] = set()
    for container in (*profile.experience, *profile.projects):
        for bullet in container.bullets:
            found.update(_numbers_in(bullet.text))
        found.update(_numbers_in(getattr(container, "one_liner", "")))
    for entry in profile.tool_evidence:
        found.update(_numbers_in(entry.evidence))
    for exemplar in profile.style_exemplars:
        found.update(_numbers_in(exemplar.text))
    for education in profile.education:
        if education.gpa is not None:
            found.add(float(education.gpa))
    return found


def _profile_names(profile: Profile) -> dict[str, set[str]]:
    companies = {normalize(e.company) for e in profile.experience}
    companies |= {normalize(p.name) for p in profile.projects}
    companies |= {normalize(e.school) for e in profile.education}
    titles = {normalize(e.title) for e in profile.experience}
    titles |= {normalize(p.one_liner) for p in profile.projects}
    dates: set[str] = set()
    for entry in (*profile.experience, *profile.education):
        dates.add(entry.start)
        dates.add(entry.start.split("-")[0])
        if entry.end:
            dates.add(entry.end)
            dates.add(entry.end.split("-")[0])
    for project in profile.projects:
        dates.update(_dates_in(project.one_liner))
    credentials = {normalize(f"{e.degree} {e.field}") for e in profile.education}
    credentials |= {normalize(e.degree) for e in profile.education}
    credentials |= {
        normalize(f"{e.degree} {e.field} {e.school}") for e in profile.education
    }
    return {
        "company": companies,
        "title": titles,
        "date": dates,
        "credential": credentials,
    }


def _numbers_in(text: str) -> set[float]:
    """Numbers a claim rests on, with K/M/B expanded and commas removed."""
    found: set[float] = set()
    for raw, suffix in re.findall(r"(\d[\d,]*\.?\d*)\s*([KkMmBb])?", text):
        try:
            value = float(raw.replace(",", ""))
        except ValueError:
            continue
        if suffix:
            value *= _MULTIPLIERS[suffix.lower()]
        found.add(value)
    return found


def _matches_any(number: float, known: set[float]) -> bool:
    return number in known


def _fmt(number: float) -> str:
    return str(int(number)) if number == int(number) else str(number)


def normalize(text: str) -> str:
    """Lowercase, strip punctuation and corporate suffixes."""
    cleaned = re.sub(r"[^a-z0-9 ]+", " ", text.lower())
    cleaned = re.sub(
        r"\b(inc|llc|ltd|corp|co|company|services|usa|the|in|of|at|and|a)\b",
        " ",
        cleaned,
    )
    return re.sub(r"\s+", " ", cleaned).strip()


def writing_preference_violations(document: str, profile: Profile) -> list[str]:
    """Document-level checks from `profile.writing_preferences`."""
    problems: list[str] = []
    prefs = profile.writing_preferences

    # ~4000 characters is about a page of resume text at typical density.
    max_chars = prefs.resume_max_pages * 4000
    if len(document) > max_chars:
        problems.append(
            f"document is {len(document)} chars; resume_max_pages="
            f"{prefs.resume_max_pages} allows roughly {max_chars}"
        )

    if prefs.no_single_bullet_projects:
        for heading, bullets in _sections(document):
            if 0 < len(bullets) < 2 and "project" in heading.lower():
                problems.append(f"project section {heading!r} has a single bullet")

    return problems


def _sections(document: str) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = []
    heading = ""
    bullets: list[str] = []
    for line in document.splitlines():
        if line.startswith("#"):
            if heading:
                sections.append((heading, bullets))
            heading, bullets = line.lstrip("# ").strip(), []
        elif line.strip().startswith(("-", "*")):
            bullets.append(line.strip())
    if heading:
        sections.append((heading, bullets))
    return sections
