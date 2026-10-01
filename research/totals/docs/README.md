# `research/totals/` index

Totals work not yet in a harness. Two strands, with nothing shared between them:
**Greenline vendor-pick evaluation** (working code and graded results) and **totals
modeling research** (reading and prompt material, no code). Unit rules live in
[`../CLAUDE.md`](../CLAUDE.md); the implemented backtest harness is `models/middle/`, not
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
| [greenline-clv-all-eras-2026-09-23.md](greenline-clv-all-eras-2026-09-23.md) | Do Greenline's totals picks beat the close, measured one way across all three eras? Pooled unders **+0.29 ± 0.21 pts** (p 0.004, n=265) but the eras disagree: 2020 ~0, 2026 **+0.50**, which holds at one book (DraftKings at capture vs its own close, +0.51 ± 0.21) with both sides moving toward PFF. Also finds GraphQL-only closes in `core.fact_game_line` are in-game totals, which withdraws the 2026-09-22 CLV. Its CLV numbers are updated by the 09-28 record below; the in-game-close finding stands here |
| [greenline-clv-through-week4-2026-09-28.md](greenline-clv-through-week4-2026-09-28.md) | Does the 09-23 CLV result hold with week 4 graded? Pooled unders still beat the close (+0.25 ± 0.18, p 0.003, n=313), but 2026 falls to +0.34 and the 2026-vs-2020 gap no longer separates (p 0.047 → 0.195); DraftKings same-book unders +0.35 ± 0.26 |
| [greenline-pff-under-filters-2026-09-28.md](greenline-pff-under-filters-2026-09-28.md) | Do five registered team-level PFF stats filter the Greenline unders? First run, once the power gate opened at n=136: nothing survives Holm (smallest 0.337), per-feature floors 72–75% |
| [pff-projection-skill-2026-09-28.md](pff-projection-skill-2026-09-28.md) | How much edge does PFF's total projection carry over the market line it displays? Pooled 2020 plus 2026 weeks 2-3 (516 games): 63% of its disagreement is real (−72% to +198%), about 2.2 pp of win probability per game against 2.38 needed at −110 — roughly the vig, upper bound 7 pp. 2020 alone scores worse than a coin at the line; 2026 weeks 2-3's strong slope rests on 5 dates |
| [greenline-price-filter-backtest-2026-09-28.md](greenline-price-filter-backtest-2026-09-28.md) | Do the bet rules (best DK/FD total above the PFF market line, or ≥ PFF projection + 2.0; both ≥ Pinnacle fair) hold on weeks 2-4, with prices rebuilt at decision time? 12 and 11 bets, 5-7 and 5-6 — noise at ~90% detection floors. The price is real (CLV +1.04 / +0.84, every moved close toward the under); PFF's projection edge runs ~4 points above what the flags return; the Pinnacle leg alone flips sign with snapshot timing |
| [greenline-flag-clv-contrast-2026-09-28.md](greenline-flag-clv-contrast-2026-09-28.md) | Does the published under list, or the size of PFF's stated `value`, predict CLV? Rerun of the 09-22 test (archived) on REST-backed closes, weeks 2-3: list −0.01 pts (MDE 0.56), edge slope +0.05 pts/SD (MDE 0.28), both null and unchanged with DK/FD left out of the capture line. Exploratory: best DK/FD total minus PFF projection +0.21 pts/SD, p 0.086. On the valid close the next look is due at ~135 flags, not ~595. Look 1 of the sequence; look 2 is below |
| [greenline-flag-clv-contrast-2026-09-28-w2-4.md](greenline-flag-clv-contrast-2026-09-28-w2-4.md) | Look 2, the scheduled one: the same contrasts on weeks 2-4, 164 flags on 8 slate dates. List −0.03 pts (MDE 0.47), edge slope +0.08 pts/SD (MDE 0.23), Holm 0.65 — still null. The weeks 2-3 book-minus-projection hint did not replicate: week 4 alone +0.03 pts/SD (p 0.80); pooled +0.14 (p 0.14) |
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
| 5f | [`../scripts/pff_under_filters.py`](../scripts/pff_under_filters.py) | Five registered team-level PFF features (pass rush, run-heavy, no-deep, weak QB, coverage), season-to-date with a prior-season fallback and a week-14 cap against lookahead. Gates on MDE first: only the 2026 era joins PFF. The gate failed at n=88 and first opened at n=136 (2026-09-28; null). `--force` overrides |
| 5e | [`../scripts/pinnacle_shade.py`](../scripts/pinnacle_shade.py) | Four pre-registered Pinnacle features on the graded unders (lean, move, disagree, limit): Wilson records, Fisher, Spearman, Holm. Picks up each week's `greenline_vs_pinnacle_*` capture automatically |
| 5i | [`../scripts/greenline_price_filter.py`](../scripts/greenline_price_filter.py) | The bet rule (E: ≥ PFF projection + 2.0 and ≥ Pinnacle fair) and four registered variants, with the PFF market line and PFF projection named apart, backtested with DK/FD and Pinnacle rebuilt from the snapshots at each capture: record, ROI bootstrap, MDE, CLV, by-week folds, and a Pinnacle-timing sensitivity. `best_book` and `passes` are the rule itself, for reuse by a weekly bet list |
| — | [`../scripts/build_greenline_history.py`](../scripts/build_greenline_history.py) | **The master analysis table**: `$CFB_DATA_ROOT/processed/greenline/greenline_history.csv`, one row per era × game × market for every Greenline source (picks and non-picks, `is_pick`), plus personal 2023-25 totals as `source=personal`. Normalizes spread sign conventions across eras, names each close and CLV by its source, joins decision-time book/Pinnacle prices, the price rules, and the ledger. Asserts the known records on every build. Column dictionary and embargo notes in its docstring; rebuild after each graded week |
| 5j | [`../scripts/pff_projection_skill.py`](../scripts/pff_projection_skill.py) | PFF's projection as a forecast against the market line PFF displayed at the same moment: level (shade vs where games land), date-clustered slope of (actual − line) on (projection − line) converted to points and win probability, MAE, hit rate, Brier and log loss. 2020 open-Greenline snapshot one row per game; 2026 slope held to weeks 2-3 while question C is embargoed |
| — | [`../scripts/greenline_pricing.py`](../scripts/greenline_pricing.py) | Side analysis: reverse-engineers the arithmetic behind PFF's displayed numbers |
| — | [`../scripts/parse_greenline_history.py`](../scripts/parse_greenline_history.py) | Off-pipeline: parses the pre-2026 OneDrive archives (`PFF_hist.xlsx`, `ncaa-best-bets*.csv`) into one long-form CSV. Derives the pick from the opening Greenline snapshot, never the close |
| — | [`../scripts/greenline_archive_review.py`](../scripts/greenline_archive_review.py) | Grades that archive — break-even from the quoted price per market, ROI, and MDE per split |
| — | [`../scripts/audit_archive_joins.py`](../scripts/audit_archive_joins.py) | Audits that archive's `game_id` joins against CFBD by score consistency — the only test that catches a wrong match sharing a school-name token. Exits 1 on failure |
| — | [`../scripts/grade_export_picks.py`](../scripts/grade_export_picks.py) | Grades the export-slate picks from CFBD finals at the captured line: Wilson and game-clustered intervals, MDE per split, no ROI (no price in the source) |
| — | [`../scripts/greenline_clv.py`](../scripts/greenline_clv.py) | CLV against a market close instead of PFF's own board. `usable_close()` gates every Pinnacle number against the book median; `--compare` runs all four gate policies plus a tolerance sweep so the gate is tested rather than assumed. **Its closes include GraphQL-only in-game totals; use `greenline_clv_all_eras.py` for a CLV number** |
| — | [`../scripts/greenline_clv_all_eras.py`](../scripts/greenline_clv_all_eras.py) | CLV for every pooled Greenline under, all three eras, against the median REST-backed book close: per-era rows, 2020-vs-2026 heterogeneity, pick-minus-unpicked drift, a same-book DraftKings check for 2026, and a sensitivity table over five close definitions. Analysis plan in the docstring |
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
Anything that gets built and backtested belongs in `models/middle/`.

| Doc | What it is |
| --- | --- |
| **[totals-modeling-guide.md](totals-modeling-guide.md)** | **Start here.** Living guide that merges the two reports below with the starter framework and the regression/priors conversation notes, then checks each claim against this repo's records: what to predict ($r^{\text{final}}$, $r^{\text{move}}$), which line eras can support ROI or CLV, opponent-adjusted points per possession and pace, previous-season priors fit as one prior-centered ridge, the step from a predictive distribution to EV at the offered price, the model ladder, a validation calendar, and eight open items. Adds no numbers of its own |
| [fbs-totals-frontier-models.md](fbs-totals-frontier-models.md) | Survey of frontier modeling approaches for FBS totals (+ [`.pdf`](fbs-totals-frontier-models.pdf)) |
| [fbs-totals-system-research-report.md](fbs-totals-system-research-report.md) | Long-form research report on a pregame totals betting system |
| [opponent-adjustment-priors-model-comparison.md](opponent-adjustment-priors-model-comparison.md) | Opponent adjustment (iterative, ridge, crossed random effects, Bayesian hierarchy, Elo), preseason priors and their decay, transfer-era roster features, and a head-to-head comparison of the methods for totals and line movement. Every equation has a where-table and a worked example |
| [research-prompts/fbs-totals/](research-prompts/fbs-totals/) | 15 numbered research prompts plus a README — odds-data audit, market-implied score distributions, price discovery, error anatomy, cold starts, joint spread/total modeling, uncertainty decomposition, abstention, staking, drift monitoring, governance, synthesis |

---

## Strand 3 — Warehouse feature research

**Code-backed results against the warehouse, market-relative.** Each doc pairs with a
reusable script under [`../scripts/`](../scripts/) and reports its own MDE, so a null can be
read as a bound rather than an absence.

| Doc | What it reports |
| --- | --- |
| [kicker-quality-volatility-totals-2026-09-18.md](kicker-quality-volatility-totals-2026-09-18.md) | Do prior-season kicker quality (CFBD PAAR) and kicker volatility (FG overdispersion) move the total past the closing book line? 5,776 games 2018-25, two-way clustered. Nothing bettable: the CI upper bound buys 50.8% over against a 52.38% break-even. Underpowered 3x (mean) and 11x (dispersion) against the mechanical ceiling, so it is a bound, not a zero. PAAR does not persist year to year (r 0.16). **Confirmed 2026-10-01 on REST-backed closes only.** Its 2024-25 medians had mixed in ActionNetwork rows under pre-48ae034c names (the consensus opener as `circa`, AN consensus as `draftkings`). Dropping every GraphQL/AN-only row changes 452 game medians, all 2024-25 (mean shift −0.01 pts), and strips the only price from 16 games, none in the panel. Still 5,776 games: quality +0.233 [−0.132, +0.598] pts/SD, CI upper bound 50.9% over, break-even needs +1.19 pts, volatility on |resid| −0.19 [−0.44, +0.06], Levene p 0.55 — same verdict. Run against the `md:cfb` mirror; with the 09-18 book list the same run reproduces that record's regressions to the printed digits (tercile tables differ by one boundary game) |
| [pff-grade-total-residual-2026-09-22.md](pff-grade-total-residual-2026-09-22.md) | Do entering PFF offense and defense grades still move the total after the book median is subtracted? 4,809 games 2019-25, season-clustered. Thirteen of fourteen intervals cover 0. Run defense vs the open excludes 0; the same grade vs the close does not |
| [pff-grade-residual-tests-2026-09-22.md](pff-grade-residual-tests-2026-09-22.md) | Do those fourteen slopes reject zero? Webb wild cluster bootstrap-t, Holm across 14. Smallest unadjusted p is run defense vs the open, 0.035; Holm moves it to 0.50. Nothing rejects |

| Script | What it does |
| --- | --- |
| [`../scripts/kicker_totals_effect.py`](../scripts/kicker_totals_effect.py) | Builds the prior-season kicker panel, fits both channels with two-way cluster-robust SEs, derives each channel's mechanical ceiling and MDE, and translates the coefficient interval into an over rate against break-even. The price is the median REST-backed close (`_source <> 'gql'`, as in `greenline_clv_all_eras.py`); `--include-gql` adds the GraphQL/AN-only rows as a sensitivity. `--self-check`, `--cache` |
| [`../scripts/pff_residual_screen.py`](../scripts/pff_residual_screen.py) | Scatter and OLS of the open and close totals residuals on seven pre-game PFF grades. Wild cluster bootstrap by season, leave-one-season range, Webb bootstrap-t p-values, Holm across the 14 tests. 2026 plotted, not fit. `--self-check` |

---

## Provenance

This tree predates the 2026-09-16 docs pass with the three Greenline reviews, its scripts,
and `figs/`. That pass moved the strand-2 material in from root `docs/` (it is totals-only
and root `docs/` is for shared docs) and added this index plus [`../CLAUDE.md`](../CLAUDE.md),
which is when `research/totals/` entered root `CLAUDE.md`'s units table. See
[`../../../docs/README.md`](../../../docs/README.md) for that pass's write-up.
