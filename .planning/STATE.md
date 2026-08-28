---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Season Readiness
current_phase: 9
current_phase_name: Live In-Season Verification
status: executing
stopped_at: Completed 08-01-PLAN.md
last_updated: "2026-08-27T09:34:04.282Z"
last_activity: 2026-08-27
last_activity_desc: "Quick task 260827-8or: Feature Filters sidebar search and collapsible groups"
progress:
  total_phases: 4
  completed_phases: 3
  total_plans: 8
  completed_plans: 5
  percent: 75
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-20)

**Core value:** A saved system's main page reads like a Bet Labs system editor (stat chips, cumulative money-won graph, plain-English active filters) and configuring any filter opens a live popup — slider or value table, per-value Record/ROI/Money, before you commit — instead of static inline form fields.
**Current focus:** Phase 8 — Neutral-Site & Indoor Unders Example

## Current Position

Phase: 9 — Live In-Season Verification
Plan: Not started
Status: Ready to execute
Last activity: 2026-08-27 — Completed quick task 260827-b9w: line-movement registry features (spread_open, spread_move, total_open, total_move)

Progress: [██████████] 100%

**Note:** Phase 6 was executed directly (git merge + directory audit) rather than through the plan-phase/execute-phase pipeline — no PLAN.md/SUMMARY.md artifacts exist for it. Both requirements (MERGE-01, MERGE-02) are satisfied and verified (test suite + directory listing), recorded here for traceability.

**Discovered during Phase 6:** PR #2 (`review-fixes-only`) had already merged a 13-commit subset of `fix/web-app-review-2026-08-26` directly to master outside this session, diverging the working branch from what `/gsd-new-milestone` had planned against. Resolved by merging the full fix branch (2 conflicts: `filter_modal.js`, `test_storage.py` — both additive, no logic lost) rather than replanning from master.

## Performance Metrics

**Velocity:**

- Total plans completed: 17
- Average duration: - min
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 5 | - | - |
| 02 | 2 | - | - |
| 04 | 4 | - | - |
| 6 | 2 | - | - |
| 7 | 3 | - | - |
| 8 | 1 | - | - |

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
| Phase 08 P01 | 45min | 2 tasks | 2 files |

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
- [Phase ?]: DATA-01: theory text cites the app's own measured backtest numbers (69-40-1, 63.30% under, +20.66% ROI, n=109, p~0.011) over the source doc's figures where they diverge (ROI/p-value), since a user backtesting the exact 3-filter system in the app would see the app's own output

### Pending Todos

- Phase 9 (Live In-Season Verification, DATA-02) — criterion 1 (pre-season calendar dry run) DONE 2026-08-27, see `.planning/phases/09-live-in-season-verification/09-DRY-RUN.md`: `startDate`/`endDate` are real `datetime` objects, live-calendar branch fires correctly, no type mismatch. Criteria 2-3 (Current Matches shows real posted-line games; season-to-date feature filters match correctly) remain genuinely calendar-blocked: criterion 2 needs the season live (~2026-08-29), criterion 3 needs week 3+ specifically (week 1-2 `games_played=0` fails closed by design, not a bug). Resume with `/gsd-autonomous --from 9` or `/gsd-plan-phase 9` once those dates pass.
- Environment gap discovered during the dry run: system Python (3.14, pydantic 2.13.4) cannot import the vendored `cfbd-python` client (`PydanticUserError`); use `.venv/Scripts/python.exe` (pydantic 1.10.26, matches `requirements.lock`) for anything touching CFBD API calls. `.venv`'s missing `waitress` was fixed 2026-08-27 via `.venv/Scripts/python.exe -m pip install -r requirements.lock` — full suite now 470 passed, 1 skipped, 3 deselected, 0 failures.

### Blockers/Concerns

- None open — Phase 9 is deferred on the calendar, not blocked by a defect. See Pending Todos above.

None open. T-01-03 (`describe()` silent filter drop) closed 2026-08-26 in Phase 7 (FIX-01, commit `da558f8` for the WR-01 follow-up fix).

## Quick Tasks Completed

Ad-hoc tasks run via `/gsd-quick` — tracked here, not in ROADMAP.md:

| Date | Slug | What | Status |
|------|------|------|--------|
| 2026-08-28 | prediction-tracker-game-id-join | `scripts/build_prediction_tracker.py` unions the 25 Prediction Tracker season CSVs (2001-2025) into `data/raw/prediction_tracker_lines.csv`, 17,755 rows x 178 cols, game_id on 17,754 (100.0%) with 99.87% score agreement; had to source CFBD from `stg.game` because `data/raw/games_*.json` is regular-season only and was silently dropping every bowl | complete |
| 2026-08-28 | graphql-total-order-repull | Single-column orderBy on the 20 tables without an `id` dropped rows across page boundaries (pregame_win_prob 12,811 -> 12,656 while gameTeam GAINED rows); now sorts on every scalar. All 20 re-pulled: gameTeam 225,344 rows / 0 dupes, pregame_win_prob 12,812. The other 15 tables sort on a unique `id`, verified, no re-pull needed | complete |
| 2026-08-28 | graphql-orderby-and-aggregate-check | Hasura arg is orderBy with an uppercase enum, so paginated pulls had always run unsorted; audit now compares each dump to {table}Aggregate row counts and found 12 tables behind the source (coachSeason -10,627, recruit -42,543); all 14 re-pulled the same day, +64,855 rows, every checkable table now matches source | complete |
| 2026-08-28 | graphql-coverage-audit | audit_endpoints.py now partitions the introspected GraphQL schema too (35 defaults + 2 documented exclusions = 37 tables); GQL_DEFAULT_TABLES 24 -> 35; Tier 3 absence degrades to a note | complete |
| 2026-08-28 | registry-features-for-new-endpoints | 5 features off the new endpoints (prior_core_overall/offense/defense, prior_srs_rating, conference_change); ratings lagged one season since core/SRS are season-final; registry 59 -> 64 features | complete |
| 2026-08-28 | bump-cfbd-client-register-10-endpoints | Vendored cfbd-python 034cd17 -> 52f2bbf; registered the last 10 spec paths (CFP x3, core ratings, expanded SRS, coach profile/seasons/tenures, conference affiliations/changes); audit now 73+1+0=74; new Endpoint.min_season; 2012-2025 scraped, 0 failed | complete |
| 2026-08-28 | cfbd-endpoint-completeness-audit | `scripts/audit_endpoints.py` diffs the live CFBD spec (74 paths) against the vendored client and `ENDPOINTS`; partition closes at 63 registered + 1 deliberate + 10 client-blocked, zero drift | complete |
| 2026-07-20 | numeric-filter-step-intervals | Filter popup numeric controls snap to a span-scaled step (0.5 for spread/total) instead of continuous `step="any"` | complete |
| 2026-07-20 | filter-group-taxonomy | Split the `pregame` feature group into Matchup / Ratings / Betting Lines / Weather (restored user work quarantined during phase 03) | complete |
| 2026-07-20 | fix-normalize-select-line-total-drop-fal | `normalize._select_line` picked one line per game; total (over/under) is now backfilled from the first sibling provider that has it when the selected line's total is null — fixes ~93-97% total-null rate in 2013-2016 seasons | complete |
| 2026-08-26 | total-filter-semantics-fixes | Filter audit findings 1-6 + 5 smaller UX gaps: totals semantics (1-3), description/grade/stats accuracy (4-6), no-JS perspective sync + dead modal buttons + silent parse warnings + Max ROI overlap fix (UX gaps) | complete |
| 2026-08-26 | register-player-success-rate-endpoints | Registered `player_success_season` and `player_success_game` CFBD endpoints in scraper registry, bringing coverage from 61 to 63 entries | complete |
| 2026-08-27 | feature-filter-sidebar-search-collapsibl | Feature Filters sidebar search + collapsible groups with active-count badges (`5231273`). Planned Fixes 2 and 3 were dropped, not applied: a concurrent session landed `7c2e694`/`969c7ca` (one row per stat, in-modal perspective switcher removed) and the `points\|length <= 60` marker gate, which solved both goals first | complete (1 of 3 landed, 2 superseded) |
| 2026-08-27 | coach-style-cluster-feature | `coach_style_cluster` registry feature: k=5 k-means coach playstyle labels (option_ground / attack_defense / bend_dont_break / pass_first_efficient / balanced_spread) from quality-stripped 2016-2024 advanced stats; embedded 189-coach dict in `coach_style.py` + generator `scripts/build_coach_style_clusters.py`; quarantined as `result_lookahead` (career-level label) | complete |
| 2026-08-27 | add-line-movement-registry-features-spre | `spread_open`/`spread_move`/`total_open`/`total_move` registry features (Betting System Builder Phase A): book-matched open vs. close from CFBD `lines_{season}.json`, computed in `enrich.py` (`computed_line_move` source kind), no `GameRecord`/CSV change; excluded from automated search (`search.py` `_LOW_COVERAGE_KEYS`) since only ~18% of games have a book-matched open, a non-random 2023-2025 slice — available for manual system building. Coverage: 2,317/13,014 spread_open, 1,379/13,014 total_open, 0 before 2021 (`3f1d9aa`) | complete |
| 2026-08-28 | coach-playstyle-analysis-note | `docs/coach-playstyle-analysis.md` + `scripts/analyze_coach_styles.py` + 8 charts in `docs/img/`: validity study behind `coach_style_cluster`. Key results — season-to-career stability 45.6% vs 22.5% chance (label is a tendency, not an identity), `balanced_spread` is a residual bucket not a style, style vs conference tier χ²=135.3 p≈2e-25 (confounds every outcome comparison), and a walk-forward market test (2019-2024, labels fit on prior seasons only) finds no edge — 0 of 10 tests survive Holm, min adjusted p 0.093 | complete |

## Deferred Items

Items acknowledged and deferred at v1.0 milestone close on 2026-07-20:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| verification | Phase 05 — live in-season confirmation that Current Matches shows real upcoming (unplayed) games with posted lines (05-VALIDATION.md Manual-Only) | scheduled into v1.1 Phase 9 (DATA-02) | 2026-07-20 |
| verification | Phase 05 — live in-season confirmation that a feature-filtered saved system correctly matches upcoming games via computed season-to-date stats | scheduled into v1.1 Phase 9 (DATA-02), specifically week 3+ | 2026-07-20 |
| requirement | DASH-04 (teaser/alternate-line records) — descoped from Phase 5 on 2026-07-20; unscheduled; partial decisions in 05-CONTEXT.md Deferred Ideas | deferred (out of v1.0 and v1.1) | 2026-07-20 |

**Note:** Phase 05 verification is `human_needed`, not `gaps_found` — all three DASH requirements are code-verified and the full suite (307 tests) passes. The two verification items above are live-in-season confirmations that cannot execute in the offseason; the visual-layout confirmation was satisfied during this session (editor sidebar layout fix, commit 428f85d). Milestone closed as override_closeout on this basis. Both items are now scheduled into v1.1 Phase 9 (see ROADMAP.md).

## Session Continuity

Last session: 2026-08-27T04:27:46.001Z
Stopped at: Completed 08-01-PLAN.md
Resume file: None

## Operator Next Steps

- Review and approve the v1.1 roadmap (.planning/ROADMAP.md), then run `/gsd-plan-phase 6`
