"""Version B, one week at a time: the same join and estimators as eval_version_b.py, cut by
season-week cluster, for the weekly "how did last week grade" read.

Reuses eval_version_b's anchor, close and score joins verbatim so a per-week number here is
the same game set that the pooled read counts. Per-week SEs are plain HC1 (one cluster), so
they are informational only; the stopping rule in eval_version_b.py governs any verdict.

    python research/spread/scripts/version_b_by_week.py            # every graded week
    python research/spread/scripts/version_b_by_week.py --week 2026-09-07
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_version_b as vb  # noqa: E402


def graded_frame() -> pd.DataFrame:
    log = pd.read_csv(vb.LOG)
    g = vb.monday_anchor(log)
    g["kick_utc"] = pd.to_datetime(g.kick, utc=True)
    g["close"] = [vb.close_from_history(e, k) for e, k in zip(g.event_id, g.kick_utc)]
    con = duckdb.connect(str(vb.base.cfb_paths.DB_PATH), read_only=True)
    g["margin"] = vb.margins(g, vb.fetch_scores(con, sorted(set(g.kick_utc.dt.year))))
    now = datetime.now(timezone.utc)
    return g[g.close.notna() & (g.kick_utc < now)].copy()


def week_read(w: pd.DataFrame) -> dict:
    y = (w.close - w.line_pt).to_numpy(float)
    x4 = (w.E4 - w.line_pt).to_numpy(float)
    ok = np.isfinite(x4) & np.isfinite(y)
    out = {"n": int(ok.sum()), "move": float(np.abs(y[ok]).mean()), "gap": float(np.abs(x4[ok]).mean())}
    r = vb.cluster_ols(y[ok], x4[ok], w.week.to_numpy()[ok])
    out["slope"] = r["slope"]; out["slope_lo"] = r["lo"]; out["slope_hi"] = r["hi"]
    for thr in vb.THRESH:
        m = ok & (np.abs(x4) >= thr)
        if m.sum() == 0:
            continue
        side = np.sign(x4[m])
        clv = side * y[m]
        res = side * (w.margin.to_numpy(float)[m] - w.line_pt.to_numpy(float)[m])
        keep = np.isfinite(res) & (res != 0)
        out[f"bets_{thr:.0f}"] = int(m.sum())
        out[f"clv_{thr:.0f}"] = float(clv.mean())
        out[f"beat_{thr:.0f}"] = float((clv > 0).mean())
        out[f"ats_{thr:.0f}"] = float((res[keep] > 0).mean()) if keep.sum() else np.nan
        out[f"wl_{thr:.0f}"] = f"{int((res[keep] > 0).sum())}-{int((res[keep] < 0).sum())}-{int(m.sum() - keep.sum())}"
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", default=None, help="season-week cluster label, e.g. 2026-09-07")
    args = ap.parse_args()
    g = graded_frame()
    weeks = [args.week] if args.week else sorted(g.week.unique())
    for wk in weeks:
        w = g[g.week == wk]
        if w.empty:
            print(f"{wk}: no graded games"); continue
        r = week_read(w)
        print(f"\nweek {wk}: {r['n']} graded  mean|close-Mon| {r['move']:.2f}  mean|E4-Mon| {r['gap']:.2f}")
        print(f"  B4 E4 slope {r['slope']:+.3f} [{r['slope_lo']:+.3f}, {r['slope_hi']:+.3f}]  (HC1, one cluster: informational)")
        for thr in vb.THRESH:
            k = f"{thr:.0f}"
            if f"bets_{k}" not in r:
                print(f"  |x| >= {k}: 0 bets"); continue
            print(f"  |x| >= {k}: {r['bets_'+k]} bets  CLV {r['clv_'+k]:+.2f}  beat close {r['beat_'+k]:.1%}  "
                  f"ATS {r['ats_'+k]:.3f} ({r['wl_'+k]} W-L-P) vs {vb.BREAKEVEN}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
