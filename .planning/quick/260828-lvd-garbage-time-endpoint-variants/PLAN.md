---
task_id: 260828-lvd
slug: garbage-time-endpoint-variants
date: 2026-08-28
mode: quick
---

# Scrape the garbage-time-excluded endpoint variants

Register `_ngt` ("no garbage time") variants of the 9 CFBD endpoints that accept
`excludeGarbageTime`, and pull 2012-2025. Closes the last documented parameter-level
gap in `docs/data-coverage.md` besides the two cost-deferred pulls.

## Why this is a new source, not a fix

`excludeGarbageTime` does not narrow the result set the way `team` or `conference` do —
it filters the *plays feeding the aggregation*, so the numbers on the surviving rows
change. It cannot be reproduced client-side from the unfiltered dumps, which store the
aggregates rather than the plays behind them.

## Probe first (done 2026-08-28, 2024, before any code change)

All nine differ from their unfiltered twin, so none is a no-op and all nine are worth
registering. Two distinct behaviours:

| Endpoint | rows (gt -> ngt) | rows differing |
|---|---|---|
| `ppa_games` | 1,711 -> 1,711 | 689 |
| `ppa_teams` | 134 -> 134 | 134 |
| `advanced_game_stats` | 3,212 -> 3,212 | 1,186 |
| `advanced_season_stats` | 134 -> 134 | 134 |
| `ppa_players_season` | 4,131 -> 3,696 | n/a (rows dropped) |
| `ppa_players_games` (wk1) | 3,250 -> 2,887 | n/a |
| `player_usage` | 4,131 -> 3,696 | n/a |
| `player_success_season` | 3,752 -> 3,309 | n/a |
| `player_success_game` (wk1) | 2,090 -> 1,801 | n/a |

Game/team-level endpoints keep every row and move values. **Player-level endpoints also
drop rows** — a player whose only snaps were garbage time has zero qualifying plays, so
the row disappears. The `ppa_games` 689/1,711 split is the falsification signal: not
every game differs (so it is not re-computing everything) and not none (so the flag is
live). ~60% of 2024 games had no garbage time at all.

## Tasks

1. **`_scrape_season_week` must apply `endpoint.fixed`.** It does not today, unlike
   `_scrape_season`. Without this the two SEASON_WEEK variants would scrape *without*
   the flag and write duplicate content under an `_ngt` name — a silent wrong-data bug
   that `resume` would then protect forever.
   Verify: no registry entry uses `fixed=` today, so the change is inert for existing data.

2. **Register 9 `_ngt` endpoints** with `fixed={"exclude_garbage_time": True}`.
   `Endpoint.name` is the output file prefix, so all filename shapes come for free:
   `{name}_ngt_{season}.json`, `..._ngt_{season}_wk{w}.json`, `..._ngt_{season}_post_wk{w}.json`.
   Verify: `python -m pytest` green; `scripts/audit_coverage.py` derives expectations
   from ENDPOINTS + mode, so it picks the new files up with no edit.

3. **Scrape 2012-2025.** ~7 SEASON endpoints x 14 seasons + 2 SEASON_WEEK endpoints x
   14 seasons x (15 regular + postseason weeks).
   Verify: files on disk, non-empty, no endpoint reported an error.

4. **Verify semantically, not by row count** — the rows are the same rows. On disk, for
   `ppa_games_2024` vs `ppa_games_ngt_2024`: a blowout's row must differ, a one-score
   game's row must be byte-identical (no garbage time occurred, nothing was excluded).
   If every game differs, or none does, stop.

5. **Update `docs/data-coverage.md`** — move `excludeGarbageTime` out of "unused options"
   and record the probe table, since that file's job is recording *why* something is
   present or absent.

## Out of scope

Not wiring these into `enrich.py`. New filenames mean `enrich` ignores them, no feature
moves, no lookahead question arises. Making them a feature source is a separate decision.
