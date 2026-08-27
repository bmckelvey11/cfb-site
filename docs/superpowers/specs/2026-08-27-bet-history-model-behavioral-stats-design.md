# Model-Agreement and Behavioral Stats for Bet History Analysis

Date: 2026-08-27
Status: approved, ready for implementation

## Goal

Extend `docs/bet-history-analysis-2023-2025.md` with two analysis sections that answer questions the existing report cannot: whether the database's own model and team-quality features agree with the bets placed, and whether betting *behavior* (volume, correlation, stake sizing) shows patterns worth correcting.

The existing report covers outcomes (what won, what lost, where the edge is). These sections cover inputs (what the data thought before the bet) and process (how the bets were placed).

## Scope

Operates on the same 488 matched NCAAF core bets already produced by the analysis script. No new data collection, no model refitting.

## Section B — Model and team-quality agreement

### B1. v1 model agreement audit (231 totals bets)

`v1_over_prob` is the repo's vendored recreation of Arscott (2022), "Market efficiency and censoring bias in college football gambling." It fits once on `games.csv` and scores any game from spread and total alone — it never reads final scores at score time. Coverage is 96%.

For each totals bet, compare the bet side to the model's probability:

| Bucket | Condition (P(over) from v1) |
|---|---|
| Strongly agrees | ≥0.55 on an over bet, ≤0.45 on an under bet |
| Leans agree | 0.50–0.55 over, 0.45–0.50 under |
| Leans disagree | 0.45–0.50 over, 0.50–0.55 under |
| Strongly disagrees | ≤0.45 over, ≥0.55 under |

Report record, win %, units, and ROI per bucket.

**Stated limitation, carried into the report body:** v1 was fit on a window that includes the 2023–2025 seasons, so this is a descriptive comparison, not an out-of-sample model bakeoff. Because v1 scores from the market line only, the audit is closer to asking "when I disagreed with the closing line's implied over-rate, was I right?" than to testing an independent forecast. A clean test would require refitting v1 with these seasons excluded; that was deliberately not done, because it churns the repo's cached fit for rigor this descriptive report does not need.

### B2. Pregame win probability vs. bet side (spread and moneyline bets)

`home_pregame_win_prob` has 98.4% coverage. For each side bet, take the bet team's pregame win probability and bucket:

- Under 25% (heavy underdog)
- 25–45%
- 45–55% (coin flip)
- 55–75%
- Over 75% (heavy favorite)

Report record and units per bucket. Answers whether backing market favorites or market underdogs has served better, independent of the spread-size cut already in the report.

### B3. Team-quality gaps (side bets)

Three features, each computed as bet-side value minus opponent value, each bucketed into bet-side-advantage / roughly-even / bet-side-disadvantage, with an explicit **unknown** bucket for missing data:

| Feature | Coverage | Gap definition |
|---|---|---|
| `*_team_talent` | 73–76% | 247-composite team talent |
| `*_recruiting_rank` | 88–91% | recruiting rank (lower is better, so sign is inverted) |
| `*_returning_ppa` | 66–75% | returning production |

The unknown bucket is reported rather than dropped, so coverage gaps stay visible.

## Section A — Betting behavior

### Hard constraint

`history.csv` records **kickoff time only**. There is no bet-placement timestamp. Every volume and tilt question is therefore answerable only at day level (yesterday's settled result → today's volume), never at bet level (this loss → the next bet). The report states this explicitly rather than implying finer resolution than the data supports.

Days are ET kickoff dates, consistent with the `betting day` term already in `CONTEXT.md`.

### A1. Volume distribution and response to prior day

- Bets per betting day: distribution, mean, median, max.
- Mean bets/day following a losing day vs. following a winning day. A meaningful gap suggests volume responds to results.

### A2. Volume vs. outcome

Split betting days into terciles by bet count. Report record, units, and ROI per tercile. Tests whether heavy days grade worse than light ones — the ledger-visible signature of forcing action.

### A3. Same-game doubles

Count games carrying more than one core bet (typically a side plus a total). For each such game, classify the pair as both-win / split / both-lose, and report the distribution against what independence would predict. A both-win/both-lose rate above chance means daily variance is higher than the raw bet count suggests.

### A4. Stake sizing

Observed stakes: 289 bets at 1.1u, 177 at 1.0u, 17 at 0.5u, 6 at 0.7u, 3 at 0.25u, 2 at 2.0u, 1 at 1.5u, 1 at 1.09u.

Group into default (1.0–1.1u), reduced (<1.0u), and elevated (>1.1u). Report record, units, and ROI per group. Answers whether sizing carried information — whether the bets sized up were actually better, and whether the bets sized down were actually worse.

## Deliverables

1. Extend `analyze_bets.py` (scratchpad, one-off) with the computations above.
2. Add both sections to `docs/bet-history-analysis-2023-2025.md`; refresh the Downloads copy.
3. Artifact gains **one** combined section, "How you bet," carrying only the volume-vs-ROI comparison, same-game doubles, and stake-deviation result. Full detail stays in the doc, so the artifact keeps its argument scannable.
4. Add `same-game double`, `stake deviation`, and `v1 agreement` to `CONTEXT.md`.
5. Update the multiple-comparison caveat in the verdicts section: these add roughly 12 comparisons to the existing ~40.
6. Commit and push.

## Non-goals

- Refitting v1 to exclude the bet seasons (rigor not needed for a descriptive section; risks churning the cached fit).
- Venue, turf, elevation, attendance, and broadcast slices (spurious-split generators at this sample size).
- Counterfactual bankroll simulation (Kelly vs. flat) — considered and deferred; it answers a different question than either section here.
