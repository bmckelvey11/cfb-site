# Phase 5: Dashboard & Current Matches - Research

**Researched:** 2026-07-20
**Domain:** CFBD upcoming-games pipeline + Flask/Jinja dashboard over existing backtest engine
**Confidence:** HIGH (all core unknowns resolved by reading vendored source and probing the live CFBD API)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Upcoming-games data path**

- **D-01:** Unplayed games live in a **separate processed file** (e.g. `data/processed/upcoming.csv`), not in `games.csv`. `games.csv` keeps its current contract — 12,964 completed games, `GameRecord` field order unchanged, no `played` flag, no CSV migration. This keeps it structurally impossible for the historical backtest path to grade an unplayed game.
- **D-02:** The upcoming file is produced by a **new CLI command** (e.g. `python -m cfb_system_maker upcoming --data-dir data`). The web app remains a pure local-file reader — no CFBD network calls from a Flask request handler, consistent with every existing page.
- **D-03:** "Upcoming" means the **current CFB week only**, matching the existing week-based data model and Bet Labs' upcoming panel. Not a rolling date window, not all remaining unplayed games.
- **D-04:** Games with **no posted betting line are excluded**. No line means no spread/total to filter on and no bet to place; this follows the existing null-fails-closed convention rather than rendering un-evaluable rows.
- **D-05:** Upcoming games are **enriched through the same feature path as historical games**, so any saved system evaluates correctly — including systems filtering on `computed_running` season-to-date stats. These are entering-game by construction, so no lookahead is introduced. A system silently failing to match because its features could not be computed is a worse outcome than the extra work.
- **D-06:** The panel displays the **fetch timestamp** of the upcoming data ("Lines as of ..."). Line movement changes which games a system matches; the timestamp is the honest minimum. No in-page refresh button (that would reintroduce a network call on page load).
- **D-07:** In the **offseason or any week with no upcoming games**, the panel shows an explicit empty state *plus* the matches from the most recent week that does have data. This keeps the feature visible and testable year-round (the phase is being built in July; the next real games are ~5 weeks out).
- **D-08:** Each row's play text **mirrors the system's bet type** — spread systems read "Play Georgia -7", total systems read "Play Over 52.5" — derived from the system's existing `side` / `total_side` so the displayed play cannot disagree with what would be graded.

**Dashboard layout and routing**

- **D-09:** The dashboard is served at `/` and the system editor moves to `/system`. A request to `/` **carrying filter query parameters redirects to `/system`** with the query string intact, so existing bookmarks and shared links keep working. A bare `/` shows the dashboard.
- **D-10:** Timeframe tabs are **All Time + per-season**. Bet Labs' "30 Days" / "7 Days" windows are not offered — `games.csv` has no kickoff dates, and the parity plan already recommends deferring them for this reason.
- **D-11:** Dashboard figures are **computed on request via the existing `run_backtest` path and cached in memory**, keyed by system plus data-file identity. No second grading path, no precomputed numbers persisted into saved-system JSON (which would go stale silently after a data rebuild).
- **D-12:** **Current Matches renders as a panel on the dashboard**, showing all systems' matches together — matching Bet Labs' layout and making one page answer "what do I bet this week."
- **D-13:** Matched-filter details per game **reuse the existing `describe()` sentence renderer** from Phase 1 rather than a second rendering path.

**Bundled example systems**

- **D-14:** Examples are **checked-in `SavedSystem` JSON files in the package, loaded read-only**. They are not copied into the user's data directory on first run and cannot be overwritten in place; editing one is a "copy to My Systems" action.
- **D-15:** Examples appear on a **separate "Example Systems" tab**, not mixed into the My Systems table, so the user's own list is never padded with systems they did not build.
- **D-16:** Ship **one example per capability** — a spread system, a total system, and one exercising a registry feature (e.g. weather or a season-to-date stat). The goal is to demonstrate the tool's range, not to present profitable angles as recommendations.
- **D-17:** Each example carries a **short written `theory`** (the free-text field from Phase 1), one or two sentences on why the angle might exist — modelling the habit of recording reasoning before trusting a backtest.

### Claude's Discretion

- Sparkline rendering approach, dashboard table column order and widths, tab styling, cache invalidation mechanics, and the exact name/flags of the upcoming CLI command are planner/implementation choices, provided the decisions above hold.
- The exact schema of the upcoming file is a planner decision. It is *not* bound by the `GameRecord` CSV field-order contract, since it is a separate file; it will need kickoff date/time, which `GameRecord` does not carry.
- Exact wording of empty states and the fetch-timestamp line.

### Deferred Ideas (OUT OF SCOPE)

- **Teaser / alternate-line records (DASH-04)** — descoped from Phase 5 on 2026-07-20 at the user's request, mid-discussion. Partial decisions captured before shelving, for whenever it is picked up: favorable-direction-only ladder (6 / 6.5 / 7 / 10 points), surfaced as a popover from the editor's Record chip. **Two questions were never answered:** (a) whether to show money/ROI at all, given that teasers do not price at -110 and a flat-stake dollar figure would overstate profit in the optimistic direction; (b) whether total systems are included (over teases down, under teases up). ROADMAP.md success criteria and REQUIREMENTS.md were updated to match this descope.
- Timeframe windows based on real dates ("30 Days", "7 Days") — needs kickoff timestamps in the historical data; deferred per the parity plan.
- In-page refresh button for upcoming data — rejected for Phase 5 because it puts a network call behind a page load (D-06).
- Grade sub-score breakdown panel — still deferred from Phase 2.
- Think Tank / multi-user sharing, moneyline wager type, public betting percentages — project-level out of scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DASH-01 | User lands on a My Systems dashboard listing saved systems with record/money-won/ROI and a sparkline, separate from the system editor page | §Reuse Surfaces (`run_backtest` result shape, `_cumulative_chart` precedent for the sparkline series), §Routing (the `/` → `/system` move and its two concrete breakages), §Performance (derive per-season tabs from one all-time `bet_details` pass) |
| DASH-02 | Dashboard ships with 2-3 bundled example systems for a new/empty install | §Bundled Examples (no packaging machinery exists — plain files under `cfb_system_maker/`; `_safe_system_name` and `_system_to_dict` are the two contracts the JSON must satisfy) |
| DASH-03 | User sees a Current Matches view: upcoming (unplayed) games each saved system matches, with the matched-filter details shown per game | §Upcoming Pipeline (verified CFBD shapes), §Pitfall 1 (`matches_system` score guard — the blocking issue), §Enrichment (`compute_running_stats` integration shape), §Reuse Surfaces (`describe()`) |

DASH-04 is out of scope and is not researched here.
</phase_requirements>

---

## Summary

The dashboard half of this phase is a new view over machinery that already exists — `run_backtest`, `describe()`, `list_systems`, the server-rendered SVG chart idiom, and the `.tabs`/`.positive`/`.negative` CSS vocabulary all transfer directly. The genuinely new work is the upcoming-games pipeline, and the good news is that every unknown in it resolved cleanly against source and a live API probe.

CFBD models unplayed games exactly as needed: `Game.completed` is a real boolean, `homePoints`/`awayPoints` are `None`, and `startDate` is a timezone-aware UTC `datetime`. A live probe confirmed that `BettingApi.get_lines` **does** return posted spreads and totals for future games — 2026 week 1 returned 99 games (all `completed=False`) with lines on 51 of them, in the same `BettingGame`/`GameLine` shape `normalize_games` already consumes. `GamesApi.get_calendar(year)` returns clean `[startDate, endDate]` week windows, which makes current-week detection a lookup rather than a heuristic. So `normalize_games` / `_select_line` apply to upcoming games unchanged, and only kickoff time needs to be captured outside `GameRecord`.

Two findings dominate planning. First, **`matches_system` returns `False` for every unplayed game** — `backtest.py:246-247` guards on `home_points`/`away_points` being non-`None`. Without a surgical change to that guard, Current Matches silently shows zero rows forever, and no test would catch it. Second, **`compute_running_stats` only produces useful values for an upcoming game if that season's already-completed weeks are in the same games list**; `games.csv` stops at 2025, so a naive implementation would give every 2026 game `games_played=0` and null season-to-date stats, causing exactly the silent no-match D-05 was written to prevent.

**Primary recommendation:** Add `require_played: bool = True` to `matches_system` and have Current Matches call it with `require_played=False`, matching but never grading (unplayed games have no result, so `grade_bet` is never involved). Build the upcoming file from a full current-season fetch (completed weeks + the current week's unplayed games), run `compute_running_stats` over the union, and emit features for the upcoming rows into a separate sidecar. Compute each system's dashboard figures with a single all-time `run_backtest` call and derive the per-season tabs and the sparkline by filtering `bet_details` on `bet.season`.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Fetch upcoming games + lines from CFBD | CLI / data pipeline (`cfbd_client.py`) | — | D-02 forbids network calls from Flask; every existing fetch lives in the CLI stage |
| Current-week detection | CLI / data pipeline | — | Needs `get_calendar`, i.e. network; must be resolved at fetch time and recorded in the output file |
| Normalize games↔lines, select line | Domain (`normalize.py`) | — | `_select_line` already owns provider precedence and the cross-provider total fallback |
| Entering-game feature computation | Domain (`running_stats.py` / `enrich.py`) | — | Existing no-lookahead convention lives here; upcoming games must not fork it |
| Persist upcoming games + features | Storage (`storage.py`) | — | CLI stages persist to disk between steps; the web layer is a pure reader |
| Match a system against upcoming games | Domain (`backtest.matches_system`) | — | D-11/D-15 single authoritative path; the web layer must not reimplement filter logic |
| Grade a bet | Domain (`backtest.grade_bet`) | — | Historical only. Never reached for upcoming games — there is no result to grade |
| Dashboard figures (Record/Money/ROI) | Domain (`run_backtest`) | Web (in-memory cache) | D-11: one grading path, cached at the web layer, never persisted |
| Sparkline geometry | Web (`web.py` helper) | — | Presentation-only projection of `bet_details`; mirrors the existing `_cumulative_chart` helper |
| Filter-sentence rendering | Domain (`describe.py`) | — | D-13 forbids a second renderer |
| Bundled example enumeration | Storage / package resources | — | Examples live in the package dir, not `data/`; needs a loader distinct from `list_systems` |
| Routing and redirects | Web (`create_app`) | — | D-09 |

---

## Upcoming-Games Pipeline

### 1. How CFBD represents an unplayed game

Read from `cfbd-python/cfbd/models/game.py` and confirmed by live probe.

`Game` fields relevant to this phase [VERIFIED: cfbd-python/cfbd/models/game.py]:

| Field | Alias | Type | Value when unplayed |
|-------|-------|------|---------------------|
| `completed` | `completed` | `StrictBool` (required, never null) | `False` |
| `home_points` | `homePoints` | `Optional[StrictInt]` | `None` |
| `away_points` | `awayPoints` | `Optional[StrictInt]` | `None` |
| `start_date` | `startDate` | `datetime` (required) | tz-aware UTC datetime |
| `start_time_tbd` | `startTimeTBD` | `StrictBool` (required) | `True` when kickoff time is not yet set |
| `season`, `week`, `seasonType` | — | required | populated |
| `home_team`/`away_team`, conferences, classifications | — | populated | populated |

There **is** a `completed` boolean — no need to infer "unplayed" from null scores. Note `GameStatus` (`scheduled`/`in_progress`/`completed`) exists as a separate enum but is **not** a field on `Game`; it belongs to `ScoreboardGame` (the live/on-demand endpoint). Use `Game.completed` [VERIFIED: cfbd-python/cfbd/models/game_status.py, game.py].

Live probe, `get_games(year=2026, week=1, season_type="regular")` [VERIFIED: live CFBD API, 2026-07-20]:

```
2026 wk1: 99 games, 99 incomplete, 99 line rows
sample: {'id': 401856766, 'completed': False,
         'startDate': datetime(2026, 8, 29, 16, 0, tzinfo=utc),
         'startTimeTBD': False, 'homePoints': None, 'awayPoints': None,
         'homeTeam': 'TCU', 'awayTeam': 'North Carolina'}
```

### 2. Does `get_lines` return lines for future games?

**Yes.** This was the one claim that could have invalidated the feature; it is now verified empirically, not assumed.

`BettingApi.get_lines(year=2026, week=1, season_type="regular")` returned 99 `BettingGame` rows, **51 of which carried at least one `GameLine`** [VERIFIED: live CFBD API, 2026-07-20]. Sample lines for the TCU game:

```json
[{"provider": "Bovada", "spread": -6.5, "formattedSpread": "TCU -6.5",
  "spreadOpen": -7.5, "overUnder": 49.5, "overUnderOpen": 50.5,
  "homeMoneyline": -235, "awayMoneyline": 195},
 {"provider": "DraftKings", "spread": -6.5, "formattedSpread": "TCU -6.5",
  "spreadOpen": null, "overUnder": 49.5, "overUnderOpen": null,
  "homeMoneyline": -250, "awayMoneyline": 205}]
```

The shape is identical to historical rows: `BettingGame` carries `id`, `season`, `week`, `startDate`, home/away team+conference, `homeScore`/`awayScore` (both `None` for unplayed), and `lines: List[GameLine]` [VERIFIED: cfbd-python/cfbd/models/betting_game.py, game_line.py].

**Consequence:** `normalize.normalize_games` and `_select_line` work on upcoming data **with no change**. `_select_line` drops rows with no usable line, which independently satisfies D-04 (games with no posted line are excluded) — the exclusion is already the existing behavior, not new code.

Note that only ~52% of 2026 week-1 games have lines this far out. In-season the coverage is higher, but the panel should never assume every scheduled game appears.

### 3. Kickoff date/time

`startDate` is a tz-aware UTC `datetime` on both `Game` and `BettingGame`. `GameRecord` has no field for it and D-01 forbids changing the `games.csv` schema, so the upcoming file needs its own schema carrying kickoff (planner discretion per CONTEXT).

Two mechanics to get right:

- `cfbd_client._to_dict` calls `.dict(by_alias=True)`, which leaves `startDate` as a **`datetime` object**, not a string. `storage.save_raw_json` / `save_raw` pass `default=str` to `json.dumps`, so it serializes to an ISO-8601 string on the way to disk. Any new writer must do the same or the dump raises `TypeError` [VERIFIED: cfb_system_maker/storage.py:25,37].
- `startTimeTBD=True` means the time component is a placeholder. The UI-SPEC's `Sat Sep 6, 3:30 PM` row format needs a TBD variant (render date only). This is an unhandled case in the copywriting contract — flag it to the planner rather than inventing copy here.

Times are UTC. UI-SPEC says "kickoff date + local time," so a conversion is needed at render (or store a local-time string at fetch). No new dependency required — `datetime.astimezone()` handles it.

### 4. Current-week detection

`GamesApi.get_calendar(year)` returns `List[CalendarWeek]` with `season`, `week`, `seasonType`, `startDate`, `endDate`, `firstGameStart`, `lastGameStart` — all tz-aware datetimes [VERIFIED: cfbd-python/cfbd/models/calendar_week.py].

Live probe returned 16 weeks for 2026, with non-overlapping windows [VERIFIED: live CFBD API, 2026-07-20]:

```
week 1: startDate 2026-08-29T07:00Z  endDate 2026-09-08T06:59Z
week 2: startDate 2026-09-08T07:00Z  endDate 2026-09-14T06:59Z
week 3: startDate 2026-09-14T07:00Z  endDate 2026-09-21T06:59Z
```

**Recommended algorithm** (deterministic, one extra API call, no heuristics):

1. `weeks = get_calendar(current_year)`.
2. Current week = the `CalendarWeek` where `startDate <= now <= endDate`.
3. If none matches and `now < min(startDate)` → **preseason/offseason**: no week is in progress.
4. If none matches and `now > max(endDate)` → **postseason gap**: also offseason for `season_type="regular"`.

Prefer this over deriving weeks from game start dates: the calendar windows are authoritative, handle the Tue-to-Mon boundary CFB actually uses, and cost one call.

**The offseason case is today's case.** `now = 2026-07-20` is before `2026-08-29`, so no regular-season week is in progress and there are no games to fetch for a "current week." This is not an edge case to defer — D-07 makes it the state the phase will be built and demoed in. Two implications:

- The `upcoming` CLI command must terminate gracefully in the offseason (write an empty-but-valid file with a timestamp, or no file plus a clear message) — not crash and not write a malformed file.
- The most-recent-week-with-data fallback (D-07) is the state every developer and reviewer will actually see. It must be first-class, not a late patch.

A pragmatic offseason option worth noting to the planner: the *next* scheduled week (2026 week 1) already has real lines on 51 games today. Nothing in D-03 or D-07 requires fetching it, but it makes the feature demonstrable now. Treat it as a planner question, not a research conclusion.

### 5. Provider drift — real, and it affects matching

Provider mix, verified across three slices:

| Slice | Providers |
|-------|-----------|
| `games.csv` all seasons | consensus (8183), ESPN Bet (1926), DraftKings (1290), Bovada (771), William Hill NJ (544), teamrankings (179), Caesars CO (62), "Draft Kings" (7), numberfire (2) |
| `games.csv` 2025 only | ESPN Bet (807), DraftKings (553), Bovada (180), "Draft Kings" (7) |
| CFBD 2026 wk1 (live) | DraftKings (51), Bovada (50) |
| CFBD 2025 wk5 (live) | ESPN Bet (106), DraftKings (53), Bovada (53) |

[VERIFIED: data/processed/games.csv; live CFBD API 2026-07-20]

**`consensus` no longer exists in recent CFBD data at all.** The `build` CLI still defaults to `--provider consensus`; `_select_line` falls back to the first usable line when the preferred provider is absent, which is why recent seasons carry real book names. Consequences for this phase:

- The upcoming builder should reuse `_select_line` with the same provider preference for consistency, and accept that upcoming rows will carry `DraftKings`/`Bovada`.
- Any saved system with a `providers` filter set to `consensus` (or `ESPN Bet`) **will match zero upcoming games**, because `matches_system` checks `game.provider not in system.providers`. This is correct fail-closed behavior, but it will look like a bug. Worth a note in the panel's empty state or at minimum in the plan's verification steps.
- Do not use a provider filter in any bundled example system (D-16), or the examples will show zero current matches.

### 6. Testability of the fetch

`fetch_games_and_lines` constructs its own `cfbd.ApiClient` internally and is not injectable, unlike `scrapers.scrape` (takes `cfbd_module`) and `graphql_client` (takes `post_fn`). The project convention, stated in CLAUDE.md, is injectable clients so tests run network-free.

**Recommendation:** the new upcoming fetch should accept an injectable `cfbd_module` (or a `games_fn`/`lines_fn`/`calendar_fn` trio) following the `scrapers.py` pattern, so `tests/` can exercise the whole pipeline — including offseason and no-lines branches — with a fake. Do not refactor `fetch_games_and_lines` itself; that is out of scope and would be a non-surgical change.

---

## Enrichment Over Unplayed Games (D-05)

### How `compute_running_stats` behaves on an unplayed game

Reading `running_stats.py` line by line, the function is already correct for unplayed games — by construction, not by accident:

1. Games are bucketed by `(team, season)` and sorted by `startDate` (fallback `season-week`).
2. For each game in order, the **entering-game** snapshot is written to `stats[(game_id, team)]` **before** that game's result is folded in (lines 43-56).
3. Only then does it accumulate — and it `continue`s early if either score is `None` (lines 58-61).

So an unplayed game receives the accumulated state of all strictly-prior games and contributes nothing to any other game's state. **No lookahead is introduced**, and unplayed games cannot contaminate each other even if several are in the list. [VERIFIED: cfb_system_maker/running_stats.py:43-61]

### The exact integration shape — and its hard prerequisite

The values are only *useful* if the season's already-completed games are in the same `games` list. This is the finding with the highest planning impact:

> `games.csv` covers 2013–2025 (12,964 rows) and contains **no 2026 games** [VERIFIED: data/processed/games.csv].

If the upcoming path passes only the upcoming games to `compute_running_stats`, every 2026 game gets `games_played=0` and `win_pct`/`ats_pct`/`ppa_*`/`adv_*` all `None`. `feature_ok` returns `False` on a `None` value (`features.py`), so **every system with a season-to-date filter silently matches nothing** — precisely the failure mode D-05 exists to prevent.

**Required shape:**

1. The `upcoming` command fetches the **full current season** (`get_games(year=current)` without a week filter), not just the current week's slice.
2. Split on `completed`: completed games are the accumulation base; `completed=False` games in the current week are the upcoming set.
3. Run `compute_running_stats` over the **union** (completed ∪ upcoming) for that season, with `start_dates` populated from the raw `startDate` values so ordering is correct.
4. Emit feature rows for the **upcoming game ids only**, into a separate sidecar file (e.g. `data/processed/upcoming_features.json`), keyed the same `{game_id: {feature_key: value}}` way `load_features` returns, so the web layer can pass it as `feature_map` unchanged.

Note this holds even for week 1 of a season: there are no prior games, so `games_played=0` and season-to-date stats are legitimately `None`. That is correct behavior, and any system with a season-to-date filter genuinely should not fire in week 1. The bug is only when it happens in week 6.

### Non-running features on upcoming games

`enrich._build_indexes` reads per-season raw files (`raw/games_{season}.json`, `lines_{season}.json`, `weather_{season}.json`, `venues.json`, `conferences.json`, GraphQL tables, …). For an upcoming game:

- Features sourced from `raw_game` (venue id, neutral site, conference game) and `raw_lines` **will resolve**, provided the upcoming fetch writes its raw games/lines JSON where the indexer looks.
- `raw_weather`, `raw_havoc`, `graphql_game_team`, `raw_pregame_wp` are **post-game or near-game** data and will be absent for an unplayed game → `None` → fail closed.
- `raw_team_season` (talent, returning production, recruiting) and `raw_teams`/`raw_coaches` are season-scoped and would resolve **only if** the current season's files have been scraped. They will not exist for 2026 until `scrape --season 2026` is run.

**Which season-to-date stats actually populate — narrower than it first appears.** `_build_running_index` sources `ppa_*` from `raw/ppa_games_{season}.json` and `adv_*` from `raw/advanced_game_stats_{season}.json` (`enrich.py:122-153`). The `upcoming` command fetches games and lines only, so neither file exists for 2026, and **every `ppa_*` and `adv_*` season-to-date field will be `None` for every 2026 game** regardless of how many weeks have been played. The only season-to-date fields that populate from games alone are `games_played`, `win_pct`, and `ats_pct` — and those are `None` until week 2, since week 1 has no priors.

So the fields that reliably resolve for an unplayed game, from data the `upcoming` fetch already writes, are: **matchup features** (neutral site, conference game, venue — via `raw_game`) and **betting-line features** (spread, total, moneylines — via `raw_lines`). Everything else is either post-game or needs a separate scrape.

This is acceptable behavior (fail-closed is the established convention), but it constrains the D-16 example choice — see §Bundled Examples.

Reusing `enrich_games` directly is possible but it hardcodes `load_processed_games` and iterates all games; the cheaper surgical route is a sibling function that takes an explicit games list and an explicit output path. Planner's call — but note that reusing `save_features` as-is would **overwrite `features.json`**, which must not happen.

---

## Reuse Surfaces for the Dashboard

### `run_backtest` result shape

`BacktestResult` (`models.py:95-110`) supplies everything the systems table and sparkline need:

| Need | Source |
|------|--------|
| Record `W-L-P` | `result.wins`, `result.losses`, `result.pushes` |
| Win % | `result.hit_rate` (already a rounded fraction of *decided* bets) |
| Money Won | `result.profit * 100` (the $100-flat-stake convention used everywhere else) |
| ROI | `result.roi` |
| Sparkline series | running sum over `result.bet_details` sorted by `(season, week, game_id)` |
| Per-season figures | `result.season_breakdown` (tuple of `SeasonRecord`: bets/wins/losses/pushes/profit/roi) |
| Type + Fade label | from the `SystemFilter`, not the result (`bet_type`, `fade`) |

`web._cumulative_chart` (`web.py:1190-1225`) is the exact precedent for the sparkline: sort `bet_details` by `(season, week, game_id)`, accumulate, project to SVG coordinates, emit a `polyline` point string. The sparkline is the same function with a different box (96×24 vs 520×150), no axes/zero-line, and a 48-point downsample cap. Write it as a sibling helper rather than parameterizing `_cumulative_chart`, to avoid disturbing the editor chart.

### `describe()`

`describe(system) -> list[{"text": str, "key": str}]` takes **only a `SystemFilter`** — it renders the system's filter sentences and has no per-game variant [VERIFIED: cfb_system_maker/describe.py:89]. So the Current Matches "Matched on" column is the same sentence list for every row of a given system. That is what D-13 asks for; there is no per-game value rendering to build.

The `index.html` path decorates each sentence with `remove_href` and `edit` metadata (`web.py:424-426`). The dashboard needs **neither** — call `describe()` raw and render the `text` values. Do not import `_query_href_removing` into the dashboard; it reads `request.args` and assumes editor query state.

### System enumeration

- `list_systems(data_dir) -> list[str]` — sorted stems of `data/systems/*.json`. Note: **sorted alphabetically**, but UI-SPEC says row order is "most recently saved first." `saved_at` lives inside each JSON, so the dashboard must `load_saved_system` each one and sort on `saved_at` itself.
- `load_saved_system(name, data_dir) -> SavedSystem` — gives `name`, `saved_at`, `system`, `theory`. Both `theory` (UI-SPEC col 1 subtitle, and the Example tab's theory block) and `fade` (col 2 ` · Fade` suffix) are available here. `_system_from_dict` defaults every field, so systems saved before `theory`/`fade` existed load fine.
- Both are `data_dir`-bound and cannot see bundled examples — see §Bundled Examples.

### Route registration

`create_app(data_dir)` registers routes with decorators inside the factory closure (`web.py:375-600`), and helpers close over `app.config["DATA_DIR"]`. Adding a dashboard route and renaming the editor endpoint are both local edits inside that factory. See §Pitfall 3 for the two things that break.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Deciding which games are unplayed | Null-score inference | `Game.completed` | It is a required non-null bool on every row |
| Which CFB week is current | Date arithmetic over game start dates | `GamesApi.get_calendar(year)` | Authoritative non-overlapping `[startDate, endDate]` windows; handles the Tue–Mon boundary |
| Picking one line per game | New provider-precedence logic | `normalize._select_line` | Already owns precedence and the recent cross-provider total fallback fix |
| Building the upcoming record | A parallel normalizer | `normalize.normalize_games` | Verified to work unchanged on future-game payloads |
| Entering-game season-to-date stats | A separate "pregame stats" function | `running_stats.compute_running_stats` | Already emits entering-game snapshots and skips null-score accumulation |
| Deciding if a system matches | A "does this system apply" check in the web layer | `backtest.matches_system` (with the score guard bypassed) | D-11/D-15 single path; duplicating filter logic guarantees eventual divergence |
| Rendering matched filters | Per-game sentence builder | `describe.describe(system)` | D-13 |
| Sparkline / any chart | A charting library | Server-rendered inline SVG, mirroring `_cumulative_chart` | UI-SPEC + PROJECT constraint: no new dependency |
| Serializing datetimes to raw JSON | Manual `isoformat()` sprinkles | `json.dumps(..., default=str)` as `storage.save_raw_json` already does | Consistent with existing raw dumps |

**Key insight:** almost every piece of the "new" pipeline already exists and was written in a way that happens to be correct for unplayed games. The phase is mostly wiring plus one deliberate, surgical guard change — not new algorithms.

---

## Common Pitfalls

### Pitfall 1 — `matches_system` rejects every unplayed game (blocking)

**What goes wrong:** Current Matches renders zero rows, always, in every state.

**Why it happens:** `backtest.py:246-247`:

```python
def matches_system(game, system, feature_map=None) -> bool:
    if game.home_points is None or game.away_points is None:
        return False
```

Every upcoming game has `home_points is None`. Additionally `grade_bet` **raises** `ValueError("game must have spread and final score")` on null scores (`backtest.py:352-353`, and `_grade_total_bet:407-408`).

**How to avoid:** Frame it as a match/grade split, which preserves D-11 and D-15 rather than fighting them:

- **Current Matches matches but never grades.** An unplayed game has no result; there is nothing to grade. It calls `matches_system(game, system, feature_map, require_played=False)` plus `describe(system)`, and never touches `grade_bet` or `run_backtest`.
- **Dashboard figures grade historical games only**, via `run_backtest` over `games.csv`, unchanged.
- Both route through the same `matches_system` filter logic, so there is still exactly one authoritative matching path.

Recommended change: add `require_played: bool = True` and make the guard conditional. This is the most surgical option and defaults to today's behavior at every existing call site (`run_backtest`, `run_backtest_summary`, `_feature_coverage`, `aggregate_filter_value_rows`).

Verified safe: nothing after the guard reads `home_points`/`away_points`. The remainder of `matches_system` reads only `spread`, `total`, `season`, `week`, `provider`, teams, conferences, and the feature map (`backtest.py:248-301`). The guard is pure gating.

**Warning signs:** the acceptance bar is that **every historical figure and every existing test must be byte-identical after the change.** If any `tests/test_backtest.py` or `tests/test_web.py` number moves, the change was not surgical.

### Pitfall 2 — season-to-date features are silently null for upcoming games

**What goes wrong:** systems with any `season_to_date` filter match zero upcoming games and look broken, with no error anywhere.

**Why it happens:** `feature_ok` returns `False` for a `None` value; `compute_running_stats` returns `None` for every rate when `games_played=0`; `games_played` is 0 unless the season's prior games were in the input list. `games.csv` has no 2026 rows.

**How to avoid:** see §Enrichment — fetch the full current season, run running-stats over completed ∪ upcoming, emit features for the upcoming ids.

**Warning signs:** a system that matches hundreds of historical games matches zero upcoming games in week 8. Add a verification step that asserts a known upcoming game has non-null `home_games_played` when prior weeks exist.

### Pitfall 3 — the `/` → `/system` move breaks `/save` and collides on `?tab=`

Two distinct breakages, both easy to miss until runtime:

**(a) `/save` redirects to the wrong page.** `web.py:457,461,462` all call `url_for("index", ...)`, including `redirect(url_for("index", load_system=name))` after a successful save. Once `index` is the dashboard, saving a system dumps the user on the dashboard instead of returning to the editor with their system loaded. The relocated editor endpoint must be repointed in all three places.

**(b) `?tab=` means two different things.** The editor already uses `?tab=graph|matches` (`web.py:421`). UI-SPEC locks the dashboard scope tabs to `?tab=mine|examples`. Therefore:

- The redirect trigger for `/` → `/system` **cannot be "a `tab` param is present"** — that would bounce `/?tab=examples` to the editor.
- Define the trigger as "any *editor* filter param is present": `side`, `bet_type`, `total_side`, `favorite`, `underdog`, `home`, `away`, `fade`, `min_spread`, `max_spread`, `min_total`, `max_total`, `filter_seasons`, `filter_weeks`, `filter_teams`, `filter_conferences`, `filter_providers`, the legacy `season`/`week`/`team`/`conference`/`provider` aliases, the `ff_*` family, `save_name`, `theory`, and `load_system`.
- The dashboard must treat an unrecognized `tab` value as the default `mine`, mirroring how the editor normalizes an unknown `tab` to `graph`.

**(c) Existing tests.** 18 calls across `tests/` hit `"/"`, split roughly between bare `client.get("/")` (asserting editor markup — these must move to `/system`) and `client.get("/?load_system=...")` / `client.get("/" + href)` (which will now 302 — these need `follow_redirects=True` or a `/system` prefix). Templates are safe: `_query_href` and `_query_href_removing` return `"?"`-prefixed **relative** hrefs, which resolve against the current path, so on `/system` they stay on `/system`. Only tests that hardcode `"/" + href` break.

### Pitfall 4 — per-system backtest cost

`run_backtest` over 12,964 games does a full match pass, then `compute_system_stats`, which runs a **1000-iteration permutation test** (`backtest.py:497-503`) plus Wilson CI, z-test, and streaks — then `compute_grade`. Doing that once per (system × timeframe tab) with 13 season tabs is a 14× blowup, and the dashboard displays **neither** the grade nor the permutation p-value.

**How to avoid, without leaving D-11:** every figure the dashboard shows — Record, Money Won, ROI, and the sparkline — is derivable from `bet_details`. Because no filter other than `seasons` depends on season, filtering an all-time `bet_details` list on `bet.season == Y` yields exactly the same bet set as a season-restricted `run_backtest`. So: **one `run_backtest` per system (all-time), then derive each per-season tab and the sparkline from `bet_details`.** `result.season_breakdown` already contains per-season bets/wins/losses/pushes/profit/roi, computed by the same path — the per-season tab figures can come straight from it.

Combine with the D-11 in-memory cache keyed by system identity plus data-file identity (mtime/size of `games.csv` + `features.json`).

**Warning signs:** if the planner writes "run_backtest per system per timeframe," expect a multi-second first paint and a stale-cache bug surface.

### Pitfall 5 — `startTimeTBD` kickoffs

`startTimeTBD=True` games have a placeholder time. Rendering `Sat Sep 6, 3:30 PM` for a TBD kickoff is a factual error on a page whose whole purpose is telling the user what to bet. The copywriting contract has no TBD variant — the planner should add one (date only, or `TBD` in place of the time).

### Pitfall 6 — `save_features` would clobber `features.json`

`save_features` writes to a fixed path, `data_dir/processed/features.json` (`enrich.py:29`). Reusing it for upcoming features would overwrite the historical sidecar. The upcoming features must go to a distinct path.

### Pitfall 7 — the whole feature is exercised in the offseason

Today is 2026-07-20; the next regular-season week starts 2026-08-29. The primary state (D-07) is the amber offseason notice plus a most-recent-week fallback. That means: the fallback path is what gets built, tested, and reviewed, while the populated current-week path will not be exercised live for ~5 weeks. Verification must lean on fixtures with an injected fake client (see §Testability), not on "run the command and look."

---

## Bundled Examples (DASH-02)

**There is no `pyproject.toml`, `setup.py`, or `MANIFEST.in` in this repo** [VERIFIED: repo root listing]. The package is never pip-installed — it runs from the repo root as `python -m cfb_system_maker`, and `cfbd-python` is loaded by path injection. So there is **no packaging or package-data problem to solve**: bundled examples are plain files in a directory under `cfb_system_maker/` (e.g. `cfb_system_maker/examples/*.json`), located via `Path(__file__).parent / "examples"`. Do not reach for `importlib.resources`; it would be complexity with no payoff here.

Contracts the example JSON must satisfy:

- **Filename stem must match `_SYSTEM_NAME_RE = ^[A-Za-z0-9_-]+$`** (`storage.py:13`) if the name ever flows through `load_saved_system`, `load_system`, or the "Copy to My Systems" path (which calls `save_system`). No spaces, no dots. `home-favorites`, not `Home Favorites`.
- **JSON must match `_system_to_dict` output** (`storage.py:128-162`): top-level `name`, `saved_at`, `theory`, and a nested `system` object. `_system_from_dict` defaults every field, so a minimal example file is legal, but writing full files keeps them diffable against saved systems.
- The simplest way to author them correctly is to build each in the editor, save it, and copy the resulting `data/systems/*.json` into the package dir.

`list_systems`/`load_saved_system` are `data_dir`-bound and cannot see the package dir, so the phase needs a small examples enumerator/loader. Keep it a thin sibling that reuses `_system_from_dict` rather than a parallel parser.

### Choosing the D-16 example filters

The point of the examples is that an empty install has something that visibly *works*. An example that matches zero current games fails DASH-02 even though it loads fine. Three constraints, all derived above:

1. **No provider filter** — `consensus` is gone from recent data and upcoming rows carry `DraftKings`/`Bovada` (§Provider drift).
2. **No weather feature** — weather is near-game data that will not exist for an unplayed game (§Non-running features).
3. **Prefer a matchup or line-derived feature over a season-to-date stat** for the registry-feature example (D-16's third slot). Season-to-date stats look like the obvious choice, but per §Non-running features: `ppa_*`/`adv_*` are `None` for all of 2026 (their source files are never scraped by the `upcoming` command), and `win_pct`/`ats_pct` are `None` in week 1. A season-to-date example would therefore show zero matches during exactly the offseason-and-early-season window this phase ships in. Matchup features (neutral site, conference game) and line features (spread/total range) populate for any unplayed game with a posted line.

**This choice is coupled to Open Question 1 and cannot be decided independently of it.** If the D-07 fallback resolves *backward* to a played mid-season week, priors exist and a season-to-date example works. If it resolves *forward* to 2026 week 1, a season-to-date example shows nothing. Decide the fallback direction first, then pick the example filter to match — a pair that looks internally consistent can still be broken.

---

## Runtime State Inventory

This is not a rename/refactor phase, but the `/` → `/system` relocation has URL-shaped state worth an explicit pass:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — `data/systems/*.json` store `SystemFilter` fields, not URLs. `games.csv` untouched by D-01. | None |
| Live service config | None — local Flask app, no external service holds a route reference | None |
| OS-registered state | `launch.bat` opens `http://127.0.0.1:5000` — still correct, that is the dashboard now (intended) | None (verified by reading `launch.bat`) |
| Secrets/env vars | None — `env.env` holds `CFBD_API_KEY` only; the upcoming fetch reuses `find_cfbd_token` unchanged | None |
| Build artifacts | `cfb_system_maker/__pycache__` only; no installed package (no pyproject/setup.py) | None |
| **User-facing URLs** | Bookmarks/shared links to `/?<filters>` | Handled by D-09's redirect — see Pitfall 3 for the trigger definition |
| **Tests** | 18 `get("/")` call sites across `tests/` | Must be split between `/system` and redirect-following |
| **In-code `url_for("index")`** | 3 call sites in `web.py` `/save` (lines 457, 461, 462) | Repoint to the editor endpoint |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | everything | ✓ | 3.14 (system), venv at `.venv` | — |
| pydantic | vendored `cfbd-python` client | ✓ **in `.venv` only** | 1.10.26 (venv) / **2.13.4 (system)** | none — see note |
| Flask | web app | ✓ | per requirements.txt | — |
| pytest | tests | ✓ | per requirements.txt | — |
| CFBD API token | upcoming fetch | ✓ | `env.env` | — |
| CFBD REST API (games/lines/calendar) | upcoming fetch | ✓ | responding, auth tier sufficient | — |
| `games.csv` (2013–2025, 12,964 rows) | dashboard figures | ✓ | — | — |
| `features.json` | feature filters | ✓ | — | web already degrades gracefully (`_try_load_features`) |
| 2026 season raw scrape | non-running upcoming features | ✗ | — | fail closed (`None`) — acceptable, see §Non-running features |
| Chart library | sparkline | ✗ (by design) | — | hand-rolled inline SVG, per UI-SPEC |

**Environment note — must be in the plan:** the vendored `cfbd-python` client requires **pydantic v1**. The system Python 3.14 has pydantic 2.13.4, and importing `cfbd` under it fails hard:

```
PydanticUserError: `const` is removed, use `Literal` instead
```

The project `.venv` has pydantic 1.10.26 and works. Any command touching the CFBD client — including the new `upcoming` command and its tests — must run under `.venv/Scripts/python.exe`, not bare `python`. [VERIFIED: both interpreters exercised 2026-07-20]

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** 2026 raw scrape (fails closed to `None` features).

---

## Project Constraints (from CLAUDE.md)

From `./CLAUDE.md`, `./.claude/CLAUDE.md`, and the user-level file — all carry locked-decision authority:

| Constraint | Source | Impact on this phase |
|------------|--------|----------------------|
| Flask + Jinja + vanilla JS/CSS; no frontend framework, no chart library, no new dependency | `.claude/CLAUDE.md` | Sparkline is hand-rolled SVG; dashboard needs no JS at all |
| `GameRecord` field order **is** the `games.csv` contract | `CLAUDE.md` | D-01's separate upcoming file exists precisely to honor this |
| No lookahead — features must be entering-game | `CLAUDE.md` | `compute_running_stats` verified safe for unplayed games |
| Spread sign convention: `GameRecord.spread` is always the **home** spread | `CLAUDE.md` | D-08 play text must negate for away side — reuse `_side_spread` |
| Null feature values fail closed | `CLAUDE.md` | Explains, and is the correct response to, several upcoming-game gaps |
| `SavedSystem` JSON changes must default gracefully | `.claude/CLAUDE.md` | `_system_from_dict` already defaults everything; examples inherit this |
| **Simplicity first** — no speculative abstraction, no unrequested flexibility | all three CLAUDE.md files | Argues for `require_played` flag over a new matcher; for a plain examples dir over `importlib.resources`; against parameterizing `_cumulative_chart` |
| **Surgical changes** — touch only what you must, match existing style | all three | The `matches_system` guard change and the `/save` repoint are the only edits to existing behavior |
| Goal-driven: state success criteria, verify each step | all three | "All existing tests produce identical numbers" is the acceptance bar for the guard change |
| Don't edit `cfbd-python/` — it is a vendored dependency | `CLAUDE.md` | The pydantic v1 constraint is inherited, not fixable here |
| GSD workflow enforcement — no direct edits outside a GSD command | `.claude/CLAUDE.md` | Execution happens under `/gsd-execute-phase` |
| `env.env` holds the real key — never commit or echo | `CLAUDE.md` | Observed: no token value appears in this document |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `consensus` as the canonical line provider | Real sportsbook names (ESPN Bet / DraftKings / Bovada) | ~2023 in CFBD data | `--provider consensus` is now a no-op fallback; provider filters won't match upcoming games |
| Inferring "unplayed" from null scores | `Game.completed` boolean | present in OpenAPI 5.16.0 | Explicit, non-null, no inference needed |
| Deriving week boundaries from game dates | `GamesApi.get_calendar(year)` | present | Authoritative windows; makes offseason detection trivial |

**Deprecated/outdated:** nothing in this phase's surface is deprecated. The vendored client targets OpenAPI 5.16.0 and pydantic v1; upgrading it is explicitly out of scope.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | In-season line coverage for the current week is materially higher than the 52% observed for 2026 week 1 five weeks out | §Upcoming Pipeline #2 | Cosmetic — panel shows fewer rows than expected; D-04 already excludes line-less games |
| A2 | `get_calendar` week windows remain non-overlapping and gapless for the whole season (verified for 2026 weeks 1-3 only) | §Current-week detection | A gap between windows would produce a false "offseason"; mitigated by the D-07 fallback |
| A3 | Postseason (`season_type="postseason"`) is out of scope for the current-week lookup | §Current-week detection | Bowl-season games would not appear; D-03 says "current CFB week" without specifying season type — worth a planner decision |
| A4 | Weather data is unavailable for upcoming games (inferred from `raw_weather` being a per-season scraped file, not probed live) | §Non-running features | If wrong, weather is a viable D-16 example after all — cheap to check before authoring the example |

---

## Open Questions

1. **Should the offseason fallback fetch the *next* scheduled week?**
   - What we know: 2026 week 1 already has real lines on 51 games today. D-07 mandates an offseason notice plus most-recent-week-with-data fallback.
   - What's unclear: whether "most recent week with data" means the last *played* week (2025 postseason) or whether showing next season's week 1 would better demonstrate the feature.
   - Recommendation: planner decision. Note that D-07's wording ("the most recent week that does have data") points backward, but the phase is being built in an offseason where the forward-looking data is the more useful demo.
   - **Decide this before choosing the D-16 example filters** — the two are coupled (see §Choosing the D-16 example filters). A backward fallback to a mid-season week makes a season-to-date example viable; a forward fallback to 2026 week 1 makes it show zero matches.

2. **Postseason handling for current-week detection (A3).**
   - What we know: `get_calendar` and `get_games` both take `season_type`; the existing pipeline uses `"regular"` throughout.
   - What's unclear: whether Current Matches should surface bowl/playoff games.
   - Recommendation: match the existing `"regular"` default for Phase 5; note it as a known limitation rather than expanding scope.

3. **TBD-kickoff copy (Pitfall 5).**
   - Recommendation: planner adds a date-only variant to the copywriting contract; not a research question.

4. **Where the `require_played` split is drawn.**
   - Options: a `require_played: bool = True` param on `matches_system` (recommended — most surgical, default preserves all call sites), or lifting the guard into `run_backtest`'s comprehension (also correct, touches more call sites).
   - Recommendation: the flag. Either way, the acceptance bar is identical historical figures and unchanged tests.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (from `requirements.txt`) |
| Config file | `pytest.ini` (`testpaths=tests`, so `cfbd-python`'s own tests are excluded) |
| Quick run command | `.venv/Scripts/python.exe -m pytest tests/test_web.py -x` |
| Full suite command | `.venv/Scripts/python.exe -m pytest` |

Use the venv interpreter — see §Environment Availability.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DASH-01 | Bare `/` renders the dashboard with a systems table | unit (Flask client) | `pytest tests/test_web.py -k dashboard -x` | ❌ Wave 0 |
| DASH-01 | `/system` renders the editor identically to today's `/` | unit | `pytest tests/test_web.py -k editor_route -x` | ❌ Wave 0 |
| DASH-01 | `/` with editor filter params 302s to `/system` with query string intact | unit | `pytest tests/test_web.py -k redirect -x` | ❌ Wave 0 |
| DASH-01 | `/?tab=examples` does **not** redirect (Pitfall 3b) | unit | `pytest tests/test_web.py -k tab_collision -x` | ❌ Wave 0 |
| DASH-01 | `/save` returns to the editor with the system loaded | unit | `pytest tests/test_web.py -k save_redirect -x` | ❌ Wave 0 |
| DASH-01 | Sparkline: 0 bets → `—`; 1 bet → flat segment; >48 points → downsampled | unit (pure fn) | `pytest tests/test_web.py -k sparkline -x` | ❌ Wave 0 |
| DASH-01 | Per-season tab figures equal a season-restricted `run_backtest` | unit | `pytest tests/test_backtest.py -k season_tab_equivalence -x` | ❌ Wave 0 |
| DASH-02 | Bundled examples enumerate, load, and render on the Examples tab | unit | `pytest tests/test_web.py -k examples -x` | ❌ Wave 0 |
| DASH-02 | Example filenames satisfy `_safe_system_name` and round-trip `_system_from_dict` | unit | `pytest tests/test_storage.py -k example_systems -x` | ❌ Wave 0 |
| DASH-03 | `matches_system(require_played=False)` matches an unplayed game | unit | `pytest tests/test_backtest.py -k unplayed -x` | ❌ Wave 0 |
| DASH-03 | **Regression:** default `matches_system` still rejects unplayed games; all historical figures unchanged | unit | `pytest tests/test_backtest.py -x` (existing suite must pass untouched) | ✅ exists |
| DASH-03 | `normalize_games` produces a record from a future-game payload with `None` scores | unit | `pytest tests/test_normalize.py -k upcoming -x` | ❌ Wave 0 |
| DASH-03 | `compute_running_stats` gives non-null entering-game stats to an unplayed week-N game when weeks 1..N-1 are present | unit | `pytest tests/test_running_stats.py -k unplayed_entering -x` | ❌ Wave 0 |
| DASH-03 | `upcoming` CLI writes a valid file network-free via an injected fake client | unit | `pytest tests/test_cli.py -k upcoming -x` | ❌ Wave 0 |
| DASH-03 | Offseason: command and panel both produce the empty state, no crash | unit | `pytest tests/test_cli.py -k offseason -x` | ❌ Wave 0 |
| DASH-03 | Panel renders play text per bet type (`Play Georgia -7` / `Play Over 52.5`), away side negated | unit | `pytest tests/test_web.py -k play_text -x` | ❌ Wave 0 |
| DASH-03 | Missing upcoming file → documented error state naming the CLI command | unit | `pytest tests/test_web.py -k missing_upcoming -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `.venv/Scripts/python.exe -m pytest tests/test_web.py tests/test_backtest.py -x`
- **Per wave merge:** `.venv/Scripts/python.exe -m pytest`
- **Phase gate:** full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_running_stats.py` — no dedicated file today; running-stats coverage needed for the unplayed-game entering-state assertion
- [ ] Fake-CFBD fixture for the upcoming fetch (mirror the `tests/test_scrapers.py` fake-module pattern) — covers DASH-03
- [ ] Upcoming-games fixture data (a completed-weeks + current-week payload) usable without network
- [ ] Existing `tests/test_web.py`: 18 `get("/")` call sites must be re-pointed to `/system` or given `follow_redirects=True` **before** the route move lands, or the suite goes red mid-wave

---

## Security Domain

Local single-user tool, no auth, no network listener beyond `127.0.0.1`. ASVS categories are assessed against that reality.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No users, no login; `app.run(host="127.0.0.1")` |
| V3 Session Management | no | Stateless GET pages, no cookies or sessions |
| V4 Access Control | **yes (path traversal)** | `_safe_system_name` regex gates every filesystem read/write of a system name — the examples loader and "Copy to My Systems" **must** reuse it, not bypass it |
| V5 Input Validation | **yes** | Existing `parse_system_strict` allowlist; the dashboard's new `tab`/`timeframe` params must be normalized to known values (mirroring the editor's `_valid_choice`), never used to build a path |
| V6 Cryptography | no | No crypto in scope; `env.env` token is read, never logged |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via system name (`../../etc`) | Tampering | `_safe_system_name` `^[A-Za-z0-9_-]+$` — already covered by `tests/test_web.py` traversal tests; extend to the examples loader |
| Stored XSS via `theory` / system name rendered on the dashboard | Tampering | Jinja autoescaping; **never** `|safe`. UI-SPEC already mandates this; `test_web_theory_is_escaped_and_never_rendered_via_safe_filter` is the existing precedent to extend |
| API token leaking into raw dumps or logs | Info Disclosure | Token is only passed to `Configuration`; never written to `data/` |
| Timeframe/tab param used to build a filesystem path | Tampering | Normalize to a known set; the timeframe is an `int` season or `"all"` |
| Malformed upcoming file crashing the page | DoS (self-inflicted) | Treat a missing/unparseable upcoming file the same way `_try_load_features` treats a missing sidecar — degrade to the documented empty state |

---

## Sources

### Primary (HIGH confidence)

- `cfbd-python/cfbd/models/game.py` — `completed`, `startDate`, `startTimeTBD`, nullable points
- `cfbd-python/cfbd/models/betting_game.py`, `game_line.py` — future-line row shape
- `cfbd-python/cfbd/models/calendar_week.py`, `game_status.py` — week windows; `GameStatus` is not on `Game`
- `cfbd-python/cfbd/api/games_api.py`, `betting_api.py` — `get_games`, `get_lines`, `get_calendar` signatures
- **Live CFBD API probe, 2026-07-20** — 2026 wk1 (99 games / 99 incomplete / 51 with lines), 2025 wk5 + wk15, `get_calendar(2026)`, provider distributions
- `cfb_system_maker/backtest.py` — score guard at 246-247; `grade_bet` raises at 352-353; permutation at 497-503
- `cfb_system_maker/running_stats.py` — entering-game snapshot before accumulation (43-61)
- `cfb_system_maker/enrich.py`, `normalize.py`, `web.py`, `storage.py`, `describe.py`, `models.py`, `cli.py`, `features.py`
- `data/processed/games.csv` — 2013–2025, 12,964 rows, provider distribution
- Repo root listing — no `pyproject.toml`/`setup.py`/`MANIFEST.in`
- Both interpreters exercised — pydantic 2.13.4 (system, fails) vs 1.10.26 (`.venv`, works)

### Secondary (MEDIUM confidence)

- `docs/bet-labs-parity-plan.md` §1.1 and §"Phase 4" items 12–13 — pipeline sketch; corroborates the approach and the line-movement caveat, and independently states "`matches_system` needs no result fields" (which this research corrected: it *does* guard on them today)
- `.planning/phases/05-dashboard-current-matches/05-CONTEXT.md`, `05-UI-SPEC.md`, `.planning/REQUIREMENTS.md`
- `CLAUDE.md`, `.claude/CLAUDE.md`

### Tertiary (LOW confidence)

- None. No claim in this document rests on WebSearch or unverified training knowledge; the four `[ASSUMED]` items are logged above.

---

## Package Legitimacy Audit

**Not applicable.** This phase installs no external packages. PROJECT constraints and UI-SPEC both forbid new runtime or build dependencies, and every capability researched here is served by existing code or the standard library. No registry lookups were required.

---

## Metadata

**Confidence breakdown:**

- CFBD upcoming-game shapes: **HIGH** — read from vendored source and confirmed by live API probe
- Current-week detection: **HIGH** — `get_calendar` probed live; offseason branch verified against today's date
- Enrichment integration: **HIGH** — `compute_running_stats` traced line by line; the `games.csv` season gap confirmed by direct inspection
- `matches_system` blocker: **HIGH** — exact line numbers; verified nothing after the guard reads score fields
- Routing breakages: **HIGH** — `url_for("index")` call sites and the `?tab=` collision read directly from `web.py` and UI-SPEC
- Performance recommendation: **HIGH** — permutation cost read from source; season-derivation equivalence follows from `matches_system` having no other season-dependent filter
- Examples packaging: **HIGH** — absence of packaging files verified
- Line coverage percentages in-season: **MEDIUM** — one offseason probe (A1)

**Research date:** 2026-07-20
**Valid until:** ~2026-08-19 (30 days). Re-verify line coverage and provider mix once the season starts; the CFBD schema itself is stable.
