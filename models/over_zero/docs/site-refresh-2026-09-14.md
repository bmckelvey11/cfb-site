# Over Zero refresh — September 14, 2026

Question: refresh the board for the Sep 17–19 slate and settle the Sep 12 (Week 2) picks.

## Board

`python models/over_zero/scripts/best_line_slate.py --json models/over_zero/site/lib/board.json`
from the repository root with `CFB_DATA_ROOT` set. Fit uses 12,988 games from 2013–2025.
Prices come from the the-odds-api snapshot taken 2026-09-14 21:29 UTC (74 events); the run
stamp is 21:42 UTC. 57 games have a fair (four regulated books) price; 3 clear bias > 1.75
and all 3 have a price at −120 or better. The 09:00 ET scheduled run on the 12:00 UTC snapshot
had the same three games; the re-run only moved the numbers.

| Kickoff (ET) | Game | Signal total | Bias | P(over) | Best price | Bet to |
| --- | --- | --- | --- | --- | --- | --- |
| Sep 19 12:00 PM | Kent State at Ohio State | 59.5 | 2.871 | 66.06% | 58.5 BetRivers −112 | 66.5 |
| Sep 19 12:00 PM | Buffalo at Penn State | 48.5 | 2.512 | 63.84% | 47.5 BetRivers −114 | 53.5 |
| Sep 19 3:30 PM | UTEP at Michigan | 48.5 | 1.894 | 59.90% | 48.5 FanDuel −104 | 49.5 |

The script also appended 32 rows to `processed/over_zero/qualified_picks_history.csv`
(940 observations). Picks sit at dog-implied 3.5–6.5, where the fit has 81 games under 5;
treat P(over) there as extrapolated.

## Week 2 settlement

`python models/over_zero/scripts/build_weekly_results.py` now reads three publications:
Week 1 from site revision `0802db9`, the first Week 2 board from `a0e0b4e` (both inline
`app/page.tsx` picks), and the Sep 12 board from `34a34df` (`lib/board.json`, the revision
pushed to the deploy remote at 09:46 ET on Sep 12, before the first kickoff). Board-era
picks are graded at the "Best lines" signal total, the headline column on the board, with
book recorded as `Market`. A game keeps its first published line: Rice at Notre Dame stays
at 54.5 from `a0e0b4e`, not the 55.5 shown on Sep 12. Finals come from the CFBD games
endpoint; the raw response is kept under `processed/over_zero/results/`.

Week 2: 7–4 across 11 settled picks.

| Game | Line | Final | Margin | Result |
| --- | --- | --- | --- | --- |
| Florida A&M at Miami | 61.5 | 7–77 | +22.5 | Win |
| Norfolk State at Virginia | 54.5 | 3–59 | +7.5 | Win |
| Howard at Indiana | 66.5 | 0–55 | −11.5 | Loss |
| Wagner at James Madison | 56.5 | 3–87 | +33.5 | Win |
| UT Martin at West Virginia | 55.5 | 7–52 | +3.5 | Win |
| Rice at Notre Dame | 54.5 | 0–52 | −2.5 | Loss |
| Mercyhurst at New Mexico | 53.5 | 7–70 | +23.5 | Win |
| Southern at Houston | 61.0 | 6–77 | +22.0 | Win |
| Towson at South Carolina | 55.5 | 9–45 | −1.5 | Loss |
| Western Illinois at Wisconsin | 50.5 | 9–36 | −5.5 | Loss |
| Grambling at TCU | 55.5 | 7–63 | +14.5 | Win |

Season: 17–8, 25 settled, 68.0%.

Grading at the best available total instead would not change any result (Towson at South
Carolina loses at 55.0 too). The intermediate commit `3adbb51` (Sep 11 board) was never
pushed on its own, so it does not define any line.

## Verification

- `scripts/verify_site_refresh.py`: board matches the model CSV, all views hold future
  kickoffs only, 201 Bet-to cutoffs and 32 per-book Bet-to values sit exactly at the threshold.
- `node --experimental-strip-types models/over_zero/site/lib/game-views.test.mjs` and
  `lib/results.test.mjs` pass (25 settled games reconcile).
- `npm run build` in `models/over_zero/site` completed; `dist/` carries the 21:29 UTC snapshot.
- Site commit made locally; deploy needs the user's push (`git -C models/over_zero/site push sites master:main`).

These checks do not validate a new edge, and the shopped price may no longer be available.
