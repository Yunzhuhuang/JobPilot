"""`python -m jobpilot.eval` -- score a stage, or regenerate compare.md."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from jobpilot.eval import NoRunError, score_stage, write_compare
from jobpilot.eval.presets import UnbuiltCapabilityError, available_stages
from jobpilot.eval.report import METRIC_LABELS, _fmt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="jobpilot.eval", description=__doc__
    )
    parser.add_argument("--stage", help=f"one of: {', '.join(available_stages())}")
    parser.add_argument(
        "--all-stages",
        action="store_true",
        help="regenerate eval/results/compare.md from the stages already scored",
    )
    parser.add_argument("--run", type=Path, help="score this run directory")
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="skip the LLM cross-check; the primary metric is unaffected",
    )
    parser.add_argument(
        "--refresh-verification",
        action="store_true",
        help="re-verify even if a cached report matches",
    )
    args = parser.parse_args(argv)

    if not args.stage and not args.all_stages:
        parser.error("give --stage <name> or --all-stages")

    load_dotenv()

    if args.stage:
        try:
            summary, directory = score_stage(
                args.stage,
                run_dir=args.run,
                use_judge=not args.no_judge,
                refresh_verification=args.refresh_verification,
            )
        except (NoRunError, UnbuiltCapabilityError, FileNotFoundError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

        print(f"{summary.stage} — {summary.description}")
        print(
            f"{summary.scores.jds_total} JDs · "
            f"{summary.scores.resumes_scored} resumes scored · "
            f"{summary.scores.jds_failed} failed\n"
        )
        for field, label in METRIC_LABELS:
            metric = getattr(summary.scores, field)
            suffix = f"  ({metric.unavailable})" if metric.unavailable else ""
            print(f"  {label:<40} {_fmt(metric):>14}{suffix}")
        print(f"\nwrote {directory}/")

    path = write_compare()
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
