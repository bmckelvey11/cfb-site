from pathlib import Path

from cfb_system_maker.betlog import (
    BetLogRecord,
    ImportSummary,
    ParsedImport,
    RawBetRow,
    import_betlog,
    load_betlog,
    match_to_game,
    parse_betlog_csv,
    save_betlog,
)
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


# --- Task 3: storage (merge/dedupe) and import ---------------------------------


def _make_bet(game_id, date, home, away, bet_type="spread", side="home"):
    return BetLogRecord(
        game_id=game_id, date=date, home_team=home, away_team=away,
        bet_type=bet_type, side=side, line_taken=-3.5, odds=-110,
        result="win", units_wagered=1.0, units_net=0.91,
    )


def test_save_and_load_betlog_round_trips(tmp_path):
    records = [_make_bet(1, "2023-09-01", "Notre Dame", "Navy")]
    save_betlog(records, tmp_path)
    loaded = load_betlog(tmp_path)
    assert loaded == records


def test_load_betlog_missing_file_returns_empty_list(tmp_path):
    assert load_betlog(tmp_path) == []


def test_import_betlog_dedupes_on_rerun(tmp_path, monkeypatch):
    # First import: one bet lands.
    existing = [_make_bet(1, "2023-09-01", "Notre Dame", "Navy")]
    save_betlog(existing, tmp_path)

    def fake_parse(path):
        return ParsedImport(
            in_scope=[
                RawBetRow(
                    league="ncaaf", start_time="2023-09-01T17:00:00.000Z",
                    game="NAVY @ ND", bet_type="spread_home", side="spread_home",
                    line_taken=-3.5, odds=-110, result="win",
                    units_wagered=1.0, units_net=0.91,
                ),
                RawBetRow(
                    league="ncaaf", start_time="2023-09-08T17:00:00.000Z",
                    game="NAVY @ ND", bet_type="spread_home", side="spread_home",
                    line_taken=-7.0, odds=-110, result="loss",
                    units_wagered=1.0, units_net=-1.0,
                ),
            ],
            out_of_scope_count=0,
            malformed_count=0,
        )

    def fake_match(row, games_by_date):
        game_id = 1 if row.start_time.startswith("2023-09-01") else 2
        return BetLogRecord(
            game_id=game_id, date=row.start_time[:10],
            home_team="Notre Dame", away_team="Navy",
            bet_type="spread", side="home", line_taken=row.line_taken,
            odds=row.odds, result=row.result,
            units_wagered=row.units_wagered, units_net=row.units_net,
        )

    monkeypatch.setattr("cfb_system_maker.betlog.parse_betlog_csv", fake_parse)
    monkeypatch.setattr("cfb_system_maker.betlog.match_to_game", fake_match)
    monkeypatch.setattr("cfb_system_maker.betlog._build_games_by_date", lambda data_dir, in_scope: {})

    summary = import_betlog("fake.csv", tmp_path)

    assert summary.total_rows == 2
    assert summary.in_scope == 2
    assert summary.already_imported == 1
    assert summary.newly_imported == 1
    assert summary.matched == 2
    assert summary.unmatched == []

    all_bets = load_betlog(tmp_path)
    assert len(all_bets) == 2  # the pre-existing bet plus the one new one
