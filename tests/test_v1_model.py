import numpy as np

from cfb_system_maker.models import GameRecord
from cfb_system_maker.v1_model import fit_v1, load_v1_fit, save_v1_fit, score_v1


def _synthetic_games(n=400, seed=0):
    """Games with a real (if noisy) totals relationship, so the fit isn't
    degenerate: true_total = line_total + N(0, 10), decided by a coin flip
    biased slightly toward the over so probit has signal to find."""
    rng = np.random.default_rng(seed)
    games = []
    for i in range(n):
        spread = float(rng.choice([-14, -7, -3, 3, 7, 14]))
        total = float(rng.uniform(40, 65))
        true_total = total + rng.normal(1.0, 10.0)  # slight over bias
        dog_pts = max(0.0, (true_total - abs(spread)) / 2 + rng.normal(0, 3))
        fav_pts = max(0.0, true_total - dog_pts)
        if spread < 0:
            home_pts, away_pts = fav_pts, dog_pts
        else:
            home_pts, away_pts = dog_pts, fav_pts
        games.append(GameRecord(
            game_id=i, season=2023, week=1,
            home_team="Home", away_team="Away",
            home_conference=None, away_conference=None,
            home_points=round(home_pts), away_points=round(away_pts),
            provider="consensus", spread=spread, total=total,
        ))
    return games


def test_fit_v1_skips_pickem_and_incomplete_rows():
    games = _synthetic_games(50)
    games.append(GameRecord(999, 2023, 1, "A", "B", None, None, 20, 20, "consensus", 0, 45))  # pick'em
    games.append(GameRecord(998, 2023, 1, "A", "B", None, None, None, None, "consensus", -3, 45))  # unplayed
    fit = fit_v1(games)
    assert fit.n_games == 50


def test_score_v1_returns_prob_in_unit_interval_and_skips_pickem():
    games = _synthetic_games(300)
    fit = fit_v1(games)
    scores = score_v1(games, fit)
    assert len(scores) == 300
    assert all(0.0 <= p <= 1.0 for p in scores.values())

    games_with_pickem = games + [
        GameRecord(9999, 2023, 1, "A", "B", None, None, None, None, "consensus", 0, 45)
    ]
    scores2 = score_v1(games_with_pickem, fit)
    assert 9999 not in scores2


def test_score_v1_needs_no_scores():
    """Scoring an upcoming (unplayed) game must not require home/away points."""
    games = _synthetic_games(300)
    fit = fit_v1(games)
    upcoming = [GameRecord(5000, 2026, 1, "TCU", "UNC", None, None, None, None, "DraftKings", -6.5, 49.5)]
    scores = score_v1(upcoming, fit)
    assert 5000 in scores
    assert 0.0 <= scores[5000] <= 1.0


def test_save_and_load_v1_fit_round_trips(tmp_path):
    games = _synthetic_games(300)
    fit = fit_v1(games)
    save_v1_fit(tmp_path, fit)
    loaded = load_v1_fit(tmp_path)
    assert loaded == fit


def test_load_v1_fit_none_when_absent(tmp_path):
    assert load_v1_fit(tmp_path) is None
