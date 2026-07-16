# Web Feature Filters — Design

Date: 2026-06-13
Status: Implemented (2026-06-13)

## Goal

Let the web backtester filter betting systems on the broader CFBD dataset already
pulled to `data/raw/` and `data/graphql/` — weather, betting-line extras, pregame
ratings, preseason team stats, and metadata — instead of only the 12 core fields in
`games.csv`. Works for both spread and total bets. Add system-quality statistics and
the ability to save/load systems.

## Scope (phase 1)

Only fields that are **honest at bet time** (no lookahead), plus a clearly fenced
"result stats (lookahead — analysis only)" group. Season-final snapshots that cannot
be made point-in-time from current data (FPI, season Elo file, season records,
season ATS, season PPA, adjustedTeamMetrics, SP+) are **deferred to phase 2**, when a
running/as-of-week compute layer will be built.

### Field groups

- **pregame** (join `game_id`): neutralSite, conferenceGame, venue, seasonType,
  homePregameElo / awayPregameElo, pregame win-prob spread, gameLines extras
  (spreadOpen, overUnderOpen, moneylineHome, moneylineAway), weather (temperature,
  windSpeed, precipitation, humidity, dewPoint, pressure, snowfall, gameIndoors,
  weatherCondition), media outlet (TV network).
- **team_preseason** (join `team`+`season`, fixed all season → no lookahead):
  returning_production.* , teamTalent, recruiting rating.
- **metadata** (join by name): coaches (current coach, hireDate), teams
  (location.state, location.timezone, location.capacity, conference), conferences
  (classification, shortName, abbreviation).
- **result_lookahead** (per-game OUTCOME — fenced, labeled, off by default for honest
  systems): game_havoc_stats.* , attendance.

## Architecture

Generic feature layer. The 12-field `GameRecord` is unchanged; enriched values ride in
a sidecar keyed by `game_id`. Filtering generalizes to a list of predicates over a
feature map, so adding a future field is one registry entry — no new filter code.

### 1. Field registry — `cfb_system_maker/features.py`

One declarative entry per feature:

```
key            # stable id, e.g. "weather_temperature", "elo" (team-scoped base)
label          # UI label, e.g. "Temperature (F)"
group          # "pregame" | "team_preseason" | "metadata" | "result_lookahead"
source         # raw/graphql file glob + json path to the value
join           # "game_id" | "team_season"
control        # "bool" | "categorical" | "numeric"
team_scoped    # bool — if true, stored as home_<key>/away_<key>
```

The registry is the single source of truth for enrich, dropdown options, and matching.

### 2. Enrich build step — `cfb_system_maker/enrich.py`, CLI `enrich`

Reads `games.csv` + `data/raw/*` + `data/graphql/*`. For each game, resolves every
registry feature and writes `data/processed/features.json`:

```json
{
  "401520": {
    "neutralSite": false,
    "weather_temperature": 54.0,
    "weather_condition": "Clear",
    "home_elo": 1620, "away_elo": 1481,
    "home_returning_ppa": 0.61, "away_returning_ppa": 0.43
  }
}
```

- `game_id`-join → direct value.
- `team_season`-join → looked up per side, stored `home_<key>` / `away_<key>`.
- Missing source/season/row → `null`.
- JSON sidecar (chosen over wide CSV): clean nulls and types, no new deps.

`enrich` runs after `build`. CLI: `python -m cfb_system_maker enrich --data-dir data`.

### 3. Models — `cfb_system_maker/models.py`

- `GameRecord`: unchanged.
- New frozen `FeatureFilter`:
  ```
  key: str          # registry key, with perspective prefix resolved (see §4)
  op: str           # "in" | "eq" | "gte" | "lte"
  value: object     # list[str] for "in"; bool for "eq"; float for gte/lte
  ```
- `SystemFilter` gains one field: `feature_filters: tuple[FeatureFilter, ...] = ()`.
  Nothing else changes.
- `BacktestResult` gains a `stats: SystemStats` block (§5).

### 4. Side handling (team-scoped fields)

Stored raw as `home_<key>` / `away_<key>`. The UI exposes perspectives:

- **Spread bets**: Home, Away, **Bet-side**, **Opponent**.
  Bet-side/Opponent resolve to home/away at match time from `system.side`.
- **Total bets**: Home, Away, Either (no single bet side → Bet-side/Opponent hidden).
  "Either" passes if home OR away value satisfies the predicate.

Resolution happens when building `FeatureFilter.key` for matching: e.g. perspective
"bet-side" + side "away" → `away_<key>`.

### 5. System-quality statistics — `SystemStats` (computed in `backtest.py`)

Pure-Python (normal approximation, no scipy):

- `break_even_rate` — from `american_odds` (−110 → 0.5238).
- `edge` = hit_rate − break_even_rate.
- `wilson_low`, `wilson_high` — Wilson 95% CI on hit rate (good for small n).
- `z_score`, `p_value` — one-sided test: hit rate > break-even (better than chance).
- `roi_std_error`, `roi_t_stat` — on per-bet returns.
- `low_sample` — bool, true when decided bets < 30 (CI too wide to trust).

Shown in web result panel and CLI output. No Kelly (deferred), no CLV (needs closing
line, out of scope).

### 6. Save / load systems — `storage.py`

- `save_system(name, system, data_dir)` → `data/systems/<name>.json` (full
  `SystemFilter` incl. `feature_filters`, plus name + ISO timestamp).
- `load_system(name, data_dir)` → `SystemFilter`.
- `list_systems(data_dir)` → list of names.
- Web: "Save as…" (name input) + "Load system" dropdown that repopulates the form.
- CLI: `backtest --save NAME` / `backtest --load NAME`.

### 7. Web UI — `web.py` + template

- Loads `games.csv` + `features.json` (missing features.json → features disabled, core
  filters still work; not an error).
- Dropdown options from registry + scanning enriched values: categorical → distinct
  values; numeric → min/max hints; bool → any/yes/no.
- Dynamic filter rows grouped by registry group. `result_lookahead` group visually
  fenced with a lookahead warning.
- Each row: field dropdown → (perspective, if team-scoped) → op → value(s).
- Result panel adds the `SystemStats` block.

### 8. Backtest matching — `backtest.py`

`matches_system` adds, after existing checks:

```
features = feature_map.get(game.game_id, {})
all(_feature_ok(features, f) for f in system.feature_filters)
```

- `run_backtest` takes an optional `feature_map: dict[int, dict]`.
- Null feature value → predicate fails closed (game excluded).
- Runs identically for spread and total bet types.

## Testing

- `test_features` — registry integrity (keys unique, sources resolvable shape).
- `test_enrich` — join correctness (game_id + team_season), null handling, home/away
  side mapping.
- `test_backtest` — feature_filter matching for each op; bet-side/opponent resolution;
  totals "either"; null fails closed; `SystemStats` math (known-input assertions).
- `test_storage` — save/load/list system round-trip.
- `test_web` — dynamic options render; features.json-missing degrades gracefully.

## Out of scope (phase 2+)

- Running / as-of-week computed stats (running W-L, running ATS, running PPA) to make
  season-final snapshots point-in-time.
- Kelly staking, CLV.
- CLI exposure of the full dynamic filter set (web is the rich surface; CLI keeps
  spread/total + save/load).
