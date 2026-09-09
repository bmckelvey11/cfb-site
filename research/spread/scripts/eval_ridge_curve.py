"""Amendment A7 -- is E6's ridge penalty identified, or is it an artifact of the grid bound?

Registered in research/spread/docs/prereg-line-movement.md. Version A chose lambda = 1e4, the top
of its grid, in 19 of 20 seasons; A4 widened to 5e4 and chose *its* top value in 19 of 19. Two
widenings, two edges, never an interior choice.

The mechanism this tests: pick_1se takes the most-shrunk lambda whose validation error is within
one SE of the best, so a FLAT validation curve makes the rule run to the top of whatever grid it
is handed. That is indistinguishable from "the data want more shrinkage" unless the curve itself
is reported -- which no run before this one did.

Why this grid is decisive: as lambda grows the ridge coefficients go to zero, E6's correction
goes to zero, and E6 degenerates to R0 (the recalibrated opener, R^2 ~ 0.0005). E6 at 5e4 scores
~0.20, so the curve MUST turn over below 1e9. The sanity check below refuses to read a decision
out of a run where it does not.

    python research/spread/scripts/eval_ridge_curve.py

Writes processed/pt_ridge_curve_a7.json. Exploratory: the one confirmatory hypothesis in this
tree is the version B E4 slope at the Monday anchor. No p-value is attached to anything here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_combination_sweep as sweep  # noqa: E402
import eval_line_movement as elm  # noqa: E402
import eval_prediction_tracker_models as base  # noqa: E402

A7_LAMBDA = [1e3, 3e3, 1e4, 3e4, 1e5, 3e5, 1e6, 3e6, 1e7, 3e7, 1e8, 3e8, 1e9]
OUT = base.OUT_DIR / "pt_ridge_curve_a7.json"
DECADES_FLAT = 3          # branch 2 fires when the curve is within 1 SE across >= this many
SANITY_TOL = 0.01         # R^2 at the top lambda must be within this of R0's


def load():
    """The A6 walk-forward panel, exactly as eval_line_movement builds it."""
    df, models = base.load()
    models = [m for m in models if m not in elm.MARKET_LINES]
    df = df[df["line"].notna() & df["lineopen"].notna()].reset_index(drop=True)
    df["margin"] = df["y"]
    df["y"] = -df["line"].to_numpy(float)
    return df, models


def r2_for(df, preds, sup, key):
    y = df["y"].to_numpy()
    open_m = -df["lineopen"].to_numpy(float)
    base_mse = float(((y - open_m) ** 2)[sup].mean())      # M0: the line does not move
    return 1 - float(((y - preds[key]) ** 2)[sup].mean()) / base_mse


def main() -> int:
    df, models = load()
    ev = (df["season"] > base.BURN_IN_THROUGH).to_numpy()
    print(f"{len(df)} games, {len(models)} models before the per-season screen; "
          f"{len(A7_LAMBDA)} grid points")

    # One run per lambda, E6 alone on a singleton grid, so every point is a real out-of-sample
    # R^2 rather than an interpolation. R0 and E4 come free from sweep regardless of `only`.
    runs, finite = {}, ev.copy()
    for lam in A7_LAMBDA:
        preds, *_ = elm.sweep_walk_forward(df, models, "lineopen", only=["E6"],
                                           grids={**sweep.GRIDS, "E6": [lam]})
        runs[lam] = preds
        finite &= np.isfinite(preds["E6"]) & np.isfinite(preds["R0"])
        print(f"  lambda={lam:>10.0f} done")

    sup = finite
    r2 = {lam: r2_for(df, p, sup, "E6") for lam, p in runs.items()}
    r2_r0 = r2_for(df, runs[A7_LAMBDA[0]], sup, "R0")
    print(f"\ncommon support n={int(sup.sum())}; R0 R^2 = {r2_r0:.4f}")
    for lam in A7_LAMBDA:
        print(f"  lambda={lam:>10.0f}  R^2={r2[lam]:.4f}")

    # The registered sanity check: if the ridge does not collapse to the anchor as lambda grows,
    # the fitter is wrong and no decision may be read out of this run.
    gap = abs(r2[A7_LAMBDA[-1]] - r2_r0)
    sane = gap <= SANITY_TOL
    print(f"\nsanity: |R^2(1e9) - R^2(R0)| = {gap:.4f} "
          f"({'within' if sane else 'OUTSIDE'} the registered {SANITY_TOL} tolerance)")

    # The tuning curve the decision rule actually keys on, from one run over the full grid.
    sweep.CURVE_LOG = []
    elm.sweep_walk_forward(df, models, "lineopen", only=["E6"],
                           grids={**sweep.GRIDS, "E6": list(A7_LAMBDA)})
    curves = [c for c in sweep.CURVE_LOG if c["method"] == "E6"]
    sweep.CURVE_LOG = None

    chosen = [float(c["chosen_1se"]) for c in curves]
    argmins = [float(c["argmin"]) for c in curves]
    modal_1se = max(set(chosen), key=chosen.count)
    modal_argmin = max(set(argmins), key=argmins.count)
    at_top = sum(c == A7_LAMBDA[-1] for c in chosen)
    print(f"\n{len(curves)} evaluation seasons")
    print(f"  1-SE choice : modal {modal_1se:.0f}, at the grid top in {at_top} of {len(curves)}")
    print(f"  argmin      : modal {modal_argmin:.0f}")

    # How many decades of lambda sit within one SE of the best, per season -- the flatness the
    # 1-SE rule is exploiting when it runs to the bound.
    flat_decades = []
    for c in curves:
        m, se = np.array(c["val_mse"]), c["se_at_best"]
        within = [float(p) for p, v in zip(c["params"], m) if v <= m.min() + se]
        flat_decades.append(np.log10(max(within) / min(within)) if within else 0.0)
    med_flat = float(np.median(flat_decades))
    print(f"  decades of lambda within 1 SE of the best: median {med_flat:.1f}")

    if not sane:
        branch, action = "defect", ("R^2 at the top of the grid did not return to R0's. The "
                                    "ridge is not collapsing to the anchor; fix the fitter "
                                    "before reading anything else from this run.")
    elif modal_1se == A7_LAMBDA[-1]:
        branch, action = "still_at_the_edge", ("1-SE chose the grid's top value even at 1e9, "
                                               "which the turnover argument says is unreachable. "
                                               "Retire E6 from the served slate and investigate "
                                               "the fitter.")
    elif med_flat >= DECADES_FLAT:
        branch, action = "flat", (f"The curve is within 1 SE across a median {med_flat:.1f} "
                                  f"decades of lambda, so the 1-SE rule is a tie-breaker rather "
                                  f"than an identification. Retire E6 from the served slate; "
                                  f"weekly_slate.py serves E4 and the model median.")
    else:
        branch, action = "identified", (f"The curve identifies a penalty: serve E6 at "
                                        f"lambda={modal_1se:.0f}.")
    print(f"\nBRANCH: {branch}\n  {action}")

    out = {"amendment": "A7", "grid": A7_LAMBDA, "n": int(sup.sum()),
           "r2_by_lambda": {str(k): v for k, v in r2.items()}, "r2_r0": r2_r0,
           "sanity_gap_vs_r0": gap, "sanity_ok": bool(sane),
           "modal_1se": modal_1se, "modal_argmin": modal_argmin,
           "seasons_choosing_grid_top": at_top, "n_seasons": len(curves),
           "median_decades_within_1se": med_flat, "flat_decades_by_season": flat_decades,
           "branch": branch, "action": action, "curves": curves}
    OUT.write_text(json.dumps(out, indent=2, default=float))
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
