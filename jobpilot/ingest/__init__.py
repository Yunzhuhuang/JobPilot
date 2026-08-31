"""JD ingestion: link list in, cached postings out."""

from jobpilot.ingest.base import JD, Ingester, normalize_url, url_hash
from jobpilot.ingest.boards import FetchError, UnsupportedBoardError, detect_board
from jobpilot.ingest.cache import CACHE_DIR, load_cache, read_entry, write_entry
from jobpilot.ingest.links import (
    MIN_TEXT_CHARS,
    CacheMissError,
    IngestResult,
    LinkListIngester,
    read_links,
)

__all__ = [
    "CACHE_DIR",
    "JD",
    "MIN_TEXT_CHARS",
    "CacheMissError",
    "FetchError",
    "IngestResult",
    "Ingester",
    "LinkListIngester",
    "UnsupportedBoardError",
    "detect_board",
    "load_cache",
    "normalize_url",
    "read_entry",
    "read_links",
    "url_hash",
    "write_entry",
]
