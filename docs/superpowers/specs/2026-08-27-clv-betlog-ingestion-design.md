# v1.2 Sub-project 1: Bet-log Ingestion + CLV Core — Design

## Context

`docs/roadmap-v2-2026-08.md` §3 defines milestone v1.2 "CLV & Bet Tracking" as the flagship next milestone, driven by `docs/clv-analysis.md`'s finding: across 344 real spread/total bets, mean CLV was +0.29 pts (p=0.00225) — the one statistically significant edge the whole 7-doc analysis arc found. Today the product has no bet-log ingestion path and no CLV surface at all; the analysis ran off a manual `~/Downloads/history.csv` export and a throwaway, never-committed AN→CFBD team-abbreviation map.

v1.2 as scoped in the roadmap bundles 6 items across ingestion, computation, and three UI surfaces, two of which (2.4 live record, 2.5 paper tracking) depend on each other and are architecturally separate from CLV itself. This design covers **sub-project 1 only**: ingestion (2.1), CLV computation (2.2), and the CLV page (2.3, full scope). Sub-project 2 (2.4, 2.5, 2.6) is a separate future design.

## Goal

Import a personal Action Network bet-history export, compute CLV against CFBD's closing lines, and surface it as a real page in the app — turning the analysis arc's finding into a durable, reusable feature instead of a one-off script.

## Non-goals (deferred)

- Live record per saved system (2.4) and paper tracking of Current Matches (2.5) — separate sub-project, since 2.4 depends on 2.5's snapshot mechanism, and neither shares files with this sub-project's scope.
- Dual-baseline CLV (2.6, stretch) — adds "vs. best-available close" alongside "vs. consensus close"; a refinement on top of working single-baseline CLV, not needed to prove the feature.
- Extending the Action Network scraper to pull bet history via its authenticated API — out of scope; this sub-project imports from the same manual CSV export format already validated by the analysis.
- Moneyline and live (in-game) bet CLV — moneyline needs implied-probability units instead of points; live bets have no fixed "closing line" in the same sense. Both are real scope expansions, not bugs to fix here.

## Architecture

Three new modules, following existing conventions exactly (no new patterns invented):

```
cfb_system_maker/
  team_abbreviations.py   -- AN team-name -> CFBD team-name map (new, first-class, tested)
  betlog.py                -- CSV parsing, filtering, AN->CFBD game matching, storage
  clv.py                   -- pure CLV computation + aggregate stats (backtest.py-style)
  cli.py                    -- + `betlog import` subcommand
  web.py                    -- + `GET /betlog` route
  templates/
    betlog.html             -- new page
  static/styles.css         -- + betlog page styles (traffic-light cells, table)
```

## Data flow

### 1. Import (`betlog.py` + `cli.py`)

```
python -m cfb_system_maker betlog import --csv <path> --data-dir data
```

- Reads the Action Network export CSV. The real export's first line is a stray `data:text/csv;charset=utf-8,` browser artifact before the real header (`League, Start Time, Game, Pick Desc, Type, Period, Odds, Odds/Spread/Total, Result, Units Wagered, Units Net, Money Wagered, Money Net, Tag`) — the parser detects and skips this line if present, rather than assuming it's always there (a re-export or a different export path might not have it).
- Filters to in-scope rows: `Type` in `{spread_home, spread_away, total_over, total_under}` (or however the real CSV spells these — confirmed by inspecting the actual file, not assumed) and `Period == full_game` (excludes live/in-game bets). Out-of-scope rows are counted, not silently dropped from the summary.
- Matches each in-scope row's free-text `Game` field (e.g. `NAVY @ ND`) plus `Start Time` to a CFBD `game_id`, via:
  - `team_abbreviations.py`'s `AN_TO_CFBD` dict (AN's abbreviation/short name → CFBD's full team name).
  - Loading `data/processed/games.csv` (via existing `storage.load_processed_games`) and matching on `(home_team, away_team, date)` within a same-day tolerance (kickoff time in the AN export vs. CFBD's `start_date` may differ by timezone handling — match on date, not exact timestamp).
- Unmatched rows (ambiguous team name, no game found for that date) are **skipped, not fatal** — counted and printed by name (date + team string) in the import summary, excluded from `bets.csv` and all downstream CLV stats.
- Writes matched bets to `data/betlog/bets.csv`, **merging** with any existing file: dedupe key is `(date, home_team, away_team, bet_type, side, odds)`. Re-running import with a fresher export adds new bets, leaves existing ones untouched, matching the resume-skip convention already used by `scrape`/`fetch`.
- Prints a summary: `580 rows in CSV, 344 in scope (spread/total, pre-game), 12 already imported, 332 new, 338 matched (6 unmatched, listed)`.

**`BetLogRecord`** (new, plain dataclass, not `GameRecord` — a bet's shape doesn't fit games at all):

```python
@dataclass(frozen=True)
class BetLogRecord:
    game_id: int
    date: str
    home_team: str
    away_team: str
    bet_type: str        # "spread" | "total"
    side: str            # "home" | "away" | "over" | "under"
    line_taken: float    # the number the bettor got
    odds: int            # American odds, e.g. -110
    result: str          # "win" | "loss" | "push"
    units_wagered: float
    units_net: float
```

Written via plain `csv.DictWriter`/`DictReader`, same as `upcoming.csv` — no `GameRecord` field-order contract to preserve, since this is a wholly separate file.

### 2. CLV computation (`clv.py`)

Pure functions, heavily tested, no I/O beyond what's passed in — same style as `backtest.py`:

```python
def compute_clv(bet: BetLogRecord, closing_line: float) -> float:
    """CLV in points. Positive = line moved in the bettor's favor."""
```

Closing-line lookup adapts `normalize._select_line`'s existing provider-preference logic (consensus → DraftKings → Bovada → ESPN Bet → Caesars → William Hill) rather than duplicating it — reads `data/raw/lines_{season}.json`, finds the game by `game_id`, applies the same preference order to pick one provider's `spread`/`overUnder` as the closing number.

Aggregate stats reuse `backtest.py`'s existing machinery directly:
- Mean CLV, t-stat: same t-test pattern as `_roi_stats`.
- Per-season breakdown: same grouping pattern as `season_breakdown`/`sign_consistency`.
- No new statistical code is written where an existing tested function already does the job.

### 3. CLV page (`web.py` + `templates/betlog.html`)

`GET /betlog`, a new top-level route (not a dashboard `?tab=` value — Current Matches is a sidebar, not a tab, and this page's content, a full table + chart + stats block, doesn't fit the systems-table shape the existing tabs control).

Renders:
- **Per-bet table**: date, teams, bet (type/side/line taken), closing line, CLV (points), traffic-light color (green/yellow/red — thresholds TBD at implementation, likely something like CLV > 0 green, ≈0 yellow, < 0 red, refined once real data is visible).
- **Aggregate block**: mean CLV, t-stat, n, per-season breakdown table (mirrors the existing per-season display pattern already used on `/system` and `/compare`).
- **Chart**: CLV over time, reusing the `_cumulative_chart` SVG-generation pattern (downsampled points, same styling as the existing money-won chart).
- **Expected vs. actual**: "expected (CLV-implied) profit" next to actual realized profit, side by side — the Pikkit/Betstamp framing from the roadmap's competitive survey.

Dashboard nav (`dashboard.html`) gains a "Bet Log" link alongside the existing My Systems / Example Systems tab links, pointing at the new route.

## Testing

- `team_abbreviations.py`: unit tests for known team-name mappings, including deliberately ambiguous cases if any exist in real AN data (e.g. teams with common short-name collisions).
- `betlog.py`: parsing tests against a small synthetic fixture CSV (checked into `tests/fixtures/` or inline as a string — never the real personal `~/Downloads/history.csv`, which stays outside the repo). Covers: the stray-first-line detection, in-scope filtering, dedupe-on-reimport, unmatched-row reporting.
- `clv.py`: CLV math tested with hand-computed expected values for a handful of known bet/closing-line pairs; aggregate stats tested against the existing `backtest.py` test patterns (construct records directly, assert on result fields).
- `web.py` / `/betlog`: route tests using the existing inline `create_app(data_dir=tmp_path).test_client()` convention (no `client` fixture exists in this codebase — don't introduce one).

## Storage summary

| Path | Format | Written by | Read by |
|---|---|---|---|
| `data/betlog/bets.csv` | `BetLogRecord` fields, plain CSV | `betlog import` | `clv.py`, `/betlog` route |

No changes to `GameRecord`, `games.csv`, or any existing storage contract.

## Open questions to resolve during implementation (not blocking design approval)

- Exact `Type`/`Period` string values in the real Action Network CSV export (confirm against the actual file structure at implementation time, don't assume the plan's placeholder spellings are exact).
- Traffic-light color thresholds for per-bet CLV (green/yellow/red cutoffs) — pick something reasonable at implementation time, refine once real data renders.
