---
phase: 01-system-editor-main-page
plan: 02
subsystem: ui
tags: [flask, jinja, backtest, svg-chart, query-string]

# Dependency graph
requires:
  - "BacktestResult.bet_details (game_id/season/week/profit fields) — from 01-01"
provides:
  - "_cumulative_chart(result) -> dict with points/polyline/zero_y/min_x/max_x, sorted chronologically by (season, week, game_id), raw stake-unit profit values"
  - "_query_href(**overrides) -> str, request-scoped query-string-preserving href builder registered as app.jinja_env.globals['query_href']"
  - "?tab= query-param split: GET / defaults to Results Graph, ?tab=matches shows Past Matches, any other value normalizes to Results Graph"
affects: [system-editor-main-page]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Request-scoped Jinja helper functions (_query_href) registered once via app.jinja_env.globals in create_app(), reading Flask's request.args directly rather than being passed as a render_template kwarg."
    - "Tab-style full-page-reload views built with a single {% if tab == 'graph' %}...{% else %}...{% endif %} conditional wrapping pre-existing sections, rather than duplicating markup."

key-files:
  created: []
  modified:
    - cfb_system_maker/web.py
    - cfb_system_maker/templates/index.html
    - cfb_system_maker/static/styles.css
    - tests/test_web.py
    - tests/test_web_features.py

key-decisions:
  - "Task 1 (_cumulative_chart aggregation function + unit tests) was already implemented and committed (c1ae313) in a prior session; this execution picked up from Task 2 (tab wiring), which was already present in the uncommitted working tree from that same prior session but lacked its required integration tests and had not been committed."
  - "Two pre-existing tests (test_web.py::test_web_filters_apply_to_results, test_web_features.py::test_unenabled_feature_filters_do_not_zero_out_matches) asserted on bets-table HTML at the default (no ?tab=) URL. Since the plan intentionally moves the bets table behind ?tab=matches, both were updated to append &tab=matches to their request URL (Rule 1 auto-fix — direct consequence of this task's behavior change, not a new feature)."
  - "SVG per-point <title> renders negative profit as \"$-100.00\" (no leading minus-then-dollar swap) exactly per the plan's literal Jinja expression `{% if point.profit >= 0 %}+{% endif %}${{ \"%.2f\"|format(point.profit * 100) }}` — verified against the plan's specified template code rather than treated as a formatting bug."

requirements-completed: [EDIT-01, EDIT-04]

coverage:
  - id: D1
    description: "_cumulative_chart returns _range_chart's empty-shape convention when bet_details is empty, sorts chronologically by (season, week, game_id) independent of input order, keeps one point per bet (no merging on equal season/week), and never pre-multiplies profit by 100"
    requirement: EDIT-01
    verification:
      - kind: unit
        ref: "tests/test_web.py#test_cumulative_chart_empty_bet_details_returns_zero_line_only"
        status: pass
      - kind: unit
        ref: "tests/test_web.py#test_cumulative_chart_single_bet_keeps_raw_stake_units"
        status: pass
      - kind: unit
        ref: "tests/test_web.py#test_cumulative_chart_sorts_chronologically_and_computes_running_sum"
        status: pass
      - kind: unit
        ref: "tests/test_web.py#test_cumulative_chart_same_season_week_produces_separate_points_by_game_id"
        status: pass
    human_judgment: false
  - id: D2
    description: "GET / defaults to Results Graph (cumulative chart + preserved by-line chart), GET /?tab=matches shows only Past Matches bets table, malformed tab values normalize to Results Graph, tab links preserve the full query string end-to-end (round-tripped, not just href-string inspection), and cumulative points expose $100-scaled values in SVG titles"
    requirement: EDIT-04
    verification:
      - kind: integration
        ref: "tests/test_web.py#test_web_default_tab_shows_results_graph_view"
        status: pass
      - kind: integration
        ref: "tests/test_web.py#test_web_invalid_tab_value_normalizes_to_results_graph"
        status: pass
      - kind: integration
        ref: "tests/test_web.py#test_web_cumulative_chart_svg_title_shows_dollar_scaled_value"
        status: pass
      - kind: integration
        ref: "tests/test_web.py#test_web_tab_switch_preserves_load_system_and_round_trips"
        status: pass
    human_judgment: true
    rationale: "Visual tab-nav styling (active-indicator underline, spacing) and the cumulative chart's on-screen legibility (UI-SPEC.md's --accent indicator, md 16px padding) are design-contract properties best confirmed by looking at the rendered page, not solely by string assertions on the HTML."

# Metrics
duration: 11min
completed: 2026-07-17
status: complete
---

# Phase 1 Plan 2: Cumulative Money-Won Chart + Results Graph/Past Matches Tabs Summary

**Added a chronologically-ordered "Money Won Over Time" SVG line chart and split the workspace into full-page-reload Results Graph / Past Matches tabs via a shared, request-scoped, query-string-preserving `_query_href()` helper.**

## Performance

- **Duration:** 11 min (across two sessions: Task 1 committed 2026-07-17 01:31 -0400, Task 2 committed 2026-07-17 01:42 -0400)
- **Tasks:** 2 completed
- **Files modified:** 5 (web.py, index.html, styles.css, test_web.py, test_web_features.py)

## Accomplishments

- `_cumulative_chart(result)` sorts `bet_details` by `(season, week, game_id)`, computes a rounded running profit sum per bet, and returns the same `{points, polyline, zero_y, min_x, max_x}` shape `_range_chart` already uses — profit values stay in raw stake-units.
- `_query_href(**overrides)` builds hrefs from a `MultiDict` copy of `request.args` via `urllib.parse.urlencode`, guaranteeing percent-encoding and preserving every unrelated query param; registered once as `app.jinja_env.globals["query_href"]`.
- `index()` normalizes `?tab=` with the exact expression `tab = "matches" if request.args.get("tab") == "matches" else "graph"` and passes `tab=tab` and `cumulative_chart=_cumulative_chart(result)` into the template context.
- `templates/index.html` gained a `<nav class="tabs">` and a `{% if tab == 'graph' %}...{% else %}...{% endif %}` split: Results Graph keeps the existing stats panel, season breakdown, coverage, and by-line `.range-chart` sections plus the new `.cumulative-chart` section; Past Matches keeps only the pre-existing bets `table-wrap` section, unchanged.
- Each cumulative-chart `<circle>` carries a `<title>` with the $100-scaled value (e.g. `+$90.91`), so the dollar convention is visible/accessible while Python retains stake-unit precision.
- `.tabs`, `.tabs a`, `.tabs a[aria-current]`, and `.cumulative-chart*` CSS rules added; the pre-existing `.range-chart` rule was left untouched.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add _cumulative_chart() aggregation function to web.py** - `c1ae313` (feat) — committed in a prior session.
2. **Task 2: Wire ?tab= query-param split and Results Graph / Past Matches sections** - `853739e` (feat) — committed this session, including the required integration tests that Task 1's commit did not cover.

## Files Created/Modified

- `cfb_system_maker/web.py` - Added `_cumulative_chart()` (Task 1) and `_query_href()` plus the `?tab=` normalization and `tab`/`cumulative_chart` render kwargs (Task 2).
- `cfb_system_maker/templates/index.html` - Added the tab nav and wrapped existing Results Graph sections + the new cumulative-chart section vs. the existing Past Matches bets table behind `{% if tab == 'graph' %}`.
- `cfb_system_maker/static/styles.css` - Added `.tabs`/`.tabs a`/`.tabs a[aria-current]` and `.cumulative-chart`/`.cumulative-chart h3`/`.cumulative-chart svg`/`.cumulative-chart polyline`/`.cumulative-chart circle`/`.cumulative-chart .zero-line`.
- `tests/test_web.py` - Added Task 1's 4 pure-function unit tests (prior session) and Task 2's 4 integration tests (this session): default-tab view, invalid-tab normalization, SVG title dollar-scaling, and a full round-trip of a generated tab href preserving `load_system`. Updated `test_web_filters_apply_to_results` to request `&tab=matches` since it asserts on bets-table rows.
- `tests/test_web_features.py` - Updated `test_unenabled_feature_filters_do_not_zero_out_matches` to request `&tab=matches` for the same reason.

## Decisions Made

- Task 1's code and tests were already committed from a prior session (`c1ae313`); Task 2's implementation code was already present in the working tree from that same prior session but was uncommitted and had no tests. This execution verified the existing implementation against the plan's acceptance criteria, wrote the missing integration tests, fixed two pre-existing tests broken by the tab split, and committed Task 2.
- Fixed two pre-existing tests that asserted on default-view bets-table HTML (Rule 1 — direct consequence of this task's intentional behavior change moving the bets table behind `?tab=matches`), rather than treating them as out of scope.
- Verified the SVG title's negative-profit format (`$-100.00`, not `-$100.00`) matches the plan's literal specified Jinja expression rather than "fixing" it as a bug.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated two pre-existing tests broken by the tab split**
- **Found during:** Full suite verification (`pytest -q`) after confirming Task 2's implementation matched plan spec.
- **Issue:** `test_web.py::test_web_filters_apply_to_results` and `test_web_features.py::test_unenabled_feature_filters_do_not_zero_out_matches` asserted on bets-table `<td>`/"No bets matched" text at the default (no `?tab=`) URL. Since the plan intentionally moves the bets table behind `?tab=matches`, the default view no longer contains that markup.
- **Fix:** Appended `&tab=matches` to each test's request URL so they exercise Past Matches, matching their original intent (checking which bets matched given filters).
- **Files modified:** `tests/test_web.py`, `tests/test_web_features.py`
- **Commit:** `853739e`

## Issues Encountered

None beyond the deviation above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

`_query_href` is now the shared query-string-preserving helper Plan 04 (`01-04-PLAN.md`) will extend with a removing variant for filter-sentence remove-links, per the plan's stated intent. The Results Graph / Past Matches tab split and cumulative chart are in place for later plans (e.g. filter popup modals, Current Matches tab) to build alongside without further changes to this tab-wiring. No blockers for the next plan in this phase.

---
*Phase: 01-system-editor-main-page*
*Completed: 2026-07-17*

## Self-Check: PASSED

All created/modified files verified present on disk; both task commits (`c1ae313`, `853739e`) verified present in git log.
