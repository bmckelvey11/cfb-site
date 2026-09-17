# Spread-Implied Power Ratings (v1.0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recover opponent-adjusted team power ratings from the closing point spread, reusing the crossed-random-effects + cross-season-shrinkage machinery already built for PPA ratings.

**Architecture:** Reshape `stg.games` (one row per game) into two rows per game — home-team perspective and away-team perspective, mirroring the shape `stg.ppa_games` already has. Feed that into the existing `fit_crossed_effects` (crossed team/opponent random effects via `statsmodels.MixedLM`) and `shrink_toward_prior` (precision-weighted cross-season blend) functions, imported unchanged from `scripts/build_ppa_opponent_adjusted_ratings.py`. One rating per team (`power_rating`), not split into offense/defense — a spread is a single differential.

**Tech Stack:** Python, `duckdb`, `pandas`, `statsmodels` (all already in `requirements.txt` and used by the PPA script). No new dependencies.

**Spec:** No separate spec file — this is a bounded task (brainstorming skill, bounded path). The approved design is captured in this plan's Architecture section and Task 1-2 below; it was presented and approved in chat on 2026-09-17, following the same pattern as `docs/ppa-opponent-adjusted-ratings-2026-09-16.md`.

## Global Constraints

- Response variable is **closing** `spread` from `stg.games` (approved default — sharpest number, most information priced in by kickoff; this is a rating, not a bet-timing question).
- Sign convention (confirmed against `docs/totals-early-weeks.md`'s cover-test convention `home_points + spread > away_points`): negative `spread` means the home team is favored. Home team's implied margin = `-spread`.
- Reuse `fit_crossed_effects` and `shrink_toward_prior` from `scripts/build_ppa_opponent_adjusted_ratings.py` **unchanged** — do not duplicate or fork that logic.
- `VERSION = "1.0"`, stamped in the output CSV and the output filename, matching the PPA script's convention.
- Data never committed to git (`data/exports/` is gitignored) — only script, test, and doc get committed.
- Regular season only (`seasonType = 'regular'`), matching the PPA script.

---

### Task 1: Build the game-to-paired-rows transform, with sign-convention tests

**Files:**
- Create: `scripts/build_spread_implied_power_ratings.py`
- Test: `tests/test_spread_implied_power_ratings.py`

**Interfaces:**
- Produces: `spread_to_paired_rows(games: pd.DataFrame) -> pd.DataFrame` — input columns `season, week, homeTeam, awayTeam, spread, neutralSite`; output columns `season, week, team, opponent, margin, is_home`, two rows per input row. Later tasks (and `fit_crossed_effects`, which expects a `team`/`opponent`/response/`is_home` shaped frame) depend on this exact output shape.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_spread_implied_power_ratings.py
import pandas as pd

from scripts.build_spread_implied_power_ratings import spread_to_paired_rows


def test_home_favorite_gets_positive_margin():
    games = pd.DataFrame({
        "season": [2025], "week": [1],
        "homeTeam": ["Ohio State"], "awayTeam": ["Akron"],
        "spread": [-21.5], "neutralSite": [False],
    })
    paired = spread_to_paired_rows(games)

    home_row = paired[paired["team"] == "Ohio State"].iloc[0]
    away_row = paired[paired["team"] == "Akron"].iloc[0]

    assert home_row["margin"] == 21.5
    assert away_row["margin"] == -21.5
    assert home_row["opponent"] == "Akron"
    assert away_row["opponent"] == "Ohio State"
    assert home_row["is_home"] == True
    assert away_row["is_home"] == False


def test_neutral_site_home_team_is_not_home():
    games = pd.DataFrame({
        "season": [2025], "week": [1],
        "homeTeam": ["Alabama"], "awayTeam": ["Georgia"],
        "spread": [-3.0], "neutralSite": [True],
    })
    paired = spread_to_paired_rows(games)

    home_row = paired[paired["team"] == "Alabama"].iloc[0]
    assert home_row["is_home"] == False


def test_missing_neutral_site_flag_defaults_to_not_neutral():
    games = pd.DataFrame({
        "season": [2025], "week": [1],
        "homeTeam": ["Duke"], "awayTeam": ["Wake Forest"],
        "spread": [-1.0], "neutralSite": [None],
    })
    paired = spread_to_paired_rows(games)

    home_row = paired[paired["team"] == "Duke"].iloc[0]
    assert home_row["is_home"] == True


def test_two_rows_per_game():
    games = pd.DataFrame({
        "season": [2025, 2025], "week": [1, 1],
        "homeTeam": ["Ohio State", "Texas"], "awayTeam": ["Akron", "Michigan"],
        "spread": [-21.5, -3.0], "neutralSite": [False, False],
    })
    paired = spread_to_paired_rows(games)
    assert len(paired) == 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_spread_implied_power_ratings.py -v`
Expected: FAIL with `ModuleNotFoundError` or `ImportError` (module doesn't exist yet).

- [ ] **Step 3: Write the minimal implementation**

```python
# scripts/build_spread_implied_power_ratings.py
"""Opponent-adjusted team power ratings from the closing spread.

v1.0
Reuses the crossed team/opponent random-effects fit and cross-season
shrinkage built for PPA ratings (scripts/build_ppa_opponent_adjusted_ratings.py),
swapping the response variable to the closing point spread. A spread already
prices in information (injuries, depth, matchup-specific factors) that
box-score PPA can't see, so this is a distinct signal, not a redundant
opponent proxy.

Sign convention: `spread` is the number added to the home team's score
(negative = home favored). Home team's implied margin = -spread.

Usage:
    python scripts/build_spread_implied_power_ratings.py --season 2026
    python scripts/build_spread_implied_power_ratings.py --season 2026 --week 3 --prior-seasons 2
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cfb_paths
from scripts.build_ppa_opponent_adjusted_ratings import fit_crossed_effects, shrink_toward_prior

VERSION = "1.0"


def spread_to_paired_rows(games: pd.DataFrame) -> pd.DataFrame:
    """Reshape one-row-per-game spreads into two rows per game (home/away perspective)."""
    is_home_team = ~games["neutralSite"].fillna(False)
    home_rows = pd.DataFrame({
        "season": games["season"],
        "week": games["week"],
        "team": games["homeTeam"],
        "opponent": games["awayTeam"],
        "margin": -games["spread"],
        "is_home": is_home_team,
    })
    away_rows = pd.DataFrame({
        "season": games["season"],
        "week": games["week"],
        "team": games["awayTeam"],
        "opponent": games["homeTeam"],
        "margin": games["spread"],
        "is_home": False,
    })
    return pd.concat([home_rows, away_rows], ignore_index=True)


def load_games(con: duckdb.DuckDBPyConnection, seasons: list[int], max_week: int | None = None) -> pd.DataFrame:
    if not seasons:
        return pd.DataFrame(columns=["season", "week", "homeTeam", "awayTeam", "spread", "neutralSite"])
    season_list = ",".join(str(s) for s in seasons)
    df = con.execute(f"""
        SELECT season, week, homeTeam, awayTeam, spread, neutralSite
        FROM stg.games
        WHERE season IN ({season_list}) AND seasonType = 'regular' AND spread IS NOT NULL
    """).fetchdf()
    if max_week is not None:
        df = df[df["week"] <= max_week]
    return df


def build_ratings(con: duckdb.DuckDBPyConnection, season: int, week: int | None, prior_seasons: int) -> pd.DataFrame:
    current_games = load_games(con, [season], max_week=week)
    prior_years = [season - i for i in range(1, prior_seasons + 1)]
    prior_games = load_games(con, prior_years)

    current_paired = spread_to_paired_rows(current_games)
    prior_paired = spread_to_paired_rows(prior_games)

    blend = shrink_toward_prior(
        fit_crossed_effects(current_paired, "margin"),
        fit_crossed_effects(prior_paired, "margin"),
    )

    games_played = current_paired.groupby("team").size().to_dict()
    rows = []
    for team, stats in blend.items():
        rows.append({
            "team": team,
            "games_played": games_played.get(team, 0),
            "power_rating": stats["estimate"],
            "power_se": stats["se"],
            "source": stats["source"],
        })
    ratings = pd.DataFrame(rows)
    return ratings.sort_values("power_rating", ascending=False).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Spread-implied power ratings (v{VERSION})")
    parser.add_argument("--season", type=int, default=cfb_paths.current_season())
    parser.add_argument("--week", type=int, default=None, help="cutoff week; default = latest loaded")
    parser.add_argument("--prior-seasons", type=int, default=1, help="prior seasons pooled for the shrinkage prior")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    con = duckdb.connect(str(cfb_paths.DB_PATH), read_only=True)
    ratings = build_ratings(con, args.season, args.week, args.prior_seasons)
    ratings.insert(0, "rating_version", VERSION)

    out_dir = args.out or (cfb_paths.DATA_ROOT / "exports")
    out_dir.mkdir(parents=True, exist_ok=True)
    week_tag = f"_wk{args.week}" if args.week else ""
    out_path = out_dir / f"spread_power_ratings_v{VERSION}_{args.season}{week_tag}.csv"
    ratings.to_csv(out_path, index=False)
    print(f"wrote {len(ratings)} teams -> {out_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_spread_implied_power_ratings.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/build_spread_implied_power_ratings.py tests/test_spread_implied_power_ratings.py
git commit -m "feat(ratings): add spread-implied power rating v1.0 (sign-convention tested)"
```

---

### Task 2: Verify the live fit runs and produces sane output

**Files:**
- No new files. Uses `scripts/build_spread_implied_power_ratings.py` from Task 1 against the live warehouse.

**Interfaces:**
- Consumes: `build_ratings(con, season, week, prior_seasons) -> pd.DataFrame` from Task 1, columns `team, games_played, power_rating, power_se, source`.

- [ ] **Step 1: Run the script against the current season**

Run: `python scripts/build_spread_implied_power_ratings.py --season 2026`
Expected: prints `wrote <n> teams -> data/exports/spread_power_ratings_v1.0_2026.csv` with `n` roughly matching FBS team count (~130-140), no traceback. `ConvergenceWarning` from `statsmodels` is expected and fine (same as the PPA script).

- [ ] **Step 2: Sanity-check the output**

Run this inline check (not a pytest — it's a one-time data sanity check, same as done for the PPA script):

```python
import pandas as pd
df = pd.read_csv("data/exports/spread_power_ratings_v1.0_2026.csv")
print(df.head(10).to_string(index=False))   # expect ranked teams matching a plausible AP-ish order
print(df.tail(5).to_string(index=False))
print(df["games_played"].describe())        # expect small positive ints (1-3 for an early-season snapshot)
print(df["team"].str.endswith("]").any())   # expect False — regression check for the bracket bug hit in the PPA script
```

If any team name ends in `]`, or `games_played` is all zero, or the top/bottom of the table looks implausible (e.g. a known-strong team at the bottom), stop and fix `spread_to_paired_rows` or `build_ratings` before proceeding — do not write the doc against broken output.

- [ ] **Step 3: Cross-check against the PPA ratings from the same week**

Run:

```python
ppa = pd.read_csv("data/exports/ppa_ratings_v1.0_2026.csv")[["team", "overall_rating"]]
spread = pd.read_csv("data/exports/spread_power_ratings_v1.0_2026.csv")[["team", "power_rating"]]
merged = ppa.merge(spread, on="team")
print(merged["overall_rating"].corr(merged["power_rating"]))
print(merged.reindex(merged["power_rating"].sub(merged["overall_rating"] * merged["power_rating"].std() / merged["overall_rating"].std()).abs().sort_values(ascending=False).index).head(10))
```

This isn't a pass/fail gate — it's the check flagged in the prior conversation ("worth checking before building more" if the two ratings disagree). Note the correlation and any teams the two ratings disagree on sharply; it goes in the doc's "what this does not support" section, not as a blocker.

---

### Task 3: Write the analysis doc and commit

**Files:**
- Create: `docs/spread-implied-power-ratings-2026-09-17.md`

**Interfaces:**
- Consumes: the real numbers from Task 2's output CSV and sanity checks — do not fabricate placeholder numbers; copy them from your actual run.

- [ ] **Step 1: Write the doc**

Use this structure (fill every `<...>` from your actual Task 2 output — follow the shape of `docs/ppa-opponent-adjusted-ratings-2026-09-16.md`, which this doc is a sibling to):

```markdown
# Spread-implied power ratings (v1.0)

**Date:** 2026-09-17
**Script:** [`scripts/build_spread_implied_power_ratings.py`](../scripts/build_spread_implied_power_ratings.py) (`VERSION = "1.0"`)
**Test:** [`tests/test_spread_implied_power_ratings.py`](../tests/test_spread_implied_power_ratings.py)

## Question

Can we recover opponent-adjusted team power ratings directly from the closing
point spread, using the same crossed-effects + cross-season-shrinkage method
built for PPA ratings — and does it agree with the box-score-derived PPA
rating?

## Method

Reshapes `stg.games` (one row per game, `spread` = points added to the home
score, negative = home favored) into two rows per game — home-team
perspective (`margin = -spread`) and away-team perspective
(`margin = +spread`) — matching the shape `stg.ppa_games` already has. Fits
the same crossed team/opponent random-effects model
(`fit_crossed_effects`, reused unchanged from
`build_ppa_opponent_adjusted_ratings.py`) on `margin`, then blends the
current season against a pooled prior-seasons fit by precision
(`shrink_toward_prior`, also reused unchanged).

## Data and date range

- `stg.games`, `seasonType = 'regular'`, `spread IS NOT NULL` only.
- Current season: 2026, snapshot pulled 2026-09-17, through week `<N>`.
- Prior-seasons default: `<prior season(s)>`.

## Numbers

Top 10 by `power_rating`:

<paste your real top-10 table here>

`<n>` of `<total>` teams are `blended`; `<n>` are `current_only` or `prior_only`.

Correlation with the PPA `overall_rating` from the same week: `<r>`.
Teams where the two ratings disagree most: `<list from Task 2 Step 3>`.

## What this does not support

- **Not validated against betting lines or outcomes as an edge** — this
  recovers a rating from the market, it doesn't test whether that rating
  beats the market.
- **Circularity caveat:** the response variable IS a market price. This
  rating cannot be used to claim an edge against the spread market itself —
  it's opponent adjustment borrowed from the market, not independent
  verification of it.
- **Not wired into `models/totals` or `research/spread`.** Standalone output.
- **Regular season only.**
- `<any other caveat you actually observed in Task 2>`

## Reproduce

\`\`\`bash
python scripts/build_spread_implied_power_ratings.py --season 2026
\`\`\`
```

- [ ] **Step 2: Commit**

```bash
git add docs/spread-implied-power-ratings-2026-09-17.md
git commit -m "docs(ratings): write up spread-implied power ratings v1.0"
git push
```
