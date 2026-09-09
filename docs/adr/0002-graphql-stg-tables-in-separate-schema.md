---
status: superseded
superseded-by: 0003-one-stg-schema-suffix-only-the-colliders
---

# GraphQL-sourced staging tables live in `stg_gql`, not a `gql_`-prefixed name in `stg`

> **Superseded 2026-09-08 by ADR-0003.** The destination choice below was reversed: there is
> one `stg` schema, with a temporary `_gql` suffix on the colliding names only. The diagnosis
> of the load-order bug, the `raw` decoupling analysis and the DuckDB migration findings in
> this ADR remain accurate and are relied on by ADR-0003.

`stg` is fed by two ingestion sources — CFBD REST and CFBD GraphQL — that can name the same
concept differently or, for 3 of 34 GraphQL entities (`draftPicks`, `predictedPoints`,
`calendar`), identically once both are snake_cased. A prior build
(`docs/superpowers/plans/2026-08-31-warehouse-naming-rationalization.md`, commits `3027774`,
`54987b1`, `a7be132`) fixed the load-order-dependent clash bug that caused with an explicit
`GQL_ENTITY_TO_STG` mapping to a `gql_<snake_case>`-prefixed name inside `stg`. That code
shipped but was never applied to the live warehouse. Before applying it, we chose to change the
destination scheme from a prefix to a separate schema: GraphQL tables move to `stg_gql` under
bare `snake_case` names (`stg_gql.game`); REST tables stay in `stg` unchanged (`stg.games`).

## Alternatives

**The shipped `gql_` prefix** (`stg.gql_game`). Rejected after shipping, before applying to the
warehouse — cheap to reverse since nothing downstream had consumed it. Provenance was encoded
in a string a reader has to know to interpret; a collision was prevented by disjoint construction
rather than being structurally impossible; and the prefix would go from useful to naming an
implementation detail exactly where the follow-on source-rationalization plan succeeds — once
`predicted_points` (REST) is deprecated in favor of `predictedPoints` (GraphQL) per that plan,
`gql_predicted_points` would be the only surviving table for the concept, permanently named
after which API produced it rather than what it is.

**Bare `snake_case` with no disambiguation** (`stg.draft_picks` for both sources). Rejected: 3
of 34 entities collide exactly (`draftPicks`→`draft_picks`, `predictedPoints`→`predicted_points`,
`calendar`→`calendar`) and 7 more differ only by a trailing `s` (`game`/`games`,
`coach`/`coaches`, …). Not viable without reintroducing some form of clash resolution.

## Consequences

**`raw` naming must be decoupled from the `stg`/`stg_gql` resolver.** `raw`'s GraphQL table
naming has always reused the same name-resolution function as the `stg` destination
(pre-dates this build). Under the `gql_` prefix that was harmless — the resolver always
returned a collision-free `gql_`-prefixed name. Under bare `stg_gql` names it is not: naming
`raw`'s GraphQL dumps with the same bare values would collide with REST raw dumps for the same
3 entities the `stg` scheme collides on. `GQL_ENTITY_TO_RAW` (unchanged `gql_`-prefixed values)
now feeds `raw` naming exclusively; `GQL_ENTITY_TO_STG` (bare values) feeds only `stg_gql`. `raw`
itself does not gain a second schema — it stays "source fidelity, names never change," now true
for GraphQL as well as REST, decoupled from whichever scheme `stg` uses.

**`stg_id_renames`/`stg_column_order` gain a required `schema` parameter.** Their GraphQL-entity
reverse lookup can no longer assume a bare destination name is unambiguous — under `stg_gql` it
might collide with a same-named REST table in `stg`. No entry in `_BARE_ID_RENAME` currently
collides, so this has no observable effect today; it closes a silent-wrong-rename class before
the next entity or mapping edit can trigger it.

**DuckDB cannot rename a table's schema.** `ALTER TABLE ... SET SCHEMA` is unimplemented
(verified, DuckDB 1.5.2: `NotImplementedException: T_AlterObjectSchemaStmt`). The migration
script is `CREATE TABLE stg_gql.<x> AS SELECT * FROM stg.gql_<x>` followed by `DROP TABLE`, not
a metadata rename — more work per table (~1.8M rows total, a minute or two) and different
failure semantics (must not leave a table live in both schemas on a mid-run failure).

**`--only <name>` can now match both schemas for the 3 colliding concepts, but only at the
`--explode-lists` phase.** `cli.py` has three consumers, each matching a different spelling:
the `duckdb` load step matches the GraphQL entity name or the raw table name;
`--explode-only` matches the raw table name only; `--explode-lists` matches the bare
`stg`/`stg_gql` destination name only, so `--only draft_picks` there selects
`stg.draft_picks` and `stg_gql.draft_picks` together. Documented per-phase in
`cfb_system_maker/CLAUDE.md` rather than given disambiguation syntax nothing currently needs.

Nothing in the live warehouse changes until the migration script (a separate, explicitly
user-run step) is executed — this build changes only unapplied code.
