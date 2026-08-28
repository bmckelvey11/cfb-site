# CFB DuckDB warehouse plan

This folds a downloaded generic warehouse design (`college-football-duckdb-plan.md`,
saved locally, not part of this repo) into what this repo's data actually looks like
today. The source plan is solid Kimball-style practice — raw/stg/core/mart layering,
`dim_`/`fact_`/`bridge_` naming, atomic `CREATE OR REPLACE TABLE AS SELECT` refreshes —
but it was written with no visibility into this project's real consumers, real table
inventory, or the two correctness bugs already found in the existing loader. This doc
is the corrected, scoped-down version: what to keep, what to cut, what the plan didn't
know to ask about, and a phase order grounded in what's actually built.

**Prerequisite, not part of this plan:** [`docs/duckdb-rebuild-spec.md`](duckdb-rebuild-spec.md)
specs a clean rebuild of the existing `raw`/`stg` loader and flags a bug (`_post_wk`
files silently losing their `season`) that must be fixed before anything below is built
on top of `raw`/`stg` — a `core` fact built on a season-less postseason row inherits the
same hole.

## Verdict, up front

The schema shape (`raw → stg → core → mart → app`) and naming convention are worth
keeping. The scope is not: the downloaded plan designs for a general-purpose college
football analytics platform (players, recruiting, draft, coaching staff, plays, drives)
when this repo has three narrower, already-defined consumers, none of which touch that
depth. Building the full plan first is solving a problem nobody has yet.

## What the plan didn't have visibility into

**Three real consumers exist today, not a hypothetical web app:**

| Consumer | What it needs |
|---|---|
| `cfb_system_maker` (Bet Labs parity backtester) | Game-level spread/total records + registry features — `GameRecord`, `games.csv`, `features.json` |
| `cfb_totals_model` (totals-line CLV model) | The same games/lines data, read from `cfb_system_maker`'s `data/` |
| `over_zero` (Arscott floor-bias research) | Games/lines plus its own 1H-line and ActionNetwork snapshots not shared with the other two |

(All three are being merged into this repo right now — see `consolidation.md`.) None of
the three model athletes, coaches, recruiting, or plays. The plan's `dim_athlete`,
`dim_coach`, `bridge_coach_team_staff_history`, `bridge_recruit_school_history`,
`fact_draft_pick`, drive/play facts, and roster-snapshot facts have zero consumers
right now. Building them is not wrong, it's just not Phase 1 — see `## Cut or
deferred` below.

**97 raw tables already exist, and they're messier than the plan assumes.** The plan's
staging list has ~30 source-shaped tables, one per entity. The live database has 97
`raw` tables because CFBD is scraped through both REST and GraphQL, and the two APIs
name the same entity differently. `explode_payloads` (the existing `stg` builder) does
**not** conform these into one table — it mirrors `raw` 1:1, one `stg` table per `raw`
table, colliding only on an exact name match (the `calendar`/`calendar_gql` case
`duckdb-rebuild-spec.md` already documents). Confirmed duplicate/near-duplicate
families sitting in `raw` right now:

| Entity | REST-shaped table(s) | GraphQL-shaped table(s) |
|---|---|---|
| Team | `teams`, `fbs_teams` | `currentTeams`, `historicalTeam` |
| Coach | `coaches` | `coach`, `coachSeason` |
| Game | `games` | `game` |
| Game/team stats | `game_team_stats` | `gameTeam` |
| Player game stats | `game_player_stats` | `gamePlayerStat` |
| Draft picks | `draft_picks` | `draftPicks` |
| Draft position | `draft_positions` | `draftPosition` |
| Draft team | `draft_teams` | `draftTeam` |
| Recruit | `recruits` | `recruit` |
| Recruiting team | `recruiting_teams` | `recruitingTeam` |
| Predicted points | `predicted_points` | `predictedPoints` |
| Conference | `conferences`, `conference_sp` | `conference` |
| Calendar | `calendar` | `calendar_gql` (renamed on collision) |

The plan's `stg.team`, `stg.game`, `stg.coach`, etc. assume this dedup already
happened. It hasn't — there is no code anywhere in this repo that picks a winner
between, say, `raw.games` and `raw.game`, or merges them. That reconciliation is real,
new work, and it's the actual hard part of building `core` — harder than the plan's
"flatten JSON into staging tables" framing suggests.

**A `core`-grain fact already exists, in Python, not SQL.** `GameRecord`
(`cfb_system_maker/models.py`) is one row per game with home/away already joined into
columns — closer to the plan's `fact_game_team` grain collapsed onto `fact_game`, not
a separate `fact_game`/`fact_game_team` pair. `features.json` (built by
`enrich.py`/`running_stats.py`) is the `mart.model_game_team_features` the plan
describes, already built, already serving the web UI and both other consumers. Building
`core.fact_game` and `mart.model_game_team_features` in SQL is not additive — it's a
second representation of data that already has one, in Python, that three consumers
already depend on. That's a real migration decision (rewrite `normalize.py`/`enrich.py`
to read from DuckDB instead of JSON, per the "Option 2" already raised and deferred in
`docs/duckdb-rebuild-spec.md`'s companion conversation), not a free addition. Don't
build the SQL version silently alongside the Python one without deciding which is
truth.

**`md:cfb` (MotherDuck) already exists and mirrors the local file** — confirmed live,
196 tables, same `raw`/`stg`/`meta` layout. `consolidation.md` documents this as "a
MotherDuck mirror (same pattern as Greenview), not a local folder," for cross-machine
sharing. No code pushes to it; it's a manual `duckdb` CLI session against the rebuilt
file. The plan's `app` schema, if built, would need the same manual-push story unless a
sync step gets written.

## Adopted from the plan, as-is

- Schema names and grain: `raw`, `stg`, `core`, `mart` — matches the existing
  `raw`/`stg` split already implemented, `core`/`mart` net-new.
- Naming convention: `dim_<entity>`, `fact_<grain>`, `bridge_<relationship>`, no
  `cfb_`/`cfbd_` prefix (the database is already all-college-football; a prefix on
  every table is one team down the wrong ladder rung — the database name already
  supplies that context).
- Raw payload preservation + typed staging before conformed modeling — this repo's
  `raw`/`stg` split already does exactly this.
- `CREATE OR REPLACE TABLE AS SELECT`, batch/full refresh — matches the existing
  loader's atomic `.building` → `replace()` rebuild, not incremental upsert.
- Grain-first fact/bridge design discipline (the plan's `## Recommended grains`
  table) — good practice, keep the habit even where the entity list below is
  trimmed.

## Cut or deferred, and why

| Plan item | Status | Reason |
|---|---|---|
| `ref`, `model`, `qa`, `scratch` schemas | Cut for now | Nothing to put in them yet. `ref` needs a real alias-mapping problem (none identified — CFBD team/conference names are already consistent across endpoints, unlike the table-name collisions above). `model` needs a trained artifact worth querying in SQL (today's model outputs are `v1_fit.json` and a JSONL ledger — fine as files until something needs to join predictions against `core` at scale). `qa` is a handful of assertions — `tests/test_duckdb_load.py` already fills that role. `scratch` is just an ad hoc `duckdb` CLI session; it doesn't need a standing schema. Add each only when a concrete need shows up — a schema holding zero tables is a hypothesis, not infrastructure. |
| `dim_athlete`, `dim_coach`, `bridge_athlete_team_history`, `bridge_coach_team_staff_history`, `bridge_recruit_school_history`, `bridge_game_athlete_availability`, `fact_draft_pick`, `fact_recruit`, `fact_coach_season` | Deferred | Zero of the three current consumers model players, coaches, or recruiting. The raw data is already scraped (`raw.athlete`, `raw.coach`, `raw.recruit`, `raw.draftPicks`, etc.) and isn't going anywhere — building the dimensional layer on top is cheap *later*, once something actually needs it. |
| `fact_drive`, `fact_play`, `bridge_play_athlete_participation`, `fact_roster_snapshot`, `fact_transfer_portal_entry` | Deferred (plan's own Phase 3) | Agreed with the plan here — these are play-by-play depth nothing today consumes. |
| `app` schema and app-facing views | Deferred | Depends on the hosted-web-app decision, which is still open (Flask currently reads `games.csv`/`features.json`, not any DuckDB table — see the hosting conversation this doc doesn't repeat). Building curated `app.*` views before there's an app pointed at them is building a contract for a client that doesn't exist yet. |

## What the plan is missing that must be added

**A raw → core entity map.** Before any `core.dim_team`/`core.fact_game` can be a
`CREATE ... AS SELECT`, something has to decide, per entity in the table above, which
`raw` source wins (or how the two get merged) — the same decision `explode_payloads`
already makes once, narrowly, for the `calendar` collision. This is the actual first
deliverable of Phase 1, and it's a design decision (which source is more complete,
more current, more field-stable per season) worth writing down per entity before
writing the `SELECT`.

## Revised phase plan

**Phase 0 — prerequisite, already spec'd, not yet executed.**
Clean `raw`/`stg` rebuild; fix the `_post_wk` season-parsing bug.
See `docs/duckdb-rebuild-spec.md`. Nothing below should be built on the current
(unreproducible, stale) `data/cfb.duckdb`.

**Phase 1 — minimal `core`, scoped to the three real consumers.**
- Write the raw → core entity map for `team`, `conference`, `venue`, `game` (the
  families in the collision table above).
- `core.dim_team`, `core.dim_conference`, `core.dim_venue`.
- `core.fact_game` — grain: one row per game. Cross-check against `GameRecord`'s
  existing fields (`cfb_system_maker/models.py`) rather than inventing a new shape.
- `core.fact_game_line` — grain: game-book-timestamp. Cross-check against the
  `spread_open`/`spread_move`/`total_open`/`total_move` features `enrich.py` already
  computes from `lines_{season}.json`.
- `core.fact_team_week` — grain: team-season_type-week. Cross-check against
  `running_stats.py`'s entering-game computed features (same no-lookahead
  requirement documented in this repo's `.claude/CLAUDE.md`).
- **Decide, explicitly, before writing SQL for the above three facts:** does this SQL
  layer replace `normalize.py`/`enrich.py`'s JSON output, or run alongside it as a
  second, eventually-reconciled representation? Don't let this get decided
  implicitly by whichever gets built first.

**Phase 2 — `mart` + `app`, only once the hosted-web-app decision is made.**
Build `mart.model_game_team_features` (if Phase 1 didn't already fold it into
`fact_team_week`) and `app.*` serving views on top of Phase 1's `core`, once
something is actually reading from DuckDB in production instead of `games.csv`.

**Phase 3+ — not committed, revisit on demand.**
Athlete/coach/recruiting/draft dimensional layer, play/drive facts, `ref`/`model`/`qa`
schemas — build the specific piece a real task needs, when it needs it, using the raw
data that's already sitting in `raw.athlete`/`raw.coach`/`raw.recruit`/etc. today.

---

A threat model was deliberately omitted from this doc: it is planning-only, no code or
schema changes ship from it, and it crosses no trust boundary.
