"""The baseline: one LLM call per JD, and nothing else.

PRD §6. This is the "reasonable basic way to handle the task" the hackathon
brief asks for -- the raw resume text plus a job posting, asked in a single
prompt to label the match and write a tailored resume and cover letter. No
profile schema, no H-1B lookup, no gap questions, no verifier, no exemplars.

Fairness is the point, so what is held identical to the agent is: the 15
fixture JDs, offline from the committed cache; the one model in `config.yaml`;
the output layout; and the scorers. The one resource difference -- baseline
reads `fixture/resume_raw.md`, the agent reads `profile.json` -- is stated in
the README, because the profile was built from that same resume.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from google.adk import Agent, Runner
from google.adk.models import BaseLlm
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types
from pydantic import BaseModel, Field, ValidationError

from jobpilot.agents import load_instruction
from jobpilot.config import REPO_ROOT, build_model, load_config
from jobpilot.eval.run_record import JDRecord, RunRecord, write_run_record
from jobpilot.ingest import JD, LinkListIngester
from jobpilot.verify.llm import strip_fence

APP_NAME = "jobpilot_baseline"
USER_ID = "baseline"
STAGE = "baseline"
RESUME_PATH = REPO_ROOT / "fixture" / "resume_raw.md"

# Mirrors the triage concurrency cap so the two runs are shaped alike.
MAX_PARALLEL = 4

# The baseline speaks its own vocabulary -- handing it the triage rubric would
# hide most of what iter1 exists to demonstrate. Mapping to the label set is
# mechanical and happens here, not in the prompt.
LABEL_MAP = {"strong": "most_matched", "weak": "less_matched", "no": "skip"}


class BaselineOutput(BaseModel):
    label: str
    reasons: list[str] = Field(default_factory=list)
    resume_markdown: str
    cover_letter_markdown: str


async def _one(
    jd: JD, resume: str, model: BaseLlm, instruction: str, gate: asyncio.Semaphore
) -> tuple[JD, BaselineOutput | None, str | None, int, int, float]:
    async with gate:
        agent = Agent(name="baseline", model=model, instruction=instruction)
        session_service = InMemorySessionService()
        runner = Runner(
            app_name=APP_NAME, agent=agent, session_service=session_service
        )
        session = await session_service.create_session(
            app_name=APP_NAME, user_id=USER_ID
        )
        message = types.Content(
            role="user",
            parts=[
                types.Part(
                    text=(
                        f"## Resume\n\n{resume}\n\n"
                        f"## Job posting\n\n"
                        f"{jd.company} — {jd.title} ({jd.location})\n\n{jd.text}\n"
                    )
                )
            ],
        )

        started = time.monotonic()
        reply = ""
        tokens_in = tokens_out = 0
        async for event in runner.run_async(
            user_id=USER_ID, session_id=session.id, new_message=message
        ):
            usage = event.usage_metadata
            if usage:
                tokens_in += usage.prompt_token_count or 0
                tokens_out += usage.candidates_token_count or 0
            if event.partial or not event.content or event.content.role != "model":
                continue
            reply += "".join(
                part.text
                for part in (event.content.parts or [])
                if part.text and not part.thought
            )
        elapsed = round(time.monotonic() - started, 2)

        try:
            parsed = BaselineOutput.model_validate_json(strip_fence(reply))
        except (ValidationError, ValueError) as exc:
            # Recorded, never swallowed: the JD stays in the denominator and
            # shows up in per_jd.md. A silently dropped JD makes every rate
            # wrong in a direction nobody notices.
            return jd, None, f"unparseable model output: {exc}"[:200], (
                tokens_in
            ), tokens_out, elapsed

        return jd, parsed, None, tokens_in, tokens_out, elapsed


async def _run_all(
    jds: list[JD], resume: str, model: BaseLlm, instruction: str
) -> list[tuple]:
    gate = asyncio.Semaphore(MAX_PARALLEL)
    return await asyncio.gather(
        *(_one(jd, resume, model, instruction, gate) for jd in jds)
    )


def _digest(record: RunRecord, results: dict[str, BaselineOutput]) -> str:
    buckets = {"most_matched": [], "less_matched": [], "skip": []}
    for jd in record.jds:
        if jd.label:
            buckets[jd.label].append(jd.jd_id)

    lines = [
        f"# Baseline digest — {record.date}",
        "",
        f"{len(record.jds)} postings ingested · "
        f"{len(buckets['most_matched'])} strong · "
        f"{len(buckets['less_matched'])} weak · "
        f"{len(buckets['skip'])} skipped · "
        f"{sum(1 for jd in record.jds if jd.error)} failed.",
        "",
        "One prompt per posting: no H-1B filter, no gap questions, no "
        "verification.",
        "",
        "| JD | label | packet |",
        "| -- | ----- | ------ |",
    ]
    for jd in record.jds:
        lines.append(
            f"| {jd.jd_id} | {jd.label or 'error'} | {jd.packet or '—'} |"
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--links", type=Path, default=Path("fixture/links.txt"))
    parser.add_argument(
        "--offline",
        action="store_true",
        default=True,
        help="score from the committed cache; on by default",
    )
    parser.add_argument("--online", dest="offline", action="store_false")
    parser.add_argument("--out", type=Path, help="run directory (default output/…)")
    args = parser.parse_args(argv)

    load_dotenv()
    config = load_config()
    resume = RESUME_PATH.read_text()
    instruction = load_instruction("baseline")

    jds = LinkListIngester(links_path=args.links, offline=args.offline).fetch().jds
    print(f"{len(jds)} JDs · model {config.model.id} · one call each\n")

    model = build_model(config)
    results = asyncio.run(_run_all(jds, resume, model, instruction))

    today = date.today().isoformat()
    run_dir = args.out or (REPO_ROOT / "output" / STAGE / today)
    (run_dir / "packets").mkdir(parents=True, exist_ok=True)

    records: list[JDRecord] = []
    outputs: dict[str, BaselineOutput] = {}
    for jd, parsed, error, tokens_in, tokens_out, elapsed in results:
        packet = None
        label = None
        if parsed is not None:
            label = LABEL_MAP.get(parsed.label.strip().lower())
            if label is None:
                error = f"unrecognised label {parsed.label!r}"
            else:
                folder = run_dir / "packets" / jd.jd_id
                folder.mkdir(parents=True, exist_ok=True)
                (folder / "resume.md").write_text(parsed.resume_markdown.strip() + "\n")
                (folder / "cover_letter.md").write_text(
                    parsed.cover_letter_markdown.strip() + "\n"
                )
                (folder / "reasons.json").write_text(
                    json.dumps({"label": parsed.label, "reasons": parsed.reasons},
                               indent=2) + "\n"
                )
                packet = f"packets/{jd.jd_id}"
                outputs[jd.jd_id] = parsed

        records.append(
            JDRecord(
                jd_id=jd.jd_id,
                label=label,
                packet=packet,
                input_tokens=tokens_in,
                output_tokens=tokens_out,
                wall_clock_s=elapsed,
                error=error,
            )
        )
        print(
            f"{jd.jd_id}  {(label or 'ERROR'):<14} {jd.company[:16]:<18} "
            f"{tokens_in:>6}in {tokens_out:>5}out {elapsed:>6.1f}s"
            + (f"  {error}" if error else "")
        )

    records.sort(key=lambda r: r.jd_id)
    record = RunRecord(
        stage=STAGE,
        date=today,
        model=config.model.id,
        flags={},
        offline=args.offline,
        jds=records,
    )
    write_run_record(record, run_dir)
    (run_dir / "digest.md").write_text(_digest(record, outputs))

    failed = sum(1 for r in records if r.error)
    print(f"\nwrote {run_dir}  ({len(records) - failed} packets, {failed} failed)")
    print(f"score it: python -m jobpilot.eval --stage {STAGE}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
