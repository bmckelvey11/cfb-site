"""Is the opening-line result model skill, or models proxying the closing line?

`docs/prediction-tracker-combination-sweep.md` section 1 claims the panel carries
information the OPENING line has not priced. The alternative reading is a tautology: some
Prediction Tracker entries may be market-anchored -- "the opening line plus my adjustment",
published mid-week once the number has already moved. Such a column beats the opening line
mechanically and says nothing about forecasting skill.

Discriminator, per model, on its own games:

    rho_i = corr(f_i - open, close - open)

A genuine forecaster anticipates SOME of the move and lands modest-positive. A market proxy
that has already seen the moved number lands near 1. Drop the top decile by rho and re-run
the opening-line result; if it survives, section 1 is about model skill.

    python scripts/diag_market_proxy.py

Also reports two smaller checks the sweep did not cover:
  * how many rows in the common support have NO screened model, where Anchor.strip's
    zero-fill produces a correction proportional to the market number instead of zero;
  * the Harvey-Newbold Wald with the full-sample principal components dropped.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import eval_prediction_tracker_models as base  # noqa: E402
import eval_combination_sweep as sw  # noqa: E402

MIN_GAMES = 400      # a correlation on fewer games than this is not worth acting on
DROP_QUANTILE = 0.90  # top decile by rho is dropped


def line_audit(df, models):
    """How close is each column to simply BEING the closing line?

    The rho check below catches market-anchored forecasts. This catches something blunter:
    columns in the panel that are not forecasts at all. A model cannot reproduce a
    sportsbook number to the half-point on most of its games; a reprinted line can.
    """
    close = df["line"].to_numpy(float)
    rows = []
    for m in models:
        a = df[m].to_numpy(float)
        ok = np.isfinite(a) & np.isfinite(close)
        if ok.sum() < MIN_GAMES:
            continue
        rows.append({"model": m, "n": int(ok.sum()),
                     "exact_close": float(np.mean(np.abs(a[ok] - close[ok]) < 1e-9)),
                     "rmse_close": float(np.sqrt(((a[ok] - close[ok]) ** 2).mean()))})
    return pd.DataFrame(rows).sort_values("rmse_close").reset_index(drop=True)


def movement_correlations(df, models):
    """corr(model's deviation from the open, the market's own open->close move)."""
    open_m = -df["lineopen"].to_numpy(float)
    close_m = -df["line"].to_numpy(float)
    move = close_m - open_m
    rows = []
    for m in models:
        f = -df[m].to_numpy(float)
        ok = np.isfinite(f) & np.isfinite(move)
        if ok.sum() < MIN_GAMES:
            continue
        dev = f[ok] - open_m[ok]
        if dev.std() == 0 or move[ok].std() == 0:
            continue
        rows.append({"model": m, "n": int(ok.sum()),
                     "rho": float(np.corrcoef(dev, move[ok])[0, 1])})
    return pd.DataFrame(rows).sort_values("rho", ascending=False).reset_index(drop=True)


KEEP = {"E6", "E11"}  # the two the headline rests on; the rest are unaffected by this check


def run(df, models, bench_col, label):
    """One narrow sweep -- E4/R0 plus E6 and E11 -- and everything derived from it."""
    preds, _, _, _ = sw.sweep(df, models, bench_col, verbose=False, only=KEEP)
    y = df["y"].to_numpy()
    season = df["season"].to_numpy()
    mkt = -df[bench_col].to_numpy(float)
    sup = (df["season"] > base.BURN_IN_THROUGH).to_numpy() & np.isfinite(mkt) \
        & np.isfinite(preds["R0"]) & np.isfinite(preds["E4"])
    for k in KEEP:
        sup &= np.isfinite(preds[k])
    r0 = preds["R0"]

    out = {"label": label, "n": int(sup.sum()), "n_models": len(models),
           "preds": preds, "sup": sup, "r0": r0, "y": y, "season": season}
    for k in ("E4", "E6", "E11"):
        d = base.sq_err(y[sup], -preds[k][sup]) - base.sq_err(y[sup], -r0[sup])
        out[k] = base.wild_cluster_boot(d, season[sup])
    for n_pcs in (3, 0):
        w, wp, wn, _ = sw.harvey_newbold(df, preds, models, bench_col, y, r0, season,
                                         sup, base.N_BOOT, n_pcs=n_pcs)
        out[f"hn{n_pcs}"] = (w, wp, wn)
    return out


def zero_fill_exposure(df, models, bench_col, sup):
    """Rows in support where NO screened model covers the game (Anchor.strip zero-fills)."""
    missing = 0
    for s in sorted(df.loc[df["season"] > base.BURN_IN_THROUGH, "season"].unique()):
        tr = df[df["season"] < s]
        idx = df.index[df["season"] == s].to_numpy()
        te = df.loc[idx]
        _, active = sw.regressor_cols(tr, te, models)
        skill = base.prior_skill(df, models, bench_col, s - 1)
        d, _ = sw.deviations(te, sw.screened(skill, active, base.SCREEN_K), bench_col)
        missing += int((np.isnan(np.nanmean(d, axis=1)) & sup[idx]).sum())
    return missing


def main():
    base.N_BOOT = 2000
    df, models = base.load()

    print("=" * 78)
    print("LINE AUDIT: which 'models' are just the closing line reprinted?")
    print("=" * 78)
    aud = line_audit(df, models)
    print(aud.head(8).to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print(f"\nmedian RMSE-to-close across {len(aud)} columns: {aud.rmse_close.median():.2f}")
    lines = aud.loc[aud.exact_close > 0.10, "model"].tolist()
    print(f"columns matching the close EXACTLY on >10% of games: {lines or 'none'}")

    print("\n" + "=" * 78)
    print("MARKET-PROXY CHECK: does a model's deviation from the open track the move?")
    print("=" * 78)
    corr = movement_correlations(df, models)
    print(f"{len(corr)} models with >= {MIN_GAMES} games")
    print(f"rho: median {corr.rho.median():.3f}  "
          f"p90 {corr.rho.quantile(0.9):.3f}  max {corr.rho.max():.3f}")
    print("\nmost market-like 12:")
    print(corr.head(12).to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    cut = corr.rho.quantile(DROP_QUANTILE)
    proxies = corr.loc[corr.rho >= cut, "model"].tolist()
    print(f"\ndropping {len(proxies)} models at rho >= {cut:.3f}")

    kept = [m for m in models if m not in set(proxies)]
    full = run(df, models, "lineopen", "all models")
    trim = run(df, kept, "lineopen", f"minus top-decile rho ({len(proxies)} dropped)")
    close = run(df, models, "line", "all models, closing benchmark")

    print("\n" + "=" * 78)
    print("OPENING-LINE RESULT, WITH AND WITHOUT THE MOST MARKET-LIKE MODELS")
    print("=" * 78)
    for res in (full, trim):
        print(f"\n{res['label']}  (n={res['n']}, {res['n_models']} models)")
        for k in ("E4", "E6", "E11"):
            dm, ci, pv = res[k]
            print(f"  {k:4s} ΔvsR0 {dm:+8.3f} [{ci[0]:+8.3f},{ci[1]:+7.3f}]  p={pv:.4f}")
        w, wp, wn = res["hn3"]
        print(f"  Harvey-Newbold Wald {w:.2f}  bootstrap p={wp:.4f}  (n={wn})")

    print("\n" + "=" * 78)
    print("ZERO-FILL EXPOSURE: rows in support with NO screened model present")
    print("=" * 78)
    for res, bench_col, lab in ((full, "lineopen", "opening"), (close, "line", "closing")):
        miss = zero_fill_exposure(df, models, bench_col, res["sup"])
        print(f"  {lab}: {miss} of {res['n']} rows ({miss / max(res['n'], 1):.3%})")

    print("\n" + "=" * 78)
    print("HARVEY-NEWBOLD WITHOUT THE FULL-SAMPLE PCs (consensus directions only)")
    print("=" * 78)
    for res, lab in ((full, "opening"), (close, "closing")):
        for key, tag in (("hn3", "with PCs"), ("hn0", "consensus only")):
            w, wp, wn = res[key]
            print(f"  {lab:8s} {tag:16s} Wald {w:7.2f}  p={wp:.4f}  n={wn}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
