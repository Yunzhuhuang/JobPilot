# _synthetic — a hand-built run that exercises every scorer; not a real stage

Run `fixture/eval_samples/output/synthetic/2026-08-30` (2026-08-30) · model `claude-opus-5` · judge on

15 JDs, 2 resumes scored, 1 failed.

| Metric | Value | Detail |
| ------ | ----- | ------ |
| Fabricated claims / resume (primary) | 2.5 claims/resume | 5 across 2 resumes; worst jd_05 with 5 |
| Softened claims / resume | 1 claims/resume | 2 across 2 resumes |
| Rules vs. judge agreement | 95.2 % | 20/21 claim verdicts matched |
| Triage agreement with author labels | 85.7 % | 12/14 exact matches against fixture/labels.json |
| JD keyword coverage | 38.5 % | 5/13 required tool-typed items present -- jd_03 5/8, jd_05 0/5 |
| Non-sponsors dropped | n/a | _not available: fixture/h1b_truth.json does not exist until step 10_ |
| Gap questions asked | 1 questions | _not available: only one run of this stage exists; run twice to see the drop_ |
| Cost / JD | 0.0485 USD/JD | 78000 in / 13500 out over 15 JDs at claude-opus-5 |
| Wall-clock / JD | 11.4 s/JD | 171.0s over 15 JDs |

## Triage confusion

| author \ agent | most_matched | less_matched | skip |
| --- | --- | --- | --- |
| **most_matched** | 5 | 0 | 0 |
| **less_matched** | 1 | 5 | 0 |
| **skip** | 0 | 1 | 2 |

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
