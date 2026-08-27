# Architecture Research

**Domain:** Brownfield integration — cfb_system_maker v1.1 "Season Readiness" milestone
**Researched:** 2026-08-26
**Confidence:** HIGH (all findings read directly from current repo code on `fix/web-app-review-2026-08-26`, no external sources needed)

## Summary Answer

- **Item 1 (merge fix branch) touches the same files items 3-5 need to edit: `backtest.py`, `features.py`, `storage.py`, `web.py`.** This is a hard sequencing constraint — the fix branch must merge to master first, or items 3-5 must be built directly on top of the fix branch (which the working tree already is) and merged together. Do not build items 3-5 against a pre-merge master; the diff would conflict on `_system_from_dict`/`_finalist_system_from_dict` (storage.py), `feature_ok` support code (features.py), and the request-parsing/rendering routes (web.py).
- **Item 3 (Hide Duplicates) does NOT follow the D-03 fade pattern.** Fade is a grading-only toggle that never changes `matches_system`'s matched count (D-03: "fade is read exclusively inside grade_bet/_grade_total_bet, never inside matches_system, to preserve matched-count invariance"). Hide Duplicates is definitionally count-changing — it exists to drop one of two candidate bets sharing a `game_id`. It belongs as a **post-processing step on `run_backtest`'s output** (operating on `matched`/`details`), not inside `matches_system` or `grade_bet`. Full placement analysis below.
- **Item 4 (describe() fallback) lives in `cfb_system_maker/describe.py`**, not `web.py` — the milestone context's premise that describe() is "currently in web.py" is incorrect; `web.py` only imports and calls it (3 call sites: line 544, 666, 1803). The dispatch is inside `_feature_group_sentence()` (lines 58-86 of describe.py), which returns `None` (silent drop, the T-01-03 bug) when a filter's `(op, control)` combo isn't one of the 4 explicit branches (`numeric`+range, `bool`+`eq`, `categorical`+`eq`, `categorical`+`in`).
- **Item 5 (4th example system) is pure data** — a JSON file dropped into `cfb_system_maker/examples/`, following the exact shape of the 3 existing files (`storage._system_to_dict` schema). No code changes required; `storage.list_examples()`/`load_example_system()` are already generic directory scans.

## Standard Architecture (as it exists today)

### System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│  web.py (Flask routes)                                            │
│  index() / compare() / /filter-detail / /api/backtest / dashboard │
│  - parses request.args -> SystemFilter (_form_values_from_args,   │
│    _system_from_form-equivalent block at web.py:1220)             │
│  - calls describe(system) for plain-English sentences             │
│  - calls run_backtest(games, system, feature_map) for results     │
├──────────────────────────────────────────────────────────────────┤
│  backtest.py                                                      │
│  matches_system(game, system, feature_map, require_played=True)   │
│    -> bool   [THE single candidate-matching gate, D-18 flag]      │
│  grade_bet(game, system) / _grade_total_bet(game, system)         │
│    -> BetDetail   [THE single grading path; reads system.fade]    │
│  run_backtest(games, system, ...) -> BacktestResult                │
│    matched = [g for g in games if matches_system(g, system, fm)]  │
│    details = [grade_bet(g, system) for g in matched]              │
├──────────────────────────────────────────────────────────────────┤
│  describe.py                                                      │
│  describe(system: SystemFilter) -> list[{"text","key"}]           │
│  _feature_group_sentence(filts) -> dict|None  [4 hardcoded        │
│    (op,control) branches; T-01-03 returns None outside them]      │
├──────────────────────────────────────────────────────────────────┤
│  storage.py                                                       │
│  SavedSystem JSON <-> SystemFilter (_system_to_dict/_from_dict)   │
│  EXAMPLES_DIR = cfb_system_maker/examples/*.json (D-14, read-only)│
│  list_examples() / load_example_system()  [generic directory scan]│
└──────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| `matches_system` | Candidate filtering — decides which games are "in" the system, before any grading | `backtest.py:332` |
| `grade_bet` / `_grade_total_bet` | Win/loss/push + profit for one matched game; reads `system.fade` (D-03) | `backtest.py:455`, `backtest.py:515` |
| `run_backtest` | Orchestrates matches_system -> grade_bet -> BacktestResult (bets, stats, season_breakdown) | `backtest.py:47` |
| `describe` | Renders `SystemFilter` into plain-English sentence list for the UI | `describe.py:89` |
| `_feature_group_sentence` | Per-(key,perspective) sentence dispatch; the 4 (op,control) branches from T-01-03 | `describe.py:58` |
| `storage.list_examples` / `load_example_system` | Enumerate/load bundled read-only example systems | `storage.py:202`, `storage.py:210` |

## Item 3 — Hide Duplicates: Integration Point Analysis

### Why duplicates are now reachable

Per PROJECT.md: "Hide Duplicates toggle (drop a game when one `game_id` yields two candidate bets — now reachable since total systems match either side)." Confirmed in `matches_system` (backtest.py:369-380): on `bet_type == "total"`, team/conference filters match if **either** `home_team`/`away_team` is in `system.teams` (or conference). A single `game_id` is still only counted once by `matches_system` itself (it iterates `games`, one `GameRecord` per `game_id`) — the "two candidate bets" scenario is not about `matches_system` returning a game twice. It is about **`grade_bet`/`_grade_total_bet` producing an ambiguous side** for a game that would match under either team's perspective (e.g., a `bet_side`/`opponent`-perspective feature filter, or a team filter matching either side of a total). In other words: the duplication risk lives in what a *matched* game *means* once graded, not in `matches_system` emitting duplicate rows.

### Where it does NOT belong

- **Not inside `matches_system`**: that function returns one bool per `GameRecord`; there is no second candidate to compare against inside a single call. It has no visibility into "this game_id would also match under the other team's perspective" without re-running matching from the opposite side — which is a different, heavier change (effectively doubling the match pass) than "drop a bet."
- **Not inside `grade_bet`/`_grade_total_bet` following the D-03 fade shape**: fade is a *value transform* (flips which side is graded) that is O(1) per call and never removes a row — it preserves `len(matched) == len(details)`. Hide Duplicates is an O(n) *set operation* across the whole matched list (you need to see all matched games to know which `game_id`s recur). A single-game function cannot detect a duplicate; only a step with access to the full `matched`/`details` list can.

### Where it belongs

**A post-filter on `run_backtest`'s matched/details list, before aggregation.** Concretely, inside `run_backtest` (backtest.py:47-93), after `matched = [game for game in games if matches_system(...)]` (line 56) and before `details = [grade_bet(...) for game in matched]` (line 57-60) — or equivalently, dedupe `details` by `game_id` after grading, whichever direction preserves existing behavior more cleanly (dedupe pre-grade avoids grading a bet that gets thrown away, cheaper and matches "candidate bet" framing in PROJECT.md).

This mirrors **D-01 (upcoming.csv separate-file pattern)** in spirit more than D-03: it is a *new orthogonal knob added at the point where the list already exists*, not a per-record value flip threaded through every grading branch. Concretely:

- `SystemFilter` gains `hide_duplicates: bool = False` (same field-addition mechanics as `fade`: default `False`, threaded through `storage._system_to_dict`/`_system_from_dict`/`_finalist_system_to_dict`/`_finalist_system_from_dict` for backward-compat, per the "Storage backward compatibility" constraint in CLAUDE.md).
- `run_backtest` (and `run_backtest_summary`, which duplicates the same matched/details construction at backtest.py:12-44) gains the dedup step, gated on `system.hide_duplicates`, applied to `matched` (or `details`) keyed by `game_id`.
- **This does change `result.bets`/matched-count** — that is the entire point of the toggle (PROJECT.md explicitly frames it as "drop a game"), so it correctly does NOT preserve the D-03 invariance property. D-03's invariance is specific to fade; it should not be read as a universal rule for all future toggles.
- `web.py` needs the same plumbing fade got: `_empty_form()` default, `_form_values_from_args()` parsing (`args.get("hide_duplicates") == "on"`), the `SystemFilter(...)` construction block (~web.py:1220-1250), and the query-param passthrough list at web.py:1433 (`"favorite", "underdog", "home", "away", "fade"` tuple — add `"hide_duplicates"`).
- Template: a checkbox in the same `.workspace-header`/`form="filters-form"` association pattern D-01/UI-SPEC established for fade (STATE.md: "Fade toggle checkbox lives outside filters-form's DOM ... associates via HTML5 form='filters-form' attribute, matching favorite/underdog/home/away pattern").

**Open question for roadmapping, not resolved by this research:** what determines *which* of the two duplicate candidates is dropped (first-seen, home-perspective-wins, or both dropped)? PROJECT.md doesn't specify. This needs a decision during phase planning, not architecture — flag it as a phase-discussion question.

## Item 4 — describe() Fallback: Integration Point Analysis

### Current dispatch shape (describe.py)

`_feature_group_sentence(filts)` (describe.py:58-86) handles exactly 4 `(op, control)` combos, each an explicit early return:

1. `control == "numeric"` → always handled via `_labeled_range_sentence` (any `op` in `{gte, lte}` present), returns a sentence or `None` if neither gte/lte present.
2. `op == "eq"` and `control == "bool"` → `"{label} is {Yes|No}"`
3. `op == "eq"` and `control == "categorical"` → `"{label} is {value}"`
4. `op == "in"` and `control == "categorical"` → `"{label} is one of {...}"`

The fall-through (`for filt in filts: ... if text is not None: return ...`, then function-level `return None` at line 86) is exactly T-01-03: any `(op, control)` combo not in this list (e.g. `op == "in"` on a `bool` control, or `op == "eq"` on `numeric` without going through the range path, or any future `control` value added to `features.py`'s `Control` Literal) silently returns `None`, and the calling loop in `describe()` (line 127-130) just skips appending a sentence — while `feature_ok()` (features.py:534, imported into `backtest.matches_system`) still applies the filter's effect on matching. Net effect: an active filter narrows results but has no visible sentence and no Remove link, which is the exact risk STATE.md flags.

### Minimal-diff fallback

Add one more branch **inside `_feature_group_sentence`**, after the 4 existing checks, before the function-level `return None`:

```python
    # Fallback: no rendered branch matched, but the filter is still active
    # (feature_ok() will still apply it) — surface a generic sentence instead
    # of silently dropping it, per T-01-03.
    for filt in filts:
        return {"text": f"{label} {filt.op} {filt.value!r}", "key": f"ff:{key}"}
    return None
```

This is minimal-diff because:
- It reuses the already-resolved `label` (line 65-68) and `key` variable already in scope.
- It does not touch any of the 4 existing branches — their returns fire before this code is ever reached, so already-rendered sentences are byte-for-byte unchanged (verifiable by running the existing `describe()` tests unmodified).
- It does not add a Remove-link special case — the existing removal-affordance path (STATE.md's "T-01-03 removal-affordance concern") reads sentences by their `key` field (`f"ff:{key}"`), which this fallback already populates identically to the 4 real branches, so Remove links work automatically without template changes.
- It requires touching only `describe.py` — no `web.py`, `features.py`, or `backtest.py` change needed, since `describe()`'s only contract with callers is "list of `{text, key}` dicts," which is unchanged.

**Where NOT to put it:** not in `web.py` (describe() is already a clean single-purpose module `web.py` merely calls three times) and not in `features.py` (that module owns `feature_ok`'s matching semantics, not sentence rendering — mixing concerns there would violate the module boundary already established).

## Item 5 — Bundled Example System: Integration Point Analysis

### Where the 3 existing examples live

`cfb_system_maker/examples/*.json` (confirmed on disk: `nonconference-away-dogs.json`, `spread-home-favorites.json`, `total-unders-high-lines.json`), loaded by `storage.list_examples()` (storage.py:202-207, generic `Path.glob("*.json")` over `EXAMPLES_DIR`) and `storage.load_example_system()` (storage.py:210-222, parses through the same `_system_from_dict` as a saved system, tagged read-only by convention/UI, not by a field). `EXAMPLES_DIR = Path(__file__).resolve().parent / "examples"` (storage.py:19) — package-relative, no installation/packaging step needed (module comment: "The package runs from the repo root and is never installed").

### Integration point for a 4th example

**Purely additive — no code changes.** Add `cfb_system_maker/examples/neutral-site-indoor-unders.json` (or similar name matching `_SYSTEM_NAME_RE = ^[A-Za-z0-9_-]+$`) with the same JSON shape `storage._system_to_dict` produces (top-level `name`, `saved_at`, `theory`, `source`, `search_candidates_tested`, nested `system: {...}`). PROJECT.md specifies the content: total/under system using `neutralSite`, `gameIndoors`, `venue_dome` feature filters — "all three features already in the registry," confirmed present in `features.py`'s `FEATURE_REGISTRY`.

Because `list_examples()`/`load_example_system()` are directory scans with no hardcoded count or filename list, `storage.list_systems`/`list_examples`-driven UI (the "Example Systems tab") picks up a 4th entry automatically — this is why PROJECT.md/STATE.md describe the existing 3 as already-generic ("Three bundled read-only example systems ... on their own Example Systems tab" — Phase 5, D-14/D-21 in STATE.md). Read one existing example file's exact JSON shape before hand-writing the new one (do not guess field names/ordering) — recommend `Read`-ing `nonconference-away-dogs.json` or `total-unders-high-lines.json` (the latter is already a total-bet-type example, closest structural match) as the last step before writing item 5's file.

**No sequencing dependency on items 3/4** — this file can be added independently at any point, including before or after the merge, since it doesn't touch any `.py` file. The only soft dependency: writing correct `feature_filters` entries for `venue_dome` (a `categorical` control, per the registry naming pattern) benefits from item 4's fallback existing first, so that if the JSON's `(op, control)` combo happens to be one `describe()` doesn't already render, the sentence still shows instead of silently vanishing — build item 4 before item 5 for defense-in-depth, though it is not a hard requirement.

## Build Order

Given the file-overlap finding and the dependency notes above:

1. **Merge `fix/web-app-review-2026-08-26` to master first.** This is a hard prerequisite for items 3 and 4 (both edit `backtest.py`/`web.py`/`storage.py`/`describe.py`-adjacent code the fix branch already modified — building on stale master would produce a conflicting divergent diff). The working tree is currently already on this branch, so in practice this means: finish items 3-5 as commits on top of the current branch state, then merge the whole branch (fix commits + new items) to master together, OR merge the fix branch alone first and then branch again for items 3-5. Either is structurally fine since the code being read for this research already reflects the fix branch's changes; the risk is only building items 3-5 against a **different, pre-merge master** in parallel.
2. **Item 4 (describe() fallback)** — smallest surface area (one function, one file, zero schema/route changes), lowest risk, unblocks safer authoring of item 5's feature filters. Build first.
3. **Item 5 (4th example system)** — pure JSON, no code dependency on item 3, soft dependency on item 4 (fallback rendering safety net). Build second.
4. **Item 3 (Hide Duplicates)** — largest surface area (new `SystemFilter` field, `storage.py` backward-compat serialization in 4 functions, `web.py` form parsing + query-param passthrough + template checkbox, `run_backtest`/`run_backtest_summary` dedup logic, and an unresolved product decision on tie-breaking). Build last, and treat the tie-break rule as an open question to resolve during phase discussion/planning, not something this research can settle from the code alone.
5. **Item 2 (live in-season verification)** has no code dependency on any of 3/4/5 — it is a manual verification task against the existing `upcoming` CLI/dashboard — and can run in parallel with or after any of the above, gated only by real games existing (season start ~2026-08-29).

## Anti-Patterns to Avoid

### Anti-Pattern: Forcing Hide Duplicates into the D-03 fade shape

**What people might do:** Read D-03 ("fade is read exclusively inside grade_bet/_grade_total_bet, never inside matches_system, to preserve matched-count invariance") and assume all future `SystemFilter` boolean toggles must follow the identical shape — implement Hide Duplicates as a flag read inside `grade_bet`.
**Why it's wrong:** `grade_bet` operates on one `GameRecord` at a time with no visibility into sibling matched games; it structurally cannot detect a duplicate `game_id` in isolation. Forcing this shape would require either a second matching pass or module-level state, both worse than a straightforward list-level post-filter.
**Do instead:** Treat D-03 as scoped to *value-flipping* toggles (fade), and implement *count-changing* toggles (Hide Duplicates) as a list-level step in `run_backtest`, matching how `count_overfit_filters`/`compute_season_breakdown` already operate on the full `details`/`system` at the orchestration level rather than per-record.

### Anti-Pattern: Editing describe()'s existing 4 branches to add the fallback

**What people might do:** Restructure `_feature_group_sentence` into a dict-dispatch or refactor the 4 branches "for cleanliness" while adding the fallback.
**Why it's wrong:** Violates CLAUDE.md's "Surgical Changes" rule and risks the exact regression T-01-03 warns about — a refactor could subtly change which branch fires for an existing combo, breaking already-correct rendered sentences. STATE.md explicitly frames this as "without breaking the existing rendered sentences."
**Do instead:** Append the fallback as a new final branch, touching zero existing lines in the 4 current branches.

## Integration Points Summary Table

| Item | New vs Modified | Files | Functions |
|------|------------------|-------|-----------|
| 1. Merge fix branch | N/A (git operation) | `backtest.py`, `features.py`, `storage.py`, `web.py`, static/templates, tests, docs | N/A |
| 3. Hide Duplicates | Modified: `models.py` (new field), `storage.py` (4 serialize/deserialize fns), `web.py` (form parsing + query passthrough + template) | New: none. Modified: `models.py` (`SystemFilter`), `backtest.py` (`run_backtest`, `run_backtest_summary`), `storage.py` (`_system_to_dict`, `_system_from_dict`, `_finalist_system_to_dict`, `_finalist_system_from_dict`), `web.py` (`_empty_form`, `_form_values_from_args`, the ~1220 `SystemFilter(...)` construction block, the 1433 query-param tuple), template (checkbox) | `SystemFilter.hide_duplicates`, `run_backtest`, `run_backtest_summary` |
| 4. describe() fallback | Modified only | `describe.py` | `_feature_group_sentence` |
| 5. 4th example system | New file only | `cfb_system_maker/examples/*.json` | N/A (data, no function) |

## Sources

- Direct code reading: `cfb_system_maker/backtest.py`, `cfb_system_maker/models.py`, `cfb_system_maker/storage.py`, `cfb_system_maker/describe.py`, `cfb_system_maker/features.py`, `cfb_system_maker/web.py` (all on `fix/web-app-review-2026-08-26`, confidence HIGH — primary source, no inference).
- `.planning/STATE.md` — Accumulated Context (D-03, D-01, D-14, D-18, D-21, T-01-03 blocker note).
- `.planning/PROJECT.md` — Current Milestone target features, Deferred/Out-of-Scope history for Hide Duplicates, Key Decisions table.
- `git diff master...fix/web-app-review-2026-08-26 --stat` — confirmed file-overlap between the fix branch and items 3-5's touch points.

---
*Architecture research for: cfb_system_maker v1.1 Season Readiness milestone*
*Researched: 2026-08-26*
