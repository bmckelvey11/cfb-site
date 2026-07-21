# Phase 3: Data Depth & Breadth - Context

**Gathered:** 2026-07-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Grow the **data** under the tool, not the UI. Two axes:

1. **Depth** — extend historical game/line coverage further back than the current 2013 floor, as far back as CFBD betting-line coverage allows (DATA-01).
2. **Breadth** — wire additional CFBD REST/GraphQL endpoints into `FEATURE_REGISTRY` as new filterable features, following the existing no-lookahead / entering-game convention (DATA-02).

No web-UI work in this phase. Success is measured by: a pre-2013 season filter yields non-empty backtest results; new filter categories appear; new features pass the existing construct-and-assert test pattern and respect no-lookahead.
</domain>

<decisions>
## Implementation Decisions

### Backfill depth (DATA-01)
- **D-01:** Backfill **as far back as CFBD betting lines allow** — not a fixed year. Research must first determine the real floor (the earliest season the CFBD `BettingApi.get_lines` consensus provider returns usable spread/total data; games exist far earlier, but lines are the binding constraint). Extend the fetch/build to that floor.
  - **RESOLVED 2026-07-17 (research + user):** The floor is **2013** — verified on disk (2012 = 805 games / **0** usable lines across all providers; games.csv already 2013–2025). SC-1 reframed accordingly. DATA-01 scope is therefore: (1) a **live line-coverage probe** sweeping ~2008–2013 against the current API (in case CFBD backfilled lines since the Jun-2026 pull) — requires the vendored `cfbd-python/` clone restored (currently empty); (2) a **floor guard + documentation** recording the confirmed floor; (3) a **test asserting 2012 contributes 0 rows** (D-02 clean behavior); (4) **backfill any pre-2013 season only if the probe returns usable lines**. No unbounded search, no non-CFBD provider (out of scope). Phase weight shifts to DATA-02 breadth.
- **D-02:** **Require a usable line** to include a game — keep the current `normalize._select_line` behavior. Backfilled seasons that have games but no usable consensus line contribute no rows. This keeps backtests clean; it means the practical history floor equals the line-coverage floor, not the game-coverage floor. (This directly satisfies success criterion 1: a pre-2013 season filter returns non-empty results *because* those seasons have lines.)

### New endpoint breadth (DATA-02)
Registry already wires: raw_game (Elo, neutral/conference), raw_lines, raw_weather, raw_media, raw_teams, raw_venues, raw_coaches, raw_conferences, raw_pregame_wp, and computed_running (to-date PPA/win/ATS). New categories to add, in priority order:

- **D-03: Advanced team stats — entering-game (to-date) only.** SP+, success rate, explosiveness, havoc, PPA splits etc. are full-season aggregates that bake in the game's own result and later games → lookahead if used pre-game. Wire them as **running / season-to-date** features (same construction as existing `running_ppa_off/def` in `running_stats.py`), NOT raw season aggregates. Honest pre-game state only.
- **D-04: Recruiting / talent — preseason values.** Team talent composite and recruiting rankings are genuinely pre-game (set before the season), so they wire directly as `team_preseason`-style team-season features. No to-date computation needed.
- **D-05: Player-level — team-aggregated only.** Roll player stats up to team-season features (e.g. returning/aggregate passing production). **No per-game per-player fan-out** this phase — that heavy pull was deliberately deferred before and stays deferred. Prefer sourcing from player data already scraped in `data/raw/adjusted_player_*` over new heavy pulls.

### No-lookahead enforcement (constraint, not optional)
- **D-06:** Every new feature is either (a) computable from entering-game state (to-date running features, D-03), (b) genuinely preseason/pre-game (D-04), or (c) if a full-season aggregate is wired at all, it MUST be tagged into the `result_lookahead` group and visually quarantined. Verified by the existing `tests/` construct-and-assert pattern. Never fold a game's own result into its own features (`running_stats.py` convention).

### Rebuild
- **D-07:** After extending data and adding registry features, `features.json` must be regenerated over the full (extended) season range via the `enrich` step, and `features.registry_version()` will change — the web UI's stale-sidecar warning is expected until rebuild completes.

### Claude's Discretion
- Exact endpoint/method names, the running-stat accumulation math for advanced stats, and whether backfill reuses `fetch` vs `scrapers.py` are implementation choices for research/planning.
- Returning-production features were mentioned but not selected as priority — planner may include if cheap alongside D-04, otherwise defer.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` §"Phase 3: Data Depth & Breadth" — goal, 3 success criteria, DATA-01/DATA-02 mapping.
- `.planning/REQUIREMENTS.md` — DATA-01 (backfill past 2013), DATA-02 (new endpoints into registry).
- `.planning/PROJECT.md` §Constraints — no-lookahead, CSV schema stability, storage back-compat.

### Data pipeline & registry (the code this phase touches)
- `cfb_system_maker/features.py` — `FEATURE_REGISTRY`, `FeatureDef`, group/source_kind taxonomy. New features are added here.
- `cfb_system_maker/running_stats.py` — `computed_running` convention (entering-game, strictly-prior games). Template for D-03 advanced to-date stats.
- `cfb_system_maker/enrich.py` — joins registry features → `features.json`; `_meta`/registry_version sidecar. Rebuild path (D-07).
- `cfb_system_maker/normalize.py` — `_select_line` line selection; the "require a usable line" behavior D-02 preserves. `_first(...)` multi-spelling key helper for CFBD field-name drift.
- `cfb_system_maker/cfbd_client.py` — `fetch_games_and_lines` (games + lines fetch, the DATA-01 extension point).
- `cfb_system_maker/scrapers.py` — 61-endpoint registry (weather/coaches/ratings/recruiting seeds); `Endpoint` modes. Broader source path for DATA-02.
- `cfb_system_maker/graphql_client.py` — GraphQL bulk-pull (Tier 3); alternate source for bulk tables.
- `CLAUDE.md` — pipeline/architecture, spread-sign convention, source_kind list, running-stats no-lookahead notes.

### Domain reference
- `docs/bet-labs-parity-plan.md` — target Bet Labs filter groups (Stats / Player-Coach / Weather / Streaks) this breadth work grows toward.
- `docs/PROJECT_MAP.md` — standing architecture reference (read instead of re-mapping).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `running_stats.py` computed_running features: exact template for D-03 (advanced stats as entering-game to-date).
- `data/raw/adjusted_player_*_{season}.json` (2012–2025 already scraped): source for D-05 team-aggregated player features without new pulls.
- `data/raw/adjusted_team_season_*`, ratings/recruiting seeds already scraped: candidate sources for D-03/D-04, may reduce new fetching.
- `scrapers.py` season-mode endpoints + `--force`/resume: how to pull additional/earlier seasons.

### Established Patterns
- `FeatureDef(key, label, group, source_kind, field, join_key, dtype, ...)` — every new feature is one registry row.
- Frozen dataclasses; `GameRecord` field order = CSV schema (D-02 preserves it; no game-level column adds needed here — new features live in the enrich sidecar, not games.csv).
- Tests mirror modules 1:1; construct `GameRecord`/`SystemFilter`, assert on fields.

### Integration Points
- Backfill: `cfbd_client.fetch_games_and_lines` → raw → `normalize` → `games.csv`, then `enrich` → `features.json`.
- New features: `features.py` registry row (+ `running_stats.py` computation for to-date) → `enrich` rebuild.

</code_context>

<specifics>
## Specific Ideas

- Line coverage is the explicit gate on how far back history can go — frame DATA-01 research as "find the earliest season with usable lines," not "find the earliest game."
- Advanced stats must not silently become lookahead — this is the single biggest correctness risk in the phase.
</specifics>

<deferred>
## Deferred Ideas

- **Full per-player / per-game player-stat fan-out** — heavy scrape (thousands of calls), deferred again. Team-aggregation only this phase (see memory: defer-gameplayerstat-pull).
- **Full-season raw aggregate features for exploration** — only if tagged `result_lookahead`; not a priority, not required by success criteria.
- **Returning-production features** — optional stretch alongside D-04, otherwise a later phase.
- **Public betting-percentage filters** — out of scope project-wide (no CFBD source; Action Network not wired).

None of these block the phase.

</deferred>

---

*Phase: 3-Data Depth & Breadth*
*Context gathered: 2026-07-17*
