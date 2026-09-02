# Review — handoff of 2026-09-02 and the "composite spread" goal

Reviewer pass over `handoffEQaszm.md` and the spread research tree, against the stated goal:
**build a composite point spread from all the models to gain an edge over the books.**

## Verdict on the goal

A composite of the Prediction Tracker panel against the closing spread is closed, and the
evidence is stronger than the handoff states. Ten combination rules (E1–E14) were tried
walk-forward on 12.8–14.3K games; best Holm p = 0.49; the ATS record is 50.31% on 12,560 bets,
p = 0.002 *below* the −110 break-even. Nothing here should be reopened without a new information
source. Details: `prediction-tracker-findings.md`.

One check added in this review, because the handoff's reasoning for *why* had a gap (§1 below).

## 1. Critique: "the disagreement tail does not exist" is the wrong reason

The handoff says a threshold rule cannot work because 89% of games sit within one point of the
close. That is true of **E4**, whose fitted tilt is γ ≈ 0.07 — E4 is the closing line plus 7% of
the consensus deviation, so it hugs the close by construction. It is not true of the panel.

Raw composite: per-season median of every model with ≥95% within-season coverage, `lineca` and
`linemidweek` excluded, no fitting, no shrinkage (~39 models per season). Graded ATS against the
PT closing line, 2001–2025, pushes dropped, season-clustered SE.

| \|composite − close\| | n | ATS win | SE (25 seasons) |
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

## 5. Direction — where "composite" still earns something

The word *composite* is right; the inputs are wrong. Compose **book lines**, not model outputs.

1. **Composite of books = fair value; the outlier book = the bet.** Seven-book Action Network
   feed, 2024–2026. Fair = median of books with `line_status = 'normal'` and
   `is_alt_market = false`. Flag any book ≥ 1.0 point off fair, and any pair straddling 3 or 7.
   Backtest: ATS win rate at the outlier book's number versus at the consensus number,
   season-clustered CI, both seasons. This is the edge the handoff's §3 hints at, measured
   properly. It is an edge over *a* book, never over the market, and that is the only kind the
   evidence supports. Done when: one script, one table, dispersion tail explained.
2. **Keep the forward timing test running; close the logging gap** (§2). It is the only asset
   that appreciates. Watch `corr(line move, edge_vs_open)`; it was +0.988 in week 1.
3. **Totals are where the user's own money says the edge is** (58.0% on 231 bets, CLV +0.45,
   results grade with CLV). Out of scope for this tree, but it should absorb the modelling
   effort the spread work no longer deserves.
4. **Do not build**: another combiner, a recency scheme, a cohort correction, or a spread GBM.
   Each has a recorded null.

If a midweek fair-value number is wanted for reference, serve E4 from the latest snapshot,
not the raw median: the raw median disagrees with the close by 2 points on a typical game and
is wrong when it does (§1).
