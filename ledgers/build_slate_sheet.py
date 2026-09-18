"""Turn this week's pred-tracker-model slate into a fillable bet sheet.

Reads `weekly_slate.py`'s latest snapshot (`{PROCESSED}/weekly_slate_latest.csv`, or the
`--book`-specific variant) and writes one row per game with a pick -- the side the model
likes, at that side's best book and price -- in the shape `ingest_bets.py` reads, plus a
leading `bet` column. Mark it `Y` for the games you're taking, leave the rest blank, then:

    python ledgers/ingest_bets.py --sheet <the sheet this prints> --dry-run

`ingest_bets.py` grades only rows marked bet in {y, yes, 1, true}; everything else is
skipped, not deleted -- rerun without --dry-run once the match report looks right.

Spread only: `weekly_slate.py`'s live book feed is spreads-only (the-odds-api's `markets`
is `spreads`), so there is no total or moneyline number to carry here yet.

Games with no pick (models flat against the book fair) are left off the sheet.

Never overwrites an existing `slate_latest.csv` -- that file is where your Y/N picks live,
and a second run (the line moved, you want a fresh look) would silently erase them. Pass
--force to refresh it anyway; the timestamped file next to it is written every run either way.

Usage:
    python ledgers/build_slate_sheet.py
    python ledgers/build_slate_sheet.py --book DraftKings
    python ledgers/build_slate_sheet.py --force
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from cfb_paths import INGEST, PROCESSED  # noqa: E402

SHEET_DIR = INGEST / "bet_history"
SOURCE = "pred_tracker_model"
COLUMNS = ["bet", "placed_at", "away", "home", "market", "side", "line", "odds",
           "stake", "book", "source", "notes", "kick_et"]


def build(slate: pd.DataFrame, generated_at: pd.Timestamp) -> pd.DataFrame:
    """One row per game with a pick: the model's side, at its book's number and price."""
    picked = slate[slate["side"].fillna("").astype(str).str.strip() != ""].copy()
    rows = []
    for r in picked.itertuples():
        kick_et = r.kick_et if pd.notna(getattr(r, "kick_et", None)) else ""
        edge = f"edge {r.edge:.1f}" if pd.notna(getattr(r, "edge", None)) else ""
        rows.append({
            "bet": "", "placed_at": generated_at.isoformat(timespec="minutes"),
            "away": r.road, "home": r.home, "market": "spread", "side": r.side,
            "line": r.side_line, "odds": r.side_odds, "stake": "",
            "book": r.side_book, "source": SOURCE, "notes": edge, "kick_et": kick_et,
        })
    return pd.DataFrame(rows, columns=COLUMNS)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--book", default=None,
                    help="use that one book's number/price instead of the best across books "
                         "(matches a weekly_slate_latest_<book>.csv on disk)")
    ap.add_argument("--force", action="store_true",
                    help="overwrite slate_latest.csv even if it already exists")
    args = ap.parse_args()

    suffix = f"_{args.book.lower()}" if args.book else ""
    src = PROCESSED / f"weekly_slate_latest{suffix}.csv"
    if not src.exists():
        raise SystemExit(f"{src} not found -- run "
                          f"research/spread/scripts/weekly_slate.py"
                          f"{' --book ' + args.book if args.book else ''} first")
    slate = pd.read_csv(src)
    generated_at = pd.Timestamp.now(tz="America/New_York")
    out = build(slate, generated_at)
    if out.empty:
        raise SystemExit(f"{src} has no picks (every game's `side` is blank)")

    SHEET_DIR.mkdir(parents=True, exist_ok=True)
    stamp = generated_at.strftime("%Y%m%dT%H%M")
    dated = SHEET_DIR / f"slate_{stamp}{suffix}.csv"
    out.to_csv(dated, index=False)

    latest = SHEET_DIR / f"slate_latest{suffix}.csv"
    if latest.exists() and not args.force:
        print(f"wrote {dated} ({len(out)} games)")
        print(f"{latest} already exists -- left alone so your Y/N picks aren't lost.\n"
              f"Fill in {dated.name} directly, or rerun with --force to refresh {latest.name}.")
        return
    out.to_csv(latest, index=False)
    print(f"wrote {dated} and {latest} ({len(out)} games)")
    print(f"mark `bet` Y on the ones you're taking, then:\n"
          f"  python ledgers/ingest_bets.py --sheet {latest} --dry-run")


def _check() -> None:
    slate = pd.DataFrame([
        {"road": "Furman", "home": "Tennessee", "side": "Tennessee", "side_line": -49.5,
         "side_odds": -115.0, "side_book": "DraftKings", "edge": 5.2, "kick_et": "Sat 7PM"},
        {"road": "Colorado", "home": "TCU", "side": "", "side_line": float("nan"),
         "side_odds": float("nan"), "side_book": "", "edge": 0.1, "kick_et": "Sat 3PM"},
    ])
    out = build(slate, pd.Timestamp("2026-09-18T12:00", tz="America/New_York"))
    assert len(out) == 1, "the flat game (blank side) must be dropped"
    row = out.iloc[0]
    assert row.away == "Furman" and row.home == "Tennessee" and row.market == "spread"
    assert row.side == "Tennessee" and row.line == -49.5 and row.odds == -115.0
    assert row.book == "DraftKings" and row.source == SOURCE and row.notes == "edge 5.2"
    assert row.bet == "" and row.stake == ""
    assert list(out.columns) == COLUMNS
    print("checks pass")


if __name__ == "__main__":
    _check()
    main()
