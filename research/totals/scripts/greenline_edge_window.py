"""Is there a PFF edge window worth betting? Lower and upper bound on `value` for unders.

    python research/totals/scripts/greenline_edge_window.py
    python research/totals/scripts/greenline_edge_window.py --self-check

Three looks at the same question, on every graded Greenline under flag:

1. Win rate by edge bin, with Wilson intervals. The raw shape.
2. Logistic fit of win on stated edge (and on edge squared). If PFF's number carried
   information the slope would be positive; a negative quadratic would justify a cap.
   Slope standard errors are the honest part: at this n they swallow any slope.
3. Edge vs disagreement with Pinnacle. A flag's stated edge is mostly how far PFF's
   projection sits below the market. If the biggest disagreements lose, the cap is
   really "don't fade Pinnacle by more than X points", which is a better-founded rule
   than a cutoff on PFF's own number.

Then the window: the widest contiguous range of edge bins whose pooled lower bound
is highest, reported with the bins it drops and what those bins did. The script
prints what the window would have done, not what it will do; read the interval.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cfb_paths import INGEST  # noqa: E402
from greenline_season_review import BREAK_EVEN, wilson  # noqa: E402

IN_DIR = INGEST / "pff_scoreboard"
EDGE_BINS = [("0-2%", 0.0, 0.02), ("2-3%", 0.02, 0.03), ("3-3.5%", 0.03, 0.035), ("3.5-4%", 0.035, 0.04),
             ("4-5%", 0.04, 0.05), ("5%+", 0.05, 1.0)]
SHADE_BINS = [("> -1", -1.0, 9), ("-1 to -1.5", -1.5, -1.0), ("-1.5 to -2", -2.0, -1.5), ("< -2", -99, -2.0)]


def rec(rows: list[dict]) -> tuple[int, int]:
    return sum(r["win"] for r in rows), sum(1 - r["win"] for r in rows)


def line(label: str, rows: list[dict]) -> str:
    w, l = rec(rows)
    if not w + l:
        return f"  {label:<14} --"
    lo, hi = wilson(w, w + l)
    return f"  {label:<14} {w:3d}-{l:<3d} {w / (w + l) * 100:5.1f}%  CI {lo * 100:3.0f}-{hi * 100:.0f}%"


def logit_fit(rows: list[dict]) -> str:
    try:
        import numpy as np
        import statsmodels.api as sm
    except ImportError:
        return "  statsmodels not available"
    x = np.array([r["edge"] * 100 for r in rows]); y = np.array([r["win"] for r in rows], dtype=float)
    out = []
    for name, X in (("linear", sm.add_constant(x)), ("quadratic", sm.add_constant(np.column_stack([x, x ** 2])))):
        try:
            m = sm.Logit(y, X).fit(disp=0)
            terms = ", ".join(f"{k}={v:+.3f} (se {s:.3f}, p={p:.2f})"
                              for k, v, s, p in zip(["const", "edge", "edge^2"], m.params, m.bse, m.pvalues))
            out.append(f"  {name:<10} {terms}")
        except Exception as exc:  # separation etc.
            out.append(f"  {name:<10} fit failed: {exc}")
    return "\n".join(out)


def window(rows: list[dict]) -> tuple[str, str, float, int, int]:
    """Contiguous bin range with the highest Wilson lower bound (ties -> wider)."""
    best = None
    for i in range(len(EDGE_BINS)):
        for j in range(i, len(EDGE_BINS)):
            lo_e, hi_e = EDGE_BINS[i][1], EDGE_BINS[j][2]
            sel = [r for r in rows if lo_e <= r["edge"] < hi_e]
            w, l = rec(sel)
            ends_populated = (any(EDGE_BINS[i][1] <= r["edge"] < EDGE_BINS[i][2] for r in rows)
                              and any(EDGE_BINS[j][1] <= r["edge"] < EDGE_BINS[j][2] for r in rows))
            if w + l < 10 or not ends_populated:   # never stretch a window across empty bins
                continue
            lb = wilson(w, w + l)[0]
            key = (round(lb, 4), j - i)
            if best is None or key > best[0]:
                best = (key, EDGE_BINS[i][0], EDGE_BINS[j][0], lb, w, l)
    return best[1:] if best else ("--", "--", float("nan"), 0, 0)


def load(season: int) -> list[dict]:
    res = IN_DIR / f"greenline_results_{season}.csv"
    rows = [r for r in csv.DictReader(res.open(encoding="utf-8"))
            if r["source"] == "pff" and r["market"] == "total" and r["side"] == "under"
            and r["value"] and float(r["value"]) > 0 and r["result"] != "push"]
    out = [{"game": r["game"], "week": r["week"], "edge": float(r["value"]), "win": 1 if r["result"] == "win" else 0}
           for r in rows]
    # Pinnacle shade at capture, joined on the game label
    shade = {}
    for p in IN_DIR.glob(f"greenline_vs_pinnacle_{season}_w*.csv"):
        for r in csv.DictReader(p.open(encoding="utf-8")):
            if r.get("proj") and r.get("pin_fair"):
                shade[r["game"].replace(" ", "")] = float(r["proj"]) - float(r["pin_fair"])
    for o in out:
        o["shade"] = shade.get(o["game"])
    return out


def report(rows: list[dict]) -> str:
    L = [f"PFF edge window, graded under flags n={len(rows)} (weeks {', '.join(sorted({r['week'] for r in rows}))})", "",
         "1. win rate by stated edge"]
    for lab, lo, hi in EDGE_BINS:
        L.append(line(lab, [r for r in rows if lo <= r["edge"] < hi]))
    L.append(line("all", rows))
    L += ["", "2. logistic fit, win ~ edge (edge in % points)", logit_fit(rows)]
    withs = [r for r in rows if r["shade"] is not None]
    if withs:
        L += ["", f"3. edge vs disagreement with Pinnacle (n={len(withs)} joined)"]
        L.append(f"  corr(edge, projection - Pinnacle fair) = {st.correlation([r['edge'] for r in withs], [r['shade'] for r in withs]):+.2f}"
                 " (more negative shade = PFF further below Pinnacle)")
        for lab, lo, hi in SHADE_BINS:
            L.append(line(f"shade {lab}", [r for r in withs if lo <= r["shade"] < hi]))
    lo_b, hi_b, lb, w, l = window(rows)
    L += ["", f"4. window: bins {lo_b} through {hi_b} -> {w}-{l}, floor {lb * 100:.1f}% "
              f"({'clears' if lb > BREAK_EVEN else 'does not clear'} 52.4%)"]
    inside = [r for r in rows if EDGE_BINS[[b[0] for b in EDGE_BINS].index(lo_b)][1] <= r["edge"]
              < EDGE_BINS[[b[0] for b in EDGE_BINS].index(hi_b)][2]] if w + l else []
    outside = [r for r in rows if r not in inside]
    L.append(line("  dropped", outside))
    L += ["", f"A window picked as the best of {sum(1 for i in range(len(EDGE_BINS)) for j in range(i, len(EDGE_BINS)))} "
              "contiguous ranges is the maximum of many noisy looks; its floor is optimistic by construction."]
    return "\n".join(L)


def self_check() -> None:
    rows = ([{"edge": 0.025, "win": 1}] * 8 + [{"edge": 0.025, "win": 0}] * 2 +
            [{"edge": 0.045, "win": 1}] * 2 + [{"edge": 0.045, "win": 0}] * 8)
    lo_b, hi_b, lb, w, l = window(rows)
    assert (lo_b, hi_b, w, l) == ("2-3%", "2-3%", 8, 2), (lo_b, hi_b, w, l)
    assert rec(rows) == (10, 10)
    print("self-check ok")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        self_check()
        return
    print(report(load(args.season)))


if __name__ == "__main__":
    main()
