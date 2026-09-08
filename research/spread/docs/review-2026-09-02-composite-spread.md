# Review — handoff of 2026-09-02 and the "model consensus spread" goal

Reviewer pass over `handoffEQaszm.md` and the spread research tree, against the stated goal:
**build a composite point spread from all the models to gain an edge over the books.**

## Verdict on the goal

A model consensus of the Prediction Tracker panel against the closing spread is closed, and the
evidence is stronger than the handoff states. Ten combination rules (E1–E14) were tried
walk-forward on 12.8–14.3K games; best Holm p = 0.49; the ATS record is 50.31% on 12,560 bets,
p = 0.002 *below* the −110 break-even. Nothing here should be reopened without a new information
source. Details: `prediction-tracker-findings.md`.

One check added in this review, because the handoff's reasoning for *why* had a gap (§1 below).

## 1. Critique: "the disagreement tail does not exist" is the wrong reason

The handoff says a threshold rule cannot work because 89% of games sit within one point of the
close. That is true of **E4**, whose fitted tilt is γ ≈ 0.07 — E4 is the closing line plus 7% of
the consensus deviation, so it hugs the close by construction. It is not true of the panel.

Raw model median: per-season median of every model with ≥95% within-season coverage, `lineca` and
`linemidweek` excluded, no fitting, no shrinkage (~39 models per season). Graded ATS against the
PT closing line, 2001–2025, pushes dropped, season-clustered SE.

| \|raw model median − close\| | n | ATS win | SE (25 seasons) |
|---|---|---|---|
| [0, 1) | 4,051 | 50.0% | 0.9% |
| [1, 2) | 4,160 | 49.4% | 0.8% |
| [2, 3) | 3,260 | 50.1% | 1.0% |
| [3, 5) | 3,747 | 49.8% | 0.8% |
| [5, ∞) | 1,948 | **49.0%** | 1.5% |
| all | 17,166 | 49.7% | — |

Median disagreement is 2.0 points, 99th percentile 8.9. **The tail exists and is large; it
carries no information.** The strongest-disagreement bucket is the worst, and its interval
(≈46–52%) tops out at break-even. Against the *opening* line the same >5 bucket is 53.9% on
1,641 games — the familiar open-only edge at an unreachable price.

Corrected statement for the record: the panel disagrees with the close often and by a lot,
and when it does, the close is right. That is a stronger closure than "no tail."

Exploratory, one run, buckets copied from `prereg-ats-tail-test.md`, not pre-registered.
Reproduce from `prediction_tracker_lines.csv` in ~40 lines; nothing to persist.

## 2. Critiques of the handoff itself

- **Two artifact paths are wrong.** `value-sources-beyond-the-close.md` and
  `bet-history-analysis-2023-2025.md` live in root `docs/`, not `research/spread/docs/`.
- **"Each `predict_upcoming.py` run appends to the forward log" — it ran once.**
  `pt_upcoming_predictions.csv` has 8 rows from the 2026-08-29 snapshot. Four snapshots exist
  (08-29, 08-30, 08-31, 09-01; latest 44 games). Both scheduled tasks are alive (`Last Result 0`).
  Nothing is lost — predictions are deterministic given a snapshot and the frozen historical
  panel, so they can be recomputed — but the log is not doing the job the handoff assigns it.
  Cheapest fix: have `collect_line_timing.cmd snapshot` invoke `predict_upcoming.py` whenever it
  writes a new file.
- **"Recompute line shopping over the full archive" overstates the archive.** Per-book Action
  Network spreads exist for 2024 (899 games, 6 books), 2025 (892, 7) and 2026 so far (106, 7).
  Two seasons is enough to measure dispersion and explain the 13.5-point tail; it is not enough to
  measure a win-rate gain to ±1 point.
- **Two CLV numbers on spreads disagree.** `clv-analysis.md`: +0.318 on 154 spreads, p = 0.058.
  `bet-history-analysis-2023-2025.md`: +0.07 on 250 spreads, no gradient. Different joins,
  different samples, opposite reads. Reconcile before either is quoted.
- **The bet-history "verdicts" are post-hoc across ~40 splits**, as that doc itself says. The
  key-number leak is 49-55-1 — a 105-bet cell whose 95% interval spans roughly 37–57%. Adopting
  the subtractive rules is right because they are free, not because they are evidence of edge.
- **Skipping GSD is correct.** Pre-registration discipline is the planning artifact here.

## 3. On the pre-registered GBM (`prereg-spread-model.md`)

Agree with the lean: do not build it for spreads. Its leakage controls are good and its own
expectation is null. A 21-feature team-state model is a strict subset of what `lineelo`,
`linefpi`, `linesag` and 150 others already bring, and those lost. If it is built at all, build
it because the totals sibling needs the differential-feature variant, not to reopen spreads.

## 4. The one live lead, sized honestly

E14 decontaminated, closing line: −0.193 MSE [−0.344, −0.045], p = 0.0125, post-hoc winner of an
eight-member family. On a margin variance of ~242, that is 0.006 RMSE. Even if it is real and
survives pre-registration, it is not a bettable number. Leave it as a pre-registration candidate;
do not spend the 2026 season on it.

## 5. Direction — where averaging still earns something

Average **book lines**, not model outputs: the book fair, not the model consensus.

1. **Book fair = median of books; the outlier book = the bet.** Seven-book Action Network
   feed, 2024–2026. Fair = median of books with `line_status = 'normal'` and
   `is_alt_market = false`. Flag any book ≥ 1.0 point off fair, and any pair straddling 3 or 7.
   Backtest: ATS win rate at the outlier book's number versus at the consensus number,
   season-clustered CI, both seasons. This is the edge the handoff's §3 hints at, measured
   properly. It is an edge over *a* book, never over the market, and that is the only kind the
   evidence supports. Done when: one script, one table, dispersion tail explained.
   **Done 2026-09-02** — `prereg-line-shopping.md` → `eval_line_shopping.py` →
   `line-shopping-results.md`.
2. **Keep the forward timing test running; close the logging gap** (§2). It is the only asset
   that appreciates. Watch `corr(line move, edge_vs_open)`; it was +0.988 in week 1.
   **Done 2026-09-02** — `collect_line_timing.py snapshot` now invokes `predict_upcoming.py`
   and `weekly_slate.py` on every new snapshot, so the forward log fills itself. `pt_rollover.py`
   (2026-09-08) detects the weekly slate flip so a wait loop can gate on it.
3. **Totals are where the user's own money says the edge is** (58.0% on 231 bets, CLV +0.45,
   results grade with CLV). Out of scope for this tree, but it should absorb the modelling
   effort the spread work no longer deserves.
   **Not done — out of scope for this tree, by design.** Belongs to `models/totals/`.
4. **Scope the nulls correctly.** Another combiner, a recency scheme, a cohort correction or a
   spread GBM each has a recorded null *as a margin forecast against the close*. That is not a
   reason to skip them against the line-movement target (§6, `prereg-line-movement.md`), where
   the same estimators succeed.
   **Done 2026-09-02** — scoped in `research/spread/CLAUDE.md` and bannered at the top of
   `prediction-tracker-findings.md`.

If a midweek fair-value number is wanted for reference, serve E4 from the latest snapshot,
not the raw median: the raw median disagrees with the close by 2 points on a typical game and
is wrong when it does (§1).

## 6. Addendum, same day — "predictions come out early in the week"

The user's live question is claim 2, not claim 1: not *does the model consensus beat the close as a
forecast* (closed), but *does the model consensus forecast where the close goes*, bet at Monday's
line. Historically the panel beat the opener by 2.6 MSE in 20 of 20 seasons and bets at the
opener with ≥2 points of edge won 55.9%; the edge was at break-even once ~25% of the
open-to-close move had happened (`prediction-tracker-model-eval.md` §8). So everything
reduces to one number: **how much of the move is left when PT publishes.**

### Measured on week 1 of 2026 — the first timestamped week that exists

106 games, 7 books, 616 book-games, full-game spread ticks with `updated_at`. Monday price
taken at 19:05Z to match the PT snapshot cadence.

| | value |
|---|---|
| \|open → close\| move, median | 1.0 point (25% of book-games never moved) |
| Fraction of that move already done by Monday 19:05Z, median | **1.00** (98% of book-games at ≥ 1.0) |
| Remaining move Monday → close, median / mean | **0.0 / 0.06 points**; 5% had ≥ 1 point left, 0% had ≥ 2 |
| Opener timestamps | earliest 2 Apr, median 8 Jun, latest 28 Aug |

**Week 1 openers are spring look-ahead lines.** By Monday of game week there was nothing left
to capture at any of the seven books. The same holds for the 7 mid-September games whose
histories are already posted: every opener is dated April–June and Monday's price equals
today's. PT's `lineopen` for these games is therefore a number nobody could bet in September,
and `edge_vs_open` on the forward log is not an available edge. That is consistent with the
chase diagnostic reading +0.999 on both week-2 snapshots.

What this does **not** settle: in-season weeks, where openers post Sunday night and the
Monday snapshot is ~18 hours later. Action Network had posted history for only 7 of 86
week-2 games by Wednesday, so that measurement waits for the Monday backfill after each
weekend. Rerun the block above on weeks 3+ once ~5 weeks exist; the number to report is the
remaining-move distribution Monday → close with a season-week cluster SE.

### What the Monday snapshot itself says

44 games, 2026-08-31 19:05Z. The line had already moved ≥ 1 point from PT's opener on 61% of
them. E4's disagreement with Monday's line: median 0.27, max 0.98, zero games at ≥ 1 point.
Tuesday's snapshot (γ = 0.10): median 0.40, max 1.39, four games at ≥ 1 point. Those four are
the entire forward-test bet set for week 2; they get graded against Saturday's close. One
PT typo to know about: UCLA–California carries `lineopen = −55.0`, which is why that row
shows a 52.9-point edge versus the open.

### Operational changes made

- Forward log populated for all four snapshots (105 rows; it had 8).
- `collect_line_timing.py snapshot` now runs `predict_upcoming.py` on any newly written
  snapshot, so the log fills on the 6-hour schedule without a hand run.

### Revised read on claim 2

Not disproven; still unsupported, and week 1 says the executable window is narrower than
the archive's open-to-close framing implied. If in-season weeks show a median remaining move
under half a point on Monday, claim 2 closes too, and the only spread value left in this
tree is book-vs-book dispersion (§5, item 1).
