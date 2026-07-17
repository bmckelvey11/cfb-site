# Roadmap: Bet Labs Parity for cfb-site

## Overview

`cfb_system_maker` already has the backtest engine, feature registry, and a save/load/compare web UI — this roadmap reshapes that UI to read and behave like Sports Insights Bet Labs. Work starts on the system editor's main page (chips, cumulative-profit graph, plain-English filter sentences, tabs, theory field), then adds trust/integrity signal (fade toggle, composite grade), then deepens the underlying data (further history, more CFBD/GraphQL endpoints wired into the feature registry) to give the next two phases more to work with. The filter popup modal — the single biggest UX lift, replacing inline sidebar editing with a live-recalculating popup — comes next. The roadmap closes with the My Systems dashboard and Current Matches, which turn the backtester from a research tool into something checked weekly.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: System Editor Main Page** - The main page reads like a Bet Labs system editor: stat chips, cumulative money-won graph, plain-English filter sentences, tabs, and a theory field. (completed 2026-07-17)
- [x] **Phase 2: Integrity — Fade & Grade** - Users can fade a system to grade the opposite side and see a composite letter grade in the stat-chip header. (completed 2026-07-17)
- [ ] **Phase 3: Data Depth & Breadth** - Historical coverage extends further back than 2013 and more CFBD/GraphQL endpoints are wired into the feature registry as filterable features.
- [ ] **Phase 4: Filter Popup Modal** - Clicking any filter opens a live-recalculating popup (slider or value table, live Record/Money/ROI, About Filter) instead of static inline fields.
- [ ] **Phase 5: Dashboard & Current Matches** - A My Systems dashboard replaces the editor as the landing page, and saved systems are evaluated live against upcoming games.

## Phase Details

### Phase 1: System Editor Main Page

**Goal**: A saved/loaded system's main page reads like a Bet Labs system editor — stat chips, cumulative money-won graph, plain-English active-filter sentences, tabbed workspace, and a theory field — instead of the current plain metrics row and raw form controls.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: EDIT-01, EDIT-02, EDIT-03, EDIT-04, EDIT-05
**Success Criteria** (what must be TRUE):

  1. User viewing an active/loaded system sees a cumulative "Money Won Over Time" line graph, sorted by season/week, showing running profit at $100-flat-stake convention.
  2. User sees a stat-chip header (Record, Margin, Money Won, ROI, and a Grade chip slot) in place of the current plain metrics text.
  3. User sees each active filter rendered as a plain-English sentence (e.g. "the spread is between -14 and -3") with a control to remove it, instead of raw form state.
  4. User can switch between Results Graph and Past Matches tabs on the same page without losing the loaded system's context.
  5. User can write a free-text "theory" on a saved system, save it, and see it displayed above the filter list on reload.

**Plans**: 5/5 plans executed
Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Stat-chip header (Record/Margin/Money Won/ROI/Grade placeholder) — EDIT-02
- [x] 01-03-PLAN.md — describe() plain-English filter sentence renderer (TDD) — EDIT-03

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02-PLAN.md — Cumulative Money Won Over Time graph + Results Graph/Past Matches tabs — EDIT-01, EDIT-04

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-04-PLAN.md — Active-filter sentence list + remove links, wired into the page — EDIT-03

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 01-05-PLAN.md — Theory field (save flow + sidebar/workspace display) — EDIT-05

**UI hint**: yes

### Phase 2: Integrity — Fade & Grade

**Goal**: Users can invert a system to test the fade and see an at-a-glance composite grade of how trustworthy a system's edge is, both surfaced directly in the stat-chip header built in Phase 1.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: INTG-01, INTG-02
**Success Criteria** (what must be TRUE):

  1. User can toggle "Fade System" on a saved system; toggling flips the graded side and updates the Record/Money Won/ROI chips to the opposite side's results.
  2. User sees a System Grade letter rendered in the stat-chip header's Grade slot, computed from sample size vs significance, ROI z-score, season sign-consistency, permutation p-value, and filter/value-count overfitting penalties.
  3. The Fade toggle state persists across save and reload of the system.

**Plans**: 2/2 plans executed
Plans:
**Wave 1**

- [x] 02-01-PLAN.md — Fade toggle: fade-flip grading logic, CLI --fade flag, storage/web round-trip, checkbox UI — INTG-01

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 02-02-PLAN.md — Composite System Grade: compute_grade + 5 sub-score helpers, overfitting penalty, Grade chip render — INTG-02

**UI hint**: yes

### Phase 3: Data Depth & Breadth

**Goal**: The underlying game/line history and feature registry grow deeper (further back than 2013) and broader (more CFBD REST/GraphQL endpoints wired in), giving the filter popup and dashboard phases more to filter and match on.
**Mode:** mvp
**Depends on**: Nothing new (independent of Phase 1-2 UI; sequenced here to unblock Phases 4-5, which benefit from more data but don't hard-depend on it)
**Requirements**: DATA-01, DATA-02
**Success Criteria** (what must be TRUE):

  1. The tool correctly handles the earliest CFBD line-covered season (2013, confirmed by a live coverage probe): a system filtered to the floor season returns non-empty results, and pre-floor seasons (e.g. 2012 — games but no usable lines) cleanly contribute zero rows. If the probe finds usable pre-2013 lines, those seasons are backfilled and become filterable. *(Reframed 2026-07-17 after research verified 2013 is the CFBD betting-line floor — original "earlier than 2013 → non-empty results" was unsatisfiable via CFBD, the only wired source.)*
  2. User sees new filter categories or features available when configuring a system (e.g. weather, player/coach, advanced stats) sourced from newly wired CFBD/GraphQL endpoints that were not present before this phase.
  3. Newly added registry features follow the existing no-lookahead convention — computable pre-game (entering-game state) or explicitly tagged into the `result_lookahead` group, verified by the existing `tests/` construct-and-assert pattern.

**Plans**: 4/4 plans executed
Plans:
**Wave 1**

- [x] 03-01-PLAN.md — To-date advanced team stats (success rate + explosiveness, off/def) as no-lookahead computed_running features — DATA-02 (D-03, D-06, D-07)
- [x] 03-02-PLAN.md — Line-floor guard: empty-lines-yields-0-rows test + confirmed 2013 floor documentation — DATA-01 (D-01, D-02)

**Wave 2** *(blocked on 03-01 completion)*

- [x] 03-03-PLAN.md — Live CFBD line-coverage probe (restore cfbd-python clone) + conditional pre-2013 backfill — DATA-01 (D-01)
- [x] 03-04-PLAN.md — Prior-season team offensive wEPA (distinct, no-lookahead team_preseason feature) — DATA-02 (D-05, D-06)

**UI hint**: no

### Phase 4: Filter Popup Modal

**Goal**: Configuring any filter opens a live, Bet Labs-style popup — slider or value table, per-value Record/ROI/Money, About Filter text — before the user commits, replacing the static inline sidebar `<details>` fields.
**Mode:** mvp
**Depends on**: Phase 1, Phase 3
**Requirements**: MODAL-01, MODAL-02, MODAL-03, MODAL-04, MODAL-05, MODAL-06
**Success Criteria** (what must be TRUE):

  1. Clicking a filter (from the sidebar or an active filter sentence's Edit control) opens a popup modal instead of expanding it inline.
  2. The modal header shows Record/Money Won/ROI chips that recompute live as the user adjusts the filter's controls, before saving.
  3. Numeric filters render a dual-handle range slider with BETWEEN-value inputs plus a per-value money-won chart across the filter's domain.
  4. Categorical/list filters render a searchable, sortable table of value to Record/ROI/Money.
  5. The modal shows an About Filter panel with the feature's definition text, and Save Filter commits the change and closes the modal while Cancel discards it.

**Plans**: TBD
**UI hint**: yes

### Phase 5: Dashboard & Current Matches

**Goal**: The tool becomes something checked weekly — a My Systems dashboard is the new landing page, and each saved system is evaluated live against upcoming games with matched-filter details and teaser records.
**Mode:** mvp
**Depends on**: Phase 1, Phase 4
**Requirements**: DASH-01, DASH-02, DASH-03, DASH-04
**Success Criteria** (what must be TRUE):

  1. User lands on a My Systems dashboard (`/`) listing saved systems with Record/Money Won/ROI and a sparkline, with the system editor moved to `/system`.
  2. A new/empty install ships with 2-3 bundled example systems visible on the dashboard.
  3. User sees a Current Matches view listing upcoming (unplayed) games each saved system currently matches, with the matched-filter details shown per game.
  4. User can view a system's alternate-line ("teaser") records from the Record chip.

**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. System Editor Main Page | 5/5 | Complete    | 2026-07-17 |
| 2. Integrity — Fade & Grade | 2/2 | Complete    | 2026-07-17 |
| 3. Data Depth & Breadth | 4/4 | Complete    | 2026-07-17 |
| 4. Filter Popup Modal | 0/TBD | Not started | - |
| 5. Dashboard & Current Matches | 0/TBD | Not started | - |
