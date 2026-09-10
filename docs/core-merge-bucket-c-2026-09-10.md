# Merging the last four GraphQL sources into tables `core` already had

**2026-09-10.** Reproduce with `python scripts/audit_core_merges.py`. Governing decision:
[ADR-0001](adr/0001-merged-sources-land-in-core.md).

## The question

The Bucket C/B merges already landed built *new* `core` tables — `dim_coach`,
`dim_draft_pick`, `dim_recruit`, `fact_team_talent`, `fact_coach_season`
([containment remeasure](warehouse-containment-remeasure-2026-09-10.md)). A wrong join
there shows up as a table nobody had before, which is loud.

The remaining four merge into tables that already exist and already have consumers
(`research/spread/scripts/eval_version_b.py`, `tests/test_core_agreement.py`,
`tests/test_spread_version_b.py`). The failure mode is the opposite and it is quiet: a
row count that moves, or a column whose values change under a query someone already
wrote. So: what does each one actually add, and does taking it obey ADR-0001?

## Method

`scripts/audit_core_merges.py` measures the same three things per merge — matched /
core-only / gql-only-in-span row counts, disagreement counts on shared columns where both
sides are non-NULL, and fill rate on the GraphQL-exclusive columns. The gate is ADR-0001:
`gql-only (in span)` must be 0, or the merge grows the table rather than widening it.

**Data:** local `cfb.duckdb`, 310 tables, rebuilt 2026-09-10 after the re-scrape.
`core` spans 2012–2026; `stg_gql.game` spans 1869–2026.

## Result

| Merge | Verdict | What it added |
|---|---|---|
| `conference` → `core.dim_conference` | taken | `division` |
| `game` → `core.fact_game` | taken | conference-FK repair; 78,030 surplus rows → `core.fact_game_historical` |
| `calendar` → `core.dim_week` | **no-op** | nothing |
| `lines` → `core.fact_game_line` | **deferred** | not a merge — see below |

### `conference` — one column, and it explains a bug

256 of 256 ids match, no name disagrees, no row on either side is exclusive. GraphQL's two
exclusive columns are `division` (fills 256/256) and `srName` (fills **1** of 256 — a §5
drop-list candidate, not a merge input). Only `division` is carried.

`division` turned out to matter for a second reason. **44 conference names in
`core.dim_conference` are held by more than one row** — four are named `Big Sky`, four
`Southland`, four `SWAC`. That is what `division` distinguishes.

### `game` — the surplus is a new table, and the conference ids were arbitrary

34,642 of 34,646 `fact_game` rows match GraphQL on `gameId`; 4 do not; **0 GraphQL rows in
`core`'s span are missing from `fact_game`**. So the merge widens without growing, exactly
as ADR-0001 requires. The 78,030 GraphQL games below 2012 go to `core.fact_game_historical`
instead, which is what the ADR prescribes for surplus.

Elo was **not** taken. `homeEndElo`/`homeStartElo` are GraphQL's spelling of REST's
`homePostgameElo`/`homePregameElo` — the near-miss `audit_pair_columns.py`'s own docstring
warns about — and nothing in `fact_game` reads Elo today. `status` was not taken either:
`completed` is already non-NULL on all 34,646 rows.

What was taken is a repair. `_build_fact_game` resolved a conference by **name**, against a
`dim_conference` whose names are not unique (above), so the lookup dict picked arbitrarily
among the same-named rows. Before the repair:

| | home | away |
|---|---|---|
| id differs from GraphQL's FK | 3,714 | 3,985 |
| NULL in `fact_game`, present in GraphQL | 0 | 0 |

Every sampled disagreement resolved to the **same conference name** on both sides
(`Western Athletic` 16 vs 215, `Mid-American` 342 vs 15). The map was non-injective, not
wrong about which conference. The builder now takes
`coalesce(gql_fk, existing)`, so the 4 games GraphQL lacks keep what they had; the
disagreement count is now 0 and the NULL counts are unchanged at 124 home / 552 away.

**This changes existing column values, which ADR-0001 does not authorize.** The ADR governs
rows versus columns and is silent on a third category: overwriting a column already in
`core`. It was taken because no consumer reads `home_conference_id` or
`away_conference_id` — grepped across the three consumers named above, plus all of
`cfb_system_maker/`, `models/`, `research/`, `scripts/`. If that changes, the ADR needs a
clause.

### `calendar` — measured no-op

0 GraphQL weeks in `core`'s span are missing from `dim_week`; the only exclusive column is
`year`, which is REST's `season` renamed. The 166 GraphQL weeks from 2002–2011 are **not**
taken: `dim_week` is what bounds `core`, `_build_fact_game` filters on
`(SELECT min(season) FROM core.dim_week)`, so merging them would expand `fact_game` by
78,030 rows through the back door — the thing ADR-0001 exists to prevent. Recorded as a
no-op rather than skipped silently.

### `lines` — not a merge, and deferred

`stg_gql.game_lines` is not a GraphQL scrape. Its `line_source` column reads `cfbd` 37,048
/ `actionnetwork` 8,656 / `cfbd+an` 1,599: it is **already** a merged table, carrying the
ActionNetwork ingest. `core.fact_game_line` (39,006 rows, 12 providers) is built by
unnesting REST `stg.lines` and is the CFBD-only subset of it.

The grain gate passes — `period='game'` is 47,303 rows, unique on
`(gameId, linesProviderId)` — and five books are in `game_lines` and have **never** been in
`core.fact_game_line`:

| provider | rows |
|---|---|
| circa | 1,950 |
| fanduel | 1,949 |
| betmgm | 1,898 |
| bet365 | 453 |
| pinnacle | 143 |

So the real task is not "merge a GraphQL source" but "repoint `_build_fact_game_line` from
`stg.lines` to `game_lines` where `period='game'`" — a rewrite of a `core` table that feeds
the spread model, adding roughly 8,300 rows and five new provider keys. Different shape of
change, its own commit, its own measurement. Tracked as `#core-fact-game-line-repoint`.

## Verification

Built on a scratch copy of `cfb.duckdb` first. Every pre-existing `core` table's row count
is byte-identical before and after; `fact_game_historical` (78,030 rows, 1869–2011, zero
`game_id` overlap with `fact_game`) is the only addition. Fast suite: 887 passed.
`-m slow tests/test_core_agreement.py`: the same two failures as the pre-change baseline,
with identical assertion text — `coverage drift: csv_only=[] sql_only=[...] (0/39)` and
`assert -57.5 == -55.5`. Both are the known `games.csv` staleness (CSV 2026-09-08 01:05 vs
`raw/games_2026.json` 2026-09-10 05:00), not caused by this change.

## What this does not support

- **It does not establish that GraphQL's conference FK is era-correct.** It establishes
  only that it is *deterministic* where the name lookup was not. Both sides agree on the
  conference *name* in every sampled disagreement; nothing here checks either against a
  third source. A 2012 realignment error in GraphQL would survive this measurement intact.
- **`core.fact_game_historical` is not classification-accurate for its own era.**
  `home_classification` and the conference FKs are what GraphQL reports *today*, and
  divisions and conferences were reorganized repeatedly across 1869–2011. Use it for
  identity and scores. The builder's docstring carries the same warning.
- **It does not re-measure the other eight pairs.** Those are
  [audit_pair_columns.py](../scripts/audit_pair_columns.py)'s job and their verdicts are
  unchanged.
- **It does not license dropping anything.** No bucket moved to A;
  `#warehouse-drop-superseded` still targets only Bucket A's three REST tables.
- **The `lines` numbers are a scoping measurement, not a validation.** They say five books
  are missing from `core.fact_game_line`; they do not say the `game_lines` values for them
  are correct, and they do not check spread sign convention, open-vs-close semantics, or
  agreement with `stg.lines` on the 12 providers both hold.
