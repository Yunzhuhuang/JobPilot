"""Per-board fetch and extraction.

The three permitted boards do not behave alike, and one of them cannot be
scraped at all:

- Greenhouse serves server-rendered HTML. The body extracts cleanly with
  trafilatura, but the metadata does not -- there is no JSON-LD, no `og:title`,
  and no usable meta description -- so title and location come from the DOM.
- Ashby serves a JS-rendered SPA. trafilatura gets 46 characters out of it.
  Its public posting API returns the description as plain text, so that is the
  path used here.
- Lever is the generic HTML path and is UNTESTED: no fixture link exercises it.
"""

from __future__ import annotations

import json
import re
import time
from datetime import date
from urllib.parse import urlparse

import httpx
import trafilatura
from lxml import html as lxml_html

from jobpilot.ingest.base import PERMITTED_BOARDS, Board, normalize_url

USER_AGENT = "JobPilot/0.1 (+hackathon fixture builder; contact via repo README)"
TIMEOUT = 30.0

# Politeness between requests to the same board (ground rule 03).
REQUEST_GAP_SECONDS = 1.0

ASHBY_POSTING_API = "https://api.ashbyhq.com/posting-api/job-board/{org}"

_HOST_BOARDS: dict[str, Board] = {
    "job-boards.greenhouse.io": "greenhouse",
    "boards.greenhouse.io": "greenhouse",
    "jobs.lever.co": "lever",
    "jobs.ashbyhq.com": "ashby",
}


class UnsupportedBoardError(ValueError):
    """Raised for a URL from a board the project will not fetch."""


class FetchError(RuntimeError):
    """Raised when a permitted board did not yield a usable posting."""


def detect_board(url: str) -> Board:
    host = urlparse(url).netloc.lower()
    board = _HOST_BOARDS.get(host)
    if board is None:
        raise UnsupportedBoardError(
            f"{host or url!r} is not a permitted job board. JobPilot fetches only "
            f"{', '.join(PERMITTED_BOARDS)} -- boards whose terms allow simple "
            f"GETs. Boards such as LinkedIn, Workday, Eightfold, Gem and Rippling "
            f"are out of scope; see the Ingester interface to add another."
        )
    return board


class Fetcher:
    """Fetches postings, one HTTP client and one Ashby board cache per run."""

    def __init__(self) -> None:
        self._client = httpx.Client(
            follow_redirects=True,
            timeout=TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
        # Ashby returns a whole board per call and Mercor appears twice in the
        # fixture; caching avoids fetching the same board again.
        self._ashby_boards: dict[str, list[dict]] = {}
        self._requests = 0

    def __enter__(self) -> Fetcher:
        return self

    def __exit__(self, *exc: object) -> None:
        self._client.close()

    @property
    def request_count(self) -> int:
        return self._requests

    def fetch(self, url: str) -> dict[str, str]:
        """Returns company, title, location, and text for one posting."""
        board = detect_board(url)
        normalized = normalize_url(url)
        if board == "ashby":
            return self._fetch_ashby(normalized)
        return self._fetch_html(normalized, board)

    def _get(self, url: str) -> httpx.Response:
        if self._requests:
            time.sleep(REQUEST_GAP_SECONDS)
        self._requests += 1
        response = self._client.get(url)
        response.raise_for_status()
        return response

    def _fetch_html(self, url: str, board: Board) -> dict[str, str]:
        """Greenhouse, and the untested Lever path."""
        response = self._get(url)
        text = trafilatura.extract(response.text) or ""
        doc = lxml_html.fromstring(response.text)

        title = _first_text(doc, "//h1")
        location = _first_text(doc, "//*[contains(@class,'job__location')]")
        if not location:
            location = _first_text(doc, "//*[contains(@class,'location')]")

        # Greenhouse formats it "Job Application for <Title> at <Company>".
        page_title = _first_text(doc, "//title")
        company = ""
        if " at " in page_title:
            company = page_title.rsplit(" at ", 1)[1].strip()
            if not title:
                title = page_title.rsplit(" at ", 1)[0]
                title = re.sub(r"^Job Application for\s+", "", title).strip()
        if not company:
            company = urlparse(url).path.strip("/").split("/")[0]

        return {
            "company": company,
            "title": title,
            "location": location,
            "text": text,
        }

    def _fetch_ashby(self, url: str) -> dict[str, str]:
        """Ashby, via the posting API -- the web page is a JS-rendered SPA."""
        parts = [p for p in urlparse(url).path.split("/") if p]
        if len(parts) < 2:
            raise FetchError(f"cannot read org and job id out of {url!r}")
        org, job_id = parts[0], parts[1]

        # The API's org slug is case-sensitive; the URL's is what works.
        if org not in self._ashby_boards:
            response = self._get(ASHBY_POSTING_API.format(org=org))
            self._ashby_boards[org] = response.json().get("jobs", [])

        for job in self._ashby_boards[org]:
            if job.get("id") == job_id:
                return {
                    "company": self._ashby_company(url, org),
                    "title": job.get("title", ""),
                    "location": job.get("location") or "",
                    "text": job.get("descriptionPlain") or "",
                }

        raise FetchError(
            f"job {job_id} is not on the {org} Ashby board -- the posting was "
            f"probably closed or unlisted"
        )


    def _ashby_company(self, url: str, org: str) -> str:
        """The employer's real name, which the posting API does not carry.

        The API returns only the board slug, and a slug is not a company:
        `oneapp` is OnePay, `mach` is Mach Industries. Wrong here means a wrong
        USCIS lookup downstream, so it is worth one extra request -- the SPA
        page embeds JSON-LD with `hiringOrganization.name`.
        """
        try:
            page = self._get(url)
        except httpx.HTTPError:
            return org

        for blob in re.findall(
            r'<script type="application/ld\+json"[^>]*>(.*?)</script>',
            page.text,
            re.S,
        ):
            try:
                data = json.loads(blob)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and data.get("@type") == "JobPosting":
                name = (data.get("hiringOrganization") or {}).get("name")
                if name:
                    return str(name).strip()

        # Ashby titles its pages "<Job title> @ <Company>".
        title = _first_text(lxml_html.fromstring(page.text), "//title")
        if " @ " in title:
            return title.rsplit(" @ ", 1)[1].strip()
        return org


def _first_text(doc: lxml_html.HtmlElement, xpath: str) -> str:
    for element in doc.xpath(xpath):
        text = re.sub(r"\s+", " ", element.text_content()).strip()
        if text:
            return text
    return ""


def today() -> str:
    return date.today().isoformat()
