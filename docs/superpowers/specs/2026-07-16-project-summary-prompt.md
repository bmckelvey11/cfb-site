# cfb-site — Project Summary (prompt format)

Paste into a fresh session for full context.

---

**Project:** `C:\Users\mckel\dev\cfb-site` — `cfb_system_maker`, Python CLI + Flask tool that backtests college football betting systems using CollegeFootballData API data (games + betting lines → `data/processed/games.csv` → filter-based "systems" → hit rate/profit/ROI).

**What I'm trying to accomplish:**
Extend the web app so betting systems can filter on the broader CFBD dataset already scraped to `data/raw/` (REST, 61 endpoints) and `data/graphql/` (Hasura tables) — not just the 12 core fields in `games.csv`. Fields include: weather (temp, wind, precip, condition, indoors), betting-line extras (opening spread/total, moneylines), pregame Elo/win-prob, neutral site, conference game, returning production, team talent, recruiting, coach/venue/conference metadata.

**Key design decisions (already made — do not relitigate):**
1. **No lookahead bias.** Team-season stats must be as-of-game. Season-final snapshots (FPI, SP+, season Elo/records/ATS/PPA, adjustedTeamMetrics) were deferred until a running/as-of-week compute layer existed. Phase 1 used only: genuinely pregame per-game fields, preseason-fixed team stats (returning production, talent, recruiting), and metadata. Post-game outcome fields (havoc rates, attendance) allowed but fenced in a labeled "result stats (lookahead — analysis only)" group.
2. **Generic feature layer, not hardcoded fields.** Declarative registry (`features.py`) — one entry per feature (key, label, group, source, join, control, team_scoped, validate, null_policy, lookahead_safe). `enrich` CLI step joins registry sources to games → `data/processed/features.json` sidecar keyed by game_id with `_meta` (registry_version, game_count). `GameRecord` unchanged; `SystemFilter` gains `feature_filters: tuple[FeatureFilter, ...]` where `FeatureFilter(key, perspective, op, value)`, ops: in/eq/gte/lte. Adding a field = one registry row, zero new filter code.
3. **Side perspectives.** Team-scoped values stored as `home_*`/`away_*`. Spread bets: home/away/bet_side/opponent. Total bets: home/away/either. Saved systems store base key + perspective (not resolved) so bet-side round-trips.
4. **Works for both spread and over/under bets** — same filter loop, `bet_type`-aware perspective resolution.
5. **System-quality stats** (`SystemStats` on `BacktestResult`, pure stdlib): break-even rate from odds, edge, Wilson 95% CI, one-sided z/p vs break-even, ROI std error/t-stat, max win/loss streaks, low_sample flag (<30 decided). No Kelly, no CLV (deferred).
6. **Save/load systems**: `data/systems/{name}.json`, web save-as + load dropdown, CLI `backtest --save/--load`.
7. **Cuts (rejected as YAGNI):** LOOKAHEAD_POLICY.md + CI script, `--incremental` enrich, tags, duplicate_system, min/max odds stats, avg/sum perspectives, `between` op, hypothesis dep.

**Docs:**
- Spec: `docs/superpowers/specs/2026-06-13-web-feature-filters-design.md` (Implemented 2026-06-13)
- Plan: `docs/superpowers/plans/2026-06-13-web-feature-filters.md` (Complete)
- Phase 2 plan: `docs/superpowers/plans/2026-07-16-web-app-phase-2.md`

**Current state (2026-07-16):**
- Phase 1 done: registry, enrich, matching, SystemStats, save/load, web UI (dynamic filter rows with lookahead fence, dry-run match count, filter coverage %, stats panel, stale-registry warning).
- Phase 2 partially done: **running/as-of-week stats layer implemented** (`running_stats.py`, source kind `computed_running` — entering-game values from strictly-prior same-season games, first game → games_played=0/None, fail closed). Compare-saved-systems view (`/compare`) implemented. Per-filter feature coverage %, max win/loss streaks, wind direction + REST pregame win prob features added.
- Verify: `python -m pytest`. Rebuild: `build` → `enrich` → `web`.

**Still open (phase 2+):** Kelly staking, CLV, season-snapshot fields via weekly API snapshots where available, CLI dynamic filter builder, heavy GraphQL gamePlayerStat pull (built, held until base data downloaded).
