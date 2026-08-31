"""CLI: `python -m models.totals backtest --line ou_open`."""

from __future__ import annotations

import argparse
from pathlib import Path

from .clv import DEFAULT_LEDGER, MIN_EDGE, refresh_closes, snapshot, summarize
from .data import DEFAULT_DATA_ROOT, load
from .model import (
    CITABLE_MIN_EDGE,
    feature_importance,
    permutation_test,
    walk_forward,
)


def _add_common(p):
    p.add_argument("--data-root", default=None,
                   help=f"cfb-site data directory (default: {DEFAULT_DATA_ROOT})")
    p.add_argument("--line", default="ou_open", choices=["ou_open", "total"],
                   help="ou_open = opening total (bettable); total = closing total")
    p.add_argument("--min-prior-games", type=int, default=3)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="models.totals")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("backtest", help="walk-forward backtest")
    _add_common(b)
    b.add_argument("--seasons", type=int, nargs="+",
                   default=[2021, 2022, 2023, 2024, 2025])
    b.add_argument("--permute", action="store_true", help="run the permutation test")

    f = sub.add_parser("importance", help="feature importance")
    _add_common(f)
    f.add_argument("--top", type=int, default=15)

    s = sub.add_parser("snapshot",
                       help="log takeable current totals (DraftKings/ESPN Bet) for CLV")
    s.add_argument("--data-root", default=None)
    s.add_argument("--season", type=int, default=2026)
    s.add_argument("--ledger", default=None)
    s.add_argument("--min-edge", type=float, default=MIN_EDGE)
    s.add_argument("--min-prior-games", type=int, default=3)
    s.add_argument("--replace", action="store_true",
                   help="overwrite existing ledger rows for the same game")

    c = sub.add_parser("clv", help="refresh closes and report mean CLV")
    c.add_argument("--data-root", default=None)
    c.add_argument("--season", type=int, default=2026)
    c.add_argument("--ledger", default=None)

    args = ap.parse_args(argv)

    if args.cmd == "snapshot":
        return _snapshot(args)
    if args.cmd == "clv":
        return _clv(args)

    ds = load(args.data_root, min_prior_games=args.min_prior_games)
    print(f"loaded {len(ds.frame)} games | {len(ds.feature_cols)} features "
          f"| line={args.line}")

    if args.cmd == "importance":
        imp = feature_importance(ds, line_col=args.line)
        print()
        for name, val in imp.head(args.top).items():
            print(f"  {100 * val:6.2f}%  {name}")
        return 0

    bt = walk_forward(ds, line_col=args.line, test_seasons=tuple(args.seasons))
    if not bt.folds:
        print("no folds produced — not enough training data for these seasons")
        return 1

    print()
    produced = {fold.season for fold in bt.folds}
    for season in args.seasons:
        if season not in produced:
            print(f"  {season}: skipped — not enough prior training "
                  f"(opening lines start 2021; need {300} prior games)")
    headline = [f for f in bt.folds if not f.week_expanding]
    expanding = [f for f in bt.folds if f.week_expanding]
    for fold in headline:
        print(f"  {fold.season}: train={fold.n_train} test={len(fold.frame)}")
    print()
    print("headline: prior-season folds only. "
          f"|edge| >= {CITABLE_MIN_EDGE:g} is the citable row; "
          "other thresholds are diagnostic.")
    summ = bt.summary()
    if summ.empty:
        print("  (no prior-season folds)")
    else:
        print(summ.to_string(index=False))
        print()
        pv = bt.paired_vs_line()
        print(_fmt_paired("paired MSPE vs line", pv["mspe"]))
        print(_fmt_paired("paired MAE  vs line", pv["mae"]))
        print("  (negative Δ = model beats the line on the same games)")
        print()
        print(f"by season (|edge| >= {CITABLE_MIN_EDGE:g}):")
        print(bt.by_season().to_string(index=False))

    if args.permute and not summ.empty:
        print()
        r = permutation_test(bt)
        print(f"permutation (headline): shuffled {r['shuffled_mean']}% "
              f"(95% CI {r['ci_lo']}-{r['ci_hi']}) vs actual {r['actual']}%")

    if expanding:
        print()
        print("appendix: week-expanding folds (not in headline)")
        for fold in expanding:
            print(f"  {fold.season}: train={fold.n_train} test={len(fold.frame)} "
                  "week-expanding")
        app = bt.summary(expanding=True)
        if not app.empty:
            print(app.to_string(index=False))
    return 0


def _fmt_paired(label: str, inf: dict) -> str:
    if inf["n"] == 0:
        return f"{label}: n=0"
    return (
        f"{label}: Δ={inf['mean']:+.3f}  "
        f"95% CI [{inf['ci_lo']:+.3f}, {inf['ci_hi']:+.3f}]  "
        f"MDE {inf['mde']:.3f}  n={inf['n']} clusters={inf['n_clusters']}"
    )


def _snapshot(args) -> int:
    ledger = Path(args.ledger) if args.ledger else DEFAULT_LEDGER
    rows = snapshot(
        data_root=args.data_root, season=args.season, ledger_path=ledger,
        min_edge=args.min_edge, min_prior_games=args.min_prior_games,
        replace=args.replace,
    )
    print(f"logged {len(rows)} game(s) -> {ledger}")
    if not rows:
        print("nothing new (unplayed takeable slate empty, or already logged)")
        return 0
    n_bet = sum(1 for r in rows if r["would_bet"])
    n_early = sum(1 for r in rows if r["regime"] != "validated")
    print(f"  |edge| >= {args.min_edge}: {n_bet}")
    print(f"  unvalidated_early (min prior < {args.min_prior_games}): {n_early}")
    print()
    shown = sorted(rows, key=lambda r: -r["abs_edge"])[:15]
    print(f"{'side':5} {'line':>5} {'pred':>6} {'edge':>6}  matchup")
    for r in shown:
        flag = " *" if r["would_bet"] else ""
        print(f"{r['side']:5} {r['bet_line']:5.1f} {r['pred']:6.1f} "
              f"{r['edge']:+6.2f}{flag}  {r['away']} at {r['home']}")
    if n_early:
        print()
        print("regime is unvalidated_early — paper-trade CLV only; not a live bet card.")
    print()
    print("CLV is empty until closes move. Re-run: python -m models.totals clv")
    return 0


def _clv(args) -> int:
    ledger = Path(args.ledger) if args.ledger else DEFAULT_LEDGER
    rows = refresh_closes(
        data_root=args.data_root, season=args.season, ledger_path=ledger)
    print(f"ledger {ledger}  n={len(rows)}")
    for label, only_bet in (("would_bet", True), ("all logged", False)):
        s = summarize(rows, would_bet_only=only_bet)
        if s is None:
            print(f"  {label}: no closes yet")
            continue
        extra = (f"  graded {s['n_graded']}  hit {s['hit_pct']}%"
                 if "hit_pct" in s else "")
        print(f"  {label}: n={s['n']}  mean CLV {s['mean_clv']:+.3f} pts  "
              f"median {s['median_clv']:+.3f}  "
              f"{s['pct_positive']}% positive{extra}")
    return 0
