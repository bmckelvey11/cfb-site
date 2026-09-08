"""Was the screened consensus measuring model skill, or measuring the line?

`research/spread/docs/prediction-tracker-model-eval.md` section 10 established that `lineca` and
`linemidweek` are market lines reprinted inside the model panel. They therefore top ANY
skill ranking, which means every screened-consensus result published so far -- the parent
plan's K=20 E4, and E3/E7/E10/E14 in the sweep -- was built on a top-20 whose two best
members were the closing line itself.

Section 10 measured the effect of dropping the top DECILE by movement correlation (15
columns). That is a different question. This asks the narrow one: remove exactly the two
market lines, change nothing else, and see whether the screened-consensus family survives.

    python research/spread/scripts/diag_screen_decontam.py

If E4's opening-line effect largely survives, the screen was measuring model skill and the
published structure holds. If it collapses, the screen was a market feed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import eval_prediction_tracker_models as base  # noqa: E402
import eval_combination_sweep as sw  # noqa: E402

MARKET_LINES = ["lineca", "linemidweek"]


def screen_membership(df, models, bench_col):
    """Where do the two market lines rank in the top-20 screen, season by season?"""
    hits = []
    for s in sorted(df.loc[df["season"] > base.BURN_IN_THROUGH, "season"].unique()):
        tr = df[df["season"] < s]
        te = df[df["season"] == s]
        _, active = sw.regressor_cols(tr, te, models)
        skill = base.prior_skill(df, models, bench_col, s - 1)
        keep = sw.screened(skill, active, base.SCREEN_K)
        hits.append({"season": int(s),
                     **{m: (keep.index(m) + 1 if m in keep else None) for m in MARKET_LINES}})
    return hits


def evaluate(df, models, bench_col, label):
    preds, _, _, _ = sw.sweep(df, models, bench_col, verbose=False, only={"E7"})
    y = df["y"].to_numpy()
    season = df["season"].to_numpy()
    mkt = -df[bench_col].to_numpy(float)
    sup = (df["season"] > base.BURN_IN_THROUGH).to_numpy() & np.isfinite(mkt) \
        & np.isfinite(preds["R0"]) & np.isfinite(preds["E4"]) & np.isfinite(preds["E7"])
    r0 = preds["R0"]
    out = {"label": label, "n": int(sup.sum()), "sup": sup, "preds": preds}
    for k in ("E4", "E7"):
        d = base.sq_err(y[sup], -preds[k][sup]) - base.sq_err(y[sup], -r0[sup])
        out[k] = base.wild_cluster_boot(d, season[sup])
        out[k + "_cw"] = base.clark_west(y[sup], r0[sup], preds[k][sup], season[sup])
    return out


def main():
    base.N_BOOT = 2000
    df, models = base.load()
    clean = [m for m in models if m not in set(MARKET_LINES)]

    print("=" * 78)
    print("WERE THE MARKET LINES INSIDE THE SCREEN?  (top-20 rank per season, closing)")
    print("=" * 78)
    hits = screen_membership(df, models, "line")
    inboth = sum(1 for h in hits if h["lineca"] and h["linemidweek"])
    inany = sum(1 for h in hits if h["lineca"] or h["linemidweek"])
    print(f"  seasons where BOTH are in the top 20: {inboth}/{len(hits)}")
    print(f"  seasons where EITHER is:              {inany}/{len(hits)}")
    for h in hits[:3] + hits[-3:]:
        print(f"    {h['season']}  lineca rank {h['lineca']}   linemidweek rank {h['linemidweek']}")

    for bench_col, lab in (("lineopen", "OPENING"), ("line", "CLOSING")):
        print("\n" + "=" * 78)
        print(f"{lab} LINE — screened consensus with and without the two market lines")
        print("=" * 78)
        full = evaluate(df, models, bench_col, "all 154")
        cln = evaluate(df, clean, bench_col, "152 (market lines removed)")
        for res in (full, cln):
            print(f"\n{res['label']}  n={res['n']}")
            for k in ("E4", "E7"):
                dm, ci, pv = res[k]
                cw, cwci, cwp = res[k + "_cw"]
                print(f"  {k}  ΔvsR0 {dm:+8.3f} [{ci[0]:+8.3f},{ci[1]:+7.3f}] p={pv:.4f}"
                      f"   Clark-West {cw:+7.3f} p={cwp:.4f}")
        for k in ("E4", "E7"):
            a, b = full[k][0], cln[k][0]
            share = (b / a * 100) if a not in (0, np.nan) else float("nan")
            print(f"\n  {k}: {a:+.3f} -> {b:+.3f}   ({share:.0f}% of the original effect retained)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
