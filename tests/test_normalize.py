from cfb_system_maker.normalize import normalize_games


def test_normalize_joins_games_to_consensus_lines():
    games = [
        {
            "id": 401520161,
            "season": 2023,
            "week": 1,
            "homeTeam": "Michigan",
            "awayTeam": "East Carolina",
            "homeConference": "Big Ten",
            "awayConference": "American",
            "homePoints": 30,
            "awayPoints": 14,
        }
    ]
    lines = [
        {
            "id": 401520161,
            "lines": [
                {"provider": "DraftKings", "spread": -35.5, "overUnder": 51.5},
                {"provider": "consensus", "spread": -14.5, "overUnder": 52.5},
            ],
        }
    ]

    [record] = normalize_games(games, lines, provider="consensus")

    assert record.game_id == 401520161
    assert record.season == 2023
    assert record.week == 1
    assert record.home_team == "Michigan"
    assert record.away_team == "East Carolina"
    assert record.home_conference == "Big Ten"
    assert record.away_conference == "American"
    assert record.home_points == 30
    assert record.away_points == 14
    assert record.provider == "consensus"
    assert record.spread == -14.5
    assert record.total == 52.5


def test_line_less_game_contributes_zero_records():
    # DATA-01 floor gate (D-02): a game whose betting row has an empty `lines`
    # list yields no GameRecord. This is the clean pre-2013 behavior — 2012 has
    # games but zero usable lines, so it contributes 0 rows.
    games = [
        {
            "id": 42,
            "season": 2012,
            "week": 1,
            "homeTeam": "Alabama",
            "awayTeam": "Michigan",
            "homePoints": 41,
            "awayPoints": 14,
        }
    ]
    lines = [{"id": 42, "lines": []}]

    assert normalize_games(games, lines, provider="consensus") == []


def test_all_unusable_lines_contribute_zero_records():
    # A betting row whose lines all lack both spread and overUnder is line-less
    # under _select_line ("require a usable line") and contributes 0 rows.
    games = [
        {
            "id": 43,
            "season": 2012,
            "week": 1,
            "homeTeam": "Ohio State",
            "awayTeam": "Purdue",
            "homePoints": 29,
            "awayPoints": 22,
        }
    ]
    lines = [{"id": 43, "lines": [{"provider": "consensus", "spread": None, "overUnder": None}]}]

    assert normalize_games(games, lines, provider="consensus") == []


def test_usable_line_contributes_one_record():
    # Floor season (2013) is non-empty: a game with a usable consensus line
    # yields exactly one GameRecord.
    games = [
        {
            "id": 44,
            "season": 2013,
            "week": 1,
            "homeTeam": "Clemson",
            "awayTeam": "Georgia",
            "homePoints": 38,
            "awayPoints": 35,
        }
    ]
    lines = [{"id": 44, "lines": [{"provider": "consensus", "spread": -3.5, "overUnder": 62.5}]}]

    records = normalize_games(games, lines, provider="consensus")

    assert len(records) == 1
    assert records[0].season == 2013


def test_normalize_uses_first_usable_line_when_provider_missing():
    games = [
        {
            "id": 1,
            "season": 2023,
            "week": 1,
            "home_team": "A",
            "away_team": "B",
            "home_points": 20,
            "away_points": 17,
        }
    ]
    lines = [{"gameId": 1, "lines": [{"provider": "Book", "spread": -2.5, "overUnder": None}]}]

    [record] = normalize_games(games, lines, provider="consensus")

    assert record.provider == "Book"
    assert record.spread == -2.5
    assert record.total is None
