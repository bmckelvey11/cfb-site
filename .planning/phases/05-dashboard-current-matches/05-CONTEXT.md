# Phase 5: Dashboard & Current Matches - Context

**Gathered:** 2026-07-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Turn the backtester into a tool checked weekly. A My Systems dashboard becomes the landing page, listing every saved system with its record, money won, ROI, and a sparkline. A Current Matches panel shows the upcoming (unplayed) games each saved system currently matches, with the matched-filter details per game. A new upcoming-games data path feeds that panel. Two or three bundled example systems ship so an empty install has something to open.

This phase does not add teaser/alternate-line records (DASH-04, descoped 2026-07-20 — see Deferred Ideas), new wager types, new data sources beyond the upcoming-games path, multi-user sharing, or changes to how filters are configured.

</domain>

<decisions>
## Implementation Decisions

### Upcoming-games data path

- **D-01:** Unplayed games live in a **separate processed file** (e.g. `data/processed/upcoming.csv`), not in `games.csv`. `games.csv` keeps its current contract — 12,964 completed games, `GameRecord` field order unchanged, no `played` flag, no CSV migration. This keeps it structurally impossible for the historical backtest path to grade an unplayed game.
- **D-02:** The upcoming file is produced by a **new CLI command** (e.g. `python -m cfb_system_maker upcoming --data-dir data`). The web app remains a pure local-file reader — no CFBD network calls from a Flask request handler, consistent with every existing page.
- **D-03:** "Upcoming" means the **current CFB week only**, matching the existing week-based data model and Bet Labs' upcoming panel. Not a rolling date window, not all remaining unplayed games.
- **D-04:** Games with **no posted betting line are excluded**. No line means no spread/total to filter on and no bet to place; this follows the existing null-fails-closed convention rather than rendering un-evaluable rows.
- **D-05:** Upcoming games are **enriched through the same feature path as historical games**, so any saved system evaluates correctly — including systems filtering on `computed_running` season-to-date stats. These are entering-game by construction, so no lookahead is introduced. A system silently failing to match because its features could not be computed is a worse outcome than the extra work.
- **D-06:** The panel displays the **fetch timestamp** of the upcoming data ("Lines as of ..."). Line movement changes which games a system matches; the timestamp is the honest minimum. No in-page refresh button (that would reintroduce a network call on page load).
- **D-07:** In the **offseason or any week with no upcoming games**, the panel shows an explicit empty state *plus* the matches from the most recent week that does have data. This keeps the feature visible and testable year-round (the phase is being built in July; the next real games are ~5 weeks out).
- **D-08:** Each row's play text **mirrors the system's bet type** — spread systems read "Play Georgia -7", total systems read "Play Over 52.5" — derived from the system's existing `side` / `total_side` so the displayed play cannot disagree with what would be graded.

### Dashboard layout and routing

- **D-09:** The dashboard is served at `/` and the system editor moves to `/system`. A request to `/` **carrying filter query parameters redirects to `/system`** with the query string intact, so existing bookmarks and shared links keep working. A bare `/` shows the dashboard.
- **D-10:** Timeframe tabs are **All Time + per-season**. Bet Labs' "30 Days" / "7 Days" windows are not offered — `games.csv` has no kickoff dates, and the parity plan already recommends deferring them for this reason.
- **D-11:** Dashboard figures are **computed on request via the existing `run_backtest` path and cached in memory**, keyed by system plus data-file identity. No second grading path, no precomputed numbers persisted into saved-system JSON (which would go stale silently after a data rebuild).
- **D-12:** **Current Matches renders as a panel on the dashboard**, showing all systems' matches together — matching Bet Labs' layout and making one page answer "what do I bet this week."
- **D-13:** Matched-filter details per game **reuse the existing `describe()` sentence renderer** from Phase 1 rather than a second rendering path.

### Bundled example systems

- **D-14:** Examples are **checked-in `SavedSystem` JSON files in the package, loaded read-only**. They are not copied into the user's data directory on first run and cannot be overwritten in place; editing one is a "copy to My Systems" action.
- **D-15:** Examples appear on a **separate "Example Systems" tab**, not mixed into the My Systems table, so the user's own list is never padded with systems they did not build.
- **D-16:** Ship **one example per capability** — a spread system, a total system, and one exercising a registry feature (e.g. weather or a season-to-date stat). The goal is to demonstrate the tool's range, not to present profitable angles as recommendations.
- **D-17:** Each example carries a **short written `theory`** (the free-text field from Phase 1), one or two sentences on why the angle might exist — modelling the habit of recording reasoning before trusting a backtest.

### Added 2026-07-20 after research (05-RESEARCH.md findings)

- **D-18:** `matches_system` currently returns `False` for every unplayed game (`backtest.py` guards on non-null scores). Resolve this with a **`require_played=False` flag on the existing matching path**, not a parallel matcher. Current Matches *matches but never grades* — there is no result to grade — so this preserves the single-authoritative-path rule (Phase 4 D-15) rather than forking it. Research verified no code after the guard reads score fields. Placeholder/fake scores are explicitly rejected: a placeholder in a grading path is how a fake result eventually gets counted as real.
- **D-20:** **The D-07 offseason fallback resolves BACKWARD** — to the most recent *completed* week (games with results), not forward to the next week that happens to have lines posted. Rationale: it works in any offseason rather than depending on books posting early, it exercises the full matching path against data that can be sanity-checked, and it is honest about being a look-back. Forward resolution would still need the backward path as a second fallback in a true dead zone, making it two behaviors instead of one.
- **D-21:** **The third example system (D-16) uses a matchup or line-derived feature, not a season-to-date stat.** Season-to-date fields (`ppa_*`, `adv_*`, `win_pct`, `ats_pct`) are null for all of 2026 until games are played, so a season-to-date example would render zero matches during exactly the window this ships in — the worst possible first impression for a bundled example. This decision is coupled to D-20 and was made with it.
- **D-19:** **Postseason is in scope.** "Current CFB week" (D-03) includes bowls and the playoff, so `season_type` must be threaded through rather than left hardcoded to `"regular"`. Rationale: the tool would otherwise go silent through December–January, the part of the season with the most betting interest. Note that postseason weeks are numbered differently — the calendar lookup must handle this.

### Claude's Discretion

- Sparkline rendering approach, dashboard table column order and widths, tab styling, cache invalidation mechanics, and the exact name/flags of the upcoming CLI command are planner/implementation choices, provided the decisions above hold.
- The exact schema of the upcoming file is a planner decision. It is *not* bound by the `GameRecord` CSV field-order contract, since it is a separate file; it will need kickoff date/time, which `GameRecord` does not carry.
- Exact wording of empty states and the fetch-timestamp line.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap and requirements
- `.planning/ROADMAP.md` §"Phase 5: Dashboard & Current Matches" — phase goal, dependencies, success criteria (note: teaser criterion removed 2026-07-20).
- `.planning/REQUIREMENTS.md` — DASH-01, DASH-02, DASH-03 are in scope. DASH-04 (teasers) is deferred out of this phase.
- `.planning/PROJECT.md` — core value, project constraints, no-new-dependencies rule.

### Bet Labs behavior and visual target
- `docs/bet-labs-parity-plan.md` §1.1 "Dashboard" — dashboard anatomy, My Systems / Example Systems tabs, Current Matches panel columns.
- `docs/bet-labs-parity-plan.md` §"Phase 4 — Dashboard + current matches" (items 12–13) — the upcoming-games pipeline sketch this phase implements, including the line-movement caveat.
- `docs/sports-insights-systems-combined-guide.md` — underlying Sports Insights documentation; use only where the parity plan is ambiguous.

### Prior phase decisions
- `.planning/phases/01-system-editor-main-page/01-CONTEXT.md` — query-string/full-page GET state model, stat chips, cumulative-profit chart, `describe()` filter sentences, theory field.
- `.planning/phases/02-integrity-fade-grade/02-CONTEXT.md` — Fade and Grade semantics the dashboard's per-system figures must preserve.
- `.planning/phases/04-filter-popup-modal/04-CONTEXT.md` — D-15 (one authoritative grading path), D-23 (Flask + Jinja + vanilla JS, no framework or chart dependency), and the existing visual vocabulary.

### Code
- `cfb_system_maker/web.py` — `create_app`, current routes (`/`, `/save`, `/compare`, `/api/backtest`, `/filter-detail`), form parsing, `_feature_options`.
- `cfb_system_maker/storage.py` — `save_system`, `load_saved_system`, `list_systems`, `_system_to_dict`; the saved-system JSON contract examples must conform to.
- `cfb_system_maker/models.py` — `GameRecord` (note: no kickoff date, no completed flag), `SavedSystem`, `SystemFilter`.
- `cfb_system_maker/backtest.py` — `run_backtest`, `matches_system`, `grade_bet`; the single authoritative source for every figure the dashboard shows.
- `cfb_system_maker/describe.py` — filter-sentence renderer to reuse for matched-filter details.
- `cfb_system_maker/cfbd_client.py` — `fetch_games_and_lines`, token resolution; the starting point for the upcoming fetch path.
- `cfb_system_maker/normalize.py` — game/line join and `_select_line`; the upcoming path should reuse this rather than reimplement line selection.
- `cfb_system_maker/enrich.py`, `cfb_system_maker/running_stats.py` — the entering-game feature computation that must also cover upcoming games (D-05).
- `cfb_system_maker/templates/index.html`, `cfb_system_maker/static/styles.css` — existing chips, tables, tabs, and SVG chart language to extend.
- `tests/test_web.py` — established Flask client assertion patterns; primary home for dashboard and Current Matches route tests.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `run_backtest` / `matches_system` / `grade_bet` — one grading path for dashboard figures, Current Matches evaluation, and the editor. Do not add a second.
- `describe()` — already renders plain-English filter sentences; directly reusable for the per-game matched-filter details column (D-13).
- `list_systems` / `load_saved_system` — saved-system enumeration already exists; the dashboard is largely a new view over it.
- `normalize_games` / `_select_line` — the games↔lines join, including the recent cross-provider total fallback fix, applies unchanged to upcoming games.
- `compute_running_stats` — entering-game by construction; works for an unplayed game given that season's prior games.
- Existing stat chips, tables, `.positive`/`.negative` classes, and server-rendered SVG chart give the dashboard and sparkline their visual vocabulary with no new dependency.

### Established Patterns
- Flask + Jinja server rendering, vanilla JS, GET query string as system state.
- Frozen dataclasses; form parsing constructs new immutable values.
- Null feature values fail closed — a system does not match rather than matching loosely.
- `GameRecord` field order **is** the `games.csv` read/write contract (project CLAUDE.md); this is precisely why upcoming games get their own file (D-01).
- CLI stages persist to disk between steps (`fetch` → `build` → `enrich` → `backtest`); the upcoming path follows the same shape.

### Integration Points
- New routes in `create_app`: dashboard at `/`, editor relocated to `/system`, redirect logic for filtered `/` requests.
- New CLI subcommand registered alongside `fetch` / `build` / `enrich` / `scrape` / `graphql`.
- New processed file read by the dashboard alongside `games.csv` and `features.json`.
- Bundled example JSON files ship inside the package and are enumerated separately from the user's `data/` systems.

</code_context>

<specifics>
## Specific Ideas

- The dashboard should read like Bet Labs' `dashboard.aspx`: systems table on the left, Current Matches panel on the right, so one page answers "what do I bet this week."
- Current Matches is the feature that converts historical research into actionable output — it is the centerpiece of the phase, not a side panel.
- Examples exist to demonstrate the tool's range and to model writing down a theory, not to present profitable angles as advice.
- The line-movement caveat is real and should be visible, not buried: a system's matches genuinely change as lines move during the week.

</specifics>

<deferred>
## Deferred Ideas

- **Teaser / alternate-line records (DASH-04)** — descoped from Phase 5 on 2026-07-20 at the user's request, mid-discussion. Partial decisions captured before shelving, for whenever it is picked up: favorable-direction-only ladder (6 / 6.5 / 7 / 10 points), surfaced as a popover from the editor's Record chip. **Two questions were never answered:** (a) whether to show money/ROI at all, given that teasers do not price at -110 and a flat-stake dollar figure would overstate profit in the optimistic direction; (b) whether total systems are included (over teases down, under teases up). ROADMAP.md success criteria and REQUIREMENTS.md were updated to match this descope.
- Timeframe windows based on real dates ("30 Days", "7 Days") — needs kickoff timestamps in the historical data; deferred per the parity plan.
- In-page refresh button for upcoming data — rejected for Phase 5 because it puts a network call behind a page load (D-06).
- Grade sub-score breakdown panel — still deferred from Phase 2.
- Think Tank / multi-user sharing, moneyline wager type, public betting percentages — project-level out of scope.

</deferred>

---

*Phase: 5-Dashboard & Current Matches*
*Context gathered: 2026-07-20*
