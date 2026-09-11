# Dropping Bucket A's REST sides and the seven dead columns

**2026-09-10.** Reproduce with `python scripts/verify_warehouse_plan.py` and
`python scripts/audit_pair_columns.py --pair draft_team --verbose`. Plan:
[§3 Bucket A and §5](superpowers/plans/2026-09-08-warehouse-rationalization-master.md).

## The question

The rationalization plan's §3 put three GraphQL/REST pairs in **Bucket A** — GraphQL is the
superset, so the REST side is droppable — and §5 listed **7 columns** as genuinely dead.
The drop is proof-gated by **R6**: the survivor must hold every *populated* column **and**
at least as many distinct keys. So: does each of the three actually pass R6, and are the
seven still dead?

## Method

Column half from `scripts/audit_pair_columns.py --verbose`, which compares columns on a
loose key (lowercased, underscores dropped) and reports what is left exclusive with its
fill rate. Key half measured per pair on whatever columns the two sides share, in both
directions. Dead columns from `scripts/verify_warehouse_plan.py`, which re-derives §5's
census rather than trusting it.

**Data:** local `cfb.duckdb` before the drop — 147 `stg` + 38 `stg_gql` tables, 11 all-NULL
columns.

## Result: two of three drop, and the third is not droppable

| Pair | Column half | Key half | Verdict |
|---|---|---|---|
| `draft_position` / `draft_positions` | GQL adds `draftPositionId`; REST-exclusive none | 29 / 29 distinct, 0 REST keys absent from GQL | **drop** |
| `draft_team` / `draft_teams` | GQL adds `draftTeamId`, `shortDisplayName`, `mascot` | 32 / 32 rows, all match on `(location, displayName)` | **drop**, but see below |
| `predicted_points` / `predicted_points` | GQL adds `distance`, `down` | **fails** — see below | **keep** |

### `draft_team` passed R6 only after reading values, not column names

The loose column key called `nickname` **shared**: both sides have a column by that name.
They are not the same concept.

| | REST `nickname` | GQL `nickname` | GQL `mascot` |
|---|---|---|---|
| Cincinnati | `Bengals` | `Cincinnati` | `Bengals` |
| Tennessee | `Titans` | `Tennessee` | `Titans` |

GraphQL's `nickname` is the location repeated; the real nickname lives in `mascot`. On a
name-only reading, 29 of 32 REST rows had no GraphQL twin and the pair failed R6. On the
values, **REST's `nickname` equals GraphQL's `mascot` on all 32 rows**, and the one row
where `mascot` is NULL (Washington) is NULL on the REST side too. So R6 holds and REST is
droppable — but it holds through a rename the audit script could not see.

This is a second failure mode for the loose key, and the mirror of the one already
documented: `team_teamId` vs `team_id` was a false *exclusive* (different names, same
concept); `nickname` vs `nickname` is a false **shared** (same name, different concepts).
The second is the dangerous one — it is what would have let a column be dropped that only
*looked* contained. Recorded in `audit_pair_columns.py`'s docstring.

### `predicted_points` fails R6 and cannot be repaired

REST has 10,140 rows carrying only `(yardLine, predictedPoints)`. GraphQL has 19,800
carrying `(down, distance, yardLine, predictedPoints)`, unique on the first three.

**The key is lost at the API, not by the flattener.** `cfb_system_maker/scrapers.py:82`
registers the endpoint as `GRID` — one call per `(down, distance)` — but the response does
not echo those parameters, and `data/raw/predicted_points.json` is a flat list of 10,140
objects with exactly two keys, `predictedPoints` and `yardLine`, on every one. There is no
flatten to fix.

Nor are the values a rounded copy. REST holds 644 distinct `predictedPoints` values rounded
to 2 decimals; GraphQL holds 19,800 at full precision (`6.06` vs `6.061978724879557`). Of
REST's 10,140 rows, **1,339 match a GraphQL row on `yardLine` within 0.005** — 13%. That is
not enough to call it contained and not enough to call it contradicted, because without
`down`/`distance` an unmatched REST row cannot be distinguished from a grid cell GraphQL
covers and REST does not.

R6 is a proof gate. It does not pass, so `stg.predicted_points` stays. **The pair moves out
of Bucket A**; §3's "3 pairs" heading is now two.

### The seven dead columns are still dead, and one had a writer

All 7 confirmed 100% NULL against the current warehouse. They are not one kind of problem:

| Column | Rows | How it arrives |
|---|---|---|
| `stg.an_team.overtime_losses` | 21,736 | **written by name** in `_AN_TEAM_SQL` |
| `stg.team_stats.statValue_anyof_schema_1_validator` | 112,242 | generic explode |
| `stg.team_stats__statValue_any_of_schemas.` *(same)* | 224,484 | generic explode |
| `stg_gql.game_weather.windGust` | 27,857 | generic explode |
| `stg_gql.poll_type.abbreviation` | 8 | generic explode |
| `stg_gql.recruit.overallRank` | 93,363 | generic explode |
| `stg_gql.recruit.positionRank` | 93,363 | generic explode |

`overtime_losses` is the odd one. ActionNetwork's payload **does** carry the key — it
appears in the `standings` block of all 10,868 `stg.an_scoreboard` rows, as
`"standings":{"draw":null,"loss":0,"overtime_losses":null,"ties":0,"win":0}` — and is null
on every one. It is a field of AN's shared multi-sport schema that college football never
fills. Because `_AN_TEAM_SQL` selects it explicitly, a sweep would have deleted it and the
next flatten would have recreated it, forever. Fixed at the writer instead: the line is
removed, so the column is never created.

The other six have no writer to edit — the payload carries the key and the source never
fills it — so they are swept after every load by `duckdb_load._DEAD_COLUMNS`, which shares
the existing spine sweep's **fail-closed guard**: a column holding any value is kept and
reported, never dropped. That is what makes the list safe to re-run after a re-scrape
rather than a decision taken once.

## How the drop is implemented, and why not with `DROP TABLE`

`stg` is rebuilt by `explode_payloads` from `raw` on every refresh, and `raw` is out of
scope (plan §12). A `DROP TABLE stg.draft_teams` survives exactly until the next load. So:

- **Tables:** `duckdb_load._SUPERSEDED_REST` skips them at explode time.
- **Six columns:** `duckdb_load._DEAD_COLUMNS`, swept after every load.
- **One column:** removed from `_AN_TEAM_SQL`.

Removing the scraper entries at `cfb_system_maker/scrapers.py:64-65` is deliberately **not**
part of this — it is `#scraper-entry-cleanup`. Until then the scraper still writes
`raw/draft_positions.json` and the loader ignores it, which is a coherent and reversible
half-state.

`verify_warehouse_plan.py`'s dead-column check is **inverted** by this change. It used to
fail when a listed column went missing; it now fails when one comes back, and says which
half regressed — populated means the source started filling it and the R6 verdict must be
re-taken, all-NULL means the sweep stopped running.

## Verification

Applied to a scratch copy first. `stg` 147 → 145 tables, all-NULL columns 11 → 4 (the four
future-dated `lines_2026_week2_*` scores, kept on purpose), verifier `0 failed check(s)`.

Then the check that matters for a sweep rather than a migration: `explode_payloads` and
`explode_an_children` were re-run on the scratch copy over every affected source.
`stg_gql.recruit` rebuilt at 93,363 rows and 10 columns, `stg.an_team` at 21,736 — and
**none of the nine objects came back**. Live warehouse then matched: `0 failed check(s)`.

## What this does not support

- **It does not establish that GraphQL's `predicted_points` is correct**, only that REST's
  cannot be checked against it. The 13% match rate is a statement about the missing key,
  not about either side's numbers.
- **It does not drop anything in Bucket B or C.** `coach_season`, `team_talent` and the
  eight Bucket C pairs are merged, not superseded; see
  [the containment remeasure](warehouse-containment-remeasure-2026-09-10.md) and
  [the Bucket C merges](core-merge-bucket-c-2026-09-10.md).
- **It does not re-derive the other nine pairs' R6 verdicts.** Only the three Bucket A
  pairs were read column by column and key by key here.
- **The `draft_team` finding does not mean the audit script is wrong**, only that its
  output is evidence and not a verdict — which its own docstring already says. It does mean
  a same-name pair must be read on values before it counts as shared.
- **It does not free any meaningful storage.** Two lookup tables of 29 and 32 rows. The win
  is that a query against `stg.draft_teams` now fails loudly instead of returning a stale
  subset, and that seven columns can no longer be mistaken for data.
