"""Glicko P3 bundles: defaults reproduce P1 exactly, and each mechanism does what the spec
declares. In-memory, no CFB_DATA_ROOT."""
import math
from datetime import date

import pandas as pd
import pytest

import scripts.glicko_p3_eval as ev3
from scripts.glicko_p3 import (GlickoContext, GlickoFull, GlickoStart, _z, new_conferences,
                               run_ctx)
from scripts.glicko_ratings import FBS, FROZEN_P1, GlickoMargin, events, run


def _games():
    rows, gid = [], 0
    sched = [("A", "B", 21), ("C", "D", -3), ("B", "C", 45), ("A", "C", 7), ("D", "A", 10), ("B", "D", -14)]
    for season in (2013, 2014, 2020):
        for wk, (h, a, mg) in enumerate(sched):
            gid += 1
            rows.append({"game_id": gid, "season": season, "season_type": "regular", "week": wk + 1,
                         "kickoff": pd.Timestamp(season, 9, 1, tz="UTC") + pd.Timedelta(days=7 * wk),
                         "home": h, "away": a, "home_div": FBS, "away_div": FBS,
                         "home_conf": "X" if h in "AB" else "Y", "away_conf": "X" if a in "AB" else "Y",
                         "neutral": wk == 5, "margin": mg})
    return pd.DataFrame(rows)


def _ctx(g, **over):
    c = pd.DataFrame({"season": g["season"], "neutral": g["neutral"], "near": 0, "dz": 0.0,
                      "k_game": False, "ot": False}, index=g.index)
    for k, v in over.items():
        c[k] = v
    return c


def _p1(g):
    return run(GlickoMargin(**FROZEN_P1, m0=-27.0), g, events(g))


def test_bundle_defaults_reproduce_p1_exactly():
    g = _games()
    ev, p1 = events(g), _p1(g)
    a = run(GlickoFull(**FROZEN_P1, m0=-27.0, cross=False), g, ev)
    b = run(GlickoStart(**FROZEN_P1, m0=-27.0, feats={"rp": {2014: {"A": 2.0}}}), g, ev)
    c = run_ctx(GlickoContext(**FROZEN_P1, m0=-27.0, ctx=_ctx(g)), g, ev)
    for other in (a, b, c):
        pd.testing.assert_frame_equal(p1, other)


def test_run_ctx_matches_run_for_p1():
    g = _games()
    pd.testing.assert_frame_equal(_p1(g), run_ctx(GlickoMargin(**FROZEN_P1, m0=-27.0), g, events(g)))


def test_full_covariance_moves_a_linked_team_that_did_not_play():
    m = GlickoFull(**{**FROZEN_P1, "hfa": 0.0}, m0=-27.0)
    for k in ("A", "B", "C"):
        m.enter(k, FBS, 0.0)
    m.update("A", "B", True, 20.0, 0.0)          # links A and B
    before = m.r["A"]
    m.update("B", "C", True, 30.0, 0.0)          # B beats C big: B's estimate rises...
    assert m.r["A"] > before                      # ...and A, who beat B, gets credit too
    diag = GlickoFull(**{**FROZEN_P1, "hfa": 0.0}, m0=-27.0, cross=False)
    for k in ("A", "B", "C"):
        diag.enter(k, FBS, 0.0)
    diag.update("A", "B", True, 20.0, 0.0)
    a0 = diag.r["A"]
    diag.update("B", "C", True, 30.0, 0.0)
    assert diag.r["A"] == a0


def test_offseason_resets_cross_covariance_and_adds_delta2():
    m = GlickoFull(**FROZEN_P1, m0=-27.0)
    for k in ("A", "B"):
        m.enter(k, FBS, 0.0, "X")
    m.update("A", "B", True, 10.0, 0.0)
    for k in ("A", "B"):
        m.played(k, FBS, 2013, "X")
    i, j = m.idx["A"], m.idx["B"]
    assert m.P[i, j] != 0.0
    var = m.P[i, i]
    m.season_start(2013, 1.0)
    assert m.P[i, j] == 0.0 and math.isclose(m.P[i, i], var + FROZEN_P1["delta"] ** 2)


def test_new_conference_target_and_history_and_rp():
    feats = {"new_conf": {2014: {"A": "Y", "B": "X", "C": "Y"}}, "rp": {2014: {"A": 1.0}}}
    m = GlickoStart(**FROZEN_P1, m0=-27.0, new_conf=True, h=0.5, c=0.1, feats=feats)
    for k, conf, r in (("A", "X", 10.0), ("B", "X", 0.0), ("C", "Y", -10.0)):
        m.enter(k, FBS, 0.0, conf)
        m.played(k, FBS, 2013, conf)
        m.r[k] = r
    m.season_start(2013, 1.0)
    # A moves to Y: Y's 2014 members are A (10) and C (-10), mean 0. History is A's 10.
    target = 0.5 * 0.0 + 0.5 * 10.0
    assert math.isclose(m.r["A"], target + (0.7 + 0.1 * 1.0) * (10.0 - target))


def test_new_conferences_reads_first_game_of_each_season():
    nc = new_conferences(_games())
    assert nc[2014]["A"] == "X" and nc[2014]["C"] == "Y"


def test_z_scores():
    z = _z({"a": 1.0, "b": 2.0, "c": 3.0})
    assert math.isclose(sum(z.values()), 0.0, abs_tol=1e-12)


def _ctx_model(g, ctx, **kw):
    m = GlickoContext(**FROZEN_P1, m0=-27.0, ctx=ctx, **kw)
    for k in ("A", "B"):
        m.enter(k, FBS, 0.0)
    m.cur = 0
    return m


def test_home_edge_trend_and_2020_value():
    g = _games()
    ctx = _ctx(g)
    m = GlickoContext(**FROZEN_P1, m0=-27.0, ctx=ctx, h2013=3.0, slope=-0.1, h2020=0.5)
    i2014 = int(g.index[(g["season"] == 2014) & ~g["neutral"]][0])
    i2020 = int(g.index[(g["season"] == 2020) & ~g["neutral"]][0])
    assert math.isclose(m.edge(i2014), 2.9) and math.isclose(m.edge(i2020), 0.5)


def test_neutral_site_near_one_campus_gets_half_edge_and_tz_term():
    g = _games()
    i = int(g.index[g["neutral"]][0])
    near = pd.Series(0, index=g.index)
    near[i] = -1
    dz = pd.Series(0.0, index=g.index)
    dz[i] = 2.0
    m = GlickoContext(**FROZEN_P1, m0=-27.0, ctx=_ctx(g, near=near, dz=dz), near=True, tz=0.25)
    assert math.isclose(m.edge(i), -0.5 * FROZEN_P1["hfa"] + 0.5)
    off = GlickoContext(**FROZEN_P1, m0=-27.0, ctx=_ctx(g, near=near), near=False)
    assert off.edge(i) == 0.0


def test_overtime_updates_on_a_tie_and_k_inflates_variance():
    g = _games()
    ot = pd.Series(False, index=g.index)
    ot[0] = True
    m = _ctx_model(g, _ctx(g, ot=ot), ot_tie=True)
    mhat, s, _ = m.forecast("A", "B", False, 0.0)
    gain = m.u2["A"] / s
    m.update("A", "B", False, 7.0, 0.0)                  # OT win by 7 read as 0
    assert math.isclose(m.r["A"], gain * (0.0 - mhat))
    kg = pd.Series(False, index=g.index)
    kg[0] = True
    hi = _ctx_model(g, _ctx(g, k_game=kg), k=2.0)
    _, s2, rd2 = hi.forecast("A", "B", False, 0.0)
    assert math.isclose(s2, rd2 + 2.0 * FROZEN_P1["sigma"] ** 2)


def test_looks_refuse_before_their_dates(tmp_path):
    with pytest.raises(SystemExit, match="not allowed before"):
        ev3.look(tmp_path, "interim", today=date(2026, 12, 1))
    with pytest.raises(SystemExit, match="not allowed before"):
        ev3.look(tmp_path, "final", today=date(2027, 12, 31))
