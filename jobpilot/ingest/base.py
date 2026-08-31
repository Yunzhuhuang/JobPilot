"""The ingestion contract: what a JD is, and how URLs become stable keys.

`Ingester` is a Protocol so the roadmap's live-discovery scraper can drop in
behind it without the pipeline noticing. v1 ships one implementation,
`LinkListIngester`, over a file of URLs the user maintains by hand.
"""

from __future__ import annotations

import hashlib
from typing import Literal, Protocol, runtime_checkable
from urllib.parse import parse_qs, urlparse, urlunparse

from pydantic import BaseModel, ConfigDict, Field

Board = Literal["greenhouse", "lever", "ashby"]

# Boards whose terms permit simple GETs (PRD 3, ground rule 03). Anything else
# is rejected by name rather than attempted -- see `boards.detect_board`.
PERMITTED_BOARDS: tuple[Board, ...] = ("greenhouse", "lever", "ashby")

# Params that identify the click, not the job. Dropping them is what keeps
# url_hash stable for the same posting shared from two places.
TRACKING_PARAMS = frozenset(
    {"jr_id", "gh_src", "utm_source", "utm_medium", "utm_campaign", "utm_term",
     "utm_content", "ref", "source"}
)


class JD(BaseModel):
    """One job posting, as cached.

    Everything above `text` is the YAML front matter of
    `fixture/cache/<jd_id>.md` (PRD 4.2).
    """

    model_config = ConfigDict(extra="forbid")

    jd_id: str = Field(pattern=r"^jd_\d{2}$")
    source_url: str
    url_hash: str = Field(min_length=8)
    board: Board
    company: str = Field(min_length=1)
    title: str = Field(min_length=1)
    location: str
    fetched_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    text: str = Field(min_length=1)
    application_questions: list[str] = Field(default_factory=list)
    """Author-added. Nothing in a scraped posting supplies these, so when the
    list is non-empty the cache entry records `author_added: true`."""


@runtime_checkable
class Ingester(Protocol):
    def fetch(self) -> list[JD]: ...


def normalize_url(url: str) -> str:
    """Canonical form of a posting URL, for hashing and for fetching.

    Two jobs of the same posting must hash alike no matter how the link was
    shared, so tracking params are dropped. Greenhouse embed URLs are rewritten
    to their canonical path -- verified to return byte-identical text, and the
    canonical form survives the `for=`/`token=` query pair being reordered.
    """
    parts = urlparse(url.strip())
    host = parts.netloc.lower()
    query = parse_qs(parts.query)

    if host == "job-boards.greenhouse.io" and parts.path.startswith("/embed/"):
        company = (query.get("for") or [""])[0]
        token = (query.get("token") or [""])[0]
        if company and token:
            return f"https://{host}/{company}/jobs/{token}"

    kept = {k: v for k, v in query.items() if k.lower() not in TRACKING_PARAMS}
    encoded = "&".join(f"{k}={v[0]}" for k, v in sorted(kept.items()))
    return urlunparse((parts.scheme or "https", host, parts.path.rstrip("/"),
                       "", encoded, ""))


def url_hash(url: str) -> str:
    """Stable cache key: the first 12 hex chars of sha256(normalized url)."""
    return hashlib.sha256(normalize_url(url).encode()).hexdigest()[:12]
