"""Pydantic models for `profile.json` (PRD 4.1).

This file is the spine of the project. The triage node reads it to judge fit,
the tailoring node draws its material from it, and the verifier treats it as a
whitelist: a generated claim is *fabricated* precisely when it cannot be traced
to an id here. The primary metric is defined by this schema, so every model
forbids extra keys -- a typo'd field is a loud error, never a setting that
silently does nothing.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1

# `YYYY-MM`. Deliberately coarser than a full date: a resume states months, and
# storing a precision the source doesn't have would invite the verifier to
# treat an invented day as supported.
MONTH = r"^\d{4}-(0[1-9]|1[0-2])$"

# Where a piece of tool evidence comes from. `self_study` is the escape hatch
# for a tool used outside any listed role or project.
EvidenceLocation = str

Source = Literal["onboarding", "gap_question", "manual_update"]
ExemplarKind = Literal["resume_bullet", "cover_letter_paragraph"]


class Base(BaseModel):
    """Shared config: no undeclared keys anywhere in the profile."""

    model_config = ConfigDict(extra="forbid")


class Identity(Base):
    """Public-resume-level identity only.

    No phone number, street address, or ID numbers (PRD 3, ground rules 06-08).
    `email` may be a public contact address.
    """

    name: str = Field(min_length=1)
    email: str = Field(min_length=3)
    location: str
    linkedin: str
    github: str | None = None
    open_to_relocation: bool


class Constraints(Base):
    """Hard constraints. A JD violating one of these is a `skip`."""

    needs_sponsorship: bool
    target_roles: list[str] = Field(min_length=1)
    excluded_locations: list[str]
    earliest_start: str = Field(pattern=MONTH)


class Education(Base):
    id: str = Field(pattern=r"^edu_\d+$")
    school: str
    degree: str
    field: str
    start: str = Field(pattern=MONTH)
    end: str | None = Field(default=None, pattern=MONTH)
    gpa: float | None = None
    coursework: list[str] = Field(default_factory=list)


class Bullet(Base):
    """One achievement, in the author's own words.

    `tools` is the claim surface: naming a tool here asserts it was used for
    *this* achievement, so every entry must also carry `tool_evidence`.
    """

    id: str
    text: str = Field(min_length=1)
    tools: list[str] = Field(default_factory=list)


class Experience(Base):
    id: str = Field(pattern=r"^exp_\d+$")
    company: str
    title: str
    start: str = Field(pattern=MONTH)
    # None means current.
    end: str | None = Field(default=None, pattern=MONTH)
    bullets: list[Bullet]
    tools: list[str] = Field(default_factory=list)
    """Union of the bullets' tools, plus anything else used in the role."""


class Project(Base):
    id: str = Field(pattern=r"^proj_\d+$")
    name: str
    one_liner: str
    bullets: list[Bullet]
    tools: list[str] = Field(default_factory=list)
    link: str | None = None


class Skills(Base):
    """The seven buckets of PRD 4.1.

    A skill listed here is *not* claimable on its own -- only `tool_evidence`
    and bullet `tools` are. This block exists for the resume's skills line.
    """

    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    cloud_infra: list[str] = Field(default_factory=list)
    data: list[str] = Field(default_factory=list)
    ai_ml: list[str] = Field(default_factory=list)
    testing: list[str] = Field(default_factory=list)
    other: list[str] = Field(default_factory=list)


class ToolEvidence(Base):
    """One claimable tool and the sentence that earns it.

    `aliases` is what makes JD matching work without an LLM: a posting asking
    for "Postgres" has to resolve to "PostgreSQL".
    """

    tool: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    where: EvidenceLocation
    evidence: str = Field(min_length=1)
    source: Source
    added_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class NotExperienced(Base):
    """A do-not-ask-again, do-not-claim entry.

    Written when the author answers "no" to a gap question. The gap-diff never
    re-asks about a tool listed here, and the verifier rejects any claim to it.
    """

    tool: str = Field(min_length=1)
    asked_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    context_jd: str | None = None


class StyleExemplar(Base):
    """A short piece of the author's own approved writing, used to steer voice.

    Only steers voice -- the verifier still checks every fact in an exemplar
    like any other text.
    """

    kind: ExemplarKind
    text: str = Field(min_length=1)
    provenance: str


class WritingPreferences(Base):
    resume_max_pages: int = Field(default=1, gt=0)
    no_single_bullet_projects: bool = True
    voice: str
    flag_gaps_instead_of_fabricating: bool = True


class Profile(Base):
    schema_version: int = SCHEMA_VERSION
    identity: Identity
    constraints: Constraints
    education: list[Education]
    experience: list[Experience]
    projects: list[Project]
    skills: Skills
    tool_evidence: list[ToolEvidence]
    not_experienced: list[NotExperienced] = Field(default_factory=list)
    style_exemplars: list[StyleExemplar] = Field(default_factory=list)
    writing_preferences: WritingPreferences
