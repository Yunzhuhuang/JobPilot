# Improvement Changelog

How JobPilot got from a single prompt to the final workflow, one measured
experiment at a time. Every stage here is re-runnable from its preset in
`eval/stages/`, and every number was written by `jobpilot.eval` into
`eval/results/`.

**Primary metric:** fabricated (unsupported) claims per generated resume — a
claim is fabricated when the verifier cannot map it to an id in the frozen
`fixture/profile.json`. Target at `final`: **0**. Secondary metrics (triage
agreement with the author's labels, JD keyword coverage, non-sponsors dropped,
gap questions asked run 1 vs. run 2, human review time, cost per JD, wall-clock
per JD) are defined in PRD §7.1 and reported in each stage's `summary.md`.

The full metric grid across every stage is `eval/results/compare.md`, emitted by
`python -m jobpilot.eval --all-stages`.

| Stage | What you tried and why | Evidence | Decision / Learning |
| ----- | ---------------------- | -------- | ------------------- |
| `baseline` | One LLM call per posting: raw pre-hackathon resume text plus the JD, asked to label the match and write a resume and cover letter. No schema, no lookup, no verifier — the "reasonable basic way" the brief asks for. | `eval/results/baseline/summary.json` — **1.6 fabricated/resume** (24 across 15) · triage **60%** (9/15) · coverage 63.8% (51/80) · $0.0922/JD · 38.71 s/JD | **Kept as the baseline.** Three failures to attack: it fabricates exactly where the JD wants what the profile lacks, it cannot see sponsorship, and it is too conservative on strong matches. [Notes →](#baseline) |
| `iter1` | The ADK graph, flag-routed, with a triage node that reads a compact `profile.json` summary and a stated rubric — including the two labelling rules the ground truth was written under. | `eval/results/iter1/summary.json` — triage **60% → 66.7%** (9/15 → 10/15) · cost **$0.0922 → $0.0243/JD** · wall **38.71 → 7.03 s/JD** · fabrication `n/a` (no resumes) | **Kept.** All the gain is on constraint cases: `skip` went **1/3 → 3/3**, including a clause that contains the word *sponsorship* while meaning its opposite. [Notes →](#iter1) |
| `iter2` | The H-1B node over the real USCIS FY2026 export (44,298 employers). The PRD's specified string-matching design was **discarded before measurement** — it broke three different ways on real data — and rebuilt as deterministic retrieval plus an agent with a search tool. | `eval/results/iter2/summary.json` — **employer identified correctly 100%** (15/15, 20 searches) · cost **$0.0243 → $0.0519/JD** · wall **7.03 → 15.3 s/JD** · 0 dropped · regression gate **PASS** | **Kept, at 2× cost/posting.** Resolving a brand to a legal entity is world knowledge, not edit distance. Triage did **not** improve — that move is one flapping posting. [Notes →](#iter2) |
| `iter3` | The tailoring node — the first stage that writes claims, so the first since `baseline` the primary metric can score. Added ahead of the PRD's schedule so `iter3a`'s delta isolates self-verification alone. | `eval/results/iter3/summary.json` — **0.2 fabricated/resume** (1 across 5) vs **2.4 for the baseline on the same 5 postings** · softened 0.4 · rules-vs-judge **97.6%** (120/123) · coverage 60.9% (14/23) · $0.0519 → **$0.0875/JD** · 28.85 s/JD | **Kept — a 92% reduction**, visible only because the baseline is restricted to the same postings. Against its headline 1.6 this stage reads as a regression. [Notes →](#iter3) |
| `iter3a` | `iter3` plus one flag: the tailor checks its own work inside a single completion. The naive fix, budgeted by the PRD as a stage **built in order to be removed**. | `eval/results/iter3a/summary.json` — raw **0.286/resume** (2 across 7) vs baseline **2.286** on those same 7 · softened 0.286 · rules-vs-judge **97.1%** (169/174) · coverage **60.9% → 46.9%** · cost **$0.0875 → $0.1026/JD** · 28.85 → 37.12 s/JD. Like-for-like on the 5 shared postings: `iter3` **0.20** → `iter3a` **0.00** — **one claim** | **Removed.** The one-claim gain is inside the noise band, it cost 14 points of coverage, and it still fabricated twice on the two postings it alone tailored — while reporting itself clean. [Notes →](#iter3a) |
| `iter3b` | The verifier as its own node: it did not write the document, holds none of the tailor's context, and reaches its verdict from the profile alone (PRD §5.8). Rejections go back to the tailor for at most two revisions; on exhaustion the lines are cut in code. The loop acts on the **union** of the rules and judge paths. | `eval/results/iter3b/summary.json` — **0 fabricated/resume** vs baseline **2.286** on the same 7 · **0.29 revision rounds/doc** (2 of 7 needed one, **0 exhausted**) · softened 1.286 · rules-vs-judge 93.8% · cost **$0.1026 → $0.1161/JD** · 37.12 → **79.56 s/JD**. Like-for-like on the 5 shared with `iter3`: fabricated **0.20 → 0.00**, supported claims **24.0 → 23.6/doc** | **Kept — but the headline number is now tautological and must not be read as the result.** The scorer counts what the rules path rejects and this node deletes exactly that, so 0 is near-guaranteed. The honest evidence is that content held: supported claims per document are flat. [Notes →](#iter3b) |
| `iter4` | Gap questions with write-back (PRD §5.6). A deterministic diff finds required tools the profile cannot evidence; the run **pauses** and asks; a yes becomes `tool_evidence` attached where the author says they used it, a no becomes `not_experienced`. Both are durable, which is what stops a question returning. | `eval/results/iter4/summary.json` — **run 1 asked 4, run 2 asked 0, 0 repeated** · coverage **46.9% → 52%** · fabricated **0** (baseline 2.167 on the same 6) · rules-vs-judge **98.6%** · cost $0.1161 → **$0.1122/JD** | **Kept.** The memory works and it is cheap. The placement answers matter more than the yes/no: two of three confirmed tools are `self_study`, so they reach the skills line and are barred from every role bullet. [Notes →](#iter4) |
| `final` | `iter1 + iter2 + iter3b + iter4`. `iter3a`'s self-review is excluded because it was measured and removed; `iter5`'s style exemplars are excluded because they were **cut for time**, not tested. | `eval/results/final/summary.json` — **0 fabricated claims per resume** across 7, against **2.429 for the baseline on those same 7** · softened 0.571 · rules-vs-judge **97.6%** (165/169) · coverage 50% · triage 66.7% · cost **$0.0922 → $0.1177/JD** · **38.71 → 76.98 s/JD** | **The headline: the primary metric goes to 0, and it costs 28% more per posting and twice the wall-clock.** Two of those numbers are honest-but-unflattering and stay that way. [Notes →](#final) |

---

## Stage notes

### `baseline`

Three failures, in the order the iterations attack them:

1. **It fabricates exactly where the posting wants what the profile lacks.**
   Canonical wants Flask and the resume claims Flask; DoorDash wants Swift and
   it appears as "Swift: currently learning"; Zynga wants C# and Unity and both
   appear. Nothing in the profile supports any of them.
2. **It cannot see sponsorship.** SpaceX (ITAR) and Mach (export-control) were
   both labelled `less_matched` rather than skipped, so effort would go to jobs
   that cannot hire her.
3. **It is too conservative on strong matches.** Of the author's 6
   `most_matched` it agreed on 3 and downgraded 3; it also downgraded 2 of 3
   `skip`s.

Rules-vs-judge agreement 86.7% (286/330). Next: `iter1` adds `profile.json`
context and a triage rubric, targeting the agreement number.

### `iter1`

**What moved.** The whole gain is on the constraint cases. `skip` went **1/3 →
3/3**: SpaceX and Mach both moved from `less_matched` to `skip`, Mach on the
buried clause conditioning an offer on receiving export-controlled technology
*"without sponsorship for an export license"* — a phrase containing the word
*sponsorship* while meaning its opposite. Figma Full Stack also recovered to
`most_matched`. Cost fell 74% because triage is a small call, not a whole resume.

**One regression.** Cohere (`jd_15`) over-skipped on seniority — the agent
treats "4+ years" as disqualifying where the author would still send a generic
application. Over-skipping is the expensive error, because a skipped posting is
only counted, never shown.

**Re-measured 2026-08-30**, after the `use_sub_branch` fix found in `iter2`. The
first run of this identical stage scored 73.3% (11/15); the re-run scored 66.7%
(10/15). Neither number is wrong — see [`iter2`](#iter2) on why one posting of
movement is not a result on this fixture.

### `iter2`

**The specified design was discarded before it was ever measured.** PRD §4.3
asks for normalize → exact → rapidfuzz ≥ 90 → "does not sponsor". Run against
the real export, that broke three different ways inside a 15-posting fixture,
and each is a different kind of failure:

1. **The legal name is not the brand name.** SpaceX files as
   `SPACE EXPLORATION TECHNOLOGIES CORP`, sharing no token with "SpaceX" — the
   fuzzy shortlist is `ISPACE INC` and `DSPACE INC`. No threshold anywhere
   retrieves it, and the strict version reported "no petitions" about a company
   with 13.
2. **Fuzzy ties span unrelated companies.** `ABRIDGE AI INC` (CA/PA, health AI)
   and `ABRIDGE INFO SYSTEMS INC` (MA, IT staffing) both score exactly 100;
   `extractOne` picks by list order. The agent breaks the tie on filing state
   against the posting's "SF Office".
3. **Normalization collides distinct employers.** Stripping
   `technologies`/`us`/`inc` maps `COHERE US, INC.` (6 approvals) and
   `COHERE TECHNOLOGIES INC` (0, a wireless company) onto one key — so even an
   **exact** hit named the wrong company and summed two firms' filings.

**The clearest single result** is `jd_12` OnePay, genuinely absent from all
44,298 rows: the agent issued **6 searches and still returned no entity**, which
is the behaviour that matters most in a project whose primary metric is
fabrication.

**Triage did not improve.** The 66.7 → 73.3 move is one posting — `jd_15` Cohere
flipping between `skip` and `less_matched` — and re-running `iter1` unchanged
reproduced 66.7% where it had scored 73.3%. With 15 items one posting is 6.7pp,
and at least two (`jd_04`, `jd_15`) flap between runs, so **differences under
~13pp on this fixture are not distinguishable from noise** and are not claimed
as results.

**Nothing is dropped, and that is correct, not a gap.** No company in the fixture
is a non-sponsor: fourteen of fifteen actively file (SpaceX 13, Mach 1, DoorDash
238), and OnePay is *absent*, which is `unknown` rather than no — a company that
has never filed and one that refuses look identical in employer-level data, and
dropping on absence would have removed `jd_12`, labelled `most_matched`. The
postings that genuinely cannot hire her, `jd_06` and `jd_14`, are caught by
**triage** reading the ITAR and clearance text, and are counted-not-listed in the
digest so no tailoring is spent on them.

**The node was initially decorative and is no longer.** As first built its
verdict reached only the digest — `triage_prompt` never saw it — so `iter2`
doubled cost while changing no label. It now feeds triage as evidence, guarded by
an instruction that filing history **never** overrides a role-level bar. That
guard is the whole risk: "SpaceX likely sponsors, 13 approvals" argues against
the `skip` SpaceX requires. It held, and the agent said why unprompted:

> `jd_06`: "SpaceX's H-1B filing history is irrelevant here; export-control and
> clearance requirements govern this specific role."
>
> `jd_14`: "H-1B filing history (1 approval FY2026) does not override the
> export-control requirement for this defense role."

**Coupling it did not move the number**, though: triage held at 73.3% (11/15)
before and after, cells reshuffling inside the noise band. The honest verdict is
that the node buys correct employer identification and a digest column at 2×
cost per posting, and has not yet been shown to improve a label.
`non_sponsors_dropped` reports `n/a`, not 0 — the metric has no true positives to
find on this fixture.

### `iter3`

**Design.** Two things carry it. The context is **bullet-level and
placement-aware** — each role and project is given with the tools that belong to
*it*, and `self_study` tools are listed separately as skills-only, because
`classify_claim` marks them `unplaced` in any experience bullet. And the
instruction pins an **exact markdown contract**, since `verify/segment.py`
resolves claims by matching `###` headings to profile names.

**Why the like-for-like baseline exists.** Against the baseline's headline 1.6
this stage reads as a *regression*; against the same five postings the baseline
scores 2.4. The pipeline tailors `most_matched` only, and the baseline's worst
document — `jd_01` Canonical, 4 fabrications — is `less_matched`, so comparing
the two averages would have compared different work.

**The metric was measuring the verifier again, and it took the whole first
reading with it.** The first run scored 2.2, and **ten of the eleven flagged
claims were one bug**: `_profile_numbers` walked the profile's *prose* only, so
`education.gpa` — a typed float — was invisible, and "GPA 3.8" was `unsupported`
against a profile literally storing 3.8. Same class of false reject that walked
the baseline 8.13 → 1.6. Fixed by whitelisting typed numeric fields; invented
GPAs (4.0, 3.95) still reject, and rules-vs-judge agreement rose **89.4% →
97.6%**, the independent corroboration that the fix was correct rather than
permissive.

**The one surviving fabrication is the interesting one.** `jd_01` Canonical
requires Flask, which the candidate does not have; the tailor wrote *"Flask-style
web services via FastAPI"* into the skills line — not a flat false claim but a
hedge that smuggles the word in, exactly what the instruction forbids. Pressure
from an unmet requirement produces evasion, not invention, and only the
placement-aware whitelist catches it.

### `iter3a`

**These numbers were re-measured at `iter3b`**, after the title rule was
narrowed to experience and project sections. That change is the one this row
flagged in advance as "a false-positive candidate for `iter3b` to settle" — it
was made on the judge's disagreement, not on the number it would move, and
`scripts/check_rules_scope.py` pins that inflation in a role heading is still
caught. It did move this stage's number, and the corrected reading is below.

**The comparison that matters is like-for-like.** Triage drifted and tailored 7
postings here against `iter3`'s 5, so the raw averages are not the same
measurement. On the **5 postings both stages produced**: `iter3` **0.20**,
`iter3a` **0.00**. Self-review did remove `iter3`'s one fabrication — the hedge
*"Flask-style web services via FastAPI"* — and its own notes say so: *"Removed
all mention of Flask, Ubuntu and open-source contributions, since none appear in
the material."*

**That is one claim across five resumes, and it does not carry the stage.**
The same discipline `iter2` established for triage applies to the primary metric:
a single claim at n=5 is 0.2/resume of movement, well inside the range that run
-to-run variation produces. Three things say to remove the stage anyway:

1. **It still fabricates, on the postings it alone tailored.** `jd_12` came back
   claiming `NoSQL` and a `Bloom filter`, neither of which has a `tool_evidence`
   entry — two fabrications in one document, from the stage whose entire purpose
   is catching them.
2. **The self-assessments are confidently wrong**, which is the durable finding.
   `jd_03`: *"No fabricated claims … All metrics, dates and tool-to-role
   attachments"* verified. `jd_10`: *"kept all tools inside the exact
   roles/projects they belong to."* On `jd_12` it reported itself clean while
   claiming a Bloom filter. A model auditing its own draft, with its own
   reasoning still in context, ratifies it.
3. **It costs coverage.** 60.9% → 46.9%, with `jd_09` falling to 1/6 required
   items. That is the `iter3a` failure mode in its quieter form: reviewing under
   pressure to remove, the model removes true things too. A resume that claims
   nothing is not a correct answer.

So the capability is real but unreliable and self-blind, and it buys one claim
for 14 points of coverage and 27% more cost. Next: `iter3b` gives the verifier
its own node, its own instruction, and no sight of the tailor's context — an
external check that can be wrong out loud, in a report, rather than a
self-assessment that is always confident.

### `iter3b`

**Read the zero with suspicion.** The pipeline verifier and the harness scorer
share code, by PRD §5.8's design. The scorer counts what the rules path rejects;
this node now deletes precisely that. **0 fabricated claims is close to
guaranteed and is not evidence the stage works.** What it does prove is that the
loop terminates and never ships a claim the verifier rejected. The numbers that
still carry information are below.

**Content held — this is the real result.** The failure mode to fear was
`iter3a`'s in a new costume: reach zero by gutting the resume. On the five
postings `iter3` and `iter3b` both produced, **supported claims per document went
24.0 → 23.6** — flat. The verifier removed `jd_01`'s fabrication (the
*"Flask-style web services via FastAPI"* hedge) and left everything else
standing; that document ended with *more* supported claims than before, 22 → 24,
and its softened count fell 2 → 0.

**The verifier touched two documents.** `jd_03` and `jd_12` each needed exactly
one revision round and ended at zero unsupported. The other five needed none —
`iter3`'s tailor was already close to clean, which is the finding, not a
disappointment. **Nothing exhausted the budget**, so `strip_units` — the "cut the
lines in code" path of PRD §5.1 — has been unit-tested but **never fired in a
real run**. That is stated rather than claimed as working.

**Two apparent regressions, both attributable, neither the verifier's.**

- *Softened rose 0.40 → 1.00.* Four of the five softened units on the shared
  postings are bare school headings — `### Northeastern University` with the
  degree on the line below — which assert nothing checkable and so score
  `softened` by definition. `iter3` happened to write education on one line. A
  formatting difference, not the tailor learning to hedge.
- *Coverage fell 60.9% → 52.2%* on the shared postings. The entire drop is
  `jd_09`, 3/6 → 1/6 — and **`jd_09` needed zero revision rounds**, so the
  verifier never modified it. That is run-to-run tailoring variance, on the same
  fixture that flips `jd_04` and `jd_15` between runs.

**What it costs.** $0.1026 → $0.1161 per posting, and wall-clock **doubles**,
37 → 79.6 s/JD, because verification is two LLM passes per document and runs
again after every revision. The most expensive stage so far, for a capability
whose headline metric cannot prove its own worth.

**One rough edge, not fixed.** Each `verify()` call opens its own event loop in a
worker thread (it calls `asyncio.run` internally, so it cannot be awaited
directly), and the abandoned Anthropic clients emit `RuntimeError: Event loop is
closed` on teardown. Noise on stderr, not a failure — every document completed —
but it should be a shared client before this is called production code.

### `iter4`

**The metric it exists for.** Run 1 asked about 4 tools across the `most_matched`
postings; run 2 asked about **0**, with **0 repeated**. A "no" is as durable as a
"yes" — `Flask` went to `not_experienced` and never came back — which is why even
an unattended `--no-questions` run moves this number.

**Coverage recovered, 46.9% → 52%**, which is what the write-back is *for*. It
only works because the tailor rebuilds its context from the **live** profile
rather than the copy it closed over at construction; with a stale context the
answers would never reach a resume and coverage would sit flat for a reason
nothing in the output would explain.

**The placement answers are the interesting part.** Asked where they had used
each tool, the author put two of three outside any role: `Ubuntu` and `Ruby` are
`self_study`, so they may appear on a skills line and `classify_claim` returns
`unplaced` for any attempt to put them in an experience bullet. Only `LLM
agents` got a real home (`proj_2`, the multi-agent project). A yes/no question
would have recorded three plain yeses and quietly licensed three fabrications.

**One deviation from the PRD, stated.** §5.6 specifies one batched question *per
posting*; this asks once *per run*, over the union. The answer is a fact about
the author, not about the posting — "have you used Ubuntu?" has one true answer
however many postings raise it — and it turns seven interruptions into one. The
buckets, the write-back and the never-re-ask rule are unchanged.

**A measurement trap this stage walked into, and how it was fixed.** The scorer
verifies against the **frozen** `fixture/profile.json`, so the first scoring
flagged `Ruby` as a fabrication — a tool the author had confirmed minutes
earlier. The frozen copy predates the answer. `scorers.scoring_profile` now adds
back exactly the entries whose `source` is `gap_question`, and nothing else, so a
`gap_memory` stage is judged against what the author actually said while still
being unable to grant itself a claim by any other route. Verified bounded:
`baseline` and `iter3b` scores are unchanged.

### `final`

**0 fabricated claims per resume, across 7 documents, against 2.429 for the
baseline on the same 7 postings.** That is the number the project was built to
move, and the like-for-like comparison is the only fair way to read it — the
pipeline tailors `most_matched` only, so the baseline's fifteen-document average
was never the same measurement.

**Read the zero the way `iter3b` says to.** The pipeline verifier and the harness
scorer share code, so the verifier deletes what the scorer counts and 0 is close
to guaranteed. The evidence that it is not hollow is elsewhere: **supported
claims per document held flat** through verification (24.0 → 23.6 at `iter3b`),
rules-vs-judge agreement is **97.6%**, and the independent judge disagrees with
the deterministic path on 4 of 169 verdicts.

**What it costs.** $0.0922 → **$0.1177 per posting** (+28%) and **38.71 → 76.98
s/JD** (2×). The pipeline is slower and dearer than one prompt, and buys
correctness for it.

**Two numbers that did not improve, kept in the table.**

- *Triage agreement 60% → 66.7%*, which is one posting of movement on a fixture
  where at least two flap between runs. Not claimed as a result. The real triage
  gain was never the aggregate: it was `skip` going 1/3 → 3/3 at `iter1`, and
  holding since.
- *Coverage 63.8% → 50%*. The baseline scores higher **because it fabricates** —
  it claims Flask, Swift, C# and Unity, so of course it covers more of what the
  postings ask for. Coverage and fabrication trade against each other by
  construction, and this project chose the side it chose. `iter4` is the honest
  way to buy coverage back: ask the author, and only then claim it.

---

## How rows get added

One row per stage, appended only after the measurement exists (PRD §7.3):

1. Flip the flag in `eval/stages/<name>.yaml`.
2. Build the node.
3. Run `python -m jobpilot.eval --stage <name>`, which writes
   `eval/results/<name>/summary.json`, `summary.md`, and `per_jd.md`.
4. Append the row. **What you tried and why** names the failure observed in the
   previous stage. **Evidence** is a path into `eval/results/<name>/` plus the
   numbers that moved. **Decision / Learning** is kept, revised, or removed, and
   what it changes about the next step. Detail goes in a **Stage notes** section
   so the table stays scannable.
5. Only then start the next feature.

No number in this file is typed by hand — each is copied from the `summary.json`
its Evidence cell points at. Stages that were removed stay in the table with
their evidence; a negative result is part of the story.
