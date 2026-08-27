from cfb_system_maker.betlog import BetLogRecord
from cfb_system_maker.clv import (
    ClvStats,
    SeasonClv,
    compute_clv,
    compute_clv_by_season,
    compute_clv_chart,
    compute_clv_stats,
    find_closing_line,
)


def _bet(game_id=1, date="2023-09-01", bet_type="spread", side="away", line_taken=4.0):
    return BetLogRecord(
        game_id=game_id, date=date, home_team="San Diego State", away_team="Ohio",
        bet_type=bet_type, side=side, line_taken=line_taken, odds=-110,
        result="win", units_wagered=1.0, units_net=0.91,
    )


def test_compute_clv_positive_when_line_moved_bettors_way_spread_away():
    # Bettor took the away dog at +6.0. `closing_line` is home-relative
    # (CFBD's raw `spread` convention): home favored by 4 at close =>
    # closing_line = -4.0, which in away-relative terms is +4.0 -- fewer
    # points than the +6.0 our bettor already had. A fresh bettor at close
    # gets a worse number than ours did, so CLV is positive for us.
    bet = _bet(side="away", line_taken=6.0)
    clv = compute_clv(bet, closing_line=-4.0)  # home-relative: home -4.0 => away +4.0
    assert clv == 2.0


def test_compute_clv_negative_when_line_moved_against_bettor():
    # Bettor took away +4.0. Closing home-relative -6.0 => away +6.0, a
    # bigger (better) number for the away side than what the bettor got --
    # a fresh bettor at close does better than ours did, so CLV is negative.
    bet = _bet(side="away", line_taken=4.0)
    clv = compute_clv(bet, closing_line=-6.0)  # home-relative: home -6.0 => away +6.0
    assert clv == -2.0


def test_compute_clv_home_side_inverts_sign_convention():
    # Home bettor took -4.0 (favorite). For the home side, home-relative
    # IS side-relative, so no sign flip applies -- unlike the away tests
    # above. Closing line -6.0 means the favorite grew: a fresh bettor at
    # close must lay 6 points, worse than our bettor's 4. Our bettor got
    # the better number, so CLV is positive: line_taken - closing_line
    # = -4.0 - (-6.0) = 2.0.
    bet = _bet(side="home", line_taken=-4.0)
    clv = compute_clv(bet, closing_line=-6.0)
    assert clv == 2.0


def test_compute_clv_total_over_positive_when_closing_total_higher():
    bet = _bet(bet_type="total", side="over", line_taken=51.0)
    clv = compute_clv(bet, closing_line=54.0)
    assert clv == 3.0


def test_compute_clv_total_under_positive_when_closing_total_lower():
    bet = _bet(bet_type="total", side="under", line_taken=51.0)
    clv = compute_clv(bet, closing_line=48.0)
    assert clv == 3.0


def test_compute_clv_stats_matches_hand_computed_values():
    stats = compute_clv_stats([2.0, -1.0, 3.0, 0.5])
    assert stats.n == 4
    assert stats.mean_clv == 1.125
    assert stats.std_error > 0
    assert stats.t_stat != 0.0


def test_compute_clv_stats_empty_list_returns_zeros():
    stats = compute_clv_stats([])
    assert stats == ClvStats(n=0, mean_clv=0.0, t_stat=0.0, std_error=0.0)


def test_compute_clv_by_season_groups_correctly():
    bet_2023 = _bet(date="2023-09-01")
    bet_2024 = _bet(date="2024-09-01")
    result = compute_clv_by_season([(bet_2023, 2.0), (bet_2024, -1.0), (bet_2024, 3.0)])
    by_season = {r.season: r for r in result}
    assert by_season[2023] == SeasonClv(season=2023, n=1, mean_clv=2.0)
    assert by_season[2024] == SeasonClv(season=2024, n=2, mean_clv=1.0)


def test_find_closing_line_prefers_consensus_provider(tmp_path):
    import json

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    lines_data = [
        {
            "id": 1, "season": 2023,
            "lines": [
                {"provider": "DraftKings", "spread": -3.5, "overUnder": 50.5},
                {"provider": "consensus", "spread": -4.0, "overUnder": 51.0},
            ],
        }
    ]
    (raw_dir / "lines_2023.json").write_text(json.dumps(lines_data))
    bet = _bet(game_id=1, date="2023-09-01", bet_type="spread")
    closing = find_closing_line(bet, tmp_path)
    assert closing == -4.0  # consensus preferred over DraftKings


def test_find_closing_line_falls_back_through_provider_cascade(tmp_path):
    import json

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    lines_data = [
        {
            "id": 1, "season": 2023,
            "lines": [{"provider": "Bovada", "spread": -3.0, "overUnder": None}],
        }
    ]
    (raw_dir / "lines_2023.json").write_text(json.dumps(lines_data))
    bet = _bet(game_id=1, date="2023-09-01", bet_type="spread")
    closing = find_closing_line(bet, tmp_path)
    assert closing == -3.0  # no consensus/DraftKings, cascades down to Bovada


def test_find_closing_line_returns_none_when_no_usable_line(tmp_path):
    import json

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    lines_data = [{"id": 1, "season": 2023, "lines": []}]
    (raw_dir / "lines_2023.json").write_text(json.dumps(lines_data))
    bet = _bet(game_id=1, date="2023-09-01")
    assert find_closing_line(bet, tmp_path) is None


def test_find_closing_line_falls_back_to_prior_season_for_january_bet(tmp_path):
    import json

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    # Bet dated January 2024 -- the game is really a 2023-season bowl game,
    # so it lives in lines_2023.json, NOT lines_2024.json (which doesn't exist).
    lines_data = [
        {"id": 1, "season": 2023, "lines": [{"provider": "consensus", "spread": -3.0, "overUnder": 55.0}]}
    ]
    (raw_dir / "lines_2023.json").write_text(json.dumps(lines_data))
    bet = _bet(game_id=1, date="2024-01-08", bet_type="spread")
    closing = find_closing_line(bet, tmp_path)
    assert closing == -3.0


def test_compute_clv_chart_empty_input_returns_empty_shape():
    result = compute_clv_chart([])
    assert result == {"points": [], "polyline": "", "zero_y": 75, "min_x": None, "max_x": None}


def test_compute_clv_chart_orders_by_date_and_accumulates():
    later = _bet(game_id=2, date="2023-09-08")
    earlier = _bet(game_id=1, date="2023-09-01")
    # passed out of order -- function must sort by date
    result = compute_clv_chart([(later, 3.0), (earlier, 2.0)])
    assert len(result["points"]) == 2
    assert result["points"][0]["clv"] == 2.0  # earlier bet first, cumulative 2.0
    assert result["points"][1]["clv"] == 5.0  # earlier + later, cumulative 2.0 + 3.0
    assert result["max_x"] == 1
