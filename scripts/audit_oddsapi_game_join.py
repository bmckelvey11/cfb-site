"""Do the-odds-api events land on exactly one `stg.games` row?

`audit_oddsapi_team_names.py` answered half of `#oddsapi-warehouse-wiring`'s blocker: names
resolve to `core.dim_team`. This answers the other half -- whether an event resolves to a
*game*. A flatten needs `(home, away, kickoff)` to pick one `gameId`, and the failure that
matters is not "no match" (loud, fixable) but "more than one" (silent, and a load would
pick arbitrarily).

Two measurements, kept apart on purpose:

**Pairing.** Resolve both team names, then look for `stg.games` rows holding that unordered
pair in the season. One / more than one / none -- and the delta is *not* used to
disambiguate, so the pair's own identifying power is what gets measured.

**Drift.** For events that paired to exactly one game, the distribution of
`commence_time - startDate`. That distribution is the answer to "how much kickoff drift",
rather than a tolerance assumed up front and then tuned until the answer looks good.

The three names `audit_oddsapi_team_names.py` found unresolved are aliased here so a known
name defect does not contaminate the pairing count. That is a measurement convenience, not
a production mapping.

    python scripts/audit_oddsapi_game_join.py
    python scripts/audit_oddsapi_game_join.py --season 2026 --list

Read-only, offline. Exits 0 always.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from audit_oddsapi_team_names import candidates, norm  # noqa: E402
from cfb_paths import DATA_ROOT  # noqa: E402

# Measured 2026-09-10 by audit_oddsapi_team_names.py: the only three snapshot names with no
# core.dim_team row under a mascot strip.
ALIASES = {"appalachian state": "app state",
           "southern mississippi": "southern miss",
           "umass": "massachusetts"}


def resolve(name: str, schools: dict[str, list[int]]) -> list[int] | None:
    for cand in candidates(name):
        for key in (cand, ALIASES.get(cand, cand)):
            if key in schools:
                return schools[key]
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", type=Path, default=DATA_ROOT / "cfb.duckdb")
    ap.add_argument("--snapshots", type=Path, default=DATA_ROOT / "ingest" / "oddsapi")
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    con = duckdb.connect(str(args.db), read_only=True)
    schools: dict[str, list[int]] = {}
    for tid, school in con.execute(
            "SELECT team_id, school FROM core.dim_team WHERE school IS NOT NULL").fetchall():
        schools.setdefault(norm(school), []).append(tid)

    games = con.execute("""
        SELECT "gameId", "homeTeamId", "awayTeamId", "startDate", "neutralSite",
               "startTimeTBD", "seasonType"
        FROM stg.games WHERE season = ?""", [args.season]).fetchall()
    by_pair: dict[frozenset, list[tuple]] = {}
    for g in games:
        by_pair.setdefault(frozenset((g[1], g[2])), []).append(g)

    events: dict[str, dict] = {}
    for path in sorted(args.snapshots.glob("odds_*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for event in payload.get("events", []):
            events[event["id"]] = event          # dedupe repeated snapshots of one event
    print(f"{len(events)} distinct events, {len(games):,} stg.games rows in {args.season}\n")

    one, many, none, unresolved = [], [], [], []
    for event in events.values():
        home, away = resolve(event["home_team"], schools), resolve(event["away_team"], schools)
        if not home or not away:
            unresolved.append(event)
            continue
        hits = by_pair.get(frozenset((home[0], away[0])), [])
        (none if not hits else one if len(hits) == 1 else many).append((event, hits))

    print("[pairing] on the unordered team pair alone, kickoff NOT used")
    print(f"  exactly one game      {len(one):4d}")
    print(f"  MORE THAN ONE         {len(many):4d}   <- a load would pick arbitrarily")
    print(f"  no game               {len(none):4d}")
    print(f"  name unresolved       {len(unresolved):4d}")

    deltas = []
    seen = Counter()
    for event, hits in one:
        game = hits[0]
        commence = con.execute("SELECT ?::TIMESTAMPTZ", [event["commence_time"]]).fetchone()[0]
        deltas.append((commence - game[3]).total_seconds() / 60)
        seen["neutral_site"] += bool(game[4])
        seen["start_time_tbd"] += bool(game[5])
        seen[f"season_type:{game[6]}"] += 1

    if deltas:
        deltas.sort()
        exact = sum(1 for d in deltas if d == 0)
        print(f"\n[drift] commence_time - startDate over {len(deltas)} paired events, minutes")
        print(f"  exactly 0      {exact}/{len(deltas)}")
        print(f"  min / median / max   {deltas[0]:.0f} / {deltas[len(deltas)//2]:.0f} / {deltas[-1]:.0f}")
        print(f"  |delta| > 60         {sum(1 for d in deltas if abs(d) > 60)}")

    # The snapshot sample is one week of one season, so it cannot show how often the team
    # pair stops being unique. That ceiling is a property of the schedule and is measurable
    # over every season on disk.
    ceiling = con.execute("""
        WITH p AS (
          SELECT season, count(*) AS n
          FROM stg.games
          WHERE season >= 2015
            AND "homeClassification" = 'fbs' AND "awayClassification" = 'fbs'
          GROUP BY season, least("homeTeamId", "awayTeamId"), greatest("homeTeamId", "awayTeamId"))
        SELECT sum(CASE WHEN n > 1 THEN 1 ELSE 0 END), count(*) FROM p""").fetchone()
    print("\n[ceiling] FBS-vs-FBS pair-seasons since 2015 where the pair meets twice")
    print(f"  {ceiling[0]:,} of {ceiling[1]:,} ({100 * ceiling[0] / ceiling[1]:.2f}%) -- conference")
    print("  title-game and playoff rematches, always weeks apart, so a kickoff tiebreak")
    print("  separates them. That is why a load should pair first and use kickoff only to split.")

    print("\n[what the matched set actually contains]")
    for key in sorted(seen):
        print(f"  {key:24s} {seen[key]}")
    print("  a zero here means that case is UNTESTED by this sample, not that it is clean")

    if args.list:
        for event, hits in many:
            print(f"  AMBIGUOUS  {event['away_team']} @ {event['home_team']} -> "
                  f"{[h[0] for h in hits]}")
        for event, _ in none:
            print(f"  NO GAME    {event['away_team']} @ {event['home_team']} "
                  f"{event['commence_time']}")
        for event in unresolved:
            print(f"  NO NAME    {event['away_team']} @ {event['home_team']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
