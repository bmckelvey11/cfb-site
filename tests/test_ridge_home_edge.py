"""ridge_v1 home-edge variants: a fixed h is held exactly, free is unchanged, carry skips 2020.
In-memory, no CFB_DATA_ROOT."""
import math

import pandas as pd
import pytest

from scripts.ridge_home_edge_eval import adopt, carry_season, h_from_points
from scripts.weekly_ratings import fit_ridge
from tests.test_weekly_ratings import H_ADV, _round_robin


def test_free_is_ridge_v1_unchanged():
    g = _round_robin()
    a, b = fit_ridge(g, 20, 2), fit_ridge(g, 20, 2, h_fixed=None)
    assert a.h == b.h
    pd.testing.assert_frame_equal(a.table, b.table)


def test_fixed_h_is_held_exactly_and_refits_the_teams():
    g = _round_robin()
    r = fit_ridge(g, 20, 2, h_fixed=0.2)
    assert r.h == 0.2
    assert not r.table["O"].equals(fit_ridge(g, 20, 2).table["O"])


def test_fixing_h_at_the_truth_recovers_the_free_fit_on_a_balanced_schedule():
    # Round robin, every pair home and away: the free fit already finds the true h,
    # so fixing it there changes nothing.
    g = _round_robin()
    free = fit_ridge(g, 1e-9, 1e-9)
    assert math.isclose(free.h, H_ADV, abs_tol=1e-6)
    held = fit_ridge(g, 1e-9, 1e-9, h_fixed=H_ADV)
    pd.testing.assert_frame_equal(free.table, held.table, atol=1e-4)  # O/D level is only weakly identified


def test_points_to_ppp():
    fs = pd.DataFrame({"N": [11.0, 13.0]})
    assert math.isclose(h_from_points(2.4, fs), 0.1)


def test_carry_never_uses_2020():
    assert carry_season(2019) == 2018
    assert carry_season(2021) == 2019
    assert carry_season(2022) == 2021


@pytest.mark.parametrize("choice,hi,expected", [("free", -0.1, False), ("carry", -0.01, True),
                                                ("carry", 0.02, False)])
def test_adopt_rule(choice, hi, expected):
    check = {"paired_minus_free": {"carry": {"crps": {"ci95": [-0.2, hi]}}}}
    assert adopt(choice, check) is expected
