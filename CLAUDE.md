# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
## What this is

`cfb_system_maker` is a Python CLI + Flask tool for backtesting college football betting systems. It fetches historical games and betting lines from the CollegeFootballData API, normalizes them into one joined table, applies filter-based "systems," and reports betting performance (hit rate, profit, ROI).

`cfbd-python/` is the **vendored upstream CFBD OpenAPI client** (a git clone of `github.com/CFBD/cfbd-python`, pydantic v1). It is a dependency, not our code — do not edit it or treat its style as the project's. It is loaded at runtime by path injection (`cfbd_client.py:_load_cfbd_module`), not pip-installed.

## Commands

```powershell
# Tests (pytest.ini sets testpaths=tests; runs only our tests, not cfbd-python's)
python -m pytest
python -m pytest tests/test_backtest.py            # single file
python -m pytest tests/test_backtest.py::test_name  # single test

# CLI (also runnable as `python -m cfb_system_maker <command>`)
python -m cfb_system_maker sample --data-dir data        # write+backtest bundled sample data, no network
python -m cfb_system_maker fetch --season 2023 --provider consensus --data-dir data
python -m cfb_system_maker scrape --season 2023 2024 --data-dir data   # pull ALL CFBD REST endpoints to data/raw/
python -m cfb_system_maker scrape --season 2023 --only games lines sp   # subset by endpoint name
python -m cfb_system_maker scrape --season 2023 --include-per-game --fbs-only   # per-game endpoints, FBS only
python -m cfb_system_maker graphql --season 2023 --data-dir data   # bulk-pull GraphQL tables to data/graphql/ (Tier 3)
python -m cfb_system_maker build --season 2023 --provider consensus --data-dir data
python -m cfb_system_maker enrich --data-dir data   # join registry features -> data/processed/features.json (run after build)
python -m cfb_system_maker backtest --data-dir data --side home --favorite --min-spread -14
python -m cfb_system_maker web --data-dir data --port 5000   # Flask UI at 127.0.0.1:5000
```

There is no build step and no linter configured for our code. Dependencies: `pip install -r requirements.txt` (pulls cfbd-python's requirements + Flask + pytest).

## Pipeline & architecture

Data flows through three stages, each a separate CLI command, persisted to disk between stages:

1. **fetch** → `cfbd_client.fetch_games_and_lines` calls `GamesApi.get_games` + `BettingApi.get_lines`, dumps each model `.dict(by_alias=True)`, writes `data/raw/{games,lines}_{season}.json` (`storage.save_raw_json`).
2. **build** → `normalize.normalize_games` joins games to lines by game id, picks one line per game (`_select_line`: preferred provider, else first usable), emits frozen `GameRecord`s → `data/processed/games.csv` (`storage.save_processed_games`).
3. **backtest** → `backtest.run_backtest` filters records with `matches_system`, grades each with `grade_bet`, aggregates into `BacktestResult`.

`web.py` (`create_app`) skips fetch/build — it loads the already-built `games.csv` and runs `run_backtest` per request from query-string form values. Build the data first or the index template renders an `error="missing_data"` state.

`scrapers.py` is a parallel, broader fetch path: a registry (`ENDPOINTS`, 63 entries) covering every CFBD REST endpoint **the vendored client exposes**, driven by one runner (`scrape`). The live CFBD spec has 74 paths; 10 of them (CFP, core ratings, expanded SRS, coach profile/seasons/tenures, conference affiliations/changes) need a `cfbd-python` bump before they can be registered, and `/info/usage` is account metering, deliberately unregistered. Re-check coverage any time with `python scripts/audit_coverage.py`; `docs/data-coverage.md` records *why* each absent endpoint is absent (client-blocked, deliberate, deferred on cost) and why the empty `[]` files are data floors rather than failures. It writes raw JSON to `data/raw/` only — it does not feed `build`/`backtest` (which still use `fetch`'s `games`/`lines` files). Intended as the load source for a future Postgres `JSONB` staging layer.

`graphql_client.py` is a **third** fetch path over the CFBD GraphQL (Hasura) API (`graphql_scrape`, CLI `graphql`) — **Patreon Tier 3 only**. It introspects the schema once, then for each root table in `GQL_DEFAULT_TABLES` auto-selects scalar columns (skips relations), picks a sort key (`id` else first scalar), and paginates with `limit`/`offset` — collapsing per-row REST fan-out into a few bulk queries. Writes to `data/graphql/{table}.json` (separate from `data/raw/` because GraphQL row shapes differ from REST). Key details: root fields advertise their own args via introspection, so tables lacking `limit`/`offset` (non-paginated views like `conference`) are fetched in one shot, and `where:{season:{_in:[…]}}` is only added when the table has a season/year column **and** a `where` arg; the HTTP poster must send a non-default `User-Agent` (Cloudflare 403s urllib's default); `post_fn` is injectable for network-free tests.

### Scraper conventions (`scrapers.py`)

- **One `Endpoint` per CFBD method, tagged with a *mode*** that says how it's parameterized: `once` (no params, `{name}.json`), `season` (loop years, `{name}_{season}.json`), `season_week` (year×week, plays), `grid` (predicted-points down×distance), `per_game`/`per_player` (fan out over ids from already-scraped `games_*`/`roster_*` seeds), `on_demand` (live/key-lookup endpoints — scoreboard, matchup, search_players, live_plays — registered but skipped in bulk).
- **`per_game`/`per_player` are opt-in** (`--include-per-game`/`--include-per-player`) because they issue one call per game/player (thousands). Seasons missing their seed file are skipped, not errored.
- **Resume by default** — an endpoint/season/week whose output file already exists is skipped (counted in `ScrapeReport.skipped`); `--force` re-scrapes. `SEASON_WEEK` empty weeks write no file, so they're re-probed each run. Several `*_game`/`ppa_players_*`/`play_stats` endpoints are `season_week` (CFBD 400s without a `week`/`team`).
- **Rate-limit safe** — `_call` sleeps `--delay` (default 1s) between calls and retries 429s with exponential backoff (5/10/20s). Model `ValidationError`s fall back to `_call_raw` (the `*_with_http_info` variant with `_preload_content=False`), bypassing pydantic for malformed rows (e.g. `recruiting_groups`).
- **Args are filtered by signature** (`_accepted` + `inspect.signature`): the generated client *rejects* unexpected kwargs, so `season_type` is only passed to methods that accept it, and the `id` vs `game_id` param-name difference resolves automatically. Don't hardcode per-endpoint kwarg lists.
- **One failing endpoint never aborts the run** — `_run_endpoint` captures any exception into `ScrapeReport.error` (covers Patreon-gated `weather`, rate limits, auth tiers) and continues.
- The runner takes an injectable `cfbd_module` so tests run network-free with a fake (`tests/test_scrapers.py`, scoped via `only=`). The GraphQL client takes an injectable `post_fn` the same way (`tests/test_graphql.py`).
- **Per-game FBS scoping** — `--fbs-only` filters the game-id seed to games where home or away is FBS (cuts ~17k all-division games to ~4k). Only affects `per_game` endpoints.

### Key conventions

- **Spread sign convention:** `GameRecord.spread` is always the **home** spread. `_side_spread` negates it for away. A bet covers when `team_points + side_spread - opponent_points > 0`. Preserve this when touching grading.
- **Two bet types share one path:** `SystemFilter.bet_type` is `"spread"` (uses `side` home/away) or `"total"` (uses `total_side` over/under). `matches_system` and `grade_bet` branch on it; `_grade_total_bet` handles totals separately. The CLI only exposes spread bets today; the web form exposes both.
- **CFBD field names are inconsistent** (camelCase vs snake_case across API versions). `normalize._first(row, *keys, fallback=...)` tries multiple key spellings — extend the key list rather than assuming one casing.
- **All domain types are frozen dataclasses** (`models.py`). `GameRecord` field order is the CSV schema — changing it changes `storage` read/write. `storage._row_to_game` parses CSV strings back, treating `""` as `None`.
- **API token resolution** (`cfbd_client.find_cfbd_token`): env vars `CFBD_API_KEY`, `CFBD-API`, `BEARER_TOKEN`, then `env.env` file. `env.env` holds the real key (gitignored-style secret) — never commit or echo its value.
- **Running season-to-date stats** (`running_stats.py`, source kind `computed_running`): values are entering-game — computed from that team's strictly-prior games in the same season, ordered by raw `startDate` (fallback: week). First game of a season → `games_played=0`, percentages/averages `None` (which fail closed as filters). Never fold a game's own result into its own features.
- **Sidecar `_meta`**: `features.json` is `{"_meta": {registry_version, game_count, generated_at}, "games": {...}}`. `features.registry_version()` hashes sorted registry keys; the web UI warns when the sidecar was built by an older registry. Legacy flat sidecars still load.
- Web has `/compare` — pick saved systems, one `run_backtest` column each.

## Tests

`tests/` mirrors modules (`test_normalize`, `test_backtest`, `test_storage`, `test_web`, `test_cli`). The CLI test is a network-free smoke test over bundled `sample_data.py`. New backtest/normalize logic should follow the existing pattern: construct `GameRecord`/`SystemFilter` directly, assert on the result fields.

## Design reference

`docs/superpowers/specs/2026-06-12-cfb-system-maker-design.md` and the plan beside it describe v1 intent (CLI-first, web UI as a later layer over the same data model).
