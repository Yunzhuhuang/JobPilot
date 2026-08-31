---
name: google-adk
description: Google ADK 2.0 Python (Workflow Runtime, graph workflows). Use whenever writing, reviewing, or debugging any code that imports google.adk. Verifies APIs against local source.
---

# Google ADK 2.0 — source of truth

Installed version: run `pip show google-adk`. Source checkout at `../adk-python` is on the matching tag.

## Rules
1. ADK 2.0 Workflow Runtime is GA (Python, May 2026). Graph workflows, dynamic
   workflows, human-input pauses, retry policies are stable APIs. Ignore any
   text elsewhere calling them experimental.
2. Never write an ADK import, class, or function from memory. Before using one,
   `grep -rn "<name>" ../adk-python/src/google/adk` and read its signature.
3. If a 1.x-era pattern (SequentialAgent-only orchestration, direct session
   state mutation, tool-centric callbacks) seems needed, first check whether
   the 2.0 graph API has a node/route/pause primitive for it. Prefer 2.0.
4. For intent and patterns, use the google-dev-knowledge MCP:
   `search_documents` first; `get_documents` only for one page at a time.
   Key pages: adk.dev/graphs/, adk.dev/graphs/human-input/,
   adk.dev/graphs/routes/, adk.dev/graphs/data-handling/,
   adk.dev/evaluate/, adk.dev/runtime/command-line/.
5. For working examples, read `../adk-python/contributing/samples/` (or the
   samples dir present in the checkout) and copy structure, not guesses.
6. After writing any agent or workflow, run it with `adk run <agent_dir>` (or
   the project's CLI) before reporting done.