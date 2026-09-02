# Warehouse schema recommendation — 2026-09-02

Naming and structure recommendation for the next rebuild. Asked: drop `stg_gql`, drop the
double-underscore names, review everything.

Evidence is the live warehouse (301 tables) plus every `<schema>.<table>` literal in the repo.
Prior decisions cited, not restated: [ADR 0002](adr/0002-graphql-stg-tables-in-separate-schema.md),
[naming rationalization](superpowers/specs/2026-08-31-warehouse-naming-rationalization.md),
[source rationalization](superpowers/specs/2026-09-01-warehouse-source-rationalization.md),
[audit](duckdb-audit-2026-09-02.md).

## Recommendation in one line

**Stop generating the `__` tables, keep `stg_gql`, and make `core` the clean-name surface —
but ship a rename guard before any of it.**

That is not the full ask. `stg_gql` I am recommending against removing *now*, for a reason worth
your judgement, laid out in §3. Everything else is a yes.

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
`raw.gql_game_media` / `stg_gql.game_media`, `raw.gql_game_player_stat` /
`stg_gql.game_player_stat`. This is a consistency hole in the existing scheme, not a new scheme.

Note `stg.gamePlayerStat` is the table carrying the 998 season-less rows from a stale
whole-corpus source file (audit S6) — worth doing both at once.

## 3. `stg_gql` — I recommend keeping it, and here is the constraint you are choosing against

You asked to remove it. The reason not to is a correctness constraint that has not changed since
ADR 0002, so I would rather put it in front of you than quietly satisfy the request.

**Bare names in one staging schema collide.** Three GraphQL entities collide *exactly* with a
REST table once snake_cased:

```
draftPicks       → draft_picks        (REST: draft_picks)
predictedPoints  → predicted_points   (REST: predicted_points)
calendar         → calendar           (REST: calendar)
```

Seven more differ only by a trailing `s` — `game`/`games`, `coach`/`coaches`,
`conference`/`conferences`, `recruit`/`recruits`, and so on. Those are not duplicates to
deduplicate: the [source rationalization](superpowers/specs/2026-09-01-warehouse-source-rationalization.md)
measured all 13 pairs and found **7 genuinely complementary** — `game`/`games` carry Elo under
different names *and different coverage* (GraphQL `awayEndElo` 0.59 filled vs REST
`awayPostgameElo` 0.43); neither dominates.

The pre-ADR scheme resolved this with a `taken` set populated as loads proceeded, so **which
source won the unsuffixed name depended on load order** — a live provenance-swapping bug. Any
single-schema staging layer has to re-solve that. A separate schema makes the collision
structurally impossible instead of prevented by convention.

**What I would do instead:** treat `core` as the clean-name surface and leave staging as
plumbing. `core` is already exactly what you are asking for —

```
core.dim_week   core.dim_team    core.dim_venue   core.dim_conference   core.dim_lines_provider
core.fact_game  core.fact_game_line   core.fact_game_team
```

snake_case, singular dims, `dim_`/`fact_` prefixes, no source in any name, no `__`. Consumers
should read `core`; `stg`/`stg_gql` should be an implementation detail nobody types.

**The honest path to actually deleting `stg_gql`** — if you want it gone, this is the sequence,
and it is the source-rationalization plan, not a rename:

1. Land the 6 droppable pairs (3 where GraphQL is the superset, 3 where REST is) — those
   concepts stop existing twice.
2. Merge the 7 complementary pairs into `core` facts/dims, which is where they were always going.
3. `stg_gql` then holds only entities with no REST counterpart, and the collision set is empty.
   *Then* one staging schema is safe, and the merge — not a rename — is what made it safe.

Doing step 3 first is the thing ADR 0002 rejected, and the reason still holds.

**One asymmetry worth naming even if you keep the split:** `stg` silently means "REST". The
symmetric spelling is `stg_rest` + `stg_gql`. I am *not* recommending it — it renames the
qualified name of 134 tables to fix a documentation problem, and §0 says renames are the
expensive thing here. Fix it in `cfb_system_maker/CLAUDE.md` instead.

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
| 3 | Route `gameMedia` / `gamePlayerStat` through the GQL mapping (§2) | 1 | renames 4 tables; 1 consumer (`stg.gamePlayerStat`) |
| 4 | `source_file` → `_source_file` in `raw` (§4) | 1 | column rename, 120 tables |
| 5 | Write down the casing boundary + the `stg`-means-REST note (§3, §5) | — | docs only |
| 6 | Source rationalization → then reconsider `stg_gql` (§3) | 2, 3 | the real project |

1–5 are small and land in the next rebuild. 6 is the one that actually earns the schema you
asked for, and it is a data-merge project, not a naming pass.

## What I am not recommending

- **No `dim_`/`fact_` prefixes in `stg`.** Staging has no dimensional model to describe.
- **No surrogate keys, soft deletes, audit columns, or RLS.** This is a single-user analytical
  warehouse rebuilt atomically from JSON on disk. Nothing here is mutated in place, nothing is
  multi-tenant, and `raw` files are the audit trail.
- **No index strategy.** DuckDB is columnar with automatic zone maps; the `core` builder already
  adds the few indexes that matter.
- **No mass rename for consistency alone.** §0 is why.
