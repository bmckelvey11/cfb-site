# Tuning lab Release E: live shadow system — design

**Status:** declared 2026-09-23. The user asked for Release E to be built end to end and
chose the schedule: one step in the daily `scripts/refresh_cfbd.cmd` job. Everything else
is Claude's default.

**Builds on:**

- [`docs/model-tuning-lab-plan.md`](../../model-tuning-lab-plan.md): §40 Release E, §29.2
  (replay parity), §34 (champion/challenger, prediction ledger, drift, fallbacks).
- Release C's run `run-de1927346ab0` and Release D's run `dist-0b0cc0382eca`.

**Amended 2026-09-23, before any period snapshot.** A second advisor pass found three
problems in the counting code:

- A game never marked final could block snapshots for 10 days, and with one run a day at
  05:00 ET that loses weeks.
- The timing check compared against the prediction's own kickoff, so it could never fire.
- Postponement was not implemented as written.

The rules below state the fixed behaviour. The hashed spec file is unchanged.

**Review:** none cross-model. An advisor pass set:

- the deadline arithmetic;
- the fetch-venv trap;
- live/historical parity as the key test;
- freezing before the first snapshot;
- SQLite with an append-only hash chain.

## Goal and go/no-go

**Goal.** Predict every 2026 FBS-vs-FBS regular-season game of a declared period before
kickoff, store each prediction in a ledger nobody can quietly edit, score it after the
game, and watch for drift.

**Go/no-go (plan §40):** complete at least one defined shadow period with no untracked
data revisions, timing violations, or missing prediction artifacts.

- **First shadow period:** 2026 weeks 5–8.
  - Week 5's first kickoff is 2026-10-02 00:00Z.
  - Week 8's last is 2026-10-25 02:00Z.
  - The verdict exists once the week-8 scores land, around 2026-10-26.
- **Week 4 is a rehearsal**, labeled as such and outside the period. Its first kickoff is
  2026-09-24 23:30Z.

## What is frozen before week 5's first snapshot

Both models below are written as sealed artifacts. `models/tuning/specs/shadow_2026_w05_08.freeze.json`
records their sha256s and parameters and is committed to git. Promotion moves an alias and
never rewrites an artifact.

**`champion` = `ridge_v1_total`.** Release B's ratings: λ 40/8, fit at the week cutoff on
the season's completed, ungated FBS-vs-FBS games; the forecast is `forecast_total`.

**`challenger` = the tuning-lab model and table:**

- Release C's selected Elastic Net (α 0.0416, L1 ratio 0.0312), refit on every usable
  season 2014–2025, for the total and for home and away regulation points.
- Release D's `joint_bootstrap` table, using residual pairs and overtime totals from the
  2023–2025 window, split into early and primary pools.

**`prior_v3` stays out.** Its sealed 2026 confirmation owns it.

**The pricing policy is frozen, then only replayed:**

- `DecisionPolicySpec(min_ev, 0.03)` on the challenger table;
- `ExecutionSpec(best book, maximum quote age 24 h)`.

It is replayed only after the period, against Action Network ticks at or before each game's
decision time. It is not part of the go/no-go.

**Replay rules (declared 2026-09-23, before week 5):** the docstring of
[`models/tuning/replay.py`](../../../models/tuning/replay.py) and the spec
`models/tuning/specs/replay_2026_w05_08.json` (`replay-0b8176899086`).

- Decision time is the recorded week cutoff.
- Action Network ticks are change events, so a price unchanged for more than 24 h counts as
  stale.
- The P(over) score is taken against the modal fresh number's mean de-vigged probability.
- Intervals resample games; they are too narrow.
- The replay prices the tables and quote files the ledger recorded. `tick` copies each
  archived history file into the shadow directory for this.

## Counting rules (declared)

- **Decision time.** Each week's cutoff is its earliest FBS-vs-FBS regular-season kickoff,
  from the raw schedule. Ratings are fit on games that kicked off strictly before it.
- **Snapshots.** Every daily run between the previous week's completion and the cutoff
  writes a snapshot of the next upcoming week.
  - A newer snapshot supersedes an older one.
  - **The prediction that counts** for a game is the last one generated before that
    game's final kickoff.
  - No snapshot is ever generated at or after a week's cutoff.
- **Expected games.** The week's FBS-vs-FBS regular-season games in the schedule at its last
  pre-cutoff snapshot.
- **Waiting for results.**
  - A snapshot waits while a game is inside the 6 h grace after kickoff.
  - It also waits while a game is past kickoff, not yet final, and no more than 36 h past
    kickoff.
  - After that it goes ahead with a stale-inputs warning.
  - Within 12 h of the cutoff it goes ahead regardless.
- **Changes to the schedule:**
  - A game in the week's current schedule that is not in its last pre-cutoff snapshot is
    logged as unscheduled, not missing.
  - A game whose kickoff moved more than 7 days past its week's decision time was
    postponed out of the period. It is no-action, not missing.
  - A game never completed within 7 days of its kickoff was cancelled. It is no-action,
    not missing.
- **Missing prediction artifact.** An expected game with no counted prediction, or a
  counted prediction whose table file is absent or fails its checksum.
- **Timing violation.** A counted prediction generated at or after its week's decision
  time, as the schedule reads when the game is scored. This happens when a kickoff moved
  earlier after the snapshot.
- **Data revision.** At scoring, the as-of input digest is rebuilt and compared with the one
  recorded at the snapshot. The digest covers the fit set's game ids, regulation points, and
  possessions.
  - **Tracked revision:** a difference that is logged as a revision record.
  - **Untracked revision:** a ledger whose hash chain does not verify.

## Components

1. **`models/tuning/ledger.py`.**
   - Stored in SQLite (`shadow/ledger.sqlite3`).
   - Triggers raise on any UPDATE or DELETE.
   - Each record carries `prev_sha256` and its own `sha256` over its canonical payload.
   - `verify_chain()` walks the chain.
   - Record kinds:
     - `arm`, `alias`
     - `snapshot`, `prediction`, `missed`
     - `score`, `revision`
     - `quotes_archived`
     - `period_verdict`
2. **`models/tuning/features.py`.** The per-game row builder is moved out of
   `_release_b_frame` so the snapshot-CSV path and the live fit-at-cutoff path share it.
   - `live_week_frame(season, week, cutoff)` builds the week's rows from ratings fit at the
     cutoff.
   - **Parity check:** on 2025 week 6 the live path must equal the CSV path, value for
     value. It is a `slow` test (real data) and a recorded in-session check.
3. **`models/tuning/shadow.py`.**
   - `freeze` writes the sealed artifacts and the committed freeze JSON.
   - `tick` runs daily after the data refresh:
     - verifies the chain and the frozen checksums;
     - takes the next upcoming week's snapshot if the week before it is complete;
     - records `missed` for any period week whose cutoff passed with no snapshot;
     - scores completed games, and checks each counted prediction against its final
       kickoff;
     - rebuilds digests for completed weeks;
     - hashes the week's AN history files after the cutoff, using the event crosswalk
       from the raw 2026 scoreboards and `duckdb_load._AN_SCHOOL_ALIAS`, and reports
       unmatched events;
     - writes `shadow/<id>/status.md`.
   - `alias` sets an alias with a reason (an `alias` record). Rollback is setting it back.
4. **Monitoring in `status.md`**, per week and period to date. Drift is an investigation
   trigger, never an automatic refit (plan §34.3).
   - Operations: expected, predicted, missing, violations, revisions, no-action.
   - Scores: champion vs challenger MAE, challenger CRPS, 80% coverage, mean residual.
   - Drift: feature and prediction means against the same weeks of 2021–2025.
   - Data freshness: the newest completed game and the games file's age.
5. **Fallbacks.**
   - A missing or tampered frozen artifact, or a failed chain, means no predictions: `tick`
     exits 1 with the reason in the log.
   - Stale data means wait. The model never imputes a prediction.
6. **Schedule.** One step after the rankings step in `scripts/refresh_cfbd.cmd`.
   - It calls `%REPO%\.venv\Scripts\python.exe`, because the fetch venv has pydantic 1
     and no optuna or sklearn.
   - It never changes the fetch's exit code.
   - It keeps the file's LF endings.

## What this cannot claim

- **Timing.** The verdict is about operations only: predictions on time, intact, and
  complete. It says nothing about skill.
- **Skill.** Weeks 5–8 give about 230 games. Champion vs challenger over that window is
  descriptive; the 2026 season is already where the prior_v3 confirmation lives.
- **Pricing.** No priced result exists until the frozen policy is replayed after the period.
