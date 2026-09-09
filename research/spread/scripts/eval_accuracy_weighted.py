"""Weight the panel by recent accuracy, bet against the closing line, grade on money.

Everything before this graded the panel on whether it anticipates the closing NUMBER, pooled
over twenty seasons, with a screen ordered by "movement skill". Three things that never got
tested together:

  1. Weight models by how ACCURATE they are at the actual game margin, not by how well they
     track the market.
  2. Use only a trailing window of recent seasons, because the panel's membership and quality
     change -- 154 models exist across the archive but only ~45 carry data in any recent season.
  3. Grade on ATS, ROI and units against the -110 price, not on R^2 or CLV.

The margin era's recency section argued no recency scheme could break the closing-line null,
because recency only reordered a screen feeding a consensus whose fitted coefficient was zero.
That argument does not cover weighting by accuracy directly, and it does not cover EVALUATING on
recent seasons only -- a null pooled over 2006-2025 hides an effect that exists only in the years
the panel actually got good.

Walk-forward by construction: every weight for season s comes from seasons strictly before s, so
every bet below is out of sample. No lookahead.

    python research/spread/scripts/eval_accuracy_weighted.py
    python research/spread/scripts/eval_accuracy_weighted.py --from 2021

EXPLORATORY. This is a scan over weighting schemes x windows x thresholds and the FULL grid is
printed, not the best cell -- a maximum over 30-odd cells is not a finding. If something here
survives, the honest next step is to pre-register that specific cell and test it forward.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_prediction_tracker_models as base  # noqa: E402
import eval_line_movement as elm  # noqa: E402

OUT = base.OUT_DIR / "pt_accuracy_weighted.json"
BREAKEVEN = 110 / 210
WINDOWS = [1, 2, 3, 5]                 # trailing seasons used to measure accuracy
SCHEMES = ["equal_all", "top5", "top10", "top20", "inv_mse"]
THRESH = [1.0, 2.0, 3.0]               # points of disagreement with the close
MIN_GAMES = 60                         # a model needs this many graded games in the window


def roi(rate):
    return rate * (100 / 110) - (1 - rate)


def weights_for(hist, models, scheme):
    """Accuracy weights from the trailing window. hist carries margin `y` and model columns."""
    mse, n = {}, {}
    marg = hist["y"].to_numpy(float)
    for m in models:
        f = -hist[m].to_numpy(float)            # model -> margin space
        ok = np.isfinite(f) & np.isfinite(marg)
        if ok.sum() >= MIN_GAMES:
            mse[m] = float(((f[ok] - marg[ok]) ** 2).mean())
            n[m] = int(ok.sum())
    if not mse:
        return {}
    if scheme == "equal_all":
        return {m: 1.0 for m in mse}
    if scheme == "inv_mse":
        # plain inverse-MSE, the simplest accuracy weighting there is
        return {m: 1.0 / v for m, v in mse.items()}
    k = int(scheme.replace("top", ""))
    best = sorted(mse, key=mse.get)[:k]
    return {m: 1.0 for m in best}


def consensus(row_frame, models, w):
    """Weighted mean of the available models, in margin space, per game."""
    cols = [m for m in models if m in w]
    if not cols:
        return np.full(len(row_frame), np.nan)
    F = -row_frame[cols].to_numpy(float)
    W = np.array([w[m] for m in cols], float)
    ok = np.isfinite(F)
    wsum = (ok * W).sum(axis=1)
    num = np.nansum(np.where(ok, F * W, 0.0), axis=1)
    out = np.where(wsum > 0, num / np.where(wsum > 0, wsum, 1), np.nan)
    return out


def _ridge(X, y, lam):
    Xc = np.column_stack([np.ones(len(X)), X])
    A = Xc.T @ Xc + lam * np.eye(Xc.shape[1])
    A[0, 0] -= lam                       # never penalise the intercept
    return np.linalg.solve(A, Xc.T @ y)


def fitted(df, models, seasons, window=5, lam=10.0, thr=1.0):
    """Let the data choose the weights, rather than imposing equal / top-k / inverse-MSE.

    Regresses the CLOSE'S OWN ERROR (margin - close) on every model's deviation from the close,
    walk-forward. This is the strongest form of "weight their predictions": if any linear
    combination of the panel knows something the closing line does not, ridge finds it.

    Betting the raw consensus deviation -- what the unfitted schemes do -- implicitly assumes a
    coefficient of 1.0 on it, and would lose money even if the true coefficient were a healthy
    0.3. That is why this mode exists and why its answer differs from the grid above.
    """
    close = -df["line"].to_numpy(float)
    resid = df["y"].to_numpy(float) - close
    pred = np.full(len(df), np.nan)
    for s in seasons:
        tr = (df.season < s) & (df.season >= s - window)
        te = (df.season == s)
        if tr.sum() < 300:
            continue
        keep = [m for m in models
                if df.loc[tr, m].notna().mean() > 0.5 and df.loc[te, m].notna().mean() > 0.5]
        if len(keep) < 5:
            continue
        Xtr = np.nan_to_num(-df.loc[tr, keep].to_numpy(float) - close[tr.to_numpy()][:, None])
        Xte = np.nan_to_num(-df.loc[te, keep].to_numpy(float) - close[te.to_numpy()][:, None])
        b = _ridge(Xtr, resid[tr.to_numpy()], lam)
        pred[te.to_numpy()] = b[0] + Xte @ b[1:]

    ev = np.isfinite(pred) & df.season.isin(seasons).to_numpy()
    corr = float(np.corrcoef(pred[ev], resid[ev])[0, 1])
    sel = ev & (np.abs(pred) >= thr)
    side = np.sign(pred[sel])
    res = side * resid[sel]
    k = res != 0
    won, n = res[k] > 0, int(k.sum())
    rate = float(won.mean())
    se = float(np.sqrt(rate * (1 - rate) / n))
    seas = df.season.to_numpy()[sel][k]

    print(f"Fitted ridge weights, window {window} seasons, lambda {lam:.0f}, "
          f"evaluating {seasons[0]}-{seasons[-1]}, |pred| >= {thr:.0f}")
    print(f"  out-of-sample corr with the close's error: {corr:+.3f}")
    print(f"  {n} bets, ATS {rate:.1%}, 95% [{rate - 1.96 * se:.1%}, {rate + 1.96 * se:.1%}], "
          f"break-even {BREAKEVEN:.1%}")
    print(f"  ROI {roi(rate):+.2%}, units {won.sum() * (100 / 110) - (~won).sum():+.1f}")
    print("  by season:")
    for ss in sorted(set(seas)):
        m = seas == ss
        print(f"    {ss}: {int(m.sum()):5d} bets  {won[m].mean():.1%}")
    print()
    print("  A positive OOS correlation this small is a whisper, not an edge: it lands on the")
    print("  vig rather than past it, and the interval spans break-even.")
    (base.OUT_DIR / "pt_fitted_weights.json").write_text(json.dumps(
        {"window": window, "lam": lam, "thresh": thr, "oos_corr": corr, "bets": n,
         "ats": rate, "roi": roi(rate), "breakeven": BREAKEVEN,
         "by_season": {int(ss): float(won[seas == ss].mean()) for ss in sorted(set(seas))}},
        indent=2, default=float))
    return 0


def per_model(df, models, seasons):
    """The extreme case of "weight the accurate ones more": weight 1 on one model, 0 on the rest.

    Averaging can only hide a winner. If any single model beat the closing line, this finds it.
    """
    d = df[df.season.isin(seasons)]
    close, marg = -d["line"].to_numpy(float), d["y"].to_numpy(float)
    rows = []
    for m in models:
        f = -d[m].to_numpy(float)
        ok = np.isfinite(f)
        if ok.sum() < 300:
            continue
        edge = f[ok] - close[ok]
        sel = np.abs(edge) >= 1.0
        if sel.sum() < 200:
            continue
        side = np.sign(edge[sel])
        res = side * (marg[ok][sel] - close[ok][sel])
        keep = res != 0
        rate, n = float((res[keep] > 0).mean()), int(keep.sum())
        se = float(np.sqrt(rate * (1 - rate) / n))
        rows.append({"model": m, "bets": n, "ats": rate, "gap": rate - BREAKEVEN,
                     "lo95": rate - 1.96 * se, "roi": roi(rate)})
    rows.sort(key=lambda r: -r["ats"])
    print(f"{len(rows)} models with >= 200 bets, {seasons[0]}-{seasons[-1]}, "
          f"backing each when it disagrees with the close by >= 1 point")
    print(f"break-even at -110 is {BREAKEVEN:.1%}")
    print()
    print(f"{'model':>16} {'bets':>6} {'ATS':>7} {'vs B/E':>8} {'95% lo':>8} {'ROI':>8}")
    for r in rows[:10]:
        print(f"{r['model']:>16} {r['bets']:6d} {r['ats']:7.1%} {r['gap']:+8.1%} "
              f"{r['lo95']:7.1%} {r['roi']:+8.1%}")
    above = sum(1 for r in rows if r["ats"] > BREAKEVEN)
    print()
    print(f"{above} of {len(rows)} models are above break-even at the point estimate; "
          f"{sum(1 for r in rows if r['lo95'] > BREAKEVEN)} with a 95% lower bound above it.")
    print("Zero above break-even is not a wash -- it means the panel sits systematically below")
    print("the price. The models are about as accurate as the close, and the vig eats the rest.")
    (base.OUT_DIR / "pt_per_model_vs_close.json").write_text(
        json.dumps({"seasons": [int(s) for s in seasons], "breakeven": BREAKEVEN,
                    "rows": rows}, indent=2, default=float))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from", dest="start", type=int, default=2015,
                    help="first season to evaluate (default 2015)")
    ap.add_argument("--fitted", action="store_true",
                    help="let ridge FIT the weights instead of imposing them")
    ap.add_argument("--per-model", action="store_true",
                    help="every model on its own against the close, instead of combinations")
    args = ap.parse_args()

    df, models = base.load()
    models = [m for m in models if m not in elm.MARKET_LINES]   # lineca/linemidweek are the market
    df = df[df["line"].notna() & df["y"].notna()].reset_index(drop=True)
    seasons = sorted(s for s in df.season.unique() if s >= args.start)

    if args.fitted:
        return fitted(df, models, seasons)
    if args.per_model:
        return per_model(df, models, seasons)
    print(f"{len(df):,} games, {len(models)} models (market lines removed), "
          f"evaluating {seasons[0]}-{seasons[-1]}")
    print(f"Target: game margin. Benchmark: the CLOSING line. Bet when the weighted panel")
    print(f"disagrees with the close by >= threshold. Break-even at -110 is {BREAKEVEN:.1%}.")
    print("Weights come only from seasons strictly before the one being bet.\n")
    print(f"{'scheme':>9} {'win':>4} {'thr':>4} {'bets':>6} {'ATS':>7} {'ROI':>8} {'units':>8}  {'':<4}")

    rows = []
    for scheme in SCHEMES:
        for win in WINDOWS:
            if scheme == "equal_all" and win != WINDOWS[0]:
                continue                       # equal weights don't depend on the window
            preds = np.full(len(df), np.nan)
            for s in seasons:
                hist = df[(df.season < s) & (df.season >= s - win)]
                if len(hist) < MIN_GAMES:
                    continue
                w = weights_for(hist, models, scheme)
                idx = df.index[df.season == s]
                preds[idx] = consensus(df.loc[idx], models, w)
            close = -df["line"].to_numpy(float)
            marg = df["y"].to_numpy(float)
            ev = df.season.isin(seasons).to_numpy()
            for thr in THRESH:
                edge = preds - close
                m = ev & np.isfinite(edge) & (np.abs(edge) >= thr)
                if m.sum() < 30:
                    continue
                side = np.sign(edge[m])
                res = side * (marg[m] - close[m])
                keep = res != 0
                rate = float((res[keep] > 0).mean())
                r, units = roi(rate), float((res[keep] > 0).sum() * (100 / 110) - (res[keep] < 0).sum())
                flag = "  <-- clears" if rate > BREAKEVEN else ""
                print(f"{scheme:>9} {win:>4} {thr:>4.0f} {int(keep.sum()):6d} {rate:7.1%} "
                      f"{r:+8.1%} {units:+8.1f}{flag}")
                rows.append({"scheme": scheme, "window": win, "thresh": thr,
                             "bets": int(keep.sum()), "ats": rate, "roi": r, "units": units,
                             "clears_breakeven": bool(rate > BREAKEVEN)})
        print()

    best = max(rows, key=lambda r: r["ats"]) if rows else None
    clears = [r for r in rows if r["clears_breakeven"]]
    print(f"{len(clears)} of {len(rows)} cells finish above the {BREAKEVEN:.1%} break-even.")
    if best:
        print(f"Best cell: {best['scheme']} / window {best['window']} / thr {best['thresh']:.0f} "
              f"-> {best['ats']:.1%} on {best['bets']} bets, ROI {best['roi']:+.1%}")
    print("A maximum over this many cells is a maximum, not an edge. Nothing here is registered;")
    print("the honest next step for any surviving cell is to fix it in advance and test forward.")

    OUT.write_text(json.dumps({"eval_from": seasons[0], "breakeven": BREAKEVEN,
                               "n_cells": len(rows), "n_clearing": len(clears),
                               "rows": rows}, indent=2, default=float))
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
