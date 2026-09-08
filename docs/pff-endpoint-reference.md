# PFF API endpoint reference

Auto-generated from the PFF OpenAPI document (**spec version 2.1.0**, 70 operations) by [`scripts/gen_pff_endpoint_reference.py`](../scripts/gen_pff_endpoint_reference.py). The spec is public-read at <https://api.pff.com/openapi.json> — no credential — so this regenerates without a subscription. Re-run it after `restish api sync pff` reports new commands.

Structure only. PFF authors long per-parameter prose in the spec; it is not copied here. Read it with `restish pff <command> --help`. Setup, auth and export mechanics are in [`docs/pff-cli.md`](pff-cli.md).

Required parameters are **positional** in Restish, in the order below, and shown as `<name>`; optional ones are `--flags`. Flag names are not always wire names — `--franchise` is `franchise_id`, `--game` is `game_id`. The **Wire name** column is what a raw HTTP client must send; `—` means the two match.

## Contents

- [`ref`](#ref) — 3 operations
- [`team`](#team) — 10 operations
- [`player`](#player) — 21 operations
- [`facet`](#facet) — 28 operations
- [`signature`](#signature) — 4 operations
- [`auth`](#auth) — 2 operations
- [`meta`](#meta) — 2 operations

## ref

Reference data — leagues, games, the player directory. Start here: these are where team and player ids come from.

### `ref-games`  ·  alias `games`

`GET /v1/games`

List game results for a league, season and week

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `<season>` | — | query | integer | yes |
| `<week>` | — | query | integer | yes |
| `--franchise` | `franchise_id` | query | integer |  |

Response schema: `GamesResponse`

### `ref-leagues`  ·  alias `leagues`

`GET /v1/leagues`

List the leagues you can read, with their seasons and weeks

Response schema: `LeaguesResponse`

### `ref-players`  ·  alias `players`

`GET /v1/players`

Search the player directory by name or id

**Requires** (`name`) or (`id`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `--id` | — | query | integer |  |
| `--name` | — | query | string |  |

Response schema: `PlayersResponse`

## team

Team lists and reports. `team-*` other than `teams`/`team-overview`/`team-summary` are PFF's own `/v2` contract — camelCase, `{columns, rows}` tables, CSV via `--format csv`.

### `team-directory`

`GET /v2/{league}/teams`

The league's teams for a season, with ids, slugs, colours and groups

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | path | nfl \| ncaa | yes |
| `--season` | — | query | integer, min 2006 |  |
| `--format` | — | query | json \| csv |  |

CSV: `--format csv` (pair with `--rsh-print b`).

Response schema: `TeamDirectoryTable`

### `team-leaders`

`GET /v2/{league}/teams/{team}/leaders`

A team's statistical leaders for one position group, ranked league-wide

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | path | nfl \| ncaa | yes |
| `<team>` | — | path | string, `^[a-z0-9]+(-[a-z0-9]+)*$` | yes |
| `--season` | — | query | integer, min 2006 |  |
| `--week-group` | — | query | REG \| PO \| REGPO |  |
| `--group` | — | query | receiving \| passing \| rushing \| defense |  |
| `--format` | — | query | json \| csv |  |

CSV: `--format csv` (pair with `--rsh-print b`).

Response schema: `TeamLeadersTable`

### `team-list`  ·  alias `teams`

`GET /v1/teams`

List a season's teams, franchise groups and schedule

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `--season` | — | query | integer |  |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |

Response schema: `TeamsResponse`

### `team-overview`

`GET /v1/teams/overview`

Season-to-date team report, one row per team

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `<season>` | — | query | integer | yes |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |

Response schema: `TeamOverviewResponse`

### `team-report`

`GET /v2/{league}/teams/{team}/reports/{report}`

One of nineteen player reports for a team, one row per player

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | path | nfl \| ncaa | yes |
| `<team>` | — | path | string, `^[a-z0-9]+(-[a-z0-9]+)*$` | yes |
| `<report>` | — | path | offense \| passing \| passing-depth \| passing-pressure \| receiving \| receiving-depth \| rushing \| blocking \| pass-blocking \| run-blocking \| defense \| run-defense \| pass-rush \| coverage \| special-teams \| kick-returns \| field-goals \| punting \| kickoffs | yes |
| `--season` | — | query | integer, min 2006 |  |
| `--week-group` | — | query | REG \| PO \| REGPO |  |
| `--week` | — | query | integer |  |
| `--week-to` | — | query | integer |  |
| `--format` | — | query | json \| csv |  |

CSV: `--format csv` (pair with `--rsh-print b`).

Response schema: `TeamReportTable`

### `team-roster`

`GET /v2/{league}/teams/{team}/roster`

A team's depth-chart roster with grades, ranks and snap counts

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | path | nfl \| ncaa | yes |
| `<team>` | — | path | string, `^[a-z0-9]+(-[a-z0-9]+)*$` | yes |
| `--season` | — | query | integer, min 2006 |  |
| `--format` | — | query | json \| csv |  |

CSV: `--format csv` (pair with `--rsh-print b`).

Response schema: `TeamRosterTable`

### `team-rushing-direction`

`GET /v2/{league}/teams/{team}/reports/rushing-direction`

A team's rushing by direction, one row per rusher and gap, plus totals

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | path | nfl \| ncaa | yes |
| `<team>` | — | path | string, `^[a-z0-9]+(-[a-z0-9]+)*$` | yes |
| `--season` | — | query | integer, min 2006 |  |
| `--week-group` | — | query | REG \| PO \| REGPO |  |
| `--format` | — | query | json \| csv |  |
| `--table` | — | query | rows \| totals |  |

CSV: `--format csv` (pair with `--rsh-print b`).

Response schema: `TeamRushingDirectionTable`

### `team-schedule`

`GET /v2/{league}/teams/{team}/schedule`

A team's season schedule, with results and strength of schedule

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | path | nfl \| ncaa | yes |
| `<team>` | — | path | string, `^[a-z0-9]+(-[a-z0-9]+)*$` | yes |
| `--season` | — | query | integer, min 2006 |  |
| `--format` | — | query | json \| csv |  |

CSV: `--format csv` (pair with `--rsh-print b`).

Response schema: `TeamScheduleTable`

### `team-stats`

`GET /v2/{league}/teams/stats`

Team stats table for one category, every value ranked against the scope

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | path | nfl \| ncaa | yes |
| `--season` | — | query | integer, min 2006 |  |
| `--week-group` | — | query | REG \| PO \| REGPO |  |
| `--week-ids` | — | query | string, `^[0-9]+(,[0-9]+)*$` |  |
| `--category` | — | query | offense-overall-success \| offense-passing \| offense-rushing \| defense-overall-success \| defense-passing \| defense-rushing \| defense-opponent-tendencies |  |
| `--scope` | — | query | league \| afc \| nfc \| afc-east \| afc-north \| afc-south \| afc-west \| nfc-east \| nfc-north \| nfc-south \| nfc-west |  |
| `--format` | — | query | json \| csv |  |

CSV: `--format csv` (pair with `--rsh-print b`).

Response schema: `TeamStatsTable`

### `team-summary`

`GET /v1/teams/summary`

Per-game team report for one franchise, one row per game

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `<season>` | — | query | integer | yes |
| `--week` | — | query | string |  |
| `<franchise_id>` | — | query | integer | yes |

Response schema: `TeamSummaryResponse`

## player

One player's reports. Takes a player id from `ref-players`.

### `player-defense-summary`

`GET /v1/player/defense/summary`

Defense summary for one player

**Requires** (`season`) or (`career`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `--season` | — | query | integer |  |
| `--week` | — | query | string |  |
| `<player_id>` | — | query | integer | yes |
| `--career` | — | query | string |  |

Response schema: `PlayerDefenseSummaryResponse`

### `player-field-goal-summary`

`GET /v1/player/field_goal/summary`

Field-goal kicking for one player

**Requires** (`season`) or (`career`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `--season` | — | query | integer |  |
| `--week` | — | query | string |  |
| `<player_id>` | — | query | integer | yes |
| `--career` | — | query | string |  |

Response schema: `PlayerFieldGoalSummaryResponse`

### `player-kickoff-summary`

`GET /v1/player/kickoff/summary`

Kickoffs for one player

**Requires** (`season`) or (`career`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `--season` | — | query | integer |  |
| `--week` | — | query | string |  |
| `<player_id>` | — | query | integer | yes |
| `--career` | — | query | string |  |

Response schema: `PlayerKickoffSummaryResponse`

### `player-offense-blocking`

`GET /v1/player/offense/blocking`

Blocking report for one player

**Requires** (`season`) or (`career`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `--season` | — | query | integer |  |
| `--week` | — | query | string |  |
| `<player_id>` | — | query | integer | yes |
| `--career` | — | query | string |  |

Response schema: `PlayerOffenseBlockingResponse`

### `player-offense-pass-blocking`

`GET /v1/player/offense/pass_blocking`

Pass-blocking report for one player

**Requires** (`season`) or (`career`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `--season` | — | query | integer |  |
| `--week` | — | query | string |  |
| `<player_id>` | — | query | integer | yes |
| `--career` | — | query | string |  |

Response schema: `PlayerOffensePassBlockingResponse`

### `player-offense-run-blocking`

`GET /v1/player/offense/run_blocking`

Run-blocking report for one player

**Requires** (`season`) or (`career`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `--season` | — | query | integer |  |
| `--week` | — | query | string |  |
| `<player_id>` | — | query | integer | yes |
| `--career` | — | query | string |  |

Response schema: `PlayerOffenseRunBlockingResponse`

### `player-offense-summary`

`GET /v1/player/offense/summary`

Offense summary for one player

**Requires** (`season`) or (`career`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `--season` | — | query | integer |  |
| `--week` | — | query | string |  |
| `<player_id>` | — | query | integer | yes |
| `--career` | — | query | string |  |

Response schema: `PlayerOffenseSummaryResponse`

### `player-passing-concept`

`GET /v1/player/passing/concept`

Passing by play concept for one player

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `<season>` | — | query | integer | yes |
| `--week` | — | query | string |  |
| `<player_id>` | — | query | integer | yes |
| `--career` | — | query | string |  |

Response schema: `PlayerPassingConceptResponse`

### `player-passing-depth`

`GET /v1/player/passing/depth`

Passing by target depth for one player

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `<season>` | — | query | integer | yes |
| `--week` | — | query | string |  |
| `<player_id>` | — | query | integer | yes |
| `--career` | — | query | string |  |

Response schema: `PlayerPassingDepthResponse`

### `player-passing-pressure`

`GET /v1/player/passing/pressure`

Passing under pressure for one player

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `<season>` | — | query | integer | yes |
| `--week` | — | query | string |  |
| `<player_id>` | — | query | integer | yes |
| `--career` | — | query | string |  |

Response schema: `PlayerPassingPressureResponse`

### `player-passing-summary`

`GET /v1/player/passing/summary`

Passing summary for one player

**Requires** (`season`) or (`career`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `--season` | — | query | integer |  |
| `--week` | — | query | string |  |
| `<player_id>` | — | query | integer | yes |
| `--career` | — | query | string |  |

Response schema: `PlayerPassingSummaryResponse`

### `player-position-pivot`

`GET /v1/player/position/pivot`

Player snap counts pivoted by position

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `<season>` | — | query | integer | yes |
| `--week` | — | query | string |  |
| `<player_id>` | — | query | integer | yes |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `PositionPivotResponse`

### `player-punting-summary`

`GET /v1/player/punting/summary`

Punting for one player

**Requires** (`season`) or (`career`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `--season` | — | query | integer |  |
| `--week` | — | query | string |  |
| `<player_id>` | — | query | integer | yes |
| `--career` | — | query | string |  |

Response schema: `PlayerPuntingSummaryResponse`

### `player-receiving-depth`

`GET /v1/player/receiving/depth`

Receiving by target depth for one player

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `<season>` | — | query | integer | yes |
| `--week` | — | query | string |  |
| `<player_id>` | — | query | integer | yes |
| `--career` | — | query | string |  |

Response schema: `PlayerReceivingDepthResponse`

### `player-receiving-summary`

`GET /v1/player/receiving/summary`

Receiving summary for one player

**Requires** (`season`) or (`career`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `--season` | — | query | integer |  |
| `--week` | — | query | string |  |
| `<player_id>` | — | query | integer | yes |
| `--career` | — | query | string |  |

Response schema: `PlayerReceivingSummaryResponse`

### `player-return-summary`

`GET /v1/player/return/summary`

Kick and punt returns for one player

**Requires** (`season`) or (`career`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `--season` | — | query | integer |  |
| `--week` | — | query | string |  |
| `<player_id>` | — | query | integer | yes |
| `--career` | — | query | string |  |

Response schema: `PlayerReturnSummaryResponse`

### `player-rushing-direction`

`GET /v1/player/rushing/direction`

Rushing by direction for one player

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `<season>` | — | query | integer | yes |
| `--week` | — | query | string |  |
| `<player_id>` | — | query | integer | yes |
| `--career` | — | query | string |  |

Response schema: `PlayerRushingDirectionResponse`

### `player-rushing-summary`

`GET /v1/player/rushing/summary`

Rushing summary for one player

**Requires** (`season`) or (`career`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `--season` | — | query | integer |  |
| `--week` | — | query | string |  |
| `<player_id>` | — | query | integer | yes |
| `--career` | — | query | string |  |

Response schema: `PlayerRushingSummaryResponse`

### `player-seasons`

`GET /v1/player/seasons`

List the seasons a player has data for

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `--season` | — | query | integer |  |
| `--week` | — | query | string |  |
| `<player_id>` | — | query | integer | yes |

Response schema: `PlayerSeasonsResponse`

### `player-snaps-summary`

`GET /v1/player/snaps/summary`

Snap counts for a player, broken out by position

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `<season>` | — | query | integer | yes |
| `--week` | — | query | string |  |
| `<player_id>` | — | query | integer | yes |

Response schema: `PlayerSnapsSummaryResponse`

### `player-special-summary`

`GET /v1/player/special/summary`

Special-teams summary for one player

**Requires** (`season`) or (`career`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `--season` | — | query | integer |  |
| `--week` | — | query | string |  |
| `<player_id>` | — | query | integer | yes |
| `--career` | — | query | string |  |

Response schema: `PlayerSpecialSummaryResponse`

## facet

League-wide leaderboards, one row per player. CSV via `--export true`.

### `facet-defense-coverage`

`GET /v1/facet/defense/coverage`

League-wide coverage leaderboard

**Requires** (`league` + `season`) or (`game_id`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `--league` | — | query | nfl \| ncaa \| hs \| aaf \| ufl |  |
| `--season` | — | query | string, `^(\d{4}(,\d{4})*)?$` |  |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |
| `--game` | `game_id` | query | integer |  |
| `--division` | — | query | string |  |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `FacetDefenseCoverageResponse`

### `facet-defense-coverage-matchup`

`GET /v1/facet/defense/coverage_matchup`

League-wide coverage matchup leaderboard

**Requires** (`league` + `season`) or (`game_id`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `--league` | — | query | nfl \| ncaa \| hs \| aaf \| ufl |  |
| `--season` | — | query | string, `^(\d{4}(,\d{4})*)?$` |  |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |
| `--game` | `game_id` | query | integer |  |
| `--division` | — | query | string |  |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `FacetReceivingCoverageResponse`

### `facet-defense-coverage-scheme`

`GET /v1/facet/defense/coverage_scheme`

League-wide coverage-by-scheme leaderboard

**Requires** (`league` + `season`) or (`game_id`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `--league` | — | query | nfl \| ncaa \| hs \| aaf \| ufl |  |
| `--season` | — | query | string, `^(\d{4}(,\d{4})*)?$` |  |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |
| `--game` | `game_id` | query | integer |  |
| `--division` | — | query | string |  |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `FacetDefenseCoverageSchemeResponse`

### `facet-defense-pass-rush`

`GET /v1/facet/defense/pass_rush`

League-wide pass-rush leaderboard

**Requires** (`league` + `season`) or (`game_id`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `--league` | — | query | nfl \| ncaa \| hs \| aaf \| ufl |  |
| `--season` | — | query | string, `^(\d{4}(,\d{4})*)?$` |  |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |
| `--game` | `game_id` | query | integer |  |
| `--division` | — | query | string |  |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `FacetDefensePassRushResponse`

### `facet-defense-run`

`GET /v1/facet/defense/run`

League-wide run-defense leaderboard

**Requires** (`league` + `season`) or (`game_id`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `--league` | — | query | nfl \| ncaa \| hs \| aaf \| ufl |  |
| `--season` | — | query | string, `^(\d{4}(,\d{4})*)?$` |  |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |
| `--game` | `game_id` | query | integer |  |
| `--division` | — | query | string |  |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `FacetDefenseRunResponse`

### `facet-defense-summary`  ·  alias `defense`

`GET /v1/facet/defense/summary`

League-wide defense summary leaderboard

**Requires** (`league` + `season`) or (`game_id`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `--league` | — | query | nfl \| ncaa \| hs \| aaf \| ufl |  |
| `--season` | — | query | string, `^(\d{4}(,\d{4})*)?$` |  |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |
| `--game` | `game_id` | query | integer |  |
| `--division` | — | query | string |  |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `FacetDefenseSummaryResponse`

### `facet-field-goal-summary`

`GET /v1/facet/field_goal/summary`

League-wide field-goal kicking leaderboard

**Requires** (`league` + `season`) or (`game_id`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `--league` | — | query | nfl \| ncaa \| hs \| aaf \| ufl |  |
| `--season` | — | query | string, `^(\d{4}(,\d{4})*)?$` |  |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |
| `--game` | `game_id` | query | integer |  |
| `--division` | — | query | string |  |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `FacetFieldGoalSummaryResponse`

### `facet-kickoff-summary`

`GET /v1/facet/kickoff/summary`

League-wide kickoff leaderboard

**Requires** (`league` + `season`) or (`game_id`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `--league` | — | query | nfl \| ncaa \| hs \| aaf \| ufl |  |
| `--season` | — | query | string, `^(\d{4}(,\d{4})*)?$` |  |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |
| `--game` | `game_id` | query | integer |  |
| `--division` | — | query | string |  |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `FacetKickoffSummaryResponse`

### `facet-offense-blocking`  ·  alias `blocking`

`GET /v1/facet/offense/blocking`

League-wide blocking leaderboard

**Requires** (`league` + `season`) or (`game_id`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `--league` | — | query | nfl \| ncaa \| hs \| aaf \| ufl |  |
| `--season` | — | query | string, `^(\d{4}(,\d{4})*)?$` |  |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |
| `--game` | `game_id` | query | integer |  |
| `--division` | — | query | string |  |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `FacetOffenseBlockingResponse`

### `facet-offense-pass-blocking`

`GET /v1/facet/offense/pass_blocking`

League-wide pass-blocking leaderboard

**Requires** (`league` + `season`) or (`game_id`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `--league` | — | query | nfl \| ncaa \| hs \| aaf \| ufl |  |
| `--season` | — | query | string, `^(\d{4}(,\d{4})*)?$` |  |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |
| `--game` | `game_id` | query | integer |  |
| `--division` | — | query | string |  |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `FacetOffensePassBlockingResponse`

### `facet-offense-run-blocking`

`GET /v1/facet/offense/run_blocking`

League-wide run-blocking leaderboard

**Requires** (`league` + `season`) or (`game_id`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `--league` | — | query | nfl \| ncaa \| hs \| aaf \| ufl |  |
| `--season` | — | query | string, `^(\d{4}(,\d{4})*)?$` |  |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |
| `--game` | `game_id` | query | integer |  |
| `--division` | — | query | string |  |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `FacetOffenseRunBlockingResponse`

### `facet-offense-summary`

`GET /v1/facet/offense/summary`

League-wide offense summary leaderboard

**Requires** (`league` + `season`) or (`game_id`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `--league` | — | query | nfl \| ncaa \| hs \| aaf \| ufl |  |
| `--season` | — | query | string, `^(\d{4}(,\d{4})*)?$` |  |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |
| `--game` | `game_id` | query | integer |  |
| `--division` | — | query | string |  |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `FacetOffenseSummaryResponse`

### `facet-passing-allowed-pressure`

`GET /v1/facet/passing/allowed_pressure`

League-wide pressure-allowed leaderboard

**Requires** (`league` + `season`) or (`game_id`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `--league` | — | query | nfl \| ncaa \| hs \| aaf \| ufl |  |
| `--season` | — | query | string, `^(\d{4}(,\d{4})*)?$` |  |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |
| `--game` | `game_id` | query | integer |  |
| `--division` | — | query | string |  |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `FacetPassingAllowedPressureResponse`

### `facet-passing-concept`

`GET /v1/facet/passing/concept`

League-wide passing-by-concept leaderboard

**Requires** (`league` + `season`) or (`game_id`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `--league` | — | query | nfl \| ncaa \| hs \| aaf \| ufl |  |
| `--season` | — | query | string, `^(\d{4}(,\d{4})*)?$` |  |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |
| `--game` | `game_id` | query | integer |  |
| `--division` | — | query | string |  |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `FacetPassingConceptResponse`

### `facet-passing-depth`

`GET /v1/facet/passing/depth`

League-wide passing-by-depth leaderboard

**Requires** (`league` + `season`) or (`game_id`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `--league` | — | query | nfl \| ncaa \| hs \| aaf \| ufl |  |
| `--season` | — | query | string, `^(\d{4}(,\d{4})*)?$` |  |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |
| `--game` | `game_id` | query | integer |  |
| `--division` | — | query | string |  |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `FacetPassingDepthResponse`

### `facet-passing-detail`

`GET /v1/facet/passing/detail`

League-wide passing detail leaderboard

**Requires** (`league` + `season`) or (`game_id`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `--league` | — | query | nfl \| ncaa \| hs \| aaf \| ufl |  |
| `--season` | — | query | string, `^(\d{4}(,\d{4})*)?$` |  |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |
| `--game` | `game_id` | query | integer |  |
| `--division` | — | query | string |  |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `FacetPassingDetailResponse`

### `facet-passing-pressure`

`GET /v1/facet/passing/pressure`

League-wide passing-under-pressure leaderboard

**Requires** (`league` + `season`) or (`game_id`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `--league` | — | query | nfl \| ncaa \| hs \| aaf \| ufl |  |
| `--season` | — | query | string, `^(\d{4}(,\d{4})*)?$` |  |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |
| `--game` | `game_id` | query | integer |  |
| `--division` | — | query | string |  |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `FacetPassingPressureResponse`

### `facet-passing-summary`  ·  alias `passing`

`GET /v1/facet/passing/summary`

League-wide passing summary leaderboard

**Requires** (`league` + `season`) or (`game_id`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `--league` | — | query | nfl \| ncaa \| hs \| aaf \| ufl |  |
| `--season` | — | query | string, `^(\d{4}(,\d{4})*)?$` |  |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |
| `--game` | `game_id` | query | integer |  |
| `--division` | — | query | string |  |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `FacetPassingSummaryResponse`

### `facet-punting-summary`

`GET /v1/facet/punting/summary`

League-wide punting leaderboard

**Requires** (`league` + `season`) or (`game_id`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `--league` | — | query | nfl \| ncaa \| hs \| aaf \| ufl |  |
| `--season` | — | query | string, `^(\d{4}(,\d{4})*)?$` |  |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |
| `--game` | `game_id` | query | integer |  |
| `--division` | — | query | string |  |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `FacetPuntingSummaryResponse`

### `facet-receiving-concept`

`GET /v1/facet/receiving/concept`

League-wide receiving-by-concept leaderboard

**Requires** (`league` + `season`) or (`game_id`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `--league` | — | query | nfl \| ncaa \| hs \| aaf \| ufl |  |
| `--season` | — | query | string, `^(\d{4}(,\d{4})*)?$` |  |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |
| `--game` | `game_id` | query | integer |  |
| `--division` | — | query | string |  |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `FacetReceivingConceptResponse`

### `facet-receiving-coverage`

`GET /v1/facet/receiving/coverage`

League-wide receiving-versus-coverage leaderboard

**Requires** (`league` + `season`) or (`game_id`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `--league` | — | query | nfl \| ncaa \| hs \| aaf \| ufl |  |
| `--season` | — | query | string, `^(\d{4}(,\d{4})*)?$` |  |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |
| `--game` | `game_id` | query | integer |  |
| `--division` | — | query | string |  |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `FacetReceivingCoverageResponse`

### `facet-receiving-depth`

`GET /v1/facet/receiving/depth`

League-wide receiving-by-depth leaderboard

**Requires** (`league` + `season`) or (`game_id`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `--league` | — | query | nfl \| ncaa \| hs \| aaf \| ufl |  |
| `--season` | — | query | string, `^(\d{4}(,\d{4})*)?$` |  |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |
| `--game` | `game_id` | query | integer |  |
| `--division` | — | query | string |  |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `FacetReceivingDepthResponse`

### `facet-receiving-scheme`

`GET /v1/facet/receiving/scheme`

League-wide receiving-by-scheme leaderboard

**Requires** (`league` + `season`) or (`game_id`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `--league` | — | query | nfl \| ncaa \| hs \| aaf \| ufl |  |
| `--season` | — | query | string, `^(\d{4}(,\d{4})*)?$` |  |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |
| `--game` | `game_id` | query | integer |  |
| `--division` | — | query | string |  |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `FacetReceivingSchemeResponse`

### `facet-receiving-summary`  ·  alias `receiving`

`GET /v1/facet/receiving/summary`

League-wide receiving summary leaderboard

**Requires** (`league` + `season`) or (`game_id`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `--league` | — | query | nfl \| ncaa \| hs \| aaf \| ufl |  |
| `--season` | — | query | string, `^(\d{4}(,\d{4})*)?$` |  |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |
| `--game` | `game_id` | query | integer |  |
| `--division` | — | query | string |  |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `FacetReceivingSummaryResponse`

### `facet-return-summary`

`GET /v1/facet/return/summary`

League-wide return leaderboard

**Requires** (`league` + `season`) or (`game_id`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `--league` | — | query | nfl \| ncaa \| hs \| aaf \| ufl |  |
| `--season` | — | query | string, `^(\d{4}(,\d{4})*)?$` |  |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |
| `--game` | `game_id` | query | integer |  |
| `--division` | — | query | string |  |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `FacetReturnSummaryResponse`

### `facet-rushing-direction`

`GET /v1/facet/rushing/direction`

League-wide rushing-by-direction leaderboard

**Requires** (`league` + `season`) or (`game_id`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `--league` | — | query | nfl \| ncaa \| hs \| aaf \| ufl |  |
| `--season` | — | query | string, `^(\d{4}(,\d{4})*)?$` |  |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |
| `--game` | `game_id` | query | integer |  |
| `--division` | — | query | string |  |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `FacetRushingDirectionResponse`

### `facet-rushing-summary`  ·  alias `rushing`

`GET /v1/facet/rushing/summary`

League-wide rushing summary leaderboard

**Requires** (`league` + `season`) or (`game_id`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `--league` | — | query | nfl \| ncaa \| hs \| aaf \| ufl |  |
| `--season` | — | query | string, `^(\d{4}(,\d{4})*)?$` |  |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |
| `--game` | `game_id` | query | integer |  |
| `--division` | — | query | string |  |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `FacetRushingSummaryResponse`

### `facet-special-summary`  ·  alias `special-teams`

`GET /v1/facet/special/summary`

League-wide special-teams leaderboard

**Requires** (`league` + `season`) or (`game_id`) — otherwise `400 invalid_parameter`.

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `--league` | — | query | nfl \| ncaa \| hs \| aaf \| ufl |  |
| `--season` | — | query | string, `^(\d{4}(,\d{4})*)?$` |  |
| `--week` | — | query | string |  |
| `--franchise` | `franchise_id` | query | integer |  |
| `--game` | `game_id` | query | integer |  |
| `--division` | — | query | string |  |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `FacetSpecialSummaryResponse`

## signature

PFF signature stats. CSV via `--export true`.

### `signature-defense-outside-pass-rush`

`GET /v1/facet/signature/defense/outside_pass_rush`

Signature stat: outside pass rush

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `<season>` | — | query | string, `^(\d{4}(,\d{4})*)?$` | yes |
| `<week>` | — | query | string | yes |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `SignatureDefenseOutsidePassRushResponse`

### `signature-defense-slot-coverage`

`GET /v1/facet/signature/defense/slot_coverage`

Signature stat: slot coverage

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `<season>` | — | query | string, `^(\d{4}(,\d{4})*)?$` | yes |
| `<week>` | — | query | string | yes |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `SignatureDefenseSlotCoverageResponse`

### `signature-pass-blocking-efficiency-line`

`GET /v1/facet/signature/pass-blocking/efficiency/line`

Signature stat: pass-blocking efficiency, by line

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `<season>` | — | query | string, `^(\d{4}(,\d{4})*)?$` | yes |
| `<week>` | — | query | string | yes |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `SignaturePassBlockingEfficiencyLineResponse`

### `signature-passing-time-in-pocket`

`GET /v1/facet/signature/passing/time_in_pocket`

Signature stat: time in pocket

| Flag | Wire name | In | Type / values | Required |
| --- | --- | --- | --- | --- |
| `<league>` | — | query | nfl \| ncaa \| hs \| aaf \| ufl | yes |
| `<season>` | — | query | string, `^(\d{4}(,\d{4})*)?$` | yes |
| `<week>` | — | query | string | yes |
| `--export` | — | query | true |  |

CSV: `--export true` (pair with `--rsh-print b`).

Response schema: `SignaturePassingTimeInPocketResponse`

## auth

Session and credential.

### `logout`

`POST /v1/auth/logout`

End this credential's access to this API

### `whoami`

`GET /v1/auth/whoami`

Show what this API believes about the current credential

Response schema: `Whoami`

## meta

The API contract itself.

### `openapi-json`

`GET /openapi.json`

Fetch this contract as JSON

### `openapi-yaml`

`GET /openapi.yaml`

Fetch this contract as YAML
