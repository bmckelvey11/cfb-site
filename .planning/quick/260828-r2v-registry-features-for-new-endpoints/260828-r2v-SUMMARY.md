---
task: registry-features-for-new-endpoints
date: 2026-08-28
mode: quick
status: complete
---

# Quick Task 260828-r2v — Summary

Five registry features added off the endpoints registered in `260828-m3k`. Registry is now
**64 features**, `registry_version()` `ba927d337b76` → `cb6b4251db00` (the web UI's stale-
sidecar warning fires as designed until `enrich` is re-run; it has been).

| Key | Source | Non-null on 13,014 real games |
|---|---|---|
| `prior_core_overall` | `core_ratings_{S-1}` | 56.3% |
| `prior_core_offense` | `core_ratings_{S-1}` | 56.3% |
| `prior_core_defense` | `core_ratings_{S-1}` | 56.3% |
| `prior_srs_rating` | `srs_expanded_{S-1}` | 93.3% |
| `conference_change` | `conference_changes_{S}` | 100% (761 home-side moves) |

## The lookahead call

Core ratings and expanded SRS are **season-final** — core rows carry
`throughSeasonType: "postseason"`. Season S's value on a season-S game leaks the result of
the game being bet. Both follow the pattern `prior_off_wepa` already established
(`_index_prior_player_agg`): index season S-1's file under key S. New
`raw_prior_team_season` source kind, one indexer shared by both files via `source_file`.
Nothing went into `result_lookahead`.

The lag pushes the usable floor out a year: `core_ratings` itself is empty before 2016, so
`prior_core_*` is null for every 2013-2016 game and lands ~850/season from 2017. The
2022+ denominator grows (1,400-1,600 games/season) because the registry file covers FBS
only while the schedule includes FCS opponents — that is why `prior_srs_rating`, which
includes FCS, is 37 points higher.

`conference_change` is current-season on purpose (realignment is public pre-kickoff) and is
stored as a per-season **set**, so a team absent from a season file that did load resolves
to `False` rather than `None` — "did not change conferences" is an answer, not missing data.

## Verified end-to-end, not just unit-tested

Ohio State's 2025 games read `prior_core_overall` 37.25 and `prior_srs_rating` 24.6 —
exactly its 2024 raw values. Arizona's 2024 games read `conference_change` True (Pac-12 →
Big 12) with its opponent False. Four new tests mirror the `prior_off_wepa` pair: a
same-season sentinel that must never surface, and absent-file → `None`.

Suite: 562 passed, 1 skipped.

## Skipped deliberately

- **`coach_seasons`** — season aggregates duplicating `records` and the `season_to_date`
  running stats; `draftFollowingSeason` is lookahead by construction.
- **`cfp_playoff` / `cfp_games` / `cfp_participants`** — pregame-legitimate (seed, committee
  rank) but ~64 of 13,014 games. No sample to filter on. Add if someone wants a
  playoff-only study.
- **`conference_affiliations`** — already covered by `conference_classification` and
  `team_conference`.
- **`coach_profile` / `coach_tenures`** — `on_demand`, nothing on disk to join.
