# Requirements: Bet Labs Parity for cfb-site

**Defined:** 2026-07-16
**Core Value:** A saved system's main page reads like a Bet Labs system editor (stat chips, cumulative money-won graph, plain-English active filters) and configuring any filter opens a live popup — slider or value table, per-value Record/ROI/Money, before you commit — instead of static inline form fields.

## v1 Requirements

### Editor (main page: chips, graph, sentences, theory, tabs)

- [x] **EDIT-01**: User sees a cumulative "Money Won Over Time" graph for the active/loaded system, sorted by season/week, running profit sum at $100-flat-stake convention
- [x] **EDIT-02**: User sees a stat-chip header (Record, Margin, Money Won, ROI, Grade) instead of the current plain metrics row
- [x] **EDIT-03**: User sees each active filter rendered as a plain-English sentence (e.g. "the spread is between -14 and -3") instead of raw form controls, with a way to remove it
- [x] **EDIT-04**: User can switch between Results Graph and Past Matches views via tabs on the same page
- [x] **EDIT-05**: User can write and save a free-text "theory" (hypothesis) on a saved system, shown above its filter list

### Integrity (fade, grade)

- [x] **INTG-01**: User can toggle "Fade System" on a system to grade the opposite side of every matched bet
- [x] **INTG-02**: User sees a composite System Grade letter combining sample size vs significance, ROI z-score, season sign-consistency, permutation p-value, and filter/value-count overfitting penalties

### Filter Popup Modal

- [x] **MODAL-01**: Clicking a filter in the sidebar opens a popup modal instead of expanding it inline
- [x] **MODAL-02**: Modal header shows live Record/Money Won/ROI chips that recompute as the user adjusts the filter's controls, before saving
- [ ] **MODAL-03**: Numeric filters show a dual-handle range slider with BETWEEN-value inputs plus a per-value money-won chart across the filter's domain
- [ ] **MODAL-04**: Categorical/list filters show a searchable, sortable table of value → Record/ROI/Money
- [x] **MODAL-05**: Modal shows an "About Filter" panel with the feature's exact definition text
- [x] **MODAL-06**: Saving a filter in the modal commits it to the system and closes the modal; canceling discards the change

### Dashboard & Current Matches

- [ ] **DASH-01**: User lands on a My Systems dashboard listing saved systems with record/money-won/ROI and a sparkline, separate from the system editor page
- [ ] **DASH-02**: Dashboard ships with 2-3 bundled example systems for a new/empty install
- [ ] **DASH-03**: User sees a Current Matches view: upcoming (unplayed) games each saved system matches, with the matched-filter details shown per game
- [ ] **DASH-04**: User can view alternate-line ("teaser") records for a system's matched bets from the Record chip

### Data

- [x] **DATA-01**: Historical game/line coverage is backfilled further back than the current 2013 floor where CFBD coverage allows
- [x] **DATA-02**: Additional CFBD REST/GraphQL endpoints (weather, player/coach, advanced stats, and other available fields) are wired into `FEATURE_REGISTRY` as new filterable features, following the existing no-lookahead / entering-game convention

## v2 Requirements

None currently deferred — see Out of Scope for explicit exclusions instead.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Think Tank (multi-user system sharing, copy counts) | Single-user local tool, no user base to share with |
| Widget/embed, Live Help chat | No external audience for embeds; Live Help is a support feature, not a betting tool |
| Moneyline wager type | Add later once spread/total UX (popup modals, dashboard) is settled |
| Public betting-percentage filters | CFBD has no bet-share data source; would need a different provider not currently wired to the registry |
| Hide Duplicates toggle | Only matters once a system can match both sides of one game; current side-fixed systems can't self-collide |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| EDIT-01 | Phase 1 | Complete |
| EDIT-02 | Phase 1 | Complete |
| EDIT-03 | Phase 1 | Complete |
| EDIT-04 | Phase 1 | Complete |
| EDIT-05 | Phase 1 | Complete |
| INTG-01 | Phase 2 | Complete |
| INTG-02 | Phase 2 | Complete |
| DATA-01 | Phase 3 | Complete |
| DATA-02 | Phase 3 | Complete |
| MODAL-01 | Phase 4 | Complete |
| MODAL-02 | Phase 4 | Complete |
| MODAL-03 | Phase 4 | Pending |
| MODAL-04 | Phase 4 | Pending |
| MODAL-05 | Phase 4 | Complete |
| MODAL-06 | Phase 4 | Complete |
| DASH-01 | Phase 5 | Pending |
| DASH-02 | Phase 5 | Pending |
| DASH-03 | Phase 5 | Pending |
| DASH-04 | Phase 5 | Pending |

**Coverage:**

- v1 requirements: 19 total
- Mapped to phases: 19
- Unmapped: 0 ✓

---
*Requirements defined: 2026-07-16*
*Last updated: 2026-07-16 after roadmap creation (5 phases, 100% coverage)*
