# CFBD and PFF currency check — 2026-09-16

## Question

Pull this past week's CFBD and PFF data and confirm both are current.

## Answer up front

**Nothing was missing.** "This past week" is week 2 (played Sept 10–12); it was
already scraped, flattened and loaded before this check ran. **Week 3 has not
been played** — it kicks off 2026-09-17, tomorrow, with 311 scheduled games and
0 results — so there is no week-3 data to pull from either vendor.

What *was* out of date was six hand-pulled GraphQL dumps, 19–58 days old. Those
were re-pulled. Five came back byte-for-byte the same size and row count; only
`linesProvider` changed, and it shrank.

## Method

Read-only checks against the live warehouse and `data/`, then a hand-run
GraphQL pull. Data: local `cfb.duckdb`, rebuilt by the 13:16–13:41 run of
`refresh_cfbd.py` (exit 0). Reproduce the audit halves with
`python scripts/audit_coverage.py` and
`python scripts/audit_graphql_dump_age.py`; the pull was
`python -m cfb_system_maker graphql --data-dir data --only <tables> --force`.

## Week 2 is complete on both sides

The daily refresh only force-rescrapes `games lines calendar conferences venues`,
so the per-week endpoints are the ones worth checking. A prior run today at
12:12–12:14 pulled them. All 11 weekly CFBD endpoints have weeks 1 and 2 for
2026, and the warehouse reflects them:

| `stg` table | wk1 | wk2 |
| --- | --- | --- |
| `plays` | 35,773 | 23,131 |
| `passing_plays` | 4,486 | 3,959 |
| `ppa_players_games` | 4,745 | 3,168 |
| `player_success_game` | 2,345 | 1,518 |
| `game_team_stats` / `game_player_stats` | 204 | 131 |

PFF is complete too: all 19 week-bearing `stg.pff_*` tables carry weeks 0, 1 and
2 for 2026 (`pff_receiving` 25,914 rows in week 2, `pff_passing` 7,661).

Two numbers look wrong at a glance and are not:

- **`play_stats` is exactly 2,000 rows every week.** It is 2,000 in every 2025
  week as well — a CFBD page limit that predates this season, not something this
  week's pull truncated.
- **`game_team_stats` covers 131 of 302 played games in week 2.** 2025 week 2
  was 130 of its own slate. The ratio is normal; CFBD only box-scores part of
  the all-divisions schedule. `dim_team.is_fbs` is *not* a usable denominator
  here — it is known-incomplete for teams outside CFBD's list, and reports fewer
  FBS-involved games than `game_team_stats` actually has rows for.

## The six stale dumps, re-pulled

| Dump | Age before | Rows before → after |
| --- | --- | --- |
| `conference` | 19.3d | 256 → 256 |
| `calendar` | 19.3d | 424 → 424 |
| `coach` | 19.3d | 1,842 → 1,842 |
| `recruit` | 19.3d | 93,363 → 93,363 |
| `draftPicks` | 19.3d | 13,080 → 13,080 |
| `linesProvider` | 58.1d | **17 → 12** |
| `gameLines` | 0.2d | 39,314 → 39,314 |

Five of the seven were stale by *file date only* — the row counts are
unchanged, and the audit classifies `coach`, `recruit` and `draftPicks` as
append-only, so an unchanged count means no new entities arrived.

`linesProvider` lost five entries upstream: `bet365`, `betmgm`, `circa`,
`fanduel` and `pinnacle` are in the warehouse's `dim_lines_provider` (16 rows)
but no longer in CFBD's GraphQL enum (12). **This is harmless**, and it is worth
being precise about why: `_build_dim_lines_provider` builds the dim from
`core.fact_game_line` plus the two selected-provider keys on `core.fact_game` —
the actual line tape — not from the `linesProvider` enum. A rebuild will not
drop FanDuel or Pinnacle.

## The `gameLines` "gap" is not staleness

`audit_graphql_dump_age.py` reports `gameLines` as **BEHIND** by 1,508 REST-lined
games despite being 0.2 days old. Re-pulling it with `--force` returned exactly
39,314 rows and left the gap **unchanged**, which is what identifies the cause.
Split by season:

| Segment | Games | What it is |
| --- | --- | --- |
| 2012 | 840 | all 840 REST-lined 2012 games; the GraphQL table does not reach back that far |
| 2026 | 572 | **all 572 are unplayed** — weeks 4+ (week 3 is missing only 2) |
| 2014–2024 | 96 | scattered singles and teens |

The 2026 segment is the whole explanation for the alarming number: REST `/lines`
publishes forward-looking lines for the rest of the season, while the GraphQL
`gameLines` table only carries games that have been played or are within about a
week. Both sources are current; they have different forward horizons.

`core.fact_game_line` consequently holds 422 of the 993 REST-lined 2026 games,
with `_source` `both` on 421 and `gql` on 253. That is the same horizon
difference, surfacing one layer down.

## What this does *not* support

- **This is not a clean bill of health for the warehouse.** It checks that week
  2 arrived and that the dumps are freshly pulled. It does not check correctness,
  nulls, or joins — `scripts/audit_data_hygiene.py` and `scripts/audit_duckdb.py`
  own that.
- **"Row count unchanged" is not "content identical."** `--force` overwrote the
  previous dumps, so a field-level diff is no longer possible. For the three
  append-only tables an unchanged count is strong evidence; for `calendar` and
  `conference` it is weaker.
- **The 96 scattered 2014–2024 `gameLines` misses are unexplained.** They are too
  few to be a horizon effect and were not investigated.
- **No rebuild was run.** The warehouse still reflects the 13:16 load, so the
  re-pulled dumps are on disk but not in `cfb.duckdb`. Given five of six came
  back with identical row counts, a rebuild would change almost nothing — the
  exception is `linesProvider`, and that one does not feed the dim.

## Recommendation

Skip the rebuild. The only dump whose content changed is `linesProvider`, which
nothing in `core` reads. The next scheduled `refresh_cfbd.py` (05:00) will pick
the new dumps up for free.

Pull week 3 after Saturday 2026-09-19:

```
python -m cfb_system_maker scrape --season 2026 --only plays play_stats game_team_stats game_player_stats ppa_players_games player_success_game
```

then the PFF weekly pull, then `python scripts/refresh_cfbd.py`.
