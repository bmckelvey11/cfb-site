from pathlib import Path

from cfb_system_maker.betlog import BetLogRecord, match_to_game, parse_betlog_csv
from cfb_system_maker.models import GameRecord

FIXTURE = Path(__file__).parent / "fixtures" / "betlog_sample.csv"


def test_parse_skips_stray_first_line_and_reads_header():
    result = parse_betlog_csv(FIXTURE)
    assert result.in_scope, "expected at least one in-scope row"


def test_parse_filters_to_pregame_spread_and_total():
    result = parse_betlog_csv(FIXTURE)
    bet_types = {row.bet_type for row in result.in_scope}
    assert bet_types == {"spread_away", "under"}
    # excluded: the live spread_home, the firsthalf spread_home, the ml_home,
    # and the malformed trailing row (over, but malformed) -- 6 data rows in,
    # 2 in scope, 1 malformed, 3 out of scope (live/firsthalf/moneyline)
    assert len(result.in_scope) == 2
    assert result.malformed_count == 1
    assert result.out_of_scope_count == 3


def test_match_to_game_resolves_known_teams():
    row = parse_betlog_csv(FIXTURE).in_scope[0]  # OHIO @ SDSU spread_away
    games_by_date = {
        "2023-08-26": [
            GameRecord(
                game_id=999, season=2023, week=1,
                home_team="San Diego State", away_team="Ohio",
                home_conference="Mountain West", away_conference="MAC",
                home_points=None, away_points=None,
                provider="consensus", spread=-4.0, total=51.0,
            )
        ]
    }
    bet = match_to_game(row, games_by_date)
    assert bet is not None
    assert bet.game_id == 999
    assert bet.bet_type == "spread"
    assert bet.side == "away"
    assert bet.line_taken == 4.0


def test_match_to_game_returns_none_for_unresolvable_team():
    row = parse_betlog_csv(FIXTURE).in_scope[0]
    games_by_date = {"2023-08-26": []}  # no games that day
    assert match_to_game(row, games_by_date) is None
