"""Audit the game_id joins in the parsed Greenline archive against CFBD.

`parse_greenline_history.py` attaches a CFBD `game_id` to each archive slot by school
name. Name matching accepts any shared non-weak token (`strong()` in
`match_greenline_books.py`), so "Eastern Kentucky" and "Western Kentucky" overlap on
`kentucky`, and "North Texas Mean Green" and "Texas" overlap on `texas`. When PFF's
home/away disagrees with CFBD the orientation-sensitive week-scoped pass misses, the
season-wide fallback returns exactly one *wrong* candidate, and `len(best) == 1` locks
it in silently.

Neither a duplicate-`game_id` scan nor a token-overlap scan finds that reliably: a wrong
match that shares tokens and does not collide with another slot is invisible to both.
Scores are the complete test -- they come from PFF, independently of the join, so a slot
whose points cannot be reconciled with its CFBD game's points is matched to the wrong
game.

The orientation flip is allowed (second branch below): PFF and CFBD disagree about who
hosted several 2020 games, which is a labelling difference, not a wrong game.

Usage:
    python research/totals/scripts/audit_archive_joins.py
    python research/totals/scripts/audit_archive_joins.py --self-check

Exit code is 1 when any slot fails, so this can gate a re-parse.
"""

from __future__ import annotations

import argparse
import sys

import duckdb
import pandas as pd

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[3]))

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))

from cfb_paths import DB_PATH, INGEST  # noqa: E402
from match_greenline_books import toks  # noqa: E402
from parse_greenline_history import same_school  # noqa: E402

ARCHIVE = INGEST / "pff_scoreboard" / "greenline_history_archive.csv"

# A slot is one (game_id, week, home, away) the archive claims. Points come from PFF, so
# they are independent of the join and can referee it.
AUDIT_SQL = """
WITH a AS (
    SELECT DISTINCT game_id::BIGINT AS gid, week, home_team AS ht, away_team AS at_,
           home_points AS hp, away_points AS ap
    FROM archive
    WHERE game_id IS NOT NULL AND home_points IS NOT NULL
)
SELECT a.gid, a.week, a.at_ AS pff_away, a.ht AS pff_home, a.ap AS pff_ap, a.hp AS pff_hp,
       g.away_team AS cfbd_away, g.home_team AS cfbd_home,
       g.away_points AS cfbd_ap, g.home_points AS cfbd_hp,
       (a.ap = g.home_points AND a.hp = g.away_points) AS orientation_flipped
FROM a JOIN core.fact_game g ON g.game_id = a.gid
WHERE NOT ((a.ap = g.away_points AND a.hp = g.home_points)
        OR (a.ap = g.home_points AND a.hp = g.away_points))
ORDER BY a.gid
"""

FLIP_SQL = AUDIT_SQL.replace(
    "WHERE NOT ((a.ap = g.away_points AND a.hp = g.home_points)\n"
    "        OR (a.ap = g.home_points AND a.hp = g.away_points))",
    "WHERE a.ap = g.home_points AND a.hp = g.away_points AND a.ap <> a.hp",
)


TRANSPOSE_SQL = """
SELECT DISTINCT a.game_id::BIGINT AS gid, a.week, a.home_team AS ht, a.away_team AS at_,
       a.home_points AS hp, a.away_points AS ap,
       g.home_team AS gh, g.away_team AS ga, g.home_points AS ghp, g.away_points AS gap
FROM archive a JOIN core.fact_game g ON g.game_id = a.game_id
WHERE a.game_id IS NOT NULL AND a.home_points IS NOT NULL
  AND a.home_points <> a.away_points
"""


def transposed(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Slots whose team-name columns contradict their own scores.

    A wrong-game join is not the only way a row can lie about who did what. PFF_hist had
    one game -- Marshall 59, Eastern Kentucky 0 -- joined to the right CFBD game with its
    `Home Team`/`Away Team` labels swapped, so the archive claimed Marshall scored 0. The
    points still lined up with CFBD positionally, which is exactly why the score check
    above cannot see it: only the names were wrong.

    Names must be compared with the parser's alias-aware `toks`, not raw tokens --
    Ole Miss/Mississippi, UL Monroe/Louisiana-Monroe and Hawai'i/Hawaii all fail a naive
    comparison and would swamp this in false positives.
    """
    rows = con.sql(TRANSPOSE_SQL).df()
    out = []
    for r in rows.itertuples():
        ht = toks(r.ht)
        names_flipped = (same_school(ht, toks(r.ga))
                         and not same_school(ht, toks(r.gh)))
        if names_flipped and r.hp == r.ghp and r.ap == r.gap:
            out.append({"gid": r.gid, "week": r.week,
                        "archive": f"{r.at_} @ {r.ht}", "cfbd": f"{r.ga} @ {r.gh}",
                        "archive_pts": f"{r.ap}-{r.hp}", "cfbd_pts": f"{r.gap}-{r.ghp}"})
    return pd.DataFrame(out)


def audit(con: duckdb.DuckDBPyConnection) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """Return (mismatched slots, orientation-flipped slots, slots checked)."""
    # read_csv_auto's path cannot be a prepared parameter, so it is quoted inline.
    path = str(ARCHIVE).replace("'", "''")
    con.execute(
        f"CREATE OR REPLACE TEMP VIEW archive AS SELECT * FROM read_csv_auto('{path}')"
    )
    checked = con.sql(
        "SELECT count(*) FROM (SELECT DISTINCT game_id, week, home_team, away_team "
        "FROM archive WHERE game_id IS NOT NULL AND home_points IS NOT NULL)"
    ).fetchone()[0]
    return con.sql(AUDIT_SQL).df(), con.sql(FLIP_SQL).df(), checked


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-check", action="store_true", help="run the built-in check")
    args = ap.parse_args()
    if args.self_check:
        self_check()
        return 0

    con = duckdb.connect(str(DB_PATH), read_only=True)
    bad, flipped, checked = audit(con)

    print(f"archive: {ARCHIVE}")
    print(f"slots checked (game_id + final score present): {checked}\n")

    print(f"WRONG GAME -- points irreconcilable with the joined CFBD game: {len(bad)}")
    if len(bad):
        print(bad.to_string(index=False, max_colwidth=28))
    print()
    print(f"home/away disagrees with CFBD, same game (allowed): {len(flipped)}")
    if len(flipped):
        print(flipped[["gid", "week", "pff_away", "pff_home",
                       "cfbd_away", "cfbd_home"]].to_string(index=False, max_colwidth=28))

    swapped = transposed(con)
    print()
    print(f"TEAM NAMES TRANSPOSED -- names contradict the row's own scores: {len(swapped)}")
    if len(swapped):
        print(swapped.to_string(index=False, max_colwidth=32))

    return 1 if (len(bad) or len(swapped)) else 0


def self_check() -> None:
    """The predicate must clear a correct join, clear a pure flip, and fail a wrong game."""
    con = duckdb.connect()
    con.execute("""
        CREATE SCHEMA core;
        CREATE TABLE core.fact_game (game_id BIGINT, away_team VARCHAR, home_team VARCHAR,
                                     away_points INT, home_points INT);
        INSERT INTO core.fact_game VALUES
            (1, 'UTEP', 'Texas', 3, 59),          -- the game the bad slot grabbed
            (2, 'North Texas', 'UTEP', 45, 43),   -- the game it should have grabbed
            (3, 'Rice', 'Tulane', 10, 20),
            -- right game, but the archive row below labels the host Eastern Kentucky
            -- while booking the home score as Marshall's 59.
            (4, 'Eastern Kentucky', 'Marshall', 0, 59);
    """)
    con.execute("""
        CREATE TABLE archive (game_id BIGINT, week INT, home_team VARCHAR,
                              away_team VARCHAR, home_points INT, away_points INT);
        INSERT INTO archive VALUES
            (3, 5, 'Tulane', 'Rice', 20, 10),            -- exact agreement -> pass
            (2, 15, 'North Texas', 'UTEP', 45, 43),      -- flipped labels -> pass
            (1, 15, 'North Texas', 'UTEP', 45, 43),      -- wrong game      -> FAIL
            (4, 1, 'Eastern Kentucky', 'Marshall', 59, 0); -- names transposed -> FAIL
    """)
    bad = con.sql(AUDIT_SQL).df()
    assert list(bad["gid"]) == [1], f"expected only gid 1 to fail, got {list(bad['gid'])}"

    flipped = con.sql(FLIP_SQL).df()
    assert list(flipped["gid"]) == [2], f"expected gid 2 flipped, got {list(flipped['gid'])}"

    # The transposition is invisible to the score check -- gid 4 agrees with CFBD
    # positionally -- so it needs its own detector.
    assert 4 not in list(bad["gid"]), "score check should not see the transposition"
    swapped = transposed(con)
    assert list(swapped["gid"]) == [4], f"expected gid 4 transposed, got {swapped.to_dict()}"

    print("self-check OK: correct join passes, pure flip passes, "
          "wrong game fails, transposed names fail")


if __name__ == "__main__":
    raise SystemExit(main())
