"""Edge-decay monitor driver.

  python monitor/run_monitor.py [--season 2013 ... 2025] [--width 3]
"""

import argparse

from monitor import (
    HURDLE,
    load_from_raw,
    per_season,
    slope_trend,
    trailing_windows,
)


def _print_table(title, stats_list):
    print("\n" + "=" * 92)
    print(title)
    print("=" * 92)
    print(f"  {'window':>9} {'N':>6} {'slope':>8} {'95% CI':>16} {'p':>9} "
          f"{'hurdleBias':>10} {'bets':>5} {'win%':>7} {'win95CI':>15} {'flag':>10}")
    for s in stats_list:
        ci = f"[{s.slope_ci[0]:+.3f},{s.slope_ci[1]:+.3f}]"
        wci = f"[{s.win_ci[0]*100:4.1f},{s.win_ci[1]*100:4.1f}]" if s.n_bets else "        n/a    "
        flags = []
        if not s.alive:
            flags.append("SLOPE~0")
        if s.n_bets and not s.profitable:
            flags.append("UNPROF")
        flag = ",".join(flags) if flags else "ok"
        wr = f"{s.win_rate*100:5.2f}%" if s.n_bets else "   n/a"
        print(f"  {s.label:>9} {s.n_games:>6} {s.slope:>+8.3f} {ci:>16} "
              f"{s.p_slope:>9.2e} {s.hurdle_bias:>10.2f} {s.n_bets:>5} {wr:>7} "
              f"{wci:>15} {flag:>10}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, nargs="+", default=list(range(2013, 2026)))
    ap.add_argument("--width", type=int, default=3, help="trailing-window width (seasons)")
    args = ap.parse_args()

    data = load_from_raw(args.season)
    print(f"Loaded {len(data)} seasons: {', '.join(map(str, sorted(data)))}")
    print(f"Breakeven hurdle = {HURDLE:.4f}.  Flags: SLOPE~0 = slope 95% CI "
          f"includes 0 (signal weak/dead); UNPROF = bias>1.0 win% CI lower "
          f"bound below breakeven.")

    season_stats = per_season(data)
    _print_table("PER-SEASON (noisy; each season standalone)", season_stats)

    _print_table(f"TRAILING {args.width}-SEASON WINDOWS (smoother decay signal)",
                 trailing_windows(data, args.width))

    # Trend test on the per-season slope.
    tr_slope, tr_p, tr_r2 = slope_trend(season_stats)
    print("\n" + "=" * 92)
    print("SLOPE TREND (OLS of per-season probit slope on year)")
    print("=" * 92)
    direction = "DECLINING (consistent with books correcting)" if tr_slope < 0 \
        else "rising/flat (no decay)"
    sig = "significant" if tr_p < 0.05 else "NOT significant"
    print(f"  trend = {tr_slope:+.4f} slope-units/yr   p = {tr_p:.3f} ({sig})   "
          f"R2 = {tr_r2:.2f}")
    print(f"  -> {direction}")
    if tr_slope < 0 and tr_p >= 0.05:
        print("  Caveat: direction is down but not statistically significant with "
              "this few seasons. Watch; do not conclude yet.")


if __name__ == "__main__":
    main()
