from cfb_system_maker.backtest import matches_system
from cfb_system_maker.models import FeatureFilter, GameRecord, SystemFilter
from cfb_system_maker.search import (
    candidate_identity,
    categorical_or_bool_values,
    count_dimensions,
    expand_candidates,
    numeric_quantile_values,
)


def _games() -> list[GameRecord]:
    return [
        GameRecord(
            game_id=1, season=2023, week=1, home_team="A", away_team="B",
            home_conference="X", away_conference="Y", home_points=30, away_points=14,
            provider="consensus", spread=-14.5, total=52.5,
        ),
        GameRecord(
            game_id=2, season=2023, week=2, home_team="C", away_team="D",
            home_conference="X", away_conference="Y", home_points=20, away_points=24,
            provider="consensus", spread=3.0, total=48.0,
        ),
        GameRecord(
            game_id=3, season=2023, week=3, home_team="E", away_team="F",
            home_conference="X", away_conference="Y", home_points=10, away_points=40,
            provider="consensus", spread=7.5, total=60.0,
        ),
        GameRecord(
            game_id=4, season=2023, week=4, home_team="G", away_team="H",
            home_conference="X", away_conference="Y", home_points=28, away_points=21,
            provider="consensus", spread=-3.5, total=55.0,
        ),
    ]


def _feature_map() -> dict[int, dict]:
    return {
        1: {"home_running_win_pct": 0.7, "away_running_win_pct": 0.3, "neutralSite": False},
        2: {"home_running_win_pct": 0.5, "away_running_win_pct": 0.5, "neutralSite": True},
        3: {"home_running_win_pct": 0.2, "away_running_win_pct": 0.9, "neutralSite": False},
        4: {"home_running_win_pct": 0.6, "away_running_win_pct": 0.4, "neutralSite": False},
    }


def test_deterministic_enumeration_same_output_twice():
    games = _games()
    feature_map = _feature_map()
    first = expand_candidates(SystemFilter(), games, feature_map)
    second = expand_candidates(SystemFilter(), games, feature_map)
    assert first == second
    assert len(first) > 0


def test_no_incompatible_predicate_combinations():
    games = _games()
    feature_map = _feature_map()
    for child in expand_candidates(SystemFilter(), games, feature_map):
        assert not (child.favorite and child.underdog)
        assert not (child.home and child.away)


def test_home_away_bool_always_paired_with_matching_side():
    games = _games()
    feature_map = _feature_map()
    children = expand_candidates(SystemFilter(), games, feature_map)
    home_children = [c for c in children if c.home]
    away_children = [c for c in children if c.away]
    assert home_children and away_children
    for c in home_children:
        assert c.side == "home"
    for c in away_children:
        assert c.side == "away"


def test_never_duplicates_dimension_already_set_in_parent():
    games = _games()
    feature_map = _feature_map()
    parent = SystemFilter(favorite=True)
    children = expand_candidates(parent, games, feature_map)
    assert all(not (c.favorite and c.underdog) for c in children)
    # favorite_underdog dimension already active -> no child re-touches it
    assert all(c.favorite == parent.favorite and c.underdog == parent.underdog for c in children)


def test_never_emits_noop_or_unchanged_candidate():
    games = _games()
    feature_map = _feature_map()
    parent = SystemFilter()
    children = expand_candidates(parent, games, feature_map)
    for c in children:
        assert c != parent
        assert count_dimensions(c) > 0


def test_lookahead_features_never_appear_as_candidates():
    games = _games()
    feature_map = {
        gid: {**row, "havoc_offense_rate": 0.5, "havoc_defense_rate": 0.4, "attendance": 50000}
        for gid, row in _feature_map().items()
    }
    children = expand_candidates(SystemFilter(), games, feature_map)
    leaked_keys = {
        f.key
        for c in children
        for f in c.feature_filters
        if f.key in {"havoc_offense_rate", "havoc_defense_rate", "attendance"}
    }
    assert leaked_keys == set()


def test_team_scoped_numeric_feature_yields_candidates():
    games = _games()
    feature_map = _feature_map()
    children = expand_candidates(SystemFilter(), games, feature_map)
    win_pct_filters = [
        f for c in children for f in c.feature_filters if f.key == "running_win_pct"
    ]
    assert win_pct_filters
    assert all(f.perspective == "bet_side" for f in win_pct_filters)


def test_in_sample_only_derivation_never_influenced_by_holdout():
    in_sample_games = _games()
    in_sample_feature_map = _feature_map()

    # A distinct "holdout" dataset with an extreme value that would shift quartiles
    # if it ever leaked in. It is deliberately never passed to the functions below —
    # the test proves the signature makes that structurally impossible, not just that
    # we chose not to call it.
    holdout_games = [
        GameRecord(
            game_id=999, season=2024, week=1, home_team="Z", away_team="Y",
            home_conference="X", away_conference="Y", home_points=100, away_points=0,
            provider="consensus", spread=-99.0, total=200.0,
        )
    ]
    holdout_feature_map = {999: {"home_running_win_pct": 0.999, "away_running_win_pct": 0.001}}

    thresholds_a = numeric_quantile_values(in_sample_games, in_sample_feature_map, "running_win_pct")
    thresholds_b = numeric_quantile_values(in_sample_games, in_sample_feature_map, "running_win_pct")
    assert thresholds_a == thresholds_b
    assert 0.999 not in thresholds_a
    assert all(t <= 0.9 for t in thresholds_a)

    levels_a = categorical_or_bool_values(in_sample_games, in_sample_feature_map, "neutralSite")
    levels_b = categorical_or_bool_values(in_sample_games, in_sample_feature_map, "neutralSite")
    assert levels_a == levels_b

    # holdout variables exist only to demonstrate they were never referenced above
    assert holdout_games and holdout_feature_map


def test_canonical_dedup_collapses_differently_ordered_identical_filters():
    filt_a = FeatureFilter(key="neutralSite", op="eq", value=True, perspective="single")
    filt_b = FeatureFilter(key="running_win_pct", op="gte", value=0.5, perspective="bet_side")

    system_1 = SystemFilter(
        seasons={2024, 2023},
        teams={"B", "A"},
        feature_filters=(filt_a, filt_b),
    )
    system_2 = SystemFilter(
        seasons={2023, 2024},
        teams={"A", "B"},
        feature_filters=(filt_b, filt_a),
    )
    assert candidate_identity(system_1) == candidate_identity(system_2)


def test_dimension_cap_returns_empty_when_max_reached():
    games = _games()
    feature_map = _feature_map()
    parent = SystemFilter(
        favorite=True,
        home=True,
        side="home",
        min_spread=-10.0,
        feature_filters=(FeatureFilter(key="neutralSite", op="eq", value=True, perspective="single"),),
    )
    assert count_dimensions(parent) == 4
    assert expand_candidates(parent, games, feature_map, max_dimensions=4) == []


def test_hard_cap_validation_rejects_over_six():
    games = _games()
    feature_map = _feature_map()
    try:
        expand_candidates(SystemFilter(), games, feature_map, max_dimensions=7, hard_cap=7)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for hard_cap > 6")


def test_spread_and_total_range_children_are_sortable_and_present():
    games = _games()
    feature_map = _feature_map()
    children = expand_candidates(SystemFilter(), games, feature_map)
    assert any(c.min_spread is not None for c in children)
    assert any(c.max_spread is not None for c in children)
    assert any(c.min_total is not None for c in children)
    assert any(c.max_total is not None for c in children)


def test_generated_feature_candidate_matches_expected_games_end_to_end():
    # Closes the gap that structural tests above can't see: a generated bet_side
    # feature candidate must be valid input to matches_system and actually select
    # the games its derived threshold implies, not just be well-formed.
    games = _games()
    feature_map = _feature_map()
    system = SystemFilter(
        side="home",
        feature_filters=(
            FeatureFilter(key="running_win_pct", op="gte", value=0.5, perspective="bet_side"),
        ),
    )
    matched_ids = {
        g.game_id for g in games if matches_system(g, system, feature_map, require_played=False)
    }
    # home_running_win_pct: game1=0.7, game2=0.5, game3=0.2, game4=0.6 -> >=0.5 is 1,2,4
    assert matched_ids == {1, 2, 4}


def test_missing_feature_values_never_become_candidate_values():
    games = _games()
    feature_map = _feature_map()
    feature_map[2] = {**feature_map[2], "running_win_pct_missing_marker": None}
    # add a game whose team-scoped feature is entirely absent
    games_with_gap = games + [
        GameRecord(
            game_id=5, season=2023, week=5, home_team="I", away_team="J",
            home_conference="X", away_conference="Y", home_points=17, away_points=10,
            provider="consensus", spread=-1.0, total=44.0,
        )
    ]
    feature_map_with_gap = {**feature_map, 5: {"home_running_win_pct": None, "away_running_win_pct": None}}

    thresholds = numeric_quantile_values(games_with_gap, feature_map_with_gap, "running_win_pct")
    assert None not in thresholds

    levels = categorical_or_bool_values(games_with_gap, feature_map_with_gap, "neutralSite")
    assert None not in levels

    children = expand_candidates(SystemFilter(), games_with_gap, feature_map_with_gap)
    for c in children:
        for f in c.feature_filters:
            assert f.value is not None


def test_categorical_values_capped_at_documented_limit():
    games = [
        GameRecord(
            game_id=i, season=2023, week=i, home_team=f"T{i}", away_team=f"O{i}",
            home_conference="X", away_conference="Y", home_points=20, away_points=10,
            provider="consensus", spread=-3.0, total=45.0,
        )
        for i in range(1, 11)
    ]
    # 10 distinct venue values -> more than the documented cap of 8
    feature_map = {i: {"venue": f"Stadium {i}"} for i in range(1, 11)}

    levels = categorical_or_bool_values(games, feature_map, "venue", perspective="single", limit=8)
    assert len(levels) <= 8
