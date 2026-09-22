# Over Zero refresh with 50-point spread cap — 2026-09-16

Request: rerun the current model with an absolute spread cap of 50 and publish the refreshed site.

Reproduction from repository root, with `CFB_DATA_ROOT=C:\Users\mckel\dev\cfb\data`:

```powershell
.venv\Scripts\python.exe scripts/pull_odds.py
.venv\Scripts\python.exe models/over_zero/scripts/best_line_slate.py --max-spread 50 --json models/over_zero/site/lib/board.json
.venv\Scripts\python.exe models/over_zero/scripts/verify_site_refresh.py
.venv\Scripts\python.exe models/over_zero/scripts/build_weekly_results.py
```

Odds snapshot: 2026-09-16 19:15:00 UTC, 75 events across nine books. Model run: 19:15:12 UTC. Fit: 12,988 games from 2013–2025; upcoming window: eight days. Scored 74 market games. The cap applies to the spread used by each view, including individual sportsbook views. Exactly 50 remains eligible; values above 50 do not.

Three market-wide signals: Buffalo at Penn State, Northern Iowa at Iowa, East Texas A&M at Tulsa. Best lines includes three additional playable book-only games: UTEP at Michigan (BetMGM), Duquesne at Washington State (BetRivers), Eastern Washington at Washington (DraftKings). Six displayed games total. Ohio State–Kent State and Oregon–Portland State exceed the cap despite clearing the market bias threshold.

Verification: all 24 pick observations across ten views satisfy absolute spread <=50; board matches model CSV; future kickoffs and all Bet-to cutoffs pass existing verification. Game-view and results tests pass. Production build passes. Pick history added 24 observations, reaching 1,310. Historical published record remains 17–8 across 25 settled games; no retrospective cap was applied.

This run does not change the model's uncapped command-line default or establish predictive performance for the capped strategy. Future capped runs must continue passing `--max-spread 50`.

Site source: `f91fc58ffb1ebf3523955fbffa1d6fad0d60ccea`; saved Sites version 35.

Completed 2026-09-16: deployment succeeded at 19:18:01 UTC. Reloaded the existing live browser tab and verified six signals, 74 priced games, the September 16 19:15 UTC odds timestamp, and all six expected matchups. Live URL: https://redpanda-overs.caerus11.chatgpt.site

## Follow-up fix completed — September 16, 2026 (Eastern)

The existing public version already contained six capped games, but its calculator accepted spreads through +/-100, the page did not disclose the cap, and the scheduled wrapper omitted --max-spread 50. A later local snapshot consequently contained uncapped picks.

Fixed the scheduled wrapper to pass --max-spread 50 while preserving its other pending edits. Added a display guard across every sportsbook view and Best lines, restricted the calculator to +/-50 inclusive, and displayed the rule. Snapshot timestamps now use America/New_York with daylight-saving handling and the source odds timestamp rather than the model execution timestamp.

Re-ran best_line_slate.py --max-spread 50 --json models/over_zero/site/lib/board.json against the September 16 8:00 PM ET odds snapshot. Result: 74 market games, three market signals, 23 observations across ten views, six combined displayed games. Published record remains 17-8 from 25 settled picks; this change does not establish historical performance for the capped strategy.

Validation: existing model/board verification passed; four Node test files passed (cutoffs, book union, results, Eastern time including winter and date rollover); production build passed. Version 36 deployed successfully from 8504956204a798e20393098b304048353dd35e5a. Live browser shows Sep 16, 2026 at 8:00 PM ET and the spread cap. Entering -50.5 clears Bet to with a range message; -50 returns 64; Reset restores -40.5 and 54.5. No retrospective changes to historical picks.
