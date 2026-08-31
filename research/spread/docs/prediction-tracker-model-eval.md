# Prediction Tracker model evaluation and ensemble — results

Implements `prediction-tracker-model-eval-plan.md`, which was written and committed
**before** anything was fit. Reproduce with `python research/spread/scripts/eval_prediction_tracker_models.py`.

17,731 games, 2001–2025. 154 model columns, 113 with ≥200 clean-coverage games, **80 with
≥3 seasons** (below that a season-clustered bootstrap is degenerate and no inference is
reported). Walk-forward evaluation 2006–2025; weights for season *t* see only seasons < *t*.
All inference is a wild cluster bootstrap at season level (25 clusters).

---

## Headline

> **CORRECTION, 2026-08-29.** `lineca` and `linemidweek` are **not computer models** — they
> are market lines reprinted inside the panel. `lineca` reproduces the closing line
> *exactly* on 65.6% of its games. Every claim below that rests on `lineca` being the best
> model is a tautology and is retracted; see **§10**. The main conclusion — no model and no
> combination beats the closing line — is unaffected and if anything strengthened, since the
> one column that "tied" the market was the market. Statements about the panel as a whole
> survive the removal of both columns (§10).

**No computer model beats the closing line, and neither does any combination of all 154 of
them.** The best single model, `lineca`, is statistically tied with the market
(ΔMSE +0.197, BH q = 0.066) — **but see the correction above: `lineca` is a market line, so
this is not a statement about forecasting skill.** The pre-registered ensemble is also tied (ΔMSE −0.191,
95% CI [−0.598, +0.230], p = 0.34; −0.248 [−0.517, +0.002], p = 0.063 once the line's own
recalibration is netted out — see §3).

This is a **tight null, not an underpowered one.** The CI rules out any improvement larger
than 0.656 MSE — about **0.021 RMSE**, a 0.13% gain — against a design that could have
detected 0.078 RMSE at 80% power.

**Where the models do add value: against a stale line.** Every result flips when the
benchmark is the opening number instead of the closing one. The market's own move from open
to close is what absorbs the models' information.

| | vs **opening** line | vs **closing** line |
|---|---|---|
| Benchmark RMSE | 15.770 | 15.617 |
| Models beating it (BH q<0.05) | **1** — `lineca` | **0** |
| Ensemble ΔMSE | **−2.64** [−4.39, −0.89], p<0.001 | −0.19 [−0.60, +0.25], p=0.34 |
| Is it the models, or a mis-scaled line? | models (recalibration alone: −0.04, p=0.83) | models (recalibration alone: +0.06, p=0.66) |
| Weight the fit puts on the model consensus | **0.53 – 0.64** | 0.18 – 0.23 |

---

## 1. Which models are best

Ranked by paired ΔMSE against the closing line on the model's own games — **never by raw
RMSE**. Raw RMSE is not comparable across models because they cover different game sets:
`linegrinder` has the single best raw RMSE in the file (15.22 vs the market's 15.62) and
still *loses* to the market by 5.08 MSE on the games it actually covers. It drew easier
games. That confound is the reason every number below is paired.

Filtered to ≥3,000 games and ≥3 seasons. Negative ΔMSE = beats the line.

| Model | n | Seasons | RMSE | Volatility | ΔMSE vs close | q | ΔMSE vs open | q |
|---|---|---|---|---|---|---|---|---|
| **lineca** | 15,007 | 21 | 15.545 | 15.543 | **+0.197** | 0.066 | **−5.089** | 0.000 |
| **linemidweek** | 9,736 | 13 | 15.704 | 15.702 | +2.048 | 0.000 | **−2.640** | 0.114 |
| lineespn | 6,699 | 9 | 15.925 | 15.913 | +10.06 | 0.000 | +4.88 | 0.070 |
| lineteamrank | 7,551 | 10 | 16.003 | 15.999 | +11.27 | 0.000 | +6.27 | 0.009 |
| lineatom | 9,595 | 13 | 15.999 | 15.999 | +11.40 | 0.000 | +6.28 | 0.000 |
| linedokter | 14,347 | 20 | 15.920 | 15.911 | +11.55 | 0.000 | +6.19 | 0.000 |
| linepimean | 9,763 | 13 | 16.070 | 16.066 | +13.44 | 0.000 | +8.79 | 0.000 |
| lineash | 11,182 | 16 | 16.059 | 16.059 | +14.09 | 0.000 | +9.08 | 0.000 |
| linepig | 15,671 | 22 | 16.075 | 16.075 | +14.25 | 0.000 | +9.72 | 0.000 |
| linesag *(Sagarin)* | 17,709 | 25 | 16.295 | 16.295 | +21.66 | 0.000 | +15.82 | 0.000 |

Worst of the well-covered models: `linesportrends` (+100.2), `linesuper` (+97.4),
`lineloud` (+92.4), `lineclean` (+82.8) — RMSE 18.1–18.5 against a market at 15.6. These
are not marginal; including them is what sinks naive averaging (§3).

**`lineca` is the standout** — and §10 explains why, which is not to its credit. 21 seasons,
15,007 games, the only column that ties the closing line and the only one that clearly beats
the opening line. `linemidweek` is second on both. **Both are market lines, not models.** A
column that reproduces the closing number is trivially tied with the closing number and
trivially beats the opening one.

### Accuracy and volatility are the same ranking

You asked for most accurate *and* least volatile. Empirically they are one question here:
Spearman correlation between the RMSE ranking and the volatility ranking is **0.9994**.

The reason is that these models are essentially unbiased — median |bias| across models is
0.34 points, max 3.98. With bias near zero, `volatility = √(MSE − bias²) ≈ RMSE`. There is
no model in this file that is accurate-but-erratic or steady-but-wrong; a model's mean error
tells you almost nothing its error spread doesn't.

*(Volatility is pre-committed as error SD with the model's own bias removed. Fixed in the
plan before fitting, precisely so that a model winning on one dispersion measure and losing
on another couldn't be chosen after the fact.)*

### Skill persists across seasons

Mean Spearman correlation of model skill rank between consecutive seasons: **0.775** over 24
season pairs (range 0.19–0.96). Last year's good models are usually this year's — which is
what makes the walk-forward screen in §3 work at all.

If "least volatile" means *consistent year to year* rather than *tight error spread*, the
answer is the same model. SD of a model's own season-level skill, models with ≥5 seasons:

| Model | Seasons | Mean skill | **SD across seasons** | Worst season | Best season |
|---|---|---|---|---|---|
| **lineca** | 21 | +0.17 | **0.50** | +1.04 | −0.50 |
| lineatom | 13 | +11.43 | 2.53 | +15.41 | +5.07 |
| linemidweek | 13 | +2.00 | 2.86 | +11.01 | −0.08 |
| lineharville | 8 | +17.47 | 3.33 | +21.99 | +12.85 |
| linepugh | 15 | +27.52 | 3.99 | +36.30 | +23.28 |

`lineca` is five times steadier than the next model and its *worst* season is +1.04 — it has
never been meaningfully worse than the closing line in 21 years. **That is what a reprinted
closing line looks like, not what a good forecaster looks like (§10).** Full table:
`pt_model_season_stability.csv` (69 models).

---

## 2. The market benchmark, and why the timing matters

| Forecast | RMSE | MAE | Bias |
|---|---|---|---|
| Closing line | **15.617** | 12.312 | −0.10 |
| Opening line | 15.770 | 12.425 | −0.06 |
| PT's own `lineavg` (mean of all models) | 15.953 | 12.605 | +0.06 |

Prediction Tracker publishes model forecasts mid-week. Scoring them only against the closing
line charges them for information that did not exist when they were published — that is a
statement about staleness, not model quality. Both benchmarks are reported throughout for
that reason, and they answer different questions:

- **Opening line** → *did the modeler add information available at publication time?* Yes,
  for `lineca` and the ensemble.
- **Closing line** → *can this beat the number you can actually bet?* No, for everything.

---

## 3. The ensemble

Five combination rules, all fit walk-forward, all scored on the **same 12,803 games**
(common support — scoring each on its own subsample would reproduce exactly the coverage
confound from §1).

| | Rule | RMSE | ΔMSE vs close | 95% CI | p |
|---|---|---|---|---|---|
| — | **closing line** | **15.5010** | — | — | — |
| E1 | mean of all available models | 15.7990 | +9.33 | [+8.02, +10.53] | <0.001 |
| E2 | median of available models | 15.7632 | +8.20 | [+6.96, +9.39] | <0.001 |
| E3 | mean of top-20 by prior skill | 15.6244 | +3.84 | [+2.62, +4.98] | <0.001 |
| R0 | **recalibration only** — `β₀ + β₁·market`, no models | 15.5028 | +0.06 | [−0.18, +0.33] | 0.66 |
| **E4** | **market + 2-param consensus tilt** | **15.4948** | **−0.19** | **[−0.60, +0.25]** | **0.33** |
| E5 | ridge on the season's active set | 15.5051 | +0.13 | [−0.50, +0.76] | 0.68 |

The forecast-combination puzzle holds hard here. Averaging everything is **9.3 MSE worse**
than just reading the line, because the bad tail is genuinely bad. Screening to the top 20
recovers most of that but still loses. Only the deliberately 2-parameter E4 reaches parity,
and ridge over the full active set does no better than E4 despite far more freedom.

### The fitted model

E4, refit each season on all prior seasons, in margin space (`margin = −spread`):

```
predicted_margin = β₀ + β₁ · market_margin + β₂ · (consensus_margin − market_margin)
```

| Benchmark | β₀ | β₁ (market) | β₂ (consensus tilt) |
|---|---|---|---|
| vs closing (2023–25) | −0.30 … −0.46 | 1.022 … 1.024 | **0.18 … 0.23** |
| vs opening (2023–25) | −0.24 … −0.47 | 1.018 … 1.021 | **0.53 … 0.64** |

The coefficients are stable and they say something clean: **against the opening line, put
about 55% weight on where the model consensus disagrees with the market; against the closing
line, about 20% — and even that 20% does not pay.** β₁ ≈ 1.02 means a mild extrapolation of
the market number itself.

The screened top-20 is stable year to year, led by: `lineca`, `linemidweek`, `lineespn`,
`lineteamrank`, `linedokter`, `linepimean`, `linepibias`, `linepiratings`.

### Is it the models, or is the line just mis-scaled?

E4 has three free parameters, so testing it against the *raw* market bundles two different
claims: "the models add information" (β₂ ≠ 0) and "the line needs recalibrating"
(β₁ ≠ 1, and β₁ ≈ 1.022 in every single season). To separate them, **R0** — the same fit
with β₂ dropped — is the restricted model. E4 vs R0 differs *only* in β₂, so a rejection
there can only be about model information.

**Recalibration is worth nothing.** R0 gains +0.06 MSE over the raw closing line
(p = 0.66): the 2.2% under-extrapolation is real and stable but has no forecasting value.
Every bit of the Clark-West rejection is therefore attributable to the models.

| Comparison | Clark-West | Paired ΔMSE |
|---|---|---|
| E4 vs **raw** closing line | +0.596 [+0.180, +1.036], p = 0.005 | −0.191 [−0.598, +0.230], p = 0.34 |
| E4 vs **recalibrated** line (isolates β₂) | +0.451 [+0.184, +0.719], **p = 0.0005** | −0.248 [−0.517, **+0.002**], **p = 0.063** |

Isolating β₂ makes the estimate both larger and roughly twice as precise — removing the
recalibration noise sharpens the measurement of what the models contribute. It still does
not reach significance, and §4 shows it is not robust to K.

The two tests disagree, and that disagreement is the finding. Clark-West asks whether the
extra term has predictive content; the paired difference asks whether the bigger model
actually forecasts better once you pay to estimate that term out-of-sample. Deployment
hinges on the second. **The models do know something the closing line doesn't — just not
enough to overcome the noise in learning how much to trust them.**

Against the opening line the same decomposition is emphatic: R0 is worth −0.04 (p = 0.83),
while E4 vs R0 is −2.60 [−4.37, −0.82], p < 0.001. Models, not recalibration, both times.

### Decision value: it never pays

Betting E4's disagreements with the closing line at −110 (break-even 52.38%):

| Filter | Bets | Hit rate | ROI |
|---|---|---|---|
| any edge | 12,560 | 50.31% | −4.0% |
| \|edge\| > 1 | 1,374 | 50.80% | −3.0% |

Not close, at any threshold. A squared-error gain that never flips a profitable bet is not
deployable, and the plan said so before the number was computed.

---

## 4. Exploratory (post-hoc — excluded from the gate by the plan)

| Cut | Result | Verdict |
|---|---|---|
| Weeks 12–15 | ΔMSE −0.842, p = 0.020 | 1 of 5 week buckets tested → BH q = 0.10. **Not significant.** |
| Model-disagreement quartiles | nothing below p = 0.06 | No exploitable dispersion signal. |
| Sensitivity to K (pre-registered at 20) | K=5 +0.13, K=10 −0.01, **K=20 −0.20**, K=40 −0.08, K=80 +0.01 | **The pre-registered K landed on the single most favourable value.** The effect vanishes at every other K. |

That last row matters more than the other two. E4's small negative ΔMSE is not robust to a
parameter that was fixed arbitrarily in advance — which is evidence *for* the null, not
against it. Had K not been pre-registered, K=20 is exactly the value a search would have
selected and then reported as a finding.

---

## 5. What to actually use

- **If you have the closing line, use the closing line.** Nothing here improves on it, and
  the CI is tight enough to say that rather than merely fail to reject it.
- **If you are forecasting before close** — grading an opener, setting a midweek number,
  reacting to a stale book — the ensemble is worth a real 2.6 MSE. On one consistent sample
  (n = 14,347): opening line 15.7222 → ensemble 15.6359, against a closing line at 15.5508.
  **The ensemble recovers 50.4% of the market's own open-to-close move.** That is the
  sharpest single statement of what the 154 models collectively contain: about half of what
  the market itself learns between opening and closing. The panel-level version of this
  claim survives dropping the market-like columns (§10), at roughly 73% of the effect.
- **~~If you want one model rather than a blend, `lineca` is the only defensible pick.~~**
  **Retracted.** `lineca` is a reprinted market line (§10). Taking it as a forecast means
  betting the closing line into the closing line. There is **no** single column in this
  panel that beats the closing line on its own merits.
- **Do not average all the models.** It is 9.3 MSE worse than doing nothing.
- **Drop `lineca` and `linemidweek` before using this panel for anything.** They will
  dominate any skill screen and contribute nothing a market feed does not already give you.

Outputs under `{CFB_DATA_ROOT}/processed/`: `pt_leaderboard_{opening,closing}.csv`,
`pt_ensemble_spread_{opening,closing}.csv` (per-game ensemble spread and its edge vs the
market), `pt_e4_weights_{opening,closing}.csv`, `pt_model_eval.json`.

## 6. Limitations

- **Survivorship.** Models that stopped publishing may have been dropped for being bad. Skill
  is estimated only over the seasons a model was active, with no forward-fill, but the
  population of models is itself selected. Not fixable in-sample.
- **Game-selective missingness.** 111 model-seasons cover 30–75% of games while appearing
  across most weeks — they skip games rather than joining late, and a model that skips games
  it is unsure about looks better than it is. The leaderboard is restricted to the 997
  model-seasons at ≥95% within-season coverage to remove this; the unrestricted version is in
  the CSVs and is not to be used for ranking.
- **33 of 113 models have fewer than 3 seasons** and carry no inference at all. Several sit
  near the top of the raw ordering (`linesprs3`, `linefpi`, `linethocal`) — those placements
  are noise, and are reported with blank CIs rather than a rank.
- **The market benchmark is Prediction Tracker's own recorded line,** not an independently
  sourced closing price, and its exact capture time is undocumented upstream.

---

## 7. Follow-up: other model sources, and where the edge actually is

Added 2026-08-29, after the main analysis. **Everything in this section is exploratory** —
none of it was pre-registered, and the thresholds below were chosen after seeing results.

### Other prediction sources in the warehouse — mostly dead ends

| Source | Grain | Usable? |
|---|---|---|
| `stg.sp`, `stg.fpi`, `stg.srs`, `stg.talent`, `stg.ratings` | season × team, **season-final** | Only lagged a full season. Using them in-season is lookahead. `features.py` already lags them. |
| `stg.core_ratings` | has `throughWeek`, but every row is `postseason` week 1 | Season-final in practice. Same limit. |
| `stg.pregame_win_prob` | per game, 2013–2026 | Its `spread` column **is the market line echoed back** (−31.5, −35.0, −14.0 …), not an independent forecast. |
| `stg.game.homeStartElo` / `awayStartElo` | **per game, as-of** | The one genuine per-game pre-game rating in the warehouse, ~700 games/season back to 2001. |

The bigger problem is redundancy, not availability. Prediction Tracker already carries
`lineelo` (99.6% coverage), `linefpi`, `lineespn` (FPI-derived) and `linesag`. Elo-, FPI- and
Sagarin-flavoured signals have already been tested here **and already lost to the closing
line.** Adding SP+ or a fresh Elo is adding more of what did not work.

Nor is the ceiling a modelling-method problem: a ridge over 60+ active models did no better
than a two-parameter fit. When extra flexibility buys nothing, the constraint is signal, not
specification — gradient boosting or stacking would not change that.

### Where the edge actually is: the open-to-close window

§5 found the ensemble recovers 50.4% of the market's open-to-close move. Pushing on that:

| Quantity | Value |
|---|---|
| corr(ensemble's disagreement with the opener, actual line move) | **0.546** |
| Market's move direction called correctly | **65.7%** of 12,301 games |

The models predict **where the line is going**, not where the game lands. Betting the opener
on the ensemble's side, season-clustered CIs, break-even 52.38%:

| Filter | Bets | Hit rate | 95% CI | ROI |
|---|---|---|---|---|
| any edge | 14,069 | 52.11% | [50.76, 53.21] | −0.5% |
| \|edge\| > 1 | 6,154 | 53.01% | [50.87, 54.93] | +1.2% |
| **\|edge\| > 2** | **1,936** | **55.89%** | **[53.05, 58.65]** | **+6.7%** |
| \|edge\| > 3 | 512 | 61.33% | [55.55, 67.92] | +17.1% |

The same bets graded at the **closing** number: 50.1%, ROI −4.3%. The entire edge lives in
the gap between the two prices and is fully gone by close — which is the same finding as §3
seen from the betting side rather than the squared-error side.

### Why this is not yet a strategy

- **The opener may not be a price you can hit.** Prediction Tracker records an opening number;
  whether it was executable, and at what limit, is undocumented. Openers carry low limits.
- **Worse, the timing may not exist at all.** PT publishes model forecasts *mid-week* — by then
  the opener is gone. The real entry price is whatever the line is at publication time, which
  is somewhere between open and close and which this dataset does not contain. The true
  capture is bounded above by the table and below by roughly zero.
- **Post-hoc thresholds.** |edge| > 2 was picked after looking; five thresholds were examined.
- A CLV proxy of 65.7% alongside a −4.3% ROI at closing prices is a standing warning that
  **beating the close is not the same as winning**, and should not be used as the success
  metric here.

**The next test worth running is a timing test, not another model:** reconstruct the line
available at PT's publication timestamp (Action Network per-book history has intraday moves
CFBD lacks) and re-grade the |edge| > 2 bets at that price. That single number decides whether
any of this is real.

---

## 8. The timing test: cannot be run, and bounded instead

Attempted 2026-08-29. **The test as specified is impossible with the data on hand**, for two
reasons — one fixable by scraping, one not.

### Blocker 1 — line history barely exists (fixable)

`{CFB_DATA_ROOT}/raw/actionnetwork/history_*.json`, 10,868 files:

| | Files |
|---|---|
| Empty `[]` | 9,129 |
| Content, but **no timestamps** | 1,730 |
| **Timestamped `updated_at` history** | **9** |

All nine are from August 2026 — the season now in progress. The evaluation window is
2006–2025 and 14,347 games, so the usable overlap is zero. Note the staged table
`stg.actionnetwork_history` (146,273 rows) is *not* a substitute: flattening kept the current
snapshot and dropped the `history` array, so it has no time column at all.

The nine files do prove the endpoint returns real intraday history — `line_status: "opener"`
followed by `"normal"` ticks with ISO `updated_at` — so this is a collection gap, not a
capability gap.

### Blocker 2 — there is no publication timestamp (not fixable retrospectively)

**Prediction Tracker's archive does not record when each forecast was published.** The season
CSVs carry no time field of any kind. Even with perfect line history for all 17,731 games,
there would be no moment to grade *at*. No amount of odds scraping fixes this: the
information was never recorded on the forecast side.

This test can therefore never be run on the historical archive. It can only be run forward.

### What can be answered now: how fast the edge decays

Without a timestamp, substitute the line's own progress for elapsed time. Enter at
`open + f·(close − open)`; `f = 0` is the opener, `f = 1` the close. Bets are the ensemble's
disagreements at that entry price, season-clustered, break-even 0.5238.

| f | Fixed bet set (\|edge vs open\| > 2) | | Re-selected at the entry price | |
|---|---|---|---|---|
| | **hit** (95% CI) | ROI | **hit** (95% CI) | ROI |
| 0.00 | 0.5589 [0.530, 0.586] | **+6.7%** | 0.5589 [0.533, 0.590] | **+6.7%** |
| 0.25 | 0.5414 [0.518, 0.566] | +3.4% | 0.5264 [0.484, 0.565] | +0.5% |
| 0.50 | 0.5191 [0.500, 0.540] | −0.9% | 0.4928 [0.466, 0.519] | −5.9% |
| 0.75 | 0.4944 [0.473, 0.516] | −5.6% | 0.4943 [0.472, 0.516] | −5.6% |
| 1.00 | 0.5008 [0.479, 0.527] | −4.4% | 0.5040 [0.491, 0.517] | −3.8% |

**The edge is gone once about a quarter of the line move has happened.** At `f = 0.25` the
realistic (re-selected) interval already straddles break-even; by `f = 0.5` it is clearly
negative. Profitability requires entering essentially *at the opener*.

### What this implies

Prediction Tracker publishes mid-week — by construction, after the opener. So the honest
reading is that **the edge found in §7 is probably already gone by the time these forecasts
are public**, and §7's +6.7% should be treated as an unreachable upper bound rather than a
strategy. It is not disproven; it is unsupported, and the burden is on a forward test.

### The only thing that would settle it

Forward collection, which can start immediately since the 2026 season is under way:

1. Fetch Prediction Tracker's weekly page **with a capture timestamp** — the field the
   archive is missing.
2. Pull Action Network `history` for those games (the endpoint demonstrably works).
3. After one season, grade the \|edge\| > 2 bets at the line prevailing at capture time.

That single number decides it. Nothing in the existing archive can.

---

## 9. The forward collector

Built 2026-08-29 and **running** — `research/spread/scripts/collect_line_timing.py`. It closes the §8
blockers for games from here on. It cannot help the 2001–2025 archive; nothing can.

### What was actually wrong

The Action Network history endpoint *does* serve full-game line history. The existing
scraper never asked for it: `actionnetwork_client.DEFAULT_PERIODS` is
`("firsthalf", "firstquarter")`, on the reasoning that "full game lives in the scoreboard's
embedded markets" — but those embedded markets are a **snapshot, not history**. So 10,868
history files existed and not one carried a full-game price path.

The full-game period is named **`event`**. `game`, the obvious guess, returns an empty
payload, which is also why 9,129 of those files are `[]`.

### The two halves have very different urgency

| | What | Urgency |
|---|---|---|
| `snapshot` | PT's live `ncaapredictions.csv`, written as `ncaapredictions_{UTC}.csv` with a `captured_at` sidecar | **Time-critical.** PT overwrites in place and keeps no history — a week not captured is lost forever. |
| `history` | AN full-game history per event → `history_event_{id}.json` | Not urgent. The endpoint replays the whole path, so one call any time before the odds come down gets everything. |

That asymmetry is the design: only the PT snapshot has to run on a schedule.

```bash
python research/spread/scripts/collect_line_timing.py snapshot                 # weekly, mid-week
python research/spread/scripts/collect_line_timing.py history --season 2026 --weeks 1-16
```

Snapshots are content-hashed against the previous one, so running it often is harmless —
it writes only when PT actually changes.

### Scheduled, and running

Registered on Windows Task Scheduler 2026-08-29 via `research/spread/scripts/collect_line_timing.cmd`,
which wraps the Python entry point and appends every run to
`{CFB_DATA_ROOT}/logs/line_timing.log` — a silent failure in October is only discoverable
if there is a log to read.

| Task | Schedule | Why |
|---|---|---|
| `CFB-PT-Snapshot` | every **6 hours** | PT posts games progressively through the week and overwrites in place. Frequent capture pins `captured_at` to within six hours of publication, and the content hash means nothing is stored unless PT actually changed. |
| `CFB-AN-History` | **Mondays 09:00** | Backfills the week just played. Not urgent — one call replays the whole price path. |

Verified: snapshot task ran on demand with `Last Result: 0`.

**Two limitations worth knowing.**

1. **The tasks run only while the user is logged on.** Running them otherwise means storing
   account credentials in the task definition, which was deliberately not done. On a machine
   that is powered off for a weekend, that weekend's PT updates are lost — the one failure
   mode that cannot be repaired later.
2. `--season` defaults to the calendar year, which is correct from August to December and
   **wrong in January**, when bowl games still belong to the prior season. Run the January
   backfill by hand: `collect_line_timing.cmd history --season 2026 --weeks 1-16`.

### First run, verified

- **PT snapshot**: `ncaapredictions_20260829T134307Z.csv`, 8 games, `captured_at`
  `2026-08-29T13:43:07+00:00`. The live file carries the same column vocabulary as the
  archive (`lineopen`, `line`, `road`, `home`, `linesag`, `linefpi`, …) in a different
  order, which the union-by-name combiner already handles.
- **AN history**: 99/99 week-1 events written, **all usable** — median 7 books, median 526
  spread ticks per game, median 95 days of price path (max 148).

That density is far more than the test needs: reconstructing the line at an arbitrary
timestamp is a lookup, not an interpolation.

### What still has to happen

The collector produces inputs, not an answer. Once a season of snapshots exists:

1. Join each snapshot's games to `game_id` (reuse `research/spread/scripts/build_prediction_tracker.py`).
2. For each game, read the AN price at that snapshot's `captured_at`.
3. Re-grade the §7 `|edge| > 2` bets at that price.

Only then does the +6.7% become either a number or a dead end. Until a full season is
banked, treat §7 as an unreachable upper bound, per §8.

---
## 10. Correction: two panel columns are market lines, not models

Added 2026-08-29, from `research/spread/scripts/diag_market_proxy.py`, run as a robustness check on the
combination sweep (`prediction-tracker-combination-sweep.md`).

The check asks a question this analysis never asked: **is every column in the panel actually
a forecast?** Prediction Tracker's `line*` naming is just its convention, and the build
already excludes the obvious market columns (`line`, `lineopen`, `lineavg`, `linemedian`,
`linestd`). But it does not test the remaining 154 for market content.

Two of them fail badly.

| column | n | matches the close **exactly** | RMSE vs close | corr(dev from open, open→close move) |
|---|---|---|---|---|
| **`lineca`** | 15,003 | **65.6%** | **0.501** | **0.979** |
| **`linemidweek`** | 9,735 | **43.3%** | 1.447 | 0.835 |
| `linethocal` | 1,477 | 4.1% | 1.537 | 0.743 |
| *median of 143 columns* | — | ~0% | **6.20** | 0.188 |

A forecasting model does not reproduce a sportsbook number to the half-point on two thirds
of its games. `lineca` is a market line. `linemidweek`, which says so in its name, is a
midweek line. Neither belongs in a model leaderboard.

**This is the coverage-difficulty confound's sibling, and the plan did not anticipate it.**
Plan §8 listed four threats and handled each; "a column in the panel is the benchmark under
another name" was not among them. The pre-registered leaderboard's winner was a market feed.

### What it invalidates

Everything in §1 that treats `lineca` as the best model, and §5's single-model
recommendation. Those are retracted above. `lineca` sitting at ΔMSE +0.197 against the
closing line and −5.089 against the opening line is arithmetic, not skill: a column that
*is* roughly the closing line must tie the closing line and must beat the opening line by
about the size of the open-to-close move.

Its "five times steadier than the next model" stability is the same artifact.

### What survives

The panel-level results, attenuated but intact. Dropping the 15 most market-like columns
(top decile by the movement correlation, which includes both offenders):

| | all 154 | minus 15 | retained |
|---|---|---|---|
| E4 vs R0, opening (consensus) | −1.976 [−3.314, −0.648] p=0.0030 | −1.446 [−2.804, −0.043] p=0.0415 | **73%** |
| E14 vs R0, opening (subset reg.) | −2.615 p<0.0001 | −1.285 [−1.948, −0.641] p<0.0001 | **49%** |
| E6 vs R0, opening (ridge) | −3.521 p<0.0001 | −0.966 [−2.561, +0.640] **p=0.2560** | **27%** |
| Harvey–Newbold Wald, opening | 70.10, p<0.0001 | 29.09, p=0.0115 | still rejects |

So roughly a quarter of the *consensus* family's opening-line effect was market content
leaking in, and about three quarters is genuine model information. The claim "the panel beats
the opening line" holds; the claim "by 2.0 MSE" becomes "by about 1.4 MSE among actual
forecasters."

**The ridge is the exception and must not be quoted as model skill.** With a large regressor
set it loads on the partially market-anchored columns the consensus dilutes away, and 73% of
its effect goes with them. See `prediction-tracker-combination-sweep.md` §9 and §10.

**The closing-line null is unaffected in direction.** Market proxying can only push a test
*toward* rejecting, and the closing-line tests did not reject (Harvey–Newbold Wald 5.44,
p = 0.56). Removing proxies cannot create an edge that was not there.

### Two smaller checks run at the same time

- **Zero-fill exposure.** The sweep's residual design zero-fills absent models before
  projecting. If a game had *no* screened model, that would produce a spurious correction
  proportional to the market number. Actual count: **0 of 14,347 rows (opening) and 0 of
  14,353 (closing).** Non-issue.
- **Harvey–Newbold without the full-sample components.** The encompassing test mixes a
  walk-forward target with full-sample PCs. Dropping the PCs entirely: opening Wald 41.92
  (p < 0.0001), closing 2.48 (p = 0.3475). Same verdict both benchmarks — the result is
  consensus-driven and the PCA never mattered.
