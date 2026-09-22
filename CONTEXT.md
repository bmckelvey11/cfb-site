# CONTEXT

Glossary of canonical terms for CFB System Maker. Add terms as they are resolved; keep implementation details out. Formulas, plugged-in values, and the assumptions behind a number live in [`docs/methods.md`](docs/methods.md); an entry here that says "method:" points there.

## Football identity

- **Team** — a school/program that persists across seasons (Ohio State). Identity only; record, ratings, and play shape do not live here.
- **FBS Team** — a Team whose classification is FBS. The Team-season profile picker is FBS Teams only.
- **Team-season** — that school in one season, built from regular and postseason games only (2020 spring types are out). Record, conference, ratings, and play shape attach here, not to the Team forever.
- **Completed Team-season** — a Team-season with at least one completed game. Distinct from a scheduled-only Team-season (slate exists, no result yet). The profile lands on the newest Completed Team-season; the picker may still open a scheduled-only year.
- **Team-season profile** — a one-subject view of a Team-season (identity, SU record, ATS record, ratings strip, play shape, coach cluster, game log). Complementary to league-wide comparison. Not a betting book.
  _Avoid_: Team summary, Team P&L, Team involvement
- **Ratings strip** — SP+, FPI, and Elo as equal-rank quality numbers for a Team-season. There is no single canonical rating.
  _Avoid_: “the” rating, SP+ as the headline
- **Play shape** — how this Team-season plays: pace, run rate, success. Not the coach’s career label.
- **Coach cluster** — the career playstyle label for a head coach on that Team-season, shown with identity (not with play shape) and always qualified as career, not this year. If two HCs served, both appear, each with a cluster.
  _Avoid_: style (that word meant both)
- **Head coaches** — every HC who served that Team-season, labeled. Not file-order last-write-wins.
- **SU record** — wins and losses on the scoreboard for Team-season games. Ties count for neither side.
- **ATS record** — covers and non-covers against the selected close, equal rank to the SU record on the profile. Pushes and unlined games count for neither side. The selected book is named on each game, not as a season-level house book. Not Team P&L: no units, no “taken” side.
- **Game log** — every Team-season game in date order. SU, ATS, and the selected book sit on the row. Unplayed slate rows appear only on a scheduled-only Team-season; they do not enter SU or ATS.

## Bet-history analysis

- **Team P&L** — net units from bets where that team was _taken_ (spread or moneyline sides only). Totals bets never contribute to Team P&L, because a totals bet backs no team.
- **Team involvement** — any core bet placed on a game that team played in, including totals. Measures where betting attention goes, not who was backed.
- **Core bet** — NCAAF full-game straight bet (spread, total, or moneyline). Excludes first-half/second-half/live/team-total bets, parlays, and teasers.
- **Break-even rate** — the win rate at which a flat bet nets zero at its price: 52.38% at −110, 54.55% at −120. Edge is win rate minus this at the price taken, never at −110 by default. (method: `docs/methods.md`)
- **CLV (closing line value)** — the difference between the number taken and a **predeclared** closing reference (named book or consensus, fixed cutoff, stated de-vig), signed so positive = better than close. A leading indicator of price acquisition, not a score: positive CLV does not establish that the probabilities are calibrated or that the bet had edge. (method: `docs/methods.md`)
- **Model consensus** — screened, equal-weighted average of Prediction Tracker model spreads (E4 input). Not "composite".
- **Book fair** — median closing spread across real sportsbooks (Action Network ids 49 Caesars, 68 DraftKings, 69 FanDuel, 71 BetRivers, 75 BetMGM; names per AN's own book list, corrected 2026-09-08). Not "composite".
- **Cover margin** — bet team's score plus the line taken, minus the opponent's score. Positive = covered by that much; negative = missed by that much. Defined for spread bets only.
- **Hook loss** — a spread bet with cover margin of exactly −0.5: lost by the half point.
- **Key number** — a spread line on or adjacent to 3 or 7 (2.5–3.5, 6.5–7.5), where NFL/CFB final-margin mass concentrates and books shade hardest. In the scoring-distribution work the same phrase is used for a *frequent outcome* rather than a pivotal line — a combined total (55, 41, 44) or an exact margin (3, 7) that stands above its neighbors. Say which sense is meant when both are in play.
- **Betting day** — the ET calendar date of kickoff (a 1am UTC kickoff belongs to the previous ET evening).

## Greenline evaluation

- **Flag** — a game PFF Greenline shows a side on, in any of its three markets. An **under flag** is a total flag on the under; a **positive-edge flag** has a stated edge above zero. Flags are what gets captured and graded; bets are the subset in the ledger. (`research/totals/scripts/greenline_unders.py`)
- **Stated edge** — PFF's `value`: its own win probability minus the 52.38% break-even. PFF's claim, not a measured edge; the graded record says it does not order outcomes. (`archive/docs/greenline-edge-cap-revisit-2026-09-17.md`, superseded by `research/totals/docs/greenline-totals-rule-search-2026-09-22.md`)
  _Avoid_: edge (bare) when PFF's number is meant
- **Line in the capture** — the number PFF showed when the board was captured. Every grade is at that line, never at the close and never at a book's number; repricing is a separate step. (`research/totals/CLAUDE.md`)
- **Pricing law** — PFF's under probability re-evaluated at any line, from its projection and a total-dependent sigma. Used to reprice a flag at a book's number; one point of total is worth roughly four points of win probability at a 50s total. (`research/totals/scripts/match_greenline_books.py`; method: `docs/methods.md`)
- **Repriced edge** — the pricing law at the book's actual line and price, minus that price's break-even. The number a bet decision runs on. (`greenline_unders_<season>_w<week>_<book>.csv`)
- **Walk-away number** — the line at which a flag's repriced edge reaches zero at −110. A full point past it is a pass.
- **Reference price** — Pinnacle. Greenline vs a retail book says what number you can get; Greenline vs Pinnacle says whether the projection disagrees with the sharpest opinion. Pinnacle is never "another book". (`research/totals/scripts/greenline_vs_pinnacle.py`)
- **Pinnacle lean / move / disagree** — three Pinnacle features per flag: **lean** is Pinnacle's fair total minus its line (its juice), **move** is Pinnacle's line minus PFF's shown line (has the market moved first), **disagree** is PFF's projection minus Pinnacle fair (how hard PFF is fading the sharp number). None is a filter yet. (`research/totals/docs/greenline-pinnacle-shade-2026-09-17.md`)
- **MDE** — minimum detectable win rate: the smallest true rate a sample of that size could distinguish from break-even. Stated with every record. A split whose observed rate sits under its own MDE is **below floor**: not evidence either way. (method: `docs/methods.md`)
- **History unders** — the 2023–25 full-game unders in the book export. Treated as a Greenline stand-in from 2026-09-17 until `pool_totals_record.overlap()` (2026-09-22) measured the overlap directly and found it false on 3 of 12 checkable days — personal bets that took the side Greenline flagged *against*. Now reported only as a **comparison stratum** beside the Greenline pool, with its own interval, never pooled into a Greenline record or a Greenline filter test. (`research/totals/docs/greenline-totals-pooled-2026-09-22.md`)
  _Avoid_: baseline, out-of-sample, Greenline stand-in (for history)
- **Pre-registered filter** — a pregame split fixed in the script's docstring before it runs, tested on the 270 Greenline-only graded unders (all three eras, personal history excluded — see History unders), stratified by era with Cochran-Mantel-Haenszel and Holm-corrected across the set. The six situational ones are line move, wind, pace, big favorite, night, short rest. Only the **big-favorite filter** (drop unders where |spread| exceeds 13.5) is applied to a live list, on Holm p 0.906: a choice, not a finding. (`research/totals/docs/greenline-under-filters-2026-09-22.md`)
- **Edge window** — the 2–4% cut on stated edge carried from week 2 into week 3. Dropped 2026-09-17: the bucket it rested on is nine games and the window's floor sits below break-even. (`archive/docs/greenline-edge-cap-revisit-2026-09-17.md`, superseded by `research/totals/docs/greenline-totals-rule-search-2026-09-22.md`)
- **Band** — the market-total ranges (<45, 45–49.5, 50–54.5, 55–59.5, 60–64.5, 65+) the under list is annotated by. Band ordering was withdrawn 2026-09-17: not significant, out-of-sample AUC 0.47. Context on the list, never a rule. (`archive/docs/greenline-band-significance-2026-09-17.md`, superseded by `research/totals/docs/greenline-totals-rule-search-2026-09-22.md`)
- **Selection-on-selection** — a split scored on the same sample that chose it (the 55–59.5 band was picked from the 2023–25 history, then reported pooled with it). Such a record is not evidence; the honest tests are the best-of-k correction and the out-of-sample ordering test. (method: `docs/methods.md`)
- **Ledger** — `greenline_bet_log.csv`: which flags were actually placed, seeded from every capture. `bet` is three-valued: `y`, `n`, or blank, and **blank means not yet marked**, not "no". Coverage refuses to compute on a week with blanks. A plan is not a mark; only a placed bet is `y`. (`research/bankroll/scripts/greenline_bet_log.py`)
- **Control** — the flags not bet in a week. Every flag is graded Monday whether or not it was placed, so the cut flags test whatever rule cut them. A selection rule with no control is untestable. (`archive/docs/greenline-totals-season-2026-09-16.md`; current status in `research/totals/docs/greenline-findings.md`)

## Bankroll

- **Seed bankroll** — money given to fund a betting bankroll with nothing owed back. A gift, not an investment, loan, or security. Profit and bankroll stay in the operation.
  _Avoid_: investment, seed money, stake (that word means bet size)
- **Leg** — one strategy bet from a shared bankroll. Two legs today: over-zero OVERs and Greenline totals. A leg has its own record, price, and volume.
- **Coverage** — the fraction of a leg's available flags that actually get bet. Historical Greenline coverage is ~13%. Coverage above that is conditional: the picked-flag record says nothing about the flags passed on.
- **Prior** — the graded record a leg's win rate is drawn from. The Greenline **planning prior** is the half-pooled record (κ = 0.5: the 2026 flags at full weight, the 2023–25 history unders at half), mean 56.1%. `n49` (κ = 0) and `pooled` (κ = 1) are the **bracket**, reported alongside and never the planning number. (method: `docs/methods.md`)
- **Growth vehicle** — the bankroll's purpose: compounded across seasons and strategies (golf to be added once graded), not defended over one stretch. Sizing is fractional Kelly off the planning prior; the per-season drawdown cap is a constraint, not the objective.
- **Bust** — a simulated path whose running bankroll passes through zero mid-season. Reported as a rate on every scenario; percentiles on a busting row are unreachable.
- **Conflict** — the same game flagged on opposite sides by two legs. Rule: over-zero takes the game, Greenline skips it (flipped 2026-09-17; was Greenline first).
- **Unit** — one flat bet as a fraction of the bankroll. Re-sized each Monday off the running bankroll (`resize_weekly`, the default since 2026-09-17), flat within the week because Saturday kickoffs are simultaneous. `--flat-stakes` sizes off the starting bankroll for the whole season instead. Today 1% for both legs. (`research/bankroll/scripts/mc_combined_totals.py`)
  _Avoid_: stake (ambiguous between the bet and the fraction)
- **Unit rule** — the Greenline unit is the smaller of quarter Kelly off the planning prior and the largest unit that passes the drawdown cap. Today 1%. (method: `docs/methods.md`)
- **Quarter Kelly** — a quarter of the Kelly fraction, shrunk for simultaneous bets; the growth-vs-drawdown dial. 1.31% off the planning prior. (method: `docs/methods.md`)
- **Drawdown cap** — the per-season constraint on the unit: P(ending down 25% or more) ≤ 3% and zero busts under the planning prior. A constraint, not the objective. (method: `docs/methods.md`)
- **Downside ratio** — median gain over the gap between the median and the 5th percentile; reported beside the median so a fatter left tail is visible. (method: `docs/methods.md`)
- **Path measures** — max drawdown, weeks under water, ES5. Reported because the fan chart of endings hides what a season feels like on the way. (method: `docs/methods.md`)
- **Planned volume** — Greenline unders per week drawn uniform on 6–12, capped by the week's FBS-vs-FBS slate (`GL_FLAGS_BY_WEEK`; the 2025 slate stands in for later seasons). Greenline flags every game, so volume is a bankroll choice, not a supply limit. About 107 unders over the rest of 2026. (`mc_combined_totals.py`)
- **Haircut** — the over-zero selection correction applied to the walk-forward record before it enters the projection, because the guide's live picks are a selected subset. Planning rate 58.2% less 0.063. (method: `docs/methods.md`)
- **Same-week shock** — one scoring-environment draw per week shared by every bet that Saturday; over-zero OVERs and Greenline UNDERs are pushed opposite ways by it. A model-or-market failure that hurts both legs together is not modelled. (method: `docs/methods.md`)
- **Stress scenario** — a projection run with one or more skeptical knobs on (over-zero centre and spread, κ, marginal-bet penalty, ρ). The decision is the unit that passes the cap across all of them, not any one scenario as the true model. (method: `docs/methods.md`)
- **Exposure** — total stake on one weekend as a share of the bankroll. Twelve unders and four overs at 1% is 16%; the over-zero guide's own caution is 8–10% a slate. The projection assumes the higher figure.
- **Bet to** — over-zero's walk-away number: the highest total at which an OVER still qualifies. A line above it is a pass; `betTo` in the board JSON. (`models/over_zero/docs/bet-to-2026-09-11.md`)
- **Price rule** — the projection prices Greenline at −110 and over-zero at −120; a bet at a worse price than its leg's assumption is a pass, and the week's list shops the best book first. (`research/bankroll/docs/seed-bankroll-proposal-2026-09-21.md`)

## Scoring distribution

- **Minute of quarter** — 1 through 15, where minute 1 is 15:00–14:01 on the game clock. Scoring-by-minute tables are indexed this way, not by game minute 1–60.
- **Game-minute cell** — the unit a conditional scoring rate is measured per: one (game, quarter, minute). Every game contributes all 60 of its regulation minutes, including the roughly one third that contain no snap, and each cell carries one bucket label read at its first play. Points per game-minute cell is comparable across buckets and against the unconditional 0.942. (method: `docs/methods.md`)
  _Avoid_: exposure (that word means weekend stake)
- **Share of own points** — a bucket's points in a quarter or half over all its own points, pooled across the bucket rather than averaged game by game. Separates _where_ a team scores from _how much_. (method: `docs/methods.md`)
- **Front-loaded / back-loaded** — a team type whose first-half share sits above / below the 52.06% all-team figure. Shape only: a back-loaded weak offense still scores fewer fourth-quarter points than a front-loaded strong one, because the share is of a smaller pile.
- **Exceedance** — the share of games finishing above a line; a scoring distribution read from the tail instead of the peak. Realized scores only, never an over/under hit rate against a market.
- **Neighbor lift** — how far an exact total or margin stands above the same-parity values around it. Separates a real spike from a bin that is merely near the middle of the bell. (method: `docs/methods.md`)
- **Prior-season bucket** — a team-type label (tempo, SP+ offense quartile) read from season − 1, so the label is never built from the games being measured, with quartile cuts recomputed each season. Stale by construction — a team that changed coordinator carries last year's label — which biases every effect toward zero. (method: `docs/methods.md`)

## Model and system evaluation

Governed by [`docs/model-evaluation-standard.md`](docs/model-evaluation-standard.md).

- **Model** vs **system** — a model outputs probabilities, spreads, totals or prices. A system adds the bet-selection rule, timing, book availability, staking and execution. The distinction decides what a result is evidence *about*: a model can forecast well and lose money, and a profitable backtest can come from staking, unavailable prices or search, with the model contributing nothing.
- **Proper scoring rule** — a forecast score whose expected value is best when you report your true probability, so it cannot be gamed by shading. Brier and log loss are the binary pair used here, RPS for three-way outcomes, CRPS for a full predictive distribution. (method: `docs/methods.md`)
- **Calibration** — whether a stated probability matches the observed frequency. Distinct from **resolution**, the ability to separate games into genuinely different risk groups. A forecast can be perfectly calibrated and carry no information; both are reported, never one as a proxy for the other. (method: `docs/methods.md`)
- **Market-relative skill** — a proper score measured against the de-vigged market price **at the same timestamp**, not against a base rate and not against a later close. The bar that matters: beating a coin flip is not an achievement, and beating a price that knew more than you did is not a measurement. (method: `docs/methods.md`)
- **Incremental information** — whether a model contributes anything the market price does not already carry, tested by conditioning on the market rather than by CLV. The claim CLV is routinely mistaken for. (method: `docs/methods.md`)
- **Turnover ROI** — net profit over total staked, net of every cost that scales with betting. Not bankroll return and not log growth; the three answer different questions and are never reported under one label. (method: `docs/methods.md`)
- **Hard gate** — a defect that makes a result **invalid** rather than merely weaker, whatever the ROI: lookahead or leakage, prices that cannot be reconstructed at decision time, incomplete bet or trial logging, a threshold chosen on the test set, materially misstated costs, or no chronological out-of-sample evaluation. Gates are checked before the score is read, not weighed against it.
- **Trial ledger** — the append-only record of every materially distinct rule, feature set, threshold, model and staking variant tested. Without the count, the winner's p-value, ROI and Sharpe are all optimistic by an unknown amount, and DSR/PBO cannot be computed at all. Recording obligation, not paperwork. (method: `docs/methods.md`)
- **Research-only** — a system that passes the gates but is not deployable: negative market-relative skill, an ROI interval too wide to act on, profit carried by a handful of outcomes, or performance that collapses under nearby parameters or modest slippage. A status, not a failure — distinct from **invalid**, which is what a hard gate produces.
- **Execution** — whether the quoted price was actually available, at the needed stake, when the decision fired: fill rate, slippage, quote age, limits, book concentration. Scored as its own pillar, because a backtest that assumes the shown price is a backtest of a market that did not exist.

## Warehouse layers

- **Pair** — one concept arriving from both CFBD APIs as two staging tables. Both live in `stg` since the 2026-09-10 collapse (ADR-0003); the GraphQL side carries a `_gql` suffix only where it would collide (`calendar_gql`, `draft_picks_gql`, `predicted_points_gql`). Different names and different column sets. A pair is two sources of the same subject, **not** a duplicate; measurement decides whether either side is redundant.
- **Canonical source** — for a given pair, the side designated authoritative after measuring column containment and coverage. Established by measurement per concept, never by row count alone.
- **Scaffolding column** — `season`, `week`, or `season_type` bound from a dump's filename rather than its payload. Where the filename does not carry one it arrives NULL and stays NULL; these are pruned at load. Distinct from a payload column that happens to be empty, which is a finding and is never auto-dropped.
- **Relation-only entity** — a GraphQL root whose identity lives in a to-one relation rather than in its own scalars. It must be nest-selected, or its dump cannot be joined to anything and its sort is not a total order.
- **Merged table** — a `core` table conforming both sides of a pair, carrying every populated column from each and a `_provenance` marker. Merged tables live in `core`; the `stg` sources they were built from stay in place.
