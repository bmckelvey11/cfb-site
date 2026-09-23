"""Re-tune the rating penalties jointly on one-step-ahead total-forecast error.

    python -m scripts.weekly_total_tuning

Release B tuned lambda_ppp and lambda_pace separately on component losses; the thing
scored is the total, which couples them. This tunes the pair on total MAE over pre-2021
seasons (ridge 2014-2019, weeks 2+; priors 2015-2019, weeks 1+), then scores 2021-2025:
ridge_v2 - ridge_v1, and prior_v2 - ridge_v2 with the priors go rule under coefficient
stress and matched-lambda stress. Declared before scoring in
docs/superpowers/specs/2026-09-23-lambda-total-tuning-design.md.

Writes data/processed/ratings/weekly_total_tuning_eval.json only.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.pregame_replay_audit import _sha256
from scripts.weekly_priors import (
    build_priors, carryover_pairs, final_ratings, fit_carryover, load_rp, season_teams,
    week1_ratings,
)
from scripts.weekly_priors_eval import COEF_STRESS, LAMBDA_STRESS, score_prior_season, week1_report
from scripts.weekly_ratings import fit_pace, fit_ppp, fit_set, forecast_total
from scripts.weekly_ratings_eval import (
    BOOT_DRAWS, BOOT_SEED, MIN_PRIOR_GAMES, OPEN_PROVIDER, accuracy, classify_verdict,
    encompassing_slope, load, load_opens, paired_mae_diff, run_season,
)

GRID_PPP = (10, 20, 40, 80, 160, 320, 640)    # possessions
GRID_PACE = (1, 2, 4, 8, 16, 32, 64)          # games
RIDGE_V1 = (40, 8)
RIDGE_TUNE = list(range(2014, 2020))
PRIOR_TUNE = list(range(2015, 2020))
SCORE = list(range(2021, 2026))


def tune_total(games, seasons, priors=None, finals=None, grid_ppp=GRID_PPP, grid_pace=GRID_PACE):
    """Joint (lambda_ppp, lambda_pace) minimizing one-step-ahead total MAE.

    With `priors` ({season: prior frame}) and `finals` ({season: Ratings}), this tunes
    prior_v2 and week 1 is scored from the priors; without, it tunes ridge from week 2.
    Only rows of `seasons` are read.
    """
    abs_err = {(a, b): 0.0 for a in grid_ppp for b in grid_pace}
    n = 0
    for s in seasons:
        sg = games[games["season"] == s]
        pr = priors[s] if priors else None
        for week, cut in sg.groupby("week")["kickoff"].min().items():
            target = sg[sg["week"] == week]
            fs = fit_set(sg, cut)
            if fs.empty:
                if pr is None:
                    continue
                r = week1_ratings(finals[s - 1], pr)
                e = sum(abs(forecast_total(r, g.home, g.away, g.neutral) - g.total)
                        for g in target.itertuples())
                abs_err = {k: v + e for k, v in abs_err.items()}  # the same for every lambda
                n += len(target)
                continue

            def rating(fitted: pd.Series, teams: pd.Series, prior_col: str) -> np.ndarray:
                out = teams.map(fitted)
                if pr is not None:
                    out = out.fillna(teams.map(pr[prior_col]))
                return out.fillna(0.0).to_numpy()

            ppp_sum = {}  # both teams' points per possession; home field cancels in the sum
            for a in grid_ppp:
                mu, _h, od = fit_ppp(fs, a, pr)
                ppp_sum[a] = (2 * mu + rating(od["O"], target["home"], "O0")
                              + rating(od["D"], target["away"], "D0")
                              + rating(od["O"], target["away"], "O0")
                              + rating(od["D"], target["home"], "D0"))
            poss = {}
            for b in grid_pace:
                nu, p = fit_pace(fs, b, pr)
                poss[b] = nu + rating(p, target["home"], "P0") + rating(p, target["away"], "P0")
            c, actual = float(fs["ot"].mean()), target["total"].to_numpy()
            for a in grid_ppp:
                for b in grid_pace:
                    abs_err[(a, b)] += float(np.abs(poss[b] * ppp_sum[a] + c - actual).sum())
            n += len(target)
    mae = {k: v / n for k, v in abs_err.items()}
    a, b = min(mae, key=mae.get)
    return {"lambda_ppp": float(a), "lambda_pace": float(b), "n_games": n,
            "pick_on_grid_boundary": a in (grid_ppp[0], grid_ppp[-1]) or b in (grid_pace[0], grid_pace[-1]),
            "mae_by_lambda": {f"{float(k[0]):g}/{float(k[1]):g}": round(v, 4) for k, v in mae.items()}}


def _verdict(pop, a, b):
    p = paired_mae_diff(pop, a, b)
    return {**p, "verdict": classify_verdict(*p["ci95"], list(p["by_season"].values()))}


def evaluate(scored: pd.DataFrame, ridge_unchanged: bool) -> dict:
    has_open = scored["open"].notna()
    later = scored[has_open & (scored["week"] >= 2)]
    pops = {"early_2plus": later[later["min_prior_games"] < MIN_PRIOR_GAMES],
            "primary": later[later["min_prior_games"] >= MIN_PRIOR_GAMES]}

    ridge_cmp = {name: ("lambda unchanged" if ridge_unchanged else _verdict(pop, "ridge_v2", "ridge_v1"))
                 for name, pop in pops.items()}

    prior_cmp = {}
    for name, pop in pops.items():
        v = _verdict(pop, "prior", "ridge_v2")
        stress = {f"coef_x{k:g}": ("prior_coef_x%g" % k, "ridge_v2") for k in COEF_STRESS}
        stress |= {f"matched_lambda_x{k:g}": ("prior_lam_x%g" % k, "ridge_x%g" % k) for k in LAMBDA_STRESS}
        v["stress"] = {key: {x: r[x] for x in ("diff", "ci95", "by_season", "verdict")}
                       for key, (fa, fb) in stress.items() for r in [_verdict(pop, fa, fb)]}
        v["stable_under_stress"] = all(r["verdict"] == v["verdict"] for r in v["stress"].values())
        prior_cmp[name] = v
    go = (prior_cmp["early_2plus"]["verdict"] == "improves"
          and prior_cmp["primary"]["verdict"] != "worse"
          and all(v["stable_under_stress"] for v in prior_cmp.values()))

    cols = ["open", "mean", "ridge_v1", "ridge_v2", "prior"]
    return {
        "populations": {k: int(len(v)) for k, v in pops.items()},
        "ridge_v2_vs_ridge_v1": ridge_cmp,
        "prior_v2_vs_ridge_v2": prior_cmp,
        "prior_go": go,
        "accuracy": {name: {"pooled": accuracy(pop, cols),
                            "by_season": {int(s): accuracy(g, cols) for s, g in pop.groupby("season")}}
                     for name, pop in pops.items()},
        "vs_open": {name: {c: paired_mae_diff(pop, c, "open") for c in ("ridge_v2", "prior")}
                    for name, pop in pops.items()},
        "encompassing_vs_open": {name: {c: encompassing_slope(pop, c) for c in ("ridge_v2", "prior")}
                                 for name, pop in pops.items()},
        "week1": week1_report(scored[has_open & (scored["week"] == 1)]),
    }


def main() -> int:
    from cfb_paths import DATA_ROOT, PROCESSED

    sources: list[Path] = []
    loaded = list(range(min(RIDGE_TUNE), max(SCORE) + 1))
    games, _drops = load(DATA_ROOT, loaded, sources)
    opens = load_opens(DATA_ROOT, SCORE, sources)
    rp = {s: load_rp(DATA_ROOT, s, sources) for s in PRIOR_TUNE + SCORE}

    ridge_tuned = tune_total(games, RIDGE_TUNE)
    ridge_lam = (ridge_tuned["lambda_ppp"], ridge_tuned["lambda_pace"])

    # Priors are built exactly as in the priors release: from ridge_v1 final ratings.
    finals = {s: final_ratings(games, s, *RIDGE_V1) for s in range(min(PRIOR_TUNE) - 1, max(SCORE))}
    pairs = pd.concat([carryover_pairs(finals[s - 1], finals[s], rp[s]) for s in PRIOR_TUNE],
                      ignore_index=True)
    coefs = fit_carryover(pairs)

    def priors_at(s, scale=1.0):
        return build_priors(finals[s - 1], rp[s], season_teams(games, s), coefs, scale)

    prior_tuned = tune_total(games, PRIOR_TUNE, {s: priors_at(s) for s in PRIOR_TUNE}, finals)
    prior_lam = (prior_tuned["lambda_ppp"], prior_tuned["lambda_pace"])

    scored = []
    for s in SCORE:
        v1, _ = run_season(games, s, *RIDGE_V1, opens)
        v2, _ = run_season(games, s, *ridge_lam, opens)
        by_scale = {k: priors_at(s, k) for k in (1.0, *COEF_STRESS)}
        pr, _ = score_prior_season(games, s, prior_lam, by_scale, finals[s - 1], opens)
        merged = pr.merge(v1[["game_id", "mean", "ridge", "min_prior_games"]]
                          .rename(columns={"ridge": "ridge_v1"}), on="game_id", how="left")
        merged = merged.merge(v2[["game_id", "ridge", *(f"ridge_x{k:g}" for k in LAMBDA_STRESS)]]
                              .rename(columns={"ridge": "ridge_v2"}), on="game_id", how="left")
        merged["mean"] = merged["mean"].fillna(merged["mean_all_weeks"])
        merged["min_prior_games"] = merged["min_prior_games"].fillna(0).astype(int)
        scored.append(merged)
    scored = pd.concat(scored, ignore_index=True)
    results = evaluate(scored, ridge_unchanged=ridge_lam == RIDGE_V1)

    manifest = {
        "command": "python -m scripts.weekly_total_tuning",
        "design": "docs/superpowers/specs/2026-09-23-lambda-total-tuning-design.md",
        "code_sha256": {p: _sha256(Path(__file__).parent / p)
                        for p in ("weekly_total_tuning.py", "weekly_priors_eval.py", "weekly_priors.py",
                                  "weekly_ratings.py", "weekly_ratings_eval.py")},
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_root": str(DATA_ROOT),
        "seasons": {"ridge_tune": RIDGE_TUNE, "prior_tune": PRIOR_TUNE, "score": SCORE},
        "market": {"provider": OPEN_PROVIDER, "field": "overUnderOpen",
                   "clock": "vendor_open_label_only (docs/pregame-replay-2026-09-22.md)"},
        "ridge_v1_lambda": list(RIDGE_V1),
        "ridge_v2_tuning": ridge_tuned,
        "prior_v2_tuning": prior_tuned,
        "carryover": coefs,
        "trial_count": {"grid_points": 2 * len(GRID_PPP) * len(GRID_PACE), "methods_scored": 2},
        "bootstrap": {"unit": "season-week", "draws": BOOT_DRAWS, "seed": BOOT_SEED},
        "results": results,
        "source_files": [{"path": str(p), "sha256": _sha256(p)} for p in dict.fromkeys(sources)],
    }
    out = PROCESSED / "ratings" / "weekly_total_tuning_eval.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")

    print(f"ridge_v2 lambda {ridge_lam} (v1 {RIDGE_V1}); prior_v2 lambda {prior_lam}")
    for name, r in results["ridge_v2_vs_ridge_v1"].items():
        print(f"ridge_v2 - ridge_v1 {name}:",
              r if isinstance(r, str) else f"{r['diff']} {r['ci95']} -> {r['verdict']}")
    for name, r in results["prior_v2_vs_ridge_v2"].items():
        print(f"prior_v2 - ridge_v2 {name}: {r['diff']} {r['ci95']} -> {r['verdict']}"
              f" (stable: {r['stable_under_stress']})")
    print(f"prior go: {results['prior_go']}")
    print(f"manifest: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
