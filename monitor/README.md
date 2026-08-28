# monitor — edge-decay tracking + walk-forward backtest

Operational truth tools for the [Floor Bias model](../v1/). Two questions a
published anomaly must keep answering: **is the edge still there?** (books
correct once a finding spreads) and **would the strategy have worked without
seeing the future?** (k-fold CV mixes seasons).

```bash
python monitor/run_monitor.py                 # decay tables, 2013–2025
python monitor/run_monitor.py --width 3       # trailing-window width
python monitor/run_walkforward.py             # train ≤ t−1, bet season t
python monitor/run_walkforward.py --threshold 1.75 --min-train 5
python monitor/roi_report.py                  # ROI of the deployed filter + figure
```

Files: `monitor.py` (per-season/trailing stats, Wilson CIs, slope trend test),
`run_monitor.py` (decay driver), `run_walkforward.py` (walk-forward backtest),
`bias_bins.py` (profit by bias bin + threshold sweep), `roi_report.py`
(ROI of the deployed filter, with intervals, plus the raw per-bet CSV),
`roi_hitrate_doc.py` (hit-rate/ROI splits by season and bias bin). Estimator
core imported from `../v2`.

## run_monitor — is the edge decaying?

If books start pricing censoring, the signature is: probit slope on
`biasTotals` → 0, the bias needed to clear the 52.38% hurdle rises, and the
bias>1.0 over-win% drifts to 50%. The monitor computes each per season and
over trailing windows, with CIs, plus an OLS trend test on the per-season
slope.

Flags:

- `SLOPE~0` — slope 95% CI includes 0 (signal weak/dead in that window).
- `UNPROF` — bias>1.0 win% CI lower bound below the 52.38% breakeven.

**Read flags on trailing windows, not single seasons.** At 20–100 bets/season
the win% CI half-width is ±10–14 pp against an edge of ~4 pp over breakeven,
so per-season `UNPROF` fires routinely on noise; the 3-season window
(~250 bets, ±6 pp) is the smallest honest unit.

Snapshot (2013–2025, run 2026-07-30): every trailing window since 2016-2018
has a positive, significant slope (recent windows ≈ +0.16 to +0.24,
p ≤ 7e-4); trend on the per-season slope is **+0.006/yr, p = 0.55 — no
decay**. The 2018-2020 window is the only one whose win% CI clears breakeven
outright; the rest sit above breakeven on the point estimate with the CI
straddling it, which is what a ~4 pp edge at these Ns looks like.

## run_walkforward — would it have worked in real time?

For each season t: fit the full pipeline (Tobit σ + probit) **only on seasons
< t**, then bet season t. No future data ever enters training — this is the
deployable protocol the k-fold tables can't certify. Two rules:

- **A** (v1 headline rule): bet the over where expected censoring bias > 1.0.
- **B** (k-fold rule): bet the over where trained-probit P(over) > 52.38%.

Note: the *operational* bet rule moved to **bias > 1.75** on 2026-08-11 (see
`bias_bins.py` and MODEL_GUIDE §3). These drivers deliberately keep 1.0 as
their default — the wider bucket has more games and therefore more power to
detect the signal decaying, which is a different question from where to bet.

Result (2013–2025 data, first bet season 2016, run 2026-07-30):

| rule | bets | win% | Wilson 95% | unit% | LR vs breakeven |
|------|------|------|------------|-------|-----------------|
| A: bias > 1.0 | 681 | **56.83%** | [53.1%, 60.5%] | +8.49% | p = 0.020 |
| B: P > 52.38% | 992 | 55.65% | [52.5%, 58.7%] | +6.23% | p = 0.039 |

9/10 test seasons profitable under rule A (2016 the exception). The pooled
Wilson **lower bound clears breakeven** for both rules, and the walk-forward
win rate matches the in-sample headline (56.62%) — the edge is not an
artifact of time-mixed cross-validation.

## roi_report — what does the deployed filter actually return?

`run_walkforward.py` answers *does it win*; this answers *what does a unit
risked earn*, for the filter actually deployed (**bias > 1.75**, not the 1.0
the decay drivers keep). Same walk-forward protocol; the only addition is a
season label per bet, which the equity curve and per-season bars need.

```bash
python monitor/roi_report.py                        # table + figure + CSV
python monitor/roi_report.py --threshold 1.0        # compare filters
python monitor/roi_report.py --self-check           # ROI maths assertions
python monitor/roi_report.py --no-fig --no-csv      # table only
```

**A unit is 1% of bankroll**, so the flat rule stakes exactly 1.00u per bet
and every stake, profit and drawdown below is on one scale.

Three ROI definitions, ranked as MODEL_GUIDE ranks them:

- **flat-stake unit ROI** — headline. Order-independent, and *affine in the
  win rate* at a fixed price, so the Wilson win-rate CI maps onto an exact
  ROI interval. No bootstrap needed.
- **¼-Kelly per unit staked** — secondary. Varying stake breaks the affine
  map, so its interval is bootstrapped (10k resamples).
- **compounded bankroll** — equity curve only, labelled order-dependent.

Result (2013–2025 data, bet seasons 2016–2025, run 2026-08-28):

| metric | value | 95% interval |
|--------|-------|--------------|
| record | 151–83 (64.53%) over N=234 | win [58.21%, 70.38%] |
| flat-stake ROI @ −110 | **+23.19%** per unit risked | [+11.13%, +34.36%] |
| flat profit | **+54.27u** on 234u risked | — |
| ¼-Kelly ROI | +23.58% per unit staked | [+11.45%, +35.77%] (boot) |
| ¼-Kelly profit | +310.36u on 1,316u staked | — |
| ROI @ −120 | +18.30% | planning bound +6.72% |
| max drawdown | 6.18u flat / 35.4u Kelly | — |

### Kelly in units — why flat is what ships

The two ROI percentages look interchangeable (+23.19% vs +23.58%) and are
not: flat's denominator is units *risked*, Kelly's is units *staked*, and
Kelly's turnover is **5.6× larger**. Converting to units makes the
distinction visible, and makes the stake sizes visible with it:

| ¼-Kelly stake | min | median | mean | max |
|---|---|---|---|---|
| units (= % of bankroll) | 1.37u | 5.25u | 5.63u | **11.20u** |

Quarter-Kelly wants **11% of bankroll on a single game**, and 5% on the
median one. That is what Kelly says when it is sized off a point-estimate
win probability with no allowance for estimation error — at p ≈ 0.65 and
b = 0.909, full Kelly is ~26% of bankroll and the quarter is ~6.6%. Add that
a college slate settles simultaneously (several 5u bets live at once, which
sequential Kelly does not model) and the realised drawdown is 35u against
flat's 6u for the same 151–83.

Flat 1u per qualifying bet is the deployable rule. The Kelly column is there
to show the edge is big enough that a stake rule *could* exploit it harder,
not as a recommendation.

### Raw backtest CSV

`docs/data/backtest_bets.csv` — one row per graded walk-forward game, **all
10,255 of them**, not just the 234 clearing the filter, so the bias-bin table
in [ROI_HITRATE.md](../docs/ROI_HITRATE.md) is reproducible from the file
alone. Columns: game identity (`game_id`, `season`, `week`, `date`, teams),
the inputs (`spread`, `total`, `fav_pts`, `dog_pts`, `actual_total`), the
out-of-sample model output (`bias`, `model_prob`), the result (`over`), and
the stake ledger (`passes_filter`, `flat_units_risked`, `flat_units_pnl`,
`kelly_units`, `kelly_units_pnl`).

Pushes are absent — `walk_forward_bets` drops them, and matching the analysis
exactly matters more than being literally every game. Rows are aligned to the
model arrays *by construction* (built inside the walk-forward loop, sliced by
the same mask), and every run re-reads the file and asserts the re-derived
record, flat ROI and Kelly ROI equal the in-memory headline before reporting
success.

**Plan on the lower bound, not the point estimate.** The 1.75 threshold was
chosen partly on this data, so +23% is inflated by selection; +11% is the
number to stake against. At −130 the planning bound is +3.0%, which is why
the operational rule caps the price at −120.

Two things the figure deliberately puts in front of the reader:

- **2025 is the largest sample and the flattest result**: 27–24, +1.07% ROI
  on n=51, against a pooled +23%. Its own CI is [−24.5%, +25.9%] — wide
  enough to contain both the pooled estimate and breakeven, so it is not
  evidence of decay on its own. `run_monitor.py` is the test that measures
  decay directly, and as of the last run it finds none.
- **The sample is back-loaded**: 2–51 bets per season, with 68% of all bets
  coming from 2022 onward. The pooled figure is mostly recent data.
