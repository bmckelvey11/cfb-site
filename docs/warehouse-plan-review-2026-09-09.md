# Review — warehouse rationalization master plan

**Reviewed 2026-09-09** against `data/cfb.duckdb` (4.8 GB, mtime 2026-09-08 16:14) and the
code on `master` at `33415ad`. Target:
`docs/superpowers/plans/2026-09-08-warehouse-rationalization-master.md`.

Reproduce with `python scripts/verify_warehouse_plan.py` (exit code = failed checks; 8 today)
and `python scripts/verify_warehouse_plan.py --coverage`.

**Verdict: do not execute §8 step 6 as written.** Its drop list would delete 6.4 M populated
values. The plan's structural argument (§1, §2) and its containment analysis (§3) both hold up;
what has rotted is everything §5 measured, and one merge key in §6 was never right.

---

## 1. Blocking — §5's drop list destroys live data

§8 step 6 says "drop … the 12 dead columns," and §5 supplies the list. Three entries are not
dead:

| Column | Rows | Non-NULL |
|---|---|---|
| `stg.plays.defenseTimeouts` | 2,600,679 | **2,377,621** |
| `stg.plays.offenseTimeouts` | 2,600,679 | **2,376,124** |
| `stg.plays.wallclock` | 2,600,679 | **1,628,388** |

Three more name tables that no longer exist — the ActionNetwork rename (`actionnetwork_scoreboard__*`
→ `an_*`) landed after §5 was measured:

- `stg.actionnetwork_scoreboard__teams.teams_standings_overtime_losses`
- `stg.actionnetwork_scoreboard__markets__markets_event_moneyline.…_odds_coefficient_score`
- `stg.actionnetwork_scoreboard__markets__markets_event_core_bet_type_6_team_score.…_odds_coefficient_score`

Only 6 of the 12 verify. One all-NULL column the plan never listed survived the rename and
belongs on the list: `stg.an_team.overtime_losses` (21,736 rows) — the successor to the first
of the three vanished entries.

**The real drop list today is 7 columns**, not 12: the 6 that verified, plus `stg.an_team.overtime_losses`.

---

## 2. §5's census is obsolete wholesale — and §8 steps 2–3 are already done

§5's three headline numbers do not survive contact with the live warehouse:

| §5 claim | Live |
|---|---|
| 332 all-NULL columns in `stg` | **11** across `stg` + `stg_gql` |
| 308 of them are loader scaffolding (`season`/`week`/`season_type`) | **0** |
| `season_type` NULL in 146 tables, `week` in 114, `season` in 48 | those columns *exist* in only 15 / 44 / 112 tables, and none is all-NULL |

Note the inversion: §5 has `season_type` as the most widespread scaffolding column at 146
tables, but `season_type` appears in only 15 `stg`/`stg_gql` tables at all. The census was
taken against a different warehouse — almost certainly before the `raw` → ingest/staging
split.

The consequence is structural, not cosmetic:

- **§8 step 2** ("stop materializing all-NULL scaffolding columns … removes 308 columns")
  removes zero. **R3 is already satisfied.** `explode_payloads` only propagates a spine column
  where the source has one — the `"season_type" if "season_type" in cols else NULL` pattern at
  `cfb_system_maker/duckdb_load.py:1386`.
- **§8 step 3** ("rebuild `stg` so the pruning applies everywhere") therefore has nothing to
  apply, and the rebuild is a multi-hour operation.
- **§8's dependency chain breaks.** Step 4 (re-measure) is declared to depend on steps 1 and 3.
  With step 3 empty, step 4 depends on step 1 alone — the user-run re-scrape. That is the only
  thing standing between today and the merges.

The 12 "future-dated, must be kept" columns are 4 today, all
`lines_2026_week2_20260908` — no `week1` tables exist.

---

## 3. §5 cites a function that does not exist, and its successor writes to `raw`

§5 attributes the scaffolding to `_insert_raw_file (duckdb_load.py:1565-1585)`. There is no
`_insert_raw_file` anywhere in the repo, and lines 1565–1585 are ActionNetwork linescore SQL.

The real code is **`_insert_json_file` at `cfb_system_maker/duckdb_load.py:1928`**, and it
inserts into **`raw`**, not `stg`. Following §5's instruction literally means editing the raw
loader — which contradicts §10 decision 4 and §12 ("`raw` naming, in any form" is out of
scope; `raw` is source fidelity). The spine reaches `stg` later, through `_RAW_SPINE`
(`duckdb_load.py:480`) and the explode path, which is where R3's pruning would have belonged
had it still been needed.

---

## 4. Bucket B's *drop verdict* fails the plan's own R6

The column evidence in §3 reproduces **exactly** — I re-ran it and got the same exclusive-column
sets, including `recruit`'s two all-NULL GraphQL columns. Bucket B's column analysis is not in
question.

What fails is the disposition. R6 gates a drop on the survivor holding "every populated column
**and at least as many distinct keys**." On year coverage the REST side loses all three:

| Pair | GraphQL | REST | Lost if GQL dropped |
|---|---|---|---|
| `recruit` / `recruits` | 93,363 rows, **2000–2027** | 45,927 rows, 2012–2025 | 14 seasons |
| `coach_season` / `coach_seasons` | 12,564 rows, **1886–2026** | 1,961 rows, 2012–2025 | **126 seasons** |
| `team_talent` / `talent` | 2,413 rows, **2015–2026** | 2,278 rows, 2015–2025 | 2026 |

Two different levels of culpability here:

- **`recruit` is an unhedged error.** §3 lists it as droppable with no provisional marker, §6
  says "drop GQL" flatly, and §4's scraper defect does not touch it. Neither side dominates —
  REST has 10 exclusive populated columns, GraphQL has 28 seasons against 14. That makes
  `recruit` a **Bucket C merge on `recruitId`**, not a Bucket B drop.
- **`coach_season` and `team_talent`** are already marked provisional by §3, so this sharpens
  rather than refutes — but "provisional" badly undersells 1886–2026 against 2012–2025.

Worth noting the repo's own audit could not have caught this:
`scripts/audit_canonical_sources.py:52` reads year coverage only from a column literally named
`season`, and every GraphQL table spells it `year`, so it prints `None` for the whole GraphQL
column. `verify_warehouse_plan.py --coverage` covers that gap.

---

## 5. The `calendar` merge key is wrong

§6 declares `calendar`'s join key as `(season, week)` with "16/16 overlap." Measured:

| | rows | distinct `(year\|season, week)` | distinct `+ seasonType` |
|---|---|---|---|
| `stg_gql.calendar` | 424 | 387 | **424** |
| `stg.calendar` | 258 | 231 | **258** |

`(season, week)` is not unique on either side — `seasonType` splits regular from postseason.
The key is **`(season, week, seasonType)`**, and the GraphQL side spells `season` as `year`, so
the merge needs a rename, not a straight join. Overlap is 258 of 258 REST rows contained in
424 GraphQL rows (REST 2012–2026, GraphQL 2002–2026); wherever "16/16" came from, it is not
this.

The other two declared keys hold: `draft_picks (year, round, pick)` is unique both sides
(13,080 / 13,080 and 3,584 / 3,584), and `game_lines (gameId, linesProviderId, period)` is
unique — though at **63,730** rows, not §7's 63,293. `period` still has exactly three values
(`game` 47,202, `firsthalf` 8,274, `firstquarter` 8,254).

Because GraphQL out-rows REST 3.6× on `draft_picks` too, both Bucket C merges must be full
outer unions with `_source` per R5, not left joins from the REST side.

---

## 6. §4's pagination argument is right, but its sort tuple is wrong — the risk is worse

§4 says `team_talent` sorts on `(season, year, week, season_type, talent)`. Three of those are
load-time scaffolding bound from the dump filename; they are never sent to the API.
`_gql_fetch` orders by relation keys plus `table.scalars` (`graphql_client.py:194-206`), and
`teamTalent`'s scalars are just `year` and `talent`.

So the actual sort is **`(year, talent)`** over 2,413 rows spanning 12 seasons — far more
tie-prone than the plan states, and ties are exactly what the code's own comment warns silently
drops rows across page boundaries. **§4's conclusion holds and R1 is more urgent than written**,
not less. Same shape for `coach_season`: scalars are `year, games, losses, postseasonRank,
preseasonRank, ties, wins`, with no team or coach to separate two coaches with identical records
in the same year.

The defect itself confirms exactly as described — `stg_gql.coach_season` (12,564 rows) carries
no coach and no team; `stg_gql.team_talent` (2,413 rows) carries no team. `GQL_RELATION_KEYS`
still holds only `pollRank`, at `cfb_system_maker/graphql_client.py:70` (§4 says line 44).

---

## 7. Staleness worth fixing, below the fold

- **ADR-0003 already exists and is accepted** (`docs/adr/0003-one-stg-schema-suffix-only-the-colliders.md`),
  and ADR-0002 is already marked superseded. §8 step 8 and §2 both list this as future work.
- **Code references are undercounted.** §2 and ADR-0003 both say "30+ … `stg_gql.game` 13,
  `stg_gql.game_lines` 12, `stg_gql.lines_provider` 6, `stg_gql.calendar` 4." Actual, excluding
  worktrees and docs: `stg_gql.game` **20**, `game_lines` 12, `lines_provider` 6, `calendar`
  **6**, plus `game_lines__backfill` 3, `game__away_line_scores` 2, `current_teams` 1 — about
  **50**. The step-7 collapse is riskier than documented.
- `stg_gql.calendar` has no `season` column at all (`year`, `week`, `seasonType`, `startDate`,
  `endDate`), which §6's key table implies it does.

---

## 8. What verified clean

Worth stating, because it means the plan's reasoning is sound and only its measurements drifted.

- **§1 structural counts, exactly:** `stg` 124, `stg_gql` 38, `raw` 116 with 34 `gql_`-prefixed,
  and exactly 3 colliders (`calendar`, `draft_picks`, `predicted_points`). §2's whole argument
  rests on these and they hold.
- **§3 Bucket A, exactly:** `draft_position` GQL-only `draftPositionId`; `draft_team` GQL-only
  `draftTeamId`, `mascot`, `shortDisplayName`; `predicted_points` GQL-only `distance`, `down`;
  no REST-only populated columns in any of the three.
- **§3 Bucket B's columns, exactly:** `coach_season` 61 REST-only, `team_talent` 1 (`team`),
  `recruit` 10 REST-only with both GraphQL-exclusive columns at 0.00 fill across 93,363 rows.
- **§3's `game`/`games` Elo fill rates:** `awayEndElo` 0.591, `homeEndElo` 0.596,
  `awayPostgameElo` 0.432, `awayPregameElo` 0.446 — all four within rounding of §3. "Neither
  dominates" is well supported.
- **§4's defect**, and `GQL_EXCLUDED`'s `gameMedia` rationale.
- **`tests/test_catalog_resolution.py` exists**, so R8's gate on step 7 is real.

---

## 9. Recommended edits

Ordered by what blocks execution.

1. **Rewrite §5 against the current warehouse.** The drop list becomes 7 columns; delete the
   three `stg.plays.*` entries and the three vanished ActionNetwork ones, add
   `stg.an_team.overtime_losses`. Replace the 332 / 308 / 12 / 12 breakdown with 11 / 0 / 4 / 7.
2. **Delete §8 steps 2 and 3, and R3** — or restate R3 as already satisfied, with
   `explode_payloads` cited as the mechanism. Re-anchor step 4 on step 1 alone.
3. **Move `recruit` from Bucket B to Bucket C**, merging on `recruitId`. Restate Bucket B's
   remaining two as "column-superset REST, coverage-superset GraphQL — both merge unless
   step 4 changes the picture," so §3 stops contradicting R6.
4. **Fix `calendar`'s key** to `(season, week, seasonType)` with the `year` → `season` rename,
   and drop the "16/16 overlap" figure.
5. **Correct the code citations** — `_insert_json_file` at `duckdb_load.py:1928` (and note it
   writes to `raw`), `GQL_RELATION_KEYS` at `graphql_client.py:70`, `team_talent`'s sort as
   `(year, talent)`.
6. **Update §8 step 8 and §2** to record ADR-0003 as landed, and re-count the `stg_gql`
   references before step 7.
7. **Pin the numbers to a run, not a date.** Every measured claim in §1, §3, §5, §6 and §7
   should cite `scripts/verify_warehouse_plan.py` output rather than sit inline as prose —
   §5 is what happens otherwise.

**Not reviewed:** §3 Bucket C's remaining five pairs (`game_lines`, `coach`, `conference`,
`recruiting_team`, `draft_picks` column diffs) and §10's open item that Round 5's fixes were
never re-reviewed.
