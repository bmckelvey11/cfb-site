# Warehouse Source Rationalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the two unjoinable GraphQL tables, remove 308 dead scaffolding columns, merge the seven complementary source pairs, and drop only what is provably superseded.

**Architecture:** `stg` holds 13 concept pairs, one GraphQL table and one REST table each. Measurement refutes the "GraphQL is a superset" hypothesis for 10 of 13 pairs and reverses it for 3. Underneath sits a scraper defect: `coachSeason` and `teamTalent` are pulled without the relation carrying their identity, so they are unjoinable and their pagination is not provably stable. The fix sequence is therefore scraper → scaffolding → re-measure → merge → drop, because dropping before re-measuring risks deleting the table that the scraper fix would have made canonical.

**Tech Stack:** Python 3, DuckDB 1.5.2, pytest, CFBD GraphQL API (Hasura)

**Spec:** `docs/superpowers/specs/2026-09-01-warehouse-source-rationalization.md`

## Global Constraints

- `CFB_DATA_ROOT` is required; paths resolve through root `cfb_paths.py`. Local `data/cfb.duckdb` is source of truth; `md:cfb` is a manual mirror.
- Data is never committed. Only code, tests, and docs enter git.
- Do not edit `cfbd-python/` — vendored upstream.
- Run all commands from repository root.
- Default verification: `python -m pytest`. Test counts in this plan are **deltas** against whatever baseline is current, not absolutes.
- This plan uses **current live table names** (`coachSeason`, `gameLines`, …). The sibling naming plan (`2026-08-31-warehouse-naming-rationalization.md`) renames these to `gql_<snake_case>`. The two are independent; whichever lands second applies the other's names. If naming landed first, map every `stg` name here through `GQL_ENTITY_TO_STG`.
- Tasks 2, 6, 8, 9, 10 mutate the live warehouse or hit the live API. **None of them auto-run or auto-commit** — the user executes each explicitly.
- No lookahead: pre-game features use only pre-kickoff information.

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `cfb_system_maker/graphql_client.py` | Add `coachSeason` / `teamTalent` entries to `GQL_RELATION_KEYS`. | 1 |
| `tests/test_graphql.py` | Assert both entities select and sort through their relation keys. | 1 |
| `cfb_system_maker/duckdb_load.py` | Prune all-NULL scaffolding columns in `_finish_stg_table`. | 3 |
| `tests/test_duckdb_load.py` | Assert scaffolding pruning drops only scaffolding, never payload columns. | 3 |
| `scripts/measure_pair_containment.py` | Bidirectional column containment + fill rates per pair; the gate for drops. | 5 |
| `tests/test_measure_pair_containment.py` | Containment logic correctness. | 5 |
| `cfb_system_maker/duckdb_load.py` | `build_merged_pairs()` — one merged table per Bucket C concept. | 7 |
| `tests/test_merge_pairs.py` | Merge preserves every populated column and every key from both sides. | 7 |
| `scripts/drop_superseded.py` | Proof-gated table drops. | 9 |
| `docs/warehouse-sources.md` | Per-concept canonical record and what was dropped. | 11 |

---

### Task 1: Give `coachSeason` and `teamTalent` their relation keys

**Files:**
- Modify: `cfb_system_maker/graphql_client.py:44-50` (`GQL_RELATION_KEYS`)
- Test: `tests/test_graphql.py`

**Interfaces:**
- Consumes: `_selection`, `_order_clause` (existing, `graphql_client.py`)
- Produces: two new `GQL_RELATION_KEYS` entries. No new symbols.

`docs/graphql-schema-draft.md:119` states `coachSeason.coach`, `coachSeason.team`, and `teamTalent.team` expose the relation only. Both entities' FKs resolve to `currentTeams`, keyed by `teamId` (`graphql-schema-draft.md:108`). The `Coach` root's scalar id is `id`, renamed to `coachId` on load (`_BARE_ID_RENAME`, `duckdb_load.py`).

Relation keys are used for **both** selection and ordering (`graphql_client.py:156-180`), so this also gives these two tables a total sort order they currently lack.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_graphql.py`:

```python
def test_coach_season_selects_and_sorts_through_its_relations(tmp_path):
    """coachSeason has no id and no team/coach scalar — its identity lives entirely in
    relations. Without them the dump is unjoinable AND the sort is not a total order,
    so paginated pulls can drop rows between pages."""
    captured = {}
    data = {"coachSeason": [{"season": 2023, "wins": 9, "losses": 3}]}
    graphql_scrape(
        data_dir=tmp_path, tables=["coachSeason"], post_fn=make_post(data, captured)
    )
    q = captured["coachSeason"]

    assert "coach { id }" in q
    assert "team { teamId }" in q
    assert "{coach: {id: ASC}}" in q
    assert "{team: {teamId: ASC}}" in q
    assert q.index("{coach: {id: ASC}}") < q.index("{season: ASC}")


def test_team_talent_selects_and_sorts_through_its_team_relation(tmp_path):
    captured = {}
    data = {"teamTalent": [{"season": 2023, "talent": 900.5}]}
    graphql_scrape(
        data_dir=tmp_path, tables=["teamTalent"], post_fn=make_post(data, captured)
    )
    q = captured["teamTalent"]

    assert "team { teamId }" in q
    assert "{team: {teamId: ASC}}" in q


def test_every_relation_only_entity_has_relation_keys():
    """Guard against the gameMedia/coachSeason failure mode returning: an entity in the
    default pull whose identity is relation-only must have an entry here."""
    from cfb_system_maker.graphql_client import (
        GQL_DEFAULT_TABLES,
        GQL_RELATION_KEYS,
    )

    relation_only = {"pollRank", "coachSeason", "teamTalent"}
    for entity in relation_only:
        assert entity in GQL_DEFAULT_TABLES, f"{entity} dropped from the default pull"
        assert GQL_RELATION_KEYS.get(entity), f"{entity} has no relation keys"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_graphql.py -k "coach_season or team_talent or relation_only" -v`
Expected: FAIL — `"coach { id }" in q` is False; `GQL_RELATION_KEYS.get("coachSeason")` is None.

- [ ] **Step 3: Add the relation keys**

In `cfb_system_maker/graphql_client.py`, extend `GQL_RELATION_KEYS` (currently ending at line 50):

```python
GQL_RELATION_KEYS: dict[str, dict[str, list[str]]] = {
    "pollRank": {
        # `pollType` separates the AP and Coaches polls, which otherwise produce
        # byte-identical rows whenever both rank a team the same in the same week.
        "poll": ["season", "seasonType", "week", "pollType.name"],
        "team": ["school", "conference", "classification"],
    },
    # coachSeason's scalars are (season, year, week, seasonType, games, wins, losses,
    # ties, preseasonRank, postseasonRank) — nothing that says *whose* season. Both FKs
    # are relation-only (docs/graphql-schema-draft.md:119). Without these the dump cannot
    # be joined to anything and the sort is not a total order.
    "coachSeason": {
        "coach": ["id"],
        "team": ["teamId"],
    },
    # teamTalent's only non-scaffolding scalar is `talent`, so every team sharing a talent
    # value ties — ties break per request and paginated pulls can skip rows.
    "teamTalent": {
        "team": ["teamId"],
    },
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_graphql.py -k "coach_season or team_talent or relation_only" -v`
Expected: 3 passed

- [ ] **Step 5: Run full suite**

Run: `python -m pytest`
Expected: baseline + 3 passed

- [ ] **Step 6: Commit**

```bash
git add cfb_system_maker/graphql_client.py tests/test_graphql.py
git commit -m "fix(graphql): give coachSeason and teamTalent their relation keys"
```

---

### Task 2: Re-scrape the two repaired entities

**Files:**
- Modify: `data/graphql/coachSeason.json`, `data/graphql/teamTalent.json` (untracked)

**Interfaces:**
- Consumes: the relation keys from Task 1
- Produces: re-pulled dumps carrying FK columns.

**Hits the live CFBD GraphQL API and needs a token. User-run only.**

- [ ] **Step 1: Back up the current dumps**

```bash
cp data/graphql/coachSeason.json data/graphql/coachSeason.json.bak
cp data/graphql/teamTalent.json data/graphql/teamTalent.json.bak
```

- [ ] **Step 2: Record the current row counts**

```bash
python -c "
import json
for t in ('coachSeason','teamTalent'):
    d=json.load(open(f'data/graphql/{t}.json', encoding='utf-8'))
    print(t, len(d), 'keys:', sorted(d[0]) if d else '(empty)')
"
```

Expected: `coachSeason 12564`, `teamTalent 2413`, with no coach/team key in either.

- [ ] **Step 3: Re-scrape**

```bash
python -m cfb_system_maker graphql --only coachSeason teamTalent
```

- [ ] **Step 4: Verify the FK columns arrived and compare row counts**

```bash
python -c "
import json
for t in ('coachSeason','teamTalent'):
    d=json.load(open(f'data/graphql/{t}.json', encoding='utf-8'))
    print(t, len(d), 'keys:', sorted(d[0]) if d else '(empty)')
"
```

Expected: `coachSeason` rows carry `coach` and `team`; `teamTalent` rows carry `team`.

**Row counts may go up.** The old sort was not a total order, so the previous pull may have skipped rows. A higher count confirms the pagination bug was real. A *lower* count is a red flag — stop and investigate before proceeding.

- [ ] **Step 5: Reload into the warehouse**

```bash
cp data/cfb.duckdb data/cfb.duckdb.pre-rescrape
python -m cfb_system_maker duckdb --only coachSeason teamTalent
```

- [ ] **Step 6: Confirm the stg tables now carry identity**

```bash
python -c "
import duckdb; c=duckdb.connect('data/cfb.duckdb', read_only=True)
for t in ('coachSeason','teamTalent'):
    cols=[r[0] for r in c.sql(f\"select column_name from information_schema.columns where table_schema='stg' and table_name='{t}'\").fetchall()]
    n=c.sql(f'select count(*) from stg.\"{t}\"').fetchone()[0]
    print(t, n, cols)
"
```

Expected: `coachSeason` has a coach id column and a `teamId`; `teamTalent` has a `teamId`. If either is still missing, Task 1's relation keys did not survive into the dump — stop.

- [ ] **Step 7: Keep the backups until Task 6 passes**

Do not delete `*.bak` or `cfb.duckdb.pre-rescrape` yet.

---

### Task 3: Stop materializing all-NULL scaffolding columns

**Files:**
- Modify: `cfb_system_maker/duckdb_load.py` — `_finish_stg_table` (line 1304)
- Test: `tests/test_duckdb_load.py`

**Interfaces:**
- Consumes: nothing new
- Produces: `prune_null_scaffolding(con, dest) -> list[str]` — drops the scaffolding columns that are entirely NULL for one `stg` table and returns their names. Called from `_finish_stg_table`.

`_insert_raw_file` (`duckdb_load.py:1565-1585`) binds `season`, `week`, `season_type` from `parse_dump_stem(path.stem)`. GraphQL dumps have no season or week in the stem; REST season dumps have no week. Those NULLs reach `stg` and account for 308 of the 332 all-NULL columns.

Only those three names are ever pruned. A payload column that happens to be all-NULL is left alone — that is data telling you something, not scaffolding.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_duckdb_load.py`:

```python
from cfb_system_maker.duckdb_load import prune_null_scaffolding


def _scaffold_table(con, *, season, week, season_type, payload_col=None):
    con.execute("CREATE SCHEMA IF NOT EXISTS stg")
    con.execute("DROP TABLE IF EXISTS stg.t")
    con.execute(
        "CREATE TABLE stg.t "
        "(season INTEGER, week INTEGER, season_type VARCHAR, wins INTEGER, dead VARCHAR)"
    )
    con.execute(
        "INSERT INTO stg.t VALUES (?, ?, ?, ?, ?)",
        [season, week, season_type, 9, payload_col],
    )
    return con


def test_prune_drops_scaffolding_that_is_entirely_null():
    con = duckdb.connect(":memory:")
    _scaffold_table(con, season=None, week=None, season_type=None)
    dropped = prune_null_scaffolding(con, "t")
    assert set(dropped) == {"season", "week", "season_type"}
    cols = {r[0] for r in con.execute("DESCRIBE stg.t").fetchall()}
    assert cols == {"wins", "dead"}


def test_prune_keeps_scaffolding_that_has_any_value():
    con = duckdb.connect(":memory:")
    _scaffold_table(con, season=2023, week=None, season_type=None)
    dropped = prune_null_scaffolding(con, "t")
    assert set(dropped) == {"week", "season_type"}
    cols = {r[0] for r in con.execute("DESCRIBE stg.t").fetchall()}
    assert "season" in cols


def test_prune_never_drops_a_payload_column():
    # `dead` is 100% NULL but is payload, not scaffolding. An all-NULL payload column is
    # a finding to report, not something the loader should silently delete.
    con = duckdb.connect(":memory:")
    _scaffold_table(con, season=2023, week=1, season_type="regular", payload_col=None)
    dropped = prune_null_scaffolding(con, "t")
    assert dropped == []
    cols = {r[0] for r in con.execute("DESCRIBE stg.t").fetchall()}
    assert "dead" in cols


def test_prune_is_a_noop_on_an_empty_table():
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA IF NOT EXISTS stg")
    con.execute("CREATE TABLE stg.t (season INTEGER, wins INTEGER)")
    assert prune_null_scaffolding(con, "t") == []
    cols = {r[0] for r in con.execute("DESCRIBE stg.t").fetchall()}
    assert "season" in cols
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_duckdb_load.py -k prune -v`
Expected: FAIL with `ImportError: cannot import name 'prune_null_scaffolding'`

- [ ] **Step 3: Write the implementation**

Add to `cfb_system_maker/duckdb_load.py`, immediately above `_finish_stg_table`:

```python
# Columns the loader binds from the filename stem rather than from the payload. A GraphQL
# dump has no season/week in its stem and a REST season dump has no week, so these arrive
# NULL and stay NULL — 308 of the 332 all-NULL stg columns. Payload columns are never
# pruned by this rule: an all-NULL payload column is a finding, not scaffolding.
_SCAFFOLD_COLS = ("season", "week", "season_type")


def prune_null_scaffolding(con: duckdb.DuckDBPyConnection, dest: str) -> list[str]:
    """Drop scaffolding columns that are entirely NULL for this table."""
    table = _qualify("stg", dest)
    present = [row[0] for row in con.execute(f"DESCRIBE {table}").fetchall()]
    candidates = [c for c in _SCAFFOLD_COLS if c in present]
    if not candidates:
        return []
    counts = con.execute(
        f"SELECT COUNT(*), "
        + ", ".join(f'COUNT("{c}")' for c in candidates)
        + f" FROM {table}"
    ).fetchone()
    if not counts[0]:
        # An empty table tells us nothing about which columns will be populated.
        return []
    dropped = [c for c, filled in zip(candidates, counts[1:]) if filled == 0]
    for col in dropped:
        con.execute(f"ALTER TABLE {table} DROP COLUMN {_ident(col)}")
    return dropped
```

Then call it from `_finish_stg_table`, after the id rename and before the reorder:

```python
def _finish_stg_table(
    con: duckdb.DuckDBPyConnection, dest: str, target: str
) -> TableLoad:
    _rename_stg_table_ids(con, dest)
    prune_null_scaffolding(con, dest)
    ordered = _reorder_stg_table(con, dest)
    if ordered.error:
        return ordered
    rows = con.execute(f"SELECT COUNT(*) FROM {target}").fetchone()[0]
    return TableLoad("stg", dest, 1, int(rows))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_duckdb_load.py -k prune -v`
Expected: 4 passed

- [ ] **Step 5: Check nothing reads a scaffolding column that will now disappear**

```bash
grep -rnE '\.(season_type|week)\b' --include=*.py cfb_system_maker models research scripts \
  | grep -vE 'cfbd-python|test_|duckdb_load\.py' | head -30
```

Review each hit: a reference to `stg.<table>.week` on a table where `week` is all-NULL would now fail. Any such reference was already reading NULL and should be fixed or removed — note it, do not silently leave it.

- [ ] **Step 6: Run full suite**

Run: `python -m pytest`
Expected: baseline + 7 passed (3 from Task 1, 4 here)

- [ ] **Step 7: Commit**

```bash
git add cfb_system_maker/duckdb_load.py tests/test_duckdb_load.py
git commit -m "fix(warehouse): stop materializing all-NULL scaffolding columns in stg"
```

---

### Task 4: Rebuild `stg` so the pruning applies everywhere

**Files:**
- Modify: `data/cfb.duckdb` (untracked)

**Interfaces:**
- Consumes: Task 3's pruning
- Produces: an `stg` with the scaffolding columns gone.

**Mutates the live warehouse. User-run only.** Task 3 only prunes at load time; existing tables keep their dead columns until rebuilt.

- [ ] **Step 1: Record the current column count**

```bash
python -c "
import duckdb; c=duckdb.connect('data/cfb.duckdb', read_only=True)
print('stg columns:', c.sql(\"select count(*) from information_schema.columns where table_schema='stg'\").fetchone()[0])
"
```

Record it.

- [ ] **Step 2: Re-explode `stg` from `raw`**

`raw` is untouched by this plan, so this rebuilds `stg` without re-ingesting anything.

```bash
python -m cfb_system_maker duckdb --explode-only
```

- [ ] **Step 3: Verify the scaffolding columns are gone and nothing else was lost**

```bash
python -c "
import duckdb
from collections import defaultdict
c=duckdb.connect('data/cfb.duckdb', read_only=True)
n=c.sql(\"select count(*) from information_schema.columns where table_schema='stg'\").fetchone()[0]
rows=c.sql(\"select table_name, column_name from information_schema.columns where table_schema='stg'\").fetchall()
sizes={t:s for t,s in c.sql(\"select table_name,estimated_size from duckdb_tables() where schema_name='stg'\").fetchall()}
bytab=defaultdict(list)
for t,col in rows: bytab[t].append(col)
dead=0
for t,cs in bytab.items():
    if not sizes.get(t): continue
    v=c.sql(f'select count(*), '+', '.join(f'count(\"{x}\")' for x in cs)+f' from stg.\"{t}\"').fetchone()
    dead += sum(1 for f in v[1:] if v[0] and f==0)
print('stg columns now:', n, '| all-NULL columns now:', dead)
"
```

Expected: column count down by roughly 308; all-NULL count down to about 24 (the 12 future-dated lines columns plus the 12 real dead ones).

- [ ] **Step 4: Run full suite against the rebuilt warehouse**

Run: `python -m pytest`
Expected: all pass. A failure here means something read a column that is now correctly gone — fix the reader.

---

### Task 5: Re-measure pair containment

**Files:**
- Create: `scripts/measure_pair_containment.py`
- Test: `tests/test_measure_pair_containment.py`

**Interfaces:**
- Consumes: the repaired warehouse from Tasks 2 and 4
- Produces: `pair_containment(con, gql, rest) -> dict` with keys `gql_only`, `rest_only`, `shared`, `gql_rows`, `rest_rows` — where `gql_only` / `rest_only` are lists of `(column, fill_rate)` for **populated** exclusive columns only. Consumed by Task 9's drop gate and Task 11's docs.

Column names are compared case- and underscore-insensitively, because the two sources spell the same concept `season_type` and `seasonType`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_measure_pair_containment.py`:

```python
import duckdb
import pytest

from scripts.measure_pair_containment import pair_containment


@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    c.execute("CREATE SCHEMA stg")
    c.execute("CREATE TABLE stg.g (id INTEGER, onlyG VARCHAR, shared VARCHAR, deadG VARCHAR)")
    c.execute("INSERT INTO stg.g VALUES (1,'a','s',NULL),(2,'b','s',NULL)")
    c.execute("CREATE TABLE stg.r (id INTEGER, only_r VARCHAR, shared VARCHAR)")
    c.execute("INSERT INTO stg.r VALUES (1,'x','s')")
    return c


def test_reports_exclusive_columns_each_way(con):
    m = pair_containment(con, "g", "r")
    assert [c for c, _ in m["gql_only"]] == ["onlyG"]
    assert [c for c, _ in m["rest_only"]] == ["only_r"]


def test_excludes_all_null_exclusive_columns(con):
    # deadG is exclusive to the GraphQL side but 100% NULL, so it is not evidence of
    # anything — counting it would make a table look like a superset when it is not.
    m = pair_containment(con, "g", "r")
    assert "deadG" not in [c for c, _ in m["gql_only"]]


def test_shared_columns_match_across_casing_and_underscores(con):
    con.execute("CREATE TABLE stg.g2 (seasonType VARCHAR)")
    con.execute("INSERT INTO stg.g2 VALUES ('regular')")
    con.execute("CREATE TABLE stg.r2 (season_type VARCHAR)")
    con.execute("INSERT INTO stg.r2 VALUES ('regular')")
    m = pair_containment(con, "g2", "r2")
    assert m["gql_only"] == [] and m["rest_only"] == []


def test_reports_row_counts(con):
    m = pair_containment(con, "g", "r")
    assert m["gql_rows"] == 2 and m["rest_rows"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_measure_pair_containment.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

Create `scripts/measure_pair_containment.py`:

```python
"""Bidirectional column containment for each GraphQL/REST pair in stg.

This is the gate for dropping a table: a side is droppable only when it has no populated
exclusive columns. An all-NULL exclusive column is not evidence — stg.recruit's two
GraphQL-only columns are 100% NULL, so the GraphQL table adds nothing despite the diff.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# (concept, gql_table, rest_table) — current live names; see the plan's naming note.
PAIRS = [
    ("game", "game", "games"),
    ("coach", "coach", "coaches"),
    ("conference", "conference", "conferences"),
    ("draft_pick", "draftPicks", "draft_picks"),
    ("draft_position", "draftPosition", "draft_positions"),
    ("draft_team", "draftTeam", "draft_teams"),
    ("recruit", "recruit", "recruits"),
    ("recruiting_team", "recruitingTeam", "recruiting_teams"),
    ("coach_season", "coachSeason", "coach_seasons"),
    ("predicted_points", "predictedPoints", "predicted_points"),
    ("talent", "teamTalent", "talent"),
    ("lines", "gameLines", "lines"),
    ("calendar", "calendar_gql", "calendar"),
]


def _norm(name: str) -> str:
    return name.lower().replace("_", "")


def _cols(con: duckdb.DuckDBPyConnection, table: str) -> list[str]:
    return [
        r[0]
        for r in con.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'stg' AND table_name = ? ORDER BY ordinal_position",
            [table],
        ).fetchall()
    ]


def _fills(
    con: duckdb.DuckDBPyConnection, table: str, cols: list[str]
) -> tuple[int, dict[str, float]]:
    if not cols:
        return 0, {}
    parts = ", ".join(f'COUNT("{c}")' for c in cols)
    row = con.execute(f'SELECT COUNT(*), {parts} FROM stg."{table}"').fetchone()
    total = row[0]
    if not total:
        return 0, {c: 0.0 for c in cols}
    return total, {c: round(f / total, 3) for c, f in zip(cols, row[1:])}


def pair_containment(
    con: duckdb.DuckDBPyConnection, gql: str, rest: str
) -> dict:
    gcols, rcols = _cols(con, gql), _cols(con, rest)
    gnorm = {_norm(c) for c in gcols}
    rnorm = {_norm(c) for c in rcols}
    grows, gfill = _fills(con, gql, gcols)
    rrows, rfill = _fills(con, rest, rcols)
    gql_only = [
        (c, gfill[c])
        for c in gcols
        if _norm(c) not in rnorm and not c.startswith("_") and gfill.get(c, 0) > 0
    ]
    rest_only = [
        (c, rfill[c])
        for c in rcols
        if _norm(c) not in gnorm and not c.startswith("_") and rfill.get(c, 0) > 0
    ]
    return {
        "gql_only": gql_only,
        "rest_only": rest_only,
        "shared": sorted(gnorm & rnorm),
        "gql_rows": grows,
        "rest_rows": rrows,
    }


def verdict(m: dict) -> str:
    if not m["rest_only"] and m["gql_only"]:
        return "DROP_REST"
    if not m["gql_only"] and m["rest_only"]:
        return "DROP_GQL"
    if not m["gql_only"] and not m["rest_only"]:
        return "IDENTICAL"
    return "MERGE"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/cfb.duckdb")
    args = ap.parse_args()
    con = duckdb.connect(args.db, read_only=True)
    present = {
        r[0]
        for r in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='stg'"
        ).fetchall()
    }
    print("| concept | verdict | gql rows | rest rows | gql-only | rest-only |")
    print("|---|---|---|---|---|---|")
    for concept, g, r in PAIRS:
        if g not in present or r not in present:
            print(f"| {concept} | MISSING | | | `{g}` or `{r}` absent | |")
            continue
        m = pair_containment(con, g, r)
        print(
            f"| {concept} | {verdict(m)} | {m['gql_rows']} | {m['rest_rows']} "
            f"| {len(m['gql_only'])} | {len(m['rest_only'])} |"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_measure_pair_containment.py -v`
Expected: 4 passed

- [ ] **Step 5: Run full suite**

Run: `python -m pytest`
Expected: baseline + 11 passed

- [ ] **Step 6: Commit**

```bash
git add scripts/measure_pair_containment.py tests/test_measure_pair_containment.py
git commit -m "feat(warehouse): add bidirectional pair containment measurement"
```

---

### Task 6: Re-measure and record the buckets

**Files:**
- Create: `docs/pair-containment-2026-09-01.md`

**Interfaces:**
- Consumes: `scripts/measure_pair_containment.py`
- Produces: the recorded verdict table that gates Task 9.

- [ ] **Step 1: Run the measurement against the repaired warehouse**

```bash
python scripts/measure_pair_containment.py --db data/cfb.duckdb > docs/pair-containment-2026-09-01.md
```

- [ ] **Step 2: Compare against the pre-repair expectation**

The spec recorded these verdicts *before* the scraper fix:

- `DROP_REST`: `draft_position`, `draft_team`, `predicted_points`
- `DROP_GQL`: `coach_season`, `talent`, `recruit`
- `MERGE`: the other seven

`coach_season` and `talent` are the two the scraper fix touched. **If either has flipped from `DROP_GQL` to `MERGE`, the repaired GraphQL table now carries columns the REST side lacks and must not be dropped.** Record whichever verdict the measurement gives; do not carry the spec's provisional one forward.

- [ ] **Step 3: Annotate the file**

Add a header to `docs/pair-containment-2026-09-01.md` recording the date, that it was measured after the Task 1 scraper fix and Task 4 rebuild, and one line per pair whose verdict differs from the spec's provisional bucket, saying what changed.

- [ ] **Step 4: Delete the Task 2 backups now that the repair is confirmed**

Only if Step 1 ran clean and `coachSeason` / `teamTalent` carry their FK columns:

```bash
rm data/graphql/coachSeason.json.bak data/graphql/teamTalent.json.bak
rm data/cfb.duckdb.pre-rescrape
```

- [ ] **Step 5: Commit**

```bash
git add docs/pair-containment-2026-09-01.md
git commit -m "docs(warehouse): record post-repair pair containment measurement"
```

---

### Task 7: Merge the complementary pairs

**Files:**
- Modify: `cfb_system_maker/duckdb_load.py` (append `build_merged_pairs` near the other `stg` builders)
- Test: `tests/test_merge_pairs.py`

**Interfaces:**
- Consumes: `pair_containment` from Task 5 (to assert nothing is lost)
- Produces: `MERGE_SPECS: list[MergeSpec]` and `build_merged_pairs(con, only=None) -> list[TableLoad]`, writing one `stg.merged_<concept>` table per Bucket C pair. `MergeSpec` is a frozen dataclass of `(concept, gql, rest, keys)`.

Merged tables are written **alongside** the sources, not over them. Nothing is dropped here — Task 9 owns drops, and only after Task 6's measurement.

Only the five pairs with a scalar join key are merged in this task. `coach`/`coaches` (name join) and `recruitingTeam`/`recruiting_teams` (needs `core.dim_team`) are deferred to a follow-up; merging on a person's name without an id is a data-quality decision, not a mechanical one.

- [ ] **Step 1: Write the failing test**

Create `tests/test_merge_pairs.py`:

```python
import duckdb
import pytest

from cfb_system_maker.duckdb_load import MERGE_SPECS, build_merged_pairs


@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    c.execute("CREATE SCHEMA stg")
    c.execute("CREATE TABLE stg.game (gameId BIGINT, homeEndElo DOUBLE)")
    c.execute("INSERT INTO stg.game VALUES (1, 1500.0), (2, 1400.0), (3, 1600.0)")
    c.execute("CREATE TABLE stg.games (gameId BIGINT, completed BOOLEAN, venue VARCHAR)")
    c.execute("INSERT INTO stg.games VALUES (1, true, 'Nippert'), (4, false, 'Rose Bowl')")
    return c


def test_merge_keeps_every_key_from_both_sides(con):
    # A full outer join, not an inner one: gameId 3 exists only in GraphQL and 4 only in
    # REST. An inner join would silently drop both.
    build_merged_pairs(con, only=["game"])
    ids = {r[0] for r in con.execute("SELECT gameId FROM stg.merged_game").fetchall()}
    assert ids == {1, 2, 3, 4}


def test_merge_keeps_exclusive_columns_from_both_sides(con):
    build_merged_pairs(con, only=["game"])
    cols = {r[0] for r in con.execute("DESCRIBE stg.merged_game").fetchall()}
    assert {"homeEndElo", "completed", "venue"} <= cols


def test_merge_records_provenance(con):
    build_merged_pairs(con, only=["game"])
    rows = dict(
        con.execute("SELECT gameId, _source FROM stg.merged_game").fetchall()
    )
    assert rows[1] == "both"
    assert rows[3] == "gql"
    assert rows[4] == "rest"


def test_merge_is_idempotent(con):
    build_merged_pairs(con, only=["game"])
    first = con.execute("SELECT COUNT(*) FROM stg.merged_game").fetchone()[0]
    build_merged_pairs(con, only=["game"])
    assert con.execute("SELECT COUNT(*) FROM stg.merged_game").fetchone()[0] == first


def test_merge_specs_cover_only_scalar_key_pairs():
    # coach and recruitingTeam are deliberately absent — they have no scalar join key.
    concepts = {s.concept for s in MERGE_SPECS}
    assert concepts == {"game", "lines", "draft_pick", "conference", "calendar"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_merge_pairs.py -v`
Expected: FAIL with `ImportError: cannot import name 'MERGE_SPECS'`

- [ ] **Step 3: Write the implementation**

Append to `cfb_system_maker/duckdb_load.py`:

```python
@dataclass(frozen=True)
class MergeSpec:
    concept: str
    gql: str
    rest: str
    keys: tuple[str, ...]


# Only pairs with a scalar join key. `coach`/`coaches` join on (firstName, lastName) —
# REST carries no coachId — and `recruitingTeam`/`recruiting_teams` need core.dim_team to
# bridge an id to a team name. Both are judgement calls, not mechanical merges.
MERGE_SPECS: list[MergeSpec] = [
    MergeSpec("game", "game", "games", ("gameId",)),
    MergeSpec("lines", "gameLines", "lines", ("gameId",)),
    MergeSpec("draft_pick", "draftPicks", "draft_picks", ("year", "round", "pick")),
    MergeSpec("conference", "conference", "conferences", ("conferenceId",)),
    MergeSpec("calendar", "calendar_gql", "calendar", ("season", "week")),
]


def build_merged_pairs(
    con: duckdb.DuckDBPyConnection, only: list[str] | None = None
) -> list[TableLoad]:
    """Write one stg.merged_<concept> per spec: FULL OUTER JOIN, both sides' columns.

    Written alongside the sources, never over them. A FULL OUTER JOIN is required — each
    side holds keys the other lacks, and an inner join would drop them silently.
    """
    reports: list[TableLoad] = []
    for spec in MERGE_SPECS:
        if only is not None and spec.concept not in only:
            continue
        dest = f"merged_{spec.concept}"
        target = _qualify("stg", dest)
        try:
            gcols = [r[0] for r in con.execute(f'DESCRIBE stg."{spec.gql}"').fetchall()]
            rcols = [r[0] for r in con.execute(f'DESCRIBE stg."{spec.rest}"').fetchall()]
            keyset = {k.lower() for k in spec.keys}
            gnorm = {c.lower().replace("_", "") for c in gcols}
            # Key columns come from COALESCE; non-key REST columns that duplicate a
            # GraphQL column by name are dropped in favour of the GraphQL one.
            rest_extra = [
                c
                for c in rcols
                if c.lower() not in keyset
                and c.lower().replace("_", "") not in gnorm
            ]
            gql_extra = [c for c in gcols if c.lower() not in keyset]
            key_sel = ", ".join(
                f'COALESCE(g."{k}", r."{k}") AS "{k}"' for k in spec.keys
            )
            g_sel = "".join(f', g."{c}"' for c in gql_extra)
            r_sel = "".join(f', r."{c}"' for c in rest_extra)
            on = " AND ".join(f'g."{k}" = r."{k}"' for k in spec.keys)
            first = spec.keys[0]
            con.execute(f"DROP TABLE IF EXISTS {target}")
            con.execute(
                f"""
                CREATE TABLE {target} AS
                SELECT {key_sel}{g_sel}{r_sel},
                  CASE
                    WHEN g."{first}" IS NOT NULL AND r."{first}" IS NOT NULL THEN 'both'
                    WHEN g."{first}" IS NOT NULL THEN 'gql'
                    ELSE 'rest'
                  END AS _source
                FROM stg."{spec.gql}" AS g
                FULL OUTER JOIN stg."{spec.rest}" AS r ON {on}
                """
            )
            rows = con.execute(f"SELECT COUNT(*) FROM {target}").fetchone()[0]
            reports.append(TableLoad("stg", dest, 1, int(rows)))
        except Exception as exc:
            detail = str(exc).split("\n", 1)[0]
            reports.append(
                TableLoad("stg", dest, 0, 0, error=f"{type(exc).__name__}: {detail}")
            )
    return reports
```

Ensure `from dataclasses import dataclass` is imported at the top of the module.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_merge_pairs.py -v`
Expected: 5 passed

- [ ] **Step 5: Run full suite**

Run: `python -m pytest`
Expected: baseline + 16 passed

- [ ] **Step 6: Commit**

```bash
git add cfb_system_maker/duckdb_load.py tests/test_merge_pairs.py
git commit -m "feat(warehouse): merge complementary GraphQL/REST pairs into stg.merged_*"
```

---

### Task 8: Build the merged tables and verify no data was lost

**Files:**
- Modify: `data/cfb.duckdb` (untracked)

**Interfaces:**
- Consumes: `build_merged_pairs` from Task 7
- Produces: five `stg.merged_*` tables.

**Mutates the live warehouse. User-run only.**

- [ ] **Step 1: Build the merged tables**

```bash
python -c "
import duckdb
from cfb_system_maker.duckdb_load import build_merged_pairs
con = duckdb.connect('data/cfb.duckdb')
for r in build_merged_pairs(con):
    print(f'{r.name:24} {r.rows:>8} rows  {r.error or \"\"}')
"
```

Expected: five tables, no errors.

- [ ] **Step 2: Verify every source key survived the merge**

```bash
python -c "
import duckdb
from cfb_system_maker.duckdb_load import MERGE_SPECS
c = duckdb.connect('data/cfb.duckdb', read_only=True)
for s in MERGE_SPECS:
    k = ', '.join(f'\"{x}\"' for x in s.keys)
    g = c.sql(f'select count(*) from (select distinct {k} from stg.\"{s.gql}\")').fetchone()[0]
    r = c.sql(f'select count(*) from (select distinct {k} from stg.\"{s.rest}\")').fetchone()[0]
    m = c.sql(f'select count(*) from (select distinct {k} from stg.merged_{s.concept})').fetchone()[0]
    flag = 'OK' if m >= max(g, r) else 'LOST KEYS'
    print(f'{s.concept:16} gql={g:>7} rest={r:>7} merged={m:>7}  {flag}')
"
```

Expected: every row `OK`. `merged` should be at least the larger of the two — a smaller value means the join dropped keys and the merge is wrong.

- [ ] **Step 3: Verify every populated source column reached the merge**

```bash
python -c "
import duckdb
from cfb_system_maker.duckdb_load import MERGE_SPECS
c = duckdb.connect('data/cfb.duckdb', read_only=True)
def cols(t): return {r[0] for r in c.sql(f'describe stg.\"{t}\"').fetchall()}
for s in MERGE_SPECS:
    m = cols(f'merged_{s.concept}')
    missing = (cols(s.gql) | cols(s.rest)) - m - {'_source_file'}
    print(f'{s.concept:16} missing from merge: {sorted(missing) or \"none\"}')
"
```

Expected: `none`, or only REST columns whose GraphQL twin was kept under a different spelling. Investigate anything else.

- [ ] **Step 4: Run full suite**

Run: `python -m pytest`
Expected: all pass.

---

### Task 9: Drop what is provably superseded

**Files:**
- Create: `scripts/drop_superseded.py`
- Test: `tests/test_drop_superseded.py`

**Interfaces:**
- Consumes: `pair_containment` and `verdict` from Task 5
- Produces: `droppable(con) -> list[tuple[str, str]]` returning `(table_to_drop, reason)`; `drop_superseded(con, *, dry_run) -> list[tuple[str, str]]`.

The gate is measurement, not the spec's provisional buckets. A table is dropped only when `verdict()` says so **at run time**, against the repaired warehouse.

- [ ] **Step 1: Write the failing test**

Create `tests/test_drop_superseded.py`:

```python
import duckdb
import pytest

from scripts.drop_superseded import drop_superseded, droppable


@pytest.fixture
def con(monkeypatch):
    import scripts.measure_pair_containment as mpc

    c = duckdb.connect(":memory:")
    c.execute("CREATE SCHEMA stg")
    # GraphQL strictly richer -> REST droppable
    c.execute("CREATE TABLE stg.gA (id INTEGER, extra VARCHAR)")
    c.execute("INSERT INTO stg.gA VALUES (1,'x')")
    c.execute("CREATE TABLE stg.rA (id INTEGER)")
    c.execute("INSERT INTO stg.rA VALUES (1)")
    # Both have exclusive populated columns -> neither droppable
    c.execute("CREATE TABLE stg.gB (id INTEGER, onlyg VARCHAR)")
    c.execute("INSERT INTO stg.gB VALUES (1,'x')")
    c.execute("CREATE TABLE stg.rB (id INTEGER, onlyr VARCHAR)")
    c.execute("INSERT INTO stg.rB VALUES (1,'y')")
    monkeypatch.setattr(mpc, "PAIRS", [("a", "gA", "rA"), ("b", "gB", "rB")])
    return c


def test_droppable_lists_the_superseded_side_only(con):
    got = dict(droppable(con))
    assert "rA" in got
    assert "gA" not in got


def test_droppable_never_lists_a_complementary_pair(con):
    got = dict(droppable(con))
    assert "gB" not in got and "rB" not in got


def test_dry_run_drops_nothing(con):
    drop_superseded(con, dry_run=True)
    names = {
        r[0]
        for r in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='stg'"
        ).fetchall()
    }
    assert "rA" in names


def test_apply_drops_only_the_superseded_table(con):
    drop_superseded(con, dry_run=False)
    names = {
        r[0]
        for r in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='stg'"
        ).fetchall()
    }
    assert "rA" not in names
    assert {"gA", "gB", "rB"} <= names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_drop_superseded.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

Create `scripts/drop_superseded.py`:

```python
"""Drop the superseded side of a pair — measured at run time, not from a stored verdict.

A table is dropped only when the surviving table has every populated column the dropped
one has. The buckets in the spec were measured before the scraper repair and are NOT
authoritative here.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.measure_pair_containment import (  # noqa: E402
    PAIRS,
    pair_containment,
    verdict,
)


def droppable(con: duckdb.DuckDBPyConnection) -> list[tuple[str, str]]:
    present = {
        r[0]
        for r in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='stg'"
        ).fetchall()
    }
    out: list[tuple[str, str]] = []
    for concept, g, r in PAIRS:
        if g not in present or r not in present:
            continue
        m = pair_containment(con, g, r)
        v = verdict(m)
        if v == "DROP_REST":
            out.append((r, f"{concept}: {g} has every populated column of {r}"))
        elif v in {"DROP_GQL", "IDENTICAL"}:
            out.append((g, f"{concept}: {r} has every populated column of {g}"))
    return out


def drop_superseded(
    con: duckdb.DuckDBPyConnection, *, dry_run: bool
) -> list[tuple[str, str]]:
    pairs = droppable(con)
    if dry_run:
        return pairs
    for table, _ in pairs:
        con.execute(f'DROP TABLE stg."{table}"')
        con.execute("DELETE FROM meta.load_report WHERE schema='stg' AND name = ?", [table])
    return pairs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/cfb.duckdb")
    ap.add_argument("--apply", action="store_true", help="without this, dry-run only")
    args = ap.parse_args()
    con = duckdb.connect(args.db, read_only=not args.apply)
    pairs = drop_superseded(con, dry_run=not args.apply)
    for table, reason in pairs:
        print(f"  {'dropped' if args.apply else 'would drop'} stg.{table} - {reason}")
    print(f"{len(pairs)} table(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_drop_superseded.py -v`
Expected: 4 passed

- [ ] **Step 5: Run full suite**

Run: `python -m pytest`
Expected: baseline + 20 passed

- [ ] **Step 6: Commit**

```bash
git add scripts/drop_superseded.py tests/test_drop_superseded.py
git commit -m "feat(warehouse): add proof-gated drop of superseded pair tables"
```

---

### Task 10: Apply the drops and remove the dead columns

**Files:**
- Modify: `data/cfb.duckdb` (untracked), `cfb_system_maker/graphql_client.py` or the REST endpoint registry

**Interfaces:**
- Consumes: `scripts/drop_superseded.py` from Task 9
- Produces: a warehouse with no superseded tables and no dead columns.

**Mutates the live warehouse. User-run only.**

- [ ] **Step 1: Back up**

```bash
cp data/cfb.duckdb data/cfb.duckdb.pre-drop
```

- [ ] **Step 2: Dry-run the drops and compare to the recorded measurement**

```bash
python scripts/drop_superseded.py --db data/cfb.duckdb
```

Cross-check the list against `docs/pair-containment-2026-09-01.md` from Task 6. Anything listed here that the recorded measurement did not mark `DROP_*` means the warehouse changed between the two runs — re-run Task 6 before proceeding.

- [ ] **Step 3: Apply the drops**

```bash
python scripts/drop_superseded.py --db data/cfb.duckdb --apply
```

- [ ] **Step 4: Drop the 12 dead columns**

These are payload columns, so the Task 3 rule deliberately leaves them alone; they are dropped explicitly. The 2026-week `homeScore`/`awayScore` columns are **excluded** — those games have not been played.

```bash
python - <<'PY'
import duckdb
con = duckdb.connect("data/cfb.duckdb")
DEAD = [
    ("plays", "defenseTimeouts"),
    ("plays", "offenseTimeouts"),
    ("plays", "wallclock"),
    ("gameWeather", "windGust"),
    ("pollType", "abbreviation"),
    ("recruit", "overallRank"),
    ("recruit", "positionRank"),
    ("team_stats", "statValue_anyof_schema_1_validator"),
    ("team_stats__statValue_any_of_schemas", "statValue_anyof_schema_1_validator"),
    ("actionnetwork_scoreboard__teams", "teams_standings_overtime_losses"),
    ("actionnetwork_scoreboard__markets__markets_event_moneyline",
     "markets_event_moneyline_odds_coefficient_score"),
    ("actionnetwork_scoreboard__markets__markets_event_core_bet_type_6_team_score",
     "markets_event_core_bet_type_6_team_score_odds_coefficient_score"),
]
for table, col in DEAD:
    try:
        n, filled = con.execute(
            f'SELECT COUNT(*), COUNT("{col}") FROM stg."{table}"'
        ).fetchone()
    except Exception as exc:
        print(f"SKIP {table}.{col} - {type(exc).__name__}")
        continue
    if filled:
        print(f"KEPT {table}.{col} - now {filled}/{n} populated, no longer dead")
        continue
    con.execute(f'ALTER TABLE stg."{table}" DROP COLUMN "{col}"')
    print(f"dropped {table}.{col}")
PY
```

Expected: 12 `dropped` lines. A `KEPT` line means a re-scrape populated that column — leave it and note it.

- [ ] **Step 5: Remove the dropped sources from the scraper**

For each table dropped in Step 3, remove its source so the next pull does not recreate it:

- A dropped GraphQL table: remove its entity from `GQL_DEFAULT_TABLES` and add it to `GQL_EXCLUDED` with the reason (`"superseded by stg.<rest_table>, which has every populated column"`). Do **not** delete its `GQL_RELATION_KEYS` entry silently — remove it in the same edit and say so in the commit.
- A dropped REST table: remove its endpoint from the REST registry, with the same style of comment.

Then confirm nothing else references the removed name:

```bash
grep -rn "<removed_name>" --include=*.py cfb_system_maker scripts tests models research | grep -v cfbd-python
```

- [ ] **Step 6: Verify a full reload does not resurrect anything**

```bash
python -m cfb_system_maker duckdb --explode-only
python scripts/drop_superseded.py --db data/cfb.duckdb
```

Expected: `0 table(s)` — nothing droppable, because nothing superseded came back.

- [ ] **Step 7: Run full suite**

Run: `python -m pytest`
Expected: all pass.

- [ ] **Step 8: Commit the scraper changes**

```bash
git add cfb_system_maker/graphql_client.py
git commit -m "chore(scraper): stop pulling sources superseded by their pair"
```

- [ ] **Step 9: Remove the backup**

Only after Steps 6 and 7 are green:

```bash
rm data/cfb.duckdb.pre-drop
```

---

### Task 11: Document the outcome

**Files:**
- Create: `docs/warehouse-sources.md`
- Modify: `CLAUDE.md` (one bullet in "Shared rules")

**Interfaces:**
- Consumes: `docs/pair-containment-2026-09-01.md` from Task 6
- Produces: the durable record.

- [ ] **Step 1: Write `docs/warehouse-sources.md`**

```markdown
# Warehouse sources

## Two sources, not duplicates

`stg` is fed by the CFBD REST API and the CFBD GraphQL API. Where both cover a concept,
the tables are named differently and carry different columns. They are not redundant
copies — measure before assuming either one is authoritative.

## Per-concept record

<!-- paste the verdict table from docs/pair-containment-2026-09-01.md, plus a column
     saying what was done: merged into stg.merged_<concept>, dropped, or kept as-is -->

## Merged tables

`stg.merged_<concept>` is a FULL OUTER JOIN of the pair, carrying every populated column
from both sides plus `_source` (`both` / `gql` / `rest`). Sources are retained alongside.

Not merged: `coach`/`coaches` (REST has no `coachId`; join is on name) and
`recruitingTeam`/`recruiting_teams` (id vs name; needs `core.dim_team`).

## Relation-only GraphQL entities

An entity whose identity lives in a to-one relation must have a `GQL_RELATION_KEYS` entry,
or its dump is unjoinable and its pagination is not a total order. Currently: `pollRank`,
`coachSeason`, `teamTalent`. `gameMedia` is excluded outright for the same reason.

## Scaffolding columns

`season`, `week`, and `season_type` are bound from the filename stem, not the payload. When
a source's filenames do not carry them they arrive NULL, and `prune_null_scaffolding` drops
them at load time. Payload columns are never auto-dropped.
```

- [ ] **Step 2: Add the shared rule**

Append to "Shared rules" in root `CLAUDE.md`:

```markdown
- `stg` has two sources: REST and GraphQL. Paired tables are not duplicates — see
  `docs/warehouse-sources.md` before treating either as canonical. A GraphQL entity whose
  identity is relation-only needs a `GQL_RELATION_KEYS` entry.
```

- [ ] **Step 3: Verify the doc names only tables that exist**

```bash
python -c "
import re, duckdb
c = duckdb.connect('data/cfb.duckdb', read_only=True)
have = {t for (t,) in c.sql(\"select table_name from duckdb_tables() where schema_name='stg'\").fetchall()}
txt = open('docs/warehouse-sources.md', encoding='utf-8').read()
named = set(re.findall(r'stg\.([A-Za-z0-9_]+)', txt))
print('named but absent:', sorted(n for n in named if n not in have and '<' not in n))
"
```

Expected: `named but absent: []`

- [ ] **Step 4: Commit**

```bash
git add docs/warehouse-sources.md CLAUDE.md
git commit -m "docs(warehouse): record source rationalization outcome"
```

---

## Self-Review

**Spec coverage.** R1 → Task 1. R2 → Task 2 Step 6. R3 → Task 3, with `test_prune_never_drops_a_payload_column` as the guard. R4 → Tasks 5 and 6; Task 9's `droppable` re-measures at run time rather than reading a stored verdict, and Task 10 Step 2 cross-checks the two. R5 → Task 7, with Task 8 Steps 2–3 proving no key or column was lost. R6 → Task 9's gate. R7 → Task 10 Step 5.

**Type consistency.** `pair_containment(con, gql, rest) -> dict` is defined in Task 5 and imported unchanged by Task 9. `verdict(m) -> str` returns the four literals Task 9 branches on (`DROP_REST`, `DROP_GQL`, `IDENTICAL`, `MERGE`). `MergeSpec(concept, gql, rest, keys)` is defined in Task 7 and read by Task 8's verification commands. `prune_null_scaffolding(con, dest) -> list[str]` matches its call in `_finish_stg_table`.

**Known soft spots.**
- Task 7's merge drops a REST column when a GraphQL column normalizes to the same name, keeping the GraphQL one. For `game`/`games` the Elo columns do **not** collide by name (`awayEndElo` vs `awayPostgameElo`), so both survive — but the rule is name-based and would prefer GraphQL on a genuine collision even where REST has better fill. Task 8 Step 3 surfaces any column that vanished; if one matters, add an explicit override to `MergeSpec`.
- Task 2's row counts may rise, which is expected (the old sort was not total). The plan treats a *fall* as a stop condition. It cannot distinguish "pagination fixed, more rows" from "upstream data changed" — if the increase is large, spot-check a few rows against the API before trusting it.
- `draftPicks`/`draft_picks` merge on `(year, round, pick)`. Neither side has an id (`graphql-schema-draft.md:126`). **Verified unique on both sides** against the live warehouse on 2026-09-01: `draftPicks` 13,080 rows / 13,080 distinct, `draft_picks` 3,584 / 3,584. Task 8 Step 2 re-checks it after any re-scrape.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-01-warehouse-source-rationalization.md`. Two execution options:

**1. Subagent-Driven (recommended)** — a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Tasks 2, 4, 6, 8, and 10 mutate the live warehouse or hit the live CFBD API; all are gated on explicit user go-ahead regardless of execution mode. Task 6 is a hard gate — Tasks 9 and 10 must not run until its measurement is recorded.
