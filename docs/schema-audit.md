# Schema Audit — REST ↔ GraphQL Join Map

Audit of scraped `data/raw/` (REST, 54 datasets) and `data/graphql/` (25 tables) to find
where they join. Id-space alignment **verified against real data** (2023), not assumed.

## Verified join keys

| Key | REST side | GraphQL side | Id space | Notes |
|-----|-----------|--------------|----------|-------|
| **game_id** | `games.id`, plus `gameId` on advanced_game_stats, drives, plays, play_stats, ppa_games, pregame_win_prob, game_player_stats.`id`, game_team_stats.`id`, lines.`id`, media.`id`, weather.`id` | `game.id`, `gameLines.gameId`, `gameTeam.gameId`, `gameWeather.gameId`, `gamePlayerStat→gameTeam.gameId` | ✅ **same** (int) | Strongest key. 2023: 3,265 shared ids, identical values. |
| **team_id** | `games.homeId/awayId`, `lines.homeTeamId/awayTeamId`, `teams.id`, `records.teamId`, `teams_ats.teamId`, `adjusted_team_season.teamId` | `game.homeTeamId/awayTeamId`, `gameTeam.teamId`, `currentTeams.teamId`, `ratings.teamId`, `athlete(Team).teamId`, `adjustedTeamMetrics.teamId` | ✅ **same** (int) | `teams.id` ↔ `currentTeams.teamId` overlap 673/674. |
| **athlete_id** | `roster.id`, `play_stats.athleteId`, `player_season_stats.playerId`, `recruits.athleteId`, `adjusted_player_*.athleteId` | `athlete.id`, `athleteTeam.athleteId`, `gamePlayerStat.athleteId`, `adjustedPlayerMetrics.athleteId` | ⚠️ **same values, different TYPE** | REST `roster.id` is **string** `"102597"`; GraphQL `athlete.id` is **int**. Cast before joining — then 100% of roster ids match. |
| **venue_id** | `games.venueId`, `weather.venueId`, `venues.id` | `game.venueId` | ✅ same (int) | |
| **conference** | name/abbrev only (`conference`, `homeConference`...) + `conferences.id` | `conferenceId` + name on `game`, `currentTeams`, `ratings`, `historicalTeam`; `conference.id`+name | ⚠️ REST stat tables key by **name**, GraphQL by **conferenceId** | Bridge via `conferences`(REST) / `conference`(GraphQL) on name/abbreviation. |

## The big impedance: name-based REST vs id-based GraphQL

- **REST is name-keyed.** 41 REST datasets carry team **names** (`team`, `offense`, `defense`, `homeTeam`, `school`); only ~6 carry `teamId`. Most REST *stat* tables (sp, srs, fpi, elo, ppa_teams, advanced_*, recruiting, etc.) have **no team id at all** — only the team name string.
- **GraphQL is id-keyed.** Nearly every GraphQL table carries `teamId`.
- **Crosswalk table:** REST `teams`/`fbs_teams` (`id` + `school`) and GraphQL `currentTeams`/`historicalTeam` (`teamId` + `school`) both carry id **and** name → use one as the `dim_team` bridge. Join REST-stat(name) → dim_team(name→id) → GraphQL(id).

## Gotchas to handle in the load

1. **athlete_id type** — REST string vs GraphQL int. Normalize to one type.
2. **season vs year** — REST mixes `season` (game-level tables) and `year` (season/ratings/recruiting). GraphQL same split + `startYear/endYear` on athleteTeam/historicalTeam. Pick one canonical `season` column.
3. **Game coverage differs** — REST `games` 2023 = 3,595; GraphQL `game` = 3,404. 330 REST-only, 139 GraphQL-only (classification coverage differs). Outer-join, don't assume 1:1.
4. **Team name spelling** — names match cleanly in practice (Eastern University ↔ Eastern University), but always crosswalk via id where available rather than name string.

## Suggested Postgres model

```
dim_team    (team_id PK, school, conference, conference_id)   -- from teams + currentTeams
dim_athlete (athlete_id PK int, name, position)               -- from athlete (+ roster names)
dim_game    (game_id PK, season, week, season_type, home_team_id, away_team_id, venue_id)
dim_conference (conference_id PK, name, abbreviation)

-- facts join on game_id / team_id / athlete_id + season/week:
fact_lines, fact_drives, fact_plays, fact_play_stats, fact_ppa_*,
fact_ratings (sp/srs/fpi/elo), fact_recruits, fact_game_player_stats ...
```
Load REST + GraphQL raw JSON into `JSONB` staging, then normalize into the above on the verified keys.

## GraphQL-only vs REST-only (no join partner)

- **REST-only (not in GraphQL):** plays, drives, play_stats, win_probability, advanced_box_score, advanced_*_stats, ppa_* detail, returning_production, havoc. → these stay REST-sourced.
- **GraphQL-only convenience:** `athlete`/`athleteTeam` (full id-keyed roster history), `currentTeams`/`historicalTeam` (the team crosswalk), pre-joined `gameTeam`.
