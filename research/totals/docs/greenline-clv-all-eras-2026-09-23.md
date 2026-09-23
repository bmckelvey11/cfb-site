# Greenline totals CLV across all three eras — and the 2026 closes that were in-game lines

2026-09-23

## Question

Do PFF Greenline's totals picks beat the closing line, measured the same way across every
era we have graded (2020 PFF_hist, 2022-23 exports, 2026 flags)? Win/loss cannot answer
it at this n: separating a 54% true rate from 52.38% needs about 5,900 picks. CLV
resolves in hundreds.

## Answer

1. **The 2026 CLV result of 2026-09-22 is withdrawn.** It was scored against closes that
   are partly in-game totals. `core.fact_game_line` rows that exist only in the CFBD
   GraphQL feed (Caesars, FanDuel, BetMGM, bet365, Circa, Pinnacle) hold in-game or
   partial-game totals on some 2026 games. The "corrupt Pinnacle rows" in
   [greenline-clv-market-close-2026-09-22.md](../../../archive/docs/greenline-clv-market-close-2026-09-22.md)
   were these same in-game lines, not random feed bugs, and the book median its gate used
   was contaminated the same way.
2. **Against REST-backed closes, 2026 Greenline flags beat the close by about half a
   point**, and the move holds at a single book: DraftKings at capture against DraftKings'
   own close is **+0.51 ± 0.21 pts** on 97 flags, and **+0.46 ± 0.22** on the 84 where
   PFF's displayed number already equalled DraftKings'. Unders and overs both move toward
   PFF's side. Two September weeks, five kickoff dates.
3. **2020 has none.** +0.05 ± 0.38 pts on 121 picks, confirmed against PFF_hist's own close
   snapshot (+0.02). 2026 minus 2020 is +0.45 ± 0.44, two-sided p 0.047: the eras disagree,
   so the pooled number is not one rate.
4. **Pooled, the registered test passes**: +0.29 ± 0.21 pts, one-sided p 0.004, n=265. Its
   upper bound, +0.50, is below the ~0.60 pts of CLV that pays for −110 on its own.

## The in-game lines

Western Kentucky at Georgia, 2026 week 2, one CFBD game:

| book | `_source` | total_open | total_close |
| --- | --- | ---: | ---: |
| Circa | gql | — | 52.5 |
| bet365 | gql | — | 55.5 |
| DraftKings | both | 52.5 | 55.5 |
| Bovada | both | 54.0 | 56.0 |
| Caesars | gql | — | 78.0 |
| FanDuel | gql | — | 78.5 |
| BetMGM | gql | — | 82.5 |
| Pinnacle | gql | — | 82.5 |

Four books agree on a pregame 52.5-56.0; four carry a number 25 points higher that only a
game in progress produces. The same shape appears on Colorado State–Southern Utah,
Florida Atlantic–Navy and James Madison–Wagner, and on each the inflated rows are the
GraphQL-only ones. With those removed, only 3 of the 272 unders still see books more than
3 pts apart. Every 2020-23 row is REST-backed (`_source` `both`). Among
2026 books, Circa's close sits a median 1.0 pt off the game median and more than 3 pts off
on 65 of 322 games.

The consequence is not limited to Pinnacle. A median of the other books cannot catch a
live row when live rows are the majority, which they are on these games, so both the
`drop` and `consensus` policies in the 09-22 doc scored some games against in-game totals.
The flag-CLV contrast ([greenline-flag-clv-contrast-2026-09-22.md](greenline-flag-clv-contrast-2026-09-22.md))
reuses that measurement and is exposed the same way. `pff_line_movement.py` is not: it
requires `total_open`, which no GraphQL-only row carries.

## Method

Script: [`../scripts/greenline_clv_all_eras.py`](../scripts/greenline_clv_all_eras.py). Its
docstring carries the analysis plan, fixed before the first run.

- **Population.** The 272 pooled Greenline totals unders exactly as
  `pool_totals_record.load()` defines them: 126 from 2020 PFF_hist, 58 from the 2022-23
  exports, 88 from the 2026 week 2-3 flags.
- **Capture.** The line each pick was graded at: the 2020 `open_greenline` snapshot, the
  2022-23 `export` snapshot, the 2026 weekly capture.
- **Benchmark.** Median `total_close` across the game's REST-backed books in
  `core.fact_game_line`, at least two books, game dropped if they span more than 3 pts.
  Pinnacle is excluded (no rows before late 2025).
- **CLV.** `capture − close` for an under, in points; positive means the market moved
  toward the under after the pick. CFBD carries no closing price, so this is point CLV;
  the win-probability column converts at the unit's 4 pp per point.
- **Inference.** One primary test, pooled mean > 0, one-sided, alpha 0.05. SE is the larger
  of iid and date-clustered.

**The benchmark changed after the first run, and this is that change.** The plan fixed
"median across every book CFBD carries". That run scored 231 unders, dropped 41, and put
2026 at +0.23 ± 0.25 on 54. Inspecting the drops found the in-game rows, so the benchmark
became REST-backed books only. The test and decision rule did not change. Under the
registered benchmark the pooled test already passed (+0.19 ± 0.23, p 0.047); the 2026 row
is what moves. Every variant is in the sensitivity table below.

## Results

| split | n | dates | mean CLV (pts, 95%) | median | mde (pts) | p (one-sided) | ~win prob | beat-lost-flat |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **all eras, unders** | 265 | 50 | **+0.29 ± 0.21** | +0.2 | 0.27 | 0.004 | +1.2pp | 138-92-35 |
| 2020 PFF_hist | 121 | 35 | +0.05 ± 0.38 | 0.0 | 0.49 | 0.396 | +0.2pp | 55-53-13 |
| 2022-23 exports | 56 | 10 | +0.46 ± 0.35 | +0.5 | 0.45 | 0.005 | +1.9pp | 32-16-8 |
| 2026 flags | 88 | 5 | +0.50 ± 0.22 | +0.2 | 0.28 | <0.001 | +2.0pp | 51-23-14 |

`mde` is the smallest true mean CLV the row's n detects 80% of the time, one-sided.

### Is it the market, not PFF?

Market drift would move every total the same way. It does not account for this:

| check | result |
| --- | --- |
| 2020 unpicked leans, same snapshot (660) | drift +0.11; picks −0.06 ± 0.41 against it |
| 2022-23 unpicked leans, same snapshot (236) | drift +0.15; picks +0.31 ± 0.44 against it |
| 2026 over flags, capture − close (18) | **−0.39**: the line rose, toward the over PFF flagged |
| 2026 market, REST open → close, weeks 1-5 (703 rows) | −0.10 |

In 2026 unders fell and overs rose after capture. Drift cannot move both toward PFF.

### Is it PFF's displayed number, not the market?

Flags are chosen on PFF's displayed line minus its projection. If that number were sometimes
off the market, unders would over-sample too-high captures and overs too-low ones, and both
would regress to the close without PFF knowing anything. One book at both ends removes it:

| split | n | dates | DraftKings at capture → DraftKings close (pts, 95%) | p (one-sided) | beat-lost-flat |
| --- | ---: | ---: | ---: | ---: | ---: |
| all 2026 flags | 97 | 5 | **+0.51 ± 0.21** | <0.001 | 47-15-35 |
| unders | 80 | 5 | +0.55 ± 0.23 | <0.001 | 41-12-27 |
| overs | 17 | 3 | +0.29 ± 0.44 | 0.094 | 6-3-8 |
| PFF's number = DraftKings' | 84 | 5 | **+0.46 ± 0.22** | <0.001 | 39-12-33 |
| PFF's number ≠ DraftKings' | 13 | 3 | +0.77 ± 0.71 | 0.017 | 8-3-2 |

Capture snapshots: odds-api `20260909T200531Z` (week 2) and `20260916T180004Z` (week 3),
the nearest to each board capture.

### Benchmark cross-checks

- **2020, CFBD close vs PFF_hist's own close snapshot**, 121 games: mean difference −0.04
  pts, 115 within half a point. The 2020 null is not a benchmark artifact.
- **2026, the 09-22 Pinnacle-gated close**, unders: −0.02 ± 0.98, n=65. Contaminated, not a
  cross-check: its Pinnacle rows and the books gating them are GraphQL-only.

### Sensitivity: the close definition

| books | gate | pooled | 2020 | 2022-23 | 2026 |
| --- | --- | ---: | ---: | ---: | ---: |
| **REST** | **span (primary)** | **+0.29 ± 0.21** (265) | +0.05 (121) | +0.46 (56) | +0.50 ± 0.22 (88) |
| REST | none | +0.31 ± 0.21 (268) | +0.07 | +0.51 | +0.50 ± 0.22 (88) |
| all | span (registered) | +0.19 ± 0.23 (231) | +0.05 | +0.46 | +0.23 ± 0.25 (54) |
| all | none | +0.03 ± 0.39 (268) | +0.07 | +0.51 | −0.34 ± 1.11 (88) |
| all | trim, added after | +0.08 ± 0.33 (264) | +0.07 | +0.52 | −0.21 ± 0.93 (84) |

2020 and 2022-23 do not move with the book set; they have no GraphQL rows. Only 2026
does, and the rows that make it negative are the in-game ones.

### Trial count

One primary test. Around it: five close definitions, three era rows, two unpicked-drift
contrasts, one era-heterogeneity test, five same-book splits, two benchmark cross-checks,
one market-drift figure. Only the primary carries a verdict; the rest are diagnostics.

## What this does not support

- **An edge that pays at −110 on CLV alone.** The pooled upper bound is +0.50 pts, below
  the ~0.60 needed. 2026 alone reaches it (upper +0.72) but does not clear it (mean +0.50).
- **Carrying the 2026 number to later weeks.** Two early-season weeks, five kickoff dates. A
  five-cluster SE is fragile, and early-season totals markets are the softest of the year.
  This needs the rest of 2026 before it is a rate.
- **Greenline having had CLV all along.** 2020 has none, on both benchmarks. Whether the
  2026 board is a better product or a softer early-season market cannot be separated here.
- **The 2022-23 row as independent support.** Capture time of the exports is unknown, and
  against its own unpicked leans the excess is +0.31 ± 0.44.
- **Moving the unit on this alone.** It raises the case for a real edge; it does not move
  the win-rate prior the unit is derived from.

## Reproduce

    python research/totals/scripts/greenline_clv_all_eras.py
    python research/totals/scripts/greenline_clv_all_eras.py --self-check

Data: `core.fact_game_line` (warehouse as of 2026-09-23), `greenline_history_archive.csv`,
`greenline_graded.csv`, odds-api snapshots under `data/ingest/oddsapi/`.
