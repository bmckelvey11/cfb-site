---
type: quick
slug: register-player-success-rate-endpoints
created: 2026-08-26
files_modified:
  - cfb_system_maker/scrapers.py
  - CLAUDE.md
  - scripts/audit_coverage.py
---

# Quick Task: Register the two player success-rate endpoints

## Problem

A coverage audit (`scripts/audit_coverage.py`, added here) diffed the live CFBD
OpenAPI spec (74 paths) against the `ENDPOINTS` registry (61 entries). All 61
registry entries resolve to real spec paths, but 13 live paths were uncovered.

Of those 13, only three are reachable with the currently vendored client
(`cfbd-python` @ 034cd17):

- `/stats/player/success`      -> `StatsApi.get_player_season_success_rates`
- `/stats/player/success/game` -> `StatsApi.get_player_game_success_rates`
- `/info/usage`                -> `InfoApi.get_usage`

The remaining 10 need a client update (vendored clone is 11 commits behind
upstream `main`, which adds CFP, core ratings, expanded SRS, coach profile /
seasons / tenures, and conference affiliations / changes).

## Decision

Register the two **football-data** endpoints only:

- `player_success_season` -> `SEASON`. Signature makes `year` optional but
  required unless `player_id` is given, which is exactly the season-loop shape.
- `player_success_game` -> `SEASON_WEEK`. `year` is required and `week` is
  required unless `team`/`player_id` is given — same shape as the already
  registered `play_stats` and `ppa_players_games`.

`InfoApi.get_usage` is deliberately **not** registered. It reports API account
metering (trailing-days request counts), not football data. It is the same
category as the existing `user_info` entry and has no place in a bulk data
scrape whose output feeds the future JSONB staging layer.

The 10 client-blocked paths are out of scope here — they need a vendored-client
bump, which is a separate change with its own regression surface.

## Done when

`ENDPOINTS` has 63 entries, both new names resolve to live spec paths, the
`scrape --only` runner accepts them, and CLAUDE.md no longer claims 61.
