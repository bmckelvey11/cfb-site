# Warehouse schema recommendation — 2026-09-02

Naming and structure recommendation for the next rebuild. Asked: drop `stg_gql`, drop the
double-underscore names, review everything.

Evidence is the live warehouse (301 tables) plus every `<schema>.<table>` literal in the repo.
Prior decisions cited, not restated: [ADR 0002](adr/0002-graphql-stg-tables-in-separate-schema.md),
[naming rationalization](superpowers/specs/2026-08-31-warehouse-naming-rationalization.md),
[source rationalization](superpowers/specs/2026-09-01-warehouse-source-rationalization.md),
[audit](duckdb-audit-2026-09-02.md).

## Recommendation in one line

**Stop generating the `__` tables, collapse `stg_gql` into `stg` with a source suffix on the
2–3 colliding names only, and make `core` the clean-name surface — behind a rename guard.**

**Revised 2026-09-02** after the question "why does `gql` have to be in the group name?" It
doesn't, and the first draft of §3 overstated the constraint that said it did. The measurement
and the correction are in §3.

---

## 0. The gate: two renames, two silent breakages, zero tests

This is the load-bearing finding and it governs the order of everything below.

| Rename | Consumer it broke | How it surfaced |
|---|---|---|
| `stg.calendar` → `stg_gql.calendar` (2026-08-31) | `duckdb_core._build_dim_week` | Nightly refresh died for a day; found by reading `cfbd_refresh.log` during the audit |
| `stg.gql_game` → `stg_gql.game` (2026-08-31) | `research/spread/scripts/build_prediction_tracker.py:139,144` | Found while writing this doc. Fixed in `17dc66e` |

Same migration, two consumers, neither caught. The suite was green through both because
`test_core_agreement` builds its own fixtures and the tracker has no test at all.

**Before any further renaming, add a catalog-resolution test:** collect every
`<schema>.<table>` string literal in `cfb_system_maker/`, `models/`, `research/`, `scripts/`,
and assert each resolves against the live warehouse (skip when `CFB_DATA_ROOT` is absent, as the
existing live tests do). That is a for-loop over `information_schema.tables` and it would have
caught both breakages the day they landed.

Without this, every recommendation below is a third breakage waiting to happen.

---

## 1. Double underscores — delete the generator, not the names

**54 tables carry `__`. Exactly one is read by any code.**

| | |
|---|---|
| `__` tables | 54 (50 in `stg`, 4 in `stg_gql`) |
| Referenced anywhere in the repo | **1** — `stg.actionnetwork_scoreboard__markets__markets_event_spread` |
| Deepest chain | 4 levels |
| Longest name | 99 chars — `stg.game_player_stats__teams__teams_categories__teams_categories_types__teams_categories_types_athletes` |

They exist because `explode_stg_lists` runs over **every** leftover LIST/JSON column
unconditionally, recursing a level at a time. Nothing asked for them. The 99-character name is
not a naming problem — it is four levels of automatic recursion given a name.

**Recommendation: make list explosion opt-in.** An allowlist of `(table, column)` pairs; default
off. Renaming 54 tables nobody reads is work with no reader; not creating 53 of them is a
deletion.

Nothing is lost. The parent keeps its LIST column, so any array stays reachable with `unnest`
in a query. Needing a materialized child again is one allowlist line.

Start the allowlist with what is actually used:

```
actionnetwork_scoreboard.markets   # the only consumed child today
lines.lines                        # feeds core.fact_game_line
```

Second-order win: this removes **13 of the 17 camelCase table names**, which are camelCase only
because a child inherited a camelCase JSON key (`advanced_box_score__teams_cumulativePpa`,
`games__awayLineScores`, `roster__recruitIds`).

## 2. camelCase — four real stragglers, and two of them are misfiled

After §1, four camelCase names remain, and they are the same two tables twice:

```
raw.gameMedia          23,907      stg.gameMedia          23,907
raw.gamePlayerStat  5,541,660      stg.gamePlayerStat  5,541,660
```

Both are **GraphQL-sourced**. Both sit in the REST schemas under the raw GraphQL entity name.
They are in `GQL_EXCLUDED` (`graphql_client.py:83-85`) and pulled by a dedicated path, so they
never pass through `GQL_ENTITY_TO_RAW` / `GQL_ENTITY_TO_STG` and get neither the `gql_` raw
prefix nor `stg_gql` placement.

**Recommendation:** route them through the same mapping as every other GraphQL entity —
`raw.gql_game_media` and `raw.gql_game_player_stat` on the `raw` side, `stg.game_media` and
`stg.game_player_stat` in staging. Neither name collides. This is a consistency hole in the
existing scheme, not a new scheme.

Note `stg.gamePlayerStat` is the table carrying the 998 season-less rows from a stale
whole-corpus source file (audit S6) — worth doing both at once.

**Under §3's single-schema recommendation this shrinks further:** with one `stg` there is nowhere
to misfile them, so all they need is snake_casing to `game_media` / `game_player_stat`.

## 3. `stg_gql` — collapse it; the constraint is 2 table names, not 38

**My first draft recommended keeping it. That was wrong, and the correction is worth showing.**

I wrote that bare names collide on "3 exactly, 7 more by a trailing `s`". I took that from ADR
0002 and did not measure it. Measured against the live warehouse:

| | |
|---|---|
| `stg` tables | 134 |
| `stg_gql` tables | 38 |
| **Exact collisions if merged into one schema** | **2** — `draft_picks`, `predicted_points` |
| `stg_gql` tables with **no `stg` counterpart at all** | **29 of 38** |

The "7 near-misses" — `game`/`games`, `coach_season`/`coach_seasons`, `conference`/`conferences`,
`recruit`/`recruits`, `draft_team`/`draft_teams`, `draft_position`/`draft_positions`,
`recruiting_team`/`recruiting_teams` — **are not collisions.** They are distinct table names.
ADR 0002 raised them as a readability complaint and I repeated it as if it were part of the
correctness constraint. It never was.

`calendar` becomes a third collision once audit S3 is fixed and the REST calendar is finally
staged. So: **3 colliding names out of 172.**

### The schema tags 38 tables to disambiguate 2

29 of the 38 carry `gql` in their qualified name for a collision that does not exist for them.
`athlete`, `athlete_team`, `game_lines`, `game_team`, `current_teams`, `adjusted_team_metrics`
and 23 others have no REST counterpart of any spelling.

And ADR 0002's own argument cuts against its own conclusion. It rejected the `gql_` prefix
because provenance would be "encoded in a string a reader has to know to interpret", and because
the prefix would end up "permanently named after which API produced it rather than what it is."
Both criticisms apply verbatim to a *schema* named `stg_gql` — at coarser granularity, so it
tags all 38 instead of only the 3 that need it.

### The bug ADR 0002 actually fixed was load-order dependence, not the prefix

The real defect was `_stg_dest_name` resolving clashes against a `taken` set populated as loads
proceeded, so which source won the unsuffixed name depended on load order. That is fixed by an
**explicit static mapping**, which already exists and already ships: `GQL_ENTITY_TO_STG`. A
separate schema was one way to make collisions structurally impossible; an explicit three-entry
mapping is another, and it does not tax the 29 non-colliding tables.

### Recommendation

**One `stg`. Source suffix on the colliding names only, from the existing explicit mapping.**

```
stg.athlete            stg.game_lines        stg.current_teams      # 29 tables, no tag needed
stg.game               stg.games                                    # distinct already, no tag
stg.draft_picks_gql    stg.draft_picks                              # 1 of 3 that need one
stg.calendar_gql       stg.calendar                                 # after S3 stages REST calendar
```

`predicted_points` needs no suffix at all — source rationalization Bucket A drops the REST side
outright, so the GraphQL table simply becomes `stg.predicted_points`.

The suffix is temporary by construction. All three colliders are exactly the tables that stop
existing in duplicate: `predicted_points` drops REST (Bucket A), `draft_picks` and `calendar`
merge into `core` (Bucket C). When source rationalization lands, the suffix count goes to zero
and nothing in the schema is named after a transport.

Two things this also buys: §2's misfiled `gameMedia` / `gamePlayerStat` stop being misfiled —
with one staging schema there is nowhere to misfile them, they just need snake_casing — and
`stg` stops silently meaning "REST", which §3 of the first draft flagged and then proposed to fix
with documentation.

**Cost, stated plainly.** This renames the qualified name of all 38 `stg_gql` tables, and code
references them 30+ times (`stg_gql.game` 13, `stg_gql.game_lines` 12, `stg_gql.lines_provider`
6, `stg_gql.calendar` 4). That is precisely the operation that silently broke two consumers in
§0. It is safe **only behind the catalog-resolution test**, which is why that is step 1 and this
is step 3.

**ADR 0002 needs superseding, not deleting.** Write ADR 0003 recording the measurement (2 real
collisions, 29 of 38 tagged for nothing) and the explicit-mapping alternative that was available
to the load-order bug. ADR 0002's diagnosis of that bug was right; only its remedy was
disproportionate.

## 4. `raw` — leave it alone

`raw` is source fidelity: one `payload` JSON column plus filename-derived spine columns, GraphQL
dumps `gql_`-prefixed to avoid the same 3 collisions. That prefix is doing real work and `raw` is
not a query surface. The only change it needs is §2's two misfiled tables.

One inconsistency to fix while you are in there: `raw` uses `source_file`, `stg` uses
`_source_file`. Pick one — `_source_file` is the better name (leading underscore reads as
metadata) and `stg` already has 134 tables using it against `raw`'s 120.

## 5. Column naming — already good, one rule to write down

The 2026-08-31 pass landed the important convention: a primary `id` takes the foreign-key name
it joins on (`gameId`, `teamId`, `venueId`), so joins read `ON a.gameId = b.gameId`.

`stg` keeps the API's own casing (camelCase for both REST and GraphQL payload keys); `core`
converts to snake_case (`game_id`, `season_type`). That is a defensible boundary — staging is
source-faithful, `core` is ours — but it is nowhere written down, and it is the exact seam the
audit's S2 trap lived on (`season_type` vs `seasonType`).

**Recommendation:** state it in `cfb_system_maker/CLAUDE.md` as a rule: *staging preserves source
casing; `core` is snake_case; nothing else converts.* Then the S2-class confusion has a rule to
violate rather than being a surprise.

## 6. Sequencing

| # | Change | Depends on | Risk |
|---|---|---|---|
| 1 | Catalog-resolution test (§0) | — | none; pure addition |
| 2 | List explosion opt-in (§1) | 1 | removes 53 unread tables |
| 3 | Collapse `stg_gql` into `stg`, suffix the colliders (§3) | 1 | 38 tables renamed, 30+ code refs — the gate exists for this |
| 4 | snake_case `gameMedia` / `gamePlayerStat` (§2) | 3 | 4 tables; trivial once there is one schema |
| 5 | `source_file` → `_source_file` in `raw` (§4) | 1 | column rename, 120 tables |
| 6 | ADR 0003 superseding 0002 + write down the casing boundary (§3, §5) | 3 | docs only |
| 7 | Source rationalization → suffix count goes to zero (§3) | 3 | the real project |

1–6 land in the next rebuild. 7 is what removes the last transport-named thing from the schema,
and it is a data-merge project, not a naming pass.

## What I am not recommending

- **No `dim_`/`fact_` prefixes in `stg`.** Staging has no dimensional model to describe.
- **No surrogate keys, soft deletes, audit columns, or RLS.** This is a single-user analytical
  warehouse rebuilt atomically from JSON on disk. Nothing here is mutated in place, nothing is
  multi-tenant, and `raw` files are the audit trail.
- **No index strategy.** DuckDB is columnar with automatic zone maps; the `core` builder already
  adds the few indexes that matter.
- **No mass rename for consistency alone.** §0 is why.
