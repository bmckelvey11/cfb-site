# Bet Labs Parity Plan

Steps to make `cfb_system_maker` function like Sports Insights Bet Labs, based on
[docs/sports-insights-systems-combined-guide.md](sports-insights-systems-combined-guide.md)
and its 34 screenshots (`C:/Users/mckel/Documents/Codex/2026-07-16/how/outputs/sports-insights-systems/`).

Written 2026-07-16. Companion to
[superpowers/plans/2026-07-16-next-steps-roadmap.md](superpowers/plans/2026-07-16-next-steps-roadmap.md) —
data download (roadmap item 1) is a prerequisite for everything here.

---

## 1. What the screenshots show (GUI inventory)

### 1.1 Dashboard (`dashboard.aspx` screenshot)

- **Add System panel**: Name, Sport, Line Type (Spread / Moneyline / O-U), Event Type → "Create System" button.
- **My Systems / Example Systems tabs**: table with Description, System Type, Money Won, Last 10. Example systems ship with the product so a new user has something to open.
- **Current Matches panel** (right side): today's/upcoming games each saved system points at. Columns: Time, Play ("Play on Atlanta Falcons"), System name, System Type, and a Details column listing the filter values that matched (Season: 2013-14, Favorite/Dog: Dog, Spread Range: 3).
- **Past Matches tab** next to Current Matches.
- Later version ("My Systems" screenshot): timeframe tabs **All Time / Season / Since Built / 30 Days / 7 Days**, search box, per-system Record + Money Won (ROI) recomputed for the chosen window.

### 1.2 System editor page (the core screen, most screenshots)

- **Header row**: system name + wager type label ("September Division Dogs — *NFL Spread*"), then stat chips:
  - **Record** `177-137-12, 56.4%` (blue chip; clickable → teaser popover)
  - **Margin** `0.5` (average cover margin)
  - **Money Won** `+$3,114` (green/red chip; flat $100 per bet, so $ = units × 100)
  - **ROI** `9.6%` (green/red chip)
  - **Grade** `A` (letter badge A/B+/C/D)
- **Top-right controls**: Widget (embed), Copy, Rename, Delete buttons; **Hide Duplicates** and **Fade System** checkboxes.
- **Theory field**: free-text hypothesis line with (Edit) — "Fade Elite MLB teams at the end of the year." Shown above the filter list; placeholder nags "Add the theory behind your system."
- **Filter list**: one row per active filter — pencil Edit | filter name | **plain-English sentence** ("the team's win percentage is between 60% and 100%", "the game was played in October or September") | red ✕ delete.
- **Filter category sidebar** (left): collapsible groups — Team Info, Line Info, Public Betting Data, Time Period, Matchup Info, Streaks, Statistics, Stat Streaks, Player/Coach Info, Weather, Event, Long-Term/Recent Form Stats — each expanding to individual filters (Team Info alone: Favorite/Dog, Home/Visitor, Team, Opposing Team, Team Win %, Opponent Win %, Team ATS %, Opponent ATS %, Pythagorean Win %, Pythagorean +/-, Team ATS at Home/as Visitor, Prev Season Wins/Postseason, Prev Game Home-Visitor/Fav-Dog…).
- **Tabs under the filter list**: **Results Graph | Past System Picks | Current System Picks**.
- **Results Graph**: cumulative **"Money Won Over Time"** line chart, x = date (2005→2020), y = $. Green when the running total is winning, red segments through losing stretches; hover tooltip shows date + value. This is the primary judge-the-system visual (consistent up-and-right vs "EKG").

### 1.3 Filter detail modal (video screenshots)

Opening any filter shows a modal with **live stats before you commit**:

- **Modal header**: filter name + live chips (Record, Money Won, ROI) recomputed for the current system *plus this candidate filter* as you move the controls; "List View" toggle.
- **Range filters** (OU %, Spread %, Rank, Days Between Games, Off Points Streak): dual-handle slider + "BETWEEN x AND y" inputs, and a **money-won-by-value mini chart** — profit at each individual value of the filter across the whole distribution, green/red dots, so users see *where* the edge lives before choosing endpoints.
- **List filters** (Opposing Team, Win/Loss Streak, Opp Prev Game Home/Visitor, Moneyline List): searchable, sortable table — checkbox | Description | **Record | ROI | Money** per value. Users sort by Money to find profitable values (this is also how overfitting happens — see grade).
- **About Filter panel**: exact definition text ("A rank of zero means the team was unranked", "A value of 1 means back-to-back games").
- **Save Filter** button commits it to the system.

### 1.4 Quality/integrity features

- **System Grade breakdown** (overfit_2 screenshot): panel of sub-scores each with its own letter — *ROI Score (Z-Score)*, *Overfitting Score — Too Many Selected Items* (e.g. 27 pitchers hand-picked in one list filter → D), *Overfitting Score — Too Many Filters* — rolled into the header Grade.
- **Fade System checkbox**: inverts the system — bet against the matched team. Screenshots show the filter row literally flipping "Team Win %" → "Opponent Win %" when toggled, and record flipping 60/40 → 44.6%.
- **Hide Duplicates checkbox**: drops games where *both* teams satisfy the filters (two bad teams playing each other). Record chip updates (154-133-4 → 136-115-4). Unneeded when a filter already forces one side (home/away, fav/dog).
- **Teaser records popover**: clicking the Record chip lists alternate-line records (-10/-7/-6/+6/+7/+10 PT: "254-68, 79%").

### 1.5 Think Tank (shared library)

List of shared systems: Pro / Community toggle, sport + wager-type facet checkboxes, search, timeframe tabs (All Time / Season / Since Shared / 30 Days), each row = name, sport icon, **sparkline thumbnail of its results graph**, share date, Copy System button with copy-count badge, performance chip ($ won, ROI, record).

### 1.6 Practices the product enforces/teaches (from articles)

Hypothesis first (Theory field), sample size (small-n warning: 55% needs ~1000+ bets at 95%), season consistency (Results Graph + season filter), anti-overfitting (grade sub-scores), volatile matches re-checked near game time (moving lines/weather), flat-stake accounting ($100/bet).

---

## 2. Where cfb-site already stands

| Bet Labs concept | cfb-site today |
|---|---|
| Filter-based system → historical record | `SystemFilter` + `run_backtest` ✅ |
| Filter categories | `FEATURE_REGISTRY` groups (pregame / season_to_date / team_preseason / metadata / lookahead) ✅ |
| Win %, ATS %, streaks entering game | `running_stats.py` (strictly-prior, no lookahead) ✅ |
| Record / ROI / hit rate chips | metrics row in `index.html` ✅ |
| Statistical validation | Wilson CI, z, permutation p, ROI t-stat, per-season breakdown, sign consistency, holdout split — **beyond** Bet Labs ✅ |
| Save / load / compare systems | `/save`, `?load_system=`, `/compare` ✅ |
| Money-won-by-line-value chart | `_range_chart` (crude version of the filter-modal distribution chart) ✅ |
| Spread + totals | ✅ |

Biggest structural difference: Bet Labs systems *identify a team* via filters and the engine bets that team; cfb-site picks a **side** (home/away) globally and filters games. The `bet_side`/`opponent` perspectives already bridge most of this.

---

## 3. Gaps → build steps

Ordered by dependency and value. Phases are independently shippable.

### Phase 0 — Data (prerequisite, already roadmap item 1)

Fetch/build/enrich 2020–2024 (then backfill to ~2015). Every screen above is empty without it. The Results Graph and per-value distributions only become persuasive with 5+ seasons.

### Phase 1 — Make the main page read like a system editor

1. **Cumulative "Money Won Over Time" graph** — the defining Bet Labs visual, currently missing.
   - Sort `bet_details` by (season, week, game_id) — no schema change needed; CFB week ordering is a fine date proxy. (Optional later: add `start_date` to `GameRecord` for true dates — CSV schema change, touch `storage`.)
   - Running sum of profit × 100 ($100 flat-stake convention). SVG polyline like `_range_chart`; color segments green above the running max / red in drawdown (or simpler: green when cumulative > 0); hover tooltip (title elements suffice).
   - Keep the existing by-line chart — it becomes the "filter distribution" chart in Phase 2.
2. **Stat-chip header** — restyle the metrics row into Bet Labs chips: Record (W-L-P, %), Margin (avg cover margin — small `backtest.py` addition: mean of `team_points + side_spread - opp_points` over graded bets), Money Won ($ = profit × 100), ROI, Grade (Phase 3). Color chips by sign.
3. **Plain-English filter sentences** — a renderer `describe(system) -> list[str]` mapping each active constraint to a sentence ("the spread is between -14 and -3", "the team's ATS % entering the game is ≥ 55%", from `FeatureDef.label` + op + value). Show as the active-filter list with per-row remove links (link = same query string minus that filter). This is the main "current system state" display in every screenshot.
4. **Tabs: Results Graph | Past Matches** — reorganize the workspace: graph tab first, bet-details table under "Past Matches" (already exists, just tabbed). "Current Matches" tab stubs to Phase 4. Server-rendered tabs (query param or CSS-only) — no SPA needed.
5. **Theory field** — add `theory: str` to `SavedSystem` (storage JSON, backward-compatible default `""`), textarea next to save name, display above filter list. Directly supports the hypothesis-first discipline the articles push.

### Phase 2 — Filter popup modals (the killer interaction)

**Decision (2026-07-16): keep the current main-page layout** (sidebar + workspace). What changes is how a filter is *configured*: instead of inline `<details>` rows in the sidebar, clicking a filter opens a **Bet Labs-style modal popup**. The sidebar becomes a launcher list; all configuration + exploration happens in the modal.

**Modal anatomy (from the video screenshots — replicate this):**

- Overlay dialog over the dimmed page; close ✕; **Save Filter** button commits and closes.
- **Title bar**: filter name left; live stat chips right — **Record** (dark chip), **Money Won** (green/red), **ROI** (green/red) — recomputed for *current system + this candidate filter* as controls change, plus a **List View** toggle (chart ⇄ table).
- **Numeric/range filters** (OU %, Spread %, Rank, Days Between Games): dual-handle slider with endpoint labels + "BETWEEN [x] AND [y]" inputs (two-way bound), optional secondary dropdown (e.g. streak length "1 Game"), and below it a **money-won-per-value chart** — one green/red dot per value across the full domain, so the user sees where the edge lives *before* picking endpoints.
- **List/categorical filters** (Opposing Team, Win/Loss Streak): search box + sortable table — checkbox | Description | **Record | ROI | Money** per value; "Showing 1 to N of N entries" footer.
- **About Filter panel** (right side): exact definition text — sourced from a new `description` field on `FeatureDef` (registry addition; feeds the anti-ambiguity role the articles emphasize, e.g. "rank 0 = unranked", "entering-game, prior games only").

**Build steps:**

6. **Per-value distribution endpoint** — `GET /filter-detail?key=...&<current form>`: run `matches_system` with the candidate filter *excluded*, group matched games by that feature's value, return per-value Record / ROI / Money as JSON. Numeric → bucketed series for the dot chart (generalize `_range_chart` from line-only to any registry feature); categorical/bool → table rows. Single highest-leverage UX gap.
7. **Live chip recalculation** — `GET /api/backtest?<form query>` returning `run_backtest` + `asdict` JSON; modal (and main chip header) `fetch()` it on control change. Form already round-trips via query string. On Save Filter, write values back into the existing hidden form inputs and submit — the no-JS full-reload path keeps working.
8. **Modal shell + sidebar-as-launcher** — sidebar rows open the modal instead of expanding inline; active filters still render as sentence rows (Phase 1 step 3) with Edit reopening the modal pre-filled. `FeatureDef.description` texts for the About panel. Registry groups keep their user-facing renames (Team Info, Line Info, Time Period, Matchup Info, Streaks/Form); lookahead group stays visually quarantined.

### Phase 3 — Integrity toggles (cheap, high trust value)

9. **Fade System toggle** — `fade: bool = False` on `SystemFilter`; in `grade_bet`, flip the graded side (opponent ATS for spreads, opposite side for totals). Storage/save/load/CLI flag. Tests: fade of a 60% system grades ~40% on same matches (pushes unchanged).
10. **System Grade** — composite letter from stats already computed: sample size (n vs the significance curve from the articles), ROI z-score, season sign-consistency, permutation p, plus two overfitting counters — number of active filters and number of discrete values selected inside `in`-list filters. Panel mirroring the screenshot: sub-score rows each with a letter + explanation, roll-up letter in the header chip. Pure function over `BacktestResult` + `SystemFilter` — very testable.
11. **Hide Duplicates** — only matters once a system can match *both* sides of one game (e.g. totals with `either` perspective, or future team-identifying systems). Implement as: when the same `game_id` produces two candidate bets, drop the game. Low urgency for spread systems where `side` is fixed — document, defer until `bet_side` systems can self-collide.

### Phase 4 — Dashboard + current matches (turns backtester into a tool you check weekly)

12. **My Systems dashboard** (`/` becomes dashboard, editor moves to `/system`) — table of saved systems: name, bet type, record, Money Won, ROI, sparkline; timeframe tabs (All Time / per-season; "30 days" needs real dates — defer or use season/week windows). "Create System" panel on top. Ship 2–3 bundled example systems (sample-data-backed) like Bet Labs' Example Systems tab.
13. **Current Matches** — for each saved system, evaluate upcoming games:
    - fetch current-week games + lines (`fetch` already does this for a season in progress; add an `--upcoming` path that keeps games with lines but no scores),
    - `matches_system` needs no result fields; running-stats features are entering-game so they're computable for unplayed games (enrich must run over the season-to-date data),
    - render Bet Labs-style rows: date, "Play on X", system name, matched-filter details (reuse the sentence renderer from step 3),
    - surface the article's caveat: systems using line-derived filters can gain/lose matches as lines move — show fetch timestamp.
    - This is the feature that converts historical research into actionable output; also the largest step (new pipeline path + page).
14. **Alternate-line ("teaser") records** — re-grade matched bets at line ± 6/6.5/7/10 via `grade_bet` with adjusted spread; popover/section from the Record chip. Cheap once grading is parameterized by line offset.

### Phase 5 — Explicitly deferred (YAGNI for single-user local tool)

- **Think Tank** (multi-user sharing, copy counts) — no user base; `/compare` + saved-system JSON files under version control already cover the single-user version.
- **Widget/embed, Live Help, public-betting-percentage filters** (no CFBD source for bet-share data; Action Network client exists if that ever changes), **weather/player filters** (CFBD has data — registry can grow later; the *mechanism* from Phase 2 already supports any new feature key), **moneyline wager type** (third `bet_type`; add when spread/total UX is settled).

---

## 4. Suggested sequencing vs existing roadmap

| Order | Item | Why |
|---|---|---|
| 1 | Phase 0 (= roadmap item 1, data 2020–2024) | unblocks everything |
| 2 | Phase 1 (graph, chips, sentences, tabs, theory) | main page reads like the template product; small diffs |
| 3 | Phase 3 items 9–10 (fade, grade) | pure-function wins, reuse existing stats; grade showcases the validation work already built |
| 4 | Phase 2 (distribution view + live recalc) | biggest UX lift, needs data volume to be meaningful |
| 5 | Phase 4 (dashboard, current matches, teasers) | weekly-use payoff; current matches is the big one |

Each numbered step is one TDD-able unit in the existing test pattern (construct `GameRecord`/`SystemFilter`, assert result fields; template changes verified via `test_web`).
