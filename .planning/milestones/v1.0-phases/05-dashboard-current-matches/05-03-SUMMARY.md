---
phase: 05-dashboard-current-matches
plan: 03
subsystem: web
tags: [dashboard, routing, flask, jinja, sparkline, backtest-cache]
status: complete
requires:
  - backtest.run_backtest
  - storage.list_systems
  - storage.load_saved_system
  - storage.load_processed_games
provides:
  - "dashboard route at / (My Systems)"
  - "editor relocated to /system"
  - "_sparkline helper"
  - "in-memory figure cache keyed on system identity + data-file identity"
  - "templates/dashboard.html (left column; right column reserved for Plan 05-06)"
affects:
  - cfb_system_maker/web.py
  - cfb_system_maker/templates/index.html
  - cfb_system_maker/static/styles.css
  - tests/test_web.py
  - tests/test_filter_modal.py
  - tests/test_web_features.py
tech-stack:
  added: []
  patterns:
    - "server-rendered inline SVG (no chart library)"
    - "query-param full-page GET tab switching (no client JS)"
    - "FileNotFoundError degradation to a missing-data render"
key-files:
  created:
    - cfb_system_maker/templates/dashboard.html
  modified:
    - cfb_system_maker/web.py
    - cfb_system_maker/templates/index.html
    - cfb_system_maker/static/styles.css
    - tests/test_web.py
    - tests/test_filter_modal.py
    - tests/test_web_features.py
decisions:
  - "Kept the editor view function named `index` and moved only its decorator to /system, so all three /save url_for('index') calls and compare.html's back-link repoint automatically with zero edits."
  - "Redirect preserves request.query_string verbatim rather than url_for(**request.args), which would silently drop repeated multi-value params."
  - "Per-season figures derive from one all-time run_backtest via season_breakdown + bet_details (D-11); no per-tab backtest."
metrics:
  duration: ~45m
  completed: 2026-07-20
  tasks: 3
  tests_before: 219
  tests_after: 264
---

# Phase 5 Plan 03: Dashboard & Route Relocation Summary

The My Systems dashboard is now the landing page at `/`, the system editor lives at `/system`, and every saved system renders with Record, Money Won, ROI and a cumulative-profit sparkline sourced from a single cached all-time `run_backtest`, with All Time plus per-season timeframe tabs.

## What Was Built

**Task 1 — test re-pointing (commit `14aa5de`)**
Enumerated and re-pointed 42 root-path call sites across `tests/test_web.py`, `tests/test_filter_modal.py` and `tests/test_web_features.py` to `/system`. Only the requested path changed; no assertion inside any re-pointed test was altered. `tests/test_web_compare.py` was confirmed to exercise only `/compare` and needed no change. Added 16 new dashboard tests covering the landing page, redirect allowlist, tab normalization, escaping and the save redirect.

**Task 2 — route move and dashboard (commit `aa4a283`)**
The editor view function keeps the name `index`; only its decorator moved from `@app.get("/")` to `@app.get("/system")`. This makes all three `url_for("index")` calls in `/save` — and `compare.html`'s back-link — follow automatically. A new `dashboard()` view serves `/`, redirecting to `/system` when any editor parameter is present (explicit named allowlist plus an `ff_` prefix match; `tab` and `timeframe` are deliberately excluded). Systems are enumerated with `list_systems`, loaded, and re-sorted `saved_at` descending. Missing `games.csv` reuses the editor's existing missing-data copy rather than forking it. Added the editor's `← My Systems` back-link.

**Task 3 — sparkline and timeframe tabs (commit `00182ff`)**
`_sparkline` is a sibling of `_cumulative_chart`, not a parameterization of it — the existing editor chart and its four tests are untouched. Key difference: the sparkline y-scales to the series' own min/max (the editor chart pins zero into the range), so a flat series centers instead of clipping.

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Keep view function named `index`, move only the decorator | Guarantees all `url_for("index")` sites (three in `/save`, one in `compare.html`) resolve to `/system` with zero edits; renaming would have caused a BuildError or silently pointed them at the dashboard |
| Redirect via `request.query_string` verbatim | `url_for(editor, **request.args)` keeps only the first value per key, silently dropping repeated `filter_seasons` / `filter_teams` / `filter_conferences` / `filter_providers` values. Covered by a test |
| Redirect trigger is a named allowlist, never the `tab` param | The editor uses `?tab=graph\|matches` and the dashboard uses `?tab=mine\|examples`; keying on it would bounce legitimate dashboard traffic. `/?tab=examples` returning 200 is a test |
| One all-time `run_backtest` per system | `run_backtest` runs a 1000-iteration permutation test and Wilson CI the dashboard never displays; 14 timeframe tabs would multiply that 14× |
| Cache key = deterministic system dict + (size, mtime) of `games.csv` and `features.json` | A data rebuild invalidates; `_system_key` sorts sets because set iteration order is unstable across processes |

## Deviations from Plan

**Task 2 scoped the Trend column to Task 3.** The plan listed the table in Task 2 and the sparkline in Task 3. Rather than ship a Task-2 table with an empty `Trend` cell (a stub), the column was added in Task 3 alongside the helper that fills it. The final column order matches the UI-SPEC exactly.

Two assertions in my own **new** tests were corrected after seeing real output — neither is a re-pointed test:
- `test_dashboard_missing_games_file_...` asserted `"missing"`; the established copy is `No processed data found`.
- `test_dashboard_zero_bet_system_...` asserted `&#8212;`; Jinja emits `&mdash;`, matching the editor's existing em-dash convention.

No Rule 1–4 deviations. No packages installed.

## Verification

| Check | Result |
|-------|--------|
| `.venv/Scripts/python.exe -m pytest` | **264 passed** (baseline was **219**, not the 214 stated in the brief) |
| No assertion changed in a re-pointed test | Confirmed — sed touched only the path substring |
| `grep -rnE 'get\("/(\?\|"\| \+)' tests/` | 19 hits, all at `tests/test_web.py:738+` — exclusively the new dashboard tests |
| Dashboard references no JavaScript | `grep -c script dashboard.html` → 0 |
| No `\|safe` on any dashboard value | `grep -c '\|safe' dashboard.html` → 0 |
| `git diff` on `index.html` | 1 insertion — the back-link only |
| No new hex literal in `styles.css` | Confirmed — all colors from existing `:root` tokens |

## Threat Mitigations Applied

| Threat ID | Mitigation |
|-----------|------------|
| T-05-09 (stored XSS via name/theory) | Jinja autoescaping throughout; `test_dashboard_escapes_system_name_and_theory` asserts the escaped form |
| T-05-10 (`tab`/`timeframe` path injection) | `tab` normalizes to `mine`/`examples`; `timeframe` normalizes to the literal `all` or an int drawn from seasons present. `test_dashboard_unknown_timeframe_falls_back_to_all_time` passes `../../etc/passwd` |
| T-05-11 (redirect mis-scoping) | Fixed internal `/system` target, never user-supplied — cannot become an open redirect. Named allowlist trigger; `/?tab=examples` non-redirect asserted |
| T-05-12 (backtest blowup) | One all-time `run_backtest` per system, cached; per-season derived from `season_breakdown`/`bet_details` |
| T-05-13 (missing `games.csv`) | `FileNotFoundError` → existing missing-data render, asserted by test |

## Known Stubs

**`<aside class="dash-side">` in `dashboard.html` is intentionally empty**, carrying an HTML comment marking it as the Current Matches panel slot. This is the reserved right column the plan explicitly required (`"leave a clearly marked block for it rather than restructuring later"`). **Plan 05-06 fills it (DASH-03).** The grid, sticky positioning and 900px collapse behavior are already in place, so 05-06 adds content only.

**The `Example Systems` tab is a non-functional placeholder this phase.** The template never branches on `tab`, so `?tab=examples` renders the My Systems table content under an active "Example Systems" tab. This plan's only requirement is that `/?tab=examples` returns 200 without redirecting (it does, and that is a test) — bundled examples and the tab's own table variant are **DASH-02, a later plan**. A visual verifier will correctly flag "Example Systems shows my systems"; that is expected at this point in the phase, not a defect in 05-03.

## For the Next Phase

- The right column awaits Plan 05-06; the grid and responsive collapse are done.
- `_FIGURE_CACHE` is module-level and unbounded. Fine at current scale (a handful of saved systems), but worth a bound if system counts grow.
- Any new dashboard test should use the `_dashboard_app(tmp_path)` / `_save_a_system(client, name, **extra)` helpers at `tests/test_web.py:717`.

## Self-Check: PASSED

- `cfb_system_maker/templates/dashboard.html` — FOUND
- Commit `14aa5de` (Task 1) — FOUND
- Commit `aa4a283` (Task 2) — FOUND
- Commit `00182ff` (Task 3) — FOUND
- Full suite: 264 passed, 0 failed
