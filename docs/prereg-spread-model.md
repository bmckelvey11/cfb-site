# Pre-registration — GBM spread model on the repo's own feature stack

**Committed before the model is fitted.** Ninth such commitment in this analysis; the eighth
defect was a post-hoc narrowing caught by an outside reviewer, so the discipline earns its keep.

## Why this is not a repeat of the Prediction Tracker work

That work combined **other people's model outputs** and closed cleanly: the panel cannot beat
the closing spread (50.31% ATS on 12,560 bets, p = 0.0020 *below* breakeven). This is a
different estimator — a gradient boosting model on **entering-game team state** (Elo, talent,
returning production, recruiting, running PPA/success/explosiveness, venue) — which has never
been tested against the closing spread. Infrastructure for a filter-based search exists but the
systems directory is empty, so there is no recorded verdict to inherit.

## Primary benchmark is the CLOSING spread. This is the whole point.

Graded ATS at -110, breakeven 52.38%. The closing spread is the only benchmark that answers
"can I act on this", and `games.csv` has 13,503 of them across all 13 seasons.

The **opening** spread is explicitly NOT the primary outcome and will be reported only if
coverage allows, with the timing caveat attached. `spread_open` exists for just 2,317 of 13,014
games, none before 2021. Fixing the primary benchmark here, in advance, so that a good
opening-line result cannot later be presented as the deliverable — which is exactly the trap the
Prediction Tracker analysis fell into for two rounds.

## Leakage controls, fixed before fitting

The totals sibling produced 57% / +8.82% ROI in a leaked era from **this-game** features
(havoc, attendance, post-game stats). The same trap is live here because `features.json` carries
all 112 columns including those.

- **Explicit allowlist only.** Features come from `cfb_totals_model.data._REGISTRY_COLS` plus
  entering-game `pre_*` aggregates. No "all columns minus known-bad".
- **The entire `result_lookahead` group is excluded**, including `coach_style_cluster` and
  `pregame_win_prob`. A walk-forward market test on coach styles already found nothing
  (0 of 10 survive Holm), so nothing is lost.
- **`min_prior_games = 3`**, so week 1 and thin-history teams are no-bet, matching the totals
  harness.
- Walk-forward via the existing `iter_walk_forward_splits`: train on prior seasons only.

## Model

`GradientBoostingRegressor` with the totals harness's `PARAMS`, target = **home margin**, with
the closing spread included as a feature so the model learns a *correction to* the line rather
than a from-scratch margin. Features are **differentials** (home minus away), not the sums the
totals model uses — a spread is about the gap, a total about the combined output.

## Outcome and inference

ATS win rate over 2016–2025 test seasons, wild cluster bootstrap by season (B = 2000, floor
1/2000), and the same `|edge|` buckets as `prereg-ats-tail-test.md`: [0,1), [1,2), [2,3), [3,5),
[5,inf). Holm across buckets. Two-sided.

## What I expect, recorded before running

**It will not beat the closing spread.** The market is efficient against a 154-model
professional panel; a GBM on 21 team-state features is unlikely to do better. I expect an
overall win rate within about a point of 50% and no bucket clearing 52.38% after Holm.

**If it appears to clear**, the first hypothesis is leakage, not edge. Required checks before
believing it: feature importances (a this-game feature at the top is the tell), the result with
the line dropped as a feature, and per-season stability. A single clearing bucket with no
confirmation window is not a system.

## Stopping rule

One run at the pre-registered settings. No hyperparameter search, no re-bucketing, no switching
to the opening line, no dropping seasons. If null, it is written up as null.
