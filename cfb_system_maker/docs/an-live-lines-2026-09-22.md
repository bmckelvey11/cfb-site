# In-game Action Network prices were landing in `total_close` / `spread_close`

**Question.** `core.fact_game_line` carries full-game closing numbers that no book could
have posted — Western Kentucky at Georgia reading a 82.5 total with a −66.5 spread against
a 56.0 multi-book consensus, Colgate at Central Michigan reading 24.5 against 49.5. The
rows were reported as a Pinnacle problem and suspected to be a first-half or alternate
market leaking into the game-close field. Is that what they are, and is Pinnacle alone?

**Answer.** They are **live, in-game prices**, not half markets, and **every Action
Network book except Circa is affected**. The period filter was never wrong and the NaN
filter was never wrong. Fixed at the loader.

## Method

Read-only against `cfb_paths.DB_PATH`. The three reported games were traced from
`core.fact_game_line` back through the `event_id → game_id` join
`_backfill_gamelines` makes, to the individual `stg.an_history` offerings. The blast
radius was then measured across every book by running the loader's own pivot twice over
the same rows, once with live offerings and once without.

Reproduce with `python scripts/audit_an_live_lines.py`. Data as of 2026-09-22; the
Action Network tape covers 2026 weeks 1–3 densely and little else.

## What the source actually says

All three reported games, Pinnacle (`book_id` 49), `stg.an_history`:

| matchup | period | market | line | `is_live` | `line_status` |
| --- | --- | --- | ---: | --- | --- |
| Western Kentucky @ Georgia | `event` | total | 82.5 | **true** | normal |
| Western Kentucky @ Georgia | `event` | spread (home) | −66.5 | **true** | normal |
| Colgate @ Central Michigan | `event` | total | 24.5 | **true** | normal |
| Montana State @ Nevada | `event` | total | 27.5 | **true** | normal |

`period = 'event'` — the *full-game* label. Action Network reprices the full-game market
during play and publishes it under the same period as the pregame line, distinguished only
by `is_live`. A 24.5 total is not half of 49.5; it is what is left of the game at the
moment the tick was taken, which is why some land near half the consensus and others
(82.5, −66.5) land nowhere near it.

## Why it reached `core`

`_backfill_gamelines` in `cfb_system_maker/duckdb_load.py` pivots offerings with
`MAX(CASE WHEN market_type = 'total' ... THEN line END)` grouped on
`(gameId, linesProviderId, period)`. `stg.an_history` has no timestamp column, so a *last*
aggregate is not available — `MAX` is the only thing the grain supports. Nothing filtered
`is_live`, so a live tick won the aggregate whenever it was the larger number.

Pregame rows are safe under `MAX`: of 1,707 `(event, book)` groups with a full-game total,
1,686 carry exactly one distinct line and 21 carry two. The aggregate only misbehaves once
a live row joins the set.

## Blast radius

Full-game `(game, book)` values that change when live offerings are dropped:

| book | games | totals changed | spreads changed | of which live-only |
| --- | ---: | ---: | ---: | ---: |
| Pinnacle | 230 | 37 | 37 | 36 |
| FanDuel | 1,889 | 28 | 19 | 0 |
| DraftKings | 1,890 | 27 | 22 | 0 |
| Caesars | 1,850 | 25 | 21 | 0 |
| BetMGM | 1,855 | 23 | 18 | 0 |
| Bet365 | 504 | 12 | 16 | 1 |
| Circa | 1,890 | **0** | **0** | 0 |

**152 totals and 133 spreads** across six books. Pinnacle reads as the broken one because
its AN coverage is thin — 1,779 history rows against DraftKings' 36,009, but 254 of them
live. For 36 games the *only* full-game Pinnacle row is a live one, so there is nothing to
out-rank it; for the other books a pregame row exists and the live tick only wins when it
happens to be higher.

Circa is untouched: `book_id` 30 publishes no live offerings at all, and spells `is_live`
NULL on every row it does publish. That is why the fix tests `IS NOT TRUE` and not
`= false`.

## The fix

`_backfill_gamelines` now filters `is_live IS NOT TRUE` on both AN inputs — the
`stg.an_market` scoreboard side and the `stg.an_history` side. Regression test:
`tests/test_duckdb_load.py::test_backfill_gamelines_fills_nulls_and_inserts_period_rows`
now stages a live `period = 'event'` pair priced above the pregame line and asserts the
pregame numbers survive; it fails with `99.5 != 44.0` if the filter is removed.

**The warehouse still holds the bad values.** The fix is in the loader; `stg.game_lines`
and `core.fact_game_line` do not change until the next rebuild through
`scripts/refresh_cfbd.py`.

## What this does not support

- **It says nothing about the two checks that came back clean.** `period` is normalised
  correctly (`'event'`/`'game'` → `'game'`, `firsthalf` and `firstquarter` kept separate),
  and NaN is filtered: `stg.game_lines` and `core.fact_game_line` both hold zero NaN in
  `spread`/`overUnder` and in all four close/open columns.
- **It does not explain every disagreement with the multi-book median.** Circa is 0% live
  and still sits 5–10 points off the consensus on ~30% of 2026 games — traced to source,
  those are genuinely what Circa published (Ball State at Liberty: 58.5 total, −13.5 home,
  `period = 'event'`, no live row). Whether that is a stale opener, a real Circa position,
  or a capture-timing artifact is **open and untested**.
- **It does not make `total_close` mean "the close" for AN books.** The value is whichever
  pregame offering the tape happened to carry, with no timestamp to prove it was the last
  one. `_source = 'gql'` on these rows means "came from the `stg.game_lines` side of
  `_merge_game_lines`", which is the merged CFBD **+ ActionNetwork** tape — it does *not*
  mean the row came from the CFBD GraphQL feed. Pinnacle in particular is AN-only
  (`linesProviderId` 9000049, `_source_file = 'actionnetwork'`).
- **It does not fix the count.** After a rebuild Pinnacle *loses* 36 of its 2026 full-game
  rows rather than having them corrected — they had no pregame price to fall back to.
  Anything sizing a Pinnacle-close test on 2026 coverage should re-count after the rebuild.

## Known adjacent defect, not fixed here

The `event_id → game_id` map fans out on two games (`401266789`, `401215311`, both
pre-2026), each joined to two Action Network events. `MAX` over the union takes the larger
of two different games' lines. Out of scope for this fix and untouched.
