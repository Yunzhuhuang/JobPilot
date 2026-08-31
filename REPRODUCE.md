# Reproducing the results

Every number in `README.md` and `CHANGELOG.md` was written by `jobpilot.eval`
into `eval/results/`. This file is how you regenerate them.

## Environment

- **Python 3.11+** (developed on 3.12.0).
- **`google-adk` 2.8.0**, pinned in `requirements.txt`. The graph uses the ADK
  2.0 Workflow runtime; 1.x will not run it.
- **One model, everywhere:** `claude-opus-5`, set once in `config.yaml` and used
  by the baseline and every stage. No stage gets a better model than the
  baseline it is compared against.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...        # your own key; none is committed
```

`.env` works too (`cp .env.example .env` and fill it in). **`.env` is gitignored
and contains no key in this repo** — bring your own.

**TeX is not required.** PDF rendering was cut (see the README's "What was cut").
Every metric is computed on `resume.md`; nothing depends on a PDF.

## The data is committed — no network needed

All fifteen job postings are frozen in `fixture/cache/`, so every command below
runs `--offline` and replays the exact text the results were computed from. You
do not need to fetch anything, and postings changing on the web cannot move a
number.

| Path | What it is |
| ---- | ---------- |
| `fixture/cache/jd_*.md` | The 15 postings, as fetched |
| `fixture/labels.json` | The author's ground-truth triage labels (6 / 6 / 3) |
| `fixture/requirements/` | Extracted requirements per posting |
| `fixture/profile.json` | **Frozen** profile — every score is computed against this |
| `fixture/h1b_truth.json` | Which USCIS employer each company is, and the evidence |
| `fixture/answers.json` | The author's own gap-question answers |
| `data/h1b_employers.json` | USCIS FY2026 Employer Data Hub, 44,298 employers |

## Commands

Run them in this order. Each writes `eval/results/<stage>/summary.json`,
`summary.md` and `per_jd.md`.

```bash
# 1. The baseline: one prompt per posting, no schema, no verifier.
python -m jobpilot.baseline
python -m jobpilot.eval --stage baseline

# 2. Any single stage.
python -m jobpilot run  --stage iter1  --offline
python -m jobpilot.eval --stage iter1
#   ...iter2, iter3, iter3a, iter3b likewise.

# 3. The memory stage, run twice — the second run is the measurement.
python -m jobpilot run --stage iter4 --offline --answers fixture/answers.json \
       --out output/iter4/$(date +%F)-run1
python -m jobpilot run --stage iter4 --offline --answers fixture/answers.json \
       --out output/iter4/$(date +%F)-run2
python -m jobpilot.eval --stage iter4

# 4. The headline.
python -m jobpilot run  --stage final --offline --answers fixture/answers.json
python -m jobpilot.eval --stage final

# 5. Every stage side by side -> eval/results/compare.md
python -m jobpilot.eval --all-stages
```

### Answering gap questions

`iter4` and `final` pause and ask. Three sources, one code path:

| Flag | Who answers | Use |
| ---- | ----------- | --- |
| *(none)* | you, at the terminal | the live demo |
| `--answers fixture/answers.json` | the author's recorded answers | reproducible runs |
| `--no-questions` | nothing — declines everything | unattended / CI |

**`--no-questions` still moves the metric.** A "no" is written to
`not_experienced` and is as durable as a "yes", so the question is never asked
again.

### One thing that legitimately changes on disk

`iter4` and `final` **write to `profile.json`** — that is the memory feature
working. After a run it will differ from `fixture/profile.json`, which is
correct: the frozen fixture is what every score is computed against, so a run
cannot move its own goalposts. Restore the working copy any time with:

```bash
git checkout profile.json
```

## Other commands

```bash
python -m jobpilot ingest  --links fixture/links.txt   # refresh the JD cache
python -m jobpilot verify  <document.md>               # verify any markdown
python scripts/check_rules_scope.py                    # verifier rule tests
python scripts/export_trajectories.py                  # regenerate trajectories/
python scripts/refresh_h1b.py                          # rebuild the USCIS index
```

`scripts/refresh_h1b.py` downloads from
`bigdataanalyticspub-sb.uscis.dhs.gov` — the Tableau backend of the H-1B
Employer Data Hub. `www.uscis.gov` returns **403 to every scripted request**
regardless of user agent, which is why that URL is the default.

## Cost and runtime

Fifteen postings, `claude-opus-5`, measured — not estimated:

| Stage | $/posting | ≈ $/run | s/posting |
| ----- | --------- | ------- | --------- |
| `baseline` | 0.0922 | 1.38 | 38.7 |
| `iter1` | 0.0243 | 0.36 | 7.0 |
| `iter2` | 0.0519 | 0.78 | 15.3 |
| `iter3` | 0.0875 | 1.31 | 28.9 |
| `iter3b` | 0.1161 | 1.74 | 79.6 |
| `iter4` | 0.1122 | 1.68 | 73.1 |
| **`final`** | **0.1177** | **1.77** | **77.0** |

Reproducing everything — baseline plus all stages plus `--all-stages` — is
roughly **$11** and about 45 minutes of wall-clock.

`eval` re-verifies each resume with two LLM calls, cached by content hash in
`eval/results/<stage>/verification/`. Re-scoring an unchanged run is free; the
deterministic verdict is recomputed on every load, so a fix to the rules costs
nothing to apply.

## Expected output

```
output/<stage>/<date>/
  run.json                 machine-readable record; every scorer reads this
  digest.md                the human-facing daily digest
  packets/<jd_id>/
    resume.md  cover_letter.md  short_answers.md
    verification_report.json    claim-by-claim verdicts
    trajectory.json             instruction -> inputs -> output, per node

eval/results/<stage>/summary.json | summary.md | per_jd.md
eval/results/compare.md           every stage, side by side
```

## Known non-fatal noise

`iter3b` and `final` print `RuntimeError: Event loop is closed` on stderr during
teardown. Each `verify()` call opens its own event loop in a worker thread and
the abandoned HTTP clients complain on close. Every document still completes;
the tracebacks are cleanup noise, not failures. It is in the changelog as a
rough edge that should be a shared client before this is production code.
