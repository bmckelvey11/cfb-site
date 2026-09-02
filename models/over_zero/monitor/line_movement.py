"""Line movement for over-zero picks: first snapshot of the week vs latest.

Reads the append-only prediction log written by v1/predict_week.py and reports,
per qualifying game, how spread/total/bias moved between the earliest capture
this week and the most recent one.

    python models/over_zero/monitor/line_movement.py [--week-start YYYY-MM-DD]
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from cfb_paths import PROCESSED  # noqa: E402

PRED = PROCESSED / "over_zero" / "predictions.csv"


def load(week_start: pd.Timestamp) -> pd.DataFrame:
    d = pd.read_csv(PRED, parse_dates=["run_at", "game_date"])
    d["run_at"] = d["run_at"].dt.tz_convert("UTC")
    return d[d["run_at"] >= week_start]


def movement(d: pd.DataFrame) -> pd.DataFrame:
    first, last = d["run_at"].min(), d["run_at"].max()
    # ponytail: pick set has been stable; union across snapshots so an entry/exit still shows.
    picks = set(d.loc[d["pick"].notna(), "game_id"])
    cols = ["game_id", "game_date", "home_team", "away_team",
            "spread", "total", "dog_implied", "bias", "pick"]
    a = d[(d.run_at == first) & d.game_id.isin(picks)][cols].set_index("game_id")
    b = d[(d.run_at == last) & d.game_id.isin(picks)][cols].set_index("game_id")

    out = pd.DataFrame({
        "game": a.away_team + " @ " + a.home_team,
        "kickoff": a.game_date.dt.date,
        "spread_open": a.spread, "spread_now": b.spread,
        "d_spread": b.spread - a.spread,
        "total_open": a.total, "total_now": b.total,
        "d_total": b.total - a.total,
        "dog_open": a.dog_implied, "dog_now": b.dog_implied,
        "bias_open": a.bias, "bias_now": b.bias,
        "d_bias": (b.bias - a.bias).round(3),
        "pick_open": a.pick.fillna("-"), "pick_now": b.pick.fillna("-"),
    })
    out.attrs["first"], out.attrs["last"] = first, last
    return out.sort_values("d_bias")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--week-start", default=None,
                   help="UTC date to treat as start of week (default: Monday of current week)")
    args = p.parse_args()
    if args.week_start:
        ws = pd.Timestamp(args.week_start, tz="UTC")
    else:
        now = pd.Timestamp.now(tz="UTC").normalize()
        ws = now - pd.Timedelta(days=now.dayofweek)

    d = load(ws)
    if d.empty:
        sys.exit(f"no snapshots at or after {ws.date()} in {PRED}")
    m = movement(d)

    print(f"over-zero line movement  {m.attrs['first']:%Y-%m-%d %H:%MZ} -> "
          f"{m.attrs['last']:%Y-%m-%d %H:%MZ}   ({d.run_at.nunique()} snapshots, {len(m)} picks)")
    print("for the OVER: total up = worse price, bias down = weaker edge\n")
    show = ["game", "kickoff", "spread_open", "spread_now", "d_spread",
            "total_open", "total_now", "d_total", "bias_open", "bias_now", "d_bias", "pick_now"]
    print(m[show].to_string(index=False))

    moved = m[(m.d_spread != 0) | (m.d_total != 0)]
    print(f"\n{len(moved)}/{len(m)} picks moved; "
          f"net total {m.d_total.sum():+.1f}, mean bias {m.d_bias.mean():+.3f}")
    played = m[pd.to_datetime(m.kickoff) < pd.Timestamp.now().normalize()]
    if len(played):
        print(f"already played (line closed): {', '.join(played.game)}")
    dropped = m[m.pick_now == "-"]
    if len(dropped):
        print(f"no longer qualifying: {', '.join(dropped.game)}")

    dest = PRED.parent / "line_movement.csv"
    m.to_csv(dest)
    print(f"wrote {dest}")


if __name__ == "__main__":
    main()
