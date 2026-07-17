# Phase 2: Integrity — Fade & Grade - Pattern Map

**Mapped:** 2026-07-17
**Files analyzed:** 6 (all modified, no new files)
**Analogs found:** 6 / 6 (all self-analogs — this phase extends existing modules in place; the "closest analog" for each change is the surrounding code in the same file)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `cfb_system_maker/models.py` | model | transform (frozen dataclass field) | itself — `SystemFilter` existing boolean fields (`favorite`, `underdog`, `home`, `away`) | exact |
| `cfb_system_maker/backtest.py` (fade flip) | service | transform (pure grading function) | itself — `grade_bet` / `_grade_total_bet` existing win/loss/push branching | exact |
| `cfb_system_maker/backtest.py` (compute_grade + sub-scores) | service | transform (pure composite scoring function) | itself — `compute_system_stats` / `sign_consistency` (same file, same call pattern: pure function over already-computed stats, called once from `run_backtest`/`web.py`) | exact |
| `cfb_system_maker/storage.py` | model / file-I/O | CRUD (JSON read/write with backward-compat defaulting) | itself — existing `theory` field handling in `_system_to_dict` / `_system_from_dict` / `load_saved_system` | exact |
| `cfb_system_maker/web.py` | controller | request-response (query-string / form parsing) | itself — existing `favorite`/`underdog`/`home`/`away` boolean round-trip in `_form_values`, `_form_values_from_post`, `_form_from_system`, `_query_args_from_form` | exact |
| `cfb_system_maker/templates/index.html` | component | request-response (SSR template render) | itself — existing checkbox fieldset (Position group) + Grade chip placeholder | exact |
| `cfb_system_maker/cli.py` | controller | request-response (CLI arg parsing, optional/discretionary) | itself — existing `backtest` subcommand's other `SystemFilter` flags | role-match (not read this session — low risk, follow existing argparse flag pattern) |
| `tests/test_backtest.py`, `tests/test_storage.py`, `tests/test_web.py` | test | — | themselves — existing test conventions per RESEARCH.md Validation Architecture | exact |

**Note:** This phase adds zero new files. Every "pattern assignment" below is "how the existing code in this same file already does an analogous thing" — there is no cross-module borrowing needed; RESEARCH.md already did this analog-finding work and it has been verified directly against source in this pass.

## Pattern Assignments

### `cfb_system_maker/models.py` — add `SystemFilter.fade: bool = False`

**Analog:** same class, existing boolean fields.

**Current field block** (`models.py` lines 30–48):
```python
@dataclass(frozen=True)
class SystemFilter:
    bet_type: str = "spread"
    side: str = "home"
    total_side: str = "over"
    seasons: set[int] = field(default_factory=set)
    weeks: set[int] = field(default_factory=set)
    teams: set[str] = field(default_factory=set)
    conferences: set[str] = field(default_factory=set)
    favorite: bool = False
    underdog: bool = False
    home: bool = False
    away: bool = False
    providers: set[str] = field(default_factory=set)
    min_spread: float | None = None
    max_spread: float | None = None
    min_total: float | None = None
    max_total: float | None = None
    feature_filters: tuple[FeatureFilter, ...] = ()
```

**Pattern to copy:** Add `fade: bool = False` alongside `favorite`/`underdog`/`home`/`away` (simple boolean field, default `False`, no `field(default_factory=...)` needed since it's a scalar). Placement: anywhere in the boolean cluster (lines 39–42) is idiomatic; exact position doesn't matter since these are constructed by keyword everywhere in the codebase (`SystemFilter(fade=True, ...)`), never positionally.

---

### `cfb_system_maker/backtest.py` — fade flip inside `grade_bet` / `_grade_total_bet`

**Analog:** the existing win/loss/push branching in the same two functions (lines 198–296).

**`grade_bet` current structure** (lines 198–253) — the load-bearing line to change is 207:
```python
def grade_bet(
    game: GameRecord,
    system: SystemFilter | str,
    *,
    stake: float = 1.0,
    american_odds: int = -110,
) -> BetDetail:
    if isinstance(system, str):
        system = SystemFilter(side=system)
    normalized_side = system.side.lower()          # <-- line 207: flip target
    if game.home_points is None or game.away_points is None:
        raise ValueError("game must have spread and final score")
    if system.bet_type == "total":
        return _grade_total_bet(game, system, stake=stake, american_odds=american_odds)
    if game.spread is None:
        raise ValueError("game must have spread and final score")

    if normalized_side == "home":
        team = game.home_team
        ...
```

**Pattern to copy:** Insert immediately after line 207:
```python
    normalized_side = system.side.lower()
    if system.fade:
        normalized_side = "away" if normalized_side == "home" else "home"
```
Everything downstream (`team`, `opponent`, `team_points`, `spread = _side_spread(...)`, `cover_margin`, `result`, `profit`, and the `BetDetail(side=normalized_side, ...)` construction at line 246) already derives from `normalized_side` — no other line in `grade_bet` needs to change. This matches the existing style: a single local variable computed once near the top, consumed by the unchanged branching below (mirrors how `side_spread` is computed once in `matches_system` at line 121 and reused).

**`_grade_total_bet` current structure** (lines 256–296) — flip target is `system.total_side` used at lines 277, 288, 290:
```python
def _grade_total_bet(
    game: GameRecord,
    system: SystemFilter,
    *,
    stake: float,
    american_odds: int,
) -> BetDetail:
    if game.total is None or game.home_points is None or game.away_points is None:
        raise ValueError("game must have total and final score")

    points = game.home_points + game.away_points
    if points > game.total:
        winner = "over"
    elif points < game.total:
        winner = "under"
    else:
        winner = "push"

    if winner == "push":
        result = "push"
        profit = 0.0
    elif winner == system.total_side:        # <-- line 277
        result = "win"
        profit = _profit_for_win(stake, american_odds)
    else:
        result = "loss"
        profit = -stake

    return BetDetail(
        ...
        team=system.total_side.title(),        # <-- line 288
        opponent=f"{game.away_team} at {game.home_team}",
        side=system.total_side,                # <-- line 290
        ...
    )
```

**Pattern to copy:** Add one local near the top (after `points`/`winner` computation, before the `if winner == "push"` block):
```python
    effective_total_side = system.total_side
    if system.fade:
        effective_total_side = "under" if effective_total_side == "over" else "over"
```
Then replace the three `system.total_side` reads at (former) lines 277/288/290 with `effective_total_side`. Do **not** touch `winner` computation (lines 266–272) — that's the matching-independent outcome, analogous to margin sign in the spread case; flipping happens only in the comparison/labeling step, exactly mirroring where the spread version flips only `normalized_side`, not `cover_margin`'s formula.

**Anti-pattern (from RESEARCH.md, verified against `matches_system` lines 99–159 directly):** Never flip `system.side`/`system.total_side` before `run_backtest` calls `matches_system` (line 21: `matched = [game for game in games if matches_system(game, system, feature_map)]`). `matches_system` reads `side` at lines 111, 119–121, 133–136 to resolve `team`/`conference`/`side_spread` for `favorite`/`underdog`/`home`/`away`/`teams`/`conferences` filters — flipping upstream changes the matched population, violating D-03.

---

### `cfb_system_maker/backtest.py` — `compute_grade` + 5 sub-score helpers + `count_overfit_filters`

**Analog:** `compute_system_stats` (lines 162–195) and `sign_consistency` (lines 94–96) — same file, same shape: pure function consuming already-computed fields, called once from `run_backtest`.

**Placement:** Add after `sign_consistency` (line 96) or after `compute_system_stats` (line 195) — both are natural neighbors since `compute_grade` consumes both their outputs. `run_backtest` (lines 12–51) already builds `BacktestResult` with `stats=compute_system_stats(...)` (line 48) and `season_breakdown=tuple(compute_season_breakdown(...))` (line 49) — `compute_grade` is called **after** `run_backtest` returns (in `web.py`, per RESEARCH.md's flow diagram), not inside `run_backtest` itself, since `BacktestResult` doesn't currently carry a `grade` field and RESEARCH.md's design passes `result` + `system` into `compute_grade` separately rather than adding a `grade` field to the frozen `BacktestResult` dataclass. **Decision point for planner:** either (a) add `grade: str | None` to `BacktestResult` and compute it inside `run_backtest` (requires `run_backtest` to also take `system` — it already does, as parameter `system` at line 14), which is more consistent with "BacktestResult is fade-correct already" framing in RESEARCH.md line 115, or (b) call `compute_grade(result, system)` separately in `web.py`. Option (a) is simpler for the template (`result.grade` alongside `result.wins` etc., matching the existing `article><span>Record</span><strong>{{ result.wins }}...` chip pattern at `index.html` line 228) — recommend (a).

**Full implementation already specified verbatim in RESEARCH.md** (lines 220–330 of `02-RESEARCH.md`) — reproduced here as the copy-source:
```python
_GRADE_BANDS = (  # (min composite score inclusive, letter)
    (0.85, "A"),
    (0.70, "B"),
    (0.55, "C"),
    (0.35, "D"),
    (0.00, "F"),
)

def _sample_size_score(decided: int) -> float:
    if decided < 30: return 0.0
    if decided < 100: return 0.3
    if decided < 300: return 0.6
    if decided < 1000: return 0.8
    return 1.0

def _roi_significance_score(z_score: float) -> float:
    if z_score < 0: return 0.0
    if z_score < 1.0: return 0.2
    if z_score < 1.645: return 0.5
    if z_score < 1.96: return 0.75
    return 1.0

def _consistency_score(profitable: int, total_seasons: int) -> float:
    if total_seasons == 0: return 0.0
    return profitable / total_seasons

def _permutation_score(p_value: float) -> float:
    if p_value < 0.01: return 1.0
    if p_value < 0.05: return 0.8
    if p_value < 0.10: return 0.5
    if p_value < 0.20: return 0.25
    return 0.0

def _overfit_score(active_filter_value_count: int) -> float:
    if active_filter_value_count <= 3: return 1.0
    if active_filter_value_count <= 7: return 0.75
    if active_filter_value_count <= 14: return 0.5
    if active_filter_value_count <= 24: return 0.25
    return 0.0

def count_overfit_filters(system: SystemFilter) -> int:
    count = 0
    for flag in (system.favorite, system.underdog, system.home, system.away):
        if flag: count += 1
    for value in (system.min_spread, system.max_spread, system.min_total, system.max_total):
        if value is not None: count += 1
    if system.providers: count += 1
    for values in (system.teams, system.conferences, system.seasons, system.weeks):
        count += len(values)
    for filt in system.feature_filters:
        if filt.op == "in" and isinstance(filt.value, (list, tuple, set)):
            count += len(filt.value)
        else:
            count += 1
    return count

def compute_grade(result: BacktestResult, system: SystemFilter) -> str | None:
    if result.bets == 0:
        return None
    decided = result.wins + result.losses
    stats = result.stats
    profitable, total_seasons = sign_consistency(result.season_breakdown)
    scores = [
        _sample_size_score(decided),
        _roi_significance_score(stats.z_score),
        _consistency_score(profitable, total_seasons),
        _permutation_score(stats.permutation_p_value),
        _overfit_score(count_overfit_filters(system)),
    ]
    composite = sum(scores) / len(scores)
    for threshold, letter in _GRADE_BANDS:
        if composite >= threshold:
            return letter
    return "F"
```

**Note on `count_overfit_filters` — does NOT include `fade` itself as a counted filter** (fade is a grading transform, not a filter that narrows the matched population — consistent with it being invisible to `matches_system`).

**Testing pattern to follow:** `tests/test_backtest.py` already constructs `GameRecord`/`SystemFilter`/`BetDetail` fixtures directly (per CLAUDE.md's "Tests" section) — new boundary tests for each of the 5 sub-score functions plus `compute_grade`/`count_overfit_filters` should use the same direct-construction style, not mocks.

---

### `cfb_system_maker/storage.py` — `fade` JSON round-trip

**Analog:** `theory` field — the only prior field added after initial ship, exact precedent for backward-compat defaulting.

**`_system_to_dict`** (lines 116–149) — `theory` is added at the `SavedSystem` level (line 121, outside the nested `"system"` dict since `theory` lives on `SavedSystem` not `SystemFilter`). **`fade` differs: it belongs on `SystemFilter`** (per D-02), so it goes inside the nested `"system"` dict alongside `favorite`/`underdog`/`home`/`away` (lines 130–133):
```python
            "favorite": system.favorite,
            "underdog": system.underdog,
            "home": system.home,
            "away": system.away,
            # add: "fade": system.fade,
```

**`_system_from_dict`** (lines 152–174, continues past what was read) — mirror the existing `bool(system.get(key, False))` pattern used for `favorite`/`underdog`/`home`/`away` at lines 171–174:
```python
        favorite=bool(system.get("favorite", False)),
        underdog=bool(system.get("underdog", False)),
        home=bool(system.get("home", False)),
        away=bool(system.get("away", False)),
        # add: fade=bool(system.get("fade", False)),
```
This `.get(key, False)` — never `system["fade"]` — is exactly what makes pre-phase saved JSON (missing the `"fade"` key) load without `KeyError`, satisfying the CLAUDE.md storage-backward-compatibility constraint and D-02.

`save_system`/`load_saved_system` (lines 79–106) need no changes — `fade` flows through automatically since it's a `SystemFilter` field, not a `SavedSystem`-level field like `theory` (which required explicit plumbing at lines 84, 105).

---

### `cfb_system_maker/web.py` — fade round-trip through form/query state

**Analog:** the existing `favorite`/`underdog`/`home`/`away` boolean handling — four call sites, all must be touched together (RESEARCH.md Pitfall 3 confirms `theory` had the identical multi-site gap).

**Site 1 — `_form_values()`** (lines 324–346), pattern at line 330:
```python
        "favorite": request.args.get("favorite") == "on",
        "underdog": request.args.get("underdog") == "on",
        "home": request.args.get("home") == "on",
        "away": request.args.get("away") == "on",
        # add: "fade": request.args.get("fade") == "on",
```
**Exact pattern to copy:** `== "on"` string comparison, never `bool(request.args.get(...))` (RESEARCH.md's documented Flask footgun — empty string is truthy).

**Site 2 — `_form_values_from_post()`** (lines 349–371), same pattern at line 355 using `request.form.get(...)` instead of `request.args.get(...)`.

**Site 3 — `_form_from_system()`** (lines 385–414), pattern at lines 390–393:
```python
        "favorite": system.favorite,
        "underdog": system.underdog,
        "home": system.home,
        "away": system.away,
        # add: "fade": system.fade,
```

**Site 4 — `_query_args_from_form()`** (lines 219–264), the boolean-flags loop at lines 225–227:
```python
    for key in ("favorite", "underdog", "home", "away"):
        if form.get(key):
            args.append((key, "on"))
```
**Pattern to copy:** add `"fade"` to this tuple: `for key in ("favorite", "underdog", "home", "away", "fade"):` — this is the exact fix RESEARCH.md Pitfall 3 calls out (analogous gap existed for `theory` and was fixed the same way, though `theory` uses a separate non-boolean branch at lines 261–263 since it's free text, not a checkbox).

**Site 5 (also needed, not explicitly separated above but implied by `_system_from_form`) — `_system_from_form`:** not read this pass but by the same pattern (grep showed it at line 457) will construct `SystemFilter(fade=form.get("fade", False), ...)` mirroring how `favorite`/`underdog`/`home`/`away` are threaded from the form dict into the dataclass constructor.

**Site 6 — `_empty_form()`** (lines 297–317): add `"fade": False,` to the default dict alongside `"favorite": False,` (line 302) — needed so unloaded/fresh page state has the key present for the template's `{% if form.fade %}`.

---

### `cfb_system_maker/templates/index.html` — Fade checkbox + Grade chip

**Analog:** existing Position fieldset checkboxes (lines 45–53) for the toggle; existing Grade chip placeholder (line 232) for the render target.

**Existing Position checkbox pattern** (lines 45–53):
```html
          <fieldset>
            <legend>Position</legend>
            <div class="check-grid">
              <label class="check"><input type="checkbox" name="favorite" {% if form.favorite %}checked{% endif %}> Favorite</label>
              <label class="check"><input type="checkbox" name="underdog" {% if form.underdog %}checked{% endif %}> Underdog</label>
              <label class="check"><input type="checkbox" name="home" {% if form.home %}checked{% endif %}> Home only</label>
              <label class="check"><input type="checkbox" name="away" {% if form.away %}checked{% endif %}> Away only</label>
            </div>
          </fieldset>
```
The sidebar `<form>` itself is at line 20: `<form method="get" class="filters" autocomplete="off">` — **has no `id` attribute currently.** Per D-01 ("near the stat chips") and RESEARCH.md's Pattern (form= attribute), this form needs an `id="filters-form"` added at line 20, and the Fade checkbox placed near the stat-chips section (lines 227–233), not inside this sidebar fieldset block, using `form="filters-form"` to still submit with it:
```html
<!-- line 20, add id: -->
        <form method="get" class="filters" id="filters-form" autocomplete="off">
```
```html
<!-- near line 227, inside or adjacent to the stat-chips section: -->
          <label class="fade-toggle">
            <input type="checkbox" name="fade" form="filters-form" {% if form.fade %}checked{% endif %}>
            Fade System
          </label>
          <section class="metrics stat-chips" aria-label="Backtest metrics">
```

**Grade chip current placeholder** (line 232):
```html
            <article><span>Grade</span><strong>&mdash;</strong></article>
```
**Pattern to copy:** follow the exact same conditional-render style already used by the `Margin` chip at line 229 (`{% if result.average_margin is not none %}...{% else %}&mdash;{% endif %}`):
```html
            <article><span>Grade</span><strong>{% if result.grade %}{{ result.grade }}{% else %}&mdash;{% endif %}</strong></article>
```
(Assumes Option (a) from the `compute_grade` placement decision above — `result.grade` — added to `BacktestResult`.) **Do not** use `|safe` — matches the existing pattern of every other chip (`result.wins`, `result.hit_rate`, `result.profit`, `result.roi`), all rendered through normal Jinja auto-escaping with no `|safe` anywhere in this section, per STATE.md's Phase 1 rule cited in RESEARCH.md.

**Breaking test to fix in the same change:** `tests/test_web.py:134` currently asserts the literal `&mdash;` placeholder string is present — this assertion must be updated once Grade renders a real letter for the sample-data system (RESEARCH.md Pitfall 1).

---

## Shared Patterns

### Backward-compatible optional field on a frozen dataclass
**Source:** `cfb_system_maker/storage.py` `_system_from_dict` (existing `theory`/`favorite` `.get(key, default)` calls, lines 171–174 and `load_saved_system` line 105)
**Apply to:** `SystemFilter.fade` load path — always `.get("fade", False)`, never direct indexing, so JSON saved before this phase loads without `KeyError`.

### Boolean form-field parsing
**Source:** `cfb_system_maker/web.py` lines 330–333, 355–358 (`request.args.get(key) == "on"` / `request.form.get(key) == "on"`)
**Apply to:** every new `fade` read site in `web.py` — never `bool(request.args.get(...))`, which is truthy even for an empty string on some browsers' unchecked-field submission edge cases; the codebase's own `== "on"` idiom is the one true pattern here.

### Query-string field enumeration completeness
**Source:** `cfb_system_maker/web.py` `_query_args_from_form` boolean loop (line 225) and `_empty_form` defaults dict (lines 297–317)
**Apply to:** any new boolean field must be added to **every** enumeration site (`_form_values`, `_form_values_from_post`, `_form_from_system`, `_query_args_from_form`, `_empty_form`, `_system_from_form`) in the same change — these are hand-enumerated lists, not derived from `SystemFilter.__annotations__`, so nothing is automatic.

### Pure function over already-computed stats
**Source:** `cfb_system_maker/backtest.py::compute_system_stats` (lines 162–195) and `sign_consistency` (lines 94–96)
**Apply to:** `compute_grade` and its 5 sub-score helpers — consume `BacktestResult.stats` / `.season_breakdown`, never recompute z-scores, p-values, or season grouping independently.

### No `|safe` on server-computed chip values
**Source:** `cfb_system_maker/templates/index.html` lines 228–231 (Record/Margin/Money Won/ROI chips, all plain Jinja substitution)
**Apply to:** the Grade chip — `result.grade` is always one of a fixed small set (`A`/`B`/`C`/`D`/`F`/`None`), rendered through normal auto-escaping like every sibling chip.

## No Analog Found

None — every file in scope is a modification of an existing file with a directly analogous existing pattern in the same file (documented above). No new files, no new modules, no unprecedented data-flow shape.

## Metadata

**Analog search scope:** `cfb_system_maker/` (backtest.py, models.py, storage.py, web.py, cli.py, templates/index.html), `tests/` (test_backtest.py, test_storage.py, test_web.py)
**Files scanned:** 6 source files read directly this session (line-verified against RESEARCH.md's inline excerpts), plus grep-located test conventions
**Pattern extraction date:** 2026-07-17
