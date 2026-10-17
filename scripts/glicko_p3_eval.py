"""Tune, freeze and (later) score the Glicko P3 bundles A, B, C.

    python -m scripts.glicko_p3_eval --freeze           # tune on 2014-2019, freeze, describe 2021-25
    python -m scripts.glicko_p3_eval --look interim     # after the 2026 postseason, once
    python -m scripts.glicko_p3_eval --look final       # after the 2027 postseason, once

Declared in rankings/docs/specs/2026-10-16-glicko-p3-bundles-design.md. Each bundle is
tuned on its own against P1 by mean CRPS on FBS-vs-FBS regular-season games 2014-2019 (2013
burn-in), jointly with sigma_pred on 11.0-16.0 step 0.5. --freeze replays only seasons through
2025 and never reads a 2026 or 2027 game. 2021-2025 is reported descriptively (it has been
scored three times on this family and decides nothing). The look modes refuse to run before
their seasons are complete, verify the frozen forecast fingerprint, and score only the
holdout: completed FBS-vs-FBS games after 2026-10-16T23:59Z (interim: through the 2026
postseason; final: plus all of 2027), each bundle minus P1 with sigma_pred 13.5.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from scripts.glicko_p3 import (GlickoContext, GlickoFull, GlickoStart, game_context,
                               new_conferences, run_ctx, transfer_aware_rp)
from scripts.glicko_pool_eval import fcs_seed_pool, load_pool_games
from scripts.glicko_ratings import FBS, FROZEN_P1, SIGMA_PRED_P1, GlickoMargin, events, run
from scripts.glicko_ratings_eval import crps

FROZEN = Path(__file__).with_name("glicko_p3_frozen.json")
TUNE = list(range(2014, 2020))
DESCRIBE = [2021, 2022, 2023, 2024, 2025]
SIGMA_PRED = tuple(np.arange(11.0, 16.01, 0.5).round(1))
GRIDS = {
    "A": {"sigma": (13, 15, 17)},
    "B": {"c": (0.0, 0.05, 0.1), "h": (0.0, 0.15, 0.3), "w": (0.6, 0.7, 0.8)},
    "C": {"h2013": (2.0, 2.75, 3.5), "slope": (0.0, -0.05, -0.1), "h2020": (0.0, 1.0, 2.0),
          "k": (1.0, 1.5, 2.0), "tz": (0.0, 0.25, 0.5)},
}
# H2020 only acts on 2020 games, which no tuning season contains: every value ties on
# 2014-2019 CRPS. Declared tie rule (recorded in the spec's build record): the grid midpoint.
H2020_UNIDENTIFIED = 1.0
HOLDOUT_START = pd.Timestamp("2026-10-16T23:59:00Z")
LOOKS = {"interim": {"last": 2026, "not_before": date(2027, 1, 20)},
         "final": {"last": 2027, "not_before": date(2028, 1, 20)}}
BOOT_DRAWS, BOOT_SEED = 10_000, 20261016


# --- data -----------------------------------------------------------------------------

def load(root: Path, last: int) -> dict:
    g, drops = load_pool_games(root, last, [])
    g = g[g["season"] <= last].reset_index(drop=True)
    fbs = {int(s): set(x["home"][x["home_div"] == FBS]) | set(x["away"][x["away_div"] == FBS])
           for s, x in g.groupby("season")}
    rp, rp_cov = transfer_aware_rp(root / "raw", fbs)
    ctx, ctx_missing = game_context(root / "raw", g)
    return {"g": g, "ev": events(g), "m0": fcs_seed_pool(g), "drops": drops,
            "feats": {"new_conf": new_conferences(g), "rp": rp}, "rp_coverage": rp_cov,
            "ctx": ctx, "ctx_missing": ctx_missing}


def forecast(bundle: str, d: dict, prm: dict | None = None) -> pd.DataFrame:
    """mhat, rd2 and the forecast-variance multiplier for every game row."""
    prm, g = dict(prm or {}), d["g"]
    if bundle == "P1":
        fc, mult = run(GlickoMargin(**FROZEN_P1, m0=d["m0"]), g, d["ev"]), 1.0
    elif bundle == "A":
        fc, mult = run(GlickoFull(**{**FROZEN_P1, **prm}, m0=d["m0"]), g, d["ev"]), 1.0
    elif bundle == "B":
        pick = {**FROZEN_P1, "w": prm.pop("w", FROZEN_P1["w"])}
        model = GlickoStart(**pick, m0=d["m0"], new_conf=True, feats=d["feats"], **prm)
        fc, mult = run(model, g, d["ev"]), 1.0
    elif bundle == "C":
        model = GlickoContext(**FROZEN_P1, m0=d["m0"], ctx=d["ctx"], ot_tie=True, near=True, **prm)
        fc = run_ctx(model, g, d["ev"])
        mult = np.where(d["ctx"]["k_game"].to_numpy(), prm.get("k", 1.0), 1.0)
    else:
        raise ValueError(bundle)
    return pd.DataFrame({"mhat": fc["mhat"].to_numpy(), "rd2": fc["rd2"].to_numpy(),
                         "mult": np.broadcast_to(mult, len(g)).astype(float)}, index=g.index)


def sd(f: pd.DataFrame, sigma_pred: float) -> np.ndarray:
    return np.sqrt(f["rd2"].to_numpy() + f["mult"].to_numpy() * sigma_pred ** 2)


def mask(g: pd.DataFrame, seasons, *, regular=True, pop: str = "fbs_fbs") -> np.ndarray:
    """pop: fbs_fbs, or fbs_fcs (one FBS team and one FCS team)."""
    h, a = g["home_div"] == FBS, g["away_div"] == FBS
    m = {"fbs_fbs": h & a, "fbs_fcs": h ^ a}[pop] & g["season"].isin(seasons)
    return (m & (g["season_type"] == "regular") if regular else m).to_numpy()


# --- tuning and scoring -----------------------------------------------------------------

def best_sigma_pred(f, m, y) -> tuple[float, float]:
    losses = {sp: float(crps(f["mhat"].to_numpy()[m], sd(f, sp)[m], y[m]).mean()) for sp in SIGMA_PRED}
    sp = min(losses, key=losses.get)
    return losses[sp], sp


def tune(bundle: str, d: dict) -> dict:
    g = d["g"]
    dt = {**d, "g": g[g["season"] <= max(TUNE)].reset_index(drop=True)}
    dt["ev"], dt["ctx"] = events(dt["g"]), d["ctx"].iloc[:len(dt["g"])].reset_index(drop=True)
    assert (d["g"]["season"].iloc[:len(dt["g"])] <= max(TUNE)).all()
    m, y = mask(dt["g"], TUNE), dt["g"]["margin"].to_numpy(float)
    grid = GRIDS[bundle]
    trials = []
    for vals in itertools.product(*grid.values()):
        prm = dict(zip(grid, vals))
        loss, sp = best_sigma_pred(forecast(bundle, dt, prm), m, y)
        trials.append((loss, prm, sp))
    trials.sort(key=lambda r: r[0])
    loss, pick, sp = trials[0]
    if bundle == "C":
        pick = {**pick, "h2020": H2020_UNIDENTIFIED}
    boundary = {a: ("low" if pick[a] == v[0] else "high") for a, v in grid.items()
                if len(v) > 1 and pick[a] in (v[0], v[-1]) and not (bundle == "C" and a == "h2020")}
    p1_loss, p1_sp = best_sigma_pred(forecast("P1", dt), m, y)
    return {"pick": pick, "sigma_pred": sp, "tune_crps": round(loss, 4), "p1_tune_crps": round(p1_loss, 4),
            "p1_tune_sigma_pred": p1_sp, "boundary": boundary, "grid_points": len(trials),
            "top5": [(round(l, 4), p, s) for l, p, s in trials[:5]]}


def fingerprint(d: dict, bundle: str, pick: dict, sigma_pred: float) -> tuple[str, int]:
    """sha256 over (game_id, mean, sd) of the FBS-vs-FBS regular-season forecasts 2014-2025."""
    f = forecast(bundle, d, pick)
    m = mask(d["g"], range(2014, 2026))
    rows = zip(d["g"]["game_id"].to_numpy()[m], f["mhat"].to_numpy()[m], sd(f, sigma_pred)[m])
    h = hashlib.sha256("\n".join(f"{int(i)},{a:.6f},{b:.6f}" for i, a, b in rows).encode())
    return h.hexdigest(), int(m.sum())


def _logit_slope(x, o) -> float:
    b, X = np.zeros(2), np.column_stack([np.ones_like(x), x])
    for _ in range(25):
        p = 1 / (1 + np.exp(-X @ b))
        b += np.linalg.solve(X.T @ (X * (p * (1 - p))[:, None]), X.T @ (o - p))
    return float(b[1])


def metrics(mu, s, y) -> dict:
    z, keep = np.abs((y - mu) / s), y != 0
    p = np.clip(norm.cdf(mu / s)[keep], 1e-9, 1 - 1e-9)
    o = (y[keep] > 0).astype(float)
    return {"n": int(len(y)), "crps": round(float(crps(mu, s, y).mean()), 4),
            "mae": round(float(np.abs(y - mu).mean()), 4),
            "logloss": round(float(-(o * np.log(p) + (1 - o) * np.log(1 - p)).mean()), 4),
            "cov68": round(float((z <= 0.9945).mean()), 4), "cov95": round(float((z <= 1.96).mean()), 4),
            "calib_slope": round(_logit_slope(np.log(p / (1 - p)), o), 3)}


def paired(t: pd.DataFrame, a: str, b: str, kind: str, seed: int = BOOT_SEED) -> dict:
    y = t["margin"].to_numpy(float)
    if kind == "crps":
        diff = crps(t[a].to_numpy(), t[a + "_sd"].to_numpy(), y) - crps(t[b].to_numpy(), t[b + "_sd"].to_numpy(), y)
    else:
        diff = np.abs(y - t[a].to_numpy()) - np.abs(y - t[b].to_numpy())
    diff = pd.Series(np.asarray(diff), index=t.index)
    sums = diff.groupby(t["season"].astype(str) + "-" + t["week"].astype(str)).agg(["sum", "count"])
    idx = np.random.default_rng(seed).integers(0, len(sums), size=(BOOT_DRAWS, len(sums)))
    boot = sums["sum"].to_numpy()[idx].sum(1) / sums["count"].to_numpy()[idx].sum(1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return {"n": int(len(t)), "diff": round(float(diff.mean()), 4),
            "ci95": [round(float(lo), 4), round(float(hi), 4)],
            "by_season": {int(s): round(float(v), 3) for s, v in diff.groupby(t["season"]).mean().items()}}


def compare(d: dict, frozen: dict, m: np.ndarray, open_margin: dict | None = None) -> dict:
    """Each bundle minus P1 (sigma_pred 13.5) on the games in mask m."""
    g = d["g"]
    t = g.loc[m, ["game_id", "season", "season_type", "week", "margin"]].copy()
    p1 = forecast("P1", d)
    t["p1"], t["p1_sd"] = p1["mhat"].to_numpy()[m], sd(p1, SIGMA_PRED_P1)[m]
    out = {"P1": metrics(t["p1"].to_numpy(), t["p1_sd"].to_numpy(), t["margin"].to_numpy(float))}
    early = (t["season_type"] == "regular") & (t["week"] <= 3)
    for b in ("A", "B", "C"):
        f = forecast(b, d, frozen["bundles"][b]["pick"])
        t[b], t[b + "_sd"] = f["mhat"].to_numpy()[m], sd(f, frozen["bundles"][b]["sigma_pred"])[m]
        res = {"metrics": metrics(t[b].to_numpy(), t[b + "_sd"].to_numpy(), t["margin"].to_numpy(float)),
               "crps": paired(t, b, "p1", "crps"), "mae": paired(t, b, "p1", "mae")}
        for name, sub in (("wk1_3", t[early]), ("later", t[~early])):
            if len(sub):
                res[f"crps_{name}"] = paired(sub, b, "p1", "crps")
        if open_margin is not None:
            res["encompassing_vs_open"] = encompassing(t, b, open_margin)
        out[b] = res
    return out


def bovada_open(root: Path, seasons) -> dict[int, float]:
    """{game_id: Bovada opening home margin} (= -spreadOpen). Reported at a look, never gated."""
    out = {}
    for s in seasons:
        p = root / "raw" / f"lines_{s}.json"
        for g in (json.loads(p.read_text()) if p.exists() else []):
            for line in g.get("lines") or []:
                if line.get("provider") == "Bovada" and line.get("spreadOpen") is not None:
                    out[g["id"]] = -float(line["spreadOpen"])
    return out


def encompassing(t: pd.DataFrame, b: str, open_margin: dict[int, float]) -> dict:
    """OLS slope of (margin - open) on (forecast - open); > 0 means information beyond the open."""
    o = t["game_id"].map(open_margin)
    k = o.notna()
    x, y = (t.loc[k, b] - o[k]).to_numpy(), (t.loc[k, "margin"] - o[k]).to_numpy()
    if k.sum() < 3 or np.var(x) == 0:
        return {"n": int(k.sum()), "beta": None}
    return {"n": int(k.sum()), "beta": round(float(np.cov(x, y)[0, 1] / np.var(x, ddof=1)), 4)}


# --- modes ---------------------------------------------------------------------------------

def _compact(frozen: dict) -> str:
    """One line per top-level key and per bundle, so the frozen file diffs readably."""
    def line(k, v, ind):
        return f'{ind}"{k}": ' + json.dumps(v, separators=(", ", ": "), default=str)
    keys = list(frozen)
    out = ["{"]
    for n, k in enumerate(keys):
        end = "," if n < len(keys) - 1 else ""
        if k == "bundles":
            bs = list(frozen[k])
            out += ['  "bundles": {'] + [line(b, frozen[k][b], "    ") + ("," if m < len(bs) - 1 else "")
                                          for m, b in enumerate(bs)] + ["  }" + end]
        else:
            out.append(line(k, frozen[k], "  ") + end)
    return "\n".join(out + ["}"]) + "\n"


def freeze(root: Path, force: bool = False) -> dict:
    if FROZEN.exists() and not force:
        raise SystemExit(f"{FROZEN} exists; P3 picks are frozen once")
    d = load(root, max(DESCRIBE))
    assert d["g"]["season"].max() <= max(DESCRIBE), "freeze must not read 2026 or later"
    tuned = {b: tune(b, d) for b in ("A", "B", "C")}
    for b, r in tuned.items():
        r["fingerprint"], r["fingerprint_n"] = fingerprint(d, b, r["pick"], r["sigma_pred"])
    frozen = {
        "spec": "rankings/docs/specs/2026-10-16-glicko-p3-bundles-design.md",
        "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "base": {"FROZEN_P1": FROZEN_P1, "sigma_pred": SIGMA_PRED_P1},
        "tune_seasons": TUNE, "bundles": tuned,
        "trial_count": {b: {"grid": r["grid_points"], "with_sigma_pred": r["grid_points"] * len(SIGMA_PRED)}
                        for b, r in tuned.items()},
        "notes": {"h2020": f"not identifiable on 2014-2019; frozen at grid midpoint {H2020_UNIDENTIFIED}",
                  "b_half_credit": "CFBD player PPA covers FBS players only, so transfers from below "
                                   "FBS have no production row and add nothing; half credit not applied",
                  "rp_coverage": d["rp_coverage"], "ctx_missing": d["ctx_missing"]},
        "holdout": {"start": HOLDOUT_START.isoformat(), "looks": {k: {"last_season": v["last"],
                    "not_before": v["not_before"].isoformat()} for k, v in LOOKS.items()},
                    "bootstrap": {"draws": BOOT_DRAWS, "seed": BOOT_SEED}},
    }
    FROZEN.write_text(_compact(frozen))
    describe = compare(d, frozen, mask(d["g"], DESCRIBE))
    return {"frozen": frozen, "describe_2021_25": describe}


def season_complete(root: Path, season: int) -> bool:
    games = json.loads((root / "raw" / f"games_{season}.json").read_text())
    d1 = [g for g in games if g.get("homeClassification") in ("fbs", "fcs")
          and g.get("awayClassification") in ("fbs", "fcs")]
    return bool(d1) and all(g.get("completed") for g in d1)


def look(root: Path, which: str, today: date | None = None) -> dict:
    spec = LOOKS[which]
    today = today or date.today()
    if today < spec["not_before"]:
        raise SystemExit(f"--look {which} is not allowed before {spec['not_before']}")
    if not season_complete(root, spec["last"]):
        raise SystemExit(f"--look {which} needs every {spec['last']} D-I game completed")
    frozen = json.loads(FROZEN.read_text())
    d_check = load(root, max(DESCRIBE))
    for b, r in frozen["bundles"].items():
        fp, _ = fingerprint(d_check, b, r["pick"], r["sigma_pred"])
        if fp != r["fingerprint"]:
            raise SystemExit(f"bundle {b}: forecast fingerprint changed since freeze; no look")
    d = load(root, spec["last"])
    g = d["g"]
    m = ((g["home_div"] == FBS) & (g["away_div"] == FBS) & (g["kickoff"] > HOLDOUT_START)).to_numpy()
    res = compare(d, frozen, m, bovada_open(root, range(2026, spec["last"] + 1)))
    for b in ("A", "B", "C"):
        c, a = res[b]["crps"]["ci95"], res[b]["mae"]["ci95"]
        res[b]["adopt"] = {"crps_below_0": c[1] < 0, "mae_not_above_0": a[0] <= 0,
                           "verdict": None if which == "interim" else bool(c[1] < 0 and a[0] <= 0)}
    return {"look": which, "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **res}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--look", choices=sorted(LOOKS))
    args = ap.parse_args(argv)
    from cfb_paths import DATA_ROOT, PROCESSED

    out = freeze(DATA_ROOT) if args.freeze else look(DATA_ROOT, args.look)
    name = "glicko_p3_freeze.json" if args.freeze else f"glicko_p3_look_{args.look}.json"
    path = PROCESSED / "ratings" / name
    path.write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps(out, indent=1, default=str))
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
