# Can `NCAAData_1980-2020.csv` backfill the warehouse lines? — 2026-09-17

## Question

`C:\Users\mckel\OneDrive\Betting\NCAAData_1980-2020.csv` was offered as a source to
backfill betting lines in `cfb.duckdb`. Does it contain lines, and if not, does it
contain anything the warehouse is missing?

## Answer

**No lines.** The file has 27 columns and none of them is a spread, total, moneyline,
or provider. `home_line_scores` / `away_line_scores` are quarter-score arrays, not
betting lines — the name collision is the whole reason the file looked usable.

**Almost nothing else is new either.** Every `id` in the file is a CFBD game id and all
28,519 match the warehouse, which is expected: this is a CFBD export and the warehouse is
CFBD-sourced. The only gap it fills is `excitement_index` for 2,378 games in 2011–2013.

## Method

`scripts/audit_ncaadata_csv.py` reads the CSV with `read_csv(..., all_varchar=true)` and
left-joins each candidate column against the warehouse table that already carries it,
counting rows where the CSV has a value and the warehouse has none.

Data: the CSV as of 2026-09-17 (28,519 rows, seasons 1980–2019 — the filename says 2020
but the last season present is 2019) against `data/cfb.duckdb` on the same date.

## Numbers

| Check | Result |
|---|---|
| CSV rows / season span | 28,519 / 1980–2019 |
| ids matching `core.fact_game_historical` | 21,877 |
| ids matching `core.fact_game` | 6,642 |
| ids matching neither | 0 |
| Quarter scores the warehouse lacks | 0 |
| Attendance the warehouse lacks (pre-2012) | 0 |
| Postgame win probability the warehouse lacks | 0 |
| Excitement index the warehouse lacks | 2,378 (2011: 768, 2012: 790, 2013: 820) |

Warehouse line coverage, for context on the gap the request was aimed at:

| Era | Games with a row in `core.fact_game_line` |
|---|---|
| Before 2013 | 0 |
| 2013 and later | 47,946 |

`core.fact_game_line` is empty for every season before 2013 — 1980–2012 has zero lines,
and 2012 itself has 1,379 games and no lines. That gap is real, and this file cannot
close it.

## What this does not support

- It does not show that pre-2013 lines are unobtainable — only that this file is not the
  source. A different vendor (historical spread archives, Action Network, a paid
  historical odds feed) would be needed.
- It does not evaluate whether the 2,378 excitement-index values are worth loading.
  Excitement index is computed from in-game win-probability swings, so it is
  result-informed and would have to be tagged `result_lookahead` and quarantined under
  the repo's no-lookahead rule. It has no pre-game modelling use.
- It does not check the CSV's columns for *disagreement* with the warehouse, only for
  presence. A value-level diff was not run.

## Reproduce

```bash
python scripts/audit_ncaadata_csv.py
```

Optionally pass a different CSV path as the first argument.
