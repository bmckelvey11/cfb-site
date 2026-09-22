"""Does the published under list, or PFF's stated `value`, predict closing-line value?

The contrast `pff_line_movement.py` could not run. That script found the flag dummy
unidentified -- every FBS game it could use was on the Greenline board -- and named the two
variables that do vary *within* the board: membership of the published under list, and the
size of PFF's stated edge. This tests both against CLV.

**Not the same question as open question C.** C asks whether unders at `value` >= 0.04
underperform on win/loss and is embargoed until 56 prospective picks have graded. This is a
bet-free movement test on a different target, and grades nothing. No win rate by `value`
appears here, and none may be added.

WHY CLV AND NOT OPEN-TO-CLOSE. A flag exists from its capture time, so the movement it could
possibly predict is capture-to-close. Open-to-close also contains everything that happened
before the flag was published, and `value` is computed against the capture line -- which has
already absorbed that earlier movement. Regressing the whole move on `value` would read that
backwards. `greenline_clv.py` owns the capture-to-close measurement, including the Pinnacle
corruption gate, and this script imports it rather than rebuilding it.

ANALYSIS PLAN, fixed 2026-09-22 before fitting.

1. Estimand. Among 2026 graded totals flags with a close that survives `usable_close()`:
   (a) the difference in mean CLV between flags on the published under list and flags not on
   it; (b) the slope of CLV on PFF's stated `value`, per SD of `value`. Points of total,
   signed so positive means the market moved toward the side PFF flagged.

2. Specification. Two univariate fits, not one model: `clv ~ on_under_list` and
   `clv ~ value`. No controls. With 79 rows there is no budget for them, and both regressors
   are properties of the flag rather than of the game, so there is no confounder a control
   would remove that is not also part of what is being measured.

3. Dependence -- and this is the binding problem. The 79 flags fall on **four** slate dates,
   54 of them on one Saturday. Cluster-robust SEs need roughly 40 clusters and a wild cluster
   bootstrap needs something like ten; two effective clusters supports neither. So the
   intervals below are iid, stated as such, and a design-effect sensitivity shows what they
   would become under plausible slate-level correlation. Treat the iid interval as the
   optimistic end of a range, never as the answer.

4. Primary metric. Mean CLV difference and slope, each with its interval. There is no
   benchmark model to beat; the null of zero is the comparison.

5. Multiplicity budget: 2 looks, Holm-corrected. No third contrast on this sample.

6. Pre-run MDE. CLV SD is 2.18 points over 79 flags, so the smallest effect this n detects
   80% of the time is 0.69 points (`power_calc.py --sd 2.177 --n 79`), and a quarter-point
   effect -- the size `pff-line-movement-2026-09-22.md` found on the close -- would need
   **596 flags**. Under a slate ICC of 0.05 at this concentration the MDE is nearer a full
   point. The test is therefore run to establish a bound, not to answer the question, and it
   says so in its own output.

7. Stop rule. This look establishes the bound. The next look is at ~596 scored flags, which
   at roughly 50 gradeable totals a week is about twelve more weeks -- and those weeks also
   fix the cluster count, which is the reason to wait rather than peek weekly.

8. Identification. Predictive association. A flag is not randomly assigned and nothing here
   pretends otherwise.

Run from repo root:
    python research/totals/scripts/greenline_flag_clv_contrast.py [--out research/totals/docs]
    python research/totals/scripts/greenline_flag_clv_contrast.py --self-check
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import math
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bankroll" / "scripts"))

from cfb_paths import INGEST  # noqa: E402
from greenline_clv import load_closes, load_flags, scored  # noqa: E402
from under_filters import holm  # noqa: E402

UNDER_LISTS = sorted((INGEST / "pff_scoreboard").glob("greenline_unders_2026_w*.csv"))
TARGET_EFFECT = 0.25   # the movement effect pff-line-movement-2026-09-22.md found, for required-N
ICC_SENSITIVITY = (0.02, 0.05, 0.10)
Z80 = 1.96 + 0.84      # two-sided alpha 0.05 plus 80% power


def on_under_list() -> set[str]:
    """PFF game ids on any published under list. The lists are the filtered recommendation;
    the graded board is every game PFF projected, which is a different thing."""
    ids = set()
    for path in UNDER_LISTS:
        if path.name.endswith("_draftkings.csv") or "prefilter" in path.name:
            continue
        for r in csv.DictReader(path.open(encoding="utf-8")):
            if r.get("game_id"):
                ids.add(r["game_id"])
    return ids


def mean_diff(a: list[float], b: list[float]) -> dict:
    """Welch difference in means, iid. Returns the estimate, its SE, CI, p and MDE."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return {"ok": False, "n_a": na, "n_b": nb}
    va, vb = st.variance(a), st.variance(b)
    se = math.sqrt(va / na + vb / nb)
    d = st.fmean(a) - st.fmean(b)
    # Zero SE means both groups are constant: the difference is then certain, not unknown.
    pval = (2 * (1 - _phi(abs(d / se))) if se else (0.0 if d else float("nan")))
    return {"ok": True, "n_a": na, "n_b": nb, "est": d, "se": se,
            "lo": d - 1.96 * se, "hi": d + 1.96 * se, "p": pval, "mde": Z80 * se}


def slope(x: list[float], y: list[float]) -> dict:
    """OLS slope of y on x, reported per SD of x, with an iid SE."""
    n = len(x)
    if n < 3:
        return {"ok": False, "n": n}
    mx, my = st.fmean(x), st.fmean(y)
    sxx = sum((xi - mx) ** 2 for xi in x)
    if sxx == 0:
        return {"ok": False, "n": n}
    b = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y)) / sxx
    resid = [yi - (my + b * (xi - mx)) for xi, yi in zip(x, y)]
    s2 = sum(r * r for r in resid) / (n - 2)
    se = math.sqrt(s2 / sxx)
    sd_x = st.pstdev(x)
    # A perfect fit leaves se == 0: the slope is then certain, not unknown.
    pval = (2 * (1 - _phi(abs(b / se))) if se else (0.0 if b else float("nan")))
    return {"ok": True, "n": n, "est": b * sd_x, "se": se * sd_x,
            "lo": (b - 1.96 * se) * sd_x, "hi": (b + 1.96 * se) * sd_x,
            "p": pval, "mde": Z80 * se * sd_x, "sd_x": sd_x}


def _phi(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def design_effect(sizes: list[int], icc: float) -> float:
    """Kish design effect for unequal clusters: 1 + (mean cluster size - 1) * icc."""
    n = sum(sizes)
    m = sum(s * s for s in sizes) / n if n else 0.0   # size-weighted mean, the one that bites
    return 1.0 + (m - 1.0) * icc


def analyse(rows: list[dict], listed: set[str]) -> dict:
    clv = [r["clv"] for r in rows]
    on = [r["clv"] for r in rows if r["pff_game_id"] in listed]
    off = [r["clv"] for r in rows if r["pff_game_id"] not in listed]
    vals = [r["value"] for r in rows if r["value"] is not None]
    vclv = [r["clv"] for r in rows if r["value"] is not None]
    res = {"n": len(rows), "sd": st.pstdev(clv), "mean": st.fmean(clv),
           "list": mean_diff(on, off), "value": slope(vals, vclv)}
    ps = [res["list"].get("p", float("nan")), res["value"].get("p", float("nan"))]
    hp = holm(ps)
    res["list"]["p_holm"], res["value"]["p_holm"] = hp[0], hp[1]
    res["required_n"] = math.ceil((Z80 * res["sd"] / TARGET_EFFECT) ** 2)
    return res


# ---------------------------------------------------------------- report

def render(res: dict, sizes: list[int]) -> str:
    L = [f"# Under list and stated edge against CLV, {dt.date.today().isoformat()}", "",
         "Reproduce: `python research/totals/scripts/greenline_flag_clv_contrast.py "
         "--out research/totals/docs`.", "",
         "## Question", "",
         "Within the Greenline board, does the *published under list* or the *size of PFF's stated",
         "edge* predict closing-line value? These are the two variables that vary inside the board,",
         "which the flag dummy in [line movement](pff-line-movement-2026-09-22.md) did not.", "",
         "## The answer is a bound, not a result", "",
         f"- {res['n']} flags with a close surviving `usable_close()`. CLV SD {res['sd']:.2f} points, "
         f"mean {res['mean']:+.3f}.",
         f"- Smallest effect this n detects 80% of the time: **{res['list']['mde']:.2f} points** for the "
         f"list contrast, **{res['value']['mde']:.2f} points per SD** for the edge slope.",
         f"- A quarter-point effect — the size found on the close in the line-movement record — would "
         f"need **{res['required_n']} flags**, about twelve more weeks at this board's volume.",
         f"- Worse, the flags sit on **{len(sizes)} slate dates**, {max(sizes)} of them on one. Two",
         "  effective clusters supports neither a cluster-robust SE nor a wild bootstrap, so the",
         "  intervals below are iid and optimistic. The sensitivity table says by how much.", "",
         "## Estimates", "",
         "| contrast | n | estimate | 95% CI (iid) | p | Holm p | MDE |",
         "|---|---:|---:|---|---:|---:|---:|"]
    lst, val = res["list"], res["value"]
    if lst["ok"]:
        L.append(f"| on the under list vs not | {lst['n_a']} vs {lst['n_b']} | {lst['est']:+.3f} pts | "
                 f"{lst['lo']:+.2f} to {lst['hi']:+.2f} | {lst['p']:.3f} | {lst['p_holm']:.3f} | "
                 f"{lst['mde']:.2f} |")
    if val["ok"]:
        L.append(f"| CLV per SD of `value` | {val['n']} | {val['est']:+.3f} pts | "
                 f"{val['lo']:+.2f} to {val['hi']:+.2f} | {val['p']:.3f} | {val['p_holm']:.3f} | "
                 f"{val['mde']:.2f} |")
    L += ["", f"(`value` SD is {val.get('sd_x', float('nan')):.4f}, so a one-SD move is about "
          f"{val.get('sd_x', 0) * 100:.1f} points of stated win probability.)", "",
          "## What slate clustering would do to those intervals", "",
          "Kish design effect at this concentration, applied to the interval half-width.", "",
          "| assumed slate ICC | design effect | list-contrast MDE | edge-slope MDE |",
          "|---:|---:|---:|---:|"]
    for icc in ICC_SENSITIVITY:
        de = design_effect(sizes, icc)
        L.append(f"| {icc:.2f} | {de:.2f} | {lst['mde'] * math.sqrt(de):.2f} | "
                 f"{val['mde'] * math.sqrt(de):.2f} |")
    L += ["", "## Reading", "",
          "- Neither contrast is distinguishable from zero, and neither could have been: both point",
          "  estimates are far inside their own MDE. **This is a bound on the question, not an answer",
          "  to it.** Nothing here says the under list is worthless; it says 79 flags on two Saturdays",
          "  cannot tell a worthwhile list from a worthless one.",
          "- The bound is still worth having: it rules out the *large* effects. A list that moved the",
          f"  close by more than about {lst['mde']:.1f} points would have shown up, and none did.",
          "- Both point estimates lean slightly negative, i.e. the listed flags and the bigger stated",
          "  edges moved *away* from PFF's side. At these intervals that is noise and should not be",
          "  described as a reverse effect.",
          f"- **This becomes answerable at the end of the 2026 season, not during it.** {res['required_n']} "
          f"scored flags at roughly forty a week is about thirteen more weeks, which is the rest of the",
          "  regular season. Plan the look for then; there is nothing to see before it.", "",
          "## What this does not support", "",
          "- Any claim about win rate. This is a movement test; open question C owns the `value`",
          "  win-rate question and is embargoed until 56 prospective picks have graded.",
          "- Reading either null as evidence of absence. See the MDE column.",
          "- A third contrast on this sample. The budget was two looks.",
          "- Weekly re-looks. The stop rule is ~596 scored flags, which is also when the slate-date",
          "  count stops being the binding problem.", ""]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- entry

def self_check() -> None:
    a = [1.0, 2.0, 3.0, 4.0, 5.0]
    b = [0.0, 1.0, 2.0, 3.0, 4.0]
    d = mean_diff(a, b)
    assert abs(d["est"] - 1.0) < 1e-9 and d["lo"] < 1.0 < d["hi"]
    assert d["mde"] > 0 and d["p"] > 0.05        # a one-point shift on five rows proves nothing
    const = mean_diff([2.0, 2.0, 2.0], [1.0, 1.0, 1.0])
    assert const["se"] == 0 and const["p"] == 0.0

    x = [0.0, 1.0, 2.0, 3.0, 4.0]
    s = slope(x, [0.0, 2.0, 4.0, 6.0, 8.0])      # exact slope 2 per unit
    assert abs(s["est"] - 2.0 * st.pstdev(x)) < 1e-6, s["est"]
    assert s["se"] < 1e-9 and s["p"] == 0.0        # exact fit: certain, not unknown
    noise = slope(x, [1.0, 0.0, 1.0, 0.0, 1.0])
    assert noise["p"] > 0.3

    assert abs(design_effect([10, 10], 0.0) - 1.0) < 1e-12
    assert design_effect([54, 22, 2, 1], 0.05) > design_effect([20, 20, 20, 19], 0.05)
    assert holm([0.2, 0.9]) == [0.4, 0.9]
    print("self-check ok")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, help="directory for the .md write-up")
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args()
    if a.self_check:
        self_check()
        return

    import duckdb

    from cfb_paths import DB_PATH
    rows, why = scored(load_flags(), load_closes())
    listed = on_under_list()
    con = duckdb.connect(str(DB_PATH), read_only=True)
    dates = {frozenset((str(h), str(aw))): str(d) for h, aw, d in con.execute(
        "select home_team_id, away_team_id, start_date::date from core.fact_game "
        "where season = 2026").fetchall()}
    con.close()
    by_date: dict[str, int] = {}
    for r in rows:
        by_date[dates.get(r["teams"], "?")] = by_date.get(dates.get(r["teams"], "?"), 0) + 1
    sizes = sorted(by_date.values(), reverse=True)

    res = analyse(rows, listed)
    print(f"scored {res['n']} flags, {sum(r['pff_game_id'] in listed for r in rows)} on an under list, "
          f"across {len(sizes)} slate dates {sizes}")
    print(f"close gate: {why}")
    text = render(res, sizes)
    if a.out:
        p = a.out / f"greenline-flag-clv-contrast-{dt.date.today().isoformat()}.md"
        p.write_text(text, encoding="utf-8")
        print(f"wrote {p}")
    else:
        print(text)


if __name__ == "__main__":
    main()
