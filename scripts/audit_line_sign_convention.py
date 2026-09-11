"""Is every book in ``core.fact_game_line`` quoting a **home-relative** spread?

`GameRecord.spread` and `core.fact_game.selected_spread` are home-relative: negative when
the home team is favoured. `_build_fact_game_line` inherits that from CFBD's REST payload
without checking it, and `_merge_game_lines` then carried 8,575 rows in from the
ActionNetwork tape -- circa, fanduel, betmgm, bet365 and pinnacle -- that no code had ever
compared against the convention.

An inverted book is silent. Nothing raises, no row count moves; a backtest just reads the
favourite as the underdog for that book and the result looks like a bad model rather than a
bad sign.

    python scripts/audit_line_sign_convention.py
    python scripts/audit_line_sign_convention.py --min-rows 20

Two independent checks, because either alone has an excuse:

* **Against a reference book on the same game.** A book that disagrees on *sign* with the
  consensus of four long-running books is either inverted or quoting a different game. Read
  the `|ref|>3` column, not the raw count: books straddle zero on pick'em games, so a
  disagreement at -1.5 vs +1.5 is normal and one at -14 vs +14 is not.
* **Against the realised margin.** `spread + (home_points - away_points)` averages to ~0
  when the spread is home-relative, because the two cancel. An inverted book lands at
  roughly *twice* the mean spread instead, and its cover rate goes to ~0% or ~100%.

Read-only. Exits 0 always -- it reports, it does not decide. `tests/test_core_merges.py`
is where the verdict is pinned.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from cfb_paths import DATA_ROOT  # noqa: E402

# Long-running books with broad coverage, used only to form a per-game reference spread.
# Averaged rather than picked, so one stale capture cannot flip the reference's sign.
REFERENCE = ("consensus", "bovada", "espn bet", "teamrankings")

REF_CTE = f"""
  WITH ref AS (
    SELECT game_id, avg(spread_close) AS ref_spread
    FROM core.fact_game_line
    WHERE provider_key IN ({", ".join(repr(p) for p in REFERENCE)})
      AND spread_close IS NOT NULL
    GROUP BY 1
  )
"""


def against_reference(con: duckdb.DuckDBPyConnection, min_rows: int) -> list[tuple]:
    return con.execute(
        REF_CTE
        + """
        SELECT l.provider_key,
               count(*) AS n,
               count(*) FILTER (
                 WHERE sign(l.spread_close) = -sign(r.ref_spread) AND r.ref_spread <> 0
               ) AS opposite,
               count(*) FILTER (
                 WHERE sign(l.spread_close) = -sign(r.ref_spread) AND abs(r.ref_spread) > 3
               ) AS opposite_clear,
               round(avg(abs(l.spread_close - r.ref_spread)), 3) AS mean_abs_diff
        FROM core.fact_game_line l JOIN ref r USING (game_id)
        WHERE l.spread_close IS NOT NULL
        GROUP BY 1 HAVING count(*) >= ? ORDER BY 2 DESC
        """,
        [min_rows],
    ).fetchall()


def against_margin(con: duckdb.DuckDBPyConnection, min_rows: int) -> list[tuple]:
    return con.execute(
        """
        SELECT l.provider_key,
               count(*) AS n,
               round(100.0 * count(*) FILTER (
                 WHERE (f.home_points - f.away_points) + l.spread_close > 0
               ) / count(*), 1) AS cover_pct,
               round(avg(l.spread_close + (f.home_points - f.away_points)), 3) AS mean_resid
        FROM core.fact_game_line l JOIN core.fact_game f USING (game_id)
        WHERE l.spread_close IS NOT NULL
          AND f.home_points IS NOT NULL AND f.away_points IS NOT NULL
        GROUP BY 1 HAVING count(*) >= ? ORDER BY 2 DESC
        """,
        [min_rows],
    ).fetchall()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", type=Path, default=DATA_ROOT / "cfb.duckdb")
    ap.add_argument("--min-rows", type=int, default=20,
                    help="skip books with fewer graded rows than this")
    args = ap.parse_args()

    con = duckdb.connect(str(args.db), read_only=True)
    try:
        print("against a reference book on the same game "
              f"({'/'.join(REFERENCE)}, averaged)")
        print(f"  {'provider':32s} {'rows':>6s} {'opp':>5s} {'opp|ref|>3':>11s} "
              f"{'mean|diff|':>10s}")
        for key, n, opp, opp_clear, diff in against_reference(con, args.min_rows):
            flag = "  <-- INVERTED?" if opp_clear > n * 0.5 else ""
            print(f"  {key:32s} {n:6d} {opp:5d} {opp_clear:11d} {diff:10.3f}{flag}")

        print()
        print("against the realised margin -- mean_resid ~ 0 means home-relative")
        print(f"  {'provider':32s} {'rows':>6s} {'cover%':>7s} {'mean_resid':>11s}")
        for key, n, cover, resid in against_margin(con, args.min_rows):
            flag = "  <-- INVERTED?" if cover is not None and (cover < 20 or cover > 80) else ""
            print(f"  {key:32s} {n:6d} {cover:7.1f} {resid:11.3f}{flag}")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
