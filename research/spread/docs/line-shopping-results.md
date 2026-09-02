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
