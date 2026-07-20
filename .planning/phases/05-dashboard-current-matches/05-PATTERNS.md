# Phase 5: Dashboard & Current Matches - Pattern Map

**Mapped:** 2026-07-20
**Files analyzed:** 14 (7 new, 7 modified)
**Analogs found:** 14 / 14

> Taxonomy note: this is a Python/Flask/vanilla-JS project. Roles are mapped to what
> actually exists here — CLI-command, pipeline, storage, route, template, test — not
> the generic controller/component/service vocabulary.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `cfb_system_maker/upcoming.py` (new — fetch + current-week detect) | pipeline / client | file-I/O + request-response | `scrapers.scrape` (injectable `cfbd_module`) + `cfbd_client.fetch_games_and_lines` | exact (composite) |
| `cfb_system_maker/templates/dashboard.html` (new) | template | request-response | `templates/index.html`, `templates/compare.html` | exact |
| `cfb_system_maker/examples/*.json` (new, 3 files) | data fixture | file-I/O | `storage._system_to_dict` output shape | exact |
| examples loader (new fn, in `storage.py`) | storage | file-I/O | `storage.list_systems` + `load_saved_system` | exact |
| `_sparkline(...)` (new fn, in `web.py`) | utility | transform | `web._cumulative_chart` (web.py:1190-1225) | exact |
| upcoming writer/reader (new fns, `storage.py`) | storage | file-I/O | `storage.save_processed_games` / `load_processed_games` / `save_raw_json` | role-match (new schema) |
| upcoming features sidecar (new fn, `enrich.py`) | pipeline | transform | `enrich.enrich_games` + `save_features` | role-match (must NOT reuse fixed path) |
| **MOD** `cfb_system_maker/backtest.py` | domain | transform | itself — guard at 246-247 | n/a (surgical edit) |
| **MOD** `cfb_system_maker/web.py` | route | request-response | its own `index` / `compare` / `save` handlers | exact |
| **MOD** `cfb_system_maker/cli.py` | CLI-command | batch | `_fetch` / `_build` / `_enrich` + `_build_parser` | exact |
| **MOD** `cfb_system_maker/static/styles.css` | config/style | n/a | `.tabs`, `.positive/.negative`, `.stale-warning`, `.empty-state`, `.cumulative-chart` | exact |
| **MOD** `tests/test_web.py` | test | request-response | its own `create_app(data_dir=tmp_path)` pattern | exact |
| **MOD** `tests/test_cli.py` | test | batch | `test_sample_command_...` | exact |
| **NEW** upcoming/running-stats tests | test | transform | `tests/test_scrapers.py` fake-module classes | exact |

**Kickoff caveat:** `normalize_games` emits `GameRecord`, which has **no kickoff field** (see
`_row_to_game`, `storage.py:59-73` — 12 columns, no date). So "reuse `normalize_games`" gets you
the matchable fields only; the raw `startDate` is dropped. Capture kickoff separately from the
raw games payload and join it back by `game_id` when writing the upcoming file. This is the one
place where "reuse unchanged" and "the upcoming file carries kickoff" must both be honored.

**Reuse unchanged — do not reimplement:** `normalize.normalize_games`, `normalize._select_line`
(verified to work on future-game payloads; `_select_line` returning `None` already implements
D-04 line exclusion), `running_stats.compute_running_stats` (entering-game by construction),
`describe.describe`, `backtest.run_backtest`.

---

## Pattern Assignments

### `cfb_system_maker/upcoming.py` (pipeline, fetch → disk)

**Analogs:** `scrapers.scrape` (injectability), `cfbd_client.fetch_games_and_lines` (client construction).

RESEARCH §6 is explicit: **do not refactor `fetch_games_and_lines`** — it constructs its own
client and is not testable. Write the new fetch with the `scrapers.py` injection seam instead.

**Injectable-client signature pattern** (`scrapers.py`, `def scrape`):
```python
def scrape(
    seasons: list[int],
    *,
    data_dir: str | Path = "data",
    season_type: str = "regular",
    token: str | None = None,
    cfbd_module: Any = None,
) -> list[ScrapeReport]:
    """Run every applicable endpoint. ``cfbd_module`` is injectable for tests."""
    cfbd = cfbd_module or _load_cfbd_module()
    configuration = cfbd.Configuration(access_token=token or find_cfbd_token())
```

**Client + API construction pattern** (`cfbd_client.py:16-31`):
```python
    cfbd = _load_cfbd_module()
    access_token = token or find_cfbd_token()
    configuration = cfbd.Configuration(access_token=access_token)

    with cfbd.ApiClient(configuration) as api_client:
        games_api = cfbd.GamesApi(api_client)
        betting_api = cfbd.BettingApi(api_client)
        for season in seasons:
            games = games_api.get_games(year=season, season_type=season_type)
            lines = betting_api.get_lines(year=season, season_type=season_type, provider=provider)
            results[season] = {
                "games": [_to_dict(game) for game in games],
                "lines": [_to_dict(line) for line in lines],
            }
```
Reuse `cfbd_client._to_dict` and `find_cfbd_token` by import — do not copy them.
Add the third call `games_api.get_calendar(year)` for current-week detection (RESEARCH §4).

**Datetime serialization** — `startDate` survives `_to_dict` as a `datetime` object.
`storage.save_raw_json` already handles it (`storage.py:25`):
```python
    path.write_text(json.dumps(rows, default=str, indent=2, sort_keys=True), encoding="utf-8")
```
Any new writer must pass `default=str` or `json.dumps` raises `TypeError`.

---

### `cfb_system_maker/cli.py` (CLI-command, batch)

**Analog:** `_fetch` / `_build` / `_enrich` handlers + `_build_parser`.

**Dispatch** (`cli.py:23-38`) — add one line in `main`:
```python
    if args.command == "fetch":
        return _fetch(args)
    if args.command == "build":
        return _build(args)
    if args.command == "enrich":
        return _enrich(args)
```

**Handler shape — thinnest analog is `_enrich`** (`cli.py:76-79`):
```python
def _enrich(args: argparse.Namespace) -> int:
    path = run_enrich(args.data_dir)
    print(f"Wrote enriched features to {path}")
    return 0
```

**Fetch-then-persist shape** (`cli.py:56-62`) — the closer analog for `upcoming`:
```python
def _fetch(args: argparse.Namespace) -> int:
    data = fetch_games_and_lines(args.seasons, season_type=args.season_type, provider=args.provider)
    for season, payload in data.items():
        save_raw_json(args.data_dir, "games", season, payload["games"])
        save_raw_json(args.data_dir, "lines", season, payload["lines"])
    print(f"Fetched {len(data)} season(s).")
    return 0
```

**Subparser registration** (`cli.py:262-263`):
```python
    enrich = subparsers.add_parser("enrich")
    enrich.add_argument("--data-dir", default="data")
```
`__main__.py` is `from cfb_system_maker.cli import main` / `raise SystemExit(main())` —
**no change needed** there (verified by reading it).

---

### `cfb_system_maker/backtest.py` (domain — the blocking surgical edit)

**Current text, `backtest.py:241-251`** — this is the exact block to modify:
```python
def matches_system(
    game: GameRecord,
    system: SystemFilter,
    feature_map: dict[int, dict[str, Any]] | None = None,
) -> bool:
    if game.home_points is None or game.away_points is None:
        return False
    if system.bet_type == "spread" and game.spread is None:
        return False
```

Add `require_played: bool = True` as a keyword param and gate lines 246-247 on it.
Default preserves every existing call site (`run_backtest`, `run_backtest_summary`,
`_feature_coverage`, `aggregate_filter_value_rows`).

**Verified safe:** nothing after the guard reads `home_points`/`away_points`. The rest of the
function (246-301) reads only `spread`, `total`, `season`, `week`, `provider`, teams,
conferences, and the feature map. Confirmed by reading the full body.

**Acceptance bar:** every existing figure and test must be byte-identical after the change.

**Spread-sign convention to reuse for D-08 play text** (`backtest.py:263`):
```python
    side_spread = _side_spread(game.spread, side) if game.spread is not None else None
```
`GameRecord.spread` is always the **home** spread — `_side_spread` negates for away. Use it
for "Play Georgia -7" rather than re-deriving the sign.

**D-08 caveat — `fade` inverts the play.** `side`/`total_side` alone are NOT sufficient to
derive play text: a fade system that *matches* a home favorite is a bet **against** it. The
direction of truth is `grade_bet` (`backtest.py:349-351`), which normalizes before anything else:
```python
    normalized_side = system.side.lower()
    if system.fade:
        normalized_side = "away" if normalized_side == "home" else "home"
```
`_grade_total_bet` applies the equivalent over/under inversion. Play text must run the same
normalization, or a fade system will display the opposite of what would be graded — exactly the
disagreement D-08 exists to prevent.

---

### `cfb_system_maker/web.py` (routes + sparkline utility)

**Route registration pattern** (`web.py:375-381`) — decorators inside the factory closure,
helpers close over `app.config["DATA_DIR"]`:
```python
def create_app(data_dir: str | Path = "data") -> Flask:
    app = Flask(__name__)
    app.config["DATA_DIR"] = Path(data_dir)
    app.jinja_env.globals["query_href"] = _query_href

    @app.get("/")
    def index():
```

**Missing-data degradation pattern** (`web.py:382-398`) — copy this for both the historical
and the missing-upcoming-file states:
```python
        try:
            games = load_processed_games(app.config["DATA_DIR"])
        except FileNotFoundError:
            return render_template(
                "index.html",
                error="missing_data",
                ...
            )
```

**Tab normalization pattern** (`web.py:421`) — unknown value falls back to the default.
Mirror this for `?tab=mine|examples` and `?timeframe=`:
```python
        tab = "matches" if request.args.get("tab") == "matches" else "graph"
```
Note the collision: the editor already owns `?tab=graph|matches`. Per RESEARCH Pitfall 3b, the
`/` → `/system` redirect trigger must be "any *editor filter* param present", **not** "a `tab`
param is present".

**`describe()` decoration — dashboard must NOT copy this** (`web.py:423-426`):
```python
        sentences = describe(system)
        for row in sentences:
            row["remove_href"] = _query_href_removing(str(row["key"]), base_query)
            row["edit"] = edit_metadata_for_sentence(system, row)
```
`_query_href_removing` reads `request.args` and assumes editor query state. The dashboard calls
`describe(system)` raw and renders `row["text"]` only.

**The three `url_for("index")` call sites to repoint** (`web.py:452-462`) — exact current text:
```python
    @app.post("/save")
    def save():
        form = _form_values_from_post()
        name = str(form.get("save_name", "")).strip()
        if not name:
            return redirect(url_for("index"))
        try:
            save_system(name, _system_from_form(form), app.config["DATA_DIR"], theory=form.get("theory", ""))
        except ValueError:
            return redirect(url_for("index"))
        return redirect(url_for("index", **{"load_system": name}))
```
All three must target the relocated editor endpoint, or saving dumps the user on the dashboard.

**Sparkline analog — `_cumulative_chart` (`web.py:1190-1216`).** Write a *sibling* helper; do
not parameterize this one (simplicity + don't disturb the editor chart):
```python
def _cumulative_chart(result: BacktestResult) -> dict[str, object]:
    if not result.bet_details:
        return {"points": [], "polyline": "", "zero_y": 75, "min_x": None, "max_x": None}

    ordered = sorted(result.bet_details, key=lambda bet: (bet.season, bet.week, bet.game_id))

    width = 520
    height = 150
    pad_x = 28
    pad_y = 18

    running = 0.0
    running_values = []
    for bet in ordered:
        running = round(running + bet.profit, 4)
        running_values.append(running)

    values = running_values + [0]
    min_profit = min(values)
    max_profit = max(values)
    span = max_profit - min_profit or 1

    points = []
    for index, profit in enumerate(running_values):
        x = pad_x if len(ordered) == 1 else pad_x + (width - pad_x * 2) * index / (len(ordered) - 1)
        y = height - pad_y - ((profit - min_profit) / span) * (height - pad_y * 2)
        points.append(...)
```
Sparkline differences per UI-SPEC: box 96×24, no pad/zero-line/points, 48-point downsample cap,
`polyline` string only, `—` when `bet_details` is empty.

**Per-season derivation (Pitfall 4):** one all-time `run_backtest` per system, then filter
`result.bet_details` on `bet.season`; `result.season_breakdown` already carries per-season
bets/wins/losses/pushes/profit/roi from the same path.

---

### `cfb_system_maker/storage.py` (upcoming file + examples loader)

**Processed-file writer/reader pair** (`storage.py:41-56`) — the shape to mirror for
`upcoming.csv` (with its own field list, since it is *not* bound by the `GameRecord` contract
and must carry kickoff):
```python
def save_processed_games(data_dir: str | Path, games: list[GameRecord]) -> Path:
    path = Path(data_dir) / "processed" / "games.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [field.name for field in fields(GameRecord)]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for game in games:
            writer.writerow(asdict(game))
    return path
```

**Blank-to-None CSV parse convention** (`storage.py:76-85`) — required for the null score
columns on unplayed rows:
```python
def _none_if_blank(value: str) -> str | None:
    return value if value != "" else None

def _optional_int(value: str) -> int | None:
    return int(value) if value != "" else None
```

**Examples enumerator analog** (`storage.py:109-125`) — same shape, but rooted at
`Path(__file__).parent / "examples"` instead of `data_dir`:
```python
def load_saved_system(name: str, data_dir: str | Path) -> SavedSystem:
    name = _safe_system_name(name)
    path = Path(data_dir) / "systems" / f"{name}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return SavedSystem(
        name=str(payload.get("name", name)),
        saved_at=str(payload.get("saved_at", "")),
        system=_system_from_dict(payload),
        theory=str(payload.get("theory", "")),
    )


def list_systems(data_dir: str | Path) -> list[str]:
    systems_dir = Path(data_dir) / "systems"
    if not systems_dir.exists():
        return []
    return sorted(path.stem for path in systems_dir.glob("*.json"))
```
Reuse `_safe_system_name` and `_system_from_dict` — do **not** write a parallel parser.
Note `list_systems` sorts alphabetically; UI-SPEC wants `saved_at` descending, so the dashboard
loads each and re-sorts.

---

### `cfb_system_maker/examples/*.json` (data fixture)

**Contract 1 — filename stem** (`storage.py:13`):
```python
_SYSTEM_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
```
`home-favorites`, not `Home Favorites`. Enforced on any path through the loader or
"Copy to My Systems".

**Contract 2 — JSON shape, `_system_to_dict` (`storage.py:128-162`):**
```python
    return {
        "name": saved.name,
        "saved_at": saved.saved_at,
        "theory": saved.theory,
        "system": {
            "bet_type": system.bet_type,
            "side": system.side,
            "total_side": system.total_side,
            "seasons": sorted(system.seasons),
            "weeks": sorted(system.weeks),
            "teams": sorted(system.teams),
            "conferences": sorted(system.conferences),
            "favorite": system.favorite,
            "underdog": system.underdog,
            "home": system.home,
            "away": system.away,
            "fade": system.fade,
            "providers": sorted(system.providers),
            "min_spread": system.min_spread,
            "max_spread": system.max_spread,
            "min_total": system.min_total,
            "max_total": system.max_total,
            "feature_filters": [ {"key":…, "op":…, "value":…, "perspective":…} ],
        },
    }
```
`_system_from_dict` defaults every field, so a partial file loads — write full files anyway so
they diff cleanly against saved systems.

**Content constraints (RESEARCH §Choosing the D-16 example filters):** no `providers` filter
(`consensus` is gone from recent data; upcoming rows carry DraftKings/Bovada), no weather
feature, and prefer a matchup/line feature over a season-to-date stat.

---

### `cfb_system_maker/enrich.py` (upcoming features sidecar)

**Analog:** `enrich_games` (`enrich.py:14-25`) already accepts an explicit games list:
```python
def enrich_games(data_dir: str | Path, games: list[GameRecord] | None = None) -> dict[str, dict[str, Any]]:
    data_dir = Path(data_dir)
    games = games or load_processed_games(data_dir)
    indexes = _build_indexes(data_dir, games)

    output: dict[str, dict[str, Any]] = {}
    for game in games:
        row: dict[str, Any] = {}
        for feature in FEATURE_REGISTRY:
            _apply_feature(row, feature, game, indexes)
        output[str(game.game_id)] = row
    return output
```

**Pitfall 6 — `save_features` writes a FIXED path** (`enrich.py:28-33`). Reusing it would
clobber the historical sidecar:
```python
def save_features(data_dir: str | Path, features: dict[str, dict[str, Any]]) -> Path:
    path = Path(data_dir) / "processed" / "features.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"_meta": _build_meta(features), "games": features}
```
Write a sibling taking an explicit output path; keep the `{"_meta": …, "games": …}` envelope so
`load_features`' reader (`enrich.py:44-47`) works unchanged.

**Entering-game guarantee to preserve** (`running_stats.py:43-61`) — the snapshot is written
*before* accumulation, and null scores `continue` early, so unplayed games take priors and
contribute nothing:
```python
        for _sort_key, game_id, game, side in entries:
            stats[(game_id, team)] = { "games_played": played, "win_pct": …, … }

            team_points = game.home_points if side == "home" else game.away_points
            opponent_points = game.away_points if side == "home" else game.home_points
            if team_points is None or opponent_points is None:
                continue
```
Hard prerequisite (Pitfall 2): pass **completed ∪ upcoming** for the season, with
`start_dates` populated from raw `startDate`, or every rate comes back `None`.

---

### `cfb_system_maker/templates/dashboard.html` (template)

**Analog:** `index.html` (tabs, chart SVG, table-wrap, empty-state, stale-warning all present).

- Tab strip: `index.html:365` `<nav class="tabs">` + `.tabs a[aria-current]` (`styles.css:342-364`)
- SVG polyline idiom: `index.html:429-433`
  ```jinja
  <section class="cumulative-chart" aria-label="Money Won Over Time">
    ...
      {% if cumulative_chart.polyline %}<polyline points="{{ cumulative_chart.polyline }}" />{% endif %}
  ```
- Amber notice: `index.html:152` `<p class="stale-warning">…<code>python -m cfb_system_maker enrich --data-dir data</code>…</p>` — exact precedent for the offseason banner *and* the missing-upcoming-file copy naming the CLI command.
- Empty state: `index.html:304` `<div class="empty-state">` (`styles.css:502-508`)
- Overflow: `.table-wrap` (`styles.css:438`)
- Signed values: `.positive` / `.negative` (`styles.css:468-475`)

No new hex values, no JS. `filter_modal.js` is editor-only and must not be loaded by `/`.

---

### Tests

**Flask-client pattern** (`tests/test_web.py:115-126`) — the template for every dashboard route test:
```python
def test_web_index_loads_filters_and_default_results(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    app = create_app(data_dir=tmp_path)

    response = app.test_client().get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
```

**Money/record formatting helpers already exist** (`tests/test_web.py:50-59`) — reuse
`_money_won_text` rather than re-deriving the `profit * 100` convention.

**Fake-CFBD-module pattern** (`tests/test_scrapers.py:10-44`) — the analog for network-free
upcoming-fetch tests. Add a `get_calendar` and `completed=False` rows to this shape:
```python
class _Config:
    def __init__(self, access_token=None):
        self.access_token = access_token


class _Client:
    def __init__(self, configuration):
        self.configuration = configuration
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        return False


class _GamesApi:
    def __init__(self, client):
        self.calls = []
    def get_games(self, year=None, week=None, season_type=None, ...):
        return [{"id": 400 + year, "season": year, "week": 1, ...}]
```

**CLI smoke test pattern** (`tests/test_cli.py:4-14`):
```python
def test_sample_command_prints_metrics_and_writes_cache(tmp_path, capsys):
    exit_code = main(["sample", "--data-dir", str(tmp_path)])

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert (tmp_path / "processed" / "games.csv").exists()
```

**Pre-work (RESEARCH Wave 0):** 18 `get("/")` call sites across `tests/` must be split between
`/system` and `follow_redirects=True` **before** the route move lands.

---

## Shared Patterns

### Injectable client for network-free tests
**Source:** `scrapers.py` `def scrape(..., cfbd_module: Any = None)`; `graphql_client` `post_fn`
**Apply to:** the new upcoming fetch, and its tests
```python
    cfbd = cfbd_module or _load_cfbd_module()
```
Do **not** follow `fetch_games_and_lines`, which is non-injectable, and do not refactor it.

### Datetime-safe JSON dumps
**Source:** `storage.py:25,37`
**Apply to:** every writer touching a CFBD `startDate`
```python
    json.dumps(rows, default=str, indent=2, sort_keys=True)
```

### Path-traversal gate on any system name
**Source:** `storage.py:13-19`
**Apply to:** examples loader and "Copy to My Systems"
```python
_SYSTEM_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")

def _safe_system_name(name: str) -> str:
    if not _SYSTEM_NAME_RE.match(name):
        raise ValueError(f"invalid system name: {name!r}")
    return name
```

### Null fails closed
**Source:** `backtest.matches_system` (returns `False` on any null it filters on);
`features.feature_ok` returns `False` for `None`
**Apply to:** all upcoming-game feature handling. Missing data means *no match*, never a loose
match — and is the reason D-04 needs no new code (`_select_line` already drops line-less games).

### Missing-file degradation, never a crash
**Source:** `web.py:382-398` (`except FileNotFoundError` → `error="missing_data"`);
`web._try_load_features`
**Apply to:** missing/unparseable upcoming file and missing upcoming-features sidecar

### Jinja autoescape — never `|safe`
**Source:** existing `test_web_theory_is_escaped_and_never_rendered_via_safe_filter`
**Apply to:** system names, `theory`, and `describe()` sentences on the dashboard

### Execution constraint — pydantic v1 venv
**Source:** RESEARCH §Environment Availability
**Apply to:** any command or test importing `cfbd`
```
.venv/Scripts/python.exe -m pytest
```
Bare system `python` (3.14, pydantic 2.13.4) fails with `PydanticUserError: const is removed`.

## No Analog Found

None. Every new surface in this phase has a close in-repo analog — consistent with RESEARCH's
conclusion that the phase is wiring plus one surgical guard change, not new algorithms.

## Metadata

**Analog search scope:** `cfb_system_maker/`, `cfb_system_maker/templates/`,
`cfb_system_maker/static/`, `tests/`
**Files scanned:** 16 (11 read in full, 5 targeted ranges)
**Pattern extraction date:** 2026-07-20
