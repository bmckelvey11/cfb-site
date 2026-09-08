"""Head-to-head: same model, same games, graded against the opening vs closing total.

This isolates the value of betting early. Any hit-rate gap here is line value,
not model skill — the predictions are identical, only the number bet differs.

    python research/spread/scripts/compare_lines.py [--data-root PATH]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = next(
    parent for parent in Path(__file__).resolve().parents
    if (parent / "cfb_paths.py").is_file()
)
sys.path.insert(0, str(REPO))

import pandas as pd

from models.totals.data import load
from models.totals.inference import cluster_ids, hit_delta_and_clv
from models.totals.model import _fit_predict, iter_walk_forward_splits


def _fmt_inf(inf: dict, *, scale: float = 1.0) -> str:
    return (
        f"{scale * inf['mean']:+.3f}  "
        f"95% CI [{scale * inf['ci_lo']:+.3f}, {scale * inf['ci_hi']:+.3f}]  "
        f"MDE {scale * inf['mde']:.3f}  "
        f"n={inf['n']} clusters={inf['n_clusters']}"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default=None)
    ap.add_argument("--seasons", type=int, nargs="+",
                    default=[2021, 2022, 2023, 2024, 2025])
    args = ap.parse_args()

    ds = load(args.data_root)
    df = ds.frame.dropna(subset=["ou_open", "total", "pts"]).copy()
    print(f"games with both open and close: {len(df)}")

    parts = []
    expanding_seasons = set()
    for season, train, test in iter_walk_forward_splits(
            df, args.seasons, min_train=300):
        pred = _fit_predict(train, test, ds.feature_cols, "ou_open")
        t = test.assign(pred=pred)
        expanding = bool(train["season"].eq(season).any())
        if expanding:
            expanding_seasons.add(season)
        keep = ["season", "pts", "pred", "ou_open", "total", "game_id"]
        if "week" in t.columns:
            keep.append("week")
        parts.append(t[keep].assign(_expanding=expanding))

    if not parts:
        print("no folds produced")
        return 1

    allg = pd.concat(parts, ignore_index=True)
    headline = allg[~allg["_expanding"]].copy()
    appendix = allg[allg["_expanding"]].copy()

    def _report(frame, title: str) -> None:
        if frame.empty:
            return
        print()
        print(title)
        out = hit_delta_and_clv(
            frame["pts"], frame["pred"], frame["ou_open"], frame["total"],
            cluster_ids(frame),
        )
        print(f"  paired n (no push on either line): {out['n_paired']}")
        print(f"  hit open:  {100 * out['hit_open']:.2f}%")
        print(f"  hit close: {100 * out['hit_close']:.2f}%")
        print(f"  Δ hit (pp): {_fmt_inf(out['hit_delta'], scale=100)}")
        print(f"  mean CLV (pts, model side at the open): {_fmt_inf(out['clv'])}")
        print(f"  mean |open - close|: "
              f"{(frame['ou_open'] - frame['total']).abs().mean():.2f} pts")

    _report(headline, "headline: prior-season folds (paired, week-clustered)")
    if not appendix.empty:
        years = ", ".join(str(s) for s in sorted(expanding_seasons))
        _report(appendix, f"appendix: week-expanding ({years}) — not in headline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
