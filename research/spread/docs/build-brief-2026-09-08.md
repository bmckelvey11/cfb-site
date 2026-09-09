# Build brief — parallel execution of the hardened spread plan

> **Dispatch appendix, 2026-09-08.** `plan-2026-09-08-master.md` is the plan of record; this
> file owns the wave structure, per-agent file ownership and acceptance checks.

**For Cursor, running subagents in parallel.** Decomposes
[`plan-2026-09-08-hardened.md`](plan-2026-09-08-hardened.md) §"Required amendments" plus the
open tasks of `docs/superpowers/plans/2026-09-08-spread-next-steps.md` into agents that can run
at the same time without touching the same file.

Read before dispatching: the hardened plan (the contract), and
`docs/superpowers/plans/2026-09-08-spread-next-steps.md` (the executable steps and their code).
This brief does not restate their content — it says who does what, in what order, and what
proves each piece landed.

## Why the waves exist

Two markdown files are wanted by almost every task — `prereg-line-movement.md` and the plan file
— and one more, `line-movement-results.md`, is where every result wants to write. Parallel
agents on those files produce merge conflicts, and worse, a half-written pre-registration while
another agent is already fitting against it. So:

- **Wave 0 (one agent, alone)** makes every contract edit. Nothing may fit anything until it lands,
  because the repository's preregistration order is that expectation text is committed *before*
  the run that tests it.
- **Wave 1 (seven agents, parallel)** does the code. Every agent owns a disjoint file set. The
  shopping tree (`prereg-line-shopping.md`, `line-shopping-results.md`) has its own single
  writer for the same reason — agent I.
- **Wave 2 (two agents)** does the work that needs Wave 1's outputs.
- **Wave 3 (one agent, alone)** writes every results section and the index, from the JSON the
  earlier waves produced.

## Rules every agent follows

Put this in every subagent prompt:

- Run all commands from the repository root. `CFB_DATA_ROOT` is required and resolves through
  root `cfb_paths.py`; never hardcode a data path.
- **Touch only the files in your "Owns" list.** If the work seems to need another file, stop and
  report it rather than editing it — another agent owns it right now.
- Data is never committed. Analysis outputs go to `data/processed/`, which `.gitignore` excludes.
- No lookahead: a predictor may use only information available before kickoff. The close and the
  score enter as grading targets only.
- Tests: `python -m pytest <your test file> -q`. Write the failing test first, watch it fail,
  then implement.
- One commit per agent, Conventional Commits, subject ≤ 72 chars, no `revert` type. Do not push;
  the orchestrator pushes after the wave.
- Match the surrounding style. Do not refactor adjacent code, reformat, or fix unrelated things
  you notice — report them instead.

**The stopping rule, verbatim.** Several agents touch documents that describe when version B
gets read. It is stated once and must not be paraphrased anywhere:

> No verdict before season end; at season end, confirmatory inference requires ≥ 8 week
> clusters, and with fewer the read is reported as inconclusive.

The observed MDE is reported at every read and triggers nothing.

---

## Wave 0 — the contract (1 agent, blocks everything)

**Owns:** `research/spread/docs/prereg-line-movement.md`,
`docs/superpowers/plans/2026-09-08-spread-next-steps.md`

No code. Every edit below comes from the hardened plan's §"Required amendments".

**Prereg edits**

1. **Amendment ledger.** A table of every amendment to date — A2, A3, B1, and the queued A4, A5,
   B2 — with, per row: what it changed, what motivated it, and **whether that motivation was
   data-driven** (A4's was: the grid edge was seen first). One honest column, not a defence.
2. **Confirmatory vs exploratory.** State that there is exactly one confirmatory hypothesis — the
   version B E4 slope at the Monday anchor — and that A1–A5 and the shopping amendments are
   exploratory. Holm stays within each family; no across-family correction is attempted, because
   with one confirmatory hypothesis none is needed.
3. **Restate the B1 gate** in the verbatim sentence above, replacing the "no verdict before the
   MDE reaches 0.2" wording.
4. **MDE from the cluster SE.** Amend B1's power paragraph: the iid `σ_resid/(σ_x√n)` arithmetic
   understates what a clustered design needs, and `eval_version_b.py` falls back to HC1 below
   `MIN_WEEKS`, so the published `n ≈ 80` came from one week's un-clustered SE. The MDE is
   computed from the cluster SE (or a season-week bootstrap) and is informational until the
   cluster count clears the fallback.
5. **A3 is conditional.** Add a line to A3: its screen is full-sample, so its inference is
   conditional on a screen that saw the evaluation seasons; a walk-forward rerun is registered as
   **amendment A6** (write A6's expectation now, before agent A runs it — expectation: the
   walk-forward drop list overlaps the full-sample one substantially and E4's retention stays
   within a few points of 90%).
6. **A4 is exploratory and its output is an engineering decision** — which λ `weekly_slate.py`
   serves. Reported without a p-value; it does not license "the ridge works".

**Plan-file edits**

7. **T5:** A4 labelled exploratory; if E6 is dropped from `MODEL_COLS`, the change is versioned
   (`model_set_version`) and existing `movement_forward_log.csv` rows are recomputed before any
   read quotes `pred_close`.
8. **T7:** one pre-specified capture per game per bucket, a fixed game set across buckets,
   missingness reported, resampling clustered by game **and** week.
9. **T8:** `collector_health.py` runs **before** the pull and gates the *grade*, not the pull — a
   non-zero exit skips `eval_version_b.py` and records the skip.
10. **T4 Step 5:** fill the undefined 10–14 publish-count branch.
11. **T11 Step 2:** fill the branch where the slope is under 0.10 but the CI does not exclude
    0.20 — the gate makes this the likely outcome, not a corner case. Also replace the Step 1
    gate (`mde_80 ≤ 0.2`) with the verbatim stopping rule.
12. **T9:** record the resolution at the task heading. The user settled it on 2026-09-08: the
    `3.2` win-rate-per-point constant is **kept for line shopping** and stays retired for the
    movement CLV claim. It was estimated on the line-shopping sample itself, so it is the
    in-sample conversion for that sample; review §1.5's objection was to the "3–5× the bar"
    phrasing on movement bets, which sit on larger spreads where a point is worth less. Note
    that the S1 results section must carry the in-sample caveat. T9 is unblocked (agent I).
13. **T10:** relabel as blocked on an external dependency (a `cfb_system_maker` Action Network
    scoreboard re-scrape that nothing in this plan triggers).
14. **New task T15 — walk-forward decontamination screen** (agent A's work), placed in Phase 1
    ahead of T5, since A4 must run on the walk-forward panel.
15. **T12–T14 area:** list the four estimator tests — `holm`, `pick_1se`, null p-value uniformity
    on `wild_cluster_boot`, and the walk-forward drop-list test.

**Acceptance**

```bash
grep -rn "mde_80 <= 0.2\|MDE reaches 0.2" research/spread/docs/ docs/superpowers/plans/
grep -rc "confirmatory" research/spread/docs/prereg-line-movement.md
```

First must return nothing outside the review and the log (both are historical records and keep
their original wording). Second must be non-zero.

**Commit:** `docs(spread): one stopping rule, one confirmatory family, A6 registered`

---

## Wave 1 — code, seven agents in parallel

Every agent's file set is disjoint from every other's. Dispatch all seven at once.

### Agent A — walk-forward decontamination screen (amendment A6)

**Highest priority in the wave.** A3 is the result the tree's self-description rests on, and its
screen is fit on the full sample.

**Owns:** `research/spread/scripts/eval_line_movement.py`, `tests/test_spread_decontam.py` (new)

`eval_line_movement.py` currently computes `ρ_i = corr(f_i − open, close − open)` over all of
2001–2025 and drops the top decile before fitting. The in-code comment argues this can only cost
accuracy. That is right about the direction of the bias on R² — the screen removes the most
target-correlated columns — but wrong that it is therefore innocuous: **the identity of the
retained panel was chosen with knowledge of the evaluation seasons**, so A3's p-values are
conditional on a screen that saw its own test set.

1. Extract the screen into a function that takes the seasons it may look at, and compute it
   **walk-forward**: for evaluation season *s*, the drop list is built from seasons < *s* only.
2. Add `--decontaminate-wf` (keep `--decontaminate` working — A3 stays on the record as run).
3. Write `tests/test_spread_decontam.py` first: the drop list for a given evaluation season is
   identical when rows from that season and later are deleted from the input, and no
   evaluation-season row reaches the screen. That is the whole point of the change, so it is the
   thing that gets tested.
4. Run once: `python research/spread/scripts/eval_line_movement.py --decontaminate-wf` and again
   with `--amend --decontaminate-wf`. Outputs `pt_movement_decon_wf.json`,
   `pt_movement_a2_decon_wf.json` and the matching `_preds` files.

Report per method: R² on the full panel, under the full-sample screen, and under the walk-forward
screen, plus each screen's drop list and their overlap. Do not write prose into
`line-movement-results.md` — Wave 3 owns that file. Leave the numbers in the JSON and in your
commit message.

**Acceptance:** `python -m pytest tests/test_spread_decontam.py -q` passes; both JSON files exist;
`--decontaminate` still reproduces A3's existing numbers.

**Commit:** `feat(spread): walk-forward decontamination screen (amendment A6)`

### Agent B — version B inference

**Owns:** `research/spread/scripts/eval_version_b.py`, `tests/test_spread_version_b.py`

1. **MDE from the cluster SE.** `cluster_ols` falls back to HC1 below `MIN_WEEKS` and says so;
   the MDE and the `n_for_mde` figure derived from it must not be presented as cluster evidence.
   Compute the MDE from the cluster SE when one exists; when the fallback is active, emit the
   figure with an explicit `se_kind: "hc1"` marker and a flag that it is informational.
2. **Apply the stopping rule.** The grader reports the slope, its CI, σ_resid, σ_x, the observed
   MDE and the week-cluster count, and states `verdict: null` unless it is season end **and**
   clusters ≥ 8. Never let a computed MDE set a verdict.
3. **`capture_offsets` (amendment B2).** One pre-specified capture per game per bucket (the
   earliest capture inside the bucket), a fixed game set across buckets — a game missing from any
   bucket is excluded from all of them — and report how many games that costs. Resample by game
   and week.
4. **A5 support.** Whatever `cluster_ols` result a second-stage regression on walk-forward
   predictions produces must carry a `conditional_on_fitted_predictor: true` marker; the first
   stage's uncertainty is not propagated.

Tests first, in `tests/test_spread_version_b.py`: one game contributing many snapshots yields
exactly one row per bucket; a game missing a bucket is dropped from all buckets; no verdict is
emitted below 8 clusters even when the MDE is small.

**Acceptance:** `python -m pytest tests/test_spread_version_b.py -q` passes;
`python research/spread/scripts/eval_version_b.py` runs and prints `verdict: null` with the
cluster count.

**Commit:** `feat(spread): version B gates on clusters, one capture per bucket`

### Agent C — collector health and the Monday chain (T3, T8)

**Owns:** `research/spread/scripts/collector_health.py` (new),
`research/spread/scripts/collect_line_timing.py`, `tests/test_spread_collector_health.py` (new),
`docs/line-timing-collector.md`

1. `collector_health.py` per plan T3: `stale(latest, now, max_gap_hours=12)` and
   `in_season(now)` (Aug 25 – Dec 15); exits non-zero when the snapshot stream is stale in
   season. A snapshot is only written when PT's file changes, so a quiet Sunday can look stale —
   12 hours tolerates two unchanged slots; if it false-alarms weekly, raise to 18 and record why.
2. Chain it in `collect_line_timing.main()`'s history branch **before** the pull, and let its
   exit code gate `eval_version_b.py` only: a stale stream skips the grade and logs the skip; the
   pull still runs, because backfilling histories is exactly what you want when collection has
   been broken.
3. Runbook: the health command under "Checking it is alive", and a line recording that the PT
   snapshots for Thu 09-04 12:30 through Sun 09-07 are gone and cannot be recovered.

**Acceptance:** `python -m pytest tests/test_spread_collector_health.py -q` passes;
`python research/spread/scripts/collector_health.py` exits 0 and names the newest snapshot.

**Commit:** `feat(spread): health check gates the Monday version B grade`

### Agent D — model publication times (T4)

**Owns:** `research/spread/scripts/model_publish_times.py` (new),
`tests/test_spread_publish_times.py` (new)

Per plan T4: `first_seen(snapshots)` giving `slate, model, first_capture_utc,
hours_after_monday_et`. A new slate starts when more than half the `(road, home)` pairs differ
from the previous snapshot (the same rule as `pt_rollover.NEW_SLATE_FRAC`); the slate is labelled
by the Monday on or before its first capture.

Wave 0 fills the decision branches, including the 10–14 case that is currently undefined. Follow
whatever it wrote — read the plan file before you start. Print the pivot; Wave 3 writes the prose.

**Acceptance:** `python -m pytest tests/test_spread_publish_times.py -q` passes; the script runs
and prints one row per slate.

**Commit:** `feat(spread): when each panel model first appears in a slate`

### Agent E — estimator core tests

**Owns:** `tests/test_spread_estimators.py`

Three cases, added to the three already there:

1. `holm` on a known input — a hand-computed adjustment, including the ties and the monotonicity
   step.
2. `pick_1se` on a known curve — the chosen point is the most-shrunk parameter within one SE of
   the best, and an edge hit is reported as an edge hit.
3. `wild_cluster_boot` calibration: over many independent null draws the p-values are ~uniform.
   The existing test checks one draw, which cannot detect a miscalibrated bootstrap. Keep the
   draw count low enough to stay off the slow-test list (`pytest.ini` excludes slow by default) —
   a few hundred draws with a fixed seed, asserting the rejection rate at α = 0.1 is within
   binomial tolerance.

Do **not** add per-fitter tests for E6–E14; they are exercised end to end by the registered runs
and this was rejected in review round 1 on purpose.

**Acceptance:** `python -m pytest tests/test_spread_estimators.py -q` passes, 6 tests, and the
file does not appear in the slow-test selection.

**Commit:** `test(spread): holm, pick_1se and bootstrap calibration`

### Agent F — hygiene (T12, T14)

**Owns:** `research/spread/scripts/eval_prediction_tracker_models.py`,
`research/spread/scripts/eval_combination_sweep.py`, `docs/clv-analysis.md`

1. First docstring line of both modules becomes: `"""Estimator core for the spread tree (imported
   by the live scripts). main() reproduces the archived margin-era tables:
   archive/spread-margin-era/."""` — keep the rest of each docstring.
2. `docs/clv-analysis.md` (+0.318 on 154 spreads) and `docs/bet-history-analysis-2023-2025.md`
   (+0.07 on 250) disagree. Open both, work out which join each uses, and write one paragraph in
   `clv-analysis.md` saying which number to quote and why. Version B's CLV will be compared
   against this record, so it needs one answer. Do not edit the bet-history file — reference it.

**Acceptance:** `python -c "import sys; sys.path.insert(0,'research/spread/scripts'); import
eval_combination_sweep, eval_prediction_tracker_models"` succeeds.

**Commit:** `docs(spread): mark the core modules' main() as margin-era`
(the CLV paragraph is a second commit: `docs(clv): say which spread CLV figure to quote`)

### Agent I — line shopping, amendment S1 (T9)

**Owns:** `research/spread/docs/prereg-line-shopping.md`,
`research/spread/scripts/eval_line_shopping.py`,
`research/spread/docs/line-shopping-results.md`

Lettered out of sequence because this task was unblocked after the brief was first written. It
runs in Wave 1 — its files are disjoint from every other agent's, and it is the only agent that
touches the shopping tree.

`combining-predictions.md` §1 lists two defects that must be fixed before the book fair drives a
live bet: the backtest has no outlier guard although the live slate does, and price is ignored.

1. **Pre-register S1 first, and commit it before you run anything.** Two commits, in this order:
   the amendment text, then the implementation and its result. The repository's preregistration
   order is not negotiable — the expectation is committed before the run that tests it.
2. **Outlier guard.** Where `eval_line_shopping.py` builds the per-game book table (the group
   over `event_id` that produces `fair`), apply the same guard the live slate uses, before the
   median.
3. **Price-adjusted value.** `value = 3.2 * gain - 100 * (breakeven(best_odds) -
   breakeven(median_odds))`, where `median_odds` is the odds at the book supplying the median
   number (or −110 when the median averages two books). Report `value.mean()` at gain ≥ 0.5 and
   ≥ 1.0, and `(value <= 0).mean()`.
4. **Write the caveat.** The `3.2` constant is in-sample — it came from line-shopping P2 on
   2024–25, 3,574 sides, dominated by 3/7 crossings on small spreads. The S1 section must say
   so. Keeping it here was a deliberate decision, not an oversight, and the section should read
   that way: it is the in-sample conversion for this sample, and it is not the right conversion
   for movement CLV, where review §1.5 retired it.

**Acceptance:** the prereg commit precedes the run commit in `git log`; the S1 section reports
the P2 figure, both value means and the caveat.

**Commit:** `docs(spread): pre-register S1, outlier guard and price` then
`feat(spread): outlier guard and price-adjusted value for shopping`

---

## Wave 2 — depends on Wave 1 (two agents, parallel with each other)

### Agent G — amendment A4, and whether E6 keeps its place (T5)

**Depends on:** Agent A. **Owns:** `research/spread/scripts/eval_line_movement.py`,
`research/spread/scripts/weekly_slate.py`

A4 must run on the **walk-forward** panel A6 produced, not the full-sample one — running it on
the old panel bakes the leak into the serving decision.

1. `FINE_LAMBDA = [1000, 2000, 5000, 1e4, 2e4, 5e4]` and a `--fine-ridge` flag; run once against
   `--decontaminate-wf`. Output `pt_movement_decon_wf_a4.json`.
2. Apply the pre-registered rule Wave 0 wrote. If E6 is retired: remove it from `PARAMS` and
   `MODEL_COLS`, update the docstring column list, and confirm
   `python research/spread/scripts/weekly_slate.py --no-books` still builds. If it is kept:
   set the modal A4 λ and cite the JSON in the `PARAMS` comment.
3. **Either way**, add `model_set_version` to the forward log and to `version_b.json`, and
   recompute the existing `movement_forward_log.csv` rows under the new definition before any
   read quotes `pred_close`. A predictor that changes mid-forward-test silently redefines the
   quantity being graded.

**Acceptance:** the JSON exists; `weekly_slate.py --no-books` builds; every forward-log row
carries a `model_set_version`.

**Commit:** `feat(spread): finer ridge grid on the walk-forward panel (A4)`

### Agent H — amendment A5, the move after PT's last capture (T6)

**Depends on:** Agent A (needs `pt_movement_preds_decon_wf.csv`) and Agent B (needs the
`conditional_on_fitted_predictor` marker). **Owns:**
`research/spread/scripts/check_pt_line_is_close.py`

Per plan T6, on the 1,219 matched 2024–25 games: does E4's disagreement with PT's `line` predict
the remaining PT-line → AN-close move? This is the only archive evidence that could distinguish
"the panel leads" from "the panel follows". Use the walk-forward predictions, `cluster_ols` from
`eval_version_b`, and label the CI conditional on the fitted predictor.

**Acceptance:** the script prints the existing table plus the three slope lines, n ≈ 1,100.

**Commit:** `feat(spread): does the panel know anything past PT's capture (A5)`

---

## Wave 3 — the integrator (1 agent, alone)

**Owns:** `research/spread/docs/line-movement-results.md`,
`research/spread/docs/README.md`, `research/spread/CLAUDE.md`

Every earlier agent left numbers in JSON and none of them wrote prose. This agent writes all of
it, from the outputs, in one pass — which is why the results file never had two writers.

1. Sections for A6 (walk-forward screen, with the full-sample vs walk-forward comparison and the
   two drop lists' overlap), A4, A5, B2, publication times, and a "Version B reads" table with
   one row per Monday.
2. **Restate the headline against A6.** If the walk-forward screen moves E4's retention
   materially, the tree's one-line result changes and this is where it changes. The hardened
   plan's Goal currently calls the A3 figure conditional; if A6 lands, drop the hedge and cite
   A6. If A6 moves the number a lot, say so plainly — the finding was that A3's inference was
   conditional, not that it was wrong.
3. `README.md`: rows for the new scripts and documents (this brief, the hardened plan, the review
   log), and the `eval_line_movement.py` row extended with `--decontaminate-wf` and
   `--fine-ridge`.
4. `research/spread/CLAUDE.md` and the README "current position": one sentence each, pointing at
   the results file. They must not restate numbers — five copies of the headline is what the
   audit objected to.
5. Mark every task this build completed in
   `docs/superpowers/plans/2026-09-08-spread-next-steps.md` as done, with the date. Standing
   repository rule: a doc that tracks work does not stay stale once the work lands.

**Acceptance:** `grep -rn "0\.153\|0\.248" research/spread/CLAUDE.md research/spread/docs/README.md`
returns nothing; every task this build completed is checked off with a date.

**Commit:** `docs(spread): record A4, A5, A6, B2 and the week's version B reads`

---

## Not in this build

| Item | Why |
|---|---|
| **T10** — "scoreboard = close" | Needs an Action Network scoreboard re-scrape that lives in `cfb_system_maker`, which nothing here triggers. |
| **T1** — AN backfill and the scheduler check | A vendor data pull plus an observation that a scheduled task fired on its own. Run it by hand; it is not agent work and its Step 3 answer is a fact about the machine, not the repo. |
| Alpha-spending for the weekly reads | The fixed season-end checkpoint removes the sequential-test problem. A spending function would be machinery for a design that no longer stops early. |
| Per-fitter unit tests for E6–E14 | Rejected in review round 1: exercised end to end by the registered runs. |

## Dispatch order

```
Wave 0  ──────────────►  contract (blocks all)
                          │
Wave 1  ──────────────►  A  B  C  D  E  F  I   (seven in parallel)
                          │        │
Wave 2  ──────────────►  G (needs A)   H (needs A, B)
                          │
Wave 3  ──────────────►  integrator (alone)
```

Run `python -m pytest` once after Wave 1 and once after Wave 2 — the whole suite, not just the
new files. `pytest.ini` excludes slow tests by default.
