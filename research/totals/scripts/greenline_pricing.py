"""Reverse-engineer PFF Greenline's pricing layer from a captured week.

    python research/totals/scripts/greenline_pricing.py
    python research/totals/scripts/greenline_pricing.py --week 2 --splits
    python research/totals/scripts/greenline_pricing.py --self-check

Reads the CSVs `scripts/pull_pff_scoreboard.py` writes under
$CFB_DATA_ROOT/ingest/pff_scoreboard/ and recovers the arithmetic that turns a
Greenline projection into the numbers PFF shows: the value metric, the implied
scoring standard deviation, and the offset between projection and coin-flip.

WHAT IS DETERMINABLE, AND WHAT IS NOT. The pricing layer -- projection and line
in, cover probability and value out -- is a closed formula and this script
recovers it. The *projection* is not: it is the model's output, and a single
week of ~50 games cannot identify what feeds it. Everything below the
"projection drivers" heading is deliberately descriptive, not a fitted model.

The reported projection is rounded to 0.1, which bounds how tightly any fit can
be checked: an exact pricing law still leaves up to 0.05 points of disagreement
between the implied and the reported projection. Fits are therefore judged on
MAX deviation against that bound, not on mean squared error -- rounding error is
bounded and uniform, not Gaussian, so least squares attenuates slopes rather
than revealing them. Per-game sigma estimates divide by `z`, so games whose
cover probability sits near 0.5 are dropped from the sigma fit: at |z| < 0.10
rounding alone moves the estimate by more than half a point.
"""

from __future__ import annotations

import argparse
import csv
import statistics as st
import sys
from pathlib import Path
from statistics import NormalDist

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from cfb_paths import INGEST  # noqa: E402

N = NormalDist()
IN_DIR = INGEST / "pff_scoreboard"
ROUNDING_HALF_WIDTH = 0.05  # projections are published to 0.1
MIN_ABS_Z = 0.10            # below this, rounding dominates the sigma estimate
BREAK_EVEN_110 = 110 / 210


def num(v):
    return float(v) if v not in ("", None) else None


def corr(a: list[float], b: list[float]) -> float:
    ma, mb = st.mean(a), st.mean(b)
    den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / den if den else float("nan")


def ols(xs: list[float], ys: list[float]) -> tuple[float, float, float, float]:
    """Returns intercept, slope, R^2, residual sd."""
    mx, my = st.mean(xs), st.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    res = [y - (a + b * x) for x, y in zip(xs, ys)]
    ss_t = sum((y - my) ** 2 for y in ys)
    return a, b, 1 - sum(e * e for e in res) / ss_t, st.pstdev(res)


def value_formula(rows: list[dict]) -> dict:
    """`best_value` should be the cover probability less a fixed break-even."""
    gaps = []
    for x in rows:
        side = x["total_best_side"]
        p = num(x["over_cover_probability"] if side == "over" else x["under_cover_probability"])
        bv = num(x["total_best_value"])
        if p is not None and bv is not None:
            gaps.append(p - bv)
    return {"n": len(gaps), "mean": st.mean(gaps), "sd": st.pstdev(gaps)}


def sigma_law(rows: list[dict]) -> dict:
    """Per-game implied sigma, then sigma as a function of the total line."""
    pts = []
    for x in rows:
        line, proj, po = (num(x["market_over_under"]), num(x["greenline_total_projection"]),
                          num(x["over_cover_probability"]))
        if None in (line, proj, po) or not 0 < po < 1:
            continue
        z = N.inv_cdf(po)
        if abs(z) < MIN_ABS_Z:
            continue
        pts.append((line, (proj - line) / z))
    if len(pts) < 3:
        return {"n": len(pts)}
    lines = [p[0] for p in pts]
    sigmas = [p[1] for p in pts]
    a, b, r2, sd = ols(lines, sigmas)
    return {"n": len(pts), "a": a, "b": b, "r2": r2, "resid_sd": sd,
            "corr_line": corr(lines, sigmas),
            "corr_absz": corr([abs(N.inv_cdf(num(x["over_cover_probability"]))) for x in rows
                               if num(x["over_cover_probability"])
                               and 0 < num(x["over_cover_probability"]) < 1
                               and abs(N.inv_cdf(num(x["over_cover_probability"]))) >= MIN_ABS_Z],
                              sigmas),
            "mean": st.mean(sigmas), "median": st.median(sigmas),
            "min": min(sigmas), "max": max(sigmas)}


def skew(rows: list[dict]) -> dict:
    """Split the implied sigma by which side of the line the projection falls on.

    A symmetric distribution prices a 1.7-point disagreement the same in either
    direction. Greenline does not, so the fitted sigma has to nearly double on the
    over side to absorb it -- the signature of a right-skewed total, which is what
    football scoring actually is: a floor at zero and a long high-scoring tail.
    """
    below, above = [], []
    for x in rows:
        line, proj, po = (num(x["market_over_under"]), num(x["greenline_total_projection"]),
                          num(x["over_cover_probability"]))
        if None in (line, proj, po) or not 0 < po < 1:
            continue
        d = proj - line
        if abs(d) < 1e-9:
            continue
        (below if d < 0 else above).append((line, d, po, N.inv_cdf(po)))

    def side(grp):
        if not grp:
            return None
        return {"n": len(grp),
                "abs_d": st.mean([abs(g[1]) for g in grp]),
                "abs_z": st.mean([abs(g[3]) for g in grp]),
                "sigma": st.mean([abs(g[1] / g[3]) for g in grp if abs(g[3]) > 1e-9]),
                "z_per_pt": st.mean([abs(g[3]) for g in grp]) / st.mean([abs(g[1]) for g in grp])}

    b, a = side(below), side(above)
    out = {"below": b, "above": a}
    if b and a and a["z_per_pt"]:
        out["ratio"] = b["z_per_pt"] / a["z_per_pt"]
    # Controlled comparison: same |d|, similar line, opposite direction.
    pairs = []
    for u in below:
        for o in above:
            if abs(abs(u[1]) - abs(o[1])) < 0.05 and abs(u[0] - o[0]) < 2.0:
                pairs.append({"abs_d": abs(u[1]), "under_line": u[0], "under_p": 1 - u[2],
                              "over_line": o[0], "over_p": o[2]})
    out["pairs"] = pairs
    return out


def reproduce(rows: list[dict], a: float, b: float, offset: float) -> float:
    """Max points by which sigma = a + b*line fails to rebuild the projection."""
    worst = 0.0
    for x in rows:
        line, proj, po = (num(x["market_over_under"]), num(x["greenline_total_projection"]),
                          num(x["over_cover_probability"]))
        if None in (line, proj, po) or not 0 < po < 1:
            continue
        implied = N.inv_cdf(po) * (a + b * line) + offset
        worst = max(worst, abs(implied - (proj - line)))
    return worst


def lean(rows: list[dict]) -> dict:
    """How far the projection sits from the market, and which side gets flagged."""
    d = [num(x["greenline_total_projection"]) - num(x["market_over_under"]) for x in rows
         if num(x["greenline_total_projection"]) is not None
         and num(x["market_over_under"]) is not None]
    sides = [x["total_best_side"] for x in rows if x["total_best_side"]]
    flags = [x["total_value_label"] for x in rows if x["total_value_label"]]
    return {"n": len(d), "mean": st.mean(d), "median": st.median(d), "sd": st.pstdev(d),
            "below": sum(1 for v in d if v < 0), "above": sum(1 for v in d if v > 0),
            "side_under": sides.count("under"), "side_over": sides.count("over"),
            "flag_under": flags.count("under"), "flag_over": flags.count("over")}


def public_join(rows: list[dict], splits: list[dict]) -> dict:
    """Is Greenline just fading the public? Join the ticket split by game."""
    by_id = {x["pff_game_id"]: x for x in rows}
    pub, glp, agree = [], [], 0
    for s in splits:
        if s["prop_type"] != "game_point_total":
            continue
        g = by_id.get(s["pff_game_id"])
        if not g:
            continue
        ot, po = num(s["over_tickets"]), num(g["over_cover_probability"])
        if ot is None or po is None:
            continue
        pub.append(ot)
        glp.append(po)
        if g["total_best_side"] == ("over" if ot > 50 else "under"):
            agree += 1
    if len(pub) < 3:
        return {"n": len(pub)}
    return {"n": len(pub), "corr": corr(pub, glp), "agree": agree,
            "public_over_pct_mean": st.mean(pub), "public_over_pct_median": st.median(pub)}


def report(rows: list[dict], splits: list[dict] | None) -> None:
    print(f"games with Greenline props: {len(rows)}\n")

    v = value_formula(rows)
    print("VALUE METRIC")
    print(f"  best_value = cover_probability - {v['mean']:.6f}   (sd {v['sd']:.2e}, n={v['n']})")
    print(f"  break-even at -110 is 110/210 = {BREAK_EVEN_110:.6f}")
    exact = abs(v["mean"] - BREAK_EVEN_110) < 1e-4
    print(f"  -> {'exact match' if exact else 'DOES NOT match -110 break-even'}\n")

    s = sigma_law(rows)
    print("IMPLIED SCORING SIGMA")
    if s["n"] < 3:
        print(f"  only {s['n']} usable games; need more capture\n")
    else:
        print(f"  per-game sigma: mean={s['mean']:.2f} median={s['median']:.2f} "
              f"range {s['min']:.2f}..{s['max']:.2f}  (n={s['n']})")
        print(f"  sigma = {s['a']:+.2f} + {s['b']:.4f} * line   "
              f"R2={s['r2']:.3f}  resid_sd={s['resid_sd']:.2f} pts")
        print(f"  corr(sigma, line) = {s['corr_line']:+.3f}   "
              f"corr(sigma, |z|) = {s['corr_absz']:+.3f} <- near zero means not a rounding artifact")
        for L in (45, 50, 55, 60, 65):
            print(f"     line {L}: sigma = {s['a'] + s['b'] * L:5.2f}")
        worst = reproduce(rows, s["a"], s["b"], 0.0)
        print(f"  rebuilding the projection from (p, line): max error {worst:.3f} pts "
              f"vs {ROUNDING_HALF_WIDTH} rounding bound")
        print(f"  -> {'law is complete' if worst <= ROUNDING_HALF_WIDTH + 1e-9 else 'a per-game input remains beyond the line'}\n")

    k = skew(rows)
    print("SHAPE OF THE MODELLED TOTAL")
    if not (k["below"] and k["above"]):
        print("  need games on both sides of the line\n")
    else:
        for lab, side in (("projection BELOW line (under)", k["below"]),
                          ("projection ABOVE line (over) ", k["above"])):
            print(f"  {lab}: n={side['n']:2d}  mean |d|={side['abs_d']:.2f} pts  "
                  f"fitted sigma={side['sigma']:6.2f}  edge={side['z_per_pt']:.4f} z/pt")
        print(f"  -> an under is worth {k['ratio']:.2f}x the probability of an over of the same size")
        print("     A symmetric distribution would give 1.00x. The gap is right-skew:")
        print("     scoring has a floor at zero and a long high-scoring tail, so mass")
        print("     below the projection is dense and mass above it is spread thin.")
        for pr in k["pairs"][:3]:
            print(f"     matched |d|={pr['abs_d']:.1f}: under p={pr['under_p']:.4f} "
                  f"(line {pr['under_line']:.1f})  vs  over p={pr['over_p']:.4f} (line {pr['over_line']:.1f})")
        print()

    L = lean(rows)
    print("WHERE THE PROJECTION SITS vs THE MARKET")
    print(f"  proj - market: mean={L['mean']:+.2f} median={L['median']:+.2f} sd={L['sd']:.2f} (n={L['n']})")
    print(f"  below the market line: {L['below']}    above: {L['above']}")
    print(f"  best side  under/over: {L['side_under']}/{L['side_over']}")
    print(f"  flagged    under/over: {L['flag_under']}/{L['flag_over']}\n")

    if splits:
        p = public_join(rows, splits)
        print("IS IT FADING THE PUBLIC?")
        if p["n"] < 3:
            print(f"  only {p['n']} games joined\n")
        else:
            print(f"  n={p['n']}  corr(public over-ticket%, Greenline p_over) = {p['corr']:+.3f}")
            print(f"  agrees with the public side: {p['agree']}/{p['n']} ({p['agree']/p['n']*100:.0f}%)")
            print(f"  public over-ticket%: mean={p['public_over_pct_mean']:.1f} "
                  f"median={p['public_over_pct_median']:.1f}")
            print("  NOTE: splits and Greenline are separate captures; a weak correlation")
            print("        cannot be told apart from a stale join unless they were pulled together.\n")


def self_check() -> None:
    """Synthesise a week from a known law and confirm the script recovers it."""
    true_a, true_b, sigma_of = -4.0, 0.27, lambda line: -4.0 + 0.27 * line
    rows = []
    for i, (line, proj) in enumerate([(45.5, 43.9), (50.5, 49.0), (54.5, 55.9), (60.5, 58.4),
                                      (47.5, 45.7), (52.5, 51.6), (66.5, 64.6), (43.5, 42.4)]):
        po = N.cdf((proj - line) / sigma_of(line))
        side = "over" if po > 0.5 else "under"
        p = po if side == "over" else 1 - po
        rows.append({
            "pff_game_id": str(9000 + i),
            "market_over_under": str(line), "greenline_total_projection": str(proj),
            "over_cover_probability": f"{po:.10f}", "under_cover_probability": f"{1-po:.10f}",
            "total_best_side": side, "total_value_label": side,
            "total_best_value": f"{p - BREAK_EVEN_110:.10f}",
        })

    v = value_formula(rows)
    assert abs(v["mean"] - BREAK_EVEN_110) < 1e-6, v

    s = sigma_law(rows)
    assert abs(s["a"] - true_a) < 0.05 and abs(s["b"] - true_b) < 0.002, s
    assert s["r2"] > 0.999, s
    # Unrounded inputs: the law must rebuild the projection essentially exactly.
    assert reproduce(rows, s["a"], s["b"], 0.0) < 1e-6

    L = lean(rows)
    assert L["below"] + L["above"] == len(rows)
    assert L["side_under"] + L["side_over"] == len(rows)

    # A near-coin-flip game must be excluded from the sigma fit, not divided by ~0.
    flat = dict(rows[0], market_over_under="50.0", greenline_total_projection="50.0",
                over_cover_probability="0.5", under_cover_probability="0.5")
    assert sigma_law(rows + [flat])["n"] == s["n"]

    assert public_join(rows, [])["n"] == 0

    # Symmetric synthetic data must price both directions alike: ratio ~ 1.00.
    k = skew(rows)
    assert k["below"] and k["above"], k
    assert abs(k["ratio"] - 1.0) < 0.25, k["ratio"]
    # A projection sitting exactly on the line is neither side and must be dropped.
    flat = dict(rows[0], market_over_under="50.0", greenline_total_projection="50.0",
                over_cover_probability="0.5", under_cover_probability="0.5")
    k2 = skew(rows + [flat])
    assert k2["below"]["n"] + k2["above"]["n"] == k["below"]["n"] + k["above"]["n"]
    print("self-check ok")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--week", default="2")
    ap.add_argument("--splits", action="store_true", help="also join the public betting split")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()

    if args.self_check:
        self_check()
        return

    path = IN_DIR / f"pff_greenline_{args.season}_w{args.week}.csv"
    if not path.exists():
        raise SystemExit(f"{path} not found -- capture it with scripts/pull_pff_scoreboard.py --greenline")
    rows = list(csv.DictReader(path.open(encoding="utf-8")))

    splits = None
    if args.splits:
        sp = IN_DIR / f"pff_bet_split_{args.season}.csv"
        if not sp.exists():
            raise SystemExit(f"{sp} not found -- run scripts/pull_pff_scoreboard.py first")
        splits = list(csv.DictReader(sp.open(encoding="utf-8")))

    print(f"=== PFF Greenline pricing, {args.season} week {args.week} ===\n")
    report(rows, splits)


if __name__ == "__main__":
    main()
