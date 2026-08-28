---
task_id: 260828-lvd
slug: garbage-time-endpoint-variants
date: 2026-08-28
status: complete
---

# Summary

Registered nine `_ngt` endpoint variants for CFBD's `excludeGarbageTime` parameter and
pulled 2012-2025. **520 files, 543,288 rows, 0 endpoints failed.**

| Endpoint | Files | Rows |
|---|---|---|
| `ppa_games_ngt` | 14 | 22,493 |
| `ppa_teams_ngt` | 14 | 1,815 |
| `ppa_players_season_ngt` | 14 | 41,892 |
| `ppa_players_games_ngt` | 211 | 241,635 |
| `player_usage_ngt` | 14 | 41,892 |
| `advanced_game_stats_ngt` | 14 | 29,112 |
| `advanced_season_stats_ngt` | 14 | 1,815 |
| `player_success_season_ngt` | 14 | 29,721 |
| `player_success_game_ngt` | 211 | 132,913 |

## What changed

- `cfb_system_maker/scrapers.py` — `_NO_GARBAGE` constant, nine `_ngt` entries, and
  `| endpoint.fixed` in `_scrape_season_week`.
- `tests/test_scrapers.py` — registry test split into 73 base + 9 variants (it hardcoded
  73 total); new `test_season_week_applies_endpoint_fixed_kwargs`.
- `docs/data-coverage.md` — `excludeGarbageTime` moved out of "unused options" into its
  own closed-gap section; `threshold` reclassified as a narrowing filter.

## Verification

Probed 2024 before registering: all nine differ from their unfiltered twin, no no-ops.
Two behaviours — game/team-level keep every row and move values; player-level *also* drop
rows (a player whose only snaps were garbage time has no qualifying plays left).

Verified by margin rather than row count, since for four endpoints the rows are the same
rows. On `ppa_games` 2024: 9.5% of 0-7 point games changed, 9.1% of 8-16, 59.9% of 17-27,
99.5% of 28+. All 40 biggest blowouts differ; 228/262 one-score games byte-identical.
A flat rate either way would have meant the flag was not doing what its name says.

`_ngt` shard sets for the two SEASON_WEEK variants match their twins' 211 `(season, week)`
tuples exactly, so `audit_coverage.py` reporting 211/232 is the pre-existing 2012 and
postseason floor.

## Notes

- Originals untouched — different `Endpoint.name` means different filenames, the run was
  `--only` scoped to the nine, and `resume` skips existing files without `--force`.
- Not wired into `enrich.py`. New filenames mean it ignores them; no feature moved and no
  lookahead question arises. Making these a feature source is a separate decision.
- `_scrape_season_week` was silently dropping `endpoint.fixed`. Caught before the scrape,
  which is the only reason the two SEASON_WEEK variants hold filtered rows.
