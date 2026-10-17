"""Tune, freeze and (later) score Glicko bundle P3-D, the FBS-vs-FCS shrink.

    python -m scripts.glicko_p3d_eval --freeze           # tune on 2014-2019, freeze, describe 2021-25
    python -m scripts.glicko_p3d_eval --look interim     # after the 2026 postseason, once
    python -m scripts.glicko_p3d_eval --look final       # after the 2027 postseason, once

Declared in rankings/docs/specs/2026-10-17-glicko-p3d-fcs-design.md. lam is tuned jointly
with sigma_pred by mean CRPS on FBS-vs-FCS regular-season games 2014-2019 (2013 burn-in).
--freeze replays only seasons through 2025. 2021-2025 is described on FBS-vs-FCS and FBS-vs-FBS
games, with the FBS-vs-FCS residual slope (diagnostic D1) under P1 and D; it decides nothing.
The looks refuse to run early, verify the frozen fingerprint, and score games kicking off after
2026-10-17T12:00Z: D minus P1 with sigma_pred 13.5, season-week bootstrap, seed 20261017.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.glicko_diagnostics import _slope
from scripts.glicko_p3 import GlickoShrinkX
from scripts.glicko_p3_eval import BOOT_DRAWS, SIGMA_PRED, best_sigma_pred, mask, metrics, paired, sd
from scripts.glicko_pool_eval import fcs_seed_pool, load_pool_games
from scripts.glicko_ratings import FROZEN_P1, SIGMA_PRED_P1, GlickoMargin, events, run

FROZEN = Path(__file__).with_name("glicko_p3d_frozen.json")
SPEC = "rankings/docs/specs/2026-10-17-glicko-p3d-fcs-design.md"
TUNE = list(range(2014, 2020))
DESCRIBE = [2021, 2022, 2023, 2024, 2025]
LAMS = (0.0, 0.05, 0.10, 0.15, 0.20, 0.25)
HOLDOUT_START = pd.Timestamp("2026-10-17T12:00:00Z")
LOOKS = {"interim": {"last": 2026, "not_before": date(2027, 1, 20)},
         "final": {"last": 2027, "not_before": date(2028, 1, 20)}}
SEED = 20261017


def load(root: Path, last: int) -> dict:
    g, _ = load_pool_games(root, last, [])
    g = g[g["season"] <= last].reset_index(drop=True)
    return {"g": g, "ev": events(g), "m0": fcs_seed_pool(g)}


def forecast(d: dict, lam: float | None = None) -> pd.DataFrame:
    """lam=None is P1 itself; GlickoShrinkX(lam=0) reproduces it exactly."""
    model = (GlickoMargin(**FROZEN_P1, m0=d["m0"]) if lam is None
             else GlickoShrinkX(**FROZEN_P1, m0=d["m0"], lam=lam))
    fc = run(model, d["g"], d["ev"])
    return pd.DataFrame({"mhat": fc["mhat"].to_numpy(), "rd2": fc["rd2"].to_numpy(),
                         "mult": 1.0}, index=d["g"].index)


def tune(d: dict) -> dict:
    g = d["g"]
    dt = {"g": g[g["season"] <= max(TUNE)].reset_index(drop=True), "m0": d["m0"]}
    dt["ev"] = events(dt["g"])
    m, y = mask(dt["g"], TUNE, pop="fbs_fcs"), dt["g"]["margin"].to_numpy(float)
    trials = sorted(((*best_sigma_pred(forecast(dt, lam), m, y), lam) for lam in LAMS),
                    key=lambda r: r[0])
    loss, sp, lam = trials[0]
    p1_loss, p1_sp = best_sigma_pred(forecast(dt), m, y)
    return {"pick": {"lam": lam}, "sigma_pred": sp, "tune_crps_fbs_fcs": round(loss, 4),
            "p1_tune_crps_fbs_fcs": round(p1_loss, 4), "p1_tune_sigma_pred": p1_sp,
            "boundary": ("low" if lam == LAMS[0] else "high") if lam in (LAMS[0], LAMS[-1]) else None,
            "grid": [(round(l, 4), s, lam) for l, s, lam in trials]}


def fingerprint(d: dict, lam: float, sigma_pred: float) -> tuple[str, int]:
    """sha256 over (game_id, mean, sd) of D's forecasts of every regular-season game 2014-2025
    with at least one FBS team (both populations it is scored on)."""
    f = forecast(d, lam)
    m = mask(d["g"], range(2014, 2026)) | mask(d["g"], range(2014, 2026), pop="fbs_fcs")
    rows = zip(d["g"]["game_id"].to_numpy()[m], f["mhat"].to_numpy()[m], sd(f, sigma_pred)[m])
    return (hashlib.sha256("\n".join(f"{int(i)},{a:.6f},{b:.6f}" for i, a, b in rows).encode()).hexdigest(),
            int(m.sum()))


def residual_slope(d: dict, f: pd.DataFrame, m: np.ndarray) -> dict:
    """Diagnostic D1 on the games in m: slope of (margin - forecast) on the forecast."""
    g = d["g"]
    t = pd.DataFrame({"mhat": f["mhat"].to_numpy()[m],
                      "e": g["margin"].to_numpy(float)[m] - f["mhat"].to_numpy()[m],
                      "cluster": (g["season"].astype(str) + "-" + g["week"].astype(str)).to_numpy()[m]})
    return _slope(t)


def compare(d: dict, frozen: dict, m: np.ndarray) -> dict:
    g = d["g"]
    t = g.loc[m, ["game_id", "season", "week", "margin"]].copy()
    p1, dd = forecast(d), forecast(d, frozen["pick"]["lam"])
    t["p1"], t["p1_sd"] = p1["mhat"].to_numpy()[m], sd(p1, SIGMA_PRED_P1)[m]
    t["D"], t["D_sd"] = dd["mhat"].to_numpy()[m], sd(dd, frozen["sigma_pred"])[m]
    y = t["margin"].to_numpy(float)
    return {"P1": metrics(t["p1"].to_numpy(), t["p1_sd"].to_numpy(), y),
            "D": metrics(t["D"].to_numpy(), t["D_sd"].to_numpy(), y),
            "crps": paired(t, "D", "p1", "crps", seed=SEED), "mae": paired(t, "D", "p1", "mae", seed=SEED),
            "slope_P1": residual_slope(d, p1, m), "slope_D": residual_slope(d, dd, m)}


def freeze(root: Path) -> dict:
    if FROZEN.exists():
        raise SystemExit(f"{FROZEN} exists; P3-D is frozen once")
    d = load(root, max(DESCRIBE))
    assert d["g"]["season"].max() <= max(DESCRIBE), "freeze must not read 2026 or later"
    r = tune(d)
    fp, n = fingerprint(d, r["pick"]["lam"], r["sigma_pred"])
    frozen = {"spec": SPEC, "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "base": {"FROZEN_P1": FROZEN_P1, "sigma_pred": SIGMA_PRED_P1}, "tune_seasons": TUNE,
              **r, "fingerprint": fp, "fingerprint_n": n,
              "trial_count": {"grid": len(LAMS), "with_sigma_pred": len(LAMS) * len(SIGMA_PRED)},
              "holdout": {"start": HOLDOUT_START.isoformat(),
                          "looks": {k: {"last_season": v["last"], "not_before": v["not_before"].isoformat()}
                                    for k, v in LOOKS.items()},
                          "bootstrap": {"draws": BOOT_DRAWS, "seed": SEED}}}
    FROZEN.write_text(json.dumps(frozen, default=str) + "\n")
    g = d["g"]
    describe = {"fbs_fcs": compare(d, frozen, mask(g, DESCRIBE, regular=False, pop="fbs_fcs")),
                "fbs_fbs": compare(d, frozen, mask(g, DESCRIBE))}
    return {"frozen": frozen, "describe_2021_25": describe}


def season_complete(root: Path, season: int) -> bool:
    games = json.loads((root / "raw" / f"games_{season}.json").read_text())
    d1 = [g for g in games if g.get("homeClassification") in ("fbs", "fcs")
          and g.get("awayClassification") in ("fbs", "fcs")]
    return bool(d1) and all(g.get("completed") for g in d1)


def look(root: Path, which: str, today: date | None = None) -> dict:
    spec = LOOKS[which]
    if (today or date.today()) < spec["not_before"]:
        raise SystemExit(f"--look {which} is not allowed before {spec['not_before']}")
    if not season_complete(root, spec["last"]):
        raise SystemExit(f"--look {which} needs every {spec['last']} D-I game completed")
    frozen = json.loads(FROZEN.read_text())
    fp, _ = fingerprint(load(root, max(DESCRIBE)), frozen["pick"]["lam"], frozen["sigma_pred"])
    if fp != frozen["fingerprint"]:
        raise SystemExit("P3-D forecast fingerprint changed since freeze; no look")
    d = load(root, spec["last"])
    g, seasons = d["g"], range(2026, spec["last"] + 1)
    after = (g["kickoff"] > HOLDOUT_START).to_numpy()
    fc = compare(d, frozen, mask(g, seasons, regular=False, pop="fbs_fcs") & after)
    ff = compare(d, frozen, mask(g, seasons, regular=False) & after)
    ok = fc["crps"]["ci95"][1] < 0 and ff["crps"]["ci95"][0] <= 0
    return {"look": which, "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "fbs_fcs": fc, "fbs_fbs": ff,
            "adopt": {"fbs_fcs_crps_below_0": fc["crps"]["ci95"][1] < 0,
                      "fbs_fbs_crps_lower_le_0": ff["crps"]["ci95"][0] <= 0,
                      "verdict": None if which == "interim" else bool(ok)}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--look", choices=sorted(LOOKS))
    args = ap.parse_args(argv)
    from cfb_paths import DATA_ROOT, PROCESSED

    out = freeze(DATA_ROOT) if args.freeze else look(DATA_ROOT, args.look)
    path = PROCESSED / "ratings" / ("glicko_p3d_freeze.json" if args.freeze else f"glicko_p3d_look_{args.look}.json")
    path.write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps(out, indent=1, default=str))
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
