# CFB Site — Project Map

> Full-project reference for humans and AI agents. Generated 2026-07-16 from the live tree.
> Companion to [CLAUDE.md](../CLAUDE.md) (agent behavioral rules + core conventions, reproduced verbatim in Appendix A).
> If this document and the code disagree, the code wins — update this file.

---

## 1. What this is

`cfb_system_maker` is a Python CLI + Flask tool for backtesting college football betting systems. It pulls historical games and betting lines from the CollegeFootballData (CFBD) API (plus Action Network for period odds), normalizes them into one joined table, applies filter-based "systems" (e.g. *home favorites of 14+*), and reports betting performance: hit rate, profit, ROI, and statistical significance.

A companion research track, **`paper_models`**, recreates and extends an academic paper on censoring bias in college football totals (bet-the-over edge). As of 2026-07-16 it lives in its own git repo at `C:\Users\mckel\dev\paper_models` (sibling checkout, reads this repo's `data/` — see §12).

**Status snapshot (2026-07-16):**
- Core pipeline + web UI with feature filters: **built and tested** (12 test files, all green expected via `python -m pytest`).
- Bulk data downloaded: 2,501 REST raw files, 25 GraphQL tables, seasons ~2020–2024 core (ratings back to 2013 for the paper work).
- **Web App Phase 2** ([plan](superpowers/plans/2026-07-16-web-app-phase-2.md)) is planned, **not yet implemented** (`running_stats.py` does not exist yet).
- The heavy `gamePlayerStat` GraphQL pull is built + tested but **deliberately held** — see [REMINDERS.md](../REMINDERS.md).
- ⚠️ **`.git` is an empty directory — there is no version control history.** See §14.

---

## 2. Repository layout

| Path | What it is |
|---|---|
| `cfb_system_maker/` | The product: CLI + Flask package (15 modules + `templates/`, `static/`) |
| `cfbd-python/` | **Vendored upstream** CFBD OpenAPI client (own git clone, pydantic v1). Dependency, not our code — never edit, never emulate its style |
| `tests/` | Our pytest suite (mirrors modules 1:1) |
| `data/` | All fetched data (see §10). Not shareable output; local working set |
| `docs/superpowers/` | Design specs + implementation plans (see §13) |
| `scripts/` | Misc personal utilities (`rename_videos.py`, `rename-by-regex.ps1`) — unrelated to CFB pipeline |
| `CLAUDE.md` | Agent guidance: behavioral rules + project conventions (Appendix A) |
| `README.md` | Human quick-start: every CLI command with examples |
| `REMINDERS.md` | Pending-work queue (held pulls, opt-in endpoints not yet scraped) |
| `SCHEMA_AUDIT.md` | Verified REST↔GraphQL join-key map + future Postgres model (see §13) |
| `data_fields.csv` | Field catalog: `source,dataset,field,type,example` for every REST/GraphQL dataset |
| `env.env` | **Secret.** Holds the real CFBD API token. Never commit, echo, or copy its value |
| `requirements.txt` | `-r cfbd-python/requirements.txt` + `pytest` + `Flask` |
| `pytest.ini` | `testpaths = tests` — keeps pytest out of `cfbd-python/`'s own tests |
| `.remember/` | Session-handoff notes for agents (now/today/recent/archive buffers) |
| `.flask-out.log`, `.flask-err.log` | Stray dev-server logs at root (harmless) |

---

## 3. Core pipeline

Three stages, each a separate CLI command, persisted to disk between stages. A fourth (`enrich`) builds a feature sidecar consumed by backtest/web filters.

```
  ACQUIRE (any of 4 paths, §4)              BUILD                    ENRICH                      CONSUME
┌─────────────────────────────┐   ┌────────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│ fetch  → data/raw/games_*,  │   │ normalize.normalize_   │  │ enrich.enrich_games  │  │ backtest CLI         │
│          lines_*.json       │──▶│ games: join games+lines│─▶│ joins raw/graphql    │─▶│ (spread bets)        │
│ scrape → data/raw/*.json    │   │ by game id, one line   │  │ sources per game via │  │                      │
│ graphql→ data/graphql/*.json│   │ per game (_select_line)│  │ FEATURE_REGISTRY     │  │ web (Flask)          │
│ action → data/raw/          │   │ → GameRecord rows      │  │ → data/processed/    │  │ (spread+total bets,  │
│  network  actionnetwork/    │   │ → data/processed/      │  │   features.json      │  │  feature filters,    │
│                             │   │   games.csv            │  │   (sidecar)          │  │  save/load systems)  │
└─────────────────────────────┘   └────────────────────────┘  └──────────────────────┘  └──────────────────────┘
```

- **fetch** → `cfbd_client.fetch_games_and_lines` calls `GamesApi.get_games` + `BettingApi.get_lines`, dumps each pydantic model `.dict(by_alias=True)`, writes `data/raw/{games,lines}_{season}.json`.
- **build** → `normalize.normalize_games` joins games to lines by game id, picks one line per game (preferred provider, else first usable), emits frozen `GameRecord`s → `data/processed/games.csv`.
- **enrich** → `enrich.run_enrich` resolves every `FeatureDef` in `features.FEATURE_REGISTRY` per game against raw/graphql indexes → `data/processed/features.json` (`{game_id_str: {key: value}}`, team-scoped keys as `home_<key>`/`away_<key>`).
- **backtest** → `backtest.run_backtest` filters records with `matches_system`, grades each with `grade_bet`, aggregates into `BacktestResult` (+ `SystemStats` significance block).
- **web** → `web.create_app` skips fetch/build; loads `games.csv` (+ `features.json` if present) and reruns `run_backtest` per request. Without built data the index renders an `error="missing_data"` state.

Only `fetch`'s `games_*`/`lines_*` files feed `build`. Everything `scrape`/`graphql`/`actionnetwork` pull is consumed by `enrich` (some of it) and reserved for a future Postgres JSONB staging layer (see `SCHEMA_AUDIT.md`).

---

## 4. Data acquisition — four parallel paths

| Path | CLI | Module | Output | Auth | Purpose |
|---|---|---|---|---|---|
| Targeted fetch | `fetch` | `cfbd_client.py` | `data/raw/games_{Y}.json`, `lines_{Y}.json` | CFBD token | The only input `build` reads |
| Full REST sweep | `scrape` | `scrapers.py` | `data/raw/{name}[_{Y}[_wk{W}]].json` | CFBD token | All 61 CFBD REST endpoints, registry-driven |
| GraphQL bulk | `graphql` | `graphql_client.py` | `data/graphql/{table}.json` | CFBD **Patreon Tier 3** | Collapses per-row REST fan-out into paginated bulk queries (24 default tables + opt-in `--game-player-stats`) |
| Action Network | `actionnetwork` | `actionnetwork_client.py` | `data/raw/actionnetwork/` | none (browser UA required) | Per-book odds incl. **1H/1Q period markets** CFBD lacks; scoreboard per week + history per event |

Shared design across all four:
- **Resume-by-file**: output file exists → skipped; `--force` re-pulls. Empty season-week probes write no file so they re-probe next run.
- **Injectable I/O for tests**: `scrapers` takes `cfbd_module`, `graphql_client` takes `post_fn`, `actionnetwork_client` takes `fetch_fn` — all tests run network-free with fakes.
- **Rate-limit safe**: 1s default delay, 429 retries with exponential backoff (5/10/20s).
- **Cloudflare**: both GraphQL and Action Network 403 urllib's default User-Agent — a browser-ish UA is mandatory.

Scraper-specific conventions (endpoint modes, per-game/per-player opt-ins, signature-filtered kwargs, error isolation) are documented in CLAUDE.md → *Scraper conventions* (Appendix A) — that section is current and authoritative.

---

## 5. Module reference (`cfb_system_maker/`)

| Module | Role | Key symbols |
|---|---|---|
| `models.py` | All domain types, frozen dataclasses | `GameRecord`, `SystemFilter`, `FeatureFilter`, `BetDetail`, `BacktestResult`, `SystemStats`, `SavedSystem` |
| `cli.py` | argparse wiring for all 9 subcommands + result printing | `main`, subparsers: `sample fetch build enrich scrape graphql actionnetwork backtest web` |
| `__main__.py` | `python -m cfb_system_maker` entry | — |
| `cfbd_client.py` | Loads vendored client by **path injection** (not pip), token resolution, targeted fetch | `_load_cfbd_module`, `find_cfbd_token`, `fetch_games_and_lines` |
| `scrapers.py` | Registry of all 61 REST endpoints + one runner | `ENDPOINTS`, `Endpoint`, `ScrapeReport`, `run_scrape` |
| `graphql_client.py` | Hasura introspection → auto column selection → paginated bulk pull | `graphql_scrape`, `GQL_DEFAULT_TABLES`, injectable `post_fn` |
| `actionnetwork_client.py` | Action Network scoreboard + per-event odds history | `AnReport`, `DEFAULT_PERIODS` (`firsthalf`, `firstquarter`) |
| `normalize.py` | games⋈lines join, provider selection, key-spelling tolerance | `normalize_games`, `_select_line`, `_first` |
| `storage.py` | All disk I/O: raw JSON, `games.csv`, saved systems | `save/load_raw_json`, `save/load_processed_games`, `save/load/list_system(s)` |
| `features.py` | Declarative feature registry (35 `FeatureDef`s) + filter evaluation | `FEATURE_REGISTRY`, `FeatureDef`, `feature_ok`, `get_nested` |
| `enrich.py` | Registry → per-game feature sidecar | `enrich_games`, `run_enrich`, `save/load_features` |
| `backtest.py` | Filter matching, bet grading, aggregation, significance stats | `run_backtest`, `matches_system`, `grade_bet`, `_grade_total_bet`, `compute_system_stats` |
| `web.py` | Flask app: filter form → backtest per request, save/load systems, charts | `create_app`, routes `GET /` (index+backtest), `POST /save`, `/favicon` |
| `sample_data.py` | Bundled offline dataset for `sample` command + CLI smoke test | — |
| `templates/index.html`, `static/styles.css` | The single-page web UI | — |

---

## 6. Domain model

All types are **frozen dataclasses** in `models.py`:

- **`GameRecord`** — one game+line row: `game_id, season, week, home_team, away_team, home_conference, away_conference, home_points, away_points, provider, spread, total`. **Field order IS the `games.csv` schema** — changing it changes `storage` read/write. Phase 2 explicitly freezes this: new data rides the `features.json` sidecar, never new CSV columns.
- **`SystemFilter`** — a betting system: `bet_type` (`"spread"`/`"total"`), `side`/`total_side`, season/week/team/conference/provider sets, favorite/underdog/home/away flags, spread/total ranges, plus `feature_filters: tuple[FeatureFilter, ...]`.
- **`FeatureFilter`** — `key, op, value, perspective` against enriched features.
- **`BacktestResult`** — counts, hit rate, profit, ROI, `bet_details: list[BetDetail]`, optional `SystemStats`.
- **`SystemStats`** — break-even rate, edge, Wilson interval, z/p, ROI t-stat, `low_sample` flag.
- **`SavedSystem`** — named `SystemFilter` + timestamp, persisted to `data/systems/{name}.json` by `storage.save_system` (dir created on first save).

---

## 7. Feature layer (registry → sidecar → filters)

The single source of truth is `features.FEATURE_REGISTRY` (35 `FeatureDef`s). Each def declares:

- `group`: `pregame | team_preseason | metadata | result_lookahead` (Phase 2 adds `season_to_date`)
- `source_kind`: which raw/graphql file family feeds it (`raw_game`, `raw_lines`, `raw_weather`, `raw_media`, `raw_team_season`, `raw_teams`, `raw_coaches`, `raw_havoc`, `graphql_game`, `graphql_weather`, `graphql_lines`, `graphql_game_team`)
- `join`: `game_id | team_season | team_name | conference_name`
- `control`: how the web UI renders it (`bool | categorical | numeric`)
- `team_scoped`: if true, stored twice in the sidecar as `home_<key>` / `away_<key>`

Flow: `enrich.py` builds per-source indexes → resolves every def per game → `data/processed/features.json`. `backtest.matches_system` applies `SystemFilter.feature_filters` through `features.feature_ok`. `web.py` renders one filter row per def, grouped by `group` (Jinja auto-titles group names; only the group-ordering tuple in `web._feature_options` needs updating for a new group).

**Invariants:** `None` feature values **fail closed** (never satisfy a filter). `result_lookahead` group exists to make lookahead explicit, not accidental. Known dead code: `features.resolve_storage_key` is defined but never called — leave it (out of scope per phase-2 plan).

---

## 8. Web app

`python -m cfb_system_maker web --data-dir data --port 5000` → `http://127.0.0.1:5000`.

- `GET /` — renders the filter form and, when params present, runs the backtest inline. Query-string is the state; results include a spread-range chart (`_range_chart`).
- `POST /save` — persists the current form as a named system (`storage.save_system`); systems reload via a `--load`-style dropdown.
- The web form exposes **both** bet types (spread + total) and all feature filters; the CLI `backtest` command exposes spread bets + scalar filters + `--save/--load`.
- Phase 2 will add: `/compare` route (rerun backtest per saved system), stale-registry banner (`registry_version()` hash vs sidecar `_meta`), filter coverage %, streaks.

---

## 9. Conventions (the law)

The canonical list lives in CLAUDE.md (Appendix A) — summarized and extended here:

1. **Spread sign:** `GameRecord.spread` is always the **home** spread. Away side negates (`_side_spread`). A bet covers when `team_points + side_spread - opponent_points > 0`. Preserve when touching grading.
2. **Never edit `cfbd-python/`.** Vendored dependency with its own git history; loaded by path injection at runtime.
3. **`GameRecord`/`games.csv` schema frozen.** New per-game data goes in the `features.json` sidecar.
4. **CFBD key spellings are inconsistent** (camelCase vs snake_case). Use/extend `normalize._first(row, *keys)` — never assume one casing.
5. **Token resolution order:** env `CFBD_API_KEY` → `CFBD-API` → `BEARER_TOKEN` → `env.env` file. The token is a secret.
6. **No new dependencies.** Stdlib + Flask + pytest is the whole stack. No linter, no build step.
7. **Style:** `from __future__ import annotations`; frozen dataclasses for domain types; module-private helpers prefixed `_`; comments only for non-obvious constraints.
8. **Testing pattern:** construct `GameRecord`/`SystemFilter` directly, assert result fields; network I/O always injectable and faked. TDD with frequent commits (per phase-2 plan).
9. **Nulls fail closed** in feature filtering; **no lookahead** in any as-of-week computation (first game of season → `games_played = 0`, percentages `None`).
10. **Resume-by-file** for every scraper; deleting a file is the retry mechanism, `--force` the override.

---

## 10. Data inventory (`data/`, local only)

| Dir | Count | Contents |
|---|---|---|
| `data/raw/` | 2,501 files | All REST endpoint pulls: per-season (`lines_2023.json`), per-season-week (`plays_2023_wk1.json`), singletons (`venues.json`, `conferences.json`), plus `actionnetwork/` subtree. Core seasons 2020–2024; some series wider |
| `data/graphql/` | 25 files | One JSON per GraphQL table (default 24 + extras). `gamePlayerStat_{Y}.json` **not yet pulled** (held — REMINDERS.md) |
| `data/processed/` | 2 files | `games.csv` (build output) + `features.json` (enrich sidecar) |
| `data/systems/` | — | Created on first `--save`; none saved yet |

`data_fields.csv` at repo root catalogs every field across both APIs (`source,dataset,field,type,example`) — use it before hunting through raw JSON.

---

## 11. Tests (`tests/`, run: `python -m pytest`)

Mirrors modules 1:1. `pytest.ini` scopes collection to `tests/` so cfbd-python's suite never runs.

| File | Covers |
|---|---|
| `test_models` *(via others)* / `test_normalize.py` | games⋈lines join, `_first`, provider selection |
| `test_backtest.py` | matching, spread/total grading, aggregation, stats |
| `test_storage.py` / `test_storage_systems.py` | CSV round-trip, `""`→`None`; saved-system JSON round-trip |
| `test_features.py` / `test_enrich.py` | registry defs, `feature_ok`, sidecar building |
| `test_web.py` / `test_web_features.py` | routes, form parsing, feature-filter rows |
| `test_cli.py` | network-free smoke test over `sample_data.py` |
| `test_scrapers.py` | runner against fake `cfbd_module`, scoped via `only=` |
| `test_graphql.py` | introspection/pagination against fake `post_fn` |
| `test_actionnetwork.py` | scoreboard/history against fake `fetch_fn` |

---

## 12. `paper_models` — censoring-bias research track (separate repo)

**Moved out of this repo 2026-07-16.** Now its own git repo at `C:\Users\mckel\dev\paper_models`. Its scripts resolve data via the **sibling path** `../cfb-site/data/` — keep both checkouts side by side (v1 also takes an explicit `--csv`).

Recreation of Arscott (2022), *"Market efficiency and censoring bias in college football gambling"* (SSRN 4197428): team scores are left-censored at 0, so totals are biased up → bet the **over** when expected censoring bias is high.

| Dir | Verdict |
|---|---|
| `v1/` | **Frozen baseline — do not edit.** Full recreation (Tobit, censoring bias, probit, Kelly), 13 seasons real CFBD data (2013–2025). Headline: bias > 1.0 → 56.6% over 680 bets |
| `v2/` | Tightened SEs + dropped independence assumption — both immaterial; v1 stands |
| `v3/` | Is the edge just "low total/lopsided game"? No — `biasTotals` dominates in- and out-of-sample |
| `floor_bias_1h/` | First-half extension; approximation mode now, true backtest awaits real 1H lines (`--half-lines`) — **this is what the Action Network 1H odds are for** |
| `saturation_bias/` | Under-side mirror: **negative result**, no symmetric under edge |
| `monitor/` | Ongoing monitoring runner |

Each subdir has its own README with run instructions. The track reads this project's `data/` (raw lines/games JSON + `games.csv`) but imports nothing from `cfb_system_maker`. It runs on the **system Python** (`C:\Python314`, has numpy) — the project `.venv` does not have numpy.

---

## 13. Docs & planning artifacts

| Doc | Status |
|---|---|
| `docs/superpowers/specs/2026-06-12-cfb-system-maker-design.md` + plan | v1 intent (CLI-first, web as layer over same data model) — **shipped** |
| `docs/superpowers/specs/2026-06-13-web-feature-filters-design.md` + plan | Feature-filter web layer — **shipped** |
| `docs/superpowers/plans/2026-07-16-web-app-phase-2.md` | Running as-of-week stats, new registry fields, `_meta`/stale banner, coverage %, streaks, `/compare` — **pending, not started** |
| `SCHEMA_AUDIT.md` | Verified REST↔GraphQL join keys (game_id ✅, team_id ✅, athlete_id ⚠️ string-vs-int, conference ⚠️ name-vs-id), the name-keyed-REST vs id-keyed-GraphQL impedance, crosswalk strategy, and the suggested Postgres dim/fact model for the future JSONB staging layer |
| `REMINDERS.md` | Held `gamePlayerStat` pull (~2.9M rows, ~425MB, resume-safe, run only after base data complete) + opt-in REST endpoints not yet scraped (`advanced_box_score`, `win_probability`, `player_season_overview`, on-demand endpoints) |

---

## 14. Known issues & gotchas

- ⚠️ **No version control.** `.git/` exists but is **empty** — `git log`/`git status` fail with `fatal: not a git repository`. Every plan says "commit frequently," but nothing has ever been committed. **Recommended first action: `git init`, add a `.gitignore` (`data/`, `env.env`, `.venv/`, `__pycache__/`, `.flask-*.log`, `cfbd-python/` as submodule-or-ignored), initial commit.**
- **CLAUDE.md is stale.** It predates and does not mention: `actionnetwork_client.py` (4th fetch path), `features.py`/`enrich.py` (feature layer), `backtest` `--save/--load` + `data/systems/`, `SystemStats` significance block, `paper_models/`, `SCHEMA_AUDIT.md`, `data_fields.csv`, `REMINDERS.md`. Its pipeline/conventions/scraper sections remain accurate.
- **`env.env` sits in repo root unprotected by git** (since git doesn't exist). Ensure it's ignored before the first commit.
- **Dead code:** `features.resolve_storage_key` — known, intentional, leave it.
- **`scripts/`** contains personal file-renaming utilities unrelated to the project.
- **Windows-first repo:** commands in docs are PowerShell; paths are Windows-style. Python 3.14 venv at `.venv/`.

---

## 15. Pending work queue (priority order as of 2026-07-16)

1. Execute **Web App Phase 2** plan (`docs/superpowers/plans/2026-07-16-web-app-phase-2.md`).
2. Finish base data downloads, then run the held **gamePlayerStat** GraphQL pull (REMINDERS.md has the exact command and expected size).
3. Optional REST backfills: `--include-per-game` (`advanced_box_score`, `win_probability`, with `--fbs-only`), `--include-per-player` (`player_season_overview`).
4. Longer-term: Postgres JSONB staging layer per `SCHEMA_AUDIT.md`; true 1H backtest in the `paper_models` repo (`floor_bias_1h/`, sibling checkout) once Action Network 1H lines are wired in (`--half-lines`).

---

## Appendix A — CLAUDE.md (verbatim copy, 2026-07-16)

````markdown
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

`scrapers.py` is a parallel, broader fetch path: a registry (`ENDPOINTS`, 61 entries) covering **every** CFBD REST endpoint, driven by one runner (`scrape`). It writes raw JSON to `data/raw/` only — it does not feed `build`/`backtest` (which still use `fetch`'s `games`/`lines` files). Intended as the load source for a future Postgres `JSONB` staging layer.

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

## Tests

`tests/` mirrors modules (`test_normalize`, `test_backtest`, `test_storage`, `test_web`, `test_cli`). The CLI test is a network-free smoke test over bundled `sample_data.py`. New backtest/normalize logic should follow the existing pattern: construct `GameRecord`/`SystemFilter` directly, assert on the result fields.

## Design reference

`docs/superpowers/specs/2026-06-12-cfb-system-maker-design.md` and the plan beside it describe v1 intent (CLI-first, web UI as a later layer over the same data model).
````
