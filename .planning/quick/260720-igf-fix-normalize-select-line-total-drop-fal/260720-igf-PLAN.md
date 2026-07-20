---
type: quick
slug: fix-normalize-select-line-total-drop-fallback
created: 2026-07-20
files_modified:
  - tests/test_normalize.py
  - cfb_system_maker/normalize.py
---

# Quick Task: Total falls back to first sibling provider when preferred line lacks it

## Problem

`normalize.normalize_games` reads BOTH `spread` and `total` from the single line
returned by `_select_line(...)` (normalize.py lines 37-39). `_select_line` picks
the preferred provider (`consensus`) for the spread. For CFBD seasons 2013-2016,
`consensus` commonly has `spread` populated but `overUnder` null, while sibling
providers on the SAME game (`teamrankings`, `numberfire`) DO carry `overUnder`.
Because total is read only from the selected line, it is dropped even though a
sibling provider has it.

Measured impact: ~93-97% of `total` values are null for 2013-2016 in
`data/processed/games.csv`, dropping to ~0-11% null from 2017 onward.

Confirmed in `data/raw/lines_2013.json` (game id 332412579): `teamrankings` and
`numberfire` both have `overUnder=56`; `consensus` (the selected line) has
`overUnder=None`, so the game's total is lost.

Root cause is already diagnosed — do not re-investigate.

## Fix

Inside `normalize_games`, when the selected line's total is null, fall back to
the FIRST line (original list order) in `betting_game["lines"]` that has a
non-null `overUnder`/`over_under`/`total`, and use that as the game's `total`.

- Do NOT change which line `_select_line` returns (spread selection unchanged).
- `GameRecord.provider` must keep reflecting the spread's provider — do NOT
  overwrite it with the total's source provider.
- Total-source selection is separate from spread-source selection ONLY for the
  `total` field.

### Scope guardrails (do NOT touch)

- No change to `_select_line` / spread selection logic.
- No change to `GameRecord` field order/schema, `models.py`, or `storage.py`.
- No new CLI flags or config options — pure fix inside `normalize.py`.
- Match existing normalize.py style: reuse `_first`/`_optional_float`, no new
  abstractions beyond a sibling helper mirroring the existing `_select_line`.

## Tasks

### Task 1 (TDD RED): Add failing test for cross-provider total fallback

**File:** `tests/test_normalize.py`

Add a test named `test_total_falls_back_to_sibling_provider_when_preferred_line_lacks_it`.
Follow the existing pattern in this file (construct `games`/`lines` dicts, call
`normalize_games(..., provider="consensus")`, destructure `[record]`).

Behavior to assert (one game, multiple lines):
- `lines` for the game, in this order:
  1. `{"provider": "consensus", "spread": -11.5, "overUnder": None}`
  2. `{"provider": "teamrankings", "spread": -11, "overUnder": 56}`
  3. `{"provider": "numberfire", "spread": -11, "overUnder": 58}`
- `record.provider == "consensus"` — spread source preserved.
- `record.spread == -11.5` — from the selected (consensus) line.
- `record.total == 56` — FIRST sibling with a total (teamrankings), NOT 58.
  This value pins both "falls back across providers" AND "first in list order".

**Verify:** `python -m pytest tests/test_normalize.py::test_total_falls_back_to_sibling_provider_when_preferred_line_lacks_it`
FAILS before Task 2 (current code yields `total is None`).

**Done:** New test exists, follows file conventions, and fails for the right
reason (total is None / not 56) against unmodified `normalize.py`.

### Task 2 (TDD GREEN): Add total fallback source in normalize_games

**File:** `cfb_system_maker/normalize.py`

Add a `_select_total(lines, selected_line)` helper mirroring `_select_line`'s
structure: return the selected line's own total if present; otherwise return the
first line in `lines` (original order) with a non-null
`overUnder`/`over_under`/`total`; else `None`. Wire it into the `GameRecord`
construction so the `total=` field uses `_select_total(betting_game.get("lines", []), selected_line)`
instead of reading only `selected_line`. Keep `provider=` and `spread=` exactly
as they are.

Add a short code comment (1-2 lines, WHY only, not a docstring) at the fallback
point noting:
1. This picks the FIRST available total across providers (not necessarily the
   spread's provider).
2. Provider precedence for totals may be revisited later (e.g. preferring a
   specific provider's total the way spread does).

**Verify:** `python -m pytest tests/test_normalize.py`

**Done:** The new test passes; all previously-passing normalize tests still pass
(notably `test_normalize_uses_first_usable_line_when_provider_missing` — single
line, no sibling total — must still yield `total is None`, and
`test_normalize_joins_games_to_consensus_lines` — consensus line already has a
total — must still yield `total == 52.5`).

## Verification

- `python -m pytest tests/test_normalize.py` — full normalize suite green,
  including the new fallback test and all pre-existing tests.
- Spread selection, `GameRecord.provider`, and CSV schema unchanged (no edits to
  `_select_line`, `models.py`, or `storage.py`).
