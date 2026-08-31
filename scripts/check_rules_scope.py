#!/usr/bin/env python
"""Negative tests for the title rule, narrowed at `iter3b`.

`iter3a` left a rules-vs-judge disagreement: the rules path called "Backend
engineer" in a Summary line an unsupported *title*, the judge called it
supported. The judge was right -- that sentence describes the candidate, it does
not claim a job title held at an employer. The fix scopes title and company
checks to experience and project sections.

Narrowing a rule right after it produced an inconvenient number is exactly how a
scorer gets quietly tuned to flatter its own results, so this script exists to
pin what the rule must *still* catch. Run it after any change to
`jobpilot/verify/rules.py`:

    python scripts/check_rules_scope.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobpilot.profile.loader import FROZEN_PROFILE_PATH, load_profile
from jobpilot.verify.rules import adjudicate
from jobpilot.verify.schema import ClaimElement, ClaimUnit

CASES = [
    # (label, text, section, kind, value, container_id, expected status)
    (
        "inflated title in an experience heading",
        "Amazon.com Services LLC — Senior Staff Engineer",
        "experience", "title", "Senior Staff Engineer", "exp_2", "unsupported",
    ),
    (
        "real title in an experience heading",
        "Amazon.com Services LLC — Software Development Engineer",
        "experience", "title", "Software Development Engineer", "exp_2", "supported",
    ),
    (
        "invented employer in an experience heading",
        "Stripe — Software Development Engineer",
        "experience", "company", "Stripe", None, "unsupported",
    ),
    (
        "self-description in a summary is not a title claim",
        "Backend engineer building public-facing APIs in Python and Java",
        "summary", "title", "Backend engineer", None, "supported",
    ),
]


def main() -> int:
    profile = load_profile(FROZEN_PROFILE_PATH)
    failures = 0
    for label, text, section, kind, value, container, expected in CASES:
        unit = ClaimUnit(
            unit_id="u01",
            text=text,
            section=section,
            container_id=container,
            elements=[ClaimElement(kind=kind, value=value)],
        )
        got = adjudicate([unit], profile)[0]
        ok = got.status == expected
        failures += not ok
        print(
            f"  {'PASS' if ok else 'FAIL'}  {label}\n"
            f"        expected {expected}, got {got.status}"
            + (f" -- {got.reasons}" if got.reasons else "")
        )
    print(f"\n{len(CASES) - failures}/{len(CASES)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
