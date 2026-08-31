# Conventions

## Environment
- Project venv only: `.venv` in the repo root (never `~/.venv`). Python 3.11+.
- `google-adk` pinned to the installed 2.x version in `requirements.txt` (currently 2.8.0). One model for baseline and every stage, set once in `config.yaml`.
- ADK source of truth: `../adk-python` checked out at the tag matching `pip show google-adk`. If the clone is missing, `.venv/lib/python*/site-packages/google/adk/` is the fallback for signatures (no samples there).
- Secrets via env vars only. `.env` and `.mcp.json` are gitignored; `.env.example` and `.mcp.json.example` are committed with placeholders.
- Skills in effect: `google-adk` (project, hand-written), `google-agents-cli-eval`, `google-agents-cli-adk-code` (project). No user-level ADK skills. Do not install `scaffold`/`deploy`/`workflow`.
- Local only. No cloud deployment, no web UI. TeX (`xelatex`) is optional and only used by the PDF render node.

## ADK 2.0 specifics learned from source (2.8.0)
- Pause = `RequestInput` yielded from a generator node in the graph. `response_schema` **does** exist (corrected 2026-08-30 against 2.8.0 source and a passing run — the earlier "no `response_schema`" note was wrong): fields are `interrupt_id`, `payload`, `message`, `response_schema`, and the schema is enforced on resume (a bad answer raises `ValueError` out of `run_async`). It still delivers a plain `dict`, so the consuming node's parameter needs a Pydantic type hint to get a model instance — `FunctionNode` coerces via `TypeAdapter`.
- Resume = `runner.run_async(new_message=Content(role="user", parts=[Part(function_response=FunctionResponse(id=<interrupt_id>, name="adk_request_input", response=<dict>))]), invocation_id=<interrupt event's>)`. Find the interrupt via `event.long_running_tool_ids`. `response` must be a Mapping; never mix text and function-response parts.
- Any node that calls `ctx.run_node()` must be `@node(rerun_on_resume=True)`; the leaf pause node stays `rerun_on_resume=False`.
- Never wrap `ctx.run_node()` in `asyncio.create_task()` — errors are swallowed and the task outlives an interrupt.
- **Concurrent `ctx.run_node()` needs `use_sub_branch=True`** (learned 2026-08-30, the hard way). Without it every dynamically-run child writes its events onto the *parent's* branch, so concurrent children see each other's history. A single-turn agent (triage) survives this; a **tool-using** agent does not — ADK logs `Dropping function responses with no matching function call` and the answers cross between items. Observed: SpaceX came back as `COHERE US, INC.`, then as `MERCOR IO CORPORATION`, each with the other posting's rationale attached, having run four other postings' tool searches. Unique agent `name=` does **not** fix it; the shared branch is the state that leaks. The flag is documented in `agents/context.py` `run_node`.
- **Accumulate `usage`, never overwrite it.** With two agent nodes per item, the second node's usage assignment silently replaced the first's, and cost/JD reported one agent's spend for a two-agent stage ($0.0244 where the truth was $0.0501). Any per-item usage record must be `+=`.
- **A second `ctx.run_node` turn does NOT see the first turn's output.** ADK scopes an agent's conversation to its own run, and neither `use_sub_branch=True` nor a shared explicit `override_branch` changes that — both were tried on 2026-08-30 and both failed the same way: the second turn answered "the candidate material was not included in this conversation" and emitted that apology *as the resume*, which then scores as a document with no fabrications and no content. A silently poisoned metric, not a crash. **If a node needs draft-then-critique, do it in one completion** (append the critique section to the instruction) or pass the prior output explicitly in the next prompt. `use_sub_branch=True` remains correct and necessary for *isolating concurrent* children from each other — that is a different problem, and it is the one it solves.
- **Do not let `extra="forbid"` discard a whole LLM result.** The convention is right for persisted artifacts and schemas, but a model volunteering one chatty extra key beside three valid documents is not a broken contract, and rejecting the packet loses real generated work. Validate the known fields, keep the required ones strict, and *record* what was dropped (`TailoredDocs.ignored_keys`) rather than silently ignoring it.
- The answer provider (stdin / `answers.json` / always-no) is app-level: one abstraction that resolves the `RequestInput` interrupt from the chosen source. The pause node never knows which provider answered.
- `RetryConfig` on `@node` **cannot** drive verdict-based retries (resolved 2026-08-30): it retries on raised exceptions only. So the verifier→tailor revision loop (max 2) is an explicit loop in a node that calls `ctx.run_node()` — proven in `scripts/adk_smoke_test.py`.
- `output_schema` on an agent is **not sent to Anthropic**; ADK validates the returned text after the fact. Every LLM node must state its JSON contract in the instruction ("reply with a single JSON object and nothing else, keys: …") or validation throws on prose.
- A `Workflow` goes into `Runner` as `node=` (or `App(root_agent=…)`), never `agent=`. Sessions are not auto-created — call `create_session` first. A `JoinNode` hands its successor a **dict keyed by predecessor node name**, not a list.
- Verify every `google.adk` symbol against source before use (see `CLAUDE.md`). Docs-only claims are not implementation-ready.

## Layout

## Layout
```
jobpilot/
  profile/      schema (Pydantic), loader, validate, onboarding + update agent
  ingest/       Ingester interface, LinkListIngester, cache
  h1b/          USCIS normalize + lookup (no LLM)
  agents/       one file per node; instructions as .md in agents/instructions/
  workflow.py   the ADK 2.0 graph; every node flag-routed by the stage preset
  render/       latex.py — verified resume.md → templates/resume.tex → xelatex
  eval/         scorers, stage preset loader, --all-stages, compare.md
  baseline/     run_baseline.py (one prompt, same model/fixture/output layout)
  cli.py
fixture/        links.txt, cache/, labels.json, requirements/, answers.json, profile.json (frozen)
eval/stages/    baseline.yaml, iter1.yaml … final.yaml
templates/      resume.tex (PRE-EXISTING — label in README)
scripts/        extract_requirements.py, refresh_h1b.py
output/<stage>/<date>/   digest.md, packets/<jd_id>/
eval/results/<stage>/    summary.json, summary.md, per_jd.md
trajectories/   one representative trajectory.json per agent node
```

## Code
- Pydantic model for every LLM output, validated on parse; log parse failures, never coerce silently.
- Deterministic steps (ingest, H-1B lookup, requirement scoring, render, digest) are plain Python — no LLM.
- Agent instructions are loaded from `.md` files at runtime; they are a deliverable, keep them readable.
- Every node appends to `trajectory.json`: instruction ref, inputs, tool calls + responses, output, retries, human checkpoints with the user's answer.
- Profile writes: only the onboarding agent, gap-question confirmation, and the update agent; each shows a diff and requires confirmation. `render` runs only on verified text.
- **Claims are verified by placement, not just membership.** `jobpilot.profile.classify_claim(profile, tool, container_id)` is the single predicate; the verifier node, the harness scorer, and `validate_profile` all call it. Statuses: `supported` · `unplaced` (evidence is `where: self_study`, so the tool may appear in a skills section but **not** inside an experience/project bullet until a gap answer supplies a real location) · `misplaced` (evidence points at a different role/project) · `declined` · `unsupported`. Only `supported` may reach a rendered document; the rest are `unsupported` in the report, and the status says whether a gap question would repair it. Rationale: a bullet can be built entirely from profile tools and still be false — "configured Kafka pipelines at Amazon" invents the *attachment*, which is the exact overstatement the product exists to prevent. Because `ToolEvidence.where` holds one id, a tool used in several places is sanctioned by the container's own `tools` list.
- Type hints everywhere, `ruff` clean, no leftover prints. Comments explain why, not what.

## Working method
- Measurement first: no agent feature before `eval --stage baseline` has a result and a `CHANGELOG.md` row.
- Per feature: flip the preset flag → build → run it → `eval --stage <name>` → append `CHANGELOG.md` row (Stage / What you tried and why / Evidence path + number / Decision) → next.
- One Claude Code session per iteration. At session start read `CLAUDE.md`, PRD §1–3 and §10, then the PRD section for the feature at hand.
- Every number in README/CHANGELOG is emitted by `jobpilot.eval` into `eval/results/`. Never hand-type a metric.
- **Two labelling rules the author applied to `fixture/labels.json` (2026-08-30). The triage instruction must state both, or agreement measures a disagreement about the rules rather than about the jobs.** (1) *Job title does not decide the label* — any software-engineering-adjacent role whose requirements match the profile can be `most_matched`; `jd_12` "Product Support Engineer" is labelled `most_matched` for this reason. (2) *A posting is `skip` if it explicitly rules out sponsorship, requires a security clearance, or requires US citizenship / ITAR-EAR eligibility* — this is why `jd_06` (SpaceX, ITAR + Top Secret) and `jd_14` (Mach, "without sponsorship for an export license") are `skip`. EEO boilerplate ("regardless of … citizenship status") is not such a requirement and must not trigger it.
- `profile.json` is the author's real profile at public-resume level: no phone, street address, or ID numbers.
- README labels pre-existing material (LaTeX template, prior resume text, style exemplars) vs. what was built.

## If behind on Sunday night
Cut in this order: `iter5` → short answers → profile update agent → H-1B fuzzy match (exact only) → PDF polish. Never cut: verifier node, eval harness, stage presets, non-interactive mode, changelog evidence, trajectories, onboarding agent.