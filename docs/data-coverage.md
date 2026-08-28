# CFBD data coverage — what we have, and what we don't

Audited 2026-08-26. Two re-runnable scripts answer the two different questions:

```bash
python scripts/audit_endpoints.py                      # spec vs code: is every CFBD endpoint covered?
python scripts/audit_coverage.py --data-dir data       # registry vs disk: is every expected file scraped?
```

`audit_endpoints.py` reads the live REST spec (`/api-docs.json`) and partitions all
74 paths into registered / in-client-but-unregistered / no-client-method, so the
74-73-1 breakdown below is generated rather than hand-counted. `audit_coverage.py`
is the source of truth for per-endpoint file counts. This note records the things
neither count can tell you — *why* something is absent.

## Every CFBD spec path is now registered but one

The live CFBD REST spec has **74 paths**. The `ENDPOINTS` registry has **73**, and
every one resolves to a real spec path. The single unregistered path is deliberate
(below).

Until 2026-08-28 the ceiling was the vendored client, not the registry: 10 paths had
no client method because `cfbd-python/` sat at `034cd17`, 11 commits behind upstream
`main`, and that is exactly where those endpoints landed. The client is now vendored
at `52f2bbf` and all 10 are registered:

| Spec path | Registry name | Mode |
|---|---|---|
| `/playoffs/cfp` | `cfp_playoff` | `season`, 2014+ |
| `/playoffs/cfp/games` | `cfp_games` | `season`, 2014+ |
| `/playoffs/cfp/participants` | `cfp_participants` | `season`, 2014+ |
| `/ratings/core` | `core_ratings` | `season` |
| `/ratings/srs/expanded` | `srs_expanded` | `season` |
| `/coaches/profile` | `coach_profile` | `on_demand` (needs `coach_id`) |
| `/coaches/seasons` | `coach_seasons` | `season` |
| `/coaches/tenures` | `coach_tenures` | `on_demand` (400s without `team`/`coach_id`) |
| `/conferences/affiliations` | `conference_affiliations` | `once` (full history, 3,604 rows) |
| `/conferences/changes` | `conference_changes` | `season` |

### Season floors are enforced, not discovered at runtime

`Endpoint.min_season` skips seasons before an endpoint existed. The CFP endpoints need
it: pre-2014 they **raise** rather than return `[]`, and one raised season aborts every
remaining season of that endpoint (`_run_endpoint` catches per endpoint, not per season).

Two more data floors, both real and both scraped as empty `[]` rather than errors:

- `core_ratings` — nothing before **2016** (2012-2015 return zero rows).
- `srs_expanded` — **2020 only** is empty upstream; 2012-2019 and 2021-2025 all have
  rows. 2019/2021 raise a pydantic `ValidationError` on a null `classification` and
  come back through the `_call_raw` fallback, so their files are complete.

### Not scraped — deliberate (1 path)

- `/info/usage` (`InfoApi.get_usage`) — reports API *account metering* (trailing
  request counts), not football data. Registering it would put billing telemetry
  into a JSONB staging layer meant for game data. Same category as `user_info`.

### Not scraped — deferred on cost (1 endpoint)

`player_season_overview` is `PER_PLAYER`: one call per roster row. The 2012-2025
rosters hold **276,782 players** ≈ **77 hours** at the 1s rate-limit delay. Not
started. See also the `gamePlayerStat` GraphQL pull, deferred for the same reason.

### Never bulk-scraped by design (4 endpoints)

`scoreboard`, `matchup`, `player_search`, `live_plays` are `ON_DEMAND` — live or
lookup-by-key endpoints with no meaningful bulk form. Registered so the runner
knows about them; skipped in bulk runs.

## Spec-level gaps: parameters, not endpoints

Audited 2026-08-28 against a downloaded copy of the OpenAPI document
(`cfbd-openapi (1).json`). It is **identical to the live spec** — same title and version
(College Football Data API 5.24.2), same 74 paths, GET-only, no path in one and not the
other. So there is no endpoint-level gap left to find; `scripts/audit_endpoints.py` already
partitions all 74. The gaps that remain are at the *parameter* level, and one of them is
serious.

### `seasonType` — closed for all 19 endpoints that accept it

Closed 2026-08-28 (quick task `260828-j8s`). `SeasonType` has **no default in the spec** —
omit it and CFBD returns `both`. Our code did not omit it: `--season-type` defaulted to
`regular` on `fetch` and `scrape`, a default **narrower than the API's own**, so nothing on
disk carried a postseason row for 2012–2024. The defaults are now `both`.

Probed before the change, and the two modes behave differently:

| 2024 | games | lines |
|---|---|---|
| `season_type=regular` | 3,747 | 1,523 |
| `season_type=postseason` | 54 | 50 |
| `season_type=both` | 3,801 | 1,573 |

SEASON mode is an exact superset. **SEASON_WEEK mode is not**: postseason week numbering
restarts at 1, so `both` with `week=1` returns regular week 1 *merged with* postseason
week 1 — `game_team_stats` 2024 wk1 gave regular=137, postseason=50, both=187, and the
`both` id set equals `regular | postseason` exactly. The filename
`{name}_{season}_wk{week}.json` has no season-type axis to hold them apart, so `both` there
would overwrite six correct endpoints with week-conflated content.
`_scrape_season_week` therefore runs **one pass per season type** rather than asking for
both at once — see the week-mode section below, closed the same day by `260828-l60`.

**Re-scraped with `both` (13, SEASON mode).** `games`, `lines`, `drives`, `media`,
`weather`, `elo`, `rankings`, `pregame_win_prob`, `ppa_games`, `advanced_game_stats`,
`game_havoc_stats`, `player_season_stats`, `player_success_season`. The first eight are
exactly the `seasonType`-accepting files `enrich.py` reads. Result: **+501 games** into
`games.csv` (13,014 → 13,515) and postseason rows in every endpoint — 751 games, 586 lines,
936 media, 639 weather, 1,178 advanced-stat, 1,100 PPA, 922 havoc, 14,804 drives.

**Also closed, via a second pass (6, SEASON_WEEK mode).** `plays`, `play_stats`,
`ppa_players_games`, `game_player_stats`, `game_team_stats`, `player_success_game`
(quick task `260828-l60`). `_scrape_season_week` runs one pass per season type: regular
keeps `{name}_{season}_wk{week}.json`, postseason writes
`{name}_{season}_post_wk{week}.json`. `--season-type` is meaningful for them again and
symmetric — `regular` runs only regular, `postseason` only postseason, `both` runs both.
Pulled 2012–2025: 100 files, 153,164 rows (plays 106,543; play_stats 29,120;
ppa_players_games 10,358; player_success_game 5,961; game_player_stats 592;
game_team_stats 590).

**The postseason week list is data, not a range.** Postseason is week 1 in most seasons,
but 2020 also has week 20, 2023 has weeks 11–15, and 2025 has weeks 13–14 — the
Division II/III playoff rounds that begin in mid-November. `_postseason_weeks` reads them
off the `games_{season}.json` seed, so the scraper cannot miss a week nobody thought to
look for. A hardcoded `week=1` would have silently dropped 32 games in 2025 alone.

Verified by disjointness, not by counts: for every `(endpoint, season, week)` the row sets
in `_wk{w}.json` and `_post_wk{w}.json` share nothing (whole-row identity, not an id
field), and for `game_team_stats` 2024 wk1 their union equals the live
`season_type="both"` result exactly — 137 + 50 = 187 ids.

`scripts/audit_coverage.py` now expects the postseason files too, derived from the same
seed. Without that a missing postseason pull would be invisible, which is the blindness
that hid the original `seasonType` gap. It reports five expected-but-absent files per
endpoint — `(2020, 20)`, `(2023, 11)`, `(2023, 12)`, `(2025, 13)`, `(2025, 14)` — and all
five are **upstream empties, not misses**: the schedule lists those lower-division playoff
rounds but CFBD returns zero rows for them, while the neighbouring `(2023, 13)` returns 8
team-stat rows and 1,120 plays. Same floor-not-failure shape as the empty `[]` payloads
below.

#### What the re-scrape verified, and what it exposed

Row counts cannot verify this. The check was per endpoint per season: the count of
`seasonType == "regular"` rows must be **unchanged**, and postseason rows must be present.
Nine endpoints carry `seasonType` per row and passed. Three came back short — 
`game_havoc_stats` (−8 across 2021–2023), `advanced_game_stats` (−2 in 2024) and `drives`
(−9, but **+1** in 2024). Re-asking the API `regular` on the spot returned the *new* lower
count, and `both`'s regular subset matched it id-for-id, so this is **upstream reprocessing
between scrapes, not loss caused by `both`**. A `both` bug cannot add a regular row.

Two things the baseline itself got wrong, both worth remembering:

- **2025 `games`/`lines` already held postseason** (86 and 50 rows) before this change, so
  "every dump is regular only" was true for 2012–2024, not 2025. A verification that
  compares a regular count against a file *total* silently fails on that season.
- `elo`, `player_season_stats` and `player_success_season` carry no per-row season type,
  and they are **season aggregates**: with `both` their existing rows *change meaning*
  (totals now include bowls) rather than merely gaining rows (+20,772 player-season rows).
  None feeds `enrich`, so no lookahead enters the feature registry, but any future feature
  reading them same-season must lag to S−1 the way `_index_prior_player_agg` does.

#### No lookahead entered the features

Bowls are terminal within a season, so `enrich` should leave every pre-existing
regular-season game untouched. 381 of 13,014 moved. All of it attributes to upstream churn
in the re-scraped files — `raw_weather` (470 values), `raw_conferences` (306), `raw_havoc`
(230), `raw_teams` (152), `raw_pregame_wp` (47), `raw_lines` (12).

246 of those drift on a source kind whose own file was *not* re-scraped
(`raw_teams`, `raw_conferences`, `raw_team_season`, `raw_prior_team_season`). Every one of
the 246 turns out to have a team-name or conference rename in `games.csv`: `games` was
re-scraped, upstream renamed teams and conferences, and the rename changes the lookup key
into those unchanged files. Indirect, but still upstream churn — 246/246, no unexplained
remainder.

The decisive field is `running_games_played`, which can only change if a game **entered**
some prior-game window. It moved **nowhere**, and neither did `running_win_pct`,
`running_ats_pct`, `running_streak` or `running_ats_streak`. The 510 `computed_running`
values that did move are only the `ppa_*`/`success_*`/`explosiveness_*` families — the ones
averaged from `ppa_games` and `advanced_game_stats`, whose per-game inputs drifted upstream.

One latent hazard found while checking this. `running_stats.compute_running_stats` sorts a
team's season by `startDate` and falls back to `f"{season}-w{week:02d}"` when a game has no
date. Postseason weeks restart at 1, so a dated-less bowl would sort to the **front** of the
season and contaminate every regular game after it. Today **0 postseason games lack a
`startDate`**, so the vector is dormant — but it is one missing field away from live.
Separately, 34 team-seasons do have a postseason game genuinely earlier in wall-clock time
than a later regular game (Division II/III playoffs begin in mid-November). Using those is
chronologically correct, not lookahead.

### Parameters we skip on purpose

Most unused query parameters are **narrowing filters** — `team`, `conference`, `opponent`,
`position`, `startWeek`/`endWeek`, `minYear`/`maxYear`. A bulk dump wants the unfiltered
result, so not passing them is correct; passing them would only fragment the files.

`classification` (`fbs`, `fcs`, `ii`, `ii/iii`, `iii`) also has no default, so our dumps
already span every division — `games_2024.json` carries all 3,747 games, not just the ~800
FBS ones.

Three groups are genuinely *unused options* rather than gaps, because they ask the API for a
different computation rather than for more rows:

- `excludeGarbageTime` (9 endpoints) and `threshold` (4) — analytic variants of the same
  rows. Registering a garbage-time-excluded variant would be a second feature source, not a
  fix.
- `final` / `latest` / `poll` on `rankings` — views over rows we already pull in full.
- `competition` / `round` on `games` and `cfp_games` — CFP slicing, already covered by the
  dedicated `cfp_*` endpoints.

## Empty files are floors, not failures

31 `[]` payloads sit in `data/raw/`. Every one is a **contiguous run starting at
2012**, which is the signature of a real data-availability floor rather than a
silent error:

| Endpoint | Empty seasons |
|---|---|
| `transfer_portal` | 2012-2020 |
| `teams_ats` | 2012-2018 |
| `kicker_paar` | 2012-2015 |
| `talent` | 2012-2014 |
| `returning_production` | 2012-2013 |
| `adjusted_player_passing`, `adjusted_player_rushing`, `player_usage`, `ppa_players_season`, `player_success_season`, `pregame_win_prob` | 2012 |
| `win_probability` (PER_GAME) | 2012-2013 |

`ppa_players_games` and `player_success_game` are each missing all 15 weeks of
2012 for the same reason (no file is written for an empty week), so their
complete counts are 195, not 210.

This matters for automation: a "wait until N files exist" gate can never be
satisfied for a `SEASON_WEEK` endpoint with an empty season. Gate on the scrape
process finishing, or on no new file appearing, rather than a target count.

`advanced_box_score` has **no** such floor — 2012 and 2013 return full team and
player content, so both seasons are scraped. Do not assume one PER_GAME
endpoint's floor applies to another; check each.

One 2012 game (`322872655`) returns a **persistent HTTP 500** upstream: three
retries with 5/10/20s backoff still fail. Such games are skipped and counted
rather than aborting the season (see `_scrape_per_game`). Expect per-game
coverage to be a game or two short of the seed count in some seasons; the count
is printed at the end of the run.

### PER_GAME final coverage (2026-08-26)

Both FBS-only per-game endpoints are complete:

| Endpoint | Games | Seeded | Missing |
|---|---|---|---|
| `advanced_box_score` (2012-2025) | 11,484 | 11,556 | 72 (0.6%) |
| `win_probability` (2014-2025) | 9,740 | 9,938 | 198 (2.0%) |

The 72 `advanced_box_score` gaps are games that return a **permanent upstream
500** after retries; they are skipped and counted rather than aborting the
season. Before that fix, one dead game meant its whole season produced *nothing*
-- 2012 has 15 such games and wrote zero rows.

The 198 `win_probability` gaps are different: those games return **0 rows**, i.e.
CFBD has no win-probability data for them. Verified by re-querying a random
sample of 12 missing 2025 games -- all 12 came back empty, none had data. 2025
accounts for 131 of the 198, spread across many weeks (not clustered), and is
not explained by FBS-vs-FCS classification (98 of the 131 are FBS-vs-FBS).

Note `advanced_box_score` rows carry **no game id** -- `gameInfo` has team names
and scores but no `gameId`. Coverage for that endpoint must be measured by row
count (one row per game call), not by distinct id.

**Network failures are retried** (as of `fe4832b`). `_call` originally matched
only `"429"` and 5xx codes in `str(exc)`, so a DNS blip raised immediately and
discarded the in-progress season — this cost `win_probability` 2025 on
2026-08-26, with the host resolving normally minutes later. Network errors are
now matched by *type* (`urllib3.exceptions.HTTPError`, the common base for
`MaxRetryError` / `NameResolutionError` / `ProtocolError` / timeouts) and get a
longer 15/30s backoff than HTTP's 5/10/20s.

`win_probability` is worth calling out separately: it returns **zero rows for
every 2012 and 2013 game**, so those seasons write no file. Because PER_GAME
fans out per game, the scraper still spends ~1,600 calls (~50 min) discovering
that before it reaches real data in 2014. Seeding a floor year per PER_GAME
endpoint would skip that, but the current runner has no such notion.

Do **not** `--force` these. Scattered gaps would be suspicious; leading runs are
the upstream floor. Betting lines floor at 2013 independently.

## GraphQL

`scripts/audit_endpoints.py` audits GraphQL the same way it audits REST: the
universe is the **live introspected schema**, not the hand-kept list. Live today:
38 root fields carry scalar columns, one (`athleteByPk`) is a Hasura per-key
wrapper, leaving **37 real tables**. The script prints what the wrapper filter
dropped, so a schema shape change surfaces as a diff rather than a quietly
different denominator.

The partition closes at **35 in the default pull + 2 documented exclusions = 37**,
with every defaulted table on disk. `GQL_DEFAULT_TABLES` grew 24 → 35 on
2026-08-28: eleven small lookup tables (`draftPosition`, `draftTeam`, `hometown`,
`linesProvider`, `playerStatCategory`, `playerStatType`, `pollType`, `position`,
`recruitPosition`, `recruitSchool`, `weatherCondition`) were on disk but reachable
only via `--tables`, so a fresh pull would have missed them.

The two exclusions live in `GQL_EXCLUDED` beside the default list, each with its
reason, and the audit reads both rather than keeping its own copy:

| Table | Why not in the default pull |
|---|---|
| `gamePlayerStat` | ~6.7M rows, multi-GB; pulled per season with `--tables`/`--season` (2012-2025 shards are on disk) |
| `scoreboard` | live in-progress games, no historical value |

### The sort key must be a total order

`orderBy` on a single non-unique column is worse than useless. 20 of the 35 defaulted
tables have no `id`, so the first scalar became the sort key — `gameTeam` by `endElo`,
`coachSeason` by `games`, `pollRank` by `firstPlaceVotes`. Ties then break differently per
request and rows fall between page boundaries.

That produced a real loss: after the first `gameTeam` refresh, `pregame_win_prob` fell from
12,811 non-null games to 12,656 even though the file **gained** 5,576 rows. Game
`332500030` had lost its `away` row while some other row was duplicated. A row-count check
cannot see this — the count was right, the rows were not.

Tables with no `id` now sort on **every scalar column**, which leaves ties only between
byte-identical rows. Re-pulled `gameTeam`: 225,344 rows, 225,344 unique `(gameId, side)`
pairs, zero duplicates, and `pregame_win_prob` back to 12,812 non-null.

### Relation-keyed tables select their join key

`_paginate` selects scalar columns and skips relations, which for a few tables dropped the
identity entirely. `GQL_RELATION_KEYS` names, per table, the relation and the handful of
columns to lift from it — enough to join, not the whole related row. Those columns are put
in the **selection and the sort**: a table like `pollRank` has only `rank`, `points` and
`firstPlaceVotes` as scalars, so without the relation key it also paginates on heavy ties.
Dotted paths nest (`pollType.name` selects `pollType { name }` and orders as
`{poll: {pollType: {name: ASC}}}`, since Hasura orders through relations).

`pollRank` now carries `poll` (season, seasonType, week, pollType.name) and `team` (school,
conference, classification) — 49,948 rows, joinable, and stable: the same multiset comes
back at page sizes 1,000 and 5,000. 152 rows are byte-identical duplicates **upstream**
(e.g. two FCS Coaches Poll 2022 wk 6 rows), not a pagination artifact — the page-size
invariance is what separates the two. 291 rows have `team: null`: the relation points at
`currentTeams`, and 1930s-era programs aren't in it.

`gameMedia` **cannot** be fixed this way and moved to `GQL_EXCLUDED`. Its type has exactly
two fields, `mediaType` and `name`; the link is one-directional (`game.mediaInfo`), so there
is no join key on that root to select. The REST `media_{season}.json` files carry `gameId`
and are what `enrich` reads, so nothing is lost.

### Row counts, not just file existence

20 of the 35 defaulted tables expose `{table}Aggregate { aggregate { count } }`, so the
audit compares each dump's row count to the source's own total. Counting does **not** parse
the files (`game.json` is 103 MB) — `_write` dumps with `indent=2`, so every top-level row
starts on a line that is exactly `  {`. Drift is reported but never fails the run: a stale
dump is a re-pull decision, not a wiring bug. The other 15 tables (`gameTeam`, `poll`,
`ratings`, `transfer`, …) have no aggregate variant and stay file-existence only, which the
output states rather than implying they were checked.

When this check first ran (2026-08-28) **14** tables trailed the source, several badly —
`recruit` 50,820 vs 93,363, `coachSeason` 1,937 vs 12,564, `athlete` 151,049 vs 158,932.
All 14 were re-pulled the same day (+64,855 rows net) and **every checkable table now matches
its source count**. Two of the 14 had *more* rows on disk than the source (`athleteTeam`
+311, `game` +1); those resolved to exact matches on re-pull, which is what stale or
duplicated rows from the pre-`orderBy` unsorted pulls look like.

Re-running `enrich` after the refresh changed **zero** features on all 13,014 games: the only
GraphQL-sourced registry feature is `pregame_win_prob` (from `gameTeam`, which has no
aggregate variant and was not part of the refresh), and the added `game`/`gameLines` rows
fall outside the built game set.

The GraphQL half needs a Patreon Tier 3 token. Not having one prints a note and is
never a failure — the REST partition runs offline from a saved spec and is not held
hostage to a paid tier. Only a table that is reached but is neither defaulted nor
documented exits non-zero.

Reach a non-default table with:

```bash
python -m cfb_system_maker graphql --data-dir data --tables hometown recruitSchool
```

## 2026 season

The 2026 season has **3,677 games scheduled and 0 completed** (opens 2026-08-27).
Its absence from `data/raw/` is correct, not a gap. Once games complete, note that
a partially-played season interacts with the no-lookahead rule in `running_stats.py`
— entering-game features are fine, season aggregates are not.

## Caveat on per-game resume

`PER_GAME` endpoints write one file per season, only *after* every game in that
season finishes. Resume is per-season, so interrupting mid-season discards that
season's calls.

Budget from the measured `_call` path, not from `--delay` alone. Three estimates,
each measured a different way, and only the last is trustworthy:

| Method | Per call | 2 endpoints x 11,556 games |
|---|---|---|
| `calls x --delay` (naive) | 1.0s | ~3.2h |
| bare API call, warm connection | 0.16s + 1s sleep | ~3.7h |
| `_call` sampled across a full season | **~2.3s** | **~7.5h** |

The naive estimate is roughly 2x optimistic. A bare call benchmarked at the front
of a season reuses one warm HTTP connection and hits the smallest payloads;
sampling across the whole season (games 0/200/400/600/800) gives ~2.3s/call, so
**~30 min per season per endpoint**. Note that measuring while a scrape is
already running inflates both, since the probes share the rate limiter.

Practical consequence: `advanced_box_score` alone is ~3.7h for 2012-2025, and the
runner finishes all 14 of its seasons before `win_probability` starts.
