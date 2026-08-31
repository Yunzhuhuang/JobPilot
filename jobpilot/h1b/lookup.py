"""Retrieval over the USCIS H-1B Employer Data Hub. No verdicts here.

PRD §4.3 originally specified this as normalize-then-match: exact, else fuzzy
at ratio 90, else "does not sponsor". Running that against the real FY2026
export (42,877 employers) broke it three separate ways inside a 15-posting
fixture, and each failure is a different kind:

1. **The legal name is not the brand name.** SpaceX files as SPACE EXPLORATION
   TECHNOLOGIES CORP. `normalize("SpaceX")` is `spacex`; the entity normalizes
   to `space exploration`. No string metric at any threshold joins those, so
   the lookup reported "no petitions found" about a company with 13.
2. **Fuzzy ties span unrelated companies.** ABRIDGE AI INC (CA/PA, the health
   AI company) and ABRIDGE INFO SYSTEMS INC (MA, IT staffing) both score 100
   against `abridge`. So do IMC AMERICAS INC and IMC CAPITAL INVESTMENT LLC.
   `extractOne` picks by list order, which is to say by accident.
3. **Normalization collides distinct employers.** Stripping `technologies`,
   `us` and `inc` maps both COHERE TECHNOLOGIES INC (a wireless company, 0
   petitions) and COHERE US, INC. (6) onto `cohere` -- so even an *exact* hit
   could name the wrong company and sum two firms' filings.

The common thread is that resolving a brand to a legal entity is a judgement
about the world, not a string operation. So this module retrieves candidates
and stops; `jobpilot.agents.h1b` decides between them, and can search again
when none of them fit. Raw names are never merged here -- collapsing them is
what hid failure 3.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from rapidfuzz import fuzz

from jobpilot.config import REPO_ROOT

DATA_DIR = REPO_ROOT / "data"
INDEX_JSON = DATA_DIR / "h1b_employers.json"

Confidence = Literal["exact", "fuzzy", "none"]

# Corporate suffixes and filler that differ between a job board and a USCIS
# filing: Ramp posts as "Ramp" and files as "RAMP BUSINESS CORPORATION". Used
# for *scoring only* -- two employers that normalize alike stay separate rows.
_SUFFIXES = re.compile(
    r"\b(inc|incorporated|llc|l\.l\.c|ltd|limited|corp|corporation|co|company|"
    r"holdings|group|technologies|technology|labs|lab|services|solutions|"
    r"software|systems|usa|us|america|the|and)\b"
)


def normalize(name: str) -> str:
    """Lowercase, strip punctuation and corporate suffixes."""
    cleaned = re.sub(r"[^a-z0-9 ]+", " ", name.lower())
    cleaned = _SUFFIXES.sub(" ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


@dataclass(frozen=True)
class Employer:
    """One row of the USCIS export, kept exactly as published."""

    name: str
    new: int
    xfer: int
    cont: int
    states: tuple[str, ...]

    @property
    def total(self) -> int:
        """Every approval type. `cont` alone can be nonzero for a company that
        has stopped filing, and `new` alone for one that just started."""
        return self.new + self.xfer + self.cont

    def describe(self) -> str:
        return (
            f"{self.name} | {'/'.join(self.states) or '??'} | "
            f"new={self.new} transfer={self.xfer} continuing={self.cont}"
        )


# Below this, a shared substring is coincidence rather than evidence: "imc"
# appears inside "simcorp" and "x" inside "spacex".
MIN_CONTAINED_CHARS = 5


def _contains(inner: str, outer: str) -> bool:
    """Is `inner` a substantial, token-aligned substring of `outer`?"""
    if len(inner) < MIN_CONTAINED_CHARS or inner not in outer:
        return False
    return bool(re.search(rf"(^|\s){re.escape(inner)}($|\s)", outer))


@dataclass(frozen=True)
class Candidate:
    employer: Employer
    score: float
    """rapidfuzz token-set ratio against the query, 0-100."""


class H1BIndex:
    """Searchable view of the export. Retrieval only -- it never concludes."""

    def __init__(self, employers: list[Employer], fiscal_year: int = 0) -> None:
        self.fiscal_year = fiscal_year
        self._employers = employers
        # Scoring keys are precomputed; a search touches all 42k rows and this
        # is the difference between 30 ms and 3 s per query.
        self._keys = [normalize(e.name) for e in employers]

    def __len__(self) -> int:
        return len(self._employers)

    def search(
        self, query: str, *, limit: int = 8, cutoff: float = 70
    ) -> list[Candidate]:
        """Rank employers against a brand or legal name.

        Substring containment is scored above the fuzzy ratio because "space
        exploration" is a *substring* of the SpaceX entity but a mediocre
        token-set match for it -- and containment is the stronger signal.

        It is only stronger when the shared text is substantial, though.
        Unguarded, this boosted `X CORP.` (normalizing to "x") to 95 against
        "spacex", and boosted every employer whose name is nothing but
        stripped suffixes -- `SOLUTIONS INC` normalizes to the empty string,
        which is a substring of every query on earth.
        """
        key = normalize(query)
        if not key:
            return []

        scored: list[Candidate] = []
        for employer, candidate_key in zip(self._employers, self._keys, strict=True):
            if not candidate_key:
                continue
            ratio = float(fuzz.token_set_ratio(key, candidate_key))
            if _contains(key, candidate_key) or _contains(candidate_key, key):
                ratio = max(ratio, 95.0)
            if ratio >= cutoff:
                scored.append(Candidate(employer=employer, score=ratio))

        # Ties are common and meaningful (two ABRIDGE entities both score 100),
        # so break them by filing volume: the larger filer is the likelier
        # match for a company big enough to be posting engineering roles. This
        # only orders the shortlist -- the agent still chooses.
        scored.sort(key=lambda c: (-c.score, -c.employer.total, c.employer.name))
        return scored[:limit]

    def exact(self, query: str) -> list[Employer]:
        """Every employer whose normalized name equals the query's.

        Returns a list, not one row: more than one distinct company can land on
        the same normalized key, and that ambiguity is the caller's to resolve.
        """
        key = normalize(query)
        return [
            employer
            for employer, candidate_key in zip(self._employers, self._keys, strict=True)
            if candidate_key == key
        ]


def load_index(path: Path | None = None) -> H1BIndex:
    path = path or INDEX_JSON
    if not path.is_file():
        raise FileNotFoundError(
            f"no H-1B data at {path}. Build it with "
            f"`python scripts/refresh_h1b.py` -- see the script's docstring."
        )
    payload = json.loads(path.read_text())
    employers = [
        Employer(
            name=row["name"],
            new=int(row.get("new", 0)),
            xfer=int(row.get("xfer", 0)),
            cont=int(row.get("cont", 0)),
            states=tuple(row.get("states", ())),
        )
        for row in payload["employers"].values()
    ]
    return H1BIndex(employers, fiscal_year=int(payload.get("fiscal_year", 0)))
