"""How much edge does PFF's total projection carry over the market line?

    python research/totals/scripts/pff_projection_skill.py
    python research/totals/scripts/pff_projection_skill.py --out research/totals/docs/x.md
    python research/totals/scripts/pff_projection_skill.py --self-check

REGISTERED 2026-09-28, committed before any output was printed.

Names: the PFF projection is `greenline_total_projection` (2026) / `greenline_line` (2020
archive), PFF's own forecast of the total. The market line is the total PFF displayed beside
it at the same moment -- `market_over_under` in 2026, `market_line` in the archive.

Question: does the projection know something the line does not, and if so how much? Two
different quantities, never mixed:

  level   mean(projection - line) against mean(actual - line). Does the average game land
          below the line by as much as PFF shades it? A systematic under-shade that games do
          not follow is bias, not information.
  slope   b in (actual - line) = a + b * (projection - line), with an intercept, SEs
          clustered by game date. b is the share of PFF's disagreement that turns out real:
          0 = the projection adds nothing to the line, 1 = PFF was fully right. The
          actionable number is b's UPPER 95% bound, converted to the most points (and, at
          4 pp per point, the most win probability) per game the projection can be worth.

Data, one row per game:

  2020  greenline_history_archive.csv, PFF_hist.xlsx totals, `open_greenline` snapshot only
        (the close snapshot's projection was updated after the market moved and was not
        available at decision time). The archive is two-sided -- every game once per side --
        so rows are deduplicated by game_id; pooling both sides would double n.
  2026  greenline_graded.csv: every Greenline totals flag (PFF flags every FBS game), at the
        capture's market line. Level and MAE use weeks 2-4. The SLOPE and the proper score
        use weeks 2-3 only: a fit on the size of PFF's disagreement is the continuous form of
        a win/loss-by-`value` split, and week 4 onward is open question C's embargo window.
        Re-fit with week 4+ only after C is read.

Also reported: MAE of projection vs line (paired, date-clustered); hit rate betting the
projection's side of the line (sign(projection - line), pushes and ties out); Brier and log
loss of PFF's under probability at the line (`match_greenline_books.p_under`) against 0.5,
the de-vigged probability of a two-sided -110 market at its own line. Eras are tested for
heterogeneity on level and slope before any pooled number is read.

Expected answer, stated before running: a BOUND, not a measurement. With (actual - line)
SD ~13.5 and (projection - line) SD ~1, the SE on b is ~13.5 / (1 * sqrt(n)), about 0.6 at
n ~ 500, so the 95% interval on b spans ~2.4 -- it cannot tell b = 0 from b = 1. Already on
record and cited, not re-derived: 2026 calibration (stated 55.0% vs actual 51.8%, Brier
0.2498 vs 0.2500, greenline_season_review.py) and the pooled betting record
(pool_totals_record.py).
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics as st
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cfb_paths import INGEST  # noqa: E402
from greenline_clv_all_eras import stats  # noqa: E402
from greenline_season_review import wilson  # noqa: E402
from match_greenline_books import p_under  # noqa: E402

GL_DIR = INGEST / "pff_scoreboard"
PP_PER_POINT = 0.04          # win probability per point of total near the line
SLOPE_WEEKS_2026 = ("2", "3")  # week 4+ is open question C's embargo


def load_2020() -> tuple[list[dict], int]:
    seen, rows, dropped = set(), [], 0
    for r in csv.DictReader((GL_DIR / "greenline_history_archive.csv").open(encoding="utf-8")):
        if r["market"] != "total" or r["source_file"] != "PFF_hist.xlsx" or r["snapshot"] != "open_greenline":
            continue
        gid = r["game_id"]
        if gid in seen:                      # two-sided: one row per side, same numbers
            continue
        seen.add(gid)
        try:
            line, proj = float(r["market_line"]), float(r["greenline_line"])
            actual = float(r["home_points"]) + float(r["away_points"])
        except ValueError:
            dropped += 1
            continue
        rows.append({"era": "2020", "game_id": gid, "week": str(int(float(r["week"]))), "date": r["kickoff_utc"][:10],
                     "line": line, "proj": proj, "actual": actual})
    return rows, dropped


def load_2026() -> tuple[list[dict], int]:
    dates = {}
    for p in GL_DIR.glob("pff_greenline_2026_w*.csv"):
        if not p.stem.rsplit("_w", 1)[1].isdigit():
            continue
        for f in csv.DictReader(p.open(encoding="utf-8")):
            dates[(f.get("pff_week"), f["pff_game_id"])] = (f.get("kickoff_raw") or "")[:10]
    rows, dropped = [], 0
    for r in csv.DictReader((GL_DIR / "greenline_graded.csv").open(encoding="utf-8")):
        try:
            line, proj, actual = float(r["line"]), float(r["projection"]), float(r["actual_total"])
        except ValueError:
            dropped += 1
            continue
        rows.append({"era": "2026", "week": r["pff_week"], "date": dates.get((r["pff_week"], r["pff_game_id"]), "?"),
                     "line": line, "proj": proj, "actual": actual})
    return rows, dropped


def ols_clustered(x: list[float], y: list[float], groups: list[str]) -> dict:
    """y = a + b x, CR1 cluster-robust SEs by group."""
    X = np.column_stack([np.ones(len(x)), np.asarray(x, float)])
    Y = np.asarray(y, float)
    xtx_inv = np.linalg.inv(X.T @ X)
    beta = xtx_inv @ X.T @ Y
    e = Y - X @ beta
    meat = np.zeros((2, 2))
    gs = sorted(set(groups))
    for g in gs:
        idx = [i for i, gi in enumerate(groups) if gi == g]
        s = X[idx].T @ e[idx]
        meat += np.outer(s, s)
    n, k, G = len(Y), 2, len(gs)
    V = xtx_inv @ meat @ xtx_inv * (G / (G - 1)) * ((n - 1) / (n - k))
    iid = xtx_inv * (e @ e / (n - k))
    se = math.sqrt(max(V[1, 1], iid[1, 1]))      # never let clustering claim more precision
    return {"a": beta[0], "b": beta[1], "se_b": se, "lo": beta[1] - 1.96 * se, "hi": beta[1] + 1.96 * se,
            "n": n, "G": G, "sd_x": float(np.std(X[:, 1])), "mean_abs_x": float(np.mean(np.abs(X[:, 1])))}


def level(rows: list[dict]) -> dict:
    d = [r["date"] for r in rows]
    return {"shade": stats([r["proj"] - r["line"] for r in rows], d),
            "landed": stats([r["actual"] - r["line"] for r in rows], d),
            "mae_proj": st.fmean(abs(r["actual"] - r["proj"]) for r in rows),
            "mae_line": st.fmean(abs(r["actual"] - r["line"]) for r in rows),
            "mae_diff": stats([abs(r["actual"] - r["proj"]) - abs(r["actual"] - r["line"]) for r in rows], d)}


def hit_rate(rows: list[dict]) -> tuple[int, int]:
    w = l = 0
    for r in rows:
        x, m = r["proj"] - r["line"], r["actual"] - r["line"]
        if x == 0 or m == 0:
            continue
        w += (x > 0) == (m > 0)
        l += (x > 0) != (m > 0)
    return w, l


def proper(rows: list[dict]) -> dict:
    """Brier / log loss of PFF's under probability at the line vs 0.5 (two-sided -110)."""
    out = [(p_under(r["line"], r["proj"]), 1.0 if r["actual"] < r["line"] else 0.0)
           for r in rows if r["actual"] != r["line"]]
    brier = st.fmean((p - y) ** 2 for p, y in out)
    ll = -st.fmean(y * math.log(p) + (1 - y) * math.log(1 - p) for p, y in out)
    return {"n": len(out), "brier": brier, "brier_mkt": 0.25, "ll": ll, "ll_mkt": math.log(2)}


def mde_b(sd_x: float, n: int, sd_y: float = 13.5) -> float:
    """Smallest true b a two-sided 5% test detects 80% of the time, iid."""
    return (1.96 + 0.84) * sd_y / (sd_x * math.sqrt(n)) if n and sd_x else float("nan")


def report(r20: list[dict], r26: list[dict], drop20: int, drop26: int) -> str:
    slope26 = [r for r in r26 if r["week"] in SLOPE_WEEKS_2026]
    pooled = r20 + slope26
    L = ["## Data", "",
         f"- 2020: {len(r20)} games (one row per game, open-Greenline snapshot); {drop20} dropped for a missing value.",
         f"- 2026: {len(r26)} graded flags, weeks {', '.join(sorted({r['week'] for r in r26}, key=int))}; "
         f"slope and proper score on weeks {', '.join(SLOPE_WEEKS_2026)} only ({len(slope26)}); {drop26} dropped.", "",
         "## Pre-outcome power (from the spread of projection − line alone)", "",
         "| sample | n | SD of projection − line | mean abs(projection − line) | MDE on b |",
         "| --- | ---: | ---: | ---: | ---: |"]
    for lab, rs in (("2020", r20), (f"2026 weeks {'-'.join(SLOPE_WEEKS_2026)}", slope26), ("pooled", pooled)):
        xs = [r["proj"] - r["line"] for r in rs]
        L.append(f"| {lab} | {len(rs)} | {st.pstdev(xs):.2f} | {st.fmean(abs(v) for v in xs):.2f} | "
                 f"{mde_b(st.pstdev(xs), len(rs)):.2f} |")
    L += ["", "## Level: does the average game follow PFF's shade?", "",
          "| era | games | dates | PFF shade (proj − line) | games landed (actual − line) | MAE proj | MAE line | MAE proj − line (95%) |",
          "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for lab, rs in (("2020", r20), ("2026 weeks 2-4", r26)):
        lv = level(rs)
        s, a, md = lv["shade"], lv["landed"], lv["mae_diff"]
        L.append(f"| {lab} | {len(rs)} | {s['g']} | {s['mean']:+.2f} | {a['mean']:+.2f} ± {1.96 * a['se']:.2f} | "
                 f"{lv['mae_proj']:.2f} | {lv['mae_line']:.2f} | {md['mean']:+.2f} ± {1.96 * md['se']:.2f} |")
    L += ["", "## Slope: how much of PFF's disagreement is real?", "",
          "(actual − line) = a + b·(projection − line); SEs clustered by date (never below iid).", "",
          "| sample | n | dates | b | 95% CI | upper-bound edge, pts/game | upper-bound edge, pp win prob |",
          "| --- | ---: | ---: | ---: | --- | ---: | ---: |"]
    fits = {}
    for lab, rs in (("2020", r20), (f"2026 weeks {'-'.join(SLOPE_WEEKS_2026)}", slope26), ("pooled", pooled)):
        f = ols_clustered([r["proj"] - r["line"] for r in rs], [r["actual"] - r["line"] for r in rs],
                          [r["date"] for r in rs])
        fits[lab] = f
        cap = max(f["hi"], 0) * f["mean_abs_x"]
        L.append(f"| {lab} | {f['n']} | {f['G']} | {f['b']:+.2f} | {f['lo']:+.2f} to {f['hi']:+.2f} | "
                 f"{cap:.2f} | {cap * PP_PER_POINT * 100:.1f} |")
    f20, f26 = fits["2020"], fits[f"2026 weeks {'-'.join(SLOPE_WEEKS_2026)}"]
    z = (f20["b"] - f26["b"]) / math.hypot(f20["se_b"], f26["se_b"])
    L += ["", f"Era heterogeneity on b: 2020 minus 2026 {f20['b'] - f26['b']:+.2f}, two-sided p "
          f"{math.erfc(abs(z) / math.sqrt(2)):.3f}.", "",
          "## Betting the projection's side, and proper score", "",
          "| sample | W-L (projection's side of the line) | win% | Wilson 95% | Brier PFF / market | log loss PFF / market |",
          "| --- | --- | ---: | --- | --- | --- |"]
    for lab, rs, pr in (("2020", r20, r20), ("2026 weeks 2-4 (record) / 2-3 (score)", r26, slope26)):
        w, l = hit_rate(rs)
        lo, hi = wilson(w, w + l)
        ps = proper(pr)
        L.append(f"| {lab} | {w}-{l} | {w / (w + l) * 100:.1f}% | {lo * 100:.0f}–{hi * 100:.0f}% | "
                 f"{ps['brier']:.4f} / {ps['brier_mkt']:.4f} | {ps['ll']:.4f} / {ps['ll_mkt']:.4f} |")
    L += ["", "Break-even at −110 is 52.38%. Market Brier and log loss are those of 0.5 at the line.", ""]
    return "\n".join(L) + "\n"


def self_check() -> None:
    rng = np.random.default_rng(1)
    x = rng.normal(0, 1, 4000)
    y = 0.5 + 0.8 * x + rng.normal(0, 1, 4000)
    f = ols_clustered(list(x), list(y), [str(i % 200) for i in range(4000)])
    assert abs(f["b"] - 0.8) < 0.1 and f["lo"] < 0.8 < f["hi"] and abs(f["a"] - 0.5) < 0.1, f
    assert abs(mde_b(1.0, 500) - 2.8 * 13.5 / math.sqrt(500)) < 1e-9
    rows = [{"line": 50.0, "proj": 49.0, "actual": 45.0, "date": "d"},    # under side, under wins
            {"line": 50.0, "proj": 51.0, "actual": 45.0, "date": "d"},    # over side, under wins
            {"line": 50.0, "proj": 49.0, "actual": 50.0, "date": "d"},    # push: out
            {"line": 50.0, "proj": 50.0, "actual": 55.0, "date": "d"}]    # no side: out
    assert hit_rate(rows) == (1, 1)
    r20, _ = load_2020()
    assert len({r["game_id"] for r in r20}) == len(r20) > 300, len(r20)   # one row per game, not per side
    print("self-check ok")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, help="also write the report here")
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args()
    if a.self_check:
        self_check()
        return
    r20, d20 = load_2020()
    r26, d26 = load_2026()
    md = report(r20, r26, d20, d26)
    print(md)
    if a.out:
        a.out.write_text(md, encoding="utf-8")
        print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
