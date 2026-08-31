"""`python -m jobpilot` -- the command line.

    ingest   fetch and cache job postings from links.txt
    verify   check any markdown document against the profile
    run      execute the pipeline for one stage

Scoring lives in its own entry point, `python -m jobpilot.eval`, because it
reads a completed run rather than producing one. See REPRODUCE.md for the exact
commands that regenerate every published number.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from jobpilot.answers import build_provider
from jobpilot.eval.presets import UnbuiltCapabilityError
from jobpilot.ingest import (
    MIN_TEXT_CHARS,
    CacheMissError,
    FetchError,
    LinkListIngester,
    UnsupportedBoardError,
)
from jobpilot.ingest.cache import CACHE_DIR
from jobpilot.profile import FROZEN_PROFILE_PATH

DEFAULT_LINKS = Path("fixture/links.txt")


def _ingest(args: argparse.Namespace) -> int:
    ingester = LinkListIngester(
        links_path=args.links,
        cache_dir=args.cache_dir,
        offline=args.offline,
        refresh=args.refresh,
    )
    result = ingester.fetch()

    print(f"{'jd':<7} {'board':<11} {'company':<16} {'chars':<7} title")
    print("-" * 88)
    for jd in result.jds:
        print(
            f"{jd.jd_id:<7} {jd.board:<11} {jd.company[:15]:<16} "
            f"{len(jd.text):<7} {jd.title[:38]}"
        )

    print(
        f"\n{len(result.jds)} JDs -- {result.hits} from cache, "
        f"{result.fetched} fetched"
    )
    if result.thin:
        print(
            f"WARNING: under {MIN_TEXT_CHARS} chars, extraction likely failed: "
            f"{', '.join(result.thin)}"
        )
        return 1
    return 0


def _verify(args: argparse.Namespace) -> int:
    from jobpilot.profile import load_profile
    from jobpilot.verify import verify_file

    profile_path = args.profile
    report = verify_file(
        args.document,
        load_profile(profile_path),
        use_judge=not args.no_judge,
        profile_name=str(profile_path),
    )

    text = {u.unit_id: u.text for u in report.units}
    print(f"{'unit':<6} {'rules':<12} {'judge':<12} claim")
    print("-" * 92)
    judged = {v.unit_id: v.status for v in report.judge}
    for verdict in report.rules:
        print(
            f"{verdict.unit_id:<6} {verdict.status:<12} "
            f"{judged.get(verdict.unit_id, '-'):<12} "
            f"{text[verdict.unit_id][:56]}"
        )
        for reason in verdict.reasons:
            if verdict.status != "supported":
                print(f"{'':<6} -> {reason}")

    print(
        f"\nfabricated {report.fabricated_claims}  "
        f"softened {report.softened_claims}  "
        f"supported {report.supported_claims}  "
        f"(of {len(report.rules)} claims)"
    )
    for violation in report.writing_preference_violations:
        print(f"writing_preferences: {violation}")

    if report.agreement:
        a = report.agreement
        print(f"\nrules vs judge: {a.agreed}/{a.compared} agree ({a.rate:.0%})")
        for line in a.disagreements:
            print(f"  {line}")

    if args.out:
        args.out.write_text(report.model_dump_json(indent=2) + "\n")
        print(f"\nwrote {args.out}")
    return 0


def _run(args: argparse.Namespace) -> int:
    from jobpilot.run import execute

    execute(
        args.stage,
        links=args.links,
        offline=args.offline,
        out=args.out,
        answers=build_provider(args.answers, no_questions=args.no_questions),
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jobpilot", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="fetch job postings into the cache")
    ingest.add_argument("--links", type=Path, default=DEFAULT_LINKS)
    ingest.add_argument("--cache-dir", type=Path, default=CACHE_DIR)
    ingest.add_argument(
        "--offline",
        action="store_true",
        help="never fetch; fail loudly on a cache miss",
    )
    ingest.add_argument(
        "--refresh", action="store_true", help="re-fetch every link"
    )
    ingest.set_defaults(func=_ingest)

    verify = sub.add_parser(
        "verify", help="check a generated document against the profile"
    )
    verify.add_argument("document", type=Path)
    verify.add_argument(
        "--profile",
        type=Path,
        default=FROZEN_PROFILE_PATH,
        help="defaults to the frozen fixture profile, which is what scores runs",
    )
    verify.add_argument(
        "--no-judge",
        action="store_true",
        help="skip the LLM cross-check; run the deterministic rules only",
    )
    verify.add_argument("--out", type=Path, help="write the full JSON report here")
    verify.set_defaults(func=_verify)

    run = sub.add_parser("run", help="execute the pipeline for one stage")
    run.add_argument("--stage", default="final")
    run.add_argument("--links", type=Path, default=DEFAULT_LINKS)
    run.add_argument("--offline", action="store_true", default=True)
    run.add_argument("--online", dest="offline", action="store_false")
    run.add_argument("--out", type=Path)
    run.add_argument(
        "--answers",
        type=Path,
        help="answer gap questions from this JSON file instead of the terminal",
    )
    run.add_argument(
        "--no-questions",
        action="store_true",
        help="decline every gap question (non-interactive; what eval uses)",
    )
    run.set_defaults(func=_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    # ADK only auto-loads .env under `adk run`, so anything with an LLM call
    # behind it has to do this itself.
    load_dotenv()
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except (
        UnsupportedBoardError,
        CacheMissError,
        FetchError,
        UnbuiltCapabilityError,
        NotImplementedError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
