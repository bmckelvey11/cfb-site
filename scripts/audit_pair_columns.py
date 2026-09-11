"""Bidirectional column diff with fill rates, per GraphQL/REST concept pair.

This is the measurement behind section 3 of
`docs/superpowers/plans/2026-09-08-warehouse-rationalization-master.md` -- which side of a
pair holds a populated column the other lacks. The plan's tables were measured by hand;
this makes them reproducible, because R6 gates every drop on the survivor holding **every
populated column**, and that verdict has to be re-taken whenever either side is re-scraped.

    python scripts/audit_pair_columns.py                     # all 12 pairs, summary
    python scripts/audit_pair_columns.py --pair coach_season --verbose

**Name matching is a judgement call and this script does not make it.** The two transports
spell the same concept differently (`team_id` vs `team_teamId`, `season` vs `year`), so
columns are compared on a loose key -- lowercased, underscores dropped -- and anything left
exclusive is reported with its fill rate for a human to read. `--verbose` also prints
near-misses: exclusive columns on opposite sides that share a token, which is where a real
match usually hides. Like `audit_canonical_sources.py`, this supplies evidence and
deliberately does not pick a winner.

**The key fails in both directions and only one of them is visible here.** A false
*exclusive* -- same concept under two names -- is what near-misses are for
(`team_teamId` vs `team_id`). A false **shared** is the opposite and nothing below can see
it: `draft_team.nickname` exists on both sides, and holds the team's nickname on REST
(`Bengals`) and the location repeated on GraphQL (`Cincinnati`), with REST's value living
in GraphQL's `mascot`. That pair reads as shared and is not. Before a same-name column
counts toward R6's "survivor holds every populated column", read the values.
See docs/warehouse-drop-superseded-2026-09-10.md.

Fill rate is non-NULL over total rows. A column at 0.00 is a drop-list candidate (section
5), not evidence of exclusivity.

Read-only. Exits 0 always.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from cfb_paths import DATA_ROOT  # noqa: E402
from verify_warehouse_plan import PAIRS  # noqa: E402

# Carried on every staged table; never evidence about a source.
BOOKKEEPING = frozenset({"_source_file"})


def loose(name: str) -> str:
    return name.lower().replace("_", "")


def columns(con: duckdb.DuckDBPyConnection, schema: str, table: str) -> list[str]:
    return [r[0] for r in con.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = ? AND table_name = ? ORDER BY ordinal_position",
        [schema, table]).fetchall()]


def fills(con: duckdb.DuckDBPyConnection, schema: str, table: str,
          cols: list[str]) -> dict[str, float]:
    """Fill rate per column, in one pass rather than one query per column."""
    if not cols:
        return {}
    total = con.execute(f'SELECT count(*) FROM "{schema}"."{table}"').fetchone()[0]
    if not total:
        return {c: 0.0 for c in cols}
    exprs = ", ".join(f'count("{c}")' for c in cols)
    counts = con.execute(f'SELECT {exprs} FROM "{schema}"."{table}"').fetchone()
    return {c: n / total for c, n in zip(cols, counts)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", type=Path, default=DATA_ROOT / "cfb.duckdb")
    ap.add_argument("--pair", help="one concept name; default is all")
    ap.add_argument("--verbose", action="store_true",
                    help="name every exclusive column, and near-misses across the pair")
    args = ap.parse_args()

    con = duckdb.connect(str(args.db), read_only=True)
    pairs = [p for p in PAIRS if args.pair in (None, p[0])]
    if not pairs:
        print(f"no such pair: {args.pair}; known: {', '.join(p[0] for p in PAIRS)}")
        return 0

    print(f"{'concept':18s} {'gql-only':>9s} {'rest-only':>10s} {'shared':>7s}   "
          f"(populated exclusives in brackets)")
    for concept, gql, rest in pairs:
        gcols = [c for c in columns(con, "stg_gql", gql) if c not in BOOKKEEPING]
        rcols = [c for c in columns(con, "stg", rest) if c not in BOOKKEEPING]
        if not gcols or not rcols:
            print(f"{concept:18s} MISSING (stg_gql.{gql}={len(gcols)}, stg.{rest}={len(rcols)})")
            continue

        gkeys, rkeys = {loose(c) for c in gcols}, {loose(c) for c in rcols}
        gonly = [c for c in gcols if loose(c) not in rkeys]
        ronly = [c for c in rcols if loose(c) not in gkeys]
        gfill, rfill = fills(con, "stg_gql", gql, gonly), fills(con, "stg", rest, ronly)
        gpop = [c for c in gonly if gfill[c] > 0]
        rpop = [c for c in ronly if rfill[c] > 0]
        print(f"{concept:18s} {len(gonly):9d} {len(ronly):10d} "
              f"{len(gkeys & rkeys):7d}   [{len(gpop)} / {len(rpop)}]")

        if args.verbose:
            for label, cols, fill in (("gql-only ", gonly, gfill), ("rest-only", ronly, rfill)):
                for c in sorted(cols, key=lambda x: -fill[x]):
                    print(f"    {label} {c:44s} {fill[c]:.3f}")
            # An exclusive on each side sharing a token is usually the same concept spelled
            # two ways -- the case the loose key cannot catch and a human has to settle.
            for g in gonly:
                gt = {t for t in loose(g).replace("id", " id ").split() if len(t) > 3}
                for r in ronly:
                    if gt & {t for t in loose(r).replace("id", " id ").split() if len(t) > 3}:
                        print(f"    near-miss  stg_gql.{g}  ~  stg.{r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
