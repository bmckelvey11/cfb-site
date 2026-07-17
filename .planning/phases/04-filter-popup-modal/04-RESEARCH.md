# Phase 04: Filter Popup Modal - Research

**Researched:** 2026-07-17
**Domain:** Flask/Jinja server-rendered filter editor with vanilla-JavaScript modal exploration
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

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

### Deferred Ideas (OUT OF SCOPE)
- Grade sub-score breakdown panel remains deferred; Phase 4 does not expand the Grade chip.
- My Systems dashboard, Current Matches, bundled examples, and teaser/alternate-line records remain Phase 5.
- Moneyline wager type, public betting percentages, Think Tank, and duplicate-side handling remain project-level out of scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MODAL-01 | Clicking a filter in the sidebar opens a popup modal instead of expanding it inline | Use one native `<dialog>` shell, data-driven launchers, and progressively enhanced canonical controls. [VERIFIED: codebase `templates/index.html`; CITED: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/dialog] |
| MODAL-02 | Modal header shows live Record/Money Won/ROI chips that recompute as the user adjusts controls | Add a lightweight `/api/backtest` response driven by the existing parser, `matches_system`, and `grade_bet`; do not run expensive significance analysis for three chips. [VERIFIED: codebase `web.py`, `backtest.py`; VERIFIED: local benchmark] |
| MODAL-03 | Numeric filters show dual handles, BETWEEN inputs, and per-value money chart | Overlay two native range inputs, synchronize them with number inputs, and consume a one-pass server distribution. [CITED: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/range; VERIFIED: codebase `_range_chart`] |
| MODAL-04 | Categorical/list filters show a searchable, sortable value-performance table | Return deterministic per-value rows; filter and sort the already-returned rows client-side. [VERIFIED: codebase feature domains and existing table styles] |
| MODAL-05 | Modal shows exact About Filter text | Add required, tested descriptions to registry and core metadata; insert them with `textContent`/Jinja escaping. [VERIFIED: codebase `FeatureDef` currently lacks `description`] |
| MODAL-06 | Save commits and closes; Cancel discards | Keep a modal-only draft and mutate canonical form controls only after successful server validation, then submit the existing GET form. [VERIFIED: codebase `filters-form`, `_form_values`, `_system_from_form`] |
</phase_requirements>

## Summary

The phase should extend the existing server-rendered architecture, not introduce a client-side system model. The current `filters-form` and its query string already define canonical state; the modal should read that form into a temporary draft, call read-only JSON endpoints for evidence, and write back only on Save. The sidebar can become a launcher list while the same real controls remain available as the no-JavaScript fallback. [VERIFIED: codebase `web.py`, `templates/index.html`; VERIFIED: CONTEXT D-01–D-05]

The main implementation risk is performance, not dialog markup. A default full-data `run_backtest` currently takes about **2.232 seconds** on 12,964 local games because it also computes system statistics and 1,000-iteration permutation analysis, while matching and grading the same games takes about **0.103 seconds**. A 250 ms live UI cannot call the current full analysis path on every adjustment. Extract or expose a lightweight core-summary path that still uses `matches_system` and `grade_bet`, and compute all per-value rows in one pass rather than invoking `run_backtest` once per value. [VERIFIED: local benchmark on 2026-07-17; VERIFIED: codebase `backtest.py`]

The second risk is contract correctness. Current feature request parsing accepts unknown keys, unsupported operator/control combinations, and unchecked perspectives, while numeric conversion can raise on malformed input. Both new endpoints need one central allowlist/validation layer, and the normal page should reuse it where practical so endpoint and full-page semantics cannot drift. [VERIFIED: codebase `web.py:_feature_filters_from_request`, `_parse_filter_value`; VERIFIED: CONTEXT D-18]

**Primary recommendation:** Build a server-owned filter metadata/resolution layer and lightweight one-pass statistics helpers first, then layer one native `<dialog>` state machine over the existing canonical form. [VERIFIED: codebase architecture; CITED: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/dialog]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Filter definitions, domains, allowed operators/perspectives | API / Backend | Server-rendered Jinja | The server owns registry/core metadata and must reject client-invented semantics. [VERIFIED: CONTEXT D-18–D-20; codebase `features.py`] |
| Current committed system state | Server-rendered form/query string | Browser / Client | `filters-form` remains canonical; the browser only stages a draft. [VERIFIED: CONTEXT D-04–D-05; codebase `web.py`] |
| Modal lifecycle, focus, draft, debounce, stale-response handling | Browser / Client | — | These are transient interaction concerns and must not mutate server state before Save. [VERIFIED: CONTEXT D-04, D-16, D-21] |
| Live summary and per-value statistics | API / Backend | Browser rendering | Matching, grading, ROI, and money must stay authoritative on the server. [VERIFIED: CONTEXT D-08, D-15, D-18] |
| Dialog, table, and SVG presentation | Browser / Client | Jinja initial markup | Existing CSS/SVG language is extended without a frontend/chart dependency. [VERIFIED: CONTEXT D-22–D-23; codebase `styles.css`] |
| Persistent saved systems | Existing storage flow | — | This phase commits form state, not saved-system storage directly. [VERIFIED: codebase `/save`; CONTEXT phase boundary] |

## Project Constraints (from repository instructions)

- Keep changes surgical, simple, and directly traceable to MODAL-01–06; do not refactor adjacent systems. [VERIFIED: `CLAUDE.md`]
- Do not edit vendored `cfbd-python/`; this phase has no reason to touch acquisition code or `GameRecord`/CSV schema. [VERIFIED: `CLAUDE.md`]
- Preserve home-spread sign handling and totals/Fade grading by reusing `matches_system` and `grade_bet`. [VERIFIED: `CLAUDE.md`; codebase `backtest.py`]
- Use top-level Python imports; no inline imports. [VERIFIED: workspace rule `no-inline-imports.mdc`]
- There is no project `.cursor/rules/`, `.claude/.cursor/rules/`, `.cursor/skills/`, or `.agents/skills/` content to add beyond the repository instructions. [VERIFIED: workspace discovery]
- No new dependencies, build step, or linter are expected. [VERIFIED: `CLAUDE.md`, `requirements.txt`, `docs/PROJECT_MAP.md`; CONTEXT D-23]

## Standard Stack

### Core

| Library / Platform | Verified Version | Purpose | Why Standard Here |
|--------------------|------------------|---------|-------------------|
| Python | 3.14.4 | Backend and tests | Existing project runtime. [VERIFIED: local environment] |
| Flask | 3.1.3 | HTML routes plus `/filter-detail` and `/api/backtest` | Existing application framework; returning a dict/list produces JSON and the test client exposes `response.json`. [VERIFIED: local environment; CITED: https://flask.palletsprojects.com/en/stable/quickstart/; CITED: https://flask.palletsprojects.com/en/stable/testing/] |
| Jinja2 | 3.1.6 | Server-rendered launchers, fallback controls, metadata | Existing template layer and auto-escaping boundary. [VERIFIED: local environment; codebase `index.html`] |
| Browser HTML/CSS/JavaScript | Native platform | `<dialog>`, two range inputs, fetch, AbortController, SVG/table rendering | Locked no-framework/no-chart-dependency approach. [VERIFIED: CONTEXT D-23; CITED: MDN sources below] |

### Supporting

| Library | Verified Version | Purpose | When to Use |
|---------|------------------|---------|-------------|
| pytest | 9.0.3 | Helper, endpoint, and rendered-contract tests | Every server contract and progressive-enhancement state. [VERIFIED: local environment; `pytest.ini`] |
| Werkzeug | 3.1.8 | MultiDict/query handling under Flask | Reuse existing `MultiDict` and Flask test-client behavior; do not add a new request library. [VERIFIED: local environment; codebase `web.py`] |

**Installation:** None. This phase should add no packages. [VERIFIED: CONTEXT D-23]

## Package Legitimacy Audit

Not applicable: the prescribed implementation uses only the already-installed project stack and browser APIs. [VERIFIED: CONTEXT D-23; `requirements.txt`]

**Packages removed due to SLOP verdict:** none.
**Packages flagged as suspicious:** none.

## Architecture Patterns

### System Architecture Diagram

```text
Sidebar launcher / Active-filter Edit
                 |
                 v
       one native <dialog> shell
                 |
        create isolated draft
          /              \
         v                v
GET /filter-detail   debounced GET /api/backtest
(candidate removed)  (candidate draft applied)
         |                |
         v                v
one-pass value rows   live Record/Money/ROI
         \                /
          v              v
        modal chart/table + About text
                 |
       Save valid? -- no --> remain open
                 |
                yes
                 v
write canonical controls in filters-form
                 |
                 v
submit existing full-page GET -> URL + main results authoritative

Cancel / close / Escape -> discard draft -> restore launcher focus
```

All arrows preserve server-owned matching and grading; the browser never computes performance. [VERIFIED: CONTEXT D-04, D-08, D-15, D-18]

### Recommended Project Structure

```text
cfb_system_maker/
├── features.py                 # FeatureDef.description and registry metadata
├── backtest.py                 # lightweight summary seam using existing matching/grading
├── web.py                      # core metadata, strict parser, resolvers, two JSON routes
├── describe.py                 # edit identity and paired numeric-range sentence handling
├── templates/index.html        # launchers, canonical fallback controls, one dialog shell
└── static/
    ├── styles.css              # modal, slider, responsive, focus, table/chart styles
    └── filter_modal.js         # modal state machine and rendering
tests/
└── test_filter_modal.py        # focused helpers, JSON contracts, rendered fallback
```

This keeps state/parsing near the existing web flow and avoids a speculative subsystem. [VERIFIED: repository conventions; codebase layout]

### Pattern 1: Server-Owned Filter Descriptor

**What:** Normalize registry and core filters into one web descriptor shape: stable namespaced ID, label, control kind, canonical parameter mapping, options/domain, description, team-scoped flag, allowed operators, allowed perspectives, and lookahead warning. [VERIFIED: codebase has split core fields and `FeatureDef`; CONTEXT D-01, D-18–D-20]

**Recommendation:** Use IDs such as `core:season`, `core:spread_range`, and `feature:weather_temperature`, then resolve only through server dictionaries. Do not accept raw model attribute names or arbitrary feature keys. [VERIFIED: CONTEXT D-18; codebase `FEATURE_BY_KEY`]

**Why:** It lets one modal shell support all required filters without turning the browser into a second registry. [VERIFIED: CONTEXT D-03]

### Pattern 2: Draft / Commit State Machine

**What:** On open, snapshot committed values into a plain draft object. Control changes update only the draft. Save is enabled only after local validity and the latest successful server validation; Save then replaces the candidate's canonical form controls and submits. Cancel clears draft and closes. [VERIFIED: CONTEXT D-04, D-17]

**Important detail:** Reopening or switching filters must abort the old request, increment a request generation counter, and ignore any response whose generation is not current. Abort alone is insufficient as a response may already have completed. [CITED: https://developer.mozilla.org/en-US/docs/Web/API/AbortController; VERIFIED: CONTEXT D-16]

### Pattern 3: Native Dialog With Explicit Lifecycle

**What:** Render one labelled `<dialog>`, open with `showModal()`, listen for `cancel` to route Escape through the same discard path, and explicitly restore focus to the triggering launcher on close. Do not implement backdrop-click dismissal. [CITED: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/dialog; VERIFIED: CONTEXT D-21]

**Why:** `showModal()` supplies top-layer rendering and makes the rest of the document inert; explicit focus restoration satisfies the locked behavior even when content is rerendered. [CITED: https://developer.mozilla.org/en-US/docs/Web/API/HTMLDialogElement/showModal]

### Pattern 4: Progressive Enhancement Around Real Controls

**What:** Keep conventional canonical controls in the DOM and visible by default. The deferred JavaScript adds a root `.js` class only after initialization, hides the fallback editor, reveals launchers, and writes back to those same controls on Save. [VERIFIED: CONTEXT D-05; codebase `filters-form`]

**Why:** This avoids duplicate same-name controls and ensures a failed/disabled script still leaves a complete GET form. [VERIFIED: HTML form behavior and current canonical form]

### Pattern 5: Numeric Range as Existing Filters

**What:** Core spread/total ranges continue using their existing min/max fields. Registry numeric ranges use two `FeatureFilter` entries with the same key and perspective: one `gte`, one `lte`. Remove/edit operations treat the pair as one logical filter. [VERIFIED: `FeatureFilter` supports one operator/value; `feature_ok` supports `gte`/`lte`; CONTEXT D-07]

**Required companion change:** `describe()` should coalesce a same-key numeric `gte` + `lte` pair into one BETWEEN sentence and expose one edit identity; candidate removal must remove both entries before distribution. [VERIFIED: current `describe.py` renders each entry separately; CONTEXT D-03, D-08]

### Pattern 6: One-Pass Per-Value Aggregation

**What:** Parse the committed system, remove every representation of the candidate, then iterate games once:

1. apply `matches_system(game, base_system, feature_map)`;
2. resolve the candidate's core or registry value using the selected perspective;
3. grade the matched game once with `grade_bet(game, base_system)`;
4. add the resulting `BetDetail` to each distinct applicable value bucket;
5. summarize each bucket into wins/losses/pushes, profit, ROI, and `$ = profit * 100`.

[VERIFIED: codebase `matches_system`, `grade_bet`, `resolve_feature_value`; CONTEXT D-08, D-15]

For `either` perspective, a game may contribute to both home and away value buckets, but duplicate equal values should be deduplicated for that game. The live candidate summary still applies `feature_ok`'s “either side may match” behavior once per game. [VERIFIED: codebase `resolve_feature_value`, `feature_ok`]

### Pattern 7: Lightweight Shared Backtest Summary

**What:** Add an explicit lightweight mode/helper that still executes `matches_system` and `grade_bet` but skips `compute_system_stats`, season breakdown, permutation testing, and grade when the caller needs only Record/Money/ROI. [VERIFIED: codebase `run_backtest` currently always computes all analysis; local benchmark]

**Why:** Current full default backtest is ~2.232 s while matching+grading is ~0.103 s on the local dataset. Client cancellation does not stop already-running Python computation, so server efficiency is required in addition to debounce. [VERIFIED: local benchmark; CITED: https://developer.mozilla.org/en-US/docs/Web/API/AbortController]

### Endpoint Contracts

#### `GET /api/backtest`

- Input: the complete current form query with the modal candidate substituted for any committed representation; parse through the same canonical form parser in strict API mode. [VERIFIED: CONTEXT D-15, D-18]
- Success `200 application/json`: minimal deterministic fields for `wins`, `losses`, `pushes`, `hit_rate`, `profit`, `money_won`, and `roi`; include no bet-detail list or significance block. [VERIFIED: required chips; planner discretion on exact names]
- Neutral no-match is `200` with numeric zeros, not an error. [VERIFIED: CONTEXT D-10]
- Invalid key/operator/value/perspective is `400` with a stable plain-text error code/message; missing processed data can be `503`. [VERIFIED: CONTEXT D-17–D-18; codebase missing-data handling]

#### `GET /filter-detail`

- Input: current form query plus one namespaced candidate ID and, for team-scoped registry features, an allowed perspective. The server removes the candidate before matching. [VERIFIED: CONTEXT D-08, D-14, D-18]
- Success `200 application/json`: descriptor metadata, observed exact bounds/options, and deterministic value rows sorted by numeric value or Description ascending. Each row contains server-computed Record/ROI/Money. [VERIFIED: CONTEXT D-08, D-12, D-19]
- Numeric chart responses may cap point density by selecting/downsampling exact observed rows for rendering, but must return exact domain bounds and never use sampled points to evaluate the selected range. [VERIFIED: CONTEXT D-09]
- Empty domain is `200` with empty rows and explicit neutral metadata. [VERIFIED: CONTEXT D-10]
- Unknown candidate or illegal perspective is `400`; registry-dependent candidates without a sidecar should return a deterministic unavailable response rather than a traceback. [VERIFIED: CONTEXT D-17–D-18; codebase optional feature sidecar]

### Core Value Resolution

| Candidate | Exact value used for distribution | Existing source |
|-----------|-----------------------------------|-----------------|
| season / week / provider | `GameRecord.season`, `.week`, `.provider` | Direct fields. [VERIFIED: `models.py`] |
| team / conference | Bet-side team/conference selected from `system.side` | Existing matching semantics. [VERIFIED: `matches_system`] |
| spread range | Side-relative spread, not raw home spread | Existing `_side_spread` sign convention. [VERIFIED: `backtest.py`; `CLAUDE.md`] |
| total range | `GameRecord.total` | Existing matching semantics. [VERIFIED: `matches_system`] |
| registry filter | `resolve_feature_value`, including perspective | Existing feature semantics. [VERIFIED: `features.py`] |

Extract/reuse a resolver for side-relative spread rather than duplicating its sign logic in `web.py`. [VERIFIED: project spread invariant]

### Frontend Rendering Details

- Use two overlaid native `input[type=range]` elements because native range inputs are single-valued and ignore `multiple`; update each input's effective min/max and validate the paired number inputs to prevent crossing. [CITED: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/range]
- Preserve the number inputs as the exact-value interface; the slider is a synchronized convenience layer. [VERIFIED: CONTEXT D-06, D-09]
- Render SVG points from server rows, with `title` or an equivalent accessible value label; use existing `.positive`/`.negative`, zero-line, chip, and chart tokens. [VERIFIED: codebase `index.html`, `styles.css`; CONTEXT D-23]
- Build table rows and definition copy using DOM nodes and `textContent`, never `innerHTML` with server/user strings. [VERIFIED: CONTEXT D-19; CITED: https://owasp.org/www-project-secure-coding-practices-quick-reference-guide/stable-en/02-checklist/05-checklist.html]
- Table sort buttons should expose direction with `aria-sort` on the active column header and remain keyboard buttons. [VERIFIED: CONTEXT D-12, D-21]

### Anti-Patterns to Avoid

- **N backtests for N values:** High-cardinality observed domains reach 25,231 exact values locally; repeated full backtests would be unusable. Aggregate in one pass. [VERIFIED: local domain audit]
- **Client-computed wins/ROI/money:** It can diverge on Fade, totals, pushes, odds, or sign handling. [VERIFIED: codebase grading branches; CONTEXT D-15]
- **Mutating canonical controls while dragging:** Cancel would no longer be a true discard. [VERIFIED: CONTEXT D-04]
- **Only aborting stale fetches:** Keep a generation check because abort races with completed responses. [CITED: https://developer.mozilla.org/en-US/docs/Web/API/AbortController]
- **Hiding fallback controls in base CSS:** If JavaScript fails before enhancement, filters become unusable. [VERIFIED: CONTEXT D-05]
- **One custom div-based ARIA slider:** Two native range inputs provide keyboard semantics with less custom accessibility code. [CITED: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/range]
- **Embedding description HTML:** Definitions are plain text and must be escaped. [VERIFIED: CONTEXT D-19]
- **Returning `asdict(BacktestResult)` wholesale:** It exposes large bet-detail/stat blocks that the live chips do not need. [VERIFIED: codebase `BacktestResult`; planner response-size discretion]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Modal inertness/focus containment | A div overlay plus homegrown page-wide focus trap | Native `<dialog>.showModal()` plus explicit initial/restore focus | Browser supplies top-layer and inert background behavior. [CITED: https://developer.mozilla.org/en-US/docs/Web/API/HTMLDialogElement/showModal] |
| Betting calculations | JavaScript record/ROI/money logic | `matches_system`, `grade_bet`, shared Python summary | Preserves spread, total, Fade, push, and flat-stake semantics. [VERIFIED: codebase `backtest.py`; CONTEXT D-15] |
| Feature authorization | Client metadata as authority | `FEATURE_BY_KEY` plus server core descriptor allowlist | Unknown keys already fail closed in matching but D-18 requires explicit API rejection. [VERIFIED: codebase `features.py`; CONTEXT D-18] |
| Chart package | New chart dependency | Existing SVG/CSS chart vocabulary | Locked dependency-free stack and sufficient chart needs. [VERIFIED: CONTEXT D-23; codebase `_range_chart`] |
| Table/search package | New grid library | Small local array filter/sort | Required behavior is limited to case-insensitive search and four sortable columns. [VERIFIED: CONTEXT D-12, D-23] |
| Second persistence/state store | Browser local storage or modal model persisted separately | Existing form/query-string round trip | Full-page GET remains authoritative. [VERIFIED: CONTEXT D-04–D-05] |

**Key insight:** The hard domain logic already exists; the phase succeeds by exposing it through a strict, lightweight contract and keeping the browser as a draft-and-render layer. [VERIFIED: codebase architecture]

## Common Pitfalls

### Pitfall 1: Full Analysis on Every Keystroke
**What goes wrong:** Live requests take seconds and stack up behind a 250 ms debounce. [VERIFIED: local benchmark]
**Why it happens:** `run_backtest` always computes permutation/system stats and grade, although the modal needs only three chips. [VERIFIED: `backtest.py`]
**How to avoid:** Reuse matching/grading but skip analytical extras through an explicit lightweight seam. [VERIFIED: measured fast path]
**Warning signs:** API latency exceeds the debounce, CPU remains busy after browser aborts, or responses arrive out of order. [VERIFIED: local benchmark; browser cancellation semantics]

### Pitfall 2: Candidate Not Fully Removed
**What goes wrong:** Distribution rows are conditioned on the old candidate, so editing a range shows only its committed slice. [VERIFIED: CONTEXT D-08]
**Why it happens:** Numeric registry ranges are represented by two same-key filters and core ranges by two fields. [VERIFIED: current model and proposed D-07 representation]
**How to avoid:** Candidate removal must clear both core bounds or all same-key `FeatureFilter` entries. [VERIFIED: model semantics]
**Warning signs:** Opening an existing filter changes the domain bounds or omits values outside the saved range. [VERIFIED: CONTEXT D-07–D-08]

### Pitfall 3: Parallel Feature Arrays Lose Alignment
**What goes wrong:** `ff_key`, `ff_op`, `ff_value`, and `ff_perspective` refer to different rows after edit/replace. [VERIFIED: codebase query encoding uses parallel arrays]
**Why it happens:** Updating one list independently shifts indices. [VERIFIED: `_query_args_from_form`, `_feature_filters_from_request`]
**How to avoid:** Decode to structured rows, replace candidate rows structurally, then rebuild all arrays together. [VERIFIED: existing remove-link alignment test pattern]
**Warning signs:** Editing one feature changes another or perspective appears on the wrong filter. [VERIFIED: current storage shape]

### Pitfall 4: Continuous Domains Explode Payload/DOM
**What goes wrong:** A numeric feature can produce tens of thousands of unique values and rows. [VERIFIED: local audit; `pregame_win_prob` observed 25,231 unique values]
**Why it happens:** `_scan_values` preserves exact floats and team-scoped features may yield two observations per game. [VERIFIED: `web.py:_scan_values`]
**How to avoid:** One-pass aggregation, deterministic chart point capping, lazy numeric list rendering if needed, and never altering exact bounds/live evaluation. [VERIFIED: CONTEXT D-09; planner discretion on response shape]
**Warning signs:** Multi-megabyte `/filter-detail` responses or long main-thread row insertion. [VERIFIED: local cardinality]

### Pitfall 5: Permissive API Parsing
**What goes wrong:** Crafted keys/operators/perspectives cause silent zero results, inconsistent UI, or numeric conversion 500s. [VERIFIED: current parser]
**Why it happens:** Existing page parsing was designed for trusted generated form controls, not a public JSON contract. [VERIFIED: `web.py`]
**How to avoid:** Validate key namespace, control/operator compatibility, perspective, finite numeric values, ordered bounds, and list membership/size server-side. [CITED: https://owasp.org/www-project-secure-coding-practices-quick-reference-guide/stable-en/02-checklist/05-checklist.html; VERIFIED: CONTEXT D-18]
**Warning signs:** Unknown filters return `200`, NaN/Infinity enters results, or malformed floats return `500`. [VERIFIED: parser behavior]

### Pitfall 6: Cancel Leaks Draft State
**What goes wrong:** Cancel, close, or Escape leaves hidden form values changed; the next Run System commits unintended state. [VERIFIED: CONTEXT D-04]
**Why it happens:** Modal controls directly alias canonical inputs during editing. [VERIFIED: common implementation risk inferred from current form]
**How to avoid:** Copy on open, write on Save only, clear draft on every close path, and test canonical form values before/after cancellation. [VERIFIED: CONTEXT D-04]
**Warning signs:** URL is unchanged but submitting the main form applies canceled values. [VERIFIED: canonical form behavior]

### Pitfall 7: Dialog Accessibility Regressions
**What goes wrong:** Focus disappears, Escape commits, dynamic table sorting is mouse-only, or focus returns to the wrong launcher. [VERIFIED: CONTEXT D-21]
**Why it happens:** One reused shell has changing content and multiple entry points. [VERIFIED: CONTEXT D-03]
**How to avoid:** Track the invoker, set labelled initial focus after render, route `cancel` to discard, restore invoker focus, use buttons for sort, and retain visible `:focus-visible` styles. [CITED: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/dialog]
**Warning signs:** Keyboard tab reaches the background, close cannot be activated, or screen reader title is missing. [CITED: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/dialog_role]

## Code Examples

Verified patterns from official sources and the current code:

### JSON Route and Test Shape

```python
# Source: https://flask.palletsprojects.com/en/stable/quickstart/
@app.get("/api/backtest")
def api_backtest():
    # parse request.args through the project allowlist
    return {"wins": 1, "losses": 0, "pushes": 0, "profit": 0.9091, "roi": 0.9091}

# Source: https://flask.palletsprojects.com/en/stable/testing/
response = client.get("/api/backtest", query_string={"side": "home"})
assert response.status_code == 200
assert response.json["wins"] == 1
```

Returning a dict is Flask's documented JSON shortcut, and `query_string`/`response.json` are the documented test path. [CITED: Flask sources above]

### Stale-Request Cancellation

```javascript
// Source: https://developer.mozilla.org/en-US/docs/Web/API/AbortController
let controller;
let generation = 0;

async function refresh(url) {
  controller?.abort();
  controller = new AbortController();
  const current = ++generation;
  const response = await fetch(url, { signal: controller.signal });
  const data = await response.json();
  if (current !== generation) return;
  renderLiveMetrics(data);
}
```

Create a new controller for each request because an aborted signal is one-use. [CITED: https://developer.mozilla.org/en-US/docs/Web/API/AbortSignal]

### Native Modal Open/Cancel

```javascript
// Source: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/dialog
let invoker;

function openFilter(button) {
  invoker = button;
  renderDraft();
  dialog.showModal();
  dialog.querySelector("[autofocus]")?.focus();
}

dialog.addEventListener("cancel", (event) => {
  event.preventDefault();
  discardAndClose();
});

dialog.addEventListener("close", () => invoker?.focus());
```

The project must keep Cancel, close-button, and Escape on the same discard path. [VERIFIED: CONTEXT D-04, D-21]

### Registry Numeric Range Representation

```python
# Source: current FeatureFilter model + feature_ok gte/lte semantics
feature_filters = (
    FeatureFilter(key=key, op="gte", value=minimum, perspective=perspective),
    FeatureFilter(key=key, op="lte", value=maximum, perspective=perspective),
)
```

Replace all prior same-key entries atomically rather than appending this pair to an existing candidate. [VERIFIED: current tuple model; CONTEXT D-07–D-08]

## State of the Art

| Old Approach | Current Recommended Approach | Impact |
|--------------|------------------------------|--------|
| Custom div overlay and manual inert/focus trap | Native `<dialog>.showModal()` plus explicit lifecycle | Less accessibility code and browser-provided modal behavior. [CITED: MDN dialog docs] |
| Let every response update the UI | Abort prior fetch and check request generation | Prevents stale metrics from replacing a newer draft. [CITED: MDN AbortController docs] |
| One range input with nonstandard `multiple` | Two synchronized native range inputs | `multiple` is ignored for range inputs. [CITED: MDN range docs] |
| Full `BacktestResult` JSON per adjustment | Minimal core summary using shared grading | Meets live latency/payload needs without calculation drift. [VERIFIED: local benchmark and current result model] |
| Inline free-text categorical entry | Server rows plus checkbox selection/search/sort | Satisfies exact, discoverable `in` semantics. [VERIFIED: CONTEXT D-11–D-12] |

**Deprecated/outdated for this phase:**
- Current sidebar `<details>` feature editors are replaced as the primary JavaScript UI but retained/reworked as conventional fallback controls. [VERIFIED: CONTEXT D-01, D-05]
- The current single-operator numeric registry UI is insufficient for BETWEEN ranges; use paired existing filters. [VERIFIED: codebase `index.html`; CONTEXT D-06–D-07]
- The main-page line-only `_range_chart` is a visual precedent, not the data algorithm for arbitrary candidate features. [VERIFIED: `_range_chart`; CONTEXT D-08–D-09]

## Likely Plan Decomposition

### Plan 04-01 — Metadata, strict parsing, and summary seams
- Add exact registry/core descriptions and unified descriptors; test completeness, units/timing warnings, namespaces, operators, and perspectives. [VERIFIED: CONTEXT D-18–D-20]
- Harden request parsing and paired numeric representation/removal/coalesced descriptions. [VERIFIED: current parser/model gaps]
- Extract lightweight shared summary logic while preserving default full backtests. [VERIFIED: performance benchmark]

### Plan 04-02 — JSON detail/live contracts
- Implement one-pass candidate-removed distribution and `/filter-detail`. [VERIFIED: CONTEXT D-08]
- Implement minimal `/api/backtest` with strict validation and neutral/error contracts. [VERIFIED: CONTEXT D-10, D-15, D-17–D-18]
- Add focused endpoint tests for spread/total, Fade, pushes, perspective, malformed input, empty domains, and high-cardinality capping. [VERIFIED: grading branches and locked behavior]

### Plan 04-03 — Progressive modal shell and lifecycle
- Convert sidebar filter editors to grouped launchers while retaining real fallback controls and lookahead quarantine. [VERIFIED: CONTEXT D-01–D-05]
- Add one native dialog, active-sentence Edit controls, About panel, responsive CSS, focus/Cancel/close/Escape behavior, and canonical Save+GET submit. [VERIFIED: CONTEXT D-03–D-05, D-19–D-22]
- Verify no-JavaScript form use and escaped definitions. [VERIFIED: D-05, D-19]

### Plan 04-04 — Numeric and value-table interactions
- Implement dual range synchronization, invalid-state Save lockout, chart/list rendering, and neutral states. [VERIFIED: CONTEXT D-06–D-10]
- Implement categorical search/sort/multiselect and boolean single-select, including team perspective defaults/preservation. [VERIFIED: CONTEXT D-11–D-14]
- Add debounce, AbortController, generation checks, loading/last-success/error/Retry behavior, then perform keyboard/responsive manual acceptance. [VERIFIED: CONTEXT D-16–D-17, D-21–D-22]

This ordering makes the server contract testable before browser behavior depends on it and leaves visual interaction as one coherent final slice. [VERIFIED: repository TDD convention and dependency direction]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| — | None. Recommendations are grounded in locked context, live code, local measurements, or cited official documentation. | — | — |

## Open Questions

No blocking product decisions remain; D-01 through D-23 determine the behavior. The planner still needs to choose exact JSON field names, chart point cap, and whether numeric List view is fetched lazily, all explicitly within Claude's discretion as long as exact bounds/live metrics are preserved. [VERIFIED: CONTEXT Claude's Discretion and D-09]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | Flask application/tests | Yes | 3.14.4 | — |
| Flask | HTML and JSON endpoints | Yes | 3.1.3 | — |
| Jinja2 | Server-rendered metadata/fallback | Yes | 3.1.6 | — |
| pytest | Validation suite | Yes | 9.0.3 | — |
| Browser `<dialog>`, fetch, AbortController, range, SVG | Modal interaction | Expected in current Chromium-class runtime; not separately browser-probed | Native APIs | Conventional no-JavaScript controls remain usable if script APIs fail. |

Versions were probed locally on 2026-07-17. [VERIFIED: local environment]

**Missing dependencies with no fallback:** none. [VERIFIED: local environment]

**Missing dependencies with fallback:** no package dependency is missing; no-JavaScript conventional controls are the interaction fallback. [VERIFIED: CONTEXT D-05]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 with Flask 3.1.3 test client. [VERIFIED: local environment] |
| Config file | `pytest.ini` (`testpaths = tests`). [VERIFIED: codebase] |
| Quick run command | `python -m pytest tests/test_filter_modal.py -x` |
| Full suite command | `python -m pytest` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MODAL-01 | Sidebar renders launchers, one dialog, grouped registry/lookahead state, and usable canonical fallback controls | Flask rendered-contract integration | `python -m pytest tests/test_filter_modal.py -x -k "launcher or fallback or lookahead"` | No — Wave 0 |
| MODAL-02 | Live endpoint returns authoritative Record/Money/ROI for spread, total, Fade, push, and neutral cases | Flask endpoint + backtest integration | `python -m pytest tests/test_filter_modal.py -x -k "api_backtest"` | No — Wave 0 |
| MODAL-03 | Numeric descriptor/domain/detail rows and paired range serialization are exact; rendered shell has two handles and BETWEEN inputs | Helper/endpoint/rendered-contract | `python -m pytest tests/test_filter_modal.py -x -k "numeric or range"` | No — Wave 0 |
| MODAL-04 | Categorical rows are deterministic and boolean domain is exactly Yes/No; multi-select parses to `in` | Helper/endpoint integration | `python -m pytest tests/test_filter_modal.py -x -k "categorical or boolean"` | No — Wave 0 |
| MODAL-05 | Every registry/core filter has escaped, non-empty exact definition and lookahead warning | Unit + rendered security contract | `python -m pytest tests/test_filter_modal.py -x -k "description or escaped"` | No — Wave 0 |
| MODAL-06 | Save serialization replaces candidate atomically and GET form remains canonical; cancel paths leave controls untouched | Python serialization/rendered contract plus manual browser interaction | `python -m pytest tests/test_filter_modal.py -x -k "serialize or commit"` | No — Wave 0 |

### Additional Contract Coverage

- Reject unknown namespaced IDs, invalid operator/control pairs, illegal perspectives, malformed/non-finite values, reversed bounds, oversized lists, and candidate values outside returned categorical options with `400` JSON. [VERIFIED: CONTEXT D-17–D-18; OWASP input-validation guidance]
- Verify `/filter-detail` removes both numeric bounds/all same-key candidate entries while preserving every other filter and Fade. [VERIFIED: CONTEXT D-08, D-15]
- Verify core spread rows use side-relative spread and team/conference rows use bet-side identity. [VERIFIED: codebase matching invariants]
- Verify team-scoped `either` contributes to distinct applicable buckets without duplicating an equal home/away value. [VERIFIED: feature semantics]
- Verify full-data response schemas omit bet details/statistical analysis and point capping is deterministic. [VERIFIED: response-size discretion; local cardinality]
- Keep existing `tests/test_web.py` remove-link, load/query round-trip, theory escaping, Fade, and tabs tests green. [VERIFIED: existing suite]

### Browser-Only Acceptance

The repository has no JavaScript unit/browser test harness and D-23 forbids adding a frontend dependency. Use one end-of-phase manual browser pass for: keyboard-only open/sort/slider/Save/Cancel, focus restoration, Escape discard, Retry after forced endpoint failure, stale-response race, backdrop behavior, narrow-screen stacking, and horizontal table scroll. [VERIFIED: repository test stack; CONTEXT D-16–D-23]

Rendered-contract tests should assert semantic markup and script hooks, but they cannot prove focus movement, range dragging, or fetch races. [VERIFIED: pytest/Flask test-client capabilities]

### Sampling Rate

- **Per task commit:** `python -m pytest tests/test_filter_modal.py -x`
- **Per wave merge:** `python -m pytest tests/test_web.py tests/test_web_features.py tests/test_filter_modal.py -x`
- **Phase gate:** `python -m pytest` plus the browser-only acceptance pass before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_filter_modal.py` — focused metadata, parser, aggregation, endpoint, rendering, and serialization coverage for MODAL-01–06.
- [ ] Tiny deterministic game/feature fixtures inside that file or existing shared fixtures — avoid full 12,964-game/permutation work in quick tests.
- [ ] No framework install or test config change is needed. [VERIFIED: existing pytest setup]

## Security Domain

Security enforcement is enabled at ASVS Level 1. [VERIFIED: `.planning/config.json`]

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| Authentication | No | Local read-only editor endpoints introduce no authentication mechanism. [VERIFIED: current app and phase boundary] |
| Session Management | No | Canonical state remains in the query string/form; no new session state. [VERIFIED: CONTEXT D-04–D-05] |
| Access Control | Limited | Explicit server allowlists for candidate IDs, operators, values, and perspectives. [VERIFIED: CONTEXT D-18] |
| Input Validation | Yes | Positive server-side validation on `request.args`; reject malformed/unknown combinations before computation. [CITED: https://owasp.org/www-project-secure-coding-practices-quick-reference-guide/stable-en/02-checklist/05-checklist.html] |
| Output Encoding | Yes | Flask JSON serialization, Jinja auto-escaping, and DOM `textContent`; never eval or inject HTML. [CITED: https://flask.palletsprojects.com/en/stable/quickstart/; CITED: OWASP source above] |
| Cryptography | No | No secrets, credentials, or cryptographic operation enters this phase. [VERIFIED: phase boundary] |

### Known Threat Patterns for Flask + Dynamic DOM

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Reflected/stored/DOM XSS through descriptions, labels, error text, or categorical values | Tampering / Elevation | Keep definitions plain text; Jinja auto-escape; construct DOM with `textContent`; do not use `safe` or `innerHTML`. [VERIFIED: CONTEXT D-19; CITED: OWASP output-encoding guidance] |
| Parameter tampering with arbitrary keys/operators/perspectives | Tampering | Namespaced allowlist, control-aware operator matrix, perspective allowlist, finite type parsing, categorical membership validation. [VERIFIED: CONTEXT D-18] |
| Computation denial of service through huge lists/repeated high-cardinality backtests | Denial of Service | Bound list length, debounce, lightweight summary, one-pass distribution, deterministic point cap, no N×backtest loops. [VERIFIED: local benchmark/cardinality audit] |
| Stale response overwrites a newer draft | Tampering (integrity) | Abort previous request and enforce generation identity before rendering/enabling Save. [CITED: MDN AbortController; VERIFIED: CONTEXT D-16–D-17] |
| Client-forged performance values | Tampering | Browser sends only filter draft; server computes every metric. [VERIFIED: CONTEXT D-15, D-18] |
| GET endpoint accidentally mutates saved/committed state | Tampering | Keep both endpoints read-only, with no storage writes or canonical-form mutation. [VERIFIED: CONTEXT D-18] |

OWASP ASVS 5.0.0 is the current stable ASVS release, and OWASP guidance requires trusted server-side input validation and context-aware output encoding. [CITED: https://owasp.org/www-project-application-security-verification-standard/; CITED: https://owasp.org/www-project-secure-coding-practices-quick-reference-guide/stable-en/02-checklist/05-checklist.html]

## Sources

### Primary (HIGH confidence)
- Live repository: `cfb_system_maker/web.py`, `features.py`, `backtest.py`, `models.py`, `describe.py`, `templates/index.html`, `static/styles.css`, `tests/test_web.py`, and `tests/test_web_features.py` — current contracts, gaps, and reusable helpers. [VERIFIED: codebase]
- Local runtime and data benchmark on 2026-07-17 — Python/Flask/Jinja/pytest/Werkzeug versions, 12,964-game latency, lightweight matching/grading latency, and domain cardinality. [VERIFIED: local execution]
- Phase context D-01–D-23 and MODAL-01–06 requirements. [VERIFIED: `.planning/phases/04-filter-popup-modal/04-CONTEXT.md`; `.planning/REQUIREMENTS.md`]

### Secondary (MEDIUM confidence)
- https://flask.palletsprojects.com/en/stable/quickstart/ — JSON responses and query arguments. [CITED]
- https://flask.palletsprojects.com/en/stable/testing/ — `query_string` and `response.json` test patterns. [CITED]
- https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/dialog — modal focus, Escape, and dialog accessibility behavior. [CITED]
- https://developer.mozilla.org/en-US/docs/Web/API/HTMLDialogElement/showModal — top-layer/inert behavior. [CITED]
- https://developer.mozilla.org/en-US/docs/Web/API/AbortController and https://developer.mozilla.org/en-US/docs/Web/API/AbortSignal — request cancellation and one-use signals. [CITED]
- https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/range — native range semantics and ignored `multiple`. [CITED]
- https://owasp.org/www-project-application-security-verification-standard/ and OWASP secure coding checklist — ASVS currency, server validation, and output encoding. [CITED]

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — installed versions and project constraints were probed directly.
- Architecture: HIGH — recommendations follow locked D-01–D-23 and current live code seams.
- Pitfalls: HIGH — parser/model gaps were read directly and performance/cardinality risks were measured locally.
- Browser API details: MEDIUM — confirmed from current official MDN documentation through web search.

**Research date:** 2026-07-17
**Valid until:** 2026-08-16 (stable stack and locked phase scope)
