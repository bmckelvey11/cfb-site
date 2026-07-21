# Phase 1: System Editor Main Page - Research

**Researched:** 2026-07-16
**Domain:** Server-rendered Flask/Jinja UI restyle (no new dependencies) — stat chips, SVG cumulative chart, plain-English filter descriptions, query-param tabs, free-text field with backward-compatible storage migration.
**Confidence:** HIGH (all findings verified directly against this repo's own source and a live test run — no external library research was needed; this phase introduces no new packages).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01 — Tabs Implementation:** Results Graph / Past Matches tabs switch via query-param reload (`?tab=graph` / `?tab=matches`), full page GET reload — no client-side JS tab toggling. This matches the existing architecture: every other interaction in the app (filter change, load system, save) already round-trips through a GET/POST form. Keeps loaded-system context automatically since it's carried in the query string like every other control.

**D-02 — Theory Field Save Flow:** Theory textarea is bundled into the existing main filter form (next to Save Name / Save System button) and saved via the existing `POST /save` endpoint alongside the system's filters — no separate quick-save endpoint. Simpler than adding new routes; consistent with the doc's stated approach.

### Claude's Discretion

**Money-graph x-axis:** `bet-labs-parity-plan.md` describes the reference graph's x-axis as real calendar dates, but `GameRecord` has no per-game date field (only `season`/`week` ints). Claude will use chronological bet order — sorted by `(season, week)` — as the x-axis, one point per graded bet, cumulative profit sum at $100-flat-stake convention. This is the closest achievable analog given the current data model; revisit if Phase 3 (Data Depth) adds a real per-game date field.

**Grade chip placeholder:** EDIT-02 ships the Grade chip *slot* now; the composite grade computation lands in Phase 2 (INTG-02). Claude will render a neutral placeholder (e.g. an em dash "—") in the Grade chip position until Phase 2 wires the real value — not blank/hidden, so the header layout is stable across both phases.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope. The two "Claude's Discretion" items above are in-scope implementation calls, not deferred ideas. Explicitly NOT in Phase 1 (confirmed against `REQUIREMENTS.md` Out of Scope / phase boundaries, not a discussion outcome but load-bearing for planning): filter *popup* modals (Phase 4, MODAL-01..06), Fade System / Hide Duplicates toggles (Phase 2/3, INTG-01), actual Grade computation (Phase 2, INTG-02), Widget/Copy/Rename/Delete top-right controls, teaser-record popover on the Record chip (Phase 5, DASH-04), My Systems dashboard (Phase 5).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EDIT-01 | Cumulative "Money Won Over Time" graph, sorted season/week, running profit at $100-flat-stake | See "Cumulative Chart" pattern below; reuses `_range_chart`'s hand-rolled SVG technique with a new `_cumulative_chart()` function; `$100 flat stake` = existing `result.profit` (computed at `stake=1.0`) × 100 |
| EDIT-02 | Stat-chip header: Record, Margin, Money Won, ROI, Grade slot | Restyle existing `.metrics` block; Margin is a **new** field requiring a `backtest.py` addition (see "Margin Computation"); Grade renders `—` placeholder only |
| EDIT-03 | Plain-English filter sentences with per-row remove control | New pure-function `describe(system) -> list[str]` + a **separate** query-string "remove href" builder in `web.py`; op-phrase mapping table below |
| EDIT-04 | Results Graph / Past Matches tabs, no lost context | `?tab=` query param per D-01; requires a **query-preserving link helper** verified against installed werkzeug 3.1.8 (see "Query-String Helper") |
| EDIT-05 | Free-text theory field, saved + shown above filter list | New `theory: str = ""` field on `SavedSystem`; storage (de)serializers need a **new accessor** since `storage.load_system()` currently returns bare `SystemFilter`, not the full `SavedSystem` (see "Storage Migration") |
</phase_requirements>

## Summary

This phase is a pure UI/backend restyle of an existing, fully-functional Flask+Jinja app — **no new packages, no new routes beyond what already exists** (`GET /`, `POST /save`), no client-side JavaScript framework. Every piece of underlying data (Record, ROI, Money Won, per-bet detail, per-season breakdown) is already computed by `backtest.run_backtest()`; this phase is almost entirely about (a) one new pure computation (Margin), (b) one new rendering function (`describe()` for plain-English sentences), (c) one new chart function (cumulative Money Won Over Time, following the existing `_range_chart` hand-rolled-SVG pattern), (d) a `?tab=` query-param split of the existing workspace, and (e) a backward-compatible storage field (`theory`) threaded through `SavedSystem`/`storage.py`/`web.py`.

The single trickiest piece is **not** the charting or the styling — it's building correct, query-string-preserving hrefs for the tab links and per-filter remove links, since the whole app's state lives in the URL and there is no JS to patch it client-side. This is fully solvable with `werkzeug.datastructures.MultiDict` (verified against the installed werkzeug 3.1.8 in this repo's `.venv`) but needs a single shared helper, not ad hoc string concatenation in five different template spots.

**Primary recommendation:** Add a small, Flask/request-independent module (or a clearly separated section of `web.py`) with a pure `describe(system: SystemFilter) -> list[dict]` function (plain-English text + a stable per-row `key` for building remove-hrefs), keep it separate from a request-scoped `_query_href(...)` helper in `web.py` that does the actual query-string surgery via `werkzeug.datastructures.MultiDict`. Reuse the pure `describe()` in Phase 4 ("Current Matches" per-game filter details, per `bet-labs-parity-plan.md` step 13) without re-deriving it from a live Flask request.

## Architectural Responsibility Map

This is a single-tier server-rendered application — there is no separate frontend/backend split, no client JS state, and no API boundary. All "tiers" below collapse onto one Flask process; the map below is about *where within that process* each capability's logic belongs, since that's the real seam in this codebase (pure functions vs. request-scoped Flask helpers vs. Jinja template).

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Money Won Over Time (cumulative) chart data | Backend (Flask/`web.py`, new `_cumulative_chart()`) | Browser (inline SVG, no JS) | Pure aggregation over `result.bet_details`, same pattern as existing `_range_chart` |
| Stat-chip values (Record/Margin/Money Won/ROI) | Backend — Margin needs a `backtest.py` addition | Browser (Jinja render only) | Margin is a genuine new computation over `BetDetail`s; the rest already exist on `BacktestResult` |
| Grade chip | Browser (static placeholder) | — | No computation this phase — literal template placeholder, wired to real data in Phase 2 |
| Plain-English filter sentences (`describe()`) | Backend — pure function, framework-independent | Browser (render only) | Must NOT depend on Flask `request` — Phase 4 ("Current Matches") reuses it outside a request-driven filter-editing context |
| Remove-filter links | Backend (`web.py`, request-scoped) | — | Genuinely query-string / `request.args`-specific; does not belong in the pure `describe()` function |
| Results Graph / Past Matches tabs | Backend (`web.py` route, conditional render by `?tab=`) | Browser (plain `<a>` links) | Server decides which panel renders; browser only follows links — consistent with D-01 |
| Theory field | Storage (`storage.py` JSON) | Backend (`web.py` form round-trip) | New persisted field on `SavedSystem`; needs a backward-compatible reader for pre-existing saved systems |

## Standard Stack

### Core (existing — no changes)
| Library | Version (verified in this repo's `.venv`) | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Flask | 3.1.3 `[VERIFIED: .venv importlib.metadata]` | Web framework, routing, Jinja integration | Already the whole web layer; CLAUDE.md forbids new dependencies |
| Werkzeug | 3.1.8 `[VERIFIED: .venv importlib.metadata]` | `request.args` MultiDict, underlies Flask | Needed for query-string-preserving hrefs (tabs, remove-links) |
| Jinja2 | 3.1.6 `[VERIFIED: .venv importlib.metadata]` | Templating | Existing `templates/index.html` pattern |
| Python | 3.14.4 (installed interpreter) `[VERIFIED: .venv]` | Runtime | Existing `from __future__ import annotations` + frozen dataclasses style |

### Supporting
None — no new packages. Per `CLAUDE.md` convention #6 ("No new dependencies. Stdlib + Flask + pytest is the whole stack.") and `docs/PROJECT_MAP.md` §9, this is a hard project rule, not a suggestion.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled inline SVG for the cumulative chart (following `_range_chart`) | Chart.js / D3 / any JS charting lib | Violates the no-new-dependencies rule and the "no client-side JS framework" tech constraint from `.claude/CLAUDE.md`; hand-rolled SVG is already proven in this codebase (`_range_chart`) and sufficient for a polyline+dots chart |
| Client-side JS tab toggling (`<div>` show/hide) | `?tab=` query-param full reload | Rejected explicitly by D-01 — would break the "every interaction round-trips through GET/POST" architecture and complicate keeping tab state in sync with loaded-system state |

**Installation:** None required.

**Version verification:** Confirmed directly via `.venv/Scripts/python.exe -c "import importlib.metadata as m; print(m.version('flask'))"` etc. — see Sources.

## Package Legitimacy Audit

**Not applicable.** This phase installs no external packages (confirmed against `requirements.txt`, which only lists `cfbd-python/requirements.txt`, `pytest`, and `Flask` — all pre-existing). No `npm`/`pip` install commands appear in any plan for this phase.

## Architecture Patterns

### System Architecture Diagram

```
 Browser (GET request, plain <a>/<form>, no client JS state)
    │
    │  querystring carries ALL state: filters, load_system=, tab=
    ▼
 Flask route  GET /  (web.py: create_app().index)
    │
    ├─▶ load_processed_games()/load_features()  ── data/processed/{games.csv,features.json}
    │
    ├─▶ resolve loaded system ──▶ storage.load_system() / (NEW) storage.load_saved_system()
    │        │                         └─ data/systems/{name}.json  (theory lives here)
    │        ▼
    │   _system_from_form() / _form_from_system()   (existing round-trip, +theory)
    │
    ├─▶ run_backtest(games, system, feature_map)   (backtest.py — existing)
    │        │
    │        ├─▶ BacktestResult.bet_details  ──▶ (NEW) _cumulative_chart()  ──▶ SVG polyline (EDIT-01)
    │        ├─▶ BacktestResult + (NEW) margin  ──▶ stat-chip values (EDIT-02)
    │        └─▶ (existing) _range_chart()  ──▶ kept, becomes Phase 2's filter-distribution chart
    │
    ├─▶ (NEW, pure fn) describe(system) -> list[{"text":.., "key":..}]     (EDIT-03)
    │        │
    │        └─▶ (NEW, request-scoped) _query_href(remove=key) in web.py  ──▶ remove-link hrefs
    │
    ├─▶ request.args.get("tab", "graph")  ──▶ conditionally render Results Graph | Past Matches (EDIT-04)
    │        └─▶ tab links built via same _query_href() helper (preserve load_system=, filters, etc.)
    │
    └─▶ render_template("index.html", ...)
              │
              ▼
        Jinja renders chips, sentence rows, tab panel, theory block
              │
              ▼
        Browser (static HTML + inline SVG; full-page reload on any interaction)

 POST /save  (web.py: create_app().save)
    │
    ├─▶ _system_from_form(form)  ──▶ SystemFilter (unchanged shape)
    ├─▶ (NEW) form.get("theory", "")
    └─▶ storage.save_system(name, system, data_dir, theory=...)  ──▶ data/systems/{name}.json
```

### Recommended Project Structure

No new files are strictly required — all additions fit into existing modules, following this codebase's established pattern of colocating request-scoped helpers in `web.py` and pure logic in the module that already owns that domain (`backtest.py` for Margin, `storage.py`/`models.py` for the theory field). The one genuinely new decision point is where `describe()` lives:

```
cfb_system_maker/
├── models.py          # SavedSystem gains theory: str = ""; BetDetail gains margin: float = 0.0
├── backtest.py        # run_backtest computes margin per bet + average margin on BacktestResult
├── storage.py         # save_system(..., theory=""); NEW load_saved_system() returns full SavedSystem
├── describe.py         # NEW (recommended) — pure describe(system) -> list[dict], no Flask import
├── web.py             # _cumulative_chart(), _query_href(), tab handling, theory round-trip, remove-hrefs
├── templates/
│   └── index.html     # chip header, sentence rows w/ remove links, tab nav, theory textarea+display
└── static/
    └── styles.css      # chip/sentence/tab styling additions
```

**Why a new `describe.py` instead of a `web.py`-private function:** `bet-labs-parity-plan.md` step 13 (Phase 4, "Current Matches") explicitly says to "reuse the sentence renderer from step 3" for describing which filters a saved system matched on an *upcoming, unplayed* game — a context with no live Flask `request` object. Keeping `describe()` framework-independent now avoids an awkward extraction later. This mirrors the existing pattern of `backtest.py`/`features.py` being pure and reused by both `cli.py` and `web.py`.

### Pattern 1: Cumulative Chart (extends `_range_chart`)

**What:** A new function that takes `result.bet_details` (already sorted implicitly by iteration order = game match order; must explicitly sort by `(season, week, game_id)` for the chart, matching the existing `_streaks()` sort key), computes a running sum of `profit`, and emits the same `{"points": [...], "polyline": "...", ...}` shape `_range_chart` already returns, so the existing SVG-rendering Jinja block can largely be copy-adapted.

**When to use:** EDIT-01's Results Graph tab.

**Example (illustrative — not a runnable diff, follows the existing `_range_chart` shape at `web.py:447`):**
```python
# Source: pattern extension of cfb_system_maker/web.py:447 _range_chart (existing code, read this session)
def _cumulative_chart(result: BacktestResult) -> dict[str, object]:
    if not result.bet_details:
        return {"points": [], "polyline": "", "zero_y": 75, "min_x": None, "max_x": None}

    ordered = sorted(result.bet_details, key=lambda bet: (bet.season, bet.week, bet.game_id))
    running = 0.0
    series: list[tuple[int, float]] = []
    for index, bet in enumerate(ordered):
        running = round(running + bet.profit, 4)
        series.append((index, running))  # x = chronological bet order (Claude's Discretion, see CONTEXT.md)

    # ... same width/height/pad_x/pad_y/min/max/scale logic as _range_chart ...
    # Convert to dollars only at render time: point["money"] = point["profit"] * 100
```

**Money convention pitfall:** `result.profit` and per-bet `bet.profit` are computed at `stake=1.0` (see `backtest.run_backtest` default and `grade_bet`'s `_profit_for_win`), i.e. in "stake units," not dollars. The Bet Labs $100-flat-stake convention (`docs/bet-labs-parity-plan.md` line 94, confirmed against `docs/sports-insights-systems-combined-guide.md` line 23: *"Money Won uses flat $100 risk per historical match"*) means **every dollar-denominated display value (chip, chart y-axis, tooltip) must multiply by 100** — but internal aggregation (ROI, hit rate, z-score, p-value) must NOT be touched; those ratios are already stake-invariant. Do the ×100 conversion at the template/rendering boundary only, not inside `backtest.py`.

### Pattern 2: `describe(system)` — Plain-English Filter Sentences

**What:** A pure function mapping each *active* constraint on a `SystemFilter` to one sentence, matching Bet Labs' wording style ("the spread is between -14 and -3", "the team's win percentage is between 60% and 100%" — `docs/bet-labs-parity-plan.md` §1.2). Two families of input: (1) the ~13 core `SystemFilter` scalar/set fields, (2) the `feature_filters` tuple (uses `FEATURE_BY_KEY[filt.key].label` already defined in `features.py`).

**Op-phrase mapping (for `feature_filters`, reusing existing `op` vocabulary already in `models.FeatureFilter`/`features._value_matches`):**

| `op` | `control` | Phrase template |
|------|-----------|------------------|
| `eq` | `bool` | `"{label} is Yes"` / `"{label} is No"` (matches existing dropdown wording "Yes"/"No" in `index.html:164-166`) |
| `eq` | `categorical` | `"{label} is {value}"` |
| `in` | `categorical` | `"{label} is one of {', '.join(value)}"` |
| `gte` | `numeric` | `"{label} is at least {value}"` |
| `lte` | `numeric` | `"{label} is at most {value}"` |

**Core `SystemFilter` fields needing their own phrase rule (no `FeatureDef` backs these — they're first-class dataclass fields, not registry entries):**

| Field(s) | Example sentence | Notes |
|----------|-------------------|-------|
| `favorite` / `underdog` | "the team is a favorite" / "the team is an underdog" | Mutually exclusive in practice (form uses independent checkboxes; both being true is a degenerate case — `matches_system` would then reject everything since `side_spread >= 0` and `<= 0` can't both hold except at 0, which both branches exclude) |
| `home` / `away` | "home games only" / "away games only" | These restrict `side`, not to be confused with `system.side` (which side gets bet) |
| `min_spread`/`max_spread` (spread bets) | "the spread is between {min} and {max}" / "the spread is at least {min}" / "the spread is at most {max}" | One combined sentence when both are set, matching Bet Labs' "BETWEEN x AND y" convention (`bet-labs-parity-plan.md` §1.3) |
| `min_total`/`max_total` (total bets) | "the total is between {min} and {max}" | Same combining rule |
| `seasons`/`weeks`/`teams`/`conferences`/`providers` | "the season is {sorted, joined}" | Current UI only ever sets one value at a time per set (single `<select>`), but the underlying model supports multi-value sets already (`_int_set`/`_str_set` split on comma) — `describe()` should handle N>1 members gracefully even though today's form can't produce them |

**Remove-link mechanics — keep OUT of `describe()`:** Each sentence needs a "remove" affordance producing a modified query string. This is Flask/`request`-specific and belongs in `web.py`, not the pure `describe()` function. See Pattern 3.

### Pattern 3: Query-String-Preserving Links (tabs + remove-filter)

**What:** Both EDIT-03 (remove-filter links) and EDIT-04 (tab links) need an href that equals *the current query string* with exactly one thing changed — never a fresh, from-scratch query string, or the loaded system's context (or all other active filters) silently vanishes. Verified directly against the installed werkzeug 3.1.8 in this repo's `.venv`:

```python
# Source: verified interactively against werkzeug 3.1.8 (installed in .venv), 2026-07-16
from urllib.parse import urlencode
from werkzeug.datastructures import MultiDict

# request.args is an ImmutableMultiDict; .items(multi=True) yields every
# (key, value) pair including repeats (needed for ff_enable, which is
# submitted once per enabled feature key).
md = MultiDict(request.args.items(multi=True))   # mutable copy
# -> md.getlist("a") == ['1', '2'] for a repeated param, confirmed live

def _href_with_tab(tab: str) -> str:
    copy = MultiDict(request.args.items(multi=True))
    copy.setlist("tab", [tab])
    return "?" + urlencode(list(copy.items(multi=True)))

def _href_removing_feature_filter(feature_key: str) -> str:
    copy = MultiDict(request.args.items(multi=True))
    enabled = [v for v in copy.getlist("ff_enable") if v != feature_key]
    copy.setlist("ff_enable", enabled)
    return "?" + urlencode(list(copy.items(multi=True)))

def _href_removing_core_param(*param_names: str) -> str:
    copy = MultiDict(request.args.items(multi=True))
    for name in param_names:
        copy.poplist(name)   # poplist on a MultiDict-copy is safe; no KeyError if absent
    return "?" + urlencode(list(copy.items(multi=True)))
```

**Why removing a feature filter is simpler than it looks:** the existing form always submits one `ff_key` hidden input **per registry feature** (all ~35, in every request — see `templates/index.html:150`), and uses a *separate* `ff_enable` multi-value list to track which ones are "on" (`web.py:263` `_enabled_feature_keys`). Because the form guarantees exactly one row per feature key (no duplicates possible), **removing a feature filter is just dropping its key from the `ff_enable` list** — not an index-based array-splice across four parallel lists. Do not build index-zipping removal logic; it's unnecessary here and is the likely first over-engineering trap.

**Verify against the exact werkzeug/Flask versions in the target venv before implementing** — this is `[VERIFIED: werkzeug 3.1.8, this repo's .venv]` for *this* environment; werkzeug's URL-encoding helpers changed across major versions (older werkzeug exposed `werkzeug.urls.url_encode`, which was removed by 2.2 — this repo is well past that, using stdlib `urllib.parse.urlencode` directly is correct here and future-proof).

### Anti-Patterns to Avoid
- **Client-side JS to toggle tab panels or patch links:** Directly contradicts D-01 and the "no frontend framework" tech constraint. Every existing interaction in this app is a full-page GET/POST reload; breaking that pattern for tabs alone creates two different state models in one page.
- **Hardcoding `?tab=graph` (or any href) as a literal string without merging `request.args`:** Silently drops the loaded system and all active filters — directly breaks EDIT-04's success criterion ("without losing the loaded system's context").
- **Storing money-won values pre-multiplied by 100 inside `backtest.py`:** Would corrupt ROI/hit-rate/stats math elsewhere (t-stats, z-scores, Wilson CI all currently assume `stake=1.0`-normalized values) and would silently break the existing `test_backtest.py` assertions (e.g. `round(result.profit, 4) == 0.9091`). Keep the ×100 conversion at the presentation boundary only.
- **Changing `storage.load_system()`'s return type to break existing callers:** `cli.py:162` and `tests/test_storage_systems.py` both call `load_system(name, data_dir) -> SystemFilter` and destructure `SystemFilter` attributes directly. Add a new function for the full `SavedSystem` (name/saved_at/theory) rather than changing this one's contract.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Query-string editing for tabs/remove-links | Ad hoc string concatenation of `?key=value&...` per template call site | One shared `_query_href(...)`-style helper built on `werkzeug.datastructures.MultiDict` (already a Flask/Werkzeug dependency, zero new packages) | Five independent hand-rolled concatenations (tab links × 2, remove-links × N filters) will inevitably diverge in which params they preserve, causing exactly the "lost context" bug EDIT-04 explicitly guards against |
| Cumulative/line charting | A JS charting library (Chart.js, D3, Recharts) | Hand-rolled inline SVG, extending the exact pattern already proven in `_range_chart` (`web.py:447`) | No-new-dependency project rule; existing pattern already solves polyline + point + axis-label rendering |
| Money formatting (`+$3,114` style) | A currency-formatting library | Python's built-in `f"{value:+,.0f}"` (or similar) applied only at render time | Stdlib is sufficient for whole-dollar, signed, thousands-separated formatting; no locale/currency-symbol complexity needed for a single-currency, single-user tool |

**Key insight:** Every "hard" part of this phase (charting, query-string state, currency formatting) already has a working, in-repo precedent (`_range_chart`, GET-form-driven filters, existing `%.4f`/`%.2f%%` Jinja formatting) or a stdlib/Werkzeug primitive. The risk in this phase is re-deriving a worse version of something already solved, not missing a genuinely new technical capability.

## Common Pitfalls

### Pitfall 1: Breaking `load_system()`'s contract while adding `theory`
**What goes wrong:** `storage.load_system(name, data_dir) -> SystemFilter` is called from three places (`web.py:50`, `web.py:114`, `cli.py:162`) and one test (`test_storage_systems.py:18`) that all expect a bare `SystemFilter`. A naive "just add theory to what load_system returns" edit either breaks these callers or silently makes `web.py`'s system-loading code use a different, undocumented shape than `cli.py`.
**Why it happens:** `theory` conceptually lives on `SavedSystem` (which wraps `SystemFilter` + `name` + `saved_at`), but `load_system()` was written before any caller needed anything but the filter itself.
**How to avoid:** Add a new function, e.g. `storage.load_saved_system(name, data_dir) -> SavedSystem`, that returns the full object including `theory`; leave `load_system()` untouched for `cli.py` and the existing test. `web.py`'s index route switches to the new function only where it needs the theory text.
**Warning signs:** Any diff that changes `load_system`'s signature or return type, or that adds a `theory` positional/keyword arg without a default.

### Pitfall 2: `_system_to_dict`/`_system_from_dict` not defaulting `theory` for pre-existing saved systems
**What goes wrong:** Any system saved *before* this phase ships (none exist yet in this dev environment per `docs/PROJECT_MAP.md` §10 — "`data/systems/` — none saved yet" — but this must still be defensive for any real-world/future saved file) has no `"theory"` key in its JSON. `payload["theory"]` throws `KeyError`; `payload.get("theory", "")` does not.
**Why it happens:** Direct-key access is a natural first pass when adding a field to an existing deserializer.
**How to avoid:** Use `.get("theory", "")` (mirrors the existing pattern already used for every other optional-ish field, e.g. `system.get("bet_type", "spread")` in `_system_from_dict`, `web.py:151`).
**Warning signs:** A test that constructs/loads a JSON file with the `theory` key stripped out should still round-trip cleanly to `theory=""`.

### Pitfall 3: Conflating stake-unit profit with dollar Money Won
**What goes wrong:** `BacktestResult.profit` and `BetDetail.profit` are in stake-units (`stake=1.0` default), e.g. `0.9091` for a single -110 win. Displaying this raw number in a chip labeled "Money Won" (which Bet Labs shows as `+$3,114`) without the ×100 conversion silently under-reports by 100x.
**Why it happens:** The existing UI already displays raw `result.profit` (see `index.html:228`, `"%.4f"|format(result.profit)`) with no dollar formatting — it's easy to copy that existing pattern for the new Money Won chip without noticing the semantic gap.
**How to avoid:** Apply `× 100` and currency formatting **only** at template-render time for anything labeled in dollars (Money Won chip, cumulative-chart y-axis/tooltip). Never touch the underlying `profit`/`roi`/`hit_rate` fields — they're shared with `SystemStats` computations (z-score, t-stat, Wilson CI) that assume the current stake-unit convention and are covered by existing passing tests (`test_backtest.py`).
**Warning signs:** Any change inside `backtest.py`'s `run_backtest`/`grade_bet`/`compute_system_stats` that multiplies by 100 — that's the wrong layer.

### Pitfall 4: Ambiguous Margin formula for total bets
**What goes wrong:** `docs/bet-labs-parity-plan.md` (line 96) specifies Margin as "mean of `team_points + side_spread - opp_points` over graded bets" — this is explicitly a **spread-bet** formula (`side_spread` only exists for spread bets; `grade_bet`'s total-bet path, `_grade_total_bet`, has no analogous `side_spread`). The doc does not specify what Margin means for a `bet_type="total"` system.
**Why it happens:** The reference doc's example screenshots are drawn from Bet Labs' NFL Spread systems; the totals case wasn't screenshotted/described.
**How to avoid:** This needs a decision, not silent invention. `[ASSUMED]` proposal for the planner/discuss step: for total bets, define margin analogously as the signed distance from the line in the direction of the bet — `(actual_total - line)` when `total_side == "over"`, `(line - actual_total)` when `"under"` — preserving the same sign convention as `cover_margin` (positive = won by that much). Flag this as needing explicit confirmation before implementation, or scope Margin to spread bets only for Phase 1 and show `—` for total systems (mirroring the Grade-chip-placeholder precedent already accepted in this phase's CONTEXT.md).
**Warning signs:** A `BetDetail.margin` field with no defined value/formula for `bet_type == "total"` rows — check it doesn't silently default to `0.0` or crash.

### Pitfall 5: Forgetting BetDetail/BacktestResult are frozen dataclasses with positional-safe defaults
**What goes wrong:** `BetDetail` and `BacktestResult` are `@dataclass(frozen=True)` with no defaults on existing fields (`models.py:67-106`). Adding a new `margin` field to `BetDetail` (and an aggregate `average_margin` to `BacktestResult`) must come with a default (`margin: float = 0.0`) placed after all fields without defaults, or every direct `BetDetail(...)`/`BacktestResult(...)` construction site (`backtest.py:239`, `backtest.py:282`, and test fixtures in `tests/test_backtest.py:136`, `tests/test_backtest.py:173`) breaks.
**Why it happens:** Dataclass field-ordering rules (no-default fields can't follow defaulted ones) are easy to violate when appending a field at the end of a class that already has some optional trailing fields (`BacktestResult` already has `stats: SystemStats | None = None` and `season_breakdown: tuple[...] = ()` at the end).
**How to avoid:** Append `margin`/`average_margin` after the *existing* defaulted fields, with their own defaults, and update the two `backtest.py` construction sites explicitly (they're not using defaults today, so they must be edited, not left to fall back).
**Warning signs:** `TypeError: non-default argument 'X' follows default argument` at import time, or existing `tests/test_backtest.py` fixtures silently getting a `margin=0.0` they didn't expect (harmless if the test doesn't assert on it, but check).

## Code Examples

### Margin Computation (spread bets) — extends existing `grade_bet`
```python
# Source: pattern extension of cfb_system_maker/backtest.py:227-228 (existing code, read this session)
# grade_bet already computes this value locally and discards it:
spread = _side_spread(game.spread, normalized_side)
cover_margin = team_points + spread - opponent_points   # <- already computed, not persisted
# Recommendation: thread cover_margin into the returned BetDetail (new `margin` field)
# instead of recomputing it from stored fields later.
```

### Storage Migration — theory field, backward compatible
```python
# Source: pattern extension of cfb_system_maker/storage.py:104-168 (existing code, read this session)
# models.py: add to SavedSystem
# theory: str = ""   # frozen dataclass, must be last / after non-default fields

# storage._system_to_dict — add one key:
"theory": saved.theory,

# storage._system_from_dict / new load_saved_system — always use .get with default:
theory=str(payload.get("theory", "")),

# storage.save_system — add an explicit default param so cli.py's existing call
# (save_system(args.save, system, args.data_dir) — no theory) keeps working:
def save_system(name, system, data_dir, theory: str = "") -> Path: ...
```

## State of the Art

Not applicable in the conventional sense — this is a brownfield restyle of an already-current, dependency-free Flask app; there is no "old approach → new approach" library migration involved. The one relevant "current practice" note: Flask 3.x's Jinja auto-escaping (on by default) is what makes the new free-text `theory` field safe to render without extra sanitization work — see Security Domain below.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Margin formula for `bet_type == "total"` systems: signed distance from the line in the bet's direction (`actual_total - line` for over, `line - actual_total` for under), mirroring spread `cover_margin`'s sign convention | Pitfall 4 / Code Examples | If the intended Bet Labs semantics differ (e.g. always unsigned, or omitted entirely for totals), the Margin chip could show a misleading value for total systems; low blast radius since it's a single display field, not used in grading/backtest logic |
| A2 | Feature-filter remove-link only needs to drop the key from `ff_enable` (not perform index-based removal across `ff_key`/`ff_op`/`ff_value`/`ff_perspective`), because the form always emits exactly one row per registry feature | Pattern 3 | If a future change makes the form emit variable/sparse `ff_key` rows (not one-per-registry-feature), this simplification would need revisiting; currently verified true by reading `templates/index.html:150` and `web.py:263` this session, so risk is low but tied to that invariant holding |
| A3 | Money Won chip / cumulative-chart dollar values should round to whole dollars (no cents), matching Bet Labs' displayed style (`+$3,114`, no decimals) | Pattern 1 | Purely cosmetic; easy to adjust either direction without touching any underlying computation |

## Open Questions

1. **Where exactly does the Margin chip appear for total-bet systems, given Pitfall 4's ambiguity?**
   - What we know: The reference doc's Margin formula is spread-specific; the app already supports total-bet systems as a first-class case (`SystemFilter.bet_type == "total"`).
   - What's unclear: Whether Bet Labs shows an analogous Margin for totals systems at all, and if so, its exact sign convention.
   - Recommendation: Planner should either (a) adopt the A1 assumption explicitly and flag it for user confirmation during `/gsd-plan-phase` or execution, or (b) scope Margin to spread-bet systems only for Phase 1, rendering `—` for total systems — consistent with how this same CONTEXT.md already accepted a placeholder pattern for the Grade chip.

2. **Exact wording/formatting conventions for compound sentences (e.g. combined min/max spread as one sentence vs. two).**
   - What we know: Bet Labs' example wording combines a range into one sentence ("the spread is between -14 and -3").
   - What's unclear: Exact punctuation/capitalization conventions beyond the one example quoted in the parity doc; `docs/sports-insights-systems-combined-guide.md` doesn't add further wording detail beyond what's already excerpted into `bet-labs-parity-plan.md`.
   - Recommendation: Low-stakes cosmetic decision; planner can lock exact wording without further research — this is well within normal implementation discretion, not a research gap.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python (project `.venv`) | All test/dev work this phase | ✓ | 3.14.4 | — |
| Flask | Web app | ✓ | 3.1.3 | — |
| Werkzeug | Query-string manipulation (`MultiDict`) | ✓ | 3.1.8 | — |
| Jinja2 | Templates | ✓ | 3.1.6 | — |
| pytest | Test suite | ✓ (94 passed via `.venv/Scripts/python.exe -m pytest -q`) | — | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None — everything needed is already installed in the project's `.venv`.

**Environment pitfall (found this session, not hypothetical):** Running `python -m pytest` with the bare `python` on `PATH` (not `.venv/Scripts/python.exe`) fails with an unrelated pydantic/langsmith collection error from packages in the global Python 3.14 environment — this is **not** a project bug, it's a global-environment collision. Always invoke tests via the project's own `.venv` interpreter (`.venv/Scripts/python.exe -m pytest`, confirmed: 94 passed in 2.31s), not the bare `python`/`python -m pytest` that may resolve to a different interpreter on `PATH`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (via `.venv`, version not pinned in `requirements.txt` — resolves whatever pip installs; already present and working) |
| Config file | `pytest.ini` (`testpaths = tests` — keeps collection out of vendored `cfbd-python/`) |
| Quick run command | `.venv/Scripts/python.exe -m pytest tests/test_web.py -q` |
| Full suite command | `.venv/Scripts/python.exe -m pytest -q` (confirmed: 94 passed in 2.31s this session) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EDIT-01 | Cumulative chart renders, ordered by (season, week), $100-flat-stake values | unit + integration | `.venv/Scripts/python.exe -m pytest tests/test_backtest.py tests/test_web.py -q` | ✅ extend existing files |
| EDIT-02 | Stat-chip header shows Record/Margin/Money Won/ROI/Grade-placeholder | unit + integration | `.venv/Scripts/python.exe -m pytest tests/test_backtest.py tests/test_web.py -q` | ✅ extend existing files |
| EDIT-03 | `describe(system)` produces correct sentences; remove-link drops correct query param | unit | `.venv/Scripts/python.exe -m pytest tests/test_describe.py -q` | ❌ Wave 0 (new file, mirrors module pattern) |
| EDIT-04 | Tab switch preserves loaded-system/filter context | integration | `.venv/Scripts/python.exe -m pytest tests/test_web.py -q` | ✅ extend existing file |
| EDIT-05 | Theory saved via `POST /save`, shown above filter list on reload, backward-compatible for pre-theory saved files | unit + integration | `.venv/Scripts/python.exe -m pytest tests/test_storage_systems.py tests/test_web.py -q` | ✅ extend existing files |

### Sampling Rate
- **Per task commit:** `.venv/Scripts/python.exe -m pytest tests/test_web.py -q` (or the more targeted file for the module just touched)
- **Per wave merge:** `.venv/Scripts/python.exe -m pytest -q` (full suite, ~2.3s — cheap enough to always run in full)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_describe.py` — new file, covers EDIT-03's `describe(system) -> list[dict]` pure function (mirrors the existing 1:1 module↔test-file pattern, e.g. `backtest.py` ↔ `test_backtest.py`)
- [ ] No new fixtures needed — existing `SAMPLE_GAMES_2023`/`SAMPLE_LINES_2023` (`sample_data.py`) and direct `GameRecord`/`SystemFilter` construction (existing pattern in every test file) cover all new test needs
- [ ] No framework install needed — pytest already present and passing (94/94) in `.venv`

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Single-user local tool, no auth layer anywhere in the app (`web.create_app()` binds to `127.0.0.1` per README; unaffected by this phase) |
| V3 Session Management | No | No sessions/cookies used anywhere in this app; all state lives in the URL query string by design |
| V4 Access Control | No | No multi-user/role concept exists or is introduced |
| V5 Input Validation | **Yes** | New free-text `theory` field (EDIT-05): rely on Jinja2's default auto-escaping (`Flask`/`Jinja2` autoescape is ON by default for `.html` templates — confirmed no `{% autoescape false %}` block or `|safe` filter anywhere in `templates/index.html` this session) to prevent stored-XSS via the theory textarea. **Do not** apply `|safe` to the rendered theory text. No other new user-input surface is introduced this phase (all other new render logic reads from already-validated `SystemFilter`/`BacktestResult` data). |
| V6 Cryptography | No | Not touched by this phase; the CFBD API token (`env.env`) is unrelated to any UI change here |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Stored XSS via free-text `theory` field rendered later on the saved-system page | Tampering / Information Disclosure | Jinja2 auto-escaping (default, already relied upon everywhere else in `index.html`) — never bypass with `|safe` for user-supplied text |
| Query-string injection into remove/tab links (a crafted `?tab=<script>` or similar) | Tampering | `_query_href`-style helper builds hrefs via `urllib.parse.urlencode`, which percent-encodes values — do not string-interpolate raw `request.args` values into an href without going through `urlencode` |

## Sources

### Primary (HIGH confidence)
- `docs/bet-labs-parity-plan.md` (this repo, read in full this session) — locked design doc for this phase; Margin formula, `describe()` spec, remove-link mechanics, theory storage spec
- `docs/sports-insights-systems-combined-guide.md` (this repo, relevant excerpts grepped this session) — source Bet Labs documentation for the $100-flat-stake / Money Won / ROI convention (line 23)
- `docs/PROJECT_MAP.md` (this repo, read in full this session) — architecture reference, module map, conventions
- `cfb_system_maker/{web,models,storage,backtest,features}.py`, `templates/index.html`, `static/styles.css`, `tests/*.py` (this repo, read in full this session) — direct code inspection, the actual authoritative source for all implementation claims
- `.venv/Scripts/python.exe -m pytest -q` (executed this session) — 94 passed in 2.31s, confirms baseline green state and the correct test-invocation command
- Interactive werkzeug/Flask version + `MultiDict` API check (executed this session against the installed `.venv`) — confirms Pattern 3's code example is accurate for this repo's exact dependency versions

### Secondary (MEDIUM confidence)
None used — no external documentation lookup was needed or performed (`config.json` has all web-search/doc-fetch providers disabled; this phase's domain is entirely internal-codebase-driven since no new libraries are introduced).

### Tertiary (LOW confidence)
None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - directly verified installed versions in the project's own `.venv`; no external packages introduced
- Architecture: HIGH - based on direct reading of every relevant existing source file plus a locked design doc (`bet-labs-parity-plan.md`) that already specifies this phase in detail
- Pitfalls: HIGH - each pitfall traced to a specific, cited line in the existing codebase or an explicit gap in the design doc (Margin-for-totals), not speculative

**Research date:** 2026-07-16
**Valid until:** No external expiry driver (no library versions to go stale) — treat as valid until the underlying `bet-labs-parity-plan.md` design doc changes or Phase 1 code lands, whichever comes first.
