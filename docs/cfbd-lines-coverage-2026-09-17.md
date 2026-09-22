# How far back CFBD betting lines go, and who posted them

**Date:** 2026-09-17
**Reproduce:** `python scripts/probe_lines_coverage.py --local` and
`.venv-cfbd\Scripts\python.exe scripts/probe_lines_coverage.py --api`

## The question

What is the earliest season with usable betting lines, and is the local floor of 2012
a limit of CFBD or a limit of what has been pulled?

## Method

Two independent views, because they answer different questions:

1. **API** — one `GET /lines?year=Y` per season for 2000, 2005, 2008, 2010, 2011, 2012,
   2013, counting games returned and games carrying a non-empty `lines` array.
2. **Warehouse** — `raw.lines` in `data/cfb.duckdb`, same count via
   `json_array_length(json_extract(payload,'$.lines')) > 0`, plus a provider tally.

Data range: all seasons present in `raw.lines` (2012–2026) and the seven probed API
seasons. Run 2026-09-17.

## Result: the floor is 2013

The API returns *games* for every season back to 2000, but zero *lines* before 2013:

| season | games | with lines |
| ---: | ---: | ---: |
| 2000 | 702 | 0 |
| 2005 | 718 | 0 |
| 2008 | 805 | 0 |
| 2010 | 808 | 0 |
| 2011 | 812 | 0 |
| 2012 | 840 | 0 |
| 2013 | 848 | 848 |

The warehouse agrees exactly: its 840 rows for 2012 are games whose `lines` array is
empty, and 2013 is 848/848 populated. So the local floor is not a pull gap — 2012 was
fetched and came back without lines. This is why the app header reads 2013–2026.

Local coverage stays near-total from 2013 on (lowest is 2015 at 832/870, 95.6%). 2026
is 421/993 because the season is in progress.

## The provider mix changes completely across the era

Rows per provider per season, from `raw.lines`:

| era | providers |
| --- | --- |
| 2013–2017 | `consensus`, `teamrankings`, `numberfire` only |
| 2018–2020 | Caesars, Bovada, SugarHouse, William Hill (New Jersey) enter |
| 2021–2022 | William Hill and Bovada dominate; `numberfire` collapses (769 → 145 → 0) |
| 2023 | DraftKings and ESPN Bet arrive; `consensus` collapses (1244 → 29) |
| 2024–2026 | ESPN Bet, DraftKings, Bovada only |

Two consequences worth naming:

- **`consensus` is effectively dead after 2022** (29 rows in 2023, none after). Any
  system pinned to `consensus` silently loses 2023–2026 rather than erroring.
- **No real sportsbook exists before 2018.** 2013–2017 is entirely aggregators and
  model lines. A "median across books" that excluded non-books would have no data for
  those five seasons — which is why the median line added on this date includes every
  provider.
- `DraftKings` and `Draft Kings` appear as separate strings in 2025–2026.
  `normalize.PROVIDER_ALIASES` folds them; a raw query against `raw.lines` will not.

## What this does not support

The API probe used seven year-level calls with the endpoint's default
`seasonType=regular`. It does not rule out stray postseason lines in a pre-2013 season,
and it does not establish that every season between the probed years is empty — 2001–2004,
2006–2007 and 2009 were not checked. The 2013 floor is firm on both sides (2012 empty,
2013 full) but the exact boundary was not bisected further because nothing below it
returned anything.

Warehouse counts describe what has been pulled into `raw.lines`, not everything CFBD
would serve for those seasons. Provider tallies count line *rows*, not games, so a
provider posting both a spread and a total for one game may appear once or twice
depending on how the payload nests.
