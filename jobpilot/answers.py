"""Where a gap question's answer comes from. One abstraction, three sources.

`CLAUDE.md` requires this to be app-level: the pause node yields a question and
never learns who answered it. That is what lets the same graph run interactively
for the author, reproducibly for a judge, and unattended for `eval` -- and
non-interactive mode is on the PRD's never-cut list precisely because a harness
that can block on a prompt is a harness nobody can re-run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field


class UsedTool(BaseModel):
    """One tool the author confirms, and -- critically -- where they used it."""

    model_config = ConfigDict(extra="forbid")

    tool: str = Field(min_length=1)
    where: str = Field(min_length=1)
    """A container id (`exp_2`, `proj_2`) or `self_study`.

    Placement is the whole point. A tool confirmed without a location is
    `self_study`: claimable on a skills line, never inside a role bullet, which
    `classify_claim` enforces as `unplaced`."""
    evidence: str = Field(min_length=1)


class GapAnswer(BaseModel):
    """The reply schema. Anything not named here is a 'no'."""

    model_config = ConfigDict(extra="forbid")

    used: list[UsedTool] = Field(default_factory=list)


class AnswerProvider(Protocol):
    def answer(self, message: str, tools: list[str], jd_id: str) -> dict[str, Any]: ...


class AlwaysNo:
    """The default, and what `--no-questions` selects.

    A 'no' is not a non-answer: it writes `not_experienced`, which is durable and
    stops the tool ever being asked about again. That is why an unattended run
    still moves the run-1 -> run-2 metric.
    """

    def answer(self, message: str, tools: list[str], jd_id: str) -> dict[str, Any]:
        return {"used": []}


class FileAnswers:
    """Answers from `fixture/answers.json` -- reproducible, and the author's own.

    Keyed by tool rather than by posting, because "have you used Ubuntu?" has one
    true answer no matter which JD raises it.
    """

    def __init__(self, path: Path) -> None:
        payload = json.loads(path.read_text())
        self._used: dict[str, dict[str, str]] = {
            k.strip().lower(): v for k, v in payload.get("used", {}).items()
        }
        self.path = path

    def answer(self, message: str, tools: list[str], jd_id: str) -> dict[str, Any]:
        used = [
            {
                "tool": tool,
                "where": entry["where"],
                "evidence": entry["evidence"],
            }
            for tool in tools
            if (entry := self._used.get(tool.strip().lower())) is not None
        ]
        return {"used": used}


class StdinAnswers:
    """The live path -- the author at a terminal. What the video records.

    Deliberately forgiving: the author is answering at speed, and a strict parser
    that rejects "1, 3 at Amazon" would turn a 20-second interruption into a
    fight. Anything not clearly confirmed stays a 'no', which is the safe default
    in a system whose whole purpose is not overstating.
    """

    def answer(self, message: str, tools: list[str], jd_id: str) -> dict[str, Any]:
        print(f"\n{'=' * 72}\n{message}\n")
        raw = input("used? (numbers, blank for none) > ").strip()
        picked: list[str] = []
        for token in raw.replace(",", " ").split():
            if token.isdigit() and 1 <= int(token) <= len(tools):
                picked.append(tools[int(token) - 1])
        used = []
        for tool in picked:
            where = input(f"  where did you use {tool}? "
                          "(exp_1/exp_2/proj_1/proj_2, or blank for self-study) > ")
            where = where.strip() or "self_study"
            used.append({
                "tool": tool,
                "where": where,
                "evidence": (
                    f"Author confirmed use in answer to a gap question "
                    f"({jd_id}); no further detail supplied."
                ),
            })
        if not used:
            print("  recorded: none used (all marked not-experienced)")
        return {"used": used}


def build_provider(
    answers: Path | None = None, *, no_questions: bool = False
) -> AnswerProvider:
    """Pick the source. The pause node never sees which one it got."""
    if no_questions:
        return AlwaysNo()
    if answers is not None:
        return FileAnswers(answers)
    return StdinAnswers()
