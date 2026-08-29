"""Checks on the recency-weighted screen.

The two that matter: discounting must actually down-weight old seasons (a rho that changes
nothing would make the whole decisive diagnostic vacuous), and rho=1 must reproduce the plain
unweighted mean, so the null sitting at the end of the grid is genuinely the existing method.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

rs = pytest.importorskip("eval_recency_screen")


def _table():
    """Two models, four seasons. Model A was good early, model B is good lately."""
    seasons = np.array([2001, 2002, 2003, 2004])
    L = np.array([[-100.0, -100.0, 0.0, 0.0],     # A: strong early, neutral late
                  [0.0, 0.0, -100.0, -100.0]])    # B: neutral early, strong late
    N = np.full((2, 4), 100.0)
    return L, N, seasons


def test_rho_one_is_the_plain_unweighted_mean():
    L, N, seasons = _table()
    mu, n_eff, _, n_seas = rs.discounted_skill(L, N, seasons, 2005, rho=1.0, lam=0.0)
    assert mu[0] == pytest.approx(-200.0 / 400.0)
    assert mu[1] == pytest.approx(-200.0 / 400.0)   # identical over the full history
    assert n_eff[0] == pytest.approx(400.0)
    assert n_seas[0] == 4


def test_decay_prefers_the_recently_good_model():
    L, N, seasons = _table()
    mu_flat, *_ = rs.discounted_skill(L, N, seasons, 2005, rho=1.0, lam=0.0)
    mu_decay, *_ = rs.discounted_skill(L, N, seasons, 2005, rho=0.5, lam=0.0)
    assert mu_flat[0] == pytest.approx(mu_flat[1])   # tied without discounting
    assert mu_decay[1] < mu_decay[0]                 # B wins once history decays


def test_decay_shrinks_the_effective_sample():
    L, N, seasons = _table()
    _, n1, _, _ = rs.discounted_skill(L, N, seasons, 2005, rho=1.0, lam=0.0)
    _, n2, _, _ = rs.discounted_skill(L, N, seasons, 2005, rho=0.8, lam=0.0)
    assert n2[0] < n1[0]


def test_gap_penalty_only_bites_after_an_absence():
    seasons = np.array([2001, 2002, 2003, 2004])
    L = np.zeros((2, 4))
    N = np.array([[100.0, 100.0, 100.0, 100.0],   # continuous
                  [100.0, 0.0, 0.0, 100.0]])      # two seasons away, then back
    _, n_eff, _, _ = rs.discounted_skill(L, N, seasons, 2005, rho=1.0, lam=0.5)
    assert n_eff[0] == pytest.approx(400.0)
    assert n_eff[1] == pytest.approx(200.0 * np.exp(-0.5 * 2))


def test_shrinkage_pulls_thin_records_toward_parity():
    """Same measured skill, less evidence -> score closer to zero."""
    seasons = np.array([2001, 2002, 2003, 2004])
    L = np.array([[-40.0] * 4, [0.0, 0.0, 0.0, -10.0]])
    N = np.array([[1000.0] * 4, [0.0, 0.0, 0.0, 250.0]])
    sc, n_eff, n_seas = rs.score_models(L, N, seasons, 2005, rho=1.0, kappa=1000,
                                        eta=0.0, c=0.0)
    assert n_eff[0] > n_eff[1]
    assert sc[0] < sc[1]           # the well-evidenced model ranks better
    assert abs(sc[1]) < abs(-10.0 / 250.0)   # the thin one is pulled toward zero


def test_eligibility_excludes_short_records():
    n_eff = np.array([600.0, 400.0, 900.0])
    n_seas = np.array([3, 5, 1])
    ok = rs.eligible(n_eff, n_seas)
    assert list(ok) == [True, False, False]   # needs BOTH the games and the seasons


def test_market_lines_are_excluded_by_name():
    assert rs.MARKET_LINES == {"lineca", "linemidweek"}


def test_k_is_never_selected():
    """k must be a reported sensitivity, not a tuned parameter (addendum 11.3)."""
    src = (Path(__file__).resolve().parents[1] / "scripts" / "eval_recency_screen.py").read_text(
        encoding="utf-8")
    assert "K_GRID" in src
    assert 'select_forward(df, models, bench_col, L, N, seasons, 20, "k"' not in src


def test_fluctuation_flags_a_regime_change_and_not_a_steady_difference():
    """The test must answer "did it CHANGE", not "is it nonzero".

    A method that is uniformly a little better must NOT trip it; one that is tied for ten
    seasons and then better for ten must.
    """
    rng = np.random.default_rng(0)
    seasons = np.repeat(np.arange(2006, 2026), 200)
    y = rng.normal(scale=10.0, size=len(seasons))
    df = pd.DataFrame({"season": seasons, "y": y})
    r0 = np.zeros(len(seasons))

    steady = np.full(len(seasons), 0.5)                       # same small edge throughout
    regime = np.where(seasons >= 2016, 3.0, 0.0)              # edge appears halfway

    o_steady, p_steady, ns = rs.fluctuation(df, steady, r0, 400)
    o_regime, p_regime, _ = rs.fluctuation(df, regime, r0, 400)

    assert ns == 20
    assert o_regime > o_steady
    assert p_regime < p_steady


def test_fluctuation_is_scale_free_on_a_constant_differential():
    """A perfectly constant loss differential has no instability to find."""
    seasons = np.repeat(np.arange(2006, 2026), 100)
    df = pd.DataFrame({"season": seasons, "y": np.zeros(len(seasons))})
    preds = np.full(len(seasons), 2.0)   # identical every season
    obs, _, _ = rs.fluctuation(df, preds, np.zeros(len(seasons)), 200)
    assert obs == pytest.approx(0.0, abs=1e-9)
