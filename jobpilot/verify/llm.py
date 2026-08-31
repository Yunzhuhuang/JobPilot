"""The two LLM passes: decomposition, and the PRD 5.8 judge.

Both read the model turn directly rather than `event.output` -- ADK only
populates that for an agent running as a workflow node, so a standalone agent's
result has to be parsed here.
"""

from __future__ import annotations

import asyncio
import json

from google.adk import Agent, Runner
from google.adk.models import BaseLlm
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types
from pydantic import BaseModel

from jobpilot.agents import load_instruction
from jobpilot.config import Config, build_model
from jobpilot.profile.schema import Profile
from jobpilot.verify.schema import ClaimElement, ClaimUnit, UnitVerdict

APP_NAME = "jobpilot_verify"
USER_ID = "verifier"


class _UnitElements(BaseModel):
    unit_id: str
    elements: list[ClaimElement] = []


class _Extraction(BaseModel):
    units: list[_UnitElements]


class _Verdicts(BaseModel):
    verdicts: list[UnitVerdict]


def analyse(
    units: list[ClaimUnit],
    profile: Profile,
    config: Config,
    *,
    use_judge: bool = True,
) -> tuple[list[ClaimUnit], list[UnitVerdict]]:
    """Both LLM passes in one event loop.

    Each `asyncio.run` builds and abandons an Anthropic client whose transport
    is then closed against a dead loop at GC, which surfaces as a spurious
    `RuntimeError: Event loop is closed` on stderr. One loop per document, and
    one model instance shared by both passes, avoids it.
    """
    return asyncio.run(_analyse(units, profile, config, use_judge))


async def _analyse(
    units: list[ClaimUnit], profile: Profile, config: Config, use_judge: bool
) -> tuple[list[ClaimUnit], list[UnitVerdict]]:
    model = build_model(config)
    labelled = await _extract(units, model)
    verdicts = await _judge(labelled, profile, model) if use_judge else []
    return labelled, verdicts


def extract_elements(units: list[ClaimUnit], config: Config) -> list[ClaimUnit]:
    """Labels what each unit asserts, leaving the unit boundaries alone.

    Segmentation is done in code (see `segment.py`) precisely so this call
    cannot move them. Deliberately runs without the profile in context: an
    extractor that knows the answer starts shaping its extraction toward it.
    """
    if not units:
        return []

    return asyncio.run(_extract(units, build_model(config)))


async def _extract(units: list[ClaimUnit], model: BaseLlm) -> list[ClaimUnit]:
    if not units:
        return []
    agent = Agent(
        name="extract_elements",
        model=model,
        instruction=load_instruction("extract_elements"),
    )
    payload = json.dumps(
        [{"unit_id": u.unit_id, "text": u.text, "section": u.section} for u in units],
        indent=2,
    )
    raw = strip_fence(await _run(agent, payload))
    extracted = _Extraction.model_validate_json(raw).units
    by_id = {e.unit_id: e.elements for e in extracted}
    # A unit the model skipped keeps an empty element list rather than
    # disappearing, so the unit count never depends on the model.
    return [u.model_copy(update={"elements": by_id.get(u.unit_id, [])}) for u in units]


def judge(
    document_units: list[ClaimUnit], profile: Profile, config: Config
) -> list[UnitVerdict]:
    return asyncio.run(_judge(document_units, profile, build_model(config)))


async def _judge(
    document_units: list[ClaimUnit], profile: Profile, model: BaseLlm
) -> list[UnitVerdict]:
    """PRD 5.8's verifier: the profile plus the claims, and nothing else.

    It never sees the tailoring node's context, so it cannot inherit the
    tailor's justification for a claim.
    """
    agent = Agent(
        name="verify_claims",
        model=model,
        instruction=load_instruction("verify_claims"),
    )
    payload = (
        "## Profile\n\n```json\n"
        + profile.model_dump_json(indent=2)
        + "\n```\n\n## Claim units\n\n```json\n"
        + json.dumps([u.model_dump() for u in document_units], indent=2)
        + "\n```\n"
    )
    raw = strip_fence(await _run(agent, payload))
    return _Verdicts.model_validate_json(raw).verdicts


async def _run(agent: Agent, message: str) -> str:
    session_service = InMemorySessionService()
    runner = Runner(app_name=APP_NAME, agent=agent, session_service=session_service)
    session = await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID
    )
    content = types.Content(role="user", parts=[types.Part(text=message)])

    reply = ""
    async for event in runner.run_async(
        user_id=USER_ID, session_id=session.id, new_message=content
    ):
        if event.partial or not event.content or event.content.role != "model":
            continue
        reply += "".join(
            part.text
            for part in (event.content.parts or [])
            if part.text and not part.thought
        )
    if not reply.strip():
        raise RuntimeError(f"{agent.name} returned no text")
    return reply


def strip_fence(text: str) -> str:
    """Drops a ```json fence if the model wrapped its object in one."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1]
        stripped = stripped.rsplit("```", 1)[0]
    return stripped.strip()
