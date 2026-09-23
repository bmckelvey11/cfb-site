# Tuning lab Release C: governed tuning MVP — design

**Status:** approved 2026-09-23. Scope, dependency, and data window chosen by the user;
the rest are Claude's defaults, listed under *Decisions*.
**Builds on:** [`docs/model-tuning-lab-plan.md`](../../model-tuning-lab-plan.md) §40
Release C (plan of record), §14 (search profile), §15 (study design), §24 (contracts,
reproducibility, storage), §27.5 (availability classes), §35 (worker reliability).
Features come from Release B's as-of ratings
([`docs/weekly-ratings-2026-09-23.md`](../../weekly-ratings-2026-09-23.md)).
**Review:** none cross-model (Codex sandbox error 206 is unresolved). An advisor pass
shaped the evaluation-standard mapping, the Optuna 5.0 API names, the code fingerprint,
list canonicalization, and the deterministic crash test.

## Goal

A CLI that runs a fixed feature set through chronological, nested validation inside a
persistent Optuna worker and writes a model card, such that:

- **Go/no-go:** any run is reproducible from one run ID in a clean environment, and
  killing the worker mid-trial does not corrupt study state.

Forecast skill is *not* the release gate. The join run on real data is reported, but its
numbers are descriptive (see *Evaluation standard*).

## Decisions

| Decision | Choice | By |
| --- | --- | --- |
| Scope | Full Release C: C0, then C1–C4, then the join; built serially, one commit per track | user |
| Dependency | `optuna` 5.0.0 from PyPI into `.venv`; `requirements.txt` pins `>=5,<6` (`da92b06`); lock not regenerated (stale, as in `b89a8e2`) | user |
| Join data | Inner (tuning) folds test 2015–2019; outer folds test 2021–2025; 2020 excluded | user |
| Spec typing | pydantic v2, `extra="forbid"`, `frozen=True` | Claude |
| Storage | SQLite job table (stdlib `sqlite3`) and Optuna `RDBStorage` on SQLite, both under `data/processed/tuning/`; §24.4 allows SQLite for a single host | Claude |
| Feature source | Release B `weekly_ratings_snapshots.csv` (`ridge_v1` rows), sha256 recorded; not refit per run | Claude |
| Objective | Mean inner-fold MAE (§17 allows MAE or RMSE; MAE matches the Release B and priors verdicts) | Claude |
| Serialization | Canonical JSON for specs, fold results, and fitted linear models; CSV for tables. No joblib, no parquet (`pyarrow` is not installed) | Claude |
| `fit_fold` signature | `fit_fold(train, test, run_spec, model)`: the plan's three-argument form has nowhere to carry a trial's hyperparameters | Claude |

## C0 — shared contract (`models/tuning/spec.py`)

Every spec is a frozen pydantic model that rejects unknown fields.

- **`DatasetSpec`:** `source` (`cfb_release_b` | `synthetic_v1`), `snapshot` (label),
  `grain` (`game`), `target` (`total`, Release B's definition), `decision_time`
  (`week_cutoff`: a week's earliest kickoff, as in Release B), `seasons`,
  `population` (`fbs_vs_fbs_week2plus`), `synthetic_seed` (required for
  `synthetic_v1`, forbidden otherwise). The plan names `DatasetSpec.decision_ts`; a
  multi-week dataset has no single decision time, so the spec holds the *policy* and
  every row carries its own `decision_ts`.
- **`FeatureRef`:** `id`, `version`, `availability_class`, one of the five §27.5
  classes: `historical_replayable`, `snapshot_dependent`, `prospective_only`,
  `retrospective_descriptive`, `provider_opaque`.
- **`FeatureSetSpec`:** `feature_set_id`, `version`, `features` (ordered; duplicates
  rejected).
- **`FoldSpec`:** `profile` (`season_holdout`), `inner_test_seasons`,
  `outer_test_seasons`, `exclude_seasons`, `group_key` (`game_id`), `embargo_days`
  (default 0). Every fold trains on all dataset seasons before its test season.
- **`SearchSpec`:** `profile_id` (`cfb_regularized_regression_v1`; the §14 bounds live in
  code under that id), `n_trials`, `objective` (`mae` | `rmse`), `sampler` (TPE:
  `multivariate`, `group`, `n_startup_trials`), `pruner` (median: `n_startup_trials`,
  `n_warmup_steps`, `interval_steps`), `max_retry`.
- **`AcceptanceSpec`:** `baselines` (subset of `market_open`, `past_mean`,
  `ridge_v1_total`), `bootstrap` (`unit` season-week, `draws`, `seed`; validated equal
  to Release B's 10,000 draws and seed 20260922, the only bootstrap `compare_outer`
  reuses), `verdict_rule` (`classify_verdict_v1`), `bias_tolerance` (points),
  `max_features`.
- **`Seeds`:** `split`, `model`, `sampler`.
- **`RunSpec`:** `schema_version` (1), `spec_id`, `created_at`, `created_by`, `notes`
  (free text for the card, such as holdout status), the five specs, `seeds`.
- **`ModelSpec`:** `family` (`ridge` | `elastic_net` | `huber`) and its parameters.
- **`FoldResult`:** `run_id`, `config_hash`, `fold_id`, `role` (`inner` | `outer`),
  `model`, fitted parameters (imputer medians, scaler mean/scale, coefficients,
  intercept), `predictions` (`game_id`, `y_hat`), `metrics`, `comparisons`, `warnings`,
  `artifact_sha256`.

**Canonical form and hash.**

- Set-like lists are sorted and de-duplicated in validators: `seasons`, the fold season
  lists, `exclude_seasons`, and `baselines`.
- Feature order is kept as declared, because it is the design matrix's column order.
- `config_hash` = sha256 of `json.dumps(spec, sort_keys=True, separators=(",", ":"))`,
  excluding `created_at`, `created_by`, and `notes`.
- `run_id` = `run-` + the first 12 hex characters of the hash, plus `-r<k>` for a
  replicate `k ≥ 1`.

**Validation.** `RunSpec` rejects:

- an outer test season inside any inner fold's train or test seasons (the confirmation
  lock);
- a fold season outside `DatasetSpec.seasons`;
- an inner profile with fewer than two folds, because the pruner needs two;
- `len(features) > max_features`.

`FoldResult.artifact_sha256` is the sha256 of its own canonical JSON with that field
removed.

## C1 — cards (`models/tuning/cards.py`)

`render_card(run_spec, manifest, study_summary, outer_results, comparisons) -> str` is a
pure function with no clock and no I/O, so the same inputs give byte-identical Markdown.

Sections, a subset of §20:

- purpose and decision time
- target and population
- data sources with sha256s
- features, with versions, classes, and any dropped features and why
- fold bounds for every inner and outer fold
- Optuna provenance: study name, storage path without secrets, sampler and pruner
  config, trials requested, completed, pruned, and failed with failure kinds, and best
  vs selected trial
- selected model and hyperparameters
- baseline comparison slots
- per-fold and per-season metrics
- calibration slope and intercept
- acceptance gates, pass or fail
- limitations
- checksums and the reproduction command

The market slot is always labeled *descriptive, untimed vendor open*. A test asserts that
the card never contains "ROI", "CLV", "hit rate", or "edge".

## C2 — features (`models/tuning/features.py`, `models/tuning/feature_sets/`)

**Catalog.** `CATALOG` maps each feature id to its version, class, and description.

| id | class | meaning |
| --- | --- | --- |
| `rv1_off_home`, `rv1_def_home`, `rv1_pace_home` | historical_replayable | `ridge_v1` O, D, P of the home team as of the week cutoff |
| `rv1_off_away`, `rv1_def_away`, `rv1_pace_away` | historical_replayable | same, away team |
| `rv1_total` | historical_replayable | `forecast_total` from that snapshot |
| `min_prior_games` | historical_replayable | fewer of the two teams' prior games in the snapshot |
| `neutral` | historical_replayable | neutral-site flag from the schedule |
| `open_total` | provider_opaque | Bovada `overUnderOpen`; untimed, so benchmark-only |

**Feature set.** `feature_sets/total_ratings_v1.json` holds the nine replayable features
in the order above.

**Loader.** `load_frame(dataset, feature_set) -> (frame, report)`.

- **Frame columns:** `game_id`, `season`, `week`, `kickoff`, `decision_ts`, `target`,
  each feature, a per-feature `as_of_ts`, and the baseline columns `market_open`,
  `past_mean`, and `ridge_v1_total`.
- **Games:** Release B's `load` over 2014–2025 (2020 loaded only for `past_mean`,
  matching Release B's train mean).
- **Cutoffs:** `week_cutoffs`.
- **Ratings:** the snapshot CSV, filtered to `method == "ridge_v1"`.
- **Opens:** `load_opens`.

The loader drops a declared feature, with the reason recorded in `report`, when:

- its catalog class or version disagrees with the feature set;
- its class is not `historical_replayable`, which in a retrospective run blocks
  prospective-only, retrospective-descriptive, provider-opaque, and (until a coverage
  check exists) snapshot-dependent features;
- any row has a non-null value whose `as_of_ts` is null or later than that row's
  `decision_ts`. This fails closed.

**Synthetic source.** `synthetic_frame(dataset)` builds a deterministic frame with the
same columns from `synthetic_seed`, for worker and join tests without `CFB_DATA_ROOT`.

On real data the as-of check passes trivially, because snapshot `as_of_ts` equals the
week cutoff by construction. The tests are the proof. They cover:

- a leaking row (`as_of > decision_ts`);
- a retrospective-descriptive feature;
- `open_total` refused as provider-opaque.

## C3 — folds and estimators (`models/tuning/folds.py`, `models/tuning/estimators.py`)

**Folds.** `make_folds(fold_spec, frame) -> list[Fold]`.

- **Fold ids:** `inner-2015` … `inner-2019` and `outer-2021` … `outer-2025`.
- **Indices:** train and test.
- **Bounds:** first and last kickoff of train and of test.
- **Asserted:** no `game_id` on both sides; every train kickoff is before the first test
  `decision_ts` minus `embargo_days`.

**Pipeline.** `build_pipeline(model, seed)` = median imputer, then standard scaler, then
the estimator:

| Estimator | Settings |
| --- | --- |
| `Ridge(alpha)` | |
| `ElasticNet(alpha, l1_ratio, random_state=seed, max_iter=10_000)` | |
| `HuberRegressor(epsilon, alpha, max_iter=1_000)` | Fixed-parameter only; not in the search profile |

**`fit_fold(train, test, run_spec, model) -> FoldResult`.**

- **Fails** with a typed `FitFailure(kind)` on:
  - an all-null training feature (`data_validation`)
  - non-finite predictions (`numerical_instability`)
- **Records** warnings, such as convergence, in `warnings`.
- **Metrics:** `n`, `mae`, `rmse`, and `bias` (mean of prediction minus actual).
- **`comparisons`:** for each baseline present in `test`, the paired `n`, model MAE,
  baseline MAE, and their difference, on the same games.

**`compare_outer(predictions, acceptance) -> dict`** pools the outer folds.

- It reports the paired MAE difference versus each baseline with a week-cluster
  bootstrap, the minimum detectable effect (MDE), and `classify_verdict`. These reuse
  `scripts.weekly_ratings_eval`.
- It adds per-season differences, calibration slope and intercept (OLS of actual on
  prediction), bias, and the gate results.

## C4 — worker (`models/tuning/worker.py`)

**Store.** `LabStore(root)` lives at `root/jobs.sqlite3`.

- A `jobs` row holds: `job_id`, `run_id`, `config_hash`, `attempt`, `state`,
  `lease_owner`, `lease_expires_at`, `retries`, `max_retries`, `error_kind`, `error`,
  `code_sha256`, `sources_sha256`, `spec_json`, and timestamps.
- `(config_hash, attempt)` is unique, where `attempt` is the replicate number (0 for the
  original).
- `retries` is the separate count of lease-expiry retries.

**States (§35.1).**

- **Transitions:**
  - `queued → claimed → running → completed`
  - `claimed/running → retry_wait → queued`
  - `claimed/running → failed`
  - `queued/claimed/running → cancellation_requested → cancelled`
- An illegal transition raises.
- Claims use `BEGIN IMMEDIATE`.
- A claimed or running job whose lease has expired moves to `retry_wait`, or to
  `failed` once `retries ≥ max_retries`.
- `retry_wait` returns to `queued` when its backoff ends.

**Idempotency and fingerprints.**

- `submit(run_spec, replicate=0)` returns the existing job for the same key.
- The code fingerprint is the sha256 of `models/tuning/*.py`, the feature-set files, and
  the three Release B scripts the loader imports. It is stored at submit.
- Source sha256s are stored at first load.
- Resuming, or returning a completed run, requires both to match the current ones.
  Otherwise the job fails with `code_changed` or `data_changed`, and the user must
  replicate.

**Study.**

- `optuna.create_study(study_name=run_id, storage=RDBStorage("sqlite:///root/optuna.sqlite3", heartbeat_interval, grace_period, heartbeat_stale_trial_callback=RetryHeartbeatStaleTrialCallback(max_retry)), sampler=TPESampler(seed=seeds.sampler, multivariate=True, group=True, n_startup_trials=…), pruner=MedianPruner(…), direction="minimize", load_if_exists=True)`
- These are the Optuna 5.0 names, checked against the installed package. The old
  `failed_trial_callback` and `RetryFailedTrialCallback` are deprecated. Heartbeats work
  only under `optimize()`, so the worker never uses ask/tell.

**Objective.**

- For each inner fold, call `fit_fold`, report the running mean objective, and allow
  pruning from the second fold on.
- Between folds, extend the job lease, and check for cancellation (which sets
  `failure_kind=cancelled` on the trial).
- Tag a `FitFailure` with its kind and count it in the budget.
- The budget counts `COMPLETE`, `PRUNED`, and tagged `FAIL`. A stale-failed trial is not
  counted: the retry callback re-queues its parameters under a new trial number, so a
  number is never reused.

**Publish.**

- The selected trial is the best complete trial; the card states the selection matches
  the best.
- Refit each outer fold with the selected model, checking cancellation between folds.
- Write to `root/runs/<run_id>.tmp-<pid>/`:
  - `run_spec.json` and `manifest.json` (git sha, dirty flag, Python and package
    versions, code fingerprint, source sha256s, seeds)
  - `folds.json` and `trials.csv` (every trial with its state, parameters, value,
    per-fold metrics, and failure kind)
  - one `outer/<fold_id>.json` per outer fold, as `FoldResult`
  - `predictions.csv` (outer predictions and baselines)
  - `comparisons.json` and `card.md`
  - `checksums.sha256`
- Re-read and verify every checksum, then `os.replace` the directory into place, then
  mark the job `completed`.

**Crash hook (test-only).** Setting `CFB_TUNING_CRASH_AT=<trial>:<fold>` makes the
worker call `os._exit(70)` at that point.

## Join

- **CLI:** `python -m models.tuning run --spec PATH [--root DIR] [--replicate K]`
  submits, works the job to a terminal state, and prints the `run_id` and card path.
  `status` and `cancel --run-id` complete it.
- **Committed spec:** `models/tuning/specs/total_ratings_v1.json`.
  - `cfb_release_b`, seasons 2014–2025.
  - Inner folds 2015–2019, outer folds 2021–2025.
  - 60 trials. The pruner has 20 startup trials and 2 warmup steps; the sampler has 20
    startup trials.
  - All three baselines.
- **Go/no-go evidence:**
  1. Run the committed spec into two fresh roots in separate processes. The `run_id` is
     identical, and `predictions.csv` and every `outer/*.json` are byte-identical.
  2. The crash test (below) passes.

## Evaluation standard

[`docs/model-evaluation-standard.md`](../../model-evaluation-standard.md) binds the join
run because it reports forecast accuracy against a market number.

- **Hard gate: prices reconstructible at decision time.** The Bovada open has no capture
  time and no price (Release A: `line_clock=vendor_open_label_only`). The market
  comparison is therefore descriptive, "forecast error against a labeled vendor number",
  and supports no betting or price claim.
- **Holdout.** 2021–2025 is already spent as a holdout (Release B, priors), so its outer
  numbers are descriptive. There is no untouched holdout in this run; 2026 is the
  untouched season.
- **Tier 1 items the card carries:**
  - trial count (requested, completed, pruned, failed);
  - walk-forward fold and season stability;
  - calibration slope and intercept;
  - intervals, not just point estimates;
  - number of games and clusters;
  - holdout status.
- **Out of scope:** economic items (ROI, CLV, drawdown, fill), because the run makes no
  wagers.

## Testing

| File | Covers |
| --- | --- |
| `tests/test_tuning_spec.py` | Equal hash for reordered keys and reordered seasons; `created_at` excluded; unknown field rejected; outer/inner overlap rejected; feature order changes the hash |
| `tests/test_tuning_cards.py` | Card from a fixture carries run id, hash, feature-set id, fold bounds, baseline slots, trial counts; byte-identical on re-render; no banned terms |
| `tests/test_tuning_features.py` | Leaking row drops the feature; retrospective and provider-opaque features refused; class mismatch refused; synthetic frame deterministic |
| `tests/test_tuning_folds.py` | Fold bounds chronological; no game on both sides; embargo applied; each estimator fits and predicts; `FitFailure` kinds; paired comparisons use the same games; `fit_fold` deterministic |
| `tests/test_tuning_worker.py` | Legal and illegal transitions; idempotent submit; lease expiry → retry → failed at the limit; cancel between folds; code-fingerprint refusal; crash test |
| `tests/test_tuning_join.py` | Synthetic spec run into two fresh roots gives the same `run_id` and byte-identical predictions |

**Crash test.** In a subprocess, crash at trial 3, fold 2, with a 1 s heartbeat, a 1 s
grace period, and a 1 s lease. Wait past the grace period, resume, and assert:

- trials 0–2 are unchanged (parameters and values);
- trial 3 is `FAIL`;
- a later trial number carries its parameters;
- no trial number repeats;
- the budget completes and the run publishes.

The test stays in the default (not `slow`) suite on the synthetic source.

## Out of scope

- Streamlit pages.
- `DecisionPolicySpec` and `ExecutionSpec` (Release D).
- Feature-group search.
- New rating math.
- Parquet.
- Multi-host workers.
- A coverage check for snapshot-dependent features.

## What this cannot claim

- **No betting value.** The market slot is an untimed, unpriced label.
- **No new holdout evidence.** Outer seasons 2021–2025 are spent.
- **Reproducibility has limits.** It holds bit-for-bit on one machine with the same
  library versions. Across machines, it holds only within the tolerance the manifest
  records.
