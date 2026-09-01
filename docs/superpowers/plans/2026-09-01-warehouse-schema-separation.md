# Warehouse GraphQL Schema Separation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the shipped-but-unapplied `gql_<snake_case>` prefix scheme with schema separation: GraphQL-sourced tables move to a `stg_gql` schema under bare `snake_case` names; REST-sourced tables stay in `stg` unchanged.

**Architecture:** Forward-fix, not revert — the prior build's `GQL_ENTITY_TO_STG` mapping stays as the single source of truth, its values change from `gql_<snake>` to bare `<snake>`. `raw` naming, which has always reused this same resolver, is decoupled into its own unchanged-value mapping (`GQL_ENTITY_TO_RAW`) so it keeps producing collision-free `gql_`-prefixed names — without that split, bare `stg_gql` values would make `raw.draft_picks`, `raw.predicted_points`, `raw.calendar` collide with REST raw dumps of the same name. Every `stg`-scanning function in `duckdb_load.py` becomes schema-aware: public orchestrators (`reorder_stg_columns`, `rename_stg_id_columns`, `promote_timestamp_columns`, `flatten_stg_nested`, `explode_stg_lists`) loop `("stg", "stg_gql")`; per-table helpers gain a required `schema` parameter (no default — every call site must state which schema, matching this codebase's existing "explicit and total" convention). The live warehouse is migrated with a rewritten script using `CREATE TABLE stg_gql.x AS SELECT * FROM stg.gql_x` + `DROP TABLE` (DuckDB has no `ALTER TABLE ... SET SCHEMA`), executed by the user, not by this plan.

**Tech Stack:** Python 3, DuckDB 1.5.2, pytest

**Spec:** `docs/superpowers/specs/2026-08-31-warehouse-naming-rationalization.md` (see "Addendum 2026-09-01: schema separation supersedes the `gql_` prefix" section)
**ADR:** `docs/adr/0002-graphql-stg-tables-in-separate-schema.md`

## Global Constraints

- `CFB_DATA_ROOT` is required; paths resolve through root `cfb_paths.py`. Local `data/cfb.duckdb` is source of truth; `md:cfb` is a manual mirror.
- Data is never committed. Only code, tests, and docs enter git.
- Do not edit `cfbd-python/` — vendored upstream.
- Run all commands from repository root.
- Default verification: `python -m pytest`. **Baseline measured 2026-09-01: 696 passed, 6 deselected** (the naming-rationalization plan's own "672" baseline is stale — treat all counts in this plan as deltas against 696, not absolutes, if that baseline has drifted).
- GraphQL field names (`GQL_DEFAULT_TABLES`, `GQL_RELATION_KEYS`, query text, `data/graphql/*.json` filenames) never change — upstream API contract. Only destination table/schema names change.
- `raw` gains no second schema. `raw` naming for GraphQL dumps stays `gql_`-prefixed, decoupled from the `stg_gql` bare-name scheme (see Task 1).
- Every per-table helper's `schema` parameter is **required**, not defaulted — this plan intentionally forces every call site open rather than defaulting to `"stg"`, so a missed call site is a `TypeError` at test time, not a silently wrong schema.
- **Task 7 (the migration script) mutates the live warehouse and must not be auto-run.** `data/cfb.duckdb` is 4.9 GB and unbacked. Tasks 1–6, 8–10 touch code, tests, and docs only.
- Do not run `git checkout <file>` while an unreviewed uncommitted build is in the tree — snapshot with `cp` first if you need to compare against HEAD.

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `cfb_system_maker/graphql_client.py` | `GQL_ENTITY_TO_STG` values become bare; add `GQL_ENTITY_TO_RAW` (unchanged `gql_`-prefixed values) and `GQL_RAW_TO_ENTITY` (its reverse). | 1 |
| `tests/test_graphql.py` | Assert bare `GQL_ENTITY_TO_STG`, prefixed `GQL_ENTITY_TO_RAW`, and that the reverse map is exact. | 1 |
| `cfb_system_maker/duckdb_load.py` | `stg_destination()` replaces `stg_dest_name`; `schema` param threaded through the id-rename, reorder, explode, and backfill paths; `_plan_loads` and `explode_payloads` updated. | 2–6 |
| `tests/test_duckdb_load.py` | Replace `stg_dest_name` tests with `stg_destination` tests; extend id-rename/explode/backfill tests for two schemas. | 2–6 |
| `scripts/migrate_gql_stg_names.py` | Rewritten: cross-schema `CREATE TABLE AS` + `DROP`, resumable, derives its table list from the mapping instead of a hand-written list. | 7 |
| `tests/test_migrate_gql_stg_names.py` | Migration correctness, idempotency, and resume-after-partial-failure against a synthetic two-schema DuckDB file. | 7 |
| `scripts/audit_canonical_sources.py` | GraphQL half of `PAIRS` reads from `stg_gql.<bare>` instead of `stg."gql_*"`. | 8 |
| `scripts/promote_to_motherduck.py` | `DEFAULT_SCHEMAS` gains `"stg_gql"`. | 9 |
| `cfb_system_maker/CLAUDE.md` | New `stg_gql` bullet; fix the stale "GraphQL dumps land in raw, not a separate graphql schema" line; document `--only` matching both schemas. | 10 |
| `CONTEXT.md` | Reword "canonical source" / add `stg_gql` if the glossary needs it. | 10 |
| `PLAN-REVIEW-LOG.md` | Append this build's record. | 10 |

---

### Task 1: Split GraphQL naming into a bare `stg_gql` map and an unchanged-value `raw` map

**Files:**
- Modify: `cfb_system_maker/graphql_client.py:40-53` (the `GQL_ENTITY_TO_STG` block)
- Test: `tests/test_graphql.py:1-32`

**Interfaces:**
- Consumes: `GQL_DEFAULT_TABLES`, `_snake` (existing, `graphql_client.py:26-38`)
- Produces: `GQL_ENTITY_TO_STG: dict[str, str]` (bare snake_case values — **breaking value change**, same keys), `GQL_ENTITY_TO_RAW: dict[str, str]` (unchanged `gql_`-prefixed values, same shape the old `GQL_ENTITY_TO_STG` had), `GQL_RAW_TO_ENTITY: dict[str, str]` (`{raw_name: entity}`, exact reverse of `GQL_ENTITY_TO_RAW`). Consumed by `duckdb_load.py` in Task 2.

- [ ] **Step 1: Write the failing test**

Replace `tests/test_graphql.py:1-32` with:

```python
import json
import re

from cfb_system_maker.graphql_client import (
    GQL_DEFAULT_TABLES,
    GQL_ENTITY_TO_RAW,
    GQL_ENTITY_TO_STG,
    GQL_RAW_TO_ENTITY,
    graphql_scrape,
    pull_game_player_stats,
)


def test_gql_entity_to_stg_is_total_and_injective():
    # Every GraphQL entity we pull must have an explicit destination — no fallback,
    # no clash detection. That totality is what removes the load-order dependence.
    assert set(GQL_ENTITY_TO_STG) == set(GQL_DEFAULT_TABLES)
    assert len(set(GQL_ENTITY_TO_STG.values())) == len(GQL_ENTITY_TO_STG)


def test_gql_destinations_are_bare_snake_case():
    # stg_gql destinations carry no gql_ prefix — the schema is the disambiguator now.
    for entity, dest in GQL_ENTITY_TO_STG.items():
        assert not dest.startswith("gql_"), f"{entity} -> {dest} still carries gql_ prefix"
        assert re.fullmatch(r"[a-z0-9_]+", dest), f"{entity} -> {dest} is not snake_case"


def test_gql_destinations_match_spec_examples():
    assert GQL_ENTITY_TO_STG["game"] == "game"
    assert GQL_ENTITY_TO_STG["gameLines"] == "game_lines"
    assert GQL_ENTITY_TO_STG["adjustedPlayerMetrics"] == "adjusted_player_metrics"
    assert GQL_ENTITY_TO_STG["playerStatCategory"] == "player_stat_category"
    assert GQL_ENTITY_TO_STG["calendar"] == "calendar"


def test_gql_entity_to_raw_is_total_injective_and_prefixed():
    # raw naming must stay decoupled from the stg_gql scheme: same shape the old
    # (prefixed) GQL_ENTITY_TO_STG had, so raw tables keep colliding with nothing.
    assert set(GQL_ENTITY_TO_RAW) == set(GQL_DEFAULT_TABLES)
    assert len(set(GQL_ENTITY_TO_RAW.values())) == len(GQL_ENTITY_TO_RAW)
    for entity, raw_name in GQL_ENTITY_TO_RAW.items():
        assert raw_name.startswith("gql_"), f"{entity} -> {raw_name} lacks gql_ prefix"


def test_gql_entity_to_raw_matches_shipped_prefix_scheme():
    # These are the exact values the (unapplied) gql_ prefix build shipped for `stg`.
    # raw keeps them verbatim even though stg_gql no longer does.
    assert GQL_ENTITY_TO_RAW["game"] == "gql_game"
    assert GQL_ENTITY_TO_RAW["gameLines"] == "gql_game_lines"
    assert GQL_ENTITY_TO_RAW["draftPicks"] == "gql_draft_picks"
    assert GQL_ENTITY_TO_RAW["calendar"] == "gql_calendar"


def test_gql_raw_to_entity_is_exact_inverse_of_gql_entity_to_raw():
    assert GQL_RAW_TO_ENTITY == {raw: entity for entity, raw in GQL_ENTITY_TO_RAW.items()}
    assert len(GQL_RAW_TO_ENTITY) == len(GQL_ENTITY_TO_RAW)


def test_gql_raw_names_never_collide_with_rest_raw_names():
    # The bug this whole scheme exists to prevent, one layer up: raw dumps for REST
    # endpoints that snake-case to the same bare name as a GraphQL entity.
    rest_raw_stems = {"games", "coaches", "conferences", "draft_picks", "recruits",
                       "recruiting_teams", "coach_seasons", "predicted_points", "talent",
                       "lines", "calendar", "draft_positions", "draft_teams"}
    assert not (set(GQL_ENTITY_TO_RAW.values()) & rest_raw_stems)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_graphql.py -v`
Expected: FAIL — `ImportError: cannot import name 'GQL_ENTITY_TO_RAW'`

- [ ] **Step 3: Write minimal implementation**

Replace `cfb_system_maker/graphql_client.py:40-53` (the comment + `GQL_ENTITY_TO_STG` block) with:

```python
# Destination table name for each GraphQL entity, per schema. Explicit and total on
# purpose: a clash resolver that picks a winner by load order previously caused
# `stg.calendar` (REST, 258 rows) and `stg.calendar_gql` (GraphQL, 424 rows) to swap
# provenance across a rebuild with nothing recording which was which.
#
# GQL_ENTITY_TO_STG: bare `stg_gql` destination. GraphQL lives in its own schema, so
# no prefix is needed to stay disjoint from REST's `stg` destinations.
#
# GQL_ENTITY_TO_RAW: `raw` destination, decoupled from the above on purpose. `raw`
# mixes REST and GraphQL dumps in one schema (no `raw_gql`), so it keeps the `gql_`
# prefix that keeps it collision-free with REST raw dumps of the same snake_case name
# (`draft_picks`, `predicted_points`, `calendar` all collide once GraphQL is bare).
#
# The keys are the upstream API contract and must not be renamed.
GQL_ENTITY_TO_STG: dict[str, str] = {entity: _snake(entity) for entity in GQL_DEFAULT_TABLES}
GQL_ENTITY_TO_RAW: dict[str, str] = {
    entity: "gql_" + _snake(entity) for entity in GQL_DEFAULT_TABLES
}
GQL_RAW_TO_ENTITY: dict[str, str] = {raw: entity for entity, raw in GQL_ENTITY_TO_RAW.items()}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_graphql.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add cfb_system_maker/graphql_client.py tests/test_graphql.py
git commit -m "feat(warehouse): split GraphQL raw naming from stg_gql naming"
```

---

### Task 2: `stg_destination()` resolves a raw table name to `(schema, name)`

`stg_dest_name` was called with two different meanings of its argument — the *entity* name
(from `_plan_loads`, to compute the raw table name) and the *raw table* name (from
`explode_payloads`, to compute the `stg` destination). Under the prefix scheme those two calls
coincidentally agreed because the raw name **was** `stg_dest_name(entity)`. Under schema
separation they diverge: the raw name comes from `GQL_ENTITY_TO_RAW` (Task 1), so
`explode_payloads` needs a resolver keyed by *raw table name* that returns which schema and
bare name it belongs in.

**Files:**
- Modify: `cfb_system_maker/duckdb_load.py:1089-1097` (`stg_dest_name` def), `:19` (import), `:504` (`explode_payloads`), `:1499` (`_plan_loads`)
- Test: `tests/test_duckdb_load.py:1-39`

**Interfaces:**
- Consumes: `GQL_ENTITY_TO_STG`, `GQL_ENTITY_TO_RAW`, `GQL_RAW_TO_ENTITY` (Task 1)
- Produces: `stg_destination(raw_name: str) -> tuple[str, str]` — `(schema, dest_name)` for a raw table name (REST endpoint stem or GraphQL `gql_`-prefixed raw name). Consumed by `explode_payloads` (Task 4).

- [ ] **Step 1: Write the failing test**

Replace `tests/test_duckdb_load.py:1-39` with:

```python
import json

from cfb_system_maker.cli import main
from cfb_system_maker.duckdb_load import (
    backfill_gamelines_from_actionnetwork,
    build_duckdb,
    explode_payloads,
    flatten_stg_nested,
    parse_dump_stem,
    rename_stg_id_columns,
    reorder_stg_columns,
    stg_column_order,
    stg_destination,
    stg_id_renames,
)


def test_stg_destination_resolves_graphql_raw_names_to_stg_gql():
    assert stg_destination("gql_calendar") == ("stg_gql", "calendar")
    assert stg_destination("gql_game_lines") == ("stg_gql", "game_lines")
    assert stg_destination("gql_draft_picks") == ("stg_gql", "draft_picks")


def test_stg_destination_passes_rest_names_through_to_stg():
    assert stg_destination("games") == ("stg", "games")
    assert stg_destination("draft_picks") == ("stg", "draft_picks")
    assert stg_destination("advanced_box_score") == ("stg", "advanced_box_score")


def test_gql_destinations_never_collide_with_rest_destinations_in_the_same_schema():
    from cfb_system_maker.graphql_client import GQL_ENTITY_TO_RAW

    rest_raw_names = {"games", "coaches", "conferences", "draft_picks", "recruits",
                       "recruiting_teams", "coach_seasons", "predicted_points", "talent",
                       "lines", "calendar", "draft_positions", "draft_teams"}
    assert not (set(GQL_ENTITY_TO_RAW.values()) & rest_raw_names)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_duckdb_load.py -k stg_destination -v`
Expected: FAIL — `ImportError: cannot import name 'stg_destination'`

- [ ] **Step 3: Write minimal implementation**

In `cfb_system_maker/duckdb_load.py:19`, change the import:

```python
from cfb_system_maker.graphql_client import GQL_ENTITY_TO_RAW, GQL_ENTITY_TO_STG, GQL_RAW_TO_ENTITY
```

Replace `stg_dest_name` (`duckdb_load.py:1089-1097`) with:

```python
def stg_destination(name: str) -> tuple[str, str]:
    """``(schema, name)`` in `stg`/`stg_gql` for a raw table name.

    Pure function of the raw table name alone. A GraphQL raw table (named through
    `GQL_ENTITY_TO_RAW`, e.g. `gql_game`) resolves through `GQL_RAW_TO_ENTITY` back to
    its entity, then through `GQL_ENTITY_TO_STG` to its bare `stg_gql` destination.
    Anything else is a REST raw table name and passes through unchanged into `stg`.
    """
    entity = GQL_RAW_TO_ENTITY.get(name)
    if entity is None:
        return "stg", name
    return "stg_gql", GQL_ENTITY_TO_STG[entity]
```

In `_plan_loads` (`duckdb_load.py:1499`), change the graphql-raw-naming line:

```python
            dest = GQL_ENTITY_TO_RAW.get(name, name)
```

(was `dest = stg_dest_name(name)` — `name` here is the entity, e.g. `"gameLines"`; this now
names the raw table exactly as the shipped prefix build did, unaffected by the `stg_gql` change.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_duckdb_load.py -k "stg_destination or gql_destinations_never_collide" -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add cfb_system_maker/duckdb_load.py tests/test_duckdb_load.py
git commit -m "feat(warehouse): resolve stg_gql destinations from raw table names"
```

Note: `explode_payloads` itself still calls the old `stg_dest_name(name)` at this point (line
504) — that call site is fixed in Task 4, alongside `_explode_table`'s schema parameter, since
both changes touch the same lines and splitting them would leave `explode_payloads` broken
between commits.

---

### Task 3: `schema` parameter on the id-rename / column-order path

`stg_id_renames`'s reverse GraphQL-entity lookup searches `GQL_ENTITY_TO_STG.values()` for a
match against the table name it's given. Under bare `stg_gql` values, a bare name can belong to
either schema (`draft_picks` exists in both once the migration runs). The function has no way
to know which. `_BARE_ID_RENAME` happens to have no entry for any of the three exactly-colliding
names today, so there's no observable wrong answer yet — this task closes the class before a
future entry silently produces one.

**Files:**
- Modify: `cfb_system_maker/duckdb_load.py:169-181` (`stg_id_renames`), `:184-194` (`stg_column_order`), `:296-322` (`_reorder_stg_table`), `:383-394` (`_rename_stg_table_ids`)
- Test: `tests/test_duckdb_load.py` (the `test_stg_id_renames_resolves_gql_destinations_back_to_their_entity` block, currently ~line 583)

**Interfaces:**
- Consumes: `GQL_ENTITY_TO_STG` (Task 1)
- Produces: `stg_id_renames(table: str, *, schema: str) -> dict[str, str]`, `stg_column_order(columns, *, schema: str, table: str | None = None) -> list[str]`, `_reorder_stg_table(con, schema: str, name: str) -> TableLoad`, `_rename_stg_table_ids(con, schema: str, name: str) -> int` — all now schema-aware. Consumed by Task 5.

- [ ] **Step 1: Write the failing test**

Replace the existing `test_stg_id_renames_resolves_gql_destinations_back_to_their_entity` (search
`tests/test_duckdb_load.py` for that name) with:

```python
def test_stg_id_renames_resolves_gql_destinations_back_to_their_entity():
    """`_BARE_ID_RENAME` is keyed by GraphQL entity name, not by the stg_gql destination.
    Without the reverse lookup, a bare `game` in stg_gql misses the table and keeps a
    bare `id` column instead of `gameId` — silently, since nothing else asserts on it."""
    assert stg_id_renames("game", schema="stg_gql") == {"id": "gameId"}
    assert stg_id_renames("coach", schema="stg_gql") == {"id": "coachId"}
    assert stg_id_renames("lines_provider", schema="stg_gql") == {"id": "linesProviderId"}
    assert stg_id_renames("historical_team", schema="stg_gql") == {"id": "teamId"}


def test_stg_id_renames_does_not_apply_graphql_renames_to_rest_tables_in_stg():
    # A bare name that exists in both schemas (draft_picks, predicted_points, calendar)
    # must not pick up a GraphQL-entity id rename when it's actually the REST table.
    assert stg_id_renames("draft_picks", schema="stg") == {}
    assert stg_id_renames("draft_picks", schema="stg_gql") == {}
    assert stg_id_renames("games", schema="stg") == {"id": "gameId"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_duckdb_load.py -k stg_id_renames -v`
Expected: FAIL — `TypeError: stg_id_renames() got an unexpected keyword argument 'schema'`

- [ ] **Step 3: Write minimal implementation**

Replace `stg_id_renames` (`duckdb_load.py:169-181`):

```python
def stg_id_renames(table: str, *, schema: str) -> dict[str, str]:
    """Map current column names → names that match what the id actually is.

    `schema` picks which id-rename spelling applies: only `stg_gql` tables reverse-
    resolve through `GQL_ENTITY_TO_STG` to a GraphQL entity name. A `stg` (REST) table
    that happens to share a bare name with a GraphQL entity (`draft_picks`,
    `predicted_points`, `calendar`) must not pick up the GraphQL entity's id rename.
    """
    base = table[:-4] if table.endswith("_ngt") else table
    source_name = base
    if schema == "stg_gql":
        source_name = next(
            (entity for entity, destination in GQL_ENTITY_TO_STG.items() if destination == base),
            base,
        )
    out: dict[str, str] = {}
    dest = _BARE_ID_RENAME.get(source_name)
    if dest:
        out["id"] = dest
    out.update(_EXTRA_ID_RENAMES.get(base, {}))
    return out
```

Update `stg_column_order` (`duckdb_load.py:184-194`) to thread `schema` through:

```python
def stg_column_order(
    columns: list[tuple[str, str]],
    *,
    schema: str,
    table: str | None = None,
) -> list[str]:
    """Return column names in browse order. ``columns`` is ``(name, type)``."""
    pk = stg_id_renames(table, schema=schema).get("id") if table else None
    ranked: list[tuple[tuple[int, int, int, int], str]] = []
    for orig, (name, dtype) in enumerate(columns):
        ranked.append((_stg_nav_key(name, dtype, orig, pk), name))
    ranked.sort()
    return [name for _, name in ranked]
```

Update `_reorder_stg_table` (`duckdb_load.py:296-322`) — replace every literal `"stg"` with the
new `schema` parameter:

```python
def _reorder_stg_table(con: duckdb.DuckDBPyConnection, schema: str, name: str) -> TableLoad:
    table = _qualify(schema, name)
    described = [
        (row[0], str(row[1])) for row in con.execute(f"DESCRIBE {table}").fetchall()
    ]
    ordered = stg_column_order(described, schema=schema, table=name)
    current = [col for col, _dtype in described]
    if ordered == current:
        rows = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return TableLoad(schema, name, 0, int(rows))
    tmp_name = name + "__reordering"
    tmp = _qualify(schema, tmp_name)
    select_list = ", ".join(_ident(col) for col in ordered)
    try:
        con.execute(f"DROP TABLE IF EXISTS {tmp}")
        con.execute(f"CREATE TABLE {tmp} AS SELECT {select_list} FROM {table}")
        con.execute(f"DROP TABLE {table}")
        con.execute(f"ALTER TABLE {tmp} RENAME TO {_ident(name)}")
        rows = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return TableLoad(schema, name, 1, int(rows))
    except Exception as exc:
        try:
            con.execute(f"DROP TABLE IF EXISTS {tmp}")
        except Exception:
            pass
        detail = str(exc).split("\n", 1)[0]
        return TableLoad(schema, name, 0, 0, error=f"{type(exc).__name__}: {detail}")
```

(`ALTER TABLE {tmp} RENAME TO {_ident(name)}` stays unqualified — `RENAME TO` keeps a table in
its current schema, it does not need `_qualify`.)

Update `_rename_stg_table_ids` (`duckdb_load.py:383-394`):

```python
def _rename_stg_table_ids(con: duckdb.DuckDBPyConnection, schema: str, name: str) -> int:
    table = _qualify(schema, name)
    present = {row[0] for row in con.execute(f"DESCRIBE {table}").fetchall()}
    changed = 0
    for old, new in stg_id_renames(name, schema=schema).items():
        if old not in present or new in present:
            continue
        con.execute(f"ALTER TABLE {table} RENAME COLUMN {_ident(old)} TO {_ident(new)}")
        present.discard(old)
        present.add(new)
        changed += 1
    return changed
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_duckdb_load.py -k "stg_id_renames" -v`
Expected: PASS. Note this leaves `_reorder_stg_table`/`_rename_stg_table_ids`'s remaining
call sites broken (Task 4/5 fix them) — run only the `-k stg_id_renames` subset here, not the
full file.

- [ ] **Step 5: Commit**

```bash
git add cfb_system_maker/duckdb_load.py tests/test_duckdb_load.py
git commit -m "feat(warehouse): require explicit schema for stg id-rename resolution"
```

---

### Task 4: Schema-aware table creation — `explode_payloads`, `_explode_table`, `_finish_stg_table`

**Files:**
- Modify: `cfb_system_maker/duckdb_load.py:470-509` (`explode_payloads`), `:1309-1317` (`_finish_stg_table`), `:1320-1328` (`_explode_failed`), `:1331-1377` (`_explode_table`), `:1135-1198` (`_explode_actionnetwork_history`), `:1201-1306` (`_explode_actionnetwork_scoreboard`)
- Test: `tests/test_duckdb_load.py:214-242` (`test_explode_payloads_writes_stg_columns`) — note `test_build_duckdb_names_graphql_calendar_with_explicit_prefix` (`:142-173`) asserts on `raw.gql_calendar`, which does **not** change (Task 1 keeps `raw` naming `gql_`-prefixed), so that test is untouched by this task.

**Interfaces:**
- Consumes: `stg_destination` (Task 2), `_reorder_stg_table`/`_rename_stg_table_ids` (Task 3, now `(con, schema, name)`)
- Produces: `_explode_table(con, schema, name, dest_schema, dest) -> TableLoad`, `_finish_stg_table(con, dest_schema, dest, target) -> TableLoad` — both schema-aware. Consumed by Task 5's `explode_stg_lists` path (via `_flatten_struct_columns`, already schema-parameterized).

- [ ] **Step 1: Write the failing test**

Replace `test_explode_payloads_writes_stg_columns` (`tests/test_duckdb_load.py:214-242`) — only
the GraphQL-destination lines change (`by_name["gql_game"]` → a schema-keyed lookup,
`stg.gql_game` → `stg_gql.game`); the REST assertions are untouched:

```python
def test_explode_payloads_writes_stg_columns(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "games_2023.json").write_text(
        json.dumps([{"id": 1, "homeTeam": "A"}, {"id": 2, "homeTeam": "B"}]),
        encoding="utf-8",
    )
    gql = tmp_path / "graphql"
    gql.mkdir()
    (gql / "game.json").write_text(
        json.dumps([{"id": 9, "season": 2023}]), encoding="utf-8"
    )

    db_path, _ = build_duckdb(tmp_path, include_actionnetwork=False)
    reports = explode_payloads(db_path)
    by_key = {(r.schema, r.name): r for r in reports if r.error is None}
    assert by_key[("stg", "games")].rows == 2
    assert by_key[("stg_gql", "game")].rows == 1

    import duckdb

    con = duckdb.connect(str(db_path), read_only=True)
    homes = con.execute("SELECT homeTeam FROM stg.games ORDER BY gameId").fetchall()
    assert homes == [("A",), ("B",)]
    assert con.execute("SELECT COUNT(*) FROM raw.games").fetchone()[0] == 2
    assert con.execute("SELECT gameId FROM stg_gql.game").fetchone()[0] == 9
    cols = {row[0] for row in con.execute("DESCRIBE stg.games").fetchall()}
    assert "_season" not in cols and "_week" not in cols
    assert "_source_file" in cols
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_duckdb_load.py -k explode_payloads_writes_stg_columns -v`
Expected: FAIL — GraphQL destination still lands as `stg.gql_game` under the old
`stg_dest_name` call, so `by_key[("stg_gql", "game")]` raises `KeyError`.

- [ ] **Step 3: Write minimal implementation**

In `explode_payloads` (`duckdb_load.py:470-509`), add the `stg_gql` schema and switch the
destination resolver:

```python
    con.execute("CREATE SCHEMA IF NOT EXISTS stg")
    con.execute("CREATE SCHEMA IF NOT EXISTS stg_gql")
    sources = con.execute(
        """
        SELECT table_schema, table_name
        FROM information_schema.columns
        WHERE column_name = 'payload'
          AND table_schema IN ('raw', 'graphql')
        GROUP BY 1, 2
        ORDER BY table_schema DESC, table_name
        """
    ).fetchall()
    # No `taken` set and no REST-first sort: destinations are disjoint by
    # construction now, so load order cannot change which table wins a name.
    for schema, name in sources:
        if only is not None and name not in only:
            continue
        dest_schema, dest = stg_destination(name)
        report = _explode_table(con, schema, name, dest_schema, dest)
        reports.append(report)
        if progress is not None:
            progress(report)
        con.execute("CHECKPOINT")
```

Update `_explode_table` (`duckdb_load.py:1331-1377`) to take and use `dest_schema`:

```python
def _explode_table(
    con: duckdb.DuckDBPyConnection, schema: str, name: str, dest_schema: str, dest: str
) -> TableLoad:
    source = _qualify(schema, name)
    target = _qualify(dest_schema, dest)
    if name == "actionnetwork_history":
        return _explode_actionnetwork_history(con, source, target, dest)
    if name == "actionnetwork_scoreboard":
        return _explode_actionnetwork_scoreboard(con, source, target, dest)
    try:
        structure = _payload_structure(con, source)
        if structure is None:
            return TableLoad(dest_schema, dest, 0, 0, error="empty payload")
        spine = _spine_select(con, source, structure)
        con.execute(f"DROP TABLE IF EXISTS {target}")
        con.execute(
            f"""
            CREATE TABLE {target} AS
            SELECT
              {spine},
              unnest(
                json_transform(payload, ?),
                recursive := true,
                keep_parent_names := true
              )
            FROM {source}
            """,
            [structure],
        )
        _rename_dotted_columns(con, target)
        leftover = _flatten_struct_columns(con, dest_schema, dest)
        if leftover is not None and leftover.error:
            return leftover
        _rename_stg_table_ids(con, dest_schema, dest)
        ordered = _reorder_stg_table(con, dest_schema, dest)
        if ordered.error:
            return ordered
        rows = con.execute(f"SELECT COUNT(*) FROM {target}").fetchone()[0]
        return TableLoad(dest_schema, dest, 1, int(rows))
    except Exception as exc:
        try:
            con.execute(f"DROP TABLE IF EXISTS {target}")
        except Exception:
            pass
        detail = str(exc).split("\n", 1)[0]
        return TableLoad(dest_schema, dest, 0, 0, error=f"{type(exc).__name__}: {detail}")
```

`_explode_actionnetwork_history`/`_explode_actionnetwork_scoreboard` (`:1135-1306`) are always
REST/Action Network-fed — no GraphQL twin exists for either. They keep calling
`_finish_stg_table(con, dest, target)` unchanged in shape, but `_finish_stg_table` itself now
needs a schema. Update both call sites (`duckdb_load.py:1196`, `:1304`) to:

```python
        return _finish_stg_table(con, "stg", dest, target)
```

Update `_finish_stg_table` (`duckdb_load.py:1309-1317`):

```python
def _finish_stg_table(
    con: duckdb.DuckDBPyConnection, schema: str, dest: str, target: str
) -> TableLoad:
    _rename_stg_table_ids(con, schema, dest)
    ordered = _reorder_stg_table(con, schema, dest)
    if ordered.error:
        return ordered
    rows = con.execute(f"SELECT COUNT(*) FROM {target}").fetchone()[0]
    return TableLoad(schema, dest, 1, int(rows))
```

Update `_explode_failed` (`duckdb_load.py:1320-1328`) to take the schema it should report:

```python
def _explode_failed(
    con: duckdb.DuckDBPyConnection, schema: str, target: str, dest: str, exc: Exception
) -> TableLoad:
    try:
        con.execute(f"DROP TABLE IF EXISTS {target}")
    except Exception:
        pass
    detail = str(exc).split("\n", 1)[0]
    return TableLoad(schema, dest, 0, 0, error=f"{type(exc).__name__}: {detail}")
```

`_explode_nested_column` (Task 5) is the only caller of `_explode_failed`; its call site is
updated there since it already needs a `schema` parameter for the same reason.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_duckdb_load.py -k "explode_payloads or explode_table" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cfb_system_maker/duckdb_load.py tests/test_duckdb_load.py
git commit -m "feat(warehouse): route GraphQL payload explode into stg_gql"
```

---

### Task 5: Schema-aware post-processing — reorder, id-rename, timestamp, flatten, list-explode orchestrators

Every top-level orchestrator that currently scans `WHERE schema_name = 'stg'` needs to cover
`stg_gql` too, or every GraphQL-sourced table silently skips reordering, id-renaming, timestamp
promotion, and list-explosion once it moves out of `stg`.

**Files:**
- Modify: `cfb_system_maker/duckdb_load.py:251-293` (`reorder_stg_columns`), `:325-380` (`rename_stg_id_columns`), `:761-821` (`promote_timestamp_columns`), `:824-859` (`flatten_stg_nested`), `:866-918` (`explode_stg_lists`), `:930-993` (`_explode_nested_columns`/`_explode_nested_column`)
- Test: `tests/test_duckdb_load.py` (extend existing tests for these functions with a `stg_gql` counterpart table in the fixture)

**Interfaces:**
- Consumes: `_reorder_stg_table`, `_rename_stg_table_ids` (Task 3), `_flatten_struct_columns` (already schema-parameterized), `_explode_failed` (Task 4)
- Produces: no new public names — the five orchestrators keep their existing signatures and now report `TableLoad`s from both schemas in one call.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_duckdb_load.py` (adjacent to the existing `explode_stg_lists` tests):

```python
def test_explode_stg_lists_explodes_both_stg_and_stg_gql():
    import duckdb

    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA stg")
    con.execute("CREATE SCHEMA stg_gql")
    con.execute("CREATE TABLE stg.games AS SELECT 1 AS gameId, [1, 2]::INTEGER[] AS scores")
    con.execute("CREATE TABLE stg_gql.game AS SELECT 1 AS gameId, [3, 4]::INTEGER[] AS scores")
    reports = explode_stg_lists(con)
    by_key = {(r.schema, r.name): r for r in reports}
    assert by_key[("stg", "games__scores")].rows == 2
    assert by_key[("stg_gql", "game__scores")].rows == 2


def test_reorder_stg_columns_reorders_both_schemas():
    import duckdb

    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA stg")
    con.execute("CREATE SCHEMA stg_gql")
    con.execute("CREATE TABLE stg.games AS SELECT 'x' AS extra, 1 AS gameId")
    con.execute("CREATE TABLE stg_gql.game AS SELECT 'x' AS extra, 1 AS gameId")
    reorder_stg_columns(con)
    stg_cols = [r[0] for r in con.execute("DESCRIBE stg.games").fetchall()]
    gql_cols = [r[0] for r in con.execute("DESCRIBE stg_gql.game").fetchall()]
    assert stg_cols[0] == "gameId"
    assert gql_cols[0] == "gameId"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_duckdb_load.py -k "explode_stg_lists_explodes_both or reorder_stg_columns_reorders_both" -v`
Expected: FAIL — `stg_gql` tables untouched (queries filter `schema_name = 'stg'` only).

- [ ] **Step 3: Write minimal implementation**

Add the schema list once, near `_CHILD_SEP` (`duckdb_load.py:863`):

```python
_STG_SCHEMAS = ("stg", "stg_gql")
```

`reorder_stg_columns` (`duckdb_load.py:251-293`) — wrap the existing body in a loop over
`_STG_SCHEMAS`, replacing every `'stg'` literal with the loop variable:

```python
def reorder_stg_columns(
    db: str | Path | duckdb.DuckDBPyConnection,
    *,
    progress: Callable[[TableLoad], None] | None = None,
) -> list[TableLoad]:
    owns_connection = not isinstance(db, duckdb.DuckDBPyConnection)
    con = duckdb.connect(str(db)) if owns_connection else db
    reports: list[TableLoad] = []
    try:
        for schema in _STG_SCHEMAS:
            views = con.execute(
                f"""
                SELECT view_name, sql
                FROM duckdb_views()
                WHERE schema_name = '{schema}'
                ORDER BY view_name
                """
            ).fetchall()
            for view_name, _sql in views:
                con.execute(f"DROP VIEW IF EXISTS {_qualify(schema, view_name)}")
            tables = [
                row[0]
                for row in con.execute(
                    f"""
                    SELECT table_name
                    FROM duckdb_tables()
                    WHERE schema_name = '{schema}'
                    ORDER BY table_name
                    """
                ).fetchall()
            ]
            for name in tables:
                report = _reorder_stg_table(con, schema, name)
                reports.append(report)
                if progress is not None:
                    progress(report)
                con.execute("CHECKPOINT")
            for view_name, sql in views:
                con.execute(sql)
    finally:
        if owns_connection:
            con.close()
    return reports
```

`rename_stg_id_columns` (`duckdb_load.py:325-380`) — same shape:

```python
def rename_stg_id_columns(
    db: str | Path | duckdb.DuckDBPyConnection,
    *,
    progress: Callable[[TableLoad], None] | None = None,
) -> list[TableLoad]:
    """Rename bare ``id`` (and ``homeId``/``awayId``) to names that match the value."""
    owns_connection = not isinstance(db, duckdb.DuckDBPyConnection)
    con = duckdb.connect(str(db)) if owns_connection else db
    reports: list[TableLoad] = []
    try:
        for schema in _STG_SCHEMAS:
            views = con.execute(
                f"""
                SELECT view_name, sql
                FROM duckdb_views()
                WHERE schema_name = '{schema}'
                ORDER BY view_name
                """
            ).fetchall()
            for view_name, _sql in views:
                con.execute(f"DROP VIEW IF EXISTS {_qualify(schema, view_name)}")
            tables = [
                row[0]
                for row in con.execute(
                    f"""
                    SELECT table_name
                    FROM duckdb_tables()
                    WHERE schema_name = '{schema}'
                    ORDER BY table_name
                    """
                ).fetchall()
            ]
            for name in tables:
                renamed = _rename_stg_table_ids(con, schema, name)
                if renamed:
                    ordered = _reorder_stg_table(con, schema, name)
                    if ordered.error:
                        reports.append(ordered)
                    else:
                        reports.append(TableLoad(schema, name, renamed, ordered.rows))
                else:
                    rows = con.execute(
                        f"SELECT COUNT(*) FROM {_qualify(schema, name)}"
                    ).fetchone()[0]
                    reports.append(TableLoad(schema, name, 0, int(rows)))
                if progress is not None:
                    progress(reports[-1])
                con.execute("CHECKPOINT")
            for view_name, sql in views:
                try:
                    con.execute(sql)
                except Exception:
                    pass
    finally:
        if owns_connection:
            con.close()
    return reports
```

`promote_timestamp_columns` (`duckdb_load.py:761-821`) — the `WHERE table_schema = 'stg'`
candidate query becomes `WHERE table_schema IN ('stg', 'stg_gql')`, and every `TableLoad(...)`
inside the loop reports the row's actual `table_schema` instead of a literal `"stg"`:

```python
        candidates = con.execute(
            """
            SELECT table_schema, table_name, column_name
            FROM information_schema.columns
            WHERE table_schema IN ('stg', 'stg_gql')
              AND data_type = 'VARCHAR'
              AND (lower(column_name) LIKE '%date%' OR lower(column_name) LIKE '%time%')
            ORDER BY table_schema, table_name, column_name
            """
        ).fetchall()
        for schema, table, column in candidates:
            target = _qualify(schema, table)
            expr = _timestamp_expr(column)
            label = f"{table}.{column}"
            try:
                parsed, unparsed = con.execute(
                    f"""
                    SELECT
                      count(*) FILTER (WHERE {_ident(column)} IS NOT NULL),
                      count(*) FILTER (WHERE {_ident(column)} IS NOT NULL AND {expr} IS NULL)
                    FROM {target}
                    """
                ).fetchone()
                if not parsed or unparsed:
                    continue
                con.execute(
                    f"ALTER TABLE {target} ALTER COLUMN {_ident(column)} "
                    f"TYPE TIMESTAMPTZ USING {expr}"
                )
            except Exception as exc:
                detail = str(exc).splitlines()[0] if str(exc) else ""
                report = TableLoad(
                    schema, label, 0, 0, error=f"{type(exc).__name__}: {detail}"
                )
            else:
                report = TableLoad(schema, label, 1, int(parsed))
            reports.append(report)
            if progress is not None:
                progress(report)
```

`flatten_stg_nested` (`duckdb_load.py:824-859`) — same `IN (...)` widening, schema comes from
the query row instead of a literal:

```python
        tables = con.execute(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema IN ('stg', 'stg_gql')
            ORDER BY table_schema, table_name
            """
        ).fetchall()
        for schema, name in tables:
            report = _flatten_struct_columns(con, schema, name)
            if report is None:
                continue
            reports.append(report)
            if progress is not None:
                progress(report)
            con.execute("CHECKPOINT")
```

`explode_stg_lists` (`duckdb_load.py:866-918`) — loop `_STG_SCHEMAS`, and keep the `__backfill`
guard scoped per schema (it currently protects only `stg`'s `gql_game_lines__backfill`; under
this scheme it protects `stg_gql`'s `game_lines__backfill` instead — either way, the guard must
run inside the per-schema loop, not just once):

```python
def explode_stg_lists(
    db: str | Path | duckdb.DuckDBPyConnection,
    *,
    only: set[str] | None = None,
    progress: Callable[[TableLoad], None] | None = None,
) -> list[TableLoad]:
    owns_connection = not isinstance(db, duckdb.DuckDBPyConnection)
    con = duckdb.connect(str(db)) if owns_connection else db
    reports: list[TableLoad] = []
    try:
        con.execute("SET preserve_insertion_order = false")
        con.execute("SET threads = 1")
        for schema in _STG_SCHEMAS:
            for (stale,) in con.execute(
                f"""
                SELECT table_name FROM duckdb_tables()
                WHERE schema_name = '{schema}'
                  AND contains(table_name, '{_CHILD_SEP}')
                  AND NOT ends_with(table_name, '{_CHILD_SEP}backfill')
                ORDER BY table_name
                """
            ).fetchall():
                if only is not None and stale.split(_CHILD_SEP, 1)[0] not in only:
                    continue
                con.execute(f"DROP TABLE IF EXISTS {_qualify(schema, stale)}")
            roots = [
                row[0]
                for row in con.execute(
                    f"SELECT table_name FROM duckdb_tables()"
                    f" WHERE schema_name = '{schema}' ORDER BY table_name"
                ).fetchall()
            ]
            for name in roots:
                if only is not None and name not in only:
                    continue
                _explode_nested_columns(con, schema, name, 0, reports, progress)
    finally:
        if owns_connection:
            con.close()
    return reports
```

`_explode_nested_columns`/`_explode_nested_column` (`duckdb_load.py:930-993`) — add `schema`:

```python
def _explode_nested_columns(
    con: duckdb.DuckDBPyConnection,
    schema: str,
    table: str,
    depth: int,
    reports: list[TableLoad],
    progress: Callable[[TableLoad], None] | None,
) -> None:
    if depth >= _EXPLODE_MAX_DEPTH:
        return
    nested = []
    for row in con.execute(f"DESCRIBE {_qualify(schema, table)}").fetchall():
        kind = _is_nested_type(row[1])
        if kind is not None:
            nested.append((row[0], kind))
    siblings = [col for col, _ in nested]
    for col, kind in nested:
        dest = f"{table}{_CHILD_SEP}{col}"
        report = _explode_nested_column(con, schema, table, col, kind, dest, siblings)
        reports.append(report)
        if progress is not None:
            progress(report)
        con.execute("CHECKPOINT")
        if report.error is None and report.rows:
            _explode_nested_columns(con, schema, dest, depth + 1, reports, progress)


def _explode_nested_column(
    con: duckdb.DuckDBPyConnection,
    schema: str,
    parent: str,
    col: str,
    kind: str,
    dest: str,
    siblings: list[str],
) -> TableLoad:
    source = _qualify(schema, parent)
    target = _qualify(schema, dest)
    exclude = ", ".join(_ident(name) for name in siblings)
    col_id = _ident(col)
    idx_id = _ident(f"{col}_idx")
    try:
        con.execute(f"DROP TABLE IF EXISTS {target}")
        if kind == "json":
            if not _explode_json_column(con, source, target, col, exclude):
                return TableLoad(
                    schema, dest, 0, 0, error="scalar JSON; nothing to explode"
                )
        else:
            con.execute(
                f"""
                CREATE TABLE {target} AS
                SELECT * EXCLUDE ({exclude}),
                  unnest(range(1, len({col_id}) + 1)) AS {idx_id},
                  unnest({col_id}) AS {col_id}
                FROM {source}
                WHERE {col_id} IS NOT NULL AND len({col_id}) > 0
                """
            )
        leftover = _flatten_struct_columns(con, schema, dest)
        if leftover is not None and leftover.error:
            return leftover
        rows = con.execute(f"SELECT COUNT(*) FROM {target}").fetchone()[0]
        return TableLoad(schema, dest, 1, int(rows))
    except Exception as exc:
        return _explode_failed(con, schema, target, dest, exc)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_duckdb_load.py -v`
Expected: PASS — full file, since this task's changes are what the remaining call sites from
Tasks 3–4 depend on.

- [ ] **Step 5: Commit**

```bash
git add cfb_system_maker/duckdb_load.py tests/test_duckdb_load.py
git commit -m "feat(warehouse): make stg post-processing cover stg_gql"
```

---

### Task 6: `backfill_gamelines_from_actionnetwork` reads/writes `stg_gql`

This function is currently broken on `master` regardless of which scheme ships — it looks for
`stg.gql_game_lines`, which does not exist under either the prefix scheme (unapplied) or bare
`stg_gql` (not yet built). It must point at the real destination before the next warehouse
build. `games` and `actionnetwork_scoreboard`/`actionnetwork_history` are REST/Action
Network-sourced and stay in `stg`; only the two GraphQL tables (`gql_game_lines` →
`stg_gql.game_lines`, `gql_lines_provider` → `stg_gql.lines_provider`) move.

**Files:**
- Modify: `cfb_system_maker/duckdb_load.py:547-577` (`backfill_gamelines_from_actionnetwork`), `:579-745` (`_backfill_gamelines`)
- Test: `tests/test_duckdb_load.py` (the backfill test block, originally ~lines 805-929 per the prior session's grep)

**Interfaces:**
- Consumes: `_finish_stg_table` (Task 4, now `(con, schema, dest, target)`)
- Produces: no signature change — same public function, corrected table references.

- [ ] **Step 1: Write the failing test**

Find the existing backfill tests (search `tests/test_duckdb_load.py` for
`backfill_gamelines_from_actionnetwork`) and update every fixture/assertion that references
`stg.gql_game_lines` or `stg.gql_lines_provider` to `stg_gql.game_lines` /
`stg_gql.lines_provider`. Representative example (adapt each existing test the same way):

```python
def test_backfill_gamelines_merges_actionnetwork_into_stg_gql():
    import duckdb

    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA stg")
    con.execute("CREATE SCHEMA stg_gql")
    con.execute("CREATE TABLE stg.games AS SELECT 1 AS gameId, 'A' AS homeTeam, 'B' AS awayTeam, 2024 AS season, 1 AS week")
    con.execute(
        "CREATE TABLE stg_gql.game_lines AS "
        "SELECT 1::BIGINT AS gameId, 1::BIGINT AS linesProviderId, -3.5::DOUBLE AS spread, "
        "NULL::DOUBLE AS spreadOpen, NULL::DOUBLE AS overUnder, NULL::DOUBLE AS overUnderOpen, "
        "NULL::BIGINT AS moneylineHome, NULL::BIGINT AS moneylineAway, 'f.json' AS _source_file"
    )
    con.execute(
        "CREATE TABLE stg.actionnetwork_scoreboard AS "
        "SELECT 100::BIGINT AS event_id, 2024 AS season, 1 AS week, "
        "'[]'::JSON AS teams, '{}'::JSON AS markets, 's.json' AS _source_file"
    )
    report = backfill_gamelines_from_actionnetwork(con)
    assert report is not None
    assert report.schema == "stg_gql"
    assert report.name == "game_lines"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_duckdb_load.py -k backfill -v`
Expected: FAIL — `needed.issubset(tables)` checks only `schema_name = 'stg'`, so
`stg_gql.game_lines` is invisible and the function returns `None`.

- [ ] **Step 3: Write minimal implementation**

Replace `backfill_gamelines_from_actionnetwork` (`duckdb_load.py:547-577`):

```python
def backfill_gamelines_from_actionnetwork(
    db: str | Path | duckdb.DuckDBPyConnection,
) -> TableLoad | None:
    """Merge Action Network period + extra-book lines into ``stg_gql.game_lines``.

    CFBD ``gameLines`` is full-game only. AN history is 1H/1Q; scoreboard
    ``markets`` is full-game per book. Existing CFBD numbers win; AN fills
    nulls and inserts missing ``(gameId, linesProviderId, period)`` rows.
    """
    owns_connection = not isinstance(db, duckdb.DuckDBPyConnection)
    con = duckdb.connect(str(db)) if owns_connection else db
    try:
        stg_tables = {
            row[0]
            for row in con.execute(
                "SELECT table_name FROM duckdb_tables() WHERE schema_name = 'stg'"
            ).fetchall()
        }
        gql_tables = {
            row[0]
            for row in con.execute(
                "SELECT table_name FROM duckdb_tables() WHERE schema_name = 'stg_gql'"
            ).fetchall()
        }
        if not (
            "game_lines" in gql_tables
            and "games" in stg_tables
            and "actionnetwork_scoreboard" in stg_tables
        ):
            return None
        return _backfill_gamelines(con, stg_tables, gql_tables)
    except Exception as exc:
        detail = str(exc).split("\n", 1)[0]
        return TableLoad(
            "stg_gql", "game_lines", 0, 0, error=f"{type(exc).__name__}: {detail}"
        )
    finally:
        if owns_connection:
            con.close()
```

Replace `_backfill_gamelines` (`duckdb_load.py:579-745`) — same SQL, `stg.gql_game_lines` →
`stg_gql.game_lines`, `stg.gql_lines_provider` → `stg_gql.lines_provider`, and the `tables`
parameter split to match the two-schema check above:

```python
def _backfill_gamelines(
    con: duckdb.DuckDBPyConnection, stg_tables: set[str], gql_tables: set[str]
) -> TableLoad:
    game_cols = {row[0] for row in con.execute("DESCRIBE stg.games").fetchall()}
    game_id = "gameId" if "gameId" in game_cols else "id"
    gl_types = {
        row[0]: row[1] for row in con.execute("DESCRIBE stg_gql.game_lines").fetchall()
    }
    gid_type = gl_types.get("gameId", "BIGINT")
    prov_type = gl_types.get("linesProviderId", "BIGINT")
    has_history = "actionnetwork_history" in stg_tables
    has_provider = "lines_provider" in gql_tables
    alias_sql = " ".join(
        f"WHEN '{src.replace(chr(39), chr(39) + chr(39))}' THEN '{dst.replace(chr(39), chr(39) + chr(39))}'"
        for src, dst in _AN_SCHOOL_ALIAS.items()
    )
    book_sql = " ".join(
        f"WHEN {an_id} THEN {cfbd_id}" for an_id, cfbd_id in _AN_BOOK_PROVIDER.items()
    )
    loc = """list_first(list_transform(list_filter(
              TRY_CAST(teams AS JSON[]),
              t -> TRY_CAST(json_extract(t, '$.id') AS BIGINT) = {tid}
            ), t -> json_extract_string(t, '$.location')))"""
    home_loc = loc.format(tid="home_team_id")
    away_loc = loc.format(tid="away_team_id")

    history_sql = (
        """
        SELECT event_id, book_id, period, market_type, side, line, odds, _source_file
        FROM stg.actionnetwork_history
        WHERE market_type IN ('spread', 'total', 'moneyline')
        """
        if has_history
        else """
        SELECT NULL::BIGINT AS event_id, NULL::INTEGER AS book_id,
               NULL::VARCHAR AS period, NULL::VARCHAR AS market_type,
               NULL::VARCHAR AS side, NULL::DOUBLE AS line, NULL::BIGINT AS odds,
               NULL::VARCHAR AS _source_file
        WHERE FALSE
        """
    )

    con.execute("DROP TABLE IF EXISTS stg_gql.game_lines__backfill")
    con.execute(
        f"""
        CREATE TABLE stg_gql.game_lines__backfill AS
        WITH map AS (
          SELECT
            sb.event_id,
            g.{_ident(game_id)} AS game_id,
            sb._source_file
          FROM stg.actionnetwork_scoreboard sb
          JOIN stg.games g
            ON g.season = sb.season
           AND g.week = sb.week
           AND g.homeTeam = CASE {home_loc} {alias_sql} ELSE {home_loc} END
           AND g.awayTeam = CASE {away_loc} {alias_sql} ELSE {away_loc} END
        ),
        sb_long AS (
          SELECT
            t.event_id,
            TRY_CAST(b.key AS INTEGER) AS book_id,
            COALESCE(json_extract_string(offering.value, '$.period'), 'event') AS period,
            COALESCE(
              json_extract_string(offering.value, '$.type'),
              mkt.key
            ) AS market_type,
            json_extract_string(offering.value, '$.side') AS side,
            TRY_CAST(json_extract(offering.value, '$.value') AS DOUBLE) AS line,
            TRY_CAST(json_extract(offering.value, '$.odds') AS BIGINT) AS odds,
            t._source_file
          FROM stg.actionnetwork_scoreboard t,
            json_each(t.markets) AS b,
            json_each(b.value) AS slot,
            json_each(slot.value) AS mkt,
            json_each(mkt.value) AS offering
          WHERE t.markets IS NOT NULL
            AND json_type(t.markets) = 'OBJECT'
            AND json_array_length(json_keys(t.markets)) > 0
        ),
        an_long AS (
          SELECT * FROM sb_long
          WHERE market_type IN ('spread', 'total', 'moneyline')
          UNION ALL
          {history_sql}
        ),
        an_wide AS (
          SELECT
            CAST(m.game_id AS {gid_type}) AS gameId,
            CAST(
              (CASE book_id {book_sql} ELSE book_id END) AS {prov_type}
            ) AS linesProviderId,
            CASE
              WHEN period IN ('event', 'game') THEN 'game'
              ELSE period
            END AS period,
            MAX(CASE WHEN market_type = 'spread' AND side = 'home'
                     THEN line END) AS spread,
            MAX(CASE WHEN market_type = 'total' AND side IN ('over', 'under')
                     THEN line END) AS overUnder,
            MAX(CASE WHEN market_type = 'moneyline' AND side = 'home'
                     THEN odds END) AS moneylineHome,
            MAX(CASE WHEN market_type = 'moneyline' AND side = 'away'
                     THEN odds END) AS moneylineAway,
            ANY_VALUE(an_long._source_file) AS _source_file
          FROM an_long
          JOIN map m USING (event_id)
          GROUP BY 1, 2, 3
        ),
        cfbd AS (
          SELECT
            gameId,
            linesProviderId,
            'game' AS period,
            TRY_CAST(spread AS DOUBLE) AS spread,
            spreadOpen,
            TRY_CAST(overUnder AS DOUBLE) AS overUnder,
            overUnderOpen,
            moneylineHome,
            moneylineAway,
            _source_file
          FROM stg_gql.game_lines
        )
        SELECT
          COALESCE(c.gameId, a.gameId) AS gameId,
          COALESCE(c.linesProviderId, a.linesProviderId) AS linesProviderId,
          COALESCE(c.period, a.period) AS period,
          COALESCE(c.spread, a.spread) AS spread,
          c.spreadOpen,
          COALESCE(c.overUnder, a.overUnder) AS overUnder,
          c.overUnderOpen,
          COALESCE(c.moneylineHome, a.moneylineHome) AS moneylineHome,
          COALESCE(c.moneylineAway, a.moneylineAway) AS moneylineAway,
          CASE
            WHEN c.gameId IS NOT NULL AND a.gameId IS NOT NULL THEN 'cfbd+an'
            WHEN c.gameId IS NOT NULL THEN 'cfbd'
            ELSE 'actionnetwork'
          END AS line_source,
          COALESCE(c._source_file, a._source_file) AS _source_file
        FROM cfbd c
        FULL OUTER JOIN an_wide a
          ON c.gameId = a.gameId
         AND c.linesProviderId = a.linesProviderId
         AND c.period = a.period
        """
    )
    con.execute("DROP TABLE stg_gql.game_lines")
    con.execute("ALTER TABLE stg_gql.game_lines__backfill RENAME TO game_lines")

    if has_provider:
        prov_cols = {
            row[0] for row in con.execute("DESCRIBE stg_gql.lines_provider").fetchall()
        }
        pid_col = "linesProviderId" if "linesProviderId" in prov_cols else "id"
        name_rows = ", ".join(
            f"({pid}, '{name.replace(chr(39), chr(39) + chr(39))}', 'actionnetwork')"
            for pid, name in _AN_PROVIDER_NAMES.items()
        )
        con.execute(
            f"""
            INSERT INTO stg_gql.lines_provider ({_ident(pid_col)}, name, _source_file)
            SELECT v.id, v.name, v.src
            FROM (VALUES {name_rows}) v(id, name, src)
            WHERE v.id NOT IN (SELECT {_ident(pid_col)} FROM stg_gql.lines_provider)
            """
        )

    return _finish_stg_table(con, "stg_gql", "game_lines", _qualify("stg_gql", "game_lines"))
```

Also fix the one remaining call site in `_explode_table` (`duckdb_load.py:744` before this task,
now inside `_backfill_gamelines`) — it's the `return _finish_stg_table(...)` line above, already
updated.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_duckdb_load.py -k backfill -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cfb_system_maker/duckdb_load.py tests/test_duckdb_load.py
git commit -m "fix(warehouse): point actionnetwork gameline backfill at stg_gql"
```

---

### Task 7: Rewrite the migration script for cross-schema moves

**Not run as part of this plan.** DuckDB has no `ALTER TABLE ... SET SCHEMA` (verified, 1.5.2:
`NotImplementedException: T_AlterObjectSchemaStmt`), so each table needs
`CREATE TABLE stg_gql.x AS SELECT * FROM stg.gql_x` then `DROP TABLE stg.gql_x` — a copy, not a
rename. Resumability matters more than cross-table atomicity at 1.8M rows: each table's
create+drop+meta-update happens in one transaction and is skipped if `stg_gql.x` already exists,
so a mid-run failure can be re-run rather than requiring a restore from backup.

**Files:**
- Modify: `scripts/migrate_gql_stg_names.py` (full rewrite)
- Test: `tests/test_migrate_gql_stg_names.py` (full rewrite)

**Interfaces:**
- Consumes: `GQL_ENTITY_TO_RAW`, `GQL_ENTITY_TO_STG` (Task 1)
- Produces: `plan_moves(con) -> list[tuple[str, str, str, str]]` — `(src_schema, src_name, dest_schema, dest_name)` per table, derived from the mapping plus a `duckdb_tables()` scan for `<parent>__%` children, not hand-listed. `migrate(con) -> list[TableLoad]`.

- [ ] **Step 1: Write the failing test**

Read the existing `tests/test_migrate_gql_stg_names.py` first (it tests the old rename-based
script against a synthetic file) and replace it with:

```python
import duckdb

from scripts.migrate_gql_stg_names import migrate, plan_moves


def _seeded_con():
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA stg")
    con.execute("CREATE SCHEMA meta")
    con.execute("CREATE TABLE stg.gql_game AS SELECT 1 AS gameId, 2024 AS season")
    con.execute("CREATE TABLE stg.gql_game__away_line_scores AS SELECT 1 AS gameId, 10 AS score")
    con.execute("CREATE TABLE stg.games AS SELECT 1 AS gameId, 2024 AS season")
    con.execute(
        """
        CREATE TABLE meta.load_report (
          schema VARCHAR, name VARCHAR, files INTEGER, rows BIGINT,
          error VARCHAR, loaded_at TIMESTAMP
        )
        """
    )
    con.execute(
        "INSERT INTO meta.load_report VALUES"
        " ('stg', 'gql_game', 1, 1, NULL, now()),"
        " ('stg', 'gql_game__away_line_scores', 1, 1, NULL, now()),"
        " ('stg', 'games', 1, 1, NULL, now())"
    )
    return con


def test_plan_moves_covers_parent_and_child_tables_not_rest():
    con = _seeded_con()
    moves = plan_moves(con)
    by_src = {(s, n): (ds, dn) for s, n, ds, dn in moves}
    assert by_src[("stg", "gql_game")] == ("stg_gql", "game")
    assert by_src[("stg", "gql_game__away_line_scores")] == ("stg_gql", "game__away_line_scores")
    assert ("stg", "games") not in by_src


def test_migrate_moves_tables_and_updates_meta():
    con = _seeded_con()
    migrate(con)
    assert con.execute(
        "SELECT COUNT(*) FROM information_schema.tables"
        " WHERE table_schema = 'stg' AND table_name = 'gql_game'"
    ).fetchone()[0] == 0
    assert con.execute("SELECT gameId FROM stg_gql.game").fetchone()[0] == 1
    assert con.execute("SELECT gameId FROM stg.games").fetchone()[0] == 1
    row = con.execute(
        "SELECT schema, name FROM meta.load_report WHERE name = 'game' AND schema = 'stg_gql'"
    ).fetchone()
    assert row == ("stg_gql", "game")


def test_migrate_is_idempotent_and_resumable():
    con = _seeded_con()
    migrate(con)
    con.execute("DROP TABLE stg.gql_game__away_line_scores")  # simulate partial prior run
    second = migrate(con)  # must not error re-processing already-moved tables
    assert all(report.error is None for report in second)
    assert con.execute("SELECT gameId FROM stg_gql.game").fetchone()[0] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_migrate_gql_stg_names.py -v`
Expected: FAIL — `ImportError: cannot import name 'plan_moves'`

- [ ] **Step 3: Write minimal implementation**

Read the current `scripts/migrate_gql_stg_names.py` (91 lines) before replacing it — reuse its
CLI argument handling (`--db`, `--dry-run`, `--yes` or equivalent) verbatim; only `plan_moves`
and the per-table execution change. Full rewrite:

```python
"""One-shot migration: move stg.gql_<x> tables into stg_gql.<x>.

DuckDB has no `ALTER TABLE ... SET SCHEMA` (verified 1.5.2), so each table is a
`CREATE TABLE ... AS SELECT * FROM ...` copy followed by a `DROP TABLE`, not a
metadata rename. Resumable: a table already present at its destination is skipped,
so a partial prior run (or a re-run after this script itself failed partway) is safe.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import duckdb

from cfb_system_maker.graphql_client import GQL_ENTITY_TO_RAW, GQL_ENTITY_TO_STG


@dataclass(frozen=True)
class MoveReport:
    src_schema: str
    src_name: str
    dest_schema: str
    dest_name: str
    rows: int = 0
    error: str | None = None


def plan_moves(con: duckdb.DuckDBPyConnection) -> list[tuple[str, str, str, str]]:
    """``(src_schema, src_name, dest_schema, dest_name)`` for every table to move.

    Parents come from the mapping (the source of truth for which raw name maps to
    which bare destination). Children are discovered by scanning `stg` for
    `<parent>__%` tables rather than hand-listed, so a new nested column doesn't
    silently strand its child table in `stg`.
    """
    moves: list[tuple[str, str, str, str]] = []
    existing = {
        row[0]
        for row in con.execute(
            "SELECT table_name FROM duckdb_tables() WHERE schema_name = 'stg'"
        ).fetchall()
    }
    for entity, raw_name in GQL_ENTITY_TO_RAW.items():
        if raw_name not in existing:
            continue
        dest_name = GQL_ENTITY_TO_STG[entity]
        moves.append(("stg", raw_name, "stg_gql", dest_name))
        prefix = raw_name + "__"
        for child in sorted(name for name in existing if name.startswith(prefix)):
            dest_child = dest_name + "__" + child[len(prefix):]
            moves.append(("stg", child, "stg_gql", dest_child))
    return moves


def migrate(con: duckdb.DuckDBPyConnection) -> list[MoveReport]:
    con.execute("CREATE SCHEMA IF NOT EXISTS stg_gql")
    reports: list[MoveReport] = []
    for src_schema, src_name, dest_schema, dest_name in plan_moves(con):
        already_moved = con.execute(
            "SELECT COUNT(*) FROM duckdb_tables()"
            f" WHERE schema_name = '{dest_schema}' AND table_name = '{dest_name}'"
        ).fetchone()[0]
        if already_moved:
            reports.append(MoveReport(src_schema, src_name, dest_schema, dest_name))
            continue
        try:
            con.execute("BEGIN TRANSACTION")
            con.execute(
                f'CREATE TABLE "{dest_schema}"."{dest_name}" AS'
                f' SELECT * FROM "{src_schema}"."{src_name}"'
            )
            con.execute(f'DROP TABLE "{src_schema}"."{src_name}"')
            con.execute(
                "UPDATE meta.load_report SET schema = ?, name = ?"
                " WHERE schema = ? AND name = ?",
                [dest_schema, dest_name, src_schema, src_name],
            )
            con.execute("COMMIT")
            rows = con.execute(
                f'SELECT COUNT(*) FROM "{dest_schema}"."{dest_name}"'
            ).fetchone()[0]
            reports.append(MoveReport(src_schema, src_name, dest_schema, dest_name, rows=int(rows)))
        except Exception as exc:
            con.execute("ROLLBACK")
            detail = str(exc).split("\n", 1)[0]
            reports.append(
                MoveReport(
                    src_schema, src_name, dest_schema, dest_name,
                    error=f"{type(exc).__name__}: {detail}",
                )
            )
    return reports


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Path to cfb.duckdb")
    parser.add_argument("--yes", action="store_true", help="Apply the migration (default: dry run)")
    args = parser.parse_args()

    con = duckdb.connect(args.db)
    moves = plan_moves(con)
    print(f"{len(moves)} tables to move (stg -> stg_gql):")
    for src_schema, src_name, dest_schema, dest_name in moves:
        print(f"  {src_schema}.{src_name} -> {dest_schema}.{dest_name}")
    if not args.yes:
        print("\nDry run only. Re-run with --yes to apply.")
        con.close()
        return
    reports = migrate(con)
    con.close()
    failed = [r for r in reports if r.error]
    print(f"\n{len(reports) - len(failed)} moved, {len(failed)} failed")
    for r in failed:
        print(f"  FAILED {r.src_schema}.{r.src_name}: {r.error}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_migrate_gql_stg_names.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/migrate_gql_stg_names.py tests/test_migrate_gql_stg_names.py
git commit -m "feat(warehouse): rewrite gql migration as cross-schema move"
```

**Do not run `python scripts/migrate_gql_stg_names.py --db data/cfb.duckdb --yes` as part of
this plan.** That is a separate, explicit, user-initiated step against the 4.9 GB unbacked
warehouse file.

---

### Task 8: `audit_canonical_sources.py` reads the GraphQL half from `stg_gql`

`_cols`/`_seasons`/`_null_rate` currently hardcode `table_schema = 'stg'` / `stg."{table}"` —
they take a table name only, no schema. Since the GraphQL member of each pair now lives in
`stg_gql`, these three helpers (and `concept_metrics`, and `main`'s presence check) need a
`schema` parameter.

**Files:**
- Modify: `scripts/audit_canonical_sources.py` (full contents — `PAIRS`, `_cols`, `_seasons`, `_null_rate`, `concept_metrics`, `main`)
- Test: `tests/test_audit_canonical_sources.py` (does not exist yet — this script had no test file; add one)

**Interfaces:**
- Consumes: none new
- Produces: `_cols(con, schema, table)`, `_seasons(con, schema, table, cols)`, `_null_rate(con, schema, table, cols)`, `concept_metrics(con, gql_table, rest_table) -> dict` (unchanged signature — resolves `stg_gql`/`stg` internally now that both are fixed per call).

- [ ] **Step 1: Write the failing test**

Create `tests/test_audit_canonical_sources.py`:

```python
import duckdb

from scripts.audit_canonical_sources import PAIRS, concept_metrics


def test_pairs_graphql_member_has_no_gql_prefix():
    for concept, gql_name, rest_name in PAIRS:
        assert not gql_name.startswith("gql_"), f"{concept}: {gql_name} still gql_-prefixed"


def test_concept_metrics_reads_graphql_side_from_stg_gql():
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA stg")
    con.execute("CREATE SCHEMA stg_gql")
    con.execute("CREATE TABLE stg.calendar AS SELECT 1 AS id, 2024 AS season")
    con.execute(
        "CREATE TABLE stg_gql.calendar AS"
        " SELECT 1 AS id, 2024 AS season UNION ALL SELECT 2, 2023"
    )
    metrics = concept_metrics(con, "calendar", "calendar")
    assert metrics["gql_rows"] == 2
    assert metrics["rest_rows"] == 1
    assert metrics["gql_seasons"] == (2023, 2024)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_audit_canonical_sources.py -v`
Expected: FAIL — `metrics["gql_rows"]` reads `stg.calendar` (1 row) instead of `stg_gql.calendar`
(2 rows), since `_cols`/`concept_metrics` still hardcode `stg`.

- [ ] **Step 3: Write minimal implementation**

Replace `scripts/audit_canonical_sources.py:18-113` (from `PAIRS` through `main`):

```python
# (concept, gql_table, rest_table) — gql_table is bare (lives in stg_gql), rest_table
# lives in stg. A concept whose two spellings collide once bare (draft_pick) still has
# distinct entries here because the two tables live in different schemas.
PAIRS = [
    ("game", "game", "games"),
    ("coach", "coach", "coaches"),
    ("conference", "conference", "conferences"),
    ("draft_pick", "draft_picks", "draft_picks"),
    ("draft_position", "draft_position", "draft_positions"),
    ("draft_team", "draft_team", "draft_teams"),
    ("recruit", "recruit", "recruits"),
    ("recruiting_team", "recruiting_team", "recruiting_teams"),
    ("coach_season", "coach_season", "coach_seasons"),
    ("predicted_points", "predicted_points", "predicted_points"),
    ("talent", "team_talent", "talent"),
    ("lines", "game_lines", "lines"),
    ("calendar", "calendar", "calendar"),
]


def _cols(con: duckdb.DuckDBPyConnection, schema: str, table: str) -> list[str]:
    return [
        row[0]
        for row in con.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = ? AND table_name = ?",
            [schema, table],
        ).fetchall()
    ]


def _seasons(
    con: duckdb.DuckDBPyConnection, schema: str, table: str, cols: list[str]
) -> tuple[int, int] | None:
    if "season" not in cols:
        return None
    row = con.execute(f'SELECT MIN(season), MAX(season) FROM "{schema}"."{table}"').fetchone()
    return None if row is None or row[0] is None else (int(row[0]), int(row[1]))


def _null_rate(
    con: duckdb.DuckDBPyConnection, schema: str, table: str, cols: list[str]
) -> float | None:
    if not cols:
        return None
    total = con.execute(f'SELECT COUNT(*) FROM "{schema}"."{table}"').fetchone()[0]
    if not total:
        return None
    parts = " + ".join(f'COUNT("{c}")' for c in cols)
    filled = con.execute(f'SELECT {parts} FROM "{schema}"."{table}"').fetchone()[0]
    return round(1 - (filled / (total * len(cols))), 4)


def concept_metrics(
    con: duckdb.DuckDBPyConnection, gql_table: str, rest_table: str
) -> dict:
    gcols = _cols(con, "stg_gql", gql_table)
    rcols = _cols(con, "stg", rest_table)
    return {
        "gql_rows": con.execute(f'SELECT COUNT(*) FROM "stg_gql"."{gql_table}"').fetchone()[0],
        "rest_rows": con.execute(f'SELECT COUNT(*) FROM "stg"."{rest_table}"').fetchone()[0],
        "gql_cols": len(gcols),
        "rest_cols": len(rcols),
        "gql_seasons": _seasons(con, "stg_gql", gql_table, gcols),
        "rest_seasons": _seasons(con, "stg", rest_table, rcols),
        "gql_null_rate": _null_rate(con, "stg_gql", gql_table, gcols),
        "rest_null_rate": _null_rate(con, "stg", rest_table, rcols),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/cfb.duckdb")
    args = ap.parse_args()
    con = duckdb.connect(args.db, read_only=True)
    gql_present = {
        row[0]
        for row in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'stg_gql'"
        ).fetchall()
    }
    rest_present = {
        row[0]
        for row in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'stg'"
        ).fetchall()
    }
    print("| concept | gql rows | rest rows | gql seasons | rest seasons "
          "| gql cols | rest cols | gql null | rest null |")
    print("|---|---|---|---|---|---|---|---|---|")
    for concept, g, r in PAIRS:
        if g not in gql_present or r not in rest_present:
            print(f"| {concept} | MISSING ({g} or {r}) | | | | | | | |")
            continue
        m = concept_metrics(con, g, r)
        print(
            f"| {concept} | {m['gql_rows']} | {m['rest_rows']} | {m['gql_seasons']} "
            f"| {m['rest_seasons']} | {m['gql_cols']} | {m['rest_cols']} "
            f"| {m['gql_null_rate']} | {m['rest_null_rate']} |"
        )
    return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_audit_canonical_sources.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/audit_canonical_sources.py tests/test_audit_canonical_sources.py
git commit -m "fix(warehouse): audit GraphQL canonical sources from stg_gql"
```

---

### Task 9: `promote_to_motherduck.py` mirrors `stg_gql`

Confirmed by reading the full script: the promote loop already issues
`CREATE SCHEMA IF NOT EXISTS md.{schema}` (line 94) generically for every schema in `tables` —
there is no separate hardcoded schema list to extend beyond `DEFAULT_SCHEMAS`. Adding
`"stg_gql"` there is the entire fix.

**Files:**
- Modify: `scripts/promote_to_motherduck.py:24`
- Test: `tests/test_promote_to_motherduck.py` (does not exist yet — add one)

**Interfaces:**
- Consumes: none
- Produces: no signature change.

- [ ] **Step 1: Write the failing test**

Create `tests/test_promote_to_motherduck.py`:

```python
from scripts.promote_to_motherduck import DEFAULT_SCHEMAS


def test_default_schemas_includes_stg_gql():
    assert "stg_gql" in DEFAULT_SCHEMAS
    assert DEFAULT_SCHEMAS == ["raw", "stg", "stg_gql", "core", "meta"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_promote_to_motherduck.py -v`
Expected: FAIL — `AssertionError: 'stg_gql' not in [...]`

- [ ] **Step 3: Write minimal implementation**

In `scripts/promote_to_motherduck.py:24`:

```python
DEFAULT_SCHEMAS = ["raw", "stg", "stg_gql", "core", "meta"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_promote_to_motherduck.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/promote_to_motherduck.py tests/test_promote_to_motherduck.py
git commit -m "feat(warehouse): promote stg_gql to MotherDuck"
```

---

### Task 10: Docs — `CLAUDE.md`, `CONTEXT.md`, `PLAN-REVIEW-LOG.md`

**Files:**
- Modify: `cfb_system_maker/CLAUDE.md`, `CONTEXT.md`, `PLAN-REVIEW-LOG.md`

No test — documentation only. Verify by reading the diff, not by running anything.

- [ ] **Step 1:** In `cfb_system_maker/CLAUDE.md`, under "Key conventions," replace the line
  `GraphQL dumps land in raw, not a separate graphql schema.` with:

  ```
  - **Two staging schemas:** `stg` holds REST-sourced tables (snake_case, unchanged names);
    `stg_gql` holds GraphQL-sourced tables (bare snake_case — `stg_gql.game`, not
    `stg.gql_game`). `raw` stays a single schema for both sources: GraphQL raw dumps keep a
    `gql_` prefix (`raw.gql_game`) so they don't collide with REST raw dumps of the same
    snake_case name (`draft_picks`, `predicted_points`, `calendar` all would). `--only <name>`
    matches a bare destination name in either schema, so `--only draft_picks` touches both
    `stg.draft_picks` and `stg_gql.draft_picks` together — use the GraphQL entity spelling
    (`--only draftPicks`) to select only the GraphQL raw dump/table.
  ```

  Also fix the earlier, pre-existing stale line in the `duckdb` command description
  (`"GraphQL calendar becomes raw.calendar_gql on name clash"`) — replace with:

  ```
  `duckdb` loads `data/raw/` + `data/graphql/` into `data/cfb.duckdb` (one file; REST lands in
  `raw`/`stg` under its endpoint names, GraphQL lands in `raw` under a `gql_`-prefixed name and
  `stg_gql` under its bare name — optional `stg`/`stg_gql` explode / `--flatten-nested`).
  ```

- [ ] **Step 2:** In `CONTEXT.md`, find the "canonical source" and "merged table" glossary
  entries (added 2026-08-31 per the handoff) and check whether either references the `gql_`
  prefix directly. If so, reword to reference the schema instead (e.g. "the GraphQL-sourced
  table in `stg_gql`" rather than "the `gql_`-prefixed table"). If neither references the
  prefix, no change needed — say so rather than editing speculatively.

- [ ] **Step 3:** Append to `PLAN-REVIEW-LOG.md` (same format as the 2026-08-31 entry) recording:
  the four locked decisions (forward-fix, keep `__` convention, leave `raw` un-schema-split,
  new ADR), the raw-naming-collision finding and its resolution (`GQL_ENTITY_TO_RAW` decoupling),
  and the test count delta from this plan's baseline (696).

- [ ] **Step 4: Commit**

```bash
git add cfb_system_maker/CLAUDE.md CONTEXT.md PLAN-REVIEW-LOG.md
git commit -m "docs(warehouse): document stg_gql schema separation"
```

---

## Self-Review Notes (for whoever executes this plan)

- **Task ordering matters.** Tasks 1→2→3→4→5→6 each depend on the previous task's signatures
  (`GQL_ENTITY_TO_RAW`/`GQL_ENTITY_TO_STG` → `stg_destination` → `schema`-aware id-rename →
  `schema`-aware explode → `schema`-aware post-process → backfill). Do not reorder. Tasks 7–10
  depend on 1 (the mapping) but not on 2–6, so they can run after Task 1 if parallelizing across
  subagents — but Task 7's tests assume `stg_id_renames`/`stg_column_order` already require
  `schema` (Task 3) if it seeds fixtures through the real loader rather than raw SQL; the plan
  above seeds fixtures with raw SQL specifically to avoid that coupling.
- **`python -m pytest` will not pass end-to-end until Task 6 is committed** — Tasks 2–5 each run
  only their own `-k` subset in Step 4 because they leave other call sites in this file broken
  between commits (documented per-task above). Run the full suite after Task 6, and again after
  each of Tasks 7–10.
- **Task 7 is the only task producing something that touches the live warehouse, and even then
  only when someone runs it with `--yes` outside this plan.**
