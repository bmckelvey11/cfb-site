from cfb_system_maker.backtest import compute_season_breakdown, compute_system_stats, run_backtest, sign_consistency, split_holdout
from cfb_system_maker.models import BetDetail, FeatureFilter, GameRecord, SeasonRecord, SystemFilter


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
