from cfb_system_maker.models import GameRecord
from cfb_system_maker.running_stats import compute_running_stats


def _game(game_id, week, home="Alpha", away="Beta", home_points=None, away_points=None, spread=None, season=2023):
    return GameRecord(
        game_id=game_id,
        season=season,
        week=week,
        home_team=home,
        away_team=away,
        home_conference=None,
        away_conference=None,
        home_points=home_points,
        away_points=away_points,
        provider="consensus",
        spread=spread,
        total=None,
    )


def test_first_game_of_season_has_zero_history():
    games = [_game(1, 1, home_points=21, away_points=14, spread=-3.5)]
    stats = compute_running_stats(games)
    assert stats[(1, "Alpha")] == {"games_played": 0, "win_pct": None, "ats_pct": None, "streak": 0, "ats_streak": 0, "ppa_off": None, "ppa_def": None, "adv_success_off": None, "adv_success_def": None, "adv_explosiveness_off": None, "adv_explosiveness_def": None}
    assert stats[(1, "Beta")] == {"games_played": 0, "win_pct": None, "ats_pct": None, "streak": 0, "ats_streak": 0, "ppa_off": None, "ppa_def": None, "adv_success_off": None, "adv_success_def": None, "adv_explosiveness_off": None, "adv_explosiveness_def": None}


def test_no_lookahead_stats_reflect_only_strictly_prior_games():
    games = [
        _game(1, 1, home_points=21, away_points=14, spread=-3.5),   # Alpha win, covers
        _game(2, 2, home="Gamma", away="Alpha", home_points=28, away_points=10, spread=-7.0),  # Alpha loss
        _game(3, 3, home_points=35, away_points=0, spread=-10.0),   # Alpha home again
    ]
    stats = compute_running_stats(games)
    entering_g2 = stats[(2, "Alpha")]
    assert entering_g2["games_played"] == 1
    assert entering_g2["win_pct"] == 1.0
    entering_g3 = stats[(3, "Alpha")]
    assert entering_g3["games_played"] == 2
    assert entering_g3["win_pct"] == 0.5
    # g3's own 35-0 result must not appear anywhere in its entering stats


def test_ats_respects_home_spread_sign_convention():
    # Alpha home, favored by 7 (home spread -7), wins by only 3: Alpha ATS loss, Beta ATS win.
    games = [
        _game(1, 1, home_points=24, away_points=21, spread=-7.0),
        _game(2, 2, home_points=0, away_points=0, spread=None),  # carrier game to read entering stats
    ]
    stats = compute_running_stats(games)
    assert stats[(2, "Alpha")]["ats_pct"] == 0.0
    assert stats[(2, "Beta")]["ats_pct"] == 1.0


def test_ats_push_and_missing_spread_are_excluded_from_ats_pct():
    games = [
        _game(1, 1, home_points=17, away_points=10, spread=-7.0),  # exact push
        _game(2, 2, home_points=21, away_points=20, spread=None),  # no line: W-L counts, ATS doesn't
        _game(3, 3, home_points=0, away_points=0, spread=-1.0),
    ]
    stats = compute_running_stats(games)
    entering_g3 = stats[(3, "Alpha")]
    assert entering_g3["games_played"] == 2
    assert entering_g3["win_pct"] == 1.0
    assert entering_g3["ats_pct"] is None  # push + no-line games leave zero decided ATS bets


def test_unplayed_games_do_not_accumulate():
    games = [
        _game(1, 1, home_points=None, away_points=None, spread=-3.0),
        _game(2, 2, home_points=7, away_points=3, spread=-3.0),
    ]
    stats = compute_running_stats(games)
    assert stats[(2, "Alpha")]["games_played"] == 0


def test_seasons_reset():
    games = [
        _game(1, 10, season=2022, home_points=42, away_points=0, spread=-20.0),
        _game(2, 1, season=2023, home_points=0, away_points=0, spread=-1.0),
    ]
    stats = compute_running_stats(games)
    assert stats[(2, "Alpha")] == {"games_played": 0, "win_pct": None, "ats_pct": None, "streak": 0, "ats_streak": 0, "ppa_off": None, "ppa_def": None, "adv_success_off": None, "adv_success_def": None, "adv_explosiveness_off": None, "adv_explosiveness_def": None}


def test_start_dates_override_week_order():
    # Bowl game stored as week 1 but dated after the week 12 game.
    games = [
        _game(1, 12, home_points=21, away_points=14, spread=-3.0),
        _game(2, 1, home_points=10, away_points=20, spread=-3.0),
    ]
    start_dates = {1: "2023-11-25 17:00:00+00:00", 2: "2023-12-30 17:00:00+00:00"}
    stats = compute_running_stats(games, start_dates=start_dates)
    assert stats[(2, "Alpha")]["games_played"] == 1
    assert stats[(1, "Alpha")]["games_played"] == 0


def test_running_ppa_is_average_of_prior_games_only():
    games = [
        _game(1, 1, home_points=21, away_points=14, spread=-3.0),
        _game(2, 2, home_points=28, away_points=7, spread=-3.0),
        _game(3, 3, home_points=0, away_points=0, spread=-3.0),
    ]
    ppa = {
        (1, "Alpha"): (0.40, -0.10),
        (2, "Alpha"): (0.60, -0.30),
        (3, "Alpha"): (9.99, 9.99),  # current game's PPA must never leak into its own entering stats
        (1, "Beta"): (0.10, 0.20),
    }
    stats = compute_running_stats(games, ppa=ppa)
    assert stats[(1, "Alpha")]["ppa_off"] is None
    assert stats[(2, "Alpha")]["ppa_off"] == 0.40
    assert stats[(3, "Alpha")]["ppa_off"] == 0.50
    assert stats[(3, "Alpha")]["ppa_def"] == -0.20
    assert stats[(2, "Beta")]["ppa_off"] == 0.10
    assert stats[(3, "Beta")]["ppa_off"] == 0.10  # no row for game 2: average over available rows


def test_running_adv_success_off_is_average_of_prior_games_only():
    games = [
        _game(1, 1, home_points=21, away_points=14, spread=-3.0),
        _game(2, 2, home_points=28, away_points=7, spread=-3.0),
        _game(3, 3, home_points=0, away_points=0, spread=-3.0),
    ]
    adv = {
        (1, "Alpha"): {"success_off": 0.40},
        (2, "Alpha"): {"success_off": 0.60},
        (3, "Alpha"): {"success_off": 9.99},  # current game's value must never leak into its own entering stats
        (1, "Beta"): {"success_off": 0.10},
    }
    stats = compute_running_stats(games, adv=adv)
    assert stats[(1, "Alpha")]["adv_success_off"] is None
    assert stats[(2, "Alpha")]["adv_success_off"] == 0.40
    assert stats[(3, "Alpha")]["adv_success_off"] == 0.50  # avg of priors, 9.99 excluded


def test_running_adv_explosiveness_respects_season_reset_and_start_date_order():
    # Prior-season game must not leak; start_date (not week) sets order.
    games = [
        _game(1, 10, season=2022, home_points=42, away_points=0, spread=-20.0),  # prior season
        _game(2, 12, season=2023, home_points=21, away_points=14, spread=-3.0),  # dated later despite lower week
        _game(3, 1, season=2023, home_points=10, away_points=20, spread=-3.0),   # bowl-style, dated last
    ]
    adv = {
        (1, "Alpha"): {"explosiveness_off": 5.00},  # 2022 — must not fold into 2023
        (2, "Alpha"): {"explosiveness_off": 1.20},
        (3, "Alpha"): {"explosiveness_off": 9.99},  # own game must not leak
    }
    start_dates = {2: "2023-11-25 17:00:00+00:00", 3: "2023-12-30 17:00:00+00:00"}
    stats = compute_running_stats(games, adv=adv, start_dates=start_dates)
    assert stats[(2, "Alpha")]["adv_explosiveness_off"] is None  # season reset: no 2023 prior
    assert stats[(3, "Alpha")]["adv_explosiveness_off"] == 1.20  # only game 2, ordered before game 3


def test_ppa_handles_partial_none_values():
    games = [
        _game(1, 1, home_points=21, away_points=14, spread=-3.0),
        _game(2, 2, home_points=0, away_points=0, spread=-3.0),
    ]
    ppa = {(1, "Alpha"): (None, -0.25)}
    stats = compute_running_stats(games, ppa=ppa)
    assert stats[(2, "Alpha")]["ppa_off"] is None
    assert stats[(2, "Alpha")]["ppa_def"] == -0.25


def test_win_streak_is_signed_and_entering_game():
    games = [
        _game(1, 1, home_points=21, away_points=14),   # Alpha win  -> +1 entering g2
        _game(2, 2, home_points=28, away_points=10),   # Alpha win  -> +2 entering g3
        _game(3, 3, home_points=3, away_points=30),    # Alpha loss -> -1 entering g4
        _game(4, 4, home_points=1, away_points=40),    # Alpha loss -> -2 entering g5
        _game(5, 5, home_points=7, away_points=7),     # tie: breaks streak -> 0 entering g6
        _game(6, 6, home_points=10, away_points=0),
    ]
    stats = compute_running_stats(games)
    assert stats[(1, "Alpha")]["streak"] == 0     # season opener, no history
    assert stats[(2, "Alpha")]["streak"] == 1
    assert stats[(3, "Alpha")]["streak"] == 2
    assert stats[(4, "Alpha")]["streak"] == -1
    assert stats[(5, "Alpha")]["streak"] == -2
    assert stats[(6, "Alpha")]["streak"] == 0
    # Beta is the mirror image of every Alpha result
    assert stats[(3, "Beta")]["streak"] == -2
    assert stats[(4, "Beta")]["streak"] == 1


def test_ats_streak_is_signed_and_pushes_break_it():
    games = [
        # Alpha -3.5 favourite, wins by 7 -> covers  => +1
        _game(1, 1, home_points=21, away_points=14, spread=-3.5),
        # Alpha -3.5, wins by 10 -> covers           => +2
        _game(2, 2, home_points=24, away_points=14, spread=-3.5),
        # Alpha -10, wins by 3 -> fails to cover     => -1
        _game(3, 3, home_points=17, away_points=14, spread=-10.0),
        # Alpha -7, wins by exactly 7 -> ATS push    => 0
        _game(4, 4, home_points=21, away_points=14, spread=-7.0),
        _game(5, 5, home_points=10, away_points=0, spread=-3.0),
    ]
    stats = compute_running_stats(games)
    assert stats[(1, "Alpha")]["ats_streak"] == 0
    assert stats[(2, "Alpha")]["ats_streak"] == 1
    assert stats[(3, "Alpha")]["ats_streak"] == 2
    assert stats[(4, "Alpha")]["ats_streak"] == -1
    assert stats[(5, "Alpha")]["ats_streak"] == 0   # push broke the streak


def test_streak_ignores_games_without_scores():
    games = [
        _game(1, 1, home_points=21, away_points=14),
        _game(2, 2, home_points=None, away_points=None),   # unplayed: no effect
        _game(3, 3, home_points=28, away_points=0),
    ]
    stats = compute_running_stats(games)
    assert stats[(3, "Alpha")]["streak"] == 1


def test_streak_does_not_carry_across_seasons():
    games = [
        _game(1, 12, home_points=35, away_points=0, season=2022),
        _game(2, 1, home_points=10, away_points=7, season=2023),
    ]
    stats = compute_running_stats(games)
    assert stats[(2, "Alpha")]["streak"] == 0
