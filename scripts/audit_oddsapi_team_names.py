"""Can the-odds-api team names reach `core.dim_team` well enough to load?

`docs/oddsapi-ingest.md` defers the warehouse wiring on one blocker: Odds API names carry
the mascot ("Miami Hurricanes") and `stg.games` carries the school ("Miami"), so nothing
joins to `game_id`. `research/spread/scripts/weekly_slate.py` already strips mascots
(`oa_resolve`) -- but against Prediction Tracker's slate, not the warehouse, and its own
docstring says the strip is *not* unambiguous. What keeps a wrong price off the board there
is that the merge keys on **both** teams, so a misresolved name has to be paired with a
partner that misresolves onto the same row. A warehouse flatten resolving one team at a
time does not get that.

So this measures the strip against `core.dim_team` directly, and reports three outcomes,
not two: resolved to exactly one team, resolved to more than one (the dangerous case -- a
one-sided join would pick one), and unresolved.

    python scripts/audit_oddsapi_team_names.py
    python scripts/audit_oddsapi_team_names.py --list

Read-only, offline: reads the snapshots already in `data/ingest/oddsapi/`. Exits 0 always.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from cfb_paths import DATA_ROOT  # noqa: E402

MAX_MASCOT_TOKENS = 2  # "Thundering Herd" is the longest; mirrors OA_MAX_MASCOT_TOKENS


def norm(name: str) -> str:
    """Casefold, fold accents, delete apostrophes, drop other punctuation to spaces.

    Deliberately not `weekly_slate.norm`: importing it drags in the whole slate module and
    its Prediction Tracker paths. The two rules that are not obvious are both CFBD
    spellings -- `San José State` needs the accent folded rather than blanked (else
    "san jos state"), and `Hawai'i` needs the apostrophe *deleted* rather than turned into
    a space (else "hawai i", which never meets "hawaii").
    """
    folded = unicodedata.normalize("NFKD", str(name).lower())
    folded = "".join(c for c in folded if not unicodedata.combining(c)).replace("'", "")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", folded)).strip()


def candidates(name: str) -> list[str]:
    """Every head the mascot strip would try, longest first."""
    parts = str(name).split()
    return [norm(" ".join(parts[:cut]))
            for cut in range(len(parts), max(0, len(parts) - MAX_MASCOT_TOKENS) - 1, -1)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", type=Path, default=DATA_ROOT / "cfb.duckdb")
    ap.add_argument("--snapshots", type=Path, default=DATA_ROOT / "ingest" / "oddsapi")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    names: set[str] = set()
    files = sorted(args.snapshots.glob("odds_*.json"))
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for event in payload.get("events", payload if isinstance(payload, list) else []):
            names.update(filter(None, (event.get("home_team"), event.get("away_team"))))
    print(f"{len(files)} snapshots, {len(names)} distinct team names\n")

    con = duckdb.connect(str(args.db), read_only=True)
    # school only. CFBD `alternateNames` is not indexed here on purpose: S4 found it carries
    # three-letter abbreviations that collide across schools, so it manufactures ambiguity.
    schools: dict[str, list[str]] = {}
    for school, in con.execute("SELECT school FROM core.dim_team WHERE school IS NOT NULL").fetchall():
        schools.setdefault(norm(school), []).append(school)

    one, many, none = [], [], []
    for name in sorted(names):
        hits = next((schools[c] for c in candidates(name) if c in schools), None)
        (none if hits is None else one if len(hits) == 1 else many).append((name, hits))

    print(f"  resolved to one team    {len(one):4d}")
    print(f"  resolved to MORE THAN 1 {len(many):4d}   <- a one-sided join would guess")
    print(f"  unresolved              {len(none):4d}")
    if args.list:
        for name, hits in many:
            print(f"    AMBIGUOUS  {name!r} -> {hits}")
        for name, _ in none:
            print(f"    UNRESOLVED {name!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
