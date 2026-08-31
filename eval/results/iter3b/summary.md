# iter3b — separate verifier node with a revision loop

Run `/Users/qiarara/Desktop/JobPilot/output/iter3b/2026-08-31` (2026-08-31) · model `claude-opus-5` · judge on

15 JDs, 7 resumes scored, 0 failed.

| Metric | Value | Detail |
| ------ | ----- | ------ |
| Fabricated claims / resume (primary) | 0 claims/resume | 0 across 7 resumes; worst jd_01 with 0 |
| ↳ baseline on the same postings | 2.286 claims/resume | 16 across the same 7 postings (jd_01, jd_03, jd_09, jd_10, jd_11, jd_12, jd_13) |
| Softened claims / resume | 1.286 claims/resume | 9 across 7 resumes |
| Rules vs. judge agreement | 93.8 % | 165/176 claim verdicts matched |
| Triage agreement with author labels | 66.7 % | 10/15 exact matches against fixture/labels.json |
| JD keyword coverage | 46.9 % | 15/32 required tool-typed items present -- jd_01 4/7, jd_03 5/8, jd_09 1/6, jd_11 1/7, jd_12 2/2, jd_13 2/2 |
| Verify → revise rounds / document | 0.29 rounds | 2 rounds over 7 documents; 2 needed at least one; 0 exhausted the budget |
| Non-sponsors dropped | n/a | _not available: no posting in the fixture states that the employer will not sponsor, so there are no true positives for this metric to find; the two constrained postings (jd_06, jd_14) are barred at the role level, which employer-level USCIS data cannot see_ |
| H-1B employer identified correctly | 100 % | 15/15 employers correctly identified; 15 index searches issued |
| Gap questions asked | 0 questions | _not available: only one run of this stage exists; run twice to see the drop_ |
| Cost / JD | 0.1161 USD/JD | 168685 in / 35933 out over 15 JDs at claude-opus-5 |
| Wall-clock / JD | 79.56 s/JD | 1193.4s over 15 JDs |

## Triage confusion

| author \ agent | most_matched | less_matched | skip |
| --- | --- | --- | --- |
| **most_matched** | 5 | 1 | 0 |
| **less_matched** | 2 | 2 | 2 |
| **skip** | 0 | 0 | 3 |

## Flags

```yaml
profile_context: true
triage: true
tailor: true
h1b_filter: true
self_verify: false
verifier_node: true
gap_memory: false
style_exemplars: false
```
