"""Bound the winner's-curse correction on the sweep's selected method.

Andrews-Kitagawa-McCloskey conditions inference on having SELECTED a candidate because
it optimised a noisy criterion. Implementing it literally needs the m-by-m cluster-robust
covariance of the candidate loss differentials, which the sweep does not persist.

It does not need to. The correction is bounded by E[max_m Z] * se * sqrt(1 - rho), and
BOTH unknown inputs (rho, effective m) only ever make it smaller than the rho=0 corner.
So the corner is a valid worst case and the conclusion needs no re-run.
"""

from __future__ import annotations

import json
import numpy as np
from scipy import stats

BOOT_FLOOR = 1 / 2000  # N_BOOT=2000 in eval_prediction_tracker_models.wild_cluster_boot


def emax(m, n=400_000, seed=0):
    """E[max of m iid standard normals]."""
    rng = np.random.default_rng(seed)
    return float(rng.standard_normal((n, m)).max(axis=1).mean())


def se_from_ci(lo, hi):
    """Conservative SE from a bootstrap-t interval.

    Deliberately divides the half-width by the NORMAL 0.975 quantile. The real bootstrap-t
    quantiles at 20 clusters are fatter than 1.96, which would imply a SMALLER se and a
    LARGER z -- so this is the reading least favourable to the finding.
    """
    return (hi - lo) / 2 / stats.norm.ppf(0.975)


def bound(d, lo, hi, m, rhos=(0.0, 0.3, 0.7, 0.9, 0.99)):
    se = se_from_ci(lo, hi)
    z = abs(d) / se
    e = emax(m)
    out = []
    for r in rhos:
        shift = e * np.sqrt(1 - r)
        zc = z - shift
        out.append({"rho": r, "z_corr": zc, "p_corr": 2 * stats.norm.sf(zc),
                    "bias_bound": shift * se})
    return se, z, e, out


def main():
    # E14 (complete subset regression, k=1), opening benchmark, post-coverage-fix run.
    d, lo, hi, m = -2.614521, -3.595841, -1.583381, 8
    se, z, e, rows = bound(d, lo, hi, m)
    print(f"E14 vs R0 (opening): d={d:+.4f}  se~{se:.4f}  naive z~{z:.3f}")
    print(f"E[max_{m} Z] = {e:.4f}   bootstrap p floor = {BOOT_FLOOR:.5f}\n")
    print(f"{'rho':>6s} {'z_corr':>8s} {'p_corr':>10s} {'<floor?':>8s} {'bias<=':>7s}")
    for r in rows:
        print(f"{r['rho']:6.2f} {r['z_corr']:8.3f} {r['p_corr']:10.2e} "
              f"{'yes' if r['p_corr'] < BOOT_FLOOR else 'NO':>8s} {r['bias_bound']:7.3f}")
    worst = rows[0]
    print(f"\nworst case (rho=0): p={worst['p_corr']:.2e}, "
          f"effect no weaker than {d + worst['bias_bound']:+.3f}")
    # Two of the eight candidates are degenerate on opening (E8 |corr|=0.03, E12=0.17):
    # they collapsed onto R0 and could not have won, so effective m is smaller.
    _, _, e6, r6 = bound(d, lo, hi, 6)
    print(f"effective m=6 (drop degenerate E8/E12): E[max]={e6:.4f}, "
          f"rho=0 p={r6[0]['p_corr']:.2e}")


def _check():
    """Monotonicity is the whole argument: both unknowns shrink the correction."""
    assert emax(4) < emax(8) < emax(16), "E[max] must grow with candidate count"
    _, _, _, rows = bound(-2.6145, -3.5958, -1.5834, 8)
    ps = [r["p_corr"] for r in rows]
    assert ps == sorted(ps, reverse=True), "p must fall as rho rises"
    assert ps[0] < BOOT_FLOOR, "rho=0 corner must still clear the bootstrap floor"
    # a null-sized effect must NOT survive
    _, _, _, weak = bound(-0.2, -0.45, 0.05, 8)
    assert weak[0]["p_corr"] > 0.05, "bound must not rescue a null effect"
    print("checks pass")


if __name__ == "__main__":
    _check()
    main()
