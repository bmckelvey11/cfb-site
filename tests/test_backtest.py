from dataclasses import replace

from cfb_system_maker.backtest import (
    _analytic_p_value,
    _consistency_score,
    _icc_one_way,
    _mde,
    _overfit_score,
    _permutation_score,
    _roi_significance_score,
    _sample_size_score,
    bh_correct,
    cluster_dependence_stats,
    compute_grade,
    compute_season_breakdown,
    compute_system_stats,
    count_overfit_filters,
    grade_bet,
    matches_system,
    run_backtest,
    sign_consistency,
    split_holdout,
    stats_verdict,
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
    assert result.bet_details[0].team_points == 30
    assert result.bet_details[0].opponent_points == 14


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


def test_total_system_team_and_conference_filters_match_either_side():
    games = [
        GameRecord(1, 2023, 1, "A", "B", "ACC", "SEC", 28, 21, "consensus", -6.5, 49.5),
        GameRecord(2, 2023, 2, "C", "D", "Big Ten", "MAC", 17, 20, "consensus", -3.0, 39.0),
    ]

    # Team B is the AWAY team of game 1; a total system must match regardless of
    # the vestigial spread-side field.
    for side in ("home", "away"):
        system = SystemFilter(bet_type="total", side=side, teams={"B"})
        assert matches_system(games[0], system) is True
        assert matches_system(games[1], system) is False

        conf = SystemFilter(bet_type="total", side=side, conferences={"SEC"})
        assert matches_system(games[0], conf) is True
        assert matches_system(games[1], conf) is False

    # Spread systems keep bet-side-only semantics: side=home never matches the
    # away team.
    assert matches_system(games[0], SystemFilter(side="home", teams={"B"})) is False
    assert matches_system(games[0], SystemFilter(side="away", teams={"B"})) is True


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
    assert over.bet_details[0].team_points == 55
    assert over.bet_details[0].opponent_points is None
    assert over.bet_details[1].team_points == 37
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


def test_analytic_p_value_agrees_with_system_stats_p_value_for_same_counts():
    # 130 wins / 200 decided = exactly 0.65 -- avoids rounding ambiguity in the oracle.
    details = _bets(130, 70)
    stats = compute_system_stats(details, hit_rate=0.65, roi=0.1815, american_odds=-110, stake=1.0)

    direct = _analytic_p_value(wins=130, decided=200, break_even_rate=stats.break_even_rate)

    assert direct == stats.p_value


def test_analytic_p_value_returns_one_when_no_decided_bets():
    assert _analytic_p_value(wins=0, decided=0, break_even_rate=0.5238) == 1.0


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


def test_count_overfit_filters_excludes_home_away_flags():
    # home/away only ever narrow matches_system when paired with the matching
    # `side`, which already implies the same restriction on its own -- the
    # flag adds no selection information and must not depress the grade.
    base = SystemFilter(favorite=True)
    assert count_overfit_filters(base) == 1
    assert count_overfit_filters(replace(base, home=True, side="home")) == 1
    assert count_overfit_filters(replace(base, away=True, side="away")) == 1


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


# --- Benjamini-Hochberg correction (MVP-001) ----------------------------------
# bh_correct is a standalone stats primitive with NO call site in compute_grade
# or any letter-grade path -- it exists only for MVP-004's holdout finalist
# batch correction, not for per-system grading.


def test_bh_correct_known_value_vector():
    # Hand-verified oracle: p=[0.001, 0.01, 0.5, 0.8], K=4, alpha=0.05
    # rank 1: 0.001 * 4/1 = 0.004
    # rank 2: 0.01  * 4/2 = 0.02
    # rank 3: 0.5   * 4/3 = 0.6667 -> rounds to 0.667
    # rank 4: 0.8   * 4/4 = 0.8
    # reverse-cummin leaves all four unchanged here (already increasing)
    p_values = [0.001, 0.01, 0.5, 0.8]

    results = bh_correct(p_values, alpha=0.05)

    corrected = [round(r["corrected_p"], 4) for r in results]
    assert corrected == [0.004, 0.02, 0.6667, 0.8]
    assert [r["bh_significant"] for r in results] == [True, True, False, False]
    assert [r["raw_p"] for r in results] == p_values


def test_bh_correct_maps_back_to_original_input_order_when_shuffled():
    # Same oracle vector as above, shuffled -- proves restoration to ORIGINAL
    # identity/order, not sorted order.
    shuffled = [0.8, 0.001, 0.5, 0.01]  # indices: 0=0.8, 1=0.001, 2=0.5, 3=0.01

    results = bh_correct(shuffled, alpha=0.05)

    assert [r["raw_p"] for r in results] == shuffled
    corrected = [round(r["corrected_p"], 4) for r in results]
    assert corrected == [0.8, 0.004, 0.6667, 0.02]
    assert [r["bh_significant"] for r in results] == [False, True, False, True]


def test_bh_correct_requires_reverse_cummin_not_just_per_rank_scaling():
    # p=[0.04, 0.05], K=2: rank1 candidate = 0.04*2/1 = 0.08, rank2 candidate
    # = 0.05*2/2 = 0.05. Without the reverse-cummin step, rank1's corrected_p
    # (0.08) would exceed rank2's (0.05) -- violating monotonicity. A naive
    # per-rank-scaling-only implementation (no running min) passes the other
    # monotonicity test below by coincidence but fails this one.
    results = bh_correct([0.04, 0.05], alpha=0.05)

    corrected = [round(r["corrected_p"], 4) for r in results]
    assert corrected == [0.05, 0.05]


def test_bh_correct_adjusted_p_values_are_monotonic_after_restoration_when_sorted_by_raw_p():
    # Standard BH step-up property: once results are re-sorted by raw_p
    # ascending, corrected_p must be non-decreasing.
    raw = [0.2, 0.001, 0.05, 0.9, 0.01, 0.5]

    results = bh_correct(raw, alpha=0.05)

    by_raw_p = sorted(results, key=lambda r: r["raw_p"])
    corrected_in_rank_order = [r["corrected_p"] for r in by_raw_p]
    assert corrected_in_rank_order == sorted(corrected_in_rank_order)


def test_bh_correct_ties_receive_identical_corrected_p_and_significance():
    # Three tied p-values at the same raw_p must get the identical corrected_p
    # (and therefore identical bh_significant) under standard BH tie handling.
    p_values = [0.3, 0.01, 0.01, 0.01, 0.9]

    results = bh_correct(p_values, alpha=0.05)

    tied_corrected = {round(results[i]["corrected_p"], 6) for i in (1, 2, 3)}
    assert len(tied_corrected) == 1
    tied_significant = {results[i]["bh_significant"] for i in (1, 2, 3)}
    assert len(tied_significant) == 1


def test_bh_correct_empty_input_returns_empty_list():
    assert bh_correct([], alpha=0.05) == []


def test_bh_correct_corrected_p_never_exceeds_one():
    results = bh_correct([0.9, 0.95, 0.99, 1.0], alpha=0.05)

    assert all(r["corrected_p"] <= 1.0 for r in results)


def test_bh_correct_is_not_called_from_compute_grade_or_grading_source():
    # Guards acceptance criterion 6 structurally: bh_correct must have no call
    # site anywhere in backtest.py's grading path. This is a source-text check
    # (import-based introspection can't distinguish "referenced" from "called
    # by compute_grade" reliably), so it directly inspects the module source.
    import inspect

    from cfb_system_maker import backtest as backtest_module

    grade_source = inspect.getsource(backtest_module.compute_grade)
    assert "bh_correct" not in grade_source

    for score_fn_name in (
        "_sample_size_score",
        "_roi_significance_score",
        "_consistency_score",
        "_permutation_score",
        "_overfit_score",
    ):
        fn_source = inspect.getsource(getattr(backtest_module, score_fn_name))
        assert "bh_correct" not in fn_source


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


# --- stats_verdict / cluster_dependence_stats / MDE ------------------------------
#
# _icc_one_way expected values below are hand-derived from the standard one-way
# random-effects ANOVA decomposition (Searle et al.), independent of the
# implementation: SSB/SSW from group means vs. grand mean, m0 the unequal-size
# harmonic correction (n - sum(n_i^2)/n) / (g-1), ICC = (MSB-MSW)/(MSB+(m0-1)*MSW).


def test_icc_one_way_recovers_high_correlation_for_well_separated_clusters():
    # Two clusters, far apart, tight within each -- textbook high-ICC case.
    # Hand-computed: SSB=81, SSW=4, MSB=81, MSW=2, m0=2 -> ICC = (81-2)/(81+(2-1)*2) = 79/83.
    icc = _icc_one_way([[1.0, 3.0], [10.0, 12.0]])

    assert icc == 79 / 83


def test_icc_one_way_is_zero_for_identical_cluster_means():
    # No between-cluster separation at all -- ICC should be exactly 0, not
    # negative-then-clamped (this case has genuinely zero, not negative, MSB).
    icc = _icc_one_way([[1.0, 3.0], [1.0, 3.0], [1.0, 3.0]])

    assert icc == 0.0


def test_icc_one_way_clamps_negative_raw_icc_to_zero():
    # Within-cluster variance exceeding between-cluster variance produces a
    # negative raw ICC (a valid, common result -- see backtest.py's docstring),
    # which must clamp to 0.0, not surface as a negative number.
    icc = _icc_one_way([[0.0, 100.0], [1.0, 99.0], [2.0, 98.0]])

    assert icc == 0.0


def test_icc_one_way_returns_zero_for_fewer_than_two_clusters():
    assert _icc_one_way([[1.0, 2.0, 3.0]]) == 0.0


def test_cluster_dependence_stats_empty_details_returns_none_fields():
    stats = cluster_dependence_stats([], stake=1.0)

    assert stats == {
        "cluster_count": 0,
        "cluster_low": None,
        "cluster_high": None,
        "effective_n": None,
        "icc": None,
    }


def test_cluster_dependence_stats_single_cluster_skips_bootstrap_but_reports_icc():
    # Only one (season, week) group present -- block bootstrap needs >=2
    # clusters to resample across, so CI stays None, but ICC/effective_n
    # (both computable from a single group's residual spread) still report.
    details = [
        BetDetail(1, 2023, 1, "A", "B", "home", -3.0, 45.0, -110, "win", 0.91),
        BetDetail(2, 2023, 1, "C", "D", "home", -3.0, 45.0, -110, "loss", -1.0),
    ]

    stats = cluster_dependence_stats(details, stake=1.0)

    assert stats["cluster_count"] == 1
    assert stats["cluster_low"] is None
    assert stats["cluster_high"] is None
    assert stats["icc"] == 0.0  # single group -> _icc_one_way's g<2 guard


def test_cluster_dependence_stats_effective_n_shrinks_with_strong_clustering():
    # Two clusters with a large, consistent within-cluster profit gap (cluster
    # A always wins, cluster B always loses) -- strong dependence, high ICC,
    # effective_n should shrink well below the raw decided-bet count of 8.
    def _bet(game_id, season, week, result, profit):
        return BetDetail(game_id, season, week, "A", "B", "home", -3.0, 45.0, -110, result, profit)

    details = [
        _bet(1, 2023, 1, "win", 0.91), _bet(2, 2023, 1, "win", 0.91),
        _bet(3, 2023, 1, "win", 0.91), _bet(4, 2023, 1, "win", 0.91),
        _bet(5, 2023, 2, "loss", -1.0), _bet(6, 2023, 2, "loss", -1.0),
        _bet(7, 2023, 2, "loss", -1.0), _bet(8, 2023, 2, "loss", -1.0),
    ]

    stats = cluster_dependence_stats(details, stake=1.0)

    assert stats["cluster_count"] == 2
    assert stats["icc"] > 0.9  # near-perfect within-cluster homogeneity
    assert stats["effective_n"] < 8
    assert stats["effective_n"] == round(8 / (1 + (4 - 1) * stats["icc"]), 2)


def test_mde_matches_reparametrized_toolkit_formula():
    # toolkit/power.py's canonical mde() is z*sd*sqrt(d_eff/n) for a generic
    # paired-difference sd. backtest._mde specializes to a hit-rate MDE using
    # the null-hypothesis binomial sd = sqrt(p*(1-p)); the two must agree
    # exactly once reparametrized this way.
    from scipy.stats import norm

    n, p, deff = 150, 0.5238, 2.5
    sd = (p * (1 - p)) ** 0.5
    z = norm.ppf(1 - 0.05 / 2) + norm.ppf(0.80)
    expected = round(z * sd * (deff / n) ** 0.5, 4)

    assert _mde(n, p, deff=deff) == expected


def test_mde_returns_none_for_zero_decided_bets():
    assert _mde(0, 0.5238) is None


def _real_stats(win_count, loss_count):
    """Build SystemStats the way run_backtest does -- from actual BetDetail rows.

    The verdict tests below MUST go through this rather than hand-picking
    SystemStats fields. p_value/permutation_p_value are one-sided upper-tail
    while wilson_low/wilson_high are two-sided, so hand-chosen combinations can
    describe states the estimators never jointly produce. An earlier version of
    these tests did exactly that and passed while the verdict asserted
    "break-even sits outside the Wilson interval" in a case where it did not.
    """
    details = _bets(win_count, loss_count)
    decided = win_count + loss_count
    # Derived exactly as run_backtest derives them, so every field agrees.
    hit_rate = round(win_count / decided, 4)
    roi = round(sum(bet.profit for bet in details) / (len(details) * 1.0), 4)
    return compute_system_stats(
        details, american_odds=-110, stake=1.0, hit_rate=hit_rate, roi=roi
    )


def test_stats_verdict_zero_decided_bets():
    assert stats_verdict(_grade_stats(), 0) == "No decided bets yet."


def test_stats_verdict_low_sample_short_circuits_before_significance_check():
    stats = _real_stats(win_count=2, loss_count=0)

    verdict = stats_verdict(stats, decided=2)

    assert stats.low_sample
    assert "too few to say anything about edge" in verdict
    assert "clears" not in verdict  # never reaches the significance branches


def test_stats_verdict_significant_positive_edge_reads_as_real_signal():
    # 70% hit rate over 100 bets clears both one-sided tests decisively.
    stats = _real_stats(win_count=70, loss_count=30)

    verdict = stats_verdict(stats, decided=100, overfit_filters=1)

    assert stats.p_value < 0.05 and stats.permutation_p_value < 0.05
    assert "clears both the normal-theory" in verdict
    assert "hypothesis-generating" not in verdict  # overfit_filters <= 7, no caveat


def test_stats_verdict_wilson_claim_matches_the_actual_interval():
    """The verdict may only claim break-even is outside Wilson when it is.

    Regression test for the one-sided-vs-two-sided mismatch: the significance
    tests can fire while the two-sided Wilson interval still spans break-even,
    so the claim has to be checked rather than inferred from significance.
    """
    for win_count, loss_count in [(70, 30), (21, 9), (60, 40), (120, 80)]:
        stats = _real_stats(win_count, loss_count)
        if not (stats.p_value < 0.05 and stats.permutation_p_value < 0.05):
            continue
        verdict = stats_verdict(stats, decided=win_count + loss_count, overfit_filters=1)
        break_even_inside = stats.wilson_low <= stats.break_even_rate <= stats.wilson_high
        if break_even_inside:
            assert "Break-even sits outside the Wilson interval" not in verdict
            assert "the two views disagree" in verdict
        else:
            assert "Break-even sits outside the Wilson interval too" in verdict


def test_stats_verdict_significant_positive_edge_with_many_overfit_filters_caveats():
    stats = _real_stats(win_count=70, loss_count=30)

    verdict = stats_verdict(stats, decided=100, overfit_filters=8)

    assert "hypothesis-generating, not confirmed" in verdict
    assert "8 active narrowing constraints" in verdict


def test_stats_verdict_non_significant_edge_reads_as_noise():
    # 53% over 100 bets is above break-even but nowhere near significant.
    stats = _real_stats(win_count=53, loss_count=47)

    verdict = stats_verdict(stats, decided=100)

    assert stats.edge > 0
    assert stats.p_value >= 0.05
    assert "not statistically distinguishable from break-even" in verdict


def test_stats_verdict_negative_edge_says_tests_cannot_confirm_a_loss():
    """A losing system can never be 'significant' -- the tests are one-sided.

    The verdict must say so plainly instead of implying the absence of a signal
    means the same thing it does for a break-even system.
    """
    stats = _real_stats(win_count=40, loss_count=60)

    verdict = stats_verdict(stats, decided=100)

    assert stats.edge < 0
    assert stats.p_value >= 0.05  # one-sided: a loss can never clear it
    assert "is negative — this system lost money" in verdict
    assert "cannot confirm a losing one" in verdict


def test_stats_verdict_never_calls_a_non_negative_edge_negative():
    """Guards the branch order: only a genuinely negative edge gets the loss copy."""
    for win_count, loss_count in [(53, 47), (70, 30), (5238, 4762)]:
        stats = _real_stats(win_count, loss_count)
        verdict = stats_verdict(stats, decided=win_count + loss_count)
        if stats.edge >= 0:
            assert "is negative" not in verdict


def test_stats_verdict_includes_mde_note_only_on_non_significant_branch():
    stats = _real_stats(win_count=53, loss_count=47)

    verdict = stats_verdict(stats, decided=100)

    assert stats.mde is not None
    assert "could only reliably detect an edge of" in verdict
    assert f"{stats.mde * 100:.2f} points" in verdict


def test_stats_verdict_includes_cluster_note_with_few_clusters_caveat():
    # _bets puts every bet in its own week, so 30 bets -> 30 clusters (<40).
    stats = _real_stats(win_count=21, loss_count=9)

    verdict = stats_verdict(stats, decided=30, overfit_filters=1)

    assert stats.cluster_count == 30
    assert "only 30 season/week groups (<40)" in verdict
    assert "anti-conservative" in verdict


def test_stats_verdict_includes_cluster_note_when_enough_clusters():
    stats = _real_stats(win_count=70, loss_count=30)

    verdict = stats_verdict(stats, decided=100, overfit_filters=1)

    assert stats.cluster_count == 100
    assert f"Accounting for 100 season/week clusters (ICC={stats.icc:.3f})" in verdict
    assert f"[{stats.cluster_low * 100:+.2f}%, {stats.cluster_high * 100:+.2f}%]" in verdict
    # The old copy claimed the interval "widens to" a baseline the UI never shows.
    assert "widens to" not in verdict


def _exclusion_game(**overrides):
    base = dict(
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
    base.update(overrides)
    return GameRecord(**base)


def test_exclude_teams_drops_the_named_bet_side_team():
    game = _exclusion_game()
    assert matches_system(game, SystemFilter(side="home"))
    assert not matches_system(game, SystemFilter(side="home", exclude_teams={"Michigan"}))
    # Excluding the other side's team leaves a home bet untouched.
    assert matches_system(game, SystemFilter(side="home", exclude_teams={"East Carolina"}))


def test_exclude_teams_on_total_drops_games_involving_the_team():
    game = _exclusion_game()
    system = SystemFilter(bet_type="total", total_side="over")
    assert matches_system(game, system)
    # A total has no bet side, so either team appearing disqualifies the game.
    assert not matches_system(game, replace(system, exclude_teams={"Michigan"}))
    assert not matches_system(game, replace(system, exclude_teams={"East Carolina"}))


def test_exclude_conferences_drops_the_named_bet_side_conference():
    game = _exclusion_game()
    assert not matches_system(game, SystemFilter(side="home", exclude_conferences={"Big Ten"}))
    assert matches_system(game, SystemFilter(side="home", exclude_conferences={"American"}))


def test_exclude_conferences_on_total_drops_games_involving_the_conference():
    game = _exclusion_game()
    system = SystemFilter(bet_type="total", total_side="over")
    assert not matches_system(game, replace(system, exclude_conferences={"Big Ten"}))
    assert not matches_system(game, replace(system, exclude_conferences={"American"}))


def test_exclude_conference_fails_closed_on_unknown_conference():
    # A null conference is "unknown", not "not Big Ten". Excluding Big Ten must
    # not silently sweep in every FCS opponent with no conference recorded.
    game = _exclusion_game(home_conference=None)
    assert not matches_system(game, SystemFilter(side="home", exclude_conferences={"Big Ten"}))


def test_exclude_seasons_weeks_providers():
    game = _exclusion_game()
    assert not matches_system(game, SystemFilter(side="home", exclude_seasons={2023}))
    assert matches_system(game, SystemFilter(side="home", exclude_seasons={2024}))
    assert not matches_system(game, SystemFilter(side="home", exclude_weeks={1}))
    assert matches_system(game, SystemFilter(side="home", exclude_weeks={2}))
    assert not matches_system(game, SystemFilter(side="home", exclude_providers={"consensus"}))
    assert matches_system(game, SystemFilter(side="home", exclude_providers={"other"}))


def test_include_and_exclude_are_disjoint():
    games = [
        _exclusion_game(game_id=1, home_conference="Big Ten"),
        _exclusion_game(game_id=2, home_conference="SEC"),
    ]
    included = run_backtest(games, SystemFilter(side="home", conferences={"Big Ten"}))
    excluded = run_backtest(games, SystemFilter(side="home", exclude_conferences={"Big Ten"}))
    assert included.bets == 1
    assert excluded.bets == 1
    assert included.bets + excluded.bets == len(games)
    included_ids = {d.game_id for d in included.bet_details}
    excluded_ids = {d.game_id for d in excluded.bet_details}
    assert included_ids.isdisjoint(excluded_ids)


def test_existing_system_unchanged_when_exclusions_default_empty():
    # Regression guard: a system saved before exclusions existed must backtest
    # identically once the new fields are present and defaulted.
    games = [
        _exclusion_game(game_id=1),
        _exclusion_game(game_id=2, home_conference="SEC", home_points=10, away_points=40),
    ]
    system = SystemFilter(side="home", favorite=True)
    result = run_backtest(games, system)
    assert result.bets == 2
    assert result.wins == 1
    assert result.losses == 1

def test_week_filter_alone_cannot_separate_bowls_from_openers():
    """Postseason week numbering restarts at 1, so week 1 holds both.

    In the real table 531 bowl and playoff games sit at week 1 alongside 1,132
    season openers. A weeks={1} system therefore matches both unless the system
    also says which season type it wants.
    """
    games = [
        GameRecord(1, 2023, 1, "A", "B", "ACC", "SEC", 28, 21, "consensus", -6.5, 49.5),
        GameRecord(2, 2023, 1, "C", "D", "ACC", "SEC", 31, 10, "consensus", -6.5, 49.5,
                   season_type="postseason"),
    ]

    both = run_backtest(games, SystemFilter(weeks={1}))
    assert both.bets == 2  # the collision is real

    openers = run_backtest(games, SystemFilter(weeks={1}, season_types={"regular"}))
    assert openers.bets == 1
    assert openers.bet_details[0].game_id == 1

    no_bowls = run_backtest(games, SystemFilter(weeks={1}, exclude_season_types={"postseason"}))
    assert no_bowls.bets == 1


def test_bowls_and_openers_are_not_one_cluster():
    """A January bowl and an August opener share a week number, not a shock.

    Clustering on (season, week) alone would pool them and understate the
    dependence correction; season_type is part of the key so it cannot.
    """
    games = [
        GameRecord(1, 2023, 1, "A", "B", "ACC", "SEC", 28, 21, "consensus", -6.5, 49.5),
        GameRecord(2, 2023, 1, "C", "D", "ACC", "SEC", 31, 10, "consensus", -6.5, 49.5,
                   season_type="postseason"),
    ]

    result = run_backtest(games, SystemFilter())
    assert result.stats.cluster_count == 2
