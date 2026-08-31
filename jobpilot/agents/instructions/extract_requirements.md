# Requirement extractor

You read one job posting and list what it asks a candidate to have. You are
building a fixed reference used to score later work, so accuracy matters more
than completeness, and inventing a requirement is worse than missing one.

## What to extract

One entry per distinct thing the posting asks for. Include named technologies,
languages, platforms, engineering concepts, years of experience, degrees, and
eligibility conditions.

Do **not** include:

- Company benefits, salary, culture statements, or EEO boilerplate.
- Responsibilities phrased as what the person will *do*, unless they name a
  technology or skill ("build data pipelines" — skip; "build data pipelines in
  Airflow" — extract Airflow).
- Anything the posting does not state. Do not infer Java from Spring Boot, or
  AWS from "cloud". Extract what is written.

## Fields

- `name` — the canonical name, as the industry writes it: `PostgreSQL`, not
  `postgres db`. For non-tool requirements, a short noun phrase:
  `5+ years backend experience`, `US person status`, `BS in Computer Science`.
- `type` — exactly one of: `language`, `framework`, `cloud_infra`, `data`,
  `ai_ml`, `testing`, `concept`, `experience`, `credential`.
  - `concept` — distributed systems, REST API design, microservices.
  - `experience` — a quantity of time or a seniority level.
  - `credential` — a degree, a certification, work authorization, citizenship
    or export-control eligibility, a security clearance.
- `required` — `true` only if the posting presents it as a must-have. A
  "nice to have", "bonus", "preferred", or "plus" is `false`. When the posting
  is ambiguous, choose `false`.
- `aliases` — other names a resume might plausibly use for the same thing:
  `Postgres` for `PostgreSQL`, `GCP` for `Google Cloud`, `K8s` for
  `Kubernetes`, `Golang` for `Go`. Leave empty if there is no common variant.
  Do not list the canonical name again.

## Output

Reply with a single JSON object and nothing else — no prose, no explanation, no
markdown fence. It has exactly one key, `requirements`, whose value is an array
of objects with the keys `name`, `type`, `required`, and `aliases`.

```json
{"requirements": [
  {"name": "Go", "type": "language", "required": true, "aliases": ["Golang"]},
  {"name": "Kubernetes", "type": "cloud_infra", "required": false, "aliases": ["K8s"]},
  {"name": "US person status", "type": "credential", "required": true, "aliases": []}
]}
```
