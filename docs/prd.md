# PRD — JobPilot: Multi-Agent Job Application Workflow (ADK 2.0)

**Event:** micro1 Agentic Workflows Hackathon
**Hard deadline:** Monday 2026-08-31, 18:00 UTC (11:00 PT)
**Framework:** Google ADK Python 2.x (Workflow Runtime, GA since 2026-05-19). Python 3.11+.
**Companion files:** `CLAUDE.md` (working rules), `CONTRIBUTING.md` (conventions), `SETUP.md` (Claude Code MCP/skills setup)
**Status:** v1 (hackathon). First release of a tool the author will keep using and extending.

Written for a coding agent. **MUST** = hard requirement. "Roadmap" = out of scope — do not build.

**Method (read first):** the project is built as an ablation. Phase 0 builds the fixture, ground truth, evaluation harness, stage presets, and baseline — and produces the first eval result — **before any agent feature exists**. Every later feature is an *iteration* with its own stage preset; it is complete only when `jobpilot.eval --stage <name>` has written `eval/results/<name>/` and a row exists in `CHANGELOG.md`. Features are never built ahead of their measurement.

---



## 1. Problem and user

**User:** a new-grad software engineer (the author) applying to 30–40 roles per day who needs H-1B sponsorship.

**Bottleneck today (manual):**

- Reading each JD and judging fit: ~3 min per posting.
- For strong matches, tailoring a resume, writing a cover letter, and answering application questions: ~30 min per application.
- Under time pressure the author sometimes overstates experience or, more often, forgets tools they actually used that the JD asks for, because that information isn't written down anywhere.
- Sponsorship eligibility is checked ad hoc; time is wasted on companies that don't sponsor.

**Why it matters:** ~80 tailored applications done by hand in two months. Every hour saved goes back into interview prep; every fabricated claim avoided is a rejection (or worse) avoided.

**Success for the user:** a daily digest splitting postings into two lists, with a ready-to-review application packet for each strong match, containing zero unsupported claims, produced in minutes instead of hours — and reading like something the author wrote, not an AI draft.

---



## 2. Scope



### 2.1 In scope (MUST ship)

**Phase 0 — measurement first**

1. **Fixture + ground truth** — `links.txt`, committed JD cache, author labels, cached requirements, recorded gap answers, frozen profile (§4.2).
2. **Evaluation harness** — `jobpilot.eval` with all §7.1 metrics, driven by **stage presets** (§7.2). Runs offline.
3. **Baseline** — single-prompt implementation of the same task (§6). First eval result: `eval/results/baseline/`.
4. **Profile schema** — `profile.json` Pydantic models and loader (§4.1).
5. **ADK 2.0 smoke test** — a hello-world graph with one LLM node, one parallel fan-out, and one human-input pause node, run end to end. De-risks Sunday.

**Phase 1+ — features as iterations** (each gated by a stage preset + eval run + changelog row)
6. **JD ingestion (links in, cache-first)** — input is a list of job URLs; the `Ingester` fetches, extracts, caches. Built in Phase 0 as infrastructure (the harness needs JDs) but is a real feature of the product.
7. **H-1B filter** — deterministic local lookup against USCIS H-1B Employer Data Hub data. Opt-in/out.
8. **Triage agent** — `most_matched` | `less_matched` | `skip`. Skipped JDs are counted in the digest header, not listed.
9. **Tailoring agent** — for `most_matched` only: resume, cover letter, short-answer drafts for the application's required open-ended questions. Uses the author's style exemplars (§5.7). Includes the **gap-question flow** (§5.6) as a human-input pause.
10. **Verification agent** — separate node; rejects any claim not supported by `profile.json`.
11. **Profile memory** — conversational onboarding agent, conversational `profile update` agent, gap-question write-back, `profile validate`.
12. **Daily digest** — markdown file plus a packet folder per most-matched JD, each with `resume.md` **and** `resume.pdf` rendered through the author's pre-existing LaTeX template.
13. **Non-interactive mode** for reproducibility.
14. **Deliverables** (§9).

### 2.2 Roadmap (DO NOT BUILD — README "Future work")

Live 24h discovery scraper (drops into the `Ingester` interface) and LinkedIn/Workday/Indeed support · scheduled morning run · alumni/referral recommendations · weekly outcome tracking via inbox · weekly skills-trend report with learning suggestions · auto-fill/submission · profile memory migration to ADK memory service · scheduled monthly H-1B refresh (v1 ships the script, run manually).

### 2.3 Non-goals

- No web UI. CLI only.
- No cloud deployment. Runs locally from a clean environment.
- No live network calls at eval time other than the LLM API.

---



## 3. Ground rules that constrain implementation (from the brief)

- **Pre-existing vs. new (rule 02):** the author's LaTeX resume template (`templates/resume.tex`, used by the PDF renderer), prior resume text, and the two or three approved bullets/paragraphs used as style exemplars existed before the hackathon; README MUST label them. All agent code, harness, fixture, verifier, and instructions are new.
- **Human approval (rules 04, 05):** the system never submits an application. Output is always a packet for human review. Gap answers require explicit confirmation before entering the profile.
- **Credentials (rule 08):** LLM API key via env var only. `.env` gitignored; `.env.example` provided. If `.mcp.json` contains a key, it is gitignored and `.mcp.json.example` is committed.
- **Data (rules 06, 07):** fixture JDs are public postings fetched from boards that permit simple GETs (Greenhouse, Lever, Ashby); no LinkedIn/Workday. USCIS data is public. `profile.json` is the author's **real** profile (public-resume-level information only: no phone number, no street address, no ID numbers; email may be a public contact address). README states this.
- **License/terms (rule 03):** only fetch boards whose terms allow it; record the board and fetch date in each cache entry.
- **Reproducibility (rules 09, 10):** evaluation runs offline against the committed cache; every stage in the changelog is re-runnable from its preset; every README number ties to a file in `eval/results/`. Judges need their own LLM API key — stated in REPRODUCE.md with approximate cost.

---



## 4. Data contracts



### 4.1 `profile.json` (MUST match)

```json
{
  "schema_version": 1,
  "identity": { "name": "", "email": "", "location": "", "linkedin": "", "github": null, "open_to_relocation": true },
  "constraints": { "needs_sponsorship": true, "target_roles": [""], "excluded_locations": [""], "earliest_start": "YYYY-MM" },
  "education": [ { "id": "edu_1", "school": "", "degree": "", "field": "", "start": "YYYY-MM", "end": "YYYY-MM", "gpa": null, "coursework": [""] } ],
  "experience": [ {
      "id": "exp_1", "company": "", "title": "", "start": "YYYY-MM", "end": null,
      "bullets": [ { "id": "exp_1_b1", "text": "one achievement, numbers where true", "tools": [""] } ],
      "tools": ["union of bullet tools plus anything else used here"]
  } ],
  "projects": [ { "id": "proj_1", "name": "", "one_liner": "", "bullets": [ { "id": "proj_1_b1", "text": "", "tools": [""] } ], "tools": [""], "link": null } ],
  "skills": { "languages": [], "frameworks": [], "cloud_infra": [], "data": [], "ai_ml": [], "testing": [], "other": [] },
  "tool_evidence": [ { "tool": "canonical name", "aliases": [""], "where": "exp_1|proj_1|edu_1|self_study", "evidence": "one sentence in the user's words", "source": "onboarding|gap_question|manual_update", "added_at": "YYYY-MM-DD" } ],
  "not_experienced": [ { "tool": "", "asked_at": "YYYY-MM-DD", "context_jd": "jd_id" } ],
  "style_exemplars": [ { "kind": "resume_bullet|cover_letter_paragraph", "text": "", "provenance": "pre-hackathon" } ],
  "writing_preferences": { "resume_max_pages": 1, "no_single_bullet_projects": true, "voice": "first person, concrete, numbers-backed, no generic adjectives", "flag_gaps_instead_of_fabricating": true }
}
```

**Rules**

- A tool is claimable only if it appears in `tool_evidence` (canonical) or in a bullet's `tools`. That is the verifier's whitelist.
- `not_experienced` is a do-not-ask-again, do-not-claim list.
- `style_exemplars` are 2–3 short pieces of the author's own approved writing, used only to steer voice; the verifier still checks every fact in them like any other text.
- Exactly three writers: onboarding agent, gap-question confirmation, `profile update` agent. Every write shows a diff and requires confirmation. `profile validate` is read-only.
- `fixture/profile.json` is a **frozen copy** used by the harness so that iterations that mutate the working profile are still scored against a fixed starting point.



### 4.2 JD fixture and ground truth

`fixture/links.txt` — one job URL per line (**12–20** links from Greenhouse/Lever/Ashby boards). This is what the user maintains day to day.

`fixture/cache/<jd_id>.md` — committed fetch results: YAML front matter (`jd_id, source_url, url_hash, board, company, title, location, fetched_at`) + extracted JD text. Optional `## Application questions` section (author-added). `jd_id` is stable (`jd_<nn>`); cache key is a hash of the normalized URL.

`fixture/labels.json` — author's ground truth: `{ "jd_01": "most_matched" | "less_matched" | "skip", ... }`.

`fixture/requirements/<jd_id>.json` — requirements extracted once per JD by the fixed extractor (§7.1).

`fixture/answers.json` — recorded gap-question answers keyed by `(jd_id, tool)`.

`fixture/profile.json` — frozen profile snapshot for scoring.

**MUST include:** hard case A (JD requiring a stack the user lacks — tests fabrication + verifier), hard case B (company whose USCIS name differs from the posting name — tests fuzzy match), one known non-sponsor or unlisted employer, one `skip`-labeled JD.

### 4.3 H-1B data

- Source: USCIS H-1B Employer Data Hub CSV, two most recent fiscal years.
- `scripts/refresh_h1b.py` downloads and normalizes to `data/h1b_employers.csv`: `employer_name_normalized, employer_name_raw, fiscal_year, initial_approvals, initial_denials, continuing_approvals, state`.
- Ship `data/h1b_employers_sample.csv` covering every fixture company.
- Lookup (pure Python): normalize (lowercase; strip punctuation and inc/llc/corp/co/ltd) → exact → fuzzy (`rapidfuzz` token-set ≥ 90). Returns `{sponsors, confidence: exact|fuzzy|none, matched_name, approvals_last_2y}`. `sponsors = approvals_last_2y >= 1`. Fuzzy matches flagged in the digest.



### 4.4 Outputs

`output/<stage>/<YYYY-MM-DD>/digest.md`: header (ingested, H-1B filter state, dropped non-sponsors, skipped), **Most matched** table (JD, company, title, why, H-1B, packet link), **Less matched** table, gap-question summary.

`output/<stage>/<date>/packets/<jd_id>/`: `resume.md`, `resume.pdf`, `cover_letter.md`, `short_answers.md`, `verification_report.json`, `trajectory.json`.

**PDF rendering:** `jobpilot/render/latex.py` maps the verified `resume.md` structure into `templates/resume.tex` (pre-existing) and compiles with `xelatex`. Rendering happens **after** verification so the PDF never contains an unverified line. If `xelatex` is absent, the run logs a warning and still produces `resume.md`; REPRODUCE.md lists TeX as an optional dependency and states that all metrics are computed on `resume.md`.

---



## 5. Agent design (ADK 2.0 graph)

The pipeline is a **2.0 workflow graph** with explicit routes. Agents, tools, and functions are nodes. Structured results pass between nodes as workflow data. Verify every ADK API against `../adk-python` source before use (see `CLAUDE.md`).

**Every node is feature-flagged** by the stage preset (§7.2). When a flag is off, the graph routes around that node. This makes each changelog row reproducible and is a first-class design requirement.

### 5.1 Graph shape

```
ingest ──> h1b_filter? ──> [triage × N in parallel] ──> join
   ──> route: most_matched ──> gap_diff? ──> (pause: gap_questions)? ──> profile_write? ──> tailor ──> verify? ──(retry ≤2)──> packet
       route: less_matched ──> digest row
       route: skip        ──> digest count only
   ──> digest
```

`?` = flag-controlled node.

- Triage nodes run in parallel across JDs with a concurrency cap.
- Gap questions are a **human-input pause node**. Answer provider is injected: stdin (interactive), `answers.json`, or `always-no` (`--no-questions`). One code path.
- Verify → tailor revision uses a **retry policy** (max 2). On exhaustion, drop unsupported lines and log.
- Every node appends to `trajectory.json`: instruction ref, inputs, tool calls + responses, output, retries, human checkpoints with the user's answer.



### 5.2 Onboarding agent (`profile init`)

Conversational `LlmAgent` node with `read_profile` / `propose_profile` / `write_profile` tools. Flow: ask for a resume file (`.pdf/.docx/.md/.tex`) → parse into the schema (every bullet gets `tools`; every tool gets a `tool_evidence` entry with `source: onboarding`) → ask, in conversation, the things a resume can't answer (sponsorship, relocation, target roles, excluded locations, earliest start, 2–3 style exemplars) → show the full proposed profile → confirm → write → `validate`. The agent may ask follow-ups when a bullet has no identifiable tools. Non-interactive variant for tests: `--answers profile/onboarding_answers.json`.

### 5.3 Profile update agent (`profile update`)

Same agent in edit mode: user states a change in natural language (add a project, add a tool to a role with evidence, change constraints, remove something) → agent proposes a JSON diff → confirm → write → `validate`. `profile validate` (read-only) checks the schema, that every bullet tool appears in `tool_evidence` or bullet `tools`, and that no `not_experienced` tool is claimed.

### 5.4 Ingestion

Plain Python, no LLM. `Ingester.fetch() -> list[JD]`. v1: `LinkListIngester`:

1. Read `links.txt`; normalize URL; compute `url_hash`.
2. Cache hit → load. Cache miss → if `--offline`, fail loudly; else `httpx` GET, extract main text (`trafilatura`), derive `company/title/location` from title/URL/structured data, write cache entry.
3. `--refresh` re-fetches all. `run` defaults online; `eval`/`baseline` default `--offline`.

Boards: Greenhouse, Lever, Ashby. Others rejected with a clear message.

### 5.5 Triage node

Input: one JD + compact profile summary. Output, Pydantic-validated: `{ jd_id, label: most_matched|less_matched|skip, score, reasons[], missing_requirements[] }`. Rubric: `most_matched` = meets required stack and level, domain overlaps targets, worth 30+ min of customization; `less_matched` = generic application only; `skip` = wrong level/domain or hard constraint violated. Triage does **not** extract requirements (§7.1 does).

### 5.6 Gap diff + gap questions (most_matched only)

1. Diff cached requirements (tool/skill) against the profile whitelist and `not_experienced`, with alias matching. Buckets: `covered`, `declined`, `unknown`.
2. If `unknown` non-empty, pause with **one batched question** per JD. Default no.
3. Yes → `tool_evidence` (`source: gap_question`) attached to the named role/project. No → `not_experienced`. Write immediately, show diff.
4. Never guess. Never re-ask a `not_experienced` tool.



### 5.7 Tailoring node

Generates resume, cover letter, short answers from the **updated** profile + JD. Instruction includes `writing_preferences` and `style_exemplars` (few-shot voice steering — this is the main lever for the End-to-End Quality criterion). Default short answers: "Why this company?", "Project you're proud of", plus `## Application questions`. Hands off to verify.

### 5.8 Verification node

Separate LLM node, own instruction, **no access to the tailoring node's context**. Input: generated docs + full `profile.json`. Per sentence/bullet: `{ text, status: supported|unsupported|softened, evidence_ids }`. Any tool, company, title, metric, date, or technology not mapping to a profile ID is `unsupported`; a number not in the profile is a new fact. Also enforces `writing_preferences`. Emits `verification_report.json`.

The same verifier module, run against the **frozen** `fixture/profile.json`, is the harness's fabrication scorer. Pipeline verifier and scorer share code, never a run.

### 5.9 Render + digest nodes

Plain Python. `render` compiles `resume.pdf` from the verified `resume.md` via the LaTeX template (§4.4). `digest` assembles `digest.md` and packet folders.

---



## 6. Baseline (MUST be fair)

`baseline/run_baseline.py`: per JD, one LLM call, same model, with the raw pre-hackathon resume text and the JD, asked to (a) label strong / weak / no match with reasons and (b) produce a tailored resume and cover letter. No profile schema, no H-1B lookup, no gap questions, no verifier, no exemplars. Same fixture, same output layout (`output/baseline/...`).

README states the resource difference: baseline sees the raw resume; agent sees `profile.json` (built from that resume plus user-confirmed gap answers and style exemplars).

---



## 7. Evaluation



### 7.1 Metrics and scorers (built in Phase 0)

`python -m jobpilot.eval --stage <name>` — always offline; scores against frozen `fixture/profile.json`.

**Primary metric:** fabricated (unsupported) claims per generated resume. Target 0 at `final`.


| Metric                                                                | Scorer                                                                   |
| --------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| Fabricated claims per resume (primary)                                | verifier vs. frozen profile                                              |
| Triage agreement with author labels (%)                               | exact match vs. `labels.json`                                            |
| JD keyword coverage in resume (%)                                     | required items from `fixture/requirements/` present (canonical or alias) |
| Non-sponsors dropped (count)                                          | H-1B lookup vs. fixture ground truth                                     |
| Gap questions asked, run 1 → run 2                                    | pipeline log, two consecutive runs                                       |
| Human review time per most-matched packet (min, author-measured, n=3) | manual                                                                   |
| Cost per JD (USD)                                                     | token usage                                                              |
| Wall-clock per JD (s)                                                 | harness timer                                                            |


**Fixed requirement extractor:** one LLM call per JD with a fixed prompt, run once, cached to `fixture/requirements/<jd_id>.json` (`name, type, required, aliases`). Never re-run during stage evals.

Per-stage outputs: `summary.json`, `summary.md`, `per_jd.md` (every case incl. failures). `eval/results/compare.md` regenerated from all stages → source for the README changelog and final table.

### 7.2 Stage presets

`eval/stages/<name>.yaml` — flags consumed by the graph and CLI:

```yaml
name: iter3b
description: separate verifier node
flags: { profile_context: true, h1b_filter: true, self_verify: false, verifier_node: true, gap_memory: false, style_exemplars: false }
```


| Stage      | Adds                                   | Capability           | Expected signal                                                            |
| ---------- | -------------------------------------- | -------------------- | -------------------------------------------------------------------------- |
| `baseline` | one prompt, raw resume                 | —                    | starting point                                                             |
| `iter1`    | `profile.json` context + triage rubric | context              | triage agreement ↑                                                         |
| `iter2`    | H-1B tool + filter                     | tools                | non-sponsors dropped                                                       |
| `iter3a`   | tailor self-verifies in own context    | verification (naive) | fabrications barely move → **removed**                                     |
| `iter3b`   | separate verifier node                 | verification         | fabrications → 0; coverage may ↓                                           |
| `iter4`    | gap questions → profile write-back     | memory               | coverage recovers; questions run1→run2 ↓                                   |
| `iter5`    | style exemplars in tailor instruction  | skill                | author-scored "would I sign this" (1–5) on 3 packets; note if unmeasurable |
| `final`    | iter1 + 2 + 3b + 4 + 5                 | —                    | final vs. baseline                                                         |


Presets exist from Phase 0; a flag for an unbuilt node fails loudly by design.

### 7.3 Iteration protocol (every feature)

1. Flip the flag in the stage preset. 2. Build the node. 3. `jobpilot.eval --stage <name>`. 4. Append a `CHANGELOG.md` row: Stage · What you tried and why (failure observed in previous stage) · Evidence (`eval/results/<name>/summary.json` + the number that moved) · Decision (kept / revised / removed) and next step. 5. Only then start the next feature.

---



## 8. CLI

```
python -m jobpilot profile init                          # conversational onboarding agent
python -m jobpilot profile update                        # conversational edit agent
python -m jobpilot profile validate
python -m jobpilot profile show
python -m jobpilot run --links fixture/links.txt --stage final                             # interactive, fetches cache misses
python -m jobpilot run --links fixture/links.txt --stage final --answers fixture/answers.json --offline
python -m jobpilot run --links fixture/links.txt --stage final --no-questions --offline
python -m jobpilot run --links fixture/links.txt --refresh
python -m jobpilot.baseline --links fixture/links.txt --offline
python -m jobpilot.eval --stage baseline | iter1 | ... | final
python -m jobpilot.eval --all-stages                                                       # regenerates compare.md
python scripts/extract_requirements.py --fixture fixture/
python scripts/refresh_h1b.py --years 2025,2026
```

`--stage` defaults to `final`. `--h1b-filter on|off` defaults on. Model in `config.yaml`, single default for all stages. API key from env.

---



## 9. Deliverables (map to brief §"Final deliverables")

1. **Repo +** `README.md`**:** intended user + bottleneck + why it matters; ASCII graph with flagged nodes; pre-existing vs. built; **Improvement Changelog** (Stage / What you tried and why / Evidence / Decision) from `CHANGELOG.md` + `compare.md`, including removed `iter3a`; final metrics table (primary outcome, human time, cost); the two hard cases and what they revealed; main failure mode; hot take; Future work. Agent instructions are in `jobpilot/agents/instructions/*.md` and linked.
2. `REPRODUCE.md`**:** clean-environment steps (Python version, `pip install -r requirements.txt`, API key env var + approximate cost), exact commands for baseline, each stage, `--all-stages`, `final` run; required data (all committed); expected output; versions (`google-adk`, model); approximate runtime.
3. **Video ≤ 5 min:** problem → baseline → one real `final` run start to finish (gap question answered live) → final table → changelog: largest contributor + removed `iter3a`.
4. `trajectories/`**:** one representative `trajectory.json` per agent node (onboarding agent incl. a follow-up question, profile update agent incl. a diff + confirmation, triage, tailor incl. gap pause + answer, verifier incl. a rejection + revision), each readable from instruction → tool calls → responses → result.

---



## 10. Build order (strict)

**Saturday — Phase 0**

1. Repo skeleton, `config.yaml`, `.env.example`, `requirements.txt`, `CHANGELOG.md` header.
2. **ADK 2.0 smoke test** (§2.1 item 5). Do not proceed until a pause node resumes correctly.
3. Profile Pydantic models; author hand-writes `profile.json` for now (+ 2–3 style exemplars) so Phase 0 isn't blocked on the onboarding agent; freeze copy to `fixture/profile.json`.
4. `links.txt` (12–20 links incl. hard cases A, B, non-sponsor, skip) → `LinkListIngester` → commit `fixture/cache/`.
5. `labels.json`; `scripts/extract_requirements.py` → `fixture/requirements/`.
6. Verifier module as a **scorer** (frozen profile in, report out).
7. `jobpilot.eval`: all scorers, preset loader, `--all-stages`, `compare.md`; write all `eval/stages/*.yaml`.
8. Baseline → `eval --stage baseline` → first `CHANGELOG.md` row. **Phase 0 ends here.**

**Sunday — iterations (§7.3 each)**
9. Graph skeleton with flag routing + triage node → `iter1`.
10. H-1B tool + filter node → `iter2`.
11. Tailoring node; self-verify variant → `iter3a` (removed).
12. Verifier node + retry policy → `iter3b`.
13. Gap diff + pause node + answer providers + write-back → `iter4` (run twice).
14. Style exemplars flag → `iter5`.
15. Render node (LaTeX PDF) — verify hard case A's PDF contains no dropped line.
16. Onboarding agent + profile update agent + `profile validate`; re-run `profile init` on the real resume and diff against the hand-written profile (this diff is a good README anecdote).
17. Digest node, trajectory export, `eval --all-stages`.

**Monday (before 11:00 PT)**
18. README (changelog from `compare.md`), REPRODUCE.md, hard-case write-ups, hot take.
19. Fresh-clone reproduction test: baseline, `final`, `--all-stages`, `profile init` with `--answers`.
20. Video.

**Cut order if behind Sunday night:** `iter5` → short answers → profile update agent (keep onboarding agent) → H-1B fuzzy matching (exact only). PDF rendering is small once the template mapping exists; cut only its polish, not its existence. **Never cut:** verifier node, eval harness, stage presets, non-interactive mode, changelog evidence, trajectories, onboarding agent.

---



## 11. Open decisions (author, before Saturday step 3)

- Model choice (one model for everything; favor cost — the fixture is run ~8 times).

