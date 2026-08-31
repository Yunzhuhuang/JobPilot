"""The verification report contract.

One module defines what "fabricated" means, and the primary metric is a count
this schema carries. The pipeline's verification node and the harness scorer
both produce a `VerificationReport` -- shared code, never a shared run.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# What a claim unit asserts. Only the first six are checkable against a
# profile; `other` exists so the decomposer can be honest about the rest
# instead of forcing everything into a checkable box.
ElementKind = Literal[
    "tool", "company", "title", "metric", "date", "credential", "other"
]

# PRD 5.8's three values. `softened` is given a definition the PRD leaves open:
# a unit that asserts nothing checkable. Not fabricated, but not evidence
# either -- and counting it separately is what stops a resume from scoring a
# perfect zero by retreating into vagueness, the exact failure mode a
# fabrication-only metric rewards.
ClaimStatus = Literal["supported", "softened", "unsupported"]


class Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClaimElement(Base):
    kind: ElementKind
    value: str = Field(min_length=1)


class ClaimUnit(Base):
    """One sentence or bullet of a generated document."""

    unit_id: str = Field(pattern=r"^u\d{2,3}$")
    text: str = Field(min_length=1)
    section: str
    """Where in the document it sits: experience, projects, skills, summary…"""
    container_id: str | None = None
    """The profile id the claim attaches to (`exp_1`, `proj_2`), when the unit
    sits under a named employer or project. None for a skills line or a general
    sentence, where placement cannot be wrong."""
    elements: list[ClaimElement] = Field(default_factory=list)

    line_index: int = -1
    """First source line of this unit, 0-based. -1 when unknown."""
    line_end: int = -1
    """Last source line, inclusive -- a soft-wrapped bullet spans several.

    Both default, deliberately: `eval/results/*/verification/*.json` holds
    reports written before these existed and `Base` forbids extra keys, so a
    *required* field here would invalidate every cached verification and make
    a schema change cost a full re-run of every stage."""


class UnitVerdict(Base):
    unit_id: str
    status: ClaimStatus
    reasons: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    """Profile ids backing the claim -- `exp_2`, `proj_1_b3`."""


class Agreement(Base):
    """Where the deterministic rules and the LLM judge differ."""

    compared: int
    agreed: int
    rate: float
    disagreements: list[str] = Field(default_factory=list)
    """One readable line per unit, carrying both verdicts and both reasons."""


class VerificationReport(Base):
    document: str
    profile: str
    model: str
    verified_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    units: list[ClaimUnit]
    rules: list[UnitVerdict]
    """The primary path. Deterministic, so re-scoring an unchanged document
    cannot move the number."""
    judge: list[UnitVerdict] = Field(default_factory=list)
    """PRD 5.8's LLM verifier, as a cross-check. Empty when --no-judge."""
    agreement: Agreement | None = None
    writing_preference_violations: list[str] = Field(default_factory=list)

    @property
    def fabricated_claims(self) -> int:
        """The primary metric: units the rules path rejects."""
        return sum(1 for v in self.rules if v.status == "unsupported")

    @property
    def softened_claims(self) -> int:
        return sum(1 for v in self.rules if v.status == "softened")

    @property
    def supported_claims(self) -> int:
        return sum(1 for v in self.rules if v.status == "supported")
