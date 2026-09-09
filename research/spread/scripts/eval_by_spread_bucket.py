"""How the movement model does by size of spread -- does its edge live in the blowouts?

The live slate's biggest model-vs-book gaps sit on very large numbers (Louisiana Tech +35.5,
Charlotte +47.5, Western Kentucky +41.5). Two reasons that is worth checking rather than assuming:
a point of spread is worth less the further you get from a pick'em, so equal "edge" in points is
not equal value; and a subgroup where the model looks strong is exactly where a forking-paths
error would hide.

Reads the walk-forward decontaminated predictions (amendment A6,
processed/pt_movement_preds_decon_wf.csv) and reports, per |opening spread| bucket, the same
quantities the registered runs report -- R^2 of the move, direction, CLV at the opener, and ATS at
the opener -- using eval_line_movement's own definitions so the numbers are comparable.

    python research/spread/scripts/eval_by_spread_bucket.py             # archive, opener anchor
    python research/spread/scripts/eval_by_spread_bucket.py --version-b  # live, Monday anchor

EXPLORATORY, and descriptive rather than a registered test. Decision 1 of the plan of record puts
every archive result outside the one confirmatory family (the version B E4 slope at the Monday
anchor). This is a subgroup breakdown of an existing result: it carries no pre-registered
expectation, no multiplicity correction across the buckets, and cannot on its own support a rule
like "bet the big spreads". Read it as a description of where the archive effect sits.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_line_movement as elm  # noqa: E402
import eval_prediction_tracker_models as base  # noqa: E402

PREDS = base.OUT_DIR / "pt_movement_preds_decon_wf.csv"
OUT = base.OUT_DIR / "pt_movement_by_spread.json"
BUCKETS = [(0, 3), (3, 7), (7, 14), (14, 21), (21, 28), (28, 35), (35, 99)]
THRESH = 1.0          # |predicted move|, matching the registered CLV tables' lower threshold
PREDICTOR = "E4"      # the graded predictor; E6 is retired from serving (amendment A7)


def version_b_frame():
    """The graded version B set, rebuilt with eval_version_b's own functions."""
    import duckdb
    import eval_version_b as vb
    log = pd.read_csv(vb.LOG)
    g = vb.monday_anchor(log)
    g["kick_utc"] = pd.to_datetime(g.kick, utc=True)
    g["close"] = [vb.close_from_history(e, k) for e, k in zip(g.event_id, g.kick_utc)]
    con = duckdb.connect(str(base.cfb_paths.DB_PATH), read_only=True)
    g["margin"] = vb.margins(g, vb.fetch_scores(con, sorted(set(g.kick_utc.dt.year))))
    return g[g.close.notna() & (g.kick_utc < datetime.now(timezone.utc))].copy()


def run_version_b() -> int:
    """Same buckets, live data. The anchor is Monday's line, not the opener."""
    d = version_b_frame()
    anchor, close, margin = d.line_pt.to_numpy(), d.close.to_numpy(), d.margin.to_numpy()
    pred = d[PREDICTOR].to_numpy()
    move, pm = close - anchor, pred - anchor
    absa = np.abs(anchor)
    weeks = d.week.nunique()

    print(f"version B: {len(d)} graded games, {weeks} week cluster(s), anchor = Monday's line")
    print("NO INTERVALS ARE SHOWN. One week cluster cannot support a cluster SE, and the whole")
    print("sample is below the >= 8 clusters amendment B3 requires before ANY verdict -- a")
    print("seven-way split of it is further from decidable still. Counts only.")
    print()
    print(f"{'|Monday|':>10} {'games':>6} {'bets':>6} {'dir':>7} {'CLV':>7} {'ATS':>7}")

    rows = []
    for lo, hi in BUCKETS:
        b = (absa >= lo) & (absa < hi)
        if not b.any():
            continue
        bet = b & (np.abs(pm) >= THRESH)
        side = np.sign(pm[bet])
        clv = side * move[bet]
        res = side * (margin[bet] - anchor[bet])
        keep = res != 0
        moved = bet & (move != 0)
        d_hit = float((np.sign(pm[moved]) == np.sign(move[moved])).mean()) if moved.any() else float("nan")
        ats = float((res[keep] > 0).mean()) if keep.any() else float("nan")
        label = f"{lo}-{hi}" if hi < 99 else f"{lo}+"
        print(f"{label:>10} {int(b.sum()):6d} {int(bet.sum()):6d} "
              f"{d_hit:7.1%} {clv.mean() if bet.any() else float('nan'):+7.2f} {ats:7.1%}")
        rows.append({"bucket": label, "games": int(b.sum()), "bets": int(bet.sum()),
                     "direction": d_hit, "clv": float(clv.mean()) if bet.any() else None,
                     "ats": ats, "weeks": int(weeks)})

    print()
    print("Largest bucket holds a single-digit number of bets. Nothing here is a finding, in")
    print("either direction -- it is the shape of the sample, recorded so the split exists when")
    print("the season has actually supplied clusters.")
    out = base.OUT_DIR / "version_b_by_spread.json"
    out.write_text(json.dumps({"predictor": PREDICTOR, "thresh": THRESH, "n_graded": int(len(d)),
                               "week_clusters": int(weeks), "readable": False,
                               "buckets": rows}, indent=2, default=float))
    print()
    print(f"wrote {out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--version-b", action="store_true",
                    help="live forward test, Monday anchor, instead of the archive")
    if ap.parse_args().version_b:
        return run_version_b()
    d = pd.read_csv(PREDS)
    open_m, close, margin = d["open"].to_numpy(), d["close"].to_numpy(), d["margin"].to_numpy()
    season, pred = d["season"].to_numpy(), d[PREDICTOR].to_numpy()
    move, pm = close - open_m, pred - open_m
    absopen = np.abs(open_m)

    print(f"{len(d)} games, {PREDICTOR} on the A6 walk-forward panel, "
          f"seasons {season.min()}-{season.max()}")
    print("R2 is of the move vs 'the line does not move'. CLV/ATS bet the model's side at the "
          f"opener when |predicted move| >= {THRESH:.0f}.\n")
    print(f"{'|open|':>10} {'games':>6} {'sd(move)':>9} {'R2':>7} {'bets':>6} "
          f"{'dir':>6} {'CLV':>7} {'CLV/sd':>7} {'95% CI':>16} {'ATS@open':>9} {'95% CI':>16}")

    rows = []
    for lo, hi in BUCKETS:
        b = (absopen >= lo) & (absopen < hi)
        if b.sum() < 30:
            continue
        r2 = 1 - float(((close - pred) ** 2)[b].mean()) / float(((close - open_m) ** 2)[b].mean())

        bet = b & (np.abs(pm) >= THRESH)
        moved = bet & (move != 0)
        direction = float((np.sign(pm[moved]) == np.sign(move[moved])).mean()) if moved.any() else np.nan

        side = np.sign(pm[bet])
        clv = side * move[bet]
        cm, cci, _ = base.wild_cluster_boot(clv, season[bet])
        res = side * (margin[bet] - open_m[bet])
        keep = res != 0
        ats = elm.cluster_rate((res[keep] > 0).astype(float), season[bet][keep])

        # CLV in points scales with how much the line moves at all, and big spreads move far
        # more, so the raw column flatters them. Divide by the bucket's own sd(move) to compare.
        sd_b = float(move[b].std())
        clv_sd = float(clv.mean()) / sd_b if sd_b else float("nan")
        label = f"{lo}-{hi}" if hi < 99 else f"{lo}+"
        print(f"{label:>10} {int(b.sum()):6d} {sd_b:9.2f} {r2:7.3f} {int(bet.sum()):6d} "
              f"{direction:6.1%} {clv.mean():+7.2f} {clv_sd:+7.3f} [{cci[0]:+6.2f},{cci[1]:+6.2f}] "
              f"{ats['rate']:9.1%} [{ats['lo']:6.1%},{ats['hi']:6.1%}]")
        rows.append({"bucket": label, "lo": lo, "hi": hi, "games": int(b.sum()),
                     "sd_move": sd_b, "clv_per_sd": clv_sd, "r2": r2, "bets": int(bet.sum()),
                     "direction": direction, "clv": float(clv.mean()),
                     "clv_lo": float(cci[0]), "clv_hi": float(cci[1]),
                     "ats_open": ats["rate"], "ats_lo": ats["lo"], "ats_hi": ats["hi"],
                     "pushes": int((~keep).sum())})

    # Value, not points. A point of spread buys less win probability the further from pick'em you
    # are, so equal CLV in points is not equal value across these buckets -- the ATS column is the
    # honest cross-bucket comparison, and even it says nothing about price.
    print()
    print("Raw CLV in POINTS is not comparable across buckets. Big-spread lines move far more")
    print("(sd(move) 5.34 at 35+ against 2.03 at 3-7), so more points are available to capture")
    print("regardless of skill, and a point out there is worth less win probability besides.")
    print("CLV/sd removes the first confound. It is flat in every bucket -- the model is not")
    print("better on blowouts, it is measured on a noisier line. Seven buckets, no multiplicity")
    print("correction, and the opener is a price PT timing cannot reach.")

    OUT.write_text(json.dumps({"predictor": PREDICTOR, "thresh": THRESH,
                               "n": int(len(d)), "buckets": rows}, indent=2, default=float))
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
