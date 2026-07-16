# Web App Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the web backtester with an as-of-week running stats layer (running W-L / ATS / PPA with zero lookahead), new pregame/metadata registry fields (venue, conference classification, wind direction, pregame win prob), sidecar `_meta` + stale-registry warning, filter coverage %, win/loss streaks in `SystemStats`, and a compare-saved-systems view.

**Architecture:** Everything rides the existing generic feature layer. Running stats are computed in a new pure module (`running_stats.py`) from `games.csv` + raw per-game PPA files, injected into `enrich` as a new `computed_running` source kind, and exposed as ordinary team-scoped registry features in a new `season_to_date` group — so matching, perspectives, save/load, and the web UI need zero new filter code. New static fields are plain registry rows + enrich indexes. The compare view is a second Flask route that reruns `run_backtest` per saved system.

**Tech Stack:** Python 3.11+ stdlib only, Flask (already a dependency), pytest (already a dependency). No new dependencies.

## Global Constraints

- **No new dependencies.** Pure stdlib for all computation (`math`, `json`, `hashlib`, `dataclasses`).
- **Never edit `cfbd-python/`** — vendored upstream client, not our code.
- **`GameRecord` and the `games.csv` schema are frozen.** All enriched values ride the `data/processed/features.json` sidecar. Do not touch `storage.py` CSV read/write.
- **Spread sign convention:** `GameRecord.spread` is always the **home** spread. Away side negates it. A team covers when `team_points + side_spread - opponent_points > 0`.
- **No lookahead:** every `season_to_date` value for a game must be computed from that team's games **strictly before** that game, same season. A team's first game of a season has `games_played = 0` and `None` for every percentage/average.
- **Nulls fail closed:** a `None` feature value never satisfies a filter (existing `feature_ok` behavior — preserve it).
- **YAGNI cuts stay cut:** no `--incremental` enrich, no tags, no duplicate_system, no min/max odds stats, no avg/sum perspectives, no `between` op, no hypothesis dep, no Kelly, no CLV.
- **TDD, frequent commits.** Run `python -m pytest` (all tests green) before every commit. Run from repo root `C:\Users\mckel\dev\cfb-site`.
- Match existing style: frozen dataclasses, `from __future__ import annotations`, module-level private helpers prefixed `_`, no comments except non-obvious constraints.

## Context primer (read once)

Pipeline: `fetch` → raw JSON in `data/raw/` → `build` → `data/processed/games.csv` → `enrich` → `data/processed/features.json` → `backtest` / `web`. The feature registry (`cfb_system_maker/features.py`, `FEATURE_REGISTRY` of `FeatureDef`) is the single source of truth: `enrich.py` resolves each registry entry per game into the sidecar (`{game_id_str: {key: value}}`; team-scoped keys stored as `home_<key>` / `away_<key>`), `backtest.matches_system` applies `SystemFilter.feature_filters` via `features.feature_ok`, and `web.py` renders filter rows grouped by `FeatureDef.group` (the Jinja template auto-titles group names: `season_to_date` → "Season To Date"; only the group **ordering tuple** in `web._feature_options` needs updating for a new group).

Verified raw file shapes (real files in `data/raw/`):

- `games_{season}.json` rows: `id`, `startDate` ("2023-08-26 18:30:00+00:00" — ISO-ish, lexicographically sortable), `seasonType`, `week`, `venueId`, `homeClassification`, `completed`, …
- `ppa_games_{season}.json` rows: `gameId`, `team`, `opponent`, `offense: {overall, …}`, `defense: {overall, …}`
- `pregame_win_prob_{season}.json` rows: `gameId`, `homeWinProbability`, `spread`
- `venues.json` (single file, no season suffix) rows: `id`, `capacity`, `dome`, `grass`, `elevation` (often null)
- `conferences.json` (single file) rows: `name` (matches `GameRecord.home_conference` strings), `classification` ("fbs"/"fcs"/"ii"/…), `shortName`
- `weather_{season}.json` rows include `windDirection` (degrees) — already indexed by enrich as `raw_weather`

Known pre-existing dead code (do **not** remove — out of scope): `features.resolve_storage_key` is defined but never called.

## File structure

| File | Action | Responsibility |
|---|---|---|
| `cfb_system_maker/running_stats.py` | Create | Pure as-of-game running stat computation (no I/O) |
| `tests/test_running_stats.py` | Create | Running stats correctness incl. no-lookahead invariant |
| `cfb_system_maker/features.py` | Modify | New group/source kinds, 12 new `FeatureDef` rows, `registry_version()` |
| `cfb_system_maker/enrich.py` | Modify | New indexes (running, venues, conferences, pregame wp), `_meta` in sidecar |
| `cfb_system_maker/models.py` | Modify | `SystemStats` gains streak fields (defaulted) |
| `cfb_system_maker/backtest.py` | Modify | Streak computation in `compute_system_stats` |
| `cfb_system_maker/web.py` | Modify | Group ordering, stale-registry flag, coverage %, `/compare` route |
| `cfb_system_maker/templates/index.html` | Modify | Stale banner, coverage panel, streaks stat, compare link |
| `cfb_system_maker/templates/compare.html` | Create | Compare-systems page |
| `cfb_system_maker/static/styles.css` | Modify | Append compare/coverage/stale styles |
| `cfb_system_maker/cli.py` | Modify | Streak lines in `print_result` |
| `tests/test_features.py`, `tests/test_enrich.py`, `tests/test_backtest.py`, `tests/test_web_features.py` | Modify | New cases following existing patterns |
| `tests/test_web_compare.py` | Create | Compare view tests |
| `CLAUDE.md`, `docs/superpowers/specs/2026-06-13-web-feature-filters-design.md` | Modify | Document new layer, mark phase-2 items delivered |

---

### Task 1: Running W-L / ATS core (`running_stats.py`)

**Files:**
- Create: `cfb_system_maker/running_stats.py`
- Test: `tests/test_running_stats.py`

**Interfaces:**
- Consumes: `cfb_system_maker.models.GameRecord` (existing frozen dataclass).
- Produces: `compute_running_stats(games: list[GameRecord], *, start_dates: dict[int, str] | None = None) -> dict[tuple[int, str], dict[str, Any]]`. Key is `(game_id, team)`. Value dict keys after this task: `"games_played"` (int), `"win_pct"` (float|None), `"ats_pct"` (float|None). Task 2 adds `"ppa_off"` / `"ppa_def"`. Task 4 consumes this function from `enrich.py`.

Ordering rule (the lookahead fence): a team-season's games are sorted by `(sort_key, game_id)` where `sort_key = start_dates.get(game_id)` falling back to `f"{season:04d}-w{week:02d}"`. Real `startDate` strings sort correctly lexicographically; the fallback keeps week order when a raw games file is missing (fallback keys sort after real dates within a season because `"w" > "0"–"9"` — acceptable, since `games.csv` is built from the same raw files that supply `startDate`, so in practice every game has one). Stats for a game are snapshotted **before** folding that game's result in.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_running_stats.py`:

```python
from cfb_system_maker.models import GameRecord
from cfb_system_maker.running_stats import compute_running_stats


def _game(game_id, week, home="Alpha", away="Beta", home_points=None, away_points=None, spread=None, season=2023):
    return GameRecord(
        game_id=game_id,
        season=season,
        week=week,
        home_team=home,
        away_team=away,
        home_conference=None,
        away_conference=None,
        home_points=home_points,
        away_points=away_points,
        provider="consensus",
        spread=spread,
        total=None,
    )


def test_first_game_of_season_has_zero_history():
    games = [_game(1, 1, home_points=21, away_points=14, spread=-3.5)]
    stats = compute_running_stats(games)
    assert stats[(1, "Alpha")] == {"games_played": 0, "win_pct": None, "ats_pct": None}
    assert stats[(1, "Beta")] == {"games_played": 0, "win_pct": None, "ats_pct": None}


def test_no_lookahead_stats_reflect_only_strictly_prior_games():
    games = [
        _game(1, 1, home_points=21, away_points=14, spread=-3.5),   # Alpha win, covers
        _game(2, 2, home="Gamma", away="Alpha", home_points=28, away_points=10, spread=-7.0),  # Alpha loss
        _game(3, 3, home_points=35, away_points=0, spread=-10.0),   # Alpha home again
    ]
    stats = compute_running_stats(games)
    entering_g2 = stats[(2, "Alpha")]
    assert entering_g2["games_played"] == 1
    assert entering_g2["win_pct"] == 1.0
    entering_g3 = stats[(3, "Alpha")]
    assert entering_g3["games_played"] == 2
    assert entering_g3["win_pct"] == 0.5
    # g3's own 35-0 result must not appear anywhere in its entering stats


def test_ats_respects_home_spread_sign_convention():
    # Alpha home, favored by 7 (home spread -7), wins by only 3: Alpha ATS loss, Beta ATS win.
    games = [
        _game(1, 1, home_points=24, away_points=21, spread=-7.0),
        _game(2, 2, home_points=0, away_points=0, spread=None),  # carrier game to read entering stats
    ]
    stats = compute_running_stats(games)
    assert stats[(2, "Alpha")]["ats_pct"] == 0.0
    assert stats[(2, "Beta")]["ats_pct"] == 1.0


def test_ats_push_and_missing_spread_are_excluded_from_ats_pct():
    games = [
        _game(1, 1, home_points=17, away_points=10, spread=-7.0),  # exact push
        _game(2, 2, home_points=21, away_points=20, spread=None),  # no line: W-L counts, ATS doesn't
        _game(3, 3, home_points=0, away_points=0, spread=-1.0),
    ]
    stats = compute_running_stats(games)
    entering_g3 = stats[(3, "Alpha")]
    assert entering_g3["games_played"] == 2
    assert entering_g3["win_pct"] == 1.0
    assert entering_g3["ats_pct"] is None  # push + no-line games leave zero decided ATS bets


def test_unplayed_games_do_not_accumulate():
    games = [
        _game(1, 1, home_points=None, away_points=None, spread=-3.0),
        _game(2, 2, home_points=7, away_points=3, spread=-3.0),
    ]
    stats = compute_running_stats(games)
    assert stats[(2, "Alpha")]["games_played"] == 0


def test_seasons_reset():
    games = [
        _game(1, 10, season=2022, home_points=42, away_points=0, spread=-20.0),
        _game(2, 1, season=2023, home_points=0, away_points=0, spread=-1.0),
    ]
    stats = compute_running_stats(games)
    assert stats[(2, "Alpha")] == {"games_played": 0, "win_pct": None, "ats_pct": None}


def test_start_dates_override_week_order():
    # Bowl game stored as week 1 but dated after the week 12 game.
    games = [
        _game(1, 12, home_points=21, away_points=14, spread=-3.0),
        _game(2, 1, home_points=10, away_points=20, spread=-3.0),
    ]
    start_dates = {1: "2023-11-25 17:00:00+00:00", 2: "2023-12-30 17:00:00+00:00"}
    stats = compute_running_stats(games, start_dates=start_dates)
    assert stats[(2, "Alpha")]["games_played"] == 1
    assert stats[(1, "Alpha")]["games_played"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_running_stats.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'cfb_system_maker.running_stats'`

- [ ] **Step 3: Write the implementation**

Create `cfb_system_maker/running_stats.py`:

```python
from __future__ import annotations

from typing import Any

from cfb_system_maker.models import GameRecord


def compute_running_stats(
    games: list[GameRecord],
    *,
    start_dates: dict[int, str] | None = None,
) -> dict[tuple[int, str], dict[str, Any]]:
    start_dates = start_dates or {}

    by_team_season: dict[tuple[str, int], list[tuple[str, int, GameRecord, str]]] = {}
    for game in games:
        sort_key = start_dates.get(game.game_id) or f"{game.season:04d}-w{game.week:02d}"
        for side, team in (("home", game.home_team), ("away", game.away_team)):
            by_team_season.setdefault((team, game.season), []).append((sort_key, game.game_id, game, side))

    stats: dict[tuple[int, str], dict[str, Any]] = {}
    for (team, _season), entries in by_team_season.items():
        entries.sort(key=lambda entry: (entry[0], entry[1]))
        played = wins = losses = 0
        ats_wins = ats_losses = 0

        for _sort_key, game_id, game, side in entries:
            decided = wins + losses
            ats_decided = ats_wins + ats_losses
            stats[(game_id, team)] = {
                "games_played": played,
                "win_pct": round(wins / decided, 4) if decided else None,
                "ats_pct": round(ats_wins / ats_decided, 4) if ats_decided else None,
            }

            team_points = game.home_points if side == "home" else game.away_points
            opponent_points = game.away_points if side == "home" else game.home_points
            if team_points is None or opponent_points is None:
                continue
            played += 1
            if team_points > opponent_points:
                wins += 1
            elif team_points < opponent_points:
                losses += 1
            if game.spread is not None:
                side_spread = game.spread if side == "home" else -game.spread
                margin = team_points + side_spread - opponent_points
                if margin > 0:
                    ats_wins += 1
                elif margin < 0:
                    ats_losses += 1
                # margin == 0 is an ATS push: counts toward neither side

    return stats
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_running_stats.py -v`
Expected: 7 passed

- [ ] **Step 5: Full suite + commit**

Run: `python -m pytest`
Expected: all pass

```bash
git add cfb_system_maker/running_stats.py tests/test_running_stats.py
git commit -m "feat: add as-of-game running W-L/ATS computation"
```

---

### Task 2: Running PPA averages

**Files:**
- Modify: `cfb_system_maker/running_stats.py`
- Test: `tests/test_running_stats.py`

**Interfaces:**
- Produces: `compute_running_stats` gains keyword `ppa: dict[tuple[int, str], tuple[float | None, float | None]] | None = None` — `(game_id, team) -> (offense_overall, defense_overall)`. Output dicts gain `"ppa_off"` / `"ppa_def"` (float|None): running mean of prior games' values, `None` when no prior PPA rows.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_running_stats.py`:

```python
def test_running_ppa_is_average_of_prior_games_only():
    games = [
        _game(1, 1, home_points=21, away_points=14, spread=-3.0),
        _game(2, 2, home_points=28, away_points=7, spread=-3.0),
        _game(3, 3, home_points=0, away_points=0, spread=-3.0),
    ]
    ppa = {
        (1, "Alpha"): (0.40, -0.10),
        (2, "Alpha"): (0.60, -0.30),
        (3, "Alpha"): (9.99, 9.99),  # current game's PPA must never leak into its own entering stats
        (1, "Beta"): (0.10, 0.20),
    }
    stats = compute_running_stats(games, ppa=ppa)
    assert stats[(1, "Alpha")]["ppa_off"] is None
    assert stats[(2, "Alpha")]["ppa_off"] == 0.40
    assert stats[(3, "Alpha")]["ppa_off"] == 0.50
    assert stats[(3, "Alpha")]["ppa_def"] == -0.20
    assert stats[(2, "Beta")]["ppa_off"] == 0.10
    assert stats[(3, "Beta")]["ppa_off"] == 0.10  # no row for game 2: average over available rows


def test_ppa_handles_partial_none_values():
    games = [
        _game(1, 1, home_points=21, away_points=14, spread=-3.0),
        _game(2, 2, home_points=0, away_points=0, spread=-3.0),
    ]
    ppa = {(1, "Alpha"): (None, -0.25)}
    stats = compute_running_stats(games, ppa=ppa)
    assert stats[(2, "Alpha")]["ppa_off"] is None
    assert stats[(2, "Alpha")]["ppa_def"] == -0.25
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_running_stats.py -v`
Expected: new tests FAIL with `TypeError: compute_running_stats() got an unexpected keyword argument 'ppa'`; Task 1 tests may also fail on missing `ppa_off` keys once compared — the two exact-dict asserts in `test_first_game_of_season_has_zero_history` and `test_seasons_reset` must be updated in Step 3 to include `"ppa_off": None, "ppa_def": None`.

- [ ] **Step 3: Write the implementation**

Replace `compute_running_stats` in `cfb_system_maker/running_stats.py` with:

```python
def compute_running_stats(
    games: list[GameRecord],
    *,
    ppa: dict[tuple[int, str], tuple[float | None, float | None]] | None = None,
    start_dates: dict[int, str] | None = None,
) -> dict[tuple[int, str], dict[str, Any]]:
    ppa = ppa or {}
    start_dates = start_dates or {}

    by_team_season: dict[tuple[str, int], list[tuple[str, int, GameRecord, str]]] = {}
    for game in games:
        sort_key = start_dates.get(game.game_id) or f"{game.season:04d}-w{game.week:02d}"
        for side, team in (("home", game.home_team), ("away", game.away_team)):
            by_team_season.setdefault((team, game.season), []).append((sort_key, game.game_id, game, side))

    stats: dict[tuple[int, str], dict[str, Any]] = {}
    for (team, _season), entries in by_team_season.items():
        entries.sort(key=lambda entry: (entry[0], entry[1]))
        played = wins = losses = 0
        ats_wins = ats_losses = 0
        ppa_off_sum = ppa_def_sum = 0.0
        ppa_off_count = ppa_def_count = 0

        for _sort_key, game_id, game, side in entries:
            decided = wins + losses
            ats_decided = ats_wins + ats_losses
            stats[(game_id, team)] = {
                "games_played": played,
                "win_pct": round(wins / decided, 4) if decided else None,
                "ats_pct": round(ats_wins / ats_decided, 4) if ats_decided else None,
                "ppa_off": round(ppa_off_sum / ppa_off_count, 4) if ppa_off_count else None,
                "ppa_def": round(ppa_def_sum / ppa_def_count, 4) if ppa_def_count else None,
            }

            team_points = game.home_points if side == "home" else game.away_points
            opponent_points = game.away_points if side == "home" else game.home_points
            if team_points is None or opponent_points is None:
                continue
            played += 1
            if team_points > opponent_points:
                wins += 1
            elif team_points < opponent_points:
                losses += 1
            if game.spread is not None:
                side_spread = game.spread if side == "home" else -game.spread
                margin = team_points + side_spread - opponent_points
                if margin > 0:
                    ats_wins += 1
                elif margin < 0:
                    ats_losses += 1
                # margin == 0 is an ATS push: counts toward neither side
            game_ppa = ppa.get((game_id, team))
            if game_ppa:
                off_value, def_value = game_ppa
                if off_value is not None:
                    ppa_off_sum += float(off_value)
                    ppa_off_count += 1
                if def_value is not None:
                    ppa_def_sum += float(def_value)
                    ppa_def_count += 1

    return stats
```

Update the two exact-dict asserts from Task 1 to the full shape:

```python
    assert stats[(1, "Alpha")] == {"games_played": 0, "win_pct": None, "ats_pct": None, "ppa_off": None, "ppa_def": None}
    assert stats[(1, "Beta")] == {"games_played": 0, "win_pct": None, "ats_pct": None, "ppa_off": None, "ppa_def": None}
```

and in `test_seasons_reset`:

```python
    assert stats[(2, "Alpha")] == {"games_played": 0, "win_pct": None, "ats_pct": None, "ppa_off": None, "ppa_def": None}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_running_stats.py -v`
Expected: 9 passed

- [ ] **Step 5: Full suite + commit**

Run: `python -m pytest`
Expected: all pass

```bash
git add cfb_system_maker/running_stats.py tests/test_running_stats.py
git commit -m "feat: add running PPA averages to running stats"
```

---

### Task 3: `season_to_date` registry group

**Files:**
- Modify: `cfb_system_maker/features.py` (Group/SourceKind literals + 5 new `FeatureDef` rows)
- Modify: `cfb_system_maker/web.py:311` (group ordering tuple in `_feature_options`)
- Test: `tests/test_features.py`

**Interfaces:**
- Produces: registry keys `running_games_played`, `running_win_pct`, `running_ats_pct`, `running_ppa_off`, `running_ppa_def` — all `group="season_to_date"`, `source_kind="computed_running"`, `join="game_id"`, `control="numeric"`, `team_scoped=True`, with `field` values `games_played` / `win_pct` / `ats_pct` / `ppa_off` / `ppa_def` matching the Task 2 dict keys exactly. Task 4's enrich wiring resolves them; until then they enrich to `None` (safe: `_lookup`'s fall-through returns `None` for unknown source kinds).
- The web template needs no change for the group header: `{{ group.group|replace('_', ' ')|title }}` renders "Season To Date".

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_features.py`:

```python
from cfb_system_maker.features import FEATURE_BY_KEY, FEATURE_REGISTRY, registry_keys_unique

RUNNING_KEYS = (
    "running_games_played",
    "running_win_pct",
    "running_ats_pct",
    "running_ppa_off",
    "running_ppa_def",
)


def test_season_to_date_features_registered():
    assert registry_keys_unique()
    for key in RUNNING_KEYS:
        feature = FEATURE_BY_KEY[key]
        assert feature.group == "season_to_date"
        assert feature.source_kind == "computed_running"
        assert feature.control == "numeric"
        assert feature.team_scoped is True


def test_season_to_date_fields_match_running_stats_output():
    expected = {"games_played", "win_pct", "ats_pct", "ppa_off", "ppa_def"}
    fields = {FEATURE_BY_KEY[key].field for key in RUNNING_KEYS}
    assert fields == expected
```

(Adjust the import line to merge with whatever `tests/test_features.py` already imports — keep existing tests untouched.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_features.py -v`
Expected: FAIL — `KeyError: 'running_games_played'`

- [ ] **Step 3: Implement registry rows**

In `cfb_system_maker/features.py`:

1. Extend the literals:

```python
Group = Literal["pregame", "season_to_date", "team_preseason", "metadata", "result_lookahead"]
```

and add `"computed_running",` to the `SourceKind` literal list.

2. Insert into `FEATURE_REGISTRY` after the metadata block, before the `# --- result lookahead ---` block:

```python
    # --- season to date (computed, as-of-game) ---
    FeatureDef("running_games_played", "Games Played (to date)", "season_to_date", "computed_running", "games_played", "game_id", "numeric", team_scoped=True),
    FeatureDef("running_win_pct", "Win % (to date)", "season_to_date", "computed_running", "win_pct", "game_id", "numeric", team_scoped=True),
    FeatureDef("running_ats_pct", "ATS Win % (to date)", "season_to_date", "computed_running", "ats_pct", "game_id", "numeric", team_scoped=True),
    FeatureDef("running_ppa_off", "Off PPA (to date)", "season_to_date", "computed_running", "ppa_off", "game_id", "numeric", team_scoped=True),
    FeatureDef("running_ppa_def", "Def PPA (to date)", "season_to_date", "computed_running", "ppa_def", "game_id", "numeric", team_scoped=True),
```

3. In `cfb_system_maker/web.py`, `_feature_options`, change the ordering tuple:

```python
    for group in ("pregame", "season_to_date", "team_preseason", "metadata", "result_lookahead"):
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_features.py -v`
Expected: all pass

- [ ] **Step 5: Full suite + commit**

Run: `python -m pytest`
Expected: all pass (enrich resolves the new keys to `None` until Task 4 — no test asserts on them yet)

```bash
git add cfb_system_maker/features.py cfb_system_maker/web.py tests/test_features.py
git commit -m "feat: register season_to_date running-stat features"
```

---

### Task 4: Wire running stats into enrich

**Files:**
- Modify: `cfb_system_maker/enrich.py`
- Test: `tests/test_enrich.py`

**Interfaces:**
- Consumes: `compute_running_stats` (Tasks 1-2), `indexes["raw_game"]` rows (for `startDate`), `data/raw/ppa_games_{season}.json`.
- Produces: `indexes["computed_running"]: dict[tuple[int, str], dict[str, Any]]`; sidecar keys `home_running_*` / `away_running_*` for every game.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_enrich.py` (reuses the file's existing imports plus `json`):

```python
def test_enrich_computes_running_stats_from_prior_games(tmp_path):
    season = 2023
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True)

    (raw_dir / f"games_{season}.json").write_text(
        json.dumps(
            [
                {"id": 1, "season": season, "startDate": "2023-09-02 17:00:00+00:00"},
                {"id": 2, "season": season, "startDate": "2023-09-09 17:00:00+00:00"},
            ]
        ),
        encoding="utf-8",
    )
    (raw_dir / f"ppa_games_{season}.json").write_text(
        json.dumps(
            [
                {"gameId": 1, "team": "Alpha", "offense": {"overall": 0.5}, "defense": {"overall": -0.2}},
                {"gameId": 1, "team": "Beta", "offense": {"overall": 0.1}, "defense": {"overall": 0.3}},
            ]
        ),
        encoding="utf-8",
    )

    games = [
        GameRecord(1, season, 1, "Alpha", "Beta", None, None, 21, 14, "consensus", -3.5, None),
        GameRecord(2, season, 2, "Alpha", "Beta", None, None, 10, 20, "consensus", -3.5, None),
    ]

    features = enrich_games(tmp_path, games)

    entering_g1 = features["1"]
    assert entering_g1["home_running_games_played"] == 0
    assert entering_g1["home_running_win_pct"] is None

    entering_g2 = features["2"]
    assert entering_g2["home_running_games_played"] == 1
    assert entering_g2["home_running_win_pct"] == 1.0       # Alpha won game 1
    assert entering_g2["home_running_ats_pct"] == 1.0        # -3.5, won by 7: covered
    assert entering_g2["away_running_ats_pct"] == 0.0        # Beta failed to cover +3.5
    assert entering_g2["home_running_ppa_off"] == 0.5
    assert entering_g2["away_running_ppa_def"] == 0.3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_enrich.py -v`
Expected: new test FAILS — `KeyError: 'home_running_games_played'` (values currently never written) or the keys resolve to `None`.

- [ ] **Step 3: Implement enrich wiring**

In `cfb_system_maker/enrich.py`:

1. Add import:

```python
from cfb_system_maker.running_stats import compute_running_stats
```

2. In `_build_indexes`, after the four `graphql` index lines and before `return indexes`, add:

```python
    indexes["computed_running"] = _build_running_index(data_dir, seasons, games, indexes["raw_game"])
```

3. Add the builder as a module-level helper:

```python
def _build_running_index(
    data_dir: Path,
    seasons: list[int],
    games: list[GameRecord],
    raw_games: dict[int, dict[str, Any]],
) -> dict[tuple[int, str], dict[str, Any]]:
    ppa: dict[tuple[int, str], tuple[float | None, float | None]] = {}
    for season in seasons:
        path = data_dir / "raw" / f"ppa_games_{season}.json"
        if not path.exists():
            continue
        for row in json.loads(path.read_text(encoding="utf-8")):
            game_id = row.get("gameId") if row.get("gameId") is not None else row.get("game_id")
            team = row.get("team")
            if game_id is None or team is None:
                continue
            offense = row.get("offense") or {}
            defense = row.get("defense") or {}
            ppa[(int(game_id), str(team))] = (offense.get("overall"), defense.get("overall"))

    start_dates: dict[int, str] = {}
    for game_id, row in raw_games.items():
        start = row.get("startDate") or row.get("start_date")
        if start:
            start_dates[game_id] = str(start)

    return compute_running_stats(games, ppa=ppa, start_dates=start_dates)
```

4. In `_lookup`, add a branch (place it next to the `raw_havoc` branch):

```python
    if feature.source_kind == "computed_running":
        running = indexes["computed_running"]
        home_stats = running.get((game.game_id, game.home_team)) or {}
        away_stats = running.get((game.game_id, game.away_team)) or {}
        return (home_stats.get(feature.field), away_stats.get(feature.field))
```

5. In `_apply_feature`, extend the tuple-return source set:

```python
        if feature.source_kind in {"raw_havoc", "graphql_game_team", "computed_running"}:
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_enrich.py -v`
Expected: all pass

- [ ] **Step 5: Full suite + commit**

Run: `python -m pytest`
Expected: all pass

```bash
git add cfb_system_maker/enrich.py tests/test_enrich.py
git commit -m "feat: wire running season-to-date stats into enrich"
```

---

### Task 5: Sidecar `_meta`, `registry_version()`, stale-registry warning

**Files:**
- Modify: `cfb_system_maker/features.py` (add `registry_version()`)
- Modify: `cfb_system_maker/enrich.py` (`save_features` / `load_features` / new `load_features_meta`)
- Modify: `cfb_system_maker/web.py` + `cfb_system_maker/templates/index.html` (banner)
- Test: `tests/test_enrich.py`, `tests/test_web_features.py`

**Interfaces:**
- Produces: `features.registry_version() -> str` (12-hex digest of sorted registry keys); sidecar shape becomes `{"_meta": {"registry_version", "game_count", "generated_at"}, "games": {...}}`; `enrich.load_features` keeps its `dict[int, dict]` contract and still reads the **legacy flat shape** (old files keep working); new `enrich.load_features_meta(data_dir) -> dict | None`; template variable `stale_registry: bool`.
- `save_features(data_dir, features)` keeps its positional signature (existing callers in tests pass 2 args); meta is built internally.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_enrich.py`:

```python
def test_save_features_writes_meta_and_load_reads_both_shapes(tmp_path):
    from cfb_system_maker.enrich import load_features, load_features_meta
    from cfb_system_maker.features import registry_version

    path = save_features(tmp_path, {"1": {"neutralSite": True}})
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["_meta"]["registry_version"] == registry_version()
    assert payload["_meta"]["game_count"] == 1
    assert load_features(tmp_path) == {1: {"neutralSite": True}}
    assert load_features_meta(tmp_path)["game_count"] == 1

    # Legacy flat shape still loads, meta reads as None
    path.write_text(json.dumps({"2": {"neutralSite": False}}), encoding="utf-8")
    assert load_features(tmp_path) == {2: {"neutralSite": False}}
    assert load_features_meta(tmp_path) is None
```

In `tests/test_web_features.py`, add `import json` to the top-of-file imports, then append:

```python
def test_stale_registry_warning_shows_only_for_old_sidecar(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    from cfb_system_maker.storage import save_processed_games

    save_processed_games(tmp_path, games)
    rows = {str(game.game_id): {"neutralSite": False} for game in games}

    path = tmp_path / "processed" / "features.json"
    path.write_text(json.dumps({"_meta": {"registry_version": "outdated"}, "games": rows}), encoding="utf-8")
    html = create_app(tmp_path).test_client().get("/").get_data(as_text=True)
    assert "older field registry" in html

    save_features(tmp_path, rows)
    html = create_app(tmp_path).test_client().get("/").get_data(as_text=True)
    assert "older field registry" not in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_enrich.py tests/test_web_features.py -v`
Expected: FAIL — `ImportError: cannot import name 'load_features_meta'`

- [ ] **Step 3: Implement**

1. `cfb_system_maker/features.py` — add near the top `import hashlib`, and after `FEATURE_BY_KEY`:

```python
def registry_version() -> str:
    digest = hashlib.sha256(",".join(sorted(FEATURE_BY_KEY)).encode("utf-8")).hexdigest()
    return digest[:12]
```

2. `cfb_system_maker/enrich.py` — add imports:

```python
from datetime import datetime, timezone

from cfb_system_maker.features import FEATURE_REGISTRY, FeatureDef, get_nested, registry_version
```

Replace `save_features`, `load_features` and add the meta pieces:

```python
def save_features(data_dir: str | Path, features: dict[str, dict[str, Any]]) -> Path:
    path = Path(data_dir) / "processed" / "features.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"_meta": _build_meta(features), "games": features}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _build_meta(features: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "registry_version": registry_version(),
        "game_count": len(features),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def load_features(data_dir: str | Path) -> dict[int, dict[str, Any]]:
    raw = json.loads(_features_path(data_dir).read_text(encoding="utf-8"))
    rows = raw["games"] if "_meta" in raw and "games" in raw else raw
    return {int(game_id): values for game_id, values in rows.items()}


def load_features_meta(data_dir: str | Path) -> dict[str, Any] | None:
    path = _features_path(data_dir)
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    meta = raw.get("_meta") if isinstance(raw, dict) else None
    return meta if isinstance(meta, dict) else None


def _features_path(data_dir: str | Path) -> Path:
    return Path(data_dir) / "processed" / "features.json"
```

(`load_features` keeps raising `FileNotFoundError` when the file is missing — web's `_try_load_features` depends on that.)

3. `cfb_system_maker/web.py` — extend imports:

```python
from cfb_system_maker.enrich import load_features, load_features_meta
from cfb_system_maker.features import FEATURE_REGISTRY, FeatureDef, registry_version
```

In `index()`, after `feature_map = _try_load_features(...)`:

```python
        meta = load_features_meta(app.config["DATA_DIR"]) if feature_map is not None else None
        stale_registry = bool(meta and meta.get("registry_version") != registry_version())
```

Add `stale_registry=stale_registry,` to the main `render_template` call and `stale_registry=False,` to the `missing_data` one.

4. `cfb_system_maker/templates/index.html` — inside the `feature-filters` section, directly under `<h3>Feature Filters</h3>`:

```html
            {% if stale_registry %}
            <p class="stale-warning">features.json was built with an older field registry — run <code>python -m cfb_system_maker enrich --data-dir data</code> to refresh.</p>
            {% endif %}
```

5. `cfb_system_maker/static/styles.css` — append:

```css
.stale-warning {
  background: #fff4e5;
  border: 1px solid #f0b429;
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 0.85rem;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_enrich.py tests/test_web_features.py -v`
Expected: all pass

- [ ] **Step 5: Full suite + commit**

Run: `python -m pytest`
Expected: all pass

```bash
git add cfb_system_maker/features.py cfb_system_maker/enrich.py cfb_system_maker/web.py cfb_system_maker/templates/index.html cfb_system_maker/static/styles.css tests/test_enrich.py tests/test_web_features.py
git commit -m "feat: add sidecar _meta and stale-registry warning"
```

---

### Task 6: Venue metadata features (dome, grass, elevation, capacity)

**Files:**
- Modify: `cfb_system_maker/features.py`, `cfb_system_maker/enrich.py`
- Test: `tests/test_enrich.py`

**Interfaces:**
- Produces: registry keys `venue_dome` (bool), `venue_grass` (bool), `venue_elevation` (numeric), `venue_capacity` (numeric) — group `metadata`, `source_kind="raw_venues"`, `join="game_id"`, not team-scoped. Resolution path: game → `indexes["raw_game"][game_id]["venueId"]` → `indexes["raw_venues"][venue_id]` → field. `venues.json` is a single season-less file.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_enrich.py`:

```python
def test_enrich_resolves_venue_fields_via_venue_id(tmp_path):
    season = 2023
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / f"games_{season}.json").write_text(
        json.dumps([{"id": 1, "season": season, "venueId": 55}]), encoding="utf-8"
    )
    (raw_dir / "venues.json").write_text(
        json.dumps([{"id": 55, "dome": True, "grass": False, "elevation": "177.0", "capacity": 70000}]),
        encoding="utf-8",
    )

    games = [GameRecord(1, season, 1, "Alpha", "Beta", None, None, 21, 14, "consensus", -3.5, None)]
    features = enrich_games(tmp_path, games)
    row = features["1"]
    assert row["venue_dome"] is True
    assert row["venue_grass"] is False
    assert row["venue_elevation"] == "177.0"
    assert row["venue_capacity"] == 70000
```

(Elevation arrives from CFBD as a string — the numeric ops already coerce via `float(actual)` in `features._value_matches`, so store it raw.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_enrich.py -v`
Expected: FAIL — `KeyError: 'venue_dome'`

- [ ] **Step 3: Implement**

1. `features.py` — add `"raw_venues",` to `SourceKind`; append to the `# --- metadata ---` block:

```python
    FeatureDef("venue_dome", "Dome", "metadata", "raw_venues", "dome", "game_id", "bool"),
    FeatureDef("venue_grass", "Grass Field", "metadata", "raw_venues", "grass", "game_id", "bool"),
    FeatureDef("venue_elevation", "Venue Elevation", "metadata", "raw_venues", "elevation", "game_id", "numeric"),
    FeatureDef("venue_capacity", "Venue Capacity", "metadata", "raw_venues", "capacity", "game_id", "numeric"),
```

2. `enrich.py` — in `_build_indexes`: add `"raw_venues": {},` to the `indexes` dict literal, and after the season loop (next to the graphql lines):

```python
    _index_raw_file(indexes["raw_venues"], data_dir / "raw" / "venues.json", "id")
```

3. `enrich.py` — add a `_lookup` branch:

```python
    if feature.source_kind == "raw_venues":
        game_row = indexes["raw_game"].get(game.game_id)
        venue_id = game_row.get("venueId") if game_row else None
        record = indexes["raw_venues"].get(int(venue_id)) if venue_id is not None else None
        return _field_value(record, feature.field) if record else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_enrich.py tests/test_features.py -v`
Expected: all pass

- [ ] **Step 5: Full suite + commit**

Run: `python -m pytest`
Expected: all pass

```bash
git add cfb_system_maker/features.py cfb_system_maker/enrich.py tests/test_enrich.py
git commit -m "feat: add venue dome/grass/elevation/capacity features"
```

---

### Task 7: Conference classification feature (team-scoped, `conference_name` join)

**Files:**
- Modify: `cfb_system_maker/features.py`, `cfb_system_maker/enrich.py`
- Test: `tests/test_enrich.py`

**Interfaces:**
- Produces: registry key `conference_classification` — group `metadata`, `source_kind="raw_conferences"`, `join="conference_name"` (the `Join` literal already includes it, currently unused), `control="categorical"`, `team_scoped=True`. Resolves via `GameRecord.home_conference` / `away_conference` against `conferences.json` `name`. Stored as `home_conference_classification` / `away_conference_classification` so all four spread perspectives work (e.g. "bet-side team is FCS").

- [ ] **Step 1: Write the failing test**

Append to `tests/test_enrich.py`:

```python
def test_enrich_resolves_conference_classification_per_side(tmp_path):
    season = 2023
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "conferences.json").write_text(
        json.dumps(
            [
                {"name": "ACC", "classification": "fbs"},
                {"name": "Big Sky", "classification": "fcs"},
            ]
        ),
        encoding="utf-8",
    )

    games = [GameRecord(1, season, 1, "Alpha", "Beta", "ACC", "Big Sky", 21, 14, "consensus", -3.5, None)]
    features = enrich_games(tmp_path, games)
    assert features["1"]["home_conference_classification"] == "fbs"
    assert features["1"]["away_conference_classification"] == "fcs"

    games_no_conf = [GameRecord(2, season, 1, "Gamma", "Delta", None, None, 7, 3, "consensus", -1.0, None)]
    features = enrich_games(tmp_path, games_no_conf)
    assert features["2"]["home_conference_classification"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_enrich.py -v`
Expected: FAIL — `KeyError: 'home_conference_classification'`

- [ ] **Step 3: Implement**

1. `features.py` — add `"raw_conferences",` to `SourceKind`; append to the metadata block:

```python
    FeatureDef("conference_classification", "Conference Classification", "metadata", "raw_conferences", "classification", "conference_name", "categorical", team_scoped=True),
```

2. `enrich.py` — add `"raw_conferences": {},` to the `indexes` dict literal; after the venues index line add:

```python
    _index_conferences(indexes["raw_conferences"], data_dir / "raw" / "conferences.json")
```

with the helper:

```python
def _index_conferences(bucket: dict[str, dict[str, Any]], path: Path) -> None:
    if not path.exists():
        return
    for row in json.loads(path.read_text(encoding="utf-8")):
        name = row.get("name")
        if name is not None:
            bucket[str(name)] = row
```

3. `enrich.py` — `_apply_feature` currently assumes team-scoped values are looked up by team name. Conference-joined features are looked up by conference name instead, so replace `_apply_feature` with (only the leading guard is new; the rest is the existing body verbatim):

```python
def _apply_feature(row: dict[str, Any], feature: FeatureDef, game: GameRecord, indexes: dict[str, Any]) -> None:
    if feature.team_scoped and feature.join == "conference_name":
        row[f"home_{feature.key}"] = _lookup_conference(feature, game.home_conference, indexes)
        row[f"away_{feature.key}"] = _lookup_conference(feature, game.away_conference, indexes)
        return
    value = _lookup(feature, game, indexes)
    if feature.team_scoped and feature.join in {"team_season", "team_name", "game_id"}:
        if feature.source_kind in {"raw_havoc", "graphql_game_team", "computed_running"}:
            home_val, away_val = value if isinstance(value, tuple) else (None, None)
            row[f"home_{feature.key}"] = home_val
            row[f"away_{feature.key}"] = away_val
        else:
            home_val = _lookup_team_scoped(feature, game.home_team, game.season, indexes)
            away_val = _lookup_team_scoped(feature, game.away_team, game.season, indexes)
            row[f"home_{feature.key}"] = home_val
            row[f"away_{feature.key}"] = away_val
    else:
        row[feature.key] = value
```

and the helper:

```python
def _lookup_conference(feature: FeatureDef, conference: str | None, indexes: dict[str, Any]) -> Any:
    if conference is None:
        return None
    record = indexes["raw_conferences"].get(conference)
    return _field_value(record, feature.field) if record else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_enrich.py -v`
Expected: all pass

- [ ] **Step 5: Full suite + commit**

Run: `python -m pytest`
Expected: all pass

```bash
git add cfb_system_maker/features.py cfb_system_maker/enrich.py tests/test_enrich.py
git commit -m "feat: add team-scoped conference classification feature"
```

---

### Task 8: Wind direction + REST pregame home win prob

**Files:**
- Modify: `cfb_system_maker/features.py`, `cfb_system_maker/enrich.py`
- Test: `tests/test_enrich.py`

**Interfaces:**
- Produces: registry keys `weather_windDirection` (existing `raw_weather` source, zero new plumbing) and `pregame_home_win_prob` (`source_kind="raw_pregame_wp"`, from `pregame_win_prob_{season}.json`, field `homeWinProbability`, keyed by `gameId`). Both group `pregame`, numeric, not team-scoped. (The existing team-scoped `pregame_win_prob` from GraphQL stays — this REST variant covers seasons where the GraphQL pull is absent.)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_enrich.py`:

```python
def test_enrich_wind_direction_and_rest_pregame_win_prob(tmp_path):
    season = 2023
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / f"weather_{season}.json").write_text(
        json.dumps([{"id": 1, "windDirection": 270}]), encoding="utf-8"
    )
    (raw_dir / f"pregame_win_prob_{season}.json").write_text(
        json.dumps([{"gameId": 1, "homeWinProbability": 0.731}]), encoding="utf-8"
    )

    games = [GameRecord(1, season, 1, "Alpha", "Beta", None, None, 21, 14, "consensus", -3.5, None)]
    features = enrich_games(tmp_path, games)
    assert features["1"]["weather_windDirection"] == 270
    assert features["1"]["pregame_home_win_prob"] == 0.731
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_enrich.py -v`
Expected: FAIL — `KeyError: 'weather_windDirection'`

- [ ] **Step 3: Implement**

1. `features.py` — add `"raw_pregame_wp",` to `SourceKind`; append to the pregame block (next to the other weather rows):

```python
    FeatureDef("weather_windDirection", "Wind Direction (deg)", "pregame", "raw_weather", "windDirection", "game_id", "numeric"),
    FeatureDef("pregame_home_win_prob", "Home Win Prob (pregame)", "pregame", "raw_pregame_wp", "homeWinProbability", "game_id", "numeric"),
```

2. `enrich.py` — add `"raw_pregame_wp": {},` to the `indexes` dict literal; inside the per-season loop add:

```python
        _index_raw_file(indexes["raw_pregame_wp"], data_dir / "raw" / f"pregame_win_prob_{season}.json", "gameId")
```

3. `enrich.py` — add a `_lookup` branch (next to `raw_weather`):

```python
    if feature.source_kind == "raw_pregame_wp":
        record = indexes["raw_pregame_wp"].get(game.game_id)
        return _field_value(record, feature.field) if record else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_enrich.py -v`
Expected: all pass

- [ ] **Step 5: Full suite + commit**

Run: `python -m pytest`
Expected: all pass

```bash
git add cfb_system_maker/features.py cfb_system_maker/enrich.py tests/test_enrich.py
git commit -m "feat: add wind direction and REST pregame win prob features"
```

---

### Task 9: Win/loss streaks in `SystemStats`

**Files:**
- Modify: `cfb_system_maker/models.py` (`SystemStats`), `cfb_system_maker/backtest.py`, `cfb_system_maker/cli.py` (`print_result`), `cfb_system_maker/templates/index.html`
- Test: `tests/test_backtest.py`

**Interfaces:**
- Produces: `SystemStats.max_win_streak: int = 0` and `SystemStats.max_loss_streak: int = 0` (defaults keep any existing direct constructions valid). Streaks are computed over `bet_details` sorted chronologically by `(season, week, game_id)`; pushes neither extend nor break a streak.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_backtest.py` (merge imports with the file's existing ones):

```python
from cfb_system_maker.backtest import compute_system_stats
from cfb_system_maker.models import BetDetail


def _bet(game_id, week, result):
    profit = 0.9091 if result == "win" else (-1.0 if result == "loss" else 0.0)
    return BetDetail(
        game_id=game_id,
        season=2023,
        week=week,
        team="Alpha",
        opponent="Beta",
        side="home",
        spread=-3.0,
        total=None,
        line=-3.0,
        result=result,
        profit=profit,
    )


def test_streaks_are_chronological_and_pushes_do_not_break_them():
    # Chronological order: W W P W L L — but pass details shuffled to prove sorting.
    details = [
        _bet(4, 4, "win"),
        _bet(1, 1, "win"),
        _bet(6, 6, "loss"),
        _bet(2, 2, "win"),
        _bet(5, 5, "loss"),
        _bet(3, 3, "push"),
    ]
    stats = compute_system_stats(details, hit_rate=0.6, roi=0.1, american_odds=-110, stake=1.0)
    assert stats.max_win_streak == 3
    assert stats.max_loss_streak == 2


def test_streaks_default_to_zero_with_no_bets():
    stats = compute_system_stats([], hit_rate=0.0, roi=0.0, american_odds=-110, stake=1.0)
    assert stats.max_win_streak == 0
    assert stats.max_loss_streak == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_backtest.py -v`
Expected: FAIL — `AttributeError: 'SystemStats' object has no attribute 'max_win_streak'`

- [ ] **Step 3: Implement**

1. `models.py` — extend `SystemStats`:

```python
@dataclass(frozen=True)
class SystemStats:
    break_even_rate: float
    edge: float
    wilson_low: float
    wilson_high: float
    z_score: float
    p_value: float
    roi_std_error: float
    roi_t_stat: float
    low_sample: bool
    max_win_streak: int = 0
    max_loss_streak: int = 0
```

2. `backtest.py` — in `compute_system_stats`, before the `return`:

```python
    max_win_streak, max_loss_streak = _streaks(sorted(details, key=lambda bet: (bet.season, bet.week, bet.game_id)))
```

and pass them into the `SystemStats(...)` construction:

```python
        max_win_streak=max_win_streak,
        max_loss_streak=max_loss_streak,
```

Add the helper near the other private helpers:

```python
def _streaks(details: list[BetDetail]) -> tuple[int, int]:
    best_win = best_loss = win_run = loss_run = 0
    for bet in details:
        if bet.result == "win":
            win_run += 1
            loss_run = 0
        elif bet.result == "loss":
            loss_run += 1
            win_run = 0
        else:
            continue  # pushes neither extend nor break a streak
        best_win = max(best_win, win_run)
        best_loss = max(best_loss, loss_run)
    return best_win, best_loss
```

3. `cli.py` — in `print_result`, inside the `if result.stats:` block after the p-value line:

```python
        print(f"Longest streaks: W{stats.max_win_streak} / L{stats.max_loss_streak}")
```

4. `templates/index.html` — in the stats panel, after the ROI t-stat article:

```html
            <article><span>Streaks</span><strong>W{{ result.stats.max_win_streak }} / L{{ result.stats.max_loss_streak }}</strong></article>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_backtest.py -v`
Expected: all pass

- [ ] **Step 5: Full suite + commit**

Run: `python -m pytest`
Expected: all pass

```bash
git add cfb_system_maker/models.py cfb_system_maker/backtest.py cfb_system_maker/cli.py cfb_system_maker/templates/index.html tests/test_backtest.py
git commit -m "feat: add max win/loss streaks to SystemStats"
```

---

### Task 10: Feature-filter coverage %

**Files:**
- Modify: `cfb_system_maker/web.py`, `cfb_system_maker/templates/index.html`, `cfb_system_maker/static/styles.css`
- Test: `tests/test_web_features.py`

**Interfaces:**
- Produces: template variable `coverage: list[dict]` with items `{"key", "label", "pct"}` — for each **enabled** feature filter, the % of games passing the *core* (non-feature) filters that have a non-null resolved value for that feature/perspective. Diagnoses "my filter matched 3 games because the field is null everywhere," which fails closed by design.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_web_features.py`:

```python
def test_coverage_panel_reports_non_null_share(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    from cfb_system_maker.storage import save_processed_games

    save_processed_games(tmp_path, games)
    rows = {}
    for index, game in enumerate(games):
        rows[str(game.game_id)] = {"weather_temperature": 50.0 if index == 0 else None}
    save_features(tmp_path, rows)

    app = create_app(tmp_path)
    html = app.test_client().get(
        "/?side=home&ff_enable=weather_temperature&ff_key=weather_temperature&ff_op=gte&ff_value=1&ff_perspective=single"
    ).get_data(as_text=True)
    assert "Filter Coverage" in html
    assert "Temperature (F)" in html

    # No enabled filters: panel absent
    html = app.test_client().get("/?side=home").get_data(as_text=True)
    assert "Filter Coverage" not in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_web_features.py -v`
Expected: FAIL — `assert "Filter Coverage" in html`

- [ ] **Step 3: Implement**

1. `web.py` — extend imports:

```python
from dataclasses import asdict, replace

from cfb_system_maker.backtest import matches_system, run_backtest
from cfb_system_maker.features import FEATURE_BY_KEY, FEATURE_REGISTRY, FeatureDef, registry_version, resolve_feature_value
```

2. In `index()`, after `result = run_backtest(...)`:

```python
        coverage = _feature_coverage(games, system, feature_map)
```

and add `coverage=coverage,` to the main `render_template` call (the `missing_data` branch does not need it — Jinja treats the undefined variable as falsy).

3. Add the helper:

```python
def _feature_coverage(
    games: list[GameRecord],
    system: SystemFilter,
    feature_map: dict[int, dict] | None,
) -> list[dict[str, object]]:
    if not system.feature_filters or feature_map is None:
        return []
    core = replace(system, feature_filters=())
    matched = [game for game in games if matches_system(game, core, feature_map)]
    if not matched:
        return []
    output: list[dict[str, object]] = []
    for filt in system.feature_filters:
        feature = FEATURE_BY_KEY.get(filt.key)
        if feature is None:
            continue
        non_null = 0
        for game in matched:
            value = resolve_feature_value(feature_map.get(game.game_id, {}), feature, filt, core)
            if filt.perspective == "either" and isinstance(value, tuple):
                value = value[0] if value[0] is not None else value[1]
            if value is not None:
                non_null += 1
        output.append({"key": filt.key, "label": feature.label, "pct": round(100 * non_null / len(matched), 1)})
    return output
```

4. `templates/index.html` — after the stats panel `{% endif %}`:

```html
          {% if coverage %}
          <section class="coverage" aria-label="Feature filter coverage">
            <h3>Filter Coverage</h3>
            <ul>
              {% for item in coverage %}
                <li><strong>{{ item.label }}</strong>: {{ item.pct }}% of core-filtered games have a value (null values fail closed)</li>
              {% endfor %}
            </ul>
          </section>
          {% endif %}
```

5. `styles.css` — append:

```css
.coverage {
  font-size: 0.85rem;
  margin: 12px 0;
}
.coverage ul {
  margin: 4px 0 0;
  padding-left: 18px;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_web_features.py -v`
Expected: all pass

- [ ] **Step 5: Full suite + commit**

Run: `python -m pytest`
Expected: all pass

```bash
git add cfb_system_maker/web.py cfb_system_maker/templates/index.html cfb_system_maker/static/styles.css tests/test_web_features.py
git commit -m "feat: show per-filter feature coverage percentages"
```

---

### Task 11: Compare-systems view

**Files:**
- Modify: `cfb_system_maker/web.py`, `cfb_system_maker/templates/index.html`, `cfb_system_maker/static/styles.css`
- Create: `cfb_system_maker/templates/compare.html`
- Test: `tests/test_web_compare.py`

**Interfaces:**
- Produces: `GET /compare` — no params: checkbox picker of saved systems; `?system=<name>&system=<name>`: metric table, one column per system, each run through `run_backtest` over the same `games.csv` + `features.json`. Unknown names are skipped silently. Index page links to it.

- [ ] **Step 1: Write the failing test**

Create `tests/test_web_compare.py`:

```python
from cfb_system_maker.models import SystemFilter
from cfb_system_maker.normalize import normalize_games
from cfb_system_maker.sample_data import SAMPLE_GAMES_2023, SAMPLE_LINES_2023
from cfb_system_maker.storage import save_processed_games, save_system
from cfb_system_maker.web import create_app


def _setup(tmp_path):
    games = normalize_games(SAMPLE_GAMES_2023, SAMPLE_LINES_2023, provider="consensus")
    save_processed_games(tmp_path, games)
    save_system("home-favs", SystemFilter(side="home", favorite=True), tmp_path)
    save_system("away-dogs", SystemFilter(side="away", underdog=True), tmp_path)
    return create_app(tmp_path)


def test_compare_picker_lists_saved_systems(tmp_path):
    app = _setup(tmp_path)
    html = app.test_client().get("/compare").get_data(as_text=True)
    assert "home-favs" in html
    assert "away-dogs" in html


def test_compare_renders_metrics_per_selected_system(tmp_path):
    app = _setup(tmp_path)
    html = app.test_client().get("/compare?system=home-favs&system=away-dogs").get_data(as_text=True)
    assert "Hit rate" in html
    assert "ROI" in html
    assert "home-favs" in html
    assert "away-dogs" in html


def test_compare_skips_unknown_system_names(tmp_path):
    app = _setup(tmp_path)
    response = app.test_client().get("/compare?system=home-favs&system=does-not-exist")
    assert response.status_code == 200
    assert "home-favs" in response.get_data(as_text=True)


def test_compare_missing_data_state(tmp_path):
    app = create_app(tmp_path)
    html = app.test_client().get("/compare").get_data(as_text=True)
    assert "No processed data" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_web_compare.py -v`
Expected: FAIL — 404 responses (`/compare` route does not exist)

- [ ] **Step 3: Implement**

1. `web.py` — add the route inside `create_app`, after the `save` route:

```python
    @app.get("/compare")
    def compare():
        try:
            games = load_processed_games(app.config["DATA_DIR"])
        except FileNotFoundError:
            return render_template("compare.html", error="missing_data", rows=[], selected=[], saved_systems=[])

        feature_map = _try_load_features(app.config["DATA_DIR"])
        selected = request.args.getlist("system")
        rows = []
        for name in selected:
            try:
                system = load_system(name, app.config["DATA_DIR"])
            except FileNotFoundError:
                continue
            result = run_backtest(games, system, feature_map=feature_map)
            rows.append({"name": name, "system": system, "result": result})
        return render_template(
            "compare.html",
            error=None,
            rows=rows,
            selected=selected,
            saved_systems=list_systems(app.config["DATA_DIR"]),
        )
```

2. Create `cfb_system_maker/templates/compare.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Compare Systems - CFB System Maker</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='styles.css') }}">
  </head>
  <body>
    <main class="app-shell compare-page">
      <section class="workspace">
        <header class="workspace-header">
          <div>
            <h2>Compare Systems</h2>
            <p><a href="{{ url_for('index') }}">&larr; Back to backtester</a></p>
          </div>
        </header>

        {% if error == "missing_data" %}
          <div class="empty-state">
            <h2>No processed data found</h2>
            <p>Run <code>python -m cfb_system_maker build --season 2023 --data-dir data</code>, then refresh.</p>
          </div>
        {% else %}
          <form method="get" class="compare-picker">
            {% for name in saved_systems %}
              <label class="check">
                <input type="checkbox" name="system" value="{{ name }}" {% if name in selected %}checked{% endif %}> {{ name }}
              </label>
            {% else %}
              <p class="no-saved-systems">No saved systems yet - save one from the backtester first.</p>
            {% endfor %}
            {% if saved_systems %}<button type="submit">Compare</button>{% endif %}
          </form>

          {% if rows %}
          <section class="table-wrap">
            <table class="compare-table">
              <thead>
                <tr><th>Metric</th>{% for row in rows %}<th>{{ row.name }}</th>{% endfor %}</tr>
              </thead>
              <tbody>
                <tr><td>Bet</td>{% for row in rows %}<td>{{ row.system.bet_type }} / {{ row.system.total_side if row.system.bet_type == 'total' else row.system.side }}</td>{% endfor %}</tr>
                <tr><td>Bets</td>{% for row in rows %}<td>{{ row.result.bets }}</td>{% endfor %}</tr>
                <tr><td>W-L-P</td>{% for row in rows %}<td>{{ row.result.wins }}-{{ row.result.losses }}-{{ row.result.pushes }}</td>{% endfor %}</tr>
                <tr><td>Hit rate</td>{% for row in rows %}<td>{{ "%.2f%%"|format(row.result.hit_rate * 100) }}</td>{% endfor %}</tr>
                <tr><td>ROI</td>{% for row in rows %}<td class="{{ 'positive' if row.result.roi > 0 else 'negative' if row.result.roi < 0 else '' }}">{{ "%.2f%%"|format(row.result.roi * 100) }}</td>{% endfor %}</tr>
                <tr><td>Profit</td>{% for row in rows %}<td>{{ "%.4f"|format(row.result.profit) }}</td>{% endfor %}</tr>
                <tr><td>Edge</td>{% for row in rows %}<td>{{ "%.2f%%"|format(row.result.stats.edge * 100) }}</td>{% endfor %}</tr>
                <tr><td>Wilson CI</td>{% for row in rows %}<td>{{ "%.1f"|format(row.result.stats.wilson_low * 100) }}-{{ "%.1f"|format(row.result.stats.wilson_high * 100) }}%</td>{% endfor %}</tr>
                <tr><td>p-value</td>{% for row in rows %}<td>{{ "%.4f"|format(row.result.stats.p_value) }}</td>{% endfor %}</tr>
                <tr><td>ROI t-stat</td>{% for row in rows %}<td>{{ "%.2f"|format(row.result.stats.roi_t_stat) }}</td>{% endfor %}</tr>
                <tr><td>Streaks</td>{% for row in rows %}<td>W{{ row.result.stats.max_win_streak }} / L{{ row.result.stats.max_loss_streak }}</td>{% endfor %}</tr>
                <tr><td>Sample</td>{% for row in rows %}<td>{{ "Low n" if row.result.stats.low_sample else "OK" }}</td>{% endfor %}</tr>
              </tbody>
            </table>
          </section>
          {% endif %}
        {% endif %}
      </section>
    </main>
  </body>
</html>
```

3. `templates/index.html` — in the `saved-systems` section, before `</section>`:

```html
          <p class="compare-link"><a href="{{ url_for('compare') }}">Compare saved systems &rarr;</a></p>
```

4. `styles.css` — append:

```css
.compare-page .workspace {
  width: 100%;
}
.compare-picker {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  margin-bottom: 16px;
}
.compare-table th,
.compare-table td {
  text-align: left;
}
.compare-link {
  margin-top: 8px;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_web_compare.py tests/test_web.py -v`
Expected: all pass

- [ ] **Step 5: Full suite + commit**

Run: `python -m pytest`
Expected: all pass

```bash
git add cfb_system_maker/web.py cfb_system_maker/templates/compare.html cfb_system_maker/templates/index.html cfb_system_maker/static/styles.css tests/test_web_compare.py
git commit -m "feat: add compare-saved-systems view"
```

---

### Task 12: Documentation + live-data verification

**Files:**
- Modify: `CLAUDE.md` (commands + conventions), `docs/superpowers/specs/2026-06-13-web-feature-filters-design.md` (out-of-scope section status)

**Interfaces:** none — docs only, plus a manual end-to-end check against real data.

- [ ] **Step 1: Update CLAUDE.md**

In the Commands block, after the `build` line, add:

```powershell
python -m cfb_system_maker enrich --data-dir data   # join registry features -> data/processed/features.json (run after build)
```

In "Key conventions", append:

```markdown
- **Running season-to-date stats** (`running_stats.py`, source kind `computed_running`): values are entering-game — computed from that team's strictly-prior games in the same season, ordered by raw `startDate` (fallback: week). First game of a season → `games_played=0`, percentages/averages `None` (which fail closed as filters). Never fold a game's own result into its own features.
- **Sidecar `_meta`**: `features.json` is `{"_meta": {registry_version, game_count, generated_at}, "games": {...}}`. `features.registry_version()` hashes sorted registry keys; the web UI warns when the sidecar was built by an older registry. Legacy flat sidecars still load.
- Web has `/compare` — pick saved systems, one `run_backtest` column each.
```

- [ ] **Step 2: Mark the phase-2 items delivered in the design doc**

In `docs/superpowers/specs/2026-06-13-web-feature-filters-design.md`, "Out of scope (phase 2+)" first bullet, append ` — **implemented 2026-07-16** (see docs/superpowers/plans/2026-07-16-web-app-phase-2.md)`.

- [ ] **Step 3: Live end-to-end verification (real data)**

```powershell
python -m cfb_system_maker enrich --data-dir data
```

Expected: writes `data/processed/features.json` without errors. Spot-check (PowerShell):

```powershell
python -c "from cfb_system_maker.enrich import load_features, load_features_meta; f = load_features('data'); m = load_features_meta('data'); print(m); row = next(iter(f.values())); print({k: row[k] for k in sorted(row) if 'running' in k or k.startswith('venue')})"
```

Expected: `_meta` prints with current `registry_version`; a game row shows `home_running_*`/`away_running_*` and `venue_*` keys with plausible values (early-season games show `0`/`None`).

Then `python -m cfb_system_maker web --data-dir data`, open `http://127.0.0.1:5000`:
- "Season To Date" group renders between Pregame and Team Preseason, with min/max hints.
- Filter `Win % (to date) ≥ 0.75` on Bet-side: bet count drops, coverage panel appears.
- `/compare` with two saved systems shows the metric table.

- [ ] **Step 4: Full suite + commit**

Run: `python -m pytest`
Expected: all pass

```bash
git add CLAUDE.md docs/superpowers/specs/2026-06-13-web-feature-filters-design.md
git commit -m "docs: document running-stats layer, _meta sidecar, compare view"
```

---

## Deferred (explicitly out of this plan)

- **Season-final snapshot fields** (FPI, SP+, season Elo file, `records`, `teams_ats`, `adjustedTeamMetrics`): still lookahead. The running layer replaces the honest subset (W-L/ATS/PPA); true point-in-time FPI/SP+ needs historical weekly snapshots CFBD doesn't provide in the scraped files.
- **Weekly poll ranks** (`rankings_{season}.json` is week-stamped and pregame-honest — good phase-3 candidate via a `(season, week, team)` join).
- **CLI exposure of feature filters** (web stays the rich surface).
- All standing YAGNI cuts (see Global Constraints).
