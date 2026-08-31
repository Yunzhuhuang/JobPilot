# iter3 — tailoring node, no verification of any kind

Run `/Users/qiarara/Desktop/JobPilot/output/iter3/2026-08-30` (2026-08-30) · model `claude-opus-5` · judge on

15 JDs, 5 resumes scored, 0 failed.

| Metric | Value | Detail |
| ------ | ----- | ------ |
| Fabricated claims / resume (primary) | 0.2 claims/resume | 1 across 5 resumes; worst jd_01 with 1 |
| ↳ baseline on the same postings | 2.4 claims/resume | 12 across the same 5 postings (jd_01, jd_03, jd_09, jd_10, jd_13) |
| Softened claims / resume | 0.4 claims/resume | 2 across 5 resumes |
| Rules vs. judge agreement | 97.6 % | 120/123 claim verdicts matched |
| Triage agreement with author labels | 73.3 % | 11/15 exact matches against fixture/labels.json |
| JD keyword coverage | 60.9 % | 14/23 required tool-typed items present -- jd_01 4/7, jd_03 5/8, jd_09 3/6, jd_13 2/2 |
| Verify → revise rounds / document | n/a | _not available: this stage ran no verifier node_ |
| Non-sponsors dropped | n/a | _not available: no posting in the fixture states that the employer will not sponsor, so there are no true positives for this metric to find; the two constrained postings (jd_06, jd_14) are barred at the role level, which employer-level USCIS data cannot see_ |
| H-1B employer identified correctly | 100 % | 15/15 employers correctly identified; 16 index searches issued |
| Gap questions asked | 0 questions | _not available: only one run of this stage exists; run twice to see the drop_ |
| Cost / JD | 0.0875 USD/JD | 147275 in / 23045 out over 15 JDs at claude-opus-5 |
| Wall-clock / JD | 28.85 s/JD | 432.8s over 15 JDs |

## Triage confusion

| author \ agent | most_matched | less_matched | skip |
| --- | --- | --- | --- |
| **most_matched** | 4 | 2 | 0 |
| **less_matched** | 1 | 4 | 1 |
| **skip** | 0 | 0 | 3 |

## Flags

```yaml
profile_context: true
triage: true
tailor: true
h1b_filter: true
self_verify: false
verifier_node: false
gap_memory: false
style_exemplars: false
```
