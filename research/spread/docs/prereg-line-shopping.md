# Pre-registration — book-line composite and line-shopping backtest

**Committed before `eval_line_shopping.py` is run.** Follows §5 item 1 of
`review-2026-09-02-composite-spread.md`.

## Question

The closing market cannot be beaten with model composites. Can it be beaten *at one book*, by
taking the best number across books instead of the consensus? Two sub-questions:

1. **Dispersion.** How far apart are real books at close, and is the tail real or artifact?
2. **Value.** How much ATS win rate does taking the best available number add over taking the
   consensus number, and does the direction of a book's discrepancy carry any information about
   the result?

## Data

`stg.actionnetwork_scoreboard__markets__markets_event_spread`, seasons **2024–2025**,
`status = 'complete'`, `side = 'home'`. The scoreboard was scraped 2026-07-31; for completed
events Action Network serves the final pre-kickoff market, so this is treated as the **close**.
Scores come from the same row (`home_points`, `away_points`). No join.

**Book identities, established from data before this was written** (the loader's
`_AN_PROVIDER_NAMES` disagrees and is not used):

| book_id | what it is | evidence | used as |
|---|---|---|---|
| 15 | Action Network consensus | median 0.00 from the other books' median | reported, **not** a book |
| 30 | consensus **opener** | equals book 15's first history tick on 97.2% of 106 timestamped games; no `line_status` field | **excluded** |
| 49 | real book, sparse | 60 games | included |
| 68, 69, 71 | real books | full coverage, ~1,750–1,790 games each | included |
| 75 | real book, partial | 417 games | included |

Real-book set **R = {49, 68, 69, 71, 75}**. Rows are dropped when `is_live` is true, when
`line_status` is neither `normal` nor null, or when odds fall outside **[−135, +125]** (an
alternate line dressed as a spread). Dropped counts are reported.

## Definitions

- `s_b` = home spread at book b (negative = home favored, repo convention).
- **Fair** = median of `s_b` over b ∈ R present for the game. Requires **≥ 2** real books.
- **Range** = max − min of `s_b` over R.
- **Best number**, per side: home → `max s_b`; away → `min s_b`. **Gain** in points:
  home `best − fair`, away `fair − best`. Gain ≥ 0 by construction.
- Grading at number s with margin m = home − away: home covers if `m + s > 0`, away covers if
  `m + s < 0`, `m + s = 0` is a push. **Pushes score 0.5** in the paired comparison so that the
  two sides of a game sum to one; the actionable cell also reports the push-dropped rate.
- Every game contributes **two game-sides** (home and away). No side is selected by any rule,
  so the paired value estimate is mechanical, not a betting system.

## Primary outcomes

**P1 — dispersion.** Median and mean range; share of games with range ≥ 0.5, ≥ 1, ≥ 2, ≥ 3.
Every game with range ≥ 3 is listed with per-book number and odds. Book 15 vs fair: share
within 0.25.

**P2 — shopping value.** Mean of `win(best) − win(fair)` over all game-sides, in win-rate
points, with a 95% CI. Also the mean gain in points, and value per point.

**P3 — the actionable cell.** Game-sides with gain ≥ 1.0:
- win rate at **fair** (does the discrepancy direction predict the result?), CI, test vs 50%;
- win rate at **best**, pushes dropped, CI, test vs the −110 break-even **52.38%**.

Same table at gain ≥ 0.5, reported alongside, not a separate hypothesis.

## Inference

Clusters = **season × week** (≈ 30). Cluster-robust SE for a mean:
`se = sqrt(Σ_g (Σ_{i∈g} (x_i − x̄))²) / n`; CI uses t with G − 1 df. Two-sided throughout.
Three primary outcomes, each one number; no correction across them beyond reporting all three.

## Secondary, reported but not decisive

- Gain split by whether best and fair straddle or land on **3 or 7** (key numbers).
- Which book supplies the best number, by side; per-book share of gain ≥ 1 cells.
- Per-season figures, so 2024 and 2025 can be seen separately.

## Expectations, recorded before running

- P1: median range **0.5**; range ≥ 1 in **15–25%** of games; ≥ 3 in **< 1%**, and those will be
  one book's alternate or mis-posted line (book 71 showed a 32-point outlier against the other
  books' median, at normal-looking odds — that is the tail to explain).
- P2: **+0.5 to +1.5** win-rate points per game-side; roughly 2–2.5 win-rate points per point of
  spread, consistent with the CFB margin distribution away from key numbers.
- P3 at gain ≥ 1: about **10–20%** of game-sides; fair-number win rate **≈ 50%**, CI including 50;
  best-number win rate **52–55%**, CI **including** 52.38. That is: the value is real and small,
  and this sample cannot show it clears vig on its own.
- Book 15 within 0.25 of fair on **> 90%** of games.

If P3's best-number CI excludes 52.38 from above, the reading is "shopping alone may pay",
not "system found": two seasons, four books, and no confirmation window.

## Stopping rule

One run at these settings. No changes to R, the odds window, the gain thresholds, or the
cluster definition after seeing results. If a data defect is found (a duplicated market, a
mis-oriented side), it is fixed, recorded here, and the run repeated once.
