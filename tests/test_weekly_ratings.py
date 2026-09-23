"""Weekly as-of PPP and pace ratings (Release B). In-memory: no CFB_DATA_ROOT, no network."""
import itertools
import math

import numpy as np
import pandas as pd
import pytest

from scripts.weekly_ratings import (
    Ratings, build_games, fit_raw, fit_ridge, fit_set, forecast_total,
)

T0 = pd.Timestamp("2024-09-07T16:00:00Z")

MU, H_ADV, NU = 2.10, 0.05, 12.0
TRUE_O = {"A": 0.6, "B": 0.3, "C": 0.1, "D": -0.2, "E": -0.3, "F": -0.5}
TRUE_D = {"A": -0.4, "B": 0.2, "C": -0.1, "D": 0.5, "E": 0.0, "F": -0.2}
TRUE_P = {"A": 1.0, "B": -0.5, "C": 0.2, "D": 0.3, "E": -0.6, "F": -0.4}


def _game(gid, home, away, kickoff, *, neutral=False, ot=0.0, gated=False):
    """A noiseless game row generated from the true ratings above."""
    n = NU + TRUE_P[home] + TRUE_P[away]
    hh = 0 if neutral else 1
    y_home = MU + TRUE_O[home] + TRUE_D[away] + H_ADV * hh
    y_away = MU + TRUE_O[away] + TRUE_D[home] - H_ADV * hh
    return {
        "game_id": gid, "season": 2024, "week": 1 + gid // 100, "kickoff": kickoff,
        "home": home, "away": away, "neutral": neutral,
        "home_reg": y_home * n, "away_reg": y_away * n,
        "home_poss": n, "away_poss": n, "N": n, "ot": ot,
        "total": (y_home + y_away) * n + ot, "gated": gated,
    }


def _round_robin() -> pd.DataFrame:
    rows, gid = [], 0
    for home, away in itertools.permutations(TRUE_O, 2):
        rows.append(_game(gid, home, away, T0 - pd.Timedelta(days=60 - gid)))
        gid += 1
    rows.append(_game(gid, "A", "F", T0 - pd.Timedelta(days=5), neutral=True))
    rows.append(_game(gid + 1, "C", "D", T0 - pd.Timedelta(days=4), neutral=True, ot=7.0))
    return pd.DataFrame(rows)


def _assert_same(a: Ratings, b: Ratings):
    assert (a.mu, a.nu, a.h, a.c) == pytest.approx((b.mu, b.nu, b.h, b.c))
    pd.testing.assert_frame_equal(a.table, b.table)


# 1. Leakage -------------------------------------------------------------------

def test_future_and_tied_games_cannot_move_the_snapshot():
    past = _round_robin()
    later = _game(900, "A", "B", T0 + pd.Timedelta(hours=3))
    tied = _game(901, "C", "E", T0)
    before = fit_ridge(fit_set(past, T0), 20, 2)
    full = pd.concat([past, pd.DataFrame([later, tied])], ignore_index=True)
    _assert_same(before, fit_ridge(fit_set(full, T0), 20, 2))

    blown_out = full.copy()
    blown_out.loc[blown_out["game_id"] == 900, ["home_reg", "total"]] = [140.0, 200.0]
    _assert_same(before, fit_ridge(fit_set(blown_out, T0), 20, 2))
    _assert_same(fit_raw(fit_set(full, T0)), fit_raw(fit_set(blown_out, T0)))


def test_gated_games_are_withheld_from_fits():
    past = _round_robin()
    bad = _game(902, "B", "F", T0 - pd.Timedelta(days=1), gated=True)
    bad.update(home_reg=300.0, total=400.0)
    with_bad = pd.concat([past, pd.DataFrame([bad])], ignore_index=True)
    _assert_same(fit_ridge(fit_set(past, T0), 20, 2),
                 fit_ridge(fit_set(with_bad, T0), 20, 2))


# 2. Recovery -------------------------------------------------------------------

def test_noiseless_round_robin_recovers_true_ratings_and_signs():
    # Tiny but well-conditioned penalties: bias ~ rating*lam/n. PPP weights are possessions
    # (~130 a team here), pace weights are games (~11), so pace needs the smaller lam.
    r = fit_ridge(fit_set(_round_robin(), T0), 1e-4, 1e-7)
    assert r.mu == pytest.approx(MU, abs=1e-5)
    assert r.h == pytest.approx(H_ADV, abs=1e-5)
    assert r.nu == pytest.approx(NU, abs=1e-5)
    for team in TRUE_O:
        assert r.table.loc[team, "O"] == pytest.approx(TRUE_O[team], abs=1e-5)
        assert r.table.loc[team, "D"] == pytest.approx(TRUE_D[team], abs=1e-5)
        assert r.table.loc[team, "P"] == pytest.approx(TRUE_P[team], abs=1e-5)
    # Sign convention: the best defense (fewest points allowed) is the most negative D.
    assert r.table["D"].idxmin() == "A"


# 3. Shrinkage ------------------------------------------------------------------

def test_huge_lambda_shrinks_every_rating_to_league_average():
    games = fit_set(_round_robin(), T0)
    r = fit_ridge(games, 1e12, 1e12)
    assert np.abs(r.table[["O", "D", "P"]].to_numpy()).max() < 1e-6
    pts = games["home_reg"].sum() + games["away_reg"].sum()
    poss = games["home_poss"].sum() + games["away_poss"].sum()
    assert r.mu == pytest.approx(pts / poss, abs=1e-6)
    assert r.nu == pytest.approx(games["N"].mean(), abs=1e-6)
    assert r.c == pytest.approx(games["ot"].mean())


def test_unrated_team_is_average_under_ridge_and_missing_under_raw():
    games = fit_set(_round_robin(), T0)
    ridge, raw = fit_ridge(games, 20, 2), fit_raw(games)
    avg = forecast_total(ridge, "Newcomer", "Newcomer2", neutral=True)
    assert avg == pytest.approx(ridge.nu * 2 * ridge.mu + ridge.c)
    assert math.isnan(forecast_total(raw, "A", "Newcomer", neutral=False))


# 4. Possessions, line-score points, gate ----------------------------------------

def _payload_game(gid, home_ls, away_ls, **kw):
    g = {"id": gid, "season": 2024, "week": 3, "seasonType": "regular", "completed": True,
         "startDate": "2024-09-14T19:30:00.000Z", "neutralSite": False,
         "homeTeam": "Home U", "awayTeam": "Away St",
         "homeClassification": "fbs", "awayClassification": "fbs",
         "homeLineScores": home_ls, "awayLineScores": away_ls,
         "homePoints": sum(home_ls), "awayPoints": sum(away_ls)}
    g.update(kw)
    return g


def _drives(gid, n_home, n_away, ot_home=0):
    rows = []
    for offense, is_home, n, period in (("Home U", True, n_home, 1), ("Away St", False, n_away, 1),
                                        ("Home U", True, ot_home, 5)):
        rows += [{"gameId": gid, "offense": offense, "isHomeOffense": is_home,
                  "startPeriod": period, "startOffenseScore": 0, "endOffenseScore": 999}
                 for _ in range(n)]
    return rows


def test_points_come_from_line_scores_and_ot_drives_are_not_possessions():
    games, drops = build_games(
        [_payload_game(1, [7, 7, 7, 7, 7], [3, 0, 7, 11])],
        _drives(1, 12, 12, ot_home=1),
    )
    g = games.iloc[0]
    assert (g["home_reg"], g["away_reg"], g["ot"], g["total"]) == (28, 21, 7, 56)
    assert (g["home_poss"], g["away_poss"], g["N"]) == (12, 12, 12.0)
    assert not g["gated"]
    assert g["kickoff"] == pd.Timestamp("2024-09-14T19:30:00Z")


def test_build_games_gates_drops_and_counts():
    payload = [
        _payload_game(1, [7, 7, 7, 7], [3, 0, 7, 0]),                     # clean
        _payload_game(2, [7, 7, 7, 7], [3, 0, 7, 0]),                     # drive gap 3 -> gated
        _payload_game(3, [7, 7, 7, 7], [3, 0, 7, 0]),                     # no drives -> gated
        _payload_game(4, [7, 7, 7, 7], [3, 0, 7, 0], awayClassification="fcs"),
        _payload_game(5, [7, 7, 7, 7], [3, 0, 7, 0], completed=False),
        _payload_game(6, [7, 7, 7, 7], [3, 0, 7, 0], homePoints=30),     # line scores != final
        _payload_game(7, [7, 7, 7, 7], [3, 0, 7, 0], seasonType="postseason"),
    ]
    games, drops = build_games(payload, _drives(1, 12, 11) + _drives(2, 12, 9))
    assert list(games["game_id"]) == [1, 2, 3]
    assert list(games["gated"]) == [False, True, True]
    assert drops == {"not_fbs_vs_fbs": 1, "not_completed": 1,
                     "line_scores_do_not_sum_to_final": 1, "not_regular_season": 1}


# 5. Total ----------------------------------------------------------------------

def test_total_reproduces_the_guide_worked_example():
    table = pd.DataFrame({"O": [0.40, -0.10], "D": [-0.30, 0.20], "P": [0.8, -0.3]},
                         index=["Home", "Away"])
    r = Ratings(mu=2.10, nu=12.0, h=0.05, c=0.0, table=table, unrated=0.0)
    assert forecast_total(r, "Home", "Away", neutral=False) == pytest.approx(55.0)
    # Neutral site: home field drops out of both rates, and it cancels in the sum.
    assert forecast_total(r, "Home", "Away", neutral=True) == pytest.approx(55.0)


# 6. Evaluation pieces -------------------------------------------------------------

def _scored(n_weeks=30, per_week=10, seed=0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = n_weeks * per_week
    truth = rng.normal(55, 14, n)
    return pd.DataFrame({
        "season": np.repeat(2021 + np.arange(n_weeks) // 6, per_week),
        "week": np.repeat(np.arange(n_weeks) % 6 + 2, per_week),
        "total": truth,
        "good": truth + rng.normal(0, 3, n),
        "bad": truth + rng.normal(0, 12, n),
    })


def test_paired_difference_is_zero_for_identical_forecasts_and_negative_for_better():
    from scripts.weekly_ratings_eval import paired_mae_diff
    df = _scored()
    same = paired_mae_diff(df, "good", "good")
    assert same["diff"] == 0 and same["ci95"] == [0.0, 0.0]
    better = paired_mae_diff(df, "good", "bad")
    assert better["ci95"][1] < 0
    assert set(better["by_season"]) == set(df["season"].unique())
    assert better["n_clusters"] == df.groupby(["season", "week"]).ngroups


def test_encompassing_slope_recovers_known_slope():
    from scripts.weekly_ratings_eval import encompassing_slope
    df = _scored()
    df["open"] = df["good"]  # truth + noise, so total - open varies
    df["fc"] = df["open"] + 2.0 * (df["total"] - df["open"])  # disagreement is half right
    out = encompassing_slope(df, "fc")
    assert out["slope"] == pytest.approx(0.5)


@pytest.mark.parametrize("lo, hi, by_season, expected", [
    (0.2, 0.9, [0.5, 0.4, 0.6, 0.3, 0.7], "worse"),           # whole interval above 0
    (-0.9, -0.2, [-0.5, -0.4, -0.6, -0.3, -0.7], "improves"),  # below 0, every season
    (-0.9, -0.2, [-0.5, -0.4, 0.1, -0.3, -0.7], "improves"),   # one season may disagree
    (-0.9, -0.2, [-0.5, 0.2, 0.1, -0.3, -0.7], "matches"),     # two may not
    (-0.3, 0.2, [-0.5, -0.4, -0.6, -0.3, -0.7], "matches"),    # interval covers 0
])
def test_classify_verdict(lo, hi, by_season, expected):
    from scripts.weekly_ratings_eval import classify_verdict
    assert classify_verdict(lo, hi, by_season) == expected
