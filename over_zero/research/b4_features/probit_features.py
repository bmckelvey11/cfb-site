"""Does anything in the raw data explain the over-edge beyond biasTotals?

Probit: over ~ z(biasTotals) + z(features), pooled, season-clustered SEs.
Feature list fixed by research/b4_features/INVENTORY.md -- edit FEATURES
to the <=4 names chosen there, then never again.
"""
import json
import sys
from pathlib import Path

import numpy as np
import statsmodels.api as sm

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "v2"))
from models_v2 import (censoring_bias, implied_team_points, pick_line,
                       tobit_left_censored_v2)

RAW = REPO / "data" / "raw"
FEATURES = ["week", "neutralSite", "conferenceGame", "home_dog"]  # fcs_dog → home_dog per BLOCKERS.md 11b2500
BONFERRONI_P = 0.05 / 4


def feature_row(game_rec, spread):
    dog_conf = (game_rec.get("awayConference") if spread < 0
                else game_rec.get("homeConference"))
    all_feats = {
        "week": float(game_rec.get("week") or 0),
        "neutralSite": 1.0 if game_rec.get("neutralSite") else 0.0,
        "conferenceGame": 1.0 if game_rec.get("conferenceGame") else 0.0,
        "fcs_dog": 0.0 if dog_conf else 1.0,
        "home_dog": 1.0 if spread > 0 else 0.0,
    }
    return [all_feats[f] for f in FEATURES]


def main():
    se, te, fp, dp, ss, X = [], [], [], [], [], []
    for season in range(2013, 2026):
        lp, gp = RAW / f"lines_{season}.json", RAW / f"games_{season}.json"
        if not lp.exists() or not gp.exists():
            continue
        games = {g["id"]: g for g in json.loads(gp.read_text(encoding="utf-8"))}
        for g in json.loads(lp.read_text(encoding="utf-8")):
            hp, ap = g.get("homeScore"), g.get("awayScore")
            line = pick_line(g)
            grec = games.get(g["id"])
            if hp is None or ap is None or line is None or grec is None:
                continue
            spread, total = line
            if spread == 0:
                continue
            fav, dog = (float(hp), float(ap)) if spread < 0 else (float(ap), float(hp))
            se.append(abs(spread)); te.append(total)
            fp.append(fav); dp.append(dog); ss.append(season)
            X.append(feature_row(grec, spread))

    se, te, fp, dp, ss = map(np.array, (se, te, fp, dp, ss))
    X = np.array(X)
    print(f"{se.size:,} games with features joined")
    assert se.size > 10_000, "join lost too many games -- inspect games_/lines_ id overlap"

    dog_est, fav_est = implied_team_points(se, te)
    s1 = tobit_left_censored_v2(dp, dog_est).sigma
    s2 = tobit_left_censored_v2(fp, fav_est).sigma
    _, bias = censoring_bias(dog_est, fav_est, s1, s2)
    nu = (fp + dp) - te
    keep = nu != 0
    y = (nu > 0).astype(float)[keep]
    groups = ss[keep]

    def zfit(cols, names):
        Z = np.column_stack([(c - c.mean()) / c.std() for c in cols])
        res = sm.Probit(y, sm.add_constant(Z)).fit(
            disp=False, cov_type="cluster", cov_kwds={"groups": groups})
        print(f"\nspec: {names}")
        for name, b, s_, p in zip(["const"] + names, res.params, res.bse, res.pvalues):
            star = " *SIG*" if name != "const" and name != "biasTotals" and p < BONFERRONI_P else ""
            print(f"  {name:>15} {b:+.4f} (SE {s_:.4f}, p={p:.4g}){star}")
        return res

    base = zfit([bias[keep]], ["biasTotals"])
    full = zfit([bias[keep]] + [X[keep][:, i] for i in range(len(FEATURES))],
                ["biasTotals"] + FEATURES)
    shift = (full.params[1] - base.params[1]) / base.bse[1]
    print(f"\nbiasTotals coefficient shift with features: {shift:+.2f} SEs "
          f"(over 1 SE = features materially overlap the censoring signal)")


if __name__ == "__main__":
    main()
