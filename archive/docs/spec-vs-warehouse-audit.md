# CFBD OpenAPI spec ↔ warehouse audit

Source spec: `cfbd-openapi (3).json` (79 GET paths, downloaded 2026-08-31).
Warehouse: local `data/cfb.duckdb` — `raw` 120 tables, `stg` 119, `core` 8.

Two axes: **endpoint coverage** (does a table exist per path) and **field coverage**
(does `stg` carry every field the spec's 200-response declares).

## 1. Endpoint coverage — 79 / 79 accounted for

`python scripts/audit_endpoints.py --spec "<spec>.json"` classifies every path:

| Bucket | Count | Meaning |
|---|---:|---|
| Registered in `ENDPOINTS` | 73 | scraped, or registered `ON_DEMAND` |
| In vendored client, deliberately unregistered | 1 | `/info/usage` — account metering |
| **No client method** | **5** | spec is ahead of vendored `cfbd-python` |

Nothing is unclassified and there is no registry drift. Endpoint coverage is not the gap.

## 2. The real gap — 5 `/passing/*` paths are unreachable

The downloaded spec publishes a passing-detail family that the vendored client has no
method for, so nothing scrapes it and no `raw`/`stg` table exists. This is the only
whole-dataset miss.

| Path | Response fields | Grain |
|---|---:|---|
| `/passing/plays` | 36 | per pass play — air yards, pass depth/direction/location, YAC, target id, spike/throwaway/grounding flags |
| `/passing/teams/games` | 33 (nested `offense`/`defense`) | per team-game |
| `/passing/teams/season` | 29 (nested) | per team-season |
| `/passing/players/games` | 22 | per passer-game — aDOT, air yards, YAC |
| `/passing/players/season` | 18 | per passer-season |

Nothing else in the warehouse carries air yards, aDOT, or YAC. `raw.plays` has play text
but not the parsed passing charting fields.

**Status (2026-08-31):** closed at the registry. `cfbd-python` bumped 5.24.2 → 5.25.0
(adds `PassingApi`), and all 5 are registered in `ENDPOINTS` with `min_season=2025` —
CFBD has no passing-charting data before 2025 (2024 and earlier return an empty list;
verified against the live API). `audit_endpoints.py` now reports
`78 registered + 1 client-only + 0 no-client`. **Tables do not exist yet** — the backfill
scrape has not been run.

## 3. Field drift — 24 tables flagged, 22 are false positives

A naive spec-field-vs-`stg`-column diff flags 24 tables. Bucketing each miss against
`raw.payload` shows almost all of it is deliberate loader convention:

Counting *findings*, not tables — `games` and `coaches` each land in two buckets:

| Bucket | Findings | Verdict |
|---|---:|---|
| Spec `id` / `homeId` / `awayId` renamed by `_BARE_ID_RENAME` | 27 (24 tables) | **not a gap** — `id` → `gameId`/`teamId`/`playId`/`athleteId` etc. by design in `duckdb_load.py:122` |
| Field in `raw.payload`, dropped by the shred | 1 (`games.playoff`) | **real** — see 3a |
| Field in spec, absent from `raw.payload` | 1 (`coaches.id`) | **real** — see 3b |

So: 22 tables are rename-only, plus `games` (rename + `playoff`) and `coaches`
(rename + missing `id`).

Nested objects are not drift either: `stg` flattens with `_` (`epa.rushing` → `epa_rushing`,
`startTime.minutes` → `startTime_minutes`), so the spec's nesting is preserved, not lost.

### 3a. `games.playoff` — shredded away (loader gap)

`raw.games` carries a `playoff` key on 34,642 of 54,264 rows (52 non-null), holding the
CFP bracket object:

```json
{"awaySeed":3,"bowlName":null,"bracketSlot":"CH","competition":"cfp",
 "format":"four_team","homeSeed":1,"round":"championship","roundName":"National Championship"}
```

`stg.games` has no `playoff` column — the key is present on a minority of rows and the
shred dropped it — `duckdb_load.py` has no `playoff` exclusion, so this is not a deliberate skip (its only skip list is `_SKIP_STEMS = {"user_info"}`). Seeds, bracket slot, and round are model-relevant and are only otherwise
reachable via `raw.cfp_games`. Same class of bug as the sampling fix in `_payload_structure`.

### 3b. `coaches.id` — never scraped (stale pull)

The spec declares `id` on the coach model; **0 of 1,936** `raw.coaches` payloads carry it.
CFBD added the field after the last coaches pull. Re-pull to close. Until then, coaches join
by name only.

## 4. Registered but intentionally unstaged (8)

Registered in `ENDPOINTS` with no `stg` table, by design — parameterized or live-only:

`/coaches/profile`, `/coaches/tenures` (need `coach_id`), `/teams/matchup`, `/player/search`,
`/player/season/overview` (`PER_PLAYER` fan-out), `/live/plays`, `/scoreboard` (live), `/info`.

Not gaps; flag only if a model needs them.

## 5. Warehouse tables with no spec counterpart

Expected — these are not CFBD REST:

- **GraphQL (34 + 3 excluded)** — camelCase tables: `gameLines`, `adjustedTeamMetrics`,
  `coachSeason`, `recruitPosition`, `pollRank`, … audited separately by the same script.
- **ActionNetwork (3)** — `actionnetwork_odds` / `_history` / `_scoreboard`.
- **Ad-hoc snapshots** — `lines_2026_week*`, `pff_facet_offense_summary_21580`,
  `venue_orientation`.
- **`_ngt` variants** — `exclude_garbage_time=True` pulls of the same REST paths.

## Actions, ranked

1. Bump `cfbd-python`, register the 5 `/passing/*` endpoints, backfill. Only real dataset gap.
2. Shred `games.playoff` into `stg.games` (or confirm `raw.cfp_games` fully supersedes it).
3. Re-pull `/coaches` to pick up `id`.
