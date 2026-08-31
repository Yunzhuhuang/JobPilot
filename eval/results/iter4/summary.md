# iter4 — gap questions with profile write-back

Run `/Users/qiarara/Desktop/JobPilot/output/iter4/2026-08-31-run2` (2026-08-31) · model `claude-opus-5` · judge on

15 JDs, 6 resumes scored, 0 failed.

| Metric | Value | Detail |
| ------ | ----- | ------ |
| Fabricated claims / resume (primary) | 0 claims/resume | 0 across 6 resumes; worst jd_03 with 0 |
| ↳ baseline on the same postings | 2.167 claims/resume | 13 across the same 6 postings (jd_03, jd_09, jd_10, jd_11, jd_12, jd_13) |
| Softened claims / resume | 0.333 claims/resume | 2 across 6 resumes |
| Rules vs. judge agreement | 98.6 % | 140/142 claim verdicts matched |
| Triage agreement with author labels | 66.7 % | 10/15 exact matches against fixture/labels.json |
| JD keyword coverage | 52 % | 13/25 required tool-typed items present -- jd_03 6/8, jd_09 2/6, jd_11 1/7, jd_12 2/2, jd_13 2/2 |
| Verify → revise rounds / document | 0.33 rounds | 2 rounds over 6 documents; 2 needed at least one; 0 exhausted the budget |
| Non-sponsors dropped | n/a | _not available: no posting in the fixture states that the employer will not sponsor, so there are no true positives for this metric to find; the two constrained postings (jd_06, jd_14) are barred at the role level, which employer-level USCIS data cannot see_ |
| H-1B employer identified correctly | 100 % | 15/15 employers correctly identified; 18 index searches issued |
| Gap questions asked | 0 questions | run 1 asked 4, run 2 asked 0; 0 repeated (target 0) |
| Cost / JD | 0.1122 USD/JD | 170997 in / 33112 out over 15 JDs at claude-opus-5 |
| Wall-clock / JD | 73.05 s/JD | 1095.7s over 15 JDs |

## Triage confusion

| author \ agent | most_matched | less_matched | skip |
| --- | --- | --- | --- |
| **most_matched** | 5 | 1 | 0 |
| **less_matched** | 1 | 2 | 3 |
| **skip** | 0 | 0 | 3 |

## Flags

```yaml
profile_context: true
triage: true
tailor: true
h1b_filter: true
self_verify: false
verifier_node: true
gap_memory: true
style_exemplars: false
```
