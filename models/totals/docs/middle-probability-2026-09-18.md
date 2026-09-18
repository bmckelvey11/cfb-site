# Live middle probability from drive-start observations — 2026-09-18

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

The sample is cross-tabbed into `(min_rem bucket, expected remaining bucket)` cells.
Expected remaining is proxied historically by `pregame_total × min_rem / 60`. Each
cell stores `n`, the mean of `rem`, and the integer histogram of `rem`.

At run time the calculator computes expected remaining as `live_total − current_score`
— the market's own estimate — picks the matching cell, and shifts that cell's
histogram so its mean sits on the user's number. The shift is split between the two
neighbouring integers so recentring introduces no rounding bias. The result is a
distribution over integer final totals, which is folded into the five branches of a
totals middle and priced.

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

## What this does not support

**P(middle) and EV are upper bounds.** Expected remaining points are estimated from
the live total and the clock. The live market prices off strictly more information —
possession, down and distance, observed pace, a weather turn, an injury. So

    Var(rem − bucket estimate) ≥ Var(rem − live line)

and the residual spread here is wider than reality. A wider spread puts more mass
inside the middle window, which overstates both the probability the middle hits and
the EV. For a betting tool that is the dangerous direction, and the calculator says
so on the page.

Also not supported:

- **No price validation.** Nothing here checks that the quoted live price is
  obtainable, or that the middle survives the vig at the sizes shown. EV is computed
  from the prices the user types in.
- **No CLV or realised-ROI claim.** This is a pricing tool, not a backtested system.
  Nothing in this document reports a hit rate or ROI against a de-vigged market, so
  the Tier 1 metrics in [`docs/model-evaluation-standard.md`](../../../docs/model-evaluation-standard.md)
  do not apply and no result here should be quoted as forecast skill.
- **No conditioning on game context.** The cells mix blowouts and one-score games at
  the same clock and expected total. Recentring fixes the mean; it does not narrow σ
  for a game whose remaining variance is genuinely lower.
- **σ is stratified only weakly.** Across the expected-remaining axis σ moves about
  10% within a time bucket, so 10-point bins were used. Inside a bin σ is treated as
  constant.
- **Historical proxy ≠ runtime input.** Cells are keyed historically by
  `pregame_total × min_rem / 60` and at run time by `live_total − current_score`.
  These agree in scale but not in information. A game state far off the linear-decay
  path borrows σ from the nearest cell, and the page flags it when the walk is two
  bins or more.

## Reproduce

```
python -m models.totals.build_middle_table
```

Reads `cfb.duckdb` via `CFB_DATA_ROOT`, rebuilds the table, and rewrites the inlined
`MIDDLE_TABLE` block in `models/totals/middle_calculator.html`. The EV math is tested
in `tests/test_middle_ev.py`, which extracts the JS from the page and runs it under
node so the tested code is the shipped code.
