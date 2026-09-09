"""When does the spread actually move? How much is left at the price you can reach?

The archive result lives at the OPENER, and the openers in this data post in April for games
played in September. The whole tree turns on one operational question that has never been
measured directly: by the time you can act, how much of the open-to-close move has already
happened?

This reads the Action Network tick histories already in the warehouse (`stg.an_history_tick`,
one row per price change per book) and, for each game, reconstructs the consensus spread's path
from its first tick to its last pre-kickoff tick. For a grid of moments before kickoff it reports
the share of the total move already complete -- and, because that is the live question, the share
still remaining at Monday 00:00 ET of game week, which is where version B anchors.

    python research/spread/scripts/eval_timing_decay.py
    python research/spread/scripts/eval_timing_decay.py --book 75

DESCRIPTIVE. No model, no fitting, no bet. This measures the market's own behaviour, so it does
not need a pre-registration -- but it also cannot on its own establish that anything is bettable.
It bounds where an edge could possibly live.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_prediction_tracker_models as base  # noqa: E402

OUT = base.OUT_DIR / "an_timing_decay.json"
ET = "America/New_York"
MIN_MOVE = 1.0        # below this the "share of the move" ratio is noise over noise

# Moments before kickoff, in hours. Openers post months out, so the grid is coarse then fine.
MARKS = [(24 * 120, "120 days"), (24 * 60, "60 days"), (24 * 30, "30 days"), (24 * 14, "14 days"),
         (24 * 7, "7 days"), (24 * 5, "5 days"), (24 * 3, "3 days"), (48, "2 days"),
         (24, "1 day"), (12, "12 hours"), (6, "6 hours"), (1, "1 hour")]


def load(book: str):
    con = duckdb.connect(str(base.cfb_paths.DB_PATH), read_only=True)
    ticks = con.execute("""
        select event_id, updated_at, line
        from stg.an_history_tick
        where market_type = 'spread' and side = 'home' and period = 'event'
          and book_id = ? and line is not null
    """, [book]).df()
    kicks = con.execute("""
        select distinct event_id, start_time from stg.an_scoreboard where start_time is not null
    """).df()
    return ticks, kicks


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--book", default="15", help="Action Network book id (15 = consensus)")
    args = ap.parse_args()

    ticks, kicks = load(args.book)
    if ticks.empty:
        print(f"no spread ticks for book {args.book}")
        return 1
    df = ticks.merge(kicks, on="event_id", how="inner")
    df["updated_at"] = pd.to_datetime(df.updated_at, utc=True)
    df["start_time"] = pd.to_datetime(df.start_time, utc=True)
    df = df[df.updated_at < df.start_time].sort_values(["event_id", "updated_at"])
    df["hours_before"] = (df.start_time - df.updated_at).dt.total_seconds() / 3600

    rows, per_event = [], []
    for eid, g in df.groupby("event_id"):
        open_v, close_v = float(g.line.iloc[0]), float(g.line.iloc[-1])
        move = close_v - open_v
        if abs(move) < MIN_MOVE:
            continue
        kick = g.start_time.iloc[0]
        rec = {"event_id": int(eid), "ticks": len(g), "open": open_v, "close": close_v,
               "move": move, "opened_days_out": float(g.hours_before.iloc[0] / 24)}
        for hrs, label in MARKS:
            at = g[g.hours_before >= hrs]
            # the line as it stood that far out; if the market had not opened yet, skip
            rec[label] = (float(at.line.iloc[-1]) - open_v) / move if len(at) else np.nan
        # the operational moment: Monday 00:00 ET of the week the game kicks
        kick_et = kick.tz_convert(ET)
        monday = (kick_et.normalize() - pd.Timedelta(days=int(kick_et.dayofweek))).tz_convert("UTC")
        at_mon = g[g.updated_at <= monday]
        rec["monday"] = (float(at_mon.line.iloc[-1]) - open_v) / move if len(at_mon) else np.nan
        per_event.append(rec)

    e = pd.DataFrame(per_event)
    print(f"book {args.book}: {len(e)} games with a total move of at least {MIN_MOVE:.0f} point "
          f"(of {df.event_id.nunique()} with ticks)")
    print(f"median |total move| {e.move.abs().median():.1f} pts, "
          f"median line age at first tick {e.opened_days_out.median():.0f} days before kickoff\n")
    print(f"{'moment':>12} {'games':>6} {'share of move done':>19} {'still to come':>15}")
    for _, label in MARKS:
        v = e[label].dropna()
        if len(v) < 20:
            continue
        print(f"{label:>12} {len(v):6d} {v.median():18.0%} {1 - v.median():15.0%}")
        rows.append({"moment": label, "games": int(len(v)), "share_done": float(v.median())})

    # Net share done can read 100% while the line still wanders and comes back. Gross movement
    # after Monday separates "nothing happens" from "nothing happens ON NET" -- only the second
    # leaves a better number on the table.
    gross = []
    for eid, g in df.groupby("event_id"):
        kick_et = g.start_time.iloc[0].tz_convert(ET)
        monday = (kick_et.normalize() - pd.Timedelta(days=int(kick_et.dayofweek))).tz_convert("UTC")
        after = g[g.updated_at > monday]
        if len(after) < 2:
            continue
        close_v = float(g.line.iloc[-1])
        gross.append({"event_id": int(eid), "ticks_after_monday": len(after),
                      "max_dev_from_close": float((after.line - close_v).abs().max()),
                      "range_after_monday": float(after.line.max() - after.line.min())})
    gr = pd.DataFrame(gross)

    mon = e["monday"].dropna()
    print(f"\n{'MONDAY 00:00 ET':>12} {len(mon):6d} {mon.median():18.0%} {1 - mon.median():15.0%}"
          "   <- where version B anchors")
    print(f"\nGames with at least a quarter of the move still to come on Monday: "
          f"{(mon < 0.75).mean():.0%}")
    print(f"Games already fully moved (or past) by Monday:                     "
          f"{(mon >= 1.0).mean():.0%}")
    if len(gr):
        print()
        print(f"After Monday the line is not frozen, it is just directionless: median "
              f"{gr.ticks_after_monday.median():.0f} further price changes per game, straying a "
              f"median {gr.max_dev_from_close.median():.1f} points from where it closes "
              f"(range {gr.range_after_monday.median():.1f}).")
        print(f"Games whose in-week range is at least 1 point: "
              f"{(gr.range_after_monday >= 1).mean():.0%}. That is shopping room, not a forecast.")

    print("\nShare of move done is a median across games; each game's own total move is the")
    print("denominator, so a game that barely moved cannot dominate one that moved five points.")

    OUT.write_text(json.dumps({"book": args.book, "games": int(len(e)), "min_move": MIN_MOVE,
                               "median_abs_move": float(e.move.abs().median()),
                               "median_open_days_out": float(e.opened_days_out.median()),
                               "marks": rows,
                               "monday_share_done": float(mon.median()),
                               "monday_quarter_left": float((mon < 0.75).mean()),
                               "monday_fully_moved": float((mon >= 1.0).mean()),
                               "after_monday_median_ticks": (float(gr.ticks_after_monday.median()) if len(gr) else None),
                               "after_monday_median_range": (float(gr.range_after_monday.median()) if len(gr) else None),
                               "after_monday_range_ge_1": (float((gr.range_after_monday >= 1).mean()) if len(gr) else None)},
                              indent=2, default=float))
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
