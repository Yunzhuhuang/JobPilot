# baseline — one prompt, raw resume text, no profile schema

Run `/Users/qiarara/Desktop/JobPilot/output/baseline/2026-08-30` (2026-08-30) · model `claude-opus-5` · judge on

15 JDs, 15 resumes scored, 0 failed.

| Metric | Value | Detail |
| ------ | ----- | ------ |
| Fabricated claims / resume (primary) | 1.6 claims/resume | 24 across 15 resumes; worst jd_01 with 4 |
| ↳ baseline on the same postings | n/a | _not available: this stage generated no resumes to compare_ |
| Softened claims / resume | 0 claims/resume | 0 across 15 resumes |
| Rules vs. judge agreement | 86.7 % | 286/330 claim verdicts matched |
| Triage agreement with author labels | 60 % | 9/15 exact matches against fixture/labels.json |
| JD keyword coverage | 63.8 % | 51/80 required tool-typed items present -- jd_01 7/7, jd_02 1/2, jd_03 5/8, jd_04 3/3, jd_05 4/5, jd_06 2/3, jd_07 2/4, jd_08 3/4, jd_09 4/6, jd_11 2/7, jd_12 2/2, jd_13 2/2, jd_14 11/16, jd_15 3/11 |
| Verify → revise rounds / document | n/a | _not available: this stage ran no verifier node_ |
| Non-sponsors dropped | n/a | _not available: no posting in the fixture states that the employer will not sponsor, so there are no true positives for this metric to find; the two constrained postings (jd_06, jd_14) are barred at the role level, which employer-level USCIS data cannot see_ |
| H-1B employer identified correctly | n/a | _not available: this stage ran no H-1B node_ |
| Gap questions asked | 0 questions | _not available: only one run of this stage exists; run twice to see the drop_ |
| Cost / JD | 0.0922 USD/JD | 64747 in / 42357 out over 15 JDs at claude-opus-5 |
| Wall-clock / JD | 38.71 s/JD | 580.6s over 15 JDs |

## Triage confusion

| author \ agent | most_matched | less_matched | skip |
| --- | --- | --- | --- |
| **most_matched** | 3 | 3 | 0 |
| **less_matched** | 0 | 5 | 1 |
| **skip** | 0 | 2 | 1 |

## Flags

```yaml
profile_context: false
triage: false
tailor: false
h1b_filter: false
self_verify: false
verifier_node: false
gap_memory: false
style_exemplars: false
```
