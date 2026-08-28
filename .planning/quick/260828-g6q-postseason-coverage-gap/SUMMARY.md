---
task: Document the regular-season-only gap in raw games/lines and audit what inherits it
status: complete
created: 2026-08-28
completed: 2026-08-28
---

# Summary

`docs/data-coverage.md` gained a top section, **"Season type — `data/raw/` is
regular-season only, and 2025 is the inconsistent one"**, placed ahead of the spec-path
coverage material because it describes a live correctness issue rather than a documented
absence. No code changed, nothing was re-scraped, and
`scripts/build_prediction_tracker.py` was not touched.

## What the audit found

**The gap.** 52,982 `regular` rows and 86 `postseason` rows across all 35
`games_*.json`; the 86 are 2025 alone. `lines_*.json` matches: postseason lines exist for
2025 only (50). So bowls, conference championships and CFP games are missing for
1992-2024 on both sides of the join — even if games had been pulled, there would have
been no lines to grade them with.

**2025 is not the good season, it's the inconsistent one.** Its postseason rows arrived
from `upcoming.py:93-94`, which calls CFBD with `season_type="both"` and then overwrites
the whole `games_{season}.json` / `lines_{season}.json` pair. Because CFBD numbers
postseason weeks from 1 and `GameRecord` has no season-type field, those 50 bowls sit in
`games.csv` labelled **week 1**, indistinguishable from the 127 regular-season openers in
the same bucket (177 rows total). 2025 is the holdout, so `--week 1` and every
week-derived feature mean something different in the holdout than in training — undeclared.

`running_stats.py` is unaffected only because it sorts on raw `startDate`; the 50 bowls
enter with `running_games_played` 10-15, which is right. Its
`f"{season}-w{week:02d}"` fallback (`running_stats.py:29`) would have sorted them ahead of
every regular-season game at `games_played=0`.

**Blast radius is 19 endpoints, not 2.** Static-parsing `ENDPOINTS` against the vendored
client signatures: 19 of 73 registered endpoints accept `season_type`, and every one is on
disk as regular-only. `PER_GAME` inherits it twice over — `_seed_game_ids`
(`scrapers.py:441`) seeds from `games_{season}.json`, so `advanced_box_score` and
`win_probability` were never called for a bowl.

**Source of record is `stg.game`.** 112,673 rows, real postseason back to 1901, versus
`stg.games` (the REST dump, plural) at 53,068 inheriting the gap exactly. Two apparent
anomalies were checked and are real season types, not mislabels: 2020's 562 non-regular
rows are `spring_regular`/`spring_postseason` (the COVID-shifted spring 2021 lower-division
season; true 2020 postseason is 30), and 2023's 139 span all four divisions (FBS 42).
So the recommendation needs no qualifier beyond "filter on classification".

**A postseason pass would destroy data.** `_scrape_season` writes
`{name}_{season}.json` with no season-type dimension, so a second pass has nowhere to
land: resume skips the existing file and `--force` replaces the regular rows with
postseason-only rows. `SeasonType` accepts `both`, which `upcoming.py` already uses, so
the correct shape is `--season-type both --force` across the 19 endpoints — one superset
file per season, no schema change. Flagged as untested: `both` on the `SEASON_WEEK`
endpoints, where `weeks=range(1,16)` meets postseason week numbering that restarts at 1.

**Backtest impact, quantified.** 515 FBS postseason games 2013-2025, and `stg.gameLines`
has a line for all 515. 50 are already in `games.csv`; 465 are missing, ≈3.4% of the
13,479-row sample `build` would otherwise produce. Small, but not a random 3.4% — bowls
are a distinct population (long layoffs, opt-outs, neutral sites, coaching changes), so no
system in the repo has been tested where naive systems most often break.

Impacted readers are tabled in the doc: `build`/`normalize` → `games.csv` and everything
downstream (`enrich`, `backtest`, `web`, `/compare`, `v1_model`), `enrich.py:112`,
`clv.py:96`, `duckdb_load.py`'s `raw.games`/`stg.games`,
`scripts/analyze_coach_styles.py:231`, and `scrapers.py:441`. `betlog.py:237` is the
sharpest one: its comment explains that a January bowl belongs to the prior season's file
and it deliberately checks year and year-1 — but those files contain no bowls, so bowl
bets land in `unmatched` rather than raising.

## Left undone, deliberately

- No re-scrape. The `--season-type both` run is a recommendation in the doc, not an action.
- `betlog.py`'s silently-unmatched bowl bets are named as an impacted analysis, not fixed.
- `GameRecord` gains no `season_type` column — that is a `storage.py` CSV-schema migration
  under the project's stated stability constraint, not an ad hoc add.
