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

## Season type — `data/raw/` is regular-season only, and 2025 is the inconsistent one

Audited 2026-08-28. Every `scrape` and `fetch` run to date used the default
`--season-type regular`, so **every bowl, conference championship and CFP game is
absent from `data/raw/`** for seasons 1992-2024. Count it from disk:

```bash
python -c "import json,collections; [print(y, collections.Counter(x.get('seasonType') for x in json.load(open(f'data/raw/games_{y}.json',encoding='utf-8')))) for y in (2003,2019,2024,2025)]"
```

| File family | `regular` | `postseason` |
|---|---|---|
| `games_*.json`, 35 seasons 1992-2026 | 52,982 | **86** (2025 only) |
| `lines_*.json`, 15 seasons 2012-2026 | all | **50** (2025 only) |

2025 is the exception because `upcoming.py` — not `scrape` — last wrote those two files.
`refresh_upcoming` calls `get_games`/`get_lines` with `season_type="both"` and then
`save_raw_json`s the **full season** over both dumps (`upcoming.py:93-94`). So the only
postseason data in `data/raw/` arrived as a side effect of the current-week refresh, and
only for the season that refresh was pointed at.

### The live bug is the week collision, not the missing bowls

CFBD numbers postseason weeks from 1, and neither `GameRecord` nor `games.csv` carries a
season type — `normalize.py:30` copies `week` straight through. So in `games.csv`:

```
2025 week 1 = 177 rows  =  127 regular-season openers  +  50 bowls/CFP games
```

2013-2024 exclude postseason uniformly, which is at least a statable sample definition.
2025 breaks that uniformity, and it is the **holdout season** — so `--week 1`, any
week-derived feature, and any "early season" system mean something different in the
holdout than in the training seasons, with nothing declaring it.

`running_stats.py` survives this by luck, not by design: it sorts on raw `startDate` and
only falls back to `f"{season}-w{week:02d}"` when the date is missing
(`running_stats.py:29`). The dates are present, so all 50 bowls come out with
`running_games_played` of 10-15, which is correct. Had the fallback fired, week-1 bowls
would have sorted ahead of every regular-season game and entered with `games_played=0`.

Restoring uniformity is one filter (drop 2025's postseason ids at build time). Carrying
postseason properly is a `season_type` column on `GameRecord`, which is a deliberate
`storage.py` migration, not an ad hoc column add.

### 19 endpoints are season-type-scoped, not just `games`

`games` and `lines` are the visible half. Static-parsing `ENDPOINTS` against the vendored
client shows 19 of the 73 registered endpoints accept `season_type`, and every one of them
is on disk as regular-only:

`advanced_game_stats`, `drives`, `elo`, `game_havoc_stats`, `game_player_stats`,
`game_team_stats`, `games`, `lines`, `media`, `play_stats`, `player_season_stats`,
`player_success_game`, `player_success_season`, `plays`, `ppa_games`, `ppa_players_games`,
`pregame_win_prob`, `rankings`, `weather`.

`PER_GAME` endpoints inherit the gap a second way: `_seed_game_ids` reads
`games_{season}.json` (`scrapers.py:441`), so `advanced_box_score` and `win_probability`
were never called for a bowl either. Their coverage tables above are complete *against a
regular-season seed*.

### Source of record: `stg.game`, not a postseason pass

Use the GraphQL-fed DuckDB tables for anything that needs full-season coverage.
`stg.game` carries 112,673 rows with real postseason back to 1901; `stg.games` (the REST
dump, note the plural) carries 53,068 and inherits the gap exactly. Two apparent anomalies
in `stg.game` are real season types, not mislabels — checked on dates and classifications:

- 2020's 562 non-regular rows are `spring_regular`/`spring_postseason` — the COVID-shifted
  spring 2021 FCS/DII/DIII season, played Feb-May 2021. True 2020 `postseason` is 30.
- 2023's 139 postseason rows span all divisions (FBS 42, DIII 43, DII 29, FCS 25). Filter
  on `homeClassification`/`awayClassification` or the counts look erratic across seasons.

`scripts/build_prediction_tracker.py` already reads `stg.game` for this reason and is
correct as written.

**Do not "add a postseason pass" to `scrapers.py`.** `_scrape_season` writes
`{name}_{season}.json` with no season-type dimension, so a second pass has nowhere to go:
resume skips the existing file, and `--force` **overwrites the regular-season rows with
postseason-only rows**. `SeasonType` accepts `both` (`cfbd/models/season_type.py`), which
is what `upcoming.py` already uses, so the correct shape is a re-scrape of the 19 endpoints
above with `--season-type both --force` — one superset file per season, no schema change.
Untested and worth probing first: whether `both` behaves on the `SEASON_WEEK` endpoints,
where `weeks=range(1,16)` meets a postseason week numbering that restarts at 1.

### Does it matter for backtests

2013-2025 has **515 FBS postseason games, and `stg.gameLines` has a line for all 515.**
50 of them (2025) are already in `games.csv`; the other 465 are missing, ≈3.4% of the
13,479-row sample the build would otherwise produce.

3.4% is small, but it is not a random 3.4%. Bowls and CFP games are a distinct population
— three-to-six week layoffs, opt-outs and portal departures, neutral sites, coaching
changes, and motivation asymmetry the market prices and simple systems do not. Every
system in this repo that claims a general edge has never been tested on the games where
naive systems most often break, and no result here should be described as covering the
full season.

Other analyses that silently inherit the gap:

| Reader | What it misses |
|---|---|
| `cli.py:86` `build` → `normalize` → `games.csv` | the 465 games above; downstream `enrich`, `backtest`, `web`, `/compare`, saved systems, `v1_model` refit |
| `enrich.py:112` raw-game index | postseason rows never indexed for 2013-2024 |
| `betlog.py:237` | reads year and year-1 season files precisely to catch January bowls — the comment is right, but the bowls are not in those files, so bowl bets land in `unmatched` rather than erroring |
| `clv.py:96` (`lines_*`) | no closing-line value on any bowl |
| `duckdb_load.py` → `raw.games`/`stg.games` | the REST-side game table is regular-only while `stg.game` beside it is not |
| `scripts/analyze_coach_styles.py:231` | style clusters fit on regular-season games only |
| `scrapers.py:441` per-game seed | per-game stats for bowls never requested |

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
