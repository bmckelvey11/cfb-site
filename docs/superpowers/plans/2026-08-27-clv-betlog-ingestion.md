# Bet-log Ingestion + CLV Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import an Action Network bet-history CSV export, compute CLV (closing-line value) against CFBD's closing lines, and surface it as a real page in the app — turning `docs/clv-analysis.md`'s one-off finding (+0.29 pts mean CLV, p=0.00225, n=344) into a durable, reusable feature.

**Architecture:** Three new modules following existing conventions: `team_abbreviations.py` (AN↔CFBD team-name map), `betlog.py` (CSV parsing, filtering, game matching, CSV storage), `clv.py` (pure CLV math + aggregate stats). Plus a `betlog import` CLI subcommand and a `GET /betlog` Flask route/template. No changes to `GameRecord`, `games.csv`, or any existing storage contract — `data/betlog/bets.csv` is a wholly separate file, same pattern as `upcoming.csv`.

**Tech Stack:** Python stdlib `csv`/`dataclasses` (matches `storage.py`'s existing style — no pandas), Flask/Jinja (matches `web.py`), vanilla SVG for the chart (matches `_cumulative_chart`).

## Global Constraints

- No changes to `GameRecord` field order or `games.csv` (CSV schema stability, per project CLAUDE.md).
- `cfbd-python/` is vendored, never edited, never treated as our code.
- No `client` pytest fixture exists anywhere in this codebase — every test builds `app = create_app(data_dir=tmp_path); client = app.test_client()` inline. Do not introduce a fixture.
- Bet scope for this plan: spread and total bets, pre-game only (Action Network's `Period == "game"`). Moneyline, live, first/second-half bets are out of scope — skipped and counted, not silently dropped.
- Unmatched or malformed rows are skipped, counted, and reported by the import command — never fatal, never silently discarded without a count.
- Re-running `betlog import` with a fresher export is idempotent: new bets are added, already-imported bets are left untouched (dedupe key below).
- All new href/text rendering uses `urlencode`/Jinja auto-escape, never `|safe` (existing project convention).

## Ground truth from the real Action Network export (verified, not assumed)

Read directly from a real personal export (`~/Downloads/history.csv`, 579 data rows, kept outside the repo — a synthetic fixture is used in tests instead):

- **The file's actual first line is a stray `data:text/csv;charset=utf-8,` browser-artifact line** before the real header. The real header (line 2) is: `League,Start Time,Game,Pick Desc,Type,Period,Odds,Odds/Spread/Total,Result,Units Wagered,Units Net,Money Wagered,Money Net,Tag` (14 columns).
- **`Period` values seen:** `game` (pre-game — what this plan imports), `live`, `firsthalf`, `secondhalf`.
- **`Type` values seen for in-scope bets:** `spread_home`, `spread_away`, `over`, `under`. (Also seen but out of scope: `ml_home`, `ml_away`, `home_over`, `away_over`, `custom`.)
- **`Game` field** is free text like `NAVY @ ND` (away @ home, confirmed by cross-checking `Pick Desc` — e.g. row `NAVY @ ND` with pick `NAVY +20.5 -110` and `Type=spread_away` means NAVY is away and the bet is on the away side).
- **`Start Time`** is ISO-8601 UTC with a trailing `Z`, e.g. `2023-08-26T23:00:00.000Z`.
- **`Odds/Spread/Total`** is the numeric line the bettor took (e.g. `20.5`, `-8`, `51` for a total).
- **The file has real malformed rows**: out of 579 data rows, 564 have exactly 14 fields; **15 rows have 0, 1, 10, or 15 fields** (a real quoting/escaping bug in Action Network's own export, likely from an unescaped comma in a free-text field). The importer must skip these without crashing, and count them separately from "out of scope" rows.

## File Structure

```
cfb_system_maker/
  team_abbreviations.py       # NEW — AN team name -> CFBD team name map
  betlog.py                    # NEW — CSV parsing, filtering, matching, storage
  clv.py                       # NEW — CLV math, aggregate stats, chart data
  cli.py                       # MODIFY — add `betlog import` subcommand
  web.py                       # MODIFY — add GET /betlog route
  templates/
    betlog.html                 # NEW — bet log page
    dashboard.html               # MODIFY — add "Bet Log" link in dash-header
  static/styles.css             # MODIFY — add betlog table/traffic-light styles
tests/
  test_team_abbreviations.py    # NEW
  test_betlog.py                 # NEW
  test_clv.py                    # NEW
  test_web_betlog.py              # NEW
  fixtures/
    betlog_sample.csv             # NEW — synthetic fixture, not the real personal export
```

---

### Task 1: Team abbreviation map

**Files:**
- Create: `cfb_system_maker/team_abbreviations.py`
- Test: `tests/test_team_abbreviations.py`

**Interfaces:**
- Produces: `AN_TO_CFBD: dict[str, str]` (module-level dict, Action Network short name → CFBD full team name), `resolve_team(an_name: str) -> str | None` (looks up `AN_TO_CFBD`, returns `None` if not found — never raises).

- [ ] **Step 1: Write the failing test**

Create `tests/test_team_abbreviations.py`:

```python
from cfb_system_maker.team_abbreviations import AN_TO_CFBD, resolve_team


def test_resolve_known_team_returns_cfbd_name():
    assert resolve_team("NAVY") == "Navy"
    assert resolve_team("ND") == "Notre Dame"
    assert resolve_team("OHIO") == "Ohio"
    assert resolve_team("SDSU") == "San Diego State"


def test_resolve_unknown_team_returns_none():
    assert resolve_team("NOT_A_REAL_TEAM_XYZ") is None


def test_an_to_cfbd_has_no_duplicate_keys_with_different_casing():
    lowered = [key.lower() for key in AN_TO_CFBD]
    assert len(lowered) == len(set(lowered))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_team_abbreviations.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cfb_system_maker.team_abbreviations'`

- [ ] **Step 3: Write the implementation**

Create `cfb_system_maker/team_abbreviations.py`. Seed the map with a small, real, verifiable starter set built from the actual export sample above (`NAVY`, `ND`, `OHIO`, `SDSU`, `MASS`, `NMSU`, `GB`, `DAL`, `HOU`, `LA`, `LAC`, `WAS` are all seen in the real export's `Game` column) — this list will grow over time as more teams are seen in real imports; unresolvable teams are reported by `betlog import`, not silently guessed at.

```python
"""Action Network team short-name -> CFBD full team-name map.

Action Network's bet-history CSV export uses short team names/abbreviations
in its free-text `Game` column (e.g. "NAVY @ ND"). CFBD's `GameRecord.home_team`
/`away_team` use full names (e.g. "Notre Dame"). This map bridges the two so
imported bets can be joined to a CFBD game_id.

Grows incrementally: `betlog import` reports any Game-column team name it
can't resolve, and you add it here once you've confirmed the correct CFBD
name (usually via games.csv for that date).
"""

from __future__ import annotations

AN_TO_CFBD: dict[str, str] = {
    "NAVY": "Navy",
    "ND": "Notre Dame",
    "OHIO": "Ohio",
    "SDSU": "San Diego State",
    "MASS": "Massachusetts",
    "NMSU": "New Mexico State",
    "GB": "Green Bay",
    "DAL": "Dallas",
    "HOU": "Houston",
    "LA": "Los Angeles",
    "LAC": "Los Angeles Chargers",
    "WAS": "Washington",
}


def resolve_team(an_name: str) -> str | None:
    """Look up an Action Network team short name. Returns None if unknown."""
    return AN_TO_CFBD.get(an_name.strip())
```

Note: `GB`/`DAL`/`HOU`/`LA`/`LAC`/`WAS` above are placeholders seen in one row of malformed/NFL-looking data in the sample export (the CSV export can contain non-CFB bets if the account also bets other sports) — Task 2's importer must filter to `League == "ncaaf"` rows before attempting any team resolution, so these particular entries may never actually be looked up in practice. Keep them in the map anyway since they cost nothing and the map's job is coverage, not minimalism-at-the-cost-of-a-future-KeyError.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_team_abbreviations.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add cfb_system_maker/team_abbreviations.py tests/test_team_abbreviations.py
git commit -m "feat(betlog): AN->CFBD team abbreviation map"
```

---

### Task 2: Bet-log CSV parsing and filtering

**Files:**
- Create: `cfb_system_maker/betlog.py`
- Create: `tests/fixtures/betlog_sample.csv`
- Test: `tests/test_betlog.py`

**Interfaces:**
- Consumes: `resolve_team` from `cfb_system_maker.team_abbreviations` (Task 1).
- Produces:
  - `@dataclass(frozen=True) class BetLogRecord` with fields `game_id: int`, `date: str`, `home_team: str`, `away_team: str`, `bet_type: str` (`"spread"` or `"total"`), `side: str` (`"home"`, `"away"`, `"over"`, `"under"`), `line_taken: float`, `odds: int`, `result: str`, `units_wagered: float`, `units_net: float`.
  - `parse_betlog_csv(path: str | Path) -> ParsedImport` where `ParsedImport` is a `@dataclass(frozen=True)` with `in_scope: list[RawBetRow]`, `out_of_scope_count: int`, `malformed_count: int`. `RawBetRow` is an intermediate `@dataclass(frozen=True)` with the raw parsed CSV fields (`league: str`, `start_time: str`, `game: str`, `bet_type: str`, `side: str`, `line_taken: float`, `odds: int`, `result: str`, `units_wagered: float`, `units_net: float`) — not yet matched to a CFBD game.
  - `match_to_game(row: RawBetRow, games_by_date: dict[str, list[GameRecord]]) -> BetLogRecord | None` — resolves `row.game`'s two team names via `resolve_team`, looks up `games_by_date` for that date, returns a `BetLogRecord` with a real `game_id` on success, `None` if either team is unresolvable or no matching game is found.
  - This task does NOT write to disk — that's Task 3.

- [ ] **Step 1: Create the fixture CSV**

Create `tests/fixtures/betlog_sample.csv` — a small synthetic file matching the real export's exact structure, including the stray first line and one deliberately malformed row (to test the skip-and-count path):

```
data:text/csv;charset=utf-8,
League,Start Time,Game,Pick Desc,Type,Period,Odds,Odds/Spread/Total,Result,Units Wagered,Units Net,Money Wagered,Money Net,Tag
ncaaf,2023-08-26T23:00:00.000Z,OHIO @ SDSU,OHIO +4 -110,spread_away,game,-110,4,loss,1,-1,1000,-1000,
ncaaf,2023-08-26T23:00:00.000Z,OHIO @ SDSU,SDSU -4 -110,spread_home,live,-110,-4,win,1,0.91,1000,910,
ncaaf,2023-09-02T17:00:00.000Z,NAVY @ ND,under 51 -110,under,game,-110,51,win,2,1.82,2000,1820,
ncaaf,2023-09-02T17:00:00.000Z,NAVY @ ND,ND -3.5 -110,spread_home,firsthalf,-110,-3.5,loss,1,-1,1000,-1000,
ncaaf,2023-09-09T20:00:00.000Z,MASS @ NMSU,NMSU ml -180,ml_home,game,-180,0,win,1,0.56,1000,556,
ncaaf,2023-09-09,MASS @ NMSU,over 55 -110,over,game,-110,55,win,1,0.91,1000,910,extra,field,here
```

(Row 7's trailing extra comma-separated values simulate the real export's malformed-row bug — an unescaped comma pushing the field count past 14.)

- [ ] **Step 2: Write the failing test**

Create `tests/test_betlog.py`:

```python
from pathlib import Path

from cfb_system_maker.betlog import BetLogRecord, match_to_game, parse_betlog_csv
from cfb_system_maker.models import GameRecord

FIXTURE = Path(__file__).parent / "fixtures" / "betlog_sample.csv"


def test_parse_skips_stray_first_line_and_reads_header():
    result = parse_betlog_csv(FIXTURE)
    assert result.in_scope, "expected at least one in-scope row"


def test_parse_filters_to_pregame_spread_and_total():
    result = parse_betlog_csv(FIXTURE)
    bet_types = {row.bet_type for row in result.in_scope}
    assert bet_types == {"spread_away", "under"}
    # excluded: the live spread_home, the firsthalf spread_home, the ml_home,
    # and the malformed trailing row (over, but malformed) -- 6 data rows in,
    # 2 in scope, 1 malformed, 3 out of scope (live/firsthalf/moneyline)
    assert len(result.in_scope) == 2
    assert result.malformed_count == 1
    assert result.out_of_scope_count == 3


def test_match_to_game_resolves_known_teams():
    row = parse_betlog_csv(FIXTURE).in_scope[0]  # OHIO @ SDSU spread_away
    games_by_date = {
        "2023-08-26": [
            GameRecord(
                game_id=999, season=2023, week=1, season_type="regular",
                home_team="San Diego State", away_team="Ohio",
                home_conference="Mountain West", away_conference="MAC",
                neutral_site=False, conference_game=False, spread=-4.0,
                total=51.0, provider="consensus", home_points=None, away_points=None,
            )
        ]
    }
    bet = match_to_game(row, games_by_date)
    assert bet is not None
    assert bet.game_id == 999
    assert bet.bet_type == "spread"
    assert bet.side == "away"
    assert bet.line_taken == 4.0


def test_match_to_game_returns_none_for_unresolvable_team():
    row = parse_betlog_csv(FIXTURE).in_scope[0]
    games_by_date = {"2023-08-26": []}  # no games that day
    assert match_to_game(row, games_by_date) is None
```

(Adjust `GameRecord`'s constructor call in the test to match its actual current field set — read `cfb_system_maker/models.py`'s `GameRecord` dataclass definition first and use its real field names/order; the fields listed above are illustrative of the shape, not a guaranteed-exact signature.)

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_betlog.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cfb_system_maker.betlog'`

- [ ] **Step 4: Write the implementation**

Create `cfb_system_maker/betlog.py`:

```python
"""Action Network bet-history CSV import: parsing, filtering, and matching
bets to CFBD games. See docs/superpowers/specs/2026-08-27-clv-betlog-ingestion-design.md.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cfb_system_maker.models import GameRecord
from cfb_system_maker.team_abbreviations import resolve_team

_IN_SCOPE_TYPES = {"spread_home", "spread_away", "over", "under"}
_IN_SCOPE_PERIOD = "game"


@dataclass(frozen=True)
class RawBetRow:
    league: str
    start_time: str
    game: str
    bet_type: str
    side: str
    line_taken: float
    odds: int
    result: str
    units_wagered: float
    units_net: float


@dataclass(frozen=True)
class ParsedImport:
    in_scope: list[RawBetRow]
    out_of_scope_count: int
    malformed_count: int


@dataclass(frozen=True)
class BetLogRecord:
    game_id: int
    date: str
    home_team: str
    away_team: str
    bet_type: str  # "spread" | "total"
    side: str  # "home" | "away" | "over" | "under"
    line_taken: float
    odds: int
    result: str
    units_wagered: float
    units_net: float


_EXPECTED_FIELD_COUNT = 14


def parse_betlog_csv(path: str | Path) -> ParsedImport:
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()

    # Real exports have a stray `data:text/csv;charset=utf-8,` artifact line
    # before the real header. Detect and skip it if present.
    start = 0
    if lines and lines[0].strip().startswith("data:text/csv"):
        start = 1

    reader = csv.reader(lines[start:])
    header = next(reader)
    if len(header) != _EXPECTED_FIELD_COUNT:
        raise ValueError(f"unexpected header shape: {header!r}")

    in_scope: list[RawBetRow] = []
    out_of_scope = 0
    malformed = 0

    for raw_row in reader:
        if len(raw_row) != _EXPECTED_FIELD_COUNT:
            malformed += 1
            continue
        row = dict(zip(header, raw_row))
        if row.get("League") != "ncaaf":
            out_of_scope += 1
            continue
        bet_type = row.get("Type", "")
        period = row.get("Period", "")
        if bet_type not in _IN_SCOPE_TYPES or period != _IN_SCOPE_PERIOD:
            out_of_scope += 1
            continue
        try:
            line_taken = float(row["Odds/Spread/Total"])
            odds = int(float(row["Odds"]))
            units_wagered = float(row["Units Wagered"])
            units_net = float(row["Units Net"])
        except (KeyError, ValueError):
            malformed += 1
            continue
        in_scope.append(
            RawBetRow(
                league=row["League"],
                start_time=row["Start Time"],
                game=row["Game"],
                bet_type=bet_type,
                side=bet_type,  # side derived properly in match_to_game
                line_taken=line_taken,
                odds=odds,
                result=row.get("Result", ""),
                units_wagered=units_wagered,
                units_net=units_net,
            )
        )

    return ParsedImport(in_scope=in_scope, out_of_scope_count=out_of_scope, malformed_count=malformed)


def _split_game_field(game: str) -> tuple[str, str] | None:
    """'NAVY @ ND' -> ('NAVY', 'ND') meaning (away, home)."""
    parts = [p.strip() for p in game.split("@")]
    if len(parts) != 2:
        return None
    return parts[0], parts[1]


def match_to_game(row: RawBetRow, games_by_date: dict[str, list[GameRecord]]) -> BetLogRecord | None:
    teams = _split_game_field(row.game)
    if teams is None:
        return None
    away_short, home_short = teams
    away_cfbd = resolve_team(away_short)
    home_cfbd = resolve_team(home_short)
    if away_cfbd is None or home_cfbd is None:
        return None

    date = row.start_time[:10]  # "2023-08-26T23:00:00.000Z" -> "2023-08-26"
    candidates = games_by_date.get(date, [])
    game = next(
        (g for g in candidates if g.home_team == home_cfbd and g.away_team == away_cfbd),
        None,
    )
    if game is None:
        return None

    if row.bet_type in ("spread_home", "spread_away"):
        bet_type = "spread"
        side = "home" if row.bet_type == "spread_home" else "away"
    else:
        bet_type = "total"
        side = row.bet_type  # "over" | "under"

    return BetLogRecord(
        game_id=game.game_id,
        date=date,
        home_team=home_cfbd,
        away_team=away_cfbd,
        bet_type=bet_type,
        side=side,
        line_taken=row.line_taken,
        odds=row.odds,
        result=row.result,
        units_wagered=row.units_wagered,
        units_net=row.units_net,
    )
```

Adjust `GameRecord` field-name references (`game_id`, `home_team`, `away_team`) to match the real dataclass if they differ from these assumed names — confirm against `cfb_system_maker/models.py` before finalizing.

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_betlog.py -v`
Expected: PASS (4 passed). If `test_parse_filters_to_pregame_spread_and_total`'s exact counts don't match, adjust the fixture or the test's expected counts to agree with each other and with the actual filtering logic — the counts must be genuinely derived from the fixture's content, not fudged to pass.

- [ ] **Step 6: Commit**

```bash
git add cfb_system_maker/betlog.py tests/test_betlog.py tests/fixtures/betlog_sample.csv
git commit -m "feat(betlog): parse and filter Action Network CSV export, match to CFBD games"
```

---

### Task 3: Bet-log storage (merge/dedupe) and CLI import command

**Files:**
- Modify: `cfb_system_maker/betlog.py` (add storage functions)
- Modify: `cfb_system_maker/cli.py` (add `betlog import` subcommand)
- Test: `tests/test_betlog.py` (add storage + CLI tests)

**Interfaces:**
- Consumes: `BetLogRecord`, `parse_betlog_csv`, `match_to_game` from Task 2; `load_raw_json` from `cfb_system_maker.storage` (existing, confirmed signature `load_raw_json(data_dir, "games", season) -> list[dict]`, reads `data/raw/games_{season}.json`).
- Produces:
  - `load_betlog(data_dir: str | Path) -> list[BetLogRecord]` — reads `data/betlog/bets.csv`, returns `[]` if the file doesn't exist.
  - `save_betlog(records: list[BetLogRecord], data_dir: str | Path) -> None` — writes the full list to `data/betlog/bets.csv`, overwriting (the merge/dedupe happens in the caller before this is invoked, matching `storage.py`'s existing convention of dumb writers + smart callers).
  - `import_betlog(csv_path: str | Path, data_dir: str | Path) -> ImportSummary` where `ImportSummary` is `@dataclass(frozen=True)` with `total_rows: int`, `in_scope: int`, `already_imported: int`, `newly_imported: int`, `matched: int`, `unmatched: list[str]` (each a human-readable `"date team @ team"` string), `malformed: int`.
  - `betlog import --csv <path> --data-dir data` CLI subcommand.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_betlog.py`:

```python
from cfb_system_maker.betlog import ImportSummary, import_betlog, load_betlog, save_betlog


def _make_bet(game_id, date, home, away, bet_type="spread", side="home"):
    return BetLogRecord(
        game_id=game_id, date=date, home_team=home, away_team=away,
        bet_type=bet_type, side=side, line_taken=-3.5, odds=-110,
        result="win", units_wagered=1.0, units_net=0.91,
    )


def test_save_and_load_betlog_round_trips(tmp_path):
    records = [_make_bet(1, "2023-09-01", "Notre Dame", "Navy")]
    save_betlog(records, tmp_path)
    loaded = load_betlog(tmp_path)
    assert loaded == records


def test_load_betlog_missing_file_returns_empty_list(tmp_path):
    assert load_betlog(tmp_path) == []


def test_import_betlog_dedupes_on_rerun(tmp_path, monkeypatch):
    # First import: one bet lands.
    existing = [_make_bet(1, "2023-09-01", "Notre Dame", "Navy")]
    save_betlog(existing, tmp_path)

    def fake_parse(path):
        return ParsedImport(
            in_scope=[
                RawBetRow(
                    league="ncaaf", start_time="2023-09-01T17:00:00.000Z",
                    game="NAVY @ ND", bet_type="spread_home", side="spread_home",
                    line_taken=-3.5, odds=-110, result="win",
                    units_wagered=1.0, units_net=0.91,
                ),
                RawBetRow(
                    league="ncaaf", start_time="2023-09-08T17:00:00.000Z",
                    game="NAVY @ ND", bet_type="spread_home", side="spread_home",
                    line_taken=-7.0, odds=-110, result="loss",
                    units_wagered=1.0, units_net=-1.0,
                ),
            ],
            out_of_scope_count=0,
            malformed_count=0,
        )

    def fake_match(row, games_by_date):
        game_id = 1 if row.start_time.startswith("2023-09-01") else 2
        return BetLogRecord(
            game_id=game_id, date=row.start_time[:10],
            home_team="Notre Dame", away_team="Navy",
            bet_type="spread", side="home", line_taken=row.line_taken,
            odds=row.odds, result=row.result,
            units_wagered=row.units_wagered, units_net=row.units_net,
        )

    monkeypatch.setattr("cfb_system_maker.betlog.parse_betlog_csv", fake_parse)
    monkeypatch.setattr("cfb_system_maker.betlog.match_to_game", fake_match)
    monkeypatch.setattr("cfb_system_maker.betlog._build_games_by_date", lambda data_dir, in_scope: {})

    summary = import_betlog("fake.csv", tmp_path)

    assert summary.total_rows == 2
    assert summary.in_scope == 2
    assert summary.already_imported == 1
    assert summary.newly_imported == 1
    assert summary.matched == 2
    assert summary.unmatched == []

    all_bets = load_betlog(tmp_path)
    assert len(all_bets) == 2  # the pre-existing bet plus the one new one
```

Also add a CLI test to `tests/test_cli.py` (read the file first for the exact invocation convention already established there — `main([...])`, `tmp_path` for `--data-dir`):

```python
def test_betlog_import_command_reports_summary(tmp_path, monkeypatch, capsys):
    from cfb_system_maker import cli

    def fake_import(csv_path, data_dir):
        from cfb_system_maker.betlog import ImportSummary
        return ImportSummary(
            total_rows=580, in_scope=344, already_imported=0,
            newly_imported=344, matched=338, unmatched=["2023-09-01 XYZ @ ABC"],
            malformed=15,
        )

    monkeypatch.setattr("cfb_system_maker.cli.import_betlog", fake_import)
    exit_code = cli.main(["betlog", "import", "--csv", "fake.csv", "--data-dir", str(tmp_path)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "344" in captured.out
    assert "338" in captured.out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_betlog.py tests/test_cli.py -k betlog -v`
Expected: FAIL (functions/subcommand don't exist yet)

- [ ] **Step 3: Write the implementation**

Add to `cfb_system_maker/betlog.py`:

```python
from cfb_system_maker.storage import load_raw_json


_BETLOG_FIELDS = [
    "game_id", "date", "home_team", "away_team", "bet_type", "side",
    "line_taken", "odds", "result", "units_wagered", "units_net",
]


@dataclass(frozen=True)
class ImportSummary:
    total_rows: int
    in_scope: int
    already_imported: int
    newly_imported: int
    matched: int
    unmatched: list[str]
    malformed: int


def _dedupe_key(bet: BetLogRecord) -> tuple:
    return (bet.date, bet.home_team, bet.away_team, bet.bet_type, bet.side, bet.odds)


def load_betlog(data_dir: str | Path) -> list[BetLogRecord]:
    path = Path(data_dir) / "betlog" / "bets.csv"
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [
            BetLogRecord(
                game_id=int(row["game_id"]),
                date=row["date"],
                home_team=row["home_team"],
                away_team=row["away_team"],
                bet_type=row["bet_type"],
                side=row["side"],
                line_taken=float(row["line_taken"]),
                odds=int(row["odds"]),
                result=row["result"],
                units_wagered=float(row["units_wagered"]),
                units_net=float(row["units_net"]),
            )
            for row in reader
        ]


def save_betlog(records: list[BetLogRecord], data_dir: str | Path) -> None:
    directory = Path(data_dir) / "betlog"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "bets.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_BETLOG_FIELDS)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "game_id": record.game_id, "date": record.date,
                    "home_team": record.home_team, "away_team": record.away_team,
                    "bet_type": record.bet_type, "side": record.side,
                    "line_taken": record.line_taken, "odds": record.odds,
                    "result": record.result, "units_wagered": record.units_wagered,
                    "units_net": record.units_net,
                }
            )


def import_betlog(csv_path: str | Path, data_dir: str | Path) -> ImportSummary:
    parsed = parse_betlog_csv(csv_path)
    total_rows = len(parsed.in_scope) + parsed.out_of_scope_count + parsed.malformed_count

    games_by_date = _build_games_by_date(data_dir, parsed.in_scope)

    existing = load_betlog(data_dir)
    existing_keys = {_dedupe_key(bet) for bet in existing}

    matched_bets: list[BetLogRecord] = []
    unmatched: list[str] = []
    for row in parsed.in_scope:
        bet = match_to_game(row, games_by_date)
        if bet is None:
            unmatched.append(f"{row.start_time[:10]} {row.game}")
            continue
        matched_bets.append(bet)

    new_bets = [bet for bet in matched_bets if _dedupe_key(bet) not in existing_keys]
    already_imported = len(matched_bets) - len(new_bets)

    save_betlog(existing + new_bets, data_dir)

    return ImportSummary(
        total_rows=total_rows,
        in_scope=len(parsed.in_scope),
        already_imported=already_imported,
        newly_imported=len(new_bets),
        matched=len(matched_bets),
        unmatched=unmatched,
        malformed=parsed.malformed_count,
    )
```

**Confirmed schema gap, not a hedge:** `GameRecord` (in `cfb_system_maker/models.py`) has NO date field at all — its fields are `game_id, season, week, home_team, away_team, home_conference, away_conference, home_points, away_points, provider, spread, total`. Matching bets to games by date is therefore not possible from `games.csv`/`GameRecord` alone. Use the raw games JSON instead, which does carry `startDate` per game (confirmed: `load_raw_json(data_dir, "games", season)` reads `data/raw/games_{season}.json`, and each entry has `id`, `startDate`, `homeTeam`, `awayTeam` fields directly — same shape already confirmed for `lines_{season}.json`). Add this helper to `betlog.py`:

```python
def _build_games_by_date(data_dir: str | Path, in_scope: list[RawBetRow]) -> dict[str, list[GameRecord]]:
    seasons_needed = {int(row.start_time[:4]) for row in in_scope}
    games_by_date: dict[str, list[GameRecord]] = {}
    for season in seasons_needed:
        try:
            raw_games = load_raw_json(data_dir, "games", season)
        except FileNotFoundError:
            continue
        for raw in raw_games:
            date = str(raw.get("startDate", ""))[:10]
            if not date:
                continue
            games_by_date.setdefault(date, []).append(
                GameRecord(
                    game_id=raw["id"], season=season, week=raw.get("week", 0),
                    home_team=raw.get("homeTeam", ""), away_team=raw.get("awayTeam", ""),
                    home_conference=raw.get("homeConference"), away_conference=raw.get("awayConference"),
                    home_points=raw.get("homePoints"), away_points=raw.get("awayPoints"),
                    provider=None, spread=None, total=None,
                )
            )
    return games_by_date
```

Adjust the raw JSON field names (`homeTeam`, `awayTeam`, `homeConference`, etc.) to match the real keys in a sample `data/raw/games_{season}.json` file if they differ — confirm by reading one such file directly (or reading `cfb_system_maker/normalize.py`'s `normalize_games`, which already parses this exact raw shape into `GameRecord`s, and reuse its field-name lookups rather than guessing new ones).

Add to `cfb_system_maker/cli.py`: import `import_betlog` at the top (`from cfb_system_maker.betlog import import_betlog`), add a handler:

```python
def _betlog_import(args: argparse.Namespace) -> int:
    summary = import_betlog(args.csv, args.data_dir)
    print(f"{summary.total_rows} rows in CSV, {summary.in_scope} in scope (spread/total, pre-game)")
    print(f"{summary.already_imported} already imported, {summary.newly_imported} new")
    print(f"{summary.matched} matched to CFBD games ({len(summary.unmatched)} unmatched)")
    if summary.unmatched:
        print("Unmatched:")
        for item in summary.unmatched:
            print(f"  {item}")
    if summary.malformed:
        print(f"{summary.malformed} malformed rows skipped")
    return 0
```

Wire the dispatch (find `main()`'s if/elif chain and add):

```python
if args.command == "betlog" and args.betlog_command == "import":
    return _betlog_import(args)
```

Add the subparser (find `_build_parser()` and add, modeled on the existing subcommand pattern):

```python
betlog_parser = subparsers.add_parser("betlog")
betlog_subparsers = betlog_parser.add_subparsers(dest="betlog_command", required=True)
betlog_import_parser = betlog_subparsers.add_parser("import")
betlog_import_parser.add_argument("--csv", required=True)
betlog_import_parser.add_argument("--data-dir", default="data")
```

Adjust to match `cli.py`'s actual current structure for how `args.command` is checked and how subparsers are added — read the file first, don't assume this snippet drops in verbatim if the real dispatch mechanism differs.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_betlog.py tests/test_cli.py -k betlog -v`
Expected: PASS. Then run the full suite to confirm no regressions: `python -m pytest -q`

- [ ] **Step 5: Commit**

```bash
git add cfb_system_maker/betlog.py cfb_system_maker/cli.py tests/test_betlog.py tests/test_cli.py
git commit -m "feat(betlog): idempotent storage + \`betlog import\` CLI subcommand"
```

---

### Task 4: CLV computation

**Files:**
- Create: `cfb_system_maker/clv.py`
- Test: `tests/test_clv.py`

**Interfaces:**
- Consumes: `BetLogRecord` from `cfb_system_maker.betlog` (Task 2); `load_raw_json` from `cfb_system_maker.storage` (existing, confirmed signature `load_raw_json(data_dir, "lines", season) -> list[dict]`).
- Produces:
  - `find_closing_line(bet: BetLogRecord, data_dir: str | Path) -> float | None` — loads `data/raw/lines_{season}.json` (season derived from `bet.date`'s year — confirm this assumption against how seasons/dates actually relate in this codebase, since a January bowl game might belong to the prior season), finds the game by `bet.game_id`, applies a provider preference cascade (consensus → DraftKings → Bovada → ESPN Bet → Caesars → William Hill, per `docs/clv-analysis.md`), returns the relevant closing number (`spread` for spread bets, `overUnder` for total bets) or `None` if no usable line is found for any preferred provider. **The returned `spread` is home-relative** (CFBD's raw convention, same as `GameRecord.spread` — see `models.py` and `backtest._side_spread`), NOT side-relative like `bet.line_taken`.
  - `compute_clv(bet: BetLogRecord, closing_line: float) -> float` — CLV in points, positive = line moved in the bettor's favor. For spread bets, `closing_line` is home-relative and must be converted to the bettor's side before comparing against `bet.line_taken` (which is already side-relative, matching how a bettor reads their own ticket).
  - `@dataclass(frozen=True) class ClvStats`: `n: int`, `mean_clv: float`, `t_stat: float`, `std_error: float`.
  - `compute_clv_stats(clv_values: list[float]) -> ClvStats` — reuses the same math as `backtest._roi_stats` (mean, standard error, t-statistic), adapted for a plain list of CLV values instead of ROI returns.
  - `@dataclass(frozen=True) class SeasonClv`: `season: int`, `n: int`, `mean_clv: float`.
  - `compute_clv_by_season(bets_with_clv: list[tuple[BetLogRecord, float]]) -> list[SeasonClv]`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_clv.py`:

```python
from cfb_system_maker.betlog import BetLogRecord
from cfb_system_maker.clv import (
    ClvStats,
    SeasonClv,
    compute_clv,
    compute_clv_by_season,
    compute_clv_stats,
    find_closing_line,
)


def _bet(game_id=1, date="2023-09-01", bet_type="spread", side="away", line_taken=4.0):
    return BetLogRecord(
        game_id=game_id, date=date, home_team="San Diego State", away_team="Ohio",
        bet_type=bet_type, side=side, line_taken=line_taken, odds=-110,
        result="win", units_wagered=1.0, units_net=0.91,
    )


def test_compute_clv_positive_when_line_moved_bettors_way_spread_away():
    # Bettor took the away dog at +6.0. `closing_line` is home-relative
    # (CFBD's raw `spread` convention): home favored by 4 at close =>
    # closing_line = -4.0, which in away-relative terms is +4.0 -- fewer
    # points than the +6.0 our bettor already had. A fresh bettor at close
    # gets a worse number than ours did, so CLV is positive for us.
    bet = _bet(side="away", line_taken=6.0)
    clv = compute_clv(bet, closing_line=-4.0)  # home-relative: home -4.0 => away +4.0
    assert clv == 2.0


def test_compute_clv_negative_when_line_moved_against_bettor():
    # Bettor took away +4.0. Closing home-relative -6.0 => away +6.0, a
    # bigger (better) number for the away side than what the bettor got --
    # a fresh bettor at close does better than ours did, so CLV is negative.
    bet = _bet(side="away", line_taken=4.0)
    clv = compute_clv(bet, closing_line=-6.0)  # home-relative: home -6.0 => away +6.0
    assert clv == -2.0


def test_compute_clv_home_side_inverts_sign_convention():
    # Home bettor took -4.0 (favorite). For the home side, home-relative
    # IS side-relative, so no sign flip applies -- unlike the away tests
    # above. Closing line -6.0 means the favorite grew: a fresh bettor at
    # close must lay 6 points, worse than our bettor's 4. Our bettor got
    # the better number, so CLV is positive: line_taken - closing_line
    # = -4.0 - (-6.0) = 2.0.
    bet = _bet(side="home", line_taken=-4.0)
    clv = compute_clv(bet, closing_line=-6.0)
    assert clv == 2.0


def test_compute_clv_total_over_positive_when_closing_total_higher():
    bet = _bet(bet_type="total", side="over", line_taken=51.0)
    clv = compute_clv(bet, closing_line=54.0)
    assert clv == 3.0


def test_compute_clv_total_under_positive_when_closing_total_lower():
    bet = _bet(bet_type="total", side="under", line_taken=51.0)
    clv = compute_clv(bet, closing_line=48.0)
    assert clv == 3.0


def test_compute_clv_stats_matches_hand_computed_values():
    stats = compute_clv_stats([2.0, -1.0, 3.0, 0.5])
    assert stats.n == 4
    assert stats.mean_clv == 1.125
    assert stats.std_error > 0
    assert stats.t_stat != 0.0


def test_compute_clv_stats_empty_list_returns_zeros():
    stats = compute_clv_stats([])
    assert stats == ClvStats(n=0, mean_clv=0.0, t_stat=0.0, std_error=0.0)


def test_compute_clv_by_season_groups_correctly():
    bet_2023 = _bet(date="2023-09-01")
    bet_2024 = _bet(date="2024-09-01")
    result = compute_clv_by_season([(bet_2023, 2.0), (bet_2024, -1.0), (bet_2024, 3.0)])
    by_season = {r.season: r for r in result}
    assert by_season[2023] == SeasonClv(season=2023, n=1, mean_clv=2.0)
    assert by_season[2024] == SeasonClv(season=2024, n=2, mean_clv=1.0)


def test_find_closing_line_prefers_consensus_provider(tmp_path):
    import json

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    lines_data = [
        {
            "id": 1, "season": 2023,
            "lines": [
                {"provider": "DraftKings", "spread": -3.5, "overUnder": 50.5},
                {"provider": "consensus", "spread": -4.0, "overUnder": 51.0},
            ],
        }
    ]
    (raw_dir / "lines_2023.json").write_text(json.dumps(lines_data))
    bet = _bet(game_id=1, date="2023-09-01", bet_type="spread")
    closing = find_closing_line(bet, tmp_path)
    assert closing == -4.0  # consensus preferred over DraftKings


def test_find_closing_line_falls_back_through_provider_cascade(tmp_path):
    import json

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    lines_data = [
        {
            "id": 1, "season": 2023,
            "lines": [{"provider": "Bovada", "spread": -3.0, "overUnder": None}],
        }
    ]
    (raw_dir / "lines_2023.json").write_text(json.dumps(lines_data))
    bet = _bet(game_id=1, date="2023-09-01", bet_type="spread")
    closing = find_closing_line(bet, tmp_path)
    assert closing == -3.0  # no consensus/DraftKings, cascades down to Bovada


def test_find_closing_line_returns_none_when_no_usable_line(tmp_path):
    import json

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    lines_data = [{"id": 1, "season": 2023, "lines": []}]
    (raw_dir / "lines_2023.json").write_text(json.dumps(lines_data))
    bet = _bet(game_id=1, date="2023-09-01")
    assert find_closing_line(bet, tmp_path) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_clv.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cfb_system_maker.clv'`

- [ ] **Step 3: Write the implementation**

Create `cfb_system_maker/clv.py`:

```python
"""CLV (closing-line value) computation. Pure functions, heavily tested --
matches the style of backtest.py's stats functions. See
docs/superpowers/specs/2026-08-27-clv-betlog-ingestion-design.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from cfb_system_maker.betlog import BetLogRecord
from cfb_system_maker.storage import load_raw_json

_PROVIDER_CASCADE = ["consensus", "DraftKings", "Bovada", "ESPN Bet", "Caesars", "William Hill"]


def compute_clv(bet: BetLogRecord, closing_line: float) -> float:
    """CLV in points. Positive = the bettor's number was better than the
    closing number, from the side actually bet (docs/clv-analysis.md).

    For spread bets, `closing_line` is home-relative (CFBD's raw `spread`
    convention -- see models.GameRecord and backtest._side_spread) while
    `bet.line_taken` is side-relative (confirmed against the real Action
    Network export: an away favorite's own negative number is recorded
    from the away side, not translated to home terms). Convert
    closing_line to the bettor's side before comparing -- same flip
    backtest._side_spread applies for away bets.
    """
    if bet.bet_type == "total":
        if bet.side == "over":
            return round(closing_line - bet.line_taken, 4)
        return round(bet.line_taken - closing_line, 4)  # under
    # spread: convert home-relative closing_line to side-relative, then a
    # bigger side-relative number is always better for the side that took it.
    closing_side_relative = closing_line if bet.side == "home" else -closing_line
    return round(bet.line_taken - closing_side_relative, 4)


@dataclass(frozen=True)
class ClvStats:
    n: int
    mean_clv: float
    t_stat: float
    std_error: float


def compute_clv_stats(clv_values: list[float]) -> ClvStats:
    n = len(clv_values)
    if n == 0:
        return ClvStats(n=0, mean_clv=0.0, t_stat=0.0, std_error=0.0)
    mean = sum(clv_values) / n
    variance = sum((v - mean) ** 2 for v in clv_values) / n
    std_error = math.sqrt(variance / n) if variance > 0 else 0.0
    t_stat = mean / std_error if std_error else 0.0
    return ClvStats(n=n, mean_clv=round(mean, 4), t_stat=round(t_stat, 4), std_error=round(std_error, 4))


@dataclass(frozen=True)
class SeasonClv:
    season: int
    n: int
    mean_clv: float


def compute_clv_by_season(bets_with_clv: list[tuple[BetLogRecord, float]]) -> list[SeasonClv]:
    by_season: dict[int, list[float]] = {}
    for bet, clv in bets_with_clv:
        season = int(bet.date[:4])
        by_season.setdefault(season, []).append(clv)
    return [
        SeasonClv(season=season, n=len(values), mean_clv=round(sum(values) / len(values), 4))
        for season, values in sorted(by_season.items())
    ]


def find_closing_line(bet: BetLogRecord, data_dir: str | Path) -> float | None:
    season = int(bet.date[:4])
    games = load_raw_json(data_dir, "lines", season)
    game = next((g for g in games if g.get("id") == bet.game_id), None)
    if game is None:
        return None
    lines = game.get("lines", [])
    field = "overUnder" if bet.bet_type == "total" else "spread"
    for provider in _PROVIDER_CASCADE:
        for line in lines:
            if line.get("provider") == provider and line.get(field) is not None:
                return line[field]
    return None
```

Sign convention confirmed directly against `docs/clv-analysis.md`'s Method section: "CLV = (my number) − (closing number), signed so positive = the line moved in my favor... Unders: my total higher than close is good. Spreads: my number better than close, from the side actually bet." Totals need no frame conversion (`overUnder` has no home/away side, so `closing_line` and `line_taken` are already directly comparable): under favorable when `line_taken > closing_line`, over favorable when `closing_line > line_taken`.

Spreads are different: `find_closing_line` returns the raw `spread` field from `lines_*.json`, which is **home-relative** (CFBD's standing convention — see `models.GameRecord.spread` and `backtest._side_spread`), while `bet.line_taken` is **side-relative** — confirmed against the real Action Network export (`C:\Users\mckel\Downloads\history.csv`): e.g. `NCST @ UCONN, NCST -14.5, spread_away` records the away team's own favorite number, not translated into home terms. Comparing the two directly without converting frames first was the bug caught during self-review. `compute_clv` fixes this by converting `closing_line` into the bettor's side (`closing_line if side == "home" else -closing_line`, the same flip `backtest._side_spread` applies) before subtracting, so a bigger side-relative number is always the better one for whichever side was bet. The corrected test cases above walk through this conversion explicitly in their comments — read them alongside the implementation if the sign logic is ever unclear.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_clv.py -v`
Expected: PASS (11 passed)

- [ ] **Step 5: Commit**

```bash
git add cfb_system_maker/clv.py tests/test_clv.py
git commit -m "feat(clv): CLV computation, aggregate stats, per-season breakdown"
```

---

### Task 5: CLV-over-time chart data

**Files:**
- Modify: `cfb_system_maker/clv.py` (add chart function)
- Test: `tests/test_clv.py` (add chart tests)

**Interfaces:**
- Consumes: list of `(BetLogRecord, float)` tuples (bet + its computed CLV), same shape as `compute_clv_by_season`'s input.
- Produces: `compute_clv_chart(bets_with_clv: list[tuple[BetLogRecord, float]]) -> dict` — same output shape as `web._cumulative_chart` (`{"points": [...], "polyline": str, "zero_y": float, "min_x": int | None, "max_x": int | None}`), but plotting cumulative CLV over chronological bet order instead of cumulative profit.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_clv.py`:

```python
from cfb_system_maker.clv import compute_clv_chart


def test_compute_clv_chart_empty_input_returns_empty_shape():
    result = compute_clv_chart([])
    assert result == {"points": [], "polyline": "", "zero_y": 75, "min_x": None, "max_x": None}


def test_compute_clv_chart_orders_by_date_and_accumulates():
    later = _bet(game_id=2, date="2023-09-08")
    earlier = _bet(game_id=1, date="2023-09-01")
    # passed out of order -- function must sort by date
    result = compute_clv_chart([(later, 3.0), (earlier, 2.0)])
    assert len(result["points"]) == 2
    assert result["points"][0]["clv"] == 2.0  # earlier bet first, cumulative 2.0
    assert result["points"][1]["clv"] == 5.0  # earlier + later, cumulative 2.0 + 3.0
    assert result["max_x"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_clv.py -k chart -v`
Expected: FAIL with `ImportError: cannot import name 'compute_clv_chart'`

- [ ] **Step 3: Write the implementation**

Add to `cfb_system_maker/clv.py` (mirrors `web._cumulative_chart`'s downsampling-free structure — CLV bet counts are far smaller than backtest bet counts, so no downsample/stride logic is needed here, unlike `_cumulative_chart`'s 60-point cap):

```python
def compute_clv_chart(bets_with_clv: list[tuple[BetLogRecord, float]]) -> dict:
    if not bets_with_clv:
        return {"points": [], "polyline": "", "zero_y": 75, "min_x": None, "max_x": None}

    ordered = sorted(bets_with_clv, key=lambda pair: pair[0].date)

    width = 520
    height = 150
    pad_x = 28
    pad_y = 18

    running = 0.0
    running_values = []
    for _, clv in ordered:
        running = round(running + clv, 4)
        running_values.append(running)

    values = running_values + [0]
    min_clv = min(values)
    max_clv = max(values)
    span = max_clv - min_clv or 1

    points = []
    for index, clv in enumerate(running_values):
        x = pad_x if len(ordered) == 1 else pad_x + (width - pad_x * 2) * index / (len(ordered) - 1)
        y = height - pad_y - ((clv - min_clv) / span) * (height - pad_y * 2)
        points.append({"x": round(x, 2), "y": round(y, 2), "order": index, "clv": clv})

    zero_y = height - pad_y - ((0 - min_clv) / span) * (height - pad_y * 2)
    return {
        "points": points,
        "polyline": " ".join(f"{point['x']},{point['y']}" for point in points),
        "zero_y": round(zero_y, 2),
        "min_x": 0,
        "max_x": len(ordered) - 1,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_clv.py -v`
Expected: PASS (13 passed)

- [ ] **Step 5: Commit**

```bash
git add cfb_system_maker/clv.py tests/test_clv.py
git commit -m "feat(clv): CLV-over-time chart data"
```

---

### Task 6: `/betlog` page — route, template, dashboard link

**Files:**
- Modify: `cfb_system_maker/web.py` (add `GET /betlog` route)
- Create: `cfb_system_maker/templates/betlog.html`
- Modify: `cfb_system_maker/templates/dashboard.html` (add "Bet Log" link)
- Modify: `cfb_system_maker/static/styles.css` (add betlog styles)
- Test: `tests/test_web_betlog.py`

**Interfaces:**
- Consumes: `load_betlog` (Task 3), `find_closing_line`, `compute_clv`, `compute_clv_stats`, `compute_clv_by_season`, `compute_clv_chart` (Tasks 4-5).
- Produces: `GET /betlog` route in `create_app`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_web_betlog.py`:

```python
from cfb_system_maker.web import create_app


def test_betlog_page_renders_empty_state(tmp_path):
    app = create_app(data_dir=tmp_path)
    client = app.test_client()
    resp = client.get("/betlog")
    assert resp.status_code == 200
    assert b"No bets imported yet" in resp.data


def test_betlog_page_renders_bets_with_clv(tmp_path, monkeypatch):
    import json

    from cfb_system_maker.betlog import BetLogRecord, save_betlog

    bet = BetLogRecord(
        game_id=1, date="2023-09-01", home_team="San Diego State", away_team="Ohio",
        bet_type="spread", side="away", line_taken=4.0, odds=-110,
        result="win", units_wagered=1.0, units_net=0.91,
    )
    save_betlog([bet], tmp_path)

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    # spread is home-relative (San Diego State, the home team, favored by 2):
    # away-relative for Ohio's side that's +2.0, smaller than the +4.0 our
    # bettor took, so our bettor got the better number -- CLV positive.
    lines_data = [{"id": 1, "season": 2023, "lines": [{"provider": "consensus", "spread": -2.0}]}]
    (raw_dir / "lines_2023.json").write_text(json.dumps(lines_data))

    app = create_app(data_dir=tmp_path)
    client = app.test_client()
    resp = client.get("/betlog")

    assert resp.status_code == 200
    assert b"San Diego State" in resp.data
    assert b"Ohio" in resp.data
    # closing_side_relative = -(-2.0) = 2.0 (away terms); CLV = 4.0 - 2.0 = 2.0
    assert b"2.0" in resp.data


def test_betlog_page_shows_bets_missing_closing_line_separately(tmp_path):
    from cfb_system_maker.betlog import BetLogRecord, save_betlog

    bet = BetLogRecord(
        game_id=999, date="2023-09-01", home_team="Nowhere", away_team="Nobody",
        bet_type="spread", side="away", line_taken=4.0, odds=-110,
        result="win", units_wagered=1.0, units_net=0.91,
    )
    save_betlog([bet], tmp_path)  # no lines_2023.json at all -- no closing line available

    app = create_app(data_dir=tmp_path)
    client = app.test_client()
    resp = client.get("/betlog")
    assert resp.status_code == 200
    assert b"CLV not available" in resp.data


def test_dashboard_links_to_betlog(tmp_path):
    app = create_app(data_dir=tmp_path)
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b'href="/betlog"' in resp.data
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_web_betlog.py -v`
Expected: FAIL with 404s (`/betlog` doesn't exist) and missing dashboard link

- [ ] **Step 3: Write the implementation**

In `web.py`'s `create_app`, add (adjacent to the other route definitions — read the file first to place it near similar routes, e.g. near `/compare` or `/search-runs/<name>`):

```python
@app.get("/betlog")
def betlog_page():
    from cfb_system_maker.betlog import load_betlog
    from cfb_system_maker.clv import (
        compute_clv, compute_clv_by_season, compute_clv_chart, compute_clv_stats, find_closing_line,
    )

    bets = load_betlog(app.config["DATA_DIR"])
    if not bets:
        return render_template("betlog.html", has_bets=False)

    rows = []
    bets_with_clv = []
    for bet in bets:
        closing = find_closing_line(bet, app.config["DATA_DIR"])
        if closing is None:
            rows.append({"bet": bet, "closing_line": None, "clv": None})
            continue
        clv = compute_clv(bet, closing)
        rows.append({"bet": bet, "closing_line": closing, "clv": clv})
        bets_with_clv.append((bet, clv))

    clv_values = [clv for _, clv in bets_with_clv]
    stats = compute_clv_stats(clv_values)
    by_season = compute_clv_by_season(bets_with_clv)
    chart = compute_clv_chart(bets_with_clv)

    expected_profit = sum(clv * 0.02 for clv in clv_values)  # placeholder conversion factor -- see note below
    actual_profit = sum(bet.units_net for bet in bets)

    return render_template(
        "betlog.html",
        has_bets=True,
        rows=rows,
        stats=stats,
        by_season=by_season,
        chart=chart,
        expected_profit=round(expected_profit, 2),
        actual_profit=round(actual_profit, 2),
    )
```

**Note on `expected_profit`:** the design's "expected (CLV-implied) profit vs actual" framing needs a real points-to-units conversion, not the placeholder `* 0.02` shown above — read `docs/clv-analysis.md`'s methodology section for how it derived expected profit from CLV points (likely via a standard vig/juice model at -110, e.g. roughly 1 point ≈ some fraction of a unit at typical spread pricing) and use that real formula, or if the doc doesn't give one, implement `expected_profit` as `None`/omitted from the template for this task and note it as a follow-up rather than shipping a fabricated conversion factor.

Create `cfb_system_maker/templates/betlog.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Bet Log — CFB System Maker</title>
    <link rel="icon" type="image/svg+xml" href="{{ url_for('static', filename='favicon.svg') }}">
    <link rel="stylesheet" href="{{ url_for('static', filename='styles.css') }}">
  </head>
  <body>
    <div class="dash-shell">
      <header class="dash-header">
        <div class="brand">
          <span class="brand-mark">CFB</span>
          <div><h1>Bet Log</h1></div>
        </div>
        <a class="dash-cta" href="{{ url_for('dashboard') }}">&larr; My Systems</a>
      </header>

      {% if not has_bets %}
        <div class="empty-state">
          <h2>No bets imported yet</h2>
          <p>Run <code>python -m cfb_system_maker betlog import --csv &lt;path&gt; --data-dir data</code> to import an Action Network bet-history export.</p>
        </div>
      {% else %}
        <section class="betlog-stats" aria-label="Aggregate CLV">
          <div class="metrics stat-chips">
            <div class="stat-chip"><span>N</span><strong>{{ stats.n }}</strong></div>
            <div class="stat-chip"><span>Mean CLV</span><strong>{{ "%.2f"|format(stats.mean_clv) }} pts</strong></div>
            <div class="stat-chip"><span>t-stat</span><strong>{{ "%.2f"|format(stats.t_stat) }}</strong></div>
          </div>
          <table class="season-breakdown">
            <thead><tr><th>Season</th><th>N</th><th>Mean CLV</th></tr></thead>
            <tbody>
              {% for row in by_season %}
                <tr><td>{{ row.season }}</td><td>{{ row.n }}</td><td>{{ "%.2f"|format(row.mean_clv) }}</td></tr>
              {% endfor %}
            </tbody>
          </table>
        </section>

        <section class="betlog-chart" aria-label="CLV over time">
          <svg viewBox="0 0 520 150" width="520" height="150" role="img" aria-label="Cumulative CLV over time">
            <line x1="0" y1="{{ chart.zero_y }}" x2="520" y2="{{ chart.zero_y }}" class="chart-zero-line" />
            {% if chart.polyline %}
              <polyline points="{{ chart.polyline }}" class="chart-line" fill="none" />
            {% endif %}
          </svg>
        </section>

        <table class="betlog-table">
          <thead>
            <tr><th>Date</th><th>Matchup</th><th>Bet</th><th>Line Taken</th><th>Closing</th><th>CLV</th></tr>
          </thead>
          <tbody>
            {% for row in rows %}
              <tr>
                <td>{{ row.bet.date }}</td>
                <td>{{ row.bet.away_team }} @ {{ row.bet.home_team }}</td>
                <td>{{ row.bet.bet_type }} {{ row.bet.side }}</td>
                <td>{{ row.bet.line_taken }}</td>
                {% if row.clv is none %}
                  <td colspan="2" class="clv-missing">CLV not available (no closing line found)</td>
                {% else %}
                  <td>{{ row.closing_line }}</td>
                  <td class="{{ 'clv-positive' if row.clv > 0 else 'clv-negative' if row.clv < 0 else 'clv-neutral' }}">{{ "%.1f"|format(row.clv) }}</td>
                {% endif %}
              </tr>
            {% endfor %}
          </tbody>
        </table>
      {% endif %}
    </div>
  </body>
</html>
```

In `dashboard.html`, add the Bet Log link inside `dash-header` (next to "New System" — read the file first to confirm exact placement, this is the header block near the top of the file):

```html
<a class="dash-cta" href="{{ url_for('betlog_page') }}">Bet Log</a>
```

Add betlog styles to `styles.css` (check existing conventions first — reuse `.stat-chips`/`.metrics` classes already present rather than duplicating, since the template above already reuses them for the aggregate block; only genuinely new classes need new CSS):

```css
.betlog-table td.clv-positive { color: var(--profit, green); }
.betlog-table td.clv-negative { color: var(--loss); }
.betlog-table td.clv-missing { color: var(--muted); font-style: italic; }
.chart-zero-line { stroke: var(--border); stroke-dasharray: 4 2; }
.chart-line { stroke: var(--accent, #1a3d2e); stroke-width: 2; }
```

Check `styles.css` for the actual names of existing color variables (`--profit`, `--loss`, `--muted`, `--accent` may not all exist under these exact names) and use the real ones.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_web_betlog.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: all existing tests still pass, plus all new tests from Tasks 1-6.

- [ ] **Step 6: Commit**

```bash
git add cfb_system_maker/web.py cfb_system_maker/templates/betlog.html cfb_system_maker/templates/dashboard.html cfb_system_maker/static/styles.css tests/test_web_betlog.py
git commit -m "feat(web): /betlog page with per-bet CLV, aggregate stats, chart"
```

---

### Task 7: End-to-end verification against the real personal export

**Files:** none created/modified — this is a manual verification task.

**Interfaces:** none — exercises the full pipeline built in Tasks 1-6.

- [ ] **Step 1: Run a real import**

With a real `data/` directory that has `games.csv` and `raw/lines_*.json` built (via `fetch`/`build`, or against whatever historical data is already present), run:

```bash
python -m cfb_system_maker betlog import --csv "$HOME/Downloads/history.csv" --data-dir data
```

(Use the actual path to a real Action Network export — this is deliberately not automated/committed, since it's personal financial data.)

- [ ] **Step 2: Sanity-check the summary output**

Confirm the printed summary's counts are internally consistent (`total_rows == in_scope + out_of_scope + malformed` is NOT necessarily how the summary is structured — check `ImportSummary`'s actual fields from Task 3 and confirm the numbers add up the way that dataclass defines them) and roughly match the scale reported in `docs/clv-analysis.md` (344 in-scope bets, ~6 unmatched) — exact numbers may differ slightly since the doc's analysis may have used a different or fresher export.

- [ ] **Step 3: Load the `/betlog` page**

```bash
python -m cfb_system_maker web --data-dir data
```

Open `http://127.0.0.1:5000/betlog` in a browser (or via the Browser tool). Confirm: the table renders with real dates/teams, aggregate CLV stats are shown, the chart renders without errors, and the mean CLV is in the neighborhood of the analysis doc's +0.29 pts finding (it will not be identical, since scope/filtering may differ slightly, but it should be the same sign and order of magnitude — a wildly different result, e.g. strongly negative, indicates a sign-convention bug in `compute_clv` from Task 4 that must be fixed before this task is considered done).

- [ ] **Step 4: Report findings**

Document in the plan's execution notes (not a new file — just report back): the real summary counts, whether the mean CLV roughly matches expectations, and any team-abbreviation gaps surfaced by the unmatched list (add any newly-discovered team names to `team_abbreviations.py`'s `AN_TO_CFBD` map from Task 1, with a follow-up commit if any are found).

- [ ] **Step 5: Commit any abbreviation-map additions found**

```bash
git add cfb_system_maker/team_abbreviations.py
git commit -m "feat(betlog): add team abbreviations discovered during real-data verification"
```

(Skip this commit if no new teams were found — don't create an empty commit.)

---

## Self-Review Notes

**Spec coverage:** Task 1 covers the team map. Tasks 2-3 cover ingestion (2.1: CSV parsing, filtering, matching, idempotent storage, CLI subcommand). Task 4 covers CLV computation (2.2). Tasks 5-6 cover the CLV page (2.3: table, aggregate stats, per-season breakdown, chart, dashboard link — expected-vs-actual profit flagged as needing a real conversion formula rather than a fabricated one). Task 7 verifies against real data. All in-scope roadmap items (2.1, 2.2, 2.3) are covered; 2.4/2.5/2.6 are explicitly out of scope per the design doc.

**Placeholder scan:** The `expected_profit` conversion factor in Task 6 is intentionally flagged as needing real-world confirmation rather than shipped as a guess — this is disclosed inline as a note to resolve during implementation, not a silent TBD. The `games_by_date` construction in Task 3 similarly flags a schema-dependent gap rather than assuming an unverified field name. Both are legitimate "confirm against real code" notes, not vague hand-waving — each names exactly what to check and what to do based on what's found.

**Type consistency:** `BetLogRecord` fields are consistent across Tasks 2-6 (`game_id`, `date`, `home_team`, `away_team`, `bet_type`, `side`, `line_taken`, `odds`, `result`, `units_wagered`, `units_net`). `ClvStats`/`SeasonClv`/`ImportSummary`/`ParsedImport`/`RawBetRow` are each defined once (Tasks 2-4) and consumed with matching field names in later tasks (Task 6's route handler, Task 7's verification).
