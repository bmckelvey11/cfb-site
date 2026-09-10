# Re-measuring containment after the relation-key repair

**2026-09-10.** Reproduce with `python scripts/audit_pair_columns.py --pair coach_season
--verbose`, `python scripts/verify_warehouse_plan.py --coverage`, and
`python scripts/audit_canonical_sources.py`.

## The question

`#gql-relation-keys` gave `coachSeason` and `teamTalent` the FK columns they had been
missing ([`gql-relation-keys-2026-09-10.md`](gql-relation-keys-2026-09-10.md)). Section 3 of
the [rationalization plan](superpowers/plans/2026-09-08-warehouse-rationalization-master.md)
had assigned both to **Bucket B** — REST the column superset, GraphQL the coverage superset,
neither droppable — with the explicit caveat that the repair "may add the FK columns that
make the merge a clean join rather than a union, but it cannot make either side droppable.
Re-measure at step 2 regardless."

So: did the buckets move, and did the merges become joins?

## Method

The plan's §3 tables were measured by hand. `scripts/audit_pair_columns.py` is new here and
makes them reproducible — a bidirectional column diff with fill rates for all twelve pairs,
which is what R6's "survivor holds every populated column" half is decided on. Columns are
compared on a loose key (lowercased, underscores dropped) because the two transports spell
the same concept differently; anything left exclusive is reported with its fill rate rather
than judged automatically, the same stance `audit_canonical_sources.py` takes.

Coverage came from `verify_warehouse_plan.py --coverage` (year span per pair;
`audit_canonical_sources.py` reads year span from a column named `season` and so reads None
for every GraphQL table, which spells it `year`).

**Data:** local `cfb.duckdb`, rebuilt 2026-09-10 after the re-scrape — 310 tables.

## Result: both stay in Bucket B, for changed reasons

Coverage is unchanged, because the re-scrape returned identical row counts:

| Pair | GraphQL | REST |
|---|---|---|
| `coach_season` / `coach_seasons` | 12,564 rows, 1886–2026 | 1,961 rows, 2012–2025 |
| `team_talent` / `talent` | 2,413 rows, 2015–2026 | 2,278 rows, 2015–2025 |

The column diff moved on both, in opposite ways.

### `coach_season` — the merge is now a clean join

§3 recorded GQL-exclusive as **none** and REST-exclusive as **61 columns including
`coach_id`, `team_id`**. After the repair:

| | Before | After |
|---|---|---|
| GQL-only (populated) | none | 1 — `team_teamId` (0.980) |
| REST-only (populated) | 61 | **57** |
| Shared | — | 12 |

`coach_id` moved out of REST-only and into **shared**: both sides now carry it under the
same name. `team_teamId` reads as GQL-exclusive only because REST spells it `team_id`; it is
the same concept, and the loose key cannot see that.

**The merge is a join, not a union.** `(coach_id, team_id, year)` is unique on both sides —
12,564 of 12,564 and 1,961 of 1,961 — and matches **1,961 of 1,961 REST rows, zero
unmatched**. That is exactly the outcome §3 said the repair might deliver, now measured.

Still not droppable in either direction: REST holds 57 populated columns GraphQL lacks (the
`cfp_*`, `pollResume_*`, `recordSplits_*`, `teamMetrics_*` blocks), and GraphQL holds 126
more seasons.

### `team_talent` — the column direction reversed

§3 recorded GQL-exclusive as **none** and REST-exclusive as **`team` (1.00)**. After the
repair:

| | Before | After |
|---|---|---|
| GQL-only (populated) | none | 3 — `team_teamId`, `team_school`, `team_conference` (0.997) |
| REST-only (populated) | 1 (`team`) | 2 — `team` (1.00), `season` (1.00) |

**GraphQL now carries the FK and REST does not.** REST's `team` is a school *name* needing
resolution; GraphQL's `team_teamId` joins directly. `season` is REST's spelling of
GraphQL's `year`, not a real exclusive.

That made REST look droppable — GraphQL out-rows it (2,413 to 2,278), out-covers it
(2026 vs 2025), and now holds a superset of its identity columns. **It is not.** R6's
containment half fails: **17 REST rows have no GraphQL twin** on `(season, team)` —
Jacksonville and St. Francis (PA), schools absent from GraphQL's `currentTeams` source. Same
class as the 8 GraphQL rows whose `team` relation is null. So Bucket B holds, and the merge
is a full outer union on the team-name key, not a join.

## What this does not support

- **It does not re-measure the other ten pairs' verdicts.** `audit_pair_columns.py` reports
  all twelve and the counts reproduce §3's structure, but only the two repaired pairs were
  read column by column. The other ten were not re-scraped and have no reason to have moved.
- **It does not settle `coach_season`'s grain problem.** The 118 school-seasons with 2–3
  coaches (§6) are unaffected by a clean join on `(coach_id, team_id, year)`;
  `core.coach_season_unmatched` is still `#core-merge-bucket-c`'s job.
- **The loose column key is not a mapping.** It matched `coach_id` to `coach_id` and missed
  `team_teamId` to `team_id`. The near-miss detector in the script also missed that pair,
  because the shared token is swallowed by the doubled `team`. Read the verbose output;
  do not trust the counts alone.
- **It does not license dropping anything.** No bucket moved to A, so the drop list is
  unchanged and `#warehouse-drop-superseded` still targets only Bucket A's three REST
  tables.

## Bearing on the chain

`#warehouse-remeasure-containment` is satisfied: the two repaired pairs are re-measured
against the new pull and both verdicts are unchanged at bucket level, with one substantive
gain — `coach_season` merges by join rather than union, which `#core-merge-bucket-c` should
now assume. §3's Bucket B table is restated in the plan.
