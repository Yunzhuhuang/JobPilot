# JobPilot

A multi-agent job-application workflow that **drafts nothing it cannot prove**.

Fifteen job postings in, a triaged digest and a verified application packet out —
resume, cover letter and short answers whose every claim traces to an id in a
structured profile. Built on Google ADK 2.0, measured at every step against a
one-prompt baseline.

**Headline: fabricated claims per resume went 2.43 → 0**, at +28% cost per
posting. Both numbers were emitted by `jobpilot.eval`; neither was typed by hand.

---

## Who this is for, and what it fixes

The author is an international MS CS student graduating May 2026 who needs H-1B
sponsorship. The bottleneck is not finding postings — it is that a *good*
application takes ~30 minutes of tailoring, so eighty applications is forty
hours, and the hours come out of interview prep.

The obvious fix — ask a model to tailor the resume — fails in a specific and
expensive way. **It writes what the posting wants to hear.** In the baseline,
Canonical asks for Flask and the resume claims Flask; DoorDash asks for Swift and
it appears as "Swift: currently learning"; Zynga asks for C# and Unity and both
turn up. None of it is in the profile. A fabricated claim on a resume is a
rejection at best, and something worse in an interview.

So the product question is not "can a model write a resume" — it can — but
**"can it be stopped from lying to help you."** Everything here is built around
measuring that.

---

## The graph

```
                    ┌──────────────────────── every ? node is flag-routed
                    │                          by a stage preset
   ingest ──> h1b_filter? ──> [ triage × N in parallel ]
                                      │
        ┌─────────────────────────────┼──────────────────────┐
        │ most_matched                │ less_matched         │ skip
        ▼                             ▼                      ▼
   gap_diff? ──> (PAUSE: ask) ──> digest row            counted only
        │
        ▼
   profile_write?  ──writes tool_evidence / not_experienced──> profile.json
        │
        ▼
     tailor ──> verify? ──(revise, ≤2)──> packet
                   │
                   └─ on exhaustion: drop the rejected lines in code
        │
        ▼
     digest ──> output/<stage>/<date>/digest.md + packets/
```

A disabled capability is **absent from the graph**, not a node that returns
early. That is what makes a stage-to-stage delta attributable to one flag.

| Node | Kind | Instruction |
| ---- | ---- | ----------- |
| `ingest` | deterministic | — |
| `h1b_filter` | agent **+ tool** | [`h1b.md`](jobpilot/agents/instructions/h1b.md) |
| `triage` | agent | [`triage.md`](jobpilot/agents/instructions/triage.md) |
| `gap_ask` | **human pause** | — |
| `gap_write` | deterministic | — |
| `tailor` | agent | [`tailor.md`](jobpilot/agents/instructions/tailor.md) |
| `verify` | agent + code, **own context** | [`verify.md`](jobpilot/agents/instructions/verify.md) |
| `digest` | deterministic | — |

Deterministic work stays deterministic: ingestion, the gap diff, requirement
scoring, line-dropping and the digest never call a model.

---

## Results

Fifteen postings, `claude-opus-5` for the baseline and every stage, all numbers
from `eval/results/`. Full grid: [`compare.md`](eval/results/compare.md).

The brief's three-row format first, then everything else the harness emits.

| Metric | Simple baseline | Agent solution | Change |
| ------ | --------------- | -------------- | ------ |
| **Primary outcome** — fabricated claims / resume | **2.429** | **0** | **−100%** |
| **Human time / application** | ~30 min (manual tailoring) | ~5 min (review and send) | **−83%** |
| **Cost / application** | $0.0922 | $0.1177 | +28% |

Human time is the author's own estimate, not a harness measurement — it is the
only number here that is not machine-emitted, and it is marked as such. The
pipeline also asks **one** batched gap question per run, not per application.

| Metric | `baseline` | `final` | |
| ------ | ---------- | ------- | - |
| **Fabricated claims / resume** | **2.429** | **0** | primary |
| Rules vs. judge agreement | 86.7% | 97.6% | |
| H-1B employer identified | n/a | 100% (15/15) | |
| Gap questions re-asked | n/a | 0 (4 → 0) | |
| Verify → revise rounds | n/a | 0.29 | |
| JD keyword coverage | 63.8% | 50% | ↓ — see below |
| Triage agreement | 60% | 66.7% | within noise |
| Cost / posting | $0.0922 | $0.1177 | +28% |
| Wall-clock / posting | 38.7 s | 77.0 s | 2× |

**On the primary metric.** 2.429 is the baseline scored on *the same seven
postings* `final` produced. Its headline 1.6 is an average over fifteen, and the
pipeline tailors only `most_matched` — comparing those two averages would compare
different work, and would have flattered the pipeline, since the baseline's worst
document is one `final` never writes.

**Read the 0 with suspicion — we do.** The pipeline verifier and the harness
scorer share code by design, so the verifier deletes what the scorer counts and 0
is close to guaranteed. The evidence it is not hollow is elsewhere: **supported
claims per document stayed flat** through verification (24.0 → 23.6), and the
independent LLM judge agrees with the deterministic path on 165 of 169 verdicts.

**Coverage fell, and that is the trade.** The baseline covers more of what
postings ask for *because it fabricates* — it claims Flask, Swift, C# and Unity.
Coverage and fabrication trade against each other by construction. `iter4` is the
honest way to buy coverage back: ask the author, and only then claim it.

---

## Improvement changelog

Eight stages, one capability each, every row re-runnable from its preset.
Full table with evidence and per-stage notes: **[`CHANGELOG.md`](CHANGELOG.md)**.

| Stage | Capability | What it moved |
| ----- | ---------- | ------------- |
| `baseline` | one prompt | 1.6 fabricated/resume — the starting point |
| `iter1` | profile context + rubric | `skip` 1/3 → **3/3**; cost −74% |
| `iter2` | H-1B agent over USCIS data | employer resolution **100%** (15/15) |
| `iter3` | tailoring node | 2.4 → **0.2** fabricated |
| `iter3a` | tailor self-verifies | **removed** — 0.20 → 0.20, changed nothing |
| `iter3b` | verifier as its own node | fabricated → **0**, content held flat |
| `iter4` | gap questions + write-back | 4 questions → **0 re-asked**; coverage +5pp |
| `final` | 1 + 2 + 3b + 4 | **0 fabricated**, +28% cost |

**The largest contributor is `iter3` — the tailoring node itself**, which took
fabrications from 2.4 to 0.2 by giving the model bullet-level, *placement-aware*
context instead of a flat tool list. The verifier closed the last 0.2.

**`iter3a` was built in order to be deleted**, and it earned its row. Letting the
tailor check its own work changed nothing: 0.20 → 0.20 on the same postings. On
one posting it *swapped* one fabrication for another while reporting *"No
fabricated claims … all metrics, dates and tool-to-role attachments"* verified.
A model auditing its own draft ratifies it. That is the whole argument for
`iter3b`'s separate verifier, and it is measured rather than asserted.

---

## Two hard cases, and what they revealed

**1. "SpaceX" is not a name any string matcher can find.** The PRD specified the
H-1B lookup as normalize → exact → fuzzy ≥ 90. Run against the real USCIS export
(44,298 employers) it broke three different ways in fifteen postings:

- SpaceX files as `SPACE EXPLORATION TECHNOLOGIES CORP` — no shared token. The
  fuzzy shortlist is `ISPACE INC` and `DSPACE INC`, so the strict lookup reported
  "no petitions" about a company with 13.
- `ABRIDGE AI INC` (CA/PA, health AI) and `ABRIDGE INFO SYSTEMS INC` (MA, IT
  staffing) both score **exactly 100**. `extractOne` picks by list order.
- Stripping `technologies`/`us`/`inc` collides `COHERE US, INC.` (6 approvals)
  with `COHERE TECHNOLOGIES INC` (0, a wireless company) — so even an *exact* hit
  named the wrong company.

Resolving a brand to a legal entity is knowledge about the world, not edit
distance. The node became deterministic retrieval **plus an agent with a search
tool**: 15/15 correct. The case that matters most is OnePay, absent from all
44,298 rows — the agent searched **six times and still returned no entity**.

**2. A phrase containing the word "sponsorship" that means its opposite.** Mach
Industries reads as a strong match and buries, in a Disclosures block, that an
offer is conditioned on receiving export-controlled technology *"without
sponsorship for an export license"*. The baseline labelled it `less_matched`. The
triage rubric catches it, and — the sharper test — it **kept** catching it after
`iter2` started telling triage that Mach files H-1B petitions. Handed evidence
pointing the wrong way, the agent wrote: *"H-1B filing history does not override
the export-control requirement for this defense role."*

---

## The main failure mode

**Under pressure from a requirement the candidate lacks, the model hedges rather
than lies.** Not `"built Kafka pipelines"` but `"Flask-style web services via
FastAPI"` — a phrase that smuggles the word in while staying deniable. Every
word comes from the profile; the *claim* does not.

The same shape appears in placement. `"Configured Kafka pipelines at Amazon"` can
be built entirely from real profile terms and still be false, because the
invention is the **attachment**. That is why verification is placement-aware:
`classify_claim` returns `unplaced` for a `self_study` tool in a role bullet, and
`misplaced` for a tool attached to the wrong employer. Membership checking would
pass both.

---

## Hot take

**The deterministic verifier is worth more than the LLM judge, and the LLM judge
is what proved it.**

Every real improvement in this project came from the rules path being *wrong* in
a way the judge exposed. The baseline's fabrication count walked 8.13 → 5.53 →
1.8 → 1.6 before it stabilised, and nothing about the baseline changed — each
drop removed a false reject in my own scorer. Rules-vs-judge agreement was the
signal: 61.8% at its worst, 97.6% now. Later, ten of eleven flags in `iter3` were
one bug (a GPA stored as a typed float and therefore invisible to a whitelist
built from prose).

The lesson is not "use two verifiers". It is that **a metric you cannot audit
will measure your parser and call it a result**, and the cheapest insurance is a
second, differently-wrong opinion over the *same* decomposition. Where the two
disagree is the finding — that is the only reason `iter3a`'s contested flag got
settled correctly rather than tuned away.

---

## Safety, data and human control

The brief's ground rules, addressed directly.

**Nothing is ever sent.** JobPilot writes files. It does not submit applications,
email anyone, or touch a job board's forms — the only outward network calls are
*reads*: fetching a public posting and downloading public USCIS data. There is no
consequential action to sandbox, because the workflow stops at a folder on disk.

**A human is in the loop by construction, not as a courtesy.** The author reviews
every packet before it is used, and the pipeline pauses mid-run to ask before it
records anything about her experience — `gap_ask` is a real ADK interrupt, not a
prompt the model answers to itself. Answers are written back with a printed diff,
and the profile is re-validated before it is saved.

**Data.** The postings are public job ads, fetched only from boards whose terms
permit it (Greenhouse, Lever, Ashby) and frozen in `fixture/cache/`. The H-1B
index is the public USCIS Employer Data Hub. The profile is the author's own, at
public-resume level — **no phone number, no street address, no ID numbers** — and
the contact address in it is a public one.

**Credentials.** No API key is committed. `.env` is gitignored; `.env.example`
holds a placeholder. Bring your own key (see REPRODUCE.md).

**The one thing that writes.** `iter4` and `final` modify `profile.json`, and only
that file, and only by *appending* evidence the author confirmed or a
`not_experienced` entry she declined. `fixture/profile.json` — the copy every
score is computed against — is never touched, so no run can move its own
goalposts.

---

## Pre-existing vs. built here

| Pre-existing | Built for this hackathon |
| ------------ | ------------------------ |
| The author's resume text and career history | Everything in `jobpilot/` |
| `fixture/labels.json` — the author's own triage labels | Profile schema, verifier, eval harness |
| `fixture/answers.json` — the author's own gap answers | All six agent instructions |
| USCIS H-1B Employer Data Hub (public data) | The ADK graph and every node |
| `docs/prd.md` — written before building | The changelog and all measurements |

No LaTeX template was supplied, so PDF rendering was cut (below). Nothing in this
repo is labelled pre-existing that was written this weekend.

---

## What was cut, and why

Cut deliberately with hours left, not forgotten:

- **`iter5` — style exemplars.** First on the PRD's own cut list. `final` is
  therefore `iter1+2+3b+4`; `final.yaml` says so.
- **PDF rendering.** Needed `templates/resume.tex`, the author's pre-existing
  template, which was never supplied. Every metric is computed on `resume.md`;
  no number depends on a PDF.
- **Onboarding and profile-update agents.** The largest remaining build. Their
  absence costs two of the five trajectories PRD §9.4 names — `trajectories/`
  ships the six nodes that exist and names the two that do not.

---

## Future work

- Verify the cover letter and short answers, not just the resume.
- A shared HTTP client for verification (see REPRODUCE's "known noise").
- The onboarding agent, so a new user can start from a PDF rather than
  hand-writing `profile.json`.
- Widen the fixture: 15 postings gives 6.7pp granularity on triage, which is why
  several results here are reported but explicitly not claimed.

---

## Repository

```
jobpilot/          profile · ingest · h1b · agents · verify · eval · workflow.py
  agents/instructions/*.md    every agent instruction, as a deliverable
fixture/           the frozen 15 postings, labels, requirements, profile, answers
data/              USCIS FY2026 H-1B employer index (44,298 employers)
eval/stages/*.yaml one preset per stage — the flags that define it
eval/results/      every number in this README
trajectories/      one representative step per node
output/<stage>/    runs: digest.md + packets/<jd_id>/
```

**[`REPRODUCE.md`](REPRODUCE.md)** — clean-environment setup, exact commands,
expected output, cost (~$11 for everything) and runtime.
