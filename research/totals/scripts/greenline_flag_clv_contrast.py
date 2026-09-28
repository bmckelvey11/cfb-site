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

AMENDED 2026-09-28, committed before the rerun printed anything:

9. Close. The first run's close (`greenline_clv.usable_close`) let in GraphQL-only rows that
   carry in-game totals (greenline-findings row 14), so it is replaced by the median
   REST-backed book close with the span gate (`greenline_clv_all_eras.book_closes` /
   `consensus`). This is look 1 done on a valid close, not a second look.
10. Population. Fixed to weeks 2-3, the flags available when the plan was set; the graded
   file now holds later weeks, and adding them before ~596 flags would be a peek.
11. Coupling sensitivity (reported, not a third test). The PFF market line sits inside both
   `value` (projection vs that line) and CLV (that line vs the close), so a line that is
   noisy-high raises both even if PFF knows nothing. The decoupled y replaces the capture line
   with the median capture total across odds-api books other than DraftKings and FanDuel. A
   slope that survives on it is not the mechanical one.
12. Exploratory, outside the Holm family: the slope of that decoupled y on (best DK/FD total
   minus PFF projection), positive-edge unders, weeks 2-3 -- the price-rule quantity. Never
   against book-minus-close, which shares the book total and is mechanical.

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
from greenline_clv import clv_points, load_flags  # noqa: E402
from greenline_clv_all_eras import CAPTURE_SNAPSHOTS, book_closes, consensus  # noqa: E402
from match_greenline_books import OA_DIR, is_placeholder, latest_snapshot, match, slug_names  # noqa: E402
from under_filters import holm  # noqa: E402

GL_DIR = INGEST / "pff_scoreboard"
UNDER_LISTS = sorted(GL_DIR.glob("greenline_unders_2026_w*.csv"))
REGISTERED_WEEKS = ("2", "3")          # the flags that existed when the plan was fixed
RETAIL = ("DraftKings", "FanDuel")     # left out of the decoupled capture line
ET = dt.timezone(dt.timedelta(hours=-4))
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


def rest_scored(flags: list[dict]) -> tuple[list[dict], dict]:
    """CLV against the median REST-backed close, span gate (amendment 9)."""
    _, by_teams = book_closes((2026,))
    kept, why = [], {}
    for f in flags:
        close, reason = consensus(by_teams.get((2026, f["teams"])))
        why[reason] = why.get(reason, 0) + 1
        if close is not None:
            kept.append(dict(f, close=close, clv=clv_points(f["side"], f["line"], close)))
    return kept, why


def capture_consensus(weeks: tuple[str, ...]) -> dict[str, float]:
    """pff_game_id -> median capture total across odds-api books other than DK and FD."""
    sched = {s["pff_game_id"]: s for s in csv.DictReader((GL_DIR / "pff_schedule_2026.csv").open(encoding="utf-8"))}
    out = {}
    for wk in weeks:
        oa = latest_snapshot(OA_DIR / CAPTURE_SNAPSHOTS[wk])[0]
        for f in csv.DictReader((GL_DIR / f"pff_greenline_2026_w{wk}.csv").open(encoding="utf-8")):
            k = (f.get("kickoff_raw") or "")[:16]
            if not k:
                continue
            away, home = slug_names((sched.get(f["pff_game_id"]) or {}).get("matchup_path", ""))
            kick = dt.datetime.fromisoformat(k).replace(tzinfo=ET).astimezone(dt.timezone.utc)
            e = match(kick, away, home, oa, is_placeholder(k))
            pts = [t[0] for b, t in ((e or {}).get("totals") or {}).items() if b not in RETAIL]
            if len(pts) >= 2:
                out[f["pff_game_id"]] = st.median(pts)
    return out


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

def _fmt(label: str, s: dict, holm_p: bool = True) -> str:
    if not s.get("ok"):
        return f"| {label} | -- | -- | -- | -- | -- | -- |"
    n = s["n"] if "n" in s else f"{s['n_a']} vs {s['n_b']}"
    return (f"| {label} | {n} | {s['est']:+.3f} pts | {s['lo']:+.2f} to {s['hi']:+.2f} | {s['p']:.3f} | "
            + (f"{s['p_holm']:.3f}" if holm_p else "not in family") + f" | {s['mde']:.2f} |")


def render(res: dict, sizes: list[int], dec: dict, expl: dict) -> str:
    L = [f"# Under list and stated edge against CLV, {dt.date.today().isoformat()}", "",
         "Reproduce: `python research/totals/scripts/greenline_flag_clv_contrast.py "
         "--out research/totals/docs`.", "",
         "## Question", "",
         "Within the Greenline board, does the *published under list* or the *size of PFF's stated",
         "edge* predict closing-line value? These are the two variables that vary inside the board,",
         "which the flag dummy in [line movement](pff-line-movement-2026-09-22.md) did not.", "",
         "## The answer is a bound, not a result", "",
         f"- {res['n']} flags (weeks {', '.join(REGISTERED_WEEKS)}) with a REST-backed close. CLV SD "
         f"{res['sd']:.2f} points, mean {res['mean']:+.3f}.",
         f"- Smallest effect this n detects 80% of the time: **{res['list']['mde']:.2f} points** for the "
         f"list contrast, **{res['value']['mde']:.2f} points per SD** for the edge slope.",
         f"- A quarter-point effect — the size found on the close in the line-movement record — would "
         f"need **{res['required_n']} flags**, about twelve more weeks at this board's volume.",
         f"- Worse, the flags sit on **{len(sizes)} slate dates**, {max(sizes)} of them on one. So few",
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
    L += ["", "## Coupling sensitivity and the exploratory price-rule fit", "",
          "Same CLV sign, but measured from the median capture total of odds-api books other than",
          "DraftKings and FanDuel, so the PFF market line (x's reference) is not also y's. Reported,",
          "not tested; the exploratory row is outside the Holm family.", "",
          "| fit | n | estimate | 95% CI (iid) | p | Holm p | MDE |",
          "|---|---:|---:|---|---:|---:|---:|",
          _fmt("list contrast, decoupled y", dec["list"], holm_p=False),
          _fmt("CLV per SD of `value`, decoupled y", dec["value"], holm_p=False),
          _fmt("exploratory: per SD of best DK/FD total − PFF projection", expl, holm_p=False)]
    sig = [k for k, s in (("list", lst), ("value", val)) if s.get("ok") and s["p_holm"] < 0.05]
    L += ["", "## Reading", "",
          (f"- Surviving Holm: {', '.join(sig)}." if sig else
           "- Neither registered contrast survives Holm. **This is a bound on the question, not an "
           "answer to it**: an effect inside the MDE column could not have been seen."),
          f"- The bound rules out large effects: a list that moved the close by more than about "
          f"{lst.get('mde', float('nan')):.1f} points, or an edge slope above "
          f"{val.get('mde', float('nan')):.1f} points per SD, would have shown up.",
          f"- Point estimates: list {lst.get('est', float('nan')):+.2f}, edge slope "
          f"{val.get('est', float('nan')):+.2f} (coupled) vs {dec['value'].get('est', float('nan')):+.2f} "
          "(decoupled). A slope that shrinks on the decoupled y was partly the shared market line.",
          f"- **The next look is at ~{res['required_n']} scored flags** (the stop rule, recomputed on "
          "this close's SD). Nothing is to be read before it.", "",
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
    rows, why = rest_scored([f for f in load_flags() if f["week"] in REGISTERED_WEEKS])
    listed = on_under_list()
    cc = capture_consensus(REGISTERED_WEEKS)
    dec_rows = [dict(r, clv=clv_points(r["side"], cc[r["pff_game_id"]], r["close"]))
                for r in rows if r["pff_game_id"] in cc]
    dec = analyse(dec_rows, listed)
    # exploratory: the price-rule quantity against the decoupled y, positive-edge unders only
    from greenline_price_filter import build
    close_of = {r["pff_game_id"]: r["close"] for r in rows}
    pf = [r for r in build()[0] if r["week"] in REGISTERED_WEEKS and r["proj_gap"] is not None
          and r["game_id"] in close_of and r["game_id"] in cc]
    expl = slope([r["proj_gap"] for r in pf],
                 [clv_points("under", cc[r["game_id"]], close_of[r["game_id"]]) for r in pf])
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
    print(f"close gate: {why}; decoupled y on {len(dec_rows)}; exploratory on {len(pf)}")
    text = render(res, sizes, dec, expl)
    if a.out:
        p = a.out / f"greenline-flag-clv-contrast-{dt.date.today().isoformat()}.md"
        p.write_text(text, encoding="utf-8")
        print(f"wrote {p}")
    else:
        print(text)


if __name__ == "__main__":
    main()
