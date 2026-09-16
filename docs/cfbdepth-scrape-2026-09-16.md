# cfbdepth.com — what can be scraped (2026-09-16)

## Question

The user pointed at `https://cfbdepth.com/alabama` and asked what could be scraped
from it. This records the site's architecture, the data actually reachable, the
access caveats, and the open scope decision.

## Method

1. Fetched `https://cfbdepth.com/alabama`. It is an SEO shell — 27 KB of marketing
   copy and no depth-chart content. All data is client-side.
2. Downloaded the SPA bundle `/assets/js/index-30578621-1788436302845.js`
   (1.9 MB, unminified enough to read) and searched it for data endpoints.
3. Found the data layer: a hardcoded registry of Google Sheets IDs plus a
   `${API_BASE_URL}/sheets/${id}/export?gid=${gid}` proxy on
   `cfbdepth-backend-production.up.railway.app`.
4. Verified the underlying sheets are world-readable via Google's own public CSV
   export endpoint, bypassing the site's backend entirely.
5. Pulled all seven Alabama tabs and inspected their layout.

Date of data: 2026 season, in-season mode, sheets last modified 2026-09-16.

## Architecture

```
cfbdepth.com/<slug>   →  static SEO shell (no data)
      ↓ React SPA
index-*.js            →  TEAM_REGISTRY: slug → {spreadsheetId, 7 tab gids}
      ↓
railway backend       →  /api/sheets/<id>/export?gid=<gid>   (their proxy)
      ↓
Google Sheets         →  the actual source of truth
```

The backend proxy is optional. The same rows come back from:

```
https://docs.google.com/spreadsheets/d/<spreadsheetId>/export?format=csv&gid=<gid>
```

with no API key, no cookie, no referer. Confirmed 200 on `alabama`, `uga`,
`akron`, `ohio`, `army`, `smu`, `wku` — P5 and G5 alike, so public access is not
an Alabama-only accident.

## The registry

139 teams (all 138 FBS plus one duplicate slug). Each entry:

```json
"alabama": {
  "spreadsheetId": "12jj5lTJkL19Sw-2R-Pf6eC7hVqZsRZOcwE74oDVXX9U",
  "color": "#9e1632",
  "dashboard": "86862659",
  "offense": "1108164649",
  "defense": "394888346",
  "specialTeam": "746314171",
  "injuryReport": "1011984599",
  "rosterBreakdown": "1690893971",
  "playerRating": "1098827574"
}
```

The seven tab gids are **identical across all 139 teams** — only `spreadsheetId`
varies. Full registry extracted to `docs/cfbdepth-teams-registry.json`.

Total addressable surface: 139 × 7 = 973 CSVs.

## What the seven tabs contain (Alabama, 2026 wk 3)

| Tab | Size | Contents |
| --- | --- | --- |
| `dashboard` | 28×27 | Record, head coach, AIR rankings (overall/off/def), dWIN, SOS+/SOSp/SOSr with ranks out of 138, injury-impact count and rank, team depth grade |
| `offense` | 124×85 | Scheme (Spread, 63% run, 31.1 sec pace + rank), play caller + rating, AIR passing/rushing, then per-position depth blocks; cols 31–45 hold a PFF-style metric glossary |
| `defense` | 146×38 | Scheme (3-4), blitz% + rank, play caller, AIR pass-rush / run-D / coverage, position depth blocks |
| `specialTeam` | 127×39 | PK/P/LS/returners with the same player-row schema, ST AIR rank |
| `injuryReport` | 69×16 | Per-player: status code, pos, rating, impact score, update date, free-text note, injury type, confirmed flag, return timeframe, original date, projected return |
| `rosterBreakdown` | 143×27 | Roster size, transfers vs home-grown, star counts, walk-ons, blue-chip% + national rank, average weight + rank |
| `playerRating` | 365×20 | Per-position rating tables: Current / Start / Diff across split contexts (overall, passing, deep passing, pressure, clean, etc.) |

### Depth-chart row schema

Inside `offense` / `defense` / `specialTeam`, each position is a block:

```
row N    : "QB Quarterbacks"   Depth: A   Rotation: 4
row N+1  : Player | # | Status | Year | HT | WT | Recruit Star | Rating |
           StatusUp | Portal | Signed | LS | OOE | NFL | CS | BG1 ...
row N+2..: one row per player, plus role label ("Full-Time", "Backup",
           "3rd String", "Depth/Develop") and prior-school color for transfers
```

The repeating literal header row (`Player,#,Status,Year,...`) is a reliable
anchor for a parser — no positional guessing needed.

Status codes are defined in-sheet: blank=Healthy, P, Q, D, O, OFS, S, OPT, GTD, RET.

## Access caveats

- **Their Google API key is exposed in the public bundle**
  (`AIzaSyC3JUD…`, alongside `SHEETS_BASE`). It was **not used** for any request
  here and should not be — the public CSV export needs no credential. Worth
  telling cfbdepth that the key is sitting in their shipped JavaScript.
- **This is a paid product.** The bundle carries `PAID_UIDS`, plan names
  `Depth+` / `All-Access`, an Outseta auth integration, and a `/api` page
  selling API access at $49–$149/month. The sheets are unprotected, but the
  gating intent is explicit. A one-off look and a recurring bulk pull are
  different acts; the latter needs a deliberate decision.

## What this does *not* support

- No claim that bulk or recurring collection is permitted. Public readability of
  the sheets is a fact about their configuration, not a licence.
- No historical data. The sheets are current-state only — they are overwritten in
  place, so there is no season archive and no as-of snapshot unless we store one
  ourselves.
- Ratings (`Rating`, AIR, dWIN, SOS+) are cfbdepth's proprietary numbers with no
  published methodology. Their construction is unknown and they cannot be assumed
  free of lookahead.
- Only the `dashboard` tab was checked on the six non-Alabama teams. The other
  six tabs are assumed to share layout because the gids are identical, but that
  is unverified outside Alabama.

## Reproduction

No script written yet — scope is undecided. The registry file plus this URL
pattern reproduces any single pull:

```
https://docs.google.com/spreadsheets/d/<spreadsheetId>/export?format=csv&gid=<gid>
```

Alabama's seven tabs were pulled to the session scratchpad as
`alabama_<tab>.csv`. If a recurring pull is chosen, it gets a reusable script
under `scripts/` per the standing rule.

## Open decision

1. **Alabama only, one-shot** — already done.
2. **All 139 teams, one snapshot** — ~973 requests, a few minutes.
3. **Recurring pull into the warehouse** — needs an explicit yes, given the
   paid-product note above.
