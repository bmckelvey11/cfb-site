"""Release C, C3: season-holdout folds, the three estimators, fit_fold, compare_outer."""
import numpy as np
import pandas as pd
import pytest

from models.tuning.estimators import FitFailure, acceptance_gates, compare_outer, fit_fold
from models.tuning.folds import make_folds
from models.tuning.spec import FoldSpec, ModelSpec, RunSpec

SEASONS = [2014, 2015, 2016, 2017, 2018, 2019, 2021, 2022]


def _run_spec(features=("x1", "x2", "x3"), **fold_over) -> RunSpec:
    return RunSpec.model_validate({
        "spec_id": "c3", "created_at": "2026-09-23T00:00:00Z", "created_by": "test",
        "dataset": {"source": "synthetic_v1", "snapshot": "fx", "synthetic_seed": 1,
                    "seasons": SEASONS},
        "feature_set": {"feature_set_id": "fx", "version": 1, "features": [
            {"id": f, "version": 1, "availability_class": "historical_replayable"}
            for f in features]},
        "folds": {"inner_test_seasons": [2016, 2017, 2018], "outer_test_seasons": [2021, 2022],
                  "exclude_seasons": [2020], **fold_over},
        "search": {"profile_id": "cfb_regularized_regression_v1", "n_trials": 3},
        "acceptance": {"baselines": ["market_open", "past_mean"]},
    })


def _frame(noise=0.3, seed=0) -> pd.DataFrame:
    """Linear truth y = 50 + 4 x1 - 2 x2 + 0 x3, two games a day for 14 weeks a season."""
    rng = np.random.default_rng(seed)
    rows = []
    for season in SEASONS + [2020]:
        start = pd.Timestamp(f"{season}-09-01T16:00:00Z")
        for week in range(2, 16):
            cut = start + pd.Timedelta(days=7 * (week - 2))
            for i in range(10):
                rows.append({"game_id": season * 10_000 + week * 100 + i, "season": season,
                             "week": week, "kickoff": cut + pd.Timedelta(hours=i), "decision_ts": cut})
    f = pd.DataFrame(rows)
    x = rng.normal(size=(len(f), 3))
    f["x1"], f["x2"], f["x3"] = x[:, 0], x[:, 1], x[:, 2]
    signal = 50 + 4 * x[:, 0] - 2 * x[:, 1]
    f["target"] = signal + rng.normal(0, noise, len(f))
    f["market_open"] = signal + rng.normal(0, 3.0, len(f))
    f["past_mean"] = 50.0
    return f


def test_folds_are_chronological_disjoint_and_inner_first():
    frame = _frame()
    folds = make_folds(_run_spec().folds, frame)
    assert [f.fold_id for f in folds] == ["inner-2016", "inner-2017", "inner-2018",
                                          "outer-2021", "outer-2022"]
    for f in folds:
        train, test = frame.loc[f.train_idx], frame.loc[f.test_idx]
        assert set(test["season"]) == {f.test_season}
        assert not set(train["game_id"]) & set(test["game_id"])
        assert train["kickoff"].max() < test["decision_ts"].min()
        assert 2020 not in set(train["season"])
        assert f.bounds["train_seasons"] == sorted(s for s in SEASONS if s < f.test_season)
        assert f.bounds["test_first_kickoff"] <= f.bounds["test_last_kickoff"]


def test_embargo_drops_training_rows_too_close_to_the_test_block():
    frame = _frame()
    plain = {f.fold_id: f for f in make_folds(_run_spec().folds, frame)}
    spec = _run_spec(embargo_days=330)  # reaches back into the previous season's weeks
    embargoed = {f.fold_id: f for f in make_folds(spec.folds, frame)}
    f, g = plain["outer-2022"], embargoed["outer-2022"]
    assert len(g.train_idx) < len(f.train_idx)
    limit = frame.loc[g.test_idx, "decision_ts"].min() - pd.Timedelta(days=330)
    assert frame.loc[g.train_idx, "kickoff"].max() < limit


def _split(frame, fold_id, spec):
    fold = {f.fold_id: f for f in make_folds(spec.folds, frame)}[fold_id]
    return frame.loc[fold.train_idx], frame.loc[fold.test_idx]


@pytest.mark.parametrize("model", [
    ModelSpec(family="ridge", alpha=0.01),
    ModelSpec(family="elastic_net", alpha=0.001, l1_ratio=0.5),
    ModelSpec(family="huber", alpha=1e-4, epsilon=1.35),
])
def test_each_estimator_recovers_a_linear_signal(model):
    spec, frame = _run_spec(), _frame()
    train, test = _split(frame, "outer-2021", spec)
    r = fit_fold(train, test, spec, model, "outer-2021")
    assert r.role == "outer" and r.test_season == 2021 and r.verify()
    assert r.metrics["n"] == len(test) and r.metrics["mae"] < 0.4
    assert r.features == ("x1", "x2", "x3")
    assert [gid for gid, _ in r.predictions] == test["game_id"].tolist()


def test_undeclared_columns_are_never_features():
    spec, frame = _run_spec(features=("x1", "x2")), _frame()
    frame["leak"] = frame["target"]
    train, test = _split(frame, "inner-2016", spec)
    r = fit_fold(train, test, spec, ModelSpec(family="ridge", alpha=1.0), "inner-2016")
    assert r.features == ("x1", "x2")


def test_an_all_null_training_feature_is_a_data_validation_failure():
    spec, frame = _run_spec(), _frame()
    frame["x3"] = np.nan
    train, test = _split(frame, "inner-2016", spec)
    with pytest.raises(FitFailure) as e:
        fit_fold(train, test, spec, ModelSpec(family="ridge", alpha=1.0), "inner-2016")
    assert e.value.kind == "data_validation"


def test_paired_comparisons_use_only_games_with_the_baseline():
    spec, frame = _run_spec(), _frame()
    train, test = _split(frame, "outer-2022", spec)
    test = test.copy()
    test.loc[test.index[::2], "market_open"] = np.nan
    r = fit_fold(train, test, spec, ModelSpec(family="ridge", alpha=1.0), "outer-2022")
    have = test["market_open"].notna()
    assert r.comparisons["market_open"]["n"] == int(have.sum())
    assert r.comparisons["past_mean"]["n"] == len(test)
    y_hat = pd.Series(dict(r.predictions))
    mine = (y_hat[test.loc[have, "game_id"]].to_numpy() - test.loc[have, "target"]).abs().mean()
    assert r.comparisons["market_open"]["model_mae"] == pytest.approx(mine)


def test_fit_fold_is_deterministic():
    spec, frame = _run_spec(), _frame()
    train, test = _split(frame, "inner-2017", spec)
    m = ModelSpec(family="elastic_net", alpha=0.05, l1_ratio=0.3)
    a = fit_fold(train, test, spec, m, "inner-2017")
    b = fit_fold(train.sample(frac=1.0, random_state=3).sort_index(), test, spec, m, "inner-2017")
    assert a == b and a.artifact_sha256 == b.artifact_sha256


def _predictions(model_noise: float, seed=5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    f = _frame(noise=6.0, seed=seed)
    f = f[f["season"].isin([2021, 2022])].copy()
    signal = f["target"] - rng.normal(0, 0.1, len(f))
    f["y_hat"] = signal + rng.normal(0, model_noise, len(f))
    f["market_open"] = f["target"] + rng.normal(0, 12.0, len(f))
    return f[["season", "week", "game_id", "target", "y_hat", "market_open", "past_mean"]]


def test_compare_outer_reports_verdicts_calibration_and_labels_the_market():
    spec = _run_spec()
    out = compare_outer(_predictions(model_noise=0.5), spec.acceptance)
    assert out["n"] == 280 and out["n_clusters"] == 28
    m = out["baselines"]["market_open"]
    assert m["verdict"] == "improves" and m["ci95"][1] < 0
    assert m["label"] == "descriptive: untimed vendor open, no price"
    assert set(m["by_season"]) == {2021, 2022}
    assert out["calibration"]["slope"] == pytest.approx(1.0, abs=0.15)
    assert set(out["by_season"]) == {2021, 2022}


def test_acceptance_gates_report_pass_and_fail():
    spec = _run_spec()
    comparisons = compare_outer(_predictions(model_noise=0.5), spec.acceptance)
    gates = acceptance_gates(comparisons, spec.acceptance, n_features=3, fold_warnings=[],
                             dropped={})
    assert all(g["pass"] for g in gates.values())
    bad = acceptance_gates(comparisons, spec.acceptance, n_features=3,
                           fold_warnings=["ConvergenceWarning: x"], dropped={"z": "late"})
    assert not bad["convergence"]["pass"] and not bad["data_availability"]["pass"]
