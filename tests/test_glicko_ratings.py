"""Glicko-margin update, clock, and sign tests. In-memory, no CFB_DATA_ROOT."""
import math

import pandas as pd

from scripts.glicko_ratings import FBS, FCS, GlickoMargin, events, run, to_home_margin

INF = float("inf")


def model(**kw):
    p = dict(sigma=15.0, tau=1.0, w=0.7, delta=6.0, cap=INF, hfa=2.5, u0=10.0, m0=-20.0)
    return GlickoMargin(**{**p, **kw})


def two_teams(m, rh=5.0, ra=2.0, uh=6.0, ua=6.0):
    for k, r, u in (("H", rh, uh), ("A", ra, ua)):
        m.enter(k, FBS, 0.0)
        m.r[k], m.u2[k] = r, u * u


def test_zero_residual_leaves_means_unchanged():
    m = model(hfa=0.0)
    two_teams(m)
    m.update("H", "A", True, 3.0, 0.0)               # forecast is exactly 5 - 2 = 3
    assert (m.r["H"], m.r["A"]) == (5.0, 2.0)


def test_equal_variances_move_equal_and_opposite():
    m = model()
    two_teams(m)
    m.update("H", "A", False, 21.0, 0.0)
    dh, da = m.r["H"] - 5.0, m.r["A"] - 2.0
    assert dh > 0 and math.isclose(dh, -da)


def test_update_never_raises_variance_and_idle_week_adds_tau2():
    m = model(tau=1.5)
    two_teams(m, uh=4.0, ua=9.0)
    before = dict(m.u2)
    m.update("H", "A", False, -30.0, 0.0)
    assert all(m.u2[k] < before[k] for k in ("H", "A"))
    u2 = m.u2["H"]
    m.forecast("H", "A", False, 7.0)                 # one idle week later
    assert math.isclose(m.u2["H"], u2 + 1.5 ** 2)


def test_offseason_pulls_toward_subdivision_mean_and_adds_delta2():
    m = model(w=0.7, delta=6.0)
    for k, r in (("X", 20.0), ("Y", -18.0)):
        m.enter(k, FBS, 0.0)
        m.r[k] = r
        m.played(k, FBS, 2020)
    u2 = m.u2["X"]
    m.season_start(2020, 400.0)                      # FBS mean of 2020 players = +1
    assert math.isclose(m.r["X"], 0.7 * 20 + 0.3 * 1)
    assert math.isclose(m.u2["X"], u2 + 36.0)


def _season():
    rows = [  # week, kickoff day, home, away, margin
        (1, "2021-09-04", "A", "B", 10), (1, "2021-09-04", "C", "D", -3),
        (2, "2021-09-11", "A", "C", 7), (2, "2021-09-11", "B", "D", 1),
        (3, "2021-09-16", "A", "D", 14),              # Thursday: sets week 3's cutoff
        (3, "2021-09-18", "B", "C", -6),
    ]
    g = pd.DataFrame(rows, columns=["week", "day", "home", "away", "margin"])
    return g.assign(season=2021, season_type="regular", neutral=False, home_div=FBS,
                    away_div=FBS, kickoff=pd.to_datetime(g["day"], utc=True))


def test_no_lookahead_at_week_cutoff():
    g = _season()
    base = run(model(), g, events(g))
    wk3 = g.index[g["week"] == 3]
    # Every game at or after week 3's cutoff gets an extreme score: week 3 forecasts hold,
    # including the Saturday game that kicks off after Thursday's result.
    wild = g.copy()
    wild.loc[wk3, "margin"] = 70
    assert base.loc[wk3].equals(run(model(), wild, events(wild)).loc[wk3])
    # Dropping those games entirely leaves weeks 1-2 forecasts unchanged too.
    kept = g.drop(index=wk3)
    assert base.loc[kept.index].equals(run(model(), kept, events(kept)).loc[kept.index])


def test_sign_convention():
    m = model()
    two_teams(m, rh=12.0, ra=0.0)
    mhat, s, _ = m.forecast("H", "A", False, 0.0)
    assert mhat > 0 and 0.5 < 0.5 * (1 + math.erf(mhat / math.sqrt(2 * s)))
    assert to_home_margin(-7.0) == 7.0
    m.enter("F", FCS, 0.0)
    assert m.r["F"] == -20.0                         # FCS team enters at the FCS seed


def test_no_conference_reproduces_v1_exactly():
    g = _season()
    with_conf = g.assign(home_conf=None, away_conf=None)
    plain = run(model(), g, events(g))
    labelled_none = run(model(), with_conf, events(with_conf))
    assert plain.equals(labelled_none)


def test_conference_mean_is_offseason_target_with_subdivision_fallback():
    m = model(w=0.8, delta=0.0)
    # Season 2020: two Big Sky teams and one team in a conference with no other member yet.
    for k, r, conf in (("A", 10.0, "Big Sky"), ("B", -2.0, "Big Sky"), ("C", 40.0, "Lonely")):
        m.enter(k, FBS, 0.0, conf)
        m.r[k] = r
        m.played(k, FBS, 2020, conf)
    m.season_start(2020, 400.0)
    # A, B pull toward the Big Sky mean (4.0), not the FBS-wide mean.
    assert math.isclose(m.r["A"], 0.8 * 10.0 + 0.2 * 4.0)
    assert math.isclose(m.r["B"], 0.8 * -2.0 + 0.2 * 4.0)
    # C is alone in "Lonely" this season, so its own rating is its own mean: no visible pull.
    assert math.isclose(m.r["C"], 40.0)
    # A brand-new Big Sky team enters at the conference mean, not the FBS mean (0.0).
    m.enter("D", FBS, 400.0, "Big Sky")
    assert math.isclose(m.r["D"], 4.0)
    # A team new to a conference nobody has played this cycle falls back to the subdivision mean.
    m.enter("E", FBS, 400.0, "Never Seen")
    assert m.r["E"] == m.mean[FBS]


def test_ratings_table_centres_on_fbs_and_ranks_within_subdivision():
    from scripts.glicko_ratings_eval import GRIDS
    from scripts.glicko_ratings_table import ratings_table
    from scripts.glicko_ratings import FROZEN_V1

    assert all(FROZEN_V1[k] in v for k, v in GRIDS["glicko_margin"].items())
    m = model()
    for k, div, r, season in (("X", FBS, 10.0, 2026), ("Y", FBS, 4.0, 2026),
                              ("F", FCS, -20.0, 2026), ("Old", FBS, 30.0, 2025)):
        m.enter(k, div, 0.0)
        m.r[k] = r
        m.played(k, div, season)
    t = ratings_table(m, 2026).set_index("team")
    assert "Old" not in t.index                      # did not play this season
    assert (t.loc["X", "rating"], t.loc["Y", "rating"], t.loc["F", "rating"]) == (3.0, -3.0, -27.0)
    assert (t.loc["X", "rank"], t.loc["Y", "rank"], t.loc["F", "rank"]) == (1, 2, 1)
