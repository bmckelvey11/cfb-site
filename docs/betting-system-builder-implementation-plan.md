# Betting System Builder — Implementation Plan

Written 2026-08-27, from the scoped spec at
`~/Downloads/betting-system-builder-product-spec.md` (edited copy of the original
product spec, cut to single-user local scope). Companion to
[bet-labs-parity-plan.md](bet-labs-parity-plan.md), whose Phases 0–4 are now
largely shipped.

Scope decisions (confirmed 2026-08-27):

- **Logic engine**: flat AND + per-filter exclusions stays. No nested OR/NOT
  groups, macros, rule tree, SQL export.
- **Versioning**: lightweight snapshots per save + rule/KPI diff. No lifecycle
  states beyond an `archived` flag.
- **Line movement**: in scope **now**, sourced from CFBD `spreadOpen` /
  `overUnderOpen` (already present in `data/raw/lines_*.json`). Action Network
  per-book depth is V2.
- **Alerts**: in-app Current Matches only (shipped). No delivery channels.

## Already shipped (do not rebuild)

Verified against `web.py` / `models.py` / templates on 2026-08-27:

- Dashboard `/` with saved systems, examples (`/copy-example`), Current Matches
  panel (`upcoming.py`); editor at `/system`; save/rename/delete; `/compare`;
  search runs + narration.
- Filter modal with live Record/Money/ROI chips, chart⇄list view, Max ROI, About
  panel, Clear (`/filter-detail`, `/api/backtest`).
- Plain-English filter sentences (`describe.py`); sidebar launcher; exclusions.
- Cumulative Money Won chart; stat chips incl. Margin and Grade; theory field;
  fade toggle; season breakdown; full stats/verdict layer (Wilson, permutation p,
  holdout, MDE, cluster adjustments).

TODO.md note: "be able to delete them" is already shipped (`/systems/<name>/delete`).

## Remaining work, phased

Each step is one TDD-able unit in the existing test pattern (construct
`GameRecord`/`SystemFilter`, assert result fields; template behavior via
`test_web`). Execute via GSD (`/gsd-quick` per step or `/gsd-execute-phase` per
phase) per repo policy.

### Phase A — Line movement features (user-prioritized)

New registry features from data already on disk. **No `GameRecord` CSV change** —
values land in the `features.json` sidecar via `enrich`.

1. **Extract open lines in enrich.** New feature source (kind alongside
   `computed_running`) that reads `data/raw/lines_{season}.json`, selects the same
   line `normalize._select_line` would pick (reuse it — same provider-preference
   logic, so open and close come from the same book row), and emits per game:
   - `spread_open` (home-perspective, same sign convention as `GameRecord.spread`)
   - `spread_move` = spread_close − spread_open
   - `total_open`, `total_move` analog
   - Missing `spreadOpen` → `None` (filters fail closed, per convention).
   → verify: unit test with two providers where only preferred has open; a game
   with no open value yields `None`s.
2. **Registry definitions.** Four `FeatureDef`s in the Line Info group with
   `description` texts for the About panel (state the home-sign convention and
   "move = close − open; positive = moved toward home team" explicitly). Decide
   perspective handling to match how existing line-derived filters treat
   home/away sides — follow whatever `min_spread` does today, and document it in
   the description.
   → verify: feature appears in sidebar, modal renders dual-slider + per-value
   chart with no endpoint changes (`/filter-detail` is registry-generic).
3. **Steam band (optional, cheap).** Derived bool/band feature
   `spread_move_band` (e.g. ≤−1, −1..1, ≥1) if the numeric slider proves awkward
   for "line moved ≥ 1 pt" systems. Skip if step 2's slider suffices.
   → verify: backtest with `spread_move >= 1` filter returns only moved games.
4. **Registry version bump fallout.** `features.registry_version()` changes →
   web UI stale-sidecar warning fires until `enrich` reruns; document rerun in
   the phase notes (`python -m cfb_system_maker enrich`).

Done when: a saved system can filter on line movement end-to-end (sidebar → modal
with per-value money chart → save → reload), with 2013–2025 coverage numbers
reported (how many games have open lines — expect gaps in early seasons).

### Phase B — Version snapshots + diff

5. **Model + storage.** `SystemVersion` frozen dataclass: `saved_at`,
   `system: SystemFilter`, `bets/wins/losses/pushes`, `profit`, `roi`,
   `note: str = ""`. `SavedSystem.versions: tuple[SystemVersion, ...] = ()`.
   On `/save` to an existing name: append the *previous* head as a version
   (cap ~50). Legacy JSON without `versions` loads as `()`.
   → verify: storage round-trip test; legacy fixture loads.
6. **Versions UI.** On the editor when a system is loaded: collapsible Versions
   list — timestamp, W-L-P, ROI, note; per row a "load" link (system → query
   string mapping already exists for `?load_system=`) and a diff vs current:
   sentence-level added/removed/changed (set-diff the `describe()` outputs;
   changed = same filter key, different sentence) + KPI deltas.
   → verify: `test_web` — save twice with a filter change, page shows one
   version, diff names the changed filter.
7. **Save note field.** Optional one-line "what changed" input next to Save;
   stored on the snapshot.
   → verify: note round-trips.

Done when: editing a saved system twice yields a browsable version with a correct
rule diff and KPI delta, and pre-existing saved systems still load.

### Phase C — Robustness gaps

8. **Max drawdown.** From the cumulative profit series in `run_backtest` (bet
   order already matches the cumulative chart): max peak-to-trough in dollars +
   as % of peak. Add to `BacktestResult`, render as a chip; shade drawdown
   segments red on the existing cumulative chart (data attribute per point —
   no new chart).
   → verify: hand-built sequence with known drawdown; chip renders.
9. **Rolling ROI chart.** Trailing-N-bets (N=50, clamp to n/5 for small samples)
   ROI polyline as a tab/section beside the cumulative chart. Server-computed
   like `cumulative_chart`.
   → verify: constant-profit series → flat line; regression on window edges.
10. **Regime splits section.** Server-rendered tables under the results area:
    splits by favorite/dog, home/away, spread band (reuse the bucketing behind
    `/filter-detail`), provider. Each row Record / ROI / Money. Season split
    already exists.
    → verify: split totals sum to headline totals (pushes included).
11. **Leave-one-season-out table.** For each season in the result: record/ROI
    with that season excluded. One loop over `season_breakdown` aggregates — no
    re-backtest needed.
    → verify: excluding the only profitable season flips the sign.

Done when: drawdown, rolling ROI, splits, and LOSO are on the editor page for any
backtest, all derived from the single existing `run_backtest` call.

### Phase D — System management (TODO.md)

12. **Archive flag.** `SavedSystem.archived: bool = False`; archive/unarchive
    POST route; dashboard defaults to active with an Archived toggle/tab.
    Backward compatible default.
    → verify: storage round-trip; archived system hidden from default dashboard
    and Current Matches panel.
13. **Dashboard search.** Client-side name/theory substring filter over the
    systems table (plain JS, no endpoint).
    → verify: `test_web` smoke (input present); manual check.
14. **Mark TODO.md** delete item done; enrich remaining bullets per global
    CLAUDE.md convention.

### Phase E — Results table polish

15. **CSV export.** `GET /export.csv?<same query>` streaming `bet_details` rows
    (game, season, week, team, opponent, side, line, result, profit, margin).
    → verify: response content-type + row count matches `bets`.
16. **Column sort.** Plain-JS client-side sort on the bet-details table headers.
    → verify: smoke test for the hook attribute; manual click check.

## Sequencing

| Order | Phase | Why |
|---|---|---|
| 1 | A (line movement) | User-prioritized; data already on disk; unlocks new system ideas immediately |
| 2 | B (versions) | Protects research iteration from here on — the sooner it exists, the more history captured |
| 3 | C (robustness) | Pure functions over existing results; drawdown chip is the biggest single spec gap |
| 4 | D (management) | Small; clears TODO.md |
| 5 | E (table polish) | Nice-to-have |

## Explicitly deferred (V2)

Action Network per-book open/close + steam timing (join by team abbr + start
date; `data/raw/actionnetwork_odds.csv` exists); `start_date` on `GameRecord`
(deliberate CSV migration) enabling real 30/90/365-day windows and month
heatmaps; weather/player/coach registry features; moneyline bet type;
rolling-window validation; tags; mobile layout; nested logic; any multi-user
feature.
