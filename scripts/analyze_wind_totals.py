"""Crosswind vs head/tail wind against scoring, per docs/wind-orientation-totals.md.

Fits the pre-registered specs in that plan and prints every estimate with a
cluster-robust CI. Nothing here picks a model from the data -- the spec, the
controls, the clusters and the speed buckets are all fixed in the plan.

    python scripts/analyze_wind_totals.py [--data-dir data]
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from cfb_paths import DATA_ROOT  # noqa: E402

# Pre-registered wind-speed buckets (mph), plan section 2.
BUCKETS = ((0.0, 7.0), (7.0, 12.0), (12.0, 18.0), (18.0, 1e9))

# teamrankings and numberfire are model projection sites, not sportsbooks. A total
# sourced from them is not a market price, so "beyond what the market priced" does
# not hold for those games. --books-only drops them.
NON_BOOK_PROVIDERS = {"teamrankings", "numberfire"}


def total_providers(data_dir: Path) -> dict[str, str]:
    """Which provider supplied each game's total, replicating normalize's selection."""

    def first(d: dict, *keys: str):
        for k in keys:
            if d.get(k) is not None:
                return d[k]
        return None

    out: dict[str, str] = {}
    for path in sorted(glob.glob(str(data_dir / "raw" / "lines_*.json"))):
        for game in json.loads(Path(path).read_text(encoding="utf-8")):
            gid = first(game, "id", "gameId", "game_id")
            lines = game.get("lines") or []
            usable = [
                ln for ln in lines
                if ln.get("spread") is not None or first(ln, "overUnder", "over_under") is not None
            ]
            if gid is None or not usable:
                continue
            line = next(
                (ln for ln in usable if str(ln.get("provider", "")).lower() == "consensus"),
                usable[0],
            )
            if first(line, "overUnder", "over_under") is None:
                line = next(
                    (ln for ln in lines if first(ln, "overUnder", "over_under") is not None), line
                )
            out[str(gid)] = str(line.get("provider") or "")
    return out


def load_rows(data_dir: Path, *, books_only: bool = False) -> list[dict]:
    """Outdoor games with a closing total, a final score and a gated field azimuth."""
    features = json.loads((data_dir / "processed" / "features.json").read_text(encoding="utf-8"))
    feature_map = features["games"]
    providers = total_providers(data_dir) if books_only else {}
    rows: list[dict] = []
    with (data_dir / "processed" / "games.csv").open(newline="", encoding="utf-8") as fh:
        for game in csv.DictReader(fh):
            f = feature_map.get(game["game_id"])
            if not f or f.get("wind_cross_mph") is None:
                continue
            if not (game["home_points"] and game["away_points"] and game["total"]):
                continue
            if f.get("weather_temperature") is None or f.get("weather_precipitation") is None:
                continue
            if books_only and providers.get(game["game_id"], "").lower() in NON_BOOK_PROVIDERS:
                continue
            total = float(game["total"])
            rows.append(
                {
                    "points": float(game["home_points"]) + float(game["away_points"]),
                    "close": total,
                    "cross": float(f["wind_cross_mph"]),
                    "along": float(f["wind_along_mph"]),
                    "speed": float(f["weather_windSpeed"]),
                    "temp": float(f["weather_temperature"]),
                    "precip": float(f["weather_precipitation"]),
                    "season": int(game["season"]),
                    "venue": f.get("venue") or game["game_id"],
                }
            )
    return rows


def design(rows: list[dict], *, control_close: bool) -> tuple[np.ndarray, list[str]]:
    """Intercept, the two wind components, weather controls, season dummies."""
    seasons = sorted({r["season"] for r in rows})[1:]  # first season is the reference level
    names = ["const", "cross", "along", "temp", "precip"]
    cols = [
        np.ones(len(rows)),
        np.array([r["cross"] for r in rows]),
        np.array([r["along"] for r in rows]),
        np.array([r["temp"] for r in rows]),
        np.array([r["precip"] for r in rows]),
    ]
    if control_close:
        names.append("close")
        cols.append(np.array([r["close"] for r in rows]))
    for s in seasons:
        names.append(f"season_{s}")
        cols.append(np.array([1.0 if r["season"] == s else 0.0 for r in rows]))
    return np.column_stack(cols), names


def cluster_ols(X: np.ndarray, y: np.ndarray, groups: list[str]) -> tuple[np.ndarray, np.ndarray, int]:
    """OLS with CR1 cluster-robust covariance. Returns (beta, vcov, n_clusters)."""
    xtx_inv = np.linalg.pinv(X.T @ X)
    beta = xtx_inv @ (X.T @ y)
    resid = y - X @ beta
    meat = np.zeros((X.shape[1], X.shape[1]))
    uniq = sorted(set(groups))
    idx: dict[str, list[int]] = {g: [] for g in uniq}
    for i, g in enumerate(groups):
        idx[g].append(i)
    for g in uniq:
        rows = idx[g]
        s = X[rows].T @ resid[rows]
        meat += np.outer(s, s)
    n, k, m = len(y), X.shape[1], len(uniq)
    # ponytail: CR1 small-sample correction, the standard one; CR3 if clusters drop below ~40.
    correction = (m / (m - 1)) * ((n - 1) / (n - k))
    return beta, correction * (xtx_inv @ meat @ xtx_inv), m


def report(label: str, rows: list[dict], *, control_close: bool) -> dict[str, tuple[float, float]]:
    X, names = design(rows, control_close=control_close)
    y = np.array([r["points"] - r["close"] for r in rows]) if not control_close else np.array(
        [r["points"] for r in rows]
    )
    beta, vcov, m = cluster_ols(X, y, [r["venue"] for r in rows])
    se = np.sqrt(np.diag(vcov))
    out: dict[str, tuple[float, float]] = {}
    print(f"\n{label}  (n={len(rows)}, venues={m})")
    for term in ("cross", "along"):
        i = names.index(term)
        out[term] = (beta[i], se[i])
        lo, hi = beta[i] - 1.96 * se[i], beta[i] + 1.96 * se[i]
        print(f"  beta_{term:<6} {beta[i]:+.4f}  SE {se[i]:.4f}  95% CI [{lo:+.4f}, {hi:+.4f}]  pts/mph")
    ic, ia = names.index("cross"), names.index("along")
    diff = beta[ic] - beta[ia]
    se_d = float(np.sqrt(vcov[ic, ic] + vcov[ia, ia] - 2 * vcov[ic, ia]))
    print(
        f"  difference   {diff:+.4f}  SE {se_d:.4f}  "
        f"95% CI [{diff - 1.96 * se_d:+.4f}, {diff + 1.96 * se_d:+.4f}]  pts/mph"
    )
    out["diff"] = (diff, se_d)
    return out


def diagnostic_speed(rows: list[dict]) -> None:
    """Sanity check: does this spec recover the known raw wind-speed effect?

    Not a pre-registered test. If total wind speed shows nothing either, a null on
    the orientation split says the pipeline is blind, not that orientation is inert.
    """
    seasons = sorted({r["season"] for r in rows})[1:]
    cols = [
        np.ones(len(rows)),
        np.array([r["speed"] for r in rows]),
        np.array([r["temp"] for r in rows]),
        np.array([r["precip"] for r in rows]),
    ]
    for s in seasons:
        cols.append(np.array([1.0 if r["season"] == s else 0.0 for r in rows]))
    X = np.column_stack(cols)
    y = np.array([r["points"] - r["close"] for r in rows])
    beta, vcov, m = cluster_ols(X, y, [r["venue"] for r in rows])
    se = np.sqrt(np.diag(vcov))
    print(f"\nmarket residual on raw wind speed  (n={len(rows)}, venues={m})")
    for i, name in enumerate(("intercept", "wind_speed", "temperature", "precipitation")):
        lo, hi = beta[i] - 1.96 * se[i], beta[i] + 1.96 * se[i]
        print(f"  {name:<14} {beta[i]:+.4f}  SE {se[i]:.4f}  95% CI [{lo:+.4f}, {hi:+.4f}]")


def holm(pairs: dict[str, tuple[float, float]]) -> None:
    from math import erfc, sqrt

    tests = [(k, abs(v[0] / v[1]) if v[1] else 0.0) for k, v in pairs.items()]
    ps = sorted(((k, erfc(z / sqrt(2))) for k, z in tests), key=lambda kv: kv[1])
    print("\nPrimary tests, Holm-corrected (plan section 5):")
    for rank, (k, p) in enumerate(ps):
        adj = min(1.0, p * (len(ps) - rank))
        print(f"  beta_{k:<6} p={p:.4f}  Holm p={adj:.4f}  {'reject' if adj < 0.05 else 'no reject'}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", default=DATA_ROOT, type=Path)
    ap.add_argument(
        "--books-only",
        action="store_true",
        help="drop games whose total came from a projection site rather than a book",
    )
    args = ap.parse_args()

    rows = load_rows(args.data_dir, books_only=args.books_only)
    if not rows:
        print("No usable rows. Run `python -m cfb_system_maker enrich` first.")
        return 1

    print("=" * 72)
    print("PRIMARY -- market residual (total_points - closing_total)")
    print("=" * 72)
    primary = report("full sample", rows, control_close=False)
    holm({k: v for k, v in primary.items() if k in ("cross", "along")})

    print("\n" + "=" * 72)
    print("DIAGNOSTIC -- can this spec see the known raw wind-speed effect at all?")
    print("=" * 72)
    diagnostic_speed(rows)

    print("\n" + "=" * 72)
    print("DESCRIPTIVE -- raw total_points, closing total as a control")
    print("=" * 72)
    report("full sample", rows, control_close=True)

    print("\n" + "=" * 72)
    print("DESCRIPTIVE -- market residual by wind-speed bucket (underpowered by design)")
    print("=" * 72)
    for lo, hi in BUCKETS:
        bucket = [r for r in rows if lo <= r["speed"] < hi]
        if len(bucket) < 200:
            print(f"\n{lo:.0f}-{hi:.0f} mph: n={len(bucket)}, too few to fit")
            continue
        report(f"{lo:.0f}-{hi:.0f} mph", bucket, control_close=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
