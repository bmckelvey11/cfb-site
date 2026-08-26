# Web App Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix every verified finding from the 2026-08-26 full web-app review: two silent-data-corruption bugs, HTML-route 500s, filter-modal input bugs, per-request performance waste, GUI/a11y defects, dead code, and (optional final phase) module splits.

**Architecture:** All fixes are surgical changes to `cfb_system_maker/web.py`, `static/filter_modal.js`, the four templates, and `static/styles.css`. No new dependencies, no schema changes. Python fixes are TDD against the existing pytest suite (409 passing baseline); JS fixes are verified in the browser via the dev server because the repo has no JS test runner.

**Tech Stack:** Python 3 + Flask + Jinja2, vanilla JS (`<dialog>`-based modal), plain CSS, pytest.

## Global Constraints

- Baseline before ANY change: `python -m pytest` → **409 passed, 3 deselected**. Every task ends with the full suite green.
- `GameRecord.spread` is always the **home** spread; never touch grading/sign logic.
- `SavedSystem` JSON must keep loading gracefully for saves that predate any field.
- `GameRecord` field order is the CSV contract — do not add/reorder fields.
- Match existing style; do not reformat adjacent code.
- One commit per task, pushed after each commit (user's auto-commit+push rule). Commit messages end with:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- Dev server for browser verification: `python -m cfb_system_maker web --data-dir data --port 5000` (or the `.claude/launch.json` entry "CFB System Maker (web)"). Data is already built in `data/processed/`.
- The saved system `data/systems/total-unders-high-lines.json` (bet_type total, side under, `min_total=55`, no max) is the manual-test fixture. **Do not overwrite it.** If a browser test mutates form state, reload the page — nothing persists without POST /save.

---

## Phase A — Correctness (silent data corruption, 500s)

### Task 1: `_form_from_system` drops multi-value core filters

**Files:**
- Modify: `cfb_system_maker/web.py:1104-1108`
- Modify: `cfb_system_maker/templates/index.html:76-99` (five selects)
- Test: `tests/test_web.py`

**Interfaces:**
- Produces: `_form_from_system` returns comma-joined strings for `season`/`week`/`team`/`conference`/`provider` (e.g. `"2022,2023"`). `_int_set`/`_str_set` already split on commas, so `_system_from_form` round-trips unchanged.

Bug: `next(iter(system.seasons), "") if len(system.seasons) == 1 else ""` renders the form **empty** when a saved system has 2+ seasons (same for weeks/teams/conferences/providers). Any subsequent Run System / remove-filter click / tab switch then re-runs over ALL seasons silently. The server-rendered `<select>` also has only single-value options, so even a joined value would fall back to `""` — both halves must be fixed together.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_web.py` (follow the file's existing app-fixture pattern for creating a client with a saved system — copy the setup style of the nearest existing `load_system` test):

```python
def test_form_from_system_joins_multi_value_sets():
    from cfb_system_maker.web import _form_from_system
    from cfb_system_maker.models import SystemFilter

    system = SystemFilter(
        bet_type="spread", side="home", total_side="over",
        seasons={2023, 2022}, weeks=set(), teams={"Auburn", "Alabama"},
        conferences=set(), favorite=False, underdog=False, home=False,
        away=False, fade=False, providers=set(),
        min_spread=None, max_spread=None, min_total=None, max_total=None,
        feature_filters=(),
    )
    form = _form_from_system(system, "multi", "")
    assert form["season"] == "2022,2023"          # sorted numerically
    assert form["team"] == "Alabama,Auburn"       # sorted alphabetically


def test_loading_multi_season_system_renders_joined_value(tmp_path):
    # Build app + save a two-season system using the module's existing helpers,
    # then GET /system?load_system=<name> and assert the joined value appears
    # as a selected option so FormData round-trips it.
    ...  # follow existing save/load test setup in this file
    # resp = client.get("/system?load_system=multi")
    # assert b'value="2022,2023" selected' in resp.data
```

(If `SystemFilter` construction differs, copy a constructor call from `tests/test_backtest.py`.)

- [ ] **Step 2: Run tests, verify they fail**

Run: `python -m pytest tests/test_web.py -k "multi" -v`
Expected: FAIL — `form["season"] == ""`.

- [ ] **Step 3: Fix `_form_from_system`**

Replace web.py lines 1104-1108:

```python
        "season": ",".join(str(s) for s in sorted(system.seasons)),
        "week": ",".join(str(w) for w in sorted(system.weeks)),
        "team": ",".join(sorted(system.teams)),
        "conference": ",".join(sorted(system.conferences)),
        "provider": ",".join(sorted(system.providers)),
```

- [ ] **Step 4: Fix the five selects in `index.html`**

Each select currently renders only single-value options. Mirror the JS draft-option trick server-side: when the form value is non-empty and doesn't match any single option, emit one extra selected option carrying the joined value. For seasons (index.html:76-79):

```jinja
<select name="filter_seasons" id="filter-seasons">
  <option value="">All Seasons</option>
  {% for season in options.seasons %}<option value="{{ season }}" {% if form.season == season|string %}selected{% endif %}>{{ season }}</option>{% endfor %}
  {% if form.season and form.season not in options.seasons|map('string')|list %}<option value="{{ form.season }}" selected>{{ form.season }}</option>{% endif %}
</select>
```

Apply the same pattern to `filter_weeks` (compare against `options.weeks|map('string')|list`), `filter_teams` (`options.teams` — strings already, no `map`), `filter_conferences`, `filter_providers`.

- [ ] **Step 5: Run the new tests and the full suite**

Run: `python -m pytest -q`
Expected: all pass (409 + new).

- [ ] **Step 6: Browser check**

Start the dev server. On `/system`, open the Season filter modal, pick two seasons, Save Filter (page reloads). Confirm the Season select shows the joined value, and clicking **Run System** keeps both seasons (URL contains `filter_seasons=2022,2023`, results unchanged).

- [ ] **Step 7: Commit**

```bash
git add cfb_system_maker/web.py cfb_system_maker/templates/index.html tests/test_web.py
git commit -m "fix(web): round-trip multi-value core filters through form and selects"
git push
```

### Task 2: Editing a half-open range filter silently destroys it

**Files:**
- Modify: `cfb_system_maker/static/filter_modal.js:1377-1384` (prefill) and `:1240-1255` (`writeNumericToForm`)

Bug (reproduced live): the saved filter "total ≥ 55" has `min_total=55`, no max. `openNumericCandidate` only prefills when **both** `committed.min` and `committed.max` are set (js:1377), so Edit opens at the full 26–90 domain; Save then writes `min_total=26, max_total=90` — filter gone.

- [ ] **Step 1: Reproduce**

Dev server → `/system?load_system=total-unders-high-lines` → click **Edit** on the "the total is at least 55" chip. Observe sliders at domain 26–90 instead of 55–90.

- [ ] **Step 2: Fix prefill — accept half-open committed bounds**

Replace js:1377-1384:

```js
        if (committed && (Number.isFinite(committed.min) || Number.isFinite(committed.max))) {
          state.min = Number.isFinite(committed.min) ? committed.min : state.domainMin;
          state.max = Number.isFinite(committed.max) ? committed.max : state.domainMax;
        } else if (state.domainMin != null && state.domainMax != null) {
          state.min = state.domainMin;
          state.max = state.domainMax;
        }
```

(`committedNumericBounds` returns `null` bounds as `null`; `Number.isFinite(null)` is `false`, so this handles both half-open cases.)

- [ ] **Step 3: Fix save — write open bounds back as open**

In `writeNumericToForm` (js:1244-1254), a bound sitting at the domain edge means "unbounded"; writing the edge value converts ≥55 into an explicit 26–90 window that would wrongly exclude future values outside observed data. Replace the core-range branch bodies:

```js
      if (minEl) {
        minEl.value = (state.domainMin != null && Number(state.min) <= Number(state.domainMin)) ? "" : String(state.min);
      }
      if (maxEl) {
        maxEl.value = (state.domainMax != null && Number(state.max) >= Number(state.domainMax)) ? "" : String(state.max);
      }
```

Leave the feature-fallback branch (`data-bound` inputs) as-is for now — feature gte/lte pairs are written per-op and a follow-up can mirror this; the core spread/total ranges are the live bug.

- [ ] **Step 4: Verify in browser**

Reload `/system?load_system=total-unders-high-lines`, click Edit on the total chip:
- Sliders/number boxes read **55 and 90** (min prefilled, max at domain edge).
- Click Save Filter without touching anything → page reloads → chip still reads "the total is at least 55", form still has `min_total=55`, `max_total` empty, Record unchanged (2988-2778-64).

- [ ] **Step 5: Run suite (guards against template/JS-adjacent Python breakage)**

Run: `python -m pytest -q` → green.

- [ ] **Step 6: Commit**

```bash
git add cfb_system_maker/static/filter_modal.js
git commit -m "fix(modal): prefill and preserve half-open numeric ranges instead of widening to full domain"
git push
```

### Task 3: Malformed numeric query params 500 the HTML routes

**Files:**
- Modify: `cfb_system_maker/web.py:1158-1168` (`_parse_filter_value`), `:1204-1213` (`_int_set`, `_optional_float`), `:559` (compare holdout parse)
- Test: `tests/test_web.py`

Reproduced live: `GET /system?min_spread=abc` → 500; `GET /compare?holdout_season=abc` → 500. The strict parser only guards `/api/backtest` + `/filter-detail`. HTML routes should treat junk as "no filter", matching how bad *choice* params already fall back.

- [ ] **Step 1: Write the failing tests**

```python
def test_editor_tolerates_malformed_numeric_params(client):
    assert client.get("/system?min_spread=abc").status_code == 200
    assert client.get("/system?min_spread=nan").status_code == 200      # NaN must not become a silent no-op bound
    assert client.get("/system?filter_seasons=abc,2023").status_code == 200
    assert client.get(
        "/system?ff_enable=temperature&ff_key=temperature&ff_op=gte&ff_value=abc"
    ).status_code == 200


def test_compare_tolerates_malformed_holdout(client):
    assert client.get("/compare?holdout_season=abc").status_code == 200
```

(Reuse the existing `client` fixture/app-construction pattern in test_web.py; if there is no shared fixture, build the app the way neighboring tests do.)

- [ ] **Step 2: Run tests, verify 500s**

Run: `python -m pytest tests/test_web.py -k "malformed or holdout" -v`
Expected: FAIL with status 500.

- [ ] **Step 3: Make the lenient parsers actually lenient**

```python
def _int_set(value: str) -> set[int]:
    result: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            result.add(int(part))
        except ValueError:
            continue
    return result


def _optional_float(value: str) -> float | None:
    try:
        number = float(value)
    except ValueError:
        return None
    return number if math.isfinite(number) else None
```

(`float("")` raises, so the blank case still returns None. `math` is already imported. The isfinite check also closes the `min_spread=nan` silent no-op.)

In `_parse_filter_value`, replace the gte/lte branch (web.py:1166-1167):

```python
    if op in {"gte", "lte"}:
        if not raw_value.strip():
            return None
        try:
            number = float(raw_value)
        except ValueError:
            return None
        return number if math.isfinite(number) else None
```

In `compare()` replace web.py:559:

```python
        holdout_seasons = _int_set(",".join(request.args.getlist("holdout_season")))
```

- [ ] **Step 4: Run new tests + full suite**

Run: `python -m pytest -q` → green.

- [ ] **Step 5: Commit**

```bash
git add cfb_system_maker/web.py tests/test_web.py
git commit -m "fix(web): treat malformed numeric params as absent instead of 500ing HTML routes"
git push
```

### Task 4: Corrupt data files 500 every page

**Files:**
- Modify: `cfb_system_maker/web.py:940-944` (`_try_load_features`), `:1396-1403` (`_saved_systems_newest_first`)
- Modify: `cfb_system_maker/storage.py` (`_system_from_dict` non-dict payload)
- Test: `tests/test_web.py`, `tests/test_storage.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_corrupt_features_sidecar_does_not_500(tmp_path):
    # build app dir with valid games.csv (reuse existing helper/sample setup)
    # then write garbage to processed/features.json:
    (data_dir / "processed" / "features.json").write_text("{not json", encoding="utf-8")
    resp = client.get("/system")
    assert resp.status_code == 200            # renders with features_enabled=False


def test_non_dict_system_file_does_not_crash_dashboard(tmp_path):
    (data_dir / "systems" / "weird.json").write_text("[]", encoding="utf-8")
    resp = client.get("/")
    assert resp.status_code == 200
```

And in `tests/test_storage.py`:

```python
def test_system_from_non_dict_payload_raises_value_error(tmp_path):
    path = tmp_path / "systems"
    path.mkdir()
    (path / "weird.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        load_saved_system("weird", tmp_path)
```

- [ ] **Step 2: Run, verify failures** (`AttributeError`/500 today).

- [ ] **Step 3: Fixes**

web.py — widen `_try_load_features` to match `_try_load_upcoming_features` (web.py:1665-1669):

```python
def _try_load_features(data_dir: Path) -> dict[int, dict] | None:
    try:
        return load_features(data_dir)
    except (FileNotFoundError, OSError, ValueError, KeyError, json.JSONDecodeError):
        return None
```

storage.py — at the top of `_system_from_dict` (around storage.py:261), raise the error type callers already catch:

```python
    if not isinstance(payload, dict):
        raise ValueError("system payload must be a JSON object")
```

(`_saved_systems_newest_first` already catches ValueError, so the dashboard test passes with no change there.)

- [ ] **Step 4: Full suite** → green.

- [ ] **Step 5: Commit**

```bash
git add cfb_system_maker/web.py cfb_system_maker/storage.py tests/test_web.py tests/test_storage.py
git commit -m "fix(web): survive corrupt features sidecar and non-object system files"
git push
```

### Task 5: Stale `/filter-detail` responses clobber modal state

**Files:**
- Modify: `cfb_system_maker/static/filter_modal.js` — the three detail fetches (`reloadFeatureDetail` js:695, `openNumericCandidate` js:1352, `openCandidate` js:1482) and the close/cleanup path (js:1277)

All three fetches mutate module-level `state` whenever they resolve — no abort/generation guard like `refreshLive` has (js:421-436). A slow Team fetch resolving after the user switched to Spread Range renders team rows into the numeric modal, or throws on `state = null`.

- [ ] **Step 1: Add a generation counter next to the live one (js:44)**

```js
  let detailGeneration = 0;
```

- [ ] **Step 2: Guard all three fetches identically**

Immediately before each of the three `fetch("/filter-detail?...` calls:

```js
    const generation = ++detailGeneration;
```

At the top of each `.then((payload) => {` and each `.catch(() => {`:

```js
        if (!state || generation !== detailGeneration) {
          return;
        }
```

- [ ] **Step 3: Invalidate on close and on reopen**

In `discardAndClose` (js:1277) and in `openCandidate` next to `liveGeneration += 1` (js:1417):

```js
    detailGeneration += 1;
```

- [ ] **Step 4: Verify in browser**

Open the Team filter (slow, 13k rows), immediately close it, open Spread Range. The numeric modal must show sliders (no value table, no "Couldn't load filter values"). Toggle a perspective button twice fast on a team-scoped feature — final render matches the last-clicked perspective.

- [ ] **Step 5: Commit**

```bash
git add cfb_system_maker/static/filter_modal.js
git commit -m "fix(modal): drop stale /filter-detail responses with a generation guard"
git push
```

### Task 6: Modal input bugs — search focus loss, negative-number typing

**Files:**
- Modify: `cfb_system_maker/static/filter_modal.js:765-768` (search), `:896-907` (`syncBoundInputs`), `:1141-1150` (number listeners)

- [ ] **Step 1: Search box — restore focus after re-render**

Replace the search input listener (js:765-768):

```js
    search.addEventListener("input", () => {
      state.search = search.value;
      renderValueTable();
      const next = controlsEl.querySelector(".filter-modal__search");
      if (next) {
        next.focus();
        const end = next.value.length;
        next.setSelectionRange(end, end);
      }
    });
```

- [ ] **Step 2: Never rewrite the input being typed in**

`syncBoundInputs(source)` force-writes `String(state.min)` into all four inputs, so typing `-` (parses to `Number("") === 0` upstream) snaps the box to `0`. In js:896-907, skip the source input:

```js
    if (minRange && source !== "minRange") {
      minRange.value = String(state.min);
    }
    if (maxRange && source !== "maxRange") {
      maxRange.value = String(state.max);
    }
    if (minNumber && source !== "minNumber") {
      minNumber.value = String(state.min);
    }
    if (maxNumber && source !== "maxNumber") {
      maxNumber.value = String(state.max);
    }
```

- [ ] **Step 3: Treat incomplete number entry as invalid, not zero**

Replace the two number-input listeners (js:1141-1150):

```js
    minNumber.addEventListener("input", () => {
      const parsed = minNumber.value.trim() === "" ? NaN : Number(minNumber.value);
      state.min = parsed;
      syncBoundInputs("minNumber");
      refreshLive();
    });
    maxNumber.addEventListener("input", () => {
      const parsed = maxNumber.value.trim() === "" ? NaN : Number(maxNumber.value);
      state.max = parsed;
      syncBoundInputs("maxNumber");
      refreshLive();
    });
```

(`boundsAreValid()` already rejects non-finite values, which disables Save and shows the bound hint via the existing `refreshLive` invalid branch at js:404-411 — so a half-typed `-` just pauses validation instead of corrupting state.)

- [ ] **Step 4: Verify in browser**

Spread Range modal: type `-14` into the min BETWEEN box character by character — it must accept the minus sign and land on -14 with live stats updating. Team filter: type three characters into Search values without re-clicking.

- [ ] **Step 5: Commit**

```bash
git add cfb_system_maker/static/filter_modal.js
git commit -m "fix(modal): keep focus in value search and allow typing negative bounds"
git push
```

### Task 7: Enter/Escape close the dialog without cleanup

**Files:**
- Modify: `cfb_system_maker/static/filter_modal.js` (dialog close handling, js:1277-1294 and init section)

The form is `method="dialog"` (index.html:494). Enter in the categorical search implicitly submits → dialog closes, draft discarded, `state` stays non-null, in-flight fetch alive, focus dropped at `<body>`. Native Escape closes the same way.

- [ ] **Step 1: Block implicit submission**

Near the other init listeners (js:1523):

```js
  const modalForm = document.getElementById("filter-modal-form");
  if (modalForm) {
    modalForm.addEventListener("submit", (event) => {
      event.preventDefault();
    });
  }
```

- [ ] **Step 2: Centralize cleanup on the dialog's `close` event**

Rework `discardAndClose` so all close paths (Cancel, ✕, Escape) share one cleanup:

```js
  function cleanupAfterClose() {
    abortLiveFetch();
    liveGeneration += 1;
    detailGeneration += 1;
    liveOk = false;
    state = null;
    setViewToggleVisible(false);
    setMaxRoiVisible(false);
    if (exploreEl) {
      exploreEl.innerHTML = "";
    }
    if (statusEl) {
      statusEl.textContent = "";
    }
    if (launcher) {
      launcher.focus();
    }
  }

  function discardAndClose() {
    dialog.close();
  }

  dialog.addEventListener("close", () => {
    if (state) {
      cleanupAfterClose();
    }
  });
```

`saveAndSubmit` (js:1296) navigates via form submit right after `dialog.close()`; set `state = null` **before** `dialog.close()` there so the close handler doesn't refocus the launcher mid-navigation:

```js
    const kind = state.kind;          // existing writes above use state; null it just before close
    state = null;
    dialog.close();
```

(Keep the existing write* calls before this; only the ordering of `state = null` vs `dialog.close()` matters.)

- [ ] **Step 3: Verify in browser**

- Open Team filter, press Escape → modal closes, focus returns to the Team launcher button, reopening works cleanly.
- Open Team filter, type in search, press Enter → modal stays open (no implicit close).
- Save Filter still submits and reloads as before.

- [ ] **Step 4: Commit**

```bash
git add cfb_system_maker/static/filter_modal.js
git commit -m "fix(modal): clean up state on every dialog close and block implicit Enter submission"
git push
```

---

## Phase B — Performance, GUI, a11y

### Task 8: Cache data loading and heavy per-request work

**Files:**
- Modify: `cfb_system_maker/web.py` — routes at :400, :457, :541, :659, :672; helpers near `_FIGURE_CACHE` (:1376) and `_cached_backtest` (:1433); `_feature_options` (:1240ish)
- Test: `tests/test_web.py`

Today every request re-parses the 38 MB `features.json` + 13k-row CSV; `/system` additionally runs ~48 full feature-map scans (`_scan_values`) and a fresh `run_backtest` (1000-iter permutation + 1000-iter bootstrap). `_data_fingerprint` (:1406) is the ready-made invalidation key.

- [ ] **Step 1: Write the failing test (load-count spy)**

```python
def test_processed_data_is_cached_across_requests(client, monkeypatch):
    import cfb_system_maker.web as web
    calls = {"n": 0}
    real = web.load_processed_games
    def counting(data_dir):
        calls["n"] += 1
        return real(data_dir)
    monkeypatch.setattr(web, "load_processed_games", counting)
    web._DATA_CACHE.clear()
    client.get("/system")
    client.get("/system")
    assert calls["n"] == 1
```

- [ ] **Step 2: Run, verify it fails** (no `_DATA_CACHE` yet).

- [ ] **Step 3: Add the fingerprint-keyed loader**

Next to `_FIGURE_CACHE` (web.py:1376):

```python
_DATA_CACHE: dict[tuple, tuple[list[GameRecord], dict[int, dict] | None]] = {}
_FEATURE_OPTIONS_CACHE: dict[tuple, list] = {}


def _load_data_cached(data_dir: Path) -> tuple[list[GameRecord], dict[int, dict] | None]:
    """Games + feature sidecar, memoized on file identity. FileNotFoundError
    still propagates so the missing_data branches keep working."""
    key = _data_fingerprint(data_dir)
    hit = _DATA_CACHE.get(key)
    if hit is None:
        games = load_processed_games(data_dir)
        features = _try_load_features(data_dir)
        _DATA_CACHE.clear()
        _FEATURE_OPTIONS_CACHE.clear()
        _DATA_CACHE[key] = (games, features)
        return games, features
    return hit
```

- [ ] **Step 4: Use it in every route**

In `dashboard`, `index`, `compare`, `api_backtest`, `filter_detail`, replace each

```python
        games = load_processed_games(app.config["DATA_DIR"])
        ...
        feature_map = _try_load_features(app.config["DATA_DIR"])
```

pair with

```python
        games, feature_map = _load_data_cached(app.config["DATA_DIR"])
```

keeping each route's existing `except FileNotFoundError` around the call. (`index` also reads `load_features_meta` — leave that line alone, it's a tiny file.)

- [ ] **Step 5: Cache `_feature_options` on the same key**

Wherever `index()` calls `_feature_options(feature_map)`, go through:

```python
def _feature_options_cached(feature_map: dict[int, dict] | None, data_dir: Path) -> list:
    if feature_map is None:
        return []
    key = _data_fingerprint(data_dir)
    hit = _FEATURE_OPTIONS_CACHE.get(key)
    if hit is None:
        hit = _feature_options(feature_map)
        _FEATURE_OPTIONS_CACHE[key] = hit
    return hit
```

- [ ] **Step 6: Route editor + compare backtests through `_cached_backtest`**

web.py:496 becomes:

```python
        result = _cached_backtest(system, games, feature_map, app.config["DATA_DIR"])
```

and the three `run_backtest(...)` calls in `compare` (web.py:569, 570, 584) likewise. While here, stop `_FIGURE_CACHE` growing across rebuilds — in `_cached_backtest` on a miss, first drop entries from other fingerprints:

```python
    if cached is None:
        stale = [k for k in _FIGURE_CACHE if k[1] != key[1]]
        for k in stale:
            del _FIGURE_CACHE[k]
        cached = run_backtest(games, system, feature_map=feature_map)
        _FIGURE_CACHE[key] = cached
```

- [ ] **Step 7: Full suite + timing proof**

Run: `python -m pytest -q` → green. (Tests that rebuild data files get fresh loads automatically — the fingerprint changes.)

Then with the dev server running:

```bash
curl -s -o /dev/null -w "cold %{time_total}s\n" "http://localhost:5000/system?load_system=total-unders-high-lines" && curl -s -o /dev/null -w "warm %{time_total}s\n" "http://localhost:5000/system?load_system=total-unders-high-lines"
```

Expected: warm request several× faster than cold. Record both numbers in the commit message body.

- [ ] **Step 8: Commit**

```bash
git add cfb_system_maker/web.py tests/test_web.py
git commit -m "perf(web): memoize data loading, feature options, and editor/compare backtests on data fingerprint"
git push
```

### Task 9: `/save` failure silently discards the user's work

**Files:**
- Modify: `cfb_system_maker/web.py:529-539`, `cfb_system_maker/templates/index.html` (near the Save System controls)
- Test: `tests/test_web.py`

- [ ] **Step 1: Failing test**

```python
def test_failed_save_preserves_form_and_reports_error(client):
    resp = client.post("/save", data={"bet_type": "total", "total_side": "under",
                                      "min_total": "55", "save_name": ""})
    assert resp.status_code == 302
    location = resp.headers["Location"]
    assert "min_total=55" in location
    assert "save_error=" in location
```

- [ ] **Step 2: Fix the route**

```python
    @app.post("/save")
    def save():
        form = _form_values_from_post()
        name = str(form.get("save_name", "")).strip()
        args = _query_args_from_form(form)
        if not name:
            args.setlist("save_error", ["missing_name"])
            return redirect("/system?" + urlencode(list(args.items(multi=True))))
        try:
            save_system(name, _system_from_form(form), app.config["DATA_DIR"], theory=form.get("theory", ""))
        except ValueError:
            args.setlist("save_error", ["invalid_name"])
            return redirect("/system?" + urlencode(list(args.items(multi=True))))
        return redirect(url_for("index", **{"load_system": name}))
```

(`urlencode` is already imported for `_query_href_removing`. If `_query_args_from_form` returns a plain dict rather than a MultiDict, adapt with `args["save_error"] = "missing_name"` and `urlencode(args)`.)

- [ ] **Step 3: Surface it in the template**

In `index.html`, directly above the Save System button block, add:

```jinja
{% if request.args.get('save_error') == 'missing_name' %}
<p class="save-error">Enter a name to save this system.</p>
{% elif request.args.get('save_error') == 'invalid_name' %}
<p class="save-error">That name can't be used — letters, numbers, dashes and underscores only.</p>
{% endif %}
```

And in `styles.css`, reuse the existing `.stale-warning` styling pattern:

```css
.save-error {
  color: #b91c1c;
  font-size: 0.85rem;
  margin: 0.25rem 0 0;
}
```

(Match the file's existing color conventions — if there's an error color already in use, use that instead of the literal.)

- [ ] **Step 4: Suite green, then commit**

```bash
git add cfb_system_maker/web.py cfb_system_maker/templates/index.html cfb_system_maker/static/styles.css tests/test_web.py
git commit -m "fix(web): redirect failed saves back with form state and an error message"
git push
```

### Task 10: GUI fixes — labels, formatting, layout

**Files:**
- Modify: `cfb_system_maker/web.py:1715-1720` (fallback label), `_range_chart` (:1296-1299), categorical week sort in `aggregate_filter_value_rows` (~:297)
- Create: `cfb_system_maker/templates/_macros.html`
- Modify: `templates/index.html:322`, `templates/dashboard.html:84`, `templates/compare.html:57`, `templates/search_run.html:28`
- Modify: `cfb_system_maker/static/styles.css` (stat-chips overflow at :287 / the 900px block at :583; lookahead quarantine)
- Test: `tests/test_web.py`

- [ ] **Step 1: Postseason week label**

`data/processed/upcoming_meta.json` carries `season_type: "postseason"` but the label says "Week 1, 2025" for bowl games. Replace web.py:1717-1720:

```python
    if is_fallback:
        season_type = str(meta.get("season_type") or "").strip()
        week_word = f"{season_type.title()} Week" if season_type and season_type != "regular" else "Week"
        fallback_label = (
            f"Most recent week with data: {week_word} {meta.get('week')}, {meta.get('season')}"
        )
```

Test:

```python
def test_fallback_label_names_postseason(...):
    # meta with season_type="postseason", week=1, season=2025 →
    # panel["fallback_label"] == "Most recent week with data: Postseason Week 1, 2025"
```

(Call `_current_matches_panel` directly with a tmp data dir following the existing current-matches test setup in test_web.py.)

- [ ] **Step 2: Shared money macro — kill the triplicated formatting**

Create `cfb_system_maker/templates/_macros.html`:

```jinja
{% macro money(profit) -%}
{%- if profit > 0 -%}+${{ "{:,.0f}".format(profit * 100) }}{%- elif profit < 0 -%}-${{ "{:,.0f}".format(-profit * 100) }}{%- else -%}$0{%- endif -%}
{%- endmacro %}
```

In `index.html:322` and `dashboard.html:84`, add at the top of each file `{% from "_macros.html" import money %}` and replace the inline `{% if ... %}+$...{% endif %}` expression with `{{ money(result.profit) }}` / `{{ money(fig.profit) }}` (keep the surrounding `positive`/`negative` class logic unchanged). In `compare.html:57` replace `{{ "%.4f"|format(row.result.profit) }}` with `{{ money(row.result.profit) }}` so Compare shows dollars like every other page.

- [ ] **Step 3: Wrap the finalist table**

`search_run.html:28` — wrap the `<table class="finalist-table">` in `<div class="table-wrap">…</div>` like every other template's tables, so the global `table { min-width: 860px }` scrolls inside its container instead of the page.

- [ ] **Step 4: Stop the stat-chips mobile overflow**

Verified live: at 420px the page scrolls to 676px, offender `.metrics.stat-chips`. Read the rule at styles.css:287 (a grid with fixed columns) and inside the existing `@media (max-width: 900px)` block at styles.css:583 make the chips wrap:

```css
  .metrics.stat-chips {
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  }
```

Verify with browser devtools/emulation at 420px: `document.documentElement.scrollWidth <= window.innerWidth`.

- [ ] **Step 5: Actually quarantine the lookahead group visually**

Project constraint says result_lookahead features are "visually quarantined", but `.lookahead` and `.lookahead-warning` (index.html:157-161) have **zero** CSS rules. Add to styles.css, matching the palette of the existing `.stale-warning` rule:

```css
.feature-group.lookahead {
  border: 1px solid #b45309;
  background: rgba(180, 83, 9, 0.05);
}
.feature-group.lookahead > legend .lookahead-warning {
  color: #b45309;
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-left: 0.5rem;
}
```

- [ ] **Step 6: Numeric sort for integer categorical value tables**

The Week table in `/filter-detail` sorts 1, 10, 11, …, 2 (lexicographic `key=str` around web.py:297). Where categorical rows are sorted, use a numeric-first key:

```python
def _categorical_sort_key(value: object) -> tuple:
    try:
        return (0, float(value))  # ints/floats and numeric strings sort numerically
    except (TypeError, ValueError):
        return (1, str(value))
```

and sort with `rows.sort(key=lambda row: _categorical_sort_key(row["value"]))`. Add a test asserting `/filter-detail?candidate_id=core:week` returns rows in numeric order (follow the existing filter-detail tests in `tests/test_filter_modal.py`).

- [ ] **Step 7: Keep the last bucket in `_range_chart` downsampling**

web.py:1297-1299 — stride sampling can drop the right edge, unlike `downsample_chart_points` which deliberately keeps extremes:

```python
    if len(items) > 18:
        step = max(1, len(items) // 18)
        sampled = items[::step]
        if sampled[-1] != items[-1]:
            sampled.append(items[-1])
        items = sampled
```

- [ ] **Step 8: Modal open flash**

In `openCandidate` after `renderChips({ wins: 0, ... })` (filter_modal.js:1425), suppress the misleading empty-state flash:

```js
    renderChips({ wins: 0, losses: 0, pushes: 0, money_won: 0, roi: 0 });
    emptyEl.hidden = true;   // don't show "No bets match" before the first live result
```

- [ ] **Step 9: Suite + browser sweep, then commit**

`python -m pytest -q` green; browser check of `/`, `/system`, `/compare?system=total-unders-high-lines` at desktop and 420px.

```bash
git add cfb_system_maker/web.py cfb_system_maker/templates cfb_system_maker/static tests
git commit -m "fix(ui): postseason week label, shared money macro, mobile overflow, lookahead quarantine, numeric week sort"
git push
```

### Task 11: Accessibility touch-ups

**Files:**
- Modify: `cfb_system_maker/static/filter_modal.js:824-838`, `templates/index.html:291`

- [ ] **Step 1: Name the value-table pick inputs**

Where each row's checkbox/radio is created (filter_modal.js:824-838), give it the row's description:

```js
      input.setAttribute("aria-label", String(row.description ?? row.value));
```

(Adapt the variable names to the actual row-building code — the input element and the row object are both in scope there.)

- [ ] **Step 2: Name the load-system select**

index.html:291 — add `aria-label="Load saved system"` to `<select class="load-system-select" ...>`.

- [ ] **Step 3: Verify + commit**

Browser: in the Team modal, inspect a row input and confirm the accessible name is the team name.

```bash
git add cfb_system_maker/static/filter_modal.js cfb_system_maker/templates/index.html
git commit -m "fix(a11y): accessible names for value-table inputs and load-system select"
git push
```

### Task 12: Same-origin check on POST routes

**Files:**
- Modify: `cfb_system_maker/web.py` (inside `create_app`, before the routes)
- Test: `tests/test_web.py`

Localhost tool, but any web page can form-POST to `127.0.0.1:5000` and overwrite saved systems or fire the narration LLM call. An Origin check is the cheap fix; browsers send `Origin` on all cross-origin POSTs, and same-origin form posts either match or omit it.

- [ ] **Step 1: Failing test**

```python
def test_cross_origin_post_is_rejected(client):
    resp = client.post("/save", data={"save_name": "x"},
                       headers={"Origin": "http://evil.example"})
    assert resp.status_code == 403


def test_same_origin_and_no_origin_posts_still_work(client):
    assert client.post("/copy-example", data={"name": "nope"}).status_code == 302
    assert client.post("/copy-example", data={"name": "nope"},
                       headers={"Origin": "http://localhost"}).status_code == 302
```

(The test client's host is `localhost`; if the second assertion's Origin host doesn't match `request.host` in the test environment, use `f"http://{...}"` built from the response of a prior request, or compare netloc only as the implementation does.)

- [ ] **Step 2: Implement**

```python
    @app.before_request
    def _reject_cross_origin_posts():
        if request.method != "POST":
            return None
        origin = request.headers.get("Origin")
        if not origin:
            return None
        if urlparse(origin).netloc != request.host:
            abort(403)
        return None
```

Add `from urllib.parse import urlparse` to the existing urllib imports.

- [ ] **Step 3: Suite green, commit**

```bash
git add cfb_system_maker/web.py tests/test_web.py
git commit -m "fix(security): reject cross-origin POSTs with an Origin/host check"
git push
```

---

## Phase C — Dead code and duplication (delete only with proof)

### Task 13: Remove verified dead code

**Files:**
- Modify: `cfb_system_maker/web.py`, `templates/index.html`, `static/styles.css`

Every deletion below was flagged by review; **re-verify each with grep before deleting** — if any grep finds a live reference, skip that item and note it in the commit message.

- [ ] **Step 1: Dead Python** — `grep -rn "_active_filter\|_feature_filters_from_request" cfb_system_maker tests` → only the definitions (web.py:1087, :1127) → delete both functions.
- [ ] **Step 2: Dead template vars** — `grep -rn "result_dict\|season_filter" cfb_system_maker/templates` → if no template references them, remove `result_dict=asdict(result)` (web.py:517) and both `season_filter=...` kwargs (web.py:473, :525). If `asdict` then has no other web.py use, drop it from the import.
- [ ] **Step 3: Dead inline script** — `grep -rn "data-initial" cfb_system_maker` → only index.html:537-543 → delete that `<script>` block.
- [ ] **Step 4: Dead attributes** — `grep -n "data-min\|data-max" cfb_system_maker/static/filter_modal.js` → no reads → remove `data-min`/`data-max` from the Edit buttons in index.html (~:352).
- [ ] **Step 5: Orphan CSS** — `grep -rn "filter-modal__season-list" cfb_system_maker` → only styles.css:884-888 → delete the block.
- [ ] **Step 6: Suite + browser smoke** — `python -m pytest -q` green; load `/system?load_system=total-unders-high-lines`, open one modal, run one backtest.
- [ ] **Step 7: Commit**

```bash
git add -A cfb_system_maker
git commit -m "chore(web): remove dead helpers, template vars, inline script, and orphan CSS"
git push
```

### Task 14 (OPTIONAL — separate session recommended): Module splits

Do **not** start this in the same session as Tasks 1-13; it's a mechanical relocation with zero behavior change, gated purely on the suite staying green. Skip entirely if the user hasn't asked for it after Phase A/B land.

**web.py (1,729 lines) → four modules**, in dependency order:
1. `cfb_system_maker/web_forms.py` — `StrictParseError`, `parse_system_strict`, all `_validate_*`, `_form_*`, `_query_*`, `_system_from_form`, `_int_set`, `_str_set`, `_optional_float`, `_parse_filter_value` (web.py ~385-393, 862-1213).
2. `cfb_system_maker/filter_domain.py` — `filter_descriptor`, `remove_candidate_filters`, `resolve_candidate_value`, `aggregate_filter_value_rows`, `serialize_numeric_draft`, `edit_metadata_for_sentence`, `CORE_FILTER_META` (~52-382, 747-826). `tests/test_filter_modal.py` already tests these standalone — update its imports.
3. `cfb_system_maker/web_charts.py` — `_range_chart`, `_cumulative_chart`, `_sparkline`, `downsample_chart_points`, plus ONE shared `_scale_points(values, width, height, pad_x, pad_y)` helper replacing the four hand-rolled copies of the same value→SVG scaling.
4. `cfb_system_maker/web_dashboard.py` — `_dashboard_row`, `_timeframe_figures`, `_current_matches_panel`, kickoff formatting (~1364-1729).

Also fold the two duplicated helpers: `aggregate_filter_value_rows` should call `run_backtest_summary`'s aggregation (backtest.py:27-44) instead of re-implementing W/L/P/profit/ROI, and `_fmt_number` should import `describe._fmt_num`.

Per module: move code, re-export from `web.py` (`from .web_forms import ...`) so external imports and tests keep working, run `python -m pytest -q`, commit (`refactor(web): extract <module>`), push. Four commits.

**filter_modal.js (1,561 lines)**: only split if the user asks — the file has no build step, so a split means multiple `<script>` tags or IIFE concatenation. The review's seams, for when that day comes: form-io / query / live / detail / value-table / numeric / modal-orchestration + shared formatters.

---

## Deferred (explicitly out of scope — do not do without being asked)

- Feature-fallback half-open bounds in `writeNumericToForm` (Task 2 fixed core ranges only).
- `aria-live` chattiness of "Updating…" (cosmetic; revisit with a screen-reader pass).
- Dual-slider both-thumbs-at-min z-index trap (recoverable; needs a pointer-proximity heuristic).
- "2023-2023" single-season header range in index.html:16.
- Dark mode (app has a single deliberate light palette).
- `_current_matches_panel` per-loop `describe()` memoization (50-row panel; negligible today).

## Success Criteria

1. `python -m pytest -q` green after every task (409 baseline + new tests, 0 failures).
2. Live checks pass: `curl` returns 200 for `/system?min_spread=abc` and `/compare?holdout_season=abc`; Edit→Save on `total-unders-high-lines` leaves `min_total=55`; two-season system round-trips through Run System; warm `/system` load measurably faster than cold; no horizontal page scroll at 420px.
3. No behavior change outside the listed findings — diffs trace 1:1 to tasks.
