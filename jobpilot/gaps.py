"""The gap diff: what a posting requires that the profile cannot evidence.

PRD §5.6, and deliberately plain Python. Deciding whether "Postgres" is already
covered by a `PostgreSQL` evidence entry is an alias lookup, not a judgement,
and running it through a model would make the question set vary between runs --
which is exactly the number `iter4` is measured on.

Three buckets:

    covered   the profile can already evidence it
    declined  the author has said they have not used it -- never ask again
    unknown   nobody has ever said; this is what becomes a gap question

The `declined` bucket is what makes the run-1 → run-2 metric mean anything. An
answer of "no" is as durable as an answer of "yes": both end the question
forever, and re-asking a declined tool is the failure this file exists to
prevent.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from jobpilot.profile.claims import claimable_tools, declined_tools
from jobpilot.profile.schema import Profile
from jobpilot.requirements import Requirement, RequirementSet

# The same restriction `scorers.score_coverage` applies, for the same reason: a
# `concept` or `credential` requirement ("Networking", "BS in Computer Science")
# can never be answered by a tool_evidence entry, so asking about it would be
# asking a question no answer can close.
COVERABLE_TYPES = {"language", "framework", "cloud_infra", "data", "ai_ml", "testing"}


@dataclass(frozen=True)
class Gaps:
    jd_id: str
    covered: list[str] = field(default_factory=list)
    declined: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)

    @property
    def has_questions(self) -> bool:
        return bool(self.unknown)


# Words that mark a requirement as a *category* rather than a nameable tool.
# The extractor types "Databases" as `data` and "Automated testing" as
# `testing`, which is correct as a requirement type and useless as a question:
# a gap question is only worth asking if the answer can become a
# `ToolEvidence` entry, and that needs a specific tool. Nobody can evidence
# "Hands-on generative AI experience" -- there is no tool to record, no
# container to attach it to, and the author would be right to find the question
# absurd.
_GENERIC = {
    "ai", "analysis", "apis", "architecture", "concepts", "data", "database",
    "databases", "design", "development", "engineering", "evaluation",
    "experience", "frameworks", "fundamentals", "integration", "knowledge",
    "languages", "methods", "ml", "pipelines", "practices", "principles",
    "systems", "techniques", "testing", "tools", "workflow", "workflows",
}
MAX_TOOL_WORDS = 2


def is_askable(name: str) -> bool:
    """Could a `ToolEvidence` entry plausibly be written for this?

    Conservative on purpose. A false negative costs one unasked question; a
    false positive puts an unanswerable question in front of the author, and
    the whole point of the pause is that it is worth interrupting them for.
    """
    words = name.strip().lower().split()
    if not words or len(words) > MAX_TOOL_WORDS:
        return False
    return not any(word in _GENERIC for word in words)


def _names(requirement: Requirement) -> set[str]:
    """Canonical name plus aliases, lowercased -- matching runs on both sides."""
    return {requirement.name.strip().lower()} | {
        alias.strip().lower() for alias in requirement.aliases
    }


def gap_diff(profile: Profile, requirements: RequirementSet | None, jd_id: str) -> Gaps:
    """Required, tool-typed items sorted into the three buckets."""
    if requirements is None:
        return Gaps(jd_id=jd_id)

    claimable = claimable_tools(profile)
    declined = declined_tools(profile)

    covered, refused, unknown = [], [], []
    for requirement in requirements.requirements:
        if not requirement.required or requirement.type not in COVERABLE_TYPES:
            continue
        names = _names(requirement)
        if names & claimable:
            covered.append(requirement.name)
        elif names & declined:
            refused.append(requirement.name)
        elif is_askable(requirement.name):
            unknown.append(requirement.name)
        # else: a category, not a tool. Not covered, but not askable either --
        # it stays out of every bucket rather than becoming a question no
        # answer could close.

    return Gaps(
        jd_id=jd_id,
        covered=sorted(set(covered)),
        declined=sorted(set(refused)),
        unknown=sorted(set(unknown)),
    )


def question_text(jd_company: str, gaps: Gaps) -> str:
    """One batched question per posting (PRD §5.6), not one per tool.

    Batching is a product decision, not a formatting one: the author is applying
    to fifteen postings, and fifteen prompts that each ask about one tool is a
    worse experience than fifteen prompts that each ask about all of them.
    """
    listed = "\n".join(f"  {i}. {tool}" for i, tool in enumerate(gaps.unknown, 1))
    return (
        f"{jd_company} asks for {len(gaps.unknown)} thing(s) your profile cannot "
        f"currently evidence:\n\n{listed}\n\n"
        "Have you actually used any of them? Answer with the numbers of the ones "
        "you have used, and where you used them — anything you do not name is "
        "recorded as 'not used' and never asked about again."
    )
