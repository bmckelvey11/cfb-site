# Pregame filter migration — 2026-09-10

## Request and result

Remove Attendance from System Maker and replace the remaining Result Lookahead
filters with values based on information from before each game. Attendance is
removed from the feature registry and loaded feature snapshots; raw source data
and warehouse fields are unchanged. No registered features remain in Result
Lookahead. Existing feature keys are preserved for saved-system compatibility.

## Definitions

| Filters | Replacement |
| --- | --- |
| Offense and defense havoc | Equal-weight average of available earlier game rates in the same season |
| Five NGT defense statistics | Equal-weight average of available earlier game values in the same season |
| Team win probability | Genuine pregame probability endpoint; away probability is one minus home probability |
| Core rating | Previous season's rating, fixed throughout the target season |
| Coach playstyle | Previous season's principal coach, classified using a model trained only on seasons before the target season |

`prior_game_stats.py` uses raw schedule history, including games absent from the
processed betting dataset. A history game must have final scores, must not be
marked incomplete, and must have a known timezone-aware kickoff at least 24 hours
before the target kickoff. The current game never contributes. Invalid dates,
nonfinite values, and other seasons are excluded. Each field averages its own
available values. Season openers and missing history stay null and fail filters
closed. These are averages of game statistics, not play-weighted season totals.

Coach models refit scaling, residualization, and clustering separately for each
target season. Training uses available 2016–2024 seasons strictly before that
target, with at least three seasons per coach. Earliest supported target is 2019.
The 2026 snapshot uses 2016–2024 training and 2025 coach assignments (84 teams).
This describes the team's previous coach where a coaching change occurred; it
does not claim to classify a new coach's current-season strategy. The legacy
career-wide generated labels are not used by this feature.

Core rating preserves both `core_overall` and existing `prior_core_overall` keys;
both now refer to the previous season. No unsupported current-season estimate is
invented. Historical source files can contain later corrections: the 24-hour lag
is a conservative availability rule, not proof of the source's original
publication time. These changes do not establish archived data vintages or
validate every other feature in the registry.

## Rebuild and coverage

Rebuilt 13,802 records across 2013–2026 and 99 upcoming records. Counts below are
non-null team-game values, out of 27,604 possible historical values (including
unplayed records). Source gaps and season openers account for missing values.

| Feature | Non-null values |
| --- | ---: |
| Pregame win probability | 22,042 |
| Each havoc rate | 23,171 |
| Each of five NGT defense statistics | 24,528 |
| Previous-season core rating | 14,741 |
| Prior-season coach playstyle | 8,213 |

Fetched missing 2026 source files with the repository virtual environment:
398 havoc rows and 406 NGT advanced-game rows; two endpoints, no failures.
The vendored client requires its compatible Pydantic environment.

```powershell
.venv\Scripts\python.exe -m cfb_system_maker scrape --season 2026 --only game_havoc_stats advanced_game_stats_ngt --data-dir data
python -m scripts.rebuild_pregame_features --data-dir data
```

The rebuild script backs up derived snapshots, generates per-season coach
models, rebuilds historical and upcoming features, and writes
`data/processed/pregame_feature_audit.json`. Snapshot replacements are atomic.
Registry version `8c821bc205c9` hashes full feature definitions. Legacy or stale
snapshots suppress migrated values until rebuilt, so old postgame values cannot
silently acquire pregame labels.

Original pre-migration backup:
`data/processed/feature_backups/20260910T151040979078Z`.
Successful rebuild backup:
`data/processed/feature_backups/20260910T151204910388Z`.
An initial rebuild completed historical enrichment but encountered an upcoming
loader tuple mismatch; that was corrected before the successful full rebuild.

## Verification

- Full default suite: **855 passed, 1 skipped, 6 deselected**. Existing numerical
  warnings remain in combination-sweep tests.
- Tests cover current/future-game exclusion, raw-only history, incomplete games,
  missing dates, season boundaries, nonfinite values, stale snapshot rejection,
  valid pregame probability, and coach model invariance to future-data changes.
- Live browser: saved SEC Primetime Unders system loads; Attendance and Result
  Lookahead are absent; converted filters appear in their new groups.
- Applied `Def PPA (to date, NGT)`, bet-side maximum 0, to an unsaved 2026 test
  system. Returned nine decided bets and displayed 20.5% feature coverage. This
  verifies filtering and missing-value handling, not predictive performance.
- Historical and upcoming rebuilds completed; app restarted with current code.
