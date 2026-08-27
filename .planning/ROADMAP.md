# Roadmap: Bet Labs Parity for cfb-site

## Milestones

- ✅ **v1.0 Bet Labs Parity** — Phases 1–5 (shipped 2026-07-20) — see [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- 🚧 **v1.1 Season Readiness** — Phases 6–9 (in progress)

## Phases

<details>
<summary>✅ v1.0 Bet Labs Parity (Phases 1–5) — SHIPPED 2026-07-20</summary>

- [x] Phase 1: System Editor Main Page (5/5 plans) — completed 2026-07-17
- [x] Phase 2: Integrity — Fade & Grade (2/2 plans) — completed 2026-07-17
- [x] Phase 3: Data Depth & Breadth (4/4 plans) — completed 2026-07-20
- [x] Phase 4: Filter Popup Modal (4/4 plans) — completed 2026-07-17
- [x] Phase 5: Dashboard & Current Matches (6/6 plans) — completed 2026-07-20

Full phase details, success criteria, and plan breakdowns archived in [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md).

</details>

### 🚧 v1.1 Season Readiness (In Progress)

**Milestone Goal:** Close out v1.0's deferred verifications and accepted risks, and merge in-flight fixes, before the 2026-08-29 season start.

- [x] **Phase 6: Merge & Stale-Stats Audit** - Land the review branch on master and confirm no stale search-run results silently disagree with the new matching semantics — completed 2026-08-26
- [ ] **Phase 7: Integrity Fixes** - Close the describe() silent-drop risk, fix the filter-detail modal's double-counting bug, and close out the Hide Duplicates deferral with the correct architectural resolution
- [ ] **Phase 8: Neutral-Site & Indoor Unders Example** - Ship the 4th bundled example system with an honest, disclosed sample size
- [ ] **Phase 9: Live In-Season Verification** - Confirm Current Matches and feature-filtered matching work against the real 2026 season

## Phase Details

### Phase 6: Merge & Stale-Stats Audit

**Status**: ✅ Complete (2026-08-26)
**Goal**: The 26-commit review branch is on master with nothing lost or broken, and any saved search-run results computed under the old total-system matching semantics are identified and corrected.
**Depends on**: Phase 5 (v1.0, complete)
**Requirements**: MERGE-01, MERGE-02
**Success Criteria** (what must be TRUE):

  1. ✅ `master` contains all commits from `fix/web-app-review-2026-08-26` (merge commit `2e86ba5`; 2 conflicts resolved — `filter_modal.js`, `test_storage.py`, both additive), and the full test suite (441 tests) passes on `master` post-merge.
  2. ✅ `data/search_runs/` audited directly — the directory is empty (0 files), so no `SearchRun`/`SearchRunFinalist` JSON exists to be stale. No-op by inspection, not by assumption.

**Note**: PR #2 (`review-fixes-only`) had already merged a 13-commit subset directly to master outside the planning session, ahead of this phase running. Resolved by merging the full branch rather than replanning against the partial state — see STATE.md for detail.
**Plans**: None — executed directly (merge + directory audit), no PLAN.md generated.

### Phase 7: Integrity Fixes

**Goal**: The system editor and Current Matches panel never silently hide an active filter, the filter-detail modal's per-value numbers reconcile with the top-line backtest result, and the Hide Duplicates deferral is closed with an accurate architectural reason instead of a stale one.
**Depends on**: Phase 6
**Requirements**: FIX-01, FIX-02, FIX-03
**Success Criteria** (what must be TRUE):

  1. Every active filter — including any `(op, control)` combination not covered by an existing hardcoded sentence branch — renders a human-readable sentence with a working remove-link, verified on both the system editor and the Current Matches dashboard panel (both reuse `describe()`).
  2. In the `/filter-detail` modal for a total-system team/conference filter, the per-value Record/ROI/Money rows reconcile with (do not double-count against) the top-line backtest result.
  3. `PROJECT.md` no longer describes Hide Duplicates as a reachable, pending deferral in either the Out of Scope bullet or the Key Decisions table — both are updated to record the correct architectural finding (`run_backtest` is 1:1 on `game_id`; no top-line duplicate bets exist to toggle away; the real bug was the filter-detail double-count fixed by FIX-02).

**Plans**: 2/3 plans executed

- [x] 07-01-PLAN.md — describe() fallback sentence for uncovered (op, control) combos (FIX-01)
- [ ] 07-02-PLAN.md — filter-detail modal reconciliation caption for double-counted rows (FIX-02)
- [x] 07-03-PLAN.md — close Hide Duplicates deferral in PROJECT.md Out of Scope (FIX-03)

### Phase 8: Neutral-Site & Indoor Unders Example

**Goal**: A user browsing the Example Systems tab can copy a 4th bundled system built on the neutral-site/indoor-unders finding, with its statistical strength disclosed honestly rather than overstated.
**Depends on**: Phase 7
**Requirements**: DATA-01
**Success Criteria** (what must be TRUE):

  1. A 4th read-only example system ("Neutral-Site & Indoor Unders") appears on the Example Systems tab alongside the existing three, using only existing registry features (`neutralSite`, `gameIndoors`, `venue_dome`).
  2. The system's `theory` field, visible to the user, states the sample size and significance (n=109, p=0.014) rather than reading as a stronger claim than the underlying analysis supports.
  3. Copy to My Systems works for the new example the same way it does for the existing three.

**Plans**: TBD

### Phase 9: Live In-Season Verification

**Goal**: Current Matches and feature-filtered matching are confirmed to work correctly against the real, live 2026 season rather than only against historical fixtures.
**Depends on**: Calendar (2026-08-29 season start; the season-to-date stats check specifically requires week 3+) — not blocked by Phases 6-8. The pre-season dry run (success criterion 1) has no date gate and can run as soon as Phase 6 lands.
**Requirements**: DATA-02
**Success Criteria** (what must be TRUE):

  1. A pre-season dry run against a live-but-past CFBD calendar date confirms whether `GamesApi.get_calendar()` returns `startDate`/`endDate` as `str` or `datetime` in production, and the live-calendar branch handles whichever shape is returned (closes the untested-path risk before it's exercised for real).
  2. Once the 2026 season is underway, the Current Matches panel shows real unplayed games with posted lines, matched correctly (not graded) against saved systems.
  3. From week 3 onward, a feature-filtered system using season-to-date stats correctly matches upcoming games using those computed stats (not week-1's expected-empty `games_played=0` state, which fails closed by design and is not a bug).

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. System Editor Main Page | v1.0 | 5/5 | Complete | 2026-07-17 |
| 2. Integrity — Fade & Grade | v1.0 | 2/2 | Complete | 2026-07-17 |
| 3. Data Depth & Breadth | v1.0 | 4/4 | Complete | 2026-07-20 |
| 4. Filter Popup Modal | v1.0 | 4/4 | Complete | 2026-07-17 |
| 5. Dashboard & Current Matches | v1.0 | 6/6 | Complete | 2026-07-20 |
| 6. Merge & Stale-Stats Audit | v1.1 | 2/1 | Complete    | 2026-08-26 |
| 7. Integrity Fixes | v1.1 | 1/3 | In Progress|  |
| 8. Neutral-Site & Indoor Unders Example | v1.1 | 0/TBD | Not started | - |
| 9. Live In-Season Verification | v1.1 | 0/TBD | Not started | - |
