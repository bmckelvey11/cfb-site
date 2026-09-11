---
status: accepted
supersedes: 0002-graphql-stg-tables-in-separate-schema
---

# One `stg` schema; a source suffix on the colliding names only

ADR-0002 moved GraphQL-sourced staging tables into a `stg_gql` schema under bare `snake_case`
names. This ADR reverses that destination choice: there is **one** `stg` schema, and the two or
three names that genuinely collide carry a `_gql` suffix. *(This ADR originally called that
suffix temporary. It is not — see the amendment at the foot.)*

ADR-0002's diagnosis was correct and is not disturbed. The real defect was `_stg_dest_name`
resolving clashes against a `taken` set populated as loads proceeded, so which source won an
unsuffixed name depended on load order. What is reversed is only the remedy.

## What changed: the constraint was measured, not assumed

ADR-0002 stated that 3 of 34 GraphQL entities collide exactly and "7 more differ only by a
trailing `s`." Measured against the live warehouse on 2026-09-08:

| | |
|---|---|
| `stg` tables | 124 |
| `stg_gql` tables | 38 |
| **Exact collisions if merged** | **3** — `calendar`, `draft_picks`, `predicted_points` |
| `stg_gql` tables with no REST counterpart of any spelling | **28 of 38** |
| Differ by a trailing `s` | 7 |

The seven trailing-`s` pairs — `game`/`games`, `coach_season`/`coach_seasons`,
`conference`/`conferences`, `recruit`/`recruits`, `draft_team`/`draft_teams`,
`draft_position`/`draft_positions`, `recruiting_team`/`recruiting_teams` — **are not
collisions.** They are distinct table names. ADR-0002 raised them as a readability complaint;
that complaint was then carried into the correctness argument, where it never belonged.

So the schema tags 38 tables to disambiguate 3, and 28 of the 38 have no counterpart of any
spelling to be disambiguated from.

## The argument turns on ADR-0002's own reasoning

ADR-0002 rejected the `gql_` prefix on two grounds: provenance would be "encoded in a string a
reader has to know to interpret," and the surviving table for a concept would end up
"permanently named after which API produced it rather than what it is."

Both objections apply verbatim to a *schema* named `stg_gql`, at coarser granularity — a prefix
tags the 3 that collide, the schema tags all 38. The example ADR-0002 chose against the prefix
is the clearest case: once source rationalization drops the REST side of `predicted_points`, the
surviving GraphQL table would be `stg_gql.predicted_points` — the only table for that concept,
still qualified by its transport.

## Alternatives

**Keep `stg_gql`** (ADR-0002 as accepted). Rejected for the reasons above. It is not wrong, it is
disproportionate, and it makes `stg` silently mean "REST" — a meaning nothing declares.

**Bare names with no disambiguation at all.** Rejected, as ADR-0002 rejected it: three names
genuinely collide. The disagreement was never about whether they collide, only about how many
tables must pay for it.

**A `gql_` prefix on all 38** (the pre-ADR-0002 scheme). Rejected — ADR-0002's objections stand
against it, and this ADR does not resurrect it.

## Consequences

~~**The suffix is temporary by construction, and the plan that introduces it removes it.** All
three colliders are exactly the tables that stop existing in duplicate under
`docs/superpowers/plans/2026-09-08-warehouse-rationalization-master.md`: `predicted_points`
drops its REST side (Bucket A), `draft_picks` and `calendar` merge into `core` (Bucket C). When
that plan completes, the suffix count is zero and no name in `stg` refers to a transport. The
collapse is therefore sequenced **after** the drops and merges, not before — at which point no
suffix ever needs to be created.~~ **Wrong on all three. See the amendment.**

**The rename is the dangerous operation and is gated.** It changes the qualified name of all 38
tables, and code references them 30+ times (`stg_gql.game` 13, `stg_gql.game_lines` 12,
`stg_gql.lines_provider` 6, `stg_gql.calendar` 4). This is the exact class of change that
silently broke two consumers before `tests/test_catalog_resolution.py` existed (`56a84db`,
which found two stale references on its first run). The collapse runs only behind that test.

**`GQL_ENTITY_TO_STG` remains the mechanism** and gains suffixed values for the colliders. This
is the point ADR-0002 under-weighted: an explicit static mapping already makes load-order
dependence impossible, so a separate schema was one way to get structural safety and not the
only one.

**`raw` is unaffected.** It keeps its `gql_` prefix and its single schema, as ADR-0002 decided —
that prefix prevents the same three collisions among raw dumps and is load-bearing. The
`GQL_ENTITY_TO_RAW` / `GQL_ENTITY_TO_STG` split that ADR-0002 introduced stays exactly as it is.

**`stg` stops silently meaning "REST."** With one staging schema there is nowhere to misfile a
table, which also resolves the misfiled `gameMedia` / `gamePlayerStat` entries — they need
snake_casing, not relocation.

**ADR-0002 is superseded, not deleted.** Its diagnosis of the load-order bug, its `raw`
decoupling analysis, and its DuckDB findings (`ALTER TABLE ... SET SCHEMA` is unimplemented, so
migration is `CREATE TABLE AS` + `DROP`) remain accurate and are relied on by the migration this
ADR implies — in the reverse direction.

## Amendment, 2026-09-10 — the three suffixes are permanent

The decision stands and was carried out: `stg_gql` is collapsed, 38 transport-tagged names
became 3. The *prediction* in the first paragraph of Consequences was wrong, on each of its
three counts, and the collapse went ahead anyway because §2's actual argument never depended
on it — a schema tagging all 38 tables to disambiguate 3 is disproportionate whether the 3
are temporary or not.

- **`predicted_points` did not drop its REST side.** It failed R6's containment half. The REST
  rows lose `down`/`distance` **at the API** — `raw/predicted_points.json` is a flat list of
  10,140 `{predictedPoints, yardLine}` objects — so they cannot be aligned to GraphQL's
  19,800-cell grid, and only 13% match on `yardLine` within 0.005. There is no flatten to fix.
  See [`warehouse-drop-superseded-2026-09-10.md`](../warehouse-drop-superseded-2026-09-10.md).
- **`draft_picks` and `calendar` did merge into `core`, and that changes nothing.** This is the
  reasoning error, not a measurement that moved: **merging a pair into `core` never retires its
  `stg` sources, because `core` is built *from* them.** `_build_dim_draft_pick` reads
  `stg.draft_picks` and `stg.draft_picks_gql` on every `build_core`; delete either and the next
  rebuild produces a smaller table. `core` is a derived layer, not a destination that consumes
  its inputs. Nothing in the rationalization plan could ever have made these two go away.
- **`calendar` is further from droppable than the others**, since its merge was measured as a
  no-op: `stg.calendar` is what bounds `core` through `core.dim_week`.

So a permanent `_gql` suffix on three names is the cost of one staging schema, and ADR-0002's
objection — that a name would be "permanently named after which API produced it" — lands on
those three. It is accepted for them and rejected for the other 31, which is the whole point:
the objection is about proportion, and 3 of 34 is a different proposition from 34 of 34.

Recorded in [`stg-gql-collapse-2026-09-10.md`](../stg-gql-collapse-2026-09-10.md).
`GQL_STG_COLLIDERS` in `cfb_system_maker/graphql_client.py` is the list, and
`tests/test_graphql.py::test_only_the_three_rest_colliders_carry_the_gql_suffix` pins it.
