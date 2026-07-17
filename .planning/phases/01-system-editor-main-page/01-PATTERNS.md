# Phase 1: System Editor Main Page - Pattern Map

**Mapped:** 2026-07-16
**Files analyzed:** 6 (2 new, 4 modified)
**Analogs found:** 6 / 6 (all are self-analogs within the same brownfield modules — this is an extend-in-place phase, not a greenfield one)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `cfb_system_maker/describe.py` (NEW) | utility (pure function) | transform | `cfb_system_maker/backtest.py` (pure, framework-independent functions like `compute_season_breakdown`) | role-match |
| `tests/test_describe.py` (NEW) | test | transform | `tests/test_backtest.py` (direct dataclass construction, no fixtures/mocks) | exact |
| `cfb_system_maker/web.py` (MODIFIED: `_cumulative_chart`, `_query_href`, tab handling, theory round-trip) | controller (Flask routes + request-scoped helpers) | request-response | `cfb_system_maker/web.py:447 _range_chart` (self, existing chart fn in same file) | exact |
| `cfb_system_maker/models.py` (MODIFIED: `SavedSystem.theory`, `BetDetail.margin`, `BacktestResult.average_margin`) | model (frozen dataclass) | CRUD | `cfb_system_maker/models.py` (self, existing dataclass field patterns) | exact |
| `cfb_system_maker/storage.py` (MODIFIED: `_system_to_dict`/`_system_from_dict`, `save_system`, new `load_saved_system`) | service (JSON persistence) | file-I/O | `cfb_system_maker/storage.py` (self, existing `_system_from_dict`/`save_system`) | exact |
| `cfb_system_maker/backtest.py` (MODIFIED: `grade_bet` threads `margin` into `BetDetail`, `run_backtest` computes `average_margin`) | service (pure computation) | transform | `cfb_system_maker/backtest.py` (self, existing `grade_bet`/`run_backtest`) | exact |
| `templates/index.html` (MODIFIED: chip header, sentence rows, tab nav, theory field, cumulative chart) | component (Jinja template) | request-response | `templates/index.html` (self — `.metrics` block lines 225-232, `.range-chart` block lines 277-289) | exact |
| `static/styles.css` (MODIFIED: chip/sentence/tab styling) | config (stylesheet) | — | `static/styles.css` (self — `.metrics`, `.range-chart`, `.chart-axis` rule blocks) | exact |

Because this phase is a brownfield restyle with no new architectural layer, every "analog" is the same file being extended — the pattern to copy is always the sibling function/section already in that file, not a different module. `describe.py` is the one genuinely new module; its closest analog is `backtest.py`'s existing pure-function style (no Flask import, plain dataclass params in/out).

## Pattern Assignments

### `cfb_system_maker/describe.py` (NEW — utility, transform)

**Analog:** `cfb_system_maker/backtest.py` (pure function style) + `cfb_system_maker/features.py` (`FEATURE_BY_KEY` lookup, referenced not re-read this session — already documented in RESEARCH.md Pattern 2)

**Module header pattern** (mirror `backtest.py` lines 1-9):
```python
from __future__ import annotations

from cfb_system_maker.features import FEATURE_BY_KEY
from cfb_system_maker.models import SystemFilter
```
No Flask/`request` import — `describe()` must stay framework-independent (RESEARCH.md explicitly calls this out: Phase 4 reuses it outside a request context).

**Function signature convention** (mirror `backtest.compute_season_breakdown(details, *, stake=1.0) -> list[SeasonRecord]`, `backtest.py:70-90`):
```python
def describe(system: SystemFilter) -> list[dict[str, object]]:
    """Return one {"text": ..., "key": ...} dict per active constraint, in a stable order."""
    sentences: list[dict[str, object]] = []
    if system.favorite:
        sentences.append({"text": "the team is a favorite", "key": "favorite"})
    if system.underdog:
        sentences.append({"text": "the team is an underdog", "key": "underdog"})
    # ... one branch per SystemFilter field per RESEARCH.md's op-phrase table ...
    for filt in system.feature_filters:
        feature = FEATURE_BY_KEY.get(filt.key)
        if feature is None:
            continue
        sentences.append({"text": _feature_phrase(feature, filt), "key": f"ff:{filt.key}"})
    return sentences
```
The `"key"` field is the stable per-row identifier `web.py`'s request-scoped `_query_href` helper will consume to build remove-links — keep it a plain string (e.g. `"favorite"`, `"min_spread"`, `"ff:<feature_key>"`), never an index, per RESEARCH.md's Pitfall about index-based removal being unnecessary.

---

### `cfb_system_maker/web.py` (MODIFIED — controller, request-response)

**Analog:** self, `_range_chart` at `web.py:447-483` (existing chart pattern), and the existing `_form_from_system`/`_system_from_form` round-trip at `web.py:274-386`.

**Imports pattern** (existing, lines 1-18 — extend, don't restructure):
```python
from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for

from cfb_system_maker.backtest import matches_system, run_backtest, sign_consistency, split_holdout
from cfb_system_maker.models import BacktestResult, FeatureFilter, GameRecord, SystemFilter
from cfb_system_maker.storage import list_systems, load_processed_games, load_system, save_system
```
Add `from cfb_system_maker.describe import describe` and (for the new `SavedSystem`-returning loader) `load_saved_system` to the `storage` import line — do not touch `load_system`'s existing signature/callers (`web.py:50`, `web.py:114`, `cli.py:162`).

**New chart function — copy `_range_chart`'s shape exactly** (`web.py:447-483`):
```python
def _range_chart(result: BacktestResult) -> dict[str, object]:
    if not result.bet_details:
        return {"points": [], "polyline": "", "zero_y": 75, "min_x": None, "max_x": None}
    buckets: dict[float, float] = {}
    for bet in result.bet_details:
        line = round(bet.line * 2) / 2
        buckets[line] = round(buckets.get(line, 0.0) + bet.profit, 4)
    items = sorted(buckets.items())
    # ... width/height/pad_x/pad_y/min/max/scale/points/polyline/zero_y ...
    return {"points": points, "polyline": " ".join(...), "zero_y": ..., "min_x": ..., "max_x": ...}
```
`_cumulative_chart(result)` reuses this exact shape (same dict keys: `points`/`polyline`/`zero_y`/`min_x`/`max_x`) so the existing SVG Jinja block (`index.html:280-286`) can be copy-adapted rather than rewritten — only the aggregation loop changes (running sum over `sorted(bet_details, key=lambda b: (b.season, b.week, b.game_id))` instead of per-line buckets).

**Request-scoped query-string helper — new pattern, verified against installed werkzeug 3.1.8** (from RESEARCH.md Pattern 3, not yet in codebase but the concrete code to use):
```python
from urllib.parse import urlencode
from werkzeug.datastructures import MultiDict

def _query_href(**overrides: str) -> str:
    copy = MultiDict(request.args.items(multi=True))
    for key, value in overrides.items():
        copy.setlist(key, [value])
    return "?" + urlencode(list(copy.items(multi=True)))

def _query_href_removing(key: str, value: str | None = None) -> str:
    copy = MultiDict(request.args.items(multi=True))
    if value is None:
        copy.poplist(key)
    else:
        copy.setlist(key, [v for v in copy.getlist(key) if v != value])
    return "?" + urlencode(list(copy.items(multi=True)))
```

**Route pattern — extend `index()`, don't restructure** (`web.py:26-81`): add `tab = request.args.get("tab", "graph")`, `chip_margin`/`chip_grade` placeholder values, `theory` from the loaded `SavedSystem`, and pass `cumulative_chart=_cumulative_chart(result)`, `sentences=describe(system)`, `tab=tab` into the existing `render_template("index.html", ...)` call — same call site, more kwargs, matching how `chart=_range_chart(result)` is already passed at `web.py:78`.

**Save route pattern — extend `save()`, don't restructure** (`web.py:83-90`):
```python
@app.post("/save")
def save():
    form = _form_values_from_post()
    name = str(form.get("save_name", "")).strip()
    if not name:
        return redirect(url_for("index"))
    save_system(name, _system_from_form(form), app.config["DATA_DIR"], theory=form.get("theory", ""))
    return redirect(url_for("index", **{"load_system": name}))
```
Requires `_form_values_from_post()` (`web.py:239-260`) to add `"theory": request.form.get("theory", "")` alongside the existing `"save_name"` line — same dict-literal pattern, one more key.

---

### `cfb_system_maker/models.py` (MODIFIED — model, CRUD)

**Analog:** self — existing frozen-dataclass field-ordering convention.

**`SavedSystem` extension** (`models.py:109-113`, current):
```python
@dataclass(frozen=True)
class SavedSystem:
    name: str
    saved_at: str
    system: SystemFilter
```
Add `theory: str = ""` as a new trailing field (no-default fields already precede it, so this is safe — no reordering needed).

**`BetDetail`/`BacktestResult` extension** (`models.py:67-79`, `93-106`) — must follow RESEARCH.md Pitfall 5's ordering rule:
```python
@dataclass(frozen=True)
class BetDetail:
    game_id: int
    season: int
    week: int
    team: str
    opponent: str
    side: str
    spread: float
    total: float | None
    line: float
    result: str
    profit: float
    margin: float = 0.0   # NEW — append after all non-default fields
```
```python
@dataclass(frozen=True)
class BacktestResult:
    # ...existing non-default fields unchanged...
    stats: SystemStats | None = None
    season_breakdown: tuple[SeasonRecord, ...] = ()
    average_margin: float | None = None   # NEW — appended after existing defaulted fields
```
Both new construction sites in `backtest.py` (`backtest.py:239` `BetDetail(...)`, `backtest.py:37` `BacktestResult(...)`) must be updated explicitly to pass `margin=cover_margin` / `average_margin=...` — they use no defaults today.

---

### `cfb_system_maker/storage.py` (MODIFIED — service, file-I/O)

**Analog:** self — existing `_system_to_dict`/`_system_from_dict`/`save_system`/`load_system` at `storage.py:79-168`.

**Serializer extension** (`storage.py:104-136` `_system_to_dict`):
```python
def _system_to_dict(saved: SavedSystem) -> dict[str, Any]:
    system = saved.system
    return {
        "name": saved.name,
        "saved_at": saved.saved_at,
        "theory": saved.theory,   # NEW key, same flat-dict style as name/saved_at
        "system": { ... unchanged ... },
    }
```

**Deserializer extension — must use `.get()` with default, per RESEARCH.md Pitfall 2** (mirror existing pattern already used for `system.get("bet_type", "spread")` at `storage.py:151`):
```python
theory=str(payload.get("theory", "")),
```

**New reader — do not touch `load_system`'s signature** (`storage.py:91-94`, existing, must stay untouched):
```python
def load_system(name: str, data_dir: str | Path) -> SystemFilter:
    path = Path(data_dir) / "systems" / f"{name}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _system_from_dict(payload)

# NEW — additive, same file-read pattern, different return type:
def load_saved_system(name: str, data_dir: str | Path) -> SavedSystem:
    path = Path(data_dir) / "systems" / f"{name}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return SavedSystem(
        name=str(payload.get("name", name)),
        saved_at=str(payload.get("saved_at", "")),
        system=_system_from_dict(payload),
        theory=str(payload.get("theory", "")),
    )
```

**`save_system` extension** (`storage.py:79-88`) — add a defaulted keyword param so `cli.py`'s existing no-theory call site keeps working:
```python
def save_system(name: str, system: SystemFilter, data_dir: str | Path, theory: str = "") -> Path:
    saved = SavedSystem(
        name=name,
        saved_at=datetime.now(timezone.utc).isoformat(),
        system=system,
        theory=theory,
    )
    path = Path(data_dir) / "systems" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_system_to_dict(saved), indent=2, sort_keys=True), encoding="utf-8")
    return path
```

---

### `cfb_system_maker/backtest.py` (MODIFIED — service, transform)

**Analog:** self — `grade_bet` at `backtest.py:197-251`, `run_backtest` at `backtest.py:12-50`.

**Thread `cover_margin` into the returned `BetDetail`** (`backtest.py:227-250`, existing computation currently discarded):
```python
spread = _side_spread(game.spread, normalized_side)
cover_margin = team_points + spread - opponent_points
if cover_margin > 0:
    result = "win"
    profit = _profit_for_win(stake, american_odds)
elif cover_margin < 0:
    result = "loss"
    profit = -stake
else:
    result = "push"
    profit = 0.0

return BetDetail(
    game_id=game.game_id, season=game.season, week=game.week,
    team=team, opponent=opponent, side=normalized_side,
    spread=spread, total=game.total, line=spread, result=result,
    profit=round(profit, 4),
    margin=round(cover_margin, 4),   # NEW
)
```
Per CONTEXT.md's discretion decision, `_grade_total_bet` (`backtest.py:254-294`) does **not** get an analogous margin formula this phase — its `BetDetail(...)` call keeps the `margin` field at its `0.0` default, and `web.py`/`index.html` render the Margin chip as `—` when `system.bet_type == "total"` (mirroring the Grade-chip placeholder pattern already accepted in CONTEXT.md).

**`run_backtest` — compute `average_margin` only over spread bets** (`backtest.py:37-50`):
```python
return BacktestResult(
    # ...existing fields unchanged...
    average_margin=(
        round(sum(bet.margin for bet in details) / bets, 4)
        if bets and system.bet_type == "spread" else None
    ),
)
```

---

### `templates/index.html` (MODIFIED — component, request-response)

**Analog:** self — `.metrics` chip block (`index.html:225-232`) is the direct restyle target; `.range-chart` SVG block (`index.html:277-289`) is the direct copy-adapt target for the new cumulative chart; `saved-systems` link-list pattern (`index.html:194-208`, plain `<a href="?...">`) is the pattern to follow for tab links and remove-links — no JS.

**Stat-chip header — restyle in place, add Margin/Money Won/Grade** (extends `index.html:225-232`):
```html
<section class="metrics" aria-label="Backtest metrics">
  <article><span>Bets</span><strong>{{ result.bets }}</strong></article>
  <article><span>ROI</span><strong class="{{ 'positive' if result.roi > 0 else 'negative' if result.roi < 0 else '' }}">{{ "%.2f%%"|format(result.roi * 100) }}</strong></article>
  <article><span>Money Won</span><strong>{{ "%+,.0f"|format(result.profit * 100) }}</strong></article>
  <article><span>Margin</span><strong>{% if result.average_margin is not none %}{{ "%.1f"|format(result.average_margin) }}{% else %}&mdash;{% endif %}</strong></article>
  <article><span>Grade</span><strong>&mdash;</strong></article>
  <!-- existing Hit Rate / W-L-P / Avg Line articles unchanged -->
</section>
```

**Tab nav — plain `<a>` query-string links, same pattern as `saved-systems` list** (new, modeled on `index.html:199-203`):
```html
<nav class="tabs">
  <a href="{{ query_href(tab='graph') }}" {% if tab == 'graph' %}aria-current="true"{% endif %}>Results Graph</a>
  <a href="{{ query_href(tab='matches') }}" {% if tab == 'matches' %}aria-current="true"{% endif %}>Past Matches</a>
</nav>
{% if tab == 'graph' %}
  <!-- cumulative chart block, copy-adapted from .range-chart at index.html:277-289 -->
{% else %}
  <!-- existing table-wrap bets table, moved under this branch -->
{% endif %}
```
`query_href` needs to be exposed to Jinja — either register `_query_href` as a Jinja global (`app.jinja_env.globals["query_href"] = _query_href`) or pass precomputed hrefs into the template context; either is consistent with this template's existing "logic in `web.py`, template only renders" split (`chart=_range_chart(result)` is already passed precomputed).

**Filter sentence rows with remove links** (new, modeled on `.saved-systems ul li` list pattern, `index.html:199-203`):
```html
<ul class="active-filters">
  {% for row in sentences %}
    <li>{{ row.text }} <a class="remove-filter" href="{{ query_href_removing(row.key) }}" aria-label="Remove filter">&times;</a></li>
  {% endfor %}
</ul>
```

**Theory field — bundled into existing `<form method="get" class="filters">`, saved via existing `POST /save`** (new field near `form-actions`, `index.html:185-191`):
```html
<label class="theory-field full-width">Theory
  <textarea name="theory" placeholder="Why does this system work?">{{ form.theory }}</textarea>
</label>
<div class="form-actions">
  <button type="submit">Run System</button>
  <label class="save-inline">Save as
    <input name="save_name" value="{{ form.save_name }}" placeholder="my-system">
  </label>
  <button type="submit" formaction="{{ url_for('save') }}" formmethod="post">Save System</button>
</div>
```
Note: the theory `<textarea>` sits inside the `method="get"` filter form but is only meaningfully consumed by the `formaction="{{ url_for('save') }}" formmethod="post"` submit button (same dual-submit pattern the form already uses for `save_name` — GET-submit ignores it harmlessly, POST-submit reads it via `request.form.get("theory", "")`).

---

### `static/styles.css` (MODIFIED — config, styling)

**Analog:** self — existing rule blocks at lines 207 (`.chart-axis`), 242-270 (`.metrics`/`.metrics article`/`.metrics span`/`.metrics strong`), 272-305 (`.range-chart`/`.range-chart h3`/`.range-chart svg`/`.range-chart polyline`/`.range-chart circle`/`.range-chart .zero-line`), 407 (responsive `.metrics` breakpoint).

New rule blocks to add follow the same naming convention (`.tabs`, `.active-filters`, `.remove-filter`, `.theory-field`) as siblings to the existing `.metrics`/`.range-chart` blocks — no restructuring of existing rules, no new CSS framework/preprocessor (plain CSS only, per tech-stack constraint).

## Shared Patterns

### Query-string-preserving links (tabs + remove-filter)
**Source:** RESEARCH.md Pattern 3 (verified against installed werkzeug 3.1.8) — new `_query_href`/`_query_href_removing` helpers in `web.py`, following the request-scoped-helper convention already established by `_form_values()` (`web.py:215-236`, which also reads from `request.args`).
**Apply to:** `templates/index.html` tab nav links (EDIT-04) and filter-sentence remove links (EDIT-03). Never hand-roll string concatenation of `?key=value&...` at more than one call site — RESEARCH.md's Anti-Patterns section flags this as the most likely over-engineering/bug trap.

### Backward-compatible JSON field defaulting
**Source:** `storage.py:151` existing `system.get("bet_type", "spread")` pattern.
**Apply to:** `storage._system_from_dict` / new `load_saved_system` reading `payload.get("theory", "")` — every optional field added to a persisted JSON shape in this codebase already uses `.get(key, default)`, never direct `payload[key]` indexing.

### Frozen-dataclass field append with defaults
**Source:** `models.py` existing trailing-defaulted fields (`SystemStats.max_win_streak`/`max_loss_streak`/`permutation_p_value`, `BacktestResult.stats`/`season_breakdown`).
**Apply to:** `SavedSystem.theory`, `BetDetail.margin`, `BacktestResult.average_margin` — always append after existing non-default fields, always give a default, always update every direct constructor call site in `backtest.py` explicitly (dataclass defaults do not retroactively fix omitted required args at existing call sites once a field becomes semantically required by the phase).

### Dollar-conversion boundary (×100 for Money Won)
**Source:** RESEARCH.md Pitfall 3, `backtest.py`'s `stake=1.0` convention throughout (`run_backtest` default, `grade_bet`'s `_profit_for_win`).
**Apply to:** Template-render-time only (`index.html`'s Money Won chip and cumulative-chart values) — never inside `backtest.py`. `result.profit`/`bet.profit`/`result.roi` must stay untouched to avoid breaking existing `test_backtest.py` assertions (e.g. `round(result.profit, 4) == 0.9091`).

## No Analog Found

None — every file in this phase's scope is either a new pure-function module (`describe.py`, patterned on `backtest.py`'s existing pure-function style) or a targeted extension of an existing module/template/stylesheet with a clear same-file precedent to copy.

## Metadata

**Analog search scope:** `cfb_system_maker/*.py`, `templates/index.html`, `static/styles.css`, `tests/*.py` (all read directly this session; no broader Glob/Grep sweep needed since RESEARCH.md had already enumerated every touch point with line numbers).
**Files scanned:** `web.py` (483 lines), `models.py` (113 lines), `storage.py` (169 lines), `backtest.py` (395 lines), `templates/index.html` (338 lines), `static/styles.css` (targeted grep for `.metrics`/`.range-chart`/`.chart-axis` rule locations).
**Pattern extraction date:** 2026-07-16
