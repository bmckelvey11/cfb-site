"""Previous-season priors for the weekly ratings. In-memory: no CFB_DATA_ROOT, no network."""
import numpy as np
import pandas as pd
import pytest

from scripts.weekly_priors import (
    build_priors, fit_carryover, priors_for_season, week1_ratings,
)
from scripts.weekly_ratings import Ratings, fit_ridge, fit_set
from test_weekly_ratings import T0, TRUE_D, TRUE_O, TRUE_P, _game, _round_robin

PRIOR = pd.DataFrame({"O0": [0.3, 0.1, 0.0, -0.1, -0.1, -0.2, 0.0],
                      "D0": [-0.2, 0.1, 0.0, 0.2, 0.0, -0.1, 0.0],
                      "P0": [0.5, -0.2, 0.1, 0.1, -0.3, -0.2, 0.0]},
                     index=list("ABCDEF") + ["G"])


# 1. Prior-centered ridge ------------------------------------------------------------

def test_huge_lambda_returns_the_priors_including_teams_without_games():
    r = fit_ridge(fit_set(_round_robin(), T0), 1e12, 1e12, prior=PRIOR)
    for team in PRIOR.index:
        assert r.table.loc[team, "O"] == pytest.approx(PRIOR.loc[team, "O0"], abs=1e-6)
        assert r.table.loc[team, "D"] == pytest.approx(PRIOR.loc[team, "D0"], abs=1e-6)
        assert r.table.loc[team, "P"] == pytest.approx(PRIOR.loc[team, "P0"], abs=1e-6)
    assert r.table.loc["G", "n_games"] == 0


def test_tiny_lambda_lets_noiseless_data_override_the_prior():
    r = fit_ridge(fit_set(_round_robin(), T0), 1e-4, 1e-7, prior=PRIOR)
    for team in TRUE_O:
        assert r.table.loc[team, "O"] == pytest.approx(TRUE_O[team], abs=1e-5)
        assert r.table.loc[team, "D"] == pytest.approx(TRUE_D[team], abs=1e-5)
        assert r.table.loc[team, "P"] == pytest.approx(TRUE_P[team], abs=1e-5)


def test_no_prior_is_exactly_release_b():
    fs = fit_set(_round_robin(), T0)
    a, b = fit_ridge(fs, 40, 8), fit_ridge(fs, 40, 8, prior=None)
    pd.testing.assert_frame_equal(a.table, b.table)


# 2. Carryover coefficients -----------------------------------------------------------

def test_fit_carryover_recovers_known_coefficients():
    rng = np.random.default_rng(1)
    n = 300
    o_prev, d_prev, p_prev = rng.normal(0, 0.5, n), rng.normal(0, 0.5, n), rng.normal(0, 1, n)
    rp = rng.uniform(0.2, 1.0, n)
    pairs = pd.DataFrame({
        "team": [f"T{i % 100}" for i in range(n)],
        "O_prev": o_prev, "O_cur": (0.4 + 0.3 * rp) * o_prev,
        "D_prev": d_prev, "D_cur": 0.5 * d_prev,
        "P_prev": p_prev, "P_cur": 0.6 * p_prev, "rp": rp,
    })
    coefs = fit_carryover(pairs)
    assert coefs["b"]["value"] == pytest.approx(0.4)
    assert coefs["c"]["value"] == pytest.approx(0.3)
    assert coefs["b_D"]["value"] == pytest.approx(0.5)
    assert coefs["a"]["value"] == pytest.approx(0.6)
    assert all("se" in v for v in coefs.values())


# 3. Building priors -------------------------------------------------------------------

COEFS = {"b": {"value": 0.4}, "c": {"value": 0.3}, "b_D": {"value": 0.5}, "a": {"value": 0.6}}


def _final(teams, o, d, p, **levels) -> Ratings:
    table = pd.DataFrame({"O": o, "D": d, "P": p, "n_games": 12, "n_possessions": 140},
                         index=teams)
    lv = {"mu": 2.2, "nu": 11.8, "h": 0.1, "c": 0.5, **levels}
    return Ratings(table=table, unrated=0.0, **lv)


def test_build_priors_centers_imputes_and_flags():
    final_prev = _final(["A", "B", "C"], [0.8, -0.2, 0.1], [-0.4, 0.3, 0.0], [1.0, -0.5, 0.2])
    rp = pd.Series({"A": 0.7, "B": 0.3})
    pr = build_priors(final_prev, rp, ["A", "B", "C", "N"], COEFS)

    assert list(pr["prior_source"]) == ["carryover", "carryover", "rp_imputed", "new_to_fbs"]
    assert pr.loc["C", "rp"] == pytest.approx(0.5)
    for col in ("O0", "D0", "P0"):
        assert pr[col].sum() == pytest.approx(0.0, abs=1e-12)
    # Centering shifts every team by one constant; the new team started at 0.
    shift = -pr.loc["N", "O0"]
    assert pr.loc["A", "O0"] + shift == pytest.approx((0.4 + 0.3 * 0.7) * 0.8)
    assert pr.loc["C", "O0"] + shift == pytest.approx((0.4 + 0.3 * 0.5) * 0.1)
    assert pr.loc["B", "D0"] - pr.loc["N", "D0"] == pytest.approx(0.5 * 0.3)
    assert pr.loc["A", "P0"] - pr.loc["N", "P0"] == pytest.approx(0.6 * 1.0)


# 4. Leakage ---------------------------------------------------------------------------

def _two_seasons() -> pd.DataFrame:
    prev = _round_robin().assign(season=2023)
    prev["kickoff"] = prev["kickoff"] - pd.Timedelta(days=365)
    cur = pd.DataFrame([_game(500 + i, h, a, T0 + pd.Timedelta(days=7 * i))
                        for i, (h, a) in enumerate([("A", "B"), ("C", "D"), ("E", "F")])])
    return pd.concat([prev, cur.assign(season=2024)], ignore_index=True)


def test_current_season_results_cannot_move_its_priors():
    games = _two_seasons()
    rp = pd.Series(0.6, index=list("ABCDEF"))
    before = priors_for_season(games, 2024, rp, COEFS, 40, 8)
    shifted = games.copy()
    shifted.loc[shifted["season"] == 2024, ["home_reg", "total"]] = [150.0, 220.0]
    pd.testing.assert_frame_equal(before, priors_for_season(shifted, 2024, rp, COEFS, 40, 8))


def test_week1_snapshot_holds_priors_and_no_current_games():
    games = _two_seasons()
    rp = pd.Series(0.6, index=list("ABCDEF"))
    pr = priors_for_season(games, 2024, rp, COEFS, 40, 8)
    final_prev = fit_ridge(games[games["season"] == 2023], 40, 8)
    w1 = week1_ratings(final_prev, pr)
    assert (w1.table["n_games"] == 0).all()
    assert w1.table["O"].to_dict() == pytest.approx(pr["O0"].to_dict())
    assert w1.table["P"].to_dict() == pytest.approx(pr["P0"].to_dict())


# 5. Week-1 levels ---------------------------------------------------------------------

def test_week1_levels_are_last_seasons_final_levels():
    final_prev = _final(["A", "B"], [0.2, -0.2], [0.1, -0.1], [0.3, -0.3],
                        mu=2.31, nu=12.4, h=0.12, c=0.61)
    pr = build_priors(final_prev, pd.Series({"A": 0.5, "B": 0.5}), ["A", "B"], COEFS)
    w1 = week1_ratings(final_prev, pr)
    assert (w1.mu, w1.nu, w1.h, w1.c) == (2.31, 12.4, 0.12, 0.61)
