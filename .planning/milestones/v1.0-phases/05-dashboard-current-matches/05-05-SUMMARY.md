---
phase: 05-dashboard-current-matches
plan: 05
subsystem: web
tags: [examples, dashboard, storage, jinja, read-only, path-safety]
status: complete
requires:
  - storage._safe_system_name
  - storage._system_from_dict
  - storage.save_system
  - web._dashboard_row
  - web._cached_backtest
provides:
  - "cfb_system_maker/examples/ (three bundled read-only SavedSystem JSON files)"
  - "storage.EXAMPLES_DIR / list_examples / load_example_system"
  - "Example Systems tab on the dashboard (?tab=examples)"
  - "POST /copy-example (Copy to My Systems)"
affects:
  - cfb_system_maker/storage.py
  - cfb_system_maker/web.py
  - cfb_system_maker/templates/dashboard.html
  - cfb_system_maker/static/styles.css
  - tests/test_storage.py
  - tests/test_web.py
tech-stack:
  added: []
  patterns:
    - "package-relative resource path (no package-resources API; the package is never installed)"
    - "no-JS form POST for a row action, redirecting back to the originating tab"
    - "optional directory override on a package-rooted loader, so a hostile fixture is testable"
key-files:
  created:
    - cfb_system_maker/examples/spread-home-favorites.json
    - cfb_system_maker/examples/total-unders-high-lines.json
    - cfb_system_maker/examples/nonconference-away-dogs.json
  modified:
    - cfb_system_maker/storage.py
    - cfb_system_maker/web.py
    - cfb_system_maker/templates/dashboard.html
    - cfb_system_maker/static/styles.css
    - tests/test_storage.py
    - tests/test_web.py
decisions:
  - "The registry-feature example filters on matchup `conferenceGame` (D-21) — populated pregame for every scheduled game with both values common in any week, so it matches non-zero games in the resolved week (must-have #5); an initial `neutralSite eq true` example was replaced because its value is true for only ~3% of games."
  - "`list_examples` / `load_example_system` take an optional directory override; the routes always pass the package dir, and the override exists so the XSS test can supply a hostile file that must never ship."
  - "The copy action writes the file *stem*, not the JSON `name` field, so a display name can never steer the filesystem write."
  - "Examples render their system name as plain text, not an editor link — a bundled example does not exist in the user's data dir, so `?load_system=` would 'not found' every time."
metrics:
  duration: ~35m
  completed: 2026-07-20
  tasks: 2
  tests_before: 272
  tests_after: 292
---

# Phase 5 Plan 05: Bundled Example Systems Summary

Three read-only example systems now ship inside the package and render on their own Example Systems tab with real Record / Money Won / ROI / sparkline figures drawn from the same cached `run_backtest` path as My Systems, each carrying a written theory and a no-JavaScript **Copy to My Systems** action.

## What Was Built

**Task 1 — failing tests (commit `aafb76f`)**
Ten storage tests and ten route tests, RED via `ImportError` on the not-yet-existing loader. The D-21 content assertions are written as a **loop over `list_examples()`** rather than three hardcoded checks, and they derive the forbidden key sets from `FEATURE_REGISTRY` groups (`weather`, `season_to_date`) rather than hardcoding key names — so a fourth example, or a newly added weather feature, cannot quietly violate the decision.

**Task 2 — examples, loader, tab, copy action (commit `b2eccd3`)**

The three files were generated *through* `storage._system_to_dict` rather than hand-written, which guarantees they are byte-shaped exactly like a real saved system and cannot drift from the serializer:

| File | Capability (D-16) | Filters |
|------|-------------------|---------|
| `spread-home-favorites` | spread | home side, favorite, spread −21 to −7 |
| `total-unders-high-lines` | total | under, total ≥ 55 |
| `nonconference-away-dogs` | registry feature | away side, underdog, `conferenceGame eq false` |

(The registry-feature example was `neutral-site-dogs` in `b2eccd3`, changed in `64d7198` — see Deviations.)

`storage.EXAMPLES_DIR` resolves relative to the module file. `list_examples` / `load_example_system` are siblings of `list_systems` / `load_saved_system` — they reuse `_safe_system_name` and `_system_from_dict` unchanged; no parallel parser and no bypassed gate.

The dashboard view branches on `tab`, `_example_rows` wraps the existing `_dashboard_row` (so figures come from `_cached_backtest`, not a second path), and `POST /copy-example` loads the bundled example and hands it to the existing `save_system`.

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| `conferenceGame` as the registry-feature example | D-21 requires a matchup or line-derived feature that populates for unplayed games. `conferenceGame` populates for *every* scheduled game and both values are common in any week, so `nonconference-away-dogs` matches non-zero games in the resolved week — unlike `neutralSite eq true`, whose value is true for only ~3% of games (see Deviations) |
| Optional `examples_dir` override on both loader functions | The escaping test (T-05-19) needs a name/theory carrying HTML metacharacters, which must never exist in a shipped file. Routes always pass `EXAMPLES_DIR`; only the test points elsewhere |
| Copy writes the file stem, not the JSON `name` | The stem is already gated by enumeration; the `name` field is free text. Using the stem means a hostile display name has no filesystem reach at all, on top of `save_system`'s own gate |
| Example names are plain text, not editor links | Examples live in the package, not the data dir, so `?load_system=` would resolve to "System not found" for all three. Copy to My Systems is the documented way in (D-14) |
| Empty state gated to `tab != 'examples'` | "No saved systems yet" must still fire for a user with no systems, but never on a tab that always has three rows |

## Verification

| Check | Result |
|-------|--------|
| `.venv/Scripts/python.exe -m pytest` | **292 passed, 0 failed** (baseline 264 at Wave 1; 272 including 05-04's parallel tests) |
| Real-data render of `/?tab=examples` | All three rows with real figures: `1722-1699-68, −$…, −3.83%` (nonconference-away-dogs) · `1813-1844-72, −$19,580, −5.25%` · `2988-2778-64, −$6,161, −1.06%`; 3 sparkline SVGs, 3 copy buttons, panel note present |
| **Resolved-week match count (must-have #5)** | Under the current offseason-resolved week (2025 wk16, D-20 backward fallback), each example matches non-zero games: nonconference-away-dogs=4, spread-home-favorites=3, total-unders-high-lines=3. Checked with `matches_system(..., require_played=False)` against `games.csv` (upcoming.csv is 05-04's and absent) |
| Fresh empty data dir | My Systems shows the empty state; Example Systems shows three working systems; copy produces an ordinary saved system that then appears on My Systems |
| `git status cfb_system_maker/examples/` after running the copy action | Bundled files unmodified (byte comparison also asserted by test) |
| No JavaScript in `dashboard.html` | `grep -c script` → 0 |
| No `\|safe` in `dashboard.html` | 0 |
| New hex literals in `styles.css` | Only `#fff`, already present in the file's `.filter-modal__retry:hover`. No new color *value* introduced |
| 05-04-owned files (`upcoming.py`, `enrich.py`) | Untouched — not staged in either commit |

## Threat Mitigations Applied

| Threat ID | Mitigation |
|-----------|------------|
| T-05-18 (path traversal) | Both the loader and the copy action route the name through `_safe_system_name`; `save_system` gates again on the write. `test_load_example_system_rejects_path_traversal_name` and `test_copy_example_rejects_a_traversal_name` (which also asserts no file escaped the data dir) |
| T-05-19 (stored XSS) | Jinja autoescaping, never disabled. `test_example_systems_tab_escapes_name_and_theory` injects `<script>` and an `onerror` payload via the directory override and asserts the escaped form |
| T-05-20 (bundled file overwritten) | The copy path only ever reads the package dir. `test_copy_example_leaves_the_bundled_file_untouched` compares bytes before and after |
| T-05-21 (examples read as recommendations) | Panel note ships the exact UI-SPEC copy; all three theories are phrased as questions/hypotheses ("asks whether…", "tests the idea that…"), never as claims |
| T-05-22 (malformed example crashes the dashboard) | `_example_rows` skips unparseable files; tests parse every shipped file through the real parser, so a malformed file fails CI rather than a user's page |
| T-05-SC | No packages installed; no new dependency |

## Deviations from Plan

**1. [Rule 1 — Bug] Registry-feature example replaced to satisfy must-have #5**
- **Found during:** post-implementation verification of must-have #5 ("every example matches non-zero upcoming games under the resolved week").
- **Issue:** The original `neutral-site-dogs` (home underdog, `neutralSite eq true`) matched **zero** games in the resolved week (2025 wk16): only Army-Navy is neutral there and it is not a home-underdog spot. `neutralSite` *populates* pregame (D-21 satisfied), but its value is true for only ~3% of games, so filtering on it reproduces the exact zero-match "shows nothing" failure D-21 exists to prevent — via value sparsity rather than a null field. All-history figures (2000+ bets) had masked this; the per-week check surfaced it.
- **Fix:** Replaced with `nonconference-away-dogs` (away underdog, `conferenceGame eq false`). `conferenceGame` is a matchup feature populating for every scheduled game, with both values common in any normal week; it matches 4 games in the resolved week and 1–13 across each of the last 10 weeks.
- **Files modified:** `cfb_system_maker/examples/neutral-site-dogs.json` → `nonconference-away-dogs.json`, `tests/test_storage.py`, `tests/test_web.py`.
- **Commit:** `64d7198`.

Two implementation choices the plan left open are recorded above (the directory override and stem-based copy naming); neither changes the plan's contract.

## Known Stubs

None.

## For the Next Phase

- `EXAMPLES_DIR` is a `web` module global (imported from `storage`), which is what makes it monkeypatchable. Any new example-reading code should read it from the `web` namespace at call time, not capture it at import.
- The examples tab is unaffected by the timeframe strip only in the sense that it composes with it normally — `/?tab=examples&timeframe=2024` works and re-derives figures from the same single all-time result.
- Plan 05-06's Current Matches panel will see three more systems' worth of matches only if it chooses to include examples; this plan deliberately keeps examples out of `_saved_systems_newest_first`.

## Self-Check: PASSED

- `cfb_system_maker/examples/spread-home-favorites.json` — FOUND
- `cfb_system_maker/examples/total-unders-high-lines.json` — FOUND
- `cfb_system_maker/examples/nonconference-away-dogs.json` — FOUND
- Commit `aafb76f` (Task 1, RED) — FOUND
- Commit `b2eccd3` (Task 2, GREEN) — FOUND
- Commit `64d7198` (must-have #5 fix) — FOUND
- Full suite: 292 passed, 0 failed
