# Bet Labs Parity for cfb-site

## What This Is

`cfb_system_maker` is a Python CLI + Flask tool that backtests college football betting systems against 2013-2025 CFBD data (13k games, enriched with running-stats features). It already has the backtest engine, feature registry, stats validation (Wilson CI, permutation p, holdout split), and a save/load/compare web UI. This project reshapes the web UI to function like Sports Insights Bet Labs — the product this whole feature set is modeled on — and grows the underlying data/feature registry to support it.

## Core Value

A saved system's main page reads like a Bet Labs system editor (stat chips, cumulative money-won graph, plain-English active filters) and configuring any filter opens a live popup — slider or value table, per-value Record/ROI/Money, before you commit — instead of static inline form fields.

## Requirements

### Validated

- ✓ `SystemFilter` + `run_backtest` filter-based backtest engine — existing
- ✓ `FEATURE_REGISTRY` (pregame / season_to_date / team_preseason / metadata / lookahead groups), no-lookahead running stats — existing
- ✓ Save / load / compare saved systems (`/save`, `?load_system=`, `/compare`) — existing
- ✓ Statistical validation beyond Bet Labs: Wilson CI, z-score, permutation p-value, ROI t-stat, per-season breakdown + sign consistency, holdout-season split — existing
- ✓ Data pipeline (fetch → build → enrich) run for 2013–2025, 12,965 games, `features.json` built — existing
- ✓ `_range_chart` money-won-by-line SVG chart — existing
- ✓ Cumulative "Money Won Over Time" graph — Phase 1
- ✓ Stat-chip header restyle: Record / Margin / Money Won / ROI / Grade (Grade chip is a placeholder — composite grade computation lands in Phase 2) — Phase 1
- ✓ Plain-English active-filter sentences (`describe(system)`) with per-row remove links — Phase 1
- ✓ Tabbed workspace split: Results Graph | Past Matches (Current Matches tab remains future work, see Active) — Phase 1
- ✓ `theory` free-text field on `SavedSystem` — Phase 1
- ✓ Fade System toggle (`fade: bool` on `SystemFilter`, flips graded side in grading only, matching untouched) — Phase 2
- ✓ System Grade letter (composite: Wilson-margin sample size vs significance, ROI z-score, season sign-consistency, permutation p, filter-count / in-list-value-count overfitting penalties) — Phase 2

### Active

- [ ] Current Matches tab: evaluate upcoming (unplayed, lines-only) games against saved systems; show matched-filter details per game
- [ ] Filter popup modal: replaces inline sidebar `<details>` editing. Title bar with live Record/Money Won/ROI chips that recompute as controls move. Numeric filters: dual-handle slider + BETWEEN inputs + per-value money-won dot chart. Categorical/list filters: searchable sortable table (value | Record | ROI | Money). About Filter panel with `FeatureDef.description` text. Save Filter commits.
- [ ] `GET /filter-detail` endpoint: per-value Record/ROI/Money for a candidate feature key, current system's other filters applied, candidate excluded
- [ ] `GET /api/backtest` JSON endpoint for live chip recalculation without full page reload
- [ ] My Systems dashboard (`/` becomes dashboard; editor moves to `/system`): saved-system table with sparkline, Create System panel, 2-3 bundled example systems
- [ ] Alternate-line ("teaser") record popover off the Record chip
- [ ] Data: backfill history further back than 2013 where CFBD coverage allows
- [ ] Data: wire more CFBD REST/GraphQL endpoints (weather, player/coach, advanced stats, public-betting where available) into `FEATURE_REGISTRY` — grows the filter categories toward Bet Labs' Team Info / Line Info / Time Period / Matchup Info / Streaks / Stats / Player-Coach / Weather groups

### Out of Scope

- Think Tank (multi-user system sharing, copy counts) — single-user local tool, no user base to share with
- Widget/embed, Live Help chat — no external audience for embeds; Live Help is a support feature, not a betting tool
- Moneyline wager type (third `bet_type` beyond spread/total) — add later once spread/total UX (popup modals, dashboard) is settled
- Public betting-percentage filters — CFBD has no bet-share data source; would need a different provider (Action Network client exists as a future option, not wired to the registry today)
- Hide Duplicates toggle — only matters once a system can match both sides of one game (e.g. `bet_side`-identifying systems); current side-fixed systems can't self-collide, so this waits until that mechanism exists

## Context

- Bet Labs (Sports Insights) documentation reviewed in full: `docs/sports-insights-systems-combined-guide.md` (26 articles, 13 video walkthroughs, 21 screenshots) plus all 34 screenshots examined directly — see `docs/bet-labs-parity-plan.md` for the complete GUI inventory (dashboard, system editor anatomy, filter popup modal anatomy, Grade breakdown, Think Tank).
- `docs/bet-labs-parity-plan.md` is the source gap-analysis doc this project executes — its phase numbering (Phase 1/2/3/4) maps loosely to roadmap phases but GSD roadmapping may resequence.
- Project is brownfield: `docs/PROJECT_MAP.md` (generated same day as this project) is the standing architecture reference — read that instead of re-mapping.
- Key architectural note from CLAUDE.md: `GameRecord.spread` is always the home spread; frozen dataclasses in `models.py`; CSV field order in `GameRecord` is the storage schema (changing it means touching `storage.py` read/write); `cfbd-python/` is a vendored dependency, never edited.
- Existing test pattern: construct `GameRecord`/`SystemFilter` directly, assert on result fields (`tests/` mirrors `cfb_system_maker/` modules 1:1).
- Companion roadmap doc `docs/superpowers/plans/2026-07-16-next-steps-roadmap.md` ranked data-download as item 1 — that item is now satisfied (13k games, 2013-2025, enriched); this project's data-extension requirements go further (backfill + new endpoints), not repeat it.

## Constraints

- **Tech stack**: Python + Flask + vanilla JS/CSS, no frontend framework — popup modals must be built with plain JS/fetch, consistent with existing `index.html`/`compare.html` pattern.
- **No lookahead**: any new registry feature must be computable pre-game (entering-game state only) or explicitly tagged into the `result_lookahead` group and visually quarantined, per existing `running_stats.py` convention.
- **Storage backward compatibility**: `SavedSystem` JSON changes (e.g. adding `theory`, `fade`) must default gracefully for systems saved before the field existed.
- **CSV schema stability**: `GameRecord` field order is the CSV read/write contract — any new game-level field needs a deliberate `storage.py` migration, not an ad hoc column add.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Keep current main-page layout (sidebar + workspace); filter configuration moves into popup modals rather than replacing the whole page | User explicitly likes the current main-page GUI; the popup-modal interaction is the specific gap vs Bet Labs | ✓ Validated — Phase 1 shipped stat chips/graph/filter sentences/theory into the existing layout, no page restructure |
| Whole bet-labs-parity-plan in scope (not just the popup modal) | User chose broad scope over narrow slice when asked | — Pending |
| Data extension (backfill + more CFBD/GraphQL endpoints into registry) included in this project | User wants both deeper history and broader feature coverage, not just UI work | — Pending |
| Hide Duplicates deferred | Only relevant once systems can match both sides of a single game; not true of side-fixed systems today | — Pending |
| Query-param `?tab=` full-page reload for Results Graph / Past Matches split (not client-side JS tabs) | Simpler, matches existing form-driven page-reload pattern; avoids introducing client-side state management | ✓ Implemented — Phase 1 |
| `theory` field bundled into existing sidebar save form (not a separate save action) | Matches Bet Labs' single-form system editor; avoids a second persistence path | ✓ Implemented — Phase 1 |
| `describe()`'s known-key-but-unrenderable-`(op,control)`-combo gap accepted as risk rather than fixed in Phase 1 | Low practical exploitability (requires hand-crafted query params), display/removal-affordance gap only, no data exposure — see `01-SECURITY.md` T-01-03 | ✓ Accepted — Phase 1, revisit if `FEATURE_REGISTRY` op/control combos grow |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-07-17 after Phase 2*
