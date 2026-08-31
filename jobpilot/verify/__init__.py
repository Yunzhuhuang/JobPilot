"""Verification: one document in, a report out.

Two independent verdicts over one shared decomposition, so they are comparable
rather than two opinions about two different readings:

    segment (code, deterministic)
        |
    extract elements (LLM, no profile)
        |-- rules  (code, the primary metric -- zero variance)
        `-- judge  (LLM, PRD 5.8 -- the cross-check)

The rules path is what the changelog quotes. Where the two disagree is itself a
finding, and the report keeps every instance rather than reconciling them.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from jobpilot.config import Config, load_config
from jobpilot.profile.schema import Profile
from jobpilot.verify.llm import analyse
from jobpilot.verify.rules import adjudicate, writing_preference_violations
from jobpilot.verify.schema import (
    Agreement,
    ClaimUnit,
    UnitVerdict,
    VerificationReport,
)
from jobpilot.verify.segment import segment

__all__ = [
    "Agreement",
    "ClaimUnit",
    "UnitVerdict",
    "VerificationReport",
    "strip_units",
    "verify",
]


def strip_units(document: str, units: list[ClaimUnit]) -> tuple[str, int]:
    """Delete the given units' source lines. Returns (document, lines removed).

    The `on exhaustion` path of PRD 5.1: after two failed revisions the
    offending lines come out. Deliberately plain Python -- deleting a line is
    not a judgement call, and asking a model to do it would let the last step
    before a packet is written introduce a claim of its own.

    Uses `ClaimUnit.line_index`/`line_end` rather than matching text, because a
    soft-wrapped bullet spans several lines and a substring search would remove
    the wrong one. Units without provenance (`line_index < 0`, from a report
    cached before the field existed) are skipped rather than guessed at.
    """
    doomed: set[int] = set()
    for unit in units:
        if unit.line_index < 0:
            continue
        doomed.update(range(unit.line_index, max(unit.line_end, unit.line_index) + 1))
    if not doomed:
        return document, 0
    kept = [
        line for i, line in enumerate(document.splitlines()) if i not in doomed
    ]
    return "\n".join(kept).rstrip() + "\n", len(doomed)


def verify(
    document: str,
    profile: Profile,
    *,
    document_name: str = "document.md",
    profile_name: str = "profile.json",
    config: Config | None = None,
    use_judge: bool = True,
) -> VerificationReport:
    config = config or load_config()

    units, judged = analyse(
        segment(document, profile), profile, config, use_judge=use_judge
    )
    rules = adjudicate(units, profile)

    return VerificationReport(
        document=document_name,
        profile=profile_name,
        model=config.model.id,
        verified_at=date.today().isoformat(),
        units=units,
        rules=rules,
        judge=judged,
        agreement=compare(units, rules, judged) if judged else None,
        writing_preference_violations=writing_preference_violations(
            document, profile
        ),
    )


def verify_file(
    path: Path, profile: Profile, *, use_judge: bool = True, **kwargs: object
) -> VerificationReport:
    return verify(
        path.read_text(),
        profile,
        document_name=path.name,
        use_judge=use_judge,
        **kwargs,  # type: ignore[arg-type]
    )


def compare(
    units: list[ClaimUnit], rules: list[UnitVerdict], judged: list[UnitVerdict]
) -> Agreement:
    """Where the whitelist and the judge differ, kept rather than reconciled."""
    by_unit = {v.unit_id: v for v in judged}
    text = {u.unit_id: u.text for u in units}

    compared = agreed = 0
    disagreements: list[str] = []
    for verdict in rules:
        other = by_unit.get(verdict.unit_id)
        if other is None:
            # The judge dropped a unit; that is itself a disagreement.
            disagreements.append(
                f"{verdict.unit_id}  rules={verdict.status}  judge=<missing>  "
                f"| {text.get(verdict.unit_id, '')[:80]}"
            )
            continue
        compared += 1
        if other.status == verdict.status:
            agreed += 1
            continue
        disagreements.append(
            f"{verdict.unit_id}  rules={verdict.status}  judge={other.status}\n"
            f"    text  : {text.get(verdict.unit_id, '')[:110]}\n"
            f"    rules : {'; '.join(verdict.reasons) or '-'}\n"
            f"    judge : {'; '.join(other.reasons) or '-'}"
        )

    return Agreement(
        compared=compared,
        agreed=agreed,
        rate=round(agreed / compared, 3) if compared else 0.0,
        disagreements=disagreements,
    )
