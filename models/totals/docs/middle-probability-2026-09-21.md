# Live middle probability from drive-start observations — 2026-09-21

Supersedes [middle-probability-2026-09-18.md](../../../archive/docs/middle-probability-2026-09-18.md).
Two things in that version were wrong and are corrected here: the distribution was
anchored on its **mean** rather than its median, and the stated direction of the bias
was **backwards**. Method, data and filters are otherwise unchanged.

## The question

Given a totals bet already placed pregame and a live total that has moved, what is
the probability the final total lands inside the middle, and what is the bet worth?

## Why the obvious data source does not exist

The natural input is a history of live totals: for each in-game moment, the posted
total and the eventual final. The warehouse does not have one.

| Candidate | What it holds | Verdict |
| --- | --- | --- |
| `stg.oa_odds_tick` | 41,644 totals ticks, `pulled_at` 2026-09-09 → 2026-09-18, 758 rows after kickoff | Nine days. Post-kickoff rows are more likely stale pregame quotes than in-play prices. Unusable. |
| `raw.an_history` | 11,143 rows, per-book, keys `firsthalf` / `firstquarter` only | Period markets, no full-game line history, no season/week. Unusable. |
| `core.fact_game_line` | `total_open`, `total_close` per game/provider | Pregame only. |

So there is no live-total history to condition on, and a pregame σ is the wrong
quantity — σ(final − closing total) is ≈15 points, σ(final − live total) at 5:00
left is ≈6. A calculator built on the former would be wrong by a factor of two or
more in exactly the situation it is meant for.

## Method

Reconstruct the distribution from drive starts instead, which the warehouse has in
depth. Every row of `stg.drives` is an observation of (clock, score so far), and
the game's final total says how many points were still to come.

For each drive start:

- `min_rem` = `(4 − startPeriod) × 15 + startTime_minutes + startTime_seconds/60`,
  with `startPeriod ≥ 5` (overtime) mapped to 0 minutes remaining.
- `pts_so_far` = `startOffenseScore + startDefenseScore`.
- `rem` = `final_total − pts_so_far` — the target quantity.

The sample is cross-tabbed into `(min_rem bucket, remaining-points bucket)` cells.
The bucket key is proxied historically by `pregame_total × min_rem / 60`. Each cell
stores `n`, the mean of `rem`, and the integer histogram of `rem`.

At run time the calculator computes the anchor as `live_total − current_score`, picks
the matching cell, and shifts that cell's histogram so its **median** sits on that
number. The result is a distribution over integer final totals, which is folded into
the five branches of a totals middle and priced.

### Why the median and not the mean

A book posting the same price on both sides of a total is posting the number it
believes is a coin flip — the 50th percentile of its distribution, not its mean.
Remaining points is right-skewed: a handful of points is typical, a shootout or
overtime is the tail. So its mean sits above its median, and the gap widens as the
clock runs down and the tail dominates what is left.

The 2026-09-18 version anchored the mean. That pushed more than half the distribution
below the live number, and the error grew with the skew:

| Game state | P(final < live total), mean anchor | median anchor |
| --- | --- | --- |
| 31 pts, 18:00 left, live 58.5 | 0.498 | 0.521 |
| 10 pts, 40:00 left, live 51.5 | 0.529 | 0.517 |
| 45 pts, 9:00 left, live 66.5 | 0.622 | 0.594 |
| 55 pts, 2:00 left, live 59 | **0.729** | 0.500 |

Under the mean anchor the last row reported the live Under as a +41% edge. That was an
artifact of the anchor, not a read on the market. Median anchoring pulls every state
back to roughly a coin flip, which is what a two-way market at matched prices means.

**Limit:** this assumes the two live prices are equal. If a book posts Over −105 /
Under −115 the fair point is not the median, and the calculator does not take the
other side's price, so it cannot de-vig to find the right quantile.

### Recentring

The cell median is fractional — it is interpolated where the CDF crosses 0.5 rather
than snapped to an integer, so the shift stays smooth — and the user's anchor is
fractional, but the histogram is over integers. Rounding the shift to the nearest integer would bias the
whole distribution by up to half a point, which matters because a half point is
exactly the difference between a push and a win. So the shift is split across the two
neighbouring integers:

    shift = anchor − cellMedian(cell)
    k     = floor(shift)
    w     = shift − k

    P(rem = lo + i + k)     += cell.p[i] × (1 − w)
    P(rem = lo + i + k + 1) += cell.p[i] × w

`final_total = current_score + rem` is then an integer, so `final == X` is a real
comparison rather than a floating-point near-miss, and the push branches carry their
true mass.

### Pricing the five branches

With `lo = min(X, Y)` and `hi = max(X, Y)` over the two numbers, a totals middle has
five branches, and within each one both legs' outcomes are fixed, so the net is a
constant:

| Final total | Pregame Over X | Live Under Y | Net |
| --- | --- | --- | --- |
| `< lo` | loss | win | one leg's profit − other's stake |
| `= lo` | **push** | win | **one leg's profit** (stake refunded) |
| `lo < t < hi` | win | win | both legs' profit |
| `= hi` | win | **push** | **one leg's profit** |
| `> hi` | win | loss | one leg's profit − other's stake |

The pregame-Under case is the same table with the leg roles swapped. The push rows
are **winners net of a refunded leg, not half-losses** — a distinction that is easy
to get wrong and not negligible: on integer totals the two push branches carried 2.5%
of the mass in a representative late-game state (Over 52 / Under 56, 38 points scored,
6:00 left).

A leg's contribution is `stake × decimalProfit(price)` on a win, `0` on a push, and
`−stake` on a loss, where `decimalProfit` converts American odds. Stakes are
independent per leg, so unequal sizing works without special-casing. EV is
`Σ(branch probability × branch net)`.

### Validation

- **Cell histograms integrate to 1.** Worst cell mass error 1.9 × 10⁻⁴, from rounding
  stored probabilities to five decimals across ~100-bin histograms. Immaterial at the
  one-decimal-place the page displays.
- **Recentring conserves mass and hits its target.** For the default state (live total
  58.5, 31 points scored, 18:00 left) the recentred distribution sums to 1.00004 and
  has mean 58.503 — i.e. it lands on the live total, which is what "the market's
  estimate is unbiased" is supposed to mean.
- **EV math is tested against the shipped code.** `tests/test_middle_ev.py` extracts
  the JS from the page and runs it under node rather than testing a Python port that
  could drift. Eight cases: each of the five branches in both directions, half-point
  numbers carrying no push mass, branch probabilities partitioning the distribution,
  unequal stakes, plus-money payouts, and a wrong-way line move.

### Filters applied

- Completed games with a non-null `selected_total` and non-null scores.
- Clock sanity: `startTime_minutes` in 0–15 and `startTime_seconds` in 0–59 for
  regulation periods. The raw field carries junk — values up to 58 minutes appear
  on a 15-minute quarter, and 297 drives are stamped `startPeriod = 0`.
- `rem` in 0–120. A drive whose start score already exceeds the final total is a
  data error; 368 such rows were dropped.
- **Overtime is kept.** OT is legitimate right-tail mass on the total and is exactly
  what kills the Under leg of a middle. The 0–2:30 cell runs out to 63 remaining
  points because of it.

### Data and range

322,746 drive-start observations, seasons 2013–2026 (the join to `selected_total`
sets the floor; `stg.drives` itself starts in 2012). Cells below n = 100 are dropped.

### Sanity check on σ

| Minutes remaining | Expected remaining | n | σ of actual remaining |
| --- | --- | --- | --- |
| 52.5–60 (kickoff) | 50–55 | 10,988 | 15.4 |
| 25–30 (halftime) | 25–30 | 8,393 | 10.9 |
| 5–7.5 | 5–10 | 7,863 | 6.1 |
| 0–2.5 | 0–5 | 18,020 | 6.9 |

σ scales as √t as it should: 15.4 at kickoff, 10.9 at the half (√(27/60) × 15.4 =
10.3 predicted). The 0–2:30 cell breaks the pattern upward because overtime lives
there.

## Alternatives tested and rejected

### A pace-blended expected-remaining proxy

The historical key `pregame_total × min_rem / 60` is a flat linear decay that ignores
how the game has actually gone. The obvious upgrade blends observed pace into it:

    elapsed_frac = (60 − min_rem) / 60
    rate         = elapsed_frac × (pts_so_far / elapsed_min)
                 + (1 − elapsed_frac) × (pregame_total / 60)
    proxy        = rate × min_rem

Measured against the 322,746-row sample:

| Proxy | corr with actual remaining | σ(actual − proxy) | Range | Populated 5-pt bins |
| --- | --- | --- | --- | --- |
| Linear decay | **0.806** | **12.17** | 0–90 | 19 |
| Pace-blended | 0.774 | 13.11 | 0–111 | 23 |

**Rejected.** The blend spans a wider range, which was the motivation, but it predicts
strictly worse — early-game scoring is noisy and reading pace off two possessions adds
more variance than it removes. Kept the linear decay.

### Five-point expected-remaining bins

The first build used 5-point bins, producing 58 cells. The default game state landed
in an empty one and the fallback warning fired on ordinary inputs, which trains a user
to ignore warnings. Checking how much σ actually varies along that axis inside a time
bucket settled it — at 30–37.5 minutes remaining, σ runs 12.12 / 13.00 / 14.60 across
the 20 / 30 / 40 expected-remaining bins, about 10% per bin.

**Widened to 10-point bins**: 34 cells, median n = 10,142, smallest n = 151, covering
322,576 of 322,746 observations (99.95%). σ stratification is weak enough that the
wider bins cost almost nothing and the lookup stops falling off the edge.

### A parametric fallback off the closing total

The original plan, had drive data not been usable, was σ of `final − closing total`
bucketed by closing total. **Rejected on inspection**: that is a pregame quantity of
≈15 points against ≈6 at 5:00 remaining. It would have been wrong by a factor of 2.5
in precisely the game state the tool exists for. Recorded here because it is the
tempting shortcut.

## What this does not support

**P(middle) and EV are lower bounds.** The 2026-09-18 version claimed the opposite.
That was wrong, and the direction matters, so here is the argument and the check.

The spread is still too wide. The cells are keyed on the clock and a pace proxy, while
the live market prices off strictly more — possession, down and distance, observed
pace, a weather turn, an injury. By the law of total variance,

    Var(rem | clock, proxy) = E[Var(rem | clock, proxy, Z)] + Var(E[rem | clock, proxy, Z])
                            ≥ E[Var(rem | everything the book sees)]

so the residual spread used here exceeds the market's, on average. That part was right.

What was wrong was the consequence. **A wider spread moves mass *out* of the middle
window, not into it**, because of where the window sits. You bet the live number, so
the live number is always one edge of the window, and the distribution is anchored on
that number. The window is therefore `[live − d, live]` — entirely on one side of the
anchor, at bounded distance. Mass in a fixed interval ending at the centre falls as
the distribution widens.

Checked numerically by stretching the real distribution about its own centre and
repricing. Pregame Over / live Under, $100 a side at −110:

| Window | σ × 0.70 | × 0.85 | × 1.00 | × 1.15 | × 1.30 |
| --- | --- | --- | --- | --- | --- |
| 52.5–58.5, 18:00 left | 33.7% / $55 | 26.4% / $41 | 15.6% / $21 | 14.1% / $18 | 13.2% / $16 |
| 52–56, 6:00 left | 10.5% / $48 | 8.8% / $21 | 7.1% / $14 | 5.1% / $10 | 3.1% / $6 |
| 44.5–51.5, 40:00 left | 27.9% / $44 | 23.9% / $37 | 19.9% / $29 | 18.5% / $26 | 16.1% / $22 |

Monotone in every window: widening σ lowers both P(middle) and EV. So an inflated σ
makes this tool **conservative**. `tests/test_middle_ev.py` pins the direction so it
cannot silently flip and make the caveat false again.

**The live leg is the only live decision.** The pregame stake is sunk; its EV does not
move with anything entered. A hedge reshapes the payoff, it does not create edge, so
the page reports the live leg's standalone EV alongside the whole-position EV. On the
default state the whole position shows +$27 while the live leg alone is −$5 — the
headline number is almost entirely the pregame bet's own EV, which is not on offer.

Also not supported:

- **No price validation.** Nothing here checks that the quoted live price is
  obtainable, or that the middle survives the vig at the sizes shown. EV is computed
  from the prices the user types in.
- **No CLV or realised-ROI claim.** This is a pricing tool, not a backtested system.
  Nothing in this document reports a hit rate or ROI against a de-vigged market, so
  the Tier 1 metrics in [`docs/model-evaluation-standard.md`](../../../docs/model-evaluation-standard.md)
  do not apply and no result here should be quoted as forecast skill.
- **No conditioning on game context.** The cells mix blowouts and one-score games at
  the same clock and expected total. Anchoring fixes the centre; it does not narrow σ
  for a game whose remaining variance is genuinely lower.
- **One price, one CDF point.** A total and one side's price pin roughly one point of
  the market's implied distribution. They do not identify its dispersion. The σ here
  comes entirely from history, not from the market.
- **σ is stratified only weakly.** Across the expected-remaining axis σ moves about
  10% within a time bucket, so 10-point bins were used. Inside a bin σ is treated as
  constant.
- **Historical proxy ≠ runtime input.** Cells are keyed historically by
  `pregame_total × min_rem / 60` and at run time by `live_total − current_score`.
  These agree in scale but not in information. A game state far off the linear-decay
  path borrows σ from the nearest cell, and the page flags it when the walk is two
  bins or more.

## What the literature pass settled

A deep-research pass was run against the questions in
[middle-research-prompt-2026-09-18.md](middle-research-prompt-2026-09-18.md). Summary
of what it established, and what it did not. Its sourcing was not independently
verified here; the two items acted on were checked against this repo's own data.

**Acted on:**

- **The bound direction was backwards.** Verified numerically above, and fixed.
- **The sunk first leg.** The live leg's standalone EV is the decision; the page now
  reports it. This is what surfaced the mean-anchor bug.

**Checked, already handled — no change:**

- *"Derive EV from all outcome regions, not from the middle probability alone."*
  Already the case: five branches, each with its own probability and net.
- *"Model discreteness, pushes and overtime explicitly."* Already the case: integer
  final totals, explicit push branches, overtime retained in the sample.

**Open, not actionable with current data:**

- **Real in-play line history may be purchasable.** The Odds API reportedly carries
  NCAAF history from June 2020 at five-minute snapshots, with each book's Over and
  Under price at a shared point. This repo already ingests that vendor —
  `stg.oa_odds_tick` — but only nine days of it, with 758 post-kickoff totals rows.
  **A backfill would replace this entire drive-start reconstruction with observed live
  lines and remove the conditioning bias outright.** That is the single highest-value
  follow-up. A five-minute snapshot still does not prove a quote was continuously
  executable, so freshness, suspension and latency filters would be needed.
- **Alternate-total ladders would identify dispersion.** Several simultaneous totals
  give several CDF points and a market-implied σ instead of a historical one. Not in
  the warehouse.
- **No published σ benchmark exists.** No peer-reviewed table of conditional
  remaining-points standard deviation for NCAA football was found, so the 15.4 / 10.9
  / 6.1 figures here have no external check. √t scaling is a consequence of assuming
  stationary independent increments, not an empirical football result — and it must
  fail at the boundary, since regulation time hits zero while overtime uncertainty
  does not.
- **Profitability is unestablished, not disproven.** No study was found testing live
  middling net of vig, latency, rejected bets and limits.

## Reproduce

```
python -m models.totals.build_middle_table
```

Reads `cfb.duckdb` via `CFB_DATA_ROOT`, rebuilds the table, and rewrites the inlined
`MIDDLE_TABLE` block in `models/totals/middle_calculator.html`. The EV math is tested
in `tests/test_middle_ev.py`, which extracts the JS from the page and runs it under
node so the tested code is the shipped code.
