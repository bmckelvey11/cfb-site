---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Season Readiness
current_phase: 7
current_phase_name: Integrity Fixes
status: verifying
stopped_at: Completed 07-02-PLAN.md
last_updated: "2026-08-27T02:51:44.502Z"
last_activity: 2026-08-27
last_activity_desc: Completed 07-01 (describe() fallback sentence, FIX-01) and 07-03 (PROJECT.md Out of Scope closure, FIX-03)
progress:
  total_phases: 4
  completed_phases: 2
  total_plans: 4
  completed_plans: 4
  percent: 50
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-20)

**Core value:** A saved system's main page reads like a Bet Labs system editor (stat chips, cumulative money-won graph, plain-English active filters) and configuring any filter opens a live popup — slider or value table, per-value Record/ROI/Money, before you commit — instead of static inline form fields.
**Current focus:** Phase 7 — Integrity Fixes

## Current Position

Phase: 7 (Integrity Fixes) — EXECUTING
Plan: 3 of 3 (wave 1 complete: 07-01, 07-03; wave 2 next: 07-02)
Status: Phase complete — ready for verification
Last activity: 2026-08-27 — Completed 07-01 (describe() fallback sentence, FIX-01) and 07-03 (PROJECT.md Out of Scope closure, FIX-03)

Progress: [██████████] 100%

**Note:** Phase 6 was executed directly (git merge + directory audit) rather than through the plan-phase/execute-phase pipeline — no PLAN.md/SUMMARY.md artifacts exist for it. Both requirements (MERGE-01, MERGE-02) are satisfied and verified (test suite + directory listing), recorded here for traceability.

**Discovered during Phase 6:** PR #2 (`review-fixes-only`) had already merged a 13-commit subset of `fix/web-app-review-2026-08-26` directly to master outside this session, diverging the working branch from what `/gsd-new-milestone` had planned against. Resolved by merging the full fix branch (2 conflicts: `filter_modal.js`, `test_storage.py` — both additive, no logic lost) rather than replanning from master.

## Performance Metrics

**Velocity:**

- Total plans completed: 13
- Average duration: - min
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 5 | - | - |
| 02 | 2 | - | - |
| 04 | 4 | - | - |
| 6 | 2 | - | - |

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
| Phase 05 P02 | 15m | 2 tasks | 2 files |
| Phase 05 P01 | 35m | 3 tasks | 5 files |
| Phase 05 P03 | 45m | 3 tasks | 6 files |
| Phase 05 P04 | 25m | 2 tasks | 4 files |
| Phase 05 P05 | ~50m | 2 tasks | 6 files |
| Phase 05-dashboard-current-matches P06 | ~60 min | 3 tasks | 4 files |
| Phase 07 P01 | 25min | 2 tasks | 4 files |
| Phase 07 P02 | 20min | 2 tasks | 3 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Roadmap: v1.1 phase sequencing — Phase 6 (merge) must land first because the review branch touches backtest.py/features.py/storage.py/web.py, the same files Phase 7's fixes touch; Phase 7 (integrity fixes) before Phase 8 (new example) since FIX-01's describe() fallback is a rendering safety net for the new example's filters; Phase 9 (live verification) is calendar-gated, not phase-gated, and runs in parallel once Phase 6 lands.
- Roadmap: FIX-03 (closing Hide Duplicates as N/A) bundled into Phase 7 alongside FIX-02 (the real bug), not split into a separate phase — research confirmed `run_backtest` is 1:1 on `game_id`, so FIX-03 is a documentation correction that pairs with the real fix rather than standing alone.
- Roadmap: Grade chip UI slot shipped in Phase 1 (EDIT-02) as placeholder; actual composite grade computation wires in behind it in Phase 2 (INTG-02).
- Roadmap: Data extension (DATA-01/02) sequenced as Phase 3 — after the UI phases that don't need it (Editor, Integrity), before the UI phases that benefit from it (Modal, Dashboard).
- Phase 1: All query-href construction (`_query_href`/`_query_href_removing`) and free-text rendering (`theory`) use `urlencode`/Jinja auto-escape exclusively, no `\|safe` — this pattern must be followed by any new href/text-rendering surface added in Phase 2+.
- Phase 1: T-01-03 accepted risk (`01-SECURITY.md`) — `describe()` silently drops a known-key feature filter whose `(op, control)` combo it doesn't render, though `feature_ok()` still applies it. Scheduled to close in v1.1 Phase 7 (FIX-01).
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
- [Phase ?]: 05-02: matches_system gains keyword-only require_played=True; unplayed games matchable but never gradable (D-18)
- [Phase ?]: 05-02: per-season dashboard figures proven derivable from one all-time run_backtest via season_breakdown (D-11); stats/grade are not derivable
- [Phase ?]: Upcoming fetch uses season_type='both'; resolved type still threads into slicing and meta (D-19)
- [Phase ?]: Offseason fallback ranks completed weeks by latest start date, never week number (postseason renumbers)
- [Phase ?]: Dashboard at /, editor relocated to /system; editor view keeps the name index so all url_for('index') call sites repoint automatically (05-03, D-09)
- [Phase ?]: Root-to-editor redirect preserves request.query_string verbatim, not url_for(**request.args), so repeated multi-value filter params survive (05-03)
- [Phase ?]: Dashboard figures come from one cached all-time run_backtest per system; per-season derived from season_breakdown/bet_details, never persisted (05-03, D-11)
- [Phase ?]: 05-04: pass the union (season's completed games + target week) to enrich_games and post-filter output to target-week ids, rather than adding an only_ids param
- [Phase ?]: 05-04: exclude target-week ids from the accumulation base — in the offseason fallback the target games are themselves completed and would be double-counted
- [Phase ?]: Example Systems tab ships three read-only bundled systems (05-05); registry-feature example uses matchup conferenceGame so it matches non-zero games in the resolved week (D-21, must-have #5)
- [Phase ?]: 05-06: Current Matches panel play text runs grade_bet's normalization (fade inversion + away sign flip), never the declared side (D-08)
- [Phase ?]: 05-06: Panel computed per-request (matching is cheap, no permutation test); did not couple upcoming.csv into the My Systems backtest cache fingerprint
- [Phase ?]: 05-06: TBD kickoffs render date-only (correctness fix over UI-SPEC date-and-time) — no fabricated clock time
- [Phase ?]: Fallback sentence text uses filt.value!r (Python repr) per D-locked wording, not a reformatted/joined value
- [Phase ?]: Phase 7: edit_metadata_for_sentence gates on explicit (op,control) renderable shapes before building Edit metadata, mirroring describe()'s 4 hand-written combos
- [Phase ?]: matched_game_ids populated inside aggregate_filter_value_rows's existing loop (post resolve_candidate_value-None skip) as the exact bucket denominator, exposed via /filter-detail as matched_games
- [Phase ?]: Reconciliation caption in renderValueTable() references only state.matchedGames, never the Record chip, per UI-SPEC's no-third-number rule

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 7 scheduled] T-01-03 (`01-SECURITY.md`): describe()'s four hardcoded (op,control) render branches don't cover every combo `feature_ok()` will actually evaluate — a mismatch is reachable via crafted query params, not the normal form UI. Scheduled to close in v1.1 Phase 7 (FIX-01).

## Quick Tasks Completed

Ad-hoc tasks run via `/gsd-quick` — tracked here, not in ROADMAP.md:

| Date | Slug | What | Status |
|------|------|------|--------|
| 2026-07-20 | numeric-filter-step-intervals | Filter popup numeric controls snap to a span-scaled step (0.5 for spread/total) instead of continuous `step="any"` | complete |
| 2026-07-20 | filter-group-taxonomy | Split the `pregame` feature group into Matchup / Ratings / Betting Lines / Weather (restored user work quarantined during phase 03) | complete |
| 2026-07-20 | fix-normalize-select-line-total-drop-fal | `normalize._select_line` picked one line per game; total (over/under) is now backfilled from the first sibling provider that has it when the selected line's total is null — fixes ~93-97% total-null rate in 2013-2016 seasons | complete |
| 2026-08-26 | total-filter-semantics-fixes | Filter audit findings 1-6 + 5 smaller UX gaps: totals semantics (1-3), description/grade/stats accuracy (4-6), no-JS perspective sync + dead modal buttons + silent parse warnings + Max ROI overlap fix (UX gaps) | complete |
| 2026-08-26 | register-player-success-rate-endpoints | Registered `player_success_season` and `player_success_game` CFBD endpoints in scraper registry, bringing coverage from 61 to 63 entries | complete |

## Deferred Items

Items acknowledged and deferred at v1.0 milestone close on 2026-07-20:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| verification | Phase 05 — live in-season confirmation that Current Matches shows real upcoming (unplayed) games with posted lines (05-VALIDATION.md Manual-Only) | scheduled into v1.1 Phase 9 (DATA-02) | 2026-07-20 |
| verification | Phase 05 — live in-season confirmation that a feature-filtered saved system correctly matches upcoming games via computed season-to-date stats | scheduled into v1.1 Phase 9 (DATA-02), specifically week 3+ | 2026-07-20 |
| requirement | DASH-04 (teaser/alternate-line records) — descoped from Phase 5 on 2026-07-20; unscheduled; partial decisions in 05-CONTEXT.md Deferred Ideas | deferred (out of v1.0 and v1.1) | 2026-07-20 |

**Note:** Phase 05 verification is `human_needed`, not `gaps_found` — all three DASH requirements are code-verified and the full suite (307 tests) passes. The two verification items above are live-in-season confirmations that cannot execute in the offseason; the visual-layout confirmation was satisfied during this session (editor sidebar layout fix, commit 428f85d). Milestone closed as override_closeout on this basis. Both items are now scheduled into v1.1 Phase 9 (see ROADMAP.md).

## Session Continuity

Last session: 2026-08-27T02:51:44.479Z
Stopped at: Completed 07-02-PLAN.md
Resume file: None

## Operator Next Steps

- Review and approve the v1.1 roadmap (.planning/ROADMAP.md), then run `/gsd-plan-phase 6`
