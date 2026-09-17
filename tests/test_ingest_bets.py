"""Tests for the hand-filled bet sheet ingest.

The sign conventions are the fragile part: a spread line is stored from the bettor's
side while the warehouse stores it home-relative, and total CLV flips direction between
OVER and UNDER. Each of those gets pinned here rather than trusted.
"""

from __future__ import annotations

import pandas as pd
import pytest

from ledgers.ingest_bets import (
    REQUIRED_COLS,
    american_payout,
    compute_clv,
    implied_prob,
    pick_close,
    settle,
    spread_result,
    total_result,
)


# ------------------------------------------------------------------------- odds maths

@pytest.mark.parametrize("odds,stake,want", [
    (-110, 110, 100.0),
    (-110, 100, 90.909090909),
    (100, 100, 100.0),
    (150, 100, 150.0),
    (-200, 100, 50.0),
])
def test_american_payout(odds, stake, want):
    assert american_payout(odds, stake) == pytest.approx(want)


@pytest.mark.parametrize("odds,want", [
    (-110, 0.523809),
    (100, 0.50),
    (150, 0.40),
    (-300, 0.75),
])
def test_implied_prob(odds, want):
    assert implied_prob(odds) == pytest.approx(want, abs=1e-5)


def test_a_two_way_market_at_minus_110_both_sides_carries_the_vig():
    # -110/+110 is a fair pair and sums to exactly 1; the real -110/-110 market does not.
    assert implied_prob(-110) + implied_prob(110) == pytest.approx(1.0)
    assert 2 * implied_prob(-110) == pytest.approx(1.0476, abs=1e-4)


# --------------------------------------------------------------------- spread grading

def test_spread_line_is_from_the_bettors_side():
    """A home favourite and the away dog on the same game settle oppositely."""
    # Home -3.5, home wins by 7.
    assert spread_result(7, -3.5) == "win"
    # Away +3.5 in that same game: own margin is -7.
    assert spread_result(-7, 3.5) == "loss"


def test_spread_favourite_failing_to_cover_is_a_loss_not_a_win():
    assert spread_result(3, -7.0) == "loss"


def test_spread_push_on_a_whole_number():
    assert spread_result(3, -3.0) == "push"
    assert spread_result(-3, 3.0) == "push"


def test_spread_dog_covers_by_losing_narrowly():
    assert spread_result(-3, 7.0) == "win"


# ---------------------------------------------------------------------- total grading

@pytest.mark.parametrize("points,line,side,want", [
    (60, 54.5, "over", "win"),
    (50, 54.5, "over", "loss"),
    (50, 54.5, "under", "win"),
    (60, 54.5, "under", "loss"),
    (54, 54.0, "over", "push"),
    (54, 54.0, "under", "push"),
])
def test_total_result_both_sides_and_push(points, line, side, want):
    assert total_result(points, line, side) == want


# -------------------------------------------------------------------------- settlement

def test_push_returns_the_stake_and_nets_nothing():
    assert settle("push", -110, 100) == (0.0, 0.0, 0.0)


def test_loss_costs_exactly_the_stake():
    assert settle("loss", 500, 100) == (0.0, -100, -1.0)


def test_win_at_minus_110_nets_under_the_stake():
    payout, net, roi = settle("win", -110, 110)
    assert (payout, net) == (100.0, 100.0)
    assert roi == pytest.approx(0.90909, abs=1e-4)


# --------------------------------------------------------------------------- CLV signs

def test_spread_clv_positive_when_the_line_moves_to_you():
    # Took home -3.5, closed -4.5: you hold the better number by a point.
    assert compute_clv("spread", "home", -3.5, -4.5, -110) == (1.0, "points")
    # Took the away dog +3.5, closed +2.5: also a point of value.
    assert compute_clv("spread", "away", 3.5, 2.5, -110) == (1.0, "points")


def test_spread_clv_negative_when_the_line_moves_against_you():
    assert compute_clv("spread", "home", -4.5, -3.5, -110) == (-1.0, "points")


def test_total_clv_flips_direction_between_over_and_under():
    assert compute_clv("total", "over", 54.5, 56.5, -110) == (2.0, "points")
    assert compute_clv("total", "under", 54.5, 56.5, -110) == (-2.0, "points")
    assert compute_clv("total", "under", 54.5, 52.5, -110) == (2.0, "points")


def test_moneyline_clv_is_a_probability_not_points():
    clv, unit = compute_clv("moneyline", "away", None, 120, 150)
    assert unit == "probability"
    # Reported to 4dp, so compare against the rounded expectation.
    assert clv == pytest.approx(implied_prob(120) - implied_prob(150), abs=5e-5)
    assert clv > 0


def test_clv_is_none_without_a_close():
    assert compute_clv("spread", "home", -3.5, None, -110) == (None, "")
    assert compute_clv("moneyline", "home", None, None, -110) == (None, "")


# --------------------------------------------------------------------- sheet contract

def test_the_two_teams_are_separate_required_columns():
    """They are read straight from the sheet, so neither may be folded into the other."""
    assert "away" in REQUIRED_COLS and "home" in REQUIRED_COLS
    assert "game" not in REQUIRED_COLS


def test_template_header_matches_the_required_columns():
    from pathlib import Path

    template = Path(__file__).resolve().parents[1] / "ledgers" / "manual_bets_template.csv"
    header = template.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header[:3] == ["placed_at", "away", "home"]
    for col in REQUIRED_COLS:
        assert col in header, col


# ------------------------------------------------------------------- close-line lookup

@pytest.fixture
def lines():
    return pd.DataFrame([
        {"game_id": 1, "provider_key": "draftkings", "spread_close": -7.0,
         "spread_open": -6.0, "total_close": 55.0, "total_open": 54.0,
         "moneyline_home": -300, "moneyline_away": 240},
        {"game_id": 1, "provider_key": "fanduel", "spread_close": -7.5,
         "spread_open": None, "total_close": 56.0, "total_open": None,
         "moneyline_home": -310, "moneyline_away": 250},
    ])


def test_your_book_is_preferred_and_named(lines):
    assert pick_close(lines, 1, "spread", "home", "DraftKings") == (-6.0, -7.0, "draftkings")


def test_book_name_is_matched_case_insensitively(lines):
    assert pick_close(lines, 1, "total", "over", "FANDUEL")[1] == 56.0


def test_away_spread_flips_the_home_relative_warehouse_number(lines):
    assert pick_close(lines, 1, "spread", "away", "DraftKings") == (6.0, 7.0, "draftkings")


def test_totals_are_not_flipped_for_an_away_row(lines):
    # side_role for a total is over/under, never home/away, so no flip can apply.
    assert pick_close(lines, 1, "total", "under", "DraftKings")[1] == 55.0


def test_unknown_book_falls_back_to_the_median_and_says_so(lines):
    opener, close, source = pick_close(lines, 1, "spread", "home", "SomeLocalBook")
    assert close == pytest.approx(-7.25)   # median of -7.0 and -7.5
    assert source.startswith("median")


def test_moneyline_picks_the_side_specific_column(lines):
    assert pick_close(lines, 1, "moneyline", "home", "DraftKings")[1] == -300
    assert pick_close(lines, 1, "moneyline", "away", "DraftKings")[1] == 240


def test_missing_game_reports_no_line_data(lines):
    assert pick_close(lines, 999, "spread", "home", "DraftKings") == (None, None, "no line data")


def test_empty_line_table_is_not_an_error():
    assert pick_close(pd.DataFrame(), 1, "spread", "home", "DraftKings") \
        == (None, None, "no line data")
