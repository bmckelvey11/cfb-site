"""Release C, C4: job state machine, leases, cancel, fingerprint, publish, crash-resume.

Synthetic data only; the crash test runs the worker in a subprocess and kills it with an
injected os._exit at a chosen trial and fold, so it is deterministic.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import optuna
import pytest

from models.tuning import worker
from models.tuning.spec import RunSpec
from models.tuning.worker import IllegalTransition, LabStore, code_fingerprint, work

REPO = Path(__file__).resolve().parents[1]
FEATURES = ["rv1_total", "rv1_off_home", "rv1_def_away", "min_prior_games"]


def _spec(n_trials=6, **search) -> RunSpec:
    return RunSpec.model_validate({
        "spec_id": "worker_fixture", "created_at": "2026-09-23T00:00:00Z", "created_by": "test",
        "dataset": {"source": "synthetic_v1", "snapshot": "fx", "synthetic_seed": 11,
                    "seasons": [2014, 2015, 2016, 2017, 2018, 2021, 2022]},
        "feature_set": {"feature_set_id": "fx", "version": 1, "features": [
            {"id": f, "version": 1, "availability_class": "historical_replayable"} for f in FEATURES]},
        "folds": {"inner_test_seasons": [2016, 2017, 2018], "outer_test_seasons": [2021, 2022]},
        "search": {"profile_id": "cfb_regularized_regression_v1", "n_trials": n_trials,
                   "pruner": {"n_startup_trials": 50, "n_warmup_steps": 1},
                   "sampler": {"n_startup_trials": 3}, **search},
        "acceptance": {"baselines": ["market_open", "past_mean", "ridge_v1_total"]},
    })


def _states(store: LabStore, job_id: int) -> list[str]:
    return [e["to_state"] for e in store.events(job_id)]


def test_transitions_follow_the_state_machine(tmp_path):
    store = LabStore(tmp_path)
    job = store.submit(_spec(), code_fingerprint())
    assert job.state == "queued" and job.run_id == _spec().run_id()
    with pytest.raises(IllegalTransition):
        store.transition(job.job_id, "completed")
    claimed = store.claim("w1", lease_s=30)
    store.transition(claimed.job_id, "running")
    store.transition(claimed.job_id, "completed")
    with pytest.raises(IllegalTransition):
        store.transition(claimed.job_id, "running")
    assert _states(store, job.job_id) == ["queued", "claimed", "running", "completed"]


def test_submit_is_idempotent_and_replicates_are_separate_runs(tmp_path):
    store = LabStore(tmp_path)
    a = store.submit(_spec(), code_fingerprint())
    assert store.submit(_spec(), code_fingerprint()).job_id == a.job_id
    r1 = store.submit(_spec(), code_fingerprint(), replicate=1)
    assert r1.job_id != a.job_id and r1.run_id == a.run_id + "-r1"


def test_expired_lease_is_retried_then_failed_at_the_limit(tmp_path):
    store = LabStore(tmp_path, retry_backoff_s=0.0)
    job = store.submit(_spec(max_retry=1), code_fingerprint())
    store.claim("w1", lease_s=10, now=0.0)
    again = store.claim("w2", lease_s=10, now=20.0)  # w1's lease expired at 10
    assert again.job_id == job.job_id and again.lease_owner == "w2" and again.retries == 1
    assert store.claim("w3", lease_s=10, now=40.0) is None  # second expiry: over the limit
    final = store.get(job.run_id)
    assert final.state == "failed" and final.error_kind == "lease_expired"
    assert _states(store, job.job_id) == ["queued", "claimed", "retry_wait", "queued", "claimed",
                                          "failed"]


def test_cancel_a_queued_job(tmp_path):
    store = LabStore(tmp_path)
    job = store.submit(_spec(), code_fingerprint())
    assert store.request_cancel(job.run_id).state == "cancelled"
    assert store.claim("w1", lease_s=30) is None


def test_cancel_between_folds_stops_the_study(tmp_path, monkeypatch):
    store = LabStore(tmp_path)
    spec = _spec()
    store.submit(spec, code_fingerprint())

    def cancel_at_trial_one(trial_number, fold_index):
        if (trial_number, fold_index) == (1, 1):
            store.request_cancel(spec.run_id())

    monkeypatch.setattr(worker, "_before_fold", cancel_at_trial_one)
    job = work(tmp_path, "w1", lease_s=30)
    assert job.state == "cancelled"
    trials = optuna.load_study(study_name=spec.run_id(), storage=worker.storage_url(tmp_path)).trials
    assert trials[1].state == optuna.trial.TrialState.FAIL
    assert trials[1].user_attrs["failure_kind"] == "cancelled"
    assert not (tmp_path / "runs" / spec.run_id()).exists()


def test_changed_code_refuses_to_resume(tmp_path):
    store = LabStore(tmp_path)
    store.submit(_spec(), "0" * 64)
    job = work(tmp_path, "w1", lease_s=30)
    assert job.state == "failed" and job.error_kind == "code_changed"


def test_completed_run_publishes_a_verified_directory(tmp_path):
    spec = _spec()
    LabStore(tmp_path).submit(spec, code_fingerprint())
    job = work(tmp_path, "w1", lease_s=30)
    assert job.state == "completed", job.error
    run_dir = tmp_path / "runs" / spec.run_id()
    assert worker.verify_run(run_dir)
    names = {p.relative_to(run_dir).as_posix() for p in run_dir.rglob("*") if p.is_file()}
    assert {"run_spec.json", "manifest.json", "folds.json", "trials.csv", "predictions.csv",
            "comparisons.json", "card.md", "checksums.sha256",
            "outer/outer-2021.json", "outer/outer-2022.json"} <= names
    assert spec.run_id() in (run_dir / "card.md").read_text(encoding="utf-8")
    trials = (run_dir / "trials.csv").read_text(encoding="utf-8").strip().splitlines()
    assert len(trials) == 1 + spec.search.n_trials
    assert work(tmp_path, "w2", lease_s=30) is None  # nothing left to claim


CHILD = """
import sys
from models.tuning.spec import load_run_spec
from models.tuning.worker import LabStore, code_fingerprint, work
root, spec = sys.argv[1], load_run_spec(sys.argv[2])
LabStore(root, retry_backoff_s=0.0).submit(spec, code_fingerprint())
job = work(root, sys.argv[3], lease_s=1, heartbeat_interval=1, grace_period=1,
           retry_backoff_s=0.0)
print(job.state)
"""


def _child(root, spec_path, worker_id, crash_at=None):
    env = {k: v for k, v in os.environ.items() if k != "CFB_TUNING_CRASH_AT"}
    if crash_at:
        env["CFB_TUNING_CRASH_AT"] = crash_at
    return subprocess.run([sys.executable, "-c", CHILD, str(root), str(spec_path), worker_id],
                          cwd=REPO, env=env, capture_output=True, text=True, timeout=180)


def test_a_crash_mid_trial_resumes_without_corrupting_the_study(tmp_path):
    spec = _spec(n_trials=6)
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(spec.model_dump_json(), encoding="utf-8")
    root = tmp_path / "lab"

    crashed = _child(root, spec_path, "w1", crash_at="3:1")
    assert crashed.returncode == 70, crashed.stderr
    storage = worker.storage_url(root)
    before = optuna.load_study(study_name=spec.run_id(), storage=storage).trials
    assert [t.state for t in before[:3]] == [optuna.trial.TrialState.COMPLETE] * 3
    assert before[3].state == optuna.trial.TrialState.RUNNING

    time.sleep(2.5)  # past the 1 s heartbeat grace period and the 1 s job lease
    resumed = _child(root, spec_path, "w2")
    assert resumed.returncode == 0 and resumed.stdout.strip() == "completed", resumed.stderr

    after = optuna.load_study(study_name=spec.run_id(), storage=storage).trials
    for old, new in zip(before[:3], after[:3]):
        assert (new.number, new.state, new.params, new.value) == \
            (old.number, old.state, old.params, old.value)
    assert after[3].state == optuna.trial.TrialState.FAIL
    retried = [t for t in after[4:] if t.params == before[3].params]
    assert retried and retried[0].state == optuna.trial.TrialState.COMPLETE
    assert len({t.number for t in after}) == len(after)
    done = [t for t in after if t.state in (optuna.trial.TrialState.COMPLETE,
                                            optuna.trial.TrialState.PRUNED)]
    assert len(done) == spec.search.n_trials
    store = LabStore(root)
    job = store.get(spec.run_id())
    assert job.state == "completed" and job.retries == 1
    assert "retry_wait" in _states(store, job.job_id)
    assert worker.verify_run(root / "runs" / spec.run_id())
