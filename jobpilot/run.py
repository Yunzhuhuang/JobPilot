"""`python -m jobpilot run --stage <name>` -- execute the pipeline.

Writes the same contract the baseline writes, so `jobpilot.eval` grades both
with one set of scorers and neither knows about the other: `run.json`,
`digest.md`, and per-JD packets.
"""

from __future__ import annotations

import asyncio
import shutil
from datetime import date
from pathlib import Path

from google.adk import Runner, Workflow
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

from jobpilot.answers import AlwaysNo, AnswerProvider
from jobpilot.config import REPO_ROOT, load_config
from jobpilot.eval.presets import load_preset
from jobpilot.eval.run_record import JDRecord, RunRecord, write_run_record
from jobpilot.ingest import LinkListIngester
from jobpilot.profile import load_profile
from jobpilot.trajectory import Recorder
from jobpilot.workflow import GraphResult, build_workflow, node_names

APP_NAME = "jobpilot"
USER_ID = "author"


REQUEST_INPUT_CALL = "adk_request_input"
MAX_PAUSES = 8


def _find_interrupt(events: list[object]) -> object | None:
    """The paused-run signal. `long_running_tool_ids` is the canonical marker."""
    for event in events:
        if getattr(event, "long_running_tool_ids", None):
            return event
    return None


def _interrupt_request(event: object) -> tuple[str, str, dict]:
    """(interrupt id, message, payload) out of the interrupt event."""
    content = getattr(event, "content", None)
    for part in (getattr(content, "parts", None) or []):
        call = getattr(part, "function_call", None)
        if call and call.name == REQUEST_INPUT_CALL:
            args = call.args or {}
            return call.id, args.get("message", ""), args.get("payload", {}) or {}
    raise AssertionError("interrupt event carried no adk_request_input call")


def _resume_message(interrupt_id: str, reply: dict) -> types.Content:
    """`response` must be a Mapping, and must not be mixed with text parts."""
    return types.Content(
        role="user",
        parts=[
            types.Part(
                function_response=types.FunctionResponse(
                    id=interrupt_id, name=REQUEST_INPUT_CALL, response=reply
                )
            )
        ],
    )


async def _drive(
    workflow: Workflow, seed: str, answers: AnswerProvider | None = None
) -> int:
    """Run the graph, answering every pause. Returns how many times it paused.

    A loop rather than a single pass, because `iter4` interrupts mid-run with
    real work on both sides. The provider is injected, so this code path is
    identical whether the author is at a terminal, a fixture file is answering,
    or `--no-questions` is declining everything.
    """
    session_service = InMemorySessionService()
    runner = Runner(app_name=APP_NAME, node=workflow, session_service=session_service)
    session = await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID
    )
    message: types.Content | None = types.Content(
        role="user", parts=[types.Part(text=seed)]
    )
    invocation_id: str | None = None
    pauses = 0

    while message is not None and pauses <= MAX_PAUSES:
        events: list[object] = []
        kwargs = {"invocation_id": invocation_id} if invocation_id else {}
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=session.id,
            new_message=message,
            **kwargs,
        ):
            events.append(event)

        interrupt = _find_interrupt(events)
        if interrupt is None:
            return pauses

        interrupt_id, text, payload = _interrupt_request(interrupt)
        provider = answers or AlwaysNo()
        reply = provider.answer(text, list(payload.get("tools", [])), "run")
        message = _resume_message(interrupt_id, reply)
        # Reconciled, not trusted: a wrong invocation id silently drops the
        # response and the graph waits forever.
        invocation_id = interrupt.invocation_id
        pauses += 1

    return pauses


def execute(
    stage_name: str,
    *,
    links: Path,
    offline: bool = True,
    out: Path | None = None,
    answers: AnswerProvider | None = None,
) -> Path:
    config = load_config()
    # require_built=True is what makes a preset for an unbuilt node fail loudly
    # rather than quietly produce a stage that measures nothing.
    stage = load_preset(stage_name, require_built=True)
    profile = load_profile()

    jds = LinkListIngester(links_path=links, offline=offline).fetch().jds
    recorder = Recorder(stage_name)
    result = GraphResult()
    workflow = build_workflow(
        jds, profile, config, stage.flags, recorder, result, answers
    )

    print(f"{stage_name} — {stage.description}")
    print(f"{len(jds)} JDs · model {config.model.id}")
    print(f"graph: {' -> '.join(node_names(workflow))}\n")

    pauses = asyncio.run(_drive(workflow, "start", answers))

    today = date.today().isoformat()
    run_dir = out or (REPO_ROOT / "output" / stage_name / today)

    # `output/<stage>/<date>/` is *one run*, not everything run today. Re-running
    # a stage on the same day used to leave the previous run's packets in place,
    # and `scorers.resume_paths` reads whatever is on disk -- so a second run
    # that tailored fewer postings was scored against a mixture of both. Caught
    # 2026-08-30 when iter3a's directory held three packets from 22:49 beside
    # three from 22:53. Packets are derived output and fully regenerable; the
    # run about to be written is the only one that should be there.
    packets_dir = run_dir / "packets"
    if packets_dir.exists():
        shutil.rmtree(packets_dir)
    packets_dir.mkdir(parents=True, exist_ok=True)

    records: list[JDRecord] = []
    for jd in jds:
        triage = result.triage.get(jd.jd_id)
        h1b = result.h1b.get(jd.jd_id)
        tokens_in, tokens_out, elapsed = result.usage.get(jd.jd_id, (0, 0, 0.0))

        # The packet folder is the tailor's output on disk. `resume.md` is the
        # path the fabrication scorer reads (scorers.resume_paths), so writing
        # it here is what makes the primary metric scoreable at all.
        docs = result.docs.get(jd.jd_id)
        if docs is not None:
            packet_dir = run_dir / "packets" / jd.jd_id
            packet_dir.mkdir(parents=True, exist_ok=True)
            for filename, body in docs.files().items():
                if body.strip():
                    (packet_dir / filename).write_text(body.rstrip() + "\n")
            # PRD 4.4 lists this as a packet deliverable: it is what makes a
            # rejection auditable after the fact, claim by claim.
            report = result.reports.get(jd.jd_id)
            if report is not None:
                (packet_dir / "verification_report.json").write_text(
                    report.model_dump_json(indent=2) + "\n"
                )
        records.append(
            JDRecord(
                jd_id=jd.jd_id,
                label=triage.label if triage else None,
                # A packet exists only when something was written into it. At
                # iter1 nothing is generated, so the trajectory is the packet.
                packet=f"packets/{jd.jd_id}",
                gap_questions=result.gap_questions.get(jd.jd_id, []),
                revision_rounds=result.revisions.get(jd.jd_id, (0, 0))[0],
                dropped_lines=result.revisions.get(jd.jd_id, (0, 0))[1],
                sponsorship=h1b.likelihood if h1b else None,
                h1b_confidence=h1b.confidence if h1b else None,
                matched_employer=h1b.matched_entity if h1b else None,
                h1b_searches=len(h1b.searches) if h1b else 0,
                dropped_by_h1b=bool(
                    h1b and h1b.likelihood == "unlikely" and h1b.confidence == "high"
                ),
                input_tokens=tokens_in,
                output_tokens=tokens_out,
                wall_clock_s=elapsed,
                error=result.errors.get(jd.jd_id),
            )
        )
        if triage:
            status = triage.label
            note = triage.reasons[0][:46] if triage.reasons else ""
        elif h1b and records[-1].dropped_by_h1b:
            status, note = "dropped-h1b", h1b.rationale[:46]
        else:
            status, note = "ERROR", (result.errors.get(jd.jd_id) or "")[:46]
        sponsor = (
            f"{h1b.likelihood[:6]:<6} {(h1b.matched_entity or '—')[:26]:<26}"
            if h1b
            else " " * 33
        )
        print(
            f"{jd.jd_id}  {status:<14} {jd.company[:16]:<18} "
            f"score={triage.score if triage else '--':>3}  {sponsor} {note}"
        )

    record = RunRecord(
        stage=stage_name,
        date=today,
        model=config.model.id,
        flags=stage.flags.model_dump(),
        offline=offline,
        jds=records,
    )
    write_run_record(record, run_dir)
    (run_dir / "digest.md").write_text(_digest(record, result))
    recorder.write(run_dir)

    if pauses:
        print(f"\npaused {pauses} time(s) for human input")
    counts = {k: sum(1 for r in records if r.label == k)
              for k in ("most_matched", "less_matched", "skip")}
    print(f"\n{counts}  ·  {sum(1 for r in records if r.error)} failed")
    print(f"wrote {run_dir}")
    print(f"score it: python -m jobpilot.eval --stage {stage_name}")
    return run_dir


def _digest(record: RunRecord, result: GraphResult) -> str:
    counts = {k: sum(1 for r in record.jds if r.label == k)
              for k in ("most_matched", "less_matched", "skip")}
    enabled = [k for k, v in record.flags.items() if v]
    jds = {jd.jd_id: jd for jd in result.jds}
    lines = [
        f"# {record.stage} digest — {record.date}",
        "",
        f"{len(record.jds)} postings · {counts['most_matched']} most matched · "
        f"{counts['less_matched']} less matched · {counts['skip']} skipped · "
        f"{sum(1 for r in record.jds if r.error)} failed.",
        "",
        f"Capabilities on: {', '.join(enabled) or 'none'}.",
        "",
        "## Most matched",
        "",
        "| JD | company | title | score | why |",
        "| -- | ------- | ----- | ----- | --- |",
    ]
    for r in record.jds:
        if r.label != "most_matched":
            continue
        t, jd = result.triage.get(r.jd_id), jds.get(r.jd_id)
        lines.append(
            f"| {r.jd_id} | {jd.company if jd else ''} | {jd.title if jd else ''} "
            f"| {t.score if t else ''} | {'; '.join(t.reasons[:2]) if t else ''} |"
        )
    lines += [
        "",
        "## Less matched",
        "",
        "| JD | company | title | score | why |",
        "| -- | ------- | ----- | ----- | --- |",
    ]
    for r in record.jds:
        if r.label != "less_matched":
            continue
        t, jd = result.triage.get(r.jd_id), jds.get(r.jd_id)
        lines.append(
            f"| {r.jd_id} | {jd.company if jd else ''} | {jd.title if jd else ''} "
            f"| {t.score if t else ''} | {'; '.join(t.reasons[:2]) if t else ''} |"
        )

    # Sponsorship is reported for every posting, including skipped ones. It is
    # employer-level history, not eligibility for this role, and the two
    # disagree often enough that collapsing them would mislead: Mach
    # Industries files H-1B petitions and still bars this posting on ITAR.
    assessed = [r for r in record.jds if r.sponsorship]
    if assessed:
        lines += [
            "",
            "## H-1B sponsorship (employer history, not role eligibility)",
            "",
            "| JD | company | likely? | USCIS entity | conf | searches |",
            "| -- | ------- | ------- | ------------ | ---- | -------- |",
        ]
        for r in assessed:
            jd = jds.get(r.jd_id)
            lines.append(
                f"| {r.jd_id} | {jd.company if jd else ''} | {r.sponsorship} "
                f"| {r.matched_employer or '—'} | {r.h1b_confidence} "
                f"| {r.h1b_searches} |"
            )

    # Skipped JDs are counted, not listed (PRD 5.5) -- but the reason is kept,
    # because an over-skip is the expensive error and needs to be auditable.
    skipped = [r for r in record.jds if r.label == "skip"]
    lines += ["", f"## Skipped ({len(skipped)})", ""]
    for r in skipped:
        t, jd = result.triage.get(r.jd_id), jds.get(r.jd_id)
        lines.append(
            f"- **{r.jd_id}** {jd.company if jd else ''} — "
            f"{t.reasons[0] if t and t.reasons else 'no reason recorded'}"
        )
    lines.append("")
    return "\n".join(lines)
