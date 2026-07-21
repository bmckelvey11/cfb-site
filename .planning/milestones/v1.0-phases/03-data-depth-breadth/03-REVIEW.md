---
phase: 03-data-depth-breadth
reviewed: 2026-07-17T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - cfb_system_maker/enrich.py
  - cfb_system_maker/features.py
  - cfb_system_maker/running_stats.py
  - docs/data-line-floor.md
  - scripts/probe_line_floor.py
  - tests/test_enrich.py
  - tests/test_features.py
  - tests/test_normalize.py
  - tests/test_running_stats.py
findings:
  critical: 0
  warning: 1
  info: 2
  total: 3
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-07-17
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Reviewed the Phase 03 (data-depth-breadth) diff against base `58e55fc`: new season-to-date
advanced-stat features (success rate / explosiveness, 03-01), a prior-season offensive wEPA
`team_preseason` feature (03-04), a token-safe live line-coverage probe (03-03), and the
line-floor documentation. The two domain-critical invariants were traced directly against the
code and the accompanying tests.

**No-lookahead (critical invariant): correct.** In `compute_running_stats`, the entering-game
`stats[(game_id, team)]` dict is written *before* the current game's points/ppa/adv values are
folded in, and `by_team_season` keys on `(team, season)` so prior-season rows cannot carry
across the reset. The new adv accumulation rides the exact strictly-prior path as the existing
ppa block. `prior_off_wepa` reads the `{season-1}` file and keys it under `season`
(`_index_prior_player_agg`), and `_lookup_team_scoped` reads `(team, game.season)`, so a
season-S game can only ever see S-1 data. Both directions are locked by tests (9.99 / 99.0 / 5.00
sentinels are all excluded).

**Token safety (probe): correct.** The CFBD token flows only into `cfbd.Configuration(access_token=...)`
and is never printed. The `except` handler prints `type(exc).__name__` + `str(exc)`; the vendored
`ApiException.__str__` renders *response* headers (`http_resp.getheaders()`), not request headers,
so the bearer token has no leak path. Output is season numbers + counts only, as documented.

**Untrusted-JSON fail-closed: correct at the leaf, one narrow structural gap** — see WR-01.

All 36 tests across the four touched test files pass. Findings below are robustness/quality, not
correctness or security defects.

## Warnings

### WR-01: enrich adv-index has two fail-open paths on malformed JSON containers

**File:** `cfb_system_maker/enrich.py:142` and `:143-147`
**Issue:** The phase invariant is "numeric coercion must fail closed (None), never raise inside
enrich." `_coerce_numeric` correctly protects the *leaf* values (a dict/string `successRate`
yields `None`), but the new adv block in `_build_running_index` has two structural paths that can
still raise and abort the entire enrich run on a malformed row:
- `offense = row.get("offense") or {}` then `offense.get("successRate")` (lines 147-152) raises
  `AttributeError` if `offense`/`defense` is a truthy non-dict (e.g. a JSON list). Same for the
  `defense` branch.
- `adv[(int(game_id), str(team))]` (line 148) — `int(game_id)` raises `ValueError` if `gameId`
  is a non-numeric string.

The existing test `test_enrich_success_off_fails_closed_on_dict_shaped_field` only exercises the
*leaf* being a dict, not the *container* being a non-dict — so the "fails closed" guarantee is
narrower than the test name implies. Likelihood on real CFBD shapes is near-zero and this mirrors
the pre-existing ppa block directly above it, so it is not a BLOCKER (no correctness/security/data
defect — it aborts the run rather than corrupting data), but it does contradict the stated
never-raise goal.
**Fix:** Guard the container type before `.get`, and coerce the id defensively, e.g.:
```python
offense = row.get("offense")
defense = row.get("defense")
offense = offense if isinstance(offense, dict) else {}
defense = defense if isinstance(defense, dict) else {}
gid = _coerce_numeric(game_id)
if gid is None:
    continue
adv[(int(gid), str(team))] = { ... }
```
Add a test where `offense` (the container) is a list to lock the guarantee end-to-end. The
identical hardening applies to the pre-existing ppa loop at lines 128-134 if you touch it.

## Info

### IN-01: near-duplicate ppa / adv index loops in `_build_running_index`

**File:** `cfb_system_maker/enrich.py:123-153`
**Issue:** The ppa loop (123-134) and the new adv loop (136-153) are structurally identical:
same `for season in seasons` / `path.exists()` / `gameId`-vs-`game_id` / `offense`/`defense`
extraction. Two copies is borderline for extraction, but the duplication means any hardening
(e.g. WR-01) has to be applied twice and can drift.
**Fix:** Optional — factor the shared "iterate a per-season raw file, key by `(int(game_id), team)`"
scaffold into one small helper that takes a row-to-value callback. Skip if you judge two uses
below the abstraction threshold (per the repo's simplicity-first convention).

### IN-02: `_index_prior_player_agg` trusts the filename for season, not the row `year`

**File:** `cfb_system_maker/enrich.py:337-354`
**Issue:** The aggregation sums every row's `wepa` in `adjusted_player_passing_{S-1}.json` and keys
the total under season S. It never inspects each row's `year`/`season` field. The no-lookahead
guarantee therefore rests entirely on the filename being single-season. If a prior-season file ever
contained mixed years (or a same-season sentinel row), it would silently fold in. The test fixture
includes `"year": 2022` fields that the code ignores.
**Fix:** Low priority given the file-per-season convention. If you want defense-in-depth, filter
rows to `row.get("year") == season - 1` (or the `season` key) before summing, and add a mixed-year
fixture asserting the wrong-year rows are dropped.

---

_Reviewed: 2026-07-17_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
