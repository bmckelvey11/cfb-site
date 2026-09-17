# `research/totals/` index

Totals work not yet in a harness. Two strands, with nothing shared between them:
**Greenline vendor-pick evaluation** (working code and graded results) and **totals
modeling research** (reading and prompt material, no code). Unit rules live in
[`../CLAUDE.md`](../CLAUDE.md); the implemented backtest harness is `models/totals/`, not
this tree.

---

## Strand 1 — PFF Greenline vendor-pick evaluation

Does PFF Greenline's board actually win? Captures come in weekly, get graded at the line
PFF showed, and accumulate until the sample can answer.

### Results

| Doc | What it reports |
| --- | --- |
| [greenline-season-review-2026-09-16.md](greenline-season-review-2026-09-16.md) | Season to date, all three markets — record, Wilson intervals, units, ROI, CLV, calibration, and the minimum detectable win rate for each sample |
| [greenline-totals-season-2026-09-16.md](greenline-totals-season-2026-09-16.md) | The same review narrowed to totals, with the CLV section against the PFF board close |
| [greenline-band-significance-2026-09-17.md](greenline-band-significance-2026-09-17.md) | Is the market-total band split real? Chi-square, Fisher, best-of-six correction, trend, and out-of-sample ordering test. Not significant; band ordering withdrawn |
| [greenline-under-filters-2026-09-17.md](greenline-under-filters-2026-09-17.md) | Six pre-registered situational filters (line move, wind, pace, big favorite, night, short rest) on the pooled unders, history and 2026 kept as strata. Nothing survives Holm; big favorites is the only split under p 0.05 raw |
| [greenline-pinnacle-shade-2026-09-17.md](greenline-pinnacle-shade-2026-09-17.md) | Does Pinnacle's position at capture (juice lean, line vs PFF's, distance from PFF's projection, limit) predict which unders win? n=38, nothing survives Holm; "Pinnacle already below PFF's line" is 9-2 raw |
| [greenline-w2-grade-2026-09-15.md](greenline-w2-grade-2026-09-15.md) | Week 2's 36 positive-edge unders graded, including the six flags that needed a score or line fallback |
| [greenline-archive-2026-09-17.md](greenline-archive-2026-09-17.md) | The pre-2026 PFF archives parsed into one CSV — 2020 season plus three 2022-23 slates. 368 derived picks, price-aware grading, every split below floor; pooled CLV is a moneyline artifact |
| [../../bankroll/docs/under-selection-profile-2026-09-17.md](../../bankroll/docs/under-selection-profile-2026-09-17.md) *(in `research/bankroll/`)* | Which unders got bet, 2023-25, against every FBS game on the same days — the selection is a high-total rule, and the bet unders sit six points above where Greenline flags |

> **Read the MDE line before quoting any record.** Each review states the smallest true win
> rate its own sample could reliably detect. Every split so far sits below that floor, so
> the numbers are not evidence in either direction — not for an edge, and not against one.
>
> **The 2023-25 personal unders are not an independent sample.** They were mostly the same
> Greenline flags, taken as bets. Pool them as prior evidence; never as a baseline.

### Pipeline

Scripts hand off through CSVs under `$CFB_DATA_ROOT/ingest/pff_scoreboard/`. Out of order,
they silently read a stale capture.

| Step | Script | What it does |
| --- | --- | --- |
| 0 | `scripts/pull_pff_scoreboard.py` *(root `scripts/`, not this tree)* | Captures the week's Greenline board, schedule, and bet splits |
| 1 | [`../scripts/greenline_unders.py`](../scripts/greenline_unders.py) | Writes the week's positive-edge under list, ranked by PFF's `value` |
| 2a | [`../scripts/match_greenline_books.py`](../scripts/match_greenline_books.py) | Reprices each flag at a book's actual number from the-odds-api |
| 2b | [`../scripts/greenline_vs_pinnacle.py`](../scripts/greenline_vs_pinnacle.py) | Compares the projection to Pinnacle — the reference price, not another book |
| 3 | [`../scripts/grade_greenline.py`](../scripts/grade_greenline.py) | Grades captured flags against finals, at the line in the capture |
| 4 | [`../scripts/greenline_season_review.py`](../scripts/greenline_season_review.py) | Rolls every graded week into the review docs above |
| 5a | [`../scripts/greenline_bet_stats.py`](../scripts/greenline_bet_stats.py) | Full workup: exact binomial, Beta posterior, bootstrap, heterogeneity, runs test, day-clustered SE |
| 5b | [`../scripts/greenline_bet_bounds.py`](../scripts/greenline_bet_bounds.py) | Conservative bet test — is a split still +EV at the Wilson *lower* bound? |
| 5c | [`../scripts/greenline_edge_window.py`](../scripts/greenline_edge_window.py) | Does PFF's stated `value` rank anything? Win rate by edge bin, logistic fit, edge vs Pinnacle disagreement |
| 5d | [`../scripts/under_filters.py`](../scripts/under_filters.py) | Pre-registered situational filters on the pooled unders (history treated as Greenline flags, kept as a stratum): Wilson records per stratum, Fisher, day-clustered logistic with a filter×source interaction, Holm across filters |
| 5e | [`../scripts/pinnacle_shade.py`](../scripts/pinnacle_shade.py) | Four pre-registered Pinnacle features on the graded unders (lean, move, disagree, limit): Wilson records, Fisher, Spearman, Holm. Picks up each week's `greenline_vs_pinnacle_*` capture automatically |
| — | [`../scripts/greenline_pricing.py`](../scripts/greenline_pricing.py) | Side analysis: reverse-engineers the arithmetic behind PFF's displayed numbers |
| — | [`../scripts/parse_greenline_history.py`](../scripts/parse_greenline_history.py) | Off-pipeline: parses the pre-2026 OneDrive archives (`PFF_hist.xlsx`, `ncaa-best-bets*.csv`) into one long-form CSV. Derives the pick from the opening Greenline snapshot, never the close |
| — | [`../scripts/greenline_archive_review.py`](../scripts/greenline_archive_review.py) | Grades that archive — break-even from the quoted price per market, ROI, and MDE per split |
| — | [`../../bankroll/scripts/greenline_bet_log.py`](../../bankroll/scripts/greenline_bet_log.py) *(in `research/bankroll/`)* | **The ledger of which flags actually got bet.** Reads these captures; seed after every one |
| — | [`../../bankroll/scripts/under_selection_profile.py`](../../bankroll/scripts/under_selection_profile.py) *(in `research/bankroll/`)* | Profiles the 2023-25 bet unders against the slate they were picked from |

Every script takes `--self-check`.

### The weekly habit — owned by `research/bankroll/`

Capture is automated; **marking is not, and an unmarked week is lost data.** The ledger
distinguishes `y`, `n`, and blank, and blank means *not yet marked* — coverage refuses to
compute on a week that still has blanks, because defaulting them to "no" manufactures the
very number the ledger exists to measure.

```
python research/bankroll/scripts/greenline_bet_log.py --seed          # after each capture
python research/bankroll/scripts/greenline_bet_log.py --import-book   # after a book re-export
python research/bankroll/scripts/greenline_bet_log.py --show 4        # review the week
python research/bankroll/scripts/greenline_bet_log.py --mark 4 31190   # or --none 4
python research/bankroll/scripts/greenline_bet_log.py --coverage
```

`--import-book` is the low-effort path: re-export the book to
`data/ingest/bet_history/history.csv` and it marks a whole week in one pass — `y` for
flags it finds a matching total on, `n` for the rest of that day's flags. It resolves
both sides to CFBD team ids first, because PFF and the book disagree on 32 of 137
abbreviations, and it only touches days the export actually covers.

This is the only thing that can answer whether the personal under record transfers to
Greenline's flags: no work on 2023-25 can, because no flag archive for those seasons
exists.

### Figures

[`figs/`](figs/) — `band_winrate.png`, `cumulative_units.png`, `pinnacle_shade.png`,
regenerated by `greenline_season_review.py --figs`.

---

## Strand 2 — Totals modeling research

**Reading and prompt material. No code, no tests, no results.** Every claim here is a
hypothesis to test against the warehouse, not a finding. Do not cite any of it as evidence.
Anything that gets built and backtested belongs in `models/totals/`.

| Doc | What it is |
| --- | --- |
| [fbs-totals-frontier-models.md](fbs-totals-frontier-models.md) | Survey of frontier modeling approaches for FBS totals (+ [`.pdf`](fbs-totals-frontier-models.pdf)) |
| [fbs-totals-system-research-report.md](fbs-totals-system-research-report.md) | Long-form research report on a pregame totals betting system |
| [research-prompts/fbs-totals/](research-prompts/fbs-totals/) | 15 numbered research prompts plus a README — odds-data audit, market-implied score distributions, price discovery, error anatomy, cold starts, joint spread/total modeling, uncertainty decomposition, abstention, staking, drift monitoring, governance, synthesis |

---

## Provenance

This tree predates the 2026-09-16 docs pass with the three Greenline reviews, its scripts,
and `figs/`. That pass moved the strand-2 material in from root `docs/` (it is totals-only
and root `docs/` is for shared docs) and added this index plus [`../CLAUDE.md`](../CLAUDE.md),
which is when `research/totals/` entered root `CLAUDE.md`'s units table. See
[`../../../docs/README.md`](../../../docs/README.md) for that pass's write-up.
