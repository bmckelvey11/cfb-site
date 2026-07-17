# Phase 3: Data Depth & Breadth - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-17
**Phase:** 3-Data Depth & Breadth
**Areas discussed:** Backfill floor, Partial coverage policy, New endpoint categories, Stats & lookahead, Player scope

---

## Backfill floor

| Option | Description | Selected |
|--------|-------------|----------|
| As far as lines allow | Backfill to earliest season CFBD returns usable consensus lines | ✓ |
| Fixed target (e.g. 2005) | Pick a concrete earlier floor, accept whatever coverage | |
| Modest extension | Push back a few known-good seasons (2010–2012) | |

**User's choice:** As far as lines allow
**Notes:** Betting lines are the binding constraint; research must find the real line-coverage floor before setting scope.

---

## Partial coverage policy

| Option | Description | Selected |
|--------|-------------|----------|
| Include games-only rows | Add games without lines; spread/total filters won't match them | |
| Require a usable line | Only include games with a real line (current build behavior) | ✓ |
| Discuss / not sure | — | |

**User's choice:** Require a usable line
**Notes:** Keeps backtests clean; practical floor = line-coverage floor. Satisfies success criterion 1.

---

## New endpoint categories (multi-select)

| Option | Description | Selected |
|--------|-------------|----------|
| Advanced team stats | SP+, FPI, success rate, explosiveness, havoc, PPA splits | ✓ |
| Recruiting / talent | Talent composite, recruiting rankings | ✓ |
| Returning production | Roster continuity / usage | |
| Player-level / injuries | Player passing/rushing aggregates, portal | ✓ |

**User's choice:** Advanced team stats, Recruiting/talent, Player-level
**Notes:** Returning production not prioritized. Player-level flagged as previously deferred (heavy fan-out).

---

## Stats & lookahead

| Option | Description | Selected |
|--------|-------------|----------|
| Entering-game (to-date) only | Running/season-to-date versions, honest pre-game state | ✓ |
| Preseason ratings only | Only genuinely pre-game sources; skip in-season aggregates | |
| Both, tag full-season as lookahead | To-date + quarantined full-season aggregates | |

**User's choice:** Entering-game (to-date) only
**Notes:** Advanced stats wired like existing running_ppa; no raw season aggregates as pre-game filters.

---

## Player scope

| Option | Description | Selected |
|--------|-------------|----------|
| Team-aggregated only | Roll player stats up to team-season; no per-game fan-out | ✓ |
| Use already-scraped data | Only wire from existing data/raw; no new pulls | |
| Full per-player pull | Heavy fan-out now | |

**User's choice:** Team-aggregated only
**Notes:** Per-player fan-out stays deferred. Prefer existing adjusted_player_* raw data as source.

---

## Claude's Discretion

- Exact CFBD endpoint/method names and running-stat accumulation math.
- Whether backfill reuses `fetch` or `scrapers.py`.
- Returning-production inclusion if cheap alongside recruiting/talent.

## Deferred Ideas

- Full per-player / per-game player-stat fan-out (heavy scrape).
- Full-season raw aggregates for exploration (only if tagged result_lookahead).
- Returning-production features.
- Public betting-percentage filters (out of scope project-wide).
