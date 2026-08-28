# B2.1 — Team-total (dog team-total OVER) college football line source survey

Bet studied: OVER on the underdog's **team total** (not full-game spread/total, not a
half/period market). Team totals are a rarer market than full-game spread/total or even
first-half lines — expected to be paid-only or entirely unlisted for NCAAF.

Reused B1.1 (`research/b1_first_half/SOURCES.md`) pricing/tier context as a starting point,
but every source below was independently re-checked for the **team-totals-specific** angle
(not just general spread/total availability), per the task brief.

## Step 1: Source survey (brief's order)

### 1. the-odds-api.com — historical endpoint

- **Market exists on the platform generically:** `team_totals` ("Featured team totals
  (Over/Under)") and `alternate_team_totals` ("All available team totals (Over/Under)") are
  documented market keys on `the-odds-api.com/sports-odds-data/betting-markets.html`, alongside
  period-scoped variants (`team_totals_h1`, `team_totals_q1`, etc.).
- **NCAAF-specific market list does not name team totals — but no sport-by-sport matrix exists
  to rule it out either.** The dedicated NCAA Football page
  (`the-odds-api.com/sports-odds-data/ncaa-football-odds.html`) enumerates this sport's
  supported markets as: **"Moneyline, Spreads (handicap), Over/Under (totals), Quarter time and
  half time odds, [NCAA football player props]."** Team totals are absent from this summary
  list. However, checked both the general betting-markets page and the canonical V4 API
  reference (`the-odds-api.com/liveapi/guides/v4/`) for a sport-by-sport market availability
  matrix — **neither publishes one.** The betting-markets page only states "spreads and totals
  markets are mainly available for US sports and bookmakers," with no per-sport breakdown of
  `team_totals` specifically, and the V4 guide doesn't mention `team_totals` at all. **Verdict:
  NCAAF team-totals availability is unconfirmed, not confirmed-absent** — the sport page is a
  marketing summary, not an exhaustive market list, so its omission of team totals is suggestive
  but not conclusive.
- **Historical data:** Same as B1 finding — historical odds (any market) require a paid plan,
  no free tier. Additional/period markets (which is the closest documented NCAAF-relevant
  category near team totals) only backfill from **May 3, 2023** onward; featured markets from
  June 6, 2020.
- **Cost:** Same tiers as B1: 20K credits/mo — **$30/month** (cheapest), up to $249/month.
- **ToS verdict:** N/A — paid API, legitimate subscription product, no scraping concern.
- **Conclusion: not usable.** Independent of the coverage ambiguity above, the cost blocker is
  solid and sufficient on its own: historical data of any kind requires a paid plan, no free
  tier exists. Team-totals coverage for NCAAF specifically remains unconfirmed either way —
  resolving it would require a support inquiry (out of scope) or an actual paid API call, not
  authorized in this session.

### 2. SportsDataIO

- **Historical odds product** (`sportsdata.io/historical-odds`): "all major sports from 2019
  onwards, with props and futures from 2020," including college football. Delivery via API, S3
  bucket, or custom setup.
- **Team-totals-specific coverage:** Not documented on any public page. The NCAA football API
  developer portal (`sportsdata.io/developers/api-documentation/ncaa-football`) does not expose
  its detailed odds-market field list without an authenticated session ("Sign In" gated,
  dynamically loaded docs) — team total availability cannot be confirmed or ruled out from
  public pages.
- **Cost:** **No published price** — page requires "Get In Touch" (contact form) or a phone
  call. Enterprise/sales-gated, same as B1's finding. No self-serve pricing to record beyond
  "unpublished."
- **ToS verdict:** N/A — blocked on cost/access-gating (no obtainable price), not on scraping
  legality.
- **Conclusion: not usable** — cost/access-blocked (unpublished, sales-gated); team-totals
  market coverage additionally unconfirmed.

### 3. Unabated

- **Market list:** Unabated's API docs describe markets for "sides, totals, partial games,
  alternate lines, DFS pick'em lines and player props" — **team totals are not named** in this
  list (unlike the-odds-api, which at least documents a `team_totals` key generically).
  "Partial games" refers to period/half markets, not team totals. No explicit team-total mention
  found anywhere on `unabated.com/get-unabated-api` or `unabated.com/cfb/odds`.
- **Cost:** Confirmed at **$3,000/month** for personal use (commercial pricing higher, via sales
  contact) — same figure as B1.
- **ToS verdict:** N/A — legitimate paid vendor, blocked on cost.
- **Conclusion: not usable** — cost-blocked at a confirmed $3,000/month with no free tier;
  team-totals coverage additionally not confirmed (published market list omits it, but no
  exhaustive market matrix was found to rule it out definitively).

### 4. OddsJam

- **Market list:** OddsJam's API product page describes "moneylines, spreads, totals, player
  props, live odds, and more" / "alternate markets" in general terms. No explicit mention of
  team totals as a named market for any sport, including NCAAF.
- **Cost:** **Sales-gated, not published** — same as B1's finding (contact-sales only for the
  API product; the ~$199/mo consumer scanner tier is a different, non-API product not counted).
- **ToS verdict:** N/A — blocked on cost/access-gating.
- **Conclusion: not usable** — cost/access-blocked (unpublished), team-totals coverage
  unconfirmed.

### 5. Kaggle

Ran a fresh search: "college football team total odds dataset" (not reusing B1's spread-focused
search). Results surfaced no new candidate beyond what B1 already found:

- **`chrisnbell/college-football-spreads`** (same dataset B1 inspected in depth): single file
  `2021CollegeFootballSpreads.csv`, one season only (2021), columns are `Id, HomeTeam,
  HomeScore, AwayTeam, AwayScore, LineProvider, OverUnder, Spread, FormattedSpread,
  OpeningSpread` plus 3 more closing-line variants — **no team-total column** (`HomeScore` /
  `AwayScore` are final scores, not team-total betting lines). License unstated/ambiguous
  ("Other, specified in description" but description is empty) — same disqualifying issue B1
  found.
- Other search hits: `cvergnolle/football-5` (general college football database, no odds
  columns), `mhixon/college-football-statistics` and `jeffgallini/college-football-team-stats-*`
  (team stats, not betting odds), `cviaxmiwnptr/college-football-team-stats-2002-to-january-2024`
  (box scores, not odds), `eladsil/football-games-odds` and `rayenjlassi/*` (soccer, not
  applicable), `oliviersportsdata/datasets-road-to-march-madness` (NCAAB moneyline closing odds
  only, wrong sport). None contain a team-total betting market for any sport, let alone NCAAF.
- **No dataset found — on Kaggle or anywhere else searched — that contains historical college
  football team-total betting lines.** This is a stricter finding than B1 (which at least found
  a dataset with the adjacent full-game spread/total market, even if disqualified on other
  grounds).
- **Cost:** Free (Kaggle downloads are free) — moot, no relevant dataset exists.
- **ToS verdict:** N/A — no relevant dataset to evaluate.
- **Conclusion: not usable** — no team-totals dataset exists on Kaggle for college football.

## Summary table

| Source | Team-totals market documented for NCAAF? | Coverage (if any) | Format | Join key | Cost | ToS |
|---|---|---|---|---|---|---|
| CFBD raw (`lines_2024.json`, already in repo) | No — B1's key scan (all 1,523 games, all `lines` entries) found only 8 keys, all full-game/moneyline: `awayMoneyline, formattedSpread, homeMoneyline, overUnder, overUnderOpen, provider, spread, spreadOpen`. Zero team-total keys. | 2024 (full season) | JSON (repo) | n/a | Free (already have it) | n/a |
| the-odds-api.com historical | Not confirmed — `team_totals`/`alternate_team_totals` documented generically on the platform; NCAAF's own market-summary page lists only moneyline/spreads/totals/quarter-half/player props; no sport-by-sport market matrix published anywhere (checked both the general markets page and the canonical V4 API guide) | Unconfirmed for NCAAF | JSON API | Team name + date (event ID) | **$30/mo minimum** (20K plan), paid only | OK for paid use, but cost-blocked regardless of coverage |
| SportsDataIO | Unconfirmed — detailed odds-field docs are login-gated | Unknown | API/S3 | Unknown | **Unpublished, sales contact required** | Cost/access-blocked |
| Unabated | Not confirmed — published market list (sides, totals, partial games, alternates, player props) omits team totals, but no exhaustive matrix found | Unconfirmed | API (SSE) | Unknown | **$3,000/mo** (published, personal tier) | Cost-blocked regardless of coverage |
| OddsJam | Unconfirmed — no market-level detail published | Unknown | API | Unknown | **Unpublished, sales contact required** | Cost/access-blocked |
| Kaggle | No — no team-totals dataset exists for college football on Kaggle (fresh search, distinct from B1's spread-focused search) | N/A | N/A | N/A | Free (moot) | N/A — no dataset to evaluate |

## Step 2: Verdict

No source surveyed offers real historical college-football team-total betting lines that is
free and permitted to use. The CFBD data already in the repo has zero team-total keys (reusing
B1's exhaustive key scan). No Kaggle dataset containing team-total odds for college football
could be found at all — a worse outcome than B1, which at least found an adjacent full-game
spread/total dataset (disqualified on other grounds). The four paid/sales-gated vendors
(the-odds-api.com, SportsDataIO, Unabated, OddsJam) are blocked on cost alone, independent of
coverage: none offers a free tier, and this task's rules forbid purchasing without owner
approval. Team-totals-specific market coverage at the-odds-api.com and Unabated is unconfirmed
(not documented as offered, but no exhaustive per-sport market matrix exists to rule it out
definitively) — resolving that would require a paid API call or a sales inquiry, neither
authorized in this session.

**VERDICT: blocked**

Cheapest paid option with a published price: **the-odds-api.com, 20K Plan, $30/month** (same as
B1) — recorded as the cheapest reference price among surveyed vendors; team-totals coverage for
NCAAF was not confirmed on that platform (or ruled out) without a paid call. Next-cheapest
confirmed price: Unabated at $3,000/month, whose published market list similarly does not name
team totals. SportsDataIO and OddsJam publish no price at all (sales-gated) and neither confirms
team-totals coverage.

This ends Phase B2 — no B2.2/B2.3 work performed, per the brief.
