"""Tune and score the Release B weekly ratings against a train mean and the vendor open.

    python -m scripts.weekly_ratings_eval --tune-seasons 2014-2019 --score-seasons 2021-2025

Tuning: one-step-ahead component loss on the tune seasons only -- possession-weighted
squared error of points per possession for lambda_ppp, squared error of possessions for
lambda_pace. The two fits share no parameters, so the grids tune independently.

Scoring, on the score seasons with lambda frozen: four forecasts of the full-game total
on the same games -- the Bovada `overUnderOpen` label (fixed book, no fallback), the mean
total of every loaded FBS-vs-FBS game before the cutoff, `raw_v1`, `ridge_v1`. Paired
MAE differences with a week-cluster bootstrap (every game in a week shares one snapshot),
an MDE beside each interval, and an encompassing slope against the open. Forecast skill
only: no wager is graded.

Writes data/processed/ratings/{weekly_ratings_snapshots.csv, weekly_ratings_eval.json}.
See docs/superpowers/specs/2026-09-22-weekly-ratings-design.md.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.pregame_replay_audit import _sha256, snapshot
from scripts.weekly_ratings import (
    _team_rows, build_games, fit_pace, fit_ppp, fit_raw, fit_ridge, fit_set, forecast_total,
)

LAMBDA_PPP_GRID = (5, 10, 20, 40, 80, 160)      # possessions
LAMBDA_PACE_GRID = (0.5, 1, 2, 4, 8, 16)        # games
STRESS = (0.5, 2.0)
MIN_PRIOR_GAMES = 3
OPEN_PROVIDER = "Bovada"
BOOT_DRAWS = 10_000
BOOT_SEED = 20260922
Z_MDE = 1.96 + 0.84                             # 80% power, two-sided 5%


def classify_verdict(lo: float, hi: float, by_season: list[float]) -> str:
    """'worse' / 'improves' / 'matches' for a paired MAE difference (forecast - comparator).

    lo, hi: pooled 95% interval. by_season: per-season point estimates.
    """
    if lo > 0:
        return "worse"
    # A season tied at exactly 0 counts as disagreeing: a tie is not an improvement.
    disagreeing = sum(1 for d in by_season if d >= 0)
    if hi < 0 and disagreeing <= 1:
        return "improves"
    return "matches"


# --- loading --------------------------------------------------------------------

def load(root: Path, seasons: list[int], sources: list[Path]) -> tuple[pd.DataFrame, dict]:
    frames, drops = [], {}
    for s in seasons:
        gp, dp = root / "raw" / f"games_{s}.json", root / "raw" / f"drives_{s}.json"
        sources += [gp, dp]
        g, d = build_games(json.loads(gp.read_text(encoding="utf-8")),
                           json.loads(dp.read_text(encoding="utf-8")))
        drops[s] = {**d, "gated_from_fits": int(g["gated"].sum()), "games": len(g)}
        frames.append(g)
    return pd.concat(frames, ignore_index=True), drops


def load_opens(root: Path, seasons: list[int], sources: list[Path]) -> dict[int, float]:
    """`overUnderOpen` from OPEN_PROVIDER only; first row per game, as in core."""
    out: dict[int, float] = {}
    for s in seasons:
        path = root / "raw" / f"lines_{s}.json"
        sources.append(path)
        for g in json.loads(path.read_text(encoding="utf-8")):
            for ln in g.get("lines") or []:
                if ln.get("provider") == OPEN_PROVIDER and g["id"] not in out:
                    out[g["id"]] = ln.get("overUnderOpen")
    return {k: v for k, v in out.items() if v is not None}


def week_cutoffs(season_games: pd.DataFrame) -> pd.Series:
    """Week w's cutoff is its earliest kickoff. Week 1 has no evidence, so it is skipped."""
    cuts = season_games.groupby("week")["kickoff"].min()
    return cuts[cuts.index >= 2]


# --- tuning ---------------------------------------------------------------------

def tune(games: pd.DataFrame, seasons: list[int]) -> dict:
    loss_ppp = dict.fromkeys(LAMBDA_PPP_GRID, 0.0)
    loss_pace = dict.fromkeys(LAMBDA_PACE_GRID, 0.0)
    n_cutoffs = 0
    for s in seasons:
        sg = games[games["season"] == s]
        for week, cut in week_cutoffs(sg).items():
            fs = fit_set(sg, cut)
            target = sg[(sg["week"] == week) & ~sg["gated"]]
            if fs.empty or target.empty:
                continue
            n_cutoffs += 1
            rows = _team_rows(target)
            for lam in LAMBDA_PPP_GRID:
                mu, h, od = fit_ppp(fs, lam)
                pred = (mu + rows["team"].map(od["O"]).fillna(0)
                        + rows["opp"].map(od["D"]).fillna(0) + h * rows["H"])
                loss_ppp[lam] += float((rows["w"] * (rows["y"] - pred) ** 2).sum())
            for lam in LAMBDA_PACE_GRID:
                nu, p = fit_pace(fs, lam)
                pred = nu + target["home"].map(p).fillna(0) + target["away"].map(p).fillna(0)
                loss_pace[lam] += float(((target["N"] - pred) ** 2).sum())

    def pick(losses: dict, grid: tuple) -> dict:
        best = min(losses, key=losses.get)
        return {"lambda": best, "loss_by_lambda": {str(k): round(v, 3) for k, v in losses.items()},
                "pick_on_grid_boundary": best in (grid[0], grid[-1])}

    return {"seasons": seasons, "n_cutoffs": n_cutoffs,
            "ppp": pick(loss_ppp, LAMBDA_PPP_GRID), "pace": pick(loss_pace, LAMBDA_PACE_GRID)}


# --- snapshots and forecasts ------------------------------------------------------

def _snapshot_rows(season, week, cut, method, r, lam_ppp, lam_pace) -> pd.DataFrame:
    t = r.table.reset_index(names="team")
    return t.assign(season=season, as_of_week=week, as_of_ts=cut.isoformat(), method=method,
                    mu=r.mu, nu=r.nu, h=r.h, c=r.c,
                    lambda_ppp=lam_ppp if method == "ridge_v1" else None,
                    lambda_pace=lam_pace if method == "ridge_v1" else None,
                    garbage_filter="none", fcs_policy="fbs_vs_fbs_only")


def run_season(games: pd.DataFrame, season: int, lam_ppp: float, lam_pace: float,
               opens: dict[int, float] | None) -> tuple[pd.DataFrame, list[pd.DataFrame]]:
    """Forecast every week-2+ game of `season` from its week's frozen snapshot."""
    sg = games[games["season"] == season]
    scored, snaps = [], []
    for week, cut in week_cutoffs(sg).items():
        fs = fit_set(sg, cut)
        if fs.empty:
            continue
        ridge = fit_ridge(fs, lam_ppp, lam_pace)
        raw = fit_raw(fs)
        snaps += [_snapshot_rows(season, week, cut, "ridge_v1", ridge, lam_ppp, lam_pace),
                  _snapshot_rows(season, week, cut, "raw_v1", raw, lam_ppp, lam_pace)]
        if opens is None:
            continue
        stress = {k: fit_ridge(fs, lam_ppp * k, lam_pace * k) for k in STRESS}
        train_mean = snapshot(games, cut)["total"].mean()  # every loaded season, before cut
        n_games = raw.table["n_games"]
        for g in sg[sg["week"] == week].itertuples():
            row = {"season": season, "week": int(week), "game_id": g.game_id,
                   "total": g.total, "open": opens.get(g.game_id), "mean": train_mean,
                   "raw": forecast_total(raw, g.home, g.away, g.neutral),
                   "ridge": forecast_total(ridge, g.home, g.away, g.neutral),
                   "min_prior_games": int(min(n_games.get(g.home, 0), n_games.get(g.away, 0)))}
            for k, r in stress.items():
                row[f"ridge_x{k:g}"] = forecast_total(r, g.home, g.away, g.neutral)
            scored.append(row)
    return pd.DataFrame(scored), snaps


# --- metrics --------------------------------------------------------------------

def _cluster_boot(df: pd.DataFrame, stats: dict[str, pd.Series]) -> tuple[dict, np.ndarray]:
    """Per-cluster sums of each stat, and BOOT_DRAWS resamples of whole season-weeks."""
    sums = pd.DataFrame(stats).groupby([df["season"], df["week"]]).sum()
    rng = np.random.default_rng(BOOT_SEED)
    idx = rng.integers(0, len(sums), size=(BOOT_DRAWS, len(sums)))
    return {c: sums[c].to_numpy()[idx].sum(axis=1) for c in sums}, sums


def paired_mae_diff(df: pd.DataFrame, a: str, b: str) -> dict:
    """MAE(a) - MAE(b) on the same games; negative means `a` is closer to the total."""
    d = (df[a] - df["total"]).abs() - (df[b] - df["total"]).abs()
    boot, sums = _cluster_boot(df, {"d": d, "n": pd.Series(1.0, index=df.index)})
    draws = boot["d"] / boot["n"]
    lo, hi = np.percentile(draws, [2.5, 97.5])
    se = float(draws.std(ddof=1))
    return {"n": int(len(df)), "n_clusters": int(len(sums)), "diff": round(float(d.mean()), 4),
            "ci95": [round(float(lo), 4), round(float(hi), 4)], "se": round(se, 4),
            "mde80": round(Z_MDE * se, 4),
            "by_season": {int(s): round(float(v), 4) for s, v in d.groupby(df["season"]).mean().items()}}


def encompassing_slope(df: pd.DataFrame, f: str) -> dict:
    """OLS slope b in (total - open) = a + b (forecast - open) + e, week-cluster bootstrap."""
    x, y = df[f] - df["open"], df["total"] - df["open"]
    stats = {"n": pd.Series(1.0, index=df.index), "x": x, "y": y, "xx": x * x, "xy": x * y}
    boot, _ = _cluster_boot(df, stats)

    def slope(n, sx, sy, sxx, sxy):
        return (n * sxy - sx * sy) / (n * sxx - sx * sx)

    b = slope(len(df), x.sum(), y.sum(), (x * x).sum(), (x * y).sum())
    draws = slope(boot["n"], boot["x"], boot["y"], boot["xx"], boot["xy"])
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return {"slope": round(float(b), 4), "ci95": [round(float(lo), 4), round(float(hi), 4)]}


def accuracy(df: pd.DataFrame, cols: list[str]) -> dict:
    out = {}
    for c in cols:
        e = df[c] - df["total"]
        out[c] = {"n": int(len(df)), "mae": round(float(e.abs().mean()), 3),
                  "rmse": round(float(np.sqrt((e ** 2).mean())), 3),
                  "bias": round(float(e.mean()), 3)}
    return out


def score(scored: pd.DataFrame) -> dict:
    has_open = scored["open"].notna()
    primary = scored[has_open & (scored["min_prior_games"] >= MIN_PRIOR_GAMES)]
    early = scored[has_open & (scored["min_prior_games"] < MIN_PRIOR_GAMES)]

    def by_season(pop, cols):
        return {int(s): accuracy(g, cols) for s, g in pop.groupby("season")}

    def verdicts(pop, ridge_col):
        out = {}
        for comp in ("raw", "mean"):
            p = paired_mae_diff(pop, ridge_col, comp)
            out[f"ridge_vs_{comp}"] = {**p, "verdict": classify_verdict(
                *p["ci95"], list(p["by_season"].values()))}
        return out

    main = verdicts(primary, "ridge")
    stress = {f"lambda_x{k:g}": verdicts(primary, f"ridge_x{k:g}") for k in STRESS}
    for key, v in main.items():
        v["stable_under_stress"] = all(s[key]["verdict"] == v["verdict"] for s in stress.values())

    four = ["open", "mean", "raw", "ridge"]
    return {
        "populations": {
            "scored_games": int(len(scored)), "with_open": int(has_open.sum()),
            "primary": int(len(primary)), "early": int(len(early)),
            "primary_rule": f"both teams >= {MIN_PRIOR_GAMES} prior FBS-vs-FBS games this "
                            f"season (ungated), {OPEN_PROVIDER} open present",
            "early_rule": f"week >= 2, some team < {MIN_PRIOR_GAMES} prior games, open present",
        },
        "primary": {
            "accuracy_pooled": accuracy(primary, four),
            "accuracy_by_season": by_season(primary, four),
            "verdicts": main,
            "stress": stress,
            "paired_vs_open": {c: paired_mae_diff(primary, c, "open") for c in ("ridge", "raw", "mean")},
            "raw_vs_mean": paired_mae_diff(primary, "raw", "mean"),
            "encompassing_vs_open": {c: encompassing_slope(primary, c) for c in ("ridge", "raw", "mean")},
        },
        "early": {
            "accuracy_pooled": accuracy(early, ["open", "mean", "ridge"]),
            "ridge_vs_mean": paired_mae_diff(early, "ridge", "mean"),
            "ridge_vs_open": paired_mae_diff(early, "ridge", "open"),
        },
    }


# --- CLI ------------------------------------------------------------------------

def _range(text: str) -> list[int]:
    a, _, b = text.partition("-")
    return list(range(int(a), int(b or a) + 1))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tune-seasons", type=_range, default=_range("2014-2019"))
    ap.add_argument("--score-seasons", type=_range, default=_range("2021-2025"))
    ap.add_argument("--skip-season", type=int, action="append", default=[2020],
                    help="excluded from tuning and scoring (default: 2020)")
    args = ap.parse_args(argv)

    from cfb_paths import DATA_ROOT, PROCESSED

    tune_seasons = [s for s in args.tune_seasons if s not in args.skip_season]
    score_seasons = [s for s in args.score_seasons if s not in args.skip_season]
    loaded = list(range(min(tune_seasons + score_seasons), max(score_seasons) + 1))
    sources: list[Path] = []
    games, drops = load(DATA_ROOT, loaded, sources)
    opens = load_opens(DATA_ROOT, score_seasons, sources)

    tuned = tune(games, tune_seasons)
    lam_ppp, lam_pace = tuned["ppp"]["lambda"], tuned["pace"]["lambda"]

    scored, snaps = [], []
    for s in tune_seasons + score_seasons:
        sc, sn = run_season(games, s, lam_ppp, lam_pace, opens if s in score_seasons else None)
        scored.append(sc)
        snaps += sn
    scored = pd.concat(scored, ignore_index=True)
    results = score(scored)

    out_dir = PROCESSED / "ratings"
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.concat(snaps, ignore_index=True).to_csv(out_dir / "weekly_ratings_snapshots.csv", index=False)
    manifest = {
        "command": "python -m scripts.weekly_ratings_eval --tune-seasons "
                   f"{tune_seasons[0]}-{tune_seasons[-1]} --score-seasons "
                   f"{score_seasons[0]}-{score_seasons[-1]}",
        "code_sha256": {p: _sha256(Path(__file__).parent / p)
                        for p in ("weekly_ratings.py", "weekly_ratings_eval.py",
                                  "pregame_replay_audit.py")},
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_root": str(DATA_ROOT),
        "seasons": {"tune": tune_seasons, "score": score_seasons, "loaded": loaded,
                    "skipped": args.skip_season},
        "market": {"provider": OPEN_PROVIDER, "field": "overUnderOpen",
                   "clock": "vendor_open_label_only (docs/pregame-replay-2026-09-22.md)"},
        "definitions": {
            "points": "Q1-Q4 line scores; drive score fields never read",
            "possession": "drive with startPeriod 1-4",
            "gate": "fits skip games with no drives or |home - away regulation drives| > 2",
            "cutoff": "earliest kickoff of the week; evidence strictly before it",
            "garbage_filter": "none",
            "fcs_policy": "fbs_vs_fbs_only",
        },
        "drops_by_season": drops,
        "tuning": tuned,
        "trial_count": {"tuning_grid_points": len(LAMBDA_PPP_GRID) + len(LAMBDA_PACE_GRID),
                        "methods_scored": 2, "providers": 1, "stress_variants": len(STRESS)},
        "bootstrap": {"unit": "season-week", "draws": BOOT_DRAWS, "seed": BOOT_SEED,
                      "interval": "percentile 95%", "mde": "2.8 x bootstrap SE (80% power)"},
        "results": results,
        "source_files": [{"path": str(p), "sha256": _sha256(p)} for p in dict.fromkeys(sources)],
    }
    out = out_dir / "weekly_ratings_eval.json"
    out.write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")

    v = results["primary"]["verdicts"]
    print(f"lambda_ppp={lam_ppp} lambda_pace={lam_pace} "
          f"(tuned on {tune_seasons[0]}-{tune_seasons[-1]}, {tuned['n_cutoffs']} cutoffs)")
    print(json.dumps(results["primary"]["accuracy_pooled"], indent=1))
    for key, r in v.items():
        print(f"{key}: diff {r['diff']} ci95 {r['ci95']} mde80 {r['mde80']} -> {r['verdict']}"
              f" (stable under stress: {r['stable_under_stress']})")
    print(f"manifest: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
