# CFBD data coverage — what we have, and what we don't

Audited 2026-08-26. Re-check any time with:

```bash
python scripts/audit_coverage.py --data-dir data
```

That script is the source of truth for per-endpoint file counts; this note
records the things a file count can't tell you — *why* something is absent.

## The ceiling is the vendored client, not the registry

The live CFBD REST spec has **74 paths**. The `ENDPOINTS` registry has **63**,
and every one resolves to a real spec path. The gap is not an oversight in the
registry — it's that `cfbd-python/` (vendored at `034cd17`) has no client method
for those paths. The clone is **11 commits behind upstream `main`**, and that is
exactly where the missing endpoints landed.

### Not scraped — blocked on a client bump (10 paths)

| Spec path | What it is |
|---|---|
| `/playoffs/cfp` | CFP bracket |
| `/playoffs/cfp/games` | CFP games |
| `/playoffs/cfp/participants` | CFP participants |
| `/ratings/core` | core ratings rollout |
| `/ratings/srs/expanded` | SRS expanded to FCS |
| `/coaches/profile` | coach profile |
| `/coaches/seasons` | coach seasons |
| `/coaches/tenures` | coach tenures |
| `/conferences/affiliations` | team↔conference affiliations |
| `/conferences/changes` | realignment history |

To unblock: bump `cfbd-python` to upstream `main`, re-run the spec diff, register
what the new client exposes. The bump has its own regression surface (the vendored
client is pydantic v1 and is loaded by path injection), so it is a deliberate
separate change, not a drive-by.

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

`win_probability` is worth calling out separately: it returns **zero rows for
every 2012 and 2013 game**, so those seasons write no file. Because PER_GAME
fans out per game, the scraper still spends ~1,600 calls (~50 min) discovering
that before it reaches real data in 2014. Seeding a floor year per PER_GAME
endpoint would skip that, but the current runner has no such notion.

Do **not** `--force` these. Scattered gaps would be suspicious; leading runs are
the upstream floor. Betting lines floor at 2013 independently.

## GraphQL

`GQL_DEFAULT_TABLES` lists 24 tables. Introspection finds **37** real data tables
(excluding `*Aggregate` / `*ByPk` wrappers). Nine small lookup tables were
outside the default list *and* unreachable from the CLI until `--tables` was
added; they are now pulled: `draftPosition`, `draftTeam`, `hometown`,
`playerStatCategory`, `playerStatType`, `pollType`, `position`,
`recruitPosition`, `recruitSchool`.

Still not pulled: `scoreboard` (live endpoint, no historical value) and
`gamePlayerStat` beyond the partial 2012-2016/2023 files already on disk
(~6.7M rows, multi-GB — deferred).

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
