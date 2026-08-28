"""CLV sign and takeable-book selection. No network."""

from cfb_totals_model.clv import clv_points, pick_takeable, summarize


def test_clv_under_benefits_when_close_drops():
    assert clv_points("UNDER", 54.5, 52.5) == 2.0
    assert clv_points("OVER", 54.5, 52.5) == -2.0


def test_clv_over_benefits_when_close_rises():
    assert clv_points("OVER", 50.5, 53.5) == 3.0
    assert clv_points("UNDER", 50.5, 53.5) == -3.0


def test_pick_takeable_skips_bovada():
    lines = [
        {"provider": "Bovada", "overUnder": 40.5},
        {"provider": "DraftKings", "overUnder": 51.5},
        {"provider": "ESPN Bet", "overUnder": 52.5},
    ]
    assert pick_takeable(lines) == (51.5, "DraftKings")


def test_pick_takeable_none_without_takeable_book():
    assert pick_takeable([{"provider": "Bovada", "overUnder": 44.5}]) is None
    assert pick_takeable([]) is None


def test_summarize_would_bet_only():
    rows = [
        {"clv": 1.0, "would_bet": True, "hit": True},
        {"clv": -2.0, "would_bet": False, "hit": False},
        {"clv": 0.5, "would_bet": True, "hit": True},
    ]
    s = summarize(rows, would_bet_only=True)
    assert s["n"] == 2
    assert s["mean_clv"] == 0.75
    assert s["hit_pct"] == 100.0
