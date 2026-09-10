# Can the-odds-api names join the warehouse?

**2026-09-10.** Reproduce with `python scripts/audit_oddsapi_team_names.py --list`.

## The question

`docs/oddsapi-ingest.md` defers `#oddsapi-warehouse-wiring` on one blocker, under *Before
this loads: the join key*: Odds API events carry team names **with the mascot** (`"Miami
Hurricanes"`, `"Florida A&M Rattlers"`) while `stg.games` carries school only, so "nothing
joins to `game_id` until that gap is closed."

That warning predates `oa_resolve`. But `oa_resolve` is not a straight refutation of it,
for two reasons worth separating:

1. It resolves against **Prediction Tracker's slate**, not `core.dim_team`. Different
   vocabulary, different target.
2. Its own docstring says the mascot strip is **not unambiguous** — `"Alabama Crimson
   Tide"` and `"Florida International Panthers"` are both three tokens, and dropping two
   gives the right school for one and the wrong one for the other. What prevents a wrong
   price on the slate is that the merge keys on *both* teams, so a misresolved name must be
   paired with a partner that misresolves onto the same row. **A warehouse flatten
   resolving one team at a time does not inherit that protection.**

So the question is not "does a strip work" but "does it resolve *uniquely* against
`core.dim_team`", which is what a one-sided join needs.

## Method

Take every distinct `home_team`/`away_team` in the snapshots already on disk. For each,
try the same heads `oa_resolve` would (drop up to two trailing mascot tokens,
longest-match-first) against `core.dim_team.school`, and bucket into three outcomes rather
than two: exactly one team, more than one, none.

Normalization folds accents and deletes apostrophes — both were needed for CFBD's own
spellings (`San José State`, `Hawai'i`) and both were bugs in the first pass of this script
that presented as vendor gaps. CFBD `alternateNames` is deliberately **not** indexed: S4
found it carries three-letter abbreviations that collide across schools, so it manufactures
exactly the ambiguity this audit is looking for.

**Data:** 5 snapshots in `data/ingest/oddsapi/`, 2026-09-09 to 2026-09-10, 173 distinct
team names, against `core.dim_team` (701 teams, 136 FBS) in local `cfb.duckdb`. Offline —
no API calls.

## Result

| Outcome | Names |
|---|---:|
| Resolved to exactly one team | 170 |
| **Resolved to more than one** | **0** |
| Unresolved | 3 |

**Zero ambiguity.** The failure mode the slate's both-teams merge was protecting against
does not occur on this sample, so a one-sided warehouse join is not exposed to it here.

The three unresolved are all FBS teams where the vendors simply spell the school
differently, and each needs one alias line:

| the-odds-api | `core.dim_team` |
|---|---|
| `Appalachian State Mountaineers` | `App State` |
| `Southern Mississippi Golden Eagles` | `Southern Miss` |
| `UMass Minutemen` | `Massachusetts` |

**The FCS worry does not materialize.** Of the 170 resolved, 131 are FBS and **39 are
FCS** — the-odds-api spells FCS opponents compatibly with CFBD, and all 39 land. The
warning's own examples are misleading for a different reason: the-odds-api only lists games
with posted markets, so a D2 opponent like `Ohio Dominican` never appears in a snapshot at
all, however it might be spelled in `stg.games`.

## What this does not support

- **One week is not a season.** Five snapshots spanning two days in September. Non-conference
  scheduling front-loads FCS opponents, so this sample is probably *favourable* on the FCS
  question and thin on late-season and bowl names. The three aliases are a floor, not a
  complete list.
- **It does not test the `game_id` join itself.** Resolving a name to a `team_id` is one of
  three keys; pairing `(home_team_id, away_team_id, commence_time)` onto a `game_id` still
  has to handle kickoff-time drift and neutral sites. Unmeasured here.
- **It does not license removing the both-teams check from a design.** Zero ambiguity on
  173 names is evidence, not a proof about names not yet seen. A flatten that resolves
  one-sided should still fail loudly on a name it cannot resolve rather than guessing.
- **It says nothing about the quota fields or point-in-time handling**, which the ingest doc
  raises separately and which remain open.

## Bearing on `#oddsapi-warehouse-wiring`

The stated blocker is smaller than recorded: the join needs a mascot strip, three alias
lines, and accent/apostrophe folding — not a settled vendor mapping project. That is
comparable to what `stg.pff_franchise` already does. `docs/oddsapi-ingest.md` *Before this
loads* has been updated to say so. See also
[`team-name-mapping-2026-09-10.md`](team-name-mapping-2026-09-10.md), which measured the
four existing vendor maps and left this one explicitly open.
