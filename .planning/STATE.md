---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 5
current_phase_name: Dashboard & Current Matches
status: planning
stopped_at: Phase 04 complete (UAT 5/5, security verified)
last_updated: "2026-07-20T16:58:56.125Z"
last_activity: 2026-07-20
last_activity_desc: Phase 04 complete, transitioned to Phase 5
progress:
  total_phases: 5
  completed_phases: 4
  total_plans: 15
  completed_plans: 15
  percent: 80
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-17)

**Core value:** A saved system's main page reads like a Bet Labs system editor (stat chips, cumulative money-won graph, plain-English active filters) and configuring any filter opens a live popup — slider or value table, per-value Record/ROI/Money, before you commit — instead of static inline form fields.
**Current focus:** Phase 5 — Dashboard & Current Matches

## Current Position

Phase: 5 — Dashboard & Current Matches
Plan: Not started
Status: Ready to plan
Last activity: 2026-07-20 - Completed quick task 260720-igf: Fix normalize._select_line total drop: fall back to first available overUnder across providers when preferred line lacks it

Progress: [█████████░] 87%

## Performance Metrics

**Velocity:**

- Total plans completed: 11
- Average duration: - min
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 5 | - | - |
| 02 | 2 | - | - |
| 04 | 4 | - | - |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 01 P01 | 8min | 2 tasks | 6 files |
| Phase 01 P03 | 4min | 2 tasks | 2 files |
| Phase 01 P02 | 11min | 2 tasks | 5 files |
| Phase 01 P04 | 10min | 2 tasks | 4 files |
| Phase 01 P05 | 15min | 2 tasks | 7 files |
| Phase 02 P01 | 25min | 2 tasks | 10 files |
| Phase 02 P02 | 9min | 2 tasks | 5 files |
| Phase 03 P01 | 20min | 3 tasks | 6 files |
| Phase 03 P02 | 6 | 2 tasks | 2 files |
| Phase 03 P04 | 12min | 2 tasks | 4 files |
| Phase 03 P03 | 20min | 3 tasks | 1 file |
| Phase 04 P01 | 7min | 2 tasks | 8 files |
| Phase 04 P02 | 18min | 2 tasks | 5 files |
| Phase 04 P03 | 7min | 2 tasks | 7 files |
| Phase 04 P04 | 7min | 2 tasks | 5 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Roadmap: Grade chip UI slot shipped in Phase 1 (EDIT-02) as placeholder; actual composite grade computation wires in behind it in Phase 2 (INTG-02).
- Roadmap: Data extension (DATA-01/02) sequenced as Phase 3 — after the UI phases that don't need it (Editor, Integrity), before the UI phases that benefit from it (Modal, Dashboard).
- Phase 1: All query-href construction (`_query_href`/`_query_href_removing`) and free-text rendering (`theory`) use `urlencode`/Jinja auto-escape exclusively, no `\|safe` — this pattern must be followed by any new href/text-rendering surface added in Phase 2+.
- Phase 1: T-01-03 accepted risk (`01-SECURITY.md`) — `describe()` silently drops a known-key feature filter whose `(op, control)` combo it doesn't render, though `feature_ok()` still applies it. Revisit if `FEATURE_REGISTRY` grows new op/control combos.
- [Phase ?]: Phase 2 Plan 1: Fade toggle checkbox lives outside filters-form's DOM (inside .workspace-header per D-01/UI-SPEC) and associates via HTML5 form="filters-form" attribute, matching favorite/underdog/home/away pattern.
- [Phase ?]: Phase 2 Plan 1: Fade is read exclusively inside grade_bet/_grade_total_bet, never inside matches_system -- new boolean toggle fields must follow this grading-only pattern to preserve matched-count invariance (D-03).
- [Phase ?]: Sample-size sub-score uses stats.wilson_low - stats.break_even_rate margin floored by decided<30, per D-04 (supersedes 02-RESEARCH.md's raw-bet-count-only example).
- [Phase ?]: Grade chip renders result.grade via plain Jinja auto-escaping mirroring the Margin chip's conditional style, no |safe filter.
- [Phase ?]: Advanced to-date stats accumulated as game-average (parity with PPA path), not play-weighted (A2)
- [Phase ?]: DATA-01 line floor confirmed as 2013; 'backfill earlier' closed by verification (live probe 03-03), not a code change.
- Phase 3: DATA-01 closed by LIVE re-confirmation (03-03) — probe of current CFBD BettingApi returned 0 usable lines for 2008-2012 and 841 for 2013; earliest usable-line season = 2013, conditional pre-2013 backfill is a documented no-op.
- [Phase ?]: Season draft uses checkboxes; Save writes comma-joined filter_seasons
- [Phase ?]: Backdrop light-dismiss blocked via cancel.preventDefault; Escape handled as Cancel
- [Phase ?]: Live chips render server JSON only via GET /api/backtest
- Phase 4 Plan 2: Boolean domain always emits Yes/No rows even when a side has zero observed games
- Phase 4 Plan 2: Numeric launchers open About + live chips; range editors deferred to 04-03
- Phase 4 Plan 2: Feature Save updates existing per-feature fallback controls (not rebuilt parallel arrays from scratch)
- [Phase ?]: chart_points capped at 60 with stride downsample; always retain last extreme
- [Phase ?]: Numeric feature fallback renders paired gte+lte slots for progressive-enhancement GET round-trip
- [Phase ?]: serialize_numeric_draft rejects non-finite and reversed bounds server-side (T-04-10)
- [Phase ?]: Edit maps D-01 only
- [Phase ?]: Edit maps D-01 only
- [Phase 04]: edit_metadata_for_sentence maps D-01 candidates only; favorite/underdog/home/away stay Remove-only
- [Phase 04]: LIVE_DEBOUNCE_MS=250 with AbortController + liveGeneration before chips/Save

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1] T-01-03 accepted risk (`01-SECURITY.md`): describe()'s four hardcoded (op,control) render branches don't cover every combo `feature_ok()` will actually evaluate — a mismatch is reachable via crafted query params, not the normal form UI. Not a blocker for Phase 2, but worth closing before registry op/control combos multiply further.

## Quick Tasks Completed

Ad-hoc tasks run via `/gsd-quick` — tracked here, not in ROADMAP.md:

| Date | Slug | What | Status |
|------|------|------|--------|
| 2026-07-20 | numeric-filter-step-intervals | Filter popup numeric controls snap to a span-scaled step (0.5 for spread/total) instead of continuous `step="any"` | complete |
| 2026-07-20 | filter-group-taxonomy | Split the `pregame` feature group into Matchup / Ratings / Betting Lines / Weather (restored user work quarantined during phase 03) | complete |
| 2026-07-20 | fix-normalize-select-line-total-drop-fal | `normalize._select_line` picked one line per game; total (over/under) is now backfilled from the first sibling provider that has it when the selected line's total is null — fixes ~93-97% total-null rate in 2013-2016 seasons | complete |

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-07-17T19:14:55.061Z
Stopped at: Completed 04-03-PLAN.md
Resume file: None
