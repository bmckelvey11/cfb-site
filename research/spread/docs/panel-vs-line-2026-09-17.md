# What are the `line*` columns in PT's panel? — 2026-09-17

**EXPLORATORY, descriptive.** Not registered in `prereg-line-movement.md`. Pooled and in-sample
by design — this characterises the columns, it does not select among them. Walk-forward
selection is `prior_skill()` / `walk_forward()` in `eval_prediction_tracker_models.py`; use those
to pick a model, never this.

## Question

The panel carries ~140 `line*` columns, nominally independent rating systems. Are they real
forecasts, copies of the market line, or noise?

## Answer: real, distinct numbers — and not one of them beats the closing line.

### They are not copies of the line

| | value |
|---|---|
| model columns with ≥ 500 graded games | 141 |
| median R² of column on `line` | 0.829 |
| columns with R² > 0.95 | 5 of 141 |
| median sd of (model − line) | 6.23 pts |

The typical column sits 6 points away from the market on a typical game. These are genuinely
different numbers, produced by genuinely different systems. Only a handful (`linethocal`,
`linethoavg`, `linethoats` — R² 0.976–0.988, sd 1.5–2.2 pts) are close enough to be
market-derived.

### None of them forecasts better than the line

RMSE against the realized margin, as a ratio to the market line's RMSE **on each column's own
support** (so eras with different coverage stay comparable to their own benchmark):

| | value |
|---|---|
| **columns beating the line (ratio < 1)** | **0 of 141** |
| within 5% of the line | 37 |
| median ratio | 1.076 |
| best / worst ratio | 1.0036 / 1.772 |

The market line's RMSE is 15.62 points against a margin sd of 21.03. The best column in the
panel is 0.36% worse than that; the median is 7.6% worse; the worst is 77% worse.

### And skill is almost entirely explained by how closely a column copies the line

| correlation across the 141 columns | value |
|---|---|
| **corr(RMSE ratio, sd of deviation from the line)** | **+0.970** |
| corr(RMSE ratio, R² on the line) | −0.840 |

Binned by how far a column strays:

| sd of deviation | columns | mean RMSE ratio | best |
|---|---|---|---|
| < 3 pts | 4 | 1.0075 | 1.0036 |
| 3–5 | 28 | 1.0346 | 1.0111 |
| 5–8 | 81 | 1.0813 | 1.0320 |
| 8–12 | 21 | 1.1619 | 1.1152 |
| > 12 | 7 | **1.4981** | 1.2766 |

Perfectly monotone. At r = +0.97, **how far a column departs from the market line is how wrong it
is.** Departure from the line is error, essentially all of it. The best-performing columns are
the ones that deviate least, and the four closest hugs occupy the top of the table.

## Correction (same day): RMSE is not a bettability test

This document originally let the RMSE ranking carry more weight than it can. **RMSE is squared,
symmetric and averaged over every game; a bet needs only the sign of the disagreement, only on
the games you choose, and only 52.381% of the time.** A column can be worse on RMSE and still
have a sign edge at a threshold.

`panel-ats-2026-09-17.md` runs that test directly — 141 models × 3 thresholds, BH-corrected. The
broad null survives (2 of 330 testable cells above break-even, pooled 0.4981), but one column,
`linecrunch`, is **3.2% worse than the line on RMSE** and still posts 0.5418 ATS over 1,185 bets
with all three of its seasons above break-even. RMSE ranking would have discarded it.

Read the measurements below as what they are — a description of point-estimate accuracy — and
not as evidence about bettability. That question is answered in the ATS study.

## Why this matters for everything else in this tree

This is the mechanism behind the day's other nulls, stated at the source:

- `phcover` is a transform of `lineavg − line` (R² 0.994) and carries no signal
  (`phcover-accuracy-2026-09-17.md`). Of course it does not: `lineavg − line` is the panel's
  average departure from the line, and departure is error.
- Betting the panel's side goes 0.4943 ATS over 16,056 games
  (`linestd-confidence-2026-09-17.md`). Same reason.
- `phwin` is a transform of `lineavg` and is encompassed by the line
  (`phwin-accuracy-2026-09-17.md`). Same reason.

The panel is a large collection of competent-but-inferior forecasts of a number the market
already publishes better. Aggregating them does not fix that, because the thing being aggregated
is the part that is wrong.

## What this does not support

- **Not a walk-forward result, and not model selection.** Everything here is pooled and
  in-sample. A column's ratio is a description, not a forecast of its future ratio. The
  registered machinery for picking models is `prior_skill()` and `walk_forward()`.
- **Not a bettability result.** See the correction above and `panel-ats-2026-09-17.md`.
- **Not a claim that the panel is useless to the registered work.** E4 does **not** bet the
  panel's level against the line. It is anchored on the **opener** and uses a screened top-20
  consensus to forecast where the line will **move**. That is a different estimand and amendment
  A6's result on it stands. What this rules out is the naive use — treating a panel number as a
  better estimate of the margin than the closing line.
- **Not a statement about any single column's niche.** A column could be bad overall and useful
  on some subset; nothing here tests that.
- **Not a version A or B read.** Amendment B3's stopping rule is untouched.

## Method

Data: `data/ingest/prediction_tracker_lines.csv`, all seasons, `match_status == 'matched'`.
Margins oriented to PT's home team by `base.load()`. `MARKET_LINES` (`lineca`, `linemidweek`)
excluded — they are market prices, not models. Columns with fewer than 500 graded games skipped
(`--min-n`).

```bash
python research/spread/scripts/eval_panel_vs_line.py
```

Writes `data/processed/panel_vs_line.json`, including the full per-column table.
