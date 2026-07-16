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
