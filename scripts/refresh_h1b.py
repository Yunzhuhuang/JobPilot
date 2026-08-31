#!/usr/bin/env python
"""Build `data/h1b_employers.json` from the USCIS H-1B Employer Data Hub.

The data is public and free. USCIS publishes it two ways, and only one of them
is reachable from a script:

  * `www.uscis.gov/.../h1b_datahubexport-<year>.csv` returns **403 to every
    scripted request**, with or without a browser user agent, on both the CSV
    and the page linking to it.
  * The Tableau backend behind the same dashboard serves the identical data
    over plain HTTP with no headers required:

        https://bigdataanalyticspub-sb.uscis.dhs.gov/views/H1BEmployerDataHub-Final/H1BPublic.csv

That second URL is the default source here, which is what makes this project
reproducible from a clean clone. `--from <path>` takes a local copy instead.

The export is ~76 MB and one row per employer *per approval type*, so it is
folded into one record per employer:

    {"name": "<as published>", "new": int, "xfer": int, "cont": int,
     "states": ["CA", "PA"]}

Nothing here invents or infers a number -- the counts are the published
"Measure Values" for the three approval measures, summed per employer.
Employer names are kept **exactly as filed**: two companies that normalize to
the same key (COHERE US, INC. and COHERE TECHNOLOGIES INC) must stay separate
rows, because merging them is one of the failures that made the strict lookup
untrustworthy. See `jobpilot/h1b/lookup.py`.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobpilot.h1b.lookup import DATA_DIR, INDEX_JSON

SOURCE_URL = (
    "https://bigdataanalyticspub-sb.uscis.dhs.gov"
    "/views/H1BEmployerDataHub-Final/H1BPublic.csv"
)

NAME_COLUMNS = ("Employer (Petitioner) Name", "Employer", "Employer Name")
MEASURE_NAME_COLUMNS = ("Measure Names",)
MEASURE_VALUE_COLUMNS = ("Measure Values",)
STATE_COLUMNS = ("Petitioner State", "State")
YEAR_COLUMNS = ("Fiscal Year", "Fiscal Year   ")

# The dashboard's "Measure Names" values, mapped to our short keys.
MEASURES = {
    "new employment approval": "new",
    "continuing approval": "cont",
    "continuation approval": "cont",
    "transferring approval": "xfer",
    "transfer approval": "xfer",
    "change of employer approval": "xfer",
}


def _column(row: dict, candidates: tuple[str, ...]) -> str | None:
    for name in candidates:
        if name in row:
            return name
    lowered = {k.lower().strip(): k for k in row}
    for name in candidates:
        if name.lower().strip() in lowered:
            return lowered[name.lower().strip()]
    return None


def _to_int(value: str | None) -> int:
    try:
        return int(float(str(value).replace(",", "").strip() or 0))
    except ValueError:
        return 0


def parse(text: str) -> tuple[dict[str, dict], int]:
    """The raw export -> {normalized key: employer record}, plus fiscal year."""
    reader = csv.DictReader(io.StringIO(text))
    first = next(reader, None)
    if first is None:
        raise ValueError("the export is empty")

    name_col = _column(first, NAME_COLUMNS)
    measure_col = _column(first, MEASURE_NAME_COLUMNS)
    value_col = _column(first, MEASURE_VALUE_COLUMNS)
    state_col = _column(first, STATE_COLUMNS)
    year_col = _column(first, YEAR_COLUMNS)
    if not (name_col and measure_col and value_col):
        raise ValueError(f"unrecognised columns: {list(first)[:10]}")

    employers: dict[str, dict] = {}
    states: dict[str, set[str]] = defaultdict(set)
    fiscal_year = 0

    for row in (first, *reader):
        raw = (row.get(name_col) or "").strip()
        if not raw:
            continue
        # Key on the published name, so distinct legal entities stay distinct.
        record = employers.setdefault(
            raw, {"name": raw, "new": 0, "xfer": 0, "cont": 0}
        )
        measure = MEASURES.get((row.get(measure_col) or "").strip().lower())
        if measure:
            record[measure] += _to_int(row.get(value_col))
        if state_col and (state := (row.get(state_col) or "").strip()):
            states[raw].add(state)
        if year_col and not fiscal_year:
            fiscal_year = _to_int(row.get(year_col))

    for raw, record in employers.items():
        record["states"] = sorted(states.get(raw, ()))
    return employers, fiscal_year


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from",
        dest="source",
        type=Path,
        help="a local copy of the export CSV; downloads from USCIS if omitted",
    )
    parser.add_argument("--out", type=Path, default=INDEX_JSON)
    args = parser.parse_args(argv)

    if args.source:
        if not args.source.is_file():
            print(f"error: no such file: {args.source}", file=sys.stderr)
            return 2
        text = args.source.read_text(encoding="utf-8-sig", errors="replace")
        origin = str(args.source)
    else:
        print(f"downloading {SOURCE_URL} …")
        response = httpx.get(SOURCE_URL, timeout=300, follow_redirects=True)
        response.raise_for_status()
        text = response.text
        origin = SOURCE_URL
        print(f"  {len(text):,} bytes")

    employers, fiscal_year = parse(text)
    filers = sum(1 for e in employers.values() if e["new"] + e["xfer"] + e["cont"])

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "fiscal_year": fiscal_year,
                "generated": date.today().isoformat(),
                "source": origin,
                "employers": employers,
            }
        )
    )
    print(
        f"wrote {args.out} — {len(employers):,} employers "
        f"({filers:,} with at least one approval), FY{fiscal_year}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
