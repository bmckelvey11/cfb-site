# System maker instructions

Scope: `cfb_system_maker`, Flask UI, scrapers, feature registry, and warehouse tooling.
Shared data, archive, and no-lookahead rules live in root `CLAUDE.md`; this file does not
own totals, over-zero, or spread-research behavior.

## What this is

`cfb_system_maker` is a Python CLI + Flask tool for backtesting college football betting systems. It fetches historical games and betting lines from the CollegeFootballData API, normalizes them into one joined table, applies filter-based "systems," and reports betting performance (hit rate, profit, ROI). Web UI is Bet Labs–style (stat chips, filter popup, dashboard) over the same engine.

`cfbd-python/` is the **vendored upstream CFBD OpenAPI client** (a git clone of `github.com/CFBD/cfbd-python`, pydantic v1). It is a dependency, not our code — do not edit it or treat its style as the project's. It is loaded at runtime by path injection (`cfbd_client.py:_load_cfbd_module`), not pip-installed.

## Commands

```powershell
pip install -r requirements.lock

# Tests (pytest.ini: testpaths=tests; addopts = -m "not slow")
python -m pytest
python -m pytest tests/test_backtest.py            # single file
python -m pytest tests/test_backtest.py::test_name  # single test
python -m pytest -m slow                            # browser smoke + search benchmark

# CLI (also runnable as `python -m cfb_system_maker <command>`)
python -m cfb_system_maker sample --data-dir data        # write+backtest bundled sample data, no network
python -m cfb_system_maker fetch --season 2023 --provider consensus --data-dir data
python -m cfb_system_maker scrape --season 2023 2024 --data-dir data   # pull ALL CFBD REST endpoints to data/raw/
python -m cfb_system_maker scrape --season 2023 --only games lines sp   # subset by endpoint name
python -m cfb_system_maker scrape --season 2023 --include-per-game --fbs-only   # per-game endpoints, FBS only
python -m cfb_system_maker graphql --season 2023 --data-dir data   # bulk-pull GraphQL tables to data/graphql/ (Tier 3)
python -m cfb_system_maker actionnetwork --season 2023 --data-dir data   # period odds CFBD lacks → data/raw/actionnetwork/
python -m cfb_system_maker build --season 2023 --provider consensus --data-dir data
python -m cfb_system_maker enrich --data-dir data   # join registry features -> data/processed/features.json (run after build)
python -m cfb_system_maker upcoming --data-dir data   # unplayed week → processed/upcoming.csv; never writes games.csv
python -m cfb_system_maker duckdb --data-dir data --explode --flatten-nested   # data/cfb.duckdb; serving still csv+features
python -m cfb_system_maker search --data-dir data --holdout-season 2024
python -m cfb_system_maker betlog import --csv path.csv --data-dir data
python -m cfb_system_maker refit-v1 --data-dir data   # Arscott tobit cache → processed/v1_fit.json
python -m cfb_system_maker backtest --data-dir data --side home --favorite --min-spread -14
python -m cfb_system_maker backtest --data-dir data --bet-type total --total-side over
python -m cfb_system_maker web --data-dir data --port 5000   # Flask UI at 127.0.0.1:5000 (waitress; --debug for reloader)
```

There is no compile step and no linter configured for our code. `requirements.lock` is the reproducible install; `requirements.txt` is the loose pins (Flask, waitress, duckdb, sklearn, pytest, plus `cfbd-python/requirements.txt`).

## Pipeline & architecture

Data flows acquire → build → enrich → consume. Each CLI command persists to disk.

1. **fetch** → `cfbd_client.fetch_games_and_lines` calls `GamesApi.get_games` + `BettingApi.get_lines`, dumps each model `.dict(by_alias=True)`, writes `data/raw/{games,lines}_{season}.json` (`storage.save_raw_json`). This is the only input `build` reads.
2. **build** → `normalize.normalize_games` joins games to lines by game id, picks one line per game (`_select_line`: preferred provider, else first usable), emits frozen `GameRecord`s → `data/processed/games.csv` (`storage.save_processed_games`).
3. **enrich** → `enrich.run_enrich` resolves `FEATURE_REGISTRY` per game → `data/processed/features.json`. Run after every `build`.
4. **backtest / web / search** → `backtest.run_backtest` filters with `matches_system`, grades with `grade_bet`, aggregates into `BacktestResult`.

`web.py` (`create_app`) skips fetch/build — it loads already-built `games.csv` (+ `features.json` if present). Missing data → `error="missing_data"`. Routes: `/` dashboard, `/system` editor, `/compare`, `/betlog`, `/filter-detail`, `/api/backtest`. Vanilla JS/CSS, no frontend framework. Waitress unless `--debug`.

Canonical data dir is required `CFB_DATA_ROOT`, resolved by root `cfb_paths.py`. Explicit
`--data-dir` still wins where a command supports it; no repository-relative fallback exists.

`scrapers.py` is a parallel REST sweep: registry `ENDPOINTS` (82 entries = unique vendored-client methods plus 9 `*_ngt` garbage-time variants). Unique live spec paths: 74; 73 methods registered, `/info/usage` is account metering (deliberately unregistered). `*_ngt` is a **second source** — `excludeGarbageTime` changes aggregates and cannot be derived from the unfiltered dump. (Vendored client bumped `034cd17` → `52f2bbf` on 2026-08-28 for CFP, core ratings, expanded SRS, coach profile/seasons/tenures, conference affiliations/changes.) Re-check with `python scripts/audit_coverage.py` (registry vs disk) and `python scripts/audit_endpoints.py` (live spec vs registry); `docs/data-coverage.md` records why absent endpoints are absent and why empty `[]` files are data floors, not failures. Writes `data/raw/` only — does not feed `build`/`backtest`.

`graphql_client.py` is a third fetch path over CFBD GraphQL (Hasura) — **Patreon Tier 3 only**. Introspects once, then for each root table in `GQL_DEFAULT_TABLES` (34 tables; `GQL_EXCLUDED` is three: `gamePlayerStat` size, `scoreboard` live-only, `gameMedia` no join key; `scripts/audit_endpoints.py` partitions the 37 introspected tables against both) auto-selects scalar columns (skips relations), picks a sort key (`id` else first scalar), paginates with `limit`/`offset`. Writes `data/graphql/{table}.json` (shapes differ from REST). Root fields advertise their own args, so tables lacking `limit`/`offset` are fetched in one shot, and `where:{season:{_in:[…]}}` is only added when the table has a season/year column **and** a `where` arg. Hasura sort arg is **`orderBy`** with an **uppercase** enum (`orderBy: {id: ASC}`) — `order_by`/`asc` are rejected, and unsorted `limit`/`offset` has no stable row order. HTTP poster must send a non-default `User-Agent` (Cloudflare 403s urllib's default); `post_fn` is injectable for tests.

`actionnetwork` is a fourth acquire path (no CFBD token): per-book odds including 1H/1Q markets CFBD lacks → `data/raw/actionnetwork/`. Browser-ish UA required.

`duckdb` loads `data/raw/` + `data/graphql/` into `data/cfb.duckdb` (one file; both land in `raw` as JSON payloads — GraphQL `calendar` becomes `raw.calendar_gql` on name clash — optional `stg` explode / `--flatten-nested`). Serving and backtests still use `games.csv` + `features.json`.

**MotherDuck (`md:cfb`) is a manual mirror, local file is source of truth.** Never write to `md:cfb` directly — rebuild and verify local first (`python -m pytest -m slow tests/test_core_agreement.py`), then promote with `python scripts/promote_to_motherduck.py --dry-run` (lists tables/rows, pushes nothing) followed by `--yes` (CTAS-replaces each table, stamps `meta.warehouse_version` on both sides). See `docs/duckdb-warehouse-plan.md` (`## MotherDuck promote`) for the full runbook.

`upcoming` writes `data/processed/upcoming.csv` (+ upcoming features sidecar) for the Current Matches panel. It never reads or writes `games.csv`.

### Scraper conventions (`scrapers.py`)

- **One `Endpoint` per CFBD method, tagged with a *mode*** that says how it's parameterized: `once` (no params, `{name}.json`), `season` (loop years, `{name}_{season}.json`), `season_week` (year×week, plays), `grid` (predicted-points down×distance), `per_game`/`per_player` (fan out over ids from already-scraped `games_*`/`roster_*` seeds), `on_demand` (live/key-lookup endpoints — scoreboard, matchup, search_players, live_plays — registered but skipped in bulk).
- **`per_game`/`per_player` are opt-in** (`--include-per-game`/`--include-per-player`) because they issue one call per game/player (thousands). Seasons missing their seed file are skipped, not errored.
- **`min_season` gates seasons an endpoint predates** — the CFP endpoints *raise* before 2014 rather than returning `[]`, and one raised season aborts the endpoint's remaining seasons (`_run_endpoint` catches per endpoint, not per season). Empty-but-valid floors (`core_ratings` before 2016) need no gate.
- **Resume by default** — an endpoint/season/week whose output file already exists is skipped (counted in `ScrapeReport.skipped`); `--force` re-scrapes. `SEASON_WEEK` empty weeks write no file, so they're re-probed each run. Several `*_game`/`ppa_players_*`/`play_stats` endpoints are `season_week` (CFBD 400s without a `week`/`team`).
- **Rate-limit safe** — `_call` sleeps `--delay` (default 1s) between calls and retries 429s with exponential backoff (5/10/20s). Model `ValidationError`s fall back to `_call_raw` (the `*_with_http_info` variant with `_preload_content=False`), bypassing pydantic for malformed rows (e.g. `recruiting_groups`).
- **Args are filtered by signature** (`_accepted` + `inspect.signature`): the generated client *rejects* unexpected kwargs, so `season_type` is only passed to methods that accept it, and the `id` vs `game_id` param-name difference resolves automatically. Don't hardcode per-endpoint kwarg lists.
- **One failing endpoint never aborts the run** — `_run_endpoint` captures any exception into `ScrapeReport.error` (covers Patreon-gated `weather`, rate limits, auth tiers) and continues.
- The runner takes an injectable `cfbd_module` so tests run network-free with a fake (`tests/test_scrapers.py`, scoped via `only=`). The GraphQL client takes an injectable `post_fn` the same way (`tests/test_graphql.py`). Action Network takes `fetch_fn`.
- **Per-game FBS scoping** — `--fbs-only` filters the game-id seed to games where home or away is FBS (cuts ~17k all-division games to ~4k). Only affects `per_game` endpoints.

### Key conventions

- **Warehouse working copy:** use `$CFB_DATA_ROOT/cfb.duckdb`
  (`C:\Users\mckel\dev\cfb\data`), not MotherDuck, for catalogs, explode, and schema work.
  Catalogs describe tables, exploded columns, and named box/play stats, not app features.
  GraphQL dumps land in `raw`, not a separate `graphql` schema.
- **Exploded staging:** `stg.plays` rebuilds with
  `python -m cfb_system_maker duckdb --explode-only --only plays`. Infer JSON shape from a
  sample; grouping structure across all `raw.plays` can exhaust memory. Browse order is
  identity → time → home/offense → away/defense → leftovers → `_source_file`.
- **Exploded arrays:** the payload explode leaves arrays as lists so a parent keeps its
  row grain. `--explode-lists` (also run by `--explode`) writes every leftover LIST/JSON
  column to `stg.<table>__<column>` at element grain, carrying the parent's scalars down
  and adding `<column>_idx` for the 1-based position. It recurses a level at a time, so
  `game_player_stats.teams` yields a table per level rather than one cross-producted leaf.
  Parents are never modified. Numeric JSON keys (Action Network `markets` book ids) become
  a `<column>_key` column, not column names. Scalar JSON (`ratings.spOffense`,
  `spOverall`) is reported and skipped.
- **Staging IDs:** primary `id` columns take the foreign-key name they join on (`gameId`,
  `playId`, `driveId`, `teamId`, `athleteId`, `conferenceId`, `venueId`, etc.). Explode and
  `--rename-ids` reapply this.
- **Action Network staging:** `stg.actionnetwork_history` is one offering per event, book,
  period, market, and side; `stg.actionnetwork_scoreboard` is one row per game. Generic
  explode is wrong for both. Use history for 1H/1Q prices and scoreboard for matchups/scores.
- **New statistics:** tempo and similar values belong in `FEATURE_REGISTRY`, not new
  `games.csv` columns or tables. Compute from `stg.drives` or `stg.plays`.
- **Spread sign convention:** `GameRecord.spread` is always the **home** spread. `_side_spread` negates it for away. A bet covers when `team_points + side_spread - opponent_points > 0`. Preserve this when touching grading.
- **Two bet types share one path:** `SystemFilter.bet_type` is `"spread"` (uses `side` home/away) or `"total"` (uses `total_side` over/under). `matches_system` and `grade_bet` branch on it; `_grade_total_bet` handles totals separately. CLI and web both expose spread and total (`--bet-type` / form). `fade` flips the graded side only.
- **No lookahead:** new registry features must be computable pre-game (entering-game state) or tagged `result_lookahead` and quarantined in the UI. Do not fold a game's own result into its features.
- **CFBD field names are inconsistent** (camelCase vs snake_case across API versions). `normalize._first(row, *keys, fallback=...)` tries multiple key spellings — extend the key list rather than assuming one casing.
- **All domain types are frozen dataclasses** (`models.py`). `GameRecord` field order is the CSV schema — changing it changes `storage` read/write. New game-level data goes in `features.json`, not new CSV columns. `storage._row_to_game` parses CSV strings back, treating `""` as `None`. `SavedSystem` JSON: new fields must default for old saves.
- **API token resolution** (`cfbd_client.find_cfbd_token`): env vars `CFBD_API_KEY`, `CFBD-API`, `BEARER_TOKEN`, then `env.env` file. `env.env` holds the real key (gitignored-style secret) — never commit or echo its value.
- **Running season-to-date stats** (`running_stats.py`, source kind `computed_running`): values are entering-game — computed from that team's strictly-prior games in the same season, ordered by raw `startDate` (fallback: week). First game of a season → `games_played=0`, percentages/averages `None` (which fail closed as filters).
- **Coach playstyle labels** (`coach_style.py`, feature `coach_style_cluster`): a GENERATED 189-coach dict mapping head-coach name → one of five k-means style groups; regenerate with `python scripts/build_coach_style_clusters.py`, never hand-edit. Grouped `result_lookahead` because the label is career-level (2016–2024) and residualized on SP+, so an early-season game reads a label informed by later results. `docs/coach-playstyle-analysis.md` is the validity study — read it before trusting a label: seasons match their coach's career cluster only 45.6% of the time, `balanced_spread` is a residual bucket rather than a style, and a walk-forward market test found no edge.
- **Sidecar `_meta`**: `features.json` is `{"_meta": {registry_version, game_count, generated_at}, "games": {...}}`. `features.registry_version()` hashes sorted registry keys; the web UI warns when the sidecar was built by an older registry. Legacy flat sidecars still load.
- **Design system (`docs/design-system.md`)**: the UI runs on Saturday Signal tokens. `static/styles.css` consumes them via `var(--*)` only — put color/type/space values in `static/tokens/{colors,typography,spacing}.css`, never inline hex in `styles.css`. Three rules that bite: Instrument Serif is for 48px+ and appears nowhere in this app; JetBrains Mono is stat values and chart axes only, never tables; tables use Instrument Sans with `font-variant-numeric: tabular-nums`. CTA labels are sentence case. Radii are tight (2px controls, 8px panels).

## Tests

`tests/` mirrors modules (~32 files). Default `python -m pytest` is `-m "not slow"` (`test_browser_smoke`, `test_search_benchmark` need `-m slow` plus Playwright + built `data/`). CLI smoke test is network-free over bundled `sample_data.py`. New backtest/normalize logic: construct `GameRecord`/`SystemFilter` directly, assert on result fields.

## Design reference

`docs/superpowers/specs/2026-06-12-cfb-system-maker-design.md` describes original v1 intent (CLI-first). Bet Labs UI + later pipeline live in code; prefer this file and `.planning/PROJECT.md`. Archived project maps are historical only.
