# Stack Research

**Domain:** Python/Flask betting-system backtester — closing out 5 deferred v1.0 items for v1.1 Season Readiness
**Researched:** 2026-08-26
**Confidence:** HIGH

## Recommended Stack

**No new dependencies are needed for any of the 5 milestone items.** All five are solvable with the existing Python 3.14 / Flask 3.1 / vanilla-JS stack and stdlib, using patterns already established in the codebase. This section documents *why*, per item, rather than proposing new core technologies (there are none to propose).

### Core Technologies (unchanged)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.14.6 (installed) | Runtime | Already the project runtime; nothing in the 5 items needs a newer capability |
| Flask | 3.1.3 (installed, per `requirements.txt`) | Web layer | Existing routes (`web.py`) and query-param/JSON patterns cover all 5 items |
| stdlib `dataclasses` / `set` / `dict` / `json` | builtin | Domain models, dedup, storage | `models.py` frozen dataclasses, `search.py`'s existing `candidate_identity`-based dedup, and `storage.py`'s JSON `_system_from_dict` parser are direct precedent for items 3, 4, 5 |

### Supporting Libraries

None required. No table entry — every item below is closed-form with what's already imported.

### Development Tools (unchanged)

| Tool | Purpose | Notes |
|------|---------|-------|
| pytest (`pytest.ini`, testpaths=`tests`) | Test runner | Existing 1:1 module-mirrored test pattern (`tests/test_describe.py`, `tests/test_backtest.py`, etc.) covers all 5 items; no new test tooling needed |

## Installation

No installation step. `requirements.txt` is unchanged by this milestone.

## Per-Item Analysis

### 1. Merge `fix/web-app-review-2026-08-26` to master

Pure `git merge`. Not a stack question — no code or dependency change of its own; whatever the 26 commits already added is already in `requirements.txt` (verified: still just `cfbd-python` reqs + `pytest` + `Flask` + pinned `anthropic==0.111.0`, unrelated to this milestone's UI/backtest work).

### 2. Live in-season verification (Current Matches, feature-filtered matching)

This is a **manual, one-time verification task**, not an automation build:
- Run the existing `upcoming` CLI pipeline against the live CFBD API once games are posted (on/after 2026-08-29) and inspect the Current Matches panel and matched systems by eye.
- **Rejected: APScheduler / Celery / cron / OS Task Scheduler.** These would matter if verification needed to *recur* (e.g., a nightly re-check). It doesn't — PROJECT.md frames this as confirming a deferred v1.0 item works once, against real data, not standing up ongoing monitoring. Adding a scheduler here is unrequested "flexibility" per this repo's CLAUDE.md (`## 2. Simplicity First`).
- **Rejected: `responses` / `vcrpy` / `freezegun`** for testing the live call path. The project's established pattern for network-free testing is *injectable fakes* — `post_fn` in `graphql_client.py`, `cfbd_module` in `scrapers.py` — not a cassette/mock-HTTP library. If a regression test is wanted for the upcoming-games matcher, follow that existing injection pattern; don't introduce a new mocking dependency for one verification pass.
- If verification surfaces a real bug, that becomes its own `/gsd-debug` or `/gsd-quick` task with its own (likely still stack-neutral) fix — not a reason to add tooling now.

### 3. Hide Duplicates toggle (drop a game when one `game_id` yields two candidate bets)

Confirmed by reading `models.py` and `backtest.py`:
- `BacktestResult.bet_details: list[BetDetail]` is a plain list of frozen `BetDetail` dataclasses, each carrying `game_id: int` (`models.py:76`). This list is assembled inside `run_backtest` (`backtest.py`), **not** `GameRecord`/`storage.py`'s CSV path.
- Since total systems now match either side (commit `d9c93e4`), two `BetDetail` rows can share one `game_id`. Dedup is a filter over `bet_details` keyed on `game_id`, done with a `set`/`dict` before building `BacktestResult` — exactly the pattern `search.py`'s `candidate_identity`-based dedup already uses (`seen: set[tuple]` / `deduped: list[...]`, `search.py:359-368`).
- This is aggregation-layer logic. It does **not** touch `GameRecord` field order or `models.py`'s frozen `GameRecord`/`storage.py`'s CSV read/write — so the CSV-schema-stability constraint in CLAUDE.md is not implicated. No migration, no new field, no library.
- **Rejected: pandas.** `pandas.drop_duplicates(subset='game_id')` would do this in one line, but it's a large dependency to add for a `set`-membership check the codebase already does natively elsewhere (`search.py`). Adding pandas here would also be the project's first use of it anywhere in `cfb_system_maker` — a real footprint increase for zero capability gain.

### 4. Close T-01-03: `describe()` fallback for unrenderable `(op, control)` combos

Confirmed by reading `describe.py`: the function is `_feature_group_sentence` in `cfb_system_maker/describe.py` (**not** `web.py`, which only calls into it) — hardcoded branches at lines 76-85 cover exactly 4 `(op, control)` combos (`eq`+`bool`, `eq`+`categorical`, `in`+`categorical`, plus the separate `numeric` branch above them at line 70). Any other combo `feature_ok()` accepts falls through to `return None` at line 86, silently dropping the filter's sentence from the UI.
- The fix is a fallback `else` branch producing a generic sentence (e.g. `f"{label} {filt.op} {filt.value}"`) instead of `None` — pure string formatting, no library.
- Test coverage follows the existing pattern: construct a `FeatureFilter`/`SystemFilter` with an out-of-matrix `(op, control)` combo directly and assert `describe()` returns a non-empty sentence, mirroring `tests/test_describe.py`'s existing style (construct model, assert on result — CLAUDE.md's "Tests" section).
- **Rejected: Jinja2 template-side fallback.** `describe()` returns plain dicts consumed by `web.py`/templates as data, not markup — the gap is a Python-side branch-completeness bug, not a rendering-engine limitation. Nothing about Jinja (already in use via Flask) needs to change.

### 5. Bundle neutral-site + indoor unders example system

Confirmed by reading `storage.py` and `cfb_system_maker/examples/*.json`: bundled examples are plain JSON files in `cfb_system_maker/examples/` (currently `nonconference-away-dogs.json`, `spread-home-favorites.json`, `total-unders-high-lines.json`), loaded read-only via `load_example_system`/`list_examples`, parsed through the **same** `_system_from_dict` parser used for user-saved systems.
- Adding a 4th file (`neutral-site-indoor-unders.json` or similar) is a **data-only change** — write JSON matching the existing shape (see `total-unders-high-lines.json` for the exact key set: `bet_type: "total"`, `total_side: "under"`, `feature_filters` array with the three boolean features `neutralSite`/`gameIndoors`/`venue_dome` at `perspective: "single"`, `op: "eq"`, `value: true`), plus a `theory` string.
- All three features (`neutralSite` matchup group, `gameIndoors` weather group, `venue_dome` metadata group) are already in `FEATURE_REGISTRY` per the milestone brief — no registry change, no new feature-computation code.
- Because `_system_from_dict` already defaults gracefully for missing/extra keys (the storage-backward-compat convention CLAUDE.md calls out for `theory`/`fade`), a new example JSON needs no parser change even though it's a new file, not a schema change.
- **Rejected: nothing to reject here** — there is no plausible library reach for "add a JSON file." Noted only because the milestone brief asked for confirmation across all 5 items.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|--------------------------|
| stdlib `set`/`dict` dedup on `BetDetail.game_id` | `pandas.drop_duplicates` | Only if the project later adopts pandas broadly for the backtest/aggregation layer (it currently doesn't use it anywhere) — not worth introducing for this one dedup |
| Manual one-time `upcoming` CLI run for live verification | APScheduler / cron-based recurring verification job | Only if the project later wants *ongoing* automated monitoring of live CFBD data drift, which is out of scope for this milestone |
| Injectable fake (`post_fn`/`cfbd_module` pattern) for any new network-adjacent test | `responses` / `vcrpy` HTTP-mocking library | Only if a future feature needs to replay complex multi-request HTTP sequences that the simple injectable-function pattern can't express cleanly |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|--------------|
| pandas | Zero current usage in `cfb_system_maker`; the one candidate use (Hide Duplicates) is a single `set`-keyed filter the codebase already does natively in `search.py` | stdlib `set`/`dict` filtering over `bet_details` |
| APScheduler / Celery / cron | Item 2 is a one-time manual verification pass tied to a real-world calendar event (season start), not a recurring job | Run the existing `upcoming` CLI command by hand once games are posted |
| `responses` / `vcrpy` / `freezegun` | Project already has an established injectable-fake pattern (`post_fn`, `cfbd_module`) for network-free tests; a cassette library duplicates that capability | Follow the existing injection pattern if a regression test is added |
| A new templating/rendering layer for `describe()` | The T-01-03 gap is Python branch-completeness (an `if/elif` chain missing an `else`), not a template-engine limitation | Add a fallback `else` branch in `_feature_group_sentence` (`describe.py`) |

## Stack Patterns by Variant

**If Hide Duplicates needs a UI toggle (checkbox) rather than always-on:**
- Add a query-param/form field to `web.py` (e.g. `hide_duplicates=1`) following the existing query-string-driven form pattern (same mechanism as `fade`, `?tab=`), threaded into the dedup step before `BacktestResult` assembly.
- Because it's a display-time filter over already-computed `bet_details`, it can even be applied post-hoc in `web.py` without changing `backtest.py`'s public signature — confirm this shape during phase planning, but no library is implicated either way.

**If the T-01-03 fallback sentence needs to look meaningfully different from the 4 known branches (e.g. to visually flag "unusual filter" in the UI):**
- Return an extra key in the sentence dict (e.g. `{"text": ..., "key": ..., "fallback": True}`) and let the existing template conditionally style it — still no new dependency, just one more dict key threaded through the existing Jinja template.

## Version Compatibility

Not applicable — no new packages are introduced, so there are no new version-compatibility constraints against `cfbd-python`'s pinned pydantic v1 stack, Flask 3.1.3, or Python 3.14.6.

## Sources

- Direct codebase inspection (HIGH confidence — primary source, not third-party docs):
  - `cfb_system_maker/models.py` — `BetDetail.game_id`, `BacktestResult.bet_details`, frozen-dataclass shapes
  - `cfb_system_maker/describe.py` — `_feature_group_sentence` fallback gap (lines 76-86), confirms T-01-03 location and mechanism
  - `cfb_system_maker/search.py` — existing `set`/`dict`-based `candidate_identity` dedup precedent (lines 359-368)
  - `cfb_system_maker/storage.py` — `load_example_system`/`list_examples`/`_system_from_dict`, confirms example systems are JSON files parsed through the backward-compatible saved-system parser
  - `cfb_system_maker/examples/total-unders-high-lines.json` — confirms exact JSON shape for a new bundled example
  - `requirements.txt`, `pip show flask`, `python --version` — confirms installed versions (Flask 3.1.3, Python 3.14.6) and that no milestone-relevant dependency has changed
  - `.planning/PROJECT.md`, `CLAUDE.md` (repo root) — milestone scope, constraints (no-lookahead, storage backward compat, CSV schema stability)

---
*Stack research for: cfb_system_maker v1.1 Season Readiness*
*Researched: 2026-08-26*
