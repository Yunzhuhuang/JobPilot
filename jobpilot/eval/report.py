"""Writes `eval/results/<stage>/` and the cross-stage `compare.md`.

`summary.json` is the file every README and CHANGELOG number must trace back
to. `summary.md` says the same thing in prose, and `per_jd.md` shows every
case, failures included -- an average hides exactly the JD worth looking at.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from jobpilot.config import REPO_ROOT
from jobpilot.eval.presets import Stage, available_stages
from jobpilot.eval.run_record import RunRecord
from jobpilot.eval.scorers import LABEL_ORDER, Metric, Scores, jd_label
from jobpilot.verify import VerificationReport

RESULTS_DIR = REPO_ROOT / "eval" / "results"

# Order matters: this is the row order of every report and of compare.md.
METRIC_LABELS: list[tuple[str, str]] = [
    ("fabricated_claims_per_resume", "Fabricated claims / resume (primary)"),
    ("baseline_same_jds", "↳ baseline on the same postings"),
    ("softened_claims_per_resume", "Softened claims / resume"),
    ("rules_vs_judge_agreement", "Rules vs. judge agreement"),
    ("triage_agreement", "Triage agreement with author labels"),
    ("jd_keyword_coverage", "JD keyword coverage"),
    ("revision_rounds_per_doc", "Verify \u2192 revise rounds / document"),
    ("non_sponsors_dropped", "Non-sponsors dropped"),
    ("h1b_resolution", "H-1B employer identified correctly"),
    ("gap_questions_run1_to_run2", "Gap questions asked"),
    ("cost_per_jd_usd", "Cost / JD"),
    ("wall_clock_per_jd_s", "Wall-clock / JD"),
]


class Summary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: str
    description: str
    flags: dict[str, bool]
    run_dir: str
    run_date: str
    model: str
    judge_enabled: bool
    scores: Scores


def results_dir(stage: str) -> Path:
    return RESULTS_DIR / stage


def write_reports(
    summary: Summary,
    record: RunRecord,
    reports: dict[str, VerificationReport],
) -> Path:
    directory = results_dir(summary.stage)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "summary.json").write_text(summary.model_dump_json(indent=2) + "\n")
    (directory / "summary.md").write_text(_summary_md(summary))
    (directory / "per_jd.md").write_text(_per_jd_md(summary, record, reports))
    return directory


def _fmt(metric: Metric) -> str:
    if metric.value is None:
        return "n/a"
    value = f"{metric.value:g}"
    return f"{value} {metric.unit}".strip()


def _summary_md(summary: Summary) -> str:
    s = summary.scores
    lines = [
        f"# {summary.stage} — {summary.description}",
        "",
        f"Run `{summary.run_dir}` ({summary.run_date}) · model `{summary.model}` · "
        f"judge {'on' if summary.judge_enabled else 'off'}",
        "",
        f"{s.jds_total} JDs, {s.resumes_scored} resumes scored, "
        f"{s.jds_failed} failed.",
        "",
        "| Metric | Value | Detail |",
        "| ------ | ----- | ------ |",
    ]
    for field, label in METRIC_LABELS:
        metric: Metric = getattr(s, field)
        note = metric.unavailable or metric.detail or ""
        if metric.unavailable:
            note = f"_not available: {metric.unavailable}_"
        lines.append(f"| {label} | {_fmt(metric)} | {note} |")

    if any(any(row.values()) for row in s.confusion.values()):
        lines += ["", "## Triage confusion", "",
                  "| author \\ agent | " + " | ".join(LABEL_ORDER) + " |",
                  "| --- " * (len(LABEL_ORDER) + 1) + "|"]
        for truth in LABEL_ORDER:
            row = s.confusion.get(truth, {})
            cells = " | ".join(str(row.get(p, 0)) for p in LABEL_ORDER)
            lines.append(f"| **{truth}** | {cells} |")

    lines += ["", "## Flags", "",
              "```yaml"] + [f"{k}: {str(v).lower()}" for k, v in summary.flags.items()]
    lines += ["```", ""]
    return "\n".join(lines)


def _per_jd_md(
    summary: Summary,
    record: RunRecord,
    reports: dict[str, VerificationReport],
) -> str:
    lines = [
        f"# {summary.stage} — per JD",
        "",
        "Every case, failures included.",
        "",
        "| JD | outcome | fabricated | softened | supported | tokens | s | note |",
        "| -- | ------- | ---------- | -------- | --------- | ------ | - | ---- |",
    ]
    for jd in record.jds:
        report = reports.get(jd.jd_id)
        fab = str(report.fabricated_claims) if report else "-"
        soft = str(report.softened_claims) if report else "-"
        sup = str(report.supported_claims) if report else "-"
        note = jd.error or ("no resume produced" if not report else "")
        lines.append(
            f"| {jd.jd_id} | {jd_label(jd)} | {fab} | {soft} | {sup} | "
            f"{jd.input_tokens + jd.output_tokens} | {jd.wall_clock_s:g} | {note} |"
        )

    flagged = [
        (jd_id, verdict, report)
        for jd_id, report in sorted(reports.items())
        for verdict in report.rules
        if verdict.status == "unsupported"
    ]
    if flagged:
        lines += ["", "## Rejected claims", ""]
        for jd_id, verdict, report in flagged:
            text = next(
                (u.text for u in report.units if u.unit_id == verdict.unit_id), ""
            )
            lines.append(f"- **{jd_id}** {verdict.unit_id}: {text}")
            for reason in verdict.reasons:
                lines.append(f"  - {reason}")
    lines.append("")
    return "\n".join(lines)


def write_compare() -> Path:
    """Regenerates the stage-by-metric table the changelog is built from."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stages = available_stages()
    summaries: dict[str, Summary] = {}
    for stage in stages:
        path = results_dir(stage) / "summary.json"
        if path.is_file():
            summaries[stage] = Summary.model_validate(json.loads(path.read_text()))

    header = "| Metric | " + " | ".join(stages) + " |"
    divider = "| --- " * (len(stages) + 1) + "|"
    lines = [
        "# Stage comparison",
        "",
        "Generated by `python -m jobpilot.eval --all-stages`. Every number here "
        "comes from a `summary.json`; none is typed by hand.",
        "",
        header,
        divider,
    ]
    for field, label in METRIC_LABELS:
        cells = []
        for stage in stages:
            summary = summaries.get(stage)
            cells.append(
                "—" if summary is None else _fmt(getattr(summary.scores, field))
            )
        lines.append(f"| {label} | " + " | ".join(cells) + " |")

    not_run = [s for s in stages if s not in summaries]
    if not_run:
        lines += [
            "",
            f"Not yet run: {', '.join(f'`{s}`' for s in not_run)}. "
            "A stage with no result is shown as — rather than omitted, so the "
            "table always states what has not been measured.",
        ]
    lines.append("")
    path = RESULTS_DIR / "compare.md"
    path.write_text("\n".join(lines))
    return path


def stage_summary(stage: Stage, record: RunRecord, run_dir: Path,
                  judge: bool, scores: Scores) -> Summary:
    return Summary(
        stage=stage.name,
        description=stage.description,
        flags=stage.flags.model_dump(),
        run_dir=str(run_dir),
        run_date=record.date,
        model=record.model,
        judge_enabled=judge,
        scores=scores,
    )
