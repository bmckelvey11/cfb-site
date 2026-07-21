# Phase 1: System Editor Main Page - Context

**Gathered:** 2026-07-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Restyle `cfb_system_maker`'s existing system editor page (`templates/index.html` + `web.py`) so a saved/loaded system reads like a Bet Labs system editor: cumulative Money Won Over Time graph, a stat-chip header (Record/Margin/Money Won/ROI/Grade), plain-English active-filter sentences, a Results Graph / Past Matches tab split, and a free-text theory field. The current sidebar + workspace page layout is kept — only the workspace's display/interaction is restyled (filter *popup* modals are Phase 4; Grade *computation* is Phase 2, this phase only ships the chip slot).

</domain>

<decisions>
## Implementation Decisions

### Tabs Implementation
- **D-01:** Results Graph / Past Matches tabs switch via query-param reload (`?tab=graph` / `?tab=matches`), full page GET reload — no client-side JS tab toggling. This matches the existing architecture: every other interaction in the app (filter change, load system, save) already round-trips through a GET/POST form. Keeps loaded-system context automatically since it's carried in the query string like every other control.

### Theory Field Save Flow
- **D-02:** Theory textarea is bundled into the existing main filter form (next to Save Name / Save System button) and saved via the existing `POST /save` endpoint alongside the system's filters — no separate quick-save endpoint. Simpler than adding new routes; consistent with the doc's stated approach.

### Claude's Discretion
- **Money-graph x-axis:** `bet-labs-parity-plan.md` describes the reference graph's x-axis as real calendar dates, but `GameRecord` has no per-game date field (only `season`/`week` ints — see `docs/PROJECT_MAP.md` and `models.py`). Claude will use chronological bet order — sorted by `(season, week)` — as the x-axis, one point per graded bet, cumulative profit sum at $100-flat-stake. This is the closest achievable analog given the current data model; revisit if Phase 3 (Data Depth) adds a real per-game date field.
- **Grade chip placeholder:** EDIT-02 ships the Grade chip *slot* now; the composite grade computation lands in Phase 2 (INTG-02). Claude will render a neutral placeholder (e.g. an em dash "—") in the Grade chip position until Phase 2 wires the real value — not blank/hidden, so the header layout is stable across both phases.
- **Margin chip for total-bet systems:** `docs/bet-labs-parity-plan.md`'s Margin formula (mean of `team_points + side_spread - opp_points`) is spread-bet-specific — `side_spread` has no analog in the total-bet grading path (`_grade_total_bet`). Per `01-RESEARCH.md` Open Question 1, Claude will scope Margin computation to `bet_type == "spread"` systems only and render the same "—" placeholder for `bet_type == "total"` systems, mirroring the Grade-chip precedent above rather than inventing an undocumented totals formula.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Bet Labs Design Reference
- `docs/bet-labs-parity-plan.md` (Phase 1 section, ~lines 90-99) — the locked design this phase executes: Margin formula (avg cover margin = mean of `team_points + side_spread - opp_points` over graded bets), `describe(system) -> list[str]` sentence renderer spec, remove-link = query string minus that filter, theory field storage spec (`SavedSystem.theory: str`, default `""`, backward-compatible).
- `docs/sports-insights-systems-combined-guide.md` — source Bet Labs documentation (26 articles, 13 video walkthroughs) the parity plan was derived from; consult for exact chip/sentence wording conventions if `bet-labs-parity-plan.md` is ambiguous.
- `docs/PROJECT_MAP.md` — standing architecture reference for this brownfield project (read instead of re-mapping the codebase).

### Project Constraints
- `.claude/CLAUDE.md` — tech stack (Python + Flask + vanilla JS/CSS, no frontend framework), no-lookahead rule, storage backward-compatibility rule, CSV schema stability rule.
- `.planning/PROJECT.md` Key Decisions table — "keep current main-page layout" and "Grade chip UI slot ships in Phase 1; computation wires in behind it in Phase 2" are locked project-level decisions, not open questions.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_range_chart()` in `cfb_system_maker/web.py:447` — existing money-won-*by-line* SVG chart (hand-rolled polyline/circle SVG, no charting library). Different axis than the new cumulative graph, but the pattern to follow (no new JS dependency needed) for the Money Won Over Time chart.
- `.metrics` chip-row CSS class in `templates/index.html` (already used for the current plain metrics row, lines 225-232) — restyle target for the new stat-chip header rather than a from-scratch component.

### Established Patterns
- Whole app is server-rendered Flask/Jinja with GET-form-driven state — the query string is the source of truth for filters, and every existing interaction is a full-page reload (informs D-01 above).
- `SystemFilter`, `GameRecord`, `SavedSystem` are frozen dataclasses (`models.py`); `storage.py` has explicit `_system_to_dict()` / `_system_from_dict()` (de)serializers that must both be updated (with a default) for the new `theory` field to stay backward-compatible with systems saved before it existed.

### Integration Points
- `_form_from_system()` / `_system_from_form()` in `web.py` — the round-trip between `SavedSystem`/`SystemFilter` and the form dict; the `theory` field needs a slot in both directions.
- `storage.save_system()` / `load_system()` — currently only persist `SystemFilter`, not free-text metadata like theory; needs a `storage.py` migration analogous to the existing `name`/`saved_at` fields on `SavedSystem`.

</code_context>

<specifics>
## Specific Ideas

No specific requirements beyond what's captured in `docs/bet-labs-parity-plan.md` — the two discussed areas were resolved by going with Claude's recommended option rather than a from-scratch preference.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. The two "Claude's Discretion" items above are in-scope implementation calls, not deferred ideas.

</deferred>

---

*Phase: 1-System Editor Main Page*
*Context gathered: 2026-07-16*
