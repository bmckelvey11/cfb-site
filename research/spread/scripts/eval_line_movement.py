"""Version A of research/spread/docs/prereg-line-movement.md: predict the CLOSE from the opener.

The combination sweep predicted the game margin against the closing line and found nothing.
This retargets the same machinery: target y = closing line (in margin space, like every `mkt`
in the sweep), anchor = opening line. Every estimator then forecasts where the line goes, and
`prior_skill` -- which scores each model's error against y -- becomes prior MOVEMENT skill for
free, which is what the pre-registration asks the screen to use.

`lineca` and `linemidweek` are removed before anything runs: `lineca` IS the closing line on
two thirds of games, so leaving it in would be leakage of the target into the regressors.

    python research/spread/scripts/eval_line_movement.py
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
import eval_combination_sweep as sweep  # noqa: E402

MARKET_LINES = base.MARKET_LINES
METHODS = ["E6", "E7", "E14"]          # M3 ridge, M2 k-by-rule, M4 screened CSR (version A)
METHODS_A2 = ["E6", "E7", "E8", "E9", "E10", "E11", "E12", "E13", "E14"]  # amendment A2
WIDE_LAMBDA = [10.0, 100.0, 1000.0, 1e4, 1e5, 1e6]
BREAKEVEN = 0.5238
FRACS = (0.0, 0.25, 0.5, 0.75, 1.0)
THRESH = (1.0, 2.0)
OUT = base.OUT_DIR


def cluster_rate(win, season):
    """Win rate with a season-cluster wild bootstrap CI (reuses the sweep's bootstrap)."""
    d = win - BREAKEVEN
    dm, ci, p = base.wild_cluster_boot(d, season)
    return {"n": int(len(win)), "rate": float(win.mean()), "lo": float(BREAKEVEN + ci[0]),
            "hi": float(BREAKEVEN + ci[1]), "p_vs_breakeven": float(p)}


def decontaminate(df, models, before_season=None):
    """rho_i = corr(f_i - open, close - open); drop the top decile before fitting.

    Amendment A6 (research/spread/docs/prereg-line-movement.md): A3 ran this once on the
    FULL 2001-2025 frame, so the retained panel's identity was chosen with knowledge of the
    evaluation seasons it was later scored on -- the direction of the bias on R^2 is
    conservative (the screen removes the *most* target-correlated columns), but conservative
    is not the same as fixed-in-advance, and a screen that saw its own test set makes every
    downstream p-value conditional on that screen.

    `before_season=None` reproduces the original full-sample screen unchanged (still what
    `--decontaminate` runs). `before_season=s` restricts rho to games with season < s, which
    is what `--decontaminate-wf` calls once per evaluation season so the drop list for season
    s never reads season s or later.

    Returns (kept_models, dropped_models sorted by rho descending, rho dict).
    """
    hist = df if before_season is None else df[df["season"] < before_season]
    open_m, close_m = -hist["lineopen"].to_numpy(float), -hist["line"].to_numpy(float)
    move = close_m - open_m
    rho = {}
    for m in models:
        f = -hist[m].to_numpy(float)
        ok = np.isfinite(f) & np.isfinite(move)
        if ok.sum() >= 400 and (f[ok] - open_m[ok]).std() > 0:
            rho[m] = float(np.corrcoef(f[ok] - open_m[ok], move[ok])[0, 1])
    if not rho:
        return list(models), [], rho
    cut = float(np.quantile(list(rho.values()), 0.90))
    dropped = sorted((m for m, r in rho.items() if r >= cut), key=rho.get, reverse=True)
    kept = [m for m in models if m not in set(dropped)]
    return kept, dropped, rho


def sweep_walk_forward(df, models, bench_col, only, grids):
    """Run `sweep.sweep` season by season, rebuilding `decontaminate` from only the seasons
    strictly before each evaluation season (amendment A6).

    `sweep.sweep` already fits every method walk-forward within one call (`tr = df[df.season
    < s]` inside its own loop), but it takes one fixed model list for the whole call -- the
    decontamination screen has to vary by evaluation season, so this calls it once per season,
    each time on a frame truncated to `season <= s` with `base.BURN_IN_THROUGH` shifted to
    `s - 1` so `sweep.sweep`'s own season list collapses to `[s]`. Total work is the same
    order as one full-panel call: each season is fit exactly once, just via N calls instead
    of one.
    """
    eval_seasons = sorted(df.loc[df["season"] > base.BURN_IN_THROUGH, "season"].unique())
    keys = list(only) + ["R0", "E4"]
    preds = {k: np.full(len(df), np.nan) for k in keys}
    chosen_parts, coefs_parts = [], []
    drop_lists, rho_by_season = {}, {}
    orig_burn_in = base.BURN_IN_THROUGH
    try:
        for s in eval_seasons:
            kept, dropped, rho = decontaminate(df, models, before_season=s)
            drop_lists[int(s)] = dropped
            rho_by_season[int(s)] = rho
            df_s = df[df["season"] <= s]
            base.BURN_IN_THROUGH = int(s) - 1
            p, ch, co, _ = sweep.sweep(df_s, kept, bench_col, verbose=False, grids=grids, only=only)
            local = (df_s["season"] == s).to_numpy()
            global_ = (df["season"] == s).to_numpy()
            for k in keys:
                preds[k][global_] = p[k][local]
            if not ch.empty:
                chosen_parts.append(ch)
            if not co.empty:
                coefs_parts.append(co)
    finally:
        base.BURN_IN_THROUGH = orig_burn_in
    chosen = (pd.concat(chosen_parts, ignore_index=True) if chosen_parts
              else pd.DataFrame(columns=["season", "method", "param"]))
    coefs = (pd.concat(coefs_parts, ignore_index=True) if coefs_parts
             else pd.DataFrame(columns=["season", "method", "coef"]))
    return preds, chosen, coefs, eval_seasons, drop_lists, rho_by_season


def main() -> int:
    global METHODS
    ap = argparse.ArgumentParser()
    ap.add_argument("--amend", action="store_true", help="amendment A2: all methods, wide ridge grid")
    ap.add_argument("--decontaminate", action="store_true",
                    help="drop the top decile of models by corr(f_i - open, close - open) first")
    ap.add_argument("--decontaminate-wf", action="store_true",
                    help="amendment A6: same screen, rebuilt per evaluation season from only "
                         "the seasons before it -- --decontaminate's screen saw its own test set")
    args = ap.parse_args()
    suffix = ("_a2" if args.amend else "") + (
        "_decon_wf" if args.decontaminate_wf else "_decon" if args.decontaminate else "")
    grids = None
    if args.amend:
        METHODS = METHODS_A2
        grids = {k: list(v) for k, v in sweep.GRIDS.items()}
        grids["E6"] = WIDE_LAMBDA
    df, models = base.load()
    models = [m for m in models if m not in MARKET_LINES]
    df = df[df["line"].notna() & df["lineopen"].notna()].reset_index(drop=True)
    dropped = []
    drop_lists_by_season, rho_by_season = {}, {}
    if args.decontaminate and not args.decontaminate_wf:
        # Decontamination (review 2026-09-08 §1.1; corrected by amendment A6). A column that
        # reprints the mid-week line predicts close - open mechanically. rho_i = corr(f_i -
        # open, close - open) on the model's own games; the top decile is removed BEFORE
        # anything is fitted. The direction of the bias on R^2 is conservative -- the screen
        # removes the *most* target-correlated columns -- but this full-sample rho is computed
        # over the evaluation seasons too, so the retained panel's identity was chosen with
        # knowledge of its own test set: conservative is not the same as fixed-in-advance, and
        # every A3 p-value is conditional on this screen. See --decontaminate-wf (amendment A6)
        # for the walk-forward version, which builds each season's drop list from earlier
        # seasons only.
        models, dropped, rho = decontaminate(df, models, before_season=None)
        cut = min(rho[m] for m in dropped) if dropped else float("nan")
        print(f"decontaminate: dropped {len(dropped)} models at rho >= {cut:.3f}: "
              + ", ".join(f"{m} ({rho[m]:.2f})" for m in dropped))
    df["margin"] = df["y"]                    # keep the real outcome for the decay curve
    df["y"] = -df["line"].to_numpy(float)     # TARGET: the close, in margin space
    print(f"{len(df)} games with open and close, {len(models)} models, "
          f"seasons {df.season.min()}-{df.season.max()}, bootstrap draws {base.N_BOOT}")

    if args.decontaminate_wf:
        (preds, chosen, coefs, seasons,
         drop_lists_by_season, rho_by_season) = sweep_walk_forward(
            df, models, "lineopen", only=METHODS, grids=grids)
        dropped = drop_lists_by_season.get(seasons[-1], [])
        counts = {}
        for lst in drop_lists_by_season.values():
            for m in lst:
                counts[m] = counts.get(m, 0) + 1
        always_dropped = sorted(m for m, c in counts.items() if c == len(seasons))
        print(f"decontaminate-wf: {len(seasons)} evaluation seasons; last season "
              f"({seasons[-1]}) dropped {len(dropped)} models: {', '.join(dropped)}")
        print("  models dropped in every evaluation season they had history for: "
              + (", ".join(always_dropped) if always_dropped else "(none)"))
    else:
        preds, chosen, coefs, seasons = sweep.sweep(df, models, "lineopen", only=METHODS, grids=grids)

    y = df["y"].to_numpy()                    # close (margin space)
    open_m = -df["lineopen"].to_numpy(float)  # opener (margin space)
    margin = df["margin"].to_numpy(float)
    season = df["season"].to_numpy()
    ev = (df["season"] > base.BURN_IN_THROUGH).to_numpy()
    move = y - open_m

    sup = ev & np.isfinite(preds["R0"]) & np.isfinite(preds["E4"])
    for k in METHODS:
        sup &= np.isfinite(preds[k])
    n = int(sup.sum())
    print(f"\n-- common support n={n}, seasons {seasons[0]}-{seasons[-1]} --")
    print(f"   sd(close - open) on support: {move[sup].std():.3f}")

    out = {"n": n, "seasons": [int(s) for s in seasons], "sd_move": float(move[sup].std()),
           "n_models": len(models), "dropped_models": dropped}
    if args.decontaminate_wf:
        # dropped_models above is the LAST evaluation season's list (most history available,
        # closest to the full-sample screen's window) -- kept as the single headline number.
        # drop_lists_by_season is every season's list, for the overlap report against A3.
        out["drop_lists_by_season"] = {str(s): lst for s, lst in drop_lists_by_season.items()}
    rows = []
    r0 = preds["R0"]
    base_mse = float(((y - open_m) ** 2)[sup].mean())     # M0: no movement
    for k in ["R0", "E4"] + METHODS:
        p = preds[k]
        err = (y - p) ** 2
        r2 = 1 - float(err[sup].mean()) / base_mse
        d_r0 = err[sup] - ((y - r0) ** 2)[sup]
        dm, ci, pv = base.wild_cluster_boot(d_r0, season[sup]) if k != "R0" else (0.0, (0.0, 0.0), 1.0)
        pm = p - open_m
        moved = sup & (move != 0) & (np.abs(pm) >= 1.0)
        direction = float((np.sign(pm[moved]) == np.sign(move[moved])).mean()) if moved.any() else np.nan
        rows.append({"method": k, "r2_vs_open": r2, "d_mse_vs_r0": dm, "ci_lo": ci[0], "ci_hi": ci[1],
                     "p": pv, "frac_seasons": sweep.season_win_rate(y, p, r0, season, sup),
                     "direction_hit": direction, "n_direction": int(moved.sum()),
                     "mean_abs_pred_move": float(np.abs(pm[sup]).mean())})
    tab = pd.DataFrame(rows).set_index("method")
    tab.loc[METHODS, "holm"] = sweep.holm(tab.loc[METHODS, "p"].to_numpy())
    pd.set_option("display.width", 160)
    print("\nA1/A2  target = close, anchor = open.  R^2 relative to 'line does not move'.")
    print(tab.round(4).to_string())
    out["table"] = json.loads(tab.reset_index().to_json(orient="records"))
    out["chosen_params"] = json.loads(chosen.to_json(orient="records"))
    out["coefs"] = json.loads(coefs.to_json(orient="records"))
    g4 = coefs[coefs.method == "E4"].coef
    print(f"\nE4 gamma on movement: min {g4.min():.3f} median {g4.median():.3f} max {g4.max():.3f}")
    print("chosen hyperparameters (endpoint hits are reported, not widened):")
    print(chosen.groupby("method")["param"].value_counts().to_string())

    # A3 decay curve: enter at open + f*(close-open); back E4's side when it disagrees by >= thr
    print("\nA3  ATS at the entry price, side = E4 vs entry, re-selected at each f")
    p4 = preds["E4"]
    decay = []
    for thr in THRESH:
        for f in FRACS:
            entry = open_m + f * move
            edge = p4 - entry
            m = sup & (np.abs(edge) >= thr) & np.isfinite(margin)
            res = np.sign(edge[m]) * (margin[m] - entry[m])   # >0 covered at the entry number
            keep = res != 0
            win = (res[keep] > 0).astype(float)
            r = cluster_rate(win, season[m][keep])
            r.update({"thr": thr, "f": f, "roi_110": float(r["rate"] * (1 + 100 / 110) - 1)})
            decay.append(r)
            print(f"  |edge|>={thr:.0f}  f={f:.2f}  n={r['n']:5d}  win {r['rate']:.4f} "
                  f"[{r['lo']:.3f}, {r['hi']:.3f}]  p={r['p_vs_breakeven']:.3f}  ROI@-110 {r['roi_110']:+.3f}")
    out["decay"] = decay

    # CLV at the opener for every method: back its side when it predicts a move >= thr
    print("\nCLV at the OPENER by method (side = method vs open; CLV = points the close moved toward the bet)")
    clv_rows = []
    for k in ["E4"] + METHODS:
        for thr in THRESH:
            pm = preds[k] - open_m
            m = sup & (np.abs(pm) >= thr) & np.isfinite(margin)
            if m.sum() < 30:
                continue
            side = np.sign(pm[m])
            clv = side * move[m]
            cm, cci, _ = base.wild_cluster_boot(clv, season[m])
            res = side * (margin[m] - open_m[m])
            keep = res != 0
            r = cluster_rate((res[keep] > 0).astype(float), season[m][keep])
            clv_rows.append({"method": k, "thr": thr, "bets": int(m.sum()), "clv": float(clv.mean()),
                             "clv_lo": float(cci[0]), "clv_hi": float(cci[1]),   # boot CI is absolute
                             "beat_close": float((clv > 0).mean()), "ats_open": r["rate"],
                             "ats_lo": r["lo"], "ats_hi": r["hi"]})
            print(f"  {k:4s} pred>={thr:.0f}  bets {m.sum():5d}  CLV {clv.mean():+.2f} "
                  f"[{cci[0]:+.2f},{cci[1]:+.2f}]  beat close {(clv>0).mean():.1%}  "
                  f"ATS@open {r['rate']:.4f} [{r['lo']:.3f},{r['hi']:.3f}]")
    out["clv_open"] = clv_rows

    pd.DataFrame({"game_id": df["game_id"], "season": season, "open": open_m, "close": y,
                  "margin": margin, **{k: preds[k] for k in ["R0", "E4"] + METHODS}})[sup].to_csv(
        OUT / f"pt_movement_preds{suffix}.csv", index=False)
    (OUT / f"pt_movement{suffix}.json").write_text(json.dumps(out, indent=2, default=float))
    print(f"\nwrote {OUT / f'pt_movement_preds{suffix}.csv'} and {OUT / f'pt_movement{suffix}.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
