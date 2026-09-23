"""Persistent Optuna worker with a leased job state machine (Release C, C4).

A job is one RunSpec (plus a replicate number) in `root/jobs.sqlite3`. A worker claims
it with a lease, extends the lease between folds, and runs the Optuna study stored in
`root/optuna.sqlite3` under the run id. Crashes are recovered two ways: an expired job
lease sends the job to retry_wait and back to the queue, and Optuna's heartbeat fails
the stale trial and re-queues its parameters under a new trial number, so no number is
reused and completed trials are never touched. A run resumes only with the same code
fingerprint and data hashes it started with. Artifacts are written to a temporary
directory, checksummed, verified, and renamed into `root/runs/<run_id>/` in one step.

States (plan §35.1): queued -> claimed -> running -> completed; claimed/running ->
retry_wait -> queued; claimed/running -> failed; queued/claimed/running ->
cancellation_requested -> cancelled.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import sqlite3
import subprocess
import time
import warnings
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

import numpy as np
import optuna
import pandas as pd

from models.tuning.cards import render_card
from models.tuning.estimators import FitFailure, acceptance_gates, compare_outer, fit_fold
from models.tuning.features import BASELINES, load_frame, source_paths
from models.tuning.folds import make_folds
from models.tuning.spec import SEARCH_PROFILES, ModelSpec, RunSpec, SearchSpec

REPO = Path(__file__).resolve().parents[2]
FINGERPRINTED = ("models/tuning/*.py", "models/tuning/feature_sets/*.json",
                 "scripts/weekly_ratings.py", "scripts/weekly_ratings_eval.py",
                 "scripts/pregame_replay_audit.py")
PACKAGES = ("optuna", "scikit-learn", "pandas", "numpy", "pydantic", "scipy")
STATES = ("queued", "claimed", "running", "completed", "retry_wait", "failed",
          "cancellation_requested", "cancelled")
TRANSITIONS = {
    "queued": {"claimed", "cancellation_requested"},
    "claimed": {"running", "retry_wait", "failed", "cancellation_requested"},
    "running": {"completed", "retry_wait", "failed", "cancellation_requested"},
    "retry_wait": {"queued"},
    "cancellation_requested": {"cancelled"},
    "completed": set(), "failed": set(), "cancelled": set(),
}
LEASED = ("claimed", "running", "cancellation_requested")
SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL UNIQUE,
    config_hash TEXT NOT NULL,
    attempt INTEGER NOT NULL,
    state TEXT NOT NULL,
    lease_owner TEXT,
    lease_expires_at REAL,
    retries INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL,
    retry_at REAL,
    error_kind TEXT,
    error TEXT,
    code_sha256 TEXT NOT NULL,
    sources_sha256 TEXT,
    spec_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    UNIQUE (config_hash, attempt)
);
CREATE TABLE IF NOT EXISTS job_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs (job_id),
    at REAL NOT NULL,
    from_state TEXT,
    to_state TEXT NOT NULL,
    detail TEXT
);
"""


class IllegalTransition(Exception):
    pass


class LeaseLost(Exception):
    pass


class Cancelled(Exception):
    pass


class RunRefused(Exception):
    """A deterministic refusal (code or data changed): failed at once, never retried."""

    def __init__(self, kind: str, message: str):
        super().__init__(f"{kind}: {message}")
        self.kind = kind


@dataclass(frozen=True)
class Job:
    job_id: int
    run_id: str
    config_hash: str
    attempt: int
    state: str
    lease_owner: str | None
    lease_expires_at: float | None
    retries: int
    max_retries: int
    retry_at: float | None
    error_kind: str | None
    error: str | None
    code_sha256: str
    sources_sha256: str | None
    spec_json: str
    created_at: float
    updated_at: float

    @property
    def spec(self) -> RunSpec:
        return RunSpec.model_validate_json(self.spec_json)


class LabStore:
    def __init__(self, root: str | Path, retry_backoff_s: float = 5.0):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "jobs.sqlite3"
        self.retry_backoff_s = retry_backoff_s
        con = sqlite3.connect(self.path, timeout=30)
        try:
            con.executescript(SCHEMA)
        finally:
            con.close()

    @contextmanager
    def _tx(self):
        con = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        con.row_factory = sqlite3.Row
        try:
            con.execute("BEGIN IMMEDIATE")
            yield con
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    @staticmethod
    def _row(con, where: str, args: tuple) -> Job | None:
        row = con.execute(f"SELECT * FROM jobs WHERE {where}", args).fetchone()
        return Job(**dict(row)) if row else None

    def _move(self, con, job_id: int, to: str, now: float, detail: str = "", **fields) -> None:
        state = con.execute("SELECT state FROM jobs WHERE job_id = ?", (job_id,)).fetchone()["state"]
        if to not in TRANSITIONS[state]:
            raise IllegalTransition(f"job {job_id}: {state} -> {to} is not allowed")
        sets = ", ".join(f"{k} = ?" for k in fields)
        con.execute(f"UPDATE jobs SET state = ?, updated_at = ?{', ' + sets if sets else ''} "
                    "WHERE job_id = ?", (to, now, *fields.values(), job_id))
        con.execute("INSERT INTO job_events (job_id, at, from_state, to_state, detail) "
                    "VALUES (?, ?, ?, ?, ?)", (job_id, now, state, to, detail))

    def _reap(self, con, now: float) -> None:
        for job in [Job(**dict(r)) for r in con.execute(
                "SELECT * FROM jobs WHERE state IN ('claimed', 'running', 'cancellation_requested', "
                "'retry_wait')")]:
            expired = job.lease_expires_at is not None and job.lease_expires_at < now
            if job.state == "cancellation_requested" and (expired or job.lease_owner is None):
                self._move(con, job.job_id, "cancelled", now, "cancel with no live worker",
                           lease_owner=None, lease_expires_at=None)
            elif job.state in ("claimed", "running") and expired:
                if job.retries < job.max_retries:
                    retries = job.retries + 1
                    self._move(con, job.job_id, "retry_wait", now, f"lease of {job.lease_owner} expired",
                               lease_owner=None, lease_expires_at=None, retries=retries,
                               retry_at=now + self.retry_backoff_s * 2 ** (retries - 1))
                else:
                    self._move(con, job.job_id, "failed", now, "lease expired past max_retries",
                               lease_owner=None, lease_expires_at=None, error_kind="lease_expired",
                               error=f"lease expired after {job.retries} retries")
        for r in con.execute("SELECT job_id FROM jobs WHERE state = 'retry_wait' AND retry_at <= ?",
                             (now,)).fetchall():
            self._move(con, r["job_id"], "queued", now, "backoff over")

    def submit(self, run_spec: RunSpec, code_sha256: str, replicate: int = 0) -> Job:
        """Same (config_hash, replicate) returns the existing job, whatever its state."""
        now = time.time()
        with self._tx() as con:
            job = self._row(con, "config_hash = ? AND attempt = ?", (run_spec.config_hash, replicate))
            if job:
                return job
            cur = con.execute(
                "INSERT INTO jobs (run_id, config_hash, attempt, state, max_retries, code_sha256, "
                "spec_json, created_at, updated_at) VALUES (?, ?, ?, 'queued', ?, ?, ?, ?, ?)",
                (run_spec.run_id(replicate), run_spec.config_hash, replicate,
                 run_spec.search.max_retry, code_sha256, run_spec.model_dump_json(), now, now))
            con.execute("INSERT INTO job_events (job_id, at, from_state, to_state, detail) "
                        "VALUES (?, ?, NULL, 'queued', 'submitted')", (cur.lastrowid, now))
            return self._row(con, "job_id = ?", (cur.lastrowid,))

    def claim(self, worker_id: str, lease_s: float, run_id: str | None = None,
              now: float | None = None) -> Job | None:
        now = time.time() if now is None else now
        with self._tx() as con:
            self._reap(con, now)
            where, args = "state = 'queued'", ()
            if run_id is not None:
                where, args = "state = 'queued' AND run_id = ?", (run_id,)
            job = self._row(con, f"{where} ORDER BY job_id LIMIT 1", args)
            if job is None:
                return None
            self._move(con, job.job_id, "claimed", now, f"claimed by {worker_id}",
                       lease_owner=worker_id, lease_expires_at=now + lease_s)
            return self._row(con, "job_id = ?", (job.job_id,))

    def heartbeat(self, job_id: int, worker_id: str, lease_s: float, now: float | None = None) -> str:
        """Extend the lease; returns the state so a worker sees a cancel request."""
        now = time.time() if now is None else now
        with self._tx() as con:
            job = self._row(con, "job_id = ?", (job_id,))
            if job.lease_owner != worker_id or job.state not in LEASED:
                raise LeaseLost(f"job {job_id} is {job.state}, lease owner {job.lease_owner}")
            con.execute("UPDATE jobs SET lease_expires_at = ?, updated_at = ? WHERE job_id = ?",
                        (now + lease_s, now, job_id))
            return job.state

    def transition(self, job_id: int, to: str, detail: str = "", **fields) -> Job:
        now = time.time()
        with self._tx() as con:
            self._move(con, job_id, to, now, detail, **fields)
            return self._row(con, "job_id = ?", (job_id,))

    def set_sources(self, job_id: int, sources_sha256: str) -> None:
        with self._tx() as con:
            con.execute("UPDATE jobs SET sources_sha256 = ? WHERE job_id = ?", (sources_sha256, job_id))

    def request_cancel(self, run_id: str) -> Job | None:
        now = time.time()
        with self._tx() as con:
            job = self._row(con, "run_id = ?", (run_id,))
            if job is None or job.state not in ("queued", "claimed", "running"):
                return job
            self._move(con, job.job_id, "cancellation_requested", now, "cancel requested")
            if job.state == "queued":
                self._move(con, job.job_id, "cancelled", now, "cancelled before any claim")
            return self._row(con, "job_id = ?", (job.job_id,))

    def get(self, run_id: str) -> Job | None:
        with self._tx() as con:
            return self._row(con, "run_id = ?", (run_id,))

    def jobs(self) -> list[Job]:
        with self._tx() as con:
            return [Job(**dict(r)) for r in con.execute("SELECT * FROM jobs ORDER BY job_id")]

    def events(self, job_id: int) -> list[dict]:
        with self._tx() as con:
            return [dict(r) for r in con.execute(
                "SELECT * FROM job_events WHERE job_id = ? ORDER BY event_id", (job_id,))]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def code_fingerprint() -> str:
    """sha256 over the code a run depends on, line endings normalized (git may rewrite them)."""
    h = hashlib.sha256()
    for pattern in FINGERPRINTED:
        for path in sorted(REPO.glob(pattern)):
            h.update(path.relative_to(REPO).as_posix().encode() + b"\0")
            h.update(path.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()


def storage_url(root: str | Path) -> str:
    return f"sqlite:///{(Path(root) / 'optuna.sqlite3').resolve().as_posix()}"


def suggest_model(trial: optuna.Trial, search: SearchSpec) -> ModelSpec:
    """Plan §14 conditional space: the family first, then only that family's parameters."""
    space = SEARCH_PROFILES[search.profile_id]
    family = trial.suggest_categorical("model_family", ["ridge", "elastic_net"])
    if family == "ridge":
        lo, hi, log = space["ridge"]["alpha"]
        return ModelSpec(family="ridge", alpha=trial.suggest_float("ridge_alpha", lo, hi, log=log))
    (alo, ahi, alog), (llo, lhi, llog) = space["elastic_net"]["alpha"], space["elastic_net"]["l1_ratio"]
    return ModelSpec(family="elastic_net",
                     alpha=trial.suggest_float("elasticnet_alpha", alo, ahi, log=alog),
                     l1_ratio=trial.suggest_float("elasticnet_l1_ratio", llo, lhi, log=llog))


def model_from_params(params: dict) -> ModelSpec:
    if params["model_family"] == "ridge":
        return ModelSpec(family="ridge", alpha=params["ridge_alpha"])
    return ModelSpec(family="elastic_net", alpha=params["elasticnet_alpha"],
                     l1_ratio=params["elasticnet_l1_ratio"])


def _before_fold(trial_number: int, fold_index: int) -> None:
    """Test hook: CFB_TUNING_CRASH_AT=<trial>:<fold> kills the process there, as a crash would."""
    if os.environ.get("CFB_TUNING_CRASH_AT") == f"{trial_number}:{fold_index}":
        os._exit(70)


def _study(root: Path, spec: RunSpec, run_id: str, heartbeat_interval: int,
           grace_period: int | None) -> optuna.Study:
    storage = optuna.storages.RDBStorage(
        url=storage_url(root), engine_kwargs={"connect_args": {"timeout": 30}},
        heartbeat_interval=heartbeat_interval, grace_period=grace_period,
        heartbeat_stale_trial_callback=optuna.storages.RetryHeartbeatStaleTrialCallback(
            max_retry=spec.search.max_retry))
    s, p = spec.search.sampler, spec.search.pruner
    return optuna.create_study(
        study_name=run_id, storage=storage, direction="minimize", load_if_exists=True,
        sampler=optuna.samplers.TPESampler(seed=spec.seeds.sampler, multivariate=s.multivariate,
                                           group=s.group, n_startup_trials=s.n_startup_trials),
        pruner=optuna.pruners.MedianPruner(n_startup_trials=p.n_startup_trials,
                                           n_warmup_steps=p.n_warmup_steps,
                                           interval_steps=p.interval_steps))


def _budget_used(study: optuna.Study) -> int:
    """Complete, pruned, and classified failures count; a stale trial's retry replaces it."""
    TS = optuna.trial.TrialState
    return sum(1 for t in study.get_trials(deepcopy=False)
               if t.state in (TS.COMPLETE, TS.PRUNED)
               or (t.state == TS.FAIL and "failure_kind" in t.user_attrs))


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True,
                              timeout=30).stdout.strip()
    except OSError:
        return ""


def study_summary(study: optuna.Study, spec: RunSpec) -> dict:
    TS = optuna.trial.TrialState
    trials = study.get_trials(deepcopy=False)
    failed = [t for t in trials if t.state == TS.FAIL]
    kinds: dict[str, int] = {}
    for t in failed:
        k = t.user_attrs.get("failure_kind", "stale_heartbeat")
        kinds[k] = kinds.get(k, 0) + 1
    complete = sorted((t for t in trials if t.state == TS.COMPLETE), key=lambda t: (t.value, t.number))
    if not complete:
        raise RunRefused("no_complete_trial", f"all {len(trials)} trials were pruned or failed")
    best = complete[0]
    return {
        "study_name": study.study_name, "requested": spec.search.n_trials,
        "completed": len(complete), "pruned": sum(t.state == TS.PRUNED for t in trials),
        "failed": len(failed), "failure_kinds": kinds,
        "sampler": {**spec.search.sampler.model_dump(), "seed": spec.seeds.sampler},
        "pruner": spec.search.pruner.model_dump(),
        "best": {"number": best.number, "value": best.value, "params": best.params},
        "selected": {"number": best.number, "reason": "the best complete trial; no override"},
        "top": [{"number": t.number, "value": t.value, "params": t.params} for t in complete[:5]],
    }


def trials_csv(study: optuna.Study) -> str:
    rows = []
    for t in study.get_trials(deepcopy=False):
        rows.append({"number": t.number, "state": t.state.name, "value": t.value,
                     "params": json.dumps(t.params, sort_keys=True),
                     "fold_values": json.dumps(t.user_attrs.get("fold_values", [])),
                     "failure_kind": t.user_attrs.get("failure_kind", ""),
                     "retried_from": optuna.storages.RetryHeartbeatStaleTrialCallback
                     .retried_trial_number(t)})
    return pd.DataFrame(rows).to_csv(index=False, lineterminator="\n")


def publish_run(root: Path, run_id: str, files: dict[str, str]) -> Path:
    """Write to a temporary directory, verify every checksum, then rename it into place."""
    runs = Path(root) / "runs"
    final = runs / run_id
    if final.exists():
        if verify_run(final):
            return final  # a crash after the rename but before `completed` was recorded
        raise RuntimeError(f"{final} exists and fails its checksums; not overwritten")
    runs.mkdir(parents=True, exist_ok=True)
    for stale in runs.glob(f"{run_id}.tmp-*"):
        shutil.rmtree(stale)
    tmp = runs / f"{run_id}.tmp-{os.getpid()}"
    sums = {}
    for rel, text in sorted(files.items()):
        path = tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        data = text.encode("utf-8")
        with open(path, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        sums[rel] = _sha256_bytes(data)
    (tmp / "checksums.sha256").write_bytes(
        "".join(f"{h}  {rel}\n" for rel, h in sorted(sums.items())).encode("utf-8"))
    if not verify_run(tmp):
        raise RuntimeError(f"checksum mismatch in {tmp}")
    os.replace(tmp, final)
    return final


def verify_run(run_dir: Path) -> bool:
    sums = Path(run_dir) / "checksums.sha256"
    if not sums.exists():
        return False
    for line in sums.read_text(encoding="utf-8").splitlines():
        h, rel = line.split("  ", 1)
        path = Path(run_dir) / rel
        if not path.exists() or _sha256_bytes(path.read_bytes()) != h:
            return False
    return True


def _sources_digest(paths: list[Path], data_root: Path | None) -> str:
    out = []
    for p in paths:
        rel = p.relative_to(data_root).as_posix() if data_root else p.as_posix()
        out.append({"path": rel, "sha256": _sha256_bytes(p.read_bytes())})
    return json.dumps(out, sort_keys=True)


def work(root: str | Path, worker_id: str, *, run_id: str | None = None, lease_s: float = 60.0,
         heartbeat_interval: int = 10, grace_period: int | None = None,
         retry_backoff_s: float = 5.0, data_root: Path | None = None) -> Job | None:
    """Claim one queued job and run it to completed, cancelled, failed, or retry_wait."""
    warnings.filterwarnings("ignore", category=optuna.exceptions.ExperimentalWarning)
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    root = Path(root)
    store = LabStore(root, retry_backoff_s=retry_backoff_s)
    job = store.claim(worker_id, lease_s, run_id=run_id)
    if job is None:
        return None
    try:
        _run(root, store, job, worker_id, lease_s, heartbeat_interval, grace_period, data_root)
        store.transition(job.job_id, "completed", "published")
    except Cancelled:
        store.transition(job.job_id, "cancelled", "stopped between folds",
                         lease_owner=None, lease_expires_at=None)
    except LeaseLost:
        pass  # a reaper or another worker owns the job now; leave it alone
    except RunRefused as e:
        store.transition(job.job_id, "failed", str(e), error_kind=e.kind, error=str(e),
                         lease_owner=None, lease_expires_at=None)
    except Exception as e:  # unexpected worker/system error: bounded retry
        current = store.get(job.run_id)
        if current.state in ("claimed", "running"):
            if current.retries < current.max_retries:
                retries = current.retries + 1
                store.transition(job.job_id, "retry_wait", repr(e), error_kind="worker_error",
                                 error=repr(e), retries=retries, lease_owner=None,
                                 lease_expires_at=None,
                                 retry_at=time.time() + retry_backoff_s * 2 ** (retries - 1))
            else:
                store.transition(job.job_id, "failed", repr(e), error_kind="worker_error",
                                 error=repr(e), lease_owner=None, lease_expires_at=None)
        elif current.state == "cancellation_requested":
            store.transition(job.job_id, "cancelled", f"cancelled after error {e!r}",
                             lease_owner=None, lease_expires_at=None)
    return store.get(job.run_id)


def _run(root: Path, store: LabStore, job: Job, worker_id: str, lease_s: float,
         heartbeat_interval: int, grace_period: int | None, data_root: Path | None) -> None:
    spec = job.spec
    if job.code_sha256 != code_fingerprint():
        raise RunRefused("code_changed", "the code fingerprint differs from the one this run "
                         "started with; submit a replicate instead")
    store.transition(job.job_id, "running", f"worker {worker_id}")

    def check() -> None:
        if store.heartbeat(job.job_id, worker_id, lease_s) == "cancellation_requested":
            raise Cancelled()

    real = spec.dataset.source == "cfb_release_b"
    if real and data_root is None:
        from cfb_paths import DATA_ROOT as data_root
    paths = source_paths(spec.dataset, Path(data_root)) if real else []
    sources = _sources_digest(paths, Path(data_root) if real else None)
    if job.sources_sha256 is None:
        store.set_sources(job.job_id, sources)
    elif job.sources_sha256 != sources:
        raise RunRefused("data_changed", "source files differ from the ones this run started with")
    frame, report = load_frame(spec.dataset, spec.feature_set, data_root)
    if real and sorted(map(str, report.sources)) != sorted(map(str, paths)):
        raise RunRefused("data_changed", "the loader read files outside the recorded sources")
    check()

    folds = make_folds(spec.folds, frame)
    inner = [f for f in folds if f.role == "inner"]
    outer = [f for f in folds if f.role == "outer"]
    study = _study(root, spec, job.run_id, heartbeat_interval, grace_period)

    def objective(trial: optuna.Trial) -> float:
        model = suggest_model(trial, spec.search)
        values = []
        for i, fold in enumerate(inner):
            _before_fold(trial.number, i)
            try:
                check()
            except Cancelled:
                trial.set_user_attr("failure_kind", "cancelled")
                raise
            try:
                r = fit_fold(frame.loc[fold.train_idx], frame.loc[fold.test_idx], spec, model,
                             fold.fold_id, run_id=job.run_id)
            except FitFailure as e:
                trial.set_user_attr("failure_kind", e.kind)
                trial.set_user_attr("failure", str(e))
                raise
            values.append(r.metrics[spec.search.objective])
            trial.set_user_attr("fold_values", values)
            if r.warnings:
                trial.set_user_attr("warnings", list(r.warnings))
            running = float(np.mean(values))
            trial.report(running, i)
            if trial.should_prune():
                raise optuna.TrialPruned()
        return running

    while (left := spec.search.n_trials - _budget_used(study)) > 0:
        study.optimize(objective, n_trials=left, catch=(FitFailure,))

    summary = study_summary(study, spec)
    model = model_from_params(summary["best"]["params"])
    results, preds = [], []
    for fold in outer:
        check()
        test = frame.loc[fold.test_idx]
        r = fit_fold(frame.loc[fold.train_idx], test, spec, model, fold.fold_id, run_id=job.run_id)
        results.append(r)
        cols = ["season", "week", "game_id", "target", *[b for b in BASELINES if b in test]]
        preds.append(test[cols].assign(y_hat=[p for _, p in r.predictions]))
    predictions = pd.concat(preds, ignore_index=True)[
        ["season", "week", "game_id", "target", "y_hat", *[b for b in BASELINES if b in frame]]]
    comparisons = compare_outer(predictions, spec.acceptance)
    manifest = {
        "run_id": job.run_id, "config_hash": spec.config_hash, "replicate": job.attempt,
        "spec_id": spec.spec_id, "git_sha": _git("rev-parse", "--short=12", "HEAD"),
        # Only the fingerprinted files: other work elsewhere in the tree must not mark a run dirty.
        "git_dirty": bool(_git("status", "--porcelain", "--", *FINGERPRINTED)),
        "code_sha256": job.code_sha256, "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": {d: metadata.version(d) for d in PACKAGES},
        "sources": json.loads(sources),
        "features": {"kept": report.kept, "dropped": report.dropped},
        "folds": [{"fold_id": f.fold_id, "role": f.role, "test_season": f.test_season,
                   "bounds": f.bounds} for f in folds],
        "gates": acceptance_gates(comparisons, spec.acceptance, n_features=len(report.kept),
                                  fold_warnings=[w for r in results for w in r.warnings],
                                  dropped=report.dropped),
        "reproduce": f"python -m models.tuning run --spec runs/{job.run_id}/run_spec.json "
                     "--root <fresh directory>",
        "storage": "optuna.sqlite3 (study name = run id)",
        "worker_id": worker_id, "retries": store.get(job.run_id).retries,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    files = {
        "run_spec.json": spec.model_dump_json(indent=2) + "\n",
        "manifest.json": json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n",
        "folds.json": json.dumps(manifest["folds"], indent=2) + "\n",
        "trials.csv": trials_csv(study),
        "predictions.csv": predictions.to_csv(index=False, lineterminator="\n"),
        "comparisons.json": json.dumps(comparisons, indent=2, sort_keys=True, default=str) + "\n",
        "card.md": render_card(spec, manifest, summary, results, comparisons),
        **{f"outer/{r.fold_id}.json": r.model_dump_json(indent=2) + "\n" for r in results},
    }
    check()
    publish_run(root, job.run_id, files)
