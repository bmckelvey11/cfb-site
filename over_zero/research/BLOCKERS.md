# Blockers log

Dated entries. Format: `## YYYY-MM-DD — <phase>` then what was attempted,
what is blocked, and a recommendation.

## 2026-07-30 — B4.2 (residual-feature probit)

**Attempted:** Write and run `research/b4_features/probit_features.py` (multivariate probit with 4 features from B4.1).

**Blocked:** `fcs_dog` feature has zero variance — all 12,493 joined games (post-lines filter) have `fcs_dog=0`.

**Evidence:**
- Joined games: 12,493 with complete score/line/game data (2013–2025)
- `fcs_dog` feature statistics: mean=0.0000, std=0.0000, unique values=[0.0]
- Direct count: "FCS games in lines with spread: 0" across all years
- Root cause: FCS opponents exist in `games_*.json` (e.g., College of Idaho, Valley City State; ~1.4–1.5% of raw records), but carry no betting lines. After `pick_line` filters for games with both spread and overUnder, no FCS dogs survive to the join.
- B4.1's "available" determination ran on `games_2024.json` alone (awayConference None in 53/3747 ≈ 1.4%), did not recheck post-join.

**Impact:**
- Script crashes: `MissingDataError: exog contains inf or nans` (standardization of zero-variance column → NaN)
- Cannot compute full spec fit; checklist questions (any feature *SIG*? biasTotals shift?) cannot be answered
- Base spec fit succeeds and matches expected: `biasTotals +0.0710 (SE 0.0081)`, confirming upstream pipeline is correct

**Unblocking options** (brief authorizes none; pick one):
1. **Drop to 3 features:** Use only `[week, neutralSite, conferenceGame]`, set `BONFERRONI_P = 0.05/3 = 0.0167`
2. **Substitute `home_dog`:** Replace `fcs_dog` with the already-computed `home_dog` (1 if spread > 0, 0 otherwise; available and non-constant in full set)
3. **Report as inestimable:** Run full spec with 3 features, explicitly note `fcs_dog` dropped due to zero variance, leave threshold at 0.0125

Each choice alters the prespecified 4-feature budget or the Bonferroni denominator — none is transparent without intervention. Recommend clarifying with the research plan owner before proceeding.

**Resolution (owner decision, 2026-07-31):** Substitute `home_dog` for
`fcs_dog`. `home_dog` is item 5 in the plan's own prespecified candidate
list (Task B4.1, "only if fewer than 4 of the above are available") —
using it here keeps the analysis within the plan's own fallback ordering.
FEATURES becomes `["week", "neutralSite", "conferenceGame", "home_dog"]`;
Bonferroni budget stays at 4 features (p < 0.0125), unchanged.

## 2026-07-31 — B1.1 (1H line source survey)

**Attempted:** Survey for real historical first-half (1H) college football betting lines
(spread + total) to feed `floor_bias_1h/run_1h.py`. Full details in
`research/b1_first_half/SOURCES.md`.

**Blocked:** No source found is both free and permitted to use for 1H spread + total lines.

**Evidence:**
- CFBD raw data already in repo (`../cfb-site/data/raw/lines_2024.json`): scanned all 1,523
  games' `lines` entries — only 8 keys exist (`awayMoneyline`, `formattedSpread`,
  `homeMoneyline`, `overUnder`, `overUnderOpen`, `provider`, `spread`, `spreadOpen`), all
  full-game markets. Zero first-half/period keys.
- sportsbookreviewsonline.com (free, robots.txt-permitted): the domain has been repurposed as a
  sportsbook-affiliate content site; its NCAA football archive pages (2007-08 – 2022-23) are
  HTML tables only (no downloadable file). Table schema is `Date, Rot, VH, Team, 1st, 2nd, 3rd,
  4th, Final, Open, Close, ML, 2H` — has a **2nd-half** column but **no 1st-half** column at
  all. Deriving 1H via FG − 2H would be a proxy, not a real posted first-half line.
- Kaggle `chrisnbell/college-football-spreads`: single season (2021), full-game columns only
  (`Spread`, `OverUnder`, `OpeningSpread`, etc.), license unstated ("Other, specified in
  description" but description is empty) — ambiguous license, treated as blocked per this task's
  rules independent of the missing-1H-column issue.
- the-odds-api.com: historical odds (any market, including 1H/period markets) require a paid
  plan — no free tier. Confirmed period markets only exist from 2023-05-03 onward even if paid.
- SportsDataIO, Unabated, OddsJam: all paid/sales-gated, no free tier for historical odds.

**Cheapest paid option found:** the-odds-api.com, 20K Plan, **$30/month** — includes historical
odds access, but 1H/period market backfill only reaches back to 2023-05-03 (covers the 2024
season this model targets; would not cover earlier seasons in a wider backtest). Next-cheapest
confirmed price: Unabated at $3,000/month. SportsDataIO and OddsJam publish no price
(sales-gated).

**Recommendation:** This task's rules forbid purchasing without owner approval, which is not
obtainable in this session. If B1 (first-half lines backtest) is to proceed, the owner needs to
either (a) approve the $30/month the-odds-api.com spend (accepting the 2023-05+ coverage
limit), or (b) approve contacting a sales-gated vendor for a quote, or (c) provide/point to an
existing 1H line dataset not surfaced by this survey. Per the brief, this ends Phase B1 — no
B1.2/B1.3/B1.4 work performed.

## 2026-07-31 — B2.1 (team-totals line source survey)

**Attempted:** Survey for real historical college-football **team-total** betting lines (dog
team-total market, feeding the OVER-on-underdog's-team-total bet in Phase B2). Full details in
`research/b2_team_totals/SOURCES.md`.

**Blocked:** No source found is both free and permitted to use for team-total lines. All four
paid vendors are blocked on cost alone (no free tier); team-totals-specific market coverage at
two of them is additionally unconfirmed either way.

**Evidence:**
- CFBD raw data already in repo (`lines_2024.json`): reused B1's exhaustive key scan (all 1,523
  games, all `lines` entries) — only 8 keys exist, all full-game/moneyline
  (`awayMoneyline, formattedSpread, homeMoneyline, overUnder, overUnderOpen, provider, spread,
  spreadOpen`). Zero team-total keys.
- the-odds-api.com: `team_totals`/`alternate_team_totals` exist as generic market keys on the
  platform, but the dedicated NCAA Football markets page lists only "Moneyline, Spreads,
  Over/Under, Quarter time and half time odds, player props" — team totals are not named for
  this sport. Checked both the general markets page and the canonical V4 API guide for a
  sport-by-sport market matrix — neither exists, so this is **unconfirmed, not ruled out**.
  Historical data requires a paid plan regardless (no free tier), cheapest $30/month (20K plan),
  same as B1 — this cost blocker holds independent of the coverage question.
- Unabated: published market list ("sides, totals, partial games, alternate lines, DFS pick'em
  lines, player props") omits team totals, but no exhaustive matrix was found either — same
  unconfirmed status. Price confirmed at $3,000/month (personal tier), a solid blocker on its
  own.
- SportsDataIO, OddsJam: both sales-gated, no published price, and team-totals coverage
  unconfirmed (detailed market/field docs require login or a sales contact).
- Kaggle: ran a fresh search distinct from B1's (which searched for "spreads") — no dataset
  containing college-football team-total odds found anywhere. The one NCAAF-odds dataset that
  exists (`chrisnbell/college-football-spreads`, already disqualified in B1 for single-season
  coverage and ambiguous license) has no team-total column at all — only full-game spread/total.

**Cheapest paid option found:** the-odds-api.com, 20K Plan, **$30/month** (same figure as B1) —
recorded as the cheapest reference price among surveyed vendors. Team-totals coverage for NCAAF
was not confirmed on that platform (or ruled out) without a paid API call or support inquiry,
neither authorized in this session.

**Recommendation:** This task's rules forbid purchasing without owner approval, and also forbid
contacting sales-gated vendors without authorization (out of scope). If Phase B2 (dog team-total
backtest) is to proceed, the owner needs to either (a) approve contacting the-odds-api.com
support directly to confirm whether `team_totals` will actually return NCAAF data before any
purchase, (b) approve a sales inquiry to SportsDataIO/OddsJam for a quote and market-coverage
confirmation, or (c) provide/point to an existing team-total line dataset not surfaced by this
survey. Per the brief, this ends Phase B2 — no B2.2/B2.3 work performed.

## 2026-07-31 — B3.1 (odds snapshot capture) — plan deviation, owner-approved

**Attempted:** Task B3.1 requires `ODDS_API_KEY` (owner-supplied env var) to run
`capture_odds.py` against the-odds-api.com's live odds endpoint (free tier, ~26
req/month). Env var was not set; owner was asked once per protocol.

**Owner decision (2026-07-31):** Do not wait for the API key / a live season of
capture. Instead, build B3's open-to-close drift analysis (open questions 4 & 5)
directly from data already on disk: `../cfb-site/data/raw/lines_{season}.json`
carries per-book `spread`/`spreadOpen` and `overUnder`/`overUnderOpen` fields for
every game in every already-downloaded season (2013–2025) — this is exactly the
open-vs-close pair B3's `analyze_drift.py` was designed to compute from live
snapshots, just already present historically instead of being captured forward.

**Scope change from the plan:** This replaces `capture_odds.py` +
`analyze_drift.py` (which need the API key and a live season to accumulate
snapshots) with a new one-shot driver reading the raw files directly. Coverage
gain: all historical seasons at once instead of one forward season.
Coverage loss: raw files have no per-book **price** field (only `spread`,
`spreadOpen`, `overUnder`, `overUnderOpen`) — open question 5 ("do books already
shade the over past −110") is **not answerable** from this data; only open
question 4 (does the total drift toward close) can be answered. If juice/price
data is wanted later, the original API-key-based capture script remains a valid
fallback — this deviation does not preclude running it once a key is provided.
