"""Where the market misprices totals, as a surface in (spread, total).

Implements `PLAN.md`. Read that first -- the specification, the dependence
structure, the multiplicity budget, and the MDE table are pre-committed there, and
this script is only their execution.

The one design point worth repeating here, because it is what makes the script
look odd: everything is fit on ALL graded games, not on the 234 bets. Inside the
bet set `bias = f(spread, total)` and the 1.75 gate is a level curve of it, so
spread and total are collinear by construction and their separate effects are not
identified. The full sample has support across the whole rectangle.

That buys a statement about where the MARKET misprices totals -- the right input to
a gate -- and not a statement about the model's record in a region, since outside
the gate the model does not bet.

    python models/over_zero/research/2026-09-10_spread_magnitude/edge_surface.py
    python models/over_zero/research/2026-09-10_spread_magnitude/edge_surface.py --since 2022
    python models/over_zero/research/2026-09-10_spread_magnitude/edge_surface.py --until 2025
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import patsy
from scipy import stats

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "models" / "over_zero" / "v1"))
sys.path.insert(0, str(Path.home() / ".claude" / "skills" / "econometrics"))

from censoring_bias import implied_team_points  # noqa: E402
from toolkit.dependence import cluster_ols, wild_cluster_bootstrap  # noqa: E402

BETS = REPO / "models" / "over_zero" / "docs" / "backtest_bets.csv"
BREAK_EVEN = 100 / 110
# PLAN.md 5: fixed in advance, not searched. Spread bands carry over from
# RESULTS.md; total bands are full-sample terciles.
SPREAD_BANDS = [(0, 20), (20, 30), (30, 40), (40, 50), (50, 99)]
N_BOOT = 9999


def load(path: Path, since: int | None = None,
         until: int | None = None) -> pd.DataFrame:
    d = pd.read_csv(path)
    if since:
        d = d[d.season >= since].copy()
    if until:
        d = d[d.season <= until].copy()
    dog_imp, fav_imp = implied_team_points(d.spread.to_numpy(), d.total.to_numpy())
    d["total_err"] = d.actual_total - d.total
    d["fav_err"] = d.fav_pts - fav_imp
    d["dog_err"] = d.dog_pts - dog_imp
    return d


def boot_mean(x: np.ndarray, clusters: np.ndarray) -> tuple[float, float, float]:
    """Cluster-robust mean of one column, as an intercept-only wild bootstrap.

    A single constant regressor makes the coefficient the mean, so the same
    few-cluster machinery covers a plain group average -- which matters because
    every band mean below is quoted as evidence and so needs an interval.
    """
    X = np.ones((len(x), 1))
    r = wild_cluster_bootstrap(X, x, clusters, coef=0, n_boot=N_BOOT, seed=0)
    return r["beta"], r["ci"][0], r["ci"][1]


def band_table(d: pd.DataFrame, col: str) -> pd.DataFrame:
    rows = []
    for lo, hi in SPREAD_BANDS:
        x = d[(d.spread > lo) & (d.spread <= hi)]
        if len(x) < 10:
            rows.append({"spread": f"{lo}-{hi}", "n": len(x)})
            continue
        est, clo, chi = boot_mean(x[col].to_numpy(), x.season.to_numpy())
        rows.append({"spread": f"{lo}-{hi}" if hi < 99 else f">{lo}", "n": len(x),
                     "mean": est, "ci_lo": clo, "ci_hi": chi})
    return pd.DataFrame(rows)


def spec(d: pd.DataFrame, formula: str, label: str, test: list[str]) -> None:
    """Fit one pre-registered spec; wild-bootstrap the coefficients named in `test`."""
    y, X = patsy.dmatrices(f"total_err ~ {formula}", d, return_type="dataframe")
    names = list(X.columns)
    Xa, ya, cl = X.to_numpy(), y.to_numpy().ravel(), d.season.to_numpy()
    r = cluster_ols(Xa, ya, cl)
    print(f"\n--- {label}: total_err ~ {formula} ---")
    print(f"    n={r.n_obs}, clusters={r.n_clusters} (season), CR1 + wild bootstrap")
    for i, nm in enumerate(names):
        line = f"    {nm:28s} {r.beta[i]:+8.4f}  CR1 se {r.se[i]:6.4f}"
        if nm in test:
            wb = wild_cluster_bootstrap(Xa, ya, cl, coef=i, n_boot=N_BOOT, seed=0)
            line += (f"  boot p {wb['p_value']:.4f}  "
                     f"boot CI [{wb['ci'][0]:+.4f}, {wb['ci'][1]:+.4f}]")
        print(line)


def surface_readout(d: pd.DataFrame) -> None:
    """The spline spec's fitted total_err along spread, at the sample's median total.

    Reading the fit rather than a bin is the whole point of fitting it: the >50 cell
    has 41 games in ten seasons and cannot support a cell estimate (PLAN.md 6). The
    smooth borrows strength -- which is an assumption, and is why this is printed as
    a fitted curve, not as data.
    """
    # No intercept: the natural-spline basis already spans the constant, and
    # leaving both in makes the design rank-deficient (unstable beta, junk SEs).
    f = "cr(spread, df=4) + total - 1"
    y, X = patsy.dmatrices(f"total_err ~ {f}", d, return_type="dataframe")
    r = cluster_ols(X.to_numpy(), y.to_numpy().ravel(), d.season.to_numpy())
    grid = pd.DataFrame({"spread": np.arange(5, 61, 5.0), "total": d.total.median()})
    Xg = patsy.build_design_matrices([X.design_info], grid)[0]
    fit = np.asarray(Xg) @ r.beta
    print(f"\n--- fitted total_err along spread (spline df=4, total at "
          f"{d.total.median():g}) ---")
    print("    " + "  ".join(f"{s:>5.0f}" for s in grid.spread))
    print("    " + "  ".join(f"{v:>5.2f}" for v in fit))


def fixed_cap(d: pd.DataFrame, cap: float | None) -> dict:
    """The deployed rule with a spread cap bolted on, graded IN SAMPLE.

    `passes_filter` is itself walk-forward, but the cap is not: every cap below was
    chosen by looking at these same 234 bets (RESULTS.md). This table is therefore
    selection, not confirmation, and is printed only so the size of that selection
    is visible next to `walk_forward_cap`, which is the honest version.
    """
    b = d[d.passes_filter == 1]
    if cap is not None:
        b = b[b.spread <= cap]
    n = len(b)
    w = int(b.over.sum())
    return {"cap": cap if cap is not None else "none", "n": n,
            "record": f"{w}-{n - w}", "hit": w / n,
            "roi": (w * BREAK_EVEN - (n - w)) / n}


def walk_forward_cap(d: pd.DataFrame, caps=(None, 50, 45, 40),
                     first: int = 2018) -> pd.DataFrame:
    """Pick the cap on seasons < t, grade season t, pool. The actual gate.

    This is the only comparison that answers "would capping have helped?" without
    grading the cap on the data that chose it (PLAN.md 7). If the picked-forward
    column does not beat the uncapped column, the cap is not adopted -- however good
    the in-sample table looks.
    """
    b = d[d.passes_filter == 1]
    picked, rows = [], []
    for t in sorted(s for s in b.season.unique() if s >= first):
        prior = b[b.season < t]
        best, best_roi = None, -np.inf
        for c in caps:
            x = prior if c is None else prior[prior.spread <= c]
            if len(x) < 10:
                continue
            w = int(x.over.sum())
            roi = (w * BREAK_EVEN - (len(x) - w)) / len(x)
            if roi > best_roi:
                best, best_roi = c, roi
        cur = b[b.season == t]
        sel = cur if best is None else cur[cur.spread <= best]
        picked.append(sel)
        rows.append({"season": t, "cap_picked": best if best is not None else "none",
                     "n_capped": len(sel), "n_uncapped": len(cur)})
    print()
    print("    per-season cap chosen on prior seasons only:")
    print(pd.DataFrame(rows).to_string(index=False))
    P = pd.concat(picked)
    # Seasons where the picked cap was `none` contribute the SAME bets to both
    # columns, so pooling them makes the two rules look more alike than they are
    # and pads the kept side with games nothing could have been dropped from.
    # The binding window is the like-for-like comparison.
    bind = [r["season"] for r in rows if r["cap_picked"] != "none"]
    out = []
    for lab, frame in (("picked fwd (all)", P),
                       ("uncapped (all)", b[b.season >= first]),
                       ("picked fwd (binding)", P[P.season.isin(bind)]),
                       ("uncapped (binding)", b[b.season.isin(bind)])):
        n = len(frame)
        w = int(frame.over.sum())
        out.append({"rule": lab, "n": n, "record": f"{w}-{n - w}", "hit": w / n,
                    "roi": (w * BREAK_EVEN - (n - w)) / n})
    return pd.DataFrame(out)


def total_bands(d: pd.DataFrame) -> pd.DataFrame:
    """Bet record by posted total. Descriptive ONLY -- see PLAN.md 2.

    Within the bet set total is collinear with spread by construction, so a split
    on total is very nearly the same split as on spread and cannot be read as a
    separate total effect. The separable estimate is the `total` coefficient in the
    full-sample regressions above.
    """
    b = d[d.passes_filter == 1]
    edges = [0, 55, 60, 65, 99]
    rows = []
    for lo, hi in zip(edges, edges[1:]):
        x = b[(b.total > lo) & (b.total <= hi)]
        if not len(x):
            continue
        w = int(x.over.sum())
        rows.append({"total": f"{lo}-{hi}" if hi < 99 else f">{lo}", "n": len(x),
                     "record": f"{w}-{len(x) - w}", "hit": w / len(x),
                     "mean_spread": x.spread.mean()})
    return pd.DataFrame(rows)


def cap_delta(d: pd.DataFrame, cap: float = 50.0, n_boot: int = 9999) -> pd.DataFrame:
    """Headline before/after: what the cap moves, with a season-cluster bootstrap.

    Read the interval for what it is. The two samples are nested, so this is not a
    test of whether the cap helps -- `gate_inference` is that -- and the cap was
    chosen knowing these seasons, which no bootstrap can undo. The CI answers only
    "how stable is this arithmetic when seasons are resampled", which is worth
    knowing and is not evidence the effect is real.

    `flat_units` is the column that keeps the ROI honest: the gain shows up by
    shrinking the denominator, not by winning more money.
    """
    rng = np.random.default_rng(0)
    b = d[d.passes_filter == 1]

    def hit_roi(x):
        n = len(x)
        w = int(x.over.sum())
        return w / n, (w * BREAK_EVEN - (n - w)) / n

    rows = []
    # Labels come from the seasons actually present: the ledger's span moved when
    # the model switched to the warehouse source, and fixed year labels went stale.
    for tag, first in (("(all)", 2016), ("", 2018), ("(binding)", 2021)):
        f = b[b.season >= first]
        lab = f"{f.season.min()}-{f.season.max()} {tag}".strip()
        k = f[f.spread <= cap]
        h0, r0 = hit_roi(f)
        h1, r1 = hit_roi(k)
        seasons = f.season.unique()
        dh, dr = [], []
        for _ in range(n_boot):
            s = pd.concat([f[f.season == p]
                           for p in rng.choice(seasons, len(seasons), replace=True)])
            ks = s[s.spread <= cap]
            if not len(ks):
                continue
            bh, br = hit_roi(ks)
            ah, ar = hit_roi(s)
            dh.append(bh - ah)
            dr.append(br - ar)
        rows.append({
            "window": lab, "n": len(f), "n_capped": len(k),
            "hit": h0, "hit_capped": h1, "d_hit_pp": (h1 - h0) * 100,
            "d_hit_ci": f"[{np.percentile(dh, 2.5) * 100:+.2f}, "
                        f"{np.percentile(dh, 97.5) * 100:+.2f}]",
            "roi": r0, "roi_capped": r1, "d_roi_pp": (r1 - r0) * 100,
            "d_roi_ci": f"[{np.percentile(dr, 2.5) * 100:+.2f}, "
                        f"{np.percentile(dr, 97.5) * 100:+.2f}]",
            "units": f.flat_units_pnl.sum(),
            "units_capped": k.flat_units_pnl.sum()})
    return pd.DataFrame(rows)


def gate_inference(d: pd.DataFrame, cap: float = 50.0, first: int = 2018) -> None:
    """Kept vs dropped under a FIXED cap, with the test and the MDE beside it.

    The comparison that matters for adoption is not "capped vs uncapped" -- those
    samples are nested, so the capped one is the uncapped one minus a slice. The
    honest question is whether the SLICE the cap removes is worse than what stays,
    which is a 2x2 on disjoint groups.
    """
    b = d[(d.passes_filter == 1) & (d.season >= first)]
    kept, dropped = b[b.spread <= cap], b[b.spread > cap]
    rows = []
    for lab, x in (("kept", kept), ("dropped", dropped), ("uncapped", b)):
        n = len(x)
        w = int(x.over.sum())
        lo, hi = stats.beta.ppf([0.025, 0.975], w + 0.5, n - w + 0.5)
        rows.append({"group": lab, "n": n, "record": f"{w}-{n - w}", "hit": w / n,
                     "ci_lo": lo, "ci_hi": hi, "roi": (w * BREAK_EVEN - (n - w)) / n,
                     "flat_units": x.flat_units_pnl.sum()})
    print(pd.DataFrame(rows).to_string(index=False,
                                       float_format=lambda v: f"{v:.4f}"))
    tab = [[int(kept.over.sum()), len(kept) - int(kept.over.sum())],
           [int(dropped.over.sum()), len(dropped) - int(dropped.over.sum())]]
    se = np.sqrt(0.5238 * (1 - 0.5238) / len(dropped))
    print(f"    kept vs dropped {tab}  Fisher two-sided p = "
          f"{stats.fisher_exact(tab)[1]:.4f}")
    print(f"    MDE on the dropped slice (n={len(dropped)}): {2.8 * se * 100:.1f}pp; "
          f"observed gap {abs(kept.over.mean() - dropped.over.mean()) * 100:.1f}pp")


CAP_GRID = np.arange(34, 63, 1.0)
# Fine bands, NOT pre-registered: PLAN.md 5 fixed 30-40/40-50/>50, and these 5-point
# slices were cut afterwards, once the coarse >50 band came back ambiguous. They are
# reported as exploratory. What they buy is real -- the coarse band pooled 50-55 with
# a 6-0 noise cell above 55 -- but a reader has to be able to see they came second.
FINE_BANDS = [(35, 40), (40, 45), (45, 50), (50, 55), (55, 62)]


def _objective(x: pd.DataFrame, obj: str) -> float:
    """Total flat units, or ROI per bet. They do not agree, and that is the point.

    ROI per bet is DEGENERATE as a cap objective: tightening the cap can only raise
    it, because the marginal bets a tighter cap removes are the ones nearest
    break-even. Maximizing it is a definition, not a discovery. Units is the
    objective a bankroll actually has.
    """
    n = len(x)
    w = int(x.over.sum())
    return (x.flat_units_pnl.sum() if obj == "units"
            else (w * BREAK_EVEN - (n - w)) / n)


def best_cap(f: pd.DataFrame, obj: str, min_n: int = 20) -> float | None:
    best, best_v = None, -np.inf
    for c in CAP_GRID:
        x = f[f.spread <= c]
        if len(x) < min_n:
            continue
        v = _objective(x, obj)
        if v > best_v:
            best, best_v = c, v
    return best


def cap_grid(d: pd.DataFrame) -> pd.DataFrame:
    """In-sample profile of every cap. The winner here is the selection estimate."""
    b = d[d.passes_filter == 1]
    rows = []
    for c in CAP_GRID:
        x = b[b.spread <= c]
        if len(x) < 20:
            continue
        n = len(x)
        w = int(x.over.sum())
        rows.append({"cap": c, "n": n, "record": f"{w}-{n - w}", "hit": w / n,
                     "roi": (w * BREAK_EVEN - (n - w)) / n,
                     "units": x.flat_units_pnl.sum()})
    return pd.DataFrame(rows)


def argmax_bootstrap(d: pd.DataFrame, obj: str = "units", n_boot: int = 2000) -> None:
    """How well determined is the argmax? Resample seasons and re-optimize.

    A point estimate of an optimum means nothing without this. If the argmax moves
    across most of the grid under resampling, there is no optimum to find and the
    honest output is a bound, not a number.
    """
    rng = np.random.default_rng(0)
    b = d[d.passes_filter == 1]
    seasons = b.season.unique()
    picks = []
    for _ in range(n_boot):
        s = pd.concat([b[b.season == p]
                       for p in rng.choice(seasons, len(seasons), replace=True)])
        c = best_cap(s, obj)
        if c is not None:
            picks.append(c)
    picks = np.array(picks)
    counts = pd.Series(picks).value_counts().sort_index()
    print(f"    objective={obj}: full-sample argmax {best_cap(b, obj):g}, "
          f"resample 2.5-97.5 pct [{np.percentile(picks, 2.5):g}, "
          f"{np.percentile(picks, 97.5):g}]")
    print("      modes: " + ", ".join(f"{k:g}x{v}" for k, v in counts.items()
                                      if v >= n_boot * 0.02))


def optimizer_vs_fixed(d: pd.DataFrame, fixed: float = 50.0,
                       first: int = 2019) -> pd.DataFrame:
    """Let the cap be FITTED on prior seasons, then grade it forward.

    The comparison is against a cap nobody fitted. If a fitted cap loses to a round
    number out of sample, the lesson is about the fitting, not about the number --
    `fixed` came from this same data too and is not being validated here.
    """
    b = d[d.passes_filter == 1]
    years = [s for s in sorted(b.season.unique()) if s >= first]
    rows = []
    for obj in ("units", "roi"):
        picked, chosen = [], []
        for t in years:
            c = best_cap(b[b.season < t], obj)
            cur = b[b.season == t]
            picked.append(cur if c is None else cur[cur.spread <= c])
            chosen.append(f"{t}:{c:g}" if c is not None else f"{t}:none")
        print(f"    cap fitted forward on {obj}: " + " ".join(chosen))
        rows.append(("cap fitted fwd (%s)" % obj, pd.concat(picked)))
    u = b[b.season >= first]
    rows += [(f"fixed cap {fixed:g}", u[u.spread <= fixed]), ("no cap", u)]
    out = []
    for lab, f in rows:
        n = len(f)
        w = int(f.over.sum())
        out.append({"rule": lab, "n": n, "record": f"{w}-{n - w}", "hit": w / n,
                    "roi": (w * BREAK_EVEN - (n - w)) / n,
                    "units": f.flat_units_pnl.sum()})
    return pd.DataFrame(out)


def fine_bands(d: pd.DataFrame) -> pd.DataFrame:
    """5-point bands across the turn, all graded games. Exploratory -- see FINE_BANDS."""
    rows = []
    for lo, hi in FINE_BANDS:
        x = d[(d.spread > lo) & (d.spread <= hi)]
        r = {"band": f"{lo}-{hi}", "n": len(x)}
        if len(x) >= 10:
            for col in ("total_err", "fav_err", "dog_err"):
                e, clo, chi = boot_mean(x[col].to_numpy(), x.season.to_numpy())
                r[col] = e
                r[col + "_ci"] = f"[{clo:+.1f},{chi:+.1f}]"
        rows.append(r)
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bets", default=str(BETS))
    ap.add_argument("--since", type=int, help="restrict to seasons >= this")
    ap.add_argument("--until", type=int, help="restrict to seasons <= this")
    args = ap.parse_args()

    d = load(Path(args.bets), args.since, args.until)
    print(f"{len(d):,} graded games, seasons {d.season.min()}-{d.season.max()}, "
          f"{int(d.passes_filter.sum())} qualifying bets")

    # PLAN.md 2: two specs, both declared in advance, both reported.
    spec(d, "spread + total + spread:total", "spec A (linear)",
         ["spread", "total", "spread:total"])
    spec(d, "cr(spread, df=4) + total - 1", "spec B (spline in spread)", ["total"])
    surface_readout(d)

    print("\n--- market total error by spread band, ALL graded games ---")
    print(band_table(d, "total_err").to_string(index=False,
                                               float_format=lambda v: f"{v:.2f}"))
    print("\n--- leg decomposition, ALL graded games ---")
    for col in ("fav_err", "dog_err"):
        t = band_table(d, col)
        print(f"  {col}")
        print(t.to_string(index=False, float_format=lambda v: f"{v:.2f}"))

    print("--- bet record by posted total (DESCRIPTIVE, collinear with spread) ---")
    print(total_bands(d).to_string(index=False,
                                   float_format=lambda v: f"{v:.3f}"))

    print()
    print("--- spread caps, graded in sample (selection, NOT confirmation) ---")
    print(pd.DataFrame([fixed_cap(d, c) for c in (None, 50, 45, 40)])
          .to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    print()
    print("--- the gate: cap picked on prior seasons only (PLAN.md 7) ---")
    print(walk_forward_cap(d).to_string(index=False,
                                        float_format=lambda v: f"{v:.4f}"))

    for first in (2018, 2021):
        print()
        print(f"--- fixed cap 50, kept vs dropped, "
              f"{max(first, d.season.min())}-{d.season.max()} ---")
        gate_inference(d, first=first)

    print()
    print("--- what the cap moves (nested; see cap_delta docstring) ---")
    print(cap_delta(d).to_string(index=False,
                                 float_format=lambda v: f"{v:.4f}"))

    print()
    print("--- is there an optimal cap? in-sample profile ---")
    print(cap_grid(d).to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print()
    print("--- argmax under season resampling ---")
    for obj in ("units", "roi"):
        argmax_bootstrap(d, obj)
    print()
    print("--- a FITTED cap vs a round number, graded forward ---")
    print(optimizer_vs_fixed(d).to_string(index=False,
                                          float_format=lambda v: f"{v:.4f}"))
    print()
    print("--- fine bands across the turn (EXPLORATORY, not pre-registered) ---")
    print(fine_bands(d).to_string(index=False, float_format=lambda v: f"{v:+.2f}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
