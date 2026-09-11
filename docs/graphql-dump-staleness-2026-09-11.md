# How stale are the GraphQL dumps, and does it reach `core`?

**2026-09-11.** Reproduce with `python scripts/audit_graphql_dump_age.py`. Raised by the
ActionNetwork provider-id offset migration ([`lines-provider-key-split`](lines-provider-key-split-2026-09-10.md)
is the same thread) — the refresh that landed it rebuilt `stg` from scratch and `stg.game`
came back at an unchanged 112,672 rows, which is what exposed the gap. Tracked as
`#graphql-dumps-never-refreshed`.

## The question

`refresh_cfbd.py` re-scrapes REST, reflattens ActionNetwork/PFF/odds and rebuilds the
warehouse. Nothing on that path re-pulls `data/graphql/*.json`. So a full rebuild reloads
whatever those dumps held the last time someone pulled them by hand, and every `core`
builder reading a GraphQL-backed `stg` table merges fresh REST against a dump of unknown
age.

Two questions, and they have different answers:

1. **Are the dumps behind?** Measurable.
2. **Does being behind move a `core` value?** The one that actually matters.

## Method

50 dumps exist; **10 feed `core`**, and only those are audited. They split by whether a
comparator that `refresh_cfbd.py` actually refreshes exists:

* **Group A (4)** — `game`, `calendar`, `conference`, `gameLines` have REST twins scraped
  hours ago, so a coverage gap measured against them is evidence about the dump.
* **Group B (6)** — `coach`, `coachSeason`, `recruit`, `teamTalent`, `draftPicks`,
  `linesProvider` have REST sides that are themselves only pulled by hand. A gap against a
  stale comparator is uninterpretable in both directions, so these are **not measured on
  divergence**. They get file age, row count and an append-only/mutable classification.

`gameLines` is measured through `raw.gql_game_lines`, not `stg.game_lines`: the AN backfill
rebuilt the latter from the dump unioned with the ActionNetwork tape, so its row count mixes
three vintages and means nothing here.

**Data:** local `cfb.duckdb` rebuilt 2026-09-11 04:27, `data/graphql/*.json` as on disk that
morning. Dump ages span 0.6–90.1 days.

## Result: yes, behind — and no, it does not currently reach `core`

### Group A — a gap here is evidence

| entity | dump age | check | gap |
|---|---|---|---|
| `game` | 13.7d | in-span REST games the dump lacks | **4** |
| `game` | 13.7d | finished games the dump still calls `scheduled` | **415** |
| `calendar` | 13.7d | REST weeks the dump lacks | 0 |
| `conference` | 13.7d | REST conferences the dump lacks | 0 |
| `gameLines` | 13.7d | REST-lined games the dump lacks | **1,682** |

### Group B — unmeasured on divergence, not clean

| entity | dump age | rows | shape |
|---|---|---|---|
| `coachSeason` | 0.6d | 12,564 | append-only, a row per coach-season |
| `teamTalent` | 0.6d | 2,413 | append-only, a row per team-season |
| `coach` | 13.8d | 1,842 | append-only, new hires only |
| `recruit` | 13.8d | 93,363 | append-only per cycle; already reaches 2027 |
| `draftPicks` | 13.7d | 13,080 | append-only, frozen until the draft |
| `linesProvider` | **52.5d** | 17 | static enum |

### The wiring is why it does not matter yet

`stg.game` reaches `core` in exactly two places:

* `_build_fact_game`'s conference-FK repair (`duckdb_core.py:430`) reads **only**
  `homeConferenceId` / `awayConferenceId`, joined on `gameId`.
* `_build_fact_game_historical` (`duckdb_core.py:1118`) reads many columns including
  `status`, but only `WHERE season < min(dim_week)` — **pre-2012**, games that never change.

So the 415 stale statuses are unreachable: 409 of them are 2026, and the only consumer of
`status` is the pre-2012 table (0 rows at `season >= 2012`). The 4 missing games are
unreachable too — `core.fact_game` is REST-defined, so they are present regardless; they
merely miss the conference-FK repair and keep their name-derived ids. That is **4 unrepaired
rows out of 34,645**, and spot-checking them shows the name lookup landed on the same ids
the dump would have supplied.

`gameLines`' 1,682-game gap cannot corrupt either: the merge is `coalesce(rest, gql)`, so a
stale dump can only fail to *add* a line, never overwrite a fresher one.

### What the 4 missing games actually were

Not games CFBD deleted. **It re-issued one under a new id.** Game 401866625 (Campbell vs
Western Carolina, 2026-09-05 15:30, `scheduled`) vanished from REST between the 09-10 and
09-11 pulls; 401917058 appeared — same teams, same venue 3629, same week — at 2026-09-06
11:00, `completed` 28–19. A postponement that CFBD recorded as a new row rather than an
update. The Aug 28 dump has only the old id; fresh REST has only the new one.

That is what broke `test_fact_game_did_not_grow_to_hold_graphql_rows`, whose premise (REST ⊇
in-span GraphQL) held only incidentally. Corrected in `f1e7d0c` to join `stg.games`, with
`test_graphql_only_games_stay_a_handful` bounding the GraphQL-only set at 25. The other
three missing games are DII/DIII independents.

## What this does not support

- **It does not show the dumps are safe to leave alone.** It shows today's `core` builders
  read too little of `stg.game` to be hurt. Any new builder reading a GraphQL column that
  mutates — `status`, points, a conference id for a team mid-realignment — inherits a
  14-day-stale value silently, and nothing in the suite would say so.
- **Group B is unmeasured, not clean.** Six of the ten have no fresh comparator. A blank in
  that table means "not checked", and reading it as "no gap" is the specific mistake the
  two-group layout exists to prevent. `linesProvider` at 52.5 days is the one most likely to
  matter, since a new book appearing there is how `core.dim_lines_provider` gains a row.
- **Age is a weak proxy and this audit shows it.** The four Group A dumps are all the same
  13.7 days old; two have a zero gap and two are materially behind. Cadence has to come from
  how often an entity *changes*, not from how old its file is — which is why
  `--stale-days` only flags, and the gap columns decide.
- **It measures coverage, not correctness.** A game the dump holds at the right id could
  still carry a value that changed since Aug 28. Only absence is checked, plus the one
  `status` cross-check.
- **It says nothing about the 40 dumps outside `core`.** They feed `stg` and whatever reads
  `stg` directly; that surface is unexamined here.

## What changed

Nothing in the data, and **no code on the refresh path**. This is a measurement plus
`scripts/audit_graphql_dump_age.py` to repeat it. The cadence-and-wiring half of
`#graphql-dumps-never-refreshed` stays open: the audit narrows it from "50 dumps of unknown
age" to "`gameLines` and `game` are the two that move, `linesProvider` is the one Group B
risk worth pricing, and the other seven are append-only or verified flush."
