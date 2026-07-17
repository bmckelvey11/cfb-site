---
phase: 1
reviewers: [gemini, codex]
reviewed_at: "2026-07-17T04:44:20Z"
plans_reviewed:
  - 01-01-PLAN.md
  - 01-02-PLAN.md
  - 01-03-PLAN.md
  - 01-04-PLAN.md
  - 01-05-PLAN.md
---

# Cross-AI Plan Review — Phase 1

## Gemini Review

Gemini review failed or returned empty output. stderr:
Please set an Auth method in your C:\Users\mckel\.gemini\settings.json or specify one of the following environment variables before running: GEMINI_API_KEY, GOOGLE_GENAI_USE_VERTEXAI, GOOGLE_GENAI_USE_GCA

*(Gemini CLI is installed but not authenticated in this environment — no review was obtained. Claude was skipped by design: this review is running inside Claude Code itself, so a same-model self-review would not be independent.)*

---

## Codex Review

# Cross-AI Plan Review — Phase 1

## Overall Summary

Plans show strong source awareness and sensible wave ordering. Two blockers prevent execution as written: remove links cannot modify loaded systems, and `describe()` hides unknown filters even though backtest rejects every game for them. Tab fallback, feature perspective wording, cumulative-dollar presentation, and theory preservation also need correction. Overall verdict: **request changes; HIGH risk**.

Current baseline verified: **94 tests passed in 3.13s**. Plans remain unimplemented. No files changed.

---

### Plan 01 — Stat-Chip Header

**Summary:** Margin computation fits existing grading path. Dataclass additions preserve compatibility. Visual implementation and tests need tightening because shared `.metrics` styling also changes unrelated statistics panel.

**Strengths:**
- Reusing existing `cover_margin` is correct. Grading already computes `team_points + spread - opponent_points`; persisting that value avoids formula drift. [cfb_system_maker/backtest.py:227]
- Trailing defaults preserve existing direct `BetDetail` and `BacktestResult` construction. [cfb_system_maker/models.py:67](cfb_system_maker/models.py:67), [cfb_system_maker/models.py:93](cfb_system_maker/models.py:93)
- Dollar conversion stays presentation-only — backend profit/ROI stay in stake units. [cfb_system_maker/backtest.py:30](cfb_system_maker/backtest.py:30)

**Concerns:**
- **MEDIUM:** Changing `.metrics` to five columns also changes `.metrics.stats-panel` — both sections share the same class, despite the plan saying the stats panel stays untouched. [templates/index.html:225](cfb_system_maker/templates/index.html:225), [templates/index.html:234](cfb_system_maker/templates/index.html:234), [static/styles.css:242](cfb_system_maker/static/styles.css:242)
- **MEDIUM:** Proposed web tests only replace `"Bets"` with `"Record"` — would not catch wrong chip order, missing Grade placeholder, backend dollar multiplication, wrong classes, or totals-Margin behavior. [tests/test_web.py:7](tests/test_web.py:7), [tests/test_web.py:22](tests/test_web.py:22)

**Suggestions:**
- Introduce a dedicated `.stat-chips` class or scope the grid rule to `.metrics:not(.stats-panel)`.
- Add rendered-markup tests covering exact 5-label order, total-system Margin placeholder, negative values, zero bets, all-pushes, neutral Grade styling.
- Define zero Money Won as `$0`, not misleading `+$0`/`-$0`.

**Risk:** MEDIUM — computation sound; presentation regression and weak verification likely.

---

### Plan 02 — Cumulative Graph and Tabs

**Summary:** Chronological aggregation and query-preserving links fit the current server-rendered design. Proposed tab normalization and graph presentation do not fulfill the stated behavior.

**Strengths:**
- Sorting by `(season, week, game_id)` matches existing chronological ordering conventions. [cfb_system_maker/backtest.py:171](cfb_system_maker/backtest.py:171)
- Reusing the hand-built SVG pattern avoids new dependencies, matches `_range_chart()`. [cfb_system_maker/web.py:447](cfb_system_maker/web.py:447)
- `MultiDict` preservation is appropriate — feature filters use repeated request values. [cfb_system_maker/web.py:306](cfb_system_maker/web.py:306)

**Concerns:**
- **HIGH:** Invalid-tab fallback is internally contradictory. Plan passes raw `request.args.get("tab", "graph")`, but template branches on `if tab == "graph" ... else ...` — so `?tab=foo` renders Past Matches, not the graph fallback the plan claims.
- **HIGH:** Proposed cumulative SVG never renders dollar values — only polyline, circles, zero-line, bet-count x-axis. No `profit * 100`, dollar y-axis, tooltip, or point label exists anywhere. Graph shape alone can't demonstrate the required `$100`-stake convention (EDIT-01). Profit stays in stake units at [cfb_system_maker/backtest.py:30](cfb_system_maker/backtest.py:30).
- **MEDIUM:** Planned integration test checks preserved query params inside an href but never follows that href to confirm the same loaded system/filters/results survive. [cfb_system_maker/web.py:46](cfb_system_maker/web.py:46)

**Suggestions:**
- Normalize explicitly: `tab = "matches" if request.args.get("tab") == "matches" else "graph"`.
- Add an invalid-value test for `?tab=foo`.
- Render dollar y-axis labels and per-point `<title>`/accessible text using `point.profit * 100`.
- Follow generated tab links in tests; verify loaded system, filters, tab, and results all survive.

**Risk:** HIGH — normal-tab behavior works, but malformed-tab handling and the required money convention are not implemented as claimed.

---

### Plan 03 — `describe()`

**Summary:** Pure-module approach is good. Two semantic gaps make displayed descriptions diverge from actual backtest behavior.

**Strengths:**
- Separating descriptions from Flask enables later reuse, follows the existing pure-domain module pattern.
- Spread-only gating matches real filter logic (favorite/underdog/spread-range live only in the spread branch; total-range also applies to spread systems). [cfb_system_maker/backtest.py:98](cfb_system_maker/backtest.py:98), [cfb_system_maker/backtest.py:134](cfb_system_maker/backtest.py:134)
- Stable keys provide a workable contract for remove-link construction.

**Concerns:**
- **HIGH:** Unknown feature keys must not be silently skipped. `feature_ok()` returns `False` for unknown keys, making the system match **zero games** — but the planned `describe()` would emit no sentence, letting the UI imply every game is included. Directly misrepresents the backtest. [cfb_system_maker/features.py:257](cfb_system_maker/features.py:257)
- **HIGH:** Feature sentences omit `perspective`. Real feature resolution distinguishes home/away/bet-side/opponent/either-team, but "Returning PPA is at least 0.5" doesn't say which team's value drives the filter. [cfb_system_maker/features.py:211](cfb_system_maker/features.py:211)
- **MEDIUM:** Required ordering and implementation instructions conflict — wrapping favorite/underdog/spread-range in one outer spread block naturally places spread-range before home/away, contrary to the declared order. The proposed ordering test doesn't exercise spread-range + home/away together, so it wouldn't catch the drift.

**Suggestions:**
- Render unknown filters as visible warnings with removal keys (e.g. `Unknown filter "x" is unavailable`) — never hide them.
- Include perspective in team-scoped feature sentences ("Bet-side Returning PPA…", "Opponent Recruiting Rank…", "Either team…").
- Implement three separate ordered sections: favorite/underdog, home/away, then spread-range.
- Add one test covering every core key plus multiple feature filters together.
- Test descriptions against `matches_system()` semantics, not just expected strings.

**Risk:** HIGH — user-facing description can materially disagree with the actual matched-game set.

---

### Plan 04 — Active Filters and Remove Links

**Summary:** Query surgery works for systems built directly from query parameters. It fails for saved/loaded systems — the phase's central use case.

**Strengths:**
- Core key map correctly accounts for actual form names (e.g. `filter_seasons`) rather than assuming model-field names equal request names. [cfb_system_maker/web.py:215](cfb_system_maker/web.py:215)
- Removing a feature key only from `ff_enable` matches the current form mechanism. [templates/index.html:130](cfb_system_maker/templates/index.html:130), [cfb_system_maker/web.py:306](cfb_system_maker/web.py:306)
- Accessible removal label includes the sentence text.

**Concerns:**
- **HIGH (blocker):** Remove links are **no-ops for loaded systems**. A loaded URL normally contains only `load_system=name`. The helper preserves that param and removes filter params that were never present. The next request reloads the unchanged saved `SystemFilter`, overriding whatever query-built state the remove link tried to produce. [cfb_system_maker/web.py:46](cfb_system_maker/web.py:46), [cfb_system_maker/web.py:48](cfb_system_maker/web.py:48), [cfb_system_maker/web.py:50](cfb_system_maker/web.py:50)
- **HIGH:** Planned tests cover query-built systems only — none saves a system, loads it, clicks a generated remove link, and verifies the filter/results actually changed. [tests/test_web.py:65](tests/test_web.py:65)
- **LOW:** The feature-removal test's "other unset features are unaffected" claim proves little — should use ≥2 enabled feature filters and remove one.

**Suggestions:**
- Serialize the loaded `SystemFilter` into full canonical query params before building the removal href (then omit `load_system`), or add an explicit removal override applied after load.
- Prefer route-built sentence rows carrying a final resolved `remove_href` — the helper needs resolved system state, not raw request state.
- Add an end-to-end test: save a two-filter system → load → follow one remove link → confirm one sentence disappears, the other remains, and the bet count changes.
- Test removing one of two enabled feature filters.

**Risk:** HIGH — core EDIT-03 interaction fails specifically on saved/loaded systems, this phase's primary use case.

---

### Plan 05 — Theory Field

**Summary:** Storage migration is backward-compatible and preserves the existing `load_system()` contract. Form behavior loses unsaved theory during the normal Run System flow, and security verification is too shallow.

**Strengths:**
- Separate `load_saved_system()` avoids breaking the CLI and existing `load_system() -> SystemFilter` tests. [cfb_system_maker/storage.py:91](cfb_system_maker/storage.py:91), [tests/test_storage_systems.py:5](tests/test_storage_systems.py:5)
- Top-level `theory` belongs on `SavedSystem`, not nested in `SystemFilter` — keeps metadata and system state cleanly separated. [cfb_system_maker/storage.py:104](cfb_system_maker/storage.py:104)
- `payload.get("theory", "")` correctly supports legacy files.
- Defaulted trailing dataclass field preserves existing constructors. [cfb_system_maker/models.py:109](cfb_system_maker/models.py:109)

**Concerns:**
- **MEDIUM:** `_form_values()` is instructed to hardcode `"theory": ""`. The main form uses GET, so typing theory then clicking Run System sends theory but the route discards it — user must retype before saving. [templates/index.html:17](cfb_system_maker/templates/index.html:17), [cfb_system_maker/web.py:203](cfb_system_maker/web.py:203)
- **MEDIUM:** XSS verification only greps for `|safe` — doesn't prove payload encoding. Stored free text is a new trust boundary and deserves a behavioral test.
- **LOW:** Plan explicitly accepts unlimited theory size — local-only scope lowers risk, but a huge POST can create unnecessarily large saved files and rendered pages.

**Suggestions:**
- Read theory on GET via `request.args.get("theory", "")`, or separate the theory/save controls so Run System can't discard it.
- Add test: type theory + submit GET + confirm textarea retains text, then save.
- Add a stored-XSS test using `<script>` and quoted HTML; assert escaped output, no executable markup.
- Add a reasonable length limit (e.g. 5–10 KB) with a clear validation message.

**Risk:** MEDIUM — persistence design sound; normal editing flow and security verification incomplete.

---

### Codex Final Risk Assessment

**Overall risk: HIGH.**

Required changes before execution:
1. Redesign loaded-system filter removal (Plan 04 blocker).
2. Never hide unknown feature filters (Plan 03 blocker).
3. Include team perspective in feature descriptions (Plan 03).
4. Normalize invalid tab values (Plan 02).
5. Make the cumulative graph visibly dollar-based (Plan 02).
6. Preserve theory across Run System (Plan 05).
7. Strengthen rendered HTML and end-to-end tests (all plans).

After these changes, wave structure remains suitable: Plans 01/03 parallel, then 02, 04, 05.

*(Baseline verified: 94 tests passed in 3.13s before review. Plans as written were not executed — no files changed.)*

---

## Consensus Summary

Only one grounded reviewer (Codex) completed — Gemini could not authenticate, Claude was self-skipped for independence. This is a single-source review, not a cross-AI consensus; treat every finding below as Codex's verdict alone, not corroborated by a second model.

### Codex's Highest-Priority Findings (both rated blocker-level HIGH)

1. **Plan 04 — remove links are no-ops for loaded/saved systems.** The remove-href helper only strips query params that were present in the request; a loaded system's URL carries just `load_system=name`, so the next request just reloads the unchanged saved filter. This breaks EDIT-03's remove-control requirement specifically for the phase's central use case (a saved/loaded system), not the query-built-system path the plan's own tests cover.
2. **Plan 03 — unknown feature keys are silently hidden instead of surfaced.** `feature_ok()` in `features.py` returns `False` (zero matching games) for an unknown feature key, but `describe()` as planned emits no sentence for it — so the UI can claim "every game is included" while the backtest is actually filtering everything out. A trust-surface bug, not cosmetic.

### Other Concerns Worth Weighing

- Plan 02's `?tab=<invalid>` fallback contradicts its own stated behavior (falls through to Past Matches instead of Results Graph).
- Plan 02's cumulative graph never actually surfaces dollar values (`profit * 100`) anywhere in the rendered SVG — EDIT-01's "$100-flat-stake convention" isn't visually demonstrated.
- Plan 01's shared `.metrics`/`.metrics.stats-panel` CSS class means the 5-column grid change leaks into the untouched stats panel.
- Plan 05's GET-path `theory` handling loses in-progress (unsaved) theory text across a normal Run System click.
- Several plans' proposed tests are asserted to be too shallow (broad string checks) to catch the regressions above — a repeated pattern, not isolated to one plan.

### Not Independently Verified

Every finding above comes from Codex's own read of the repo (it cites concrete `file:line` evidence throughout, and confirmed the 94-test baseline before reviewing). No second reviewer corroborated or disputed any of it. Recommend fixing Gemini's auth (or configuring another reviewer) before treating this as a full cross-AI signal, especially for Plan 03/04's two blocker-level findings.
