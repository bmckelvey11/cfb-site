"""Glicko P3-D: lam = 0 is P1 exactly; the shrink touches only FBS-vs-FCS games and feeds the
update's innovation; the looks refuse to run early. In-memory, no CFB_DATA_ROOT."""
import math
from datetime import date

import pandas as pd
import pytest

import scripts.glicko_p3d_eval as evd
from scripts.glicko_p3 import GlickoShrinkX
from scripts.glicko_ratings import FBS, FCS, FROZEN_P1, GlickoMargin, events, run


def _games():
    rows, gid = [], 0
    sched = [("A", "X", 38, FBS, FCS), ("B", "A", -7, FBS, FBS), ("X", "Y", 3, FCS, FCS),
             ("B", "Y", 45, FBS, FCS), ("A", "B", 10, FBS, FBS)]
    for season in (2013, 2014):
        for wk, (h, a, mg, hd, ad) in enumerate(sched):
            gid += 1
            rows.append({"game_id": gid, "season": season, "season_type": "regular", "week": wk + 1,
                         "kickoff": pd.Timestamp(season, 9, 1, tz="UTC") + pd.Timedelta(days=7 * wk),
                         "home": h, "away": a, "home_div": hd, "away_div": ad,
                         "home_conf": "F" if hd == FBS else "C", "away_conf": "F" if ad == FBS else "C",
                         "neutral": False, "margin": mg})
    return pd.DataFrame(rows)


def test_lam_zero_reproduces_p1_exactly():
    g = _games()
    ev = events(g)
    pd.testing.assert_frame_equal(run(GlickoMargin(**FROZEN_P1, m0=-27.0), g, ev),
                                  run(GlickoShrinkX(**FROZEN_P1, m0=-27.0, lam=0.0), g, ev))


def _pair(lam, adiv):
    m = GlickoShrinkX(**FROZEN_P1, m0=-27.0, lam=lam)
    m.enter("H", FBS, 0.0)
    m.enter("A", adiv, 0.0)
    m.r["H"], m.r["A"] = 10.0, -20.0
    return m


def test_shrink_applies_only_across_subdivisions():
    full = FROZEN_P1["hfa"] + 30.0
    assert math.isclose(_pair(0.2, FCS).forecast("H", "A", False, 0.0)[0], 0.8 * full)
    assert math.isclose(_pair(0.2, FBS).forecast("H", "A", False, 0.0)[0], full)


def test_update_innovation_uses_the_shrunk_mean_and_p1_gains():
    m = _pair(0.2, FCS)
    mhat, s, _ = m.forecast("H", "A", False, 0.0)
    kh = m.u2["H"] / s
    m.update("H", "A", False, 40.0, 0.0)
    assert math.isclose(m.r["H"], 10.0 + kh * (40.0 - mhat))
    assert math.isclose(mhat, 0.8 * (FROZEN_P1["hfa"] + 30.0))


def test_looks_refuse_before_their_dates(tmp_path):
    with pytest.raises(SystemExit, match="not allowed before"):
        evd.look(tmp_path, "interim", today=date(2027, 1, 1))
    with pytest.raises(SystemExit, match="not allowed before"):
        evd.look(tmp_path, "final", today=date(2028, 1, 1))
