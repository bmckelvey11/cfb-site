# `docs/superpowers/` index

Implementation plans (`plans/`) and design specs (`specs/`) written with the superpowers
workflow. Several are cited as plan of record by docs, ADRs, scripts, and `TODO.md`, so
they are documentation, not tool state. Finished and superseded ones were moved to
[`archive/docs/superpowers/`](../../archive/docs/superpowers/) on 2026-10-16.

Status: **open** (work remains), **done** (executed; kept because a finding doc or script
cites it as the declared-before-scoring record), **record** (plan of record or appendix
whose remaining items are not verified).

## Plans

| Doc | Status | What it answers |
| --- | --- | --- |
| [2026-09-08-warehouse-rationalization-master.md](plans/2026-09-08-warehouse-rationalization-master.md) | record | Warehouse rationalization plan of record; the `stg_gql` collapse (§8 step 5) ran 2026-09-10, §10 open items not re-checked |
| [2026-09-01-warehouse-source-rationalization.md](plans/2026-09-01-warehouse-source-rationalization.md) | record | Execution appendix to the master plan: task-level steps and code |
| [2026-09-08-spread-next-steps.md](plans/2026-09-08-spread-next-steps.md) | open | Spread line-movement fixes; Task 8 recurs weekly, Task 10 blocked, Task 11 at season end |
| [2026-09-17-spread-implied-power-ratings.md](plans/2026-09-17-spread-implied-power-ratings.md) | open | Power ratings recovered from the closing spread; not started |
| [2026-09-21-data-root-move.md](plans/2026-09-21-data-root-move.md) | open | Moving the data root out of the repo tree; Commit 2 (cutover) not done |
| [2026-09-21-data-root-move-review-log.md](plans/2026-09-21-data-root-move-review-log.md) | open | Review log for the data-root move plan |
| [2026-09-23-tuning-lab-release-e-PLAN.md](plans/2026-09-23-tuning-lab-release-e-PLAN.md) | open | Tuning lab Release E (live shadow system); Task 6 waits on the calendar |

## Specs

| Doc | Status | What it answers |
| --- | --- | --- |
| [2026-08-27-bet-history-model-behavioral-stats-design.md](specs/2026-08-27-bet-history-model-behavioral-stats-design.md) | open | Model-agreement and behavioral sections for the bet-history analysis; approved, not built (owner to confirm it is still wanted) |
| [2026-08-28-drive-level-dispersion-design.md](specs/2026-08-28-drive-level-dispersion-design.md) | open | Drive-level dispersion features and a volatility axis; approved, not implemented |
| [2026-09-01-new-system-type-catalog.md](specs/2026-09-01-new-system-type-catalog.md) | open | New System type catalog for the `/system` editor; draft waiting on human review |
| [2026-09-22-weekly-ratings-design.md](specs/2026-09-22-weekly-ratings-design.md) | done | Release B weekly PPP and pace ratings; result in `docs/weekly-ratings-2026-09-23.md` |
| [2026-09-23-weekly-priors-design.md](specs/2026-09-23-weekly-priors-design.md) | done | Previous-season priors for the weekly ratings; no-go |
| [2026-09-23-lambda-total-tuning-design.md](specs/2026-09-23-lambda-total-tuning-design.md) | done | Re-tuning rating penalties on total-forecast loss |
| [2026-09-23-prior-scale-2026-confirmation-design.md](specs/2026-09-23-prior-scale-2026-confirmation-design.md) | open | Carryover scale tuned pre-2021; the 2026 confirmatory look is open until the regular season ends |
| [2026-09-23-tuning-lab-release-c-design.md](specs/2026-09-23-tuning-lab-release-c-design.md) | done | Tuning lab Release C: governed tuning MVP |
| [2026-09-23-tuning-lab-release-d-design.md](specs/2026-09-23-tuning-lab-release-d-design.md) | done | Tuning lab Release D: probabilistic decisions |
| [2026-09-23-tuning-lab-release-e-design.md](specs/2026-09-23-tuning-lab-release-e-design.md) | open | Tuning lab Release E: live shadow system |
| [2026-09-23-tuning-lab-release-f-dynamic-ratings-design.md](specs/2026-09-23-tuning-lab-release-f-dynamic-ratings-design.md) | done | Release F1 dynamic ratings vs weekly ridge; stopped at the screen gate |
