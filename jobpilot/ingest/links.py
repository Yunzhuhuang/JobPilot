"""`LinkListIngester` -- v1's Ingester: a file of URLs the user maintains.

Cache-first by design. `--offline` never reaches the network and never silently
drops a JD, because a run that quietly scores 14 of 15 postings would make every
number in the changelog wrong in a way nobody would notice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from jobpilot.ingest.base import JD, url_hash
from jobpilot.ingest.boards import Fetcher, FetchError, detect_board, today
from jobpilot.ingest.cache import CACHE_DIR, load_cache, next_jd_id, write_entry

# Below this, an extraction has silently failed rather than found a short
# posting. Ashby's SPA problem surfaced as 46 characters.
MIN_TEXT_CHARS = 1500


class CacheMissError(RuntimeError):
    """Raised when `--offline` meets a URL that was never cached."""


@dataclass
class IngestResult:
    jds: list[JD] = field(default_factory=list)
    hits: int = 0
    fetched: int = 0
    thin: list[str] = field(default_factory=list)
    """jd_ids whose extracted text came in under MIN_TEXT_CHARS."""


def read_links(path: Path) -> list[str]:
    """One URL per line. `#` comments and blank lines are ignored."""
    lines = path.read_text().splitlines()
    return [
        line.strip()
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    ]


@dataclass
class LinkListIngester:
    links_path: Path
    cache_dir: Path = CACHE_DIR
    offline: bool = False
    refresh: bool = False

    def fetch(self) -> IngestResult:
        urls = read_links(self.links_path)
        cached = load_cache(self.cache_dir)
        result = IngestResult()

        # Validate every board before opening a connection, so an unsupported
        # URL fails immediately rather than after a dozen polite fetches.
        for url in urls:
            detect_board(url)

        with Fetcher() as fetcher:
            for url in urls:
                key = url_hash(url)
                hit = cached.get(key)

                if hit is not None and not self.refresh:
                    result.jds.append(hit)
                    result.hits += 1
                    continue

                if self.offline:
                    raise CacheMissError(
                        f"{url} is not in {self.cache_dir} (url_hash {key}) and "
                        f"--offline forbids fetching. Run without --offline to "
                        f"populate the cache, or remove the link."
                    )

                jd = self._fetch_one(fetcher, url, key, cached, hit)
                write_entry(jd, self.cache_dir)
                cached[key] = jd
                result.jds.append(jd)
                result.fetched += 1
                if len(jd.text) < MIN_TEXT_CHARS:
                    result.thin.append(jd.jd_id)

        return result

    def _fetch_one(
        self,
        fetcher: Fetcher,
        url: str,
        key: str,
        cached: dict[str, JD],
        previous: JD | None,
    ) -> JD:
        parsed = fetcher.fetch(url)
        if not parsed["text"].strip():
            raise FetchError(f"{url} yielded no text")

        return JD(
            # Reuse the id on --refresh so a re-fetch cannot renumber the fixture.
            jd_id=previous.jd_id if previous else next_jd_id(cached),
            source_url=url,
            url_hash=key,
            board=detect_board(url),
            company=parsed["company"],
            title=parsed["title"],
            location=parsed["location"],
            fetched_at=today(),
            text=parsed["text"].strip(),
            application_questions=(
                previous.application_questions if previous else []
            ),
        )
