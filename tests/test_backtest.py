from dataclasses import replace

from cfb_system_maker.backtest import (
    _consistency_score,
    _overfit_score,
    _permutation_score,
    _roi_significance_score,
    _sample_size_score,
    compute_grade,
    compute_season_breakdown,
    compute_system_stats,
    count_overfit_filters,
    grade_bet,
    matches_system,
    run_backtest,
    sign_consistency,
    split_holdout,
)
from cfb_system_maker.models import BacktestResult, BetDetail, FeatureFilter, GameRecord, SeasonRecord, SystemFilter, SystemStats


def test_home_favorite_cover_wins_at_minus_110():
    games = [
        GameRecord(
            game_id=1,
            season=2023,
            week=1,
            home_team="Michigan",
            away_team="East Carolina",
            home_conference="Big Ten",
            away_conference="American",
            home_points=30,
            away_points=14,
            provider="consensus",
            spread=-14.5,
            total=52.5,
        )
    ]

    result = run_backtest(games, SystemFilter(side="home", favorite=True))

    assert result.bets == 1
    assert result.wins == 1
    assert result.losses == 0
    assert result.pushes == 0
    assert round(result.profit, 4) == 0.9091
    assert round(result.roi, 4) == 0.9091
    assert result.bet_details[0].margin == 1.5
    assert result.average_margin == 1.5


def test_away_underdog_push_counts_no_profit_or_loss():
    games = [
        GameRecord(
            game_id=2,
            season=2023,
            week=2,
            home_team="Texas",
            away_team="Wyoming",
            home_conference="SEC",
            away_conference="Mountain West",
            home_points=31,
            away_points=17,
            provider="consensus",
            spread=-14.0,
            total=45.0,
        )
    ]

    result = run_backtest(games, SystemFilter(side="away", underdog=True))

    assert result.bets == 1
    assert result.wins == 0
    assert result.losses == 0
    assert result.pushes == 1
    assert result.profit == 0
    assert result.roi == 0


def test_filters_limit_by_team_conference_week_and_spread_range():
    games = [
        GameRecord(1, 2023, 1, "A", "B", "ACC", "SEC", 28, 21, "consensus", -6.5, 49.5),
        GameRecord(2, 2023, 2, "C", "D", "Big Ten", "MAC", 17, 20, "consensus", -3.0, 39.0),
        GameRecord(3, 2022, 1, "A", "E", "ACC", "Sun Belt", 10, 21, "consensus", 2.5, 44.0),
    ]

    result = run_backtest(
        games,
        SystemFilter(
            side="home",
            seasons={2023},
            weeks={1},
            teams={"A"},
            conferences={"ACC"},
            min_spread=-7,
            max_spread=-1,
        ),
    )

    assert result.bets == 1
    assert result.bet_details[0].team == "A"


def test_over_under_bets_grade_against_total_points():
    games = [
        GameRecord(1, 2023, 1, "A", "B", "ACC", "SEC", 31, 24, "consensus", -6.5, 52.5),
        GameRecord(2, 2023, 1, "C", "D", "ACC", "SEC", 20, 17, "consensus", -3.0, 37.0),
    ]

    over = run_backtest(games, SystemFilter(bet_type="total", total_side="over"))
    under = run_backtest(games, SystemFilter(bet_type="total", total_side="under"))

    assert over.bets == 2
    assert over.wins == 1
    assert over.pushes == 1
    assert over.bet_details[0].team == "Over"
    assert over.bet_details[0].line == 52.5
    assert under.losses == 1
    assert under.pushes == 1


def test_average_margin_is_none_for_total_bet_systems():
    games = [
        GameRecord(1, 2023, 1, "A", "B", "ACC", "SEC", 31, 24, "consensus", -6.5, 52.5),
        GameRecord(2, 2023, 1, "C", "D", "ACC", "SEC", 20, 17, "consensus", -3.0, 37.0),
    ]

    over = run_backtest(games, SystemFilter(bet_type="total", total_side="over"))

    assert over.average_margin is None
    assert all(bet.margin == 0.0 for bet in over.bet_details)


def test_average_margin_averages_across_multiple_spread_bets():
    games = [
        GameRecord(1, 2023, 1, "A", "B", "ACC", "SEC", 30, 14, "consensus", -14.5, 52.5),
        GameRecord(2, 2023, 2, "C", "D", "ACC", "SEC", 20, 21, "consensus", -3.0, 45.0),
    ]

    result = run_backtest(games, SystemFilter(side="home"))

    assert result.bet_details[0].margin == 1.5
    assert result.bet_details[1].margin == -4.0
    assert result.average_margin == round((1.5 + -4.0) / 2, 4)


def test_feature_filter_excludes_games_with_null_feature():
    games = [
        GameRecord(1, 2023, 1, "A", "B", "ACC", "SEC", 28, 21, "consensus", -6.5, 49.5),
        GameRecord(2, 2023, 1, "C", "D", "ACC", "SEC", 24, 21, "consensus", -3.0, 45.0),
    ]
    feature_map = {1: {"weather_temperature": 55.0}, 2: {}}
    system = SystemFilter(
        side="home",
        feature_filters=(FeatureFilter("weather_temperature", "gte", 50.0),),
    )

    result = run_backtest(games, system, feature_map=feature_map)

    assert result.bets == 1
    assert result.bet_details[0].game_id == 1


def test_system_stats_include_edge_and_wilson_bounds():
    games = [
        GameRecord(1, 2023, 1, "A", "B", "ACC", "SEC", 28, 21, "consensus", -6.5, 49.5),
        GameRecord(2, 2023, 1, "C", "D", "ACC", "SEC", 24, 21, "consensus", -3.0, 45.0),
    ]
    result = run_backtest(games, SystemFilter(side="home"))

    assert result.stats is not None
    assert result.stats.break_even_rate == 0.5238
    assert result.stats.wilson_low <= result.hit_rate <= result.stats.wilson_high
    assert 0.0 <= result.stats.p_value <= 1.0
    assert result.stats.low_sample is True


def _bet(game_id, week, result):
    profit = 0.9091 if result == "win" else (-1.0 if result == "loss" else 0.0)
    return BetDetail(
        game_id=game_id,
        season=2023,
        week=week,
        team="Alpha",
        opponent="Beta",
        side="home",
        spread=-3.0,
        total=None,
        line=-3.0,
        result=result,
        profit=profit,
    )


def test_streaks_are_chronological_and_pushes_do_not_break_them():
    # Chronological order: W W P W L L — but pass details shuffled to prove sorting.
    details = [
        _bet(4, 4, "win"),
        _bet(1, 1, "win"),
        _bet(6, 6, "loss"),
        _bet(2, 2, "win"),
        _bet(5, 5, "loss"),
        _bet(3, 3, "push"),
    ]
    stats = compute_system_stats(details, hit_rate=0.6, roi=0.1, american_odds=-110, stake=1.0)
    assert stats.max_win_streak == 3
    assert stats.max_loss_streak == 2


def test_streaks_default_to_zero_with_no_bets():
    stats = compute_system_stats([], hit_rate=0.0, roi=0.0, american_odds=-110, stake=1.0)
    assert stats.max_win_streak == 0
    assert stats.max_loss_streak == 0


def test_season_breakdown_groups_bets_by_season_with_roi():
    season_2022_bet = BetDetail(
        game_id=3, season=2022, week=3, team="Alpha", opponent="Beta",
        side="home", spread=-3.0, total=None, line=-3.0, result="win", profit=0.9091,
    )
    details = [
        _bet(1, 1, "win"),
        _bet(2, 2, "loss"),
        season_2022_bet,
    ]

    records = compute_season_breakdown(details)

    assert [r.season for r in records] == [2022, 2023]
    season_2023 = next(r for r in records if r.season == 2023)
    assert season_2023.bets == 2
    assert season_2023.wins == 1
    assert season_2023.losses == 1
    expected_profit = round(0.9091 - 1.0, 4)
    assert season_2023.profit == expected_profit
    assert season_2023.roi == round(expected_profit / 2, 4)


def test_season_breakdown_computes_roi_per_season():
    details = [_bet(1, 1, "win"), _bet(2, 2, "win"), _bet(3, 3, "loss")]

    records = compute_season_breakdown(details, stake=1.0)

    assert len(records) == 1
    record = records[0]
    assert record.season == 2023
    assert record.bets == 3
    assert record.wins == 2
    assert record.losses == 1
    assert record.profit == round(0.9091 + 0.9091 - 1.0, 4)
    assert record.roi == round(record.profit / 3, 4)


def test_sign_consistency_counts_profitable_and_total_seasons():
    records = [
        SeasonRecord(season=2021, bets=10, wins=6, losses=4, pushes=0, profit=1.0, roi=0.1),
        SeasonRecord(season=2022, bets=10, wins=4, losses=6, pushes=0, profit=-1.0, roi=-0.1),
        SeasonRecord(season=2023, bets=10, wins=7, losses=3, pushes=0, profit=2.0, roi=0.2),
    ]

    profitable, total = sign_consistency(records)

    assert profitable == 2
    assert total == 3


def test_run_backtest_populates_season_breakdown():
    games = [
        GameRecord(1, 2022, 1, "A", "B", "ACC", "SEC", 28, 21, "consensus", -6.5, 49.5),
        GameRecord(2, 2023, 1, "A", "C", "ACC", "SEC", 30, 14, "consensus", -6.5, 49.5),
    ]

    result = run_backtest(games, SystemFilter(side="home", favorite=True))

    assert [r.season for r in result.season_breakdown] == [2022, 2023]
    assert all(r.bets == 1 for r in result.season_breakdown)


def _bets(win_count, loss_count):
    bets = []
    game_id = 1
    for _ in range(win_count):
        bets.append(_bet(game_id, game_id, "win"))
        game_id += 1
    for _ in range(loss_count):
        bets.append(_bet(game_id, game_id, "loss"))
        game_id += 1
    return bets


def test_permutation_test_flags_injected_edge_as_low_p_value():
    details = _bets(130, 70)  # 65% hit rate vs. 52.38% break-even at -110

    stats = compute_system_stats(details, hit_rate=0.65, roi=0.1815, american_odds=-110, stake=1.0)

    assert stats.permutation_p_value < 0.05


def test_permutation_test_flags_noise_dataset_as_high_p_value():
    details = _bets(262, 238)  # ~52.4% hit rate, essentially at break-even -> no edge

    stats = compute_system_stats(details, hit_rate=0.524, roi=0.0, american_odds=-110, stake=1.0)

    assert stats.permutation_p_value > 0.2


def test_permutation_test_excludes_pushes_from_resampling():
    edge = _bets(130, 70)
    with_pushes = edge + [_bet(9001, 9001, "push"), _bet(9002, 9002, "push")]

    stats_edge = compute_system_stats(edge, hit_rate=0.65, roi=0.1815, american_odds=-110, stake=1.0)
    stats_with_pushes = compute_system_stats(with_pushes, hit_rate=0.65, roi=0.1815, american_odds=-110, stake=1.0)

    assert stats_with_pushes.permutation_p_value == stats_edge.permutation_p_value


def test_permutation_test_is_reproducible_with_fixed_seed():
    details = _bets(130, 70)

    first = compute_system_stats(details, hit_rate=0.65, roi=0.1815, american_odds=-110, stake=1.0)
    second = compute_system_stats(details, hit_rate=0.65, roi=0.1815, american_odds=-110, stake=1.0)

    assert first.permutation_p_value == second.permutation_p_value


def test_permutation_test_defaults_to_no_signal_with_zero_decided_bets():
    stats = compute_system_stats([], hit_rate=0.0, roi=0.0, american_odds=-110, stake=1.0)

    assert stats.permutation_p_value == 1.0


def test_split_holdout_separates_in_sample_and_holdout_seasons():
    system = SystemFilter(side="home", seasons={2020, 2021, 2022, 2023})

    in_sample, holdout = split_holdout(system, {2023}, {2020, 2021, 2022, 2023})

    assert in_sample.seasons == {2020, 2021, 2022}
    assert holdout.seasons == {2023}


def test_split_holdout_uses_available_seasons_when_system_has_no_season_filter():
    system = SystemFilter(side="home")  # empty seasons = unrestricted

    in_sample, holdout = split_holdout(system, {2023}, {2020, 2021, 2022, 2023})

    assert in_sample.seasons == {2020, 2021, 2022}
    assert holdout.seasons == {2023}


def test_split_holdout_returns_sentinel_holdout_when_no_overlap_remains():
    system = SystemFilter(side="home", seasons={2023})

    in_sample, holdout = split_holdout(system, {2020}, {2020, 2021, 2022, 2023})

    # 2020 isn't in the system's own season set -> holdout side must match
    # nothing, not fall back to "no restriction" (empty set means unrestricted
    # in matches_system, so an empty result here must use the sentinel instead).
    assert holdout.seasons == {-1}
    assert in_sample.seasons == {2023}


def test_split_holdout_returns_sentinel_in_sample_when_holdout_covers_all_seasons():
    system = SystemFilter(side="home", seasons={2023})

    in_sample, holdout = split_holdout(system, {2023}, {2020, 2021, 2022, 2023})

    assert in_sample.seasons == {-1}
    assert holdout.seasons == {2023}


def test_fade_flips_spread_win_to_loss():
    game = GameRecord(
        game_id=1,
        season=2023,
        week=1,
        home_team="Michigan",
        away_team="East Carolina",
        home_conference="Big Ten",
        away_conference="American",
        home_points=30,
        away_points=14,
        provider="consensus",
        spread=-14.5,
        total=52.5,
    )

    bet = grade_bet(game, SystemFilter(side="home", favorite=True, fade=True))

    assert bet.result == "loss"
    assert bet.margin == -1.5


def test_fade_preserves_spread_push():
    game = GameRecord(
        game_id=2,
        season=2023,
        week=2,
        home_team="Texas",
        away_team="Wyoming",
        home_conference="SEC",
        away_conference="Mountain West",
        home_points=31,
        away_points=17,
        provider="consensus",
        spread=-14.0,
        total=45.0,
    )

    bet = grade_bet(game, SystemFilter(side="away", underdog=True, fade=True))

    assert bet.result == "push"


def test_fade_flips_total_bet_result():
    games = [
        GameRecord(1, 2023, 1, "A", "B", "ACC", "SEC", 31, 24, "consensus", -6.5, 52.5),
        GameRecord(2, 2023, 1, "C", "D", "ACC", "SEC", 20, 17, "consensus", -3.0, 37.0),
    ]

    result = run_backtest(games, SystemFilter(bet_type="total", total_side="over", fade=True))

    assert result.bet_details[0].result == "loss"
    assert result.bet_details[1].result == "push"


def test_fade_does_not_change_matched_bet_count():
    games = [
        GameRecord(
            game_id=1, season=2023, week=1, home_team="Michigan", away_team="East Carolina",
            home_conference="Big Ten", away_conference="American", home_points=30, away_points=14,
            provider="consensus", spread=-14.5, total=52.5,
        ),
        GameRecord(
            game_id=2, season=2023, week=2, home_team="Texas", away_team="Wyoming",
            home_conference="SEC", away_conference="Mountain West", home_points=31, away_points=17,
            provider="consensus", spread=-14.0, total=45.0,
        ),
        GameRecord(
            game_id=3, season=2023, week=3, home_team="Ohio State", away_team="Indiana",
            home_conference="Big Ten", away_conference="Big Ten", home_points=45, away_points=10,
            provider="consensus", spread=-20.5, total=55.5,
        ),
    ]
    system = SystemFilter(side="home", favorite=True)

    normal_result = run_backtest(games, system)
    faded_result = run_backtest(games, replace(system, fade=True))

    assert normal_result.bets == faded_result.bets
    assert any(
        normal.result != faded.result
        for normal, faded in zip(normal_result.bet_details, faded_result.bet_details)
    )


def test_grade_sample_size_score_boundaries():
    # bet-count floor overrides any margin, however favorable
    assert _sample_size_score(29, wilson_low=0.90, break_even_rate=0.524) == 0.0

    # break_even_rate=0.0 keeps margin == wilson_low exactly (no float rounding
    # from an intervening add), so boundary comparisons are exact.
    for decided in (30, 1000):
        assert _sample_size_score(decided, wilson_low=-0.001, break_even_rate=0.0) == 0.0
        assert _sample_size_score(decided, wilson_low=0.0, break_even_rate=0.0) == 0.3
        assert _sample_size_score(decided, wilson_low=0.02, break_even_rate=0.0) == 0.6
        assert _sample_size_score(decided, wilson_low=0.05, break_even_rate=0.0) == 0.8
        assert _sample_size_score(decided, wilson_low=0.10, break_even_rate=0.0) == 1.0


def test_grade_roi_significance_score_boundaries():
    assert _roi_significance_score(-0.001) == 0.0
    assert _roi_significance_score(0.0) == 0.2
    assert _roi_significance_score(0.999) == 0.2
    assert _roi_significance_score(1.0) == 0.5
    assert _roi_significance_score(1.644) == 0.5
    assert _roi_significance_score(1.645) == 0.75
    assert _roi_significance_score(1.959) == 0.75
    assert _roi_significance_score(1.96) == 1.0


def test_grade_consistency_score_boundaries():
    assert _consistency_score(0, 0) == 0.0
    assert _consistency_score(2, 4) == 0.5
    assert _consistency_score(4, 4) == 1.0


def test_grade_permutation_score_boundaries():
    assert _permutation_score(0.0) == 1.0
    assert _permutation_score(0.0099) == 1.0
    assert _permutation_score(0.01) == 0.8
    assert _permutation_score(0.0499) == 0.8
    assert _permutation_score(0.05) == 0.5
    assert _permutation_score(0.0999) == 0.5
    assert _permutation_score(0.10) == 0.25
    assert _permutation_score(0.1999) == 0.25
    assert _permutation_score(0.20) == 0.0


def test_grade_overfit_score_boundaries():
    assert _overfit_score(3) == 1.0
    assert _overfit_score(7) == 0.75
    assert _overfit_score(14) == 0.5
    assert _overfit_score(24) == 0.25
    assert _overfit_score(25) == 0.0


def test_count_overfit_filters_follows_d06_counting_rule():
    system = SystemFilter(
        favorite=True,
        min_spread=3.0,
        providers={"consensus"},
        teams={"A", "B", "C"},
        feature_filters=(FeatureFilter(key="x", op="in", value=[1, 2, 3, 4]),),
    )

    assert count_overfit_filters(system) == 10  # 1 + 1 + 1 + 3 + 4

    # fade must never be counted as an overfit-relevant filter (D-06)
    assert count_overfit_filters(replace(system, fade=True)) == 10


def _grade_stats(**overrides):
    defaults = dict(
        break_even_rate=0.524,
        edge=0.0,
        wilson_low=0.0,
        wilson_high=0.0,
        z_score=0.0,
        p_value=1.0,
        roi_std_error=0.0,
        roi_t_stat=0.0,
        low_sample=True,
        permutation_p_value=1.0,
    )
    defaults.update(overrides)
    return SystemStats(**defaults)


def _grade_result(*, bets, wins, losses, stats, season_breakdown=()):
    return BacktestResult(
        bets=bets,
        wins=wins,
        losses=losses,
        pushes=0,
        hit_rate=(wins / (wins + losses)) if (wins + losses) else 0.0,
        profit=0.0,
        roi=0.0,
        average_line=None,
        average_stake=1.0,
        bet_details=[],
        stats=stats,
        season_breakdown=season_breakdown,
    )


def test_compute_grade_returns_none_for_zero_matched_bets():
    result = _grade_result(bets=0, wins=0, losses=0, stats=_grade_stats())

    assert compute_grade(result, SystemFilter(side="home")) is None


def test_compute_grade_returns_a_for_all_high_subscores():
    stats = _grade_stats(wilson_low=0.7, z_score=3.0, permutation_p_value=0.001, low_sample=False)
    season_breakdown = (
        SeasonRecord(season=2021, bets=10, wins=8, losses=2, pushes=0, profit=1.0, roi=0.1),
        SeasonRecord(season=2022, bets=10, wins=8, losses=2, pushes=0, profit=1.0, roi=0.1),
    )
    result = _grade_result(bets=40, wins=32, losses=8, stats=stats, season_breakdown=season_breakdown)
    system = SystemFilter(side="home", favorite=True)  # 1 active filter value -> overfit_score 1.0

    assert compute_grade(result, system) == "A"


def test_compute_grade_returns_f_for_all_low_subscores():
    stats = _grade_stats(wilson_low=0.1, z_score=-3.0, permutation_p_value=0.9)
    result = _grade_result(bets=10, wins=3, losses=7, stats=stats, season_breakdown=())
    system = SystemFilter(
        side="home",
        teams={f"Team{i}" for i in range(25)},  # 25 active filter values -> overfit_score 0.0
    )

    assert compute_grade(result, system) == "F"


def test_run_backtest_populates_grade_field():
    games = [
        GameRecord(1, 2022, 1, "A", "B", "ACC", "SEC", 28, 21, "consensus", -6.5, 49.5),
        GameRecord(2, 2023, 1, "A", "C", "ACC", "SEC", 30, 14, "consensus", -6.5, 49.5),
    ]

    result = run_backtest(games, SystemFilter(side="home", favorite=True))

    assert result.grade is not None
    assert len(result.grade) == 1
    assert [r.season for r in result.season_breakdown] == [2022, 2023]
    assert all(r.bets == 1 for r in result.season_breakdown)


# --- Unplayed-game matching (D-18) -------------------------------------------
# Current Matches must evaluate games with no result yet. No placeholder scores
# are used anywhere below: an unplayed game carries null points, full stop.


def _unplayed_game(*, spread=-7.0, total=52.5, game_id=9100):
    return GameRecord(
        game_id=game_id,
        season=2026,
        week=3,
        home_team="Georgia",
        away_team="Clemson",
        home_conference="SEC",
        away_conference="ACC",
        home_points=None,
        away_points=None,
        provider="consensus",
        spread=spread,
        total=total,
    )


def test_unplayed_game_is_rejected_by_default_and_matched_when_played_not_required():
    game = _unplayed_game()
    system = SystemFilter(side="home", favorite=True)

    assert matches_system(game, system) is False
    assert matches_system(game, system, require_played=False) is True


def test_require_played_false_still_applies_every_other_filter():
    game = _unplayed_game()  # home is a 7-point favorite

    # underdog on the home side contradicts a -7.0 home spread
    assert matches_system(game, SystemFilter(side="home", underdog=True), require_played=False) is False
    # season / week / team filters are likewise untouched by the flag
    assert matches_system(game, SystemFilter(side="home", seasons={2025}), require_played=False) is False
    assert matches_system(game, SystemFilter(side="home", weeks={9}), require_played=False) is False
    assert matches_system(game, SystemFilter(side="home", teams={"Alabama"}), require_played=False) is False


def test_require_played_false_does_not_relax_the_missing_spread_guard():
    game = _unplayed_game(spread=None)

    assert matches_system(game, SystemFilter(side="home"), require_played=False) is False


def test_require_played_false_still_evaluates_feature_filters_and_fails_closed_on_null():
    game = _unplayed_game()
    system = SystemFilter(
        side="home",
        feature_filters=(FeatureFilter("weather_temperature", "gte", 50.0),),
    )

    passing_map = {game.game_id: {"weather_temperature": 55.0}}
    failing_map = {game.game_id: {"weather_temperature": 30.0}}
    null_map = {game.game_id: {"weather_temperature": None}}

    assert matches_system(game, system, passing_map, require_played=False) is True
    assert matches_system(game, system, failing_map, require_played=False) is False
    assert matches_system(game, system, null_map, require_played=False) is False
    assert matches_system(game, system, {}, require_played=False) is False


# --- Per-season derivation from an all-time result (D-11) ---------------------
# The dashboard's timeframe tabs read per-season figures off ONE all-time
# run_backtest rather than re-running (and re-permuting) per season. That is
# only sound if the derived bet set is identical to a season-restricted run.

_SEASON_SPECS = {
    2021: [(1, 28, 21, -6.5), (2, 17, 20, -3.0), (3, 30, 14, -14.5), (4, 24, 21, -3.0), (5, 35, 10, -20.5)],
    2022: [(1, 21, 24, -2.5), (2, 42, 7, -10.0), (3, 14, 13, -7.5), (4, 27, 20, -7.0), (5, 31, 28, -1.5)],
    2023: [(1, 20, 17, -9.5), (2, 38, 21, -13.0), (3, 10, 24, -4.5), (4, 45, 24, -21.0), (5, 26, 23, -3.0)],
}


def _multi_season_games():
    games = []
    for season, specs in _SEASON_SPECS.items():
        for week, home_points, away_points, spread in specs:
            games.append(
                GameRecord(
                    game_id=season * 100 + week,
                    season=season,
                    week=week,
                    home_team=f"Home{week}",
                    away_team=f"Away{week}",
                    home_conference="ACC",
                    away_conference="SEC",
                    home_points=home_points,
                    away_points=away_points,
                    provider="consensus",
                    spread=spread,
                    total=49.5,
                )
            )
    return games


def test_season_slice_of_all_time_backtest_equals_season_restricted_backtest():
    games = _multi_season_games()
    system = SystemFilter(side="home")
    all_time = run_backtest(games, system)

    assert all_time.bets == len(games)

    for season in _SEASON_SPECS:
        restricted = run_backtest(games, replace(system, seasons={season}))
        derived = [bet for bet in all_time.bet_details if bet.season == season]

        assert len(derived) >= 3  # each season carries a meaningful sample
        assert sorted((bet.game_id, bet.profit) for bet in derived) == sorted(
            (bet.game_id, bet.profit) for bet in restricted.bet_details
        )

        season_record = next(r for r in all_time.season_breakdown if r.season == season)
        assert season_record.bets == restricted.bets
        assert season_record.wins == restricted.wins
        assert season_record.losses == restricted.losses
        assert season_record.pushes == restricted.pushes
        assert season_record.profit == restricted.profit
        assert season_record.roi == restricted.roi
