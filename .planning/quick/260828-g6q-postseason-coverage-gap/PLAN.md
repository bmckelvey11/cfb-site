---
task: Document the regular-season-only gap in raw games/lines and audit what inherits it
status: complete
created: 2026-08-28
---

# Quick: postseason coverage gap

## Goal

`data/raw/games_{season}.json` holds `seasonType=regular` rows only for every season
1992-2024, so every bowl / conference championship / CFP game is missing. Record this in
`docs/data-coverage.md` (the file that documents *why* data is absent), answer whether the
fix is a `seasonType=postseason` pass in `scrapers.py` or `stg.game` as source of record,
and audit every downstream reader that silently inherits the gap.

## Approach

1. Enumerate the gap from disk, not from memory — count `seasonType` per season across all
   35 `games_*.json`, the same for `lines_*.json`, and the same for `stg.game` /
   `stg.gameLines` in `data/cfb.duckdb`.
2. Static-parse `ENDPOINTS` against the vendored client signatures to find every endpoint
   that takes `season_type` — the blast radius is wider than `games`.
3. Grep every reader of `data/raw/games_*.json` and `data/processed/games.csv`.
4. Check whether the 2025 exception is benign: are its 50 bowls week-labelled in a way that
   collides with regular week 1, and do their running-stats features come out right?
5. Confirm the two `stg.game` anomalies (2020=562, 2023=139 non-regular) are real season
   types and not mislabels, so the source-of-record recommendation needs no qualifier.
6. Write one new section in `docs/data-coverage.md`. No code changes, no rescrape, no
   touching `scripts/build_prediction_tracker.py`.

## Done when

`docs/data-coverage.md` states the gap with per-season counts, names the source of record,
documents the `--force` footgun, and lists the impacted readers — and the audit is reported.
