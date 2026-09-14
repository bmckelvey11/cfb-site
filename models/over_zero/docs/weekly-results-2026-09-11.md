# Weekly published results

Published September 11, 2026: the season record now derives from a settled-game ledger. Week 1 is 10–4 across 14 games; Week 2 is 1–0; season is 11–4 (73.3%). Each week opens an accessible drawer with games, published OVER lines, final scores, final totals, signed margins and results. Mobile uses game cards.

Margin is final combined score minus the recorded OVER line. Zero is a push and excluded from hit rate. Scores display away–home. Current prices and edited Bet to scenarios do not alter historical grading.

## Sources and rebuild

`scripts/build_weekly_results.py` reads the final published Week 1 board from site revision `0802db9` and first Week 2 board from `a0e0b4e`. It matches those games against fresh CFBD 2026 regular-season finals and writes `site/lib/weekly-results.json`. Raw API response is retained under `CFB_DATA_ROOT/processed/over_zero/results/`.

Run from repository root with `CFB_DATA_ROOT` configured:

```powershell
python models/over_zero/scripts/build_weekly_results.py
```

The publication list is explicit: add subsequent recorded publications when extending coverage. Extended 2026-09-14 with the Sep 12 board (`34a34df`, board-era `lib/board.json` picks); see `site-refresh-2026-09-14.md`. Pending games in those publications are excluded until completed. This is a published-pick record, not all raw model signals or all current sportsbook qualifiers. Week 1 has 14 published picks, not the 15 raw signals. Miami's recorded first Week 2 line is 61.5; final 84 gives +22.5.

## Verification

- Production build passed.
- Results tests verify unique games, weekly counts, all score sums and margins, grading signs, season reconciliation, pushes and empty records. Existing Bet to and bookmaker union tests passed.
- Public deployment succeeded: version 32, source `86965d9aed9e3f05d1e983f0332874f980db67f6`.
- Live desktop drawer shows all 14 Week 1 results and Miami Week 2 result. Escape closes and restores focus to the week trigger.
- At 320px, game cards fit, long Week 1 drawer reaches final game, and fixed Close remains accessible. Close button works. Browser error log empty. Viewport restored.
