# Trajectories

One representative step per agent node (PRD §9 deliverable 4), each
readable as instruction -> inputs -> tool calls -> output. Regenerate
with `python scripts/export_trajectories.py`.

- `h1b_filter.json` — from `iter2`, jd_08
- `triage.json` — from `final`, jd_01
- `tailor.json` — from `final`, jd_01
- `verify.json` — from `final`, jd_12
- `gap_ask.json` — from `iter4`, 2026-08-31-run1
- `gap_write.json` — from `iter4`, 2026-08-31-run1

**Not present:** `onboarding` and `profile_update`. Those agents were
cut for time and the README says so — an absent trajectory for an agent
that does not exist is more honest than a hand-written one.
