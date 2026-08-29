"""Recency-weighted skill estimation and cohort-aware pooling.

Implements docs/prediction-tracker-model-eval-plan-addendum.md section 11, committed before
any of this ran. Read section 11.0 first: recency enters only through the SCREEN, and against
the closing line the correction coefficient is already zero, so nothing here can produce a
closing-line edge. What it can move is the opening-line effect and which models get screened.

    python scripts/eval_recency_screen.py            # full run
    python scripts/eval_recency_screen.py --quick    # fewer bootstrap draws

The two market lines (section 10 of the parent results) are excluded throughout: lineca ranked
#1 in the top-20 screen in 20 of 20 seasons, so leaving it in would tune a decay factor on a
screen whose best member is the benchmark.

SPEED. Skill for any retention factor is a reweighting of per-model-per-season loss sums, so
those are computed once per benchmark and every rho on the grid is then almost free.
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", r"Mean of empty slice", RuntimeWarning)
warnings.filterwarnings("ignore", r"invalid value encountered", RuntimeWarning)

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cfb_paths  # noqa: E402
import eval_prediction_tracker_models as base  # noqa: E402
import eval_combination_sweep as sw  # noqa: E402

OUT_DIR = cfb_paths.PROCESSED
MARKET_LINES = {"lineca", "linemidweek"}

# ---- grids (addendum 11.3). Each list runs LEAST -> MOST conservative; the 1-SE rule takes
# the last entry within one SE of the best, exactly as in the sweep.
RHO = [0.80, 0.85, 0.90, 0.95, 0.975, 1.00]
KAPPA = [500, 1000, 2000, 4000]
ETA = [1.00, 0.75, 0.50, 0.25, 0.00]
C_PEN = [0.0, 0.5, 1.0]
Q_SLEEVE = [0.20, 0.10, 0.05, 0.00]

# k is REPORTED, never selected -- the sweep showed it is unidentifiable out-of-sample
K_GRID = [5, 8, 12, 16, 20, 30]

# defaults while another parameter is being selected (the conservative end of each grid)
D_RHO, D_KAPPA, D_ETA, D_C, D_Q = 1.00, 1000, 0.00, 0.5, 0.00
LAMBDA_GAP = 0.25          # unidentifiable at 25 gapped models; fixed, never tuned
LAMBDA_SENS = [0.0, 0.5]   # reported as sensitivity only
MIN_PRIOR_SEASONS = 2
MIN_EFF_GAMES = 500
RECENT_WINDOW = 3
INNER_VAL_SEASONS = 3


# ------------------------------------------------------------------ precomputed skill table


def season_loss_table(df, models, bench_col):
    """L[i,u] = summed market-relative squared-error loss; N[i,u] = games. Lower L is better."""
    seasons = sorted(df["season"].unique())
    s_idx = {s: j for j, s in enumerate(seasons)}
    y = df["y"].to_numpy()
    bench = base.sq_err(y, df[bench_col].to_numpy(float))
    L = np.zeros((len(models), len(seasons)))
    N = np.zeros((len(models), len(seasons)))
    col = df["season"].map(s_idx).to_numpy()
    for i, m in enumerate(models):
        p = df[m].to_numpy(float)
        ok = np.isfinite(p) & np.isfinite(bench)
        if not ok.any():
            continue
        rel = base.sq_err(y[ok], p[ok]) - bench[ok]
        np.add.at(L[i], col[ok], rel)
        np.add.at(N[i], col[ok], 1.0)
    return L, N, np.array(seasons)


def gap_seasons(N, seasons, upto_idx):
    """Consecutive inactive seasons immediately before the model's return, per model."""
    out = np.zeros(len(N))
    act = N[:, : upto_idx + 1] > 0
    for i in range(len(N)):
        w = np.flatnonzero(act[i])
        if len(w) < 2:
            continue
        out[i] = (w[-1] - w[-2]) - 1
    return out


def discounted_skill(L, N, seasons, s, rho, lam=LAMBDA_GAP, window=None):
    """Discounted market-relative skill, effective sample size, and its uncertainty.

    `window` limits to the last N seasons (used for the recent half of the two-window blend
    and for the rolling-window robustness specs).
    """
    upto = int(np.searchsorted(seasons, s)) - 1
    if upto < 0:
        n = len(L)
        return np.full(n, np.nan), np.zeros(n), np.full(n, np.nan), np.zeros(n)
    lo = 0 if window is None else max(0, upto - window + 1)
    ages = s - seasons[lo : upto + 1]
    w = rho ** ages
    Ls, Ns = L[:, lo : upto + 1], N[:, lo : upto + 1]
    den = Ns @ w
    with np.errstate(invalid="ignore", divide="ignore"):
        mu = (Ls @ w) / den
        # weighted spread of the per-season skill means, then the SE of their weighted mean
        per = np.where(Ns > 0, Ls / np.maximum(Ns, 1), np.nan)
        ww = np.where(Ns > 0, w * Ns, 0.0)
        wsum = ww.sum(axis=1)
        centred = per - mu[:, None]
        var = np.nansum(ww * centred**2, axis=1) / np.maximum(wsum, 1e-9)
        n_seas = (Ns > 0).sum(axis=1)
        sigma = np.sqrt(var / np.maximum(n_seas, 1))
    n_eff = den * np.exp(-lam * gap_seasons(N, seasons, upto))
    return mu, n_eff, sigma, n_seas


def score_models(L, N, seasons, s, rho, kappa, eta, c, lam=LAMBDA_GAP):
    """Shrunk, uncertainty-penalised rank score. Lower is better. NaN = not evaluable."""
    mu_l, n_eff, sig_l, n_seas = discounted_skill(L, N, seasons, s, rho, lam)
    if eta > 0:
        mu_r, _, sig_r, _ = discounted_skill(L, N, seasons, s, rho, lam, window=RECENT_WINDOW)
        mu = np.where(np.isfinite(mu_r), (1 - eta) * mu_l + eta * mu_r, mu_l)
        sig = np.where(np.isfinite(sig_r), (1 - eta) * sig_l + eta * sig_r, sig_l)
    else:
        mu, sig = mu_l, sig_l
    omega = n_eff / (n_eff + kappa)          # empirical-Bayes credibility
    return omega * mu + c * np.nan_to_num(sig), n_eff, n_seas


def eligible(n_eff, n_seas):
    return (n_seas >= MIN_PRIOR_SEASONS) & (n_eff >= MIN_EFF_GAMES)


def cohort_adjust(L, N, seasons, s, entry_year):
    """Rank on persistent ability after removing season effects and an entry-year trend.

    Cohort DUMMIES are infeasible (87/29/29/5/4 entrants), so entry year is a linear trend --
    addendum 11.4. Fit on pre-season-s cells only; the returned score is the model effect.
    """
    upto = int(np.searchsorted(seasons, s)) - 1
    if upto < 1:
        return np.full(len(L), np.nan)
    per = np.where(N[:, : upto + 1] > 0, L[:, : upto + 1] / np.maximum(N[:, : upto + 1], 1), np.nan)
    mi, si = np.where(np.isfinite(per))
    if len(mi) < 50:
        return np.full(len(L), np.nan)
    wts = N[:, : upto + 1][mi, si]
    # design: model dummies + season dummies + entry-year trend (models absorb the intercept)
    nm, ns = len(L), upto + 1
    X = np.zeros((len(mi), nm + ns + 1))
    X[np.arange(len(mi)), mi] = 1.0
    X[np.arange(len(mi)), nm + si] = 1.0
    X[:, -1] = entry_year[mi] - entry_year.mean()
    sw_ = np.sqrt(wts)[:, None]
    beta = np.linalg.lstsq(X * sw_, per[mi, si] * sw_[:, 0], rcond=None)[0]
    out = np.full(nm, np.nan)
    seen = np.unique(mi)
    out[seen] = beta[seen]
    return out


# --------------------------------------------------------------------------- forecasting


def build_pred(df, models, bench_col, L, N, seasons, k, rho, kappa, eta, c, q,
               lam=LAMBDA_GAP, use_cohort=False, entry_year=None, eval_seasons=None,
               window=None):
    """Walk-forward prediction for one fully-specified configuration."""
    idx = {m: i for i, m in enumerate(models)}
    evs = eval_seasons if eval_seasons is not None else \
        sorted(df.loc[df["season"] > base.BURN_IN_THROUGH, "season"].unique())
    preds = np.full(len(df), np.nan)
    r0 = np.full(len(df), np.nan)
    picks = []
    for s in evs:
        tr = df[df["season"] < s]
        te_idx = df.index[df["season"] == s].to_numpy()
        te = df.loc[te_idx]
        a = sw.Anchor(tr, te, bench_col)
        if not a.usable:
            continue
        r0[te_idx] = a.r0_te
        _, active = sw.regressor_cols(tr, te, models)
        if not active:
            continue
        if window is not None:
            mu, n_eff, n_seas = None, None, None
            m_, n_eff, sg_, n_seas = discounted_skill(L, N, seasons, s, 1.0, lam, window=window)
            sc = m_
        else:
            sc, n_eff, n_seas = score_models(L, N, seasons, s, rho, kappa, eta, c, lam)
        if use_cohort:
            ca = cohort_adjust(L, N, seasons, s, entry_year)
            sc = np.where(np.isfinite(ca), ca, sc)
            _, n_eff, n_seas = score_models(L, N, seasons, s, rho, kappa, eta, c, lam)

        ok = eligible(n_eff, n_seas) & np.isfinite(sc)
        est = [m for m in active if ok[idx[m]]]
        new = [m for m in active if not ok[idx[m]]]
        if not est:
            est, new = list(active), []
        est = sorted(est, key=lambda m: sc[idx[m]])[:k]

        d_tr, _ = sw.deviations(tr, est, bench_col)
        d_te, _ = sw.deviations(te, est, bench_col)
        cons_tr, cons_te = np.nanmean(d_tr, axis=1), np.nanmean(d_te, axis=1)
        if q > 0 and new:  # capped challenger sleeve for models too young to be eligible
            nd_tr, _ = sw.deviations(tr, new, bench_col)
            nd_te, _ = sw.deviations(te, new, bench_col)
            n_tr, n_te = np.nanmean(nd_tr, axis=1), np.nanmean(nd_te, axis=1)
            cons_tr = np.where(np.isfinite(n_tr), (1 - q) * cons_tr + q * n_tr, cons_tr)
            cons_te = np.where(np.isfinite(n_te), (1 - q) * cons_te + q * n_te, cons_te)
        p, g = sw.gamma_fit(a, cons_tr, cons_te)
        preds[te_idx] = p
        picks.append({"season": int(s), "gamma": float(g), "n_screened": len(est),
                      "top": ",".join(est[:5])})
    return preds, r0, pd.DataFrame(picks)


def delta(df, preds, r0, bench_col):
    """Paired ΔMSE vs R0 with season-clustered inference, on the pair's own support."""
    y = df["y"].to_numpy()
    season = df["season"].to_numpy()
    sup = (df["season"] > base.BURN_IN_THROUGH).to_numpy() & np.isfinite(preds) & np.isfinite(r0)
    d = base.sq_err(y[sup], -preds[sup]) - base.sq_err(y[sup], -r0[sup])
    dm, ci, pv = base.wild_cluster_boot(d, season[sup])
    return dm, ci, pv, int(sup.sum())


# ------------------------------------------------------------- forward selection of rho


def select_forward(df, models, bench_col, L, N, seasons, k, param, grid, fixed):
    """Pick one parameter per season by 1-SE on an inner split, never touching season s."""
    evs = sorted(df.loc[df["season"] > base.BURN_IN_THROUGH, "season"].unique())
    chosen = []
    for s in evs:
        tr_seasons = sorted(df.loc[df["season"] < s, "season"].unique())
        if len(tr_seasons) <= INNER_VAL_SEASONS + 1:
            continue
        val = tr_seasons[-INNER_VAL_SEASONS:]
        cands = []
        for v in grid:
            cfg = dict(fixed, **{param: v})
            p, r, _ = build_pred(df, models, bench_col, L, N, seasons, k,
                                 eval_seasons=val, **cfg)
            m = df["season"].isin(val).to_numpy() & np.isfinite(p)
            e = (df["y"].to_numpy()[m] - p[m]) ** 2
            cands.append((v, e if len(e) > 30 else None))
        pick = sw.pick_1se(cands)
        if pick is not None:
            chosen.append({"season": int(s), param: pick})
    return pd.DataFrame(chosen)


# ------------------------------------------------------------ Giacomini-Rossi fluctuation


def fluctuation(df, preds, r0, n_boot):
    """GR fluctuation test on season-level loss differentials vs R0.

    Statistic = max |t| over rolling windows of one third the evaluation span. Critical value
    by the same season-level wild bootstrap used everywhere else, with the null imposed.
    """
    y = df["y"].to_numpy()
    season = df["season"].to_numpy()
    sup = (df["season"] > base.BURN_IN_THROUGH).to_numpy() & np.isfinite(preds) & np.isfinite(r0)
    d = base.sq_err(y[sup], -preds[sup]) - base.sq_err(y[sup], -r0[sup])
    ss = season[sup]
    su = np.unique(ss)
    per = np.array([d[ss == s].mean() for s in su])
    m = max(4, len(su) // 3)

    def stat(x):
        # Centre before taking rolling means: the question is whether relative performance
        # CHANGES over time, not whether it is nonzero on average -- the full-sample paired
        # test already answers the latter. Centring here also matches the bootstrap below,
        # which imposes its null the same way; scoring an uncentred observed statistic
        # against a centred null distribution would reject on a constant difference.
        xc = x - x.mean()
        c = np.array([xc[i : i + m].mean() for i in range(len(xc) - m + 1)])
        sd = x.std(ddof=1) / np.sqrt(m)
        return np.max(np.abs(c)) / sd if sd > 0 else 0.0

    obs = stat(per)
    null = per - per.mean()
    draws = np.array([stat(null * base.RNG.choice([-1.0, 1.0], size=len(per)))
                      for _ in range(n_boot)])
    return float(obs), float((draws >= obs).mean()), int(len(su))


# ------------------------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    n_boot = 300 if args.quick else 2000
    base.N_BOOT = n_boot

    df, all_models = base.load()
    models = [m for m in all_models if m not in MARKET_LINES]
    entry = np.array([df.loc[df[m].notna(), "season"].min() for m in models], float)
    print(f"{len(df)} games, {len(models)} models "
          f"({len(all_models) - len(models)} market lines excluded), draws {n_boot}")

    results = {}
    for bench_col, label in (("lineopen", "opening"), ("line", "closing")):
        print(f"\n{'='*78}\nBENCHMARK: {label} line\n{'='*78}")
        L, N, seasons = season_loss_table(df, models, bench_col)
        base_cfg = dict(rho=D_RHO, kappa=D_KAPPA, eta=D_ETA, c=D_C, q=D_Q)

        # ---- 11.6 decisive diagnostic: does any rho < 1 beat rho = 1, at every k?
        print("\n-- rho grid at fixed k (ΔMSE vs R0; k is reported, never selected) --")
        hdr = "  ".join(f"{r:>7.3f}" for r in RHO)
        print(f"{'k':>4s}  {hdr}   best")
        rho_tab = []
        for k in K_GRID:
            row = []
            for rho in RHO:
                p, r, _ = build_pred(df, models, bench_col, L, N, seasons, k,
                                     **dict(base_cfg, rho=rho))
                dm, ci, pv, n = delta(df, p, r, bench_col)
                row.append(dm)
                rho_tab.append({"k": k, "rho": rho, "d_vs_r0": dm, "ci_lo": ci[0],
                                "ci_hi": ci[1], "p": pv, "n": n})
            best = RHO[int(np.argmin(row))]
            print(f"{k:>4d}  " + "  ".join(f"{v:+7.3f}" for v in row) + f"   ρ={best}")
        rho_df = pd.DataFrame(rho_tab)
        rho_df.to_csv(OUT_DIR / f"pt_recency_rho_{label}.csv", index=False)

        # ---- forward selection of rho, season by season, at the reference k
        sel = select_forward(df, models, bench_col, L, N, seasons, 20, "rho", RHO, base_cfg)
        if not sel.empty:
            share1 = float((sel["rho"] == 1.00).mean())
            print(f"\nforward-selected ρ at k=20 over {len(sel)} seasons: "
                  f"mode {sel['rho'].mode().iloc[0]}, ρ=1.00 chosen {share1:.0%} of seasons")
            sel.to_csv(OUT_DIR / f"pt_recency_rho_selected_{label}.csv", index=False)

        # ---- coordinate refinement of the remaining grids, at k=20
        print("\n-- coordinate refinement at k=20 (each grid, others at their defaults) --")
        cfg = dict(base_cfg)
        for name, grid in (("kappa", KAPPA), ("eta", ETA), ("c", C_PEN), ("q", Q_SLEEVE)):
            row = []
            for v in grid:
                p, r, _ = build_pred(df, models, bench_col, L, N, seasons, 20,
                                     **dict(cfg, **{name: v}))
                row.append((v, *delta(df, p, r, bench_col)[:1]))
            vals = "  ".join(f"{v}:{d:+.3f}" for v, d in row)
            print(f"  {name:6s} {vals}")

        # ---- robustness specifications (11.7)
        print("\n-- robustness specifications, k=20 --")
        specs = {
            "primary (ρ=1, κ=1000)": dict(base_cfg),
            "ρ=0.90": dict(base_cfg, rho=0.90),
            "blend η=0.5": dict(base_cfg, eta=0.50),
            "5-season rolling": dict(base_cfg, window=5),
            "10-season rolling": dict(base_cfg, window=10),
            "cohort-adjusted": dict(base_cfg, use_cohort=True, entry_year=entry),
            "λ=0 (no gap penalty)": dict(base_cfg, lam=0.0),
            "λ=0.5": dict(base_cfg, lam=0.5),
        }
        rob = []
        keep_primary = None
        for name, cfg_i in specs.items():
            p, r, picks = build_pred(df, models, bench_col, L, N, seasons, 20, **cfg_i)
            dm, ci, pv, n = delta(df, p, r, bench_col)
            rob.append({"spec": name, "n": n, "d_vs_r0": dm, "ci_lo": ci[0],
                        "ci_hi": ci[1], "p": pv})
            print(f"  {name:24s} n={n:6d}  Δ {dm:+7.3f} [{ci[0]:+7.3f},{ci[1]:+6.3f}]  p={pv:.4f}")
            if name.startswith("primary"):
                keep_primary = (p, r, picks)
        pd.DataFrame(rob).to_csv(OUT_DIR / f"pt_recency_robust_{label}.csv", index=False)

        # ---- post-2014 / post-2021 expanding samples
        for cut in (2014, 2021):
            p, r, _ = build_pred(df, models, bench_col, L, N, seasons, 20, **base_cfg)
            m = (df["season"] >= cut).to_numpy() & np.isfinite(p) & np.isfinite(r)
            y = df["y"].to_numpy()
            d = base.sq_err(y[m], -p[m]) - base.sq_err(y[m], -r[m])
            dm, ci, pv = base.wild_cluster_boot(d, df["season"].to_numpy()[m])
            print(f"  {'post-' + str(cut) + ' only':24s} n={int(m.sum()):6d}  "
                  f"Δ {dm:+7.3f} [{ci[0]:+7.3f},{ci[1]:+6.3f}]  p={pv:.4f}")

        # ---- 11.5 Giacomini-Rossi fluctuation test
        p, r, picks = keep_primary
        obs, pv, nseas = fluctuation(df, p, r, n_boot)
        print(f"\nGiacomini-Rossi fluctuation, screened consensus vs R0 "
              f"({nseas} seasons): stat {obs:.3f}  p={pv:.4f}  "
              f"({'UNSTABLE over time' if pv < 0.05 else 'no detected instability'})")

        if not picks.empty:
            print(f"\nscreened-consensus γ, last 3 seasons: "
                  + ", ".join(f"{r_.season}:{r_.gamma:+.3f}" for r_ in picks.tail(3).itertuples()))
            print(f"most recent top-5: {picks.iloc[-1].top}")

        results[label] = {"rho_grid": rho_tab, "robust": rob,
                          "gr_fluctuation": {"stat": obs, "p": pv, "seasons": nseas},
                          "rho_selected_share_1": share1 if not sel.empty else None}

    (OUT_DIR / "pt_recency_screen.json").write_text(json.dumps(results, indent=2, default=float))
    print(f"\nwrote {OUT_DIR}/pt_recency_screen.json and per-benchmark CSVs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
