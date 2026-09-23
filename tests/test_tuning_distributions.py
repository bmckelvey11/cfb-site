"""Release D, D1: integer predictive tables for the total, their scores, and the gate."""
import numpy as np
import pandas as pd
import pytest

from models.tuning.dist_spec import CalibrationGate
from models.tuning.distributions import (
    calibration_report, empirical_pmf, joint_pmf, normal_pmf, open_label_scores, score_pmf,
    season_forecasts, window_seasons,
)
from models.tuning.features import synthetic_frame
from models.tuning.spec import ModelSpec, RunSpec

S = 150


def _point(k: int) -> np.ndarray:
    p = np.zeros(S + 1)
    p[k] = 1.0
    return p


def test_normal_table_sums_to_one_and_centres_on_the_mean():
    pmf = normal_pmf(np.array([55.0, 20.3]), np.array([15.0, 15.0]), S)
    assert np.allclose(pmf.sum(axis=1), 1.0)
    # The mass below 0 is folded into bin 0, nudging the mean up by ~4e-4.
    assert (pmf @ np.arange(S + 1))[0] == pytest.approx(55.0, abs=1e-3)
    assert pmf[0, 50] == pytest.approx(pmf[0, 60])


def test_empirical_table_rounds_each_shifted_residual():
    pmf = empirical_pmf(np.array([10.0]), [np.array([-1.4, 0.2, 1.6])], S)
    assert pmf[0, 9] == pmf[0, 10] == pmf[0, 12] == pytest.approx(1 / 3)
    assert pmf[0].sum() == pytest.approx(1.0)


def test_joint_table_adds_overtime_only_to_regulation_ties():
    pmf, home_win, tie = joint_pmf(np.array([10.0]), np.array([10.0]),
                                   [np.array([[0.0, 0.0], [1.0, -1.0]])], [np.array([3.0, 7.0])], S)
    assert tie[0] == pytest.approx(0.5)
    assert pmf[0, 20] == pytest.approx(0.5)            # 11-9: no overtime
    assert pmf[0, 23] == pytest.approx(0.25) and pmf[0, 27] == pytest.approx(0.25)
    assert pmf[0].sum() == pytest.approx(1.0)
    assert home_win[0] == pytest.approx(0.75)           # one win, one tie counted as half


def test_scores_on_hand_checked_tables():
    exact = score_pmf(_point(5)[None, :], np.array([5]), quantiles=(0.5,), levels=(0.8,))
    assert exact.loc[0, "crps"] == 0 and exact.loc[0, "pit"] == 0.5 and exact.loc[0, "cover_0.8"]
    split = np.zeros(S + 1)
    split[4] = split[5] = 0.5
    s = score_pmf(split[None, :], np.array([5]), quantiles=(0.5,), levels=(0.5,))
    assert s.loc[0, "crps"] == pytest.approx(0.25)
    assert s.loc[0, "pit"] == pytest.approx(0.75)
    assert s.loc[0, "q_0.5"] == 4 and s.loc[0, "pinball_0.5"] == pytest.approx(0.5)
    assert s.loc[0, "mean"] == pytest.approx(4.5)


def test_window_uses_only_earlier_usable_seasons():
    usable = [2014, 2015, 2016, 2017, 2018, 2019, 2021, 2022]
    assert window_seasons(2021, usable, 3) == [2017, 2018, 2019]
    assert window_seasons(2022, usable, 3) == [2018, 2019, 2021]
    assert window_seasons(2015, usable, 3) == [2014]


def _spec():
    return RunSpec.model_validate({
        "spec_id": "d1", "created_at": "2026-09-23T00:00:00Z", "created_by": "test",
        "dataset": {"source": "synthetic_v1", "snapshot": "fx", "synthetic_seed": 2,
                    "seasons": [2014, 2015, 2016, 2017, 2021, 2022]},
        "feature_set": {"feature_set_id": "fx", "version": 1, "features": [
            {"id": f, "version": 1, "availability_class": "historical_replayable"}
            for f in ("rv1_total", "rv1_off_home", "min_prior_games")]},
        "folds": {"inner_test_seasons": [2015, 2016], "outer_test_seasons": [2021, 2022],
                  "exclude_seasons": [2020]},
        "search": {"profile_id": "cfb_regularized_regression_v1", "n_trials": 2},
        "acceptance": {"baselines": ["market_open"]},
    })


def test_season_forecasts_never_see_their_own_or_later_seasons():
    spec = _spec()
    frame = synthetic_frame(spec.dataset, spec.feature_set)
    model = ModelSpec(family="ridge", alpha=1.0)
    seasons = [2015, 2016, 2017, 2021, 2022]
    base = season_forecasts(frame, spec, model, "target", seasons)
    moved = frame.copy()
    moved.loc[moved["season"] == 2021, "target"] += 50.0
    after = season_forecasts(moved, spec, model, "target", seasons)
    early = frame["season"] <= 2021
    pd.testing.assert_series_equal(base[early], after[early])
    assert not np.allclose(base[frame["season"] == 2022], after[frame["season"] == 2022])
    assert base[frame["season"] == 2014].isna().all()


def _calibrated(sigma_model: float, n=6000, seed=4):
    rng = np.random.default_rng(seed)
    mu = rng.uniform(40, 70, n)
    y = np.clip(np.round(mu + rng.normal(0, 15, n)), 0, S).astype(int)
    scores = score_pmf(normal_pmf(mu, np.full(n, sigma_model), S), y,
                       quantiles=(0.5,), levels=(0.5, 0.8, 0.9))
    scores["season"] = np.repeat([2021, 2022, 2023], n // 3)
    scores["week"] = np.tile(np.arange(2, 14), n // 12)
    return scores


def test_gate_passes_a_calibrated_table_and_fails_an_overconfident_one():
    gate = CalibrationGate()
    good = calibration_report(_calibrated(15.0), gate, (0.5, 0.8, 0.9))
    assert good["pass"], good
    bad = calibration_report(_calibrated(9.0), gate, (0.5, 0.8, 0.9))
    assert not bad["pass"] and bad["pooled_coverage"]["0.8"]["value"] < 0.75


def test_open_label_scores_exclude_pushes():
    pmf = np.vstack([_point(50), _point(60)])
    pmf[0] = 0.0
    pmf[0, 48], pmf[0, 50], pmf[0, 53] = 0.25, 0.5, 0.25   # P(over 50 | no push) = 0.5
    y = np.array([50, 61])                                   # game 0 pushes on 50
    out = open_label_scores(pmf, y, np.array([50.0, 55.5]))
    assert out["n"] == 1 and out["pushes_excluded"] == 1
    assert out["brier"] == pytest.approx(0.0)                # game 1: P(over 55.5) = 1, went over
