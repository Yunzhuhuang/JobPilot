"""Read and write `fixture/cache/<jd_id>.md`.

The cache is committed, and it is what makes the changelog reproducible: every
stage from `baseline` onward replays these files offline, so a judge reaches the
same numbers without the postings still being live.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from jobpilot.config import REPO_ROOT
from jobpilot.ingest.base import JD

CACHE_DIR = REPO_ROOT / "fixture" / "cache"
QUESTIONS_HEADING = "## Application questions"

_FRONT_MATTER = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.S)


def entry_path(jd_id: str, cache_dir: Path | None = None) -> Path:
    return (cache_dir or CACHE_DIR) / f"{jd_id}.md"


def write_entry(jd: JD, cache_dir: Path | None = None) -> Path:
    """Writes one cache entry. Front matter, body, then optional questions."""
    directory = cache_dir or CACHE_DIR
    directory.mkdir(parents=True, exist_ok=True)

    front: dict[str, object] = {
        "jd_id": jd.jd_id,
        "source_url": jd.source_url,
        "url_hash": jd.url_hash,
        "board": jd.board,
        "company": jd.company,
        "title": jd.title,
        "location": jd.location,
        "fetched_at": jd.fetched_at,
    }
    if jd.application_questions:
        # Provenance: nothing in a scraped posting supplies these.
        front["author_added"] = True

    body = jd.text.strip()
    if jd.application_questions:
        asked = "\n".join(f"- {q}" for q in jd.application_questions)
        body = f"{body}\n\n{QUESTIONS_HEADING}\n{asked}"

    rendered = (
        "---\n"
        + yaml.safe_dump(front, sort_keys=False, allow_unicode=True)
        + "---\n"
        + body
        + "\n"
    )
    path = entry_path(jd.jd_id, directory)
    path.write_text(rendered)
    return path


def read_entry(path: Path) -> JD:
    match = _FRONT_MATTER.match(path.read_text())
    if not match:
        raise ValueError(f"{path} has no YAML front matter")
    front = yaml.safe_load(match.group(1)) or {}
    front.pop("author_added", None)  # derived from the questions on write
    body = match.group(2)

    questions: list[str] = []
    if QUESTIONS_HEADING in body:
        body, _, tail = body.partition(QUESTIONS_HEADING)
        questions = [
            line.lstrip("- ").strip()
            for line in tail.splitlines()
            if line.strip().startswith("-")
        ]

    return JD(**front, text=body.strip(), application_questions=questions)


def load_cache(cache_dir: Path | None = None) -> dict[str, JD]:
    """Every cached JD, keyed by `url_hash`."""
    directory = cache_dir or CACHE_DIR
    if not directory.is_dir():
        return {}
    entries = (read_entry(p) for p in sorted(directory.glob("jd_*.md")))
    return {jd.url_hash: jd for jd in entries}


def next_jd_id(existing: dict[str, JD]) -> str:
    """The lowest unused `jd_<nn>`.

    Ids are pinned to a `url_hash` on first write and reused thereafter, so
    reordering `links.txt` cannot renumber the fixture out from under
    `labels.json` and `fixture/requirements/`.
    """
    taken = {jd.jd_id for jd in existing.values()}
    for n in range(1, 100):
        candidate = f"jd_{n:02d}"
        if candidate not in taken:
            return candidate
    raise RuntimeError("fixture is capped at 99 JDs")
