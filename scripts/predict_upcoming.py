"""Predict spreads for the upcoming week from a live Prediction Tracker snapshot.

READ THIS BEFORE USING THE OUTPUT.

  1. Against the CLOSING line there is no edge. Ten combination rules were tried; the best
     Holm-adjusted p is 0.4865. If the number you can actually bet is the close, this
     predicts nothing. See docs/prediction-tracker-findings.md.
  2. Against the OPENING line the measured effect is real (-2.615 MSE, 20 of 20 seasons)
     but it is an UPPER BOUND, not a strategy: the historical archive carries no
     publication timestamp, so it cannot be shown the forecast existed before the open.
  3. What is different now: snapshots ARE timestamped. A prediction written today can be
     scored against a line that moves later. That forward test is the point of this script.
     The log it appends to matters more than the table it prints.

SIGN CONVENTION -- the thing most likely to silently invert every number here. Prediction
Tracker publishes spreads as "points the home team is favoured by" (positive = home
favoured). build_prediction_tracker.clean_cells NEGATES every line* column except linestd
when building the archive, so the archive runs the opposite way and `y ~ -line`. The live
snapshot is raw, so it must be flipped before it touches any analysis code. Verified
against archive rows with known outcomes (Duke home vs Florida St. 2001, archive line
+32.0, Duke lost by 42).

Serves E4, the screened equal-weighted consensus: pre-registered, never selected on, and
73% of its effect survives decontamination. E14 (complete subset regression) has a larger
effect but is the selection-conditional winner of an eight-member family and is roughly
half market proxying, so it is reported beside E4 rather than instead of it.

    python scripts/predict_upcoming.py
    python scripts/predict_upcoming.py --snapshot <path>
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
import eval_prediction_tracker_models as base  # noqa: E402
import eval_combination_sweep as sweep  # noqa: E402
from build_prediction_tracker import UNSIGNED_LINES  # noqa: E402

SNAP_DIR = base.cfb_paths.RAW / "pt_snapshots"
LOG = base.OUT_DIR / "pt_upcoming_predictions.csv"

# Not models. Both reproduce the market line under a model name, so they would top any
# skill screen and consume slots in the K=20. See docs/prediction-tracker-findings.md.
MARKET_LINES = {"lineca", "linemidweek"}


def latest_snapshot():
    snaps = sorted(SNAP_DIR.glob("ncaapredictions_*.csv"))
    if not snaps:
        raise SystemExit(f"no snapshots in {SNAP_DIR}; run collect_line_timing.py snapshot")
    return snaps[-1]


def to_archive_convention(live):
    """Negate every spread column, matching build_prediction_tracker.clean_cells.

    Without this the live file runs opposite to everything the models were fitted on and
    every prediction comes out inverted.
    """
    out = live.copy()
    for c in out.columns:
        if c.startswith("line") and c not in UNSIGNED_LINES:
            out[c] = pd.to_numeric(out[c], errors="coerce") * -1.0
    return out


def predict(hist, models, live, bench_col="line", k=base.SCREEN_K):
    """E4 and E14 for the live rows, fitted on the whole historical panel.

    `live` must already be in archive sign convention.
    """
    usable = [m for m in models if m not in MARKET_LINES and m in live.columns]
    skill = base.prior_skill(hist, usable, bench_col, int(hist.season.max()))
    active = [m for m in usable if live[m].notna().any()]

    a = sweep.Anchor(hist, live, bench_col)
    if not a.usable:
        raise SystemExit("anchor could not be fitted on the historical panel")

    keep = sweep.screened(skill, active, k)
    d_tr, _ = sweep.deviations(hist, keep, bench_col)
    d_te, _ = sweep.deviations(live, keep, bench_col)
    e4, gamma = sweep.gamma_fit(a, np.nanmean(d_tr, axis=1), np.nanmean(d_te, axis=1))

    cols, _ = sweep.regressor_cols(hist, live, usable)
    try:
        e14, _ = sweep.fit_E14(a, hist, live, cols, active, skill, bench_col, 1)
    except Exception:
        e14 = np.full(len(live), np.nan)

    return {"r0": a.r0_te, "e4": e4, "e14": e14, "screened": keep,
            "gamma": gamma, "n_active": len(active)}


def build_table(live_raw, live, out):
    """Predictions are MARGINS (home team). Lines are shown in raw PT convention."""
    mkt_close = -live["line"].to_numpy(float)
    mkt_open = -live["lineopen"].to_numpy(float)
    t = pd.DataFrame({
        "road": live_raw["road"], "home": live_raw["home"],
        "line_open": live_raw["lineopen"], "line_now": live_raw["line"],
        "r0": out["r0"].round(2), "e4": np.round(out["e4"], 2),
        "e14": np.round(out["e14"], 2),
    })
    # Edge vs each benchmark, in margin space. Positive = model likes the home team more.
    t["edge_vs_close"] = (out["e4"] - mkt_close).round(2)
    t["edge_vs_open"] = (out["e4"] - mkt_open).round(2)
    return t


def chase_diagnostic(t):
    """Is the apparent edge over the open just the move that already happened?

    This is the timing caveat made measurable each week. Because gamma is small, E4 sits
    very close to the closing line, so edge_vs_open is arithmetically near (close - open)
    plus a small correction -- the correlation is near-tautological AS LONG AS the
    correction stays small. That is exactly what makes it worth printing: if it ever falls
    materially below 1, the consensus has started disagreeing with the market rather than
    restating it, and THAT is the week the forward test gets interesting.
    """
    move = (t["line_now"] - t["line_open"]).to_numpy(float)
    edge = t["edge_vs_open"].to_numpy(float)
    ok = np.isfinite(move) & np.isfinite(edge)
    if ok.sum() < 3 or np.std(move[ok]) == 0:
        return "line-chase check: not enough spread in line movement to compute"
    r = float(np.corrcoef(move[ok], edge[ok])[0, 1])
    verdict = ("edge over the open is essentially the move that already happened"
               if r > 0.9 else "consensus is departing from the market's own move")
    return (f"line-chase check: corr(line move, edge_vs_open) = {r:+.3f} "
            f"over {int(ok.sum())} games\n  -> {verdict}")


def append_log(t, snap_path, out):
    """Persist every prediction. Without this the forward test has no data in 12 weeks."""
    rec = t.copy()
    rec.insert(0, "snapshot", snap_path.name)
    rec.insert(1, "captured_utc", snap_path.stem.split("_")[-1])
    rec.insert(2, "logged_utc", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    rec["method"] = "E4_screened_consensus_k20"
    rec["n_active_models"] = out["n_active"]
    rec["gamma"] = round(float(out["gamma"]), 4)
    header = not LOG.exists()
    rec.to_csv(LOG, mode="a", header=header, index=False)
    return len(rec)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", type=Path, default=None)
    args = ap.parse_args()

    snap = args.snapshot or latest_snapshot()
    hist, models = base.load()
    live_raw = pd.read_csv(snap)
    live = to_archive_convention(live_raw)
    live["season"] = int(hist.season.max()) + 1
    live = live.reset_index(drop=True)

    out = predict(hist, models, live)
    t = build_table(live_raw, live, out)

    mpath = snap.with_suffix("").with_suffix(".meta.json")
    meta = json.loads(mpath.read_text()) if mpath.exists() else {}
    print(f"snapshot {snap.name}  captured {meta.get('captured_at', 'unknown')}")
    print(f"{out['n_active']} live models with data, screened to {len(out['screened'])}; "
          f"gamma {out['gamma']:+.4f}\n")
    print(t.to_string(index=False))

    n = append_log(t, snap, out)
    print(f"\nlogged {n} predictions to {LOG}")
    print(f"\n{chase_diagnostic(t)}")
    print("\n" + "-" * 74)
    print("vs CLOSING line: no edge. Best Holm p = 0.4865 over ten methods. Bet nothing")
    print("                 on edge_vs_close -- it is shown for the forward test only.")
    print("vs OPENING line: -2.615 MSE measured, but the archive cannot show the forecast")
    print("                 predated the open, so it is an upper bound, not a strategy.")
    print("This log is the forward test. Its value is that the snapshot is timestamped.")


def _check():
    """The sign flip is the whole risk, so it gets a direct test.

    Also round-trips a historical week through the live code path: if predict() disagrees
    with a direct E4 computation, the live path has diverged from what was validated.
    """
    live = pd.DataFrame({"line": [9.5], "lineopen": [9.0], "linestd": [4.6],
                         "linemassey": [3.7]})
    conv = to_archive_convention(live)
    assert conv["line"].iloc[0] == -9.5, "spreads must be negated"
    assert conv["linestd"].iloc[0] == 4.6, "linestd is unsigned and must not flip"

    hist, models = base.load()
    s = int(hist.season.max())
    tr, te = hist[hist.season < s], hist[hist.season == s].head(200).reset_index(drop=True)
    out = predict(tr, models, te)

    a = sweep.Anchor(tr, te, "line")
    skill = base.prior_skill(tr, [m for m in models if m not in MARKET_LINES], "line", s - 1)
    active = [m for m in models
              if m not in MARKET_LINES and m in te.columns and te[m].notna().any()]
    keep = sweep.screened(skill, active, base.SCREEN_K)
    d_tr, _ = sweep.deviations(tr, keep, "line")
    d_te, _ = sweep.deviations(te, keep, "line")
    direct, _ = sweep.gamma_fit(a, np.nanmean(d_tr, axis=1), np.nanmean(d_te, axis=1))
    assert np.allclose(out["e4"], direct, atol=1e-9), "live path diverged from direct E4"
    print("checks pass\n")


if __name__ == "__main__":
    _check()
    main()
