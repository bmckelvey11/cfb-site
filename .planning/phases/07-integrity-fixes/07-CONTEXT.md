# Phase 7: Integrity Fixes - Context

**Gathered:** 2026-08-26
**Status:** Ready for planning

<domain>
## Phase Boundary

The system editor and Current Matches panel must never silently hide an active filter; the `/filter-detail` modal's per-value numbers must reconcile with (not silently disagree with) the top-line backtest result for total-system team/conference filters; and the original "Hide Duplicates" deferral must be closed in `PROJECT.md` with the accurate architectural reason instead of the stale one — `run_backtest` is 1:1 on `game_id`, there is no top-line duplication to toggle away (already partially recorded in PROJECT.md's Key Decisions table by the Phase 6 transition, but FIX-03 formally closes the Out of Scope bullet too).

Requirements: FIX-01, FIX-02, FIX-03.

</domain>

<decisions>
## Implementation Decisions

### Filter-Detail Double-Count (FIX-02)

- The tuple fan-out in `aggregate_filter_value_rows` (one row per matching team-value for either-perspective total systems) is **kept, not collapsed**. A game between Team A and Team B legitimately contributes to both A's row and B's row — this is the correct per-team breakdown, not a bug.
- The actual fix: the modal must show/label the per-value row-sum **separately** from the system's true matched-game count, so the two numbers are never mistaken for each other or appear to silently contradict. A caption or footer note reconciling "rows sum to N (each game counted once per matching team-value)" against the top-line "M games matched" is the expected shape.
- Concrete test from research (PITFALLS.md Pitfall 2): build a total system with `filter_teams` containing both teams of at least one fixture game, run `/filter-detail` for `core:team`, and assert the sum of `bets` across all rows equals `2 × len(matched_games_where_both_teams_are_in_filter) + 1 × len(matched_games_where_only_one_team_is_in_filter)` (or equivalent per-game fan-out count) — not silently equal to `len(matched_games)`, and not silently unequal without explanation in the UI.

### describe() Fallback Wording (FIX-01)

- The fallback sentence for any `(op, control)` combination not covered by the four existing branches must be **deliberately distinct** from hand-written sentences — e.g. `f"{label} filter applied (value: {value})"` — not a best-effort natural-English blend-in.
- Rationale (from PITFALLS.md Pitfall 4): a fallback that blends in perfectly removes the only signal that a new registry combo needs a real branch, and nobody circles back once the symptom disappears. Visibly-distinct text keeps that pressure alive.
- The fallback's `key` must round-trip through `_query_href_removing` (either matching the existing `ff:{feature_key}` shape or an entry in `_REMOVE_PARAM_MAP`) so the remove `×` link actually works — a broken-but-visible remove link is worse UX than today's silent sentence drop.
- Verify on **both** render surfaces that reuse `describe()`: the system editor's active-filter list and the Current Matches dashboard panel.
- Never use `|safe` — plain Jinja interpolation only, matching the existing project-wide convention (the "Unknown filter" branch already proves this is safe).

### FIX-03 (Documentation Closure)

- Close the Hide Duplicates deferral in `PROJECT.md`'s Out of Scope bullet with the same accurate finding already recorded in the Key Decisions table (done during Phase 6 transition — this task confirms/finalizes it, does not re-derive it).

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `.planning/research/PITFALLS.md` — Pitfall 2 (filter-detail double-count), Pitfall 4 (describe() fallback masking + key round-trip), both with concrete test shapes.
- `.planning/research/ARCHITECTURE.md` — integration points for all three items (from earlier v1.1 milestone research), including the corrected location of `describe()` (`cfb_system_maker/describe.py`, not `web.py`).
- `06-REVIEW.md`/`06-REVIEW-FIX.md` (Phase 6) — a related bug (Max ROI silently discarding filters at domain edges) was just fixed in `filter_modal.js`; the fix pattern (distinguish "user dragged to edge" from "algorithm selected a specific value") is a nearby precedent worth being aware of, though it's a different code path (client-side JS vs. server-side `aggregate_filter_value_rows`/`describe()`).

### Established Patterns
- `_query_href_removing` (`web.py:962`) parses a sentence's `key` field to build remove-link hrefs — any new key shape must round-trip through it.
- Jinja auto-escape only, no `|safe`, project-wide convention.
- `_feature_group_sentence` in `describe.py:58` currently has 4 hardcoded `(op, control)` branches with a silent `return None` fallthrough — this is exactly T-01-03.

### Integration Points
- `cfb_system_maker/describe.py` — `_feature_group_sentence`, needs the fallback branch.
- `cfb_system_maker/web.py:242` — `aggregate_filter_value_rows`, backs `GET /filter-detail`, needs the row-sum-vs-total reconciliation.
- `cfb_system_maker/templates/index.html` — renders `describe()` sentences via `{{ row.text }}`.
- `cfb_system_maker/static/filter_modal.js` — renders the `/filter-detail` per-value table; will need the new reconciliation caption wired in.
- `.planning/PROJECT.md` — Out of Scope bullet for FIX-03.

</code_context>

<specifics>
## Specific Ideas

No specific UI wording beyond the two decisions above (fallback sentence format, row-sum caption) was requested — implementation is free to choose exact phrasing consistent with the existing modal's tone, as long as the two behavioral requirements (visibly distinct fallback, row-sum reconciliation) are met.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. (One question was initially dismissed mid-interactive-discuss on 2026-08-26 before switching to `/gsd-autonomous`; both grey areas were re-presented and resolved via smart-discuss with user-accepted recommended answers.)

</deferred>
