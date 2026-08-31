#!/usr/bin/env python
"""ADK 2.0 smoke test -- the gate on every later build step.

PRD 10, Saturday step 2: "Do not proceed until a pause node resumes correctly."
JobPilot's whole pipeline is an ADK 2.0 graph with a parallel triage fan-out and
a human-input pause, so this exercises those primitives in miniature before any
of them carries real work:

    START
      |-> (upper, count, reverse)   fan-out: three plain Python nodes
            |-> JoinNode            barrier: waits for all three
                  |-> compose       formats the join dict into a prompt
                        |-> summarize   the one LLM node (AnthropicLlm)
                              |-> revise_loop  ctx.run_node() bounded at 2
                                    |-> ask_human   leaf pause (RequestInput)
                                          |-> finish   receives the answer

`revise_loop` is here because a verdict-driven retry cannot be expressed with
ADK's `RetryConfig` (it retries on raised exceptions, not on a verdict), so the
verifier -> tailor revision loop (PRD 5.1, max 2) has to be built on
`ctx.run_node()`. Its child is a plain function, so proving the primitive costs
no API calls.

Run it:
    python scripts/adk_smoke_test.py                # scripted answer
    python scripts/adk_smoke_test.py --interactive  # answer on stdin

Costs one small Claude call.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, Protocol

from dotenv import load_dotenv
from google.adk import Agent, Context, Event, Runner, Workflow
from google.adk.apps import App, ResumabilityConfig
from google.adk.events import RequestInput
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.workflow import START, JoinNode, node
from google.genai import types
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobpilot.config import build_model, load_config

APP_NAME = "jobpilot_smoke"
USER_ID = "smoke"
SEED_TEXT = "ships tailored applications"

# An explicit id, not the uuid default: the caller has to quote it back on the
# resume call, and a stable one keeps the assertion below readable.
INTERRUPT_ID = "smoke_approval"

# The real revision loop is capped at 2 (PRD 5.1); mirror it here.
MAX_REVISIONS = 2

# ADK's own name for the interrupt function call. Matching on resume is by id,
# not by name, but the name is what the framework emitted, so echo it.
REQUEST_INPUT_FUNCTION_CALL_NAME = "adk_request_input"


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------


class Summary(BaseModel):
    """What the LLM node must return."""

    headline: str = Field(description="A short headline, at most 8 words.")
    sentiment: str = Field(description="One of: positive, neutral, negative.")


class Approval(BaseModel):
    """What the human must answer at the pause."""

    approved: bool
    note: str = ""


# --------------------------------------------------------------------------
# Observations -- what the assertions at the end are checked against.
# Recorded from inside the nodes, so they are evidence the graph actually ran
# rather than a re-derivation of what it should have done.
# --------------------------------------------------------------------------

observed: dict[str, Any] = {
    "fanout_keys": None,
    "summary": None,
    "revise_attempts": None,
    "final": None,
}


# --------------------------------------------------------------------------
# Fan-out: three plain Python nodes. In `state` parameter binding (the default)
# a parameter named `node_input` receives the upstream value; any other name
# would be looked up in ctx.state instead.
# --------------------------------------------------------------------------


def upper(node_input: str) -> str:
    return node_input.upper()


def count(node_input: str) -> int:
    return len(node_input)


def reverse(node_input: str) -> str:
    return node_input[::-1]


join_node = JoinNode(name="join_results")


def compose(node_input: dict[str, Any]) -> str:
    """Turns the join payload into a prompt.

    A JoinNode hands its successor a dict keyed by *predecessor node name*, not
    a list. Formatting it here rather than feeding the dict straight to the LLM
    node keeps the agent's input a plain string.
    """
    observed["fanout_keys"] = sorted(node_input)
    return (
        "Three functions were applied to a phrase.\n"
        f"uppercase: {node_input['upper']}\n"
        f"length: {node_input['count']}\n"
        f"reversed: {node_input['reverse']}\n"
        "Describe the original phrase."
    )


# --------------------------------------------------------------------------
# The one LLM node.
#
# `output_schema` is NOT sent to Anthropic -- AnthropicLlm never reads
# config.response_schema. ADK validates the returned *text* against the schema
# after the fact, so the JSON contract has to be stated in the instruction or
# the model returns prose and validation throws.
# --------------------------------------------------------------------------

summarize = Agent(
    name="summarize",
    model=build_model(load_config()),
    output_schema=Summary,
    instruction=(
        "You summarize a short phrase.\n"
        "Reply with a single JSON object and nothing else -- no prose, no "
        "explanation, no markdown fence.\n"
        'It must have exactly these keys: "headline" (a string of at most 8 '
        'words) and "sentiment" (exactly one of: positive, neutral, negative).'
    ),
)


# --------------------------------------------------------------------------
# Dynamic node: the ctx.run_node() primitive the verifier -> tailor loop needs.
# --------------------------------------------------------------------------


def check_draft(node_input: int) -> bool:
    """Stand-in for the verifier's verdict. Approves on the second attempt."""
    return node_input >= MAX_REVISIONS


@node(rerun_on_resume=True)
async def revise_loop(
    ctx: Context, node_input: dict[str, Any]
) -> AsyncGenerator[Any, None]:
    """Loops until the child node approves, bounded at MAX_REVISIONS.

    `rerun_on_resume=True` is mandatory for any node that calls
    `ctx.run_node()`: a dynamically scheduled child may interrupt, and the
    framework re-runs the parent so it can collect the child's response. ADK
    raises a ValueError at run time otherwise.
    """
    attempts = 0
    approved = False
    while not approved and attempts < MAX_REVISIONS:
        attempts += 1
        # Awaited directly, never wrapped in asyncio.create_task(): a task
        # would outlive an interrupt and swallow its errors.
        approved = await ctx.run_node(check_draft, node_input=attempts)

    observed["summary"] = node_input
    observed["revise_attempts"] = attempts
    yield {"summary": node_input, "attempts": attempts, "approved": approved}


# --------------------------------------------------------------------------
# The pause, and the node that consumes the answer.
# --------------------------------------------------------------------------


def ask_human(node_input: dict[str, Any]) -> AsyncGenerator[RequestInput, None]:
    """The leaf pause node.

    Left at the default `rerun_on_resume=False`, which means it is never
    re-executed: on resume the user's answer simply *becomes* this node's
    output and flows down the edge as `finish`'s node_input. That is the shape
    JobPilot's gap-question flow needs (PRD 5.1).
    """
    yield RequestInput(
        interrupt_id=INTERRUPT_ID,
        message=(
            f"Draft summary: {node_input['summary']}\n"
            f"Approved after {node_input['attempts']} attempt(s). Accept it?"
        ),
        payload=node_input,
        response_schema=Approval,
    )


def finish(node_input: Approval) -> str:
    """Receives the human's answer.

    ADK delivers a plain dict even when `response_schema` is set; the `Approval`
    type hint is what makes FunctionNode coerce it into a model instance.
    """
    observed["final"] = node_input
    return f"approved={node_input.approved}"


workflow = Workflow(
    name="smoke",
    # A nested tuple inside the chain is the fan-out.
    edges=[
        (
            START,
            (upper, count, reverse),
            join_node,
            compose,
            summarize,
            revise_loop,
            ask_human,
            finish,
        )
    ],
    # Mirrors the triage concurrency cap. Only throttles graph-scheduled nodes;
    # ctx.run_node() children are exempt, since throttling them would deadlock.
    max_concurrency=4,
)


# --------------------------------------------------------------------------
# Answer providers. The pause node never learns which one answered -- a first
# sketch of the stdin / answers.json / always-no abstraction PRD 5.1 needs.
# --------------------------------------------------------------------------


class AnswerProvider(Protocol):
    def answer(self, message: str) -> dict[str, Any]: ...


class ScriptedAnswers:
    """Answers from a fixed table, so the test runs unattended."""

    def __init__(self, reply: dict[str, Any]) -> None:
        self._reply = reply

    def answer(self, message: str) -> dict[str, Any]:
        print(f"\n[pause] {message}")
        print(f"[scripted answer] {self._reply}")
        return self._reply


class StdinAnswers:
    """Answers from the terminal -- the real human path."""

    def answer(self, message: str) -> dict[str, Any]:
        print(f"\n[pause] {message}")
        raw = input("accept? [y/N] ").strip()
        return {"approved": raw.lower().startswith("y"), "note": raw}


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------


def find_interrupt(events: list[Event]) -> Event | None:
    """Finds the paused-run signal.

    `long_running_tool_ids` is the canonical marker -- it is what the node
    runner keys off and what ADK's own CLI scans for.
    """
    for event in events:
        if event.long_running_tool_ids:
            return event
    return None


def interrupt_request(event: Event) -> tuple[str, str]:
    """Pulls (interrupt_id, message) out of the interrupt event."""
    for part in event.content.parts if event.content else []:
        call = part.function_call
        if call and call.name == REQUEST_INPUT_FUNCTION_CALL_NAME:
            return call.id, (call.args or {}).get("message", "")
    raise AssertionError("interrupt event carried no adk_request_input call")


def resume_message(interrupt_id: str, reply: dict[str, Any]) -> types.Content:
    """Builds the function-response that answers the interrupt.

    `response` must be a Mapping. A dict is delivered to the node as-is; a bare
    scalar would have to be wrapped as {"result": value}. Text parts must not be
    mixed in -- ADK rejects a message carrying both.
    """
    return types.Content(
        role="user",
        parts=[
            types.Part(
                function_response=types.FunctionResponse(
                    id=interrupt_id,
                    name=REQUEST_INPUT_FUNCTION_CALL_NAME,
                    response=reply,
                )
            )
        ],
    )


async def run_smoke(provider: AnswerProvider) -> list[str]:
    """Runs the graph, pauses, answers, resumes. Returns failure messages."""
    session_service = InMemorySessionService()
    app = App(
        name=APP_NAME,
        root_agent=workflow,
        # Optional for a Workflow -- pause/resume works without it -- but it
        # persists node status and resume_inputs instead of reconstructing them
        # by replaying events, which is what a durable pause wants.
        resumability_config=ResumabilityConfig(is_resumable=True),
    )
    runner = Runner(app=app, session_service=session_service)
    session = await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID
    )

    print(f"--- run 1: expecting a pause ---\nseed: {SEED_TEXT!r}")
    seed = types.Content(role="user", parts=[types.Part(text=SEED_TEXT)])
    first: list[Event] = []
    async for event in runner.run_async(
        user_id=USER_ID, session_id=session.id, new_message=seed
    ):
        first.append(event)

    interrupt = find_interrupt(first)
    failures: list[str] = []

    if interrupt is None:
        failures.append("run 1 never paused: no event carried long_running_tool_ids")
        return failures

    interrupt_id, message = interrupt_request(interrupt)
    reply = provider.answer(message)

    print("\n--- run 2: resuming ---")
    async for _ in runner.run_async(
        user_id=USER_ID,
        session_id=session.id,
        # Reconciled, not trusted: a wrong id means the response is dropped.
        invocation_id=interrupt.invocation_id,
        new_message=resume_message(interrupt_id, reply),
    ):
        pass

    return failures


def check(failures: list[str], ok: bool, label: str, detail: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {label}" + (f" -- {detail}" if detail else ""))
    if not ok:
        failures.append(label)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="answer the pause on stdin instead of from the scripted table",
    )
    args = parser.parse_args()

    load_dotenv()  # ADK only auto-loads .env under `adk run`.

    expected: dict[str, Any] = {"approved": True, "note": "looks right"}
    provider: AnswerProvider = (
        StdinAnswers() if args.interactive else ScriptedAnswers(expected)
    )

    failures = asyncio.run(run_smoke(provider))

    print("\n--- results ---")
    check(
        failures,
        observed["fanout_keys"] == ["count", "reverse", "upper"],
        "fan-out + join: all three predecessors reached the barrier",
        json.dumps(observed["fanout_keys"]),
    )

    summary = observed["summary"]
    llm_ok = False
    if isinstance(summary, dict) and "summary" not in summary:
        try:
            Summary.model_validate(summary)
            llm_ok = True
        except Exception as exc:
            print(f"       schema error: {exc}")
    check(
        failures,
        llm_ok,
        "LLM node: Claude returned schema-valid structured output",
        json.dumps(summary) if summary is not None else "no output",
    )

    check(
        failures,
        observed["revise_attempts"] == MAX_REVISIONS,
        "dynamic node: ctx.run_node() loop ran to its verdict",
        f"attempts={observed['revise_attempts']}",
    )

    final = observed["final"]
    check(
        failures,
        isinstance(final, Approval),
        "pause + resume: the answer reached the node past the pause",
        type(final).__name__,
    )
    if isinstance(final, Approval) and not args.interactive:
        check(
            failures,
            final.approved == expected["approved"] and final.note == expected["note"],
            "pause + resume: the answer arrived unchanged",
            final.model_dump_json(),
        )

    if failures:
        print(f"\nFAILED ({len(failures)}): " + "; ".join(failures))
        return 1
    print("\nAll checks passed. ADK 2.0 pause/resume is sound; step 2 is cleared.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
