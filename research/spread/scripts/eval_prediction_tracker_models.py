"""Rank the Prediction Tracker models and build a walk-forward ensemble spread.

Implements research/spread/docs/prediction-tracker-model-eval-plan.md. Read that first -- the estimand,
the dual open/close benchmark, the pre-registration of E4, the volatility definition and
the multiplicity budget are all fixed there, before any of this was fit.

    python research/spread/scripts/eval_prediction_tracker_models.py            # full run
    python research/spread/scripts/eval_prediction_tracker_models.py --quick    # skip the bootstrap

Everything is expressed as a predicted HOME MARGIN (= -spread), oriented to Prediction
Tracker's home/road. Error = margin + spread.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", r"Mean of empty slice", RuntimeWarning)

REPO = next(
    parent for parent in Path(__file__).resolve().parents
    if (parent / "cfb_paths.py").is_file()
)
sys.path.insert(0, str(REPO))
import cfb_paths  # noqa: E402

SRC = cfb_paths.INGEST / "prediction_tracker_lines.csv"
OUT_DIR = cfb_paths.PROCESSED
BURN_IN_THROUGH = 2005  # seasons <= this are fitting-only; evaluation starts 2006
SCREEN_K = 20  # E3/E4 keep the top-K models by prior-season skill (fixed in the plan)
CLEAN_COVERAGE = 0.95  # leaderboard restricts to model-seasons at/above this coverage
RIDGE_ALPHA = 10.0
N_BOOT = 2000
RNG = np.random.default_rng(20260829)
MIN_CLUSTERS = 3  # below this a cluster bootstrap is degenerate -- report no inference


# --------------------------------------------------------------------------- loading


def load():
    df = pd.read_csv(SRC, low_memory=False)
    cols = list(df.columns)
    models = cols[cols.index("linestd") + 1 :]

    df = df[(df["match_status"] == "matched") & df["home_points"].notna()].copy()
    margin = df["home_points"] - df["away_points"]
    # the line columns are oriented to PT's home team; orient the margin the same way
    df["y"] = np.where(df["orientation_flipped"] == 1, -margin, margin)
    df["season"] = df["season"].astype(int)
    df["wk"] = df["season"] * 100 + df["pt_week"].fillna(0).astype(int)
    return df.reset_index(drop=True), models


# ------------------------------------------------------------------- core statistics


def sq_err(y, spread):
    """Squared error of a spread prediction. NaN propagates for absent predictions."""
    return (y + spread) ** 2


def wild_cluster_boot(d, clusters, n_boot=N_BOOT):
    """Wild cluster bootstrap-t CI for mean(d). 25 season clusters is well under the
    ~40 where analytic cluster SEs can be trusted, so this is the primary inference."""
    d = np.asarray(d, float)
    keep = ~np.isnan(d)
    d, clusters = d[keep], np.asarray(clusters)[keep]
    n = len(d)
    if n < 2:
        return np.nan, (np.nan, np.nan), np.nan
    codes, idx = np.unique(clusters, return_inverse=True)
    g = len(codes)
    mean = d.mean()
    if g < MIN_CLUSTERS:
        # a wild cluster bootstrap over 1-2 clusters is degenerate: every draw flips the
        # same sign pattern, the CI collapses to a point and the p-value is meaningless
        return mean, (np.nan, np.nan), np.nan

    def cluster_se(x):
        resid = x - x.mean()
        sums = np.bincount(idx, weights=resid, minlength=g)
        # small-cluster correction
        adj = g / max(g - 1, 1)
        return np.sqrt(adj * (sums**2).sum()) / n

    se = cluster_se(d)
    t_obs = mean / se if se > 0 else np.nan

    # impose the null by centering, then Rademacher-reweight whole clusters
    centered = d - mean
    ts = np.empty(n_boot)
    for b in range(n_boot):
        w = RNG.choice([-1.0, 1.0], size=g)[idx]
        star = centered * w
        se_b = cluster_se(star)
        ts[b] = star.mean() / se_b if se_b > 0 else 0.0
    p = float((np.abs(ts) >= abs(t_obs)).mean()) if np.isfinite(t_obs) else np.nan
    lo, hi = np.quantile(ts, [0.025, 0.975])
    return mean, (mean - hi * se, mean - lo * se), p


def clark_west(y, pred_small, pred_big, clusters):
    """Clark-West MSPE-adjusted test for a nested pair (big nests small).

    f = (y-small)^2 - [(y-big)^2 - (small-big)^2];  H1: mean(f) > 0 (big is better).
    Plain Diebold-Mariano is biased toward the bigger model here and would over-reject.
    """
    e_s = (y - pred_small) ** 2
    e_b = (y - pred_big) ** 2
    adj = (pred_small - pred_big) ** 2
    f = e_s - (e_b - adj)
    mean, ci, p_two = wild_cluster_boot(f, clusters)
    return mean, ci, (p_two / 2 if mean > 0 else 1 - p_two / 2)  # one-sided


def bh_qvalues(p):
    """Benjamini-Hochberg step-up q-values."""
    p = np.asarray(p, float)
    ok = ~np.isnan(p)
    q = np.full_like(p, np.nan)
    ps = p[ok]
    order = np.argsort(ps)
    m = len(ps)
    ranked = ps[order]
    raw = ranked * m / np.arange(1, m + 1)
    monotone = np.minimum.accumulate(raw[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.clip(monotone, 0, 1)
    q[ok] = out
    return q


# ---------------------------------------------------------------------- leaderboard


def coverage_table(df, models):
    """Per (season, model) within-season coverage -- the MNAR screen from the plan."""
    sizes = df.groupby("season").size()
    present = df.groupby("season")[models].apply(lambda g: g.notna().sum())
    return present.div(sizes, axis=0)


def leaderboard(df, models, bench_col, cov, clean_only=True):
    y = df["y"].to_numpy()
    bench = df[bench_col].to_numpy(float)
    bench_err = sq_err(y, bench)
    season = df["season"].to_numpy()

    rows = []
    for m in models:
        pred = df[m].to_numpy(float)
        if clean_only:
            good = cov[m].reindex(season).to_numpy() >= CLEAN_COVERAGE
            pred = np.where(good, pred, np.nan)
        mask = ~np.isnan(pred) & ~np.isnan(bench)
        n = int(mask.sum())
        if n < 200:
            continue
        err = y[mask] + pred[mask]
        d = sq_err(y[mask], pred[mask]) - bench_err[mask]
        delta, ci, p = wild_cluster_boot(d, season[mask], n_boot=400)
        bias = err.mean()
        rows.append(
            {
                "model": m,
                "n": n,
                "seasons": int(len(np.unique(season[mask]))),
                "rmse": float(np.sqrt((err**2).mean())),
                "bias": float(bias),
                # pre-committed volatility: error SD with the model's own bias removed
                "volatility": float(np.sqrt((err**2).mean() - bias**2)),
                "delta_mse": float(delta),
                "ci_lo": float(ci[0]),
                "ci_hi": float(ci[1]),
                "p": float(p),
            }
        )
    out = pd.DataFrame(rows).sort_values("delta_mse").reset_index(drop=True)
    out["q_bh"] = bh_qvalues(out["p"].to_numpy())
    out["inference"] = np.where(out["seasons"] >= MIN_CLUSTERS, "ok", "too few seasons")
    return out


def rank_stability(df, models, bench_col, cov):
    """Spearman correlation of per-model skill rank between consecutive seasons."""
    y = df["y"].to_numpy()
    bench = sq_err(y, df[bench_col].to_numpy(float))
    per = {}
    for s, g in df.groupby("season"):
        i = g.index.to_numpy()
        skill = {}
        for m in models:
            if cov.loc[s, m] < CLEAN_COVERAGE:
                continue
            p = g[m].to_numpy(float)
            mask = ~np.isnan(p) & ~np.isnan(bench[i])
            if mask.sum() < 100:
                continue
            skill[m] = float((sq_err(y[i][mask], p[mask]) - bench[i][mask]).mean())
        per[s] = skill
    cors = []
    seasons = sorted(per)
    for a, b in zip(seasons, seasons[1:]):
        shared = sorted(set(per[a]) & set(per[b]))
        if len(shared) < 8:
            continue
        va = pd.Series([per[a][m] for m in shared]).rank()
        vb = pd.Series([per[b][m] for m in shared]).rank()
        cors.append((b, len(shared), float(va.corr(vb))))
    return pd.DataFrame(cors, columns=["season", "n_models", "spearman"])


# ------------------------------------------------------------------------ ensembles


def prior_skill(df, models, bench_col, upto):
    """Mean ΔMSE vs benchmark per model over seasons <= upto. Lower is better."""
    h = df[df["season"] <= upto]
    if h.empty:
        return {}
    y = h["y"].to_numpy()
    bench = sq_err(y, h[bench_col].to_numpy(float))
    out = {}
    for m in models:
        p = h[m].to_numpy(float)
        mask = ~np.isnan(p) & ~np.isnan(bench)
        if mask.sum() < 200:
            continue
        out[m] = float((sq_err(y[mask], p[mask]) - bench[mask]).mean())
    return out


def walk_forward(df, models, bench_col):
    """Build every ensemble's out-of-sample prediction, one season at a time.

    Weights for season t see only seasons < t. Predictions are margins.
    """
    from sklearn.linear_model import Ridge

    seasons = sorted(df.loc[df["season"] > BURN_IN_THROUGH, "season"].unique())
    # R0 = recalibration only (margin ~ b0 + b1*market). It is the restricted model that
    # isolates beta2: E4 vs the RAW market would bundle "the models add information" with
    # "the line is mildly under-extrapolated", and only the first is a claim about models.
    preds = {k: np.full(len(df), np.nan) for k in ("E1", "E2", "E3", "E4", "E5", "R0")}
    weights_log = []

    for s in seasons:
        tr = df[df["season"] < s]
        te_idx = df.index[df["season"] == s].to_numpy()
        te = df.loc[te_idx]

        skill = prior_skill(df, models, bench_col, s - 1)
        # models active this season (season-level availability, no imputation)
        active = [m for m in models if te[m].notna().mean() >= 0.5]
        screened = [m for m in sorted(skill, key=skill.get)[:SCREEN_K] if m in active]
        if not screened:
            screened = active[:SCREEN_K]

        te_all = te[active].to_numpy(float)
        preds["E1"][te_idx] = -np.nanmean(te_all, axis=1)
        preds["E2"][te_idx] = -np.nanmedian(te_all, axis=1)
        cons_te = -np.nanmean(te[screened].to_numpy(float), axis=1)
        preds["E3"][te_idx] = cons_te

        mkt_te = -te[bench_col].to_numpy(float)

        # ---- E4 (pre-registered primary): margin ~ mkt + (screened_consensus - mkt)
        cons_tr = -np.nanmean(tr[screened].to_numpy(float), axis=1)
        mkt_tr = -tr[bench_col].to_numpy(float)
        ok = ~np.isnan(cons_tr) & ~np.isnan(mkt_tr)
        if ok.sum() > 500:
            ytr = tr["y"].to_numpy()[ok]
            X = np.column_stack([np.ones(ok.sum()), mkt_tr[ok], (cons_tr - mkt_tr)[ok]])
            beta, *_ = np.linalg.lstsq(X, ytr, rcond=None)
            Xt = np.column_stack(
                [np.ones(len(te_idx)), mkt_te, np.nan_to_num(cons_te - mkt_te)]
            )
            preds["E4"][te_idx] = Xt @ beta

            # R0: same fit with beta2 dropped -- recalibration of the line, no models
            b_r0, *_ = np.linalg.lstsq(X[:, :2], ytr, rcond=None)
            preds["R0"][te_idx] = np.column_stack([np.ones(len(te_idx)), mkt_te]) @ b_r0
            weights_log.append(
                {
                    "season": int(s),
                    "b0": float(beta[0]),
                    "b_mkt": float(beta[1]),
                    "b_consensus_dev": float(beta[2]),
                    "n_train": int(ok.sum()),
                    "screened": ",".join(screened[:8]),
                }
            )

        # ---- E5: ridge on the season's active set + benchmark, complete data only
        cols = [c for c in active if tr[c].notna().mean() > 0.8]
        if cols:
            tr_sub = tr[cols + [bench_col, "y"]].dropna()
            if len(tr_sub) > 500:
                rg = Ridge(alpha=RIDGE_ALPHA).fit(
                    -tr_sub[cols + [bench_col]].to_numpy(float), tr_sub["y"].to_numpy()
                )
                Xte = -te[cols + [bench_col]].to_numpy(float)
                row_ok = ~np.isnan(Xte).any(axis=1)
                p5 = np.full(len(te_idx), np.nan)
                if row_ok.any():
                    p5[row_ok] = rg.predict(Xte[row_ok])
                preds["E5"][te_idx] = p5

    return preds, pd.DataFrame(weights_log), seasons


# ----------------------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="fewer bootstrap draws")
    args = ap.parse_args()
    global N_BOOT
    if args.quick:
        N_BOOT = 300

    df, models = load()
    cov = coverage_table(df, models)
    print(f"{len(df)} games, {len(models)} models, seasons {df.season.min()}-{df.season.max()}")

    results = {}
    for bench_col, label in (("lineopen", "opening"), ("line", "closing")):
        print(f"\n{'='*78}\nBENCHMARK: {label} line ({bench_col})\n{'='*78}")
        b = df[bench_col].to_numpy(float)
        ok = ~np.isnan(b)
        print(f"benchmark RMSE {np.sqrt(sq_err(df['y'].to_numpy()[ok], b[ok]).mean()):.4f}"
              f"  on {ok.sum()} games")

        lb = leaderboard(df, models, bench_col, cov)
        lb.to_csv(OUT_DIR / f"pt_leaderboard_{label}.csv", index=False)
        print(f"\n-- top 15 by skill (ΔMSE vs {label}; negative = beats the line) --")
        cols = ["model", "n", "seasons", "rmse", "volatility", "delta_mse", "ci_lo", "ci_hi", "q_bh"]
        print(lb.head(15)[cols].to_string(index=False, float_format=lambda v: f"{v:.3f}"))
        beat = lb[(lb.delta_mse < 0) & (lb.q_bh < 0.05)]
        print(f"\nmodels beating the {label} line at BH q<0.05: {len(beat)}"
              + (f"  -> {', '.join(beat.model)}" if len(beat) else ""))

        preds, wlog, seasons = walk_forward(df, models, bench_col)
        ev = df["season"] > BURN_IN_THROUGH
        y = df["y"].to_numpy()
        mkt = -df[bench_col].to_numpy(float)
        season = df["season"].to_numpy()

        # common support: every ensemble scored on the SAME games. Scoring each on its
        # own subsample reproduces exactly the coverage confound that sinks the raw
        # per-model RMSE leaderboard.
        common = ev & ~np.isnan(mkt)
        for k in preds:
            common &= ~np.isnan(preds[k])
        mkt_rmse = float(np.sqrt(sq_err(y[common], -mkt[common]).mean()))
        print(f"\n-- walk-forward ensembles, {seasons[0]}-{seasons[-1]}, "
              f"common support n={int(common.sum())} --")
        print(f"{'ens':4s} {'n':>6s} {'RMSE':>8s} {'ΔMSE':>9s} {'95% CI':>20s} {'p':>8s}")
        print(f"{'mkt':4s} {int(common.sum()):6d} {mkt_rmse:8.4f} {0.0:+9.3f} "
              f"{'(benchmark)':>20s}")
        ens_rows = []
        for k in ("E1", "E2", "E3", "R0", "E4", "E5"):
            p = preds[k]
            mask = common
            d = sq_err(y[mask], -p[mask]) - sq_err(y[mask], -mkt[mask])
            delta, ci, pv = wild_cluster_boot(d, season[mask])
            rmse = float(np.sqrt(sq_err(y[mask], -p[mask]).mean()))
            ens_rows.append({"ens": k, "n": int(mask.sum()), "rmse": rmse,
                             "delta_mse": delta, "ci_lo": ci[0], "ci_hi": ci[1], "p": pv})
            print(f"{k:4s} {int(mask.sum()):6d} {rmse:8.4f} {delta:+9.3f} "
                  f"[{ci[0]:+8.3f},{ci[1]:+8.3f}] {pv:8.4f}")

        # Primary test. E4 nests the benchmark, so Clark-West is the right test -- but CW
        # and the plain paired difference answer DIFFERENT questions out-of-sample:
        #   CW      : do the extra terms carry population signal?
        #   plain Δ : does the bigger model actually forecast better once you pay the
        #             estimation cost? Deployment hinges on the second, not the first.
        p4, r0 = preds["E4"], preds["R0"]
        mask = common
        print(f"\nPRIMARY, E4 vs {label} line (n={int(mask.sum())}):")
        for small, name in ((mkt, f"raw {label} line"), (r0, "recalibrated line (R0)")):
            cw, cwci, cwp = clark_west(y[mask], small[mask], p4[mask], season[mask])
            dd = sq_err(y[mask], -p4[mask]) - sq_err(y[mask], -small[mask])
            pdm, pdci, pdp = wild_cluster_boot(dd, season[mask])
            print(f"  vs {name}:")
            print(f"    Clark-West  (signal?)    adj mean {cw:+.3f} "
                  f"CI [{cwci[0]:+.3f},{cwci[1]:+.3f}] one-sided p={cwp:.4f}")
            print(f"    paired ΔMSE (forecast?)  {pdm:+.3f} "
                  f"CI [{pdci[0]:+.3f},{pdci[1]:+.3f}] two-sided p={pdp:.4f}")
            if name.startswith("raw"):
                cw_raw, pd_mean, pd_ci, pd_p = cw, pdm, pdci, pdp
            else:
                # this is the one that isolates beta2 -- only the models differ here
                cw_r0, cw_r0_ci, cw_r0_p = cw, cwci, cwp
                b2_mean, b2_ci, b2_p = pdm, pdci, pdp

        # decision value: ATS on E4's disagreements with the CLOSING line
        close = -df["line"].to_numpy(float)
        dm = common & ~np.isnan(close)
        edge = p4[dm] - close[dm]
        actual = y[dm] - close[dm]
        for thr in (0.0, 1.0, 2.0, 3.0):
            sel = np.abs(edge) > thr
            if sel.sum() < 50:
                continue
            win = (np.sign(edge[sel]) == np.sign(actual[sel])) & (actual[sel] != 0)
            push = actual[sel] == 0
            dec = sel.sum() - push.sum()
            hit = win.sum() / dec if dec else np.nan
            roi = (win.sum() * (100 / 110) - (dec - win.sum())) / dec if dec else np.nan
            print(f"  ATS |edge|>{thr:.0f}: {dec:5d} bets  {hit:.4f} hit  {roi:+.4f} ROI/unit"
                  f"   (break-even .5238)")

        results[label] = {
            "benchmark_rmse": float(np.sqrt(sq_err(df["y"].to_numpy()[ok], b[ok]).mean())),
            "ensembles": ens_rows,
            "clark_west_vs_raw": {"mean": cw_raw, "p_one_sided": cwp},
            "e4_paired_vs_raw": {"mean": pd_mean, "ci": list(pd_ci), "p_two_sided": pd_p},
            "clark_west_vs_recalibrated": {"mean": cw_r0, "ci": list(cw_r0_ci),
                                           "p_one_sided": cw_r0_p},
            "e4_paired_vs_recalibrated": {"mean": b2_mean, "ci": list(b2_ci),
                                          "p_two_sided": b2_p},
            "n_models_beating": int(len(beat)),
        }
        # the usable artifact: E4's spread per game, next to both benchmarks
        out = df.loc[common, ["game_id", "season", "pt_week", "home", "road", "y"]].copy()
        out["market_spread"] = df.loc[common, bench_col]
        out["ensemble_spread"] = -p4[common]
        out["edge_vs_market"] = out["market_spread"] - out["ensemble_spread"]
        out.rename(columns={"y": "actual_margin"}).to_csv(
            OUT_DIR / f"pt_ensemble_spread_{label}.csv", index=False
        )

        if not wlog.empty:
            wlog.to_csv(OUT_DIR / f"pt_e4_weights_{label}.csv", index=False)
            print(f"\nE4 fitted weights (last 3 seasons), benchmark={label}:")
            print(wlog.tail(3).to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    st = rank_stability(df, models, "line", cov)
    print(f"\n-- skill-rank stability across consecutive seasons --")
    print(f"mean Spearman {st.spearman.mean():.3f} over {len(st)} season pairs "
          f"(min {st.spearman.min():.3f}, max {st.spearman.max():.3f})")

    (OUT_DIR / "pt_model_eval.json").write_text(json.dumps(results, indent=2, default=float))
    print(f"\nwrote {OUT_DIR / 'pt_model_eval.json'} and per-benchmark CSVs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
