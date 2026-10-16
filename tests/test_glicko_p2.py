"""glicko_p2_eval: the P2 candidate reduces to P1, its clip and prior move ratings as declared,
and the table's RD advances to as_of. In-memory, no CFB_DATA_ROOT."""
import math

import pandas as pd

from scripts.glicko_p2_eval import INF, GlickoPrior, _z
from scripts.glicko_ratings import (FBS, FROZEN_P1, SIGMA_PRED_P1, GlickoMargin, events,
                                    predictive_sd, run)
from scripts.glicko_ratings_table import ratings_table


def _games():
    rows, gid = [], 0
    for season in (2013, 2014):
        for wk, (h, a, mg) in enumerate([("A", "B", 21), ("C", "A", -3), ("B", "C", 45), ("A", "C", 7)]):
            gid += 1
            rows.append({"game_id": gid, "season": season, "season_type": "regular", "week": wk + 1,
                         "kickoff": pd.Timestamp(f"{season}-09-0{wk + 1}", tz="UTC"),
                         "home": h, "away": a, "home_div": FBS, "away_div": FBS,
                         "home_conf": "X", "away_conf": "X", "neutral": False, "margin": mg})
    return pd.DataFrame(rows)


def test_neutral_prior_reproduces_p1_exactly():
    g = _games()
    ev = events(g)
    p1 = run(GlickoMargin(**FROZEN_P1, m0=-27.0), g, ev)
    p2 = run(GlickoPrior(**FROZEN_P1, m0=-27.0, b_rp=0.0, b_rec=0.0, c=0.0, clip=INF,
                         feats={2014: {"A": (1.0, 1.0)}}), g, ev)
    pd.testing.assert_frame_equal(p1, p2)


def test_clip_caps_the_innovation_at_clip_times_forecast_sd():
    def step(clip):
        m = GlickoPrior(**{**FROZEN_P1, "hfa": 0.0}, m0=-27.0, clip=clip)
        for k in ("H", "A"):
            m.enter(k, FBS, 0.0)
        mhat, s, _ = m.forecast("H", "A", True, 0.0)
        m.update("H", "A", True, 100.0, 0.0)
        return m.r["H"], m.u2["H"], s
    rh_inf, _, s = step(INF)
    rh_2, _, _ = step(2.0)
    gain = FROZEN_P1["u0"] ** 2 / s
    assert math.isclose(rh_inf, gain * 100.0)
    assert math.isclose(rh_2, gain * 2.0 * math.sqrt(s))


def test_prior_shifts_offseason_rating_by_feature_effects():
    m = GlickoPrior(**FROZEN_P1, m0=-27.0, b_rp=2.0, b_rec=1.0, feats={2014: {"A": (1.0, -0.5)}})
    m.enter("A", FBS, 0.0, "X")
    m.played("A", FBS, 2013, "X")
    m.enter("B", FBS, 0.0, "X")
    m.played("B", FBS, 2013, "X")
    m.r["A"], m.r["B"] = 10.0, -10.0
    m.season_start(2013, 1.0)
    # conference mean 0, w 0.7: 7.0 from persistence, + 2*1.0 - 1*0.5 from the prior
    assert math.isclose(m.r["A"], 8.5) and math.isclose(m.r["B"], -7.0)


def test_z_scores_have_mean_zero_unit_sd():
    z = _z({"a": 1.0, "b": 2.0, "c": 3.0})
    assert math.isclose(sum(z.values()), 0.0, abs_tol=1e-12) and math.isclose(z["c"], math.sqrt(1.5))


def test_predictive_sd_uses_sigma_pred_not_gain_sigma():
    assert math.isclose(predictive_sd(36.0), math.sqrt(36.0 + SIGMA_PRED_P1 ** 2))
    assert SIGMA_PRED_P1 < FROZEN_P1["sigma"]


def test_table_rd_grows_by_tau2_per_idle_week_to_as_of():
    g = _games()
    m = GlickoMargin(**FROZEN_P1, m0=-27.0)
    run(m, g, events(g))
    rd_last = {k: math.sqrt(m.u2[k]) for k in m.r}
    last_t = dict(m.tl)
    as_of = pd.Timestamp("2014-09-18", tz="UTC")
    t = ratings_table(m, 2014, as_of).set_index("team")
    days = (as_of - pd.Timestamp("1970-01-01", tz="UTC")).total_seconds() / 86_400.0
    for k in ("A", "B", "C"):
        want = math.sqrt(rd_last[k] ** 2 + FROZEN_P1["tau"] ** 2 * (days - last_t[k]) / 7.0)
        assert math.isclose(t.loc[k, "rd"], want)
