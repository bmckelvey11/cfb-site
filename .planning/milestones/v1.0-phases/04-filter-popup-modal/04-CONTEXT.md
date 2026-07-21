# Phase 4: Filter Popup Modal - Context

**Gathered:** 2026-07-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace inline sidebar filter editing with a Bet Labs-style modal workflow. A user launches a filter, explores its values and historical performance without changing the current system, then explicitly saves or cancels. The modal supports live Record/Money Won/ROI, numeric range exploration, categorical/list selection, exact filter definitions, and editing from active-filter sentences.

This phase does not add new wager types, dashboard behavior, upcoming-game matching, teaser records, or new data sources.

</domain>

<decisions>
## Implementation Decisions

### Modal launch and commit lifecycle
- **D-01:** Every filtering constraint presented in the sidebar uses the modal workflow: registry features plus season, week, team, conference, provider, and spread/total ranges. Bet type, spread/total side, position toggles, Fade, theory, load, Run System, and Save System remain global editor controls rather than modal filters.
- **D-02:** Keep the current sidebar + workspace layout. The sidebar becomes a grouped launcher list; registry groups and the `result_lookahead` visual quarantine remain intact.
- **D-03:** Use one reusable modal shell for both adding and editing. Clicking a sidebar launcher opens a clean draft; clicking an active-filter sentence's **Edit** control opens the same modal prefilled. Existing Remove behavior remains a separate one-click action.
- **D-04:** Modal changes are draft-only. **Cancel**, the close button, and Escape discard the draft and leave the system/query string unchanged. **Save Filter** validates the draft, writes the canonical controls back to `filters-form`, closes the modal, and submits the existing full-page GET flow so the main results and URL remain authoritative.
- **D-05:** Preserve progressive enhancement. The server-rendered form/query-string path remains canonical, and a no-JavaScript fallback retains usable conventional controls rather than making filter configuration impossible.

### Numeric range exploration
- **D-06:** Numeric filters use synchronized dual handles and explicit `BETWEEN [min] AND [max]` number inputs. Both directions stay in sync, crossing handles is prevented, and Save is disabled while values are invalid or reversed.
- **D-07:** Opening a new numeric filter starts at the observed domain bounds. Editing starts at the committed bounds. The saved result is a lower-and-upper range constraint; the planner should reuse the current `FeatureFilter` model where possible rather than introduce a second filter model solely for the modal.
- **D-08:** The distribution is computed with the candidate filter removed while all other current-system filters remain applied. Each plotted/table value shows the historical Record, ROI, and Money for that individual value; the live header separately shows the result of applying the current candidate range.
- **D-09:** Numeric filters default to chart view and offer the documented Chart/List toggle. Preserve exact underlying values and statistics; visual bucketing/downsampling is allowed only for rendering a high-cardinality chart and must not alter the selected bounds or live metrics.
- **D-10:** Empty domains and no-match candidate ranges render an explicit neutral state (`0-0-0`, `$0`, `0%`, with explanatory copy) instead of a broken chart or stale values.

### Categorical and boolean selection
- **D-11:** Categorical filters use a searchable, sortable checkbox table with Description, Record, ROI, and Money columns. Multi-select is allowed and saved as the existing `in` semantics; no free-text comma entry remains in the primary modal UI.
- **D-12:** Search filters the already-returned rows client-side and is case-insensitive. Default ordering is Description ascending for predictability; every performance column is sortable in both directions.
- **D-13:** Boolean filters use the same value-table language but present exactly two single-choice rows, Yes and No. Save requires one choice.
- **D-14:** Team-scoped registry features expose perspective inside the modal. Spread systems default new filters to Bet-side; total systems default to Either. Existing filters always preserve their committed perspective.

### Live metrics and data contract
- **D-15:** The header always shows Record, Money Won, and ROI for `current system + current modal draft`. It updates while controls move, before Save, and uses the same grading/backtest path as the main page so spread sign, totals, Fade, pushes, and flat-stake money cannot diverge.
- **D-16:** Debounce live requests at roughly 250 ms and cancel/ignore stale responses. Keep the last successful values visible with a loading indicator; do not flash zeros during ordinary recalculation.
- **D-17:** A failed live request shows a compact inline error with Retry. It does not close the modal, mutate committed form state, or replace the last successful metrics. Save remains unavailable when the current draft has not been successfully validated.
- **D-18:** `/filter-detail` and `/api/backtest` are JSON-only read endpoints. Candidate keys, operators, values, and perspectives must be parsed through server-side allowlists/current form parsing; never trust arbitrary feature keys or client-computed performance numbers.

### Definitions, accessibility, and visual behavior
- **D-19:** Add exact, plain-text definitions to filter metadata. Registry filters source About Filter copy from `FeatureDef.description`; core filters receive equivalent server-owned metadata. Definitions are rendered as text with normal Jinja/DOM escaping, never trusted HTML.
- **D-20:** Definitions must explain units, directionality, perspective, and entering-game timing where relevant. `result_lookahead` filters repeat the analysis-only warning inside the modal, not only in the sidebar.
- **D-21:** Use an accessible dialog interaction: labelled title, focus moved into the modal and restored to its launcher, keyboard-operable controls/table sorting, Escape as Cancel, visible focus states, and explicit Save/Cancel buttons. Backdrop clicks do not commit or silently discard work.
- **D-22:** Desktop layout uses a wide content area plus right-side About panel. Narrow screens stack the About panel below the controls, keep actions reachable, and allow the value table to scroll horizontally without overflowing the page.
- **D-23:** Stay within Flask + Jinja + vanilla JavaScript/CSS. Reuse the existing stat-chip, table, positive/negative color, and SVG chart language; add no frontend framework or chart dependency.

### Claude's Discretion
- Exact modal dimensions, spacing, animation duration, loading indicator treatment, and chart point density are implementation choices, provided the behavior and accessibility decisions above hold.
- Exact JSON field names and internal helper boundaries are planner decisions. Responses should remain small, deterministic, and directly testable.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap and requirements
- `.planning/ROADMAP.md` §"Phase 4: Filter Popup Modal" — phase goal, dependencies, and five success criteria.
- `.planning/REQUIREMENTS.md` §"Filter Popup Modal" — locked MODAL-01 through MODAL-06 requirements.
- `.planning/PROJECT.md` — core value, active endpoint requirements, project constraints, and the locked decision to retain the current main-page layout.

### Bet Labs behavior and visual target
- `docs/bet-labs-parity-plan.md` §"1.3 Filter detail modal" and §"Phase 2 — Filter popup modals" — canonical modal anatomy, per-value behavior, endpoint intent, and sidebar-as-launcher design.
- `docs/sports-insights-systems-combined-guide.md` — underlying Sports Insights/Bet Labs documentation; use only where the parity plan leaves wording or behavior ambiguous.

### Prior phase decisions
- `.planning/phases/01-system-editor-main-page/01-CONTEXT.md` — query-string/full-page state model, retained sidebar/workspace layout, active-filter sentences, and existing chart/chip patterns.
- `.planning/phases/02-integrity-fade-grade/02-CONTEXT.md` — Fade/Grade behavior that live modal metrics must preserve.
- `.planning/phases/03-data-depth-breadth/03-CONTEXT.md` — registry growth, no-lookahead rules, new feature groups, and lookahead quarantine.

### Brownfield architecture and code
- `docs/PROJECT_MAP.md` §§7–9 — feature registry flow, web architecture, and no-new-dependencies convention. Treat live code as authoritative where this snapshot is stale.
- `cfb_system_maker/templates/index.html` — current inline `<details>` controls, `filters-form`, active-filter sentences, stat chips, and server-rendered SVGs.
- `cfb_system_maker/static/styles.css` — existing visual tokens, responsive rules, chips, tables, charts, and filter-panel styling to extend.
- `cfb_system_maker/web.py` — current routes, form parsing, backtest execution, `_feature_options`, `_scan_values`, and `_range_chart`.
- `cfb_system_maker/features.py` — `FeatureDef`, `FEATURE_REGISTRY`, allowlisted feature keys, control kinds, team perspectives, and filter evaluation.
- `cfb_system_maker/backtest.py` — authoritative matching, grading, profit, ROI, Fade, and totals behavior for both JSON endpoints.
- `cfb_system_maker/describe.py` — active-filter sentence keys and the integration point for Edit launch metadata.
- `tests/test_web.py` — established Flask client assertions and the primary home for endpoint/modal rendering tests.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `filters-form` and `_form_values`/`_system_from_form`: canonical query-string round trip; modal Save should feed this path rather than inventing separate persisted client state.
- `run_backtest`, `matches_system`, and existing result serialization: one authoritative source for live chips and per-value grading.
- `_range_chart` and the server-rendered SVG/CSS chart language: useful presentation precedent, though the new endpoint must return general per-value data rather than line-only coordinates.
- `_feature_options`/`_scan_values`: existing observed-domain discovery for numeric and categorical registry filters.
- Existing stat chips, tables, `.positive`/`.negative`, and active-filter sentence rows provide the visual vocabulary for the modal.

### Established Patterns
- Flask/Jinja server rendering with vanilla JS and GET query parameters as the system state.
- `SystemFilter` and `FeatureFilter` are frozen dataclasses; form parsing constructs new immutable values.
- Feature keys come from `FEATURE_BY_KEY`; null feature values fail closed; team-scoped values depend on perspective.
- User-controlled strings use URL encoding and Jinja auto-escaping. The same rule applies to search labels, descriptions, query construction, and error text.

### Integration Points
- Add JSON routes inside `create_app`; load games/features through the same paths as `index`.
- Replace sidebar filter controls in `index.html` with launchers plus canonical hidden/fallback controls.
- Add Edit metadata/actions to `describe()` output or its web-layer enrichment while preserving existing Remove links.
- Extend `FeatureDef`/web-owned metadata with descriptions and expose control/domain/perspective metadata to the modal.
- Add modal behavior as a small static vanilla-JS asset or an inline module consistent with the current app; keep styling in `static/styles.css`.

</code_context>

<specifics>
## Specific Ideas

- Replicate the Bet Labs interaction, not a generic settings dialog: title left, live chips right, exploratory distribution in the main area, About Filter on the right, and a prominent Save Filter action.
- Performance-by-value is exploratory evidence, while the header is the candidate range/selection result. Keep these concepts visually distinct.
- The existing main page is liked and remains structurally intact; this phase changes how filters are configured, not the overall product shell.

</specifics>

<deferred>
## Deferred Ideas

- Grade sub-score breakdown panel remains deferred; Phase 4 does not expand the Grade chip.
- My Systems dashboard, Current Matches, bundled examples, and teaser/alternate-line records remain Phase 5.
- Moneyline wager type, public betting percentages, Think Tank, and duplicate-side handling remain project-level out of scope.

</deferred>

---

*Phase: 4-Filter Popup Modal*
*Context gathered: 2026-07-17*
