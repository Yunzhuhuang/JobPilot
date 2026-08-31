"""The evaluation harness: score a run, write the reports, compare the stages.

Always offline, and always against the frozen `fixture/profile.json` -- an
iteration that mutates the working profile is still graded from a fixed start.

`eval` scores a run; it does not perform one. That separation is what lets the
same scorers grade the baseline and the pipeline without either importing the
other: both write `output/<stage>/<date>/run.json`, and this reads it.
"""

from __future__ import annotations

from pathlib import Path

from jobpilot.config import Config, load_config
from jobpilot.eval.presets import Stage, load_preset
from jobpilot.eval.report import Summary, stage_summary, write_compare, write_reports
from jobpilot.eval.run_record import (
    latest_run,
    previous_run,
    read_run_record,
)
from jobpilot.eval.scorers import (
    Metric,
    Scores,
    failure_summary,
    load_labels,
    resume_paths,
    score_baseline_on,
    score_cost,
    score_coverage,
    score_fabrication,
    score_gap_questions,
    score_h1b_resolution,
    score_judge_agreement,
    score_non_sponsors,
    score_revisions,
    score_triage,
    scoring_profile,
    verification_for,
)
from jobpilot.verify import VerificationReport

__all__ = ["Summary", "score_stage", "write_compare"]


class NoRunError(RuntimeError):
    """A stage has been asked for that nobody has run yet."""


def score_stage(
    stage_name: str,
    *,
    run_dir: Path | None = None,
    use_judge: bool = True,
    refresh_verification: bool = False,
    config: Config | None = None,
) -> tuple[Summary, Path]:
    config = config or load_config()
    stage = load_preset(stage_name)

    directory = run_dir or latest_run(stage_name)
    if directory is None:
        raise NoRunError(
            f"no run found under output/{stage_name}/. Produce one first "
            f"(`python -m jobpilot.baseline` for baseline, "
            f"`python -m jobpilot run --stage {stage_name}` otherwise), "
            f"or pass --run <path>."
        )

    record = read_run_record(directory)
    # Frozen, plus gap-acquired evidence for a gap_memory stage. See
    # scorers.scoring_profile for why that exception is bounded and safe.
    profile = scoring_profile(record)

    from jobpilot.eval.report import results_dir

    cache = results_dir(stage_name) / "verification"
    reports: dict[str, VerificationReport] = {}
    resumes: dict[str, str] = {}
    for jd_id, path in resume_paths(record, directory).items():
        reports[jd_id] = verification_for(
            path, profile, config, cache,
            use_judge=use_judge, refresh=refresh_verification,
        )
        resumes[jd_id] = path.read_text()

    fabricated, softened = score_fabrication(reports)
    triage, confusion = score_triage(record, load_labels())
    cost, wall = score_cost(record)
    failed, _ = failure_summary(record)

    scores = Scores(
        fabricated_claims_per_resume=fabricated,
        baseline_same_jds=(
            score_baseline_on(set(reports), profile, config, use_judge=use_judge)
            if reports and stage_name != "baseline"
            else Metric(
                unit="claims/resume",
                unavailable="this stage generated no resumes to compare",
            )
        ),
        softened_claims_per_resume=softened,
        rules_vs_judge_agreement=score_judge_agreement(reports),
        triage_agreement=triage,
        jd_keyword_coverage=score_coverage(resumes),
        revision_rounds_per_doc=score_revisions(record),
        non_sponsors_dropped=score_non_sponsors(record),
        h1b_resolution=score_h1b_resolution(record),
        gap_questions_run1_to_run2=score_gap_questions(
            record, previous_run(stage_name)
        ),
        cost_per_jd_usd=cost,
        wall_clock_per_jd_s=wall,
        resumes_scored=len(reports),
        jds_total=len(record.jds),
        jds_failed=failed,
        confusion=confusion,
    )

    summary = stage_summary(stage, record, directory, use_judge, scores)
    return summary, write_reports(summary, record, reports)


def describe(stage_name: str) -> Stage:
    return load_preset(stage_name)
