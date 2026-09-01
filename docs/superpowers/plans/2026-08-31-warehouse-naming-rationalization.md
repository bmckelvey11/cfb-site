# Warehouse Naming Rationalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every GraphQL-sourced `stg` table name explicit, snake_case, and order-independent, and record which source is canonical per duplicated concept.

**Architecture:** `stg` is fed by two ingestion sources. REST endpoints land snake_case; the 34 GraphQL entities currently land under their verbatim camelCase API field names, and clashes between the two are resolved by a load-order-dependent helper. We replace that helper with an explicit total mapping (`GQL_ENTITY_TO_STG`) that renames GraphQL destinations to `gql_<snake_case>`, leaving the GraphQL field names — an upstream API contract — untouched. Existing tables are migrated in place with a one-shot idempotent script that also repairs `meta.load_report`, avoiding a 4.9 GB rebuild. Canonical-source designation is an audit that produces a documented table; it does not delete anything.

**Tech Stack:** Python 3, DuckDB 1.5.2, pytest

**Spec:** `docs/superpowers/specs/2026-08-31-warehouse-naming-rationalization.md`

## Global Constraints

- `CFB_DATA_ROOT` is required; paths resolve through root `cfb_paths.py`. Local `data/cfb.duckdb` is source of truth; `md:cfb` is a manual mirror.
- Data is never committed. Only code, tests, and docs enter git.
- Do not edit `cfbd-python/` — vendored upstream.
- Run all commands from repository root.
- Default verification: `python -m pytest`. The suite must pass at every commit. The plan quotes absolute counts (675 → 678 → 685 → 688) against a **672-test baseline measured 2026-08-31**. If that baseline has drifted, treat every quoted count as a **delta** (+3, +3, +7, +3) rather than an absolute, and check that the delta matches the tests the task adds. A mismatched absolute is not a failure; a mismatched delta is.
- `raw` schema names never change — `raw` preserves source fidelity by design.
- GraphQL field names (`GQL_DEFAULT_TABLES`, `GQL_RELATION_KEYS`, query text, `data/graphql/*.json` filenames) never change. Only `stg` destination table names change.
- Tasks 1–4 touch code and docs only. **Task 5 mutates the warehouse and must not be auto-committed or auto-run** — it is executed by the user explicitly.

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `cfb_system_maker/graphql_client.py` | Add `GQL_ENTITY_TO_STG`, the single source of truth for GraphQL→`stg` destination names. Lives here because it is a property of the GraphQL source, not of the loader. | 1 |
| `tests/test_graphql.py` | Assert the mapping is total, injective, snake_case, `gql_`-prefixed. | 1 |
| `cfb_system_maker/duckdb_load.py` | Replace `_stg_dest_name` with mapping lookup; update the 7 `stg.gameLines` / `stg.linesProvider` reference lines. | 2, 3 |
| `tests/test_duckdb_load.py` | Assert destination names are load-order-independent; update 8 fixture/assertion lines. | 2, 3 |
| `scripts/migrate_gql_stg_names.py` | One-shot idempotent migration: rename existing `stg` tables + child tables, repair `meta.load_report`. | 4 |
| `tests/test_migrate_gql_stg_names.py` | Migration correctness and idempotency against a synthetic DuckDB file. | 4 |
| `scripts/audit_canonical_sources.py` | Emit per-concept coverage metrics for canonical designation. | 6 |
| `docs/warehouse-naming.md` | The convention, the rename map, and the canonical-source table. | 7 |

---

### Task 1: Explicit GraphQL→`stg` destination mapping

**Files:**
- Modify: `cfb_system_maker/graphql_client.py` (append after `GQL_DEFAULT_TABLES`, which ends at line 38)
- Test: `tests/test_graphql.py`

**Interfaces:**
- Consumes: `GQL_DEFAULT_TABLES` (existing, `graphql_client.py:25`)
- Produces: `GQL_ENTITY_TO_STG: dict[str, str]` — maps each of the 34 GraphQL root field names to its `stg` destination table name. Imported by `duckdb_load.py` in Task 2 and by `scripts/migrate_gql_stg_names.py` in Task 4.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_graphql.py`:

```python
import re

from cfb_system_maker.graphql_client import GQL_DEFAULT_TABLES, GQL_ENTITY_TO_STG


def test_gql_entity_to_stg_is_total_and_injective():
    # Every GraphQL entity we pull must have an explicit destination — no fallback,
    # no clash detection. That totality is what removes the load-order dependence.
    assert set(GQL_ENTITY_TO_STG) == set(GQL_DEFAULT_TABLES)
    assert len(set(GQL_ENTITY_TO_STG.values())) == len(GQL_ENTITY_TO_STG)


def test_gql_destinations_are_snake_case_and_prefixed():
    for entity, dest in GQL_ENTITY_TO_STG.items():
        assert dest.startswith("gql_"), f"{entity} -> {dest} lacks gql_ prefix"
        assert re.fullmatch(r"[a-z0-9_]+", dest), f"{entity} -> {dest} is not snake_case"


def test_gql_destinations_match_spec_examples():
    # Spot-check the transformations the spec's rename map fixes, including the
    # multi-word and acronym-adjacent cases where a naive splitter goes wrong.
    assert GQL_ENTITY_TO_STG["game"] == "gql_game"
    assert GQL_ENTITY_TO_STG["gameLines"] == "gql_game_lines"
    assert GQL_ENTITY_TO_STG["adjustedPlayerMetrics"] == "gql_adjusted_player_metrics"
    assert GQL_ENTITY_TO_STG["playerStatCategory"] == "gql_player_stat_category"
    assert GQL_ENTITY_TO_STG["calendar"] == "gql_calendar"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_graphql.py -k gql_entity_to_stg -v`
Expected: FAIL with `ImportError: cannot import name 'GQL_ENTITY_TO_STG'`

- [ ] **Step 3: Write minimal implementation**

Insert into `cfb_system_maker/graphql_client.py` immediately after the closing `]` of `GQL_DEFAULT_TABLES` (line 38):

```python
def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


# Destination `stg` table name for each GraphQL entity. Explicit and total on purpose:
# `stg` is fed by REST (snake_case) and GraphQL (camelCase API field names), and the
# previous clash-resolution helper picked a winner by load order. The `gql_` prefix is
# disjoint from every REST destination, so a clash is impossible by construction.
# The keys are the upstream API contract and must not be renamed.
GQL_ENTITY_TO_STG: dict[str, str] = {
    entity: "gql_" + _snake(entity) for entity in GQL_DEFAULT_TABLES
}
```

Add `import re` to the imports at the top of the file if not already present.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_graphql.py -k "gql_entity_to_stg or gql_destinations" -v`
Expected: 3 passed

- [ ] **Step 5: Run full suite**

Run: `python -m pytest`
Expected: 675 passed (672 existing + 3 new)

- [ ] **Step 6: Commit**

```bash
git add cfb_system_maker/graphql_client.py tests/test_graphql.py
git commit -m "feat(warehouse): add explicit GraphQL to stg destination mapping"
```

---

### Task 2: Make loader destination naming order-independent

**Files:**
- Modify: `cfb_system_maker/duckdb_load.py:1086-1092` (`_stg_dest_name`), `:493-503` (explode loop), `:1487-1501` (raw load-job loop)
- Test: `tests/test_duckdb_load.py`

**Interfaces:**
- Consumes: `GQL_ENTITY_TO_STG` from Task 1
- Produces: `stg_dest_name(name: str) -> str` — a pure function of the source name alone, no `taken` parameter. Returns the mapped destination for a GraphQL entity, or `name` unchanged for a REST endpoint.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_duckdb_load.py`:

```python
from cfb_system_maker.duckdb_load import stg_dest_name


def test_stg_dest_name_is_order_independent():
    # The old helper took a `taken` set populated as loads proceeded, so whether the
    # GraphQL or the REST table won an unsuffixed name depended on load order. The
    # new one is a pure function: same input, same output, always.
    assert stg_dest_name("calendar") == "gql_calendar"
    assert stg_dest_name("calendar") == "gql_calendar"
    assert stg_dest_name("gameLines") == "gql_game_lines"


def test_stg_dest_name_passes_rest_names_through():
    assert stg_dest_name("games") == "games"
    assert stg_dest_name("draft_picks") == "draft_picks"
    assert stg_dest_name("advanced_box_score") == "advanced_box_score"


def test_gql_destinations_never_collide_with_rest_destinations():
    from cfb_system_maker.graphql_client import GQL_ENTITY_TO_STG

    rest_names = {"games", "coaches", "conferences", "draft_picks", "recruits",
                  "recruiting_teams", "coach_seasons", "predicted_points", "talent",
                  "lines", "calendar", "draft_positions", "draft_teams"}
    assert not (set(GQL_ENTITY_TO_STG.values()) & rest_names)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_duckdb_load.py -k stg_dest_name -v`
Expected: FAIL with `ImportError: cannot import name 'stg_dest_name'`

- [ ] **Step 3: Replace the helper**

In `cfb_system_maker/duckdb_load.py`, delete `_stg_dest_name` (lines 1086-1092) and put in its place:

```python
def stg_dest_name(name: str) -> str:
    """`stg` destination for a source table name.

    Pure function of the name alone. GraphQL entities map through the explicit table
    in `graphql_client`; REST endpoint names pass through unchanged. The previous
    implementation took a `taken` set and resolved clashes by load order, which made a
    table's provenance depend on the order loads happened to run in.
    """
    return GQL_ENTITY_TO_STG.get(name, name)
```

Add to the imports at the top of `duckdb_load.py`:

```python
from cfb_system_maker.graphql_client import GQL_ENTITY_TO_STG
```

- [ ] **Step 4: Update the explode loop**

In `cfb_system_maker/duckdb_load.py`, replace lines 493-503 with:

```python
        # No `taken` set and no REST-first sort: destinations are disjoint by
        # construction now, so load order cannot change which table wins a name.
        for schema, name in sources:
            if only is not None and name not in only:
                continue
            dest = stg_dest_name(name)
            report = _explode_table(con, schema, name, dest)
            reports.append(report)
            if progress is not None:
                progress(report)
            con.execute("CHECKPOINT")
```

Also delete the now-stale `sources.sort(...)` line and its comment at lines 494-495.

- [ ] **Step 5: Update the raw load-job loop**

In `cfb_system_maker/duckdb_load.py`, replace lines 1487-1501 with:

```python
    gql_dir = data_dir / "graphql"
    if gql_dir.is_dir():
        gql_groups: dict[str, list[Path]] = {}
        for path in sorted(gql_dir.glob("*.json")):
            name, _, _, _ = parse_dump_stem(path.stem)
            gql_groups.setdefault(name, []).append(path)
        for name, paths in sorted(gql_groups.items()):
            dest = stg_dest_name(name)
            if only is not None and name not in only and dest not in only:
                continue
            jobs.append(
                {"schema": "raw", "name": dest, "paths": paths, "format": "array"}
            )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_duckdb_load.py -k stg_dest_name -v`
Expected: 3 passed

- [ ] **Step 7: Run full suite**

Run: `python -m pytest`
Expected: 678 passed. If any test fails referencing `_stg_dest_name`, update it to `stg_dest_name` and drop the `taken` argument — the rename is the point.

- [ ] **Step 8: Commit**

```bash
git add cfb_system_maker/duckdb_load.py tests/test_duckdb_load.py
git commit -m "fix(warehouse): make stg destination naming independent of load order"
```

---

### Task 3: Update the live `stg.gameLines` / `stg.linesProvider` references

**Files:**
- Modify: `cfb_system_maker/duckdb_load.py` lines 547, 562, 569, 580, 695, 720-721, 725, 734, 737, 741
- Test: `tests/test_duckdb_load.py` lines 770, 780, 786, 792, 875, 880, 888, 894

**Interfaces:**
- Consumes: `stg_dest_name` from Task 2
- Produces: nothing new; this task only retargets existing SQL at the new table names.

These are the only two GraphQL-sourced tables referenced by name anywhere in the live tree. `backfill_gamelines_from_actionnetwork` merges Action Network period lines into the GraphQL lines table.

- [ ] **Step 1: Run the tests that cover the backfill, to capture the current pass state**

Run: `python -m pytest tests/test_duckdb_load.py -k "gamelines or lines_provider or backfill" -v`
Expected: PASS. Record the count — the same tests must pass after the rename.

- [ ] **Step 2: Rewrite the source references**

In `cfb_system_maker/duckdb_load.py`, replace every `stg.gameLines` with `stg.gql_game_lines`, every `stg.linesProvider` with `stg.gql_lines_provider`, and the bare table names inside `backfill_gamelines_from_actionnetwork`:

```bash
python - <<'PY'
import pathlib
p = pathlib.Path("cfb_system_maker/duckdb_load.py")
s = p.read_text(encoding="utf-8")
s = s.replace("stg.gameLines", "stg.gql_game_lines")
s = s.replace("stg.linesProvider", "stg.gql_lines_provider")
s = s.replace('_qualify("stg", "gameLines")', '_qualify("stg", "gql_game_lines")')
s = s.replace('_finish_stg_table(con, "gameLines"', '_finish_stg_table(con, "gql_game_lines"')
s = s.replace('stg.gameLines__backfill', 'stg.gql_game_lines__backfill')
s = s.replace('RENAME TO gameLines', 'RENAME TO gql_game_lines')
s = s.replace('{"gameLines", "games", "actionnetwork_scoreboard"}',
              '{"gql_game_lines", "games", "actionnetwork_scoreboard"}')
s = s.replace('TableLoad("stg", "gameLines"', 'TableLoad("stg", "gql_game_lines"')
p.write_text(s, encoding="utf-8")
PY
```

- [ ] **Step 3: Verify no camelCase references survive in the module**

Run:

```bash
grep -nE 'stg\.(gameLines|linesProvider)|"gameLines"|"linesProvider"' cfb_system_maker/duckdb_load.py
```

Expected: no output. If the docstring at line 547 still says `stg.gameLines`, edit it to `stg.gql_game_lines` by hand — it is prose, not code, and the replacements above may not have caught its backtick form.

- [ ] **Step 4: Rewrite the test references**

In `tests/test_duckdb_load.py`, apply the same two substitutions:

```bash
python - <<'PY'
import pathlib
p = pathlib.Path("tests/test_duckdb_load.py")
s = p.read_text(encoding="utf-8")
s = s.replace("stg.gameLines", "stg.gql_game_lines")
s = s.replace("stg.linesProvider", "stg.gql_lines_provider")
p.write_text(s, encoding="utf-8")
PY
```

- [ ] **Step 5: Run the backfill tests**

Run: `python -m pytest tests/test_duckdb_load.py -k "gamelines or lines_provider or backfill" -v`
Expected: same count as Step 1, all passing.

- [ ] **Step 6: Run full suite**

Run: `python -m pytest`
Expected: 678 passed

- [ ] **Step 7: Commit**

```bash
git add cfb_system_maker/duckdb_load.py tests/test_duckdb_load.py
git commit -m "refactor(warehouse): retarget gameLines backfill at gql_ table names"
```

---

### Task 4: Migration script for the existing warehouse

**Files:**
- Create: `scripts/migrate_gql_stg_names.py`
- Test: `tests/test_migrate_gql_stg_names.py`

**Interfaces:**
- Consumes: `GQL_ENTITY_TO_STG` from Task 1
- Produces: `plan_renames(con) -> list[tuple[str, str]]` returning `(old_name, new_name)` pairs for `stg` tables present in the database, parents and `__`-suffixed children alike; `migrate(con, *, dry_run: bool) -> list[tuple[str, str]]` applying them and repairing `meta.load_report`.

`meta.load_report` keys on `(schema, name)` (`duckdb_load.py:1304`), so a bare `ALTER TABLE ... RENAME` desyncs the bookkeeping. The script renames and repairs in one transaction.

The live `stg.calendar_gql` is the GraphQL calendar (424 rows) and becomes `gql_calendar`; the REST `stg.calendar` (258 rows) keeps its name. The script must handle that legacy `_gql` suffix, which is why `plan_renames` cannot simply apply `GQL_ENTITY_TO_STG` to the entity names.

- [ ] **Step 1: Write the failing test**

Create `tests/test_migrate_gql_stg_names.py`:

```python
import duckdb
import pytest

from scripts.migrate_gql_stg_names import migrate, plan_renames


@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    c.execute("CREATE SCHEMA stg")
    c.execute("CREATE SCHEMA meta")
    c.execute("CREATE TABLE stg.gameLines (id INTEGER)")
    c.execute("INSERT INTO stg.gameLines VALUES (1)")
    c.execute('CREATE TABLE stg."gameTeam__lineScores" (id INTEGER)')
    c.execute("CREATE TABLE stg.calendar_gql (id INTEGER)")
    c.execute("CREATE TABLE stg.calendar (id INTEGER)")
    c.execute("CREATE TABLE stg.games (id INTEGER)")
    c.execute(
        "CREATE TABLE meta.load_report "
        "(schema VARCHAR, name VARCHAR, files INTEGER, rows BIGINT, "
        " error VARCHAR, loaded_at TIMESTAMP)"
    )
    c.execute(
        "INSERT INTO meta.load_report VALUES "
        "('stg','gameLines',1,63293,NULL,NOW()), ('stg','games',1,54264,NULL,NOW())"
    )
    return c


def test_plan_renames_covers_parents_and_children(con):
    pairs = dict(plan_renames(con))
    assert pairs["gameLines"] == "gql_game_lines"
    assert pairs["gameTeam__lineScores"] == "gql_game_team__line_scores"


def test_plan_renames_maps_legacy_gql_suffix(con):
    # stg.calendar_gql is the GraphQL calendar that lost the order-dependent clash.
    pairs = dict(plan_renames(con))
    assert pairs["calendar_gql"] == "gql_calendar"


def test_plan_renames_leaves_rest_tables_alone(con):
    pairs = dict(plan_renames(con))
    assert "games" not in pairs
    assert "calendar" not in pairs


def test_migrate_renames_tables_and_preserves_rows(con):
    migrate(con, dry_run=False)
    assert con.execute("SELECT id FROM stg.gql_game_lines").fetchall() == [(1,)]
    names = {r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='stg'"
    ).fetchall()}
    assert "gameLines" not in names
    assert "games" in names


def test_migrate_repairs_load_report(con):
    migrate(con, dry_run=False)
    rows = dict(con.execute("SELECT name, rows FROM meta.load_report").fetchall())
    assert rows["gql_game_lines"] == 63293
    assert "gameLines" not in rows
    assert rows["games"] == 54264


def test_migrate_is_idempotent(con):
    migrate(con, dry_run=False)
    second = migrate(con, dry_run=False)
    assert second == []


def test_dry_run_changes_nothing(con):
    planned = migrate(con, dry_run=True)
    assert planned
    names = {r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='stg'"
    ).fetchall()}
    assert "gameLines" in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_migrate_gql_stg_names.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.migrate_gql_stg_names'`

- [ ] **Step 3: Write the implementation**

Create `scripts/migrate_gql_stg_names.py`:

```python
"""Rename GraphQL-sourced stg tables to their explicit gql_ destinations.

One-shot and idempotent. `meta.load_report` keys on (schema, name), so renaming a table
without repairing the report desyncs the bookkeeping; both happen in one transaction.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cfb_system_maker.graphql_client import GQL_ENTITY_TO_STG  # noqa: E402


def plan_renames(con: duckdb.DuckDBPyConnection) -> list[tuple[str, str]]:
    existing = {
        row[0]
        for row in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'stg'"
        ).fetchall()
    }
    pairs: list[tuple[str, str]] = []
    for entity, dest in GQL_ENTITY_TO_STG.items():
        # `calendar_gql` is the legacy suffix the order-dependent helper produced when
        # the REST table won the bare name. Prefer it over the bare entity name, which
        # in that case belongs to REST and must not be touched.
        source = f"{entity}_gql" if f"{entity}_gql" in existing else entity
        if source in existing and source != dest:
            pairs.append((source, dest))
        for name in sorted(existing):
            if name.startswith(f"{entity}__"):
                child = name[len(entity):]
                pairs.append((name, dest + _snake_child(child)))
    return sorted(set(pairs))


def _snake_child(suffix: str) -> str:
    import re

    return re.sub(r"(?<!^)(?=[A-Z])", "_", suffix).lower()


def migrate(
    con: duckdb.DuckDBPyConnection, *, dry_run: bool
) -> list[tuple[str, str]]:
    pairs = plan_renames(con)
    if dry_run or not pairs:
        return pairs
    con.execute("BEGIN TRANSACTION")
    try:
        for old, new in pairs:
            con.execute(f'ALTER TABLE stg."{old}" RENAME TO "{new}"')
            con.execute(
                "UPDATE meta.load_report SET name = ? WHERE schema = 'stg' AND name = ?",
                [new, old],
            )
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    return pairs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/cfb.duckdb")
    ap.add_argument("--apply", action="store_true", help="without this, dry-run only")
    args = ap.parse_args()
    con = duckdb.connect(args.db, read_only=not args.apply)
    pairs = migrate(con, dry_run=not args.apply)
    verb = "renamed" if args.apply else "would rename"
    for old, new in pairs:
        print(f"  {old} -> {new}")
    print(f"{verb} {len(pairs)} tables")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_migrate_gql_stg_names.py -v`
Expected: 7 passed

- [ ] **Step 5: Run full suite**

Run: `python -m pytest`
Expected: 685 passed

- [ ] **Step 6: Commit**

```bash
git add scripts/migrate_gql_stg_names.py tests/test_migrate_gql_stg_names.py
git commit -m "feat(warehouse): add idempotent gql_ stg rename migration"
```

---

### Task 5: Run the migration against the live warehouse

**Files:**
- Modify: `data/cfb.duckdb` (not tracked in git)

**Interfaces:**
- Consumes: `scripts/migrate_gql_stg_names.py` from Task 4
- Produces: no code artifact; the live warehouse now matches the naming convention.

**This task mutates a 4.9 GB untracked database and must not be auto-committed or run unattended.** The user runs it and confirms the counts.

- [ ] **Step 1: Back up the warehouse**

```bash
cp data/cfb.duckdb data/cfb.duckdb.pre-gql-rename
```

- [ ] **Step 2: Dry-run the migration and read the plan**

```bash
python scripts/migrate_gql_stg_names.py --db data/cfb.duckdb
```

Expected: 38 pairs listed — 34 GraphQL parents (with `calendar_gql -> gql_calendar` among them) plus the 4 child tables `game__awayLineScores`, `game__homeLineScores`, `gameTeam__lineScores`, `historicalTeam__images`. No REST name (`games`, `coaches`, `calendar`, `draft_picks`) may appear on the left.

- [ ] **Step 3: Capture pre-migration row counts**

```bash
python -c "
import duckdb; c=duckdb.connect('data/cfb.duckdb', read_only=True)
print(sum(n for (n,) in c.sql(\"select estimated_size from duckdb_tables() where schema_name='stg'\").fetchall()))
print(c.sql(\"select count(*) from duckdb_tables() where schema_name='stg'\").fetchone())
"
```

Record both numbers.

- [ ] **Step 4: Apply the migration**

```bash
python scripts/migrate_gql_stg_names.py --db data/cfb.duckdb --apply
```

Expected: `renamed 38 tables`

- [ ] **Step 5: Verify totals are unchanged and no camelCase remains**

```bash
python -c "
import re, duckdb; c=duckdb.connect('data/cfb.duckdb', read_only=True)
tabs=[t for (t,) in c.sql(\"select table_name from duckdb_tables() where schema_name='stg'\").fetchall()]
print('tables:', len(tabs), 'rows:', sum(n for (n,) in c.sql(\"select estimated_size from duckdb_tables() where schema_name='stg'\").fetchall()))
print('camelCase left:', [t for t in tabs if re.search(r'[a-z][A-Z]', t)])
print('orphan load_report rows:', c.sql(\"select name from meta.load_report where schema='stg' and name not in (select table_name from duckdb_tables() where schema_name='stg')\").fetchall())
"
```

Expected: same table count and row total as Step 3; `camelCase left: []`; `orphan load_report rows: []`.

- [ ] **Step 6: Confirm a re-explode targets the new name**

The subcommand is `duckdb`, not `load` (`cfb_system_maker/cli.py:815`). `--explode-only` re-runs `explode_payloads` (raw → stg) without re-ingesting `raw`, which is the cheap check here. It **rewrites `stg.gql_game_lines` in place**; the Step 1 backup is what makes that safe, so do not delete it before this step passes.

`--only` matches on the **source** name in `raw`, not the destination — `raw` names are unchanged by this plan (R6), so `gameLines` is correct here. Do not "fix" it to `gql_game_lines`; after Task 2 the filter is `name not in only and dest not in only`, so either spelling happens to match, but `raw` is what is being read.

```bash
python -m cfb_system_maker duckdb --explode-only --only gameLines 2>&1 | tail -20
```

Expected: the report names `gql_game_lines`. If a table named `gameLines` reappears in `stg`, Task 2 missed a call site — restore from the backup and fix before continuing.

- [ ] **Step 7: Remove the backup once every check above has passed**

Only after Steps 5 and 6 are both green:

```bash
rm data/cfb.duckdb.pre-gql-rename
```

---

### Task 6: Canonical-source audit

**Files:**
- Create: `scripts/audit_canonical_sources.py`
- Test: `tests/test_audit_canonical_sources.py`

**Interfaces:**
- Consumes: the migrated warehouse from Task 5
- Produces: `concept_metrics(con, gql_table, rest_table) -> dict` with keys `gql_rows`, `rest_rows`, `gql_seasons`, `rest_seasons`, `gql_cols`, `rest_cols`, `gql_null_rate`, `rest_null_rate`. Consumed by Task 7's documentation.

Row count alone does not settle canonicity — `coaches` (1,936) exceeds `coach` (1,842) while `game` (112,672) doubles `games` (54,264). The criterion is season span first, then column coverage, then null density; the script reports all three and the human decides.

- [ ] **Step 1: Write the failing test**

Create `tests/test_audit_canonical_sources.py`:

```python
import duckdb
import pytest

from scripts.audit_canonical_sources import concept_metrics


@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    c.execute("CREATE SCHEMA stg")
    c.execute("CREATE TABLE stg.gql_game (id INTEGER, season INTEGER, venue VARCHAR)")
    c.execute("INSERT INTO stg.gql_game VALUES (1,2020,'A'),(2,2021,'B'),(3,2022,NULL)")
    c.execute("CREATE TABLE stg.games (id INTEGER, season INTEGER)")
    c.execute("INSERT INTO stg.games VALUES (1,2021),(2,2022)")
    return c


def test_concept_metrics_reports_season_span(con):
    m = concept_metrics(con, "gql_game", "games")
    assert m["gql_seasons"] == (2020, 2022)
    assert m["rest_seasons"] == (2021, 2022)


def test_concept_metrics_reports_row_and_column_counts(con):
    m = concept_metrics(con, "gql_game", "games")
    assert m["gql_rows"] == 3
    assert m["rest_rows"] == 2
    assert m["gql_cols"] == 3
    assert m["rest_cols"] == 2


def test_concept_metrics_handles_table_without_season(con):
    con.execute("CREATE TABLE stg.gql_hometown (id INTEGER)")
    con.execute("CREATE TABLE stg.hometowns (id INTEGER)")
    m = concept_metrics(con, "gql_hometown", "hometowns")
    assert m["gql_seasons"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_audit_canonical_sources.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

Create `scripts/audit_canonical_sources.py`:

```python
"""Report coverage metrics for each GraphQL/REST table pair.

Designating a canonical source is a judgement call; this script supplies the evidence
and deliberately does not pick a winner. Row count alone is misleading — REST `coaches`
has more rows than GraphQL `coach`, while GraphQL `game` has twice the rows of `games`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# (concept, gql_table, rest_table) — the pairs the spec identified.
PAIRS = [
    ("game", "gql_game", "games"),
    ("coach", "gql_coach", "coaches"),
    ("conference", "gql_conference", "conferences"),
    ("draft_pick", "gql_draft_picks", "draft_picks"),
    ("draft_position", "gql_draft_position", "draft_positions"),
    ("draft_team", "gql_draft_team", "draft_teams"),
    ("recruit", "gql_recruit", "recruits"),
    ("recruiting_team", "gql_recruiting_team", "recruiting_teams"),
    ("coach_season", "gql_coach_season", "coach_seasons"),
    ("predicted_points", "gql_predicted_points", "predicted_points"),
    ("talent", "gql_team_talent", "talent"),
    ("lines", "gql_game_lines", "lines"),
    ("calendar", "gql_calendar", "calendar"),
]


def _cols(con: duckdb.DuckDBPyConnection, table: str) -> list[str]:
    return [
        row[0]
        for row in con.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'stg' AND table_name = ?",
            [table],
        ).fetchall()
    ]


def _seasons(
    con: duckdb.DuckDBPyConnection, table: str, cols: list[str]
) -> tuple[int, int] | None:
    if "season" not in cols:
        return None
    row = con.execute(f'SELECT MIN(season), MAX(season) FROM stg."{table}"').fetchone()
    return None if row is None or row[0] is None else (int(row[0]), int(row[1]))


def _null_rate(
    con: duckdb.DuckDBPyConnection, table: str, cols: list[str]
) -> float | None:
    if not cols:
        return None
    total = con.execute(f'SELECT COUNT(*) FROM stg."{table}"').fetchone()[0]
    if not total:
        return None
    parts = " + ".join(f'COUNT("{c}")' for c in cols)
    filled = con.execute(f'SELECT {parts} FROM stg."{table}"').fetchone()[0]
    return round(1 - (filled / (total * len(cols))), 4)


def concept_metrics(
    con: duckdb.DuckDBPyConnection, gql_table: str, rest_table: str
) -> dict:
    gcols, rcols = _cols(con, gql_table), _cols(con, rest_table)
    return {
        "gql_rows": con.execute(f'SELECT COUNT(*) FROM stg."{gql_table}"').fetchone()[0],
        "rest_rows": con.execute(f'SELECT COUNT(*) FROM stg."{rest_table}"').fetchone()[0],
        "gql_cols": len(gcols),
        "rest_cols": len(rcols),
        "gql_seasons": _seasons(con, gql_table, gcols),
        "rest_seasons": _seasons(con, rest_table, rcols),
        "gql_null_rate": _null_rate(con, gql_table, gcols),
        "rest_null_rate": _null_rate(con, rest_table, rcols),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/cfb.duckdb")
    args = ap.parse_args()
    con = duckdb.connect(args.db, read_only=True)
    present = {
        row[0]
        for row in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'stg'"
        ).fetchall()
    }
    print("| concept | gql rows | rest rows | gql seasons | rest seasons "
          "| gql cols | rest cols | gql null | rest null |")
    print("|---|---|---|---|---|---|---|---|---|")
    for concept, g, r in PAIRS:
        if g not in present or r not in present:
            print(f"| {concept} | MISSING ({g} or {r}) | | | | | | | |")
            continue
        m = concept_metrics(con, g, r)
        print(
            f"| {concept} | {m['gql_rows']} | {m['rest_rows']} | {m['gql_seasons']} "
            f"| {m['rest_seasons']} | {m['gql_cols']} | {m['rest_cols']} "
            f"| {m['gql_null_rate']} | {m['rest_null_rate']} |"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_audit_canonical_sources.py -v`
Expected: 3 passed

- [ ] **Step 5: Run against the live warehouse and save the output**

```bash
python scripts/audit_canonical_sources.py --db data/cfb.duckdb
```

Copy the emitted markdown table — Task 7 pastes it into the docs.

- [ ] **Step 6: Run full suite**

Run: `python -m pytest`
Expected: 688 passed

- [ ] **Step 7: Commit**

```bash
git add scripts/audit_canonical_sources.py tests/test_audit_canonical_sources.py
git commit -m "feat(warehouse): add canonical-source coverage audit"
```

---

### Task 7: Document the convention and the canonical designations

**Files:**
- Create: `docs/warehouse-naming.md`
- Modify: `CLAUDE.md` (append one bullet to "Shared rules")
- Modify: `docs/raw-stg-classification.md` (note the rename)

**Interfaces:**
- Consumes: the audit table from Task 6 Step 5
- Produces: the documented convention; no code artifact.

- [ ] **Step 1: Write `docs/warehouse-naming.md`**

Create the file with these sections, filling the audit table from Task 6 Step 5:

```markdown
# Warehouse naming

## Convention

| Layer | Convention | Rationale |
|---|---|---|
| `raw` | Source name verbatim | Preserves source fidelity; `raw` is a JSON landing zone |
| `stg` (REST) | snake_case, plural, endpoint name | Matches the CFBD REST path |
| `stg` (GraphQL) | `gql_<snake_case_entity>` | snake_case, and provenance is legible at the call site |
| `core` | `dim_*` / `fact_*`, snake_case | Conformed model |
| `meta` | snake_case | Bookkeeping |

GraphQL entity names are an upstream API contract. `GQL_ENTITY_TO_STG` in
`cfb_system_maker/graphql_client.py` is the only place the mapping to `stg` names lives;
add an entry there when adding a GraphQL entity.

## Why `game` and `games` both exist

They are different sources, not duplicates: `gql_game` comes from the GraphQL `game` root
field, `games` from the REST `/games` endpoint. Coverage differs. See the canonical table
below before choosing one for a feature.

## Canonical source per concept

<!-- paste the table emitted by scripts/audit_canonical_sources.py, then add a
     "canonical" column with the chosen source and a one-line reason each -->

Criterion, in order: season span, then column coverage, then null density. Row count is
not a criterion on its own.

## Deprecation

None yet. Non-canonical tables remain in place. Removing them is a separate change.
```

- [ ] **Step 2: Fill the canonical column**

For each row of the pasted audit table, add a `canonical` column naming the chosen source and a one-line reason. Where the audit shows the GraphQL table strictly dominating on season span and column coverage, choose it. Where the two disagree across criteria (for example REST has more rows but a narrower season span), write `undecided` and state what additional check would settle it — do not guess.

- [ ] **Step 3: Add the shared rule**

Append to the "Shared rules" list in root `CLAUDE.md`:

```markdown
- `stg` tables from the GraphQL source are named `gql_<snake_case_entity>`; REST tables keep
  their snake_case endpoint name. The mapping lives in `GQL_ENTITY_TO_STG`
  (`cfb_system_maker/graphql_client.py`). See `docs/warehouse-naming.md`.
```

- [ ] **Step 4: Note the rename in the classification doc**

Append to `docs/raw-stg-classification.md`:

```markdown
## Naming update (2026-08-31)

GraphQL-sourced `stg` tables were renamed to `gql_<snake_case>`; `raw` names are unchanged.
The camelCase names in this document's tables refer to the pre-rename schema. See
`docs/warehouse-naming.md`.
```

- [ ] **Step 5: Verify the docs reference only names that exist**

```bash
python -c "
import re, duckdb
c = duckdb.connect('data/cfb.duckdb', read_only=True)
have = {t for (t,) in c.sql(\"select table_name from duckdb_tables() where schema_name='stg'\").fetchall()}
txt = open('docs/warehouse-naming.md', encoding='utf-8').read()
named = set(re.findall(r'\bgql_[a-z0-9_]+', txt))
print('named but absent:', sorted(named - have))
"
```

Expected: `named but absent: []`

- [ ] **Step 6: Commit**

```bash
git add docs/warehouse-naming.md CLAUDE.md docs/raw-stg-classification.md
git commit -m "docs(warehouse): record gql_ naming convention and canonical sources"
```

---

### Task 8: Re-promote the renamed tables to the MotherDuck mirror

**Files:**
- Modify: `md:cfb` (remote mirror; no local artifact)

**Interfaces:**
- Consumes: the migrated warehouse from Task 5
- Produces: nothing local.

`md:cfb` holds the 248 tables promoted on 2026-08-31 under the old camelCase names. After Task 5 the mirror is stale: it has both the old names and none of the new ones. `scripts/promote_to_motherduck.py` reads its token from `env.env` per repo convention.

**This task writes to a remote service. Run it only with the user's explicit go-ahead.**

- [ ] **Step 1: List the stale camelCase tables on the mirror**

```bash
python -c "
import re, duckdb, os
con = duckdb.connect('md:cfb')
tabs = [t for (t,) in con.sql(\"select table_name from duckdb_tables() where schema_name='stg'\").fetchall()]
print('camelCase on mirror:', sorted(t for t in tabs if re.search(r'[a-z][A-Z]', t)))
"
```

Expected: the 34 parents plus 4 children, matching Task 5 Step 2's left column.

- [ ] **Step 2: Promote the renamed tables**

```bash
python scripts/promote_to_motherduck.py --schema stg
```

- [ ] **Step 3: Verify parity before dropping anything**

Parity is checked *before* the drop, so the drop list is derived from proof rather than judgement. `extra on mirror` is the candidate drop list; `missing on mirror` must be empty before proceeding.

```bash
python -c "
import duckdb
loc = duckdb.connect('data/cfb.duckdb', read_only=True)
rem = duckdb.connect('md:cfb')
q = \"select table_name, estimated_size from duckdb_tables() where schema_name='stg'\"
l = dict(loc.sql(q).fetchall()); r = dict(rem.sql(q).fetchall())
print('missing on mirror:', sorted(set(l) - set(r)))
print('extra on mirror:', sorted(set(r) - set(l)))
print('count mismatches:', {k: (l[k], r[k]) for k in set(l) & set(r) if l[k] != r[k]})
"
```

Expected: `missing on mirror: []` and `count mismatches: {}`. `extra on mirror` should list exactly the 38 old camelCase names from Step 1.

**If `missing on mirror` is non-empty, stop.** Step 2 did not promote everything, and dropping now would lose data the local DB would have to re-promote.

- [ ] **Step 4: Drop only the proven-superseded tables**

This drops a table only when its `gql_` replacement exists on the mirror with a matching row count. Anything else is reported and left alone.

The stale list is derived from `GQL_ENTITY_TO_STG`, not from a casing regex. A regex misses both `calendar_gql` (no camelCase) and the eleven all-lowercase entities (`game`, `coach`, `poll`, `athlete`, `recruit`, `ratings`, `transfer`, `conference`, `hometown`, `position`, `calendar`). Intersecting with `extra on mirror` is what keeps the REST `calendar`, which the local DB still has, from being considered.

Save as `scripts/drop_stale_mirror_tables.py` and run it — it is too long to be a safe one-liner:

```python
"""Drop mirror tables superseded by the gql_ rename. Proof-gated: a table is dropped
only when its replacement exists on the mirror with a matching local row count."""

import re
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cfb_system_maker.graphql_client import GQL_ENTITY_TO_STG  # noqa: E402

loc = duckdb.connect("data/cfb.duckdb", read_only=True)
rem = duckdb.connect("md:cfb")
Q = "select table_name, estimated_size from duckdb_tables() where schema_name='stg'"
local = dict(loc.sql(Q).fetchall())
mirror = dict(rem.sql(Q).fetchall())
extra = set(mirror) - set(local)


def snake(x: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", x).lower()


# old mirror name -> new name, for parents and their __ children
expected: dict[str, str] = {}
for entity, dst in GQL_ENTITY_TO_STG.items():
    expected[entity] = dst
    expected[f"{entity}_gql"] = dst           # legacy clash suffix, e.g. calendar_gql
    for name in mirror:
        if name.startswith(f"{entity}__"):
            expected[name] = dst + snake(name[len(entity):])

dropped = kept = 0
for name in sorted(extra):
    new = expected.get(name)
    if new and new in mirror and new in local and mirror[new] == local[new]:
        rem.execute(f'DROP TABLE stg."{name}"')
        print(f"dropped {name} (superseded by {new})")
        dropped += 1
    else:
        print(f"KEPT {name} - replacement {new or '(unmapped)'} absent or count mismatch")
        kept += 1
print(f"\n{dropped} dropped, {kept} kept")
```

```bash
python scripts/drop_stale_mirror_tables.py
```

Expected: `38 dropped, 0 kept`. Investigate any `KEPT` line before rerunning — an unmapped name means the mirror holds something this plan did not create.

- [ ] **Step 5: Re-verify parity**

Re-run the Step 3 command.

Expected: all three empty.

---

## Self-Review

**Spec coverage.** R1 → Task 1. R2 → Tasks 1, 4. R3 → Task 1 Step 3 comment plus Task 2's pass-through behaviour; no task edits `GQL_DEFAULT_TABLES`, query text, or JSON filenames. R4 → Task 4's `migrate` and its `test_migrate_repairs_load_report`. R5 → Tasks 6 and 7 Step 2, with deprecation explicitly deferred in Task 7 Step 1. R6 → no task touches `raw`; Task 4's `plan_renames` reads only `table_schema = 'stg'`.

**Type consistency.** `GQL_ENTITY_TO_STG: dict[str, str]` is defined in Task 1 and consumed unchanged in Tasks 2 and 4. `stg_dest_name(name: str) -> str` is defined in Task 2 (public, no underscore, no `taken` argument) and used in Tasks 2 and 3 only. `plan_renames` / `migrate` signatures in Task 4's tests match the implementation in the same task. `concept_metrics` returns the eight keys Task 6's tests assert and Task 6's `main()` reads.

**Known soft spot.** Task 4's `plan_renames` builds child-table pairs inside the loop over entities, so a child of an entity whose parent is absent is still renamed. That is intentional — an orphaned child should follow the convention — but it means the returned list is deduplicated via `sorted(set(pairs))` rather than being unique by construction. Task 5 Step 2's expected count of 38 is the check that catches any surprise.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-31-warehouse-naming-rationalization.md`. Two execution options:

**1. Subagent-Driven (recommended)** — a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Note that Tasks 5 and 8 mutate the live warehouse and the remote mirror; both are gated on explicit user go-ahead regardless of execution mode.
