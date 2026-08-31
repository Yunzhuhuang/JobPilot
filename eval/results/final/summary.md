# final — iter1 + iter2 + iter3b + iter4 (iter5 cut for time)

Run `/Users/qiarara/Desktop/JobPilot/output/final/2026-08-31` (2026-08-31) · model `claude-opus-5` · judge on

15 JDs, 7 resumes scored, 0 failed.

| Metric | Value | Detail |
| ------ | ----- | ------ |
| Fabricated claims / resume (primary) | 0 claims/resume | 0 across 7 resumes; worst jd_01 with 0 |
| ↳ baseline on the same postings | 2.429 claims/resume | 17 across the same 7 postings (jd_01, jd_03, jd_09, jd_10, jd_11, jd_12, jd_13) |
| Softened claims / resume | 0.571 claims/resume | 4 across 7 resumes |
| Rules vs. judge agreement | 97.6 % | 165/169 claim verdicts matched |
| Triage agreement with author labels | 66.7 % | 10/15 exact matches against fixture/labels.json |
| JD keyword coverage | 50 % | 16/32 required tool-typed items present -- jd_01 4/7, jd_03 6/8, jd_09 1/6, jd_11 1/7, jd_12 2/2, jd_13 2/2 |
| Verify → revise rounds / document | 0.29 rounds | 2 rounds over 7 documents; 2 needed at least one; 0 exhausted the budget |
| Non-sponsors dropped | n/a | _not available: no posting in the fixture states that the employer will not sponsor, so there are no true positives for this metric to find; the two constrained postings (jd_06, jd_14) are barred at the role level, which employer-level USCIS data cannot see_ |
| H-1B employer identified correctly | 100 % | 15/15 employers correctly identified; 19 index searches issued |
| Gap questions asked | 0 questions | _not available: only one run of this stage exists; run twice to see the drop_ |
| Cost / JD | 0.1177 USD/JD | 176144 in / 35400 out over 15 JDs at claude-opus-5 |
| Wall-clock / JD | 76.98 s/JD | 1154.6s over 15 JDs |

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
gap_memory: true
style_exemplars: false
```
