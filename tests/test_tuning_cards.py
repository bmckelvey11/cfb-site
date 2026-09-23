"""Release C, C1: the Markdown model card is complete, deterministic, and claim-free."""
import re

from models.tuning.cards import BANNED_TERMS, render_card
from models.tuning.spec import FoldResult, ModelSpec, RunSpec

SPEC = RunSpec.model_validate({
    "spec_id": "card_fixture", "created_at": "2026-09-23T00:00:00Z", "created_by": "test",
    "notes": "Outer seasons already spent as a holdout; descriptive only.",
    "dataset": {"source": "synthetic_v1", "snapshot": "fx", "synthetic_seed": 1,
                "seasons": [2014, 2015, 2016, 2017, 2021]},
    "feature_set": {"feature_set_id": "fx_set", "version": 3, "features": [
        {"id": "rv1_total", "version": 1, "availability_class": "historical_replayable"},
        {"id": "neutral", "version": 1, "availability_class": "historical_replayable"}]},
    "folds": {"inner_test_seasons": [2015, 2016], "outer_test_seasons": [2017, 2021]},
    "search": {"profile_id": "cfb_regularized_regression_v1", "n_trials": 12},
    "acceptance": {"baselines": ["market_open", "past_mean", "ridge_v1_total"]},
})
RUN_ID = SPEC.run_id()

FOLDS = [
    {"fold_id": fid, "role": fid.split("-")[0], "test_season": int(fid.split("-")[1]),
     "bounds": {"train_seasons": [2014], "train_rows": 100, "test_rows": 50,
                "train_first_kickoff": "2014-09-01T16:00:00+00:00",
                "train_last_kickoff": "2014-12-01T16:00:00+00:00",
                "test_first_kickoff": f"{fid[-4:]}-09-01T16:00:00+00:00",
                "test_last_kickoff": f"{fid[-4:]}-12-01T16:00:00+00:00", "embargo_days": 0}}
    for fid in ("inner-2015", "inner-2016", "outer-2017", "outer-2021")]

MANIFEST = {
    "run_id": RUN_ID, "config_hash": SPEC.config_hash, "git_sha": "abc1234", "git_dirty": False,
    "code_sha256": "c" * 64, "python": "3.14.6", "packages": {"optuna": "5.0.0"},
    "sources": [{"path": "data/raw/games_2021.json", "sha256": "d" * 64}],
    "features": {"kept": ["rv1_total", "neutral"], "dropped": {}},
    "folds": FOLDS,
    "gates": {"bias": {"pass": True, "detail": "outer mean residual +0.100"},
              "convergence": {"pass": False, "detail": "ConvergenceWarning: slow"}},
    "reproduce": "python -m models.tuning run --spec models/tuning/specs/x.json",
    "storage": "data/processed/tuning/optuna.sqlite3",
}
STUDY = {
    "study_name": RUN_ID, "requested": 12, "completed": 7, "pruned": 3, "failed": 2,
    "failure_kinds": {"stale_heartbeat": 1, "data_validation": 1},
    "sampler": {"name": "tpe", "seed": 42, "multivariate": True, "group": True, "n_startup_trials": 20},
    "pruner": {"name": "median", "n_startup_trials": 20, "n_warmup_steps": 2, "interval_steps": 1},
    "best": {"number": 4, "value": 12.3456, "params": {"model_family": "ridge", "ridge_alpha": 3.2}},
    "selected": {"number": 4, "reason": "best complete trial"},
    "top": [{"number": 4, "value": 12.3456, "params": {"model_family": "ridge", "ridge_alpha": 3.2}},
            {"number": 9, "value": 12.4, "params": {"model_family": "elastic_net",
                                                    "elasticnet_alpha": 0.1,
                                                    "elasticnet_l1_ratio": 0.4}}],
}
MODEL = ModelSpec(family="ridge", alpha=3.2)
OUTER = [FoldResult(run_id=RUN_ID, config_hash=SPEC.config_hash, fold_id=f"outer-{s}", role="outer",
                    test_season=s, model=MODEL, features=("rv1_total", "neutral"),
                    fitted={"coef": [1.0, 0.0], "intercept": 0.0}, predictions=((1, 50.0),),
                    metrics={"n": 50, "mae": 13.1, "rmse": 16.2, "bias": 0.1},
                    comparisons={}).sealed() for s in (2017, 2021)]
COMPARISONS = {
    "n": 100, "n_clusters": 20, "model": {"n": 100, "mae": 13.0, "rmse": 16.0, "bias": 0.1},
    "calibration": {"slope": 0.97, "intercept": 1.2},
    "by_season": {2017: {"n": 50, "mae": 13.1, "rmse": 16.2, "bias": 0.1},
                  2021: {"n": 50, "mae": 12.9, "rmse": 15.8, "bias": 0.1}},
    "baselines": {
        "market_open": {"n": 50, "n_clusters": 10, "model_mae": 12.9, "baseline_mae": 12.6,
                        "diff": 0.3, "ci95": [0.1, 0.5], "mde80": 0.28, "se": 0.1,
                        "by_season": {2021: 0.3}, "verdict": "worse",
                        "label": "descriptive: untimed vendor open, no price"},
        "past_mean": {"n": 100, "n_clusters": 20, "model_mae": 13.0, "baseline_mae": 14.0,
                      "diff": -1.0, "ci95": [-1.3, -0.7], "mde80": 0.4, "se": 0.15,
                      "by_season": {2017: -1.1, 2021: -0.9}, "verdict": "improves"},
        "ridge_v1_total": {"n": 0},
    },
}


def _card() -> str:
    return render_card(SPEC, MANIFEST, STUDY, OUTER, COMPARISONS)


def test_card_carries_identity_folds_trials_and_every_baseline_slot():
    card = _card()
    for needle in (RUN_ID, SPEC.config_hash, "fx_set", "v3", "abc1234",
                   "inner-2015", "inner-2016", "outer-2017", "outer-2021",
                   "2021-09-01T16:00:00+00:00", "market_open", "past_mean", "ridge_v1_total",
                   "requested 12", "completed 7", "pruned 3", "failed 2", "stale_heartbeat",
                   "data/raw/games_2021.json", SPEC.notes, MANIFEST["reproduce"],
                   OUTER[0].artifact_sha256):
        assert needle in card, needle


def test_market_slot_is_labeled_descriptive_and_empty_slots_say_so():
    card = _card()
    market_row = next(line for line in card.splitlines() if line.startswith("| market_open"))
    assert "descriptive" in market_row and "untimed" in market_row
    empty_row = next(line for line in card.splitlines() if line.startswith("| ridge_v1_total"))
    assert "no games" in empty_row


def test_failed_gate_is_visible():
    row = next(line for line in _card().splitlines() if line.startswith("| convergence"))
    assert "FAIL" in row


def test_rendering_is_byte_identical():
    assert _card() == _card()


def test_card_makes_no_betting_claims():
    card = _card()
    for term in BANNED_TERMS:
        assert not re.search(rf"\b{re.escape(term)}\b", card, flags=re.IGNORECASE), term
