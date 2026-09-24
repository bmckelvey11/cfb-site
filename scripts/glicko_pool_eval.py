"""Score a connected FBS/FCS Glicko pool (rung P1) against v1 on v1's own primary population.

    python -m scripts.glicko_pool_eval

v1 (`glicko_ratings_eval.py`) reads `games.csv`, which holds only games that carried a
betting line, so its state saw roughly one FCS game a team per season. The raw CFBD files
hold every completed Division I game. This rung refits Glicko-margin on that fuller pool in
two variants -- `pool_sub` (offseason target = subdivision mean, v1's rule) and `pool_conf`
(target = conference mean) -- picks the lower-CRPS variant on 2014-2019 tuning seasons only,
and compares it to v1 on v1's exact 3,718-game primary population plus its 580-game
FBS-vs-FCS population. v1 itself is reproduced from its own frozen manifest, not re-tuned.

Writes data/processed/ratings/glicko_pool_eval.json.
See docs/superpowers/specs/2026-09-24-glicko-pool-design.md.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import scripts.glicko_ratings_eval as v1
from scripts.glicko_ratings import FBS, FCS, VERSION, GlickoMargin, events, run
from scripts.pregame_replay_audit import _sha256

D1 = {FBS, FCS}
TUNE_SEASONS = list(range(2014, 2020))
CONF_COLS = ["home_conf", "away_conf"]


# --- loading ----------------------------------------------------------------------

def load_pool_games(root: Path, last: int, sources: list[Path]) -> tuple[pd.DataFrame, dict]:
    """Every completed D-I (FBS/FCS) game from the raw CFBD games files, 2013 through `last`.

    Dropped and counted, not silently skipped: games with a D-II/D-III/unlabelled side, and
    games with no final score (postponed, or 2026 games not yet played).
    """
    rows, non_d1, unplayed = [], {}, {}
    for s in range(v1.BURN_IN, last + 1):
        path = root / "raw" / f"games_{s}.json"
        sources.append(path)
        n_non_d1 = n_unplayed = 0
        for g in json.loads(path.read_text(encoding="utf-8")):
            hp, ap = g.get("homePoints"), g.get("awayPoints")
            if not g.get("completed") or hp is None or ap is None:
                n_unplayed += 1
                continue
            hc, ac = g.get("homeClassification"), g.get("awayClassification")
            if hc not in D1 or ac not in D1:
                n_non_d1 += 1
                continue
            rows.append({"game_id": g["id"], "season": s, "week": g["week"],
                        "season_type": g["seasonType"], "kickoff": g.get("startDate"),
                        "home": g["homeTeam"], "away": g["awayTeam"],
                        "home_div": hc, "away_div": ac,
                        "home_conf": g.get("homeConference"), "away_conf": g.get("awayConference"),
                        "neutral": bool(g.get("neutralSite")), "margin": hp - ap})
        non_d1[s], unplayed[s] = n_non_d1, n_unplayed
    g = pd.DataFrame(rows)
    g["kickoff"] = pd.to_datetime(g["kickoff"], utc=True, errors="coerce")
    g = g.sort_values(["kickoff", "game_id"]).reset_index(drop=True)
    return g, {"non_d1_by_season": non_d1, "unplayed_by_season": unplayed}


def _hist_for(g_pool: pd.DataFrame, use_conf: bool, through: int) -> pd.DataFrame:
    hist = g_pool[g_pool["season"] <= through]
    return hist if use_conf else hist.drop(columns=CONF_COLS)


def fcs_seed_pool(g_pool: pd.DataFrame) -> float:
    """m0 from every 2013 FBS-vs-FCS game in the raw files (v1.fcs_seed's ~fbs_fbs shortcut
    would wrongly sweep in FCS-vs-FCS games too, since the pool keeps those)."""
    b = g_pool[(g_pool["season"] == v1.BURN_IN) & (g_pool["home_div"] != g_pool["away_div"])]
    fbs_margin = np.where(b["home_div"] == FBS, b["margin"], -b["margin"])
    return round(-float(np.mean(fbs_margin)), 3)


def pool_forecast(hist: pd.DataFrame, ev: list, m0: float, pick: dict) -> pd.DataFrame:
    fc = run(GlickoMargin(**pick, m0=m0), hist, ev)
    return pd.DataFrame({"game_id": hist["game_id"].to_numpy(), "f": fc["mhat"].to_numpy(),
                         "f_sd": np.sqrt(fc["S"].to_numpy()), "f_rd": np.sqrt(fc["rd2"].to_numpy())})


# --- tuning -------------------------------------------------------------------------

def _tuning_loss(hist: pd.DataFrame, ev: list, m0: float, pick: dict, mask, y) -> float:
    fc = run(GlickoMargin(**pick, m0=m0), hist, ev)
    return float(v1.crps(fc["mhat"].to_numpy()[mask], np.sqrt(fc["S"].to_numpy()[mask]), y).mean())


def tune_variant(g_pool: pd.DataFrame, seasons: list[int], m0: float, grid: dict,
                 use_conf: bool) -> list[tuple]:
    hist = _hist_for(g_pool, use_conf, max(seasons)).reset_index(drop=True)
    ev = events(hist)
    mask = (hist["season"].isin(seasons) & (hist["season_type"] == "regular")
            & (hist["home_div"] == FBS) & (hist["away_div"] == FBS)).to_numpy()
    y = hist["margin"].to_numpy(float)[mask]
    return [(_tuning_loss(hist, ev, m0, p, mask, y), p) for p in v1._points(grid)]


def tune_pool(g_pool: pd.DataFrame, seasons: list[int], m0: float) -> dict:
    """Tune both variants on the declared (v1's final) grid, then one boundary-extension pass."""
    grid = {k: tuple(v) for k, v in v1.GRIDS["glicko_margin"].items()}
    variants = {name: v1._pick(tune_variant(g_pool, seasons, m0, grid, use_conf), grid,
                               "mean CRPS")
                for name, use_conf in (("pool_sub", False), ("pool_conf", True))}
    edges: dict[str, set[str]] = {}
    for name in ("pool_sub", "pool_conf"):
        for axis, edge in variants[name]["boundary"].items():
            edges.setdefault(axis, set()).add(edge)
    extended: dict[str, list[str]] = {}
    for axis, dirs in edges.items():
        vals = list(grid[axis])
        lo, hi = v1.LIMITS.get(axis, (-v1.INF, v1.INF))
        step = vals[1] - vals[0] if len(vals) > 1 else 1
        if "low" in dirs and vals[0] - step > lo:
            vals = [vals[0] - step, *vals]
            extended.setdefault(axis, []).append("low")
        if "high" in dirs and vals[-1] + step < hi:
            vals = [*vals, vals[-1] + step]
            extended.setdefault(axis, []).append("high")
        grid[axis] = tuple(vals)
    if extended:
        variants = {name: v1._pick(tune_variant(g_pool, seasons, m0, grid, use_conf), grid,
                                   "mean CRPS")
                    for name, use_conf in (("pool_sub", False), ("pool_conf", True))}
    adopted = min(variants, key=lambda k: variants[k]["best_loss"])
    return {"grid": {a: list(v) for a, v in grid.items()}, "extended": extended,
            "variants": variants, "adopted_name": adopted, "adopted_pick": variants[adopted]["pick"]}


# --- v1 reference, reproduced from its frozen manifest, not re-tuned ----------------

def load_v1_reference(root: Path, sources: list[Path]) -> tuple[pd.DataFrame, dict, list[int]]:
    manifest_path = root / "processed" / "ratings" / "glicko_eval.json"
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    score_seasons = m["seasons"]["score"]
    g_v1, _ = v1.load(root, max(score_seasons), sources)
    m0_v1 = v1.fcs_seed(g_v1)
    assert abs(m0_v1 - m["seeds"]["m0_fcs"]) < 1e-6, "v1's FCS seed drifted from its frozen run"
    tuned_v1 = m["tuning"]  # the manifest's tuning dict is exactly v1.tune()'s return value
    fc_v1 = v1.forecasts(g_v1, tuned_v1, m0_v1)
    market = v1.load_market(root, score_seasons, sources)
    d_v1, market_sd = v1.scored_frame(g_v1, fc_v1, market, score_seasons)
    return d_v1, {"tuned": tuned_v1, "m0": m0_v1, "market_sd": market_sd}, score_seasons


# --- adopt verdict and stress ---------------------------------------------------------

def adopt_verdict(d_primary: pd.DataFrame, d_fcs: pd.DataFrame) -> tuple[bool, dict, dict]:
    """(adopt?, paired CRPS on v1's primary games, paired CRPS on v1's FBS-vs-FCS games)."""
    crps_primary = v1.paired(d_primary, "pool", "glk", "crps")
    crps_fcs = v1.paired(d_fcs, "pool", "glk", "crps")
    not_worse = crps_primary["verdict"] != "worse"
    improves_fcs = crps_fcs["verdict"] == "improves"
    return not_worse and improves_fcs, crps_primary, crps_fcs


def pool_stress(g_pool, use_conf, pick, grid, m0, primary_ids: pd.DataFrame,
                fcs_ids: pd.DataFrame, base_adopt: bool) -> dict:
    """Move each adopted-P1 parameter to its neighbouring grid values; the ADOPT verdict
    (not G1/G2) must hold in every variant, per the spec's declared "Stress" rule."""
    hist = _hist_for(g_pool, use_conf, primary_ids["season"].max()).reset_index(drop=True)
    ev = events(hist)

    def adopt_for(p) -> bool:
        fc = pool_forecast(hist, ev, m0, p)
        dp = primary_ids.merge(fc, on="game_id", how="left").rename(
            columns={"f": "pool", "f_sd": "pool_sd"})
        df = fcs_ids.merge(fc, on="game_id", how="left").rename(
            columns={"f": "pool", "f_sd": "pool_sd"})
        ok, *_ = adopt_verdict(dp, df)
        return ok

    runs = {}
    for axis, vals in grid.items():
        i = vals.index(pick[axis])
        for j in (i - 1, i + 1):
            if 0 <= j < len(vals):
                runs[f"{axis}={vals[j]}"] = adopt_for({**pick, axis: vals[j]})
    stable = all(v == base_adopt for v in runs.values())
    return {"base_adopt": base_adopt, "variants": runs, "n_variants": len(runs), "stable": stable}


# --- CLI ------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    args = ap.parse_args(argv)

    from cfb_paths import DATA_ROOT, PROCESSED

    sources: list[Path] = []
    d_v1, v1_ref, score_seasons = load_v1_reference(DATA_ROOT, sources)
    tune_seasons = [s for s in TUNE_SEASONS if s not in v1.SKIP_SEASONS]

    g_pool, drops = load_pool_games(DATA_ROOT, max(score_seasons), sources)
    m0 = fcs_seed_pool(g_pool)
    tuned = tune_pool(g_pool, tune_seasons, m0)
    adopted_name, pick = tuned["adopted_name"], tuned["adopted_pick"]

    hist_full = _hist_for(g_pool, adopted_name == "pool_conf", max(score_seasons)).reset_index(
        drop=True)
    fc = pool_forecast(hist_full, events(hist_full), m0, pick)
    assert fc["f"].notna().all(), "NaN pool forecast"

    d_v1 = d_v1.merge(fc, on="game_id", how="left")
    missing = int(d_v1["f"].isna().sum())
    assert missing == 0, f"{missing} of v1's games have no P1 forecast (pool coverage gap)"
    d_v1 = d_v1.rename(columns={"f": "pool", "f_sd": "pool_sd", "f_rd": "pool_rd"})

    primary = d_v1[d_v1["primary"]].reset_index(drop=True)
    fcs_pop = d_v1[~d_v1["fbs_fbs"]].reset_index(drop=True)
    go, crps_primary, crps_fcs = adopt_verdict(primary, fcs_pop)
    mae_primary = v1.paired(primary, "pool", "glk", "mae")
    mae_fcs = v1.paired(fcs_pop, "pool", "glk", "mae")

    d_gate = primary.copy()
    d_gate["glk"], d_gate["glk_sd"], d_gate["rd"] = d_gate["pool"], d_gate["pool_sd"], d_gate["pool_rd"]
    gates_p1 = v1.gates(d_gate)

    stressed = pool_stress(g_pool, adopted_name == "pool_conf", pick, tuned["grid"], m0,
                           primary[["game_id", "season", "week", "margin", "glk", "glk_sd"]],
                           fcs_pop[["game_id", "season", "week", "margin", "glk", "glk_sd"]], go)

    out_dir = PROCESSED / "ratings"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": VERSION, "rung": "P1_pool",
        "command": "python -m scripts.glicko_pool_eval",
        "code_sha256": {p: _sha256(Path(__file__).parent / p)
                        for p in ("glicko_ratings.py", "glicko_pool_eval.py",
                                  "glicko_ratings_eval.py")},
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_root": str(DATA_ROOT),
        "seasons": {"burn_in": v1.BURN_IN, "tune": tune_seasons, "score": score_seasons},
        "drops": drops,
        "seeds": {"m0_fcs_pool": m0, "m0_fcs_v1": v1_ref["m0"]},
        "tuning": {"grid": tuned["grid"], "extended": tuned["extended"],
                  "variants": {k: {"pick": v["pick"], "best_loss": v["best_loss"],
                                   "boundary": v["boundary"], "grid_points": v["grid_points"]}
                               for k, v in tuned["variants"].items()},
                  "adopted": adopted_name},
        "trial_count": {
            "pool_sub_tuning": tuned["variants"]["pool_sub"]["grid_points"],
            "pool_conf_tuning": tuned["variants"]["pool_conf"]["grid_points"],
            "boundary_extension": bool(tuned["extended"]),
            "stress_variants": stressed["n_variants"], "scoring_runs": 1,
            "v1_prior_total": 4162,
        },
        "populations": {"primary": int(len(primary)), "fbs_vs_fcs": int(len(fcs_pop))},
        "declared_rules": {
            "adopt": "primary CRPS not worse AND fbs_vs_fcs CRPS improves",
            "go": go,
            "primary_crps": crps_primary, "primary_mae": mae_primary,
            "fbs_vs_fcs_crps": crps_fcs, "fbs_vs_fcs_mae": mae_fcs,
        },
        "gates_re_read_for_adopted_p1": gates_p1,
        "stress": stressed,
        "bootstrap": {"unit": "season-week", "draws": v1.BOOT_DRAWS, "seed": v1.BOOT_SEED},
    }
    out = out_dir / "glicko_pool_eval.json"
    out.write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")

    print(f"adopted: {adopted_name} {json.dumps(pick, default=str)}")
    print(f"primary CRPS diff (pool - v1): {crps_primary['diff']} {crps_primary['ci95']} "
          f"-> {crps_primary['verdict']}")
    print(f"fbs-vs-fcs CRPS diff (pool - v1): {crps_fcs['diff']} {crps_fcs['ci95']} "
          f"-> {crps_fcs['verdict']}")
    print(f"ADOPT: {go}  stress stable: {stressed['stable']}")
    print(f"gates re-read for P1: G1={gates_p1['G1']['pass']} G2={gates_p1['G2']['pass']} "
          f"G3={gates_p1['G3']['pass']}")
    print(f"manifest: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
