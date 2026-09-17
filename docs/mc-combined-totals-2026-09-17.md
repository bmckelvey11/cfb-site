# Monte Carlo: $20,000 bankroll across over-zero + Greenline totals, weeks 4–15 of 2026

Completed September 17, 2026. Reproduce with
`python scripts/mc_combined_totals.py --paths 100000`
(`--self-check` runs the copula and payout assertions).

## The question

Starting from a $20,000 bankroll on September 17, 2026 — week 3 played, weeks 4–15
of the regular season ahead — what does the ending bankroll distribution look like
if both totals strategies are bet: the over-zero floor-bias OVERs and the PFF
Greenline totals flags?

**Scope is the regular season only.** Bowls and the playoff are excluded: they run
on a different calendar and Greenline's flag volume is not established for them.
Adding them would roughly halve a normal week's Greenline volume across the bowl
stretch and give over-zero a handful of extra bets, so it widens the distribution
modestly in both directions without moving the conclusions.

## The answer in one paragraph

Median **$21,644 (+8.2%)**, with a 90% band of **$14,018 to $28,979** and a
**36.0% chance of ending the season down**. But that headline is a statement about
Greenline, not about the combination. Greenline supplies ~590 of the ~601 bets and
over-zero supplies ~11, so over-zero on its own moves the median by **+0.7%**
($20,133) and cannot move it further at any sane stake. And Greenline has no
established edge — its own season review says so, and 35% of the simulated paths
draw a Greenline win rate below break-even. This is a variance projection, not an
expected-value projection.

## Method

One path = one whole remainder-of-season, 100,000 paths.

**Win rates are drawn, not fixed.** Each path draws its own win rate from the
Jeffreys Beta posterior of that strategy's graded record:

| leg | record | source | posterior mean | P(below break-even) |
|---|---|---|---:|---:|
| over-zero OVER | 151–83 walk-forward, 2016–2025 | `models/over_zero/docs/ROI_HITRATE.md` | 64.5% → **58.2%** after haircut | 12% |
| Greenline totals | 27–22, 2026 week 2 | `research/totals/docs/greenline-season-review-2026-09-16.md` | **55.0%** | 35% |

This is the load-bearing choice. Fixing Greenline at 55.1% would produce a
confident-looking curve resting entirely on a number its own source disclaims
("**any claim that Greenline totals beat break-even**… n=49, CI 41–68%"). Drawing
it keeps 35% of paths on a losing strategy, which is what n=49 actually buys.

The over-zero draw takes MODEL_GUIDE.md's instruction literally and subtracts a
6.3-point selection haircut (64.5% → 58.2%), because the 1.75 threshold was chosen
on the same data that produced the 64.5%.

**Volume.** over-zero's season count is front-loaded into the FCS-cupcake weeks
that have already played. Week-4-and-later counts by season were 2021–2025:
8, 11, 9, 11, 14. Paths resample that, then Poisson it: **~11 bets for the entire
rest of the season**, not the 12–14/week the published board showed in weeks 1–2.
Greenline draws Poisson(49) totals flags per week: 49 gradeable in week 2 and 57
flagged in week 3, and 49 is used as the conservative floor of the two — **~590
bets** across the 12 weeks. Using 53 would scale the Greenline leg by ~8% and move
no conclusion.

The over-zero volume assumption has one direct check. 2026 published 25 picks in
weeks 1–2; the 2025 backtest had 26 over the same weeks. That agreement is what
licenses extrapolating the backtest's week-4+ history to 2026, and it pre-empts the
obvious objection that the board showed 12–14 picks a week. The two counts are
different constructions — published per-book union vs market-consensus qualifiers —
so read it as reassurance, not validation.

**Correlation.** Bets inside a week share one scoring-environment shock through a
Gaussian copula. **ρ = 0.10 is assumed, not estimated** — one graded Greenline week
cannot measure it — so a ρ = 0.25 row is run alongside, and finding 4 below is
stated as a range rather than a point. Because over-zero is all overs and
Greenline is ~85% unders, that shared factor correlates the two legs *negatively* —
a high-scoring Saturday pays over-zero and hurts Greenline. Conditional on the
shock, bets are independent, so each week's win count is a single binomial draw.

**Prices per leg**, not one blended price: over-zero at −120 (its operational rule,
break-even 54.55%), Greenline at −110 (how it is graded, break-even 52.38%).

**Pushes are not modelled.** All 234 graded over-zero bets and all 49 graded
Greenline totals sat on half-point lines. Realised push rate: zero.

**Staking** is flat, as a fraction of the *starting* $20,000 — no compounding.
MODEL_GUIDE.md §"compounded bankroll" explicitly warns off compounded figures for
this strategy, because simultaneous Saturday kickoffs make within-slate compounding
impossible.

## Results

All figures: 100,000 paths, ρ = 0.10, over-zero at 1% ($200/bet) unless stated.

| scenario | staked | median | 5th pct | 95th pct | P(down) | P(−50%) | busts mid-season |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Greenline 0.25% ($50), over-zero 1% — headline** | $31.5k | **$21,644** | $14,018 | $28,979 | **36.0%** | 0.5% | 0.0% |
| Greenline 0.50% ($100), over-zero 1% | $60.9k | $23,158 | $7,924 | $37,842 | 36.6% | 7.8% | 0.6% |
| Greenline 1.0% ($200), over-zero 1% | $119.7k | $26,185 | −$4,306 | $55,618 | 36.9% | 19.1% | **8.7%** |
| Over-zero only | $2.1k | $20,133 | $19,100 | $21,133 | 39.3% | 0.0% | 0.0% |
| Greenline only, 0.25% | $29.4k | $21,509 | $13,877 | $28,882 | 37.2% | 0.6% | 0.0% |
| Headline at ρ = 0 (variance check) | $31.5k | $21,647 | $14,736 | $28,330 | 34.6% | 0.3% | 0.0% |
| Headline at ρ = 0.25 (sensitivity) | $31.5k | $21,656 | $13,141 | $29,859 | — | 0.7% | 0.0% |
| Headline, no over-zero haircut | $31.5k | $21,882 | $14,286 | $29,229 | 34.0% | 0.4% | 0.0% |

**Read the last column before the others.** Stakes are flat off the starting
$20,000 with no stop-loss, so a path that goes through zero keeps betting. In the
1% row, 8.7% of paths do exactly that — its 1st, 5th and 10th percentiles
(−$16,633, −$4,306, $2,385) are arithmetic, not outcomes anyone could have. The
median of that row survives the contamination; its left tail does not.

Headline scenario, full percentiles:

| pct | 1% | 5% | 10% | 25% | 50% | 75% | 90% | 95% | 99% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ending bankroll | $10,997 | $14,018 | $15,702 | $18,542 | $21,644 | $24,703 | $27,406 | $28,979 | $31,789 |

Worst single week in the headline scenario: median −$945, 5th percentile −$1,761.

## What the numbers say

**1. Over-zero is a rounding error from here.** ~11 bets × $200 at 58.2% is a
median of +$133 over twelve weeks. Its whole season was decided in weeks 1–3.
Its 5th–95th band is $19,100–$21,133 — it cannot lose you much and cannot make you
much. Any meaningful return for the rest of 2026 has to come from Greenline.

**2. Which means the projection is a Greenline projection, and Greenline has no
established edge.** P(down) sits near 36% across every combined scenario
(36.0 → 36.6 → 36.9 as the stake quadruples). That flatness is forced, not
discovered — flat staking off a fixed base makes terminal P&L linear in the unit,
so the sign of the result stops depending on the unit once it is large enough to
matter. The claim worth keeping is the one underneath it: **stake size moves the
spread, not the sign.** No unit converts an unestablished edge into a likely profit.

The 36% itself is roughly, not exactly, the 35% posterior mass below break-even.
Sampling noise is not negligible — 49 bets a week at ρ = 0.10 gives a season
win-rate sd of about 0.049 against a posterior sd of about 0.07; convolved,
Φ((0.5238 − 0.55) / 0.0855) ≈ 0.38. The two effects are close in size and the
agreement is partly coincidence.

**3. Greenline has no stake that is both meaningful and survivable.** 49 bets a
Saturday at 1% is 49% of bankroll at risk in one afternoon on ~85% same-direction
unders. At that stake the 1st percentile path is **−$16,633** — arithmetically
negative, i.e. bust well before week 15, because the model flat-stakes off the
starting bankroll with no ruin stop. Even 0.25% puts ~12% of bankroll on one
correlated slate every week. And there is no principled way to trim to a top-N:
the season review found PFF's own `value` ranking does not order outcomes
(top half 13–11 vs bottom half 14–11 on totals). This is a structural property of
the strategy as specified, not a tuning parameter.

**4. Correlation matters in the tail, not the middle.** The median is flat across
ρ ($21,647 at 0, $21,644 at 0.10, $21,656 at 0.25) while the tail is not: the 1st
percentile runs $11,968 → $10,997 → $9,703 and the worst expected week runs
−$468 → −$945 → −$1,429. So across the plausible range, treating 590 mostly-unders
as independent understates the bad week by roughly 2–3x. ρ is assumed; what is
robust is the direction and rough magnitude, not a specific tail number.

**5. The two legs can collide.** Week 2, Rice @ Notre Dame: over-zero published
OVER 54.5, Greenline flagged UNDER 55.5. Same game, opposite sides — a hedge
paying −110/−120 on both, not two bets. It was 1 of 11 over-zero picks that week
and rare only because over-zero's early-season picks are FCS cupcakes PFF does not
flag. As over-zero's remaining bets shift toward FBS matchups, collision frequency
goes up. **"Combined" needs a stated conflict rule before this is bet.** None exists
in the repo today.

## What this does not support

- **Any claim that this combination is +EV.** Greenline drives it and its record is
  27–22 on one graded week. 36% of paths lose money precisely because the data does
  not rule out a losing strategy.
- **The median as a forecast.** It is the median of a mixture that includes a 35%
  chance the larger leg has no edge at all. Read the whole distribution.
- **Anything about Greenline spreads or moneylines.** Totals only; spreads went
  21–28 in week 2 and their stated probabilities were worse-calibrated than a coin.
- **The Greenline volume assumption past a few weeks.** 49 and 57 flags are two
  observations. If PFF's projection stops sitting below the market, the leg shrinks.
- **Repriced results.** Greenline grades at PFF's captured number;
  `match_greenline_books.py` shows books hang a different number on a third of the
  slate. Real fills will differ.
- **Ruin dynamics.** Flat stakes come off the fixed $20,000 with no stop-loss and no
  bust rule. The "busts mid-season" column reports how often a path passes through
  zero (8.7% at the 1% Greenline stake), but the percentiles for those rows still
  assume betting continued — they flag the sizing problem rather than measuring
  what a real, ruin-stopped bankroll would have done.

## What would settle it

The Greenline season review's own answer: four more graded weeks gets totals to
n ≈ 250, where a true 56% separates from 52.38% about half the time; eight weeks
gets there reliably. Keep capturing Wednesday
(`scripts/pull_pff_scoreboard.py --greenline`), grading Monday
(`research/totals/scripts/grade_greenline.py`), and rerun this simulation with the
updated record — `GL_WINS` / `GL_LOSSES` at the top of the script are the only
values that need to change.

## Data and dates

over-zero: 234 walk-forward graded bets, seasons 2016–2025, from
`models/over_zero/docs/backtest_bets.csv`; 2026 published record 17–8 through week 2
from `models/over_zero/site/lib/weekly-results.json` (not used as a prior — the
walk-forward record is). Greenline: 49 graded totals flags, 2026 week 2, from
`data/ingest/pff_scoreboard/greenline_graded.csv`; week-3 volume from
`data/ingest/pff_scoreboard/pff_greenline_2026_w3.csv`. Projection span: weeks 4–15,
2026 regular season. Seed 20260917.
