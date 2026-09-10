# Do the-odds-api events land on exactly one `stg.games` row?

**2026-09-10.** Reproduce with `python scripts/audit_oddsapi_game_join.py --list`.

## The question

[`oddsapi-team-name-join-2026-09-10.md`](oddsapi-team-name-join-2026-09-10.md) showed the
names resolve: 170 of 173 to exactly one `core.dim_team` row, none ambiguously. It left the
harder half open — resolving a name to a `team_id` is one of three keys, and pairing
`(home, away, kickoff)` onto a `gameId` "still has to handle kickoff-time drift and neutral
sites."

The failure that matters is not "no match", which is loud and fixable, but **"more than one
match"**, which is silent: a load would pick one and nobody would know.

## Method

Two measurements, deliberately not combined:

**Pairing.** Resolve both team names, then look for `stg.games` rows in the season holding
that *unordered* pair. Bucket one / more than one / none — with the kickoff **not** used to
disambiguate, so what gets measured is the pair's own identifying power.

**Drift.** For events that paired to exactly one game, the distribution of `commence_time −
startDate`. That distribution is the drift answer, rather than a tolerance assumed up front
and tuned until it looks good.

The three names the previous audit found unresolved (`Appalachian State`, `Southern
Mississippi`, `UMass`) are aliased in the script, so a known name defect does not
contaminate the pairing count.

**Data:** 98 distinct events across 5 snapshots in `data/ingest/oddsapi/` (2026-09-09 to
2026-09-10), against 3,680 `stg.games` rows for 2026 and 9,028 FBS pair-seasons since 2015.
Local `cfb.duckdb`, offline.

## Result

| Pairing, on the team pair alone | Events |
|---|---:|
| Exactly one game | **98** |
| More than one game | **0** |
| No game | 0 |
| Name unresolved | 0 |

**Drift:** 95 of 98 exactly zero. The three that differ are instructive:

| Δ | Game | What it is |
|---:|---|---|
| −8 min | Prairie View A&M @ Baylor | kickoff-time precision |
| +1 min | New Mexico State @ Hawai'i | kickoff-time precision |
| **+1440 min** | Houston @ Texas Tech | **the vendors disagree by a full day** — Odds API has it Friday 09-19, CFBD Thursday 09-18 |

## The design this implies: pair first, kickoff only to split

The 24-hour case is the load-bearing one. **A join keyed on kickoff within any tolerance
under a day would have silently dropped that game** — it is not drift to be absorbed, it is
two vendors holding different dates. So kickoff cannot be part of the key.

The team pair can be, nearly always. Over every season since 2015, an FBS-vs-FBS pair meets
more than once in the same season in **59 of 9,028 pair-seasons (0.65%)**. Those are real
rematches — a conference title game (which CFBD codes `seasonType='regular'` at week 15) or
a playoff meeting — with distinct `gameId`s *weeks* apart, so a nearest-kickoff tiebreak
separates them trivially.

**So: join on the unordered team pair within the season; when it matches more than one row,
take the nearest kickoff.** That survives both failure modes — the 24-hour disagreement
(pair is unique, kickoff never consulted) and the rematch (pair is ambiguous, kickoff is
decisive). A flatten should still fail loudly rather than guess if a name will not resolve.

## What this does not support

The matched set is one week of one September, and it does not contain the cases the
original warning named. Reported by the script for exactly this reason:

- **`startTimeTBD = true`: zero in the matched set.** 2026 has 421 such games. A TBD game
  carries a placeholder `startDate`, which is the concrete mechanism behind "kickoff
  drift", and it is **untested here** — not clean.
- **`neutralSite = true`: one.** 2026 has 37. Home/away orientation on neutral sites is
  where the two vendors are most likely to disagree, and a single case is not a measurement.
  The unordered pair is orientation-independent, which should make this moot — but that is
  an argument, not evidence.
- **`seasonType`: all 98 `regular`.** The rematch case is structurally absent from a
  September sample, so the 0.65% ceiling above is measured from the schedule rather than
  observed in the snapshots.
- **It does not validate the odds payload itself** — books, markets, or the nullable quota
  fields (`requests_remaining` and friends), which `docs/oddsapi-ingest.md` raises
  separately and which stay open.
- **It does not say which vendor is right** about Houston–Texas Tech, only that they differ.

## Bearing on `#oddsapi-warehouse-wiring`

Both halves of the stated blocker are now measured, and neither is the "settle the mapping
before designing a flatten" project the deferral assumed: names resolve with three aliases,
and games pair on the team pair with a documented tiebreak. What remains before a load is
the payload work — the flatten shape, pinned types, and the nullable quota fields — plus
re-running this audit once TBD kickoffs and postseason games are actually in the snapshots.
