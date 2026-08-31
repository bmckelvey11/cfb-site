# Repo review — paper_models

*2026-07-30. Full review: code, structure, docs, and an econometrics audit of the
analyses (leakage, dependence, power, multiplicity, scoring). Severity labels:
**Critical** blocks use, unlabeled items are recommended, **Consider**/**Nit**
are optional. Methodology findings use BLOCKER/CAVEAT/NOTE.*

**TLDR.** The science is unusually honest and well-organized for a research repo
— frozen baseline, negative results published, adversarial self-checks (v3),
caveats proven immaterial rather than asserted (v2). Verdict on the analyses:
**sound-with-caveats** — the market-inefficiency replication is strong; the
"deployable edge" numbers rest on randomized (time-mixed) cross-validation and
in-sample thresholds, and want a walk-forward backtest before being treated as
tradable. The code has one real bug: `v1 --raw`, the README's recommended
headline command, is broken in this extracted repo (bad path). Docs drifted in
the extraction; `monitor/` is undocumented.

## What was run to verify

| Check | Result |
|---|---|
| `python v1/demo_reproduce.py` (synthetic self-test) | ✅ Tobit recovers planted σ (11.29/11.94 vs true 11.28/11.94); probit slope positive; pipeline sound |
| `python v2/run_v2.py --season 2024` | ✅ loads 1,502 games from sibling `cfb-site`, OPG vs BFGS SEs agree |
| `python v1/run_on_project_data.py --raw --season 2024` | ❌ loads 0 games, then crashes with a traceback (bug 1) |
| `git ls-files` / status | ✅ clean; `__pycache__` correctly untracked; no secrets |

---

## Code & repo findings

### 1. Critical — `v1 --raw` is broken: `RAW_DIR` points at a nonexistent directory

[run_on_project_data.py:28](v1/run_on_project_data.py:28):

```python
REPO = Path(__file__).resolve().parents[2]          # -> dev/
DEFAULT_CSV = REPO / "cfb-site" / "data" / "processed" / "games.csv"   # ✅ fixed in extraction
RAW_DIR = REPO / "data" / "raw"                      # ❌ dev/data/raw does not exist
```

When the repo was extracted from `cfb-site`, `parents[1]` became `parents[2]`
and `DEFAULT_CSV` gained the `cfb-site` segment — but `RAW_DIR` didn't. Every
season prints `(no raw file for …)`, 0 games load, and `ols_line_test` crashes
on the empty array. This is the exact command the v1 README recommends for the
headline 13-season backtest. v2/v3/saturation/monitor all have the correct
path (`parents[2] / "cfb-site" / "data" / "raw"`), so only v1 is affected.

**Fix (one line):** `RAW_DIR = REPO / "cfb-site" / "data" / "raw"`. v1 is
frozen, but the freeze protects the model logic and results — not a path bug
introduced by the move. Fixing it *restores* the frozen behavior.

### 2. Stale run commands and docstrings (extraction drift)

- [v1/README.md:80-88](v1/README.md) — `python paper_models/run_on_project_data.py …`
  and `python paper_models/demo_reproduce.py` are the pre-extraction paths; in
  this repo they're `v1/run_on_project_data.py`, `v1/demo_reproduce.py`.
- [run_on_project_data.py:8](v1/run_on_project_data.py:8) — docstring says
  `[path/to/games.csv]` positional; the actual interface is `--csv`.
- The other modules' docstrings/READMEs use `python paper_models/v2/run_v2.py`,
  which only works when your CWD is `dev/` (it resolves through the repo *dir
  name*). From the repo root it fails. Standardize every run command to
  repo-root-relative (`python v2/run_v2.py`).

### 3. `monitor/` is undocumented

Absent from the root README's module list and has no README of its own — yet
it's the operationally load-bearing piece (edge-decay tracking is what tells
you when to stop betting the edge). Add a bullet in [README.md](README.md)'s
Extensions section and a short `monitor/README.md` (what the flags `SLOPE~0` /
`UNPROF` mean, sample output).

### 4. No dependency manifest

Deps are numpy, scipy, statsmodels (v1 needs only the first two). Add a
3-line `requirements.txt` (or a minimal `pyproject.toml`, which would also
solve finding 6) and note the Python version you run (3.14 works today).

### 5. Turn the demo into a real self-test

[demo_reproduce.py](v1/demo_reproduce.py) already *is* the regression test —
it recovers planted parameters — but it only prints. Four asserts at the end
(`abs(sigma_dog − 11.28) < 0.15`, same for fav, `probit.slope > 0`, hurdle
bias in a sane range) make it fail loudly when shared code regresses. That's
the entire test suite this repo needs; v2/v3/saturation/1h/monitor all lean on
`models_v2`, so one canary covers a lot.

### 6. Consider — `load_from_raw` is copy-pasted five times

Identical ~25-line loader in [run_v2.py:31](v2/run_v2.py:31),
[run_v3.py:24](v3/run_v3.py:24),
[run_saturation.py:24](saturation_bias/run_saturation.py:24),
[monitor.py:37](monitor/monitor.py:37) (per-season variant), plus the
game-line block inside [floor_bias_1h.py:99](floor_bias_1h/floor_bias_1h.py:99).
A CFBD schema change means five edits. v1's copy stays (frozen); move one
canonical loader into `models_v2.py` — every non-frozen module already imports
from there via the `sys.path` shim — and delete the rest. Net ~80-line
deletion. The `sys.path.insert` shims themselves are fine for a research repo
(they're `__file__`-anchored, so they work from any CWD); a pyproject +
`pip install -e .` would remove them if you ever tire of them.

### 7. Nits

- [models_v2.py:37-39](v2/models_v2.py:37) — section header says "Shared with
  v1 (verbatim behavior)" but `kelly_bankroll_roi` default is `fraction=0.25`
  vs v1's `1.0`. Dormant (every call site passes it explicitly), but either
  restore the default or drop "verbatim".
- [censoring_bias.py:138](v1/censoring_bias.py:138) — comment says the Tobit
  starts from "OLS on the observed (uncensored) points"; it's OLS on *all*
  points. Harmless (starting values only), inaccurate comment.
- [censoring_bias.py:244-246](v1/censoring_bias.py:244) —
  `log_likelihood_ratio` produces `log(0)` when a small fold goes 0-for-N or
  N-for-N (reachable: saturation's OOS folds had 6 bets). Clip `phat` into
  `[1/(2N), 1−1/(2N)]`.
- [models_v3.py:110](v3/models_v3.py:110) — `n=int(y.sum() * 0 + y.size)` is
  `int(y.size)`.
- [run_v3.py:104](v3/run_v3.py:104) (and run_saturation, run_1h) — wins are
  reconstructed via `round(win_rate * n_bets)`; store the win count in the
  fold result instead.
- [floor_bias_1h.py:117](floor_bias_1h/floor_bias_1h.py:117) —
  `sum(hl[:2])` raises `TypeError` if CFBD ever ships a null quarter entry;
  cheap guard if you re-scrape.
- [floor_bias_1h/chat_history.md](floor_bias_1h/chat_history.md) — a
  1,358-line session transcript (with local machine paths) committed next to
  the model. If it's deliberate provenance, keep it, but consider a `docs/` or
  `notes/` home; it's the only module carrying dev exhaust.

---

## Methodology audit (econometrics)

Full-audit depth. The distinction that organizes everything below: the repo
makes a **strong claim** (the totals market ignores censoring — probit slope
+0.176, analytic SE 0.028, p ≈ 6e−10) and a **moderate claim** (you could have
made money: 56.62% over 680 bets). The strong claim is a replication of a
published, pre-registered hypothesis on *non-overlapping years* (2013–2025 vs
the paper's 1992–2017) — that's the best kind of evidence and the repo should
say so more loudly. The moderate claim: 56.62% vs the 52.38% breakeven is
p ≈ 0.027 (Wilson 95% CI [52.9%, 60.3%] — lower bound 0.5 pp above breakeven).
Real, but one bad season of variance sits inside that interval.

### CAVEAT — randomized k-fold mixes time; no walk-forward backtest

- **What**: [kfold_cross_validate](v1/censoring_bias.py:382) (and v3's
  bake-off, saturation, 1h) shuffle all seasons together, so training folds
  contain games played *after* the test games. The headline per-season table in
  v1's README is in-sample (flagged as such).
- **Why it bites here**: fine as a replication of the paper's own Table 6
  protocol; not fine as support for "≈ +22%/yr" deployability, because a real
  bettor trains only on the past. Scoring environments drift (2023/2024 clock
  rules), so future-trained σ and probit are mildly informative about the past
  in a way no deployed model can be.
- **Resolves with**: an expanding-window backtest — train on seasons ≤ t−1,
  bet season t, for t = 2016…2025. All pieces exist (monitor already loads
  per-season). This is the single highest-value computation the repo hasn't
  run. Monitor's stability tables suggest it will survive; that's exactly what
  the run would settle.

### CAVEAT — independence assumed across games in all SEs and tests

- **What**: probit SEs, LR tests, and Wilson CIs treat games as iid. Games
  share weeks (weather shocks, slate-wide pace) and seasons (rule changes).
- **Why it bites here**: p = 6e−10 on the slope has enormous headroom and will
  survive clustering; the strategy-level p ≈ 0.027 vs breakeven has much less.
  Quoted p-values should be robust to the obvious clustering before being
  cited outside the repo.
- **Resolves with**: season-clustered (or season×week) SEs on the probit —
  statsmodels `fit(cov_type="cluster", …)` is a one-line change in
  `probit_win_v2`.

### NOTE — book-selection robustness

The loader prefers `consensus` else the *first* book carrying both lines. The
first book is arbitrary and could systematically be a softer line, flattering
the edge (the raw path recovers ~2,800 games the consensus build drops —
those extra games are by construction non-consensus). Re-run the headline
(bias > 1.0 win%) on the consensus-only subset; if it holds within a point,
done. One sensitivity table, cheap.

### NOTE — sequential Kelly compounding overstates achievable growth

`kelly_bankroll_roi` compounds bet-by-bet in sequence, but the 680 bets
cluster on Saturday slates — you cannot size bet *i+1* on the settled outcome
of bet *i* within the same slate. Simultaneous-Kelly on a slate stakes less
and compounds slower. The +1288% pooled figure is the flashiest number in the
v1 README and the least meaningful; the README's own caveat says as much —
consider demoting it to a footnote and letting win%/unit% lead.

### NOTE — per-season monitor windows are underpowered by design

At N ≈ 20–100 bets/season, the win% CI half-width is ±10–14 pp against an edge
of ~4 pp over breakeven — the `UNPROF` flag will fire routinely on noise, and
`SLOPE~0` similarly. The 3-season trailing window (N ≈ 250, ±6 pp) is the
smallest honest unit; per-season rows are best treated as descriptive. Also
[slope_trend](monitor/monitor.py:136) regresses estimated slopes without
weighting by their SEs — inverse-variance weights (WLS) are the standard
meta-regression and free to add. With 13 seasons neither change flips
anything today; they matter as seasons accumulate.

### NOTE — saturation ceiling grid reuses the evaluation folds

[select_ceiling](saturation_bias/saturation.py:108) picks C by OOS log-loss on
the same folds later used to evaluate the under strategy. Had the result been
positive, that would demand nested CV. Since the result is negative, the
optimism cuts *against* the conclusion — a slightly flattered eval still
failed — so the negative verdict stands. Worth one line in that README.

### Checked and fine

- **Generated regressor**: `biasTotals` is built from estimated Tobit σ; with
  n ≈ 12k the σ SE (~0.1 on 11) contributes negligible attenuation.
- **Scaling leakage**: v3 standardizes features on the training fold and
  applies train μ/σ to test — correct.
- **Pushes** dropped before every binomial fit/test; pick'em games excluded —
  matches the paper.
- **Proper scoring**: v3's bake-off compares specs on log-loss with a shared
  fold split (paired) — right tool.
- **Multiplicity honesty**: thresholds (1.0/1.75) and the 52.38% hurdle are
  inherited from the paper, i.e. effectively pre-registered; negative results
  (saturation) and failed alternatives (v3) are published, not shelved. The
  1H module is where post-hoc selection lives (`total_frac = 0.52` chosen
  after seeing the excess) and it's correctly labeled "not a validated edge"
  — keep that label until real 1H lines arrive.
- **Selection/missingness**: games without both lines are dropped; that skews
  the sample toward liquid games, which is the *right* population for a
  tradability claim (you can only bet quoted markets).

### Verdict: sound-with-caveats

The inefficiency replication (biased totals line, positive bias→over slope) is
robust and would survive every caveat above. The profitability numbers are
directionally supported but rest on time-mixed CV and iid inference; run the
walk-forward backtest and cluster the SEs before citing 56.62% / +8.1% outside
this repo. Nothing found suggests the conclusion is wrong — the two CAVEATs
are about making the evidence match the strength of the claim.

---

## What's good (keep doing this)

- **Frozen baseline discipline** — v1 untouched, extensions build beside it.
- **Negative results committed** (saturation) with the mechanism for *why* the
  asymmetry is real. This is rarer than it should be.
- **Adversarial self-checks** — v3 attacks the repo's own headline ("is it
  just low totals?") with univariate/multivariate/OOS evidence.
- **Proving caveats instead of asserting them** — v2's OPG-vs-BFGS and
  ρ-invariance work.
- **A decay monitor** — treating the edge as perishable is the correct prior
  for a published anomaly.
- **Synthetic self-test** that recovers planted parameters.

## Recommended action order

1. Fix `RAW_DIR` in [run_on_project_data.py:28](v1/run_on_project_data.py:28) (one line; restores the frozen entry point).
2. Fix stale run commands/docstrings (v1 README + all module docstrings → repo-root-relative).
3. Add walk-forward backtest (train ≤ t−1, bet t) — the one new computation that upgrades the headline claim.
4. Cluster probit SEs by season (one line in `probit_win_v2`).
5. Document `monitor/` (root README bullet + short README).
6. Add `requirements.txt`; add asserts to `demo_reproduce.py`.
7. Consolidate `load_from_raw` into `models_v2.py` (delete 4 copies).
8. Consensus-only sensitivity table; demote the +1288% compounded figure.
9. Nits as touched: LR zero-guard, `n=int(y.size)`, wins in fold results, v2 "verbatim" header, chat_history relocation.

---

## Addendum — all fixes applied (2026-07-30)

Every item above landed the same day (commits `22ca204` … `32a43c3`). What the
new computations found — **both CAVEATs resolve in the model's favor**:

- **Walk-forward backtest** ([monitor/run_walkforward.py](monitor/run_walkforward.py),
  train ≤ t−1, bet t, first bet season 2016): rule A (bias > 1.0) pools
  **56.83% over 681 bets**, Wilson 95% [53.1%, 60.5%], unit +8.49%, LR vs
  breakeven p = 0.020; 9/10 test seasons profitable. Matches the in-sample
  56.62% — the edge is not a time-mixing artifact. The pooled Wilson lower
  bound clears breakeven under the honest protocol.
- **Season-clustered probit SEs**: slope +0.176 with clustered SE 0.0200
  (p ≈ 1e−18, 13 clusters — indicative) vs analytic iid SE 0.0284
  (p ≈ 6e−10). Significance is robust to clustering.
- **Consensus-only sensitivity**: 4,927 games / 282 bets at bias > 1.0 win
  **58.16%** (Wilson 95% [52.3%, 63.8%], unit +11.0%) vs 56.62% any-book —
  the edge is not an artifact of soft first-listed books.

Post-fix verdict upgrades from *sound-with-caveats* to **sound** for the
line-only strategy on 2013–2025 CFBD closing lines: the inefficiency claim and
the profitability claim now rest on the deployable protocol with
dependence-aware uncertainty. Remaining honest limits (unchanged): −110 flat
vig assumed, slate-level Kelly sizing not modeled (compounded figures are
upper bounds), and the 1H module still awaits real first-half lines.
