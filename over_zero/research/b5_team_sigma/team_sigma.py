"""Does team-specific (shrunk) score noise beat one pooled sigma per role?

Walk-forward, paired OOS log-loss, season-block bootstrap CI. K=30 primary.
"""
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "v2"))
from models_v2 import (_team_censor_bias, implied_team_points, pick_line,
                       probit_win_v2, tobit_left_censored_v2)

RAW = REPO / "data" / "raw"
K_PRIMARY, K_SENS = 30, (15, 60)


def load(seasons):
    """season -> dict of arrays: dog_est, fav_est, dog_pts, fav_pts, total,
    dog_team, fav_team."""
    out = {}
    for season in seasons:
        p = RAW / f"lines_{season}.json"
        if not p.exists():
            continue
        rows = {k: [] for k in ("de", "fe", "dp", "fp", "te", "dt", "ft")}
        for g in json.loads(p.read_text(encoding="utf-8")):
            hp, ap = g.get("homeScore"), g.get("awayScore")
            line = pick_line(g)
            home, away = g.get("homeTeam"), g.get("awayTeam")
            if hp is None or ap is None or line is None or not home or not away:
                continue
            spread, total = line
            if spread == 0:
                continue
            if spread < 0:
                favp, dogp, favt, dogt = float(hp), float(ap), home, away
            else:
                favp, dogp, favt, dogt = float(ap), float(hp), away, home
            d, f = implied_team_points(abs(spread), total)
            for k, v in (("de", float(d)), ("fe", float(f)), ("dp", dogp),
                         ("fp", favp), ("te", total), ("dt", dogt), ("ft", favt)):
                rows[k].append(v)
        if rows["de"]:
            out[season] = {k: np.array(v) for k, v in rows.items()}
    return out


def team_sigmas(seasons_data, role, K):
    """role 'dog' or 'fav': team -> shrunk sigma, plus (pooled fit alpha,beta,sigma)."""
    est = np.concatenate([d["de" if role == "dog" else "fe"] for d in seasons_data])
    pts = np.concatenate([d["dp" if role == "dog" else "fp"] for d in seasons_data])
    team = np.concatenate([d["dt" if role == "dog" else "ft"] for d in seasons_data])
    fit = tobit_left_censored_v2(pts, est)
    unc = pts > 0
    resid = (pts - (fit.alpha + fit.beta * est))[unc]
    tm = team[unc]
    s2_pool = fit.sigma ** 2
    out = {}
    for t in np.unique(tm):
        r = resid[tm == t]
        if r.size >= 5:
            out[t] = (r.size * r.var(ddof=1) + K * s2_pool) / (r.size + K)
    return {t: float(np.sqrt(v)) for t, v in out.items()}, fit


def season_logloss(data_t, sd_dog, sd_fav, s1, s2, probit, per_team):
    de, fe, te = data_t["de"], data_t["fe"], data_t["te"]
    if per_team:
        sig_d = np.array([sd_dog.get(t, s1) for t in data_t["dt"]])
        sig_f = np.array([sd_fav.get(t, s2) for t in data_t["ft"]])
    else:
        sig_d = np.full(de.size, s1)
        sig_f = np.full(fe.size, s2)
    bias = _team_censor_bias(de, sig_d) + _team_censor_bias(fe, sig_f)
    p = np.clip(probit.win_prob(bias), 1e-6, 1 - 1e-6)
    nu = (data_t["dp"] + data_t["fp"]) - te
    keep = nu != 0
    y = (nu > 0).astype(float)[keep]
    return -(y * np.log(p[keep]) + (1 - y) * np.log(1 - p[keep]))


def run(K):
    data = load(range(2013, 2026))
    years = sorted(data)
    diffs_by_season = []
    for t in years[3:]:
        tr = [data[y] for y in years if y < t]
        sd_dog, fit_d = team_sigmas(tr, "dog", K)
        sd_fav, fit_f = team_sigmas(tr, "fav", K)
        s1, s2 = fit_d.sigma, fit_f.sigma
        de = np.concatenate([d["de"] for d in tr])
        fe = np.concatenate([d["fe"] for d in tr])
        bias_tr = _team_censor_bias(de, s1) + _team_censor_bias(fe, s2)
        nu_tr = np.concatenate([d["dp"] + d["fp"] - d["te"] for d in tr])
        keep = nu_tr != 0
        probit = probit_win_v2((nu_tr > 0).astype(float)[keep], bias_tr[keep])

        ll_pool = season_logloss(data[t], sd_dog, sd_fav, s1, s2, probit, False)
        ll_team = season_logloss(data[t], sd_dog, sd_fav, s1, s2, probit, True)
        diffs_by_season.append(ll_pool - ll_team)   # positive = team-sigma better

    flat = np.concatenate(diffs_by_season)
    rng = np.random.default_rng(0)
    boots = [np.concatenate([diffs_by_season[i] for i in
                             rng.integers(0, len(diffs_by_season), len(diffs_by_season))]).mean()
             for _ in range(1000)]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    print(f"K={K}: mean OOS logloss improvement (pooled - team) = "
          f"{flat.mean()*1e4:+.2f} x1e-4  season-block bootstrap 95% "
          f"[{lo*1e4:+.2f},{hi*1e4:+.2f}] x1e-4  ({flat.size:,} games)")
    return flat.mean(), lo, hi


def main():
    results = {K: run(K) for K in (K_PRIMARY,) + K_SENS}
    m, lo, hi = results[K_PRIMARY]
    verdict = ("TEAM-SIGMA IMPROVES OOS" if lo > 0
               else "NO OOS IMPROVEMENT" if hi > 0 else "TEAM-SIGMA HURTS OOS")
    print(f"\nVERDICT (K={K_PRIMARY}): {verdict}")


if __name__ == "__main__":
    main()
