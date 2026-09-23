"""Tune one carryover scale on pre-2021 total loss, freeze it, confirm on 2026.

    python -m scripts.weekly_prior_scale tune                   # 2015-2019 only; writes the freeze
    python -m scripts.weekly_prior_scale confirm --season 2026  # reads the freeze; interim or final

The scale k multiplies every carryover coefficient (k = 0 is a prior-free ridge). It is
tuned jointly with lambda on one-step-ahead total MAE and written to
scripts/weekly_prior_v3.json, which is committed before any confirmation run. `confirm`
only reads that file; a run before the season's last regular-season week is complete is
labeled interim and carries no verdict. Declared in
docs/superpowers/specs/2026-09-23-prior-scale-2026-confirmation-design.md.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.pregame_replay_audit import _sha256
from scripts.weekly_priors import (
    build_priors, carryover_pairs, final_ratings, fit_carryover, load_rp, season_teams,
)
from scripts.weekly_priors_eval import COEF_STRESS, score_prior_season, week1_report
from scripts.weekly_ratings_eval import (
    BOOT_DRAWS, BOOT_SEED, MIN_PRIOR_GAMES, OPEN_PROVIDER, accuracy, classify_verdict, load,
    load_opens, paired_mae_diff, run_season,
)
from scripts.weekly_total_tuning import GRID_PACE, GRID_PPP, tune_total

FROZEN = Path(__file__).with_name("weekly_prior_v3.json")
SCALES = (0.0, 0.25, 0.5, 0.75, 1.0, 1.25)
TUNE = list(range(2015, 2020))
RIDGE_V1 = (40, 8)
CODE = ("weekly_prior_scale.py", "weekly_priors.py", "weekly_ratings.py", "weekly_total_tuning.py")


def tune_scale(games, seasons, finals, rp, coefs, scales=SCALES,
               grid_ppp=GRID_PPP, grid_pace=GRID_PACE) -> dict:
    """(k, lambda_ppp, lambda_pace) with the lowest one-step-ahead total MAE on `seasons`."""
    by_scale = {}
    for k in scales:
        priors = {s: build_priors(finals[s - 1], rp[s], season_teams(games, s), coefs, k)
                  for s in seasons}
        t = tune_total(games, seasons, priors, finals, grid_ppp, grid_pace)
        by_scale[f"{k:g}"] = {"lambda_ppp": t["lambda_ppp"], "lambda_pace": t["lambda_pace"],
                              "mae": min(t["mae_by_lambda"].values()), "n_games": t["n_games"],
                              "pick_on_grid_boundary": t["pick_on_grid_boundary"]}
    k, best = min(by_scale.items(), key=lambda kv: kv[1]["mae"])
    return {"scale": float(k), "lambda_ppp": best["lambda_ppp"], "lambda_pace": best["lambda_pace"],
            "mae": best["mae"], "scale_on_grid_boundary": float(k) in (scales[0], scales[-1]),
            "by_scale": by_scale}


def run_tune() -> dict:
    from cfb_paths import DATA_ROOT

    sources: list[Path] = []
    games, _ = load(DATA_ROOT, list(range(min(TUNE) - 1, max(TUNE) + 1)), sources)
    rp = {s: load_rp(DATA_ROOT, s, sources) for s in TUNE}
    finals = {s: final_ratings(games, s, *RIDGE_V1) for s in range(min(TUNE) - 1, max(TUNE) + 1)}
    pairs = pd.concat([carryover_pairs(finals[s - 1], finals[s], rp[s]) for s in TUNE],
                      ignore_index=True)
    coefs = fit_carryover(pairs)
    tuned = tune_scale(games, TUNE, finals, rp, coefs)
    frozen = {
        "candidate": "prior_v3",
        "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "design": "docs/superpowers/specs/2026-09-23-prior-scale-2026-confirmation-design.md",
        "tune_seasons": TUNE,
        "ridge_v1_lambda": list(RIDGE_V1),
        "coefficients": {k: v["value"] for k, v in coefs.items()},
        "coefficient_se": {k: v["se"] for k, v in coefs.items()},
        **tuned,
        "code_sha256": {p: _sha256(Path(__file__).parent / p) for p in CODE},
        "source_files": [{"path": str(p), "sha256": _sha256(p)} for p in dict.fromkeys(sources)],
    }
    FROZEN.write_text(json.dumps(frozen, indent=2) + "\n", encoding="utf-8")
    return frozen


def confirm(season: int, frozen_path: Path = FROZEN) -> dict:
    if not frozen_path.exists():
        raise SystemExit(f"no frozen candidate at {frozen_path}: run `tune` and commit it first")
    fz = json.loads(frozen_path.read_text(encoding="utf-8"))
    if fz["scale"] == 0:
        raise SystemExit("k = 0 won the tuning: there is no prior candidate to confirm")

    from cfb_paths import DATA_ROOT, PROCESSED

    sources: list[Path] = [frozen_path]
    games, drops = load(DATA_ROOT, list(range(2014, season + 1)), sources)
    opens = load_opens(DATA_ROOT, [season], sources)
    rp = load_rp(DATA_ROOT, season, sources)
    look = "interim" if drops[season].get("not_completed", 0) else "final"

    prev = final_ratings(games, season - 1, *fz["ridge_v1_lambda"])
    coefs = {k: {"value": v} for k, v in fz["coefficients"].items()}
    teams = season_teams(games, season)
    by_scale = {m: build_priors(prev, rp, teams, coefs, fz["scale"] * m) for m in (1.0, *COEF_STRESS)}
    lam = (fz["lambda_ppp"], fz["lambda_pace"])

    b_rows, _ = run_season(games, season, *fz["ridge_v1_lambda"], opens)
    p_rows, _ = score_prior_season(games, season, lam, by_scale, prev, opens)
    scored = p_rows.merge(b_rows[["game_id", "mean", "ridge", "min_prior_games"]]
                          .rename(columns={"ridge": "ridge_v1"}), on="game_id", how="left")
    scored["mean"] = scored["mean"].fillna(scored["mean_all_weeks"])
    scored["min_prior_games"] = scored["min_prior_games"].fillna(0).astype(int)

    has_open = scored["open"].notna()
    later = scored[has_open & (scored["week"] >= 2)]
    pops = {"early_2plus": later[later["min_prior_games"] < MIN_PRIOR_GAMES],
            "primary": later[later["min_prior_games"] >= MIN_PRIOR_GAMES]}
    comparisons = {}
    for name, pop in pops.items():
        if pop.empty:
            comparisons[name] = {"n": 0}
            continue
        d = (pop["prior"] - pop["total"]).abs() - (pop["ridge_v1"] - pop["total"]).abs()
        entry = {"n": int(len(pop)), "n_weeks": int(pop["week"].nunique()),
                 "prior_v3_minus_ridge_v1": round(float(d.mean()), 4),
                 "accuracy": accuracy(pop, ["open", "mean", "ridge_v1", "prior"])}
        if look == "final":  # the one confirmatory look
            p = paired_mae_diff(pop, "prior", "ridge_v1")
            entry |= {"ci95": p["ci95"], "mde80": p["mde80"],
                      "verdict": classify_verdict(*p["ci95"], [p["diff"]]),
                      "prior_v3_vs_open": paired_mae_diff(pop, "prior", "open"),
                      "ridge_v1_vs_open": paired_mae_diff(pop, "ridge_v1", "open")}
        comparisons[name] = entry
    confirmed = None
    if look == "final":
        confirmed = (comparisons["early_2plus"].get("verdict") == "improves"
                     and comparisons["primary"].get("verdict") != "worse")

    out = {
        "candidate": "prior_v3", "season": season, "look": look,
        "note": ("interim: descriptive only, no verdict, nothing changes because of it"
                 if look == "interim" else "final confirmatory look"),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "frozen": {k: fz[k] for k in ("scale", "lambda_ppp", "lambda_pace", "coefficients", "frozen_at")},
        "frozen_sha256": _sha256(frozen_path),
        "market": {"provider": OPEN_PROVIDER, "field": "overUnderOpen"},
        "completed_weeks": sorted(int(w) for w in scored["week"].unique()),
        "games_not_yet_completed": drops[season].get("not_completed", 0),
        "comparisons": comparisons,
        "week1": week1_report(scored[has_open & (scored["week"] == 1)]),
        "confirmed": confirmed,
        "bootstrap": {"unit": "season-week", "draws": BOOT_DRAWS, "seed": BOOT_SEED},
        "source_files": [{"path": str(p), "sha256": _sha256(p)} for p in dict.fromkeys(sources)],
    }
    stamp = out["generated_at"][:10]
    path = PROCESSED / "ratings" / f"prior_v3_confirm_{season}_{look}_{stamp}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
    out["path"] = str(path)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("tune")
    c = sub.add_parser("confirm")
    c.add_argument("--season", type=int, required=True)
    args = ap.parse_args(argv)
    if args.cmd == "tune":
        fz = run_tune()
        print(json.dumps({k: fz[k] for k in ("scale", "lambda_ppp", "lambda_pace", "mae",
                                            "scale_on_grid_boundary", "by_scale")}, indent=1))
        print(f"frozen: {FROZEN} -- commit it before running confirm")
    else:
        out = confirm(args.season)
        print(json.dumps({k: out[k] for k in ("look", "completed_weeks", "games_not_yet_completed",
                                             "comparisons", "confirmed")}, indent=1, default=str))
        print(f"written: {out['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
