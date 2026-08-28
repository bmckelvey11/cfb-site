"""B7 - test betting the UNDER on totals lines in the 55-65 band.

B6 tested ">66 -> under" and filed a null. The 55-65 band is a different
question that B6's bin edges straddle: 55-59 falls inside a region averaging
50.18% under, 59-66 inside one averaging 52.49%. This tests the band directly,
with materially more power than B6 had (N ~4-5k vs 977).

Pre-registered before running (see RESULTS.md for the same list):

  [A] Disjoint sub-bins 55-59 / 59-62 / 62-65 BEFORE the 55-65 aggregate, so a
      real plateau is distinguishable from an average across two regimes.
  [B] Band-restricted probit on the totals level. If the band is just a slice
      of a continuous gradient, the slope inside it should look like B6's.
  [C] Feature scan INSIDE the band. Candidate pool fixed up front from
      b4_features/INVENTORY.md (week, neutral_site, conference_game, home_dog)
      plus the two line-shape variables the model already knows (spread,
      censoring bias). Every feature tested is reported, not just survivors,
      and every split family tiles its variable with no unreported middle.
  [D] Any cell clearing break-even goes through the repo's walk-forward
      protocol (train on seasons <= t-1, bet season t) - the discriminator
      between "found a cell" and "found an edge".

Break-even is 52.36%, measured from real consensus under prices in
data/raw/actionnetwork_odds.csv (4,399 games, 2018/2019/2023-2025): books do
NOT shade the under on high totals, median under price is -110 in every band.
So the -110 hurdle is the right one, not an assumption. Note that price
coverage is 5 of the 13 seasons tested; the hurdle is measured on those and
extrapolated to the rest, which is safe here only because it is flat across
every band and the band loses to it anyway.

Run:  python research/b7_mid_total_under/test_mid_total_under.py
      python research/b7_mid_total_under/test_mid_total_under.py --selftest
"""

import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "v1"))
sys.path.insert(0, str(REPO / "research" / "b6_high_total_under"))

from censoring_bias import censoring_bias, fit_pipeline, implied_team_points  # noqa: E402
from test_high_total_under import (  # noqa: E402
    fit_probit,
    mde,
    season_block_bootstrap,
    wilson_ci,
)

RAW_DIR = REPO / "data" / "raw"
SEASONS = list(range(2013, 2026))
RNG = np.random.default_rng(20260811)

BAND_LO, BAND_HI = 55.0, 65.0
BREAK_EVEN = 0.5236  # measured, see module docstring

# Comparison budget carried forward honestly. B6 documented 9 priors
# (4 totals bins + 5 spread bins). B7 adds 3 sub-bins + 1 aggregate + 13
# feature cells = 17, counted as printed cells rather than split families so
# the constant always matches the tables below (asserted in main()). A
# survivor must clear Bonferroni over all 26.
N_PRIOR_COMPARISONS = 9
N_B7_COMPARISONS = 17
N_ALL_COMPARISONS = N_PRIOR_COMPARISONS + N_B7_COMPARISONS


def load_neutral_site(season, raw_dir=RAW_DIR):
    """game id -> neutralSite. lines_*.json has no venue field, so this comes
    from games_*.json (same join pattern as b4_features/probit_features.py)."""
    path = Path(raw_dir) / f"games_{season}.json"
    if not path.exists():
        return {}
    return {g["id"]: 1.0 if g.get("neutralSite") else 0.0
            for g in json.loads(path.read_text(encoding="utf-8"))
            if g.get("id") is not None}


def load_with_features(seasons=SEASONS, raw_dir=RAW_DIR):
    """B6's loader plus the pre-registered feature columns.

    Same book-selection rule as v1/run_on_project_data.load_from_raw:
    consensus provider when present, else the first line carrying both a
    spread and a total.
    """
    cols = {k: [] for k in (
        "spread", "total", "fav_pts", "dog_pts", "season",
        "week", "neutral_site", "conference_game", "home_dog",
    )}
    for season in seasons:
        path = Path(raw_dir) / f"lines_{season}.json"
        if not path.exists():
            print(f"  (no raw file for {season}: {path.name})")
            continue
        neutral = load_neutral_site(season, raw_dir)
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
            if spread == 0:
                continue
            fav, dog = (float(hp), float(ap)) if spread < 0 else (float(ap), float(hp))
            hc, ac = g.get("homeConference"), g.get("awayConference")
            cols["spread"].append(abs(spread))
            cols["total"].append(float(line["overUnder"]))
            cols["fav_pts"].append(fav)
            cols["dog_pts"].append(dog)
            cols["season"].append(season)
            cols["week"].append(float(g.get("week") or 0))
            cols["neutral_site"].append(neutral.get(g.get("id"), np.nan))
            cols["conference_game"].append(
                float(hc is not None and ac is not None and hc == ac))
            cols["home_dog"].append(float(spread > 0))
    return {k: np.array(v, dtype=float) for k, v in cols.items()}


def report_cell(label, wins, n, extra=""):
    """One line per tested cell: rate, Wilson CI, gap to break-even."""
    if n == 0:
        print(f"  {label:>26} {'--':>6}")
        return float("nan")
    rate = wins / n
    lo, hi = wilson_ci(wins, n)
    print(f"  {label:>26} {n:>6} {rate*100:>7.2f}% "
          f"[{lo*100:>5.1f},{hi*100:>5.1f}] "
          f"{(rate-BREAK_EVEN)*100:>+7.2f}pp{extra}")
    return rate


def one_sided_p(rate, n, baseline=BREAK_EVEN):
    z = (rate - baseline) / np.sqrt(baseline * (1 - baseline) / n)
    return z, 1 - stats.norm.cdf(z)


def walk_forward(under_win, season, sel):
    """Repo's deployable-protocol check: for each season t, decide using only
    seasons <= t-1. The rule here has no fitted parameters beyond 'does the
    cell's prior-seasons rate clear break-even', so this tests whether the cell
    would ever have been bettable in real time.

    Note this gate is deliberately GENEROUS to the hypothesis: it bets on the
    prior-seasons point estimate clearing break-even, not on a Wilson lower
    bound as monitor/ does. A cell that fails here fails the easy version.
    """
    seasons = np.unique(season)
    bets = wins = 0
    for t in seasons[1:]:
        prior = sel & (season < t)
        if prior.sum() < 100:
            continue
        if under_win[prior].mean() <= BREAK_EVEN:
            continue                      # would not have bet this season
        cur = sel & (season == t)
        bets += int(cur.sum())
        wins += int(under_win[cur].sum())
    return wins, bets


def main():
    d = load_with_features()
    sp, to = d["spread"], d["total"]
    fav, dog, season = d["fav_pts"], d["dog_pts"], d["season"]
    print(f"Loaded {sp.size:,} usable games, seasons "
          f"{int(season.min())}-{int(season.max())}")

    nu = (fav + dog) - to
    keep = nu != 0                        # drop pushes
    under_win = (nu < 0).astype(float)[keep]
    sp, to, fav, dog, season = (a[keep] for a in (sp, to, fav, dog, season))
    feats = {k: d[k][keep] for k in ("week", "neutral_site",
                                     "conference_game", "home_dog")}
    print(f"{sp.size:,} after dropping pushes")
    print(f"Break-even {BREAK_EVEN*100:.2f}% (measured from real under prices)\n")

    band = (to >= BAND_LO) & (to <= BAND_HI)

    # --- [A] Disjoint sub-bins first, then the aggregate --------------------
    print("[A] Sub-bins before the aggregate")
    print(f"  {'cell':>26} {'N':>6} {'under%':>8} {'95% CI':>14} {'vs BE':>9}")
    for lo, hi, lab in ((55, 59, "55-59"), (59, 62, "59-62"), (62, 65, "62-65")):
        s = (to >= lo) & (to < hi) if hi != 65 else (to >= lo) & (to <= hi)
        report_cell(lab, float(under_win[s].sum()), int(s.sum()))
    print()
    n_b, w_b = int(band.sum()), float(under_win[band].sum())
    rate_b = report_cell("55-65 (aggregate)", w_b, n_b)

    # Neighbours, for context on whether the band is a plateau or a slice.
    print()
    for lab, s in (("<55 (below band)", to < BAND_LO),
                   (">65 (above band)", to > BAND_HI)):
        report_cell(lab, float(under_win[s].sum()), int(s.sum()))

    z, p = one_sided_p(rate_b, n_b)
    boot = season_block_bootstrap(under_win[band], season[band])
    print(f"\n  55-65: {rate_b*100:.2f}% on N={n_b}")
    print(f"  vs break-even {BREAK_EVEN*100:.2f}%: z={z:+.2f}, one-sided p={p:.3f}")
    print(f"  Bonferroni over {N_ALL_COMPARISONS} comparisons "
          f"({N_PRIOR_COMPARISONS} prior + {N_B7_COMPARISONS} here): "
          f"p_adj={min(1.0, p*N_ALL_COMPARISONS):.3f}")
    print(f"  season block-bootstrap 95% CI: "
          f"[{boot[0]*100:.2f}%, {boot[1]*100:.2f}%]")
    print(f"  MDE at N={n_b} (80% power, one-sided 0.05): "
          f"{mde(n_b, BREAK_EVEN)*100:.2f}% true rate needed")

    # --- [B] Probit inside the band -----------------------------------------
    print("\n[B] Probit on totals level, restricted to the band")
    c, slope, slope_se, s_s, se_s = fit_probit(to[band], under_win[band])
    z_s = s_s / se_s
    print(f"  slope={slope:+.6f} per point (SE={slope_se:.6f}), "
          f"z={z_s:+.2f}, two-sided p={2*(1-stats.norm.cdf(abs(z_s))):.4f}")
    print(f"  (B6 full-range slope was +0.003279/pt, z=+2.28)")

    # --- [C] Pre-registered feature scan inside the band --------------------
    print("\n[C] Feature scan inside 55-65 (all tested features reported)")
    fit = fit_pipeline(sp, to, fav, dog)
    dog_est, fav_est = implied_team_points(sp, to)
    _, bias = censoring_bias(dog_est, fav_est,
                             fit.tobit_dog.sigma, fit.tobit_fav.sigma)

    splits = [
        ("week <= 4 (early)",       band & (feats["week"] <= 4)),
        ("week > 4 (late)",         band & (feats["week"] > 4)),
        ("conference game",         band & (feats["conference_game"] == 1)),
        ("non-conference",          band & (feats["conference_game"] == 0)),
        ("home dog",                band & (feats["home_dog"] == 1)),
        ("home favorite",           band & (feats["home_dog"] == 0)),
        ("neutral site",            band & (feats["neutral_site"] == 1)),
        ("non-neutral site",        band & (feats["neutral_site"] == 0)),
        ("spread <= 7 (close)",     band & (sp <= 7)),
        ("spread 7-14 (middle)",    band & (sp > 7) & (sp <= 14)),
        ("spread > 14 (lopsided)",  band & (sp > 14)),
        ("censoring bias < 0.25",   band & (bias < 0.25)),
        ("censoring bias >= 0.25",  band & (bias >= 0.25)),
    ]
    # Budget must equal what is actually printed: 3 sub-bins + 1 aggregate
    # + every feature cell. Fails loudly rather than drifting silently.
    assert N_B7_COMPARISONS == 4 + len(splits), (
        f"comparison budget {N_B7_COMPARISONS} != 4 + {len(splits)} printed cells")

    print(f"  {'cell':>26} {'N':>6} {'under%':>8} {'95% CI':>14} {'vs BE':>9}")
    results = []
    for lab, s in splits:
        n = int(s.sum())
        r = report_cell(lab, float(under_win[s].sum()), n)
        if n >= 200:
            results.append((lab, s, r, n))

    n_missing = int(np.isnan(feats["neutral_site"][band]).sum())
    if n_missing:
        print(f"\n  ({n_missing} band games unmatched in games_*.json, excluded "
              f"from the neutral-site split only)")

    # --- [D] Walk-forward on anything that cleared --------------------------
    print("\n[D] Walk-forward on cells clearing break-even in-sample")
    clearing = [(lab, s, r, n) for lab, s, r, n in results if r > BREAK_EVEN]
    if not clearing:
        print("  No cell clears break-even in-sample. Nothing to walk forward.")
    for lab, s, r, n in clearing:
        z_c, p_c = one_sided_p(r, n)
        w_wf, n_wf = walk_forward(under_win, season, s)
        wf = f"{w_wf/n_wf*100:.2f}% on {n_wf} bets" if n_wf else "never bet"
        print(f"  {lab}: in-sample {r*100:.2f}% (N={n}), raw p={p_c:.3f}, "
              f"p_adj={min(1.0, p_c*N_ALL_COMPARISONS):.3f}")
        print(f"    walk-forward: {wf}")
        # A walk-forward rate means nothing without its own CI and its
        # season-by-season spread: a single hot season can carry the average.
        if n_wf >= 200:
            r_wf = w_wf / n_wf
            lo, hi = wilson_ci(w_wf, n_wf)
            z_wf, p_wf = one_sided_p(r_wf, n_wf)
            print(f"    walk-forward Wilson 95% CI [{lo*100:.2f}%, {hi*100:.2f}%], "
                  f"z={z_wf:+.2f}, one-sided p={p_wf:.3f}")
            per = []
            for t in np.unique(season)[1:]:
                prior = s & (season < t)
                if prior.sum() < 100 or under_win[prior].mean() <= BREAK_EVEN:
                    continue
                cur = s & (season == t)
                if cur.sum():
                    per.append(f"{int(t)}:{under_win[cur].mean()*100:.0f}%"
                               f"(n={int(cur.sum())})")
            print(f"    per-season: {' '.join(per)}")


def _selftest():
    """Smallest checks that fail if the band logic or accounting breaks."""
    # under_win coding: realized < line => under wins
    nu = np.array([-3.0, 3.0])
    assert list((nu < 0).astype(float)) == [1.0, 0.0]

    # Band is inclusive on both ends and sub-bins tile it without overlap.
    to = np.array([54.5, 55.0, 58.9, 59.0, 61.9, 62.0, 65.0, 65.5])
    band = (to >= BAND_LO) & (to <= BAND_HI)
    assert list(band) == [False, True, True, True, True, True, True, False]
    b1 = (to >= 55) & (to < 59)
    b2 = (to >= 59) & (to < 62)
    b3 = (to >= 62) & (to <= 65)
    assert not (b1 & b2).any() and not (b2 & b3).any() and not (b1 & b3).any()
    assert list(b1 | b2 | b3) == list(band), "sub-bins must tile the band"

    # walk_forward must not bet a season using that season's own result.
    season = np.array([2013] * 200 + [2014] * 200)
    sel = np.ones(400, dtype=bool)
    win = np.concatenate([np.ones(200), np.zeros(200)])   # 2013 all wins
    w, n = walk_forward(win, season, sel)
    assert (w, n) == (0, 200), f"expected 2014 bet at 0 wins, got {(w, n)}"

    # break-even accounting from American odds
    assert abs(-(-110) / (-(-110) + 100) - 0.5238) < 0.001
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        main()
