# Plan: Tuning lab Release C — governed tuning MVP
_By Claude + mckel, 2026-09-23. Executed inline, serially._

Design (contract, tracks, evaluation-standard mapping, tests):
[`../specs/2026-09-23-tuning-lab-release-c-design.md`](../specs/2026-09-23-tuning-lab-release-c-design.md).
This file is the build order; where the two differ, fix both.

## Status

| Task | Status |
| --- | --- |
| 1. C0 contract | Done 2026-09-23: 29 tests in `tests/test_tuning_spec.py` |
| 2. C2 features | Done 2026-09-23: 10 tests; real loader reproduces Release B (2021–25: 3,488 games, 3,480 opens; primary ridge − open +0.33) |
| 3. C3 folds and estimators | Done 2026-09-23: 11 tests; gates live in `acceptance_gates` beside `compare_outer` |
| 4. C1 cards | Done 2026-09-23: 5 tests; `RunSpec.notes` (unhashed) added so the card can state holdout status |
| 5. C4 worker | pending |
| 6. Join, real run, docs | pending |

## Global constraints

- Python in `.venv` (3.14); `optuna` 5.0.0, pydantic 2, scikit-learn 1.9, pandas 3.
- Package `models/tuning/`; outputs under `data/processed/tuning/` (gitignored). Stage
  `models/tuning/...` paths by name: another session has uncommitted `models/totals/*`
  deletions and `models/middle/`.
- Tests are in-memory or synthetic; none needs `CFB_DATA_ROOT` or the network.
- No ROI, CLV, hit-rate, or edge claims anywhere, including cards.
- Build order is C0, C2, C3, C1, C4, join. The plan of record lets C1–C4 run in any
  order after C0; C1 goes after C3 so its fixtures are real `FoldResult`s.
- One commit per task, pushed. Full suite before the first commit and after the last;
  the known baseline is 18 failed and 4 errors, all pre-existing.

## Task 1: C0 contract

- **Create:** `models/tuning/__init__.py`, `models/tuning/spec.py`, `tests/test_tuning_spec.py`.
- **Produces:**
  - Spec types: `DatasetSpec`, `FeatureRef`, `FeatureSetSpec`, `FoldSpec`, `SamplerSpec`,
    `PrunerSpec`, `SearchSpec`, `BootstrapSpec`, `AcceptanceSpec`, `Seeds`, `RunSpec`,
    `ModelSpec`, `FoldResult`.
  - Constant: `SEARCH_PROFILES["cfb_regularized_regression_v1"]` (§14 bounds).
  - Functions and members: `canonical_json(model, exclude=()) -> str`,
    `RunSpec.config_hash -> str`, `RunSpec.run_id(replicate=0) -> str`,
    `load_run_spec(path) -> RunSpec`, `FoldResult.sealed() -> FoldResult` (fills
    `artifact_sha256`), `FoldResult.verify() -> bool`.
- **Tests:**
  - equal hash for reordered keys and for reordered seasons
  - `created_at` is excluded from the hash
  - an unknown field is rejected at any level
  - an outer season inside the inner folds is rejected
  - a fold season outside the dataset is rejected
  - fewer than two inner folds is rejected
  - feature order changes the hash
  - a duplicate feature is rejected
  - the synthetic seed is required iff the source is synthetic
  - a non-Release-B bootstrap is rejected
  - `FoldResult` seal and verify round-trip; tampering fails verify

## Task 2: C2 features

- **Create:** `models/tuning/features.py`, `models/tuning/feature_sets/total_ratings_v1.json`,
  `tests/test_tuning_features.py`.
- **Consumes:**
  - Task 1 types.
  - `scripts.weekly_ratings_eval.load`, `load_opens`, `week_cutoffs`.
  - `scripts.weekly_ratings.forecast_total` and `Ratings`.
- **Produces:**
  - `CATALOG: dict[str, CatalogEntry]` and `BASELINES`.
  - `load_feature_set(path) -> FeatureSetSpec`.
  - `screen_features(frame, feature_set) -> (kept: list[str], dropped: dict[str, str])`,
    which is pure.
  - `load_frame(dataset, feature_set, data_root=None) -> (frame, LoadReport)`, where
    `LoadReport` holds `kept`, `dropped`, and `sources` (a list of path and sha256).
  - `synthetic_frame(dataset, feature_set) -> frame`.
  - Frame columns: `game_id, season, week, kickoff, decision_ts, target`, then each kept
    feature and `<feature>__as_of`, then `market_open, past_mean, ridge_v1_total`.
- **Tests:**
  - a row with `as_of > decision_ts` drops that feature only
  - a non-null value with a null `as_of` drops it
  - retrospective, provider-opaque (`open_total`), and prospective features are refused
  - a class or version mismatch against the catalog is refused
  - an unknown feature id is refused
  - the synthetic frame is deterministic and has the documented columns
  - the committed feature set loads and matches the catalog

## Task 3: C3 folds and estimators

- **Create:** `models/tuning/folds.py`, `models/tuning/estimators.py`, `tests/test_tuning_folds.py`.
- **Produces:**
  - `Fold`, with `fold_id`, `role`, `test_season`, `train_idx`, `test_idx`, and `bounds`.
  - `make_folds(fold_spec, frame) -> list[Fold]`, inner folds first.
  - `FitFailure(kind, message)`.
  - `build_pipeline(model, seed) -> Pipeline`.
  - `fit_fold(train, test, run_spec, model, fold_id) -> FoldResult` (sealed). Its features
    are the declared features present as columns.
  - `compare_outer(predictions, acceptance) -> dict`. The predictions frame has
    `season, week, game_id, target, y_hat` plus the baselines.
- **Tests:**
  - folds are chronological with no shared game
  - the embargo drops late training rows
  - inner folds come before outer ones
  - Ridge, Elastic Net, and Huber each fit and recover a synthetic linear signal
  - an all-null feature raises `FitFailure("data_validation")`
  - comparisons use only games where the baseline is present
  - the same inputs give an identical sealed `FoldResult`
  - `compare_outer` verdicts and calibration on a synthetic frame

## Task 4: C1 cards

- **Create:** `models/tuning/cards.py`, `tests/test_tuning_cards.py`.
- **Produces:** `render_card(run_spec, manifest, study_summary, outer_results, comparisons) -> str`
  and `BANNED_TERMS`.
- **Tests:**
  - the card carries the run id, config hash, feature-set id, every fold's bounds, all
    three baseline slots, and the requested, completed, pruned, and failed trial counts
  - the market slot is labeled descriptive
  - re-rendering is byte-identical
  - no banned term appears

## Task 5: C4 worker

- **Create:** `models/tuning/worker.py`, `tests/test_tuning_worker.py`.
- **Produces:**
  - `STATES` and `TRANSITIONS`.
  - `Job`.
  - `LabStore(root)`, with `submit(run_spec, code_sha256, replicate=0) -> Job`,
    `claim(worker_id, lease_s) -> Job | None`, `heartbeat`, `transition`,
    `request_cancel(run_id)`, `get(run_id)`, and `reap(now)`.
  - `code_fingerprint() -> str`.
  - `suggest_model(trial, search) -> ModelSpec`.
  - `work(root, worker_id, *, lease_s, heartbeat_interval, grace_period) -> Job | None`,
    which claims and runs one job to a terminal or retry state.
  - `publish_run(root, run_id, files) -> Path`.
- **Tests:**
  - legal and illegal transitions
  - submitting twice returns the same job
  - an expired lease leads to a retry, then to failed at the limit
  - cancel between folds leaves the job cancelled and the trial tagged
  - a changed code fingerprint refuses to resume
  - completed publishes a verified directory
  - the crash test: a subprocess crashes at trial 3 fold 2, then resumes; see the spec for
    the assertions

## Task 6: Join, real run, docs

- **Create:** `models/tuning/__main__.py`, `models/tuning/specs/total_ratings_v1.json`,
  `tests/test_tuning_join.py`.
- **Tests:** a synthetic spec run into two fresh roots gives the same `run_id` and
  byte-identical `predictions.csv` and `outer/*.json`.
- **Real run:** run the committed spec into two fresh roots in separate processes, then
  `cmp` the files. That is the go/no-go evidence.
- **Docs:**
  - Mark Release C in the plan of record. Its file carries another session's hunk, so
    stage it partially by binary patch.
  - Update this status table.
  - Write a finding doc only if the outer numbers change a downstream conclusion;
    otherwise record them as a line in the guide.
