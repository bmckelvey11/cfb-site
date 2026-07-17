# Phase 3: Data Depth & Breadth - Research

**Researched:** 2026-07-17
**Domain:** CFBD data pipeline (fetch/normalize/enrich), feature registry, no-lookahead season-to-date computation
**Confidence:** HIGH (all sources are on-disk data + read source code; one live-network claim is dated, see DATA-01)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Backfill **as far back as CFBD betting lines allow** — not a fixed year. Research must first determine the real floor (earliest season `BettingApi.get_lines` consensus returns usable spread/total data; games exist far earlier, but lines are the binding constraint). Extend fetch/build to that floor.
- **D-02:** **Require a usable line** to include a game — keep current `normalize._select_line` behavior. Backfilled seasons with games but no usable consensus line contribute no rows. History floor = line-coverage floor, not game-coverage floor. (Satisfies success criterion 1.)
- **D-03: Advanced team stats — entering-game (to-date) only.** SP+, success rate, explosiveness, havoc, PPA splits are full-season aggregates that bake in the game's own result → lookahead if used pre-game. Wire as **running / season-to-date** features (same construction as `running_ppa_off/def` in `running_stats.py`), NOT raw season aggregates.
- **D-04: Recruiting / talent — preseason values.** Team talent composite and recruiting rankings are genuinely pre-game; wire directly as `team_preseason` team-season features. No to-date computation.
- **D-05: Player-level — team-aggregated only.** Roll player stats up to team-season features. **No per-game per-player fan-out** this phase (deferred). Prefer `data/raw/adjusted_player_*` over new heavy pulls.
- **D-06:** Every new feature is (a) computable from entering-game state, (b) genuinely preseason/pre-game, or (c) if a full-season aggregate, MUST be tagged `result_lookahead` and quarantined. Verified by existing `tests/` construct-and-assert pattern. Never fold a game's own result into its own features.
- **D-07:** After extending data + adding features, `features.json` regenerated over full extended range via `enrich`; `features.registry_version()` will change — web UI stale-sidecar warning expected until rebuild.

### Claude's Discretion
- Exact endpoint/method names, the running-stat accumulation math for advanced stats, and whether backfill reuses `fetch` vs `scrapers.py` are implementation choices.
- Returning-production features may be included if cheap alongside D-04, otherwise defer.

### Deferred Ideas (OUT OF SCOPE)
- Full per-player / per-game player-stat fan-out (heavy scrape).
- Full-season raw aggregate features for exploration (only if tagged `result_lookahead`; not required).
- Returning-production features (optional stretch).
- Public betting-percentage filters (no CFBD source; Action Network not wired).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-01 | Historical game/line coverage backfilled further back than the 2013 floor **where CFBD coverage allows** | CFBD line floor is empirically 2013 (see DATA-01 findings). Built `games.csv` already covers 2013–2025. The fetch/build path is fully parameterized by `--season`; no code change needed to add seasons — the constraint is data availability, not code. Deliverable is a **live probe + floor guard + documentation**, not a large backfill. **SC-1 conflict flagged as blocking open question.** |
| DATA-02 | Additional CFBD REST/GraphQL endpoints wired into `FEATURE_REGISTRY` following no-lookahead / entering-game convention | All candidate source files already on disk 2012–2025 (`advanced_game_stats`, `adjusted_team_season`, `sp`, `talent`, `recruiting_teams`, `adjusted_player_*`). D-03 = extend `compute_running_stats` from per-game `advanced_game_stats`. D-04 largely already wired. D-05 = prior-season player aggregation. Per-feature plumbing table below. |
</phase_requirements>

## Summary

This is a backend/data phase with two very asymmetric axes. **DATA-01 (depth) is thin and near-complete; DATA-02 (breadth) is the substance.**

**Depth (DATA-01):** The binding constraint on how far back history can go is CFBD *betting-line* coverage, not game coverage. Empirical evidence on disk is unambiguous: a full 2012 pull captured 805 game/line rows with **zero** usable lines across all providers, while 2013 has 806/813 games with usable consensus lines. Games exist on disk back to 1992, but lines start in 2013. The currently-built `games.csv` is already 2013–2025 (12,964 games) — i.e. **the current floor already equals the CFBD line-coverage floor.** The fetch (`fetch --season <list>`) and build (`build --season <list>`) commands are fully parameterized; no hardcoded floor exists anywhere in `cli.py`, `web.py`, or `backtest.py`. So "backfill earlier than 2013" is essentially a no-op against CFBD — the DATA-01 deliverable is a bounded **live line-coverage probe** (to re-confirm the floor against a possibly-refreshed API and upgrade the dated on-disk evidence), a floor **guard**, and documentation. **Success Criterion 1 ("season filter earlier than 2013 → non-empty results") is unsatisfiable if 2013 is the floor and must be escalated to the user — see Open Questions.**

**Breadth (DATA-02):** This is where the real work lives, and it is nearly all local — every candidate source file is already scraped on disk for 2012–2025. The single decisive question for every proposed feature is: **does the metric have a per-game source?** If yes (per-game `advanced_game_stats`: success rate, explosiveness, EPA/PPA splits, line yards) → accumulate to-date exactly like the existing PPA path → entering-game, no-lookahead (D-03). If the metric only exists as a season rating (`sp_*`, `fpi_*`, `adjusted_team_season`) → it **cannot** be made to-date; current-season use is lookahead (`result_lookahead` only), and the sole no-lookahead surface is *prior-season-as-preseason*. D-04 (talent/recruiting) is **largely already wired** in the registry. D-05 player aggregation overlaps the existing `returning_production` features and must use *prior* season to stay pre-game.

**Primary recommendation:** Spend ~15% of effort on DATA-01 (live probe → confirm floor → guard → doc; escalate SC-1) and ~85% on DATA-02, implementing D-03 to-date advanced stats by extending `compute_running_stats` from `advanced_game_stats_{season}.json` (mirroring the existing `ppa` plumbing), then closing D-04/D-05 gaps. No new packages, no schema changes, no new heavy scrapes.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Backfill season fetch (DATA-01) | Fetch (`cfbd_client.fetch_games_and_lines`) | Storage (`save_raw_json`) | Season list is a runtime arg; the fetch path already loops seasons |
| Line floor gate | Normalize (`_select_line`) | — | "Require a usable line" already drops line-less games (D-02) |
| To-date advanced stats (D-03) | Compute (`running_stats.compute_running_stats`) | Enrich (index builder) | Per-game accumulation belongs in the same layer as PPA to-date |
| Preseason talent/recruiting (D-04) | Registry (`features.py`) + Enrich (`_lookup_team_scoped`) | — | Static team-season joins; mostly already wired |
| Player→team aggregation (D-05) | Enrich (new index builder) | Registry | Aggregation is a join/index concern, surfaced as one registry row |
| Feature exposure to filter UI | Registry (`FEATURE_REGISTRY`) | web.py (auto-renders) | New rows auto-render; no UI work (verified web.py:527 / index.html:114) |

## Standard Stack

No external packages are added or changed in this phase. All work uses the existing in-repo modules and the already-vendored CFBD client.

| Component | Role in this phase | Why standard |
|-----------|-------------------|--------------|
| `cfb_system_maker/cfbd_client.py` | `fetch_games_and_lines(seasons, ...)` — the DATA-01 fetch extension point (season list already parameterized) | Existing, canonical fetch path used by `fetch` CLI |
| `cfb_system_maker/normalize.py` | `_select_line` "require a usable line" gate (D-02) | Existing; unchanged behavior is the desired behavior |
| `cfb_system_maker/running_stats.py` | `compute_running_stats` — template + extension point for D-03 to-date advanced stats | Existing no-lookahead accumulation engine |
| `cfb_system_maker/enrich.py` | Index builders + `_lookup` branches join raw files → `features.json` | Existing; every new source needs an index + lookup here |
| `cfb_system_maker/features.py` | `FEATURE_REGISTRY` / `FeatureDef` — one row per new feature | Existing registry; new rows auto-render in the filter UI |

**Installation:** none. `pip install -r requirements.txt` already satisfies all needs.

**Environment note:** the vendored `cfbd-python/` clone is **empty in the current working copy** (`find cfbd-python -name __init__.py` → nothing). Any task that runs a live fetch/probe must first restore the clone (`git clone https://github.com/CFBD/cfbd-python` into `cfbd-python/`, pydantic v1) — the fetch path injects it by `sys.path` (`cfbd_client._load_cfbd_module`). Pure enrich/registry/test work does not need it (operates on on-disk JSON). `[VERIFIED: on-disk grep]`

## Package Legitimacy Audit

**No external packages are installed in this phase.** All data sources are already on disk; all code uses existing in-repo modules and the already-vendored (path-injected, not pip-installed) CFBD client. Package Legitimacy Gate: N/A — nothing to audit.

## DATA-01 — Depth / Backfill Findings

### The real floor is 2013 (line coverage, not game coverage)

| Season | Game rows on disk | Line rows | Rows w/ any provider line | Usable consensus rows | Source |
|--------|-------------------|-----------|---------------------------|-----------------------|--------|
| 2012 | 805 (`games_2012.json`) | 805 (`lines_2012.json`) | **0** | **0** | `[VERIFIED: on-disk pull, dated 2026-06-13]` |
| 2013 | 813 | 813 | 813 | 806 (providers: consensus, numberfire, teamrankings) | `[VERIFIED: on-disk pull]` |

Games exist on disk far earlier (1992, 1998, 2001–2004, 2007–2025), but the `lines_*.json` set starts at 2012 and 2012 is **empty of actual line children**. Under D-02 ("require a usable line"), 2012 contributes **zero** rows — which is exactly the desired clean-backtest behavior. The built `games.csv` is already **2013–2025, 12,964 games**; `features.json` `_meta` = 12,964 games, `registry_version` `69084ed55504`. `[VERIFIED: on-disk games.csv + features.json]`

Web documentation does not authoritatively state a betting-line start year (searched; cfbfastR betting examples use 2018 but that is not a floor). The on-disk 2012-empty / 2013-full pattern is the strongest available evidence and matches community knowledge that CFBD lines begin in 2013. `[CITED: cfbfastr.sportsdataverse.org/articles/cfbd_betting.html]` `[ASSUMED: 2013 is the hard CFBD line floor — confirm via live probe]`

### The fetch/build path is fully parameterized — no code change needed to add seasons

- `fetch` CLI: `--season` is `nargs="+"` → `fetch_games_and_lines(args.seasons, ...)` loops seasons (`cli.py:57`, `cfbd_client.py:24`). `[VERIFIED: source]`
- `build` CLI: `--season` is `nargs="+"` → `normalize_games` per season (`cli.py:70`). `[VERIFIED: source]`
- **No hardcoded floor year** in `cli.py`, `web.py`, or `backtest.py` (grepped `2013`/`2012`/`SEASON_MIN`/`floor` → no matches in web/backtest; season set is data-driven from what `games.csv` contains). `[VERIFIED: grep]`
- Backfill should **reuse the existing `fetch` path**, not `scrapers.py`. `fetch` writes the `games_{season}.json` + `lines_{season}.json` that `build`/`normalize` actually consume; `scrapers.py` writes to `data/raw/` but does **not** feed build/backtest (per CLAUDE.md). Using `scrapers.py` for the game/line backfill would produce files the pipeline ignores.

### What DATA-01 actually delivers

Because 2013 already equals the CFBD line floor, the honest DATA-01 scope is:
1. **Live line-coverage probe** (the plan's first task; re-confirms floor against a possibly-refreshed API and upgrades the dated on-disk claim). Bounded sweep, e.g. seasons 2008–2013, calling `BettingApi.get_lines` and counting usable consensus rows; stop at the first season with usable lines. If any pre-2013 season now returns usable lines, backfill it via `fetch`→`build`→`enrich`.
2. **Floor guard / documentation** — record the confirmed floor so the "backfill earlier" requirement is closed with evidence rather than an unbounded search.
3. **Confirm 2012 contributes 0 rows** (D-02 clean behavior) — already true; assert with a test.

**SC-1 escalation:** Success Criterion 1 ("a season filter earlier than 2013 yields non-empty backtest results") is **unsatisfiable** if the probe confirms 2013 is the floor. The requirement text (DATA-01 "where CFBD coverage allows"; D-01 "as far back as lines allow") is satisfiable by verification, but SC-1's stronger wording conflicts. See Open Questions — this needs user resolution, not a silent workaround.

## DATA-02 — Breadth / New Registry Features

### The decisive discriminator: does the metric have a per-game source?

| Metric family | Per-game source on disk? | No-lookahead class | How to wire |
|---------------|--------------------------|--------------------|-------------|
| Success rate, explosiveness, EPA/PPA splits, line yards (D-03) | **Yes** — `advanced_game_stats_{season}.json` (per game/team, 2012–2025) | **(a) entering-game to-date** | Extend `compute_running_stats` to accumulate from a `(game_id, team)` advanced-stats index, exactly like the existing `ppa` arg |
| SP+ rating/havoc (`sp_*`), FPI (`fpi_*`), season-adjusted EPA (`adjusted_team_season`) | **No** — season-level only (one row per team-year) | **(c) lookahead** if current-season | Do **not** wire as pregame. Only surfaces no-lookahead as *prior-season* preseason feature (optional) or as `result_lookahead` (quarantined) |
| Team talent composite, recruiting rank/points (D-04) | N/A — set before season | **(b) preseason** | Direct `team_preseason` team-season join — **mostly already wired** |
| Player wepa (`adjusted_player_passing/rushing`) (D-05) | Season-total per player | **(c) lookahead** if same-season; **(b) preseason** if prior-season | Aggregate **prior** season to team; overlaps existing `returning_production` |

### D-03: Advanced team stats as to-date (locked mechanism)

`advanced_game_stats_{season}.json` is **per-game** offense/defense with exactly the fields Bet Labs surfaces: `offense.successRate.total`, `offense.explosiveness`, `offense.ppa`, `defense.*` mirrors, plus rushing line-yards splits and standard/passing-downs breakdowns. `[VERIFIED: on-disk structure, count 1644 rows for 2015]`

This is the honest entering-game source. The plumbing mirrors the existing PPA path **exactly**:
1. In `enrich._build_running_index`, build a second dict `adv[(game_id, team)] = {...selected fields...}` from `advanced_game_stats_{season}.json` (same shape as the existing `ppa` dict built from `ppa_games_{season}.json`, `enrich.py:120-132`).
2. Pass it into `compute_running_stats(games, ppa=..., adv=..., start_dates=...)` as a new keyword arg (mirrors `ppa`).
3. In `compute_running_stats`, accumulate running sums/counts of each advanced field over **strictly-prior** games (identical loop structure to the existing `ppa_off_sum`/`ppa_off_count`), writing entering-game averages into the per-`(game_id, team)` stats dict.
4. Add `FeatureDef` rows (`source_kind="computed_running"`, `group="season_to_date"`, `team_scoped=True`, `field=<new key>`) — `enrich._lookup`'s `computed_running` branch already returns `(home_stats.get(field), away_stats.get(field))` for any field, so **no new enrich `_lookup` branch is needed**, only new registry rows + the `compute_running_stats` extension. `[VERIFIED: enrich.py:215-219]`

**Methodology choice to name explicitly (Claude's discretion, do not silently pick):** accumulate as a **game-average** (parity with the existing PPA to-date, simplest, mirrors `test_running_ppa_is_average_of_prior_games_only`) vs a **play-weighted** average (`advanced_game_stats` carries `plays`/`drives` counts, arguably more correct). Recommend **game-average** for parity and testability; note the play-weighted option in the plan.

**Do NOT** source D-03 from `adjusted_team_season` or `sp_*` — those are full-season aggregates (one row per team-year); using them pre-game bakes in the whole season including the game's own result → lookahead. `[VERIFIED: on-disk — adjusted_team_season is season-level, 131 rows/year keyed team+year]`

### D-04: Recruiting / talent — largely ALREADY WIRED

The registry **already contains** these preseason team-season features (`features.py:79-133`): `returning_ppa`, `returning_usage` (from `returning_production`), `team_talent` (from `talent`), `recruiting_rank`, `recruiting_points` (from `recruiting_teams`). `[VERIFIED: features.py]` This materially cuts D-04 scope — much of it is done.

Remaining D-04 opportunities (optional): none strictly required. If adding, the only additional genuinely-preseason ratings are *projected* preseason SP+/FPI (a different, forward-looking value than the season-final `sp_*`/`fpi_*` on disk). The on-disk `sp_*`/`fpi_*` are season-final = lookahead; do not wire them as pregame.

**Coverage gap to note:** `talent_2012/2013/2014.json` are **empty (2 bytes)** → `team_talent` is null for those seasons. Fails closed (null features never match, per `feature_ok` null-fails-closed), so safe but thin. `adjusted_player_passing_2012.json` is also empty. `[VERIFIED: on-disk]`

### D-05: Player-level → team-aggregated (overlap warning)

`adjusted_player_passing/rushing_{season}.json` is **season-total** per player: `{athleteId, athleteName, team, position, plays, wepa, year}`. `[VERIFIED: on-disk, 183 rows for 2015]`

**No-lookahead trap:** aggregating the **same season's** player wepa to team level and using it pre-game = lookahead (it's a whole-season total including the game being bet). To stay pre-game, aggregate the **prior** season's player wepa to the current team-season (last year's production is known at season start). `[VERIFIED: reasoning from data shape + running_stats convention]`

**Overlap warning:** prior-season aggregated passing production conceptually **duplicates** the already-wired `returning_ppa`/`returning_usage` and ignores roster turnover (a returning-production endpoint already models "who's back"). Flag to planner: D-05 may be redundant with existing features. If built at all, frame it as a distinct signal (e.g. prior-season *team* offensive wepa, not returning-player-weighted) and tag clearly. Given the overlap and D-05's "optional-ish" framing, **defer or minimize** is a defensible plan choice.

### Per-feature plumbing table (prescriptive)

| Feature work | New `SourceKind`? | Registry row (`features.py`) | Enrich index builder | Enrich `_lookup` branch | `running_stats` change |
|--------------|-------------------|------------------------------|----------------------|-------------------------|------------------------|
| D-03 to-date advanced (each field) | **No** — reuse `computed_running` | 1 row/field, `group=season_to_date` | Extend `_build_running_index` to build `adv` dict from `advanced_game_stats_{season}.json` | **None** (existing `computed_running` branch handles any field) | **Yes** — add `adv` kwarg + accumulation loop |
| D-04 (already wired) | No | Already present | Already present (`_index_team_season_file`) | Already present | None |
| D-04 (optional new preseason rating) | Reuse `raw_team_season` + `source_file` | 1 row/field | Reuse `_index_team_season_file` with a new `source_file` name | Existing `_lookup_team_scoped` `raw_team_season` branch | None |
| D-05 (if built) | Likely new (e.g. `raw_player_agg`) OR reuse `raw_team_season` via a precomputed team-aggregate file | 1 row | New index builder aggregating prior-season players → `(team, season)` | New branch in `_lookup_team_scoped` (or reuse `raw_team_season`) | None |

## Architecture Patterns

### System Architecture Diagram

```
                        DATA-01 (depth)                         DATA-02 (breadth)
                        ===============                         =================

  CFBD BettingApi ──get_lines(year)──┐              advanced_game_stats_{season}.json  (per game/team)
  CFBD GamesApi   ──get_games(year)──┤                         │
                                     ▼                         ▼  (D-03: extend index)
                    fetch_games_and_lines(seasons)   enrich._build_running_index ──ppa dict──┐
                                     │                         │  ──adv dict (NEW)──────────┤
                                     ▼                         ▼                            ▼
                    data/raw/{games,lines}_{season}.json   compute_running_stats(games, ppa, adv, start_dates)
                                     │                         │  (strictly-prior accumulation, entering-game)
                                     ▼                         ▼
              normalize_games ──_select_line (require usable line, D-02)──► drops line-less 2012 games
                                     │                         │
                                     ▼                         ▼
                    data/processed/games.csv          (game_id, team) → {win_pct, ppa_off, adv_* ...}
                                     │                         │
   talent/recruiting_{season}.json  │   adjusted_player_*_{season}.json (prior season, D-05)
   (D-04, mostly wired)             ▼                         ▼
                    enrich_games ──apply FEATURE_REGISTRY rows──► data/processed/features.json
                                     │                              (_meta.registry_version changes, D-07)
                                     ▼
                    web.py loads features.json + games.csv ──► filter UI auto-renders new registry rows
                                     (stale-sidecar warning until enrich rebuild)
```

### Pattern 1: To-date accumulation (the D-03 template)
**What:** For each team-season, iterate games in start-date order; write entering-game stats *before* folding in the current game's result.
**When to use:** Any metric with a per-game source that must be pre-game.
**Example:**
```python
# Source: cfb_system_maker/running_stats.py:31-40 (existing PPA path — mirror it for advanced stats)
for _sort_key, game_id, game, side in entries:
    stats[(game_id, team)] = {
        "ppa_off": round(ppa_off_sum / ppa_off_count, 4) if ppa_off_count else None,
        # NEW: "adv_success_off": round(sr_sum / sr_count, 4) if sr_count else None,
        ...
    }
    # ...THEN accumulate this game's values into the running sums (never before the write)
```

### Pattern 2: One registry row per feature; new to-date fields need no new enrich branch
**What:** `computed_running` `_lookup` already returns `(home_stats.get(field), away_stats.get(field))` for any field name.
**Example:**
```python
# Source: cfb_system_maker/features.py:147-151 — add rows analogous to these
FeatureDef("running_success_off", "Off Success Rate (to date)", "season_to_date",
           "computed_running", "adv_success_off", "game_id", "numeric", team_scoped=True),
```

### Anti-Patterns to Avoid
- **Sourcing to-date advanced stats from `adjusted_team_season`/`sp_*`/`fpi_*`.** Season aggregates → lookahead. Use per-game `advanced_game_stats`.
- **Aggregating same-season player wepa for pre-game use.** Whole-season total = lookahead. Use prior season.
- **Backfilling game/line data via `scrapers.py`.** It writes files `build`/`backtest` ignore. Use `fetch`.
- **Folding the current game's result into its own entering stats.** The write must precede the accumulate (see Pattern 1).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Entering-game accumulation | New per-feature loop | Extend `compute_running_stats` (add a dict kwarg like `ppa`) | The strictly-prior, start-date-ordered, season-reset logic is already correct and tested |
| Season backfill loop | New scraper | `fetch --season <list>` | Already loops seasons; writes the exact files `build` consumes |
| Line-less-game filtering | New guard | `normalize._select_line` (unchanged) | D-02 behavior already drops games with no usable line |
| Registry version tracking | New hash | `features.registry_version()` | Already hashes sorted keys; drives the stale-sidecar warning |
| Team-season joins | New join code | `enrich._index_team_season_file` + `_lookup_team_scoped` | Existing `raw_team_season` + `source_file` pattern handles talent/recruiting/returning |

**Key insight:** Almost everything this phase needs already exists as a pattern with one representative instance. The work is *replicating* an existing pattern (PPA to-date → advanced to-date; talent join → new preseason join), not inventing mechanism.

## Runtime State Inventory

Not a rename/refactor/migration phase — this section is scoped to those. The one migration-like concern is the enrich rebuild:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored/derived data | `data/processed/features.json` (sidecar) must be regenerated after registry changes; `_meta.registry_version` changes (D-07) | Run `enrich` after feature additions; web UI shows stale-sidecar warning until then |
| Built game data | `data/processed/games.csv` (2013–2025) — only changes if DATA-01 probe finds new pre-2013 lines | Re-run `build` then `enrich` only if backfill adds seasons |
| Vendored client | `cfbd-python/` clone is **empty** in current working copy | Restore clone before any live fetch/probe task |
| Secrets/env | CFBD token via `find_cfbd_token` (`env.env`) — used only if live fetch runs | None (do not log/commit `env.env`) |
| Build artifacts | None affected | — |

## Common Pitfalls

### Pitfall 1: Silent lookahead via season-aggregate stats
**What goes wrong:** Wiring SP+/`adjusted_team_season` success rate directly as a pregame feature.
**Why it happens:** They look like "team quality" features and are convenient (one row per team-year).
**How to avoid:** Only per-game-sourced metrics can be to-date. Season ratings are `result_lookahead` or prior-season-only.
**Warning signs:** A new feature's value for a team is identical across all that team's games in a season → it's a season aggregate, not entering-game.

### Pitfall 2: Same-season player aggregation (D-05)
**What goes wrong:** Aggregating current-season player wepa to team and filtering pre-game.
**How to avoid:** Use prior-season aggregation; or defer D-05 given overlap with `returning_production`.
**Warning signs:** Feature correlates suspiciously with game outcome in tests.

### Pitfall 3: Expecting pre-2013 backtest rows
**What goes wrong:** SC-1 assumes pre-2013 seasons return results; CFBD has no pre-2013 lines.
**How to avoid:** Run the live probe first; escalate SC-1 to the user before building toward an impossible criterion.

### Pitfall 4: Empty early-season source files
**What goes wrong:** `talent_2012/2013/2014` and `adjusted_player_*_2012` are empty (2 bytes) → null features for those years.
**How to avoid:** Expect nulls (fail closed, safe). Don't treat empty files as fetch errors.

## Code Examples

### Extending compute_running_stats with an `adv` dict (D-03)
```python
# Pattern mirrors the existing `ppa` arg (running_stats.py:8-13, 59-67).
def compute_running_stats(games, *, ppa=None, adv=None, start_dates=None):
    adv = adv or {}
    # ...inside the per-game loop, BEFORE folding current game:
    #   write entering averages: sr_sum/sr_count if sr_count else None
    # ...AFTER: fold this game's advanced_game_stats values into running sums
```

### Building the adv index in enrich (D-03)
```python
# Source pattern: enrich.py:120-132 (existing ppa index) applied to advanced_game_stats
adv = {}
for season in seasons:
    path = data_dir / "raw" / f"advanced_game_stats_{season}.json"
    if not path.exists():
        continue
    for row in json.loads(path.read_text(encoding="utf-8")):
        gid, team = row.get("gameId"), row.get("team")
        off, deff = row.get("offense") or {}, row.get("defense") or {}
        adv[(int(gid), str(team))] = {
            "success_off": (off.get("successRate") or {}).get("total"),
            "explosiveness_off": off.get("explosiveness"),
            "success_def": (deff.get("successRate") or {}).get("total"),
            # ...select the fields you register
        }
```

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| PPA-only to-date | Add success rate / explosiveness / EPA to-date from per-game advanced stats | Richer entering-game filters, same no-lookahead engine |
| Talent/recruiting already wired | (unchanged) | D-04 mostly complete |

**Deprecated/outdated:** none relevant.

## Validation Architecture

> `nyquist_validation: true` in config — this section is required. `test_running_stats.py` and `test_features.py` are the exact templates; the construct-`GameRecord`-and-assert convention covers everything below.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (`pytest.ini`, `testpaths=tests`) |
| Config file | `pytest.ini` |
| Quick run command | `python -m pytest tests/test_running_stats.py tests/test_features.py -x` |
| Full suite command | `python -m pytest` |

### Phase Requirements → Test Map
| Req | Behavior | Test type | Command | Exists? |
|-----|----------|-----------|---------|---------|
| DATA-01 | 2012 (line-less) contributes 0 rows | unit (normalize) | `pytest tests/test_normalize.py -x` | ⚠️ add case: games with empty `lines` → 0 records |
| DATA-01 | No hardcoded floor; season filter data-driven | unit (web/backtest) | `pytest tests/test_web.py -x` | ✅ existing season-filter tests |
| DATA-01 | Live line-coverage probe (floor confirmation) | manual/script | probe script (needs restored `cfbd-python`, token) | ❌ Wave 0 — probe task |
| DATA-02 D-03 | New to-date advanced field excludes game's own result | unit | `pytest tests/test_running_stats.py -x` | ⚠️ extend: add `adv` analog of `test_running_ppa_is_average_of_prior_games_only` (the `9.99`-leak pattern) |
| DATA-02 D-03 | First game of season → None; season reset | unit | `pytest tests/test_running_stats.py -x` | ⚠️ extend for new fields |
| DATA-02 D-03 | start_date ordering respected for new fields | unit | `pytest tests/test_running_stats.py -x` | ⚠️ extend |
| DATA-02 | New registry rows valid group/source_kind; keys unique | unit | `pytest tests/test_features.py -x` | ⚠️ extend `RUNNING_KEYS`/group checks |
| D-06/D-07 | `registry_version()` changes when registry changes | unit | `pytest tests/test_features.py -x` or `test_enrich.py` | ⚠️ add: assert version differs from baseline after adding rows |
| DATA-02 | enrich surfaces new field home/away from computed_running | unit | `pytest tests/test_enrich.py -x` | ⚠️ extend |

### Key correctness properties (invariants to assert)
1. **No-lookahead for every new to-date field:** the current game's own advanced value never appears in its entering stats. Reuse the `9.99` sentinel pattern from `test_running_ppa_is_average_of_prior_games_only` per new field.
2. **First-game emptiness:** entering advanced stats are `None` when no prior game exists (mirrors `test_first_game_of_season_has_zero_history`).
3. **Season reset:** prior-season games don't leak into a new season (mirrors `test_seasons_reset`).
4. **Ordering:** start_date overrides week order (mirrors `test_start_dates_override_week_order`).
5. **Line-floor behavior:** a game whose `lines` is empty yields no `GameRecord` (add to `test_normalize.py`).
6. **registry_version change:** adding rows changes the 12-char hash (D-07 stale-sidecar contract).
7. **Preseason correctness (if D-05 built):** feature value derives from *prior* season only.

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_running_stats.py tests/test_features.py -x`
- **Per wave merge:** `python -m pytest`
- **Phase gate:** full suite green before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] Extend `tests/test_running_stats.py` — no-lookahead / first-game / reset / ordering per new advanced field.
- [ ] Extend `tests/test_features.py` — new registry rows valid + `registry_version` change assertion.
- [ ] Extend `tests/test_normalize.py` — empty-`lines` game → 0 records (DATA-01 floor behavior).
- [ ] Add DATA-01 live-probe script (requires restored `cfbd-python` + token).
- [ ] (If D-05) new `tests/test_enrich.py` case for prior-season player aggregation.

## Security Domain

> `security_enforcement: true`, ASVS L1. This is a **local single-user CLI/Flask tool** operating on already-downloaded data; most ASVS categories are N/A. The two live surfaces are the CFBD token and untrusted API JSON.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | No user auth; local tool |
| V3 Session Management | no | No sessions |
| V4 Access Control | no | Single local user |
| V5 Input Validation | yes | New fetch/enrich code parses untrusted CFBD JSON — use existing `_first`/`get_nested`/None-safe patterns; never `eval`; treat all fields as optional |
| V6 Cryptography | no | No crypto in scope |
| V7 Secrets | yes | CFBD token via `find_cfbd_token` only; never log/echo/commit `env.env` (CLAUDE.md) |

### Known Threat Patterns
| Pattern | STRIDE | Mitigation |
|---------|--------|------------|
| Token leakage in logs/commits | Information Disclosure | Resolve via `find_cfbd_token`; keep `env.env` gitignored; no token in print/probe output |
| Malformed API JSON (missing/typed fields) | Tampering/DoS | None-safe access (existing `_field_value`, `_first`); fail closed |

## Sources

### Primary (HIGH confidence)
- On-disk data probes (2026-06-13 snapshot): `lines_{2012,2013}.json`, `games.csv`, `features.json`, `advanced_game_stats_2015.json`, `adjusted_team_season_2015.json`, `sp_2015.json`, `adjusted_player_passing_2015.json` — counts and structures cited inline.
- Source read: `cfbd_client.py`, `normalize.py`, `running_stats.py`, `enrich.py`, `features.py`, `cli.py` (grep), `web.py`/`backtest.py` (grep for floor), `tests/test_running_stats.py`, `tests/test_features.py`.
- `CLAUDE.md` — pipeline stages, spread-sign convention, source_kind list, no-lookahead convention.

### Secondary (MEDIUM confidence)
- `.planning/phases/03-data-depth-breadth/03-CONTEXT.md` — D-01..D-07 decisions.

### Tertiary (LOW confidence)
- WebSearch on CFBD betting-line coverage — no authoritative floor year found; cfbfastR betting examples use 2018 (not a floor).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | 2013 is the hard CFBD betting-line floor (nothing usable earlier) | DATA-01 | If CFBD has since backfilled pre-2013 lines, a real backfill becomes possible and SC-1 becomes satisfiable. **Mitigation: the DATA-01 live probe resolves this.** On-disk evidence is dated 2026-06-13. |
| A2 | Game-average (not play-weighted) accumulation for D-03 advanced stats | DATA-02 D-03 | Wrong choice = slightly less accurate features; both are valid. Named for planner decision. |
| A3 | D-05 prior-season player aggregation is redundant with existing `returning_production` | DATA-02 D-05 | If distinct enough, D-05 adds value; if redundant, wasted work. Flag for planner to decide/defer. |

## Open Questions (RESOLVED)

1. **SC-1 vs the 2013 floor — ✅ RESOLVED 2026-07-17 (user: "Reframe to confirmed floor").** Accepted 2013 as the CFBD line floor; SC-1 reframed in ROADMAP.md and CONTEXT D-01 amended; DATA-01 planned as probe + guard + doc + 2012-zero-rows test (plans 03-02, 03-03). Original escalation retained below for the record.
   - What we know: CFBD betting lines start 2013 (on-disk evidence; live probe will confirm). Built data already 2013–2025.
   - What's unclear: Success Criterion 1 requires "a season filter earlier than 2013 yields non-empty results" — unsatisfiable if 2013 is the floor.
   - Recommendation: escalate to user. Options: (a) reinterpret SC-1 as "the tool correctly handles the earliest line-covered season and 2012 cleanly contributes 0 rows"; (b) accept DATA-01 as verification-only and mark SC-1 as met-by-documentation; (c) source pre-2013 lines from a non-CFBD provider (out of scope — Action Network deferred). Do not build toward SC-1 as literally worded until resolved.

2. **D-05 scope — ✅ RESOLVED (planned as minimal distinct signal in 03-04).** D-05 is a locked CONTEXT decision, so "overlaps `returning_production`" is not a sanctioned defer reason; implemented as the minimal *distinct* prior-season team signal (raw prior-season team offensive wEPA, `prior_off_wepa`), no-lookahead via prior-season aggregation only.
   - What we know: overlaps `returning_production`; only no-lookahead via prior season.
   - Recommendation: minimize or defer unless a distinct prior-season *team* signal is wanted.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| On-disk raw JSON (2012–2025) | DATA-02 (all sources) | ✓ | — | — |
| `cfbd-python` vendored client | DATA-01 live probe / any live fetch | ✗ (dir empty) | pydantic v1 | Restore clone before probe; enrich/registry work needs none |
| CFBD API token (`env.env`) | Live probe/fetch only | ✓ (`env.env` present) | — | — |
| pytest | Validation | ✓ | per requirements.txt | — |

**Missing dependencies with fallback:** vendored `cfbd-python` clone is empty — required only for live fetch/probe; restore via `git clone https://github.com/CFBD/cfbd-python`. All DATA-02 (enrich/registry/test) work proceeds on on-disk JSON without it.

## Metadata

**Confidence breakdown:**
- DATA-01 floor: HIGH (on-disk empirical) — one live probe upgrades A1 from dated to VERIFIED.
- DATA-02 sources & plumbing: HIGH — all source files inspected on disk; enrich/running_stats/features read in full.
- No-lookahead classification: HIGH — grounded in data shape (per-game vs season-level) + existing convention.
- SC-1 conflict: HIGH — arithmetic certainty given 2013 floor.

**Research date:** 2026-07-17
**Valid until:** 2026-08-16 (stable domain; DATA-01 A1 should be re-probed live before build)
