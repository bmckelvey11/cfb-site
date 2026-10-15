import itertools
import warnings

import duckdb
import numpy as np
import pandas as pd

from scripts.build_spread_implied_power_ratings import VERSION, build_ratings, spread_to_paired_rows


def test_version_is_stamped():
    assert VERSION == "1.0"


def test_home_favorite_gets_positive_margin():
    games = pd.DataFrame({
        "season": [2025], "week": [1],
        "homeTeam": ["Ohio State"], "awayTeam": ["Akron"],
        "spread": [-21.5], "neutralSite": [False],
    })
    paired = spread_to_paired_rows(games)

    home_row = paired[paired["team"] == "Ohio State"].iloc[0]
    away_row = paired[paired["team"] == "Akron"].iloc[0]

    assert home_row["margin"] == 21.5
    assert away_row["margin"] == -21.5
    assert home_row["opponent"] == "Akron"
    assert away_row["opponent"] == "Ohio State"
    assert home_row["is_home"] == True
    assert away_row["is_home"] == False


def test_neutral_site_home_team_is_not_home():
    games = pd.DataFrame({
        "season": [2025], "week": [1],
        "homeTeam": ["Alabama"], "awayTeam": ["Georgia"],
        "spread": [-3.0], "neutralSite": [True],
    })
    paired = spread_to_paired_rows(games)

    home_row = paired[paired["team"] == "Alabama"].iloc[0]
    assert home_row["is_home"] == False


def test_missing_neutral_site_flag_defaults_to_not_neutral():
    games = pd.DataFrame({
        "season": [2025], "week": [1],
        "homeTeam": ["Duke"], "awayTeam": ["Wake Forest"],
        "spread": [-1.0], "neutralSite": [None],
    })
    paired = spread_to_paired_rows(games)

    home_row = paired[paired["team"] == "Duke"].iloc[0]
    assert home_row["is_home"] == True


def test_mixed_neutral_site_column_stays_boolean():
    # An object column holding None alongside bools must not be integer-inverted.
    games = pd.DataFrame({
        "season": [2025, 2025], "week": [1, 1],
        "homeTeam": ["Duke", "Alabama"], "awayTeam": ["Wake Forest", "Georgia"],
        "spread": [-1.0, -3.0], "neutralSite": [None, True],
    })
    paired = spread_to_paired_rows(games)
    assert set(paired["is_home"].tolist()) <= {True, False}
    assert paired.loc[paired["team"] == "Duke", "is_home"].iloc[0] == True
    assert paired.loc[paired["team"] == "Alabama", "is_home"].iloc[0] == False


def test_two_rows_per_game():
    games = pd.DataFrame({
        "season": [2025, 2025], "week": [1, 1],
        "homeTeam": ["Ohio State", "Texas"], "awayTeam": ["Akron", "Michigan"],
        "spread": [-21.5, -3.0], "neutralSite": [False, False],
    })
    paired = spread_to_paired_rows(games)
    assert len(paired) == 4
    assert list(paired.columns) == ["season", "week", "team", "opponent", "margin", "is_home"]


def _synthetic_warehouse(strengths: dict[str, float], seasons: list[int], hfa: float = 2.5) -> duckdb.DuckDBPyConnection:
    """In-memory stg.games: round-robin each season, spread = -(home - away + hfa) + noise."""
    rng = np.random.default_rng(0)
    rows = []
    for season in seasons:
        for week, (home, away) in enumerate(itertools.permutations(strengths, 2), start=1):
            spread = -(strengths[home] - strengths[away] + hfa) + rng.normal(0, 1.0)
            rows.append((season, week, "regular", home, away, round(spread * 2) / 2, False))
    df = pd.DataFrame(rows, columns=["season", "week", "seasonType", "homeTeam", "awayTeam", "spread", "neutralSite"])
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA stg")
    con.register("games_df", df)
    con.execute("CREATE TABLE stg.games AS SELECT * FROM games_df")
    return con


def test_build_ratings_recovers_synthetic_order():
    strengths = {"Alpha": 14.0, "Bravo": 7.0, "Charlie": 0.0, "Delta": -7.0, "Echo": -14.0}
    con = _synthetic_warehouse(strengths, [2024, 2025])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ratings = build_ratings(con, season=2025, week=None, prior_seasons=1)

    assert list(ratings.columns) == ["team", "games_played", "power_rating", "power_se", "source"]
    assert ratings["team"].tolist() == ["Alpha", "Bravo", "Charlie", "Delta", "Echo"]
    assert not ratings["team"].str.endswith("]").any()
    assert (ratings["source"] == "blended").all()
    # Each team plays 8 games per round-robin season (4 home, 4 away).
    assert (ratings["games_played"] == 8).all()
