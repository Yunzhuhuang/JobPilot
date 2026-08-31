"""The ADK 2.0 graph. Every node is flag-routed by the stage preset.

A disabled capability is *absent from the graph*, not a node that returns
early -- `iter2` is `iter1` with one more node in the chain and nothing else
changed. That is what makes a stage-to-stage delta attributable, and it is why
the edges are assembled from flags rather than fixed.

    START -> ingest -> [h1b?] -> triage -> [tailor?] -> digest

Nodes are built by factories closing over the profile, config and recorder. The
profile is a Pydantic object; threading it through `ctx.state` would mean
serializing it at every hop for no benefit.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator
from typing import Any

from google.adk import Context, Workflow
from google.adk.events import RequestInput
from google.adk.models import BaseLlm
from google.adk.workflow import START, BaseNode, node

from jobpilot.agents import h1b as h1b_agent
from jobpilot.agents import tailor as tailor_agent
from jobpilot.agents import triage as triage_agent
from jobpilot.answers import AnswerProvider, GapAnswer
from jobpilot.config import Config, build_model
from jobpilot.eval.presets import StageFlags
from jobpilot.gaps import gap_diff, question_text
from jobpilot.h1b import load_index
from jobpilot.ingest import JD
from jobpilot.profile.schema import Profile
from jobpilot.profile.writeback import apply_answer, write_profile
from jobpilot.requirements import load_requirements
from jobpilot.trajectory import Recorder, Step
from jobpilot.verify import VerificationReport, strip_units, verify
from jobpilot.verify.llm import strip_fence
from jobpilot.verify.schema import ClaimUnit

MAX_PARALLEL_TRIAGE = 4

# PRD 5.1: verify -> tailor revision, at most twice. On exhaustion the
# offending lines are removed in code.
MAX_REVISIONS = 2


class GraphResult:
    """What the run produced, collected out of the nodes."""

    def __init__(self) -> None:
        self.jds: list[JD] = []
        self.profile: Profile | None = None
        """The live profile. `iter4` rewrites it mid-run, so the tailor and
        verifier must read it here rather than close over a stale copy."""
        self.gap_questions: dict[str, list[str]] = {}
        self.gap_diff_note: list[str] = []
        self.triage: dict[str, triage_agent.TriageResult] = {}
        self.errors: dict[str, str] = {}
        self.h1b: dict[str, h1b_agent.SponsorshipAssessment] = {}
        self.docs: dict[str, tailor_agent.TailoredDocs] = {}
        self.reports: dict[str, VerificationReport] = {}
        self.revisions: dict[str, tuple[int, int]] = {}
        """jd_id -> (revision rounds, lines dropped on exhaustion)."""
        self.usage: dict[str, tuple[int, int, float]] = {}


def build_workflow(
    jds: list[JD],
    profile: Profile,
    config: Config,
    flags: StageFlags,
    recorder: Recorder,
    result: GraphResult,
    answers: AnswerProvider | None = None,
) -> Workflow:
    model = build_model(config)
    result.profile = profile
    chain: list[Any] = [START, _ingest_node(jds, recorder, result)]

    if flags.h1b_filter:
        chain.append(_h1b_node(model, recorder, result))

    if flags.triage:
        chain.append(_triage_node(profile, model, recorder, result))

    if flags.gap_memory:
        chain.append(_gap_ask_node(recorder, result))
        chain.append(_gap_write_node(recorder, result, answers))

    if flags.tailor:
        chain.append(
            _tailor_node(
                profile, model, recorder, result, self_verify=flags.self_verify
            )
        )

    if flags.verifier_node:
        chain.append(_verify_node(profile, config, model, recorder, result))

    chain.append(_digest_node(recorder, result))
    return Workflow(
        name="jobpilot",
        edges=[tuple(chain)],
        max_concurrency=MAX_PARALLEL_TRIAGE,
    )


def _ingest_node(
    jds: list[JD], recorder: Recorder, result: GraphResult
) -> BaseNode:
    """Deterministic: the JDs are already fetched and cached (PRD §5.4)."""

    @node(name="ingest")
    def ingest(node_input: str) -> list[str]:
        started = time.monotonic()
        result.jds = jds
        recorder.add(
            "run",
            Step(
                node="ingest",
                inputs={"links": len(jds)},
                output={"jd_ids": [jd.jd_id for jd in jds]},
                wall_clock_s=round(time.monotonic() - started, 3),
            ),
        )
        return [jd.jd_id for jd in jds]

    return ingest


def _h1b_node(model: BaseLlm, recorder: Recorder, result: GraphResult) -> BaseNode:
    """Employer-level sponsorship, resolved by an agent over USCIS data (PRD §4.3).

    The retrieval is deterministic and the *decision* is not, for reasons
    `jobpilot.h1b.lookup` documents at length: a brand name and a legal entity
    name are related by knowledge of the world, not by edit distance.

    This answers "does this employer ever sponsor", which is not the question
    "can this candidate be hired into this role". SpaceX files H-1B petitions
    and still cannot staff Starshield with a non-US-person, so a sponsorship
    `likely` and a triage `skip` are both correct about it at the same time.
    Triage owns the second question; this node must not touch it.

    Nothing is dropped on a `likely`/`unknown`. Dropping is destructive -- a
    dropped posting never reaches triage, the digest, or the author -- so only
    a positive `unlikely` finding removes anything, and `unknown` (an employer
    absent from the data) is never treated as a no.
    """
    gate = asyncio.Semaphore(MAX_PARALLEL_TRIAGE)

    @node(name="h1b_filter", rerun_on_resume=True)
    async def h1b(ctx: Context, node_input: list[str]) -> AsyncGenerator[Any, None]:
        index = load_index()

        async def one(jd: JD) -> None:
            async with gate:
                meter = triage_agent.UsageMeter()
                searches: list[dict] = []
                # The name must be unique per concurrent run -- see
                # h1b_agent.build_agent for what a shared one does.
                agent = h1b_agent.build_agent(
                    index,
                    model,
                    meter,
                    name=f"h1b_{jd.jd_id}",
                    searches=searches,
                )
                started = time.monotonic()
                error = None
                try:
                    reply = await ctx.run_node(
                        agent,
                        node_input=h1b_agent.sponsorship_prompt(jd, index),
                        # Mandatory for a concurrent tool-using agent. Without
                        # it every child writes its function_call and
                        # function_response events onto the parent's branch,
                        # so each agent's next request carries the others'
                        # tool traffic -- ADK logs "Dropping function
                        # responses with no matching function call" and the
                        # answers cross. Observed 2026-08-30: SpaceX came back
                        # as MERCOR IO CORPORATION, having run four other
                        # postings' searches. Unique agent names do not fix
                        # it; the shared branch is the state that leaks.
                        use_sub_branch=True,
                    )
                    parsed = h1b_agent.parse_assessment(
                        reply if isinstance(reply, str) else str(reply)
                    )
                    parsed.searches = list(searches)
                    # The agent may only name employers that exist. Checking is
                    # cheap and the alternative is fabricated evidence in the
                    # one project that measures fabrication.
                    if parsed.matched_entity:
                        found = [
                            c.employer
                            for c in index.search(parsed.matched_entity, cutoff=99)
                            if c.employer.name == parsed.matched_entity
                        ]
                        parsed.entity_verified = bool(found)
                        if found:
                            parsed.approvals = found[0].total
                        else:
                            parsed.likelihood = "unknown"
                            parsed.confidence = "low"
                            parsed.rationale += (
                                " [rejected: no such employer in the USCIS data]"
                            )
                    result.h1b[jd.jd_id] = parsed
                    output: Any = parsed.model_dump()
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"[:200]
                    result.errors[jd.jd_id] = error
                    output = None
                elapsed = round(time.monotonic() - started, 3)
                previous = result.usage.get(jd.jd_id, (0, 0, 0.0))
                result.usage[jd.jd_id] = (
                    previous[0] + meter.input_tokens,
                    previous[1] + meter.output_tokens,
                    previous[2] + elapsed,
                )
                recorder.add(
                    jd.jd_id,
                    Step(
                        node="h1b_filter",
                        instruction=f"{h1b_agent.INSTRUCTION}.md",
                        inputs={
                            "jd_id": jd.jd_id,
                            "company": jd.company,
                            "location": jd.location,
                            "employers_in_index": len(index),
                            "fiscal_year": index.fiscal_year,
                        },
                        output=output,
                        error=error,
                        tool_calls=list(searches),
                        wall_clock_s=elapsed,
                        input_tokens=meter.input_tokens,
                        output_tokens=meter.output_tokens,
                    ),
                )

        wanted = set(node_input)
        await asyncio.gather(*(one(jd) for jd in result.jds if jd.jd_id in wanted))

        dropped = [
            jd_id
            for jd_id, a in result.h1b.items()
            if a.likelihood == "unlikely" and a.confidence == "high"
        ]
        recorder.add(
            "run",
            Step(
                node="h1b_filter",
                inputs={"employers_in_index": len(index), "jds": len(wanted)},
                output={
                    "dropped": dropped,
                    "resolved": sum(
                        1 for a in result.h1b.values() if a.matched_entity
                    ),
                },
            ),
        )
        yield [jd_id for jd_id in node_input if jd_id not in dropped]

    return h1b


def _triage_node(
    profile: Profile, model: BaseLlm, recorder: Recorder, result: GraphResult
) -> BaseNode:
    """Fans out across JDs with a concurrency cap (PRD §5.1).

    `rerun_on_resume=True` is mandatory for any node calling `ctx.run_node`:
    a dynamically scheduled child may interrupt, and the framework re-runs the
    parent to collect its answer. It is also the node shape the gap-question
    pause drops into at iter4.
    """
    summary = triage_agent.profile_summary(profile)
    gate = asyncio.Semaphore(MAX_PARALLEL_TRIAGE)

    @node(name="triage", rerun_on_resume=True)
    async def triage(ctx: Context, node_input: list[str]) -> AsyncGenerator[Any, None]:
        async def one(jd: JD) -> None:
            async with gate:
                meter = triage_agent.UsageMeter()
                agent = triage_agent.build_agent(model, meter)
                started = time.monotonic()
                try:
                    reply = await ctx.run_node(
                        agent,
                        node_input=triage_agent.triage_prompt(
                            jd, summary, result.h1b.get(jd.jd_id)
                        ),
                        use_sub_branch=True,
                    )
                    parsed = triage_agent.TriageResult.model_validate_json(
                        strip_fence(reply if isinstance(reply, str) else str(reply))
                    )
                    result.triage[jd.jd_id] = parsed
                    output: Any = parsed.model_dump()
                    error = None
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"[:200]
                    result.errors[jd.jd_id] = error
                    output = None
                elapsed = round(time.monotonic() - started, 3)
                # Accumulate: a JD may already carry the H-1B node's usage,
                # and cost/JD is a per-posting total across every node that
                # ran, not the last one to write.
                previous = result.usage.get(jd.jd_id, (0, 0, 0.0))
                result.usage[jd.jd_id] = (
                    previous[0] + meter.input_tokens,
                    previous[1] + meter.output_tokens,
                    round(previous[2] + elapsed, 3),
                )
                recorder.add(
                    jd.jd_id,
                    Step(
                        node="triage",
                        instruction=f"{triage_agent.INSTRUCTION}.md",
                        inputs={
                            "jd_id": jd.jd_id,
                            "company": jd.company,
                            "title": jd.title,
                            "profile_summary_chars": len(summary),
                            "h1b_evidence": (
                                result.h1b[jd.jd_id].likelihood
                                if jd.jd_id in result.h1b
                                else None
                            ),
                            "claimable_tools": triage_agent.whitelist_size(profile),
                        },
                        output=output,
                        error=error,
                        wall_clock_s=elapsed,
                        input_tokens=meter.input_tokens,
                        output_tokens=meter.output_tokens,
                    ),
                )

        surviving = set(node_input)
        await asyncio.gather(
            *(one(jd) for jd in result.jds if jd.jd_id in surviving)
        )
        yield {jd_id: r.label for jd_id, r in result.triage.items()}

    return triage


GAP_INTERRUPT_ID = "jobpilot_gap_questions"


def _gap_ask_node(recorder: Recorder, result: GraphResult) -> BaseNode:
    """The human checkpoint (PRD §5.6). A leaf pause, or a pass-through.

    **One batched question per run, not per posting.** The PRD says per JD; this
    asks once across every `most_matched` posting instead, because the answer is
    a fact about the author rather than about the posting -- "have you used
    Ubuntu?" has one true answer however many postings raise it -- and because
    seven separate interruptions is a worse product than one. The buckets, the
    write-back and the never-re-ask rule are unchanged.

    Left at the default `rerun_on_resume=False`: on resume the answer simply
    *becomes* this node's output and flows down the edge, which is the shape
    `scripts/adk_smoke_test.py` proved.
    """

    @node(name="gap_ask")
    def gap_ask(node_input: dict[str, str]) -> AsyncGenerator[Any, None]:
        profile = result.profile
        requirements = load_requirements()
        asked: list[str] = []
        for jd in result.jds:
            if node_input.get(jd.jd_id) != "most_matched":
                continue
            gaps = gap_diff(profile, requirements.get(jd.jd_id), jd.jd_id)
            result.gap_questions[jd.jd_id] = gaps.unknown
            asked.extend(t for t in gaps.unknown if t not in asked)

        recorder.add(
            "run",
            Step(
                node="gap_ask",
                inputs={"most_matched": sum(
                    1 for v in node_input.values() if v == "most_matched"
                )},
                output={"tools_to_ask": asked},
            ),
        )
        if not asked:
            # Nothing unknown. Do not pause -- interrupting a human to tell them
            # there is nothing to ask is the worst possible use of a pause.
            yield {"used": []}
            return

        companies = ", ".join(
            sorted({jd.company for jd in result.jds
                    if node_input.get(jd.jd_id) == "most_matched"})
        )
        yield RequestInput(
            interrupt_id=GAP_INTERRUPT_ID,
            message=question_text(companies, _AskedGaps(asked)),
            payload={"tools": asked},
            response_schema=GapAnswer,
        )

    return gap_ask


class _AskedGaps:
    """Adapter so `question_text` can render a run-level question unchanged."""

    def __init__(self, tools: list[str]) -> None:
        self.unknown = tools


def _gap_write_node(
    recorder: Recorder, result: GraphResult, answers: AnswerProvider | None
) -> BaseNode:
    """Applies the answer to `profile.json`, immediately, with a diff (§5.6).

    A yes becomes `tool_evidence` attached where the author says it belongs; a no
    becomes `not_experienced`, which is what stops the question ever returning.
    Both are durable, which is why an unattended `--no-questions` run still moves
    the run-1 -> run-2 number.
    """

    @node(name="gap_write")
    def gap_write(node_input: GapAnswer) -> dict[str, str]:
        # The `GapAnswer` hint is load-bearing, not decoration: ADK delivers a
        # plain dict even when `RequestInput.response_schema` is set, and it is
        # the parameter annotation that makes FunctionNode coerce it into a
        # model via TypeAdapter (CLAUDE.md).
        asked = sorted({t for tools in result.gap_questions.values() for t in tools})
        answer = (
            node_input
            if isinstance(node_input, GapAnswer)
            else GapAnswer.model_validate(node_input or {"used": []})
        )
        labels = {jd_id: r.label for jd_id, r in result.triage.items()}
        if not asked:
            return labels

        updated, diff = apply_answer(
            result.profile, answer, asked, jd_id="run", today=None
        )
        write_profile(updated)
        result.profile = updated
        result.gap_diff_note = diff

        print("\nprofile updated from gap answers:")
        for line in diff:
            print(line)

        recorder.add(
            "run",
            Step(
                node="gap_write",
                instruction="(deterministic)",
                inputs={"asked": asked},
                output={
                    "confirmed": [u.tool for u in answer.used],
                    "declined": [
                        t for t in asked
                        if t.lower() not in {u.tool.lower() for u in answer.used}
                    ],
                    "diff": diff,
                },
                human_checkpoint={
                    "question": "gap questions",
                    "answer": answer.model_dump(),
                },
            ),
        )
        return labels

    return gap_write


def _tailor_node(
    profile: Profile,
    model: BaseLlm,
    recorder: Recorder,
    result: GraphResult,
    *,
    self_verify: bool,
) -> BaseNode:
    """Writes the packet for `most_matched` postings only (PRD §5.1).

    `less_matched` gets a digest row and `skip` gets a count, so neither is
    tailored -- that routing is the product decision, and it also means the
    fabrication metric is computed over fewer resumes than the baseline's. The
    scorer reports the baseline restricted to the same postings so the
    comparison is not quietly flattered by the ones the pipeline never writes.

    `self_verify` is the whole of `iter3a`: a second turn on the *same* agent,
    with its own draft and its own reasoning still in context, asked to find its
    own fabrications. `iter3b` moves that job to a node that cannot see any of
    it. The pair only means something if this version is genuinely the naive
    one rather than a weaker prompt.
    """
    requirements = load_requirements()
    gate = asyncio.Semaphore(MAX_PARALLEL_TRIAGE)

    @node(name="tailor", rerun_on_resume=True)
    async def tailor(
        ctx: Context, node_input: dict[str, str]
    ) -> AsyncGenerator[Any, None]:
        # Read the profile now, not at construction: `iter4` rewrites it
        # between triage and here, and a stale context would silently drop every
        # gap answer -- making coverage, the number that stage exists to move,
        # look flat for a reason nothing in the output would explain.
        live = result.profile or profile
        context = tailor_agent.tailoring_context(live)
        wanted = [
            jd for jd in result.jds if node_input.get(jd.jd_id) == "most_matched"
        ]

        async def one(jd: JD) -> None:
            async with gate:
                meter = triage_agent.UsageMeter()
                agent = tailor_agent.build_agent(
                    live,
                    model,
                    meter,
                    name=f"tailor_{jd.jd_id}",
                    self_verify=self_verify,
                )
                started = time.monotonic()
                error, retries = None, 0

                async def turn(prompt: str, branch: str) -> tailor_agent.TailoredDocs:
                    """One turn, with a single corrective retry on a parse failure.

                    A no-op whenever the model returns valid JSON, so it does
                    not change a run that had no failures. It exists because a
                    single unparseable reply costs a whole posting: `jd_01` --
                    the only posting in the fixture carrying a fabrication, and
                    therefore the one the self-review stage exists to test --
                    was lost to one non-JSON reply on 2026-08-30.
                    """
                    nonlocal retries
                    reply = await ctx.run_node(
                        agent, node_input=prompt, override_branch=branch
                    )
                    text = reply if isinstance(reply, str) else str(reply)
                    try:
                        return tailor_agent.parse_docs(text)
                    except (ValueError, TypeError):
                        retries += 1
                        again = await ctx.run_node(
                            agent,
                            node_input=(
                                "That reply was not valid JSON. Send the same "
                                "packet again as a single JSON object with the "
                                "keys resume_md, cover_letter_md and "
                                "short_answers_md, and nothing else -- no "
                                "prose, no code fence."
                            ),
                            override_branch=branch,
                        )
                        return tailor_agent.parse_docs(
                            again if isinstance(again, str) else str(again)
                        )
                # One branch per posting, shared by both turns. `use_sub_branch`
                # cannot be used here: it names the branch from the agent name
                # *plus a per-call run_id*, so two turns on the same agent land
                # in different branches and the self-review turn cannot see the
                # draft it is supposed to review -- observed 2026-08-30, when it
                # answered "I don't have the candidate material". An explicit
                # branch keeps the two turns together while still isolating each
                # posting from the others.
                branch = (
                    f"{ctx.branch}.tailor_{jd.jd_id}"
                    if ctx.branch
                    else f"tailor_{jd.jd_id}"
                )
                try:
                    docs = await turn(
                        tailor_agent.tailor_prompt(
                            jd, context, requirements.get(jd.jd_id)
                        ),
                        branch,
                    )
                    result.docs[jd.jd_id] = docs
                    output: Any = {
                        "resume_chars": len(docs.resume_md),
                        "cover_letter_chars": len(docs.cover_letter_md),
                        "short_answers_chars": len(docs.short_answers_md),
                    }
                    if self_verify:
                        output["self_review_notes"] = docs.self_review_notes
                    if docs.ignored_keys:
                        output["ignored_keys"] = docs.ignored_keys
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"[:200]
                    result.errors[jd.jd_id] = error
                    output = None
                elapsed = round(time.monotonic() - started, 3)
                previous = result.usage.get(jd.jd_id, (0, 0, 0.0))
                result.usage[jd.jd_id] = (
                    previous[0] + meter.input_tokens,
                    previous[1] + meter.output_tokens,
                    round(previous[2] + elapsed, 3),
                )
                recorder.add(
                    jd.jd_id,
                    Step(
                        node="tailor",
                        instruction=f"{tailor_agent.INSTRUCTION}.md"
                        + (
                            f" + {tailor_agent.SELF_VERIFY_INSTRUCTION}.md"
                            if self_verify
                            else ""
                        ),
                        inputs={
                            "jd_id": jd.jd_id,
                            "company": jd.company,
                            "context_chars": len(context),
                            "requirements": len(
                                requirements[jd.jd_id].requirements
                            )
                            if jd.jd_id in requirements
                            else 0,
                            "self_verify": self_verify,
                        },
                        output=output,
                        error=error,
                        retries=retries,
                        wall_clock_s=elapsed,
                        input_tokens=meter.input_tokens,
                        output_tokens=meter.output_tokens,
                    ),
                )

        await asyncio.gather(*(one(jd) for jd in wanted))
        recorder.add(
            "run",
            Step(
                node="tailor",
                inputs={"most_matched": len(wanted), "self_verify": self_verify},
                output={"packets_written": len(result.docs)},
            ),
        )
        yield node_input

    return tailor


def _verify_node(
    profile: Profile,
    config: Config,
    model: BaseLlm,
    recorder: Recorder,
    result: GraphResult,
) -> BaseNode:
    """The verifier as its own node, with a bounded revision loop (PRD §5.8).

    What `iter3a` could not have: this node did not write the document, holds
    none of the tailor's context, and reaches its verdict from the profile
    alone. `iter3a` measured what the alternative is worth — a writer reviewing
    its own draft reported *"No fabricated claims"* over a resume claiming a
    Bloom filter it had no evidence for.

    The loop acts on the **union of both verdict paths**. The rules catch
    placement precisely (`classify_claim`); the judge catches fabrications with
    no proper noun in them, which the rules are structurally blind to. The
    consequence is stated in the changelog rather than hidden: the harness
    scorer counts what the rules path rejects, and this node now deletes
    exactly that, so the primary metric at `iter3b` is largely tautological.
    Coverage, softening, and rounds-needed are the numbers that still inform.

    `RetryConfig` cannot drive this -- it retries on raised exceptions only
    (`CLAUDE.md`), and a verdict is not an exception. So it is an explicit loop.
    """
    gate = asyncio.Semaphore(MAX_PARALLEL_TRIAGE)

    def failures_of(report: VerificationReport) -> list[ClaimUnit]:
        """Units either path rejects, in document order."""
        bad = {v.unit_id for v in report.rules if v.status == "unsupported"}
        bad |= {v.unit_id for v in report.judge if v.status == "unsupported"}
        return [u for u in report.units if u.unit_id in bad]

    def reason_for(report: VerificationReport, unit_id: str) -> str:
        for verdicts in (report.rules, report.judge):
            for v in verdicts:
                if v.unit_id == unit_id and v.status == "unsupported":
                    return "; ".join(v.reasons) or "unsupported"
        return "unsupported"

    @node(name="verify", rerun_on_resume=True)
    async def verify_node(
        ctx: Context, node_input: dict[str, str]
    ) -> AsyncGenerator[Any, None]:
        live = result.profile or profile
        context = tailor_agent.tailoring_context(live)

        async def one(jd: JD) -> None:
            docs = result.docs.get(jd.jd_id)
            if docs is None:
                return
            async with gate:
                meter = triage_agent.UsageMeter()
                agent = tailor_agent.build_agent(
                    live, model, meter, name=f"revise_{jd.jd_id}"
                )
                started = time.monotonic()
                rounds, dropped, error = 0, 0, None
                rejections: list[dict] = []
                document = docs.resume_md
                try:
                    # `verify` calls asyncio.run internally (one loop per
                    # document, so the Anthropic client is not abandoned mid-
                    # flight). A thread gives it that loop without nesting one
                    # inside the node's.
                    report = await asyncio.to_thread(
                        verify, document, live,
                        document_name=f"{jd.jd_id}/resume.md",
                        config=config,
                    )
                    while failures_of(report) and rounds < MAX_REVISIONS:
                        bad = failures_of(report)
                        # The feedback that shaped the next step, kept verbatim
                        # so a trajectory shows *why* a revision happened.
                        rejections.append({
                            "round": rounds + 1,
                            "rejected": [
                                {
                                    "text": u.text[:200],
                                    "section": u.section,
                                    "reason": reason_for(report, u.unit_id),
                                }
                                for u in bad
                            ],
                        })
                        reply = await ctx.run_node(
                            agent,
                            node_input=tailor_agent.revision_prompt(
                                jd,
                                context,
                                document,
                                [
                                    (u.text, u.section, reason_for(report, u.unit_id))
                                    for u in bad
                                ],
                            ),
                            use_sub_branch=True,
                        )
                        revised = tailor_agent.parse_docs(
                            reply if isinstance(reply, str) else str(reply)
                        )
                        document = revised.resume_md
                        docs = revised
                        rounds += 1
                        report = await asyncio.to_thread(
                            verify, document, live,
                            document_name=f"{jd.jd_id}/resume.md",
                            config=config,
                        )

                    remaining = failures_of(report)
                    if remaining:
                        # Exhausted. Cut the lines in code and log it -- the
                        # packet must not carry a claim the verifier rejected.
                        document, dropped = strip_units(document, remaining)
                        docs = docs.model_copy(update={"resume_md": document})
                        report = await asyncio.to_thread(
                            verify, document, live,
                            document_name=f"{jd.jd_id}/resume.md",
                            config=config,
                        )

                    result.docs[jd.jd_id] = docs
                    result.reports[jd.jd_id] = report
                    output: Any = {
                        "revision_rounds": rounds,
                        "lines_dropped": dropped,
                        "fabricated_remaining": report.fabricated_claims,
                        "softened": report.softened_claims,
                        "supported": report.supported_claims,
                    }
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"[:200]
                    result.errors[jd.jd_id] = error
                    output = None

                elapsed = round(time.monotonic() - started, 3)
                previous = result.usage.get(jd.jd_id, (0, 0, 0.0))
                result.usage[jd.jd_id] = (
                    previous[0] + meter.input_tokens,
                    previous[1] + meter.output_tokens,
                    round(previous[2] + elapsed, 3),
                )
                result.revisions[jd.jd_id] = (rounds, dropped)
                recorder.add(
                    jd.jd_id,
                    Step(
                        node="verify",
                        instruction="verify.md",
                        inputs={
                            "jd_id": jd.jd_id,
                            "max_revisions": MAX_REVISIONS,
                            "sees_tailor_context": False,
                        },
                        output=output,
                        error=error,
                        tool_calls=rejections,
                        retries=rounds,
                        wall_clock_s=elapsed,
                        input_tokens=meter.input_tokens,
                        output_tokens=meter.output_tokens,
                    ),
                )

        wanted = [
            jd for jd in result.jds if node_input.get(jd.jd_id) == "most_matched"
        ]
        await asyncio.gather(*(one(jd) for jd in wanted))
        revised = sum(1 for r, _ in result.revisions.values() if r)
        exhausted = sum(1 for _, d in result.revisions.values() if d)
        recorder.add(
            "run",
            Step(
                node="verify",
                inputs={"documents": len(wanted), "max_revisions": MAX_REVISIONS},
                output={"needed_revision": revised, "exhausted": exhausted},
            ),
        )
        yield node_input

    return verify_node


def _digest_node(recorder: Recorder, result: GraphResult) -> BaseNode:
    """Deterministic: counts the routes (PRD §5.9)."""

    @node(name="digest")
    def digest(node_input: dict[str, str]) -> dict[str, int]:
        counts = {"most_matched": 0, "less_matched": 0, "skip": 0}
        for label in node_input.values():
            counts[label] = counts.get(label, 0) + 1
        recorder.add(
            "run",
            Step(node="digest", inputs={"labelled": len(node_input)}, output=counts),
        )
        return counts

    return digest


def node_names(workflow: Workflow) -> list[str]:
    """The nodes in the graph, in chain order.

    The check that flag routing is real: a disabled capability has no node
    here at all.
    """
    names: list[str] = []
    for element in workflow.edges[0]:
        name = getattr(element, "name", element)
        if isinstance(name, str) and name not in names:
            names.append(name)
    return names
