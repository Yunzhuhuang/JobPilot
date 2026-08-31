"""One function per PRD 7.1 metric.

Every number in the README and CHANGELOG comes from here, via
`eval/results/<stage>/summary.json`. Nothing is ever typed by hand.

A metric whose input does not exist yet reports `None` with a stated reason
rather than 0 -- a zero reads like a result. That applies to a metric with no
true positives to find as much as to one with no input file: see
`score_non_sponsors`, where the fixture contains no employer-level non-sponsor
and saying "0 dropped" would misreport an empty question as a failed answer.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from jobpilot.config import REPO_ROOT, Config
from jobpilot.eval.run_record import JDRecord, RunRecord, read_run_record
from jobpilot.profile.loader import (
    DEFAULT_PROFILE_PATH,
    FROZEN_PROFILE_PATH,
    load_profile,
)
from jobpilot.profile.schema import Profile
from jobpilot.requirements import RequirementSet, load_requirements
from jobpilot.verify import VerificationReport, verify

LABELS_PATH = REPO_ROOT / "fixture" / "labels.json"
H1B_TRUTH_PATH = REPO_ROOT / "fixture" / "h1b_truth.json"

# Only these requirement types can ever match a tool whitelist. `concept`,
# `experience` and `credential` are a third of the extracted requirements
# ("Networking", "Refactoring", "BS in Computer Science") and no amount of
# tailoring makes them appear as tools -- counting them would cap coverage far
# below 100% for reasons no stage can move, burying the iter4 signal in noise.
COVERABLE_TYPES = {"language", "framework", "cloud_infra", "data", "ai_ml", "testing"}

LABEL_ORDER = ("most_matched", "less_matched", "skip")


class Metric(BaseModel):
    """A number, or an honest absence of one."""

    model_config = ConfigDict(extra="forbid")

    value: float | None = None
    unit: str = ""
    detail: str = ""
    unavailable: str | None = None
    """Why there is no value. Set means `value` is None by design, not failure."""


class Scores(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fabricated_claims_per_resume: Metric
    softened_claims_per_resume: Metric
    rules_vs_judge_agreement: Metric
    triage_agreement: Metric
    jd_keyword_coverage: Metric
    baseline_same_jds: Metric = Metric(
        unit="claims/resume",
        unavailable="only meaningful for a stage that generates resumes",
    )
    revision_rounds_per_doc: Metric = Metric(
        unit="rounds", unavailable="this stage ran no verifier node"
    )
    non_sponsors_dropped: Metric
    h1b_resolution: Metric = Metric(
        unit="%", unavailable="this stage predates the H-1B node"
    )
    gap_questions_run1_to_run2: Metric
    cost_per_jd_usd: Metric
    wall_clock_per_jd_s: Metric
    resumes_scored: int = 0
    jds_total: int = 0
    jds_failed: int = 0
    confusion: dict[str, dict[str, int]] = Field(default_factory=dict)


# --------------------------------------------------------------------------
# Verification, with a content-addressed cache. Scoring re-verifies every
# resume at two LLM calls each; without this, --all-stages re-pays for seven
# stages that have not moved.
# --------------------------------------------------------------------------


def verification_for(
    resume_path: Path,
    profile: Profile,
    config: Config,
    cache_dir: Path,
    *,
    use_judge: bool = True,
    refresh: bool = False,
) -> VerificationReport:
    document = resume_path.read_text()
    key = hashlib.sha256(
        "\n".join(
            [document, profile.model_dump_json(), config.model.id, str(use_judge)]
        ).encode()
    ).hexdigest()[:16]
    cached = cache_dir / f"{resume_path.parent.name}-{key}.json"

    if cached.is_file() and not refresh:
        report = VerificationReport.model_validate(json.loads(cached.read_text()))
        # The cache holds the LLM passes -- segmentation and element
        # extraction. The deterministic verdict is recomputed on every load, so
        # a fix to the rules takes effect immediately and costs nothing. The
        # cache key covers the document, profile and model, not the rule
        # version, and this is what makes that correct rather than stale.
        return _readjudicate(report, profile)

    report = verify(
        document,
        profile,
        document_name=str(resume_path),
        profile_name="fixture/profile.json",
        config=config,
        use_judge=use_judge,
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached.write_text(report.model_dump_json(indent=2) + "\n")
    return report


def _readjudicate(report: VerificationReport, profile: Profile) -> VerificationReport:
    from jobpilot.verify import compare
    from jobpilot.verify.rules import adjudicate

    rules = adjudicate(report.units, profile)
    return report.model_copy(
        update={
            "rules": rules,
            "agreement": (
                compare(report.units, rules, report.judge) if report.judge else None
            ),
        }
    )


# --------------------------------------------------------------------------
# Scorers
# --------------------------------------------------------------------------


def scoring_profile(record: RunRecord) -> Profile:
    """The profile a stage's output is judged against.

    Always the **frozen** `fixture/profile.json` -- that is what makes a
    stage-to-stage delta mean anything, and no run may move its own goalposts.

    One bounded exception, for stages with `gap_memory`. `iter4` exists to
    *expand* the profile: the author is asked whether they have used a tool and
    their answer is written back. A resume that then uses `Ruby` is correct, but
    the frozen copy predates the answer and scores it `unsupported` -- a
    fabrication that is really a timestamp problem. Observed 2026-08-31: the one
    flagged claim in `iter4` was `Ruby`, confirmed by the author minutes earlier.

    So gap-acquired evidence is added back, and *only* that: entries whose
    `source` is `gap_question`. Everything else about the frozen profile stands,
    so a stage still cannot grant itself a claim by any other route.
    """
    frozen = load_profile(FROZEN_PROFILE_PATH)
    if not record.flags.get("gap_memory"):
        return frozen
    working = load_profile(DEFAULT_PROFILE_PATH)
    known = {(e.tool, e.where) for e in frozen.tool_evidence}
    acquired = [
        e
        for e in working.tool_evidence
        if e.source == "gap_question" and (e.tool, e.where) not in known
    ]
    if not acquired:
        return frozen
    return frozen.model_copy(
        update={"tool_evidence": [*frozen.tool_evidence, *acquired]}
    )


def score_fabrication(reports: dict[str, VerificationReport]) -> tuple[Metric, Metric]:
    """The primary metric, and its vagueness counterweight."""
    if not reports:
        reason = "no resumes were produced by this run"
        return (
            Metric(unit="claims/resume", unavailable=reason),
            Metric(unit="claims/resume", unavailable=reason),
        )

    fabricated = [r.fabricated_claims for r in reports.values()]
    softened = [r.softened_claims for r in reports.values()]
    worst = max(reports.items(), key=lambda kv: kv[1].fabricated_claims)
    return (
        Metric(
            value=round(sum(fabricated) / len(fabricated), 3),
            unit="claims/resume",
            detail=(
                f"{sum(fabricated)} across {len(fabricated)} resumes; "
                f"worst {worst[0]} with {worst[1].fabricated_claims}"
            ),
        ),
        Metric(
            value=round(sum(softened) / len(softened), 3),
            unit="claims/resume",
            detail=f"{sum(softened)} across {len(softened)} resumes",
        ),
    )


def score_baseline_on(
    jd_ids: set[str],
    profile: Profile,
    config: Config,
    *,
    use_judge: bool = True,
) -> Metric:
    """The baseline's fabrication rate over exactly the postings a stage tailored.

    The pipeline tailors `most_matched` only (PRD 5.1) -- five or six postings
    where the baseline wrote fifteen. Comparing those two averages directly
    would flatter the pipeline, and not by a little: the baseline's worst
    document is `jd_01` Canonical with 4 fabrications, and Canonical is
    `less_matched`, so the pipeline would never have written it at all.

    Costs nothing. Those baseline resumes are already verified and cached by
    `verification_for`, keyed on document + profile + model, so this is a cache
    read rather than a re-run.
    """
    from jobpilot.eval.report import results_dir
    from jobpilot.eval.run_record import latest_run

    directory = latest_run("baseline")
    if directory is None or not jd_ids:
        return Metric(
            unit="claims/resume",
            unavailable="no baseline run to compare against",
        )
    record = read_run_record(directory)
    paths = {
        jd_id: path
        for jd_id, path in resume_paths(record, directory).items()
        if jd_id in jd_ids
    }
    if not paths:
        return Metric(
            unit="claims/resume",
            unavailable="the baseline produced none of these postings",
        )
    cache = results_dir("baseline") / "verification"
    counts = [
        verification_for(
            path, profile, config, cache, use_judge=use_judge
        ).fabricated_claims
        for path in paths.values()
    ]
    return Metric(
        value=round(sum(counts) / len(counts), 3),
        unit="claims/resume",
        detail=(
            f"{sum(counts)} across the same {len(counts)} postings "
            f"({', '.join(sorted(paths))})"
        ),
    )


def score_judge_agreement(reports: dict[str, VerificationReport]) -> Metric:
    compared = sum(r.agreement.compared for r in reports.values() if r.agreement)
    agreed = sum(r.agreement.agreed for r in reports.values() if r.agreement)
    if not compared:
        return Metric(unit="%", unavailable="the judge path was not run (--no-judge)")
    return Metric(
        value=round(100 * agreed / compared, 1),
        unit="%",
        detail=f"{agreed}/{compared} claim verdicts matched",
    )


def score_triage(record: RunRecord, labels: dict[str, str]) -> tuple[Metric, dict]:
    """Exact-match agreement with the author's labels, plus a confusion table."""
    scored = [jd for jd in record.jds if jd.label is not None and jd.jd_id in labels]
    confusion = {
        truth: {predicted: 0 for predicted in LABEL_ORDER} for truth in LABEL_ORDER
    }
    for jd in scored:
        confusion[labels[jd.jd_id]][jd.label] += 1

    if not scored:
        return (
            Metric(unit="%", unavailable="no JD in this run carries a triage label"),
            confusion,
        )

    agreed = sum(1 for jd in scored if jd.label == labels[jd.jd_id])
    return (
        Metric(
            value=round(100 * agreed / len(scored), 1),
            unit="%",
            detail=f"{agreed}/{len(scored)} exact matches against fixture/labels.json",
        ),
        confusion,
    )


def coverage_for_resume(text: str, requirements: RequirementSet) -> tuple[int, int]:
    """(matched, total) over the required, tool-typed items of one JD."""
    wanted = [
        r for r in requirements.requirements if r.required and r.type in COVERABLE_TYPES
    ]
    lowered = text.lower()
    matched = 0
    for requirement in wanted:
        names = [requirement.name, *requirement.aliases]
        if any(re.search(rf"\b{re.escape(n.lower())}\b", lowered) for n in names):
            matched += 1
    return matched, len(wanted)


def score_coverage(resumes: dict[str, str]) -> Metric:
    requirements = load_requirements()
    matched = total = 0
    per_jd: list[str] = []
    for jd_id, text in sorted(resumes.items()):
        rs = requirements.get(jd_id)
        if rs is None:
            continue
        m, t = coverage_for_resume(text, rs)
        matched += m
        total += t
        if t:
            per_jd.append(f"{jd_id} {m}/{t}")

    if not total:
        return Metric(
            unit="%",
            unavailable="no tool-typed required items among the scored JDs",
        )
    return Metric(
        value=round(100 * matched / total, 1),
        unit="%",
        detail=f"{matched}/{total} required tool-typed items present -- "
        + ", ".join(per_jd),
    )


def score_non_sponsors(record: RunRecord) -> Metric:
    """Employer-level H-1B filter: correct drops, and — more important — false ones.

    A drop is destructive. A dropped JD never reaches triage and never reaches
    the digest, so the author never sees it; a false drop costs an application
    she would have sent. That asymmetry is why the false-drop count is reported
    even when the fixture has no true positives to find.
    """
    if not H1B_TRUTH_PATH.is_file():
        return Metric(unit="count", unavailable="fixture/h1b_truth.json is missing")

    truth = {
        k: v
        for k, v in json.loads(H1B_TRUTH_PATH.read_text()).items()
        if not k.startswith("_")
    }
    non_sponsors = {k for k, v in truth.items() if v.get("sponsors") is False}
    dropped = {jd.jd_id for jd in record.jds if jd.dropped_by_h1b}
    false_drops = dropped - non_sponsors

    if not non_sponsors:
        # Not a zero: a zero would read as "found none of the non-sponsors".
        # There are none to find. Every posting in this fixture is either
        # silent on sponsorship or bars the candidate at the ROLE level
        # (export control, clearance) -- which an employer-level lookup
        # cannot see. See fixture/h1b_truth.json.
        return Metric(
            unit="count",
            unavailable=(
                "no posting in the fixture states that the employer will not "
                "sponsor, so there are no true positives for this metric to "
                "find; the two constrained postings (jd_06, jd_14) are barred "
                "at the role level, which employer-level USCIS data cannot see"
            ),
            detail=(
                f"{len(dropped)} dropped, {len(false_drops)} of them false"
                + (f" ({', '.join(sorted(false_drops))})" if false_drops else "")
            ),
        )

    correct = dropped & non_sponsors
    return Metric(
        value=float(len(correct)),
        unit="count",
        detail=(
            f"{len(correct)}/{len(non_sponsors)} known non-sponsors dropped; "
            f"{len(false_drops)} false drops"
            + (f" ({', '.join(sorted(false_drops))})" if false_drops else "")
        ),
    )


def score_h1b_resolution(record: RunRecord) -> Metric:
    """Did the node identify the right USCIS employer? The H-1B node's own metric.

    This is the number the sponsorship question actually rests on: an
    approval count attached to the wrong company is worse than no count,
    because it reads as evidence. `fixture/h1b_truth.json` records the
    accepted entity (sometimes more than one) and the evidence for it, and
    `[]` means the correct answer is to name nobody -- OnePay is in the
    fixture precisely to catch an agent that invents an employer rather than
    return `unknown`.
    """
    graded = [jd for jd in record.jds if jd.sponsorship is not None]
    if not graded:
        return Metric(unit="%", unavailable="this stage ran no H-1B node")
    if not H1B_TRUTH_PATH.is_file():
        return Metric(unit="%", unavailable="fixture/h1b_truth.json is missing")

    truth = json.loads(H1B_TRUTH_PATH.read_text())
    correct, wrong, searched = 0, [], 0
    for jd in graded:
        entry = truth.get(jd.jd_id)
        if entry is None:
            continue
        searched += jd.h1b_searches
        accepted = entry.get("expected_entity", [])
        got = jd.matched_employer
        if (got in accepted) if accepted else (got is None):
            correct += 1
        else:
            wrong.append(f"{jd.jd_id}: {got or 'none'}")

    return Metric(
        value=round(100 * correct / len(graded), 1),
        unit="%",
        detail=(
            f"{correct}/{len(graded)} employers correctly identified; "
            f"{searched} index searches issued"
            + (f"; wrong: {', '.join(wrong)}" if wrong else "")
        ),
    )


def _cut_detail(exhausted: list[JDRecord]) -> str:
    return ", ".join(f"{jd.jd_id}: {jd.dropped_lines} lines cut" for jd in exhausted)


def score_revisions(record: RunRecord) -> Metric:
    """How hard the verifier had to work, and where it gave up.

    Reported because the primary metric cannot speak for this stage: the
    pipeline verifier and the harness scorer share code, so once the revision
    loop runs, fabrications go to ~0 largely by construction. What is *not*
    tautological is how many documents needed fixing, how many rounds it took,
    and how often the budget ran out and lines had to be cut in code.
    """
    if not record.flags.get("verifier_node"):
        # 0 rounds and "no verifier ran" are different facts, and a stage
        # without the node must not report the first.
        return Metric(unit="rounds", unavailable="this stage ran no verifier node")
    tailored = [jd for jd in record.jds if jd.packet and jd.label == "most_matched"]
    if not tailored:
        return Metric(unit="rounds", unavailable="this stage tailored nothing")
    revised = [jd for jd in tailored if jd.revision_rounds]
    exhausted = [jd for jd in tailored if jd.dropped_lines]
    total = sum(jd.revision_rounds for jd in tailored)
    return Metric(
        value=round(total / len(tailored), 2),
        unit="rounds",
        detail=(
            f"{total} rounds over {len(tailored)} documents; "
            f"{len(revised)} needed at least one; "
            f"{len(exhausted)} exhausted the budget"
            + (f" ({cut})" if (cut := _cut_detail(exhausted)) else "")
        ),
    )


def score_gap_questions(current: RunRecord, previous_dir: Path | None) -> Metric:
    asked_now = sum(len(jd.gap_questions) for jd in current.jds)
    if previous_dir is None:
        return Metric(
            value=float(asked_now),
            unit="questions",
            unavailable="only one run of this stage exists; run twice to see the drop",
            detail=f"{asked_now} asked in this run",
        )
    before = read_run_record(previous_dir)
    asked_before = sum(len(jd.gap_questions) for jd in before.jds)
    repeated = _repeated_questions(before, current)
    return Metric(
        value=float(asked_now),
        unit="questions",
        detail=(
            f"run 1 asked {asked_before}, run 2 asked {asked_now}; "
            f"{repeated} repeated (target 0)"
        ),
    )


def _repeated_questions(before: RunRecord, after: RunRecord) -> int:
    earlier = before.by_id()
    return sum(
        len(set(jd.gap_questions) & set(earlier[jd.jd_id].gap_questions))
        for jd in after.jds
        if jd.jd_id in earlier
    )


# Claude Opus 5, USD per million tokens. Cost is a reported figure, not a
# scored one, so an approximate rate is honest as long as the README says so.
RATES = {"claude-opus-5": (5.0, 25.0), "claude-sonnet-5": (2.0, 10.0)}


def score_cost(record: RunRecord) -> tuple[Metric, Metric]:
    if not record.jds:
        reason = "the run scored no JDs"
        return Metric(unit="USD/JD", unavailable=reason), Metric(
            unit="s/JD", unavailable=reason
        )

    rate_in, rate_out = RATES.get(record.model, (0.0, 0.0))
    tokens_in = sum(jd.input_tokens for jd in record.jds)
    tokens_out = sum(jd.output_tokens for jd in record.jds)
    seconds = sum(jd.wall_clock_s for jd in record.jds)
    n = len(record.jds)

    if not rate_in:
        cost = Metric(
            unit="USD/JD", unavailable=f"no published rate for {record.model}"
        )
    elif not tokens_in and not tokens_out:
        cost = Metric(unit="USD/JD", unavailable="the run recorded no token usage")
    else:
        total = tokens_in / 1e6 * rate_in + tokens_out / 1e6 * rate_out
        cost = Metric(
            value=round(total / n, 4),
            unit="USD/JD",
            detail=f"{tokens_in} in / {tokens_out} out over {n} JDs at {record.model}",
        )

    wall = (
        Metric(unit="s/JD", unavailable="the run recorded no timings")
        if not seconds
        else Metric(value=round(seconds / n, 2), unit="s/JD",
                    detail=f"{round(seconds, 1)}s over {n} JDs")
    )
    return cost, wall


def load_labels() -> dict[str, str]:
    if not LABELS_PATH.is_file():
        raise FileNotFoundError(f"no author labels at {LABELS_PATH}")
    return json.loads(LABELS_PATH.read_text())


def failure_summary(record: RunRecord) -> tuple[int, Counter[str]]:
    failed = [jd for jd in record.jds if jd.error]
    return len(failed), Counter(jd.error or "" for jd in failed)


def resume_paths(record: RunRecord, directory: Path) -> dict[str, Path]:
    """Packet resumes that actually exist on disk, keyed by jd_id."""
    found: dict[str, Path] = {}
    for jd in record.jds:
        if not jd.packet:
            continue
        candidate = directory / jd.packet / "resume.md"
        if candidate.is_file():
            found[jd.jd_id] = candidate
    return found


def jd_label(jd: JDRecord) -> str:
    if jd.error:
        return "error"
    if jd.dropped_by_h1b:
        return "dropped (H-1B)"
    return jd.label or "-"
