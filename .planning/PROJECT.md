# Bet Labs Parity for cfb-site

## What This Is

`cfb_system_maker` is a Python CLI + Flask tool that backtests college football betting systems against 2013-2025 CFBD data (13k games, enriched with running-stats features). As of **v1.0 (shipped 2026-07-20)** its web UI reads and behaves like Sports Insights Bet Labs: a stat-chip system editor with a money-won graph and plain-English filters, a live filter-popup exploration flow, and a My Systems dashboard that evaluates saved systems against upcoming games with matched-filter details. The backtest engine, feature registry, and statistical validation (Wilson CI, permutation p, holdout split) underneath it all predate this work.

## Current State

**Shipped v1.0 — Bet Labs Parity** (2026-07-20): 5 phases, 21 plans, ~11k Python LOC, 307 tests passing. All requirements code-verified; two live-in-season checks deferred to season start. Teaser records (DASH-04) descoped.

**In progress: v1.1 Season Readiness** — closes v1.0's deferred items ahead of the 2026-08-29 season start: merge the `fix/web-app-review-2026-08-26` review branch, run the two deferred live in-season verifications, close two accepted risks that are now reachable/due (`describe()` silent filter drop, Hide Duplicates), and ship the one surviving lead from a week of statistical analysis (neutral-site + indoor unders) as a bundled example system. Full context: [docs/roadmap-v2-2026-08.md](../docs/roadmap-v2-2026-08.md) §2, informed by a competitive survey of 11 betting system-builder tools (§1).

## Current Milestone: v1.1 Season Readiness

**Goal:** Close out v1.0's deferred verifications and accepted risks, and merge in-flight fixes, before the 2026-08-29 season start.

**Target features:**
- Merge `fix/web-app-review-2026-08-26` (26 review-fix commits) to master
- Commit the 7 uncommitted analysis docs; fix STATE.md quick-task bookkeeping drift
- Live in-season verification: Current Matches shows real unplayed games with posted lines; feature-filtered systems match via season-to-date stats
- Hide Duplicates toggle (drop a game when one `game_id` yields two candidate bets — now reachable since total systems match either side)
- Close T-01-03: `describe()` must never silently drop an active filter's sentence while `feature_ok()` still applies it
- Bundle a neutral-site + indoor unders example system (63.3% over 109 games, p=0.014; all three features — `neutralSite`, `gameIndoors`, `venue_dome` — already in the registry)

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
- ✓ To-date advanced features (Off/Def Success Rate, Off/Def Explosiveness) + prior-season offensive wEPA, all entering-game / no-lookahead — Phase 3
- ✓ 2013 CFBD betting-line floor confirmed against the live API (no usable pre-2013 lines to backfill) — Phase 3
- ✓ Filter popup modal: live Record/Money Won/ROI chips, numeric dual-handle + BETWEEN + money chart, categorical searchable/sortable value table, About Filter, Edit-from-sentence, 250ms debounced live path — Phase 4
- ✓ `GET /filter-detail` per-value table endpoint and `GET /api/backtest` live-chip endpoint — Phase 4
- ✓ My Systems dashboard (`/` = dashboard, editor at `/system`) with per-season figures from one cached backtest and sparklines — Phase 5
- ✓ Three bundled read-only example systems on their own Example Systems tab, with Copy to My Systems — Phase 5
- ✓ `upcoming` CLI pipeline + Current Matches panel: upcoming (unplayed, lines-only) games matched against saved systems, fade-correct play text, reused `describe()` filter details — Phase 5

### Active

*(none — v1.0 shipped; next milestone requirements defined via `/gsd-new-milestone`)*

**Deferred out of v1.0:**
- [ ] Alternate-line ("teaser") record popover off the Record chip (DASH-04) — descoped 2026-07-20; partial decisions in the v1.0 Phase 5 context archive
- [ ] Live in-season verification of Current Matches (real upcoming games) — cannot run until the season starts (~2026-08-29)

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
| Whole bet-labs-parity-plan in scope (not just the popup modal) | User chose broad scope over narrow slice when asked | ✓ Delivered — v1.0 shipped all five phases (editor, integrity, data, modal, dashboard) |
| Data extension (backfill + more CFBD/GraphQL endpoints into registry) included in this project | User wants both deeper history and broader feature coverage, not just UI work | ✓ Delivered — Phase 3 (2013 floor confirmed; success-rate/explosiveness/wEPA features added) |
| Hide Duplicates deferred | Only relevant once systems can match both sides of a single game; not true of side-fixed systems today | — Pending (still out of scope) |
| Teaser / alternate-line records (DASH-04) descoped from v1.0 during Phase 5 discussion | Two pricing questions unresolved (teasers don't price at -110; totals direction); shelved to avoid guessing | ✓ Deferred — 2026-07-20, partial decisions preserved in Phase 5 context archive |
| Upcoming games get a separate `upcoming.csv`, not a `games.csv` column | `GameRecord` field order is the CSV contract; a separate file avoids a migration and makes it structurally impossible to grade an unplayed game | ✓ Implemented — Phase 5 (D-01) |
| Current Matches matches but never grades (`require_played=False` flag) | Unplayed games have no result; extend the one authoritative matcher with a flag rather than fork a second one | ✓ Implemented — Phase 5 (D-18) |
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
*Last updated: 2026-07-20 after v1.0 milestone*
