---
task: bump-cfbd-client-register-10-endpoints
date: 2026-08-28
mode: quick
status: complete
---

# Quick Task 260828-m3k — Summary

Vendored `cfbd-python` bumped `034cd17` → `52f2bbf` (upstream `main`, 11 commits, 495
files) and all 10 previously client-blocked spec paths registered. `audit_endpoints.py`
now closes at **73 registered + 1 client-only (`/info/usage`) + 0 no-client = 74**.

## The bump was bracketed by a live probe, because the suite can't see client drift

`test_scrapers` drives a fake cfbd module and `test_cli` uses bundled sample data, so a
green suite proves nothing about the real client's field spellings — which `normalize`
and `enrich` index by name. Probed the 16 endpoints `build`/`enrich` consume before and
after the bump and diffed first-row nested key sets:

- **Zero keys removed.** Two added: `games.playoff`, `coaches.id`. Both inert.

Full suite green either side (557 → 558 with the new test).

## Registered (mode from live signature + one probe call each)

| Registry name | Mode | Why |
|---|---|---|
| `cfp_playoff` / `cfp_games` / `cfp_participants` | `season`, `min_season=2014` | pre-CFP seasons raise |
| `core_ratings` | `season` | empty before 2016, valid |
| `srs_expanded` | `season` | FCS included |
| `coach_seasons` | `season` | 400s unfiltered |
| `coach_profile` / `coach_tenures` | `on_demand` | 400 without `coach_id`/`team` |
| `conference_affiliations` | `once` | full 3,604-row history in one call |
| `conference_changes` | `season` | year required |

## New `Endpoint.min_season`

`_run_endpoint` catches exceptions **per endpoint, not per season** — so one pre-2014 CFP
season would have aborted every later season of that endpoint, silently yielding nothing.
`min_season` skips those years (counted as `skipped`). `scripts/audit_coverage.py` honours
the same floor, otherwise it would report the skipped years as missing files.
`tests/test_scrapers.py::test_season_skips_years_before_min_season` was confirmed to fail
when the guard is removed.

Empty-but-valid floors need no gate and are documented instead: `core_ratings` returns zero
rows before 2016; `srs_expanded` is empty for **2020 only** (checked live — 2019 and 2021
raise a pydantic `ValidationError` on a null `classification` and come back through the
existing `_call_raw` fallback, so those files are complete).

## Scraped

`scrape --season 2012..2025 --only <the 8 bulk endpoints>` → **0 failed**, 93 files:
coach_seasons 1,961 rows · conference_affiliations 3,604 · conference_changes 324 ·
cfp_playoff 12 · cfp_games 52 · cfp_participants 64 · core_ratings 1,309 · srs_expanded 3,341.

Docs: `docs/data-coverage.md`'s "blocked on a client bump" section is now history plus the
registered-mode table; root `CLAUDE.md` updated (73 entries, `min_season` convention).

Not done: none of the new data is wired into the feature registry — that is a separate
`enrich` change, not part of registering the endpoints.
