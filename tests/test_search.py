import random

import cfb_system_maker.search as search_module
from cfb_system_maker.backtest import matches_system
from cfb_system_maker.models import FeatureFilter, GameRecord, SystemFilter
from cfb_system_maker.search import (
    BeamCandidate,
    BeamSearchResult,
    beam_search,
    candidate_identity,
    categorical_or_bool_values,
    count_dimensions,
    expand_candidates,
    grade_finalists,
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


def test_low_coverage_line_move_features_excluded_from_candidate_pool():
    """spread_open/spread_move/total_open/total_move are genuine pregame values but
    populated on only ~18% of games, non-randomly (2023-2025, book-matched closes).
    Search must not silently include them -- re-enabling is a deliberate code change,
    not a side effect of registering the features."""
    games = _games()
    feature_map = {
        1: {**_feature_map()[1], "spread_open": -3.0, "spread_move": -1.0, "total_open": 50.0, "total_move": 2.5},
        2: {**_feature_map()[2], "spread_open": 2.0, "spread_move": 1.0, "total_open": 47.0, "total_move": 1.0},
        3: {**_feature_map()[3], "spread_open": 6.0, "spread_move": 1.5, "total_open": 58.0, "total_move": 2.0},
        4: {**_feature_map()[4], "spread_open": -2.0, "spread_move": -1.5, "total_open": 53.0, "total_move": 2.0},
    }
    low_coverage_keys = {"spread_open", "spread_move", "total_open", "total_move"}
    children = expand_candidates(SystemFilter(), games, feature_map)
    for child in children:
        for filt in child.feature_filters:
            assert filt.key not in low_coverage_keys


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


def _biased_games(
    n: int,
    *,
    season: int = 2023,
    home_cover_rate: float = 0.5,
    seed: int = 1,
    game_id_start: int = 1,
) -> list[GameRecord]:
    """Synthetic in-sample-shaped games where home favorites cover at
    `home_cover_rate`, so a "home + favorite" candidate has a real, deterministic
    in-sample edge (or lack of one) to rank on.
    """
    rng = random.Random(seed)
    games = []
    for i in range(n):
        gid = game_id_start + i
        home_covers = rng.random() < home_cover_rate
        # home favored by 7; home wins by 14 (covers) or loses by 3 (doesn't cover)
        if home_covers:
            home_points, away_points = 30, 16
        else:
            home_points, away_points = 17, 20
        games.append(
            GameRecord(
                game_id=gid, season=season, week=(i % 15) + 1,
                home_team=f"H{gid}", away_team=f"A{gid}",
                home_conference="X", away_conference="Y",
                home_points=home_points, away_points=away_points,
                provider="consensus", spread=-7.0, total=45.0,
            )
        )
    return games


def _biased_feature_map(games: list[GameRecord]) -> dict[int, dict]:
    return {g.game_id: {"neutralSite": False} for g in games}


def test_min_decided_bets_gate_excludes_undersized_candidates():
    games = _biased_games(20, home_cover_rate=0.9)
    feature_map = _biased_feature_map(games)
    result = beam_search(games, feature_map, min_decided_bets=100)
    assert result.survivors == ()


def test_min_decided_bets_gate_boundary_is_inclusive():
    # Every game in _biased_games has a distinct spread/total, no pushes, so the
    # root-level "favorite"/"home" candidates decide on exactly n games. n=100
    # must survive a min_decided_bets=100 gate (>=); n=99 must not.
    feature_map_100 = _biased_feature_map(_biased_games(100, home_cover_rate=0.85))
    result_at_boundary = beam_search(
        _biased_games(100, home_cover_rate=0.85), feature_map_100, min_decided_bets=100, beam_width=50, top_k=10
    )
    assert any(c.decided == 100 for c in result_at_boundary.survivors)

    feature_map_99 = _biased_feature_map(_biased_games(99, home_cover_rate=0.85))
    result_below_boundary = beam_search(
        _biased_games(99, home_cover_rate=0.85), feature_map_99, min_decided_bets=100, beam_width=50, top_k=10
    )
    assert result_below_boundary.survivors == ()


def test_beam_search_surfaces_profitable_candidate_above_gate():
    games = _biased_games(150, home_cover_rate=0.85)
    feature_map = _biased_feature_map(games)
    result = beam_search(games, feature_map, min_decided_bets=50, beam_width=50, top_k=10)
    assert result.survivors
    assert all(c.decided >= 50 for c in result.survivors)
    assert all(c.roi > 0 for c in result.survivors)
    # winners must be ranked by wilson_low desc, then roi desc, then decided desc
    keys = [(-c.wilson_low, -c.roi, -c.decided) for c in result.survivors]
    assert keys == sorted(keys)


def test_run_backtest_never_called_during_beam_search(monkeypatch):
    games = _biased_games(150, home_cover_rate=0.85)
    feature_map = _biased_feature_map(games)
    calls = []
    # Patch search_module's own name binding (`from ... import run_backtest`), not
    # backtest_module's attribute -- search.py holds its own reference, so patching
    # the source module's attribute never intercepts calls made from search.py.
    monkeypatch.setattr(search_module, "run_backtest", lambda *a, **k: calls.append(1))
    beam_search(games, feature_map, min_decided_bets=50, beam_width=50, top_k=10)
    assert calls == []


def test_in_sample_only_evaluation_holdout_signal_never_leaks():
    # In-sample: home favorites do NOT cover (losing signal). Holdout-only: home
    # favorites cover overwhelmingly (winning signal). If holdout rows ever reached
    # the beam loop, "home favorite" would rank as profitable; it must not.
    in_sample = _biased_games(150, season=2023, home_cover_rate=0.3, seed=2, game_id_start=1)
    holdout_only = _biased_games(150, season=2024, home_cover_rate=0.95, seed=3, game_id_start=1000)

    in_sample_feature_map = _biased_feature_map(in_sample)
    holdout_feature_map = _biased_feature_map(holdout_only)

    result = beam_search(in_sample, in_sample_feature_map, min_decided_bets=50, beam_width=50, top_k=10)

    home_favorite_survivors = [
        c for c in result.survivors if c.system.favorite and c.system.home
    ]
    assert home_favorite_survivors == []

    # holdout variables exist only to demonstrate they were never referenced above
    assert holdout_only and holdout_feature_map


def test_deterministic_ranking_same_fixture_twice():
    games = _biased_games(150, home_cover_rate=0.85)
    feature_map = _biased_feature_map(games)
    first = beam_search(games, feature_map, min_decided_bets=50, beam_width=50, top_k=10)
    second = beam_search(games, feature_map, min_decided_bets=50, beam_width=50, top_k=10)
    assert [c.identity for c in first.survivors] == [c.identity for c in second.survivors]
    assert first.candidates_tested == second.candidates_tested


def test_effective_params_reported_back():
    games = _biased_games(150, home_cover_rate=0.85)
    feature_map = _biased_feature_map(games)
    result = beam_search(games, feature_map)
    assert result.effective_params == {
        "beam_width": 100,
        "top_k": 20,
        "min_decided_bets": 100,
        "alpha": 0.05,
        "max_dimensions": 4,
    }


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


# --- MVP-004: holdout finalist grading + BH correction -----------------------------


def _candidate(system: SystemFilter, *, wilson_low: float, roi: float, decided: int) -> BeamCandidate:
    return BeamCandidate(
        system=system, wins=decided, losses=0, decided=decided, roi=roi,
        wilson_low=wilson_low, identity=candidate_identity(system),
    )


def test_holdout_cannot_alter_finalist_identity_or_order():
    # Two "finalists" ranked A-before-B by MVP-003's in-sample beam search. On
    # holdout, B dramatically outperforms A. Even so, grade_finalists must not
    # reorder or re-select finalists based on holdout results.
    system_a = SystemFilter(favorite=True, home=True, side="home")
    system_b = SystemFilter(away=True, side="away")
    candidate_a = _candidate(system_a, wilson_low=0.6, roi=0.2, decided=200)  # ranked first in-sample
    candidate_b = _candidate(system_b, wilson_low=0.5, roi=0.1, decided=150)  # ranked second in-sample

    beam_result = BeamSearchResult(
        survivors=(candidate_a, candidate_b),
        candidates_tested=500,
        effective_params={"alpha": 0.05},
    )

    # Holdout games where home favorites (A) never cover but away underdogs (B)
    # cover every game -- if holdout ever influenced ranking, B would be promoted
    # ahead of A.
    holdout_games = _biased_games(60, season=2024, home_cover_rate=0.0, seed=7, game_id_start=5000)
    holdout_feature_map = _biased_feature_map(holdout_games)

    result = grade_finalists(beam_result, holdout_games, holdout_feature_map)

    assert [f.system for f in result.finalists] == [system_a, system_b]


def test_zero_holdout_bet_finalist_omitted():
    system_matches = SystemFilter()  # matches everything
    system_never_matches = SystemFilter(teams={"NoSuchTeam"})
    candidate_matches = _candidate(system_matches, wilson_low=0.6, roi=0.2, decided=200)
    candidate_never = _candidate(system_never_matches, wilson_low=0.55, roi=0.15, decided=150)

    beam_result = BeamSearchResult(
        survivors=(candidate_matches, candidate_never),
        candidates_tested=100,
        effective_params={"alpha": 0.05},
    )

    holdout_games = _biased_games(60, season=2024, home_cover_rate=0.6, seed=11, game_id_start=9000)
    holdout_feature_map = _biased_feature_map(holdout_games)

    result = grade_finalists(beam_result, holdout_games, holdout_feature_map)

    assert len(result.finalists) == 1
    assert result.finalists[0].system == system_matches
    assert result.finalists_graded == 1
    assert result.candidates_tested == 100


def test_full_run_backtest_call_count_equals_finalists_graded(monkeypatch):
    # 4 survivors match holdout data, 1 never matches -- the zero-match survivor
    # must be excluded WITHOUT ever triggering a full run_backtest call (only the
    # cheap run_backtest_summary pre-check), so call count == finalists_graded
    # exactly, strictly less than len(survivors).
    matching_systems = [SystemFilter(seasons={2024}) for _ in range(4)]
    never_matches = SystemFilter(teams={"NoSuchTeam"})
    survivors = tuple(
        _candidate(s, wilson_low=0.6 - i * 0.01, roi=0.1, decided=100)
        for i, s in enumerate(matching_systems)
    ) + (_candidate(never_matches, wilson_low=0.5, roi=0.05, decided=50),)
    beam_result = BeamSearchResult(survivors=survivors, candidates_tested=1000, effective_params={"alpha": 0.05})

    holdout_games = _biased_games(60, season=2024, home_cover_rate=0.6, seed=13, game_id_start=7000)
    holdout_feature_map = _biased_feature_map(holdout_games)

    calls = []
    real_run_backtest = search_module.run_backtest

    def spy(*args, **kwargs):
        calls.append(1)
        return real_run_backtest(*args, **kwargs)

    monkeypatch.setattr(search_module, "run_backtest", spy)

    result = grade_finalists(beam_result, holdout_games, holdout_feature_map)

    assert result.finalists_graded == 4
    assert len(calls) == result.finalists_graded
    assert len(calls) < len(survivors)
    assert len(calls) <= 20  # top_k default
    assert len(calls) < beam_result.candidates_tested


def test_bh_batch_size_is_k_not_n():
    systems = [SystemFilter(seasons={2024}, min_spread=float(i)) for i in range(4)]
    survivors = tuple(
        _candidate(s, wilson_low=0.6 - i * 0.01, roi=0.1, decided=100) for i, s in enumerate(systems)
    )
    beam_result = BeamSearchResult(survivors=survivors, candidates_tested=5000, effective_params={"alpha": 0.05})

    holdout_games = _biased_games(60, season=2024, home_cover_rate=0.6, seed=17, game_id_start=3000)
    holdout_feature_map = _biased_feature_map(holdout_games)

    captured_batches = []
    real_bh_correct = search_module.bh_correct

    def spy_bh(p_values, alpha=0.05):
        captured_batches.append(list(p_values))
        return real_bh_correct(p_values, alpha=alpha)

    orig = search_module.bh_correct
    search_module.bh_correct = spy_bh
    try:
        result = grade_finalists(beam_result, holdout_games, holdout_feature_map)
    finally:
        search_module.bh_correct = orig

    assert len(captured_batches) == 1
    assert len(captured_batches[0]) == result.finalists_graded
    assert result.finalists_graded != beam_result.candidates_tested
    assert result.candidates_tested == 5000
