# Do the four vendor team-name maps need consolidating?

**2026-09-10.** Reproduce with `python scripts/audit_team_name_maps.py --list`.

## The question

`#core-dim-team` in `TODO.md` proposes building `core.dim_team` once and collapsing four
consumers onto it, on the premise that `stg.massey_teams` and `stg.pff_franchise` "each
hand-maintain the same mapping", that `recruiting_team`/`recruiting_teams` is "deferred
purely for want of it", and that `stg.coaches__seasons`' `seasons_school` → `teamId` is
"what routes rows into `core.coach_season_unmatched`".

Before writing that, two things needed checking: whether the mapping is actually failing
anywhere, and whether `core.dim_team` exists at all.

## Method

`core.dim_team` is already built — `cfb_system_maker/duckdb_core.py:135`, one row per CFBD
`team_id` with `school`, `abbreviation`, `classification` and `is_fbs`, keyed and rebuilt
by `build_core`. So the question is not whether the dimension exists but whether the four
consumers reach it.

For each consumer, take every distinct vendor team name and its resolved `team_id`, then
re-check each unresolved name against `core.dim_team` a second way — exact `school`, then
CFBD's own `alternateNames` (`stg.teams__alternateNames`, 1,395 distinct aliases). That
split matters: a vendor covering FCS and D2 will always carry schools CFBD has no team
for, and counting those as misses makes a complete map look broken.

**Data:** local `cfb.duckdb` as of 2026-09-10 — 701 CFBD teams (136 FBS), Massey editions
through the 2026 season, PFF 2025–2026 `team_directory`, CFBD recruiting 2013–2026, CFBD
coaches. No API calls.

## Result: zero real gaps

| Source | Names | Mapped | Unmapped | Not in CFBD | Real gaps |
|---|---:|---:|---:|---:|---:|
| `stg.massey_teams` | 137 | 137 | 0 | 0 | **0** |
| `stg.pff_franchise` (`kind='team'`) | 267 | 266 | 1 | 1 | **0** |
| `stg.recruiting_teams` | 268 | 262 | 6 | 6 | **0** |
| `stg.coaches__seasons` | 137 | 137 | 0 | 0 | **0** |

Every unmapped name is a school CFBD carries no team for: PFF's `Chicago State Cougars`
(added for 2026), and recruiting's `Albany`, `Grand Valley State`, `Saint Francis (PA)`,
`Savannah State`, `Southeastern Louisiana`, `UTRGV`. Not one is a name CFBD does carry
that a vendor's rules missed.

Two corrections the data made to the framing:

- **`coaches__seasons` joins at 137/137 on the school string alone**, and
  `core.coach_season_unmatched` does not exist — the `core` schema holds `dim_week`,
  `dim_conference`, `dim_team`, `dim_venue`, `dim_lines_provider`, `fact_game`,
  `fact_game_line`, `fact_game_team` and nothing else. That table is a future artifact of
  `#core-merge-bucket-c`, not something the current mapping feeds. The 118 school-seasons
  with 2–3 coaches are a *grain* problem, not a name-resolution one.
- **PFF's 96 all-star franchises are not schools**, so they have no CFBD team to be
  missing. Counting them reports four false gaps — `FAIRST`, `OBERLIN`, `THMORE`, `WCU`,
  each of which does resolve uniquely through `alternateNames`. The audit excludes
  `kind = 'allstar'` for this reason.

## What this does not support

- **It does not say the four maps are identical or interchangeable.** They resolve
  different vocabularies (a Massey edition name, a PFF slug, a CFBD recruiting string) and
  were measured only on whether each reaches a `team_id`, not on whether one rule set
  would serve all four.
- **It does not measure a fifth would-be consumer.** `OA_ALIASES`/`oa_resolve`
  (`research/spread/scripts/weekly_slate.py:351`) maps the-odds-api names and was not
  audited here. *(Answered separately the same day —
  [`oddsapi-team-name-join-2026-09-10.md`](oddsapi-team-name-join-2026-09-10.md): 170 of
  173 names resolve uniquely against `core.dim_team`, zero ambiguously, three need an
  alias.)*
- **It does not license matching on `alternateNames` in production.** The second pass uses
  aliases only to classify a residual. S4 found CFBD aliases carry three-letter
  abbreviations (`liu`, `cal`, `sou`) that collide across schools; a map that indexes them
  blindly will match confidently and wrongly.
- **It says nothing about consolidation as a code question.** Four rule sets that each
  reach 100% still cost four maintenances, and a new vendor still starts from scratch.
  That case stands or falls on maintenance cost, which this does not measure.

## Bearing on `#core-dim-team`

The item's data premise does not hold: nothing is unmapped that CFBD could map, and the
dimension it proposes building already exists. What remains is a refactor — one alias
surface instead of four rule sets — justified by future maintenance rather than by broken
joins today. That is a smaller and lower-priority piece of work than the item describes,
and the item should be restated before anyone picks it up.
