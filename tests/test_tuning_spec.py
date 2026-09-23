"""Release C, C0: typed run specs, canonical hash, and fold-result sealing. In-memory."""
import json

import pytest
from pydantic import ValidationError

from models.tuning.spec import FoldResult, ModelSpec, RunSpec, SEARCH_PROFILES, load_run_spec


def _spec_dict(**over) -> dict:
    d = {
        "schema_version": 1,
        "spec_id": "unit",
        "created_at": "2026-09-23T00:00:00Z",
        "created_by": "test",
        "dataset": {"source": "synthetic_v1", "snapshot": "fixture", "synthetic_seed": 7,
                    "seasons": [2014, 2015, 2016, 2017, 2018, 2019, 2021, 2022]},
        "feature_set": {"feature_set_id": "fx", "version": 1, "features": [
            {"id": "a", "version": 1, "availability_class": "historical_replayable"},
            {"id": "b", "version": 1, "availability_class": "historical_replayable"}]},
        "folds": {"inner_test_seasons": [2016, 2017], "outer_test_seasons": [2021, 2022],
                  "exclude_seasons": [2020]},
        "search": {"profile_id": "cfb_regularized_regression_v1", "n_trials": 5},
        "acceptance": {"baselines": ["past_mean", "market_open"]},
        "seeds": {"split": 0, "model": 0, "sampler": 42},
    }
    for path, value in over.items():
        node = d
        *parents, leaf = path.split(".")
        for p in parents:
            node = node[p]
        node[leaf] = value
    return d


def test_reordered_keys_and_sets_hash_the_same():
    a = RunSpec.model_validate(_spec_dict())
    shuffled = json.loads(json.dumps(_spec_dict(), sort_keys=True))  # different key order
    shuffled["dataset"]["seasons"] = list(reversed(shuffled["dataset"]["seasons"]))
    shuffled["folds"]["outer_test_seasons"] = [2022, 2021]
    shuffled["acceptance"]["baselines"] = ["market_open", "past_mean"]
    b = RunSpec.model_validate(shuffled)
    assert a.config_hash == b.config_hash
    assert a.run_id() == b.run_id() == f"run-{a.config_hash[:12]}"
    assert a.run_id(replicate=2) == f"run-{a.config_hash[:12]}-r2"


def test_provenance_is_not_hashed_but_results_inputs_are():
    base = RunSpec.model_validate(_spec_dict()).config_hash
    assert RunSpec.model_validate(_spec_dict(created_at="2027-01-01T00:00:00Z",
                                             created_by="someone")).config_hash == base
    assert RunSpec.model_validate(_spec_dict(**{"seeds.model": 1})).config_hash != base


def test_feature_order_changes_the_hash():
    d = _spec_dict()
    d["feature_set"]["features"].reverse()
    assert RunSpec.model_validate(d).config_hash != RunSpec.model_validate(_spec_dict()).config_hash


@pytest.mark.parametrize("path", ["surprise", "dataset.surprise", "search.sampler.surprise",
                                  "feature_set.features.0.surprise"])
def test_unknown_fields_are_rejected_at_any_level(path):
    d = _spec_dict()
    node = d
    *parents, leaf = path.split(".")
    for p in parents:
        node = node[int(p)] if p.isdigit() else node.setdefault(p, {})
    node[leaf] = 1
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        RunSpec.model_validate(d)


@pytest.mark.parametrize("over, message", [
    ({"folds.outer_test_seasons": [2017, 2021]}, "confirmation lock"),
    ({"folds.outer_test_seasons": [2016, 2021]}, "confirmation lock"),
    ({"folds.outer_test_seasons": [2021, 2023]}, "not in dataset"),
    ({"folds.inner_test_seasons": [2017]}, "at least two inner folds"),
    ({"folds.inner_test_seasons": [2014, 2015]}, "no training season"),
    ({"dataset.synthetic_seed": None}, "synthetic_seed"),
    ({"dataset.source": "cfb_release_b"}, "synthetic_seed"),
    ({"acceptance.bootstrap": {"draws": 500}}, "Release B bootstrap"),
    ({"acceptance.max_features": 1}, "max_features"),
    ({"search.pruner": {"n_warmup_steps": 0}}, "n_warmup_steps"),
    ({"search.profile_id": "anything_goes"}, "profile_id"),
])
def test_invalid_specs_are_rejected(over, message):
    with pytest.raises(ValidationError, match=message):
        RunSpec.model_validate(_spec_dict(**over))


def test_duplicate_feature_is_rejected():
    d = _spec_dict()
    d["feature_set"]["features"].append(dict(d["feature_set"]["features"][0]))
    with pytest.raises(ValidationError, match="duplicate feature"):
        RunSpec.model_validate(d)


def test_spec_round_trips_through_a_file(tmp_path):
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(_spec_dict()), encoding="utf-8")
    assert load_run_spec(path) == RunSpec.model_validate(_spec_dict())


@pytest.mark.parametrize("model, ok", [
    ({"family": "ridge", "alpha": 1.0}, True),
    ({"family": "elastic_net", "alpha": 0.1, "l1_ratio": 0.5}, True),
    ({"family": "huber", "alpha": 1e-4, "epsilon": 1.35}, True),
    ({"family": "ridge", "alpha": 1.0, "l1_ratio": 0.5}, False),
    ({"family": "elastic_net", "alpha": 0.1}, False),
    ({"family": "huber", "alpha": 1e-4, "epsilon": 0.9}, False),
    ({"family": "ridge", "alpha": 0.0}, False),
])
def test_model_spec_parameters_match_the_family(model, ok):
    if ok:
        ModelSpec.model_validate(model)
    else:
        with pytest.raises(ValidationError):
            ModelSpec.model_validate(model)


def test_search_profile_is_the_plan_section_14_space():
    p = SEARCH_PROFILES["cfb_regularized_regression_v1"]
    assert p["ridge"]["alpha"] == (0.001, 1000.0, True)
    assert p["elastic_net"]["alpha"] == (0.0001, 20.0, True)
    assert p["elastic_net"]["l1_ratio"] == (0.01, 0.99, False)


def _result(**over) -> FoldResult:
    fields = dict(run_id="run-x", config_hash="h", fold_id="outer-2021", role="outer",
                  test_season=2021, model=ModelSpec(family="ridge", alpha=1.0),
                  features=("a", "b"), fitted={"coef": [0.5, -0.25], "intercept": 50.0},
                  predictions=((1, 51.5), (2, 49.0)), metrics={"n": 2, "mae": 1.25},
                  comparisons={"past_mean": {"n": 2, "diff": -0.5}})
    fields.update(over)
    return FoldResult(**fields)


def test_fold_result_seal_verifies_and_detects_tampering():
    sealed = _result().sealed()
    assert len(sealed.artifact_sha256) == 64 and sealed.verify()
    assert _result().sealed() == sealed  # deterministic
    tampered = sealed.model_copy(update={"predictions": ((1, 51.5), (2, 49.5))})
    assert not tampered.verify()
    again = FoldResult.model_validate_json(sealed.model_dump_json())
    assert again.verify()
