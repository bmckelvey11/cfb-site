# One book, two names: the DraftKings provider-key split

**2026-09-10.** Reproduce with `python scripts/audit_core_merges.py --merge lines` and the
queries below. Follows [the Bucket C merges](core-merge-bucket-c-2026-09-10.md), which
flagged this and deferred it.

## The question

`core.fact_game_line` carried both `draftkings` (2,963 rows) and `draft kings` (235). A
consumer filtering `provider_key = 'draftkings'` silently missed the other 235. Are they the
same book — and if so, which row is real?

## Method

Compare the two keys on the games they share, column by column, in both directions: how many
rows carry a value the other lacks, and how many carry different values where both are
populated. Then check the raw JSON to see where the duplication originates.

**Data:** local `cfb.duckdb`, 2013–2026.

## Result: one book, and one of the two rows is strictly degraded

**CFBD emits both spellings inside the same `lines` array**, on **215 games**. From
`raw/lines_2026.json`, game 401856666 (Tennessee–Furman):

```json
{"provider": "DraftKings",  "spread": -49.5, "spreadOpen": -46.5, "overUnder": 66.5, "overUnderOpen": 66.5}
{"provider": "Draft Kings", "spread": -49.5, "spreadOpen": null,  "overUnder": 66.5, "overUnderOpen": null}
```

Across all 215 shared games:

| column | only `DraftKings` has it | only `Draft Kings` has it | both, differing | identical |
|---|---|---|---|---|
| `spread_close` | 0 | **0** | 31 | 184 |
| `spread_open` | 161 | **0** | 0 | 54 |
| `total_close` | 0 | **0** | 21 | 194 |
| `total_open` | 121 | **0** | 0 | 94 |
| `moneyline_home` | 184 | **0** | 0 | 31 |
| `moneyline_away` | 185 | **0** | 0 | 30 |

**`Draft Kings` never carries a value `DraftKings` lacks.** It is a degraded duplicate — same
book, a less complete capture. The only divergences are 31 spreads and 21 totals differing by
a half point or so, which is the same book at two moments inside one payload.

That settles the merge rule without a coin flip: collapse the key, and where both rows exist,
**the more populated one wins**. Nothing is lost that is not also present in the survivor.

## What was arbitrary before

The split was not the only symptom. **Every consumer was already choosing between the two
rows, and all of them chose by array order:**

- `normalize._select_line` returned the first usable match — so `games.csv` carried the
  degraded row's nulls for roughly half of the 215 games.
- `core.fact_game_line` kept "the first occurrence" per `(game_id, provider_key)`.
- `enrich._build_line_move_index` re-selects through `_select_line`, so a game whose open was
  sitting in the same payload got a **null line-move feature** instead.

So this was never only a naming problem. It was a non-injective provider key feeding four
consumers that each resolved it differently — the same shape as the `dim_conference` name
collision in [the Bucket C merges](core-merge-bucket-c-2026-09-10.md).

## The fix: one rule, owned by one module

`normalize.provider_key` owns the alias map and `duckdb_core._provider_key` delegates to it.
Two definitions of what a book is called is how `core.fact_game_line` and `games.csv` end up
disagreeing about whether a game has a DraftKings row at all.

`normalize._best_of_book` picks the most complete row **for the book already selected** —
which book gets chosen is untouched, only which of its duplicate rows is read. The same rule
appears twice more because the data arrives three ways: the REST unnest dedupes in Python,
and `_merge_game_lines`'s view re-establishes the grain with a `QUALIFY row_number()`, because
`stg.game_lines` is unique on `(gameId, linesProviderId)` and the alias maps **two provider
ids onto one key** — CFBD's 100 and the synthetic 888888 `_AN_BOOK_PROVIDER` assigned the
ActionNetwork feed. Without that the full outer join fans out and the primary key fails, which
is how it was caught.

Ties break on the lower provider id, so a rebuild is reproducible.

## Result

| | before | after |
|---|---|---|
| `core.fact_game_line` rows | 47,581 | 47,366 |
| `draftkings` / `draft kings` | 2,963 / 235 | **2,983** / — |
| `core.dim_lines_provider` | 17 | 16 |

The 215 duplicate rows collapse; 56 games **gain** a DraftKings line, because aliasing the
GraphQL side too lets the AN feed's rows land on games REST had no DraftKings row for.
Verified against the pre-change warehouse: **0 rows lost, 0 non-NULL values became NULL**, and
51 values changed — all on the `draftkings` key, which is exactly the 31 spread and 21 total
conflicts resolving to the more complete row.

`games.csv` was rebuilt for all 14 seasons, unchanged at 13,841 rows.

## What was deliberately not done

**The Caesars family is left split.** `Caesars` (2018–2026, with a 2021–23 gap), `Caesars
(Pennsylvania)` (2020–21) and `Caesars Sportsbook (Colorado)` (2021–23) **never share a
game**, and their season ranges are disjoint in a way consistent with either a rename history
or genuinely separate state licences. Nothing measured here settles which. Merging them on a
guess destroys the distinction irreversibly, and unlike DraftKings there is no
strictly-degraded twin to justify a winner. `tests/test_core_merges.py` pins that they stay
separate, so a future merge has to be a decision rather than a drift.

## What this does not support

- **It does not establish which of the 31 differing spreads is "correct".** The more populated
  row wins because it carries strictly more information, not because its number is righter.
  Both come from CFBD, for the same book, in one payload.
- **It does not audit the other 14 provider names** for the same defect. Only the DraftKings
  pair was read row by row; the Caesars family was checked for overlap and season range only.
- **It does not address the synthetic provider ids.** `_AN_BOOK_PROVIDER` maps ActionNetwork's
  DraftKings to 888888 and Bovada to 999999 rather than to CFBD's own ids. The alias makes the
  *key* correct downstream, but `stg.lines_provider` still carries two rows for one book.
- **It does not re-fit anything.** `games.csv` now carries opens on games where it carried
  nulls, which changes the line-move features `enrich` derives. No model was re-fit or
  re-evaluated here, and no claim is made about whether that changes any result.
