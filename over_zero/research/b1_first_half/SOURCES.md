# B1.1 — First-half (1H) college football line source survey

## Step 1: Raw CFBD data (`lines_2024.json`) key check

```bash
python -c "
import json
from pathlib import Path
g = json.loads(Path('../cfb-site/data/raw/lines_2024.json').read_text(encoding='utf-8'))
seen = set()
for game in g[:200]:
    for l in (game.get('lines') or []):
        seen.update(l.keys())
print(sorted(seen))
"
```

**Printed key list (first 200 games):**
```
['awayMoneyline', 'formattedSpread', 'homeMoneyline', 'overUnder', 'overUnderOpen', 'provider', 'spread', 'spreadOpen']
```

Re-ran the same scan over the **full file (all 1,523 games, all `lines` entries)** to be sure a
rare/late-season key wasn't missed by the `[:200]` slice in the brief's one-liner — identical
result, same 8 keys, no additional keys anywhere in the file.

**Verdict on Step 1:** No first-half-related keys present. No `spreadFirstHalf`,
`overUnderFirstHalf`, `period`, `spread1H`, or anything resembling a half/period market. CFBD's
`lines` payload (as vendored into this repo's raw data) only carries full-game spread
(open/close), full-game total (open/close), and moneyline, per provider. This is *not* the
cheapest source — it doesn't exist here at all. Must look externally.

## Step 2: External source survey (in brief's order)

### 1. sportsbookreviewsonline.com — historical odds archives

- **URL checked:** `https://www.sportsbookreviewsonline.com/scoresoddsarchives/ncaafootball/ncaafootballoddsarchives.htm`
  plus a season page: `https://www.sportsbookreviewsonline.com/scoresoddsarchives/ncaa-football-2022-23`
- **robots.txt:** `User-agent: *` / `Disallow: /go/` only (that's the outbound affiliate-link
  redirector path), plus a separate `Allow: /`. No blanket disallow on the archive pages. Also
  checked the site's posted "content signal" policy (Cloudflare-style AI/search opt-in/opt-out
  page) — it governs AI training/search-index use, not scraping for personal/research data
  extraction, and doesn't prohibit reading these pages.
- **Reality check — this is NOT the classic free-Excel-workbook site anymore.** The domain has
  been repurposed as a sportsbook-affiliate/casino-review content site (same brand, different
  operator/content: "Sportsbook Reviews", copyright 2026, review pages for BetOnline/Bovada/etc,
  bonus codes, "Bet Now" affiliate buttons). The NCAA football archive page it still hosts:
  - Lists seasons **2007-08 through 2022-23 only** — no 2023-24 or 2024-25 season link exists.
    (Secondary note only — coverage is not the deciding factor here; see below.)
  - Each season is now an **HTML table rendered directly on the page** (2,547 `<tr>` rows for
    2022-23) — there is **no downloadable .xlsx/.xls/.csv file** anymore (grepped all `href`
    attributes on the season page: zero matches for any spreadsheet extension or "download"
    link). The historical claim of "free Excel workbooks" no longer holds for this domain as it
    exists today.
  - **Columns present** (from the actual table header row):
    `Date, Rot, VH, Team, 1st, 2nd, 3rd, 4th, Final, Open, Close, ML, 2H`
    - `1st/2nd/3rd/4th/Final` = quarter-by-quarter and final **scores**, not lines.
    - `Open/Close` = full-game opening/closing spread or total (SBRO's classic format
      interleaves spread and total across the two team rows of a game).
    - `ML` = moneyline.
    - **`2H` = second-half line** (combined 2H spread/total in SBRO's classic single-column
      encoding). **There is no `1H` (first-half) column at all**, in this format or on this
      page. The page's own meta-description ("...including moneylines, 2nd half lines, opening
      and closing point spreads and totals") matches — it advertises 2nd-half lines, never
      first-half.
- **Coverage:** 2007-08 – 2022-23. (Would overlap most of this repo's 2013–2025 backtest window
  per B4's field inventory, so coverage alone is not disqualifying — the missing-column finding
  below is what actually rules this source out.)
- **1H spread AND 1H total?** No. Confirmed no first-half market of any kind — only a `2H`
  (second-half) column exists, full-game `Open`/`Close`, and `ML`. No `1H` field anywhere in the
  table schema or page description.
- **Considered deriving 1H from FG − 2H:** rejected. A subtracted number (full-game line minus
  the posted 2H line) is a derived proxy, not a real posted first-half market — books price 1H
  independently with its own vig/market movement, so this wouldn't satisfy "real historical
  first-half betting lines" per the task brief.
- **Format:** HTML table only, no export.
- **Join key:** Team name (informal short names, e.g. "Northwestern"), date, rotation number
  (`Rot`) — would need name normalization against CFBD team names, but moot given no 1H data.
- **Cost:** Free (page is publicly viewable).
- **ToS verdict:** Permitted to read (robots.txt allows it), but irrelevant — **no first-half
  market exists on this source at all**.
- **Conclusion: not usable — no 1H data (only 2H), and deriving 1H from FG − 2H would not be a
  real posted line.**

### 2. Kaggle datasets

Searched "college football odds first half" on Kaggle. Top candidates surfaced:
`chrisnbell/college-football-spreads`, `cvergnolle/football-5`, `mexwell/historical-football-resultsbetting-odds-data`
(soccer, not applicable), `austro/beat-the-bookie-worldwide-football-dataset` (soccer/worldwide,
not NCAAF).

Inspected the most relevant one in depth:

- **`chrisnbell/college-football-spreads`**
  - Single file: `2021CollegeFootballSpreads.csv` (382.52 kB) — **one season only (2021)**.
  - Columns (13 total, confirmed via Kaggle's column browser): `Id, HomeTeam, HomeScore,
    AwayTeam, AwayScore, LineProvider, OverUnder, Spread, FormattedSpread, OpeningSpread`, plus
    3 more not surfaced in the preview (likely closing-line variants). All full-game
    spread/total fields (`Spread`, `OverUnder`, `OpeningSpread`) — **no first-half or
    second-half columns visible in the schema**.
  - **License: "Other (specified in description)"** — but the dataset's "About" section says
    **"No description available."** License terms are effectively unstated/unknowable without
    contacting the uploader. Per this task's ToS rule (ambiguous → treat as blocked), this alone
    disqualifies it even before considering coverage.
  - **Coverage:** 2021 only — one season, doesn't cover the 2024 season this repo's model
    targets.
  - Usability score 2.94/10 on Kaggle (low), single contributor, "updated 2 years ago" (stale,
    unmaintained).
- Other search hits were soccer/worldwide datasets, not NCAAF, or general full-game college
  football stats/results with no odds column — none had first-half markets.
- **1H spread AND 1H total?** No, on the only NCAAF-specific candidate found.
- **Cost:** Free (Kaggle downloads are free).
- **ToS verdict:** License unstated/ambiguous → treated as blocked per this task's rule, moot
  anyway since coverage (1 season, no 1H columns) doesn't meet requirements.
- **Conclusion: not usable — no 1H columns, single stale season, ambiguous license.**

### 3. the-odds-api.com — historical endpoint

- **Markets:** Confirmed NCAAF supports "additional markets" beyond the featured set
  (moneyline/spreads/totals), including half-time/period markets (would include first-half
  spread and total, i.e. `spreads_h1`/`totals_h1`-style keys per their v4 API market
  documentation), but these require per-event calls (`/events/{eventId}/odds`), not the bulk
  endpoint.
- **Historical data:** **"Historical data is only available on paid usage plans"** — stated
  explicitly on `the-odds-api.com/historical-odds-data/`. No free-tier access to any historical
  odds, regardless of market.
- **Historical depth:** Featured markets back to June 6, 2020 (10-min intervals until Sept 2022,
  5-min after); additional/period markets only from **May 3, 2023** onward. This means even a
  paid plan could not backfill 1H lines for seasons before mid-2023 — a real coverage gap
  against this repo's broader multi-season backtest ambitions, though it would reach the 2024
  season this specific model targets.
- **Cost (from pricing page):**
  - 20K credits/month — **$30/month**
  - 100K credits/month — $59/month
  - 5M credits/month — $119/month
  - 15M credits/month — $249/month
  - All paid tiers include historical odds access. Historical odds endpoint costs 10 credits per
    region per market per call, so a full 1H spread+total backfill for a season would consume a
    non-trivial amount of quota (games × weeks × 2 markets × 10 credits), but even the cheapest
    $30/mo tier is nonzero cost.
- **ToS verdict:** N/A (this is a paid API with a documented ToS/license for use of the data
  under subscription — no scraping concern). The blocker is purely cost: **no free tier for
  historical data of any kind.**
- **Conclusion: not usable without payment. Cheapest tier: $30/month (20K Plan).**

### 4. SportsDataIO / Unabated / OddsJam historical archives

- **SportsDataIO** (`sportsdata.io/historical-odds`): Historical odds database for "all major
  sports from 2019 onwards, with props and futures from 2020," including college football.
  Delivery via API, S3 bucket, or custom setup. **No published price** — page requires "Get In
  Touch" (contact form) or a phone call to get a quote; this is an enterprise/sales-gated
  product, not self-serve pricing. First-half college football line availability specifically is
  not documented on the public page (would require a sales conversation to confirm).
- **Unabated** (`unabated.com/get-unabated-api`): **Published starting price — $3,000/month for
  personal use** (commercial pricing higher, via sales contact). Covers College Football among
  other sports, with "partial games" markets mentioned (consistent with 1H availability) via
  their proprietary vig-free consensus "Unabated Line." Confirmed price, but far above what any
  reasonable interpretation of "cheapest paid option" would select over the-odds-api's $30/mo.
- **OddsJam** (`oddsjam.com/odds-api`): API product pricing is **sales-gated, not published** —
  contact-sales only. Third-party estimates put API access in the $500-$1,000+/month range for
  comparable providers, though this is not an OddsJam-confirmed figure. (Their separate consumer
  "scanner" subscription product, ~$199/mo Gold tier, is a different product — not developer API
  access — and not counted here.) Treated as sales-gated/unknown, same as SportsDataIO.
- **Cost:** SportsDataIO and OddsJam: unpublished, sales-gated, no price obtainable without
  contacting a vendor (which is out of scope — cannot be authorized without owner approval, and
  no price is available to record). Unabated: published at $3,000/month, confirmed but not
  competitive with the-odds-api's $30/mo.
- **ToS verdict:** N/A — blocked on cost/access-gating, not scraping legality (all three are
  legitimate paid data vendors, not scrape targets).
- **Conclusion: not usable — cheapest of the three with a published price (Unabated, $3,000/mo)
  is still far more expensive than the-odds-api.com's $30/mo; the other two are sales-gated with
  no obtainable price. This group does not change the overall cheapest-paid-option figure.**

## Summary table

| Source | Coverage | 1H spread + 1H total? | Format | Join key | Cost | ToS |
|---|---|---|---|---|---|---|
| CFBD raw (`lines_2024.json`) | 2024 (full season) | No — full-game only | JSON (repo) | n/a | Free (already have it) | n/a |
| sportsbookreviewsonline.com | 2007-08 – 2022-23 | No (has 2H only, no 1H) | HTML table, no export | Team name + date + Rot | Free | Permitted, but no 1H data |
| Kaggle `college-football-spreads` | 2021 only | No | CSV | Team name | Free | License unstated (ambiguous) |
| the-odds-api.com historical | 2023-05+ (period markets) | Likely yes (per-event call) | JSON API | Team name + date (event ID) | **$30/mo minimum** (20K plan), paid only | OK for paid use, but cost-blocked |
| SportsDataIO historical | 2019+ (general) | Unconfirmed, sales-gated | API/S3 | Unknown | **Unpublished, sales contact required** | Cost/access-blocked |
| Unabated | Multi-sport incl. CFB | Unconfirmed ("partial games" mentioned) | API | Unknown | **$3,000/mo** (published, personal tier) | Cost-blocked |
| OddsJam | Multi-sport | Unconfirmed | API | Unknown | **Unpublished, sales contact required** (API product) | Cost/access-blocked |

## Step 3: Verdict

No source surveyed provides first-half college football spread AND total lines that is both
free and permitted to use. The CFBD data already in the repo has zero first-half markets. The
one remaining nominally-free source (sportsbookreviewsonline.com) has no first-half column at
all — only a 2nd-half column exists, and deriving 1H by subtracting 2H from the full-game line
would be a proxy, not a real posted first-half market. The one Kaggle dataset found with NCAAF
odds has no 1H columns, one season only, and an ambiguous/unstated license. All four paid
vendors surveyed (the-odds-api.com, SportsDataIO, Unabated, OddsJam) require payment (or are
sales-gated with no obtainable price) with no free tier for historical data, and this task's
rules forbid purchasing without owner approval, which is not obtainable in this session.

**VERDICT: blocked**

Cheapest paid option found: **the-odds-api.com, 20K Plan, $30/month** (includes historical odds
access across all markets/sports, but period/first-half market backfill only extends back to
2023-05-03 — would cover the 2024 season this model targets, but not earlier seasons if a wider
backtest window is later needed). Next-cheapest confirmed price: Unabated at $3,000/month
(personal tier). SportsDataIO and OddsJam publish no price at all (sales-gated).
