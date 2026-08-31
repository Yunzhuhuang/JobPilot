#!/usr/bin/env python
"""Extract what each fixture JD asks for. Run once; the result is frozen.

PRD 7.1: one LLM call per JD with a fixed prompt, cached to
`fixture/requirements/<jd_id>.json`, never re-run during a stage eval. The
prompt lives in `jobpilot/agents/instructions/extract_requirements.md` so
"fixed" is auditable rather than asserted.

    python scripts/extract_requirements.py --fixture fixture/
    python scripts/extract_requirements.py --only jd_07 --force

Roughly $0.85 for all 15 on claude-opus-5. Already-extracted JDs are skipped
and cost nothing, so a re-run is free.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from google.adk import Agent, Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types
from pydantic import BaseModel, ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobpilot.agents import load_instruction
from jobpilot.config import build_model, load_config
from jobpilot.ingest import read_entry
from jobpilot.requirements import (
    REQUIREMENTS_DIR,
    Requirement,
    RequirementSet,
    requirements_path,
    write_requirements,
)

APP_NAME = "jobpilot_extract"
USER_ID = "fixture"


class _Extraction(BaseModel):
    """What the model returns. Wrapped in an object because a bare array is a
    weaker contract to state in a prompt."""

    requirements: list[Requirement]


async def _extract_one(agent: Agent, jd_text: str) -> _Extraction:
    session_service = InMemorySessionService()
    runner = Runner(
        app_name=APP_NAME, agent=agent, session_service=session_service
    )
    session = await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID
    )

    message = types.Content(role="user", parts=[types.Part(text=jd_text)])
    # `event.output` is only populated for an agent running as a workflow node
    # (ADK's _llm_agent_wrapper does that), so a standalone agent's result has
    # to be read off the model turn and parsed here.
    reply = ""
    async for event in runner.run_async(
        user_id=USER_ID, session_id=session.id, new_message=message
    ):
        if event.partial or not event.content or event.content.role != "model":
            continue
        reply += "".join(
            part.text for part in (event.content.parts or [])
            if part.text and not part.thought
        )

    if not reply.strip():
        raise RuntimeError("the model returned no text")
    return _Extraction.model_validate_json(_strip_fence(reply))


def _strip_fence(text: str) -> str:
    """Drops a ```json fence if the model wrapped its object in one."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1]
        stripped = stripped.rsplit("```", 1)[0]
    return stripped.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=Path("fixture"))
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite existing extractions (for fixing a bad one, not routine use)",
    )
    parser.add_argument("--only", help="a single jd_id, e.g. jd_07")
    args = parser.parse_args(argv)

    load_dotenv()
    config = load_config()
    agent = Agent(
        name="extract_requirements",
        model=build_model(config),
        output_schema=_Extraction,
        instruction=load_instruction("extract_requirements"),
    )

    cache_dir = args.fixture / "cache"
    out_dir = args.fixture / "requirements"
    if out_dir == Path("fixture/requirements"):
        out_dir = REQUIREMENTS_DIR

    paths = sorted(cache_dir.glob("jd_*.md"))
    if args.only:
        paths = [p for p in paths if p.stem == args.only]
        if not paths:
            print(f"error: no cache entry named {args.only}", file=sys.stderr)
            return 2

    extracted = skipped = failed = 0
    for path in paths:
        jd = read_entry(path)
        target = requirements_path(jd.jd_id, out_dir)
        if target.exists() and not args.force:
            print(f"{jd.jd_id}  skip (already extracted)")
            skipped += 1
            continue

        try:
            result = asyncio.run(_extract_one(agent, jd.text))
        except (RuntimeError, ValidationError) as exc:
            print(f"{jd.jd_id}  FAILED: {exc}", file=sys.stderr)
            failed += 1
            continue

        rs = RequirementSet(
            jd_id=jd.jd_id,
            extracted_at=date.today().isoformat(),
            model=config.model.id,
            requirements=result.requirements,
        )
        write_requirements(rs, out_dir)
        must = len(rs.required_only())
        print(
            f"{jd.jd_id}  {jd.company[:16]:<18} "
            f"{len(rs.requirements):>2} requirements ({must} required)"
        )
        extracted += 1

    print(f"\n{extracted} extracted, {skipped} skipped, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
