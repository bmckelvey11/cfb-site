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
| `lines_*.json`, 15 seasons 2012-2026 | 13,751 | **50** (2025 only) |

Neither audit script can see this. `audit_endpoints.py` partitions spec paths and
`audit_coverage.py` counts files; both are blind to what is *inside* a file, so a run that
reports full coverage is still reporting on a regular-season-only corpus. The count above
is the check — re-run it, not the audits.

2025 is the exception because `upcoming.py` — not `scrape` — last wrote those two files.
`refresh_upcoming` calls `get_games`/`get_lines` with `season_type="both"` and then
`save_raw_json`s the **full season** over both dumps (`upcoming.py:94-95`). So the only
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
`games.csv` already holds 46 of them (2025), so **469 are missing** — ≈3.5% of the
13,483-row sample the build would otherwise produce. Mind the two filters: `games.csv`
carries 50 postseason rows, not 46, because it is line-gated rather than FBS-gated and
picks up 4 lower-division bowls; 515/469 are the FBS-filtered counts.

3.5% is small, but it is not a random 3.5%. Bowls and CFP games are a distinct population
— three-to-six week layoffs, opt-outs and portal departures, neutral sites, coaching
changes, and motivation asymmetry the market prices and simple systems do not. Every
system in this repo that claims a general edge has never been tested on the games where
naive systems most often break, and no result here should be described as covering the
full season.

Other analyses that silently inherit the gap:

| Reader | What it misses |
|---|---|
| `cli.py:86` `build` → `normalize` → `games.csv` | the 469 games above; downstream `enrich`, `backtest`, `web`, `/compare`, saved systems, `v1_model` refit |
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

`threshold` (4 endpoints — the player PPA and success-rate pairs) is a minimum-sample cut:
"minimum number of plays" / "minimum credited passing and rushing plays". It drops
low-volume player rows and leaves the survivors' numbers alone, so it is a narrowing filter
like the rest — any minimum-plays rule is a client-side `if plays >= n` over the unfiltered
dump, and applying it at the API would mean re-scraping to change the cutoff.

Two groups are genuinely *unused options*, because they ask the API for a different view of
rows we already hold in full:

- `final` / `latest` / `poll` on `rankings` — views over rows we already pull in full.
- `competition` / `round` on `games` and `cfp_games` — CFP slicing, already covered by the
  dedicated `cfp_*` endpoints.

### `excludeGarbageTime` — closed 2026-08-28 as a parallel `_ngt` source

Closed by quick task `260828-lvd`. This one is **not** a narrowing filter and not a view: it
drops the blowout plays that feed the aggregation, so the numbers on the surviving rows
change. Our dumps store the aggregates and not the plays behind them, so it cannot be
reproduced client-side — the only way to have it is to ask CFBD for it.

Registered as nine `_ngt` ("no garbage time") variants rather than a flag on the existing
entries. `Endpoint.name` is the output file prefix, so each variant lands beside its
unfiltered twin — `ppa_games_ngt_2024.json`, `..._ngt_{season}_wk{w}.json`,
`..._ngt_{season}_post_wk{w}.json` — and never overwrites it. They are a **second source,
not a correction of the first**; `enrich.py` reads neither, so no registry feature moved.

Probed 2024 before registering any of them, because a no-op param would write identical
content that `resume` then protects until someone thinks to `--force`. The probe omitted
`seasonType`, so both sides of every pair are `both` — the numbers below will not match a
naive diff against an on-disk file for an endpoint that was never re-scraped with `both`
(`player_usage_2024.json` holds 4,129 regular-season rows, not the 4,131 here). All nine
are real, and they split into two behaviours:

| Endpoint | rows (unfiltered → ngt) | rows differing |
|---|---|---|
| `ppa_games` | 1,711 → 1,711 | 689 |
| `ppa_teams` | 134 → 134 | 134 |
| `advanced_game_stats` | 3,212 → 3,212 | 1,186 |
| `advanced_season_stats` | 134 → 134 | 134 |
| `ppa_players_season` | 4,131 → 3,696 | — |
| `ppa_players_games` (wk1) | 3,250 → 2,887 | — |
| `player_usage` | 4,131 → 3,696 | — |
| `player_success_season` | 3,752 → 3,309 | — |
| `player_success_game` (wk1) | 2,090 → 1,801 | — |

Game- and team-level endpoints keep every row and move values. **Player-level endpoints also
drop rows**: a player whose only snaps came in garbage time has no qualifying plays left, so
the row disappears entirely. Any join against an `_ngt` player file must expect a smaller
population than its twin, not just different numbers.

`player_usage` and `ppa_players_season` agreeing to the row (4,131 → 3,696 both times, and
41,892 rows each across 2012-2025) is a **property, not a copy-paste bug** — they are
separate methods on separate APIs (`PlayersApi.get_player_usage`,
`MetricsApi.get_predicted_points_added_by_player_season`) whose payloads differ (`usage` vs
`averagePPA`/`totalPPA`); they simply share CFBD's qualifying-player universe, so the same
players qualify and the same players drop.

Pulled 2012-2025: **520 files, 543,288 rows**, 0 endpoints failed.

#### Verified by margin, not by row count

Row counts cannot check this — for four of the nine the rows are the same rows. The check
that falsifies is that garbage time can only have been excluded from games where it
occurred, so on `ppa_games` 2024 the change must track final margin:

| Final margin | rows changed | share |
|---|---|---|
| 0-7 | 54 / 569 | 9.5% |
| 8-16 | 35 / 384 | 9.1% |
| 17-27 | 233 / 389 | 59.9% |
| 28+ | 367 / 369 | 99.5% |

The 40 biggest blowouts all differ; 228 of 262 one-score games are byte-identical. A flat
rate in either direction — everything changed, or nothing — would have meant the flag was
not doing what its name says. The ~9% floor in close games is consistent with a game that
was a blowout earlier and finished within a score, since the rule reads in-game state rather
than the final margin — but that mechanism was **not** probed, only the gradient was.

For the two SEASON_WEEK variants the `_ngt` shard set is the **same 211 `(season, week)`
tuples** as its unfiltered twin, so `audit_coverage.py` reporting 211/232 is the documented
2012-and-postseason floor those endpoints already have, not something the flag emptied.

#### The trap this exposed

`_scrape_season_week` never applied `endpoint.fixed`, unlike `_scrape_season`. Two of the
nine are SEASON_WEEK, so the call would have gone out with no flag and written unfiltered
rows under the `_ngt` name — right row count, wrong content, and `resume` protecting the bad
file on every later run. No registry entry used `fixed=` before this change, so the fix is
inert for existing data. `tests/test_scrapers.py::test_season_week_applies_endpoint_fixed_kwargs`
pins it.

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
