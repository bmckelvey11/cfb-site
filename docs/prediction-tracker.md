# Prediction Tracker lines

`data/raw/prediction_tracker_lines.csv` — 17,755 rows × 179 columns, one row per
Prediction Tracker game 2001–2025, each carrying a CFBD `game_id`.

Built by `python scripts/build_prediction_tracker.py` from
`C:/Users/mckel/dev/cfb/prediction-tracker/ncaa*.csv` plus `stg.game` in `data/cfb.duckdb`.
No network. The output is gitignored (`data/`) — regenerate rather than commit it.

Upstream is [thepredictiontracker.com](https://www.thepredictiontracker.com), which
publishes one CSV per season holding the market line and every computer model's predicted
spread for that game.

## Column blocks

Columns are grouped, and within the model block ranked by how many rows they cover, so
the usable models come first and the long tail of one-season modelers sits at the end.

CFBD owns the unprefixed names, because it is the authoritative side. Prediction Tracker
columns keep their upstream spelling except for the one that collides: PT's `week` becomes
`pt_week`. Everything else PT ships — `home`, `road`, `hscore`, `vscore`, `actual`,
`total`, `phcover`, `phwin` — reads exactly as it does in the source CSVs.

### Identity (10) — CFBD, authoritative

| Column | Notes |
|---|---|
| `game_id` | CFBD game id. Null only on the single unmatched row. |
| `season` | From the source filename. |
| `week` | CFBD's week. Postseason weeks restart at 1 — read it with `season_type`. |
| `season_type` | `regular` or `postseason`. 815 rows are postseason. |
| `home_team`, `away_team` | CFBD's canonical names for the season in question. |
| `home_points`, `away_points` | CFBD final score, oriented to *CFBD's* home/away. |
| `orientation_flipped` | `1` when PT's home team is CFBD's away team — 409 rows, neutral sites and bowls. **When this is 1, `home` is `away_team` and `hscore` is `away_points`.** |
| `match_status` | `matched` (17,731), `matched_score_mismatch` (23), `ambiguous` (1). |

### Prediction Tracker meta (10)

Upstream names, unchanged. Kept for traceability — CFBD wins wherever the two disagree.

| Column | Notes |
|---|---|
| `home`, `road` | PT's team names, e.g. `Fresno St.`, `Miami (Fla.)`. Some are truncated to 16 chars (`Louisiana-Lafaye`). Not the same field as `home_team` on the 409 flipped rows. |
| `pt_week` | PT's own week numbering — the only PT column renamed, since CFBD owns `week`. It is not redundant: it disagrees with `week` on 30% of regular-season rows (almost always by 1), and PT numbers bowls 19/20 where CFBD restarts postseason at 1. |
| `date` | 2001–2002 only (7.6% fill); PT dropped the column afterwards. |
| `hscore`, `vscore` | PT's final score, home and visitor. See the caveat below. |
| `actual` | Home margin, `hscore - vscore`. |
| `total` | Combined points, `hscore + vscore`. |
| `phcover`, `phwin` | PT's probabilities that the home team covers / wins, 0–1. 2017+ only (38% fill). |

### Market (2)

`line` is the market spread and `lineopen` the opening spread.

**Signs are flipped from the source.** Prediction Tracker writes spreads positive when the
home team is favored; this file negates them so they match `GameRecord.spread` elsewhere in
the repo, where a favored home team gets a negative number. Every `line*` column is
negated on the way in except `linestd`. Verified after the build: mean `line` −4.75
against mean home margin +4.53, the same shape as `games.csv` (−6.66 / +6.65).

**Orientation is still PT's, not CFBD's.** Spreads are relative to `home`/`road`, so on
the 409 rows where `orientation_flipped` is 1, `line` refers to `away_team`, not
`home_team`. Negate again on those rows to get a CFBD-home-oriented spread.

### Consensus (3)

`lineavg`, `linemedian`, `linestd` — PT's own aggregates *over the model columns in that
row*, not models themselves. Verified against the source: `linemedian` reproduces the
median of the model columns exactly; `lineavg` and `linestd` track the mean and stdev
within rounding.

`linestd` is a dispersion, not a spread, so it is **not** sign-flipped. One cell in the
source carries a negative standard deviation, which is impossible; it is passed through
rather than special-cased.

### Models (154)

Every remaining `line*` column is one modeler's predicted spread, negated to the repo's
sign convention along with `line` (see Market above). The names are PT's own shorthand for
the modeler, and upstream is the only place they are defined — this file does not carry a
name-to-modeler key.

Coverage is wildly uneven. Four models cover ~100% of rows (`linesag`, `linepfz`,
`linehow`, `lineelo`); the bottom of the block includes `linemaxy` at 50 rows and a dozen
single-season entries. **Filter on fill before using a model in anything comparative** —
a model present for three seasons will look better or worse than one present for 25 for
reasons that have nothing to do with its accuracy.

Model names are only case-folded across seasons, never fuzzy-merged. Several stems look
like the same modeler under a renamed column, and their season spans are suspiciously
disjoint, but nothing in the source confirms it:

| Probably one modeler | Spans |
|---|---|
| `linemore` / `linemoore` | 2001–2013, 2014–2025 |
| `linegupt` / `linegupta` | 2001–2002, 2004–2007 |
| `lineburd` / `lineburdorf` | 2005, 2006–2019 |
| `linefremeau` / `linefei` | 2013–2016, 2017–2025 |

Merging them is a judgement call about upstream identity, not a data cleanup, so it is
left undone. Others that *look* related are genuinely distinct methods from one source and
should stay separate: the Sagarin family (`linesag`, `linesagr`, `linesagpred`,
`linesagelo`, `linesaggm`, `linesage`, `linesagp`) and the TSR family (`linetsr`,
`linetsr2/3/4`, `linetsrelo`, `linetsrslots`).

`linejens` was dropped — the column exists in the 2017 header with zero values behind it.

## Caveats

**Grade off `home_points`/`away_points`, not `hscore`/`vscore`.** 23 rows carry
`match_status=matched_score_mismatch`: the team pair is unique that season so the
`game_id` is certain, but PT's score is wrong or missing — 11 unfilled (mostly
hurricane-postponed 2016–17 games), 9 typos (Duke 29 vs 28, Rice 21 vs 14), 1 shifted row
(2006 New Mexico–Wyoming). One goes the other way: 2001 Oklahoma–North Carolina, where
*CFBD* carries 10-0 for a game that finished 41–27.

**9 `game_id`s appear on two rows each.** Four are games PT listed twice — the original
postponed date with a blank score plus the rescheduled result — and five are near-duplicate
PT rows differing only in a line value. Deduplicate on `game_id` before joining if a 1:1
row count matters.

**One row has no `game_id`**: 2017 UCF–Memphis, which PT files at week 3 with an unplayed
0–0 score while CFBD has two UCF–Memphis meetings that season (the rescheduled week 5 game
and the week 14 AAC championship), both typed `regular`. Nothing distinguishes them, so it
is left null rather than guessed.

**Junk cells are blanked, not carried through**: a team name that appeared in `linecoll`,
a run of NUL bytes in `lineanderson`, and the five shifted cells in that 2006 row.
