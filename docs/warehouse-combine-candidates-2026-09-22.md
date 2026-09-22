# Combine candidates in `stg` and `core` — 2026-09-22

## Question

Which non-`raw` tables hold the same concept and should be combined? The 13 REST/GraphQL
pairs in the [rationalization plan](superpowers/plans/2026-09-08-warehouse-rationalization-master.md)
§3 were paired **by name** (`coach_season` / `coach_seasons`) and are settled (buckets A–C,
[bucket C merge](core-merge-bucket-c-2026-09-10.md),
[bucket A drop](warehouse-drop-superseded-2026-09-10.md)). This covers what name matching
cannot see: the same concept under different names on each side.

## Method

1. Inventory all 190 `stg` / `core` / `meta` tables, and screen every pair of root tables
   for column-set overlap (Jaccard ≥ 0.6 on lowercased, underscore-stripped names). Those
   are the columns that count toward a pair; `season`, `year`, `week` and `_source_file`
   are left out.
2. Keep the hits that core builders don't already consume. Add the pairs found by
   hand: the screen skips `__` children, and it misses pairs whose vendors spell the
   same column differently.
3. For each candidate, measure key coverage in both directions and value agreement on
   the shared keys.

Data: local `data/cfb.duckdb` as of 2026-09-22 (the last load was the 2026-09-16 refresh
plus that day's explode additions). Reproduce with
`python scripts/audit_combine_candidates.py` (read-only). Every number below comes from
that script.

## Candidates, ranked

| # | Combine | Why | Shape |
|---|---|---|---|
| 1 | `poll_rank` (GQL) + `rankings__polls__polls_ranks` (REST) → `core.fact_poll_rank` | Fixes a documented defect: `fact_poll_rank` is built from GQL only, and that dump stops at **2026 week 1**. REST has weeks 1–3. | Union; REST wins 2012+ |
| 2 | `adjusted_player_metrics` (GQL, long) ⊇ `adjusted_player_passing` + `_rushing` + `kicker_paar` (REST, wide) | GQL holds every REST key at full precision; REST is rounded | New `core` fact from GQL; REST droppable |
| 3 | `adjusted_team_metrics` (GQL) ⊇ `adjusted_team_season` (REST) | Same metrics, identical values; GQL adds 2008–2011 | Repoint the ratings merge's `adj_` source to GQL |
| 4 | `game__{home,away}_line_scores` (GQL) ⊇ `games__{home,away}_line_scores` (REST) | Identical where both exist; GQL has 339 more games | One `core` game × side × period table |
| 5 | `transfer` (GQL) + `transfer_portal` (REST) | 99.8% the same rows; REST carries origin, destination and position | Union → `core` transfer fact |
| 6 | 9 `_ngt` twins → long form with a garbage-time flag | Tidiness only; nothing reads them | Low value |

### 1. Polls — the one with a live defect

| | GQL `poll_rank` | REST `rankings` |
|---|---|---|
| span | 1936–2026, 49,948 rows | 2012–2026, 23,223 rows |
| 2026 latest week | **1** | **3** |
| NULL team id | n/a (name-keyed; 291 rows lost resolving names) | **0** — carries `teamId` |

AP Top 25, 2012–2025, keyed on `(season, week, seasonType, school)`: **5,729 of 5,729
match, 0 rank disagreements.** `seasonType` has to be in the key. Without it, week-1
postseason ballots collide with week-1 regular ones, and 384 false disagreements appear.

The union is: REST for 2012+ (fresher, and keyed by id), GQL for 1936–2011. **Neither
source is on the daily refresh.** `refresh_cfbd.py`'s `DEFAULT_ONLY` is
`games, lines, calendar, conferences, venues`. The REST file is fresher only because it
was scraped by hand on 2026-09-16. Adding `rankings` to `DEFAULT_ONLY` is what keeps it
current.

### 2. Adjusted player metrics

| metric | REST rows | GQL rows | matched | off by > 0.005 | REST-only | GQL-only |
|---|---:|---:|---:|---:|---:|---:|
| passing (`wepa`) | 2,497 | 2,494 | 2,497 | 0 | 0 | 6 |
| rushing (`wepa`) | 5,280 | 5,268 | 5,280 | 0 | 0 | 2 |
| field goals (`paar`) | 1,734 | 1,740 | 1,734 | 0 | 0 | 8 |

Every REST row finds a GQL twin. Every exact-value "disagreement" is REST's 2-decimal
rounding. REST matches more rows than GQL has keys because REST repeats some
`(athlete, year)` pairs (passing 9, rushing 14). So GQL passes both halves of R6
(columns and keys). The REST side is droppable, the way the bucket A pairs were.

### 3. Adjusted team metrics

GQL 2008–2025 / 2,363 rows; REST 2012–2025 / 1,848. **0 REST keys absent from GQL.** All
22 REST metrics map to a GQL column under another name (`epa_passing` → `passingEpa`,
`successRate_total` → `success`, …; the map is `ADJ_TEAM_COLUMNS` in the script).
Across 1,848 × 22 cells, **0 differ** by more than 0.005. REST's only extras are the
`team` and `conference` names, which `dim_team` already supplies.
`fact_team_season_rating_postgame` reads REST today. Switching its `adj_` source would
add 2008–2011 and lose nothing.

### 4. Line scores

REST and GQL agree on **183,211 of 183,211** matched periods on each side, home and away.
GQL covers 45,586 games and REST 45,247. **0 REST games are missing from GQL**, and 339
GQL games are missing from REST. `game_team__line_scores` (GQL, per team, 44,720 games) and
`an_linescore` (Action Network) are two more copies. Neither is measured here. A
`core` linescore table would serve the 1H/1Q totals work, which currently has no scored
first half in `core`.

### 5. Transfers

18,880 rows match on `(season, firstName, lastName, transferDate)`. That leaves 29 GQL-only
and 13 REST-only rows, so neither side contains the other. REST is the column superset
(`origin`, `destination`, `position`). This makes it a bucket C shape: a full outer union.

### 6. `_ngt` twins

The garbage-time-excluded variants are a second source (`cfb_system_maker/CLAUDE.md`).
They cannot be derived from the base table. On game/team grain, the ngt keys are a
subset of the base keys: `advanced_game_stats` 29,518 of 29,784, `ppa_games` all 22,778.
On player grain, a few ngt keys don't match base keys: `player_usage` 45,290 rows,
44,844 shared. A long form with an `excludes_garbage_time` flag halves the table count.
Nothing reads either side, so this is tidiness.

## Not candidates

- **`pregame_win_prob` vs `game_team.winProb`.** 10,631 of 11,028 home values differ by
  more than 0.001. They are different quantities: `winProb` sits next to `startElo` and
  reads as an Elo win expectancy, not the vendor's pregame model.
- **`sp` / `conference_sp`**, **`passing_*_games` / `passing_*_season`**,
  **`ppa_games` / `ppa_teams`**. Different grain (team vs conference, game vs season).
- **`an_history` / `an_market`.** Already documented as the same 19-column grain (1H/1Q
  vs full game). Their overlap on `period = 'event'` (16,024 `an_history` rows) is not
  measured here.
- **`srs` / `srs_expanded`**, **`teams` / `fbs_teams`**, **`draft_*`**. Already merged or
  dropped by prior work.
- **Havoc.** `advanced_box_score__teams_havoc` has no `gameId` (only team names and
  `gameInfo_*`), so it cannot be keyed against `game_havoc_stats` without a name join.
  Not measured.
- **PFF (21 tables) and Massey.** Single-vendor families with their own grain. Nothing
  overlaps across vendors at the table level.

## What this does not support

- The Jaccard screen misses pairs whose vendors name the same columns differently.
  Candidates 1–5 were confirmed by hand, not found by the screen. Others may remain.
- Nothing here was built. Each candidate is measured, not implemented. A `core` build
  still needs the usual orphan and PK checks against `dim_team` / `fact_game`.
- "REST droppable" (2, 3) means it passes R6 on today's data. It is still a loader skip
  (`duckdb_load._SUPERSEDED_REST`), and it has to be re-measured after any re-scrape.
- The poll `week` convention is still unverified
  ([core expansion](core-expansion-2026-09-18.md)). Combining sources doesn't make a poll
  safe to use as a pre-game feature.
