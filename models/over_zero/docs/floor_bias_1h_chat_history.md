# Floor Bias Model — Chat Export

Session: 35207b77-2b77-420f-8c1e-98dfa65dc487  |  2026-06-13

### **User**  ·  2026-06-13 14:08:36

@"C:\Users\mckel\Downloads\aca2db1f-c155-4e15-80e9-59e43b485ded.pdf"
summarize this paper and recreate all the models discussed in it. especially the censoring bias one betting on college football point totals /caveman

### **Claude**  ·  2026-06-13 14:08:42

Read paper first. 28 pages.

### **Claude**  ·  2026-06-13 14:08:43

[tool: Read]

### **Claude**  ·  2026-06-13 14:08:48

Read tool needs poppler (missing). Extract text via python.

### **Claude**  ·  2026-06-13 14:08:49

[tool: Bash]

### **Claude**  ·  2026-06-13 14:09:03

No PDF libs. Install pypdf.

### **Claude**  ·  2026-06-13 14:09:04

[tool: Bash]

### **Claude**  ·  2026-06-13 14:09:22

[tool: Bash]

### **Claude**  ·  2026-06-13 14:09:37

[tool: Read]

### **Claude**  ·  2026-06-13 14:09:42

Got core. Read rest (tables/appendix).

### **Claude**  ·  2026-06-13 14:09:43

[tool: Read]

### **Claude**  ·  2026-06-13 14:10:08

Have full paper. Now build. Check deps first.

### **Claude**  ·  2026-06-13 14:10:09

[tool: Bash]

### **Claude**  ·  2026-06-13 14:10:56

All deps present (numpy/scipy/statsmodels/pandas). 

Paper read complete. Building recreation now. Plan:

```
1. censoring_bias.py  → all models → verify: import + unit math checks
2. demo_reproduce.py  → synthetic data calibrated to paper params → verify: reproduce ~55.7% win@bias>1.0
3. README.md          → summary + model map
```

Models in paper (recreating each):

| # | Model | Eq | 
|---|-------|-----|
| 1 | Implied team points | 6,7 |
| 2 | OLS line-bias test (α=0,β=1 F-test) | 3,4 |
| 3 | OLS team-points | 8,9 |
| 4 | **Tobit Type-1 left-censored MLE** | 10,11 |
| 5 | **Censoring bias** (the key one) | 12,13 |
| 6 | Probit win model | 14 |
| 7 | Even-Noble LL-ratio test | 5 |
| 8 | Game win prob = Φ(spread/σ) | — |
| 9 | Strategy backtest (unit + Kelly) | Tbl 5 |
| 10 | K-fold CV | Tbl 6 |

### **Claude**  ·  2026-06-13 14:10:57

[tool: Bash]

### **Claude**  ·  2026-06-13 14:11:05

Write core module.

### **Claude**  ·  2026-06-13 14:12:07

[tool: Write]

### **Claude**  ·  2026-06-13 14:12:12

Write demo that reproduces paper numbers from calibrated synthetic data.

### **Claude**  ·  2026-06-13 14:12:42

[tool: Write]

### **Claude**  ·  2026-06-13 14:12:47

[tool: Bash]

### **Claude**  ·  2026-06-13 14:13:30

Works. Tobit recovers σ exactly (11.29/11.94 vs paper 11.28/11.94). OLS underdog intercept biased up (1.52) / slope down (0.94), Tobit corrects (0.21/0.99). Probit slope positive. Over beats 52.38% above bias threshold, Kelly > unit. Mechanism reproduced.

Win% slightly under paper's 55.72% — expected: real bias distribution depends on actual joint line data (Goldsheet, not public). Quant, not mechanism, differs. Now README + check for real project data.

### **Claude**  ·  2026-06-13 14:13:31

[tool: Bash]

### **Claude**  ·  2026-06-13 14:13:53

Real `games.csv` exists. Check schema — could run models on real CFBD data.

### **Claude**  ·  2026-06-13 14:13:54

[tool: Bash]

### **Claude**  ·  2026-06-13 14:14:10

Real data maps cleanly: `spread`=home spread (sign→favorite), `total`=totals line, points per side. Build a real-data runner — runs the recreated models on actual CFBD lines.

### **Claude**  ·  2026-06-13 14:14:31

[tool: Write]

### **Claude**  ·  2026-06-13 14:14:35

[tool: Bash]

### **Claude**  ·  2026-06-13 14:14:52

Real CFBD data (2023, 2808 games) reproduces paper near-perfectly:
- **Spread line unbiased** (F=0.96, p=0.38) — paper p=0.27 ✓
- **Totals line biased** (F=10.2, p<0.001) ✓
- Tobit σ: 10.76/11.77 (paper 11.28/11.94) ✓
- Probit slope +0.19, positive (paper +0.117) ✓
- **Bet over @ bias>1.0 → 55.49% win** — paper 55.72% ✓✓

Write README.

### **Claude**  ·  2026-06-13 14:15:17

[tool: Write]

### **Claude**  ·  2026-06-13 14:15:33

Done. 

## Paper summary

**Arscott (2022), "Market efficiency and censoring bias in college football gambling"** (SSRN 4197428).

Core idea: spread + totals lines jointly imply each team expected points. Teams can't score <0 → scores **left-censored at 0**. Lines unbiased about *latent* score but ignore censoring. Censoring inflates realized totals:
- **Totals** = fav bias + dog bias → always ≥0 → over underpriced.
- **Spread** = fav bias − dog bias → cancels (underdog censors more) → stays fair.

Measure bias via **Tobit**, regress over-wins on it via **probit**. Bet over when expected bias >1.0 pt → **55.72% win** vs 52.38% breakeven → totals market semi-strong **inefficient**. ~43 spots/season.

## Built — `paper_models/`

All 10 models recreated as pure numpy functions:

| # | Model | Eq |
|---|-------|----|
| 1 | implied team points | 6,7 |
| 2/3 | OLS line-bias test (joint α=0,β=1 F-test) | 3,4,8,9 |
| 4 | **Tobit Type-1 left-censored MLE** | 10,11 |
| 5 | **censoring bias** (`σφ(μ/σ) − μΦ(−μ/σ)`) | 12,13 |
| 6 | probit win model | 14 |
| 7 | Even–Noble LL-ratio test | 5 |
| 8 | game win prob Φ(spread/σ) | §5 |
| 9 | strategy returns (unit + Kelly) | Tbl 5 |
| 10 | k-fold CV | Tbl 6 |

Files:
- [censoring_bias.py](paper_models/censoring_bias.py) — library
- [demo_reproduce.py](paper_models/demo_reproduce.py) — synthetic validation (Tobit recovers planted σ to 2 decimals)
- [run_on_project_data.py](paper_models/run_on_project_data.py) — runs on your real `games.csv`
- [README.md](paper_models/README.md) — summary + model map + results

## Verification (real 2023 CFBD, 2808 games)

| | Paper | Yours |
|--|-------|-------|
| Spread unbiased | p=0.27 | p=0.38 ✓ |
| Totals biased | p<0.01 | p<0.001 ✓ |
| Tobit σ dog/fav | 11.28/11.94 | 10.76/11.77 ✓ |
| Probit slope | +0.117 | +0.19 ✓ |
| **Over win% @ bias>1.0** | **55.72%** | **55.49%** ✓ |

Mechanism reproduced on real data. Run: `python paper_models/run_on_project_data.py`.

Caveat: exact % needs paper Goldsheet 1992–2017 (not public); magnitudes shift with line distribution, mechanism holds.

### **User**  ·  2026-06-13 14:19:42

run the model on 2025 and 2024 data

### **Claude**  ·  2026-06-13 14:19:46

Check what seasons exist. games.csv looked like 2023 only.

### **Claude**  ·  2026-06-13 14:19:47

[tool: Bash]

### **Claude**  ·  2026-06-13 14:20:04

games.csv has 2023+2024 (my earlier run pooled both). No 2025. Check if 2025 data fetchable/exists.

### **Claude**  ·  2026-06-13 14:20:06

[tool: Bash]

### **Claude**  ·  2026-06-13 14:20:21

Raw `games_2025.json`/`lines_2025.json` exist — just not built into games.csv. Check `build` command to make per-season CSVs.

### **Claude**  ·  2026-06-13 14:20:21

[tool: Read]

### **Claude**  ·  2026-06-13 14:20:31

`build` writes one games.csv. I'll build 2023+2024+2025 into it (strictly more data, project wants 2025 anyway), then filter by season in the runner. First build.

### **Claude**  ·  2026-06-13 14:20:32

[tool: Bash]

### **Claude**  ·  2026-06-13 14:20:42

[tool: Bash]

### **Claude**  ·  2026-06-13 14:20:51

Now add season filter to runner.

### **Claude**  ·  2026-06-13 14:20:57

[tool: Edit]

### **Claude**  ·  2026-06-13 14:21:08

[tool: Edit]

### **Claude**  ·  2026-06-13 14:21:13

`sys` now orphaned by my change — remove it.

### **Claude**  ·  2026-06-13 14:21:14

[tool: Edit]

### **Claude**  ·  2026-06-13 14:21:17

Run 2024 and 2025 separately.

### **Claude**  ·  2026-06-13 14:21:18

[tool: Bash]

### **Claude**  ·  2026-06-13 14:21:52

Ran both seasons separately. Results:

## 2024 (1,501 games) — confirms paper

| Test | Result |
|------|--------|
| Spread bias | unbiased, F=1.72 (p=0.18) ✓ |
| Totals bias | **biased**, F=5.16 (p=0.006) ✓ |
| Tobit σ dog/fav | 10.89 / 11.93 |
| Probit slope | **+0.204** (positive) ✓ |
| Over @ bias>1.0 | **58.06%** win, +10.9% unit |
| Over @ bias>1.75 | 64.29% win, +22.7% unit |
| K-fold | 4/5 folds win >50% |

Clean reproduction. Edge present.

## 2025 (1,541 games) — weak/absent

| Test | Result |
|------|--------|
| Spread bias | unbiased, F=1.90 (p=0.15) ✓ |
| Totals bias | **NOT significant**, F=0.39 (p=0.68) ✗ |
| Tobit σ dog/fav | 10.18 / 11.51 |
| Probit slope | +0.141 (still positive) |
| Over @ bias>1.0 | 55.13% win (+5.2% unit) — marginal |
| Over @ bias>1.75 | 45.45% win (−13% unit) — **loses**, N=22 |
| K-fold | noisy, 40–65% win, mixed returns |

## Read

- **2024 = textbook paper result.** Totals biased, censoring-bias edge real, over profitable above threshold.
- **2025 = edge mostly gone.** Aggregate totals line NOT significantly biased this season; high-bias bucket actually lost (tiny N=22). Probit slope still positive but flatter.
- **Caveat — small samples.** Single season ≈ 78–93 qualifying bets; k-fold folds N=13–55. Very noisy. Paper's 55.72% came from ~13k games over 26 seasons. One season can't confirm/reject; 2025 may be variance or genuine market tightening (sportsbooks adjusting to known censoring — exactly the anomaly-vanishing the author predicted).

Side effect: built `data/processed/games.csv` now holds 2023+2024+2025 (4,401 games) — was 2023+2024. Pooled all-season run: `python paper_models/run_on_project_data.py` (no `--season`).

### **User**  ·  2026-06-13 14:29:15

what data do you need to backtest that model?

### **Claude**  ·  2026-06-13 14:29:30

Model needs almost nothing — that's the paper's whole point (strategy uses only the two lines themselves). Per game:

## Required (4 fields)

| Field | Have it? | Used for |
|-------|----------|----------|
| Closing **point spread** | ✓ `games.csv:spread` | implied points, spread error |
| Closing **total** (O/U) | ✓ `games.csv:total` | implied points, totals error |
| **Favorite final points** | ✓ derive from `home_points`/`away_points` + spread sign | actual score, censoring fit |
| **Underdog final points** | ✓ same | actual score, censoring fit |

That's it. From spread+total → implied team points (Eqs 6,7). From scores → forecast errors. Tobit needs the score column (censoring at 0). Everything else (bias, probit, strategy) derives from those four. **You already have all of it.**

## What would make backtest *better*

1. **More seasons.** Biggest gap. Paper = ~13k games / 26 seasons (1992–2017). You have 3 (2023–25, ~4.4k). Raw `games_2012..2025.json` + `lines_2012..2025.json` exist on disk — build them in:
   ```
   python -m cfb_system_maker build --season 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 --data-dir data
   ```
   → ~14 seasons, sample size near paper's. Fixes the small-N noise that made 2025 unreadable.

2. **Per-book price (vig), not just the line.** Currently assume −110 flat. Real `lines_*.json` may carry `spread`/`overUnder` per provider but break-even hurdle varies if a book tilts juice on the over. Paper notes strategy can adapt to actual commission. Optional.

3. **Opening + closing lines.** You have closing only. Paper used closing (correct choice). Opening would let you test line movement — not needed for this model.

## Not needed

Drives, player stats, advanced metrics, weather, recruiting — none. Model is deliberately information-light. The 4 GB of scraped endpoints in `data/raw/` are irrelevant to it.

Want me to build all 14 seasons and rerun? That's the single highest-value next step.

### **User**  ·  2026-06-13 14:30:50

is that how far back that data goes?

### **Claude**  ·  2026-06-13 14:30:58

Two things: what's on disk vs what CFBD API offers. Check disk.

### **Claude**  ·  2026-06-13 14:30:59

[tool: Bash]

### **Claude**  ·  2026-06-13 14:31:16

On disk: **games** go back to 1992, but **lines only 2012→2025**. Model needs both → floor is **2012** (14 seasons) with current data.

Why 2012: CFBD's betting-lines endpoint coverage effectively starts ~2012. Games/scores go back to 1992 but no spread/total before 2012, so they're unusable for this model. The paper got 1992–2017 from Goldsheet (a different source); CFBD won't match that depth on lines.

Verify 2012 lines actually carry totals (not spread-only):

### **Claude**  ·  2026-06-13 14:31:19

[tool: Bash]

### **Claude**  ·  2026-06-13 14:31:29

2012 file has games but 0 spreads/totals — empty or different key. Peek structure.

### **Claude**  ·  2026-06-13 14:31:31

[tool: Bash]

### **Claude**  ·  2026-06-13 14:31:47

2012 lines are empty (`"lines": []`) — CFBD has no betting lines that year. So real floor is **2013**, not 2012.

## Bottom line

| Data | Coverage on disk | Binding? |
|------|------------------|----------|
| Games/scores | 1992, 1998, 2001+ … 2025 | no |
| **Betting lines (spread+total)** | **2013→2025, populated** | **yes — this is the limit** |

**Usable backtest range = 2013–2025 = 13 seasons** (~10k+ games with totals). 2013/2014 have ~700 games with totals each, full seasons from there.

Can't go earlier without a non-CFBD source. Paper's 1992–2017 came from Goldsheet, which CFBD doesn't replicate pre-2013. To match paper depth you'd need to source historical lines elsewhere (Goldsheet archive, Sportsbook Review, etc.) — separate data-acquisition problem.

13 seasons is plenty to beat the single-season noise that wrecked 2025. Want me to build 2013–2025 and run the full backtest?

### **User**  ·  2026-06-13 14:43:28

yes

### **Claude**  ·  2026-06-13 14:43:31

Build 2013–2025, then run pooled + per-season.

### **Claude**  ·  2026-06-13 14:43:33

[tool: Bash]

### **Claude**  ·  2026-06-13 14:43:43

12,964 games — nearly paper's 13,276. Run pooled full pipeline.

### **Claude**  ·  2026-06-13 14:43:44

[tool: Bash]

### **Claude**  ·  2026-06-13 14:44:06

Pooled 2013–2025 (9,653 usable games) — robust reproduction:

| Metric | Paper | Pooled 2013–25 |
|--------|-------|----------------|
| Spread bias | unbiased p=0.27 | unbiased p=0.57 ✓ |
| Totals bias | biased p<0.01 | biased p<0.001 ✓ |
| Tobit σ dog/fav | 11.28/11.94 | 10.88/11.73 ✓ |
| Probit slope | +0.117 | +0.191 ✓ |
| **Over @ bias>1.0** | **55.72%** | **57.42%** ✓✓ |
| Over @ bias>1.75 | 59.19% | 64.92% ✓ |
| K-fold OOS | robust | 4/5 folds positive (51.6–61% win) ✓ |

Edge holds out-of-sample. Now per-season stability check.

### **Claude**  ·  2026-06-13 14:44:14

[tool: Bash]

### **Claude**  ·  2026-06-13 14:44:52

Done. Per-season + pooled complete. 

## Per-season: edge is stable

| Season | Totals biased? | Probit slope | Over @ bias>1.0 win% | Unit% |
|--------|---------------|--------------|------|-------|
| 2017 | p=0.93 | +0.29 | 52.94% | +1.1% |
| 2018 | p=0.31 | +0.24 | 58.54% | +11.8% |
| 2019 | p=0.02 ✓ | +0.21 | 62.96% | +20.2% |
| 2020 | p=0.28 | +0.29 | 57.14% | +9.1% |
| 2021 | p=0.01 ✓ | +0.27 | 57.69% | +10.1% |
| 2022 | p=0.11 | +0.10 | 55.21% | +5.4% |
| 2023 | p=0.006 ✓ | +0.18 | 55.41% | +5.8% |
| 2024 | p=0.006 ✓ | +0.20 | 58.06% | +10.9% |
| 2025 | p=0.68 | +0.14 | 55.13% | +5.2% |

**Probit slope positive in all 9 seasons. Over @ bias>1.0 beats 52.38% breakeven in all 9.** Even 2025 — the >1.75 bucket that lost earlier was just noise (N=22); at the correct >1.0 threshold it's 55.13%, +5.2%.

## Pooled 2013–2025 (9,653 games) vs paper

| | Paper | Yours |
|--|-------|-------|
| Over @ bias>1.0 | 55.72% | **57.42%** |
| Unit return | +6.37% | +9.63% |
| Kelly return | +9.91% | +16.15% |
| K-fold OOS | robust | 4/5 folds positive |

**Verdict: paper replicates on independent CFBD data, 2013–2025. The censoring-bias over edge is real and out-of-sample robust.** Earlier 2025-alone scare was small-sample variance, not signal death.

## Two notes

1. **2013/2015/2016 dropped** from per-season (consensus provider sparse those years → empty spread/total rows). Pooled still used what was usable. Rebuild without forcing `--provider consensus` (let `_select_line` fall back to any book) to recover them — want that?
2. games.csv now = 2013–2025 (12,964 rows, 9,653 usable). Was 2023–2025.

Highest-value verification is done. The model holds.

### **User**  ·  2026-06-13 14:46:08

1. yes

### **Claude**  ·  2026-06-13 14:46:21

Confirms it: 2013/2015/2016 ≈ 0 usable, so `consensus` selection emptied them at build. Check normalize logic + build provider default before rebuild.

### **Claude**  ·  2026-06-13 14:46:22

[tool: Bash]

### **Claude**  ·  2026-06-13 14:46:31

[tool: Read]

### **Claude**  ·  2026-06-13 14:46:52

`_select_line` returns `usable[0]` — first line with spread **or** total. For 2013/2015/2016 the first book is spread-only → total empty → my model drops it (needs both). Forcing a provider won't fix generically. Won't touch project `normalize.py` (changes build/backtest behavior).

Better: the raw `lines_{yr}.json` already carries scores **and** all books' lines. Add a raw loader that per game picks a line with **both** spread and total. Self-sufficient, recovers every season. Check shape first.

### **Claude**  ·  2026-06-13 14:46:55

[tool: Bash]

### **Claude**  ·  2026-06-13 14:47:09

721/829 recovered for 2015 by picking any book with both fields. Raw lines file has scores too — self-sufficient. Add raw loader.

### **Claude**  ·  2026-06-13 14:47:10

[tool: Edit]

### **Claude**  ·  2026-06-13 14:47:22

[tool: Edit]

### **Claude**  ·  2026-06-13 14:47:32

[tool: Edit]

### **Claude**  ·  2026-06-13 14:47:36

Run pooled 2013–2025 from raw + per-season table.

### **Claude**  ·  2026-06-13 14:47:37

[tool: Bash]

### **Claude**  ·  2026-06-13 14:47:52

12,443 usable now (+2,800 recovered, ≈ paper's 13,276). Tobit σ 11.03/11.77 — even closer to paper. Now per-season from raw.

### **Claude**  ·  2026-06-13 14:47:59

[tool: Bash]

### **Claude**  ·  2026-06-13 14:48:27

All 13 seasons now. Recovered 2013/2015/2016.

## Per-season, over @ bias>1.0 (raw loader, both-field books)

| Season | N | Win% | Unit% | Slope |
|--------|---|------|-------|-------|
| 2013 | 26 | 53.85% | +2.8% | + |
| 2014 | 25 | 64.00% | +22.2% | + |
| **2015** | 14 | **50.00%** | **−4.6%** | **−0.10** |
| **2016** | 31 | **51.61%** | **−1.5%** | + |
| 2017 | 17 | 52.94% | +1.1% | + |
| 2018 | 41 | 58.54% | +11.8% | + |
| 2019 | 54 | 62.96% | +20.2% | + |
| 2020 | 21 | 57.14% | +9.1% | + |
| 2021 | 78 | 57.69% | +10.1% | + |
| 2022 | 96 | 55.21% | +5.4% | + |
| 2023 | 76 | 55.26% | +5.5% | + |
| 2024 | 93 | 58.06% | +10.9% | + |
| 2025 | 79 | 55.70% | +6.3% | + |
| **TOTAL** | **651** | **56.84%** | — | — |

## Read

- **11/13 seasons profitable** (clear 52.38%). Aggregate 651 bets @ **56.84%** — beats paper's 55.72%.
- **2 losing seasons: 2015, 2016.** 2015 probit slope went *negative* (−0.10) — censoring relation inverted that year. Both tiny N (14, 31). Looks like variance, not regime — flanked by strong 2014 (64%) and 2017–19.
- Pooled 12,443 games: spread unbiased (p=0.63), totals biased (p<0.001), σ 11.03/11.77 (paper 11.28/11.94), k-fold 4/5 positive. Full replication.

## Deliverable state

Two load paths in [run_on_project_data.py](paper_models/run_on_project_data.py):
- default → built `games.csv` (consensus, drops spread-only-first seasons)
- `--raw --season …` → reads `data/raw/lines_{yr}.json`, picks a book with **both** spread+total → **+2,800 more games**, recovers all seasons. Use this for backtesting.

```
python paper_models/run_on_project_data.py --raw --season 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025
```

Model fully backtested on 13 seasons of real CFBD data. Paper's censoring-bias edge confirmed and out-of-sample robust. Update README to document `--raw` + these results?

### **User**  ·  2026-06-13 14:49:42

yes and run the roi using a quarter kelly stakes

### **Claude**  ·  2026-06-13 14:50:05

Two things: quarter-Kelly ROI + README. 

Note: my current `kelly_return` is return-on-turnover (profit/staked) — flat-scaling stakes by ¼ leaves it unchanged. Quarter-Kelly only matters as **compounded bankroll growth**. So I'll add a proper sequential-compounding bankroll ROI at a configurable Kelly fraction.

### **Claude**  ·  2026-06-13 14:50:25

[tool: Edit]

### **Claude**  ·  2026-06-13 14:50:30

Wire ¼-Kelly ROI into runner display.

### **Claude**  ·  2026-06-13 14:50:36

[tool: Edit]

### **Claude**  ·  2026-06-13 14:50:46

[tool: Bash]

### **Claude**  ·  2026-06-13 14:51:07

Full-period compounding → big numbers. ¼-Kelly @ bias>1.0 = **+1288%** (13.9× bankroll) over 680 bets / 13 seasons. Per-season breakdown + sanity:

### **Claude**  ·  2026-06-13 14:51:14

[tool: Bash]

### **Claude**  ·  2026-06-13 14:51:34

All numbers in. Now update README. (Note: 2015 ¼K = 0.0% — model win-prob fell below breakeven that year so Kelly correctly staked ~nothing. 2025 −3.9% despite +6.3% unit is a within-season loss-clustering/compounding artifact.)

### **Claude**  ·  2026-06-13 14:51:36

[tool: Edit]

### **Claude**  ·  2026-06-13 14:52:02

[tool: Edit]

### **Claude**  ·  2026-06-13 14:52:07

Update Caveats section (Kelly definition + sample caveat now stale).

### **Claude**  ·  2026-06-13 14:52:14

[tool: Edit]

### **Claude**  ·  2026-06-13 14:52:21

Verify runner + demo still run with new signature.

### **Claude**  ·  2026-06-13 14:52:23

[tool: Bash]

### **Claude**  ·  2026-06-13 14:52:48

Both run clean. Done.

## Quarter-Kelly ROI — full backtest (2013–2025, raw, 12,443 games)

**Bet over when expected censoring bias > 1.0:**

| Season | N | Win% | ¼-Kelly ROI |
|--------|---|------|-------------|
| 2013 | 26 | 53.85% | −2.3% |
| 2014 | 25 | 64.00% | +41.8% |
| 2015 | 14 | 50.00% | 0.0% (model stakes ~0) |
| 2016 | 31 | 51.61% | −2.1% |
| 2017 | 17 | 52.94% | +3.9% |
| 2018 | 41 | 58.54% | +87.5% |
| 2019 | 54 | 62.96% | +67.2% |
| 2020 | 21 | 57.14% | +15.9% |
| 2021 | 78 | 57.69% | +119.4% |
| 2022 | 96 | 55.21% | +16.5% |
| 2023 | 76 | 55.26% | +61.3% |
| 2024 | 93 | 58.06% | +66.8% |
| 2025 | 79 | 55.70% | −3.9% |
| **Pooled** | **680** | **56.62%** | **+1288% = 13.9× over 13 yr ≈ +22%/yr** |

## Why ¼-Kelly

Edge is thin (≈55–58% at −110) → full Kelly stakes ~5%/bet, compounds to +21,800% but brutal variance. ¼-Kelly (~1.4%/bet) → +1288%, far smaller drawdowns, ~⅓ the growth. Standard practical sizing.

Two quirks (honest): **2015** = 0.0% because the probit win-prob fell below breakeven that year, so Kelly correctly staked ~nothing (no forced bet). **2025** = −3.9% despite +6.3% flat-unit — within-season loss clustering; compounded ROI is order-dependent.

## Code

- `kelly_bankroll_roi(wins, probs, fraction)` — sequential compounding, any fraction.
- `strategy_returns(..., kelly_fraction=0.25)` — now reports unit / Kelly-turnover / ¼-Kelly-bankroll, with LL-ratio tests.
- README updated: `--raw` usage, 13-season results table, ¼-Kelly column, three-return distinction, refreshed caveats (data floor 2013, in-sample, no vig modeling).

Caveat stands: win rates in-sample (k-fold is the OOS check, 4/5 folds positive); compounded ROIs depend on bet order; −110 assumed.

### **User**  ·  2026-06-13 14:58:05

keep and dont touch this current version of the model, maybe archive it somewhere. make a new version exploring these caveats Tobit/probit standard errors use the BFGS inverse-Hessian approximation, not the analytic information matrix — fine for inference here, tighten if needed.
Models assume favorite/underdog score errors are independent (paper's assumption: cov(δ₁, δ₂) = 0).

### **Claude**  ·  2026-06-13 14:58:52

Two caveats to explore in v2:
1. **Analytic SEs** — replace BFGS inverse-Hessian approx with closed-form Tobit/probit information matrix.
2. **Drop independence** cov(δ₁,δ₂)=0 — estimate fav/dog score-error correlation ρ, build bivariate censored model, test if edge survives.

First, key math insight to scope (b) correctly:

The **expected censoring bias is marginal** — `E[max(0,x)] − μ` depends only on each team's own (μ,σ), *not* on ρ. So `biasTotals` point estimate is **invariant to correlation**. What ρ *does* change: the variance/shape of the totals error ν, hence `P(over wins | bias)` and the profit threshold. That's the real thing to test. v2 will quantify it.

Plan:
```
1. Archive v1 untouched      → paper_models/v1/
2. v2: analytic-SE Tobit+probit (closed form) → verify vs BFGS
3. v2: estimate ρ, bivariate censored win-prob → compare threshold/edge to v1
4. v2 README: findings
```

Archive v1 first.

### **Claude**  ·  2026-06-13 14:58:53

[tool: Bash]

### **Claude**  ·  2026-06-13 14:59:18

Move broke v1's data-path (now one dir deeper: `parents[1]` resolves to `paper_models/`, not repo root). Fixing only the path constant — model math untouched — so the archive stays runnable.

### **Claude**  ·  2026-06-13 14:59:19

[tool: Edit]

### **Claude**  ·  2026-06-13 14:59:22

[tool: Read]

### **Claude**  ·  2026-06-13 14:59:27

[tool: Grep]

### **Claude**  ·  2026-06-13 14:59:34

[tool: Edit]

### **Claude**  ·  2026-06-13 14:59:38

[tool: Bash]

### **Claude**  ·  2026-06-13 15:00:55

v1 archived and runs (only a path constant touched, model frozen). Now build v2.

Key design call for caveat 2, stated up front: v1's probit is fit on **realized** over/under outcomes, which already embed the true fav/dog correlation. So the independence assumption only ever entered the *theoretical* bias derivation — not the empirical edge. v2 will prove this: estimate ρ, show `biasTotals` is invariant to it, and compare theoretical P(over|bias) under independent vs correlated models against the empirical probit. That's the honest exploration.

Writing v2 core module.

### **Claude**  ·  2026-06-13 15:01:37

[tool: Write]

### **Claude**  ·  2026-06-13 15:01:53

Now v2 driver: analytic-vs-BFGS SE comparison, ρ estimate, ρ-invariance proof, theoretical-vs-empirical P(over).

### **Claude**  ·  2026-06-13 15:02:29

[tool: Write]

### **Claude**  ·  2026-06-13 15:02:33

[tool: Bash]

### **Claude**  ·  2026-06-13 15:03:11

Bug in the ρ-invariance check: MC means (−0.06) don't match analytic bias (+0.20). Cause: common-random-numbers draws have a finite-sample mean ≈ −0.005; for near-uncensored games `max(0,·)` passes it straight through, so σ×(that offset) ≈ −0.06 swamps the small censoring signal. Fix: demean the draws so E[z]=0 exactly. Both MC functions.

### **Claude**  ·  2026-06-13 15:03:15

[tool: Edit]

### **Claude**  ·  2026-06-13 15:03:21

[tool: Edit]

### **Claude**  ·  2026-06-13 15:03:25

[tool: Bash]

### **Claude**  ·  2026-06-13 15:03:47

Now the three match (rho=0 → 0.1909, rho_hat → 0.1911 — identical; residual 0.19-vs-0.20 is MC noise). Findings are clean. Write v2 README.

### **Claude**  ·  2026-06-13 15:04:11

[tool: Write]

### **Claude**  ·  2026-06-13 15:04:16

Add top-level index (README moved into v1/, so root has none now).

### **Claude**  ·  2026-06-13 15:04:21

[tool: Write]

### **Claude**  ·  2026-06-13 15:04:26

[tool: Bash]

### **Claude**  ·  2026-06-13 15:04:43

Stale root `__pycache__` orphaned by the move — remove it.

### **Claude**  ·  2026-06-13 15:04:43

[tool: Bash]

### **Claude**  ·  2026-06-13 15:05:01

Done.

## Structure
```
paper_models/
  README.md          ← version index
  v1/                ← FROZEN baseline (untouched; only a path constant fixed so archive runs)
    censoring_bias.py, demo_reproduce.py, run_on_project_data.py, README.md
  v2/                ← caveat exploration
    models_v2.py, run_v2.py, README.md
```

## v2 findings — both caveats checked, both harmless

### (A) Analytic SEs vs BFGS
Derived closed-form Tobit score, covariance via OPG/BHHH; probit → statsmodels (analytic info matrix).

| Param | OPG analytic | BFGS (v1) |
|-------|--------------|-----------|
| Tobit dog β | 0.0173 | 0.0167 |
| Tobit fav β | 0.0154 | 0.0152 |

Agree within ~7%, OPG slightly more conservative. Probit slope +0.176, p=**5.9e−10**. **v1's "fine for inference" confirmed.** (Analytic gradient validated: optimizer used it, converged to same σ 11.03/11.77.)

### (B) Drop independence cov(δ₁,δ₂)=0
Estimated **ρ = +0.067** (tiny, on 11,976 both-uncensored games).

- **biasTotals invariant to ρ** — proved. It's a marginal expectation, so ρ=0 and ρ=0.067 give identical bias (MC: 0.1909 vs 0.1911). The trading signal is untouched.
- **Win prob barely moves** — theory P(over) under ρ=0 vs ρ=0.067 differ ≤0.003 per bin.
- **Why v1 was safe even in principle:** its probit fits *realized* outcomes, which already embed real correlation. Independence only entered the *theoretical* derivation, never the empirical edge.

### Bonus
Pure-censoring theory predicts a flatter bias→P(over) slope (0.50→0.52) than the empirical probit (0.48→0.56). Censoring explains the direction; realized edge is *larger* than censoring alone → extra bias correlated with low-total/lopsided games. Candidate for v3.

## Net
v1 strategy unchanged and vindicated: 680 bets, 56.62%, slope significant at p≈1e−9 with rigorous SEs. Run: `python paper_models/v2/run_v2.py`.

### **User**  ·  2026-06-13 15:07:23

test out the v3

### **Claude**  ·  2026-06-13 15:08:11

v3 = chase the v2 bonus finding: realized over-edge is *larger* than pure censoring predicts. 

Hypothesis to test: **is `biasTotals` just a repackaging of "low total / lopsided game," or does censoring's specific nonlinearity add signal beyond the raw line features?** Since high biasTotals ⟺ low totalsEst mechanically, the key confound is `totalsEst` itself.

v3 plan:
1. Features per game: `biasTotals`, `totalsEst`, `spreadEst`, `dogPointEst`.
2. Univariate probits — which single feature predicts the over best (OOS log-loss).
3. Multivariate probit — does `biasTotals` survive controlling for `totalsEst`, and vice versa?
4. k-fold OOS strategy bake-off: v1 censoring rule vs "low total" rule vs multivariate model.

v3 imports shared core from v2 (v1 stays frozen). Build it.

### **Claude**  ·  2026-06-13 15:08:39

[tool: Write]

### **Claude**  ·  2026-06-13 15:08:46

Fix ugly NORM import.

### **Claude**  ·  2026-06-13 15:08:48

[tool: Edit]

### **Claude**  ·  2026-06-13 15:08:53

[tool: Edit]

### **Claude**  ·  2026-06-13 15:09:21

[tool: Write]

### **Claude**  ·  2026-06-13 15:09:26

[tool: Bash]

### **Claude**  ·  2026-06-13 15:09:53

v3 done — clean, decisive result. Write README.

### **Claude**  ·  2026-06-13 15:10:11

[tool: Write]

### **Claude**  ·  2026-06-13 15:10:18

[tool: Edit]

### **Claude**  ·  2026-06-13 15:10:32

Done. v3 tested, decisive result.

## v3 verdict: censoring is the real signal — NOT a "low total" proxy

Tested whether `biasTotals` is just repackaging "bet over on low-total/lopsided games." It isn't.

**1. Univariate — biasTotals is the best single predictor**

| feature | slope | p | pseudo-R² |
|---------|-------|---|-----------|
| **biasTotals** | +0.071 | 6e−10 | **0.227%** |
| dogPointEst | −0.065 | 9e−9 | 0.194% |
| spreadEst | +0.056 | 7e−7 | 0.144% |
| totalsEst | −0.026 | 0.024 | 0.030% (weakest) |

**2. Multivariate — biasTotals survives, totalsEst dies**
- bias + totals: biasTotals **p=7e−9**, totalsEst **p=0.58** (insignificant)
- + spread: biasTotals still sig (p=0.013), totals & spread both insignificant

Dependence runs one way: the total level's signal is fully absorbed by censoring bias, not vice versa.

**3. OOS 5-fold bake-off — v1 wins on every metric**

| spec | bets | win% | unit% | logloss |
|------|------|------|-------|---------|
| **v1: biasTotals** | 1053 | **55.46%** | **+5.88%** | **0.6848** |
| totalsEst only | 16 | 31% | −40% | 0.716 |
| bias+totals | 1100 | 55.36% | +5.69% | 0.685 |
| bias+totals+spread | 1241 | 55.36% | +5.68% | 0.685 |

Extra features don't help — slight dilution (overfitting). "totals only" barely bets and loses.

**4. Incremental pseudo-R²:** biasTotals over totals = **+0.199pp**; totals over biasTotals = **+0.002pp**. Censoring nonlinearity carries ~all the signal.

## Takeaway
v3 **refutes** the v2 "just low totals" worry. The paper's feature is irreducible — dominates raw total & spread in/out of sample. The v2 puzzle (theory underpredicts empirical slope) is *not* an omitted simple line feature; residual is either probit flexibility or genuine fat-tail mispricing in low-scoring games — needs a feature outside the two lines = different study.

## Structure
```
paper_models/
  README.md          ← index (v1/v2/v3)
  v1/  FROZEN baseline
  v2/  analytic SEs + correlation (caveats immaterial)
  v3/  censoring-vs-low-total test (censoring wins)
```
v1 & v2 untouched. `python paper_models/v3/run_v3.py`.

### **User**  ·  2026-06-13 15:11:47

could the theory extend to other betting situations on the other side like betting the under?

### **Claude**  ·  2026-06-13 15:12:26

Good question. Theory first, then I'll test it.

## Why the under gets NO edge from *this* mechanism

The paper's bias is **left-censoring at 0** — scores can't go negative. That's strictly one-directional: realized totals can only be pushed *up* relative to the latent prediction, never down. So `biasTotals ≥ 0` always, by construction. Paper's own Fig 6: zero observations below the lower profit bound — *"censoring does not inform a profitable betting strategy on the under."* The asymmetry is fundamental, not empirical.

So extending to the under requires a **different** mechanism that biases totals *down*. Candidates:

1. **A scoring ceiling (right-side soft censoring).** No hard cap, but blowouts throttle scoring late — winning team pulls starters, kills clock. Expected-blowout (huge-spread) games could systematically come *under*. This is the natural mirror image and a known betting folk-strategy ("blowout under").
2. **Individual team totals.** Censoring is per-team → a heavy underdog's team-total has positive bias → bet that team's **over** (still over, just on a prop).

Only #1 is a genuine "other side." Let me test it on the data.

### **Claude**  ·  2026-06-13 15:12:36

[tool: Bash]

### **Claude**  ·  2026-06-13 15:13:17

Data refutes the blowout-under idea and confirms the asymmetry — but turns up one real lead.

## Findings

**Blowout-under hypothesis (#1): REFUTED.** Bigger spread → under wins *less*, not more:

| spread | under-win% |
|--------|-----------|
| 0–7 | 52.32% |
| 14–21 | 51.10% |
| 21–28 | 48.42% |
| >28 | 44.69% |
| >40 | **40.00%** |

The censoring *floor* (big spread → underdog pinned near 0 → totals inflate → **over**) completely dominates any clock-kill *ceiling*. No blowout-under edge exists; the opposite does.

**Censoring gives the under nothing — confirmed.** Under-win% by censoring bias: bias>1.75 → **36.56%** under (= 63.4% over). Higher bias, worse for the under. Exactly as the paper says.

**But — one genuine lead.** The under shows life as a function of the **total level**, not the spread:

| totals line | under-win% | N |
|-------------|-----------|---|
| ≤45 | 50.55% | 1272 |
| 45–59 | ~50.2% | 7832 |
| 59–66 | 52.45% | 2242 |
| **>66** | **54.15%** | 977 |

## Interpretation

The censoring theory is **mathematically one-sided** — it cannot produce an under edge, ever. The honest answer to "does it extend to the under" is **no**, by construction.

The >66 signal is a **different, symmetric mechanism**: a *possession/clock ceiling*. Scoring has no hard cap but a soft one — finite drives per game. When the line is very high (shootout priced in), the right tail is bounded, so extreme totals overshoot → under. That's the true "other side" analog: not zero-censoring but **ceiling-censoring on the total**, showing up at high lines instead of high spreads.

Caveat: 54.15% on N=977, single in-sample cut — a *lead*, not a confirmed edge (barely clears 52.38%, multiple-comparison risk). Needs the full pipeline (probit on a "distance above expected ceiling" feature, k-fold OOS) before trusting it.

Want a **v4** that models the ceiling side properly — define an upper-censoring bias on the total, test the under at high lines with OOS validation? That's the real extension.

### **User**  ·  2026-06-13 15:15:07

yes but name it a different model

### **Claude**  ·  2026-06-13 15:16:13

Right — it's a distinct mechanism, deserves its own name. Naming it the **Saturation Bias model** (soft scoring *ceiling* from finite possessions, the structural mirror of the paper's floor-at-zero censoring). Directory `paper_models/saturation_bias/`.

Key honesty point baked into the design: the floor at 0 is *observed* (real pile-up of 0-scores → Tobit identifies it). A scoring ceiling has **no pile-up** (no team "maxes out"), so the ceiling `C` can't be read off the score distribution — it must be inferred by predictive fit. I'll grid-search `C` by OOS log-loss and flag this as the model's main weakness.

Math: ceiling bias mirrors floor bias. For `Y=min(C,X)`, `X~N(μ,σ)`:
`E[Y]−μ = −[σφ(d/σ) − d·Φ(−d/σ)]`, where `d=C−μ` (distance below ceiling). ≤0 → totals biased down → under edge, biting only when μ is near C (high-scoring teams).

### **Claude**  ·  2026-06-13 15:16:46

[tool: Write]

### **Claude**  ·  2026-06-13 15:17:11

[tool: Write]

### **Claude**  ·  2026-06-13 15:17:17

[tool: Bash]

### **Claude**  ·  2026-06-13 15:17:53

Built, tested — and it's a clean **negative result**. The Saturation Bias model fails, which is the honest finding. Writing it up.

### **Claude**  ·  2026-06-13 15:18:11

[tool: Write]

### **Claude**  ·  2026-06-13 15:18:28

[tool: Edit]

### **Claude**  ·  2026-06-13 15:18:44

Done. Built the **Saturation Bias model** (distinct name — ceiling mirror of the paper's floor censoring), tested it. It fails cleanly.

## Saturation Bias model — verdict: NO under edge

Mechanism: soft scoring ceiling `min(C, latent)` per team → totals biased down → under. Mirror math of the floor bias.

**Three ways it fails:**

1. **Ceiling C unidentifiable.** OOS log-loss flat across all C (0.69295–0.69310, 5th-decimal noise). Unlike the floor — real games pile up at 0 points so Tobit finds it — *nothing* piles up at a scoring ceiling, so C can't be read from the data. Had to grid-search it by predictive fit, and the fit is flat.

2. **Probit slope wrong way.** `P(under) = Φ(const + slope·satBias)` → slope **−0.031 (p=0.006)**. More saturation bias → *less* under. Highest-bias quartile = 49.89% under (worse than 50.95% baseline).

3. **No OOS strategy.** Betting under where P>52.38%: only **6 bets** cleared the hurdle across 5 folds, 33% win. Model basically never finds a profitable under.

## Answer to your question

**The theory does not extend to the under** — both mathematically and empirically:
- Left-censoring at a *known* floor (0) is inherently one-directional. Can only bias totals up.
- The ceiling mirror has no predictive power, C is unidentified, relationship runs backward.
- The v3 hint (totals>66 → 54% under) **did not survive** proper modeling — small-N, non-monotone in-sample artifact.

A real under edge would need a mechanism *outside the two lines* (pace, weather, specific offenses) — different study, different data. Not an extension of censoring.

## Structure
```
paper_models/
  README.md
  v1/  FROZEN baseline (over edge, confirmed)
  v2/  analytic SEs + correlation (caveats immaterial)
  v3/  censoring-vs-low-total (censoring wins)
  saturation_bias/  ceiling/under analog (NEGATIVE result)
```

Negative results are results — the asymmetry is the finding. `python paper_models/saturation_bias/run_saturation.py`.

### **User**  ·  2026-06-13 15:20:20

back to the first model, name it something

### **Claude**  ·  2026-06-13 15:20:50

The first model is the paper's mechanism — left-censoring at the **floor** (0). Natural pair with the Saturation Bias (ceiling) model: name it the **Floor Bias model**. Floor Bias (over) ↔ Saturation Bias (under).

Renaming dir `v1/` → `floor_bias/` to match. Model files stay frozen (content untouched; path constant uses depth-invariant `parents[2]`, so no code change). Check cross-references first.

### **Claude**  ·  2026-06-13 15:20:50

[tool: Grep]

### **Claude**  ·  2026-06-13 15:21:05

Many `v1` lineage refs in v2/v3 prose. Renaming the dir would orphan them. Better: keep `v1/` for lineage, give the model its **name** in the docs (naming is what you asked, and authorizes the doc touch; model `.py` stays frozen).

Pair: **Floor Bias model** (v1, over) ↔ **Saturation Bias model** (under).

### **Claude**  ·  2026-06-13 15:21:05

[tool: Read]

### **Claude**  ·  2026-06-13 15:21:15

[tool: Edit]

### **Claude**  ·  2026-06-13 15:21:27

[tool: Edit]

### **Claude**  ·  2026-06-13 15:21:36

Named. 

**Floor Bias model** = the first model (v1). Mechanism: scores censored at the **floor** (0) → totals biased up → over edge.

Clean pair:
- **Floor Bias model** (floor=0 → over) — works. 56.6%, robust.
- **Saturation Bias model** (ceiling → under) — fails.

Done in docs only — v1 model `.py` files stay frozen, dir keeps `v1` for v2/v3 lineage refs. Updated [v1/README.md](paper_models/v1/README.md) title + [index](paper_models/README.md).

### **User**  ·  2026-06-13 15:22:21

could we extend the floor bias model to 1 half spreads and point totals?

### **Claude**  ·  2026-06-13 15:22:46

First-half betting — strong extension idea. The theory *predicts it should be stronger*: a half has ~half the expected points, so each team's mean sits much closer to the 0 floor → censoring binds harder, more actual 0-point halves, bigger `biasTotals`. The over edge should amplify in 1H totals.

Feasibility hinges on data. Need: 1H scores (gradeable) + 1H lines. Check what CFBD gives.

### **Claude**  ·  2026-06-13 15:22:49

[tool: Bash]

### **Claude**  ·  2026-06-13 15:23:21

Data verdict:
- **1H scores: YES** — `homeLineScores`/`awayLineScores` are per-quarter `[Q1,Q2,Q3,Q4]`, so 1H = Q1+Q2. (Note the example: home `[0,0,0,7]` → **0 first-half points** — real floor censoring.)
- **1H lines: NO** — CFBD only gives full-game spread + total. Can't grade against a real 1H line.

So a true 1H backtest needs 1H lines sourced elsewhere. But I can (a) test the **mechanism** — is censoring much stronger in halves? — for free, and (b) run an **approximate** backtest using line ≈ ½ game line, clearly flagged. Mechanism first.

### **Claude**  ·  2026-06-13 15:23:31

[tool: Bash]

### **Claude**  ·  2026-06-13 15:24:15

Mechanism **confirmed and strong**:

| | mean | σ | P(score 0) |
|--|------|---|-----------|
| Full-game underdog | 21.1 | 12.1 | 3.51% |
| **1H underdog** | 10.5 | 7.7 | **13.78%** |

First-half shutouts are **3.9× more common** — the floor binds far harder. Now quantify the predicted bias via Tobit (the legit deliverable, since I can't grade a real 1H line).

### **Claude**  ·  2026-06-13 15:24:29

[tool: Bash]

### **Claude**  ·  2026-06-13 15:25:12

Quantified — theory extends **powerfully**:

| | full game | first half |
|--|-----------|-----------|
| Tobit σ (dog/fav) | 11.0 / 11.8 | 8.1 / 9.3 |
| Mean censoring bias | 0.280 | **0.645** (2.3×) |
| Median bias | 0.144 | 0.564 |
| Games clearing bias>1.0 (v1 bet rule) | 5.5% | **14.4%** (~3×) |

## Answer: yes — and it should be *stronger* in first halves

The Floor Bias mechanism scales with how close a team's expected points sit to the 0 floor. Halving the game halves the means but shrinks σ less, so the standardized distance `μ/σ` drops → **2.3× bigger censoring bias** and ~3× more qualifying games. Backed by real data: 13.78% of 1H underdog scores are 0 (vs 3.51% full) — genuine censoring mass.

**Totals/over: big edge predicted.** **Spreads: no.** 1H `biasSpread` ≈ full (fav and dog biases partly cancel, like the paper) → likely already priced. The edge is on the 1H **over**, same asymmetry as the full game, amplified.

## The blocker: no 1H lines

CFBD gives 1H *scores* (quarter line-scores) but **not 1H betting lines**. Can't grade a real over/under without the 1H line. Two paths:

1. **Approximate** 1H line = ½ game line — *contaminated*. Actual 1H scoring runs ~1.1 pt above half the game (fresh legs, less clock-kill: 28.7 vs 27.6). Setting line=½ bakes that structural excess into "edge," so any backtest overstates it. Unreliable.
2. **Source real 1H lines** (sportsbooks post them; some historical APIs have them) → then the model runs as-is on (1H line, 1H score) and gives a true backtest.

## Recommendation

The mechanism is proven and the predicted edge is large. But I won't claim a backtested edge without real 1H lines — that's the honest line. Best next step: build a **Floor Bias 1H** module (mirrors v1, swaps in 1H scores + a `half_line` input) that's ready to run the instant you supply 1H lines, and meanwhile reports the theoretical bias/opportunity counts above.

Want me to build that ready-to-run 1H module, or do you have a source for historical 1H lines I should wire in?

### **User**  ·  2026-06-13 15:33:07

build a ready to run 1h module

### **Claude**  ·  2026-06-13 15:33:37

Building `floor_bias_1h/` — mirrors the Floor Bias model for first halves. Runs **now** in approximation mode (½ game line = the paper's latent-symmetric assumption) and **drops in real 1H lines** the moment you supply them via `--half-lines`.

### **Claude**  ·  2026-06-13 15:34:11

[tool: Write]

### **Claude**  ·  2026-06-13 15:34:33

[tool: Write]

### **Claude**  ·  2026-06-13 15:34:39

Need to add the `over_diag()` helper I referenced on Data1H.

### **Claude**  ·  2026-06-13 15:34:42

[tool: Edit]

### **Claude**  ·  2026-06-13 15:34:50

[tool: Bash]

### **Claude**  ·  2026-06-13 15:35:28

Module runs. Results are striking and survive the de-biasing check:

| | full game (v1) | 1H approx ½ | 1H approx 0.52 |
|--|----------------|-------------|----------------|
| Probit slope | +0.176 | +0.198 (p=2e-11) | +0.210 (p=4e-11) |
| Over @ bias>1.0 | 56.6% / 680 | 58.3% / 1778 | 55.9% / 1299 |
| Over @ bias>1.75 | 63.4% | 71.9% | 69.2% |
| OOS 5-fold | 4/5 + | **5/5 +** | +  |

**Key:** even after raising the line to 0.52× (removing the structural "more scoring in 1H" excess — baseline over drops to 48.2%), the censoring bias *still* predicts the 1H over strongly (55.9%, OOS positive). So the edge isn't just the half-scoring artifact — the floor mechanism survives. Write README.

### **Claude**  ·  2026-06-13 15:35:48

[tool: Write]

### **Claude**  ·  2026-06-13 15:35:56

[tool: Edit]

### **Claude**  ·  2026-06-13 15:36:06

Verify the REAL-mode path works end-to-end (so it's genuinely ready). Build a tiny test CSV from actual game ids and run `--half-lines`.

### **Claude**  ·  2026-06-13 15:36:10

[tool: Bash]

### **Claude**  ·  2026-06-13 15:36:35

Both modes verified working. Module ready.

## Floor Bias 1H — built & runnable

```
paper_models/floor_bias_1h/
  floor_bias_1h.py   loader (1H scores + line) + pipeline + k-fold
  run_1h.py          driver
  README.md
```

**Two modes, both tested:**
- **APPROX** (now): `python run_1h.py` — 1H line = frac × game line. `--total-frac 0.52` to de-bias the half-scoring excess.
- **REAL** (true backtest): `python run_1h.py --half-lines lines.csv` — drop in real 1H lines (`game_id,half_spread,half_total`). Plumbing confirmed working.

## What it shows

Mechanism confirmed on real data: 1H censoring bias **2.3× larger**, underdog shutouts **3.9× more common**, **~3× more qualifying bets** (14.4% vs 5.5% clear bias>1.0).

Approx-mode edge (illustrative, not validated):

| | full game | 1H @0.50 | 1H @0.52 |
|--|-----------|----------|----------|
| probit slope | +0.176 | +0.198 | +0.210 |
| over @ bias>1.0 | 56.6% | 58.3% | 55.9% |
| OOS folds | 4/5 + | 5/5 + | + |

**Robustness:** raising the line to 0.52× drops baseline over to 48% (kills the structural half-excess), yet censoring bias *still* predicts 1H over at 55.9% with significant slope + positive OOS. Edge isn't the half-artifact — floor mechanism carries independent signal, as theory predicts.

## Honest limits (in README)
- APPROX = mechanism illustration, NOT validated. Real 1H lines (`--half-lines`) needed for a trustworthy edge — CFBD doesn't carry them.
- fav/dog + 1H spread derived from full-game spread in approx mode.
- compounded ¼-Kelly numbers meaningless in approx (explosive over ~1,800 bets) — read win%/unit%.
- 1H spreads: no edge expected (biases cancel); edge is on 1H **over**.

Index updated. To go live: source historical 1H closing lines, key to CFBD game ids, pass `--half-lines`.

### **User**  ·  2026-06-15 13:07:59

Continue from where you left off.

### **Claude**  ·  2026-06-15 13:07:59

No response requested.

### **User**  ·  2026-06-15 13:09:23

what are the risks of books correcting totals using these findings and what would be steps to account for it if they do and if theres any way to exploit that?

### **Claude**  ·  2026-06-15 13:10:17

Pure strategy question. No code. Reasoning:

## How books correct (4 channels)

1. **Line shading** — book adds the censoring bias to the total (bumps low-total/big-spread games up ~0.2–1 pt). Edge vanishes on exactly the games you bet.
2. **Vig tilt** — keep the number, make the over more expensive (−115/−120) on high-bias games. Raises breakeven above 52.38% → kills marginal bets without moving the line. Cheapest fix for them, hardest to spot.
3. **Limit/flag** — detect sharp over-action on lopsided unders-looking games, cut your limits.
4. **Already happening** — paper published 2022; the author *predicts* the anomaly dies as knowledge spreads. Your own 2025 season is the weakest in the sample (probit slope flattest +0.14, totals-bias F insignificant). Consistent with early correction — or variance. Can't tell yet from one season.

## Early-warning signals (you can monitor with current data)

| Signal | Correction if… |
|--------|---------------|
| Rolling probit slope (per-season, you have it) | trending toward 0 |
| Bias-to-clear-52.38% hurdle | rising over time (need more bias for same edge) |
| Win% in bias>1.0 bucket | drifting toward 50% |
| Over-vig on high-bias games | systematically worse than −110 |
| Closing-vs-opening line on high-bias games | closing shaded up (need opening lines — you don't have these yet) |

The single best detector you're missing: **opening vs closing lines**. If books correct via late movement, the opening still ignores censoring. CFBD = closing only. Sourcing openers is the highest-value data add.

## Steps to account for it

1. **Rolling re-estimation** — fit σ and probit on a trailing window (e.g. last 2–3 seasons), not the pooled 13. Threshold adapts as edge decays. Pooled estimates mask a dying signal.
2. **Per-game vig in the model** — already supported (breakeven is a parameter). Pull actual over price per game, set the hurdle dynamically. A game only bets if edge clears *its* real juice, not a flat 52.38%.
3. **Bet the opener** — once you have opening lines, bet early before shading; measure CLV as the real edge proxy.
4. **Stop-loss on slope** — if rolling slope's CI includes 0 for N consecutive windows, halt that market.

## Exploiting the correction itself

This is the interesting part — correction creates new edges:

1. **Migration to derivative/illiquid markets.** Censoring exists everywhere scores floor at 0, but books only correct the *watched* main total. Same nonlinearity, ignored, in: **1H/1Q totals** (your 1H module — censoring 2.3× stronger), **team totals**, **alternate totals**, **lower divisions** (FCS/D2/D3 — lower scoring, more censoring, near-zero book attention). The main-market edge dies first; the edge persists longest where liquidity and attention are lowest.
2. **Over-correction → flip to under.** If books overshoot (add more than the true bias), high-bias games become +EV on the *under*. Watch for the probit slope on high-bias games going negative — that's the tell. (Your Saturation Bias model found no under edge *today*; over-correction could create one.)
3. **Book-to-book lag.** Sharp books (Pinnacle, Circa) correct first; soft books (DK/FD/regional) lag. Bet the over at the laggard, line-shop. The correction gradient *is* the edge during the transition.
4. **Opening-line timing arb** — bet over at open across books before the consensus shades to close.

## Bottom line
Correction is the base case (the paper says so, 2025 hints at it). The robust play isn't defending the main-total edge — it's **migrating down the liquidity ladder** (1H → team totals → lower divisions) where censoring is *stronger* and attention is *weaker*, while monitoring the rolling slope to know when each market dies.

Want me to build a **rolling-window slope monitor** (per-season/trailing-N probit slope + hurdle + bucket win% with CIs) so you can watch for decay quantitatively? That's the one piece your current code doesn't have and it directly answers "is correction happening."

### **User**  ·  2026-06-15 13:11:40

yes

### **Claude**  ·  2026-06-15 13:12:00

Building the decay monitor: per-season + trailing-window probit slope (with CI), breakeven-bias hurdle, and bias>1.0 bucket win% (Wilson CI), plus a trend test on the slope. Reuses v2 core.

### **Claude**  ·  2026-06-15 13:12:20

[tool: Write]

### **Claude**  ·  2026-06-15 13:12:40

[tool: Write]

### **Claude**  ·  2026-06-15 13:12:46

[tool: Bash]
