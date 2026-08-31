# The model

## What it is

A `GradientBoostingRegressor` that predicts **total combined points** in a
college football game, using 35 pre-game features plus the betting line itself.

It does not predict over/under directly. It predicts a number, then that number
is compared to the line:

```
edge = line - prediction
```

Positive edge means the model thinks fewer points will be scored than the line
implies → **bet the under**. Negative → bet the over.

The **citable** decision row is `|edge| ≥ 0` (the unselected full book). Other
`|edge|` cutoffs are printed as diagnostics only — they are not a ship gate.

### Hyperparameters

```python
GradientBoostingRegressor(
    n_estimators=300, max_depth=3, learning_rate=0.05,
    subsample=0.8, random_state=0,
)
```

**These were never tuned.** They are first-guess defaults. That cuts both ways:
no hyperparameter search means no selection bias against the validation seasons,
but it also means there is no evidence these are good values.

## The features

| group | count | what it captures |
|---|---|---|
| **The line** | 1 | `ou_open` (opening total) or `total` (closing) |
| Pace | 2 | combined plays/game, drives/game — tempo drives totals |
| Mismatch | 6 | each offense's PPA/success **minus the defense it faces** |
| Weather | 6 | temp, wind, precipitation, humidity, elevation, dome |
| Efficiency | 12 | PPA, success rate, explosiveness (off/def × home/away) |
| Priors | 8 | talent composite, Elo, recruiting, returning production |

Havoc rates, reported attendance, and team-scoped `pregame_win_prob` were
removed. Those columns are this-game (or post-game) results, not entering-game
features. `tests/test_model.py::test_registry_excludes_result_lookahead_features`
fails if they come back.

### Why mismatch is computed, not averaged

An earlier version of this analysis averaged both teams' offensive stats. That
destroys the signal: *good offense vs bad defense* is the classic totals angle,
and averaging collapses it into a single mid-range number. Mismatch features
subtract the opposing defense from each offense, preserving the asymmetry:

```python
mm_h_ppa = home_offense_ppa - away_defense_ppa
mm_a_ppa = away_offense_ppa - home_defense_ppa
```

Honest footnote: fixing this did **not** rescue the signal. De-averaged mismatch
tested flatter than the averaged version. It is the right way to compute the
feature; it just is not a profitable feature on its own.

## The no-lookahead guarantee

This is the part most likely to be silently wrong, so it is isolated in one
function (`data._entering_game_stats`) and covered by a test.

Every team stat is an **expanding mean shifted one game**:

```python
df.groupby(["team", "season"])[col].transform(
    lambda s: s.shift(1).expanding().mean()
)
```

Week 5's feature averages weeks 1–4. Never week 5. A team's first game of a
season has no prior data and is dropped, as are games where either team has
fewer than three prior games (default `--min-prior-games 3`), because two-game
averages are too noisy to be worth the rows.

`tests/test_model.py::test_entering_game_stats_exclude_current_game` asserts
this directly on a hand-built three-game sequence.

## Validation

**Headline window: 2022–25, prior-season folds only.** Each test season trains
only on seasons before it. 2021 is week-expanding inside the year (no prior
opening lines) and is reported as an appendix, not mixed into the headline.

| test season | trained on | train games |
|---|---|---|
| 2022 | 2021 | 580 |
| 2023 | 2021–22 | 1,162 |
| 2024 | 2021–23 | 1,757 |
| 2025 | 2021–24 | 2,364 |

No season ever sees its own future. Training data is thin for 2022 because
opening lines only exist in the source data from 2021 onward.

**Permutation test.** Shuffling the model's predictions 500 times on the
headline book yields **49.91%** (95% CI 48.09–51.78). Observed hit rate is
**49.69%** — inside that null. This is the check that the grading metric is not
scoring itself.

**Pushes are dropped.** A game landing exactly on the number is void, not a win.

**Invalid previous figure.** 57.00% hit / +8.82% ROI / +1.52 pp open-vs-close
(2023–25) used current-game havoc, attendance, and post-game win probability.
Those numbers are not evidence of edge.

## Results

Betting against the **opening** total, walk-forward, **2022–25 prior-season
folds**. Hit/ROI intervals are week-clustered Wald 95% CIs. MDE is 80% power,
two-sided 5% (`2.8 · SE`). −110 breakeven is 52.38%.

**Citable row** (`|edge| ≥ 0`):

| n | record | hit % | hit 95% CI | MDE | ROI | ROI 95% CI |
|---|---|---|---|---|---|---|
| 2,383 | 1184–1199 | 49.69% | 47.66–51.71% | 2.89 pp | −5.15% | −9.01 to −1.28% |

Hit-rate CI sits entirely below 52.38%. ROI CI sits entirely below zero. There
is no evidence of a takeable edge on the clean feature set.

Diagnostic ladder (not a ship gate):

| min \|edge\| | n | hit % | hit 95% CI | ROI |
|---|---|---|---|---|
| 0 (citable) | 2,383 | 49.69% | 47.66–51.71% | −5.15% |
| 1 | 1,916 | 50.31% | 47.95–52.67% | −3.95% |
| 2 | 1,544 | 51.68% | 49.31–54.06% | −1.33% |
| 3 | 1,192 | 51.85% | 48.62–55.07% | −1.02% |
| 5 | 649 | 51.62% | 47.67–55.56% | −1.46% |

By season at the citable threshold: 2022 49.13%, 2023 50.00%, 2024 52.00%,
2025 47.66%.

### Paired score vs the line

Same games, week-clustered. Negative Δ would mean the model beats the line.

| score | mean Δ | 95% CI | MDE | n | clusters |
|---|---|---|---|---|---|
| MSPE `(pts−pred)² − (pts−line)²` | **+22.77** | +14.85 to +30.69 | 11.32 | 2,383 | 51 |
| MAE | **+0.60** | +0.37 to +0.83 | 0.32 | 2,383 | 51 |

The line is a better point forecast than the model. That comparison is
informative (observed Δ > MDE; CI excludes 0).

### Open vs close, same model, same games

`compare_lines.py` holds the predictions fixed and changes only which number is
bet. Games that push on either number are dropped so the Δ is paired. CLV is
`UNDER: open − close`, `OVER: close − open` on the side the model would have
bet at the open.

| | point | 95% CI | MDE | n |
|---|---|---|---|---|
| Δ hit (open − close), pp | +0.34 | −1.17 to +1.84 | 2.15 pp | 2,358 |
| mean CLV, pts | +0.065 | −0.029 to +0.160 | 0.135 | 2,408 |

Mean `|open − close|` is 1.59 pts. Both gaps sit inside noise (MDE > observed;
CIs include 0). This is not evidence that betting the open is worth more than
the close for these predictions.

### Appendix: 2021 week-expanding

Not in the headline. Six week-clusters, MDE 9.7 pp at `|edge| ≥ 0`.

| n | hit % | hit 95% CI | ROI |
|---|---|---|---|
| 257 | 52.53% | 45.76–59.30% | +0.28% |

Uninformative.

## Feature importance

Top features when trained on 2021–22 against the opening line (clean registry):

```
 20.28%  ou_open
  3.95%  home_running_explosiveness_off
  3.66%  away_running_ppa_def
  3.41%  pace_plays
  3.36%  away_running_explosiveness_off
  3.28%  temp
  3.04%  home_running_explosiveness_def
  3.03%  home_running_success_def
  2.97%  pace_drives
  2.79%  away_running_success_def
```

The line is still the single most important feature. Remaining share is spread
thinly across pace, explosiveness, and weather. There is no leftover havoc-sized
nudge — that signal was the leak.

## What would still sink a claim of edge

The clean backtest does not support a claim of edge. Independently of that:

1. **The opening lines may not have been takeable.** They come mostly from
   Bovada. Whether those numbers were available, at size, at the moment they
   posted, is untested.

2. **No vig modeling beyond −110.** Opening numbers frequently carry worse
   prices than −110.

3. **Multiple comparisons in the parent project.** Roughly 35 hypotheses were
   tested before this repo froze `|edge| ≥ 0` as the citable row.

4. **Four test seasons, week-clustered.** 2025 (47.66%) is the worst of the
   four. Season cells are descriptive, not a stability proof.

## The test that would actually settle it

Everything above is retrospective. The honest test is forward:

> For each game, log the number **available at the moment of the bet** and the
> number the market **eventually closed at**. Compare.

`python -m cfb_totals_model snapshot` / `clv` does that on takeable
DraftKings / ESPN Bet numbers. That is the measurement that can still change
the verdict.

