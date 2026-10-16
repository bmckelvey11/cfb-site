# Live middle calculator: anchoring fix (2026-10-16)

**Question.** Does the live middle calculator (`models/middle/middle_calculator.html`)
compute the final-total distribution correctly once it has picked a historical cell?

**Answer.** No. The 2026-09-21 method ([middle-probability-2026-09-21.md](middle-probability-2026-09-21.md),
section "Recentring") slid the cell's remaining-points histogram sideways until its
interpolated median sat on `live_total − score`. That broke three things, and the
fix replaces the slide with a re-weighting.

## What was wrong

1. **Mass below the current score.** Sliding left moves "remaining points = 0" to a
   negative number. At 55 points, 6:00 left, live 58.5, the old code put **41.6%** of
   the probability on final totals of 52 and 53, which are impossible because 55
   points are already on the board. A pregame Over 51.5 that had already cashed was
   priced as if it could still lose.
2. **"Nobody scores again" moved off the current score.** Sliding right moves the
   big zero spike (70% of drive starts in the last 2:30) up to the live number. At
   55 points, 2:00 left, live 59, the old code gave a final of exactly 55 **0%** and
   a final of 58 **50%**.
3. **The live number was not a coin flip.** Remaining points is lumpy (0, 3, 6, 7,
   10, ...), and a median interpolated inside a lump does not split a half-point
   line evenly. At 55 points, 2:00 left, live 59.5, the old code had P(Under) =
   **69.6%**, which is the same fake late-game Under edge the 2026-09-21 doc set out
   to remove. Even the page's default inputs (31 points, 18:00 left, live 58.5) had
   P(Under) = 52.1%, and that tilt alone made the calculator recommend a $15.86
   hedge that is not justified at matched prices.

## Method now

`tiltToMarket(cell, anchor)` (inside the page's `EV_MATH` block) scales each
historical probability by `exp(theta * rem)` and renormalises, with `theta` found by
bisection so that `P(rem < anchor) = P(rem > anchor)`:

    q(rem) = p(rem) * exp(theta * (rem - anchor)) / Z

This only re-weights outcomes the history already contains, so remaining points
stays ≥ 0 and stays on real scoring totals, and the live number is an exact coin
flip on half-point and integer lines alike. It is the smallest change to the
historical shape (minimum KL divergence) that agrees with the market.

## Before and after

Same cells, same inputs. Pregame Over at the listed number, live Under at the live
total, -110 both sides.

| Game state | Old P(final < score) | Old P(Under live) | New P(Under live) | Old P(middle) | New P(middle) |
| --- | --- | --- | --- | --- | --- |
| 55 pts, 6:00, live 58.5, pre 51.5 | 41.6% | 52.2% | 50.0% | 52.2% | 50.0% |
| 55 pts, 2:00, live 59.5, pre 52.5 | 0% | 69.6% | 50.0% | 69.6% | 50.0% |
| 31 pts, 18:00, live 55.5, pre 49.5 | 0% | 52.1% | 50.0% | 15.6% | 21.7% |
| 42 pts, 10:00, live 61.5, pre 55.5 | 0% | 53.2% | 50.0% | 34.7% | 23.1% |
| 10 pts, 40:00, live 51.5, pre 45.5 | 0% | 51.7% | 50.0% | 18.5% | 16.6% |

In the first two rows the pregame Over is already won, so the whole under side is
the middle; the old numbers there were right only by accident.

## What this does not support

- **The far tail is not trustworthy.** When the market's expected remaining points
  sits far above the cell's (late game, live total well above the score), the
  re-weighting piles mass into the cell's extreme right tail. With 1:00 left and a
  live total 7.5 above the score, about 25% of the mass lands 28+ points over the
  line. This does not move any number the page shows, because everything above the
  live number is one branch whose probability is pinned at 50%, but do not read the
  distribution's shape above the line as a forecast.
- **Overtime contaminates the last cell.** `build_middle_table.py` stamps every
  overtime drive start as 0 minutes remaining, so the 0–2:30 cell mixes late
  regulation with overtime possessions. That fattens the right tail above. Fixing it
  needs a table rebuild against the warehouse.
- **Matched prices are still assumed.** As before, with unequal live prices the fair
  point is not the median and the page cannot de-vig with one price.
- **No calibration against real live lines.** There is still no live-total history
  to test any of this against; see [middle-research-prompt-2026-09-18.md](middle-research-prompt-2026-09-18.md).

Reproduce: `python -m pytest tests/test_middle_ev.py` (the anchoring tests at the
bottom), and the before/after table by loading the page's `MIDDLE_TABLE` and
`EV_MATH` blocks in node and calling `finalTotalDist` for each state.
