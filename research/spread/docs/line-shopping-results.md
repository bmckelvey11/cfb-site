# Book fair and line shopping — results

Run 2026-09-02 by `research/spread/scripts/eval_line_shopping.py`, implementing
`prereg-line-shopping.md`, committed at `57637a4` before the run. Outputs:
`{CFB_DATA_ROOT}/processed/line_shopping_sides.csv`, `line_shopping.json`.

Data: Action Network closing spreads, 2024–2025, real books {49, 68, 69, 71, 75}, 1,787 games
with ≥ 2 real books (3 books on 77% of games, 4 on 19%), 3,574 game-sides, 29 season-week
clusters. Cleaning dropped 15 of 9,222 rows (4 non-normal status, 11 odds outside [−135, +125]).

## Headline

**Taking the best available number instead of the consensus is worth +1.26 win-rate points per
bet [+0.94, +1.58], mechanically, before any opinion about the game.** The average best number
is 0.40 points better than fair, and each point of spread is worth about 3.2 win-rate points
because so much of the value comes from crossing 3 or 7. The direction of a book's discrepancy
says nothing about who covers. On the 14% of sides where a full point is available, the bet at
the shopped number sits at 52.8% [48.7, 56.9], which spans the −110 break-even. Shopping is a
real, small, free gain; this sample cannot show that it pays the vig on its own.

## P1 — dispersion across real books

| | value | pre-registered expectation |
|---|---|---|
| range (max − min), median / mean | **0.50 / 0.80** | 0.5 ✓ |
| games with range ≥ 0.5 | 78.3% | — |
| range ≥ 1 | **38.1%** | 15–25% ✗ (more dispersion than expected) |
| range ≥ 2 | 7.8% | — |
| range ≥ 3 | **2.9%** (51 games) | < 1% ✗ |
| book 15 (consensus) within 0.25 of fair | 78.5% | > 90% ✗ |

**The tail is one book.** Of the 51 games with range ≥ 3, the extreme ones are all book 71
posting a number 10–25 points away from every other book at ordinary odds: +18 against 7.5,
+34 against 9.5, 0 against −20.5, +30.5 against 14.5, +20.5 against −2.5, −6.5 against −20.5,
−10 against −27.5. Those are not prices anyone took; they are mis-posts or a stale market
caught in the closing snapshot. The 3–6 point ranges on 30–50 point spreads are ordinary
blowout-line dispersion and are real. Full list in the run output and `line_shopping.json`.

Book 15's 78.5% agreement with the three-book median is lower than expected because Action
Network's consensus draws on more books than the five in the scoreboard markets.

## P2 — value of the best number, all game-sides

Pushes score 0.5; every game contributes both sides; nothing selects a bet.

| | as registered | excl. range ≥ 3 (post-hoc) |
|---|---|---|
| win(best) − win(fair), win-rate pts | **+1.26 [+0.94, +1.58]** | +1.15 [+0.81, +1.50] |
| points gained, mean | 0.40 [0.36, 0.44] | 0.33 |
| sides with any gain | 51.2% | — |
| win-rate pts per point of spread | 3.16 | 3.53 |
| n sides / clusters | 3,574 / 29 | 3,472 / 29 |

Expectation was +0.5 to +1.5 ✓. The per-point figure runs above the 2–2.5 expected; the
key-number split explains it.

| gain > 0 sides, tail excluded | n | win gain, pts | mean gain, pts |
|---|---|---|---|
| best and fair do **not** straddle 3 or 7 | 1,490 | +1.88 [+1.22, +2.54] | 0.67 |
| they **do** | 258 | **+4.65 [+2.40, +6.91]** | 0.52 |

A half-point that crosses a key number is worth roughly what two and a half points elsewhere
are worth. That is the standard key-number result, measured here on this feed.

## P3 — the actionable cells

| gain ≥ | sides | share | at **fair** number | at **best** number, pushes dropped |
|---|---|---|---|---|
| 0.5 | 1,695 | 47.4% | 51.06% [49.28, 52.85], p = 0.23 vs 50 | **53.65% [51.87, 55.44]**, p = 0.16 vs 52.38 |
| 1.0 | 500 | 14.0% | 49.00% [44.65, 53.35], p = 0.64 vs 50 | **52.80% [48.73, 56.87]**, p = 0.83 vs 52.38 |

Both expectations held: the fair-number rate is indistinguishable from 50% (the off-market
book is not telling you who wins), and the best-number rate sits above break-even with an
interval that includes it. Tail excluded, the gain ≥ 1 cell is 51.38% [46.51, 56.26] on 434
sides. Note 66 of the 500 gain ≥ 1 sides come from range ≥ 3 games and 23 of those from book
71's mis-posts; the interval is not materially moved by them.

## Secondary

- **Who supplies the best number.** Book 71 most often (666 of 1,830 gain > 0 sides), then 69
  (572) and 68 (546). Book 71 is also the one that mis-posts, so its "best" numbers need a
  sanity check against the other books before being taken at face value.
- **Per season.** 2024: +1.45 win-rate pts, mean gain 0.40, 12.6% of sides with ≥ 1.
  2025: +1.07, 0.40, 15.4%. Same picture both years.

## Scorecard against the pre-registration

| expectation | outcome |
|---|---|
| median range 0.5 | ✓ |
| range ≥ 1 in 15–25% | ✗ 38% — books disagree more than assumed |
| range ≥ 3 under 1%, explained by one book's alt or mis-post | ✗ 2.9%; ✓ explanation — book 71 |
| P2 +0.5 to +1.5 win-rate pts | ✓ +1.26 |
| 2–2.5 win-rate pts per point | ✗ 3.2, key numbers |
| gain ≥ 1 in 10–20% of sides | ✓ 14% |
| fair-number rate ≈ 50%, CI includes 50 | ✓ |
| best-number rate 52–55%, CI includes 52.38 | ✓ 52.8 [48.7, 56.9] |
| book 15 within 0.25 of fair > 90% | ✗ 78.5% |

Four of nine wrong, all in the direction of *more* dispersion than assumed. None changes the
reading.

## What this means for betting

- **Never take the consensus number when a better one is posted.** Worth about 1.3 win-rate
  points on average, more than half of the gap between a coin flip and break-even, at zero cost.
- **The half-point that matters is the one across 3 or 7.** Worth ~4.7 points of win rate on
  those sides. This is the exact mechanism behind the key-number leak in
  `docs/bet-history-analysis-2023-2025.md`.
- **Shopping does not manufacture a positive-EV bet from nothing.** A side that is 50% at fair
  is about 52–54% at the best number, break-even territory. It converts a losing spread process
  into a roughly break-even one, and adds on top of any real edge. The user's own spread record
  (51.0%) plus 1.3 points lands at about 52.3%.
- **Treat book 71's outliers as suspect** until confirmed live; a 20-point gift is a mis-post.

## Limits

- Two seasons, three to four books per game, one scrape. The scoreboard snapshot for a completed
  game is assumed to be the final pre-kickoff market; the timestamped 2026 histories can check
  that assumption once the season has a few weeks of closes.
- The value is measured at the posted number and −110 is assumed throughout; odds at the best
  number were within [−135, +125] by filter but were not priced into the gain.
- Nothing here is a betting system. Every game contributes both sides. The number to carry
  forward is +1.26 [+0.94, +1.58], and the rule it supports is a habit, not a model.

---

## Amendment S1 — outlier guard and price-adjusted value

Run 2026-09-08 by the same script, implementing `prereg-line-shopping.md` amendment S1,
committed before this run. Same data, same season/book/odds/gain-threshold/cluster
definitions; two pre-registered changes, both fixing defects `combining-predictions.md` §1
flagged before the book fair drives a live bet.

1. **Outlier guard.** Before `fair`, `hi`/`lo`, `book_hi`/`book_lo` are computed, a book more
   than 2.5 points from the median of *all* real books on the game is dropped, when ≥ 3 books
   are posted and ≥ 2 remain — the same rule and threshold `weekly_slate.shop()` already
   applies live (`OUTLIER_PTS = 2.5`). Not a new number chosen for this run: it is the constant
   already serving live traffic, applied retroactively to the backtest that lacked it.
2. **Price-adjusted value.** `value = 3.2 × gain − 100 × (breakeven(best_odds) −
   breakeven(median_odds))`, `breakeven(o) = |o| / (|o| + 100)` for negative odds,
   `100 / (o + 100)` for positive. `median_odds` is the odds at the book supplying the
   (post-guard) median number, or −110 when the median averages two books (an even guarded
   count) — consistent with the −110 assumed throughout the rest of this file.

### What the guard changes

Book 71's mis-posts (18 against 7.5, 34 against 9.5, 0 against −20.5, …) are no longer
eligible to be the "best" number, and no longer widen `range`. Games with range ≥ 3 drop from
51 to **16**; every remaining one is an ordinary blowout-line spread (margins of 18–61
points), not a mis-post — the 16 are listed in `line_shopping.json`'s `P1_tail`.

| | as registered (no guard) | S1 (guarded) |
|---|---|---|
| P2 win(best) − win(fair), win-rate pts | +1.26 [+0.94, +1.58] | **+1.15 [+0.81, +1.49]** |
| points gained, mean | 0.40 | 0.33 |
| win-rate pts per point (measured fresh) | 3.16 | 3.43 |
| range ≥ 3 games | 51 | 16 |
| gain ≥ 1.0 sides | 500 (14.0%) | 464 (13.0%) |
| gain ≥ 1.0, ATS at best (pushes dropped) | 52.80% [48.73, 56.87] | 51.72% [47.26, 56.18] |

The guarded P2 figure (+1.15) lands exactly on the "tail excluded" post-hoc figure the base
run already reported (+1.15 [+0.81, +1.50]) — the guard drops the same games that exclusion
did. Pre-registered expectation was "about +1.1" — **matched**.

### Price-adjusted value

| gain ≥ | sides | value mean, win-rate pts | share with value ≤ 0 |
|---|---|---|---|
| 0.5 | 1,657 | **+2.16** | 9.8% |
| 1.0 | 464 | **+3.63** | **1.1%** |

Pre-registered expectation was "about 12% of sides have value ≤ 0" at gain ≥ 1, a post-hoc
estimate off the odds distribution. Measured: **1.1%**, well under the guess (✗ against the
number, direction is favorable — fewer sides get priced away than feared, not more). Most
games carry three real books (77% of the 1,787), so `median_odds` is usually a real posted
price rather than the −110 fallback, and real books' vig rarely strays far from −110 on either
side; the fallback and the even-guarded-count case apply to a minority of games. The gain ≥ 1
ATS-at-best point estimate (51.72%) stays inside the pre-registered [48, 57] band.

### The 3.2 constant — what this section does and does not claim

`value` uses **3.2**, the win-rate-points-per-point figure measured on the *original*,
unguarded P2 run (2024–25, 3,574 game-sides) — not the 3.43 measured fresh in the guarded run
above, and not re-estimated here. It is dominated by the 3/7 key-number crossings on small
spreads: the base run's "Secondary" table shows crossing sides worth ~4.6 win-rate points per
point of gain against ~1.9 for non-crossing sides. Keeping 3.2 here was a deliberate decision
by the user on 2026-09-08, not an oversight — it is the in-sample conversion rate for *this*
line-shopping sample, and this section's `value` column inherits that limit: in-sample,
small-spread, key-number-dominated. **It is not the right conversion for the movement/CLV
claim.** The 2026-09-08 tree audit §1.5 retired 3.2 there because movement bets sit on larger
spreads, where a point is worth less than it is here; nothing in this section reopens that
retirement or licenses reusing 3.2 outside line shopping.

### Scorecard against amendment S1

| expectation | outcome |
|---|---|
| P2 falls to about +1.1 | ✓ +1.15 |
| gain ≥ 1, value ≤ 0 on ~12% of sides | ✗ 1.1% — far fewer priced-away sides than the post-hoc estimate suggested |
| gain ≥ 1 ATS at best stays inside [48, 57] | ✓ 51.72 |

One of three missed, and the miss runs in the direction of the price penalty being smaller
than guessed, not larger. Nothing here changes "What this means for betting" above: shopping
is still a small, mechanical, close-to-free gain, and pricing it shows that almost none of
that gain is an illusion bought by paying more juice for the better number. The number to
carry forward, guard applied, is **+1.15 [+0.81, +1.49]** win-rate points per game-side.
