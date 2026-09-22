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
| **[greenline-findings.md](greenline-findings.md)** | **Start here.** Living summary — the twelve settled findings with a pointer to the record that establishes each, the four open questions and which one is worth the next hour, the standing cautions, and what it all implies for staking. Undated because it must stay current; if it disagrees with a dated record, the record wins |
| [greenline-under-filters-2026-09-22.md](greenline-under-filters-2026-09-22.md) | Six pre-registered situational filters, rerun on the 270 Greenline-only unders across all three eras (2020, 2022-23, 2026), stratified by era via CMH — supersedes the 09-17 run, which pooled the 2023-25 personal unders on a premise since found false. Nothing survives Holm; `big_fav`, the previous best candidate, weakens from Holm 0.256 to 0.906 |
| [greenline-pinnacle-shade-2026-09-17.md](greenline-pinnacle-shade-2026-09-17.md) | Does Pinnacle's position at capture (juice lean, line vs PFF's, distance from PFF's projection, limit) predict which unders win? n=38, nothing survives Holm; "Pinnacle already below PFF's line" is 9-2 raw |
| [greenline-w2-grade-2026-09-15.md](greenline-w2-grade-2026-09-15.md) | Week 2's 36 positive-edge unders graded, including the six flags that needed a score or line fallback |
| [greenline-w3-grade-2026-09-21.md](greenline-w3-grade-2026-09-21.md) | Week 3's 22-pick under list graded at PFF's number and at DraftKings' (11-11, neither price flips a pick), plus all 57 flags |
| [greenline-archive-2026-09-17.md](greenline-archive-2026-09-17.md) | The pre-2026 PFF archives parsed into one CSV — 2020 season plus three 2022-23 slates. 368 derived picks, price-aware grading, every split below floor; pooled CLV is a moneyline artifact |
| [greenline-archive-join-audit-2026-09-21.md](greenline-archive-join-audit-2026-09-21.md) | Is the parsed archive safe to query? `is_greenline_pick` is copied onto all three snapshots (1,104 rows vs 368 picks — deliberate, still a trap), and two slots were joined to the wrong CFBD game via a weak-token name match. Matcher fixed, one transposed game repaired, 220 export picks derived, archive re-parsed the same day; audit now clean |
| [greenline-export-picks-graded-2026-09-21.md](greenline-export-picks-graded-2026-09-21.md) | The 220 derived 2022-23 export picks graded against CFBD finals: 80-73 on spread+total, every judgeable split below its MDE floor. No ROI — the exports carry no price, which is an integrity-gate failure — and moneyline is not judgeable at all. Also replays the totals through `grade_greenline.py`: 0 result disagreements on 77 shared picks |
| [greenline-totals-pooled-2026-09-22.md](greenline-totals-pooled-2026-09-22.md) | All three graded totals eras pooled — 2020 PFF_hist, the 2022-23 exports, and 2026 through week 3. 324 picks, 175-149 (54.0%, Wilson 48.6–59.4) against a 59.3% floor; eras homogeneous (p 0.93) so the pool is legitimate; overs match unders (p 0.96); ROI only on the 237 priced rows, interval straddling zero. Also measures the 2023-25 personal unders as a fourth stratum (114-87, +8.2% at real prices) and, for the first time, their actual overlap with Greenline's board: 7 of 12 checkable bets the same pick, **3 the opposite side** |
| [greenline-clv-market-close-2026-09-22.md](greenline-clv-market-close-2026-09-22.md) | Do the flags beat a real market close, and does the Pinnacle feed need filtering? Both: the gate is required — ungated CLV reads +0.24 pts but the 18 corrupt rows it removes carry +1.06 on their own — and once gated the CLV is **+0.06 ± 0.48, i.e. zero**, agreed by all three gated policies and stable from 0.5 to 5 points of tolerance |
| [greenline-flag-clv-contrast-2026-09-22.md](greenline-flag-clv-contrast-2026-09-22.md) | Does the published under list, or the size of PFF's stated `value`, predict CLV? **Neither is distinguishable from zero and neither could have been** — the list contrast is −0.36 pts against a 1.46-pt MDE, the edge slope −0.03 pts/SD against 0.69. A bound, not an answer: it rules out effects above ~1.5 pts. 79 flags on 4 slate dates, 54 on one Saturday, so the design effect is 3.1 at ICC 0.05. Re-look at ~595 scored flags, which is the end of the 2026 season |
| [pff-line-movement-2026-09-22.md](pff-line-movement-2026-09-22.md) | Do team-level PFF stats predict how the market moves a total between open and close? Yes, one of them: dropback-weighted passing grade is worth **+0.26 points per SD** (Holm p 0.003) over 956 games, same sign in both seasons and unmoved by week-clustering — about 1pp of win probability, a nudge on the number rather than a filter. The Greenline flag interaction is unidentified: every FBS game the analysis can use was on the board |
| [greenline-totals-rule-search-2026-09-22.md](greenline-totals-rule-search-2026-09-22.md) | What edge threshold and totals band to bet, each side, searched over the pooled 324. No rule survives: the best cell (under/55-59.5/Q4, 63.6%) is matched by a within-era shuffle 54.7% of the time, the walk-forward is *not runnable* because the eras' boards barely overlap, nothing survives Holm, and overs are not estimable at n=54. Registers one hypothesis for weeks 4+ — PFF's top edge quintile is its worst |
| [../../bankroll/docs/under-selection-profile-2026-09-17.md](../../bankroll/docs/under-selection-profile-2026-09-17.md) *(in `research/bankroll/`)* | Which unders got bet, 2023-25, against every FBS game on the same days — the selection is a high-total rule, and the bet unders sit six points above where Greenline flags |

> **Read the MDE line before quoting any record.** Each review states the smallest true win
> rate its own sample could reliably detect. Every split so far sits below that floor, so
> the numbers are not evidence in either direction — not for an edge, and not against one.
>
> **The 2023-25 personal unders are not an independent sample, and not a pool member.**
> Measured on the only days where a Greenline board and a book bet both exist: 7 of 12 are
> the same pick, **3 take the side Greenline flagged against**, 2 are games it never flagged.
> Report them as a comparison stratum with their own interval — never as a baseline, never as
> out-of-sample confirmation, never as a row inside a pooled Greenline record.

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
| 3b | [`../scripts/grade_unders_list.py`](../scripts/grade_unders_list.py) | Grades the published under list only, at PFF's number and the repriced book number side by side, with Wilson intervals |
| 4 | [`../scripts/greenline_season_review.py`](../scripts/greenline_season_review.py) | Rolls every graded week into the review docs above |
| 5a | [`../scripts/greenline_bet_stats.py`](../scripts/greenline_bet_stats.py) | Full workup: exact binomial, Beta posterior, bootstrap, heterogeneity, runs test, day-clustered SE |
| 5b | [`../scripts/greenline_bet_bounds.py`](../scripts/greenline_bet_bounds.py) | Conservative bet test — is a split still +EV at the Wilson *lower* bound? |
| 5c | [`../scripts/greenline_edge_window.py`](../scripts/greenline_edge_window.py) | Does PFF's stated `value` rank anything? Win rate by edge bin, logistic fit, edge vs Pinnacle disagreement |
| 5d | [`../scripts/under_filters.py`](../scripts/under_filters.py) | Pre-registered situational filters on the pooled unders (history treated as Greenline flags, kept as a stratum): Wilson records per stratum, Fisher, day-clustered logistic with a filter×source interaction, Holm across filters |
| 5h | [`../scripts/greenline_flag_clv_contrast.py`](../scripts/greenline_flag_clv_contrast.py) | The two contrasts that vary inside the board — under-list membership and stated `value` — against CLV, reusing `greenline_clv.py`'s capture-to-close measurement and its Pinnacle gate. Reports MDE and a slate-ICC design-effect sensitivity beside every estimate, because 79 flags on 4 dates cannot carry a clustered SE |
| 5g | [`../scripts/pff_line_movement.py`](../scripts/pff_line_movement.py) | The same five PFF features against total line movement instead of win/loss: cluster-robust OLS with week FE, Holm across features, season-stability split, week-cluster robustness, and a 2025→2026 out-of-sample check. Carries its own pre-registered analysis plan and MDE in the docstring |
| 5f | [`../scripts/pff_under_filters.py`](../scripts/pff_under_filters.py) | Five registered team-level PFF features (pass rush, run-heavy, no-deep, weak QB, coverage), season-to-date with a prior-season fallback and a week-14 cap against lookahead. Gates on MDE first: only the 2026 era joins PFF, so at n=88 the gate fails and the search does not run. `--force` overrides |
| 5e | [`../scripts/pinnacle_shade.py`](../scripts/pinnacle_shade.py) | Four pre-registered Pinnacle features on the graded unders (lean, move, disagree, limit): Wilson records, Fisher, Spearman, Holm. Picks up each week's `greenline_vs_pinnacle_*` capture automatically |
| — | [`../scripts/greenline_pricing.py`](../scripts/greenline_pricing.py) | Side analysis: reverse-engineers the arithmetic behind PFF's displayed numbers |
| — | [`../scripts/parse_greenline_history.py`](../scripts/parse_greenline_history.py) | Off-pipeline: parses the pre-2026 OneDrive archives (`PFF_hist.xlsx`, `ncaa-best-bets*.csv`) into one long-form CSV. Derives the pick from the opening Greenline snapshot, never the close |
| — | [`../scripts/greenline_archive_review.py`](../scripts/greenline_archive_review.py) | Grades that archive — break-even from the quoted price per market, ROI, and MDE per split |
| — | [`../scripts/audit_archive_joins.py`](../scripts/audit_archive_joins.py) | Audits that archive's `game_id` joins against CFBD by score consistency — the only test that catches a wrong match sharing a school-name token. Exits 1 on failure |
| — | [`../scripts/grade_export_picks.py`](../scripts/grade_export_picks.py) | Grades the export-slate picks from CFBD finals at the captured line: Wilson and game-clustered intervals, MDE per split, no ROI (no price in the source) |
| — | [`../scripts/greenline_clv.py`](../scripts/greenline_clv.py) | CLV against a market close instead of PFF's own board. `usable_close()` gates every Pinnacle number against the book median; `--compare` runs all four gate policies plus a tolerance sweep so the gate is tested rather than assumed |
| — | [`../scripts/totals_rule_search.py`](../scripts/totals_rule_search.py) | Searches the pooled corpus for an edge × band rule and then tries to kill it: era composition per bin, within-era edge quintiles, pre-registered 5-point bands, the full 60-cell grid, a max-cell permutation null, two-way walk-forward, and Holm over four pre-registered splits |
| — | [`../scripts/pool_totals_record.py`](../scripts/pool_totals_record.py) | Pools all three graded eras into one totals record: per-era and pooled Wilson + MDE, chi-square heterogeneity across eras, day-clustered SE, side splits, the published under lists as a nested subset, and ROI restricted to the price-bearing rows |
| — | [`../scripts/format_exports_for_grading.py`](../scripts/format_exports_for_grading.py) | Reshapes the export total picks into the weekly capture format so `grade_greenline.py` can replay them, into a separate `export_replay/` dir and a separate graded file. Cross-check: both graders agree on all 77 shared picks |
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

## Strand 3 — Warehouse feature research

**Code-backed results against the warehouse, market-relative.** Each doc pairs with a
reusable script under [`../scripts/`](../scripts/) and reports its own MDE, so a null can be
read as a bound rather than an absence.

| Doc | What it reports |
| --- | --- |
| [kicker-quality-volatility-totals-2026-09-18.md](kicker-quality-volatility-totals-2026-09-18.md) | Do prior-season kicker quality (CFBD PAAR) and kicker volatility (FG overdispersion) move the total past the closing book line? 5,776 games 2018-25, two-way clustered. Nothing bettable: the CI upper bound buys 51.5% over against a 52.38% break-even. Underpowered 3x (mean) and 11x (dispersion) against the mechanical ceiling, so it is a bound, not a zero. PAAR does not persist year to year (r 0.16) |

| Script | What it does |
| --- | --- |
| [`../scripts/kicker_totals_effect.py`](../scripts/kicker_totals_effect.py) | Builds the prior-season kicker panel, fits both channels with two-way cluster-robust SEs, derives each channel's mechanical ceiling and MDE, and translates the coefficient interval into an over rate against break-even. `--self-check`, `--cache` |

---

## Provenance

This tree predates the 2026-09-16 docs pass with the three Greenline reviews, its scripts,
and `figs/`. That pass moved the strand-2 material in from root `docs/` (it is totals-only
and root `docs/` is for shared docs) and added this index plus [`../CLAUDE.md`](../CLAUDE.md),
which is when `research/totals/` entered root `CLAUDE.md`'s units table. See
[`../../../docs/README.md`](../../../docs/README.md) for that pass's write-up.
