# Phase 5: Dashboard & Current Matches — Discussion Log

**Date:** 2026-07-20
**Mode:** default (interactive)

*Human reference only. Downstream agents read `05-CONTEXT.md`, not this file.*

## Scouting findings that shaped the discussion

Two facts were established from the code before any questions were asked, and they drove most of the session:

1. `data/processed/games.csv` contains **zero unplayed games** (verified: 12,964 rows, 0 with an empty `home_points`) and has **no kickoff date column**. Current Matches therefore needs a genuinely new data path, and kickoff timing cannot come from `GameRecord` without a CSV schema migration.
2. The session date is 2026-07-20 — the offseason. The next real games are roughly five weeks out, so Current Matches would render empty on every test run during development.

## Areas selected

All four offered: Upcoming-games data path, Dashboard layout & routing, Bundled example systems, Teaser records.

## Area 1 — Upcoming-games data path

| Question | Options presented | Chosen |
|---|---|---|
| Where should unplayed games live? | Separate upcoming file / One games.csv with a played flag / Fetch live per request | **Separate upcoming file** |
| What shows in the offseason? | Empty state + last week's matches / Plain empty state / Dev-only fake "today" | **Empty state + last week's matches** |
| How far should feature enrichment go? | Enrich upcoming too / Line+matchup filters only / Enrich but skip missing | **Enrich upcoming too** |
| How much to say about line movement? | Fetch timestamp / Timestamp + refresh button / Nothing | **Fetch timestamp** |
| What counts as "upcoming"? | Current week only / Next 7 days / All remaining unplayed | **Current week only** |
| Include games with no line yet? | Exclude / Include marked "no line yet" | **Exclude** |
| How does the data refresh? | New CLI command / CLI + web button / Fold into `fetch --upcoming` | **New CLI command** |
| What does each row's play text say? | Mirror bet type / Team name only | **Mirror bet type** |

Notes: the separate-file choice removes the need for a `GameRecord` CSV migration entirely, which the project's CLAUDE.md flags as requiring deliberate handling. The refresh choice keeps the Flask app a pure local-file reader.

## Area 2 — Dashboard layout & routing

| Question | Options presented | Chosen |
|---|---|---|
| What happens to existing filtered `/` bookmarks? | Redirect to `/system` when filters present / Hard move, no redirect / Keep editor at `/` | **Redirect when filters present** |
| Which timeframe tabs? | All Time + per-season / All Time only / All Time + last N seasons | **All Time + per-season** |
| How are dashboard figures computed? | On request, cached in memory / Fresh every load / Precomputed into saved JSON | **On request, cached in memory** |
| Where does Current Matches live? | Panel on the dashboard / Own page at `/matches` / Tab on the editor | **Panel on the dashboard** |

Notes: "30 Days" / "7 Days" tabs were ruled out because `games.csv` has no dates — the parity plan independently recommends deferring them.

## Area 3 — Bundled example systems

| Question | Options presented | Chosen |
|---|---|---|
| Where do examples live? | Checked-in JSON, read-only / Copied into data dir on first run / Generated in code | **Checked-in JSON, read-only** |
| Same table or separate? | Separate "Example Systems" tab / Same table with a badge / Hidden once you save your own | **Separate tab** |
| What should the examples be? | One per capability / Known profitable angles / User picks later | **One per capability** |
| Include a written theory? | Yes, short theory each / Leave blank | **Yes** |

## Area 4 — Teaser records (shelved mid-area)

| Question | Options presented | Chosen |
|---|---|---|
| Which offsets? | Favorable-only ladder (6/6.5/7/10) / Both directions / Favorable 6 and 7 only | **Favorable-only ladder** |
| Where does the panel appear? | Popover from editor's Record chip / Editor and dashboard both / Always-visible section | **Popover from editor's Record chip** |
| Show money/ROI given teaser pricing isn't -110? | Record + win % only / Record + money at -110 / Record + money at configurable price | *not answered* |
| Include total systems? | Yes, same ladder in the right direction / Spread only | *not answered* |

**The user shelved the entire teasers section** after the second question. Because teasers are requirement DASH-04 — a roadmap commitment, not just a discussion topic — this was handled as a formal descope rather than a note:

- `ROADMAP.md` Phase 5: success criterion 4 removed, requirements line changed to DASH-01/02/03, descope noted in the phase bullet and detail section.
- `REQUIREMENTS.md`: DASH-04 marked deferred and unscheduled; the mapping table and coverage counts updated (18 mapped, 1 deferred).
- `05-CONTEXT.md`: partial decisions and both unanswered questions preserved under Deferred Ideas so nothing has to be re-derived when it's picked up.

## Deferred ideas captured

- Teaser / alternate-line records (DASH-04) — descoped, unscheduled.
- Real-date timeframe windows ("30 Days" / "7 Days") — needs kickoff timestamps in historical data.
- In-page refresh button for upcoming data — rejected for this phase; puts a network call behind a page load.
- Grade sub-score breakdown panel — still deferred from Phase 2.
- Think Tank / sharing, moneyline wager type, public betting percentages — project-level out of scope.

## Claude's discretion

Sparkline rendering, dashboard column order and widths, tab styling, cache invalidation mechanics, the upcoming CLI command's exact name and flags, the upcoming file's schema, and empty-state wording.
