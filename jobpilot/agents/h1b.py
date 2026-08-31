"""The sponsorship node: a company name in, a reasoned likelihood out.

`jobpilot.h1b.lookup` explains why this is an agent and not a `dict.get`.
Short version: resolving "Abridge" to ABRIDGE AI INC rather than ABRIDGE INFO
SYSTEMS INC, or "SpaceX" to SPACE EXPLORATION TECHNOLOGIES CORP, is a
judgement about which legal entity is which company. String similarity scores
both Abridge entities at 100 and scores the SpaceX one at nothing.

The division of labour is the same one the rest of the project uses: the facts
stay deterministic (the USCIS counts are read, never guessed, and the agent can
only see rows that exist) and the judgement is the model's. The agent cannot
invent an employer -- `matched_entity` is checked against the index by the
caller, and an unknown name is rejected rather than trusted.
"""

from __future__ import annotations

from typing import Literal

from google.adk import Agent
from google.adk.models import BaseLlm
from google.adk.tools import FunctionTool
from pydantic import BaseModel, ConfigDict, Field

from jobpilot.agents import load_instruction
from jobpilot.h1b.lookup import H1BIndex
from jobpilot.ingest import JD

INSTRUCTION = "h1b"

Likelihood = Literal["likely", "unlikely", "unknown"]


class SponsorshipAssessment(BaseModel):
    """What the agent concluded about one employer."""

    model_config = ConfigDict(extra="forbid")

    likelihood: Likelihood
    matched_entity: str | None = None
    approvals: int = 0
    confidence: Literal["high", "medium", "low"] = "low"
    rationale: str = ""

    # Filled by the node, not the model.
    searches: list[dict] = Field(default_factory=list)
    """Each entry is {tool, query, response} -- the call and what it returned."""
    entity_verified: bool = False
    """True when `matched_entity` was found verbatim in the USCIS index.

    A model naming an employer that does not exist is the one failure mode that
    would let fabricated data into a project whose primary metric is
    fabrication, so the claim is checked rather than accepted."""


def parse_assessment(reply: str) -> SponsorshipAssessment:
    """Tolerant of a model volunteering keys the contract does not define.

    Same failure the tailor hit: `extra="forbid"` is right for a persisted
    artifact, but discarding a whole valid assessment because the model added a
    `confidence_note` loses real work. It cost `jd_06` its H-1B verdict on
    2026-08-31. The required fields stay strict; the extras are dropped.
    """
    import json as _json

    from jobpilot.verify.llm import strip_fence

    text = strip_fence(reply)
    try:
        payload = _json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise
        payload = _json.loads(text[start : end + 1])
    known = set(SponsorshipAssessment.model_fields)
    return SponsorshipAssessment.model_validate(
        {k: v for k, v in payload.items() if k in known}
    )


def build_agent(
    index: H1BIndex,
    model: BaseLlm,
    meter: object | None = None,
    *,
    name: str = "h1b",
    searches: list[dict] | None = None,
) -> Agent:
    """An agent with one tool: search the same index it is being asked about.

    `name` must be unique per concurrent invocation. ADK registers a
    dynamically-run agent by name, so several `ctx.run_node` calls on agents
    sharing a name are treated as one node: their tool-calling conversations
    interleave, and a JD can be handed another JD's answer. A single-turn
    agent like triage hides this -- there is no second turn to interleave --
    but a tool-using one surfaces it immediately, and silently. Observed
    2026-08-30: SpaceX resolved to COHERE US, INC. with Cohere's rationale
    attached, having run four other postings' searches on the way.
    """
    searches = [] if searches is None else searches

    def search_employers(query: str) -> str:
        """Search USCIS H-1B employers by name.

        Args:
            query: a company or legal entity name, e.g. "space exploration".

        Returns:
            Up to 8 matching employers with their filing states and approval
            counts, or a line saying nothing matched.
        """
        found = index.search(query)
        response = (
            "\n".join(c.employer.describe() for c in found)
            if found
            else f"No employer matching {query!r}."
        )
        # Both halves. A trajectory that shows the query but not what came back
        # cannot be followed -- PRD 9.4 and the brief both ask for the tool's
        # response, because that is the feedback that shaped the next step.
        searches.append({"tool": "search_employers", "query": query,
                         "response": response})
        return response

    return Agent(
        name=name,
        model=model,
        instruction=load_instruction(INSTRUCTION).replace(
            "{fiscal_year}", str(index.fiscal_year)
        ),
        tools=[FunctionTool(search_employers)],
        after_model_callback=meter,
    )


def sponsorship_prompt(jd: JD, index: H1BIndex) -> str:
    """The company, where it is hiring, and a string-similarity shortlist."""
    candidates = index.search(jd.company)
    if candidates:
        shortlist = "\n".join(
            f"- {c.employer.describe()}  (name similarity {c.score:.0f})"
            for c in candidates
        )
    else:
        shortlist = "(no employer name resembles this company)"
    return (
        f"Company: {jd.company}\n"
        f"Posting location: {jd.location}\n"
        f"Role: {jd.title}\n\n"
        f"Shortlist by name similarity:\n{shortlist}\n\n"
        "Decide which of these, if any, is this company, searching again if "
        "none of them fit."
    )
