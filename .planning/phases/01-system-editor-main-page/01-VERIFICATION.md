---
phase: 01-system-editor-main-page
verified: 2026-07-17T06:35:42Z
status: human_needed
score: 5/5 roadmap success criteria verified (plus 20+ plan-level must-have truths verified by source inspection, grep, and live Flask test-client behavior)
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Load or construct a system with 10+ simultaneously active filters (several core fields + several feature filters) so the `.active-filters-panel` renders 10+ sentence rows, and view the workspace at a typical viewport width."
    expected: "The `.active-filters` grid (display:grid; gap:8px; no max-height/scroll region) does not visually collide with the `.tabs` nav or the sections rendered below it."
    why_human: "01-04-PLAN.md's must_haves flags this explicitly as `verification: backstop` — CSS source (confirmed present: `.active-filters { display: grid; gap: 8px; ... }` with no max-height) proves the rule as written, but whether 10+ rows visually collide with adjacent sections is a rendered-layout judgment call, not something grep/static analysis can determine."
  - test: "Save a system with a long (280+ character) theory string and one containing non-ASCII/emoji characters, reload the page, and view the `.theory-panel` and sidebar `<textarea>` rendering in a browser."
    expected: "Long/unicode text wraps within the panel (`white-space: normal; overflow-wrap: anywhere`, confirmed present in styles.css) with no horizontal overflow and no truncation or mojibake."
    why_human: "01-05-PLAN.md's must_haves flags this explicitly as `verification: backstop`. The SUMMARY claims a manual round-trip check was already done (35-char unicode + 300-char strings survived save/load without truncation), but actual on-screen wrap behavior in a real browser viewport was not independently re-confirmed by this verification pass."
---

# Phase 1: System Editor Main Page Verification Report

**Phase Goal:** A saved system's main page reads like a Bet Labs system editor — stat chips (Record/Margin/Money Won/ROI/Grade), cumulative money-won graph, plain-English active filter sentences with remove links, and a persisted theory field — instead of the plain metrics-row/inline-form layout it replaced.
**Verified:** 2026-07-17T06:35:42Z
**Status:** human_needed
**Re-verification:** No — initial verification

**Process note:** ROADMAP.md marks this phase `Mode: mvp`, but neither the ROADMAP goal text nor the goal text supplied for this verification is phrased as a User Story (`gsd_run query user-story.validate` returns `valid: false`). Since ROADMAP.md already supplies five concrete, observable Success Criteria (not just a single user-outcome clause), this report proceeds with standard goal-backward verification against those criteria rather than refusing outright — MVP-mode's User-Flow-Coverage narrowing would add no additional rigor here. Flagging the mode/goal-format mismatch for the developer to resolve (e.g. via `/gsd mvp-phase 1`) is recommended but is not itself a phase-goal blocker.

## Goal Achievement

### Observable Truths (ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Cumulative "Money Won Over Time" line graph, sorted by season/week, $100-flat-stake convention | ✓ VERIFIED | `_cumulative_chart()` in `web.py:594-629` sorts `bet_details` by `(season, week, game_id)`, computes a running raw-stake-unit sum; template renders it in `.cumulative-chart` (index.html:318-330) with SVG `<title>` scaled `* 100`. Live test-client GET confirmed "Money Won Over Time" renders on the default/graph tab with real (non-empty, non-zero) chart data from `data/games.csv`. |
| 2 | Stat-chip header (Record, Margin, Money Won, ROI, Grade slot) replacing the plain metrics row | ✓ VERIFIED | `templates/index.html:227-233` renders exactly 5 `<article>` chips in order under `class="metrics stat-chips"`. Live GET rendered `Record: 194-204-6, 48.7%`, `Margin: 0.3` (positive), `Money Won: -$2,763` (negative), `ROI: -6.84%` (negative), `Grade: —`. `BetDetail.margin`/`BacktestResult.average_margin` are computed in `backtest.py` (spread-only, guarded by `bets and system.bet_type == "spread"`, line 50). |
| 3 | Each active filter renders as a plain-English sentence (e.g. "the spread is between -14 and -3") with a remove control | ✓ VERIFIED | `describe()` in `cfb_system_maker/describe.py` is a pure function producing `{text, key}` rows; `web.py`'s `index()` wires `sentences = describe(system)` and attaches `remove_href` via `_query_href_removing()`/`_REMOVE_PARAM_MAP`. Live GET with `favorite=on&min_spread=-14&max_spread=-3&filter_seasons=2023` rendered exactly the sentences "the team is a favorite", "the spread is between -14 and -3", "the season is 2023", each with a working `aria-label="Remove filter: ..."` anchor whose href correctly omits only that filter's param(s) while preserving the others. Empty-state copy "No filters applied yet — every game in the dataset is included." confirmed present when `sentences == []` (source + 01-04 test). |
| 4 | Switch between Results Graph and Past Matches tabs without losing loaded-system context | ✓ VERIFIED | `index()` normalizes `tab = "matches" if request.args.get("tab") == "matches" else "graph"` (web.py:82, exact literal expression matching the must_have). Live GETs confirmed: default tab shows the cumulative graph and hides the bets table; `?tab=matches` hides the graph and shows the bets table; `?tab=garbage` normalizes to the graph view. `_query_href()` preserves the full query string (including `load_system`) across tab links via `MultiDict`+`urlencode`. |
| 5 | Write/save a free-text theory on a saved system, see it displayed above the filter list on reload | ✓ VERIFIED | `SavedSystem.theory: str = ""` (models.py:116); `storage.save_system(..., theory=...)`/`load_saved_system()` persist/read it backward-compatibly (`payload.get("theory", "")`, no KeyError on legacy files — confirmed via source and passing `test_load_saved_system_backward_compatible_with_missing_theory_key`). Live end-to-end test: POSTed `/save` with `theory="Fade the public on primetime road dogs."`, then GET `/?load_system=...` rendered `.theory-panel` positioned directly above `.active-filters-panel` in document order (index.html:235-252) containing the exact escaped theory text, plus the sidebar `<textarea name="theory">` pre-filled with the same text. |

**Score:** 5/5 roadmap success criteria verified.

### Plan-Level Must-Haves (spot-checked beyond the roadmap SCs)

| Must-have (source plan) | Status | Evidence |
|---|---|---|
| `average_margin` spread-only, `None`/0.0 for totals (01-01) | ✓ VERIFIED | `backtest.py:50` guard `bets and system.bet_type == "spread"`; `_grade_total_bet` has no `margin=` kwarg (grep confirmed). |
| Money Won zero renders unsigned `$0`, not `+$0`/`-$0` (01-01) | ✓ VERIFIED | Template ternary at index.html:230 has an explicit `{% else %}$0{% endif %}` branch. |
| Grade chip never fabricates a value (01-01 prohibition) | ✓ VERIFIED | index.html:232 is a bare literal `&mdash;` with no conditional/class; `grep -rn "grade\b" cfb_system_maker/*.py` (excluding `grade_bet`) returns zero matches — no Grade-computation logic exists anywhere in the codebase yet. |
| Positive/negative chip color classes (01-01 backstop) | ✓ VERIFIED (elevated from backstop) | Live GET rendered `class="positive"` on Margin and `class="negative"` on Money Won/ROI for a losing system — confirms the CSS-class logic executes correctly at runtime, not just in source. |
| `_cumulative_chart` empty-shape/ordering/no-merge/raw-units (01-02) | ✓ VERIFIED | Source at web.py:594-629 matches the documented algorithm exactly; unit tests pass. |
| Tab normalization exact expression (01-02 backstop) | ✓ VERIFIED (elevated from backstop) | `grep` confirms the literal `tab = "matches" if request.args.get("tab") == "matches" else "graph"` expression; live `?tab=garbage` test confirms fallback behavior. |
| `describe()` sentence semantics mirror `matches_system()` gating (01-03 prohibition, judgment-tier) | ✓ VERIFIED (elevated from backstop) | Direct side-by-side read of `backtest.py:99-159` vs `describe.py:39-57` confirms: favorite/underdog/spread_range gated on `bet_type == "spread"` in both; total_range ungated in both; home/away/seasons/weeks/teams/conferences/providers ungated in both. Structural match confirmed, not just test-asserted. |
| Unknown feature key renders visible warning, never silently dropped (01-03, blocker-severity fix) | ✓ VERIFIED | describe.py:70-76 appends a warning sentence and `continue`s (never a bare skip); `test_describe_unknown_feature_key_renders_warning_sentence` passes. |
| Remove-link materializes loaded-system state, drops `load_system`, keeps `ff_*` arrays aligned (01-04) | ✓ VERIFIED | `_query_args_from_form`/`_query_href_removing` in web.py; integration tests for spread-range, feature-filter, and save→load→remove round trips all pass. |
| Theory backward compatibility / no `\|safe` XSS surface (01-05) | ✓ VERIFIED | `grep -n "\|safe" cfb_system_maker/templates/index.html` returns no matches; stored-XSS regression test passes; live theory text rendered escaped. |
| Active-filters grid layout doesn't collide with 10+ filters (01-04 backstop) | ⚠️ HUMAN NEEDED | CSS rule exists as documented (`display:grid; gap:8px`, no scroll region) but actual visual collision at 10+ rows requires a rendered-browser check — see Human Verification below. |
| Theory long-text/unicode wraps without overflow (01-05 backstop) | ⚠️ HUMAN NEEDED | CSS rule exists as documented (`white-space: normal; overflow-wrap: anywhere`); SUMMARY claims a manual data round-trip check was done, but on-screen wrap rendering was not independently re-verified in this pass — see Human Verification below. |

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `cfb_system_maker/models.py` | `BetDetail.margin`, `BacktestResult.average_margin`, `SavedSystem.theory` | ✓ VERIFIED | All three fields present with documented defaults. |
| `cfb_system_maker/backtest.py` | margin computation, spread-only guard | ✓ VERIFIED | Lines 50, 229-252. |
| `cfb_system_maker/describe.py` | `describe()` pure function | ✓ VERIFIED | New file, no Flask import, all branches implemented. |
| `cfb_system_maker/storage.py` | `load_saved_system()`, `save_system(..., theory=)` | ✓ VERIFIED | Lines 79-121; `load_system()`/`_system_from_dict()` untouched. |
| `cfb_system_maker/web.py` | `_cumulative_chart`, `_query_href`, `_query_href_removing`, `_REMOVE_PARAM_MAP`, `describe()` wiring | ✓ VERIFIED | All present and wired into `index()`'s render context. |
| `cfb_system_maker/templates/index.html` | stat-chip header, tabs, active-filters panel, theory panel/textarea | ✓ VERIFIED | All sections present in correct document order (chips → theory panel → active-filters → tabs → tab content), confirmed live. |
| `cfb_system_maker/static/styles.css` | `.metrics.stat-chips`, `.tabs`, `.cumulative-chart`, `.active-filters*`, `.theory-*` | ✓ VERIFIED | All classes present. |

### Key Link Verification

| From | To | Via | Status |
|---|---|---|---|
| `grade_bet()`/`run_backtest()` | `.metrics.stat-chips` Margin chip | `result.average_margin` passed to template | ✓ WIRED |
| `_cumulative_chart(result)` | `.cumulative-chart` SVG | `cumulative_chart` render kwarg | ✓ WIRED |
| `describe(system)` | `.active-filters-panel` | `sentences` render kwarg with `remove_href` attached | ✓ WIRED |
| `index()`'s `tab` normalization | `{% if tab == 'graph' %}` conditional | `tab` render kwarg | ✓ WIRED |
| `storage.load_saved_system()` | sidebar textarea + `.theory-panel` | `saved.theory` → `_form_from_system(..., saved.theory)` → `form.theory` | ✓ WIRED |

### Data-Flow Trace (Level 4)

All chart/chip data traced to `run_backtest()` output over real `data/games.csv`/`data/features.json` — live GET requests against the actual bundled dataset produced non-trivial, varying values (194-204-6 record, -6.84% ROI, non-empty cumulative chart points), not static/hardcoded placeholders. ✓ FLOWING.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Full test suite | `.venv/Scripts/python.exe -m pytest -q` | 137 passed | ✓ PASS |
| Stat-chip rendering with real filters | Flask test-client GET `/?side=home&favorite=on&min_spread=-14&max_spread=-3&filter_seasons=2023` | 5 chips rendered with correct sign classes | ✓ PASS |
| Tab default/matches/garbage normalization | Flask test-client GET `/`, `/?tab=matches`, `/?tab=garbage` | Graph/table mutually exclusive as documented; garbage falls back to graph | ✓ PASS |
| Theory save → load → display | Flask test-client POST `/save` then GET `/?load_system=...` | `.theory-panel` renders directly above `.active-filters-panel` with escaped text | ✓ PASS |
| No fabricated Grade computation anywhere in codebase | `grep -rn "grade\b" cfb_system_maker/*.py` (excluding `grade_bet`) | 0 matches | ✓ PASS |
| Debt markers in phase-modified files | `grep -n -E "TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER"` across all modified files | 0 matches | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| EDIT-01 | 01-02 | Cumulative Money Won Over Time graph | ✓ SATISFIED | See Truth #1 |
| EDIT-02 | 01-01 | Stat-chip header | ✓ SATISFIED | See Truth #2 |
| EDIT-03 | 01-03, 01-04 | Plain-English active filter sentences w/ remove | ✓ SATISFIED | See Truth #3 |
| EDIT-04 | 01-02 | Results Graph / Past Matches tabs | ✓ SATISFIED | See Truth #4 |
| EDIT-05 | 01-05 | Persisted theory field | ✓ SATISFIED | See Truth #5 |

No orphaned requirements — every EDIT-0x ID in REQUIREMENTS.md's Phase-1 traceability table is claimed by exactly one plan's `requirements:` frontmatter (EDIT-03 is claimed by both 01-03 and 01-04, reflecting its backend/UI split, not a conflict).

### Anti-Patterns Found

None. No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` markers, no empty stub returns, and no hardcoded-empty props in any file modified by this phase.

### Human Verification Required

### 1. Active-filter panel layout with 10+ simultaneous filters

**Test:** Build or load a system with 10+ active filters (several core fields plus several feature filters) so the `.active-filters` list renders 10+ rows, then view the workspace.
**Expected:** The list (`display:grid; gap:8px`, no `max-height`/scroll region) does not visually collide with the `.tabs` nav or sections below it.
**Why human:** Explicitly flagged `verification: backstop` in 01-04-PLAN.md's must_haves — CSS source matches the documented rule, but whether it visually collides at 10+ rows is a rendered-layout judgment call.

### 2. Theory panel long-text / unicode wrapping

**Test:** Save a system with a 280+ character theory string and one containing emoji/non-Latin characters; reload and view both the sidebar `<textarea>` and the `.theory-panel`.
**Expected:** Text wraps (`white-space: normal; overflow-wrap: anywhere`) with no horizontal overflow, truncation, or mojibake.
**Why human:** Explicitly flagged `verification: backstop` in 01-05-PLAN.md's must_haves. The SUMMARY claims this was manually checked once already (data round-trip only, no browser screenshot), but this verification pass did not independently re-confirm on-screen wrap rendering.

### Gaps Summary

No gaps found. All five roadmap Success Criteria and every plan-level must-have with an automatable verification path are confirmed VERIFIED via source inspection, `grep`, the full passing test suite (137/137), and live Flask test-client behavioral checks against the real bundled dataset. The only open items are two CSS-layout/visual checks that the plans themselves explicitly deferred to manual/visual confirmation (`verification: backstop`) — these route to human_needed per the verification decision tree, not to gaps_found, since the underlying code/CSS is present, correct, and wired.

---

_Verified: 2026-07-17T06:35:42Z_
_Verifier: Claude (gsd-verifier)_
