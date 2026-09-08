# Spread research — session guide, 2026-09-02

> **Dated record.** Written on 2026-09-02 and left as written. Since then: data paths under
> `raw/` moved to `ingest/` (`e2e9e5d`, except `raw/actionnetwork/`); the margin-era documents
> it cites moved to `archive/spread-margin-era/`; the §5.5 numbers predate decontamination
> (`line-movement-results.md` § A3), where the ridge's R² 0.25 falls to 0.16 and E4's 0.17 to
> 0.15; the scheduled tasks' health claims in §7 are superseded by `docs/line-timing-collector.md`.
> Read `README.md` for the current state.

A complete account of one working session: what was asked, what was built, which models and
methods were used, what the numbers say, where every artifact lives, and how to pick it up.
Written for someone who did not watch it happen. Every figure below is reproducible from a
named script in `research/spread/scripts/`; every design decision was pre-registered before
its run unless marked *post hoc*.

---

## 1. The question, and how it changed

The session opened with a handoff document claiming the spread work was closed: a 154-model
Prediction Tracker panel cannot beat the closing spread. The user's stated goal was **a
composite point spread from all the models that gains an edge over the books.**

Over the session the goal sharpened three times, each time because a measurement forced it:

| stage | question | answer |
|---|---|---|
| 1 | Can the model consensus out-forecast the closing line? | No. Closed harder than the handoff said (§5.1). |
| 2 | Can the book fair beat any one book? | Yes, mechanically: +1.26 win-rate points per bet by taking the best number (§5.3). |
| 3 | Can the model consensus forecast **where the line goes**, so a bet placed early has closing line value? | Yes, strongly, at the opener (§5.5). Whether the opener is reachable is the open question. |

The last framing is the user's thesis in their own words: *if I can get points early on the
closing line, the obvious closing line value is very valuable.* Everything from §5.4 onward
serves that.

---

## 2. Timeline of work (commits on `master`)

| commit | what |
|---|---|
| `0d5383f` | Review of the handoff. New check: raw unshrunk model median vs close, 17,166 games. |
| `7aac642` | Collector now runs the predictor whenever a new PT snapshot lands. |
| `4437d67` | Week-1 2026 timing: how much of the open→close move is left on Monday (none). |
| `57637a4` | Pre-registration: book fair and line-shopping backtest. |
| `61d746f` | Line-shopping backtest script and results. |
| `0d3da6c` | Review of the book fair; how predictions should combine; juice measured. |
| `c9bbab5` | Pre-registration: retarget the panel at line movement. |
| `313e3cd` | Line-movement sweep (version A) and results. |
| `63f26dc` | Prior nulls rescoped to the margin target; amendment A2 pre-registered. |
| `95622ec` | "Composite" retired: model consensus vs book fair, defined in `CONTEXT.md`. |
| (this) | Amendment A2: E8–E13 and a wide ridge grid on the movement target. |

Uncommitted by design: data outputs under `data/processed/`, the weekly slate, memory notes.
Left untouched: `models/over_zero/docs/figs/bias_bins.png`, dirty before the session began.

---

## 3. Data

### 3.1 Prediction Tracker archive
`{CFB_DATA_ROOT}/raw/prediction_tracker_lines.csv`, built by `build_prediction_tracker.py`.
17,731 CFBD-matched games 2001–2025, 154 model columns, plus `line` (PT's recorded market
line, treated as the close) and `lineopen`. Documented in `prediction-tracker.md`.

**Sign convention, the single most dangerous fact in this tree.** PT publishes spreads
positive = home favored. The build script negates every `line*` column except `linestd`, so
the *archive* runs negative = home favored (repo convention), and "margin space" in the
sweep code is `mkt = -spread`. Live snapshots are raw PT and must be flipped before touching
any fitted code (`predict_upcoming.to_archive_convention`). One double-negation slipped into
the week-2 slate draft and was caught by reading the numbers; check signs against a game you
know.

**Two columns are not models.** `lineca` reproduces the closing line exactly on 65.6% of its
games; `linemidweek` on 43.3%. Both are excluded everywhere. When the *target* is the close
(§4.6), leaving `lineca` in would be leakage of the target into the regressors.

### 3.2 Prediction Tracker live snapshots
`{CFB_DATA_ROOT}/raw/pt_snapshots/ncaapredictions_<UTC>.csv` with a `.meta.json` sidecar.
Captured every 6 hours by Windows task `CFB-PT-Snapshot`, content-hashed so unchanged files
are not stored. Four exist: 08-29, 08-30, 08-31 (Monday 15:05 ET, 44 games), 09-01 (Tuesday
18:30 ET, 44 games). This is the only asset in the tree that appreciates: it carries the
publication timestamp the archive lacks.

### 3.3 Action Network
- **Scoreboard markets** (`stg.actionnetwork_scoreboard__markets__markets_event_spread`):
  per-book full-game spreads. For completed games this is taken as the closing market
  (assumption, verifiable from 3.3b once 2026 has closes). Coverage: 2024 (899 games), 2025
  (892), 2026 in progress. Scraped 2026-07-31.
- **Event history** (`raw/actionnetwork/history_event_<id>.json`): timestamped ticks per book
  per market. 106 files, all 2026 week 1 plus 7 mid-September look-aheads. Pulled Mondays by
  task `CFB-AN-History`; the endpoint replays the full path, so late pulls lose nothing.
- **Live scoreboard** (fetched ad hoc for the slate): `AN_SCOREBOARD?season=&week=&seasonType=reg`.
  Note AN's "week 1" spans Aug 29 – Sep 7; PT's week 2 games (Sep 5–6) are AN week 1.

**Book identities, established from data.** The loader's `_AN_PROVIDER_NAMES` labels book 30
"Circa" and 15 "DraftKings". Both wrong:

| id | is | evidence |
|---|---|---|
| 15 | consensus | median 0.00 from the other books' median |
| 30 | **consensus opener** | equals book 15's *first* tick on 97.2% of 106 timestamped games; median 2.0 off the close, 35% of games 3+ off; no `line_status` field |
| 49 Pinnacle, 68 FanDuel, 69 BetMGM, 71 Caesars, 75 Bet365 | real books | full or partial coverage |

The handoff's earlier "book 30 is stale" was this: the opener mistaken for a slow book. A
background task to fix the loader mapping was spawned and is running in a separate session.
Book 71 (Caesars) mis-posts: numbers 10–25 points from every other book at normal odds.

> **Correction 2026-09-08.** The real-book names in the table above were guesses and are
> wrong. Action Network's `/web/v1/books` says 49 = Caesars, 68 = DraftKings, 69 = FanDuel,
> 71 = BetRivers, 75 = BetMGM. The mis-posting book 71 is BetRivers. The loader and
> `weekly_slate.py` were corrected the same day.

### 3.4 Warehouse
`cfb.duckdb` is source of truth; `CFB_DATA_ROOT=C:\Users\mckel\dev\cfb\data`. Scores for
Action Network games come from the same rows (no join needed). PT games carry CFBD `game_id`.

---

## 4. Models and estimators

All combination work is in **market-residual form**: anchor `m_t` (a line), regressors
`d_it = f_it − m_t`, forecast `ŷ_t = m_t + ĝ_t`. Zero correction equals the market exactly.

| id | estimator | free parameters | role |
|---|---|---|---|
| R0 | `α + β·m` (recalibrated market) | 2 | reference; recalibration is worth nothing (+0.06 MSE) |
| **E4** | `R0 + γ·mean(d_i over top-20 by prior skill)` | 1 more (γ) | **pre-registered primary**; the served model |
| E6 | ridge on all active `d_i`, centred at 0 | λ ∈ {10,100,1000,10⁴} | generalized shrinkage to market |
| E7 | E4 with k chosen by 1-SE rule | k | is k identifiable? (no) |
| E8 | Stock–Watson shrinkage, scalar ψ toward market | ψ | kept none of the correction |
| E9 | principal components of `d_i` | q | 1 component chosen |
| E10 | market-anchored peLASSO: select by LASSO, equal-weight survivors, one γ | λ | Diebold–Shin, retargeted |
| E11 | trimmed residual consensus | τ | robust average |
| E12 | combination elastic net | (λ, α) | zeroed everything |
| E13 | online Hedge over `d_i` with a zero expert | η | ran to the floor |
| E14 | screened complete subset regression, top 10, k ∈ {1,2,3} | k | best exploratory method; selection-conditional |

Plus, this session:

- **Raw model median**: per-season median of every model with ≥95% within-season coverage, no
  fitting. Used to test whether *unshrunk* disagreement with the close carries information.
- **Book fair**: `fair = median of closing home spread over real books`, ≥2 books.
- **Movement retarget**: the same E4/E6/E7/E14 with target `y = close` (margin space) and
  anchor `m = open`. `prior_skill` then ranks models by error against the *close*, i.e. by
  movement skill, automatically.

Screening skill is prior-season ΔMSE against the benchmark, computed only over seasons a model
was active (the whole-history version was a tenure test that excluded the best forecasters).

---

## 5. Methods and findings

### 5.1 The model consensus cannot out-forecast the close — and the reason given was wrong

The handoff argued a threshold rule cannot work because 89% of games sit within a point of the
close. True of E4, whose γ ≈ 0.07 makes it the close plus 7% of a deviation. Not true of the
panel. The raw model median (≈39 models per season) disagrees with the close by a **median of 2.0
points**, 99th percentile 8.9, and:

| \|raw model median − close\| | n | ATS vs close | SE, 25 seasons |
|---|---|---|---|
| [0,1) | 4,051 | 50.0% | 0.9% |
| [1,2) | 4,160 | 49.4% | 0.8% |
| [2,3) | 3,260 | 50.1% | 1.0% |
| [3,5) | 3,747 | 49.8% | 0.8% |
| [5,∞) | 1,948 | **49.0%** | 1.5% |
| all | 17,166 | 49.7% | |

The panel disagrees often and by a lot, and when it does the close is right. That is a
stronger closure than "no tail". *Post hoc, one run, buckets copied from the ATS pre-registration.*

### 5.2 Timing — how much of the move is left when PT publishes

Week 1 of 2026, 7 books, 616 book-games with timestamped ticks, Monday price at 19:05Z:

| | |
|---|---|
| open→close move, median | 1.0 point; 25% never moved |
| fraction of move done by Monday, median | **1.00**; 98% of book-games ≥ 1.0 |
| remaining move Monday→close | median **0.0**, mean 0.06; 5% had a point left, none had two |
| opener timestamps | 2 Apr – 28 Aug, median 8 Jun |

Week-1 openers are spring look-ahead lines. Nothing left by game week. In-season weeks (Sunday
openers, Monday snapshot ~18h later) are unmeasured; AN had posted history for only 7 of 86
week-2 games by Wednesday, so that waits for the Monday backfills.

Monday snapshot (44 games): line already moved ≥1 from PT's opener on 61%; E4 within a point of
Monday's line on every game. Tuesday: four games ≥1, max 1.39. PT typo: UCLA–Cal `lineopen = −55`.

### 5.3 Book fair and line shopping (pre-registered `prereg-line-shopping.md`)

Design: fair = median of real books; every game contributes **both sides**; each side graded at
its best available number and at fair; pushes 0.5; season×week clusters (29); t(G−1) CI.
1,787 games, 3,574 game-sides, 2024–25.

| measure | value |
|---|---|
| range across real books, median / mean | 0.50 / 0.80 |
| games with range ≥ 1 | 38.1% (expected 15–25%) |
| range ≥ 3 | 2.9%, 51 games — Caesars mis-posts explain the extremes |
| **win(best) − win(fair), all sides** | **+1.26 [+0.94, +1.58] win-rate pts** |
| points gained, mean | 0.40 |
| win-rate pts per point of spread | 3.2 |
| gain > 0 sides not crossing 3 or 7 | +1.88 [+1.22, +2.54] |
| gain > 0 sides **crossing 3 or 7** | **+4.65 [+2.40, +6.91]** |
| gain ≥ 1 (14% of sides): at fair | 49.0% [44.7, 53.4] — the off-market book's direction is uninformative |
| gain ≥ 1: at best, pushes dropped | 52.8% [48.7, 56.9] — includes break-even |
| gain ≥ 0.5 (47%): at best | 53.65% [51.9, 55.4], p=0.16 vs 52.38 |

Sensitivity excluding the 51 tail games: +1.15. Scorecard: 4 of 9 expectations wrong, all in
the direction of more dispersion than assumed.

**Juice** (*post hoc*): on gain ≥ 0.5 sides the best number is −115 or worse 26% of the time; the
break-even penalty vs the median book is ≥1 win-rate point on 18% and erases the point gain on
12%. Second-order, but belongs in a live rule.

Reading: shopping is worth about half the gap between a coin flip and break-even, free. It does
not make a positive-EV bet from nothing.

### 5.4 The methods memo the user supplied

A literature memo ranked market-anchored shrinkage, screened residual consensus, residual PCs,
market-anchored peLASSO, CSR-after-screening, trimmed means, Hedge/BOA, and Harvey–Newbold.
Every ranked method maps to E4–E14 and had already been run against the close; every one
tripped the memo's own stopping rules (grid edge, collapse to zero, <60% seasons). Not run and
not worth running against the close: BOA, scalar online γ (recency screen is this by proxy),
EB-shrunk skill ranks, winsorized/median-of-means, group ridge, encompassing selection. The
memo's premise "your current top-20 raw consensus" described E4, which is already the residual
form. Its library *does* earn its keep against the early line — §5.5.

### 5.5 Retargeting at line movement (pre-registered `prereg-line-movement.md`, version A)

Same machinery, target = close, anchor = open, `lineca`/`linemidweek` removed. 16,999 games with
both lines; common walk-forward support 14,068, 2006–2025. sd(close−open) = 2.48 vs
sd(margin−close) = 15.6: **43× less noise in the target**, which is why weight estimation stops
failing.

| method | R² of move | ΔMSE vs R0 | p | Holm | seasons beating R0 | direction right (moved, \|pred\|≥1) |
|---|---|---|---|---|---|---|
| E4 | 0.170 | −1.04 [−1.82, −0.26] | 0.006 | — | 74% | 70.6% (n 2,577) |
| **E6 ridge** | **0.248** | **−1.52** [−2.46, −0.60] | <0.001 | <0.001 | 84% | 77.2% (n 4,888) |
| E7 | 0.147 | −0.90 | 0.011 | 0.011 | 74% | 69.3% |
| E14 | 0.136 | −0.83 | 0.001 | 0.001 | 95% | 78.2% (n 766) |

E4's γ on movement: **median 0.30, range 0.19–0.33, positive 20 of 20 seasons** (vs 0.07 when
the target was the margin). The market moves ~30% of the way toward the screened consensus
between open and close, every season.

**Closing line value at the opener** (bet the method's side at the opening number):

| rule | bets | CLV, pts | beat close | ATS at the opener |
|---|---|---|---|---|
| E4, pred move ≥ 1 | 2,914 | +1.32 [+0.86, +1.79] | 62.4% | 52.5% [49.6, 55.2] |
| E4, pred move ≥ 2 | 356 | +3.89 [+2.10, +5.76] | 75.8% | 64.4% [54.6, 74.3] |
| **E6, pred move ≥ 2** | **1,567** | **+2.33 [+1.77, +2.94]** | **77.0%** | **57.8% [54.7, 60.6]** |

Break-even needs ~0.75 points of CLV at 3.2 win-rate points per point. These rules deliver 3–5×
that, and the ATS column confirms it cashes (57.8% ≈ +10% ROI at −110).

**Decay.** The registered re-selected curve dipped *below* 50% at intermediate entry prices.
That is an artifact: with γ≈0.3 the predictor understates large moves, so after a partial move
the games still showing a gap are ones where the market moved further than predicted, and the
rule fades the steam. The honest curve is the fixed-set version (*post hoc, no free parameter*):

| fixed bets chosen at open, graded at entry f | 0 | 0.25 | 0.5 | 0.75 | 1 (close) |
|---|---|---|---|---|---|
| E4 ≥ 1 | 52.5% | 51.4% | 50.5% | 49.5% | 48.5% |
| E4 ≥ 2 | 64.4% | 62.4% | 60.7% | 57.8% | 55.2% |

Good at the open, a coin flip at the close. The panel forecasts the line, not the game.

E6 chose λ = 10⁴ (grid edge) in 19 of 20 seasons; the grid was scaled for a target six times
noisier, so a wider grid is a pre-registered amendment for later, not a reason to look again.

### 5.6 This week's slate (PT week 2, Sep 3–7)

Movement consensus vs Tuesday's line, largest gaps: JMU (models −14.4 vs −6.5), Indiana (−33.6
vs −40, lean North Texas), Tulsa (OSU −8 vs −13.5, lean Tulsa), Rutgers, Alabama (lean ECU),
Penn State, USF, Nebraska (lean Ohio). Only JMU clears the archive rule's 2-point predicted-move
bar *if Wednesday were the opener*; it is not, and that timing is unvalidated. Live Tuesday→
Wednesday check: 13 lines moved, 54% toward consensus, correlation +0.05.

Shopping: median range 1.0 across the five books, 21 of 41 games with a point of dispersion.
Key-number half-points: Wyoming +3.5 (Caesars), Florida State +3.5 (BetMGM), SMU −2.5
(Bet365). Full-point gaps mostly at Bet365 on dogs (Tulane +9.5, Central Michigan +11.5, Tulsa
+14.5). Saved to `data/processed/weekly_slate_2026w2.csv`.

---

## 6. Inference conventions (used everywhere)

- **Walk-forward by season**: weights for season t see only seasons < t. Burn-in through 2005.
- **Hyperparameters**: 1-SE rule on the last three training seasons; endpoint hits reported,
  never widened inside a registered run.
- **Nesting**: Frisch–Waugh anchoring so every method reproduces R0 when its correction is zero.
- **Standard errors**: wild cluster bootstrap by season (B = 2,000, p floor 1/2,000) for the
  panel; season×week clusters with t(G−1) for the two-season book data.
- **Multiplicity**: Holm within an exploratory family; Andrews–Kitagawa–McCloskey bound for the
  selected winner; expectations written down before each run so a confirmation cannot be
  reported as a discovery.
- **Two tests that disagree are the finding**: Clark–West (is there signal in population?) vs
  paired ΔMSE (does it survive estimation?). Against the close: yes and no. Against movement: yes
  and yes.

---

## 7. Where everything lives

**Docs** (`research/spread/docs/`)

| file | what |
|---|---|
| `review-2026-09-02-composite-spread.md` | handoff review, raw-model-median tail test, §6 timing addendum |
| `prereg-line-shopping.md` → `line-shopping-results.md` | book fair and shopping |
| `combining-predictions.md` | four defects of the fair value; how model and book numbers combine; bet rule |
| `prereg-line-movement.md` → `line-movement-results.md` | movement retarget, versions A and B |
| `prediction-tracker-findings.md` | the prior sweep's consolidated record (unchanged) |
| this file | session guide |

**Scripts** (`research/spread/scripts/`)

| file | run |
|---|---|
| `collect_line_timing.py snapshot` | PT snapshot; now also runs the predictor on a new file |
| `collect_line_timing.py history --season 2026 --weeks 1-16` | AN tick histories |
| `predict_upcoming.py [--snapshot path]` | E4/E14 vs the line at capture; appends the forward log |
| `eval_line_shopping.py` | §5.3 |
| `eval_line_movement.py` | §5.5 (≈10 min, 2,000 draws) |
| `weekly_slate.py` | every movement model on the latest snapshot + live book fair and best numbers; appends `movement_forward_log.csv` (version B data) |

**Data outputs** (`{CFB_DATA_ROOT}/processed/`): `pt_upcoming_predictions.csv` (forward log,
105 rows, four snapshots), `line_shopping_sides.csv`, `line_shopping.json`,
`pt_movement_preds.csv`, `pt_movement.json`, `weekly_slate_2026w2.csv`.

**Scheduled tasks**: `CFB-PT-Snapshot` every 6h (irreplaceable if missed), `CFB-AN-History`
Mondays 09:00 (repairable). Both returned `Last Result 0` on 2026-09-02. They run only while
the user is logged on.

**Memory**: `~/.claude/projects/C--Users-mckel-dev-cfb/memory/spread-composite-goal-closed.md`.

**Spawned task**: fix `_AN_PROVIDER_NAMES` in `cfb_system_maker/duckdb_load.py` (book 30 is the
opener, 15 the consensus) — running in another session.

---

## 8. Pitfalls found this session

1. Sign convention flips silently; the slate draft double-negated once.
2. `lineca` is the close; excluding it is mandatory when the close is the target.
3. Book 30 is the opener, not a stale book. Book 15 is the consensus. Neither is a sportsbook.
4. Caesars (71) mis-posts by 10–25 points at normal odds; an outlier guard (>2.5 from the
   other books' median) is required before any live rule.
5. PT's `lineopen` is a look-ahead number posted months early for early-season games; "edge vs
   open" on the forward log is not an available edge. UCLA–Cal carries a −55 typo.
6. Action Network week numbers do not match PT's; AN week 1 runs to Sep 7.
7. Re-selecting bets at a partially-moved price with a shrunk predictor fades steam and loses;
   decay curves must use a fixed bet set.
8. Hyperparameter grids scaled for a 15-point target are wrong for a 2.5-point target.
9. The loader's book-name map is wrong and downstream `game_lines` rows may be mislabelled.

---

## 9. What is established, what is not, what to do

**Established.** The model consensus cannot beat the closing spread as a forecast of the game
(tight null, three independent angles). Taking the best book number is worth +1.26 win-rate
points per bet, +4.65 across 3 and 7, and the outlier book's direction carries no information.
The panel predicts line movement from the opener with γ ≈ 0.30, stable across 20 seasons, and a
bet at the opener on the ridge rule earns +2.3 points of CLV and covers 57.8%.

**Not established.** That the opener, or anything near it, is a price the user can get. Week 1
said Monday had none of the move left; in-season weeks are unmeasured.

**Decision tree.**
1. **Version B** (Monday anchor, from snapshots + AN closes): first read at ~300 graded games
   (~week 8). Slope of `close − line_Monday` on the correction. Under 0.1 with a tight CI:
   PT-timed spread work is finished; keep shopping. Around 0.25: marginal (~0.6 pts CLV at the
   ridge rule). 0.5 or more: bettable at Monday's number.
2. **Get earlier than PT**: the leading movement forecasters (rank by E6 loadings or prior
   movement skill) publish before PT compiles them. Pulling them Sunday night when in-season
   openers post is a scraping task and the version of this that could pay.
3. **Shopping script**: add the outlier guard and price-adjusted value as a pre-registered
   amendment; verify snapshot = close on 2026 histories after ~4 weeks.
4. **Scope of the nulls.** Every "closed" verdict in this tree is about forecasting the *margin*
   against the *closing* line. It is not a gate against trying a method on the movement target
   (§5.5), where the same estimators worked. Pre-register generously and run them; the user's
   instruction on 2026-09-02 was explicit that prior conclusions targeted a different question.
5. **Totals** remain where the user's own bet history shows edge (58% on 231 bets, CLV +0.45);
   the spread tree should not absorb that effort.

---

## 10. Glossary

- **ATS** — against the spread; a side "covers" if margin + spread > 0 from its perspective.
- **CLV** — closing line value; points the line moved in the bet's favour after it was placed.
  Beating the close consistently is the strongest evidence of edge; one point ≈ 3.2 win-rate
  points on this feed, more across 3 and 7.
- **Break-even** — 52.38% at −110.
- **Anchor / residual form** — forecast = market + correction; regressors are model deviations
  from the market, so zero correction is the market.
- **γ (gamma)** — the scalar weight on the screened consensus deviation; 0.07 against the close
  as margin benchmark, 0.30 against the close as movement target.
- **Book fair** — median closing home spread across real books.
- **Model consensus** — screened, equal-weighted average of Prediction Tracker model spreads; the
  input to E4. "Composite" is retired: it was used for both of these and confused the reader.
- **Gain** — points by which a side's best available number beats fair.
- **Key numbers** — 3 and 7, the most common CFB margins; a half-point across them is worth
  ~2.5× a half-point elsewhere.
- **1-SE rule** — pick the most conservative hyperparameter whose validation error is within one
  standard error of the best.
- **Wild cluster bootstrap** — resampling residual signs by cluster (season) to get standard
  errors that respect within-season dependence.
