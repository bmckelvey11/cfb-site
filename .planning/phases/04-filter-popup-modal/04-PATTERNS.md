# Phase 4: Filter Popup Modal - Pattern Map

**Mapped:** 2026-07-17
**Files analyzed:** 8 primary (6 modify + 2 new) + 3 companion test files
**Analogs found:** 7 / 8 (1 partial: new static JS module — no existing `.js` asset)

> Phase 4 extends the existing Flask/Jinja/vanilla stack. Canonical state stays in
> `filters-form` + query string. New work exposes server-owned descriptors and lightweight
> grading through two JSON routes, then wraps a native `<dialog>` draft/commit shell over
> the same form. Do not invent a client system model or chart dependency.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `cfb_system_maker/features.py` (MODIFY: `FeatureDef.description` + registry copy) | model/config | declarative registry | itself — `FeatureDef` + `FEATURE_REGISTRY` rows | exact |
| `cfb_system_maker/backtest.py` (MODIFY: lightweight summary seam) | service | transform / batch | itself — `run_backtest` match+grade head before stats | exact |
| `cfb_system_maker/web.py` (MODIFY: descriptors, strict parse, `/filter-detail`, `/api/backtest`) | controller/route + helpers | request-response + file-I/O (load games/features) | itself — `create_app` routes + `_feature_options` / `_feature_filters_from_request` | exact |
| `cfb_system_maker/describe.py` (MODIFY: coalesce gte+lte; edit identity) | utility | transform | itself — `_range_sentence` for core ranges + feature loop | exact |
| `cfb_system_maker/templates/index.html` (MODIFY: launchers, fallback, one `<dialog>`) | component/template | request-response (SSR) | itself — sidebar `<details>`, `filters-form`, active-filter sentences, chips/SVG | exact |
| `cfb_system_maker/static/styles.css` (MODIFY: modal/slider/responsive) | config/style | — | itself — CSS vars, chips, tables, charts, `@media` | exact |
| `cfb_system_maker/static/filter_modal.js` (NEW) | component (client) | request-response (fetch) + event-driven draft | `index.html` inline `<script>` + RESEARCH MDN dialog/AbortController examples | partial |
| `tests/test_filter_modal.py` (NEW) | test | request-response | `tests/test_web.py` + `tests/test_web_features.py` Flask client fixtures | role-match |
| `tests/test_describe.py` (MODIFY companion) | test | construct + assert | existing describe BETWEEN / feature tests | exact |
| `tests/test_features.py` (MODIFY companion) | test | construct + assert | registry completeness tests | exact |

**Not modified (reuse as-is):**
- `cfb_system_maker/models.py` — reuse `FeatureFilter` / `SystemFilter`; paired numeric ranges are two `FeatureFilter` rows (`gte` + `lte`), not a new model.
- `matches_system` / `grade_bet` / `feature_ok` / `resolve_feature_value` — authoritative matching/grading; call them, do not reimplement in JS or `web.py`.
- `/save`, saved-system storage, Grade chip expansion — out of phase scope.

## Pattern Assignments

### `cfb_system_maker/features.py` (model/config, declarative registry)

**Analog:** itself — frozen `FeatureDef` + tuple registry.

**Imports / dataclass pattern** (lines 1–42):
```python
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Literal

# ... Group / Control / Join / SourceKind Literals ...

@dataclass(frozen=True)
class FeatureDef:
    key: str
    label: str
    group: Group
    source_kind: SourceKind
    field: str
    join: Join
    control: Control
    team_scoped: bool = False
    lines_field: str | None = None
    source_file: str | None = None
    # NEW: description: str = ""   # plain-text About Filter copy (D-19)
```

**Row registration pattern** (lines 45–62) — add `description=` to each row (or a post-pass dict), keep positional fields stable:
```python
FEATURE_REGISTRY: tuple[FeatureDef, ...] = (
    FeatureDef("neutralSite", "Neutral Site", "pregame", "raw_game", "neutralSite", "game_id", "bool"),
    FeatureDef(
        "pregame_win_prob",
        "Pregame Win Prob",
        "pregame",
        "graphql_game_team",
        "winProb",
        "game_id",
        "numeric",
        team_scoped=True,
    ),
    # ...
)
```

**Allowlist / evaluation to keep** (lines 191, 225–288) — API must reject unknown keys via `FEATURE_BY_KEY`; live metrics must still go through `feature_ok` / `resolve_feature_value`:
```python
FEATURE_BY_KEY: dict[str, FeatureDef] = {feature.key: feature for feature in FEATURE_REGISTRY}

def resolve_feature_value(features, feature, filt, system) -> Any: ...
def feature_ok(features, filt, system) -> bool: ...
```

**Companion test analog:** `tests/test_features.py` lines 22–31 — extend with “every feature has non-empty `description`” and lookahead wording checks.

---

### `cfb_system_maker/backtest.py` (service, transform)

**Analog:** itself — extract the cheap head of `run_backtest` (match → grade → aggregate) and skip `compute_system_stats` / season breakdown / grade when callers only need chips.

**Core match+grade aggregation** (lines 12–35) — this is the lightweight seam to extract/reuse:
```python
def run_backtest(
    games: list[GameRecord],
    system: SystemFilter,
    *,
    stake: float = 1.0,
    american_odds: int = -110,
    feature_map: dict[int, dict[str, Any]] | None = None,
) -> BacktestResult:
    feature_map = feature_map or {}
    matched = [game for game in games if matches_system(game, system, feature_map)]
    details = [
        grade_bet(game, system, stake=stake, american_odds=american_odds)
        for game in matched
    ]
    wins = sum(1 for bet in details if bet.result == "win")
    losses = sum(1 for bet in details if bet.result == "loss")
    pushes = sum(1 for bet in details if bet.result == "push")
    bets = len(details)
    decided = wins + losses
    profit = round(sum(bet.profit for bet in details), 4)
    risked = bets * stake
    hit_rate = round(wins / decided, 4) if decided else 0.0
    roi = round(profit / risked, 4) if risked else 0.0
    # FULL path continues into stats / season_breakdown / grade — modal must skip that.
```

**Authoritative matching / grading** (lines 206–266, 305–348) — `/api/backtest` and per-value aggregation must call these, preserving Fade and totals:
```python
def matches_system(game, system, feature_map=None) -> bool:
    ...
    side_spread = _side_spread(game.spread, side) if game.spread is not None else None
    ...
    return all(feature_ok(features, filt, system) for filt in system.feature_filters)

def grade_bet(game, system, *, stake=1.0, american_odds=-110) -> BetDetail:
    if system.fade:
        normalized_side = "away" if normalized_side == "home" else "home"
    ...
```

**Spread sign invariant** (lines 502–503) — core spread distribution must use this, not raw `GameRecord.spread`:
```python
def _side_spread(home_spread: float, side: str) -> float:
    return home_spread if side == "home" else -home_spread
```

**One-pass per-value pattern (new helper, same primitives):** for each game that `matches_system` against the candidate-removed system, `grade_bet` once, then bucket by resolved core/feature value. Mirror `_range_chart`’s bucket-then-summarize shape (web.py 567–574) but keep exact values for metrics and only downsample for chart rendering (D-09).

---

### `cfb_system_maker/web.py` (controller, request-response)

**Analog:** itself — nested routes in `create_app`, form parse → `SystemFilter` → `run_backtest`, plus feature domain helpers.

**Route registration pattern** (lines 38–43, 110–120, 181–185) — add JSON routes beside existing ones; return dict for Flask JSON:
```python
def create_app(data_dir: str | Path = "data") -> Flask:
    app = Flask(__name__)
    app.config["DATA_DIR"] = Path(data_dir)
    app.jinja_env.globals["query_href"] = _query_href

    @app.get("/")
    def index():
        ...

    @app.post("/save")
    def save():
        ...

    # NEW:
    # @app.get("/api/backtest")
    # def api_backtest(): ...
    # @app.get("/filter-detail")
    # def filter_detail(): ...

    return app
```

**Data load + missing-data pattern** (lines 45–59, 293–297) — reuse for JSON `503`/unavailable when processed games or feature sidecar missing:
```python
        try:
            games = load_processed_games(app.config["DATA_DIR"])
        except FileNotFoundError:
            return render_template(..., error="missing_data", ...)

def _try_load_features(data_dir: Path) -> dict[int, dict] | None:
    try:
        return load_features(data_dir)
    except FileNotFoundError:
        return None
```

**Canonical form round-trip** (lines 328–351, 464–494) — Save Filter must write into these fields, then submit GET; API parsing should harden (not fork) this path:
```python
def _form_values() -> dict[str, object]:
    filters = _feature_filters_from_request()
    return {
        "side": _valid_choice(request.args.get("side", "home"), ("home", "away"), "home"),
        ...
        "feature_filters": filters,
    }

def _system_from_form(form: dict[str, object]) -> SystemFilter:
    feature_filters = tuple(
        FeatureFilter(
            key=str(row["key"]),
            op=str(row["op"]),
            value=row["value"],
            perspective=str(row.get("perspective", "single")),
        )
        for row in form.get("feature_filters", [])
        if row.get("key")
    )
    return SystemFilter(..., feature_filters=feature_filters)
```

**Current permissive feature parse — harden for D-18** (lines 424–461):
```python
def _feature_filters_from_request() -> list[dict[str, object]]:
    enabled = set(request.values.getlist("ff_enable"))
    keys = request.values.getlist("ff_key")
    ...
    # Gap today: unknown keys accepted; float() can 500; perspectives unchecked.
    # Strict API mode must allowlist key ∈ FEATURE_BY_KEY (or namespaced core IDs),
    # operator×control matrix, perspective, finite numerics, ordered bounds.

def _parse_filter_value(op: str, raw_value: str) -> object | None:
    if op in {"gte", "lte"}:
        return float(raw_value) if raw_value.strip() else None
```

**Descriptor / domain discovery analog** (lines 525–564) — extend `_feature_option` shape into namespaced modal descriptors (`core:season`, `feature:weather_temperature`) and reuse `_scan_values`:
```python
def _feature_options(feature_map: dict[int, dict] | None) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for feature in FEATURE_REGISTRY:
        grouped.setdefault(feature.group, []).append(_feature_option(feature, feature_map))
    ...

def _feature_option(feature: FeatureDef, feature_map: dict[int, dict] | None) -> dict[str, object]:
    values = _scan_values(feature, feature_map or {})
    return {
        "key": feature.key,
        "label": feature.label,
        "control": feature.control,
        "team_scoped": feature.team_scoped,
        "values": values,
        "min_value": min(values) if values and feature.control == "numeric" else None,
        "max_value": max(values) if values and feature.control == "numeric" else None,
        # NEW: description, allowed ops/perspectives, lookahead flag
    }
```

**Chart downsample precedent** (lines 567–579) — visual cap only; do not use sampled points for live range evaluation:
```python
    items = sorted(buckets.items())
    if len(items) > 18:
        step = max(1, len(items) // 18)
        items = items[::step]
```

**Sentence enrichment pattern** (lines 84–86) — attach Edit metadata the same way Remove is attached:
```python
        sentences = describe(system)
        for row in sentences:
            row["remove_href"] = _query_href_removing(str(row["key"]), base_query)
            # NEW: row["edit"] = {"candidate_id": ..., "perspective": ...}
```

**Atomic feature-array rewrite** (lines 270–285) — Save/Edit must decode → replace candidate rows → rebuild `ff_*` lists together (same alignment rule as remove):
```python
    if key.startswith("ff:"):
        feature_key = key[len("ff:"):]
        keys = copy.getlist("ff_key")
        ...
        keep = [index for index, item in enumerate(keys) if item != feature_key]
        copy.setlist("ff_key", [keys[index] for index in keep])
        # ... keep ops/values/perspectives/enable aligned
```

**Core range removal map** (lines 23–35) — candidate removal for distribution must clear both bounds:
```python
_REMOVE_PARAM_MAP: dict[str, tuple[str, ...]] = {
    "spread_range": ("min_spread", "max_spread"),
    "total_range": ("min_total", "max_total"),
    "seasons": ("filter_seasons"),
    ...
}
```

---

### `cfb_system_maker/describe.py` (utility, transform)

**Analog:** itself — core ranges already coalesce min/max into one sentence; registry numeric filters currently emit one sentence per `FeatureFilter`.

**Core BETWEEN coalescing to copy** (lines 22–33, 50–57):
```python
def _range_sentence(minimum, maximum, *, noun: str, key: str) -> dict[str, object] | None:
    ...
    elif minimum is not None and maximum is not None:
        text = f"the {noun} is between {_fmt_num(minimum)} and {_fmt_num(maximum)}"
    ...
    return {"text": text, "key": key}

# Used for spread_range / total_range today — replicate for same-key feature gte+lte pairs.
```

**Feature loop to change** (lines 70–96) — group by `(key, perspective)`, coalesce numeric `gte`+`lte` into one BETWEEN sentence and one edit identity (`ff:key` or namespaced id); keep bool/categorical wording:
```python
    for filt in system.feature_filters:
        feature = FEATURE_BY_KEY.get(filt.key)
        ...
        elif filt.op == "gte" and feature.control == "numeric":
            text = f"{label} is at least {_fmt_num(float(filt.value))}"
        elif filt.op == "lte" and feature.control == "numeric":
            text = f"{label} is at most {_fmt_num(float(filt.value))}"
        if text is not None:
            sentences.append({"text": text, "key": f"ff:{filt.key}"})
```

**Perspective label map** (lines 6–12, 78–81) — reuse for modal About/title language:
```python
_PERSPECTIVE_PREFIX: dict[str, str] = {
    "home": "Home",
    "away": "Away",
    "bet_side": "Bet-side",
    "opponent": "Opponent",
    "either": "Either team's",
}
```

**Companion test analog:** `tests/test_describe.py` lines 29–40 (core BETWEEN) and 76–85 (bool Yes/No) — add paired `gte`+`lte` → one sentence + one key.

---

### `cfb_system_maker/templates/index.html` (component/template, SSR)

**Analog:** itself — keep shell; convert filter editors to launchers + fallback; add one dialog.

**Canonical form + global controls stay outside modal** (lines 20–53) — D-01: bet type, side, position, Fade remain here:
```html
<form id="filters-form" method="get" class="filters" autocomplete="off">
  <fieldset>
    <legend>Bet Type</legend>
    <select name="bet_type">...</select>
  </fieldset>
  ...
```

**Core filters that become modal candidates** (lines 55–105) — keep real `<select>` / number inputs as no-JS fallback (D-05); JS enhancement hides them after init:
```html
<label>Season
  <select name="filter_seasons">...</select>
</label>
...
<section class="range-filter">
  <div class="range-row">
    <input name="min_spread" ...>
    <span>and</span>
    <input name="max_spread" ...>
  </div>
</section>
```

**Grouped registry + lookahead quarantine** (lines 114–120) — preserve groups and warning; replace `<details>` primary UX with launcher buttons while retaining checkbox/op/value controls for fallback:
```html
<fieldset class="feature-group {% if group.group == 'result_lookahead' %}lookahead{% endif %}">
  <legend>
    {{ group.group|replace('_', ' ')|title }}
    {% if group.group == 'result_lookahead' %}
      <span class="lookahead-warning">lookahead — analysis only</span>
    {% endif %}
  </legend>
```

**Parallel ff_* control encoding** (lines 127–174) — Save must continue writing these names:
```html
<input type="checkbox" name="ff_enable" value="{{ feature.key }}" ...>
<input type="hidden" name="ff_key" value="{{ feature.key }}">
<select name="ff_op">...</select>
<select name="ff_perspective">...</select>  <!-- or hidden single -->
<input name="ff_value" ...>
```

**Stat chips language for modal header** (lines 228–233) — reuse Record / Money Won / ROI markup classes (modal omits Margin/Grade):
```html
<section class="metrics stat-chips" aria-label="Backtest metrics">
  <article><span>Record</span><strong>{{ result.wins }}-{{ result.losses }}-{{ result.pushes }}, ...</strong></article>
  <article><span>Money Won</span><strong class="{{ 'positive' if result.profit > 0 else 'negative' if ... }}">...</strong></article>
  <article><span>ROI</span><strong class="{{ 'positive' if result.roi > 0 else 'negative' if ... }}">...</strong></article>
</section>
```

**Active-filter sentence + Remove** (lines 243–248) — add Edit control beside Remove; Remove stays one-click GET (D-03):
```html
<li>{{ row.text }}
  <a class="remove-filter" href="{{ row.remove_href }}" aria-label="Remove filter: {{ row.text }}">&times;</a>
  <!-- NEW: <button type="button" class="edit-filter" data-candidate="..." data-perspective="...">Edit</button> -->
</li>
```

**SVG chart language** (lines 305–327) — modal numeric chart should reuse zero-line / polyline / circle / `<title>` pattern:
```html
<svg viewBox="0 0 520 150" role="img">
  <line x1="28" x2="492" y1="{{ chart.zero_y }}" y2="{{ chart.zero_y }}" class="zero-line" />
  {% if chart.polyline %}<polyline points="{{ chart.polyline }}" />{% endif %}
  {% for point in chart.points %}
    <circle cx="{{ point.x }}" cy="{{ point.y }}" r="4">
      <title>...</title>
    </circle>
  {% endfor %}
</svg>
```

**Table + positive/negative** (lines 276–287, 335–362) — categorical value table reuses `.table-wrap` / `.positive` / `.negative`.

**Existing JS footprint** (lines 374–381) — only tiny inline `pageshow` helper today; prefer new `static/filter_modal.js` via `url_for('static', ...)` rather than growing inline script:
```html
<script>
  window.addEventListener("pageshow", () => { ... });
</script>
```

**New dialog shell (no in-repo analog — follow RESEARCH Pattern 3):**
```html
<dialog id="filter-modal" aria-labelledby="filter-modal-title">
  <!-- title + live chips | main controls/chart/table | About panel | Save/Cancel -->
</dialog>
<script src="{{ url_for('static', filename='filter_modal.js') }}" defer></script>
```

---

### `cfb_system_maker/static/styles.css` (style)

**Analog:** itself — extend tokens; do not introduce a new palette.

**Design tokens** (lines 1–16):
```css
:root {
  color-scheme: light;
  --bg: #f6f8fb;
  --panel: #ffffff;
  --panel-strong: #f1f5f9;
  --text: #162033;
  --muted: #617086;
  --border: #d8e0ea;
  --accent: #166f5b;
  --accent-dark: #0d4f41;
  --loss: #b42318;
  ...
}
```

**Chips / active filters / polarity** (lines 260–335, 468–472) — modal header chips and money columns reuse these:
```css
.metrics.stat-chips { grid-template-columns: repeat(5, minmax(120px, 1fr)); }
.metrics article { background: var(--panel); border: 1px solid var(--border); border-radius: 6px; ... }
.active-filters li { ... background: var(--panel-strong); ... }
.positive { ... }
.negative { ... }
```

**Chart tokens** (lines 400–428) — reuse `.range-chart`, polyline, circle, `.zero-line`.

**Responsive stacking precedent** (lines 525–536) — modal About-below-controls on narrow screens should follow the same breakpoint style:
```css
@media (max-width: 900px) {
  .app-shell { grid-template-columns: 1fr; }
  .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
```

**Progressive enhancement rule (D-05):** hide fallback editors only under a root `.js` class added by `filter_modal.js` after init — never hide fallback in base CSS alone.

---

### `cfb_system_maker/static/filter_modal.js` (NEW client component)

**Analog:** partial — only inline script in `index.html` today. Copy interaction contracts from RESEARCH Code Examples (MDN `<dialog>`, AbortController) and server contracts from `web.py` form field names.

**Draft / commit state machine (required behavior):**
1. Open from launcher or Edit → snapshot committed form controls into draft; `dialog.showModal()`; focus first control; store invoker.
2. Control changes update draft only; debounce ~250 ms → `GET /api/backtest` with draft substituted into current query; AbortController + generation counter.
3. `GET /filter-detail` once per open (candidate removed) to fill chart/table/About.
4. Save enabled only after local validity + latest successful server validation → write canonical `filters-form` controls → `form.requestSubmit()` / GET submit.
5. Cancel / close button / `cancel` event → discard draft, close, restore invoker focus. Backdrop click must not commit or silently discard (D-21).

**Stale-request pattern** (from RESEARCH; apply verbatim):
```javascript
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

**Dialog lifecycle pattern** (from RESEARCH):
```javascript
dialog.addEventListener("cancel", (event) => {
  event.preventDefault();
  discardAndClose();
});
dialog.addEventListener("close", () => invoker?.focus());
```

**DOM safety (D-19):** build table rows and About text with `textContent` / `createElement` — never `innerHTML` with server strings.

**Numeric UI:** two overlaid native `input[type=range]` synchronized with BETWEEN number inputs; disable Save when reversed/invalid (D-06).

**Categorical UI:** client-side case-insensitive filter + sortable columns over already-fetched rows; multi-select → `in` list written to `ff_value` (D-11–D-12). Boolean: two exclusive Yes/No rows (D-13).

---

### `tests/test_filter_modal.py` (NEW test)

**Analog:** `tests/test_web.py` + `tests/test_web_features.py` — Flask `create_app(tmp_path)`, sample games, features sidecar, HTML/JSON assertions.

**Fixture / client pattern** (`test_web_features.py` lines 11–36):
```python
from cfb_system_maker.enrich import save_features
from cfb_system_maker.normalize import normalize_games
from cfb_system_maker.sample_data import SAMPLE_GAMES_2023, SAMPLE_LINES_2023
from cfb_system_maker.storage import save_processed_games
from cfb_system_maker.web import create_app

def test_...(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    save_features(tmp_path, {str(game.game_id): {...} for game in games})
    app = create_app(tmp_path)
    response = app.test_client().get("/?side=home&...")
    assert response.status_code == 200
```

**JSON endpoint test shape** (RESEARCH + Flask testing docs):
```python
response = client.get("/api/backtest", query_string={"side": "home", ...})
assert response.status_code == 200
assert response.json["wins"] == ...
```

**Parallel-array alignment tests** (`test_web.py` lines 487–510) — extend for Save serialization of paired numeric filters and Edit rewrite:
```python
parsed = parse_qs(href.lstrip("?"))
assert parsed["ff_key"] == ["weather_windSpeed"]
assert parsed["ff_op"] == ["lte"]
assert parsed["ff_value"] == ["20"]
assert parsed["ff_perspective"] == ["single"]
```

**Remove both bounds** (`test_web.py` lines 470–484) — mirror for `/filter-detail` candidate removal of `spread_range` / paired feature filters.

**Rendered-contract checks:** launchers, one `<dialog>`, `.js`-gated fallback visibility hooks, escaped descriptions, lookahead warning inside modal markup, Edit buttons on sentences.

**Keep green:** existing `tests/test_web.py` remove-link / load / Fade / tabs tests and `tests/test_web_features.py`.

## Shared Patterns

### Canonical state = form + query string
**Source:** `web.py` `_form_values` / `_system_from_form` / `_query_args_from_form`
**Apply to:** modal Save, `/api/backtest` input, progressive enhancement
- Browser drafts only; commit writes real named controls then full-page GET.
- No localStorage / separate persisted modal model.

### Server-owned matching and grading
**Source:** `backtest.matches_system`, `backtest.grade_bet`, `features.feature_ok`
**Apply to:** `/api/backtest`, `/filter-detail` per-value rows, live chips
- Never compute Record/ROI/Money in JavaScript.
- Preserve home-spread sign via `_side_spread`; preserve Fade flip inside `grade_bet`.

### Allowlisted feature keys + parallel `ff_*` arrays
**Source:** `FEATURE_BY_KEY`, `_feature_filters_from_request`, `_query_href_removing`
**Apply to:** strict API parser, Save rewrite, Edit/Remove
- Unknown namespaced IDs → `400`.
- Replace candidate rows structurally; rebuild all five arrays together.

### Progressive enhancement
**Source:** CONTEXT D-05; `filters-form` real controls in `index.html`
**Apply to:** sidebar launchers + `filter_modal.js`
- Fallback controls visible without JS; enhancement adds root `.js` then hides fallback / reveals launchers.

### Visual vocabulary
**Source:** `styles.css` tokens + `index.html` chips/SVG/tables
**Apply to:** modal header, chart, value table, About panel
- Reuse `.positive`/`.negative`, chip articles, SVG chart classes; no new framework/chart lib (D-23).

### Plain-text definitions
**Source:** Jinja auto-escape + `FeatureDef.description` (new)
**Apply to:** About Filter panel, error messages, categorical labels
- `textContent` / Jinja escaping only; never `|safe` or `innerHTML` for definitions (D-19).

### Lightweight vs full backtest
**Source:** `run_backtest` head vs `compute_system_stats` (1000-iter permutation)
**Apply to:** `/api/backtest` only
- Default index page may keep full analysis; live modal path must skip stats/permutation/grade.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `cfb_system_maker/static/filter_modal.js` (interaction shell) | client component | event-driven + fetch | Repo has no static JS modules or `<dialog>` usage yet — follow RESEARCH MDN patterns; wire to existing form field names and CSS tokens |

Planner should use RESEARCH.md Patterns 2–4 and Code Examples for dialog/AbortController/dual-range details where this map marks partial.

## Metadata

**Analog search scope:** `cfb_system_maker/` (`web.py`, `backtest.py`, `features.py`, `describe.py`, `models.py`, `templates/`, `static/`), `tests/test_web.py`, `tests/test_web_features.py`, `tests/test_describe.py`, `tests/test_features.py`, `.planning/phases/04-filter-popup-modal/{04-CONTEXT,04-RESEARCH}.md`, `.planning/ROADMAP.md` Phase 4
**Files scanned:** ~20 primary sources
**Pattern extraction date:** 2026-07-17
