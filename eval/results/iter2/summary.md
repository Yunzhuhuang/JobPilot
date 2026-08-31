# iter2 — H-1B lookup tool + filter node

Run `/Users/qiarara/Desktop/JobPilot/output/iter2/2026-08-30` (2026-08-30) · model `claude-opus-5` · judge on

15 JDs, 0 resumes scored, 0 failed.

| Metric | Value | Detail |
| ------ | ----- | ------ |
| Fabricated claims / resume (primary) | n/a | _not available: no resumes were produced by this run_ |
| Softened claims / resume | n/a | _not available: no resumes were produced by this run_ |
| Rules vs. judge agreement | n/a | _not available: the judge path was not run (--no-judge)_ |
| Triage agreement with author labels | 73.3 % | 11/15 exact matches against fixture/labels.json |
| JD keyword coverage | n/a | _not available: no tool-typed required items among the scored JDs_ |
| Non-sponsors dropped | n/a | _not available: no posting in the fixture states that the employer will not sponsor, so there are no true positives for this metric to find; the two constrained postings (jd_06, jd_14) are barred at the role level, which employer-level USCIS data cannot see_ |
| H-1B employer identified correctly | 100 % | 15/15 employers correctly identified; 17 index searches issued |
| Gap questions asked | 0 questions | _not available: only one run of this stage exists; run twice to see the drop_ |
| Cost / JD | 0.0519 USD/JD | 117134 in / 7697 out over 15 JDs at claude-opus-5 |
| Wall-clock / JD | 15.3 s/JD | 229.5s over 15 JDs |

## Triage confusion

| author \ agent | most_matched | less_matched | skip |
| --- | --- | --- | --- |
| **most_matched** | 5 | 1 | 0 |
| **less_matched** | 1 | 3 | 2 |
| **skip** | 0 | 0 | 3 |

## Flags

```yaml
profile_context: true
triage: true
tailor: false
h1b_filter: true
self_verify: false
verifier_node: false
gap_memory: false
style_exemplars: false
```
