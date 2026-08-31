#!/usr/bin/env python
"""Label the fixture JDs. Your ground truth, unaided.

Triage agreement is scored against `fixture/labels.json`, so these labels must
be yours. This script deliberately offers no suggestion: triage runs on the same
model that would make one, and agreement between a model and its own draft
measures nothing.

    python scripts/label_fixture.py              # resumes at the first unlabelled JD
    python scripts/label_fixture.py --relabel jd_07

Writes after every keystroke, so quitting loses nothing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobpilot.config import REPO_ROOT
from jobpilot.ingest import JD, read_entry
from jobpilot.ingest.cache import CACHE_DIR
from jobpilot.profile import load_profile
from jobpilot.requirements import RequirementSet, load_requirements

LABELS_PATH = REPO_ROOT / "fixture" / "labels.json"

CHOICES = {"m": "most_matched", "l": "less_matched", "s": "skip"}
PREVIEW_CHARS = 700

BOLD, DIM, OFF = "\033[1m", "\033[2m", "\033[0m"
RULE = "-" * 78


def load_labels(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text())


def save_labels(labels: dict[str, str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = {k: labels[k] for k in sorted(labels)}
    path.write_text(json.dumps(ordered, indent=2) + "\n")


def show_rubric() -> None:
    profile = load_profile()
    constraints = profile.constraints
    print(f"\n{BOLD}Rubric{OFF} (PRD 5.5)")
    print("  most_matched   meets the required stack and level, domain overlaps")
    print("                 your target roles, worth 30+ min of customization")
    print("  less_matched   worth a generic application only")
    print("  skip           wrong level or domain, or a hard constraint violated")
    print(f"\n{BOLD}Your constraints{OFF} (from profile.json)")
    print(f"  target roles        {', '.join(constraints.target_roles)}")
    print(f"  excluded locations  {', '.join(constraints.excluded_locations)}")
    print(f"  needs sponsorship   {constraints.needs_sponsorship}")
    print(f"  earliest start      {constraints.earliest_start}")


def show_jd(jd: JD, rs: RequirementSet | None, position: str, full: bool) -> None:
    print(f"\n{RULE}")
    print(f"{BOLD}{jd.jd_id}{OFF}  {position}   {DIM}{jd.board}{OFF}")
    print(f"{BOLD}{jd.title}{OFF}")
    print(f"{jd.company}  --  {jd.location}")
    print(RULE)

    if rs is not None:
        required = [r.name for r in rs.requirements if r.required]
        nice = [r.name for r in rs.requirements if not r.required]
        print(f"{BOLD}Required{OFF} ({len(required)})")
        print(_wrap(required))
        if nice:
            print(f"{DIM}Nice to have ({len(nice)}){OFF}")
            print(f"{DIM}{_wrap(nice)}{OFF}")
    else:
        print(f"{DIM}(no extracted requirements for this JD){OFF}")

    body = jd.text if full else jd.text[:PREVIEW_CHARS]
    print(f"\n{DIM}{body}{OFF}")
    if not full and len(jd.text) > PREVIEW_CHARS:
        rest = len(jd.text) - PREVIEW_CHARS
        print(f"{DIM}... {rest} more characters -- press v{OFF}")
    if jd.application_questions:
        print(f"\n{BOLD}Application questions{OFF}")
        for q in jd.application_questions:
            print(f"  - {q}")


def _wrap(names: list[str], width: int = 74) -> str:
    """Requirement names, dot-separated, wrapped to the terminal."""
    lines: list[list[str]] = [[]]
    length = 0
    for name in names:
        if length and length + len(name) + 3 > width:
            lines.append([])
            length = 0
        lines[-1].append(name)
        length += len(name) + 3
    return "\n".join(f"  {' · '.join(row)}" for row in lines if row) or "  (none)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=CACHE_DIR)
    parser.add_argument("--labels", type=Path, default=LABELS_PATH)
    parser.add_argument("--relabel", help="redo a single jd_id, e.g. jd_07")
    args = parser.parse_args(argv)

    jds = [read_entry(p) for p in sorted(args.cache_dir.glob("jd_*.md"))]
    if not jds:
        print(f"error: no cache entries in {args.cache_dir}", file=sys.stderr)
        return 2
    requirements = load_requirements()
    labels = load_labels(args.labels)

    if args.relabel:
        queue = [jd for jd in jds if jd.jd_id == args.relabel]
        if not queue:
            print(f"error: no JD named {args.relabel}", file=sys.stderr)
            return 2
    else:
        queue = [jd for jd in jds if jd.jd_id not in labels]

    if not queue:
        print(f"All {len(jds)} JDs already labelled. --relabel <jd_id> to change one.")
        _summarize(labels, len(jds))
        return 0

    show_rubric()
    index = 0
    full = False
    while index < len(queue):
        jd = queue[index]
        position = f"{len(labels) + 1} of {len(jds)}" if not args.relabel else "relabel"
        show_jd(jd, requirements.get(jd.jd_id), position, full)

        answer = input(
            f"\n{BOLD}[m]{OFF}ost  {BOLD}[l]{OFF}ess  {BOLD}[s]{OFF}kip  "
            f"{BOLD}[v]{OFF}iew full  {BOLD}[b]{OFF}ack  {BOLD}[q]{OFF}uit > "
        ).strip().lower()

        if answer == "q":
            break
        if answer == "v":
            full = True
            continue
        if answer == "b":
            full = False
            if index == 0:
                print("already at the first unlabelled JD")
                continue
            index -= 1
            labels.pop(queue[index].jd_id, None)
            save_labels(labels, args.labels)
            continue
        if answer not in CHOICES:
            print("please answer m, l, s, v, b, or q")
            continue

        labels[jd.jd_id] = CHOICES[answer]
        save_labels(labels, args.labels)
        full = False
        index += 1

    _summarize(labels, len(jds))
    if labels and len(labels) < len(jds):
        print(f"\nSaved. Re-run to continue at {len(labels) + 1} of {len(jds)}.")
    return 0


def _summarize(labels: dict[str, str], total: int) -> None:
    print(f"\n{RULE}")
    print(f"{len(labels)} of {total} labelled -> fixture/labels.json")
    for value in ("most_matched", "less_matched", "skip"):
        ids = sorted(k for k, v in labels.items() if v == value)
        print(f"  {value:<14} {len(ids):>2}  {' '.join(ids)}")


if __name__ == "__main__":
    raise SystemExit(main())
