"""Tune and score prior_v1 (previous-season priors) against Release B's ridge_v1.

    python -m scripts.weekly_priors_eval --tune-seasons 2015-2019 --score-seasons 2021-2025

Steps, all on pre-2021 seasons until scoring:
  1. Release B's lambda (re-tuned on 2014-2019, must come back 40 / 8) fits every
     season's final ratings.
  2. Carryover coefficients b, c, b_D, a by OLS on the 2014->2015 ... 2018->2019 transitions.
  3. prior_v1's lambda by the same one-step-ahead component loss, now including week 1.
  4. 2021-2025 scored: Bovada open, train mean, raw_v1, ridge_v1, prior_v1 on the same
     games, in three populations (week 1, early weeks 2+, primary). Declared verdicts:
     prior_v1 - ridge_v1 on early 2+ and on primary. Week 1 has one cluster per season,
     so it gets per-season differences, not an interval.

Release B's own manifest and snapshots are not touched; this writes
data/processed/ratings/weekly_priors_{eval.json,snapshots.csv}.
See docs/superpowers/specs/2026-09-23-weekly-priors-design.md.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.pregame_replay_audit import _sha256, snapshot
from scripts.weekly_priors import (
    build_priors, carryover_pairs, final_ratings, fit_carryover, load_rp, season_teams,
    week1_ratings,
)
from scripts.weekly_ratings import _team_rows, fit_pace, fit_ppp, fit_ridge, fit_set, forecast_total
from scripts.weekly_ratings_eval import (
    BOOT_DRAWS, BOOT_SEED, MIN_PRIOR_GAMES, OPEN_PROVIDER, _range, _snapshot_rows, accuracy,
    classify_verdict, encompassing_slope, load, load_opens, paired_mae_diff, run_season, tune,
)

LAMBDA_PPP_GRID = (10, 20, 40, 80, 160, 320, 640)   # possessions
LAMBDA_PACE_GRID = (1, 2, 4, 8, 16, 32, 64)          # games
LAMBDA_STRESS = (0.5, 2.0)
COEF_STRESS = (0.5, 1.5)
B_TUNE_SEASONS = list(range(2014, 2020))
# Release B's recorded pooled differences (docs/weekly-ratings-2026-09-23.md). Recomputing
# them exactly is the check that adding priors did not change ridge_v1 or raw_v1.
B_POOLED = {("ridge", "raw"): -1.1381, ("ridge", "mean"): -0.8401}


def all_cutoffs(season_games: pd.DataFrame) -> pd.Series:
    return season_games.groupby("week")["kickoff"].min()


def prior_ratings(games, season, cut, lam_ppp, lam_pace, prior, final_prev):
    """No games before the cutoff yet: the priors with last season's levels."""
    fs = fit_set(games[games["season"] == season], cut)
    if fs.empty:
        return week1_ratings(final_prev, prior)
    return fit_ridge(fs, lam_ppp, lam_pace, prior)


def tune_prior(games, seasons, priors, finals) -> dict:
    """One-step-ahead component loss for prior_v1, week 1 included."""
    loss_ppp = dict.fromkeys(LAMBDA_PPP_GRID, 0.0)
    loss_pace = dict.fromkeys(LAMBDA_PACE_GRID, 0.0)
    n_cutoffs = week1_ppp = week1_pace = 0
    for s in seasons:
        sg, pr, prev = games[games["season"] == s], priors[s], finals[s - 1]
        for week, cut in all_cutoffs(sg).items():
            fs = fit_set(sg, cut)
            target = sg[(sg["week"] == week) & ~sg["gated"]]
            if target.empty:
                continue
            n_cutoffs += 1
            rows = _team_rows(target)

            def ppp_loss(mu, h, o, d):
                pred = (mu + rows["team"].map(o).fillna(rows["team"].map(pr["O0"])).fillna(0)
                        + rows["opp"].map(d).fillna(rows["opp"].map(pr["D0"])).fillna(0)
                        + h * rows["H"])
                return float((rows["w"] * (rows["y"] - pred) ** 2).sum())

            def pace_loss(nu, p):
                fill = lambda t: t.map(p).fillna(t.map(pr["P0"])).fillna(0)  # noqa: E731
                pred = nu + fill(target["home"]) + fill(target["away"])
                return float(((target["N"] - pred) ** 2).sum())

            if fs.empty:  # week 1: the priors alone, the same for every lambda
                lp, lq = ppp_loss(prev.mu, prev.h, pr["O0"], pr["D0"]), pace_loss(prev.nu, pr["P0"])
                week1_ppp, week1_pace = week1_ppp + lp, week1_pace + lq
                for lam in LAMBDA_PPP_GRID:
                    loss_ppp[lam] += lp
                for lam in LAMBDA_PACE_GRID:
                    loss_pace[lam] += lq
                continue
            for lam in LAMBDA_PPP_GRID:
                mu, h, od = fit_ppp(fs, lam, pr)
                loss_ppp[lam] += ppp_loss(mu, h, od["O"], od["D"])
            for lam in LAMBDA_PACE_GRID:
                nu, p = fit_pace(fs, lam, pr)
                loss_pace[lam] += pace_loss(nu, p)

    def pick(losses, grid):
        best = min(losses, key=losses.get)
        return {"lambda": best, "loss_by_lambda": {str(k): round(v, 3) for k, v in losses.items()},
                "pick_on_grid_boundary": best in (grid[0], grid[-1])}

    return {"seasons": seasons, "n_cutoffs": n_cutoffs,
            "week1_loss": {"ppp": round(week1_ppp, 3), "pace": round(week1_pace, 3)},
            "ppp": pick(loss_ppp, LAMBDA_PPP_GRID), "pace": pick(loss_pace, LAMBDA_PACE_GRID)}


def score_prior_season(games, season, lam, prior_by_scale, final_prev, opens):
    """prior_v1 (and its stress variants) for every game of `season`, week 1 included."""
    sg = games[games["season"] == season]
    base = prior_by_scale[1.0]
    variants = {"prior": (lam[0], lam[1], base)}
    variants |= {f"prior_lam_x{k:g}": (lam[0] * k, lam[1] * k, base) for k in LAMBDA_STRESS}
    variants |= {f"prior_coef_x{k:g}": (lam[0], lam[1], prior_by_scale[k]) for k in COEF_STRESS}
    rows, snaps = [], []
    for week, cut in all_cutoffs(sg).items():
        fitted = {name: prior_ratings(games, season, cut, lp, lq, pr, final_prev)
                  for name, (lp, lq, pr) in variants.items()}
        snaps.append(_snapshot_rows(season, week, cut, "prior_v1", fitted["prior"], *lam)
                     .assign(lambda_ppp=lam[0], lambda_pace=lam[1])
                     .merge(base[["O0", "D0", "P0", "rp", "prior_source"]],
                            left_on="team", right_index=True, how="left"))
        train_mean = snapshot(games, cut)["total"].mean()
        for g in sg[sg["week"] == week].itertuples():
            row = {"season": season, "week": int(week), "game_id": g.game_id, "total": g.total,
                   "open": opens.get(g.game_id), "mean_all_weeks": train_mean}
            row |= {name: forecast_total(r, g.home, g.away, g.neutral) for name, r in fitted.items()}
            rows.append(row)
    return pd.DataFrame(rows), snaps


def week1_report(w1: pd.DataFrame) -> dict:
    """Per-season week-1 differences; one cluster per season, so no interval."""
    out = {}
    for comp in ("mean_all_weeks", "open"):
        d = (w1["prior"] - w1["total"]).abs() - (w1[comp] - w1["total"]).abs()
        by = d.groupby(w1["season"]).mean()
        out[f"prior_vs_{comp.replace('_all_weeks', '')}"] = {
            "pooled_point": round(float(d.mean()), 4),
            "by_season": {int(s): round(float(v), 4) for s, v in by.items()},
            "seasons_prior_closer": int((by < 0).sum()), "seasons": int(len(by)),
        }
    return {"n": int(len(w1)), "accuracy": accuracy(w1, ["open", "mean_all_weeks", "prior"]),
            **out}


def evaluate(scored: pd.DataFrame) -> dict:
    has_open = scored["open"].notna()
    week1 = scored[has_open & (scored["week"] == 1)]
    later = scored[has_open & (scored["week"] >= 2)]
    early = later[later["min_prior_games"] < MIN_PRIOR_GAMES]
    primary = later[later["min_prior_games"] >= MIN_PRIOR_GAMES]
    stress_cols = [c for c in scored.columns if c.startswith("prior_")]

    def verdict(pop, col):
        p = paired_mae_diff(pop, col, "ridge")
        return {**p, "verdict": classify_verdict(*p["ci95"], list(p["by_season"].values()))}

    verdicts = {}
    for name, pop in (("early_2plus", early), ("primary", primary)):
        v = verdict(pop, "prior")
        v["stress"] = {c: {k: x[k] for k in ("diff", "ci95", "by_season", "verdict")}
                       for c, x in ((c, verdict(pop, c)) for c in stress_cols)}
        v["stable_under_stress"] = all(x["verdict"] == v["verdict"] for x in v["stress"].values())
        verdicts[f"prior_vs_ridge_{name}"] = v
    go = (verdicts["prior_vs_ridge_early_2plus"]["verdict"] == "improves"
          and verdicts["prior_vs_ridge_primary"]["verdict"] != "worse"
          and all(v["stable_under_stress"] for v in verdicts.values()))

    five = ["open", "mean", "raw", "ridge", "prior"]
    four = ["open", "mean", "ridge", "prior"]  # raw has no forecast for teams without games
    return {
        "populations": {"week1": int(len(week1)), "early_2plus": int(len(early)),
                        "primary": int(len(primary))},
        "go": go,
        "verdicts": verdicts,
        "week1": week1_report(week1),
        "early_2plus": {
            "accuracy_pooled": accuracy(early, four),
            "accuracy_by_season": {int(s): accuracy(g, four) for s, g in early.groupby("season")},
            "prior_vs_open": paired_mae_diff(early, "prior", "open"),
            "prior_vs_mean": paired_mae_diff(early, "prior", "mean"),
            "encompassing_vs_open": encompassing_slope(early, "prior"),
        },
        "primary": {
            "accuracy_pooled": accuracy(primary, five),
            "accuracy_by_season": {int(s): accuracy(g, five) for s, g in primary.groupby("season")},
            "prior_vs_open": paired_mae_diff(primary, "prior", "open"),
            "encompassing_vs_open": encompassing_slope(primary, "prior"),
        },
        "release_b_check": {f"{a}_vs_{b}": paired_mae_diff(primary, a, b)["diff"]
                            for a, b in B_POOLED},
        # Post-hoc and descriptive, not a verdict: the declared lambda stress moves prior_v1
        # against ridge_v1 at its tuned lambda, which mixes the prior's effect with ridge's
        # own lambda curve. This compares both at the same stressed lambda.
        "matched_lambda_descriptive": {
            f"lambda_x{k:g}": {
                name: {x: p[x] for x in ("diff", "ci95", "by_season")}
                for name, pop in (("early_2plus", early), ("primary", primary))
                for p in [paired_mae_diff(pop, f"prior_lam_x{k:g}", f"ridge_x{k:g}")]
            } for k in LAMBDA_STRESS
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tune-seasons", type=_range, default=_range("2015-2019"))
    ap.add_argument("--score-seasons", type=_range, default=_range("2021-2025"))
    args = ap.parse_args(argv)

    from cfb_paths import DATA_ROOT, PROCESSED

    tune_seasons, score_seasons = args.tune_seasons, args.score_seasons
    loaded = list(range(min(B_TUNE_SEASONS), max(score_seasons) + 1))
    sources: list[Path] = []
    games, drops = load(DATA_ROOT, loaded, sources)
    opens = load_opens(DATA_ROOT, score_seasons, sources)
    rp = {s: load_rp(DATA_ROOT, s, sources) for s in tune_seasons + score_seasons}

    b_tuned = tune(games, B_TUNE_SEASONS)
    b_lam = (b_tuned["ppp"]["lambda"], b_tuned["pace"]["lambda"])
    finals = {s: final_ratings(games, s, *b_lam) for s in range(min(tune_seasons) - 1, max(score_seasons))}

    pairs = pd.concat([carryover_pairs(finals[s - 1], finals[s], rp[s]).assign(season=s)
                       for s in tune_seasons], ignore_index=True)
    coefs = fit_carryover(pairs)

    def priors_at(s, scale=1.0):
        return build_priors(finals[s - 1], rp[s], season_teams(games, s), coefs, scale)

    tuned = tune_prior(games, tune_seasons, {s: priors_at(s) for s in tune_seasons}, finals)
    lam = (tuned["ppp"]["lambda"], tuned["pace"]["lambda"])

    scored, snaps, prior_sources = [], [], {}
    for s in score_seasons:
        by_scale = {k: priors_at(s, k) for k in (1.0, *COEF_STRESS)}
        prior_sources[s] = by_scale[1.0]["prior_source"].value_counts().to_dict()
        b_rows, _ = run_season(games, s, *b_lam, opens)
        p_rows, sn = score_prior_season(games, s, lam, by_scale, finals[s - 1], opens)
        snaps += sn
        b_rows = b_rows[["game_id", "mean", "raw", "ridge", "min_prior_games",
                         *(f"ridge_x{k:g}" for k in LAMBDA_STRESS)]]
        merged = p_rows.merge(b_rows, on="game_id", how="left")
        # Week 1 has no Release B forecast and no prior games; its mean is the one computed here.
        merged["mean"] = merged["mean"].fillna(merged["mean_all_weeks"])
        merged["min_prior_games"] = merged["min_prior_games"].fillna(0).astype(int)
        scored.append(merged)
    scored = pd.concat(scored, ignore_index=True)
    results = evaluate(scored)

    b_default = (tune_seasons == list(range(2015, 2020)) and score_seasons == list(range(2021, 2026)))
    if b_default:
        for (a, b), want in B_POOLED.items():
            got = results["release_b_check"][f"{a}_vs_{b}"]
            if abs(got - want) > 5e-5:
                raise SystemExit(f"Release B check failed: {a} - {b} = {got}, recorded {want}")

    out_dir = PROCESSED / "ratings"
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.concat(snaps, ignore_index=True).to_csv(out_dir / "weekly_priors_snapshots.csv", index=False)
    manifest = {
        "command": "python -m scripts.weekly_priors_eval --tune-seasons "
                   f"{tune_seasons[0]}-{tune_seasons[-1]} --score-seasons "
                   f"{score_seasons[0]}-{score_seasons[-1]}",
        "code_sha256": {p: _sha256(Path(__file__).parent / p)
                        for p in ("weekly_priors_eval.py", "weekly_priors.py", "weekly_ratings.py",
                                  "weekly_ratings_eval.py", "pregame_replay_audit.py")},
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_root": str(DATA_ROOT),
        "seasons": {"tune": tune_seasons, "score": score_seasons, "loaded": loaded,
                    "release_b_tune": B_TUNE_SEASONS},
        "market": {"provider": OPEN_PROVIDER, "field": "overUnderOpen",
                   "clock": "vendor_open_label_only (docs/pregame-replay-2026-09-22.md)"},
        "release_b_lambda": {"ppp": b_lam[0], "pace": b_lam[1]},
        "release_b_check_passed": b_default,
        "carryover": {**coefs, "transitions": [f"{s - 1}->{s}" for s in tune_seasons],
                      "rp_field": "returning_production.percentPPA"},
        "prior_sources_by_season": prior_sources,
        "tuning": tuned,
        "trial_count": {"lambda_grid_points": len(LAMBDA_PPP_GRID) + len(LAMBDA_PACE_GRID),
                        "prior_coefficients": 4, "methods_added": 1,
                        "stress_variants": len(LAMBDA_STRESS) + len(COEF_STRESS)},
        "bootstrap": {"unit": "season-week", "draws": BOOT_DRAWS, "seed": BOOT_SEED},
        "drops_by_season": drops,
        "results": results,
        "source_files": [{"path": str(p), "sha256": _sha256(p)} for p in dict.fromkeys(sources)],
    }
    out = out_dir / "weekly_priors_eval.json"
    out.write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")

    print(f"release B lambda {b_lam}, check passed: {b_default}")
    print("carryover", {k: (round(v["value"], 3), round(v["se"], 3)) for k, v in coefs.items()})
    print(f"prior_v1 lambda_ppp={lam[0]} lambda_pace={lam[1]}")
    for key, v in results["verdicts"].items():
        print(f"{key}: diff {v['diff']} ci95 {v['ci95']} mde80 {v['mde80']} -> {v['verdict']}"
              f" (stable: {v['stable_under_stress']})")
    print(f"go: {results['go']}")
    print(f"manifest: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
