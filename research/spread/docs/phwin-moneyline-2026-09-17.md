# Does PT's `phwin` beat real moneyline prices? — 2026-09-17

**EXPLORATORY.** Not registered in `prereg-line-movement.md`. Follows
`phwin-accuracy-2026-09-17.md`, which found `phwin` is a real forecast (AUC 0.80) but is beaten
and encompassed by the spread — and which could not price anything, because the PT panel carries
no moneyline. This joins the warehouse's moneylines and asks the betting question directly.

## Question

Betting `phwin` against real moneyline prices: does it make money?

## Answer: no. It loses, significantly so at the median price.

| price | rule | bets | ROI | 95% CI (season clusters) |
|---|---|---|---|---|
| best across books | EV > 0 | 3,160 | −0.019 | [−0.074, +0.035] |
| best across books | EV > 2% | 2,883 | −0.023 | [−0.076, +0.019] |
| **median** | **EV > 0** | 2,720 | **−0.055** | **[−0.104, −0.015]** |
| **median** | **EV > 2%** | 2,391 | **−0.061** | **[−0.124, −0.014]** |

At the median price both intervals exclude zero: betting `phwin`'s +EV side loses about 5–6
cents on the dollar. At the best price across books it is still negative, with intervals that
include zero — the difference between the two columns is line shopping, not `phwin`.

The bet set skews to underdogs (win rate 0.33–0.36, home share ~0.48), which is what a forecast
that disagrees with prices in the tails produces.

## The control arm, and why it does not rescue anything

`phwin` is encompassed by the spread, so "phwin beats the moneyline" would be confounded with
"the spread beats the moneyline". Both arms were therefore run **on the identical bet universe**,
the spread arm taking its probability from a logit of home-win on the panel's own `line`, fit
walk-forward on strictly prior seasons.

| price | rule | bets | ROI | 95% CI |
|---|---|---|---|---|
| best across books | EV > 0 | 2,125 | +0.040 | [−0.005, +0.094] |
| best across books | EV > 2% | 1,558 | +0.067 | [−0.009, +0.143] |
| median | EV > 0 | 1,166 | −0.004 | [−0.027, +0.025] |
| median | EV > 2% | 672 | +0.022 | [−0.029, +0.118] |

The spread arm's +6.7% at the best price is **not an established edge**, and it should not be
read as one. Every interval contains zero, and the per-season path shows why:

| season | books/game | spread bets | spread ROI |
|---|---|---|---|
| 2021 | 1.00 | 93 | **+0.249** |
| 2022 | 1.00 | 156 | −0.031 |
| 2023 | 1.89 | 277 | −0.029 |
| 2024 | 6.49 | 546 | **+0.149** |
| 2025 | 6.56 | 486 | +0.027 |

Two of five seasons carry the pooled number, and the largest per-bet ROI sits on the smallest
sample (93 bets in 2021, from a single book). Three seasons are flat or negative. That is the
shape of noise across five clusters, not a strategy.

## The confound that would have produced a false positive

**The book panel thickens by a factor of six inside the sample**: 1.00 books per game in 2021–22,
1.89 in 2023, 6.49–6.56 in 2024–25. "Best price across books" is therefore not one series — in
2021–22 it is a single book with no shopping at all, and by 2024 it is the best of six or seven.

Any pooled best-price result mixes a real effect (line shopping, which only exists where there
are books to shop) with whatever the model is doing. That is why the median-price series is
reported beside it: median is comparable across seasons, and on the median series the spread arm
is flat (−0.004) and `phwin` is significantly negative.

Mean overround on the median price is **1.0433** — a 4.3% hold, which is the bar both arms had to
clear.

## What this does not support

- **Not a claim that moneylines are beatable by the spread.** The +0.067 has a CI containing zero
  and rests on two seasons. Read it as unresolved, not as an edge.
- **Not a generalizable ROI.** Moneyline coverage is a **book-chosen subset** — 48% of games in
  2021–22 rising to ~58% by 2025. Books price moneylines on the games they want action on, so
  nothing here transfers to a full slate.
- **Five season clusters is thin.** It is above the harness's `MIN_CLUSTERS` of 3 but well under
  what would settle a marginal effect; the wide intervals are honest about that.
- **Not a version A or B read.** Amendment B3's stopping rule is untouched.
- **Not a test of E4.** `phwin` derives from `lineavg`, the raw unscreened panel mean.

## Method

Data: `data/ingest/prediction_tracker_lines.csv` joined on `game_id` to `core.fact_game_line`
moneylines, seasons **2021–2025** (the warehouse carries no moneyline before 2021), **3,792
games**. PT-home wins iff `y > 0`.

Two corrections that materially change the answer if skipped:

1. **Orientation.** `base.load()` orients `y` and `line` to PT's home team; `moneyline_home` is
   CFBD's. The sides are swapped on `orientation_flipped == 1` — **52 rows** inside this joined
   sample — and the script asserts the swap fired.
2. **Odds conversion.** American odds are converted to decimal **per book before any
   aggregation**. Averaging American odds across the ±100 discontinuity is meaningless.

Bet rule: back whichever side the model makes +EV at the offered price,
`p × (decimal − 1) − (1 − p) > threshold`; ROI is profit per unit staked. Season-cluster
bootstrap for every interval.

```bash
python research/spread/scripts/eval_phwin_moneyline.py
```

Writes `data/processed/phwin_moneyline.json`.
