# Pre-registration — book fair and line-shopping backtest

**Committed before `eval_line_shopping.py` is run.** Follows §5 item 1 of
`review-2026-09-02-composite-spread.md`.

## Question

The closing market cannot be beaten with the model consensus. Can it be beaten *at one book*, by
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

---

## Amendment S4 — the-odds-api and Pinnacle are the whole live fair (committed 2026-09-11)

**Names and replaces S3's live fair set.** The backtest set R stands unchanged, for S2's reason:
every number in `line-shopping-results.md` was computed under R from the Action Network
archive, and that archive is still on disk.

**Motivation.** The Action Network scrape is being retired
([`docs/odds-sources-an-vs-apis-2026-09-11.md`](../../../docs/odds-sources-an-vs-apis-2026-09-11.md),
*Decision*): the bulk scrape stops now, and the per-game history task stops after the 2026
season. The live fair therefore has to stand without AN's five books. Nothing in a result
motivated this; a source is going away.

**Fixed now.**

- **Live fair set, from 2026-09-11:** the nine the-odds-api books — DraftKings, FanDuel,
  BetRivers, BetMGM, BetOnline.ag, Bovada, LowVig.ag, BetUS, MyBookie.ag — **∪** Pinnacle from
  oddspapi. `OA_BOOKS` and `BOOKS` in `weekly_slate.py` are the list. **Caesars leaves the
  set**: no other feed carries it. The four books R shared with the-odds-api stay, priced from
  the snapshot rather than live.
- **Staleness.** Every the-odds-api quote is as of the latest `CFB-Odds-Snapshot` pull, up to six
  hours old (every two hours on Saturday afternoons from this date); Pinnacle's is up to 24
  hours old. Nothing in the fair is live any more. Amendment S1's outlier guard (2.5 points from
  the all-book median) is unchanged and is what keeps a stale number on a moved line out.
- **≥ 2 books still required.**
- **The Action Network scoreboard is still called once per slate, for the event id only** —
  `live_books` returns no prices. The forward log needs that id because version B's close is
  keyed on it (below). That call retires with `CFB-AN-History`.
- **Tagged.** `BOOK_SET_VERSION` = 4 on every `movement_forward_log.csv` row from here on.
  Version-3 rows (2026-09-09 to 2026-09-11) stand as written and cannot be recomputed — AN's
  live quotes at those moments were not stored. Any read pooling eras must say so.
- **Scope.** This changes `book_fair`, `side`, `side_line`, `edge` and the printed bet set.
  **Version B is untouched**: its anchor is Prediction Tracker's line and its close is Action
  Network's consensus book 15 from `history_event_<id>.json`, which `CFB-AN-History` keeps
  pulling through the 2026 season. The close definition changes only when that task is cut, and
  that will be its own amendment to `prereg-line-movement.md`.

**Measured on commit, 2026 week 3, 49 games, snapshot `ncaapredictions_20260910T163007Z`,
version-3 and version-4 slates built minutes apart from the same the-odds-api and oddspapi
snapshots.** Books per game 11 → 10 (Caesars out). `book_fair` moved on 8 of 49 games, median
0.00, mean +0.005, max 0.50 points — every move a quarter or half point, the size of one book
leaving an even-count median. E4's side flipped on 2 games; the edge ≥ 1 bet set went 24 → 23.
Reproduce: build both versions with `weekly_slate.build(snapshot, with_books=True)` and diff
`book_fair`.

## Amendment S3 — Pinnacle in the live fair (committed 2026-09-09)

**Names and extends S2's live fair set.** The backtest set R stands unchanged, for S2's reason:
no history exists for the added feed, so nothing already reported can be recomputed.

**Motivation, opportunistic again.** An oddspapi.io key became available on 2026-09-09; it is
the only feed in the repo that carries Pinnacle, which neither Action Network nor the-odds-api
serves for college football. Nothing in a result motivated this.

**Fixed now.**

- **Live fair set, from 2026-09-09 (same day as S2, later in the day):** S2's ten books **∪**
  Pinnacle, read from the daily `scripts/pull_oddspapi.py` snapshot by `pinnacle_lines` in
  `weekly_slate.py`. Only the full-game main line (Pinnacle market path period 0) counts; halves,
  quarters and alternate numbers are ignored.
- **One vote, not a weight.** Pinnacle enters the median as one book of up to eleven. It is the
  sharpest book on the list and the median does not know that; weighting it, or using it as the
  fair outright, would be a further amendment with its own measurement, not an interpretation of
  this one.
- **Staleness.** The Pinnacle quote is up to 24 hours old where Action Network's is live and
  the-odds-api's is up to six hours old. Amendment S1's outlier guard (2.5 points from the
  all-book median) is what keeps a stale Pinnacle number on a moved line out of the fair.
- **≥ 2 books still required; the outlier guard applies unchanged.**
- **Tagged.** `BOOK_SET_VERSION` = 3 on every `movement_forward_log.csv` row from here on. No
  version-2 rows exist beyond the same day's captures; version-1 rows remain as S2 left them.
  Any read pooling eras must say so.
- **Scope.** As S2: this changes `book_fair`, `side`, `side_line`, `edge` and the printed bet set.
  Version B is untouched — its anchor is Prediction Tracker's line and its close is Action
  Network's consensus, neither of which is `book_fair`.

**Measured on commit, 2026 week 3, 49 games, against the set-2 slate from the same snapshots.**
Pinnacle priced 48 of 49 (UCF at Pittsburgh not yet posted); books per game 10 → 11.
`book_fair` moved on 5 games, median 0.00, mean −0.015, max 0.25 points. E4's side flipped on 0
games. The edge ≥ 1 bet set went 20 → 19: Oregon at Oklahoma St fell from 1.00 to 0.75. Pinnacle
sat exactly on the eleven-book median in 33 of 48 priced games and within 0.5 points in 46; its
largest disagreement was 2.0 points (LSU, −33.5 against −35.5), inside the guard.

## Amendment S2 — the-odds-api books in the live fair (committed 2026-09-09)

**Names and replaces the "Fair" definition above for the LIVE slate only.** The backtest's
real-book set **R = {49, 68, 69, 71, 75}** stands unchanged, and every number already reported in
`line-shopping-results.md` was computed under it. It has to stand: the-odds-api has no history on
the free plan, so there is no 2024–25 the-odds-api data and no way to recompute the backtest
under a wider set even if that were wanted.

**Motivation, and it is opportunistic — say so plainly.** An the-odds-api key became available on
2026-09-09. Nothing in a result motivated this; a data source appeared. It is registered here
rather than applied silently because the "Fair" definition above is pre-registered, and
`weekly_slate.py` computes the live fair under it.

**Fixed now.**

- **Live fair set, from 2026-09-09:** R (via Action Network, live at slate time) **∪** the five
  the-odds-api books Action Network does not carry — BetOnline.ag, Bovada, LowVig.ag, BetUS,
  MyBookie.ag. All five are offshore. `OA_ONLY_BOOKS` in `weekly_slate.py` is the list.
- **One vote per book.** Four of R's five are on both feeds. Quotes are keyed by book identity,
  not by either feed's ids, and **Action Network wins every overlap** — its quote is fetched live
  where the-odds-api snapshot is up to six hours old. So this amendment ADDS five books; it does
  not reprice the four already there.
- **Amendment S1's outlier guard applies unchanged**, over the wider set.
- **≥ 2 books still required**, unchanged.
- **Tagged, not silent.** `BOOK_SET_VERSION` = 2 is written on every `movement_forward_log.csv`
  row from here on; the 399 rows written before it are stamped 1 by
  `migrate_book_set_version.py` and **cannot be recomputed** under set 2 — no the-odds-api
  snapshot exists for those moments. Any read that pools the two eras must say so.
- **Scope.** This changes `book_fair`, and therefore `side`, `side_line`, `edge` and the slate's
  printed bet set. It does **not** touch version B: `eval_version_b.py` grades
  `close − line_Monday` on `E4 − line_Monday`, where the anchor is Prediction Tracker's line and
  the close is Action Network's consensus book 15. Neither is `book_fair`.

**Measured on commit, 2026 week 3, 49 games.** Books per game rose 4 → 10 (dedup working: 10, not
14). `book_fair` moved a median of 0.00 points, mean −0.046, max 0.50; no game moved more than
1.5. E4's side flipped on 5 of 49 games and the edge ≥ 1 bet set stayed at 20. A larger shift
would have meant a dedup failure or a sign error, not a better consensus.

## Amendment S1 — outlier guard and price-adjusted value (committed before the rerun)

Motivated by `combining-predictions.md` §1: the backtest's book fair has no outlier guard,
though the live slate (`weekly_slate.shop`) has always applied one, and price is ignored
entirely — spreads are compared at face value, so a shopped gain that costs more juice than
it is worth still counts as a win. Both defects must be fixed before the book fair drives a
live bet.

### 1. Outlier guard

A book's number is ignored when it is more than **2.5 points** from the median of *all* real
books on the game, and at least two books remain. Applied in `build_sides` before `fair`,
`hi`/`lo`, and `book_hi`/`book_lo` are computed — the same rule and the same threshold
`weekly_slate.shop()` applies live (`OUTLIER_PTS = 2.5`), so the backtest and the live slate
agree on what a book fair is. Not a new threshold chosen for this run: it is the constant
already serving live traffic.

### 2. Price-adjusted value

Each side gets one scored number on a single scale:

```
value = 3.2 * gain - 100 * (breakeven(best_odds) - breakeven(median_odds))
breakeven(o) = |o| / (|o| + 100)   for o < 0
             = 100 / (o + 100)     for o > 0
```

`gain` is unchanged (points, `best − fair` for home / `fair − best` for away, post-guard).
`best_odds` is the odds posted at the book supplying the best number. `median_odds` is the
odds at the book supplying the (post-guard) median number — when the guarded book count is
even, the median is the average of two books' numbers and no single book supplies it, so
`median_odds` is taken as **−110**. Missing odds (not every AN row carries one) also fall back
to −110, matching the assumption already made throughout `line-shopping-results.md` ("−110 is
assumed throughout").

Reported: `value.mean()` at gain ≥ 0.5 and ≥ 1.0, and the share of sides at each threshold
where `value ≤ 0` — a shopped gain the juice cancels out.

### The 3.2 constant — what it is, and what it is not

`3.2` is **not** re-derived here. It is the win-rate-points-per-point-of-spread figure measured
in P2 of the original line-shopping run (`line-shopping-results.md`, "win-rate pts per point:
3.16", rounded and carried forward as the registered constant), fit on 2024–25, 3,574
game-sides, dominated by the 3/7 key-number crossings on small spreads. It is the **in-sample**
conversion rate for *that sample* — a number a fresh sample from the same population would
likely land close to, not a structural constant good for any spread on any market.

This is a deliberate decision, made by the user on 2026-09-08, not an oversight.
`docs/superpowers/plans/2026-09-08-spread-next-steps.md` Task 9's heading records the
resolution: keep `3.2` for line shopping, where it was estimated; the review that retired the
same constant applied it to a **different** claim — the movement/CLV claim, where bets sit on
larger spreads and a point is worth less, so "3–5× the bar" was the wrong multiple to quote
there. One number, two uses; only the movement use was wrong. It is not the right conversion
for movement CLV and must not be reused there. The S1 results section carries this caveat
again, in place, so a reader who only reads results does not miss it.

### Expectations, recorded before running

- P2 (win(best) − win(fair)) falls from **+1.26** to **about +1.1** win-rate points once the
  guard removes book 71's mis-posts from the "best" side.
- At gain ≥ 1, about **12%** of sides have `value ≤ 0` once priced (post-hoc estimate from the
  2026-09-02 run's odds distribution: 18% of gain ≥ 0.5 sides lost ≥ 1 win-rate point of juice,
  and 12% lost the whole gain).
- The gain ≥ 1 ATS-at-best figure stays inside **[48, 57]** — pricing should not move the P3
  headline by more than the guard does.

### Stopping rule

One run at these settings, same as the parent prereg. If a data defect surfaces (a duplicated
odds row, a sign error), it is fixed, recorded here, and the run repeated once.
