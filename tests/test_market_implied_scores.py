"""Market-implied scores: (T +/- M)/2 arithmetic and the sportsbook sign convention.
In-memory, no CFB_DATA_ROOT."""
import json
import math

from scripts.market_implied_scores import bovada_opens, implied_scores


def test_home_favourite_by_seven_with_total_55():
    # spreadOpen -7: home favoured by 7, so the implied home margin is +7.
    assert implied_scores(-7.0, 55.0) == (31.0, 24.0)


def test_home_underdog_and_the_scores_add_back():
    h, a = implied_scores(3.5, 48.5)
    assert math.isclose(h, 22.5) and math.isclose(a, 26.0)
    assert math.isclose(h + a, 48.5) and math.isclose(h - a, -3.5)


def test_pick_em_splits_the_total():
    assert implied_scores(0.0, 41.0) == (20.5, 20.5)


def test_bovada_opens_takes_first_bovada_row_and_needs_both_numbers(tmp_path):
    lines = [
        {"id": 1, "lines": [{"provider": "DraftKings", "spreadOpen": -3, "overUnderOpen": 50},
                            {"provider": "Bovada", "spreadOpen": -7, "overUnderOpen": 55},
                            {"provider": "Bovada", "spreadOpen": -1, "overUnderOpen": 40}]},
        {"id": 2, "lines": [{"provider": "Bovada", "spreadOpen": -3, "overUnderOpen": None}]},
        {"id": 3, "lines": None},
    ]
    (tmp_path / "lines_2019.json").write_text(json.dumps(lines))
    assert bovada_opens(tmp_path, 2019) == {1: (-7.0, 55.0)}
