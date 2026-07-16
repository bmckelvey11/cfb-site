# paper_models — Arscott (2022) censoring-bias recreation

Recreation of *"Market efficiency and censoring bias in college football
gambling"* (SSRN 4197428): the over/under line ignores that team scores are
left-censored at 0, so the **over** is underpriced when expected censoring bias
is high.

## Versions

- **[v1/](v1/) — Floor Bias model** — frozen reference. Named for the mechanism:
  scores censored at the **floor** of 0 bias totals up → bet the over. Full
  recreation (Tobit, censoring bias, probit, Kelly), backtested on 13 seasons of
  real CFBD data (2013–2025). Headline: bet the over when expected bias > 1.0 →
  56.6% win over 680 bets. **Do not edit — this is the baseline.**

- **[v2/](v2/)** — tightens two v1 caveats: analytic (OPG) standard errors in
  place of the BFGS approximation, and dropping the favorite/underdog error
  independence assumption. Both proven immaterial on this data; v1 stands.

- **[v3/](v3/)** — tests whether the over-edge is genuinely censoring or just a
  repackaging of "low total / lopsided game." Verdict: `biasTotals` dominates
  the raw total and spread in- and out-of-sample; nothing simpler replaces it.
  v1's single-feature rule is the best line-only strategy.

## Extensions & sibling models

- **[floor_bias_1h/](floor_bias_1h/)** — Floor Bias extended to **first-half**
  totals. Theory predicts a stronger over edge (1H censoring bias ~2.3× larger,
  underdog shutouts 3.9× more common). Ready to run: approximation mode now,
  true backtest the moment real 1H lines are supplied (`--half-lines`). Approx
  results show the edge survives de-biasing the 1H scoring excess.

- **[saturation_bias/](saturation_bias/)** — the ceiling-side mirror: does the
  theory extend to betting the **under** via a soft scoring ceiling? **Negative
  result.** The ceiling isn't identifiable (no pile-up at the top), the fitted
  relationship runs the wrong way, and no OOS under strategy survives. The
  censoring asymmetry is real: floor → over edge, no symmetric under edge.

Run instructions are in each version's README.
