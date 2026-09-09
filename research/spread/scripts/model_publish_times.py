# research/spread/scripts/model_publish_times.py
"""When does each Prediction Tracker constituent publish, relative to Monday?

The 6-hourly snapshots record, per model column, the first capture in which the column is
non-null for a slate. That is the model's publication time to within six hours -- the field
the archive lacks. Joined to the movement-skill screen, it answers whether the models that
lead the line are already in the Monday compile or arrive later in the week.

    python research/spread/scripts/model_publish_times.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_prediction_tracker_models as base  # noqa: E402
import eval_combination_sweep as sweep  # noqa: E402
import collect_line_timing as clt  # noqa: E402
from pt_rollover import NEW_SLATE_FRAC  # noqa: E402

ET = ZoneInfo("America/New_York")
OUT = base.OUT_DIR / "model_publish_times.csv"
NOT_MODELS = {"road", "home", "line", "lineopen", "linestd"} | base.MARKET_LINES


def _capture(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)


def first_seen(snapshots):
    """snapshots: [(stamp, frame)] in time order -> one row per (slate, model) first seen."""
    rows, prev_games, slate = [], set(), None
    seen: dict[str, datetime] = {}
    for stamp, df in snapshots:
        cap = _capture(stamp)
        games = set(zip(df.road, df.home))
        if not prev_games or len(games - prev_games) / max(len(games), 1) > NEW_SLATE_FRAC:
            et = cap.astimezone(ET)
            monday = (et - pd.Timedelta(days=et.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            slate, seen = monday.strftime("%Y-%m-%d"), {}
        prev_games = games
        et = cap.astimezone(ET)
        monday = (et - pd.Timedelta(days=et.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        for m in df.columns:
            if m in NOT_MODELS or m in seen or not m.startswith("line"):
                continue
            if pd.to_numeric(df[m], errors="coerce").notna().any():
                seen[m] = cap
                rows.append({"slate": slate, "model": m, "first_capture_utc": stamp,
                             "hours_after_monday_et": (et - monday).total_seconds() / 3600})
    return pd.DataFrame(rows)


def movement_rank():
    """Rank of every model by prior movement skill on the full archive (the E4 screen's order)."""
    hist, models = base.load()
    hist = hist[hist["line"].notna() & hist["lineopen"].notna()].copy()
    hist["y"] = -hist["line"].to_numpy(float)
    skill = base.prior_skill(hist, [m for m in models if m not in base.MARKET_LINES], "lineopen",
                             int(hist.season.max()))
    return pd.Series({m: i + 1 for i, m in enumerate(sorted(skill, key=skill.get))}, name="movement_rank")


def main() -> int:
    snaps = [(p.stem.split("_")[-1], pd.read_csv(p)) for p in sorted(clt.SNAP_DIR.glob("ncaapredictions_*.csv"))]
    fs = first_seen(snaps).merge(movement_rank(), left_on="model", right_index=True, how="left")
    fs.to_csv(OUT, index=False)
    top = fs[fs.movement_rank <= base.SCREEN_K]
    print(f"{fs.slate.nunique()} slates, {fs.model.nunique()} models seen; top-{base.SCREEN_K} by movement skill:")
    piv = top.pivot_table(index="model", columns="slate", values="hours_after_monday_et").round(1)
    print(piv.sort_index().to_string())
    for s, g in top.groupby("slate"):
        by_mon = int((g.hours_after_monday_et <= 20).sum())
        print(f"  slate {s}: {by_mon} of {len(g)} top-{base.SCREEN_K} present in the first Monday snapshot "
              f"(<= 20h); earliest capture this slate {g.hours_after_monday_et.min():.1f}h")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
