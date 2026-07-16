# Floor Bias 1H — first-half extension (ready to run)

Extends the [Floor Bias model](../v1/) to **first-half** totals. Theory predicts
a *stronger* over edge: a half has ~half the expected points, so each team's mean
sits closer to the 0 floor, censoring binds harder, and the expected censoring
bias is ~2.3× larger.

```bash
# APPROX mode (runs now; 1H line = frac × game line):
python paper_models/floor_bias_1h/run_1h.py
python paper_models/floor_bias_1h/run_1h.py --total-frac 0.52   # de-bias 1H excess

# REAL mode (true backtest once you have 1H lines):
python paper_models/floor_bias_1h/run_1h.py --half-lines my_1h_lines.csv
```

Files: `floor_bias_1h.py` (loader + pipeline), `run_1h.py` (driver). Estimator
core (Tobit, censoring bias, probit, Kelly) imported from `../v2`.

## Why it should be stronger (mechanism, real data 2013–2025)

| | full game | first half |
|--|-----------|-----------|
| Underdog mean / σ | 21.1 / 12.1 | 10.5 / 7.7 |
| P(team scores 0) — underdog | 3.5% | **13.8%** (3.9×) |
| Mean censoring bias (biasTotals) | 0.28 | **0.65** (2.3×) |
| Games clearing bias > 1.0 | 5.5% | **14.4%** (~3×) |

The floor binds far harder in halves, and there are ~3× more qualifying bets.

## The data gap (read this)

CFBD gives 1H **scores** (quarter line-scores; 1H = Q1+Q2) but **not** 1H
**lines**. So the module runs two ways:

- **REAL** (`--half-lines`): a true backtest on the actual 1H market. Supply a
  CSV with columns `game_id,half_spread,half_total`. The model uses those exact
  lines. **This is the mode that produces a trustworthy edge.**
- **APPROX** (default): 1H line = `frac × game line`. With `total_frac = 0.5`
  this is the paper's latent-symmetric prediction (implied 1H team points = full
  implied / 2). Caveat: actual 1H scoring runs ~1.1 pt above half the game, so
  `0.5` lets that structural excess inflate the apparent edge. `--total-frac 0.52`
  removes it.

## Results — APPROX mode (illustrative, NOT validated)

| metric | total_frac 0.50 | total_frac 0.52 |
|--------|-----------------|-----------------|
| baseline 1H over rate | 51.99% | 48.22% |
| probit slope (p) | +0.198 (2e−11) | +0.210 (4e−11) |
| over @ bias>1.0 | 58.27% (N=1778) | 55.89% (N=1299) |
| over @ bias>1.75 | 71.88% (N=256) | 69.23% (N=169) |
| 5-fold OOS | 5/5 folds +, 58.2% | folds + , ~55% |

**Robustness finding:** raising the line to 0.52× drops the baseline over rate to
48% (removing the half-scoring excess), yet the censoring bias *still* predicts
the 1H over at 55.9% with a significant probit slope and positive OOS folds. The
edge is therefore **not** just the structural half-excess — the floor-censoring
mechanism carries independent signal, exactly as theory predicts.

## Caveats

- APPROX results are **mechanism illustration**, not a real backtest. A real
  book may price 1H censoring better or worse than the full game; only
  `--half-lines` settles it.
- Favorite/underdog and the 1H spread are derived from the **full-game** spread
  in approx mode; real 1H spreads differ.
- The compounded ¼-Kelly ROI figures in approx mode are not meaningful (large
  win rates over ~1,800 sequential bets compound explosively); read win% and
  unit% instead.
- 1H **spreads** are not expected to carry an edge (favorite/underdog censoring
  biases partly cancel, as in the full-game spread). The edge is on 1H **totals
  (over)**.

## To run a real backtest

Get historical 1H closing lines (sportsbooks post them; some odds APIs/archives
carry first-half markets), write them to `game_id,half_spread,half_total` keyed
on CFBD game ids, and pass `--half-lines`. The model is otherwise ready.
