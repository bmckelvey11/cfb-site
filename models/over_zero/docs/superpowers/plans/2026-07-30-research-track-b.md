# Research Track B Implementation Plan (MODEL_GUIDE §9.B)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the five ranked research items from `docs/MODEL_GUIDE.md` §9 track B — 1H lines backtest, dog team-total backtest, multi-snapshot odds capture, residual-feature probit, hierarchical team σ — each producing a written, uncertainty-quantified result (positive OR negative).

**Architecture:** Five independent phases. Each phase lives in its own `research/bN_*/` directory, reuses the existing estimator core in `v2/models_v2.py` (never reimplements it), and ends with a `RESULTS.md` containing verbatim command output. Phases B1–B3 begin with a data hunt that can legitimately end in "blocked — no data"; that is a valid deliverable, recorded in `research/BLOCKERS.md`.

**Tech Stack:** Python 3.14, numpy, scipy, statsmodels (already in `requirements.txt`). Standard library only for HTTP (`urllib.request`) — do NOT add dependencies.

## Global Constraints

- **`v1/` is frozen.** Never modify any file under `v1/`.
- **Never modify** `v2/models_v2.py`, `monitor/monitor.py`, `monitor/run_walkforward.py`, or any existing driver. All new code goes under `research/`.
- **Reuse, don't reimplement.** Estimators come from `v2/models_v2.py` via the sys.path shim (exact block in Interfaces below). If you find yourself writing a Tobit likelihood or a probit fit by hand, stop — you are off-plan.
- **Prespecified analyses only.** Every threshold, feature list, and hyperparameter in this plan is fixed BEFORE seeing results. Do not tune thresholds, drop features, re-bin, or re-run with different seeds because a result "looks wrong." Running exactly what the plan says and reporting the number is the job.
- **Every number reported carries uncertainty.** Win rates get Wilson 95% CIs (`monitor._wilson`); probit coefficients get SEs and p-values with `groups=` season clustering; forecast comparisons get a CI on the difference.
- **Negative results are deliverables.** "No edge," "wrong sign," and "not enough data" go into RESULTS.md with the same care as positive results.
- **Data acquisition rules:** no purchases without owner approval; no scraping that violates a source's ToS; API keys come from environment variables and are NEVER written to any file or committed. If a source requires payment or a key you don't have, record it in `research/BLOCKERS.md` and stop that phase.
- **Escalation protocol:** any decision this plan does not answer → append a dated entry to `research/BLOCKERS.md` (what you were doing, what's ambiguous, what you recommend), stop that phase, continue with the next phase. Never guess.
- **Commit after every task** with the message given in the task. Do not push (no remote configured).
- **Data dependency:** all loaders read the sibling checkout `../cfb-site/data/raw/` (relative to the repo root `paper_models/`). Verify it exists before starting (Task 0).

## Interfaces (used by every phase)

The sys.path shim — copy verbatim at the top of every `research/` script
(paths are relative to the script sitting in `research/bN_name/`):

```python
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]          # .../paper_models
sys.path.insert(0, str(REPO / "v2"))
sys.path.insert(0, str(REPO / "monitor"))
```

Available functions (exact signatures — do not modify their modules):

```python
# from models_v2 import ...
load_raw_seasons(seasons, raw_dir=RAW_DIR, provider=None)
    # -> dict[int season -> (spread_est, totals_est, fav_pts, dog_pts)], np arrays
load_from_raw(seasons, raw_dir=RAW_DIR, provider=None)
    # -> (spread_est, totals_est, fav_pts, dog_pts) flat pooled arrays
pick_line(game_dict, provider=None)          # -> (spread, total) or None
implied_team_points(spread_est, totals_est)  # -> (dog_est, fav_est)
tobit_left_censored_v2(y, x, censor=0.0)     # -> TobitFitV2; use .sigma
censoring_bias(dog_est, fav_est, sigma_dog, sigma_fav)
    # -> (bias_spread, bias_totals)
_team_censor_bias(mu, sigma)                 # -> per-team bias array (dog-only work)
probit_win_v2(win, bias, groups=None)        # -> ProbitFitV2; .win_prob(x),
    # .const, .slope, .se_slope, .pvalue_slope; groups=season array -> clustered SEs
log_likelihood_ratio(n_wins, n_total, q=0.5) # -> (stat, pvalue)

# from monitor import ...
_wilson(wins, n, z=1.96)                     # -> (lo, hi) 95% CI on a proportion

# from run_walkforward import ...
fit_train(se, te, fp, dp)                    # -> (sigma_dog, sigma_fav, probit)
```

Raw data files (per season, in `../cfb-site/data/raw/`):
- `lines_{season}.json` — list of games: `id`, `homeScore`, `awayScore`,
  `lines` (list of books: `provider`, `spread` home-relative, `overUnder`).
- `games_{season}.json` — list of games: `id`, `homeLineScores`,
  `awayLineScores` (per-quarter), plus other fields inventoried in B4 Task 1.

Reference constants: breakeven at −110 = 0.5238; trained pooled values for
sanity checks: σ_dog ≈ 11.03, σ_fav ≈ 11.78, probit slope ≈ +0.176.

---

### Task 0: Environment check (run once, before any phase)

**Files:** none created.

- [ ] **Step 1: Verify data + estimator chain**

Run from the repo root `paper_models/`:

```bash
ls ../cfb-site/data/raw/lines_2024.json && python v1/demo_reproduce.py
```

Expected: the file lists, and the demo ends with
`SELF-TEST OK: sigmas recovered, probit slope positive, hurdle sane.`

- [ ] **Step 2: Create the research scaffold**

```bash
mkdir -p research
```

Create `research/BLOCKERS.md` with exactly:

```markdown
# Blockers log

Dated entries. Format: `## YYYY-MM-DD — <phase>` then what was attempted,
what is blocked, and a recommendation.
```

- [ ] **Step 3: Commit**

```bash
git add research/BLOCKERS.md
git commit -m "research: scaffold blockers log"
```

---

## Phase B1 — First-half lines backtest (resolves open question 2)

The model code is DONE (`floor_bias_1h/run_1h.py --half-lines file.csv`).
This phase is: find real historical 1H closing lines, convert them to the
expected CSV, validate, run.

### Task B1.1: Source survey

**Files:**
- Create: `research/b1_first_half/SOURCES.md`

- [ ] **Step 1: Check whether CFBD raw data already carries 1H markets**

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

Record the printed key list in SOURCES.md. If any key looks first-half
related (e.g. `spreadFirstHalf`, `overUnderFirstHalf`, `period`), note it
and check how many games have it non-null — that would be the cheapest
source of all.

- [ ] **Step 2: Survey external sources**

Investigate each candidate IN THIS ORDER, spending no more than ~20 minutes
each. For each, record in SOURCES.md: coverage (seasons), does it have BOTH
1H spread and 1H total, file format, join key available (team names/date?),
cost, terms-of-use verdict.

1. sportsbookreviewsonline.com historical odds workbooks (free Excel; check
   whether NCAAF files include 2H/1H columns)
2. Kaggle datasets (search "college football odds first half")
3. the-odds-api.com historical endpoint (paid tiers; note price)
4. SportsDataIO / Unabated / OddsJam historical archives (note price)

- [ ] **Step 3: Write the verdict**

End SOURCES.md with one of:
- `VERDICT: acquire from <source>` (free + permitted) → continue to B1.2, or
- `VERDICT: blocked` → copy the verdict and the price of the cheapest paid
  option into `research/BLOCKERS.md`, commit, and END THIS PHASE.

- [ ] **Step 4: Commit**

```bash
git add research/b1_first_half/SOURCES.md
git commit -m "research(b1): 1H line source survey"
```

### Task B1.2: Convert acquired data to the model's CSV

**Files:**
- Create: `research/b1_first_half/convert.py`
- Create: `research/b1_first_half/half_lines.csv` (generated)

**Interfaces:**
- Produces: `half_lines.csv` with header `game_id,half_spread,half_total`,
  one row per game; `game_id` = CFBD id from `lines_{season}.json`;
  `half_spread` home-relative (negative = home favored), matching the
  full-game convention in the raw files.

- [ ] **Step 1: Write the converter**

The source format is unknown until B1.1 — the fixed part is the OUTPUT
contract and the JOIN. Use this skeleton; fill only the `read_source` body:

```python
"""Convert acquired 1H lines to half_lines.csv (game_id,half_spread,half_total)."""
import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RAW = REPO.parent / "cfb-site" / "data" / "raw"


def norm(name):
    """Team-name join key: lowercase alphanumerics only."""
    return "".join(c for c in str(name).lower() if c.isalnum())


def cfbd_index(seasons):
    """(season, norm(home), norm(away)) -> game_id from lines_{season}.json."""
    idx = {}
    for season in seasons:
        p = RAW / f"lines_{season}.json"
        if not p.exists():
            continue
        for g in json.loads(p.read_text(encoding="utf-8")):
            idx[(season, norm(g.get("homeTeam", "")), norm(g.get("awayTeam", "")))] = g["id"]
    return idx


def read_source():
    """YIELD (season, home_name, away_name, half_spread, half_total).
    Fill in per the acquired format. half_spread home-relative."""
    raise NotImplementedError("fill in for the acquired source format")


def main():
    seasons = range(2013, 2026)
    idx = cfbd_index(seasons)
    rows, misses = [], 0
    for season, home, away, hs, ht in read_source():
        gid = idx.get((season, norm(home), norm(away)))
        if gid is None:
            misses += 1
            continue
        rows.append((gid, float(hs), float(ht)))
    out = Path(__file__).parent / "half_lines.csv"
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["game_id", "half_spread", "half_total"])
        w.writerows(rows)
    total = len(rows) + misses
    print(f"wrote {len(rows):,} rows, {misses:,} unmatched "
          f"({misses / max(total, 1) * 100:.1f}% miss rate)")
    assert rows, "no rows converted"
    assert misses / max(total, 1) < 0.10, "join miss rate over 10% -- fix norm()/names, do not proceed"


if __name__ == "__main__":
    main()
```

If `lines_{season}.json` turns out not to carry `homeTeam`/`awayTeam` keys
(check with B4 Task 1's inventory command), join through
`games_{season}.json` instead (it has the same `id`). If neither file has
team names, log to BLOCKERS.md and stop the phase.

- [ ] **Step 2: Run it**

```bash
python research/b1_first_half/convert.py
```

Expected: `wrote N rows` with miss rate < 10% and no assertion failure.

- [ ] **Step 3: Spot-check 5 rows by hand**

Pick 5 random rows from half_lines.csv; for each, find the game in
`lines_{season}.json` by id and confirm the matchup is the one the source
listed (right game, right season). Record the 5 checked ids in SOURCES.md.

- [ ] **Step 4: Commit**

```bash
git add research/b1_first_half/convert.py research/b1_first_half/half_lines.csv research/b1_first_half/SOURCES.md
git commit -m "research(b1): convert 1H lines to model CSV"
```

### Task B1.3: Validate the CSV

**Files:**
- Create: `research/b1_first_half/validate.py`

- [ ] **Step 1: Write the validator**

```python
"""Schema + sanity validation for half_lines.csv. Exits nonzero on failure."""
import csv
from pathlib import Path

path = Path(__file__).parent / "half_lines.csv"
n = bad_spread = bad_total = 0
with open(path, newline="", encoding="utf-8") as fh:
    r = csv.DictReader(fh)
    assert r.fieldnames == ["game_id", "half_spread", "half_total"], r.fieldnames
    for row in r:
        n += 1
        hs, ht = float(row["half_spread"]), float(row["half_total"])
        if not (-40 <= hs <= 40):
            bad_spread += 1
        if not (10 <= ht <= 60):
            bad_total += 1
print(f"{n:,} rows; spread out of [-40,40]: {bad_spread}; total out of [10,60]: {bad_total}")
assert n >= 500, "under 500 rows -- too thin to backtest, log to BLOCKERS.md"
assert bad_spread / n < 0.01 and bad_total / n < 0.01, "over 1% out-of-range -- inspect source parsing"
print("VALIDATION OK")
```

- [ ] **Step 2: Run it**

```bash
python research/b1_first_half/validate.py
```

Expected: `VALIDATION OK`.

- [ ] **Step 3: Commit**

```bash
git add research/b1_first_half/validate.py
git commit -m "research(b1): validate 1H lines CSV"
```

### Task B1.4: Run the real-lines backtest and write results

**Files:**
- Create: `research/b1_first_half/RESULTS.md`

- [ ] **Step 1: Run the existing driver in REAL mode**

```bash
python floor_bias_1h/run_1h.py --half-lines research/b1_first_half/half_lines.csv
```

Expected: header says `1H line source: real` (NOT the APPROX warning).
Copy the ENTIRE output verbatim into RESULTS.md.

- [ ] **Step 2: Interpret with this fixed checklist (answer each in RESULTS.md)**

1. Probit slope on 1H biasTotals: sign, SE, p. Positive and p < 0.05?
2. In-sample win% at bias > 1.0 and > 1.75 with N — above 52.38%?
3. 5-fold OOS rows: how many of 5 folds positive?
4. Compare against approx-mode expectations in `floor_bias_1h/README.md`
   (slope ≈ +0.20, over @ bias>1.0 ≈ 56–58%): same ballpark, stronger, or
   absent?
5. One-paragraph verdict: `EDGE CONFIRMED ON REAL 1H LINES` /
   `NO EDGE ON REAL 1H LINES` / `INCONCLUSIVE (n too small)` — n is "too
   small" only if the bias>1.0 bucket has fewer than 200 bets.

- [ ] **Step 3: Note the follow-up (do NOT build it)**

Add to RESULTS.md: "If confirmed, a season walk-forward variant of this
backtest is the next validation step — needs owner sign-off (new code)."

- [ ] **Step 4: Commit**

```bash
git add research/b1_first_half/RESULTS.md
git commit -m "research(b1): real 1H lines backtest results"
```

---

## Phase B2 — Dog team-total backtest (resolves open question 3)

Bet studied: OVER on the *underdog's team total*, where the censoring
mechanism lives undiluted. Blocked on finding a team-totals line history.

### Task B2.1: Source survey

**Files:**
- Create: `research/b2_team_totals/SOURCES.md`

- [ ] **Step 1: Survey** (same procedure and time-box as B1.1; team totals
  are rarer — likely paid): the-odds-api historical, SportsDataIO, Unabated,
  OddsJam, Kaggle. Record coverage/format/join-key/cost/ToS per source.
- [ ] **Step 2: Verdict** — `acquire from <source>` or `blocked` (→
  BLOCKERS.md, end phase).
- [ ] **Step 3: Commit**

```bash
git add research/b2_team_totals/SOURCES.md
git commit -m "research(b2): team-totals source survey"
```

### Task B2.2: Convert to CSV

**Files:**
- Create: `research/b2_team_totals/convert.py` (reuse the B1.2 skeleton —
  copy it, same `norm`/`cfbd_index` helpers, different output contract)
- Create: `research/b2_team_totals/dog_tt.csv` (generated)

**Interfaces:**
- Produces: `dog_tt.csv` with header `game_id,dog_team_total,over_price`,
  where `dog_team_total` is the closing team-total line for the game's
  UNDERDOG (the side with the positive home-relative spread; resolve which
  team is the dog from `lines_{season}.json` spread sign) and `over_price`
  is the American price on its over (empty string if the source has no
  prices).

- [ ] **Step 1: Write the converter** (B1.2 skeleton with the new output;
  the dog side: load the game's `pick_line` spread — `spread < 0` means home
  is the favorite, so the DOG is away; `spread > 0` → dog is home; skip
  `spread == 0`).
- [ ] **Step 2: Run; require join miss rate < 10% and ≥ 500 rows** (same
  asserts as B1).
- [ ] **Step 3: Commit**

```bash
git add research/b2_team_totals/convert.py research/b2_team_totals/dog_tt.csv
git commit -m "research(b2): convert dog team-total lines"
```

### Task B2.3: Walk-forward backtest driver

**Files:**
- Create: `research/b2_team_totals/backtest_dog_tt.py`

**Interfaces:**
- Consumes: `dog_tt.csv` (B2.2), estimators per the global Interfaces block.
- Primary analysis (PRESPECIFIED, do not alter): per test season t ≥ third
  available season, train σ_dog on seasons < t; signal = dog-team censoring
  bias `_team_censor_bias(dog_est, sigma_dog)`; probit of "dog actual points
  > dog_team_total" on that signal, trained on seasons < t; bet the over on
  season t where trained P > 0.5238; also report the fixed rule
  `dog bias > 0.5` (half the game-level 1.0 threshold, since only one
  team's bias is in play — prespecified here, before any data is seen).

- [ ] **Step 1: Write the driver**

```python
"""Walk-forward backtest: OVER on the underdog's team total.

Signal: the dog's own censoring bias, trained only on past seasons.
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "v2"))
sys.path.insert(0, str(REPO / "monitor"))
from models_v2 import (_team_censor_bias, implied_team_points, pick_line,
                       tobit_left_censored_v2, probit_win_v2)
from monitor import _wilson

RAW = REPO.parent / "cfb-site" / "data" / "raw"
HURDLE = 0.5238
DOG_BIAS_RULE = 0.5     # prespecified fixed rule; do not tune


def load_tt():
    out = {}
    with open(Path(__file__).parent / "dog_tt.csv", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out[int(row["game_id"])] = float(row["dog_team_total"])
    return out


def load_games(seasons, tt):
    """season -> dict(dog_est, fav_est, dog_pts, tt_line) arrays, joined on game id."""
    data = {}
    for season in seasons:
        p = RAW / f"lines_{season}.json"
        if not p.exists():
            continue
        de, fe, dp_, tl = [], [], [], []
        for g in json.loads(p.read_text(encoding="utf-8")):
            hp, ap = g.get("homeScore"), g.get("awayScore")
            line = pick_line(g)
            if hp is None or ap is None or line is None or g["id"] not in tt:
                continue
            spread, total = line
            if spread == 0:
                continue
            dog_pts = float(ap) if spread < 0 else float(hp)
            d, f = implied_team_points(abs(spread), total)
            de.append(float(d)); fe.append(float(f))
            dp_.append(dog_pts); tl.append(tt[g["id"]])
        if de:
            data[season] = tuple(np.array(v) for v in (de, fe, dp_, tl))
    return data


def main():
    tt = load_tt()
    data = load_games(range(2013, 2026), tt)
    years = sorted(data)
    print(f"joined {sum(v[0].size for v in data.values()):,} games "
          f"across {len(years)} seasons: {years}")
    assert len(years) >= 4, "need >= 4 seasons for walk-forward; log to BLOCKERS.md"

    res = {"probit": [], "rule": []}
    for t in years[2:]:
        tr = [y for y in years if y < t]
        de = np.concatenate([data[y][0] for y in tr])
        dp_ = np.concatenate([data[y][2] for y in tr])
        sigma = tobit_left_censored_v2(dp_, de).sigma
        bias_tr = _team_censor_bias(de, sigma)
        nu_tr = dp_ - np.concatenate([data[y][3] for y in tr])
        keep_tr = nu_tr != 0
        pr = probit_win_v2((nu_tr > 0).astype(float)[keep_tr], bias_tr[keep_tr])

        de_t, _fe_t, dp_t, tl_t = data[t]
        bias_t = _team_censor_bias(de_t, sigma)
        nu_t = dp_t - tl_t
        keep_t = nu_t != 0
        over_t = nu_t > 0
        for name, sel in (("probit", keep_t & (pr.win_prob(bias_t) > HURDLE)),
                          ("rule", keep_t & (bias_t > DOG_BIAS_RULE))):
            res[name].append((t, int(sel.sum()), int(over_t[sel].sum())))

    for name, rows in res.items():
        N = sum(r[1] for r in rows)
        W = sum(r[2] for r in rows)
        print(f"\n[{name}] per season:", ", ".join(f"{t}:{w}/{n}" for t, n, w in rows))
        if N == 0:
            print(f"[{name}] no bets")
            continue
        lo, hi = _wilson(W, N)
        print(f"[{name}] POOLED N={N} win={W/N*100:.2f}% "
              f"Wilson95=[{lo*100:.1f},{hi*100:.1f}] "
              f"(breakeven 52.38% at -110)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

```bash
python research/b2_team_totals/backtest_dog_tt.py
```

Expected: joined-games line, then per-season and pooled rows for both
selection rules with Wilson CIs. No exceptions.

- [ ] **Step 3: Write RESULTS.md**

Create `research/b2_team_totals/RESULTS.md`: verbatim output, then the
fixed checklist: (1) does the pooled Wilson lower bound clear 52.38% for
either rule? (2) if the source had prices, note the median over price and
recompute breakeven `price/(price+100)`; (3) verdict:
`DOG TEAM-TOTAL EDGE CONFIRMED` / `NO EDGE` / `INCONCLUSIVE (N < 200)`.
Caveat to include verbatim: "Team-total pushes are common (whole-number
lines); pushes are excluded, which the `nu != 0` mask handles."

- [ ] **Step 4: Commit**

```bash
git add research/b2_team_totals/backtest_dog_tt.py research/b2_team_totals/RESULTS.md
git commit -m "research(b2): dog team-total walk-forward backtest"
```

---

## Phase B3 — Multi-snapshot odds capture (resolves open questions 4 and 5)

Forward-looking: set up now, runs all season, analyze when the season ends.
Uses the-odds-api.com (free tier: 500 requests/month; one request returns
all CFB games for one market — 3 snapshots/week ≈ 26 requests/month, well
inside the free tier).

### Task B3.1: Capture script

**Files:**
- Create: `research/b3_snapshots/capture_odds.py`

**Interfaces:**
- Requires: environment variable `ODDS_API_KEY` (owner supplies; if unset
  after asking once → BLOCKERS.md, end phase).
- Produces: `research/b3_snapshots/snapshots.jsonl` — one JSON object per
  run: `{"ts": iso8601, "payload": <api response>}`, appended.

- [ ] **Step 1: Write the capture script**

```python
"""Append one odds snapshot (CFB totals + spreads, with prices) to snapshots.jsonl.

Run 3x/week during the season (Sun, Wed, Sat morning) via Task Scheduler.
Requires env var ODDS_API_KEY. Free tier budget: ~26 requests/month.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

KEY = os.environ.get("ODDS_API_KEY")
if not KEY:
    sys.exit("ODDS_API_KEY not set -- see research/BLOCKERS.md protocol")

URL = ("https://api.the-odds-api.com/v4/sports/americanfootball_ncaaf/odds"
       f"?regions=us&markets=totals,spreads&oddsFormat=american&apiKey={KEY}")

with urllib.request.urlopen(URL, timeout=60) as r:
    payload = json.load(r)

out = Path(__file__).parent / "snapshots.jsonl"
with open(out, "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(),
                         "payload": payload}) + "\n")
print(f"captured {len(payload)} games at {datetime.now(timezone.utc).isoformat()}")
```

- [ ] **Step 2: Dry-run once** (only if the key exists and it is football
  season or preseason lines are up):

```bash
python research/b3_snapshots/capture_odds.py
```

Expected: `captured N games at <timestamp>` and a new line in
snapshots.jsonl. Off-season, N may be 0 — that is fine; note it.

- [ ] **Step 3: Schedule it (Windows Task Scheduler, 3x/week)**

```powershell
schtasks /Create /SC WEEKLY /D SUN,WED,SAT /ST 09:00 /TN "cfb-odds-snapshot" /TR "python C:\Users\mckel\dev\paper_models\research\b3_snapshots\capture_odds.py"
```

Note in RESULTS.md (created in B3.2) that the env var must be set
machine-level for the scheduled task (`setx ODDS_API_KEY ...` by the owner —
never write the key into any file).

- [ ] **Step 4: Add the data file to .gitignore and commit**

Append to the repo `.gitignore`:

```
research/b3_snapshots/snapshots.jsonl
```

(The snapshot log grows all season and has no place in git.)

```bash
git add research/b3_snapshots/capture_odds.py .gitignore
git commit -m "research(b3): odds snapshot capture script + schedule"
```

### Task B3.2: Analysis script (write now, run at season end)

**Files:**
- Create: `research/b3_snapshots/analyze_drift.py`
- Create: `research/b3_snapshots/RESULTS.md` (stub now; numbers in January)

- [ ] **Step 1: Write the analyzer**

```python
"""Open-to-close drift + juice on qualifying games, from snapshots.jsonl.

Run after the season. For each game seen in >= 2 snapshots: first-seen vs
last-seen consensus total, and the last-seen over price. 'Qualifying' =
bias > 1.0 computed at the LAST snapshot with pooled sigmas (11.03/11.78).
"""
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "v2"))
from models_v2 import _team_censor_bias, implied_team_points

S1, S2 = 11.03, 11.78          # pooled sigmas (sanity constants from the repo)


def consensus(game):
    """Median total, median |spread|, median over price across books."""
    totals, spreads, prices = [], [], []
    for bk in game.get("bookmakers", []):
        for m in bk.get("markets", []):
            if m["key"] == "totals":
                for o in m["outcomes"]:
                    if o["name"] == "Over":
                        totals.append(float(o["point"]))
                        prices.append(float(o["price"]))
            if m["key"] == "spreads":
                for o in m["outcomes"]:
                    spreads.append(abs(float(o["point"])))
    if not totals or not spreads:
        return None
    return (float(np.median(totals)), float(np.median(spreads)),
            float(np.median(prices)))


def main():
    path = Path(__file__).parent / "snapshots.jsonl"
    first, last = {}, {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            snap = json.loads(line)
            for g in snap["payload"]:
                c = consensus(g)
                if c is None:
                    continue
                gid = g["id"]
                first.setdefault(gid, (snap["ts"], c))
                last[gid] = (snap["ts"], c)

    both = [g for g in first if g in last and first[g][0] != last[g][0]]
    print(f"{len(both)} games with >= 2 snapshots")
    assert both, "no multi-snapshot games -- capture ran less than twice?"

    drifts, qual_drifts, qual_prices = [], [], []
    for gid in both:
        t0 = first[gid][1][0]
        t1, sp1, pr1 = last[gid][1]
        d, f = implied_team_points(sp1, t1)
        bias = float(_team_censor_bias(d, S1) + _team_censor_bias(f, S2))
        drifts.append(t1 - t0)
        if bias > 1.0:
            qual_drifts.append(t1 - t0)
            qual_prices.append(pr1)

    def rep(name, xs):
        xs = np.array(xs)
        if xs.size == 0:
            print(f"{name}: none")
            return
        se = xs.std(ddof=1) / np.sqrt(xs.size)
        print(f"{name}: n={xs.size} mean={xs.mean():+.2f} "
              f"(95% CI [{xs.mean()-1.96*se:+.2f},{xs.mean()+1.96*se:+.2f}])")

    rep("total drift open->close, ALL games (pts)", drifts)
    rep("total drift open->close, QUALIFYING games (pts)", qual_drifts)
    if qual_prices:
        print(f"over price on qualifying games: median {np.median(qual_prices):+.0f}, "
              f"share worse than -110: {np.mean(np.array(qual_prices) < -110)*100:.0f}%")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create the RESULTS.md stub**

```markdown
# B3 results — open/close drift and juice (open questions 4 & 5)

Capture running via Task Scheduler ("cfb-odds-snapshot", Sun/Wed/Sat 09:00).
Run `python research/b3_snapshots/analyze_drift.py` after the season's final
week and paste the output here.

Interpretation (fixed in advance): positive mean drift on qualifying games
= totals rise toward close = EARLY numbers are better for the over bettor;
negative = the close is the better number. The qualifying-price line answers
whether books already shade the over past −110 (open question 5).
```

- [ ] **Step 3: Commit**

```bash
git add research/b3_snapshots/analyze_drift.py research/b3_snapshots/RESULTS.md
git commit -m "research(b3): drift/juice analyzer + results stub"
```

---

## Phase B4 — Residual features (resolves open question 1; data on hand — DO THIS PHASE FIRST)

Why does the realized edge exceed pure-censoring theory? Test whether
game-context features already in the raw data carry signal beyond
`biasTotals`.

### Task B4.1: Field inventory

**Files:**
- Create: `research/b4_features/INVENTORY.md`

- [ ] **Step 1: Print every field available**

```bash
python -c "
import json
from pathlib import Path
for name in ('games_2024.json', 'lines_2024.json'):
    p = Path('../cfb-site/data/raw') / name
    g = json.loads(p.read_text(encoding='utf-8'))
    keys = {}
    for rec in g[:500]:
        for k, v in rec.items():
            keys.setdefault(k, type(v).__name__)
    print(name, '->', dict(sorted(keys.items())))
"
```

Paste output into INVENTORY.md.

- [ ] **Step 2: Mark the candidate features**

The PRESPECIFIED candidate list, IN THIS ORDER, capped at 4 features (the
Bonferroni budget). For each, mark in INVENTORY.md whether the raw data
supports it; take the first 4 supported ones and skip the rest:

1. `week` (season week number — early-season lines may be softer)
2. `neutralSite` (0/1)
3. `conferenceGame` (0/1)
4. `fcs_dog`: 1 if the underdog's conference field is missing/None (FCS
   opponent — scores near the floor for a different reason)
5. `home_dog`: 1 if the home team is the underdog (only if fewer than 4 of
   the above are available)

If fewer than 2 features are available at all, write that in INVENTORY.md,
log to BLOCKERS.md ("B4 limited: only K features available; weather/pace
absent from raw data"), and still proceed with what exists.

- [ ] **Step 3: Commit**

```bash
git add research/b4_features/INVENTORY.md
git commit -m "research(b4): raw-data field inventory"
```

### Task B4.2: Multivariate probit

**Files:**
- Create: `research/b4_features/probit_features.py`

**Interfaces:**
- Consumes: the feature list fixed in B4.1 (read it from INVENTORY.md and
  hard-code the chosen names in the script header).
- Analysis (PRESPECIFIED): probit of over-win on standardized
  `[biasTotals] + features`, pooled 2013–2025, season-clustered SEs.
  Significance bar for a feature: p < 0.0125 (0.05 Bonferroni / 4). The
  question is (a) does any feature clear the bar, and (b) does the
  `biasTotals` coefficient move by more than one SE when features enter.

- [ ] **Step 1: Write the driver**

```python
"""Does anything in the raw data explain the over-edge beyond biasTotals?

Probit: over ~ z(biasTotals) + z(features), pooled, season-clustered SEs.
Feature list fixed by research/b4_features/INVENTORY.md -- edit FEATURES
to the <=4 names chosen there, then never again.
"""
import json
import sys
from pathlib import Path

import numpy as np
import statsmodels.api as sm

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "v2"))
from models_v2 import (censoring_bias, implied_team_points, pick_line,
                       tobit_left_censored_v2)

RAW = REPO.parent / "cfb-site" / "data" / "raw"
FEATURES = ["week", "neutralSite", "conferenceGame", "fcs_dog"]  # from INVENTORY.md
BONFERRONI_P = 0.05 / 4


def feature_row(game_rec, spread):
    dog_conf = (game_rec.get("awayConference") if spread < 0
                else game_rec.get("homeConference"))
    all_feats = {
        "week": float(game_rec.get("week") or 0),
        "neutralSite": 1.0 if game_rec.get("neutralSite") else 0.0,
        "conferenceGame": 1.0 if game_rec.get("conferenceGame") else 0.0,
        "fcs_dog": 0.0 if dog_conf else 1.0,
        "home_dog": 1.0 if spread > 0 else 0.0,
    }
    return [all_feats[f] for f in FEATURES]


def main():
    se, te, fp, dp, ss, X = [], [], [], [], [], []
    for season in range(2013, 2026):
        lp, gp = RAW / f"lines_{season}.json", RAW / f"games_{season}.json"
        if not lp.exists() or not gp.exists():
            continue
        games = {g["id"]: g for g in json.loads(gp.read_text(encoding="utf-8"))}
        for g in json.loads(lp.read_text(encoding="utf-8")):
            hp, ap = g.get("homeScore"), g.get("awayScore")
            line = pick_line(g)
            grec = games.get(g["id"])
            if hp is None or ap is None or line is None or grec is None:
                continue
            spread, total = line
            if spread == 0:
                continue
            fav, dog = (float(hp), float(ap)) if spread < 0 else (float(ap), float(hp))
            se.append(abs(spread)); te.append(total)
            fp.append(fav); dp.append(dog); ss.append(season)
            X.append(feature_row(grec, spread))

    se, te, fp, dp, ss = map(np.array, (se, te, fp, dp, ss))
    X = np.array(X)
    print(f"{se.size:,} games with features joined")
    assert se.size > 10_000, "join lost too many games -- inspect games_/lines_ id overlap"

    dog_est, fav_est = implied_team_points(se, te)
    s1 = tobit_left_censored_v2(dp, dog_est).sigma
    s2 = tobit_left_censored_v2(fp, fav_est).sigma
    _, bias = censoring_bias(dog_est, fav_est, s1, s2)
    nu = (fp + dp) - te
    keep = nu != 0
    y = (nu > 0).astype(float)[keep]
    groups = ss[keep]

    def zfit(cols, names):
        Z = np.column_stack([(c - c.mean()) / c.std() for c in cols])
        res = sm.Probit(y, sm.add_constant(Z)).fit(
            disp=False, cov_type="cluster", cov_kwds={"groups": groups})
        print(f"\nspec: {names}")
        for name, b, s_, p in zip(["const"] + names, res.params, res.bse, res.pvalues):
            star = " *SIG*" if name != "const" and name != "biasTotals" and p < BONFERRONI_P else ""
            print(f"  {name:>15} {b:+.4f} (SE {s_:.4f}, p={p:.4g}){star}")
        return res

    base = zfit([bias[keep]], ["biasTotals"])
    full = zfit([bias[keep]] + [X[keep][:, i] for i in range(len(FEATURES))],
                ["biasTotals"] + FEATURES)
    shift = (full.params[1] - base.params[1]) / base.bse[1]
    print(f"\nbiasTotals coefficient shift with features: {shift:+.2f} SEs "
          f"(over 1 SE = features materially overlap the censoring signal)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Adjust `FEATURES`** to exactly the ≤4 names INVENTORY.md
  marked available (only removals allowed, no additions), run:

```bash
python research/b4_features/probit_features.py
```

Expected: games count > 10,000, base spec `biasTotals` coefficient ≈ +0.07
standardized (matches v3's univariate table), full spec prints each feature
with clustered SE and a `*SIG*` flag only under Bonferroni.

- [ ] **Step 3: Write RESULTS.md** (`research/b4_features/RESULTS.md`):
  verbatim output + fixed checklist: (1) any feature `*SIG*`? (2)
  biasTotals shift over 1 SE? (3) verdict paragraph: what this says about
  open question 1 — "features tested do not explain the excess edge" is the
  expected (and useful) null; state the MDE caveat verbatim: "With ~12k
  games a standardized probit coefficient below ≈0.03 is undetectable at
  this power; absence of significance is not absence of effect for smaller
  influences."

- [ ] **Step 4: Commit**

```bash
git add research/b4_features/probit_features.py research/b4_features/RESULTS.md
git commit -m "research(b4): residual-feature probit"
```

---

## Phase B5 — Hierarchical team-level σ (resolves open question 9)

One σ per role is fitted for all teams. Test whether team-specific score
noise (shrunk toward the pool) improves the bias signal out-of-sample.

### Task B5.1: Team-σ walk-forward comparison

**Files:**
- Create: `research/b5_team_sigma/team_sigma.py`

**Interfaces:**
- Consumes: raw `lines_{season}.json` (needs team names — if the inventory
  from B4.1 shows no `homeTeam`/`awayTeam` keys in lines files, join names
  from `games_{season}.json` by id; if neither has names, BLOCKERS.md and
  end phase).
- Analysis (PRESPECIFIED): per team, residual variance about the pooled
  Tobit line on UNCENSORED games; EB shrinkage
  `var_i = (n_i*s2_i + K*s2_pool) / (n_i + K)` with `K = 30` (primary),
  sensitivity `K ∈ {15, 60}`. Compare pooled-σ vs team-σ pipelines
  walk-forward (train < t, score season t) on mean OOS log-loss of P(over),
  paired by game, with a season-block bootstrap CI (1000 resamples, seed 0).

- [ ] **Step 1: Write the driver**

```python
"""Does team-specific (shrunk) score noise beat one pooled sigma per role?

Walk-forward, paired OOS log-loss, season-block bootstrap CI. K=30 primary.
"""
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "v2"))
from models_v2 import (_team_censor_bias, implied_team_points, pick_line,
                       probit_win_v2, tobit_left_censored_v2)

RAW = REPO.parent / "cfb-site" / "data" / "raw"
K_PRIMARY, K_SENS = 30, (15, 60)


def load(seasons):
    """season -> dict of arrays: dog_est, fav_est, dog_pts, fav_pts, total,
    dog_team, fav_team."""
    out = {}
    for season in seasons:
        p = RAW / f"lines_{season}.json"
        if not p.exists():
            continue
        rows = {k: [] for k in ("de", "fe", "dp", "fp", "te", "dt", "ft")}
        for g in json.loads(p.read_text(encoding="utf-8")):
            hp, ap = g.get("homeScore"), g.get("awayScore")
            line = pick_line(g)
            home, away = g.get("homeTeam"), g.get("awayTeam")
            if hp is None or ap is None or line is None or not home or not away:
                continue
            spread, total = line
            if spread == 0:
                continue
            if spread < 0:
                favp, dogp, favt, dogt = float(hp), float(ap), home, away
            else:
                favp, dogp, favt, dogt = float(ap), float(hp), away, home
            d, f = implied_team_points(abs(spread), total)
            for k, v in (("de", float(d)), ("fe", float(f)), ("dp", dogp),
                         ("fp", favp), ("te", total), ("dt", dogt), ("ft", favt)):
                rows[k].append(v)
        if rows["de"]:
            out[season] = {k: np.array(v) for k, v in rows.items()}
    return out


def team_sigmas(seasons_data, role, K):
    """role 'dog' or 'fav': team -> shrunk sigma, plus (pooled fit alpha,beta,sigma)."""
    est = np.concatenate([d["de" if role == "dog" else "fe"] for d in seasons_data])
    pts = np.concatenate([d["dp" if role == "dog" else "fp"] for d in seasons_data])
    team = np.concatenate([d["dt" if role == "dog" else "ft"] for d in seasons_data])
    fit = tobit_left_censored_v2(pts, est)
    unc = pts > 0
    resid = (pts - (fit.alpha + fit.beta * est))[unc]
    tm = team[unc]
    s2_pool = fit.sigma ** 2
    out = {}
    for t in np.unique(tm):
        r = resid[tm == t]
        if r.size >= 5:
            out[t] = (r.size * r.var(ddof=1) + K * s2_pool) / (r.size + K)
    return {t: float(np.sqrt(v)) for t, v in out.items()}, fit


def season_logloss(data_t, sd_dog, sd_fav, s1, s2, probit, per_team):
    de, fe, te = data_t["de"], data_t["fe"], data_t["te"]
    if per_team:
        sig_d = np.array([sd_dog.get(t, s1) for t in data_t["dt"]])
        sig_f = np.array([sd_fav.get(t, s2) for t in data_t["ft"]])
    else:
        sig_d = np.full(de.size, s1)
        sig_f = np.full(fe.size, s2)
    bias = _team_censor_bias(de, sig_d) + _team_censor_bias(fe, sig_f)
    p = np.clip(probit.win_prob(bias), 1e-6, 1 - 1e-6)
    nu = (data_t["dp"] + data_t["fp"]) - te
    keep = nu != 0
    y = (nu > 0).astype(float)[keep]
    return -(y * np.log(p[keep]) + (1 - y) * np.log(1 - p[keep]))


def run(K):
    data = load(range(2013, 2026))
    years = sorted(data)
    diffs_by_season = []
    for t in years[3:]:
        tr = [data[y] for y in years if y < t]
        sd_dog, fit_d = team_sigmas(tr, "dog", K)
        sd_fav, fit_f = team_sigmas(tr, "fav", K)
        s1, s2 = fit_d.sigma, fit_f.sigma
        de = np.concatenate([d["de"] for d in tr])
        fe = np.concatenate([d["fe"] for d in tr])
        bias_tr = _team_censor_bias(de, s1) + _team_censor_bias(fe, s2)
        nu_tr = np.concatenate([d["dp"] + d["fp"] - d["te"] for d in tr])
        keep = nu_tr != 0
        probit = probit_win_v2((nu_tr > 0).astype(float)[keep], bias_tr[keep])

        ll_pool = season_logloss(data[t], sd_dog, sd_fav, s1, s2, probit, False)
        ll_team = season_logloss(data[t], sd_dog, sd_fav, s1, s2, probit, True)
        diffs_by_season.append(ll_pool - ll_team)   # positive = team-sigma better

    flat = np.concatenate(diffs_by_season)
    rng = np.random.default_rng(0)
    boots = [np.concatenate([diffs_by_season[i] for i in
                             rng.integers(0, len(diffs_by_season), len(diffs_by_season))]).mean()
             for _ in range(1000)]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    print(f"K={K}: mean OOS logloss improvement (pooled - team) = "
          f"{flat.mean()*1e4:+.2f} x1e-4  season-block bootstrap 95% "
          f"[{lo*1e4:+.2f},{hi*1e4:+.2f}] x1e-4  ({flat.size:,} games)")
    return flat.mean(), lo, hi


def main():
    results = {K: run(K) for K in (K_PRIMARY,) + K_SENS}
    m, lo, hi = results[K_PRIMARY]
    verdict = ("TEAM-SIGMA IMPROVES OOS" if lo > 0
               else "NO OOS IMPROVEMENT" if hi > 0 else "TEAM-SIGMA HURTS OOS")
    print(f"\nVERDICT (K={K_PRIMARY}): {verdict}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

```bash
python research/b5_team_sigma/team_sigma.py
```

Expected: three `K=...` lines (30, 15, 60) with bootstrap CIs and a final
`VERDICT` line. Takes a few minutes (Tobit refits per season). If it fails
with missing `homeTeam` keys, follow the Interfaces fallback (join names
from `games_{season}.json` by id), or BLOCKERS.md if impossible.

- [ ] **Step 3: Write RESULTS.md** (`research/b5_team_sigma/RESULTS.md`):
  verbatim output + fixed checklist: (1) CI excludes 0 at K=30? (2) same
  sign across K=15/60? (3) verdict; if improved, add the prespecified
  follow-up note: "Next validation before betting on it: rerun the full
  walk-forward BET simulation (win% at bias > 1.0) with team-σ — needs
  owner sign-off." Include verbatim caveat: "Team σ estimated on uncensored
  games only (mild truncation); shrinkage constant K is games-count prior
  weight, K=30 ≈ 2.5 seasons."

- [ ] **Step 4: Commit**

```bash
git add research/b5_team_sigma/team_sigma.py research/b5_team_sigma/RESULTS.md
git commit -m "research(b5): hierarchical team-sigma OOS comparison"
```

---

## Execution order

Run phases in this order (differs from the guide's payoff ranking because
B4/B5 need no external data):

1. **Task 0** (environment) — always first.
2. **B4** (features) — data on hand, fully executable today.
3. **B5** (team σ) — data on hand, fully executable today.
4. **B1** (1H lines) — starts with a data hunt; may end at SOURCES.md.
5. **B2** (team totals) — same shape as B1.
6. **B3** (snapshot capture) — setup now, analysis after the season.

## Final deliverable

After the last executable phase, create `research/SUMMARY.md`: one table —
phase, status (`done` / `blocked` / `capture running`), verdict line copied
from each RESULTS.md, link to the phase folder. Commit as
`research: track B summary`.
