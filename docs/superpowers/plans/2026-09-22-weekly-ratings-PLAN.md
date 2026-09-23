# Plan: Release B — weekly PPP and pace ratings vs the mean and the vendor open
_Locked via claudex-loop — by Claude + mckel, 2026-09-22_

Detailed design (equations, metrics, tests): [`../specs/2026-09-22-weekly-ratings-design.md`](../specs/2026-09-22-weekly-ratings-design.md).
This file is the reviewable plan; where the two differ, fix both.

## Goal

Build weekly, as-of **team points-per-possession** (offense $O$, defense $D$) and **pace**
($P$) ratings for FBS teams, two ways (`ridge_v1` opponent-adjusted and shrunk to league
average; `raw_v1` season-to-date means), turn each into a full-game total forecast, and
score both against a train mean and the Bovada `overUnderOpen` label on 2021–2025, with λ
tuned on 2014–2019 only. Output is forecast skill with intervals and a predeclared verdict,
not betting value. Implements `research/totals/docs/totals-modeling-guide.md` §13 step 3.

## Approach

1. **Load** (`load_team_games`): per season, from `data/raw/games_<s>.json` and
   `data/raw/drives_<s>.json`, build team-game rows for completed FBS-vs-FBS regular-season
   games: `y` = Q1–Q4 line-score points ÷ regulation drives (`startPeriod` 1–4), `w` =
   regulation drives, `H` = +1/−1/0 (neutral), kickoff from `startDate`. Game rows carry
   `N` = both teams' regulation drives ÷ 2 and OT points = total − Q1–Q4 line scores.
   Drive score fields are never read.
2. **Gate** fits (not scoring): drop a game with no drives or with |home − away regulation
   drives| > 2; count every drop by reason.
3. **Cutoffs**: for season $s$, week $w\ge2$, cutoff $t$ = earliest kickoff of week $w$;
   fit set = rows with kickoff strictly before $t$, via `snapshot()` imported from
   `scripts/pregame_replay_audit.py`.
4. **Fit** at each cutoff:
   - `fit_ridge`: weighted least squares with offense/defense team dummies, unpenalized
     $\mu$ and $h$, penalty $\lambda_{\text{PPP}}$ on $O$, $D$; pace with team dummies on
     both sides of each game, unpenalized $\nu$, penalty $\lambda_{\text{pace}}$. Solved
     directly with numpy.
   - `fit_raw`: possession-weighted means minus $\mu$ (offense, allowed) and mean $N$
     minus $\nu$.
   - $c_t$ = fit-set mean OT points.
5. **Snapshot** rows `season, as_of_week, as_of_ts, team, method, O, D, P, n_games,
   n_possessions, lambda_ppp, lambda_pace, garbage_filter, fcs_policy` + per-snapshot
   `mu, nu, h, c`; write `data/processed/ratings/weekly_ratings_snapshots.csv`.
6. **Forecast** each week-$w$ game from its week's snapshot:
   $\widehat T=(\nu+P_h+P_a)\left[(\mu+O_h+D_a+hH)+(\mu+O_a+D_h-hH)\right]+c_t$.
7. **Tune** on 2014–2019 (2020 excluded): one-step-ahead possession-weighted squared
   error of $y$ over $\lambda_{\text{PPP}}\in\{5,10,20,40,80,160\}$ and squared error of
   $N$ over $\lambda_{\text{pace}}\in\{0.5,1,2,4,8,16\}$, every cutoff week ≥2; the grids
   are independent (12 trials).
8. **Score** 2021–2025 with λ frozen: forecasts = Bovada open (fixed provider, no
   fallback), train mean (FBS-vs-FBS full totals before the cutoff, since 2014), `raw_v1`,
   `ridge_v1`, on the same games. Populations: primary (both teams ≥3 prior FBS-vs-FBS
   games this season, open present) and early (weeks 2+, some team <3; ridge/mean/open).
   Metrics per season and pooled: n, MAE, RMSE, bias; paired MAE differences with a
   week-cluster bootstrap 95% interval (10,000 draws, fixed seed); encompassing slope
   $b$ from $T-L=a+b(\widehat T-L)$ with the same interval.
9. **Verdict** (`classify_verdict`) per paired difference, pooled interval $[\ell,u]$:
   worse if $\ell>0$; improves if $u<0$ and the point estimate is negative in all but at
   most one season; else matches. Applied to ridge vs raw and ridge vs train mean. Stress:
   rescore at λ ×0.5 and ×2; a changed verdict is reported as unstable.
10. **Manifest** `data/processed/ratings/weekly_ratings_eval.json`: command, code and
    source sha256s, λ grid losses and picks, metrics, verdicts, stress, trial count,
    population and drop counts. Grep stdout and manifest for betting terms, as in
    Release A.
11. **Tests** `tests/test_weekly_ratings.py` (in-memory, no `CFB_DATA_ROOT`): leakage
    (post-cutoff extreme score and tied kickoff change nothing), noiseless recovery of
    known $O,D,h,P$ with signs, large-λ shrinkage to 0, possessions/line-score points/gate,
    guide §7.3 total = 55.0, each verdict branch.
12. **Docs**: `docs/weekly-ratings-<date>.md` (question, method, data and range, numbers,
    verdicts, what it does not support) + row in `docs/README.md`; update the living guide's
    §7 status line and §13 step-3 row in the same commit.
13. **Commits**: (a) fit + snapshots + tests 1–5; (b) tune + evaluate + verdict + test 6 +
    docs. Auto-push each.

## Key decisions & tradeoffs

- **Line-score points, drive counts for possessions** (Q1, locked with the user). Drive
  score fields are corrupt in 19–58 games/season from 2021. Cost: $O$ includes a team's
  own defensive and return TDs, so it is a team rate, not a pure offense rate.
- **Ridge toward league average, no priors.** Early weeks shrink hard to the mean; the
  early population is reported so the gap is visible. Priors are the next release, and the
  penalty target is the only thing that changes (guide §7.5).
- **Per-week cutoff at the week's first kickoff**, stricter than per-game: a Tuesday game's
  result does not inform the same week's Saturday games.
- **One fixed book (Bovada)** for the open, chosen on coverage across all scored seasons.
  Release A used ESPN Bet for a single week on the same coverage rule.
- **λ tuned on component loss (PPP, $N$), not on total MAE**, on 2014–2019 only. The
  total's skill is then an honest out-of-sample consequence, not a tuning target.
- **Week-cluster bootstrap**, not game-level: every game in a week shares one snapshot.
- **Verdict gates ridge vs raw and ridge vs mean; the open is reported, not gated.**
- **FBS vs FBS only**, fits and scoring; FBS–FCS games are dropped, not rated.
- **Root `scripts/` + `docs/`**, not `models/totals/` (mid-rename to untracked
  `models/middle/`; a committed file there breaks a clean checkout).

## Toolchain

- Claude (build and evaluation): load `econometrics` before writing the evaluation and
  before interpreting results — forecast comparison, clustered intervals, leakage audit.
  `test-driven-development` for the fit module (tests 2–5 before `fit_ridge`).
- Codex (review): `statistical-analysis` is installed on its bench; optional. Its
  loading under headless `codex exec` is unverified.

## Assumptions

1. Drive `offense` names join to game home/away names with 0 mismatches; `isHomeOffense`
   is consistent — recon, 2014/2019/2021/2024/2025.
2. Q1–Q4 line scores are present and sum to the final in every FBS-vs-FBS regular-season
   game checked — recon, 2014/2019/2021/2025.
3. Regulation drive counts are sane: median 11.5–13 per team; |home − away| ≤ 2 in ~98% of
   games — recon.
4. Bovada opens cover 732–762 FBS-vs-FBS games a season 2021–2025; no book has opens in
   2019–2020 — recon of `data/raw/lines_<s>.json`.
5. Regular-season weeks run 1–16, no week-0 label; 20–35 neutral-site games a season —
   recon.
6. 13–14 FBS-vs-FBS games a season lack drives in 2014–2016 (1 in 2019, 0 after) —
   recon; gated.
7. `overUnderOpen` has no capture time — Release A, `docs/pregame-replay-2026-09-22.md`.
8. A ~270-column weighted normal-equation solve per cutoff is fast enough for ~12 seasons
   × ~15 cutoffs × 12 λ values — convention; checked during build.

## Risks / open questions

- **2023 clock-rule change** shifted possessions. $\nu$ and $\mu$ are refit each season,
  so level shifts are absorbed; the train mean (pooled since 2014) is not, which makes it
  a weaker baseline in 2023+. Bias is reported per season so this is visible.
- **Team PPP includes defensive/return TDs**, so defense ratings absorb opponents' return
  scores. Small; named in docs.
- **Neutral pace and garbage time** are not handled (guide open item 5, §7.2 caution).
- **Encompassing slope** on ~600 games a season has wide intervals; pooled is the
  headline.
- **Line-score OT attribution**: games with no OT have $c$ contribution 0; if a season's
  line scores ever lack OT periods, OT points would read as 0 — checked by the
  sum-to-final assertion at load.

## Out of scope

Previous-season priors and prior-centered ridge; garbage-time filter; neutral
seconds-per-play pace; Ridge/elastic net on a feature block; Optuna; GUI; warehouse
tables; writes to `games.csv`, `features.json`, `FEATURE_REGISTRY`, `cfb.duckdb`,
MotherDuck; bet grading, return figures, cover rates, closing-line comparisons,
thresholds; FBS–FCS ratings; 2020 and 2026 seasons.
