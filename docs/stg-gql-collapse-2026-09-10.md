# Collapsing `stg_gql` into `stg`

**2026-09-10.** Reproduce with `python scripts/verify_warehouse_plan.py` and
`python scripts/verify_warehouse_plan.py --selftest`. Migration:
`python scripts/collapse_stg_gql.py --dry-run`. Decision:
[ADR-0003](adr/0003-one-stg-schema-suffix-only-the-colliders.md) and
[plan §2](superpowers/plans/2026-09-08-warehouse-rationalization-master.md).

## The question

ADR-0002 put GraphQL staging tables in their own `stg_gql` schema to stop a load-order-dependent
clash resolver from letting `stg.calendar` (REST, 258 rows) and the GraphQL calendar (424 rows)
swap provenance across a rebuild. ADR-0003 reversed the *remedy* — an explicit static mapping
already makes load order irrelevant, and a schema tagging all 38 tables to disambiguate 3 is
disproportionate — but sequenced the collapse last, on a prediction: that by the time
rationalization finished, the colliders would have stopped existing in duplicate and **zero**
suffixes would be needed.

So: is that true now, and what does the collapse actually cost?

## Result: the collapse holds, the prediction does not

38 transport-tagged names became 3. All three remain, and they are **permanent**.

| Collider | Predicted fate | Actual |
|---|---|---|
| `predicted_points` | REST side drops (Bucket A) | **failed R6** — kept |
| `draft_picks` | "merges into `core`" (Bucket C) | merged, and `stg` sources retained |
| `calendar` | "merges into `core`" (Bucket C) | merge was a measured no-op |

`predicted_points` is the measurement that moved: its REST rows lose `down`/`distance` at the
API, so containment cannot be proved
([the drop write-up](warehouse-drop-superseded-2026-09-10.md)).

The other two are a **reasoning error**, not a measurement. Merging a pair into `core` never
retires its `stg` sources, because **`core` is built *from* them**. `_build_dim_draft_pick`
reads `stg.draft_picks` and `stg.draft_picks_gql` on every `build_core`; delete either and the
next rebuild produces a smaller table. `core` is a derived layer, not a destination that
consumes its inputs. Nothing the rationalization plan could have done would have made those two
go away — the prediction was never reachable.

**The collapse went ahead anyway, because §2's argument never rested on it.** A schema that
tags 38 tables to disambiguate 3, where 28 of them have no counterpart of any spelling to be
disambiguated from, is disproportionate whether the 3 are temporary or not. ADR-0002's own
objection — that a name would be "permanently named after which API produced it" — is about
proportion, and 3 of 34 is a different proposition from 34 of 34. It is accepted for the three
and rejected for the other 31.

## What moved

40 tables, 0 collisions, 0 failures. DuckDB has no `ALTER TABLE ... SET SCHEMA` (1.5.2), so
each is a `CREATE TABLE AS SELECT` plus `DROP`, resumable and refusing to overwrite.

- **35 tables** to their bare name: `stg_gql.game` → `stg.game`, `stg_gql.game_lines` →
  `stg.game_lines`, and so on, including explode children (`game__awayLineScores`,
  `game_team__lineScores`, `historical_team__images`), which are **scanned for** rather than
  listed — a new nested column creates a child table nobody edited a list for.
- **3 tables** suffixed: `calendar_gql` (424), `draft_picks_gql` (13,080),
  `predicted_points_gql` (19,800).
- **2 camelCase roots** snake-cased, which ADR-0003 committed to and never assigned:
  `stg.gameMedia` → `stg.game_media` (23,907), `stg.gamePlayerStat` → `stg.game_player_stat`
  (5,541,660).

Those two were the trap the TODO flagged. They are **GraphQL entity names**, not REST ones —
`gamePlayerStat` has a hand-written pull because its scalar columns do not identify a row, and
`gameMedia` is reachable only through a relation, so both bypass `GQL_ENTITY_TO_RAW` and land in
`raw` under their entity spelling. The same string is also a dump stem (`parse_dump_stem`
parses `gamePlayerStat_2012`) and an upstream API contract key. Only the `stg` destination is in
scope, so the rename is a two-entry map in `stg_destination` — `_REST_STG_RENAMES` — and
deliberately not a general camelCase rule. The 10 remaining camelCase names in `stg` are explode
*children*, which need a change to how child names are derived: `#stg-camelcase-children`.

`raw` is untouched and still separates the transports by a `gql_` prefix. Only `stg` collapsed.

## Code surface

The plan measured ~50 `stg_gql.*` references on 2026-09-09 and warned the figure had already
grown once. On 2026-09-10 it was **95 qualified literals plus 124 bare `"stg_gql"` strings
across 20 files** — part of the growth from this session's own Bucket C merge work. All moved
in one commit, because `tests/test_catalog_resolution.py` fails on any literal that does not
resolve, so a partial rename is a red suite.

Three pieces carried the change rather than absorbing it:

- **`GQL_ENTITY_TO_STG`** gains the suffix, derived from `GQL_STG_COLLIDERS`. One place decides.
- **`stg_destination`** returns `"stg"` unconditionally.
- **`stg_id_renames`** used `schema` to decide whether to reverse-resolve a name to a GraphQL
  entity. With one schema, the *name* decides — which works only because the suffix keeps
  `stg.draft_picks` (REST, no entity, keeps its own id) distinct from `stg.draft_picks_gql`
  (resolves to `draftPicks`, takes that entity's rename).

`scripts/migrate_gql_stg_names.py` and its test are **deleted**. It performed the previous
migration (`stg.gql_<x>` → `stg_gql.<x>`); with `stg_gql` gone, re-running it would recreate the
schema. A one-shot migration whose destination no longer exists is a footgun, and git holds it.

`verify_warehouse_plan.py`'s structure checks **invert**, the same shape as the dead-column
check the day before: `stg_gql` must now be absent, and each collider must be present under
*both* the bare REST name and the suffixed GraphQL one. A missing suffix means a GraphQL table
overwrote its REST twin — the exact failure ADR-0002 existed to prevent — so that is the
assertion that bites hardest. `promote_to_motherduck.DEFAULT_SCHEMAS` drops `stg_gql` too;
promoting a schema that no longer exists is silent, and MotherDuck would have kept the last
mirror of it forever.

## Verification

Dry run on a scratch copy first: 40 moves, 0 failures, no destination already occupied. Then
live, then the check the test suite cannot make — `test_catalog_resolution.py` proves literals
*resolve*, not that a builder still joins correctly, and `duckdb_core.py` held 32 of the 95
references. **`build_core` was re-run and all 18 `core` tables rebuilt at byte-identical row
counts.** `verify_warehouse_plan.py`: `0 failed check(s)`, with `no stg_gql 0 tables`, all 34
entities present in `stg`, all three colliders paired, and `camelCase names 10` (children only).
`--selftest` passes, including new guards that the schema coming back and a collider losing a
side both fail. 896 fast tests pass; the slow suite is unchanged from its standing baseline.

**The load path was verified separately, because nothing above executes it.** `build_core`
only *reads* `stg`; `collapse_stg_gql.py` only moved tables. The collapse changed
`stg_destination`, `explode_payloads`, `_STG_SCHEMAS`, `_finish_stg_table`'s call and
`_backfill_gamelines`'s signature — none of which runs until the next refresh, and a rebuild
has silently dropped a table here before. So `explode_payloads` was re-run on a scratch copy
over a set covering each shape: a collider (`gql_calendar` → `calendar_gql`), a child-bearing
table (`gql_game` → `game` + `game__awayLineScores`), both camelCase roots, and
`gql_game_lines` so the backfill fires. All 14 watched tables rebuilt at identical counts, no
load errors, no `stg_gql` table recreated, the camelCase roots stayed snake-cased, and neither
the superseded tables nor the dead columns came back.

`_backfill_gamelines` took a second `gql_tables` set and used it for exactly one lookup
(`"lines_provider" in gql_tables`). Passing the same set twice post-collapse would have worked
while reading as if the two still meant different things, so the parameter is gone.

## What this does not support

- **It does not claim the suffix is a good name.** It is the cost of one staging schema, paid
  by three tables. `calendar_gql` says which API produced it, which is exactly what ADR-0002
  objected to, and the objection is conceded for those three.
- **It does not finish the camelCase work.** Ten explode children still carry camelCase names
  and `verify_warehouse_plan.py --camel` lists them; that needs a change to how
  `explode_payloads` derives child names, not a rename.
- **It does not touch `raw`**, which still carries `gql_` prefixes and the two camelCase dump
  names. `raw` is out of scope per plan §12, and `parse_dump_stem` depends on the spelling.
- **It does not prove the migration is safe to re-run against a half-collapsed warehouse it did
  not create.** It is resumable for its own output — a destination that exists while the source
  is gone is a completed move — but a destination that exists while the source *also* does is
  reported as an error rather than guessed at.
- **The mirror is not migrated.** `md:cfb` still holds a pre-collapse `stg_gql`, and dropping
  it from `DEFAULT_SCHEMAS` means the next promote will neither overwrite nor remove it — a
  stale schema answering queries silently, which is ADR-0002's original failure mode relocated.
  Tracked as `#motherduck-drop-stale-stg-gql`; the drop is the user's to run.
- **Row counts matching is not the same as data matching.** `CREATE TABLE AS SELECT *` preserves
  values and the copy is row-count-checked against its source before the drop, but nothing here
  re-validates column types or content beyond that.
