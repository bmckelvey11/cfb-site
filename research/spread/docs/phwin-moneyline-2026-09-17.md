# Does PT's `phwin` beat real moneyline prices? — 2026-09-17

**EXPLORATORY.** Not registered in `prereg-line-movement.md`. Follows
`phwin-accuracy-2026-09-17.md`, which found `phwin` is a real forecast (AUC 0.80) but is beaten
and encompassed by the spread — and which could not price anything, because the PT panel carries
no moneyline. This joins the warehouse's moneylines and asks the betting question directly.

## Question

Betting `phwin` against real moneyline prices: does it make money?

## Answer: no. It loses about 5-6 cents on the dollar at the median price.

| price | rule | bets | ROI | 95% CI (week clusters) |
|---|---|---|---|---|
| best across books | EV > 0 | 3,160 | −0.019 | [−0.078, +0.040] |
| best across books | EV > 2% | 2,883 | −0.023 | [−0.081, +0.033] |
| **median** | **EV > 0** | 2,720 | **−0.055** | **[−0.110, +0.0001]** |
| **median** | **EV > 2%** | 2,391 | **−0.061** | **[−0.119, +0.003]** |

Betting `phwin`'s +EV side loses about 5–6 cents on the dollar at the median price. At the best
price across books it is still negative — the difference between the two columns is line
shopping, not `phwin`.

> **Correction, 2026-09-17.** This table originally reported season-cluster intervals of
> [−0.104, −0.015] and [−0.124, −0.014] on the two median-price rows and described them as
> excluding zero. `base.MIN_CLUSTERS` was raised from 3 to 6 the same day (see
> `panel-ats-2026-09-17.md`), and **five season clusters no longer supports a bootstrap CI** — so
> this run now clusters by season-week, 96 clusters. The point estimates are unchanged; the
> intervals widen and now just touch zero (+0.0001 and +0.003). **The word "significantly" is
> withdrawn.** The data still points clearly one way — the upper bound is a hundredth of a cent —
> but it no longer clears a two-sided 95% bar, and the original intervals were produced by the
> same too-few-clusters bootstrap that generated the retracted `linecrunch` result.

The bet set skews to underdogs (win rate 0.33–0.36, home share ~0.48), which is what a forecast
that disagrees with prices in the tails produces.

## The control arm, and why it does not rescue anything

`phwin` is encompassed by the spread, so "phwin beats the moneyline" would be confounded with
"the spread beats the moneyline". Both arms were therefore run **on the identical bet universe**,
the spread arm taking its probability from a logit of home-win on the panel's own `line`, fit
walk-forward on strictly prior seasons.

| price | rule | bets | ROI | 95% CI (week clusters) |
|---|---|---|---|---|
| best across books | EV > 0 | 2,125 | +0.040 | [−0.025, +0.106] |
| best across books | EV > 2% | 1,558 | +0.067 | [−0.009, +0.154] |
| median | EV > 0 | 1,166 | −0.004 | [−0.077, +0.072] |
| median | EV > 2% | 672 | +0.022 | [−0.089, +0.142] |

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

## Follow-up: 2024–25 only, where the book panel is stable

The pooled result above mixes seasons priced by one book with seasons priced by six or seven, so
the unresolved +0.067 could have been line shopping rather than forecasting. Restricting to
**2024–25**, where the panel sits at 6.49–6.56 books a game, isolates it. Two seasons is below
the harness's 3-cluster floor, so the bootstrap clusters by **season-week instead — 43 clusters**
(`--cluster` overrides; the fallback is automatic). 1,592 games, mean overround 1.0435.

| price | rule | arm | bets | ROI | 95% CI (week clusters) |
|---|---|---|---|---|---|
| best | EV > 0 | phwin | 1,481 | +0.028 | [−0.056, +0.114] |
| best | EV > 0 | spread | 1,282 | +0.061 | [−0.022, +0.150] |
| best | EV > 2% | phwin | 1,394 | +0.015 | [−0.067, +0.098] |
| **best** | **EV > 2%** | **spread** | 1,032 | **+0.092** | **[−0.004, +0.193]** |
| median | EV > 0 | phwin | 1,118 | −0.035 | [−0.117, +0.044] |
| median | EV > 0 | spread | 458 | **−0.030** | [−0.130, +0.068] |
| median | EV > 2% | phwin | 973 | −0.036 | [−0.127, +0.057] |
| median | EV > 2% | spread | 250 | **−0.016** | [−0.184, +0.146] |

**This resolves the thread, and the answer is line shopping.** On the stable panel the spread arm
returns +0.092 at the **best** price and **−0.016 at the median** price. The typical book loses.
The entire positive number is the gap between the best of ~6.5 books and the middle one — which
is a real thing a bettor can do, but it is not the spread out-forecasting the moneyline, and it
would survive substituting any roughly-accurate probability for the model.

Two further reasons not to bank the +0.092: its interval still touches zero (lower bound −0.004),
and the per-season split remains unstable — 2024 at +0.149 against 2025 at +0.027 on the same
book panel.

`phwin` is negative at the median price in this window too (−0.035, −0.036), consistent with the
pooled result.

```bash
python research/spread/scripts/eval_phwin_moneyline.py --from-season 2024 --to-season 2025
```

## What this does not support

- **Not a claim that moneylines are beatable by the spread.** The +0.067 has a CI containing zero
  and rests on two seasons. Read it as unresolved, not as an edge.
- **Not a generalizable ROI.** Moneyline coverage is a **book-chosen subset** — 48% of games in
  2021–22 rising to ~58% by 2025. Books price moneylines on the games they want action on, so
  nothing here transfers to a full slate.
- **Five seasons is below the inference floor.** `base.MIN_CLUSTERS` is now 6, so the pooled run
  clusters by week rather than by season. Week clusters ignore season-regime correlation and are
  the less conservative unit; they are used because five season clusters cannot support a
  bootstrap CI at all.
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
`p × (decimal − 1) − (1 − p) > threshold`; ROI is profit per unit staked. Cluster
bootstrap for every interval, by season where the season count clears
`base.MIN_CLUSTERS` and by season-week otherwise (`--cluster` overrides).

```bash
python research/spread/scripts/eval_phwin_moneyline.py
```

Writes `data/processed/phwin_moneyline.json`.
