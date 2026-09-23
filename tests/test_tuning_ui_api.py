"""The GUI's guardrails live in `validate`, so the UI cannot route around them."""
import json
import sqlite3
from pathlib import Path

from models.tuning.fingerprint import code_fingerprint
from models.tuning.spec import RunSpec, load_run_spec
from models.tuning.ui.api import catalog, validate
from models.tuning.worker import LabStore

SPEC = Path(__file__).resolve().parents[1] / "models" / "tuning" / "specs" / "total_ratings_v1.json"


def _doc(**edit) -> dict:
    d = json.loads(SPEC.read_text(encoding="utf-8"))
    for path, value in edit.items():
        *parents, leaf = path.split("__")
        node = d
        for p in parents:
            node = node[p]
        node[leaf] = value
    return d


def _check(tmp_path, doc: dict) -> dict:
    return validate(json.dumps(doc), tmp_path)


def _set_state(root: Path, run_id: str, state: str, code: str) -> None:
    con = sqlite3.connect(root / "jobs.sqlite3")
    con.execute("UPDATE jobs SET state = ?, code_sha256 = ? WHERE run_id = ?", (state, code, run_id))
    con.commit()
    con.close()


def test_the_committed_spec_validates_to_its_run_id_with_a_spent_holdout_warning(tmp_path):
    out = _check(tmp_path, _doc())
    assert out["ok"] and out["run_id"] == "run-de1927346ab0"
    assert out["launch"]["replicate"] == 0 and out["launch"]["existing_state"] is None
    assert out["holdout"]["used_outside_lab"] == [2021, 2022, 2023, 2024, 2025]
    assert any("descriptive" in w for w in out["warnings"])


def test_blocking_errors_lock_sealed_seasons_and_refused_features(tmp_path):
    lock = _check(tmp_path, _doc(folds__outer_test_seasons=[2019]))
    assert not lock["ok"] and any("confirmation lock" in e for e in lock["errors"])
    sealed = _check(tmp_path, _doc(dataset__seasons=list(range(2014, 2027)),
                                   folds__outer_test_seasons=[2026]))
    assert not sealed["ok"] and any("sealed" in e for e in sealed["errors"])
    d = _doc()
    d["feature_set"]["features"].append({"id": "open_total", "version": 1,
                                         "availability_class": "provider_opaque"})
    opaque = _check(tmp_path, d)
    assert not opaque["ok"] and any("provider_opaque: benchmark-only" in e for e in opaque["errors"])
    assert not _check(tmp_path, _doc(folds__bogus=1))["ok"]  # unknown fields are rejected


def test_prior_trials_on_the_same_outer_seasons_are_counted_and_synthetic_runs_are_not(tmp_path):
    store = LabStore(tmp_path)
    store.submit(RunSpec.model_validate(_doc(search__n_trials=7)), "code")
    synth = _doc(search__n_trials=5)
    synth["dataset"] |= {"source": "synthetic_v1", "synthetic_seed": 1}
    store.submit(RunSpec.model_validate(synth), "code")
    h = _check(tmp_path, _doc())["holdout"]
    assert h["prior_trials"] == 7 and len(h["prior_runs"]) == 1


def test_the_launch_skips_stale_replicates_and_refuses_a_run_in_flight(tmp_path):
    spec = load_run_spec(SPEC)
    LabStore(tmp_path).submit(spec, "old-code")
    _set_state(tmp_path, spec.run_id(), "completed", "old-code")
    launch = _check(tmp_path, _doc())["launch"]
    assert launch["replicate"] == 1 and launch["skipped"][0]["same_code"] is False
    _set_state(tmp_path, spec.run_id(), "completed", code_fingerprint())
    same = _check(tmp_path, _doc())
    assert same["launch"]["replicate"] == 0 and any("already completed" in w for w in same["warnings"])
    _set_state(tmp_path, spec.run_id(), "running", "old-code")
    busy = _check(tmp_path, _doc())
    assert not busy["ok"] and any("is running" in e for e in busy["errors"])


def test_launch_revalidates_the_exact_file_and_refuses_an_invalid_one(tmp_path):
    from models.tuning.ui import actions

    bad = actions.write_draft(tmp_path, _doc(folds__outer_test_seasons=[2019]))
    assert actions.write_draft(tmp_path, _doc(folds__outer_test_seasons=[2019])) == bad  # by content
    try:
        actions.launch(tmp_path, bad, 0)
        raise AssertionError("an invalid draft launched")
    except actions.Refused as e:
        assert "confirmation lock" in str(e)
    assert not (tmp_path / "logs").exists() and not (tmp_path / "jobs.sqlite3").exists()


def test_trials_decode_categorical_parameters(tmp_path):
    import optuna

    from models.tuning.ui.data import trials

    study = optuna.create_study(study_name="run-x", storage=f"sqlite:///{(tmp_path / 'optuna.sqlite3').as_posix()}")
    study.optimize(lambda t: t.suggest_float("a", 0.1, 1.0) if t.suggest_categorical(
        "model_family", ["ridge", "elastic_net"]) else 0.0, n_trials=3)
    tr = trials(tmp_path, "run-x")
    assert len(tr) == 3 and set(tr["model_family"]) <= {"ridge", "elastic_net"}
    assert (tr["state"] == "COMPLETE").all() and tr["objective"].notna().all()


def test_catalog_marks_only_historical_features_eligible():
    c = catalog()
    eligible = {f["id"]: f["eligible"] for f in c["features"]}
    assert eligible["rv1_total"] and not eligible["open_total"] and c["sealed"] == [2026]
