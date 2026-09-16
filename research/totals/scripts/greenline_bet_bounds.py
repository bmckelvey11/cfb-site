"""Lower-bound bet test: which Greenline under splits clear break-even at the interval floor?

    python research/totals/scripts/greenline_bet_bounds.py
    python research/totals/scripts/greenline_bet_bounds.py --z 1.645      # 90% two-sided / 95% one-sided
    python research/totals/scripts/greenline_bet_bounds.py --self-check

Reads `greenline_results_<season>.csv` (from `greenline_season_review.py`: PFF flags
plus the personal 2023-25 unders, which were mostly the same flags as bet) and, for
each split, treats the Wilson LOWER bound of the win rate as the true probability.
That is the conservative bet test: a split is bettable only if it is still +EV when
the sample has been as lucky as the interval allows. For each split it reports the
EV per unit at -110 at that floor, the quarter-Kelly stake, and the worst price you
could pay and still break even at the floor. Point-estimate EV is shown beside it so
the cost of the conservatism is visible.

A split whose floor is below 52.4% is not "no edge"; it is "not proven". The gap
between the two is the sample size, and the MDE column says how many games the
split needs before a true 56% would clear.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cfb_paths import INGEST  # noqa: E402
from greenline_season_review import BREAK_EVEN, decimal, wilson  # noqa: E402
from greenline_unders import BANDS, band  # noqa: E402

IN_DIR = INGEST / "pff_scoreboard"
B110 = 100 / 110  # net win per unit at -110


def american(p: float) -> str:
    """The price at which win probability p is exactly break-even."""
    dec = 1 / p
    return f"+{(dec - 1) * 100:.0f}" if dec >= 2 else f"-{100 / (dec - 1):.0f}"


def kelly(p: float, b: float = B110) -> float:
    return max(0.0, (p * b - (1 - p)) / b)


def n_for(p_true: float, p0: float = BREAK_EVEN, z_lo: float = 1.96) -> int:
    """Games needed before the Wilson lower bound at a true win rate p_true clears p0 (approx)."""
    if p_true <= p0:
        return 0
    return math.ceil((z_lo ** 2) * p_true * (1 - p_true) / (p_true - p0) ** 2)


def bound_row(label: str, rows: list[dict], z: float) -> dict:
    w = sum(1 for r in rows if r["result"] == "win")
    l = sum(1 for r in rows if r["result"] == "loss")
    n = w + l
    if not n:
        return {"label": label, "n": 0}
    p = w / n
    lo, hi = wilson(w, n, z)
    return {"label": label, "n": n, "record": f"{w}-{l}", "p": p, "lo": lo, "hi": hi,
            "ev_lo": lo * B110 - (1 - lo), "ev_pt": p * B110 - (1 - p),
            "kelly_q_lo": kelly(lo) / 4, "worst_price": american(lo), "bettable": lo > BREAK_EVEN,
            "n_needed": n_for(0.56, z_lo=z)}


def splits(rows: list[dict]) -> list[tuple[str, list[dict]]]:
    U = [r for r in rows if r["market"] == "total" and r["side"] == "under"]
    pff = [r for r in U if r["source"] == "pff"]
    hist = [r for r in U if r["source"] == "personal"]
    out = [("all unders, history + flags", U), ("PFF flags only", pff), ("history only", hist)]
    for b in BANDS:
        out.append((f"band {b[0]}, pooled", [r for r in U if band(float(r["line"]))[0] == b[0]]))
    for lab, fn in (("PFF value 3-4%", lambda v: 0.03 <= v < 0.04), ("PFF value 4%+", lambda v: v >= 0.04)):
        out.append((lab, [r for r in pff if r["value"] and fn(float(r["value"]))]))
    return out


def report(rows: list[dict], z: float) -> str:
    conf = "95%" if abs(z - 1.96) < 0.01 else ("90%" if abs(z - 1.645) < 0.01 else f"z={z}")
    L = [f"lower-bound bet test, {conf} Wilson interval, -110 (break-even {BREAK_EVEN * 100:.1f}%)", "",
         f"{'split':<32} {'record':>8} {'win%':>6} {'floor':>6} {'EV@floor':>9} {'EV@point':>9} "
         f"{'1/4 Kelly':>9} {'worst price':>11}  bet?"]
    for s in rows:
        if not s["n"]:
            continue
        L.append(f"{s['label']:<32} {s['record']:>8} {s['p'] * 100:5.1f}% {s['lo'] * 100:5.1f}% "
                 f"{s['ev_lo'] * 100:+8.1f}% {s['ev_pt'] * 100:+8.1f}% {s['kelly_q_lo'] * 100:8.2f}% "
                 f"{s['worst_price']:>11}  {'YES' if s['bettable'] else 'no'}")
    L += ["", "floor = Wilson lower bound used as the true win rate; EV per 1u; 1/4 Kelly as % of bankroll at the floor;",
          "worst price = the juice at which the floor is exactly break-even (a lower number than this loses at the floor).",
          f"A true 56% needs about {n_for(0.56, z_lo=z)} games before its floor clears break-even at this confidence.",
          "Multiplicity: the band and value rows are 8 looks at one sample. A floor that clears on one of them is what",
          "8 looks at no edge produce about a third of the time; only a split chosen before its data counts as one test.",
          "The 2023-25 history both chose the 55-59.5 band and sits inside its pooled floor -- the clean test is 2026 only."]
    return "\n".join(L)


def edge_sweep(rows: list[dict], z: float) -> str:
    """Win rate of PFF under flags at or above each stated-edge cutoff: is there a floor worth using?"""
    U = [r for r in rows if r["source"] == "pff" and r["market"] == "total" and r["side"] == "under"
         and r["value"] and r["result"] != "push"]
    L = ["", f"PFF stated edge as a cutoff (2026 under flags, n={len(U)}):", "",
         f"{'min edge':>9} {'record':>8} {'win%':>6} {'floor':>6} {'EV@floor':>9}"]
    for t in (0.0, 0.02, 0.03, 0.035, 0.04, 0.05):
        s = [r for r in U if float(r["value"]) >= t]
        w = sum(r["result"] == "win" for r in s)
        if s:
            lo, _ = wilson(w, len(s), z)
            L.append(f"{t * 100:8.1f}% {w:>4}-{len(s) - w:<3} {w / len(s) * 100:5.1f}% {lo * 100:5.1f}% "
                     f"{(lo * B110 - (1 - lo)) * 100:+8.1f}%")
    xs = sorted(U, key=lambda r: float(r["value"]))
    h = len(xs) // 2
    lo_w = sum(r["result"] == "win" for r in xs[:h]); hi_w = sum(r["result"] == "win" for r in xs[h:])
    L.append(f"bottom half by edge {lo_w}-{h - lo_w}, top half {hi_w}-{len(xs) - h - hi_w}")
    return "\n".join(L)


def self_check() -> None:
    assert american(0.5238) == "-110" and american(0.5) == "+100" and american(0.4) == "+150"
    assert abs(kelly(0.5238)) < 0.001 and abs(kelly(0.60) - (0.6 * B110 - 0.4) / B110) < 1e-9
    rows = [dict(result="win")] * 62 + [dict(result="loss")] * 36
    s = bound_row("x", rows, 1.96)
    assert s["record"] == "62-36" and 0.53 < s["lo"] < 0.54 and s["bettable"], s
    s2 = bound_row("y", [dict(result="win")] * 22 + [dict(result="loss")] * 17, 1.96)
    assert not s2["bettable"] and s2["ev_lo"] < 0 < s2["ev_pt"], s2
    assert n_for(0.56) > n_for(0.60) > 0 and n_for(0.50) == 0
    print("self-check ok")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--z", type=float, default=1.96, help="1.96 = 95%% interval, 1.645 = 90%%")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        self_check()
        return
    src = IN_DIR / f"greenline_results_{args.season}.csv"
    if not src.exists():
        raise SystemExit(f"{src} not found -- run greenline_season_review.py first")
    rows = list(csv.DictReader(src.open(encoding="utf-8")))
    print(report([bound_row(lab, rs, args.z) for lab, rs in splits(rows)], args.z))
    print(edge_sweep(rows, args.z))


if __name__ == "__main__":
    main()
