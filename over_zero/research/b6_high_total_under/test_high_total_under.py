"""Test the ">66 totals line -> bet the under" lead surfaced during the
floor-bias work (docs/floor_bias_1h_chat_history.md:980-987, 54.15% / N=977).

The lead came from eyeballing a 4-bin scan on the same data that produced the
floor-bias result, so the bin edge is not independent evidence. This tests the
underlying claim three ways instead of re-running the bin:

  [A] Point estimate vs juice. Break-even is 52.38% at -110, 54.55% at -120.
  [B] Continuous probit: P(under) = Phi(const + slope*totalsEst).
      Real mechanism -> positive significant slope. Bin artifact -> flat.
  [C] Conditioned on censoring bias ~ 0. High totals lines are roughly the
      complement of the floor-bias sweet spot, so the apparent under edge may
      just be the absence of the over edge read backwards.

Season block-bootstrap for CIs (games within a season are not independent).

Run:  python research/b6_high_total_under/test_high_total_under.py
"""

import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats
from scipy.optimize import minimize

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "v1"))

from censoring_bias import censoring_bias, fit_pipeline, implied_team_points  # noqa: E402

RAW_DIR = REPO / "data" / "raw"
SEASONS = list(range(2013, 2026))
RNG = np.random.default_rng(20260811)

# Scans already run against this dataset: 4 totals bins + 5 spread bins.
N_PRIOR_COMPARISONS = 9


def load_with_season(seasons=SEASONS, raw_dir=RAW_DIR):
    """Same book-selection rule as v1/run_on_project_data.load_from_raw,
    plus the season label (needed for the block-bootstrap)."""
    spread_est, totals_est, fav_pts, dog_pts, season_of = [], [], [], [], []
    for season in seasons:
        path = Path(raw_dir) / f"lines_{season}.json"
        if not path.exists():
            print(f"  (no raw file for {season}: {path.name})")
            continue
        for g in json.loads(path.read_text(encoding="utf-8")):
            hp, ap = g.get("homeScore"), g.get("awayScore")
            if hp is None or ap is None:
                continue
            both = [l for l in (g.get("lines") or [])
                    if l.get("spread") is not None and l.get("overUnder") is not None]
            if not both:
                continue
            line = next((l for l in both
                         if str(l.get("provider", "")).lower() == "consensus"), both[0])
            spread = float(line["spread"])
            total = float(line["overUnder"])
            if spread == 0:
                continue
            fav, dog = (float(hp), float(ap)) if spread < 0 else (float(ap), float(hp))
            spread_est.append(abs(spread))
            totals_est.append(total)
            fav_pts.append(fav)
            dog_pts.append(dog)
            season_of.append(season)
    return tuple(np.array(a) for a in
                 (spread_est, totals_est, fav_pts, dog_pts, season_of))


def probit_ll(params, x, y):
    const, slope = params
    p = np.clip(stats.norm.cdf(const + slope * x), 1e-12, 1 - 1e-12)
    return -np.sum(y * np.log(p) + (1 - y) * np.log(1 - p))


def fit_probit(x, y):
    """Returns (const, slope, slope_se) via numeric Hessian at the optimum."""
    x_s = (x - x.mean()) / x.std()
    res = minimize(probit_ll, [0.0, 0.0], args=(x_s, y), method="BFGS")
    const, slope_s = res.x
    # Delta-method back to raw units.
    slope = slope_s / x.std()
    hess_inv = res.hess_inv
    se_s = float(np.sqrt(hess_inv[1, 1]))
    return const, slope, se_s / x.std(), slope_s, se_s


def wilson_ci(wins, n, conf=0.95):
    if n == 0:
        return (float("nan"), float("nan"))
    z = stats.norm.ppf(1 - (1 - conf) / 2)
    p = wins / n
    d = 1 + z**2 / n
    c = (p + z**2 / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / d
    return (c - h, c + h)


def season_block_bootstrap(under_wins, seasons, n_boot=5000):
    """Resample whole seasons with replacement; return the win-rate CI."""
    uniq = np.unique(seasons)
    rates = []
    for _ in range(n_boot):
        pick = RNG.choice(uniq, size=uniq.size, replace=True)
        sample = np.concatenate([under_wins[seasons == s] for s in pick])
        if sample.size:
            rates.append(sample.mean())
    return np.percentile(rates, [2.5, 97.5])


def mde(n, baseline=0.5238, alpha=0.05, power=0.80):
    """One-sided minimum detectable true rate at this N."""
    z_a = stats.norm.ppf(1 - alpha)
    z_b = stats.norm.ppf(power)
    se = np.sqrt(baseline * (1 - baseline) / n)
    return baseline + (z_a + z_b) * se


def main():
    sp, to, fav, dog, season = load_with_season()
    print(f"Loaded {sp.size:,} usable games, seasons {season.min()}-{season.max()}")

    true_totals = fav + dog
    nu = true_totals - to
    keep = nu != 0                      # drop pushes
    under_win = (nu < 0).astype(float)

    sp, to, fav, dog, season = (a[keep] for a in (sp, to, fav, dog, season))
    under_win = under_win[keep]
    print(f"{sp.size:,} after dropping pushes\n")

    # --- [A] The original bin, restated against both juice levels -----------
    print("[A] The >66 bin vs break-even")
    print(f"  {'bin':>10} {'N':>6} {'under%':>8} {'95% CI':>16} {'vs -110':>9} {'vs -120':>9}")
    edges = [(0, 45), (45, 59), (59, 66), (66, 999)]
    for lo, hi in edges:
        sel = (to > lo) & (to <= hi)
        n, w = int(sel.sum()), float(under_win[sel].sum())
        rate = w / n if n else float("nan")
        ci = wilson_ci(w, n)
        label = f">{lo}" if hi == 999 else f"{lo}-{hi}"
        print(f"  {label:>10} {n:>6} {rate*100:>7.2f}% "
              f"[{ci[0]*100:>5.1f},{ci[1]*100:>5.1f}] "
              f"{(rate-0.5238)*100:>+8.2f}pp {(rate-0.5455)*100:>+8.2f}pp")

    hi_sel = to > 66
    n_hi, w_hi = int(hi_sel.sum()), float(under_win[hi_sel].sum())
    rate_hi = w_hi / n_hi
    z = (rate_hi - 0.5238) / np.sqrt(0.5238 * (1 - 0.5238) / n_hi)
    p_one = 1 - stats.norm.cdf(z)
    boot_ci = season_block_bootstrap(under_win[hi_sel], season[hi_sel])
    print(f"\n  >66: {rate_hi*100:.2f}% on N={n_hi}")
    print(f"  vs -110 break-even 52.38%: z={z:.2f}, one-sided p={p_one:.3f}")
    print(f"  Bonferroni over {N_PRIOR_COMPARISONS} prior bin comparisons: "
          f"p_adj={min(1.0, p_one*N_PRIOR_COMPARISONS):.3f}")
    print(f"  season block-bootstrap 95% CI: "
          f"[{boot_ci[0]*100:.2f}%, {boot_ci[1]*100:.2f}%]")
    print(f"  MDE at N={n_hi} (80% power, one-sided 0.05): "
          f"{mde(n_hi)*100:.2f}% true rate needed")

    # --- [B] Continuous probit: is totals level really predictive? ----------
    print("\n[B] Continuous probit  P(under) = Phi(const + slope*totalsEst)")
    const, slope, slope_se, slope_s, se_s = fit_probit(to, under_win)
    z_slope = slope_s / se_s
    p_slope = 2 * (1 - stats.norm.cdf(abs(z_slope)))
    print(f"  const={const:+.4f}  slope={slope:+.6f} per point "
          f"(SE={slope_se:.6f})")
    print(f"  z={z_slope:+.2f}  two-sided p={p_slope:.4f}")
    # Season-clustered slope CI (repo standard); the Hessian SE above is
    # unclustered and games within a season are not independent.
    uniq = np.unique(season)
    boot_slopes = []
    for _ in range(1000):
        pick = RNG.choice(uniq, size=uniq.size, replace=True)
        idx = np.concatenate([np.flatnonzero(season == s) for s in pick])
        try:
            boot_slopes.append(fit_probit(to[idx], under_win[idx])[1])
        except Exception:
            continue
    slope_ci = np.percentile(boot_slopes, [2.5, 97.5])
    print(f"  season block-bootstrap slope 95% CI: "
          f"[{slope_ci[0]:+.6f}, {slope_ci[1]:+.6f}] per point"
          f"{'  (includes 0)' if slope_ci[0] <= 0 <= slope_ci[1] else ''}")

    lo68, hi68 = to.mean() - to.std(), to.mean() + to.std()
    print(f"  implied P(under) at totals={lo68:.0f}: "
          f"{stats.norm.cdf(const + slope_s*(lo68-to.mean())/to.std())*100:.2f}%")
    print(f"  implied P(under) at totals={hi68:.0f}: "
          f"{stats.norm.cdf(const + slope_s*(hi68-to.mean())/to.std())*100:.2f}%")

    # --- [C] Does it survive conditioning on censoring bias ~ 0? ------------
    print("\n[C] Conditioned on censoring bias (is this just the over edge inverted?)")
    fit = fit_pipeline(sp, to, fav, dog)
    dog_est, fav_est = implied_team_points(sp, to)
    _, bias = censoring_bias(dog_est, fav_est,
                             fit.tobit_dog.sigma, fit.tobit_fav.sigma)
    print(f"  mean censoring bias, totals>66: {bias[hi_sel].mean():.3f}  "
          f"| totals<=66: {bias[~hi_sel].mean():.3f}")
    print(f"  {'stratum':>28} {'N':>6} {'under%':>8}")
    for lab, sel in (
        ("totals>66 & bias<0.25", hi_sel & (bias < 0.25)),
        ("totals>66 & bias>=0.25", hi_sel & (bias >= 0.25)),
        ("totals<=66 & bias<0.25", (~hi_sel) & (bias < 0.25)),
        ("totals<=66 & bias>=0.25", (~hi_sel) & (bias >= 0.25)),
    ):
        n = int(sel.sum())
        rate = under_win[sel].mean() if n else float("nan")
        print(f"  {lab:>28} {n:>6} {rate*100:>7.2f}%")

    # Within low-bias games only, does the totals level still matter?
    low = bias < 0.25
    if low.sum() > 200:
        c2, s2, se2, s2s, se2s = fit_probit(to[low], under_win[low])
        z2 = s2s / se2s
        print(f"\n  probit within bias<0.25 only (N={int(low.sum())}): "
              f"slope={s2:+.6f}/pt, z={z2:+.2f}, p={2*(1-stats.norm.cdf(abs(z2))):.4f}")


def _selftest():
    """Smallest check that fails if the probit or the win-coding breaks."""
    x = RNG.normal(60, 8, 20000)
    y = (RNG.uniform(size=x.size) < stats.norm.cdf(-1.2 + 0.02 * x)).astype(float)
    _, slope, _, s_s, se_s = fit_probit(x, y)
    assert abs(slope - 0.02) < 0.004, f"probit slope off: {slope}"
    assert abs(s_s / se_s) > 5, "planted signal should be detected"
    # under_win coding: realized < line => under wins
    nu = np.array([-3.0, 3.0])
    assert list((nu < 0).astype(float)) == [1.0, 0.0]
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        main()
