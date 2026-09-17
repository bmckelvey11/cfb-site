"""Does Pinnacle's shade at capture predict which Greenline unders win?

Three Pinnacle-derived features per graded under flag, joined from
`greenline_vs_pinnacle_<season>_w<week>.csv` (captured alongside the flag):

    lean       Pinnacle fair total minus Pinnacle line. Negative = Pinnacle's juice
               already leans under. "Does the sharp book agree with PFF?"
    move       Pinnacle line minus PFF's shown line. Negative = Pinnacle already sits
               below the number PFF graded against. "Has the market moved first?"
    disagree   PFF projection minus Pinnacle fair. More negative = PFF further below
               the sharpest opinion. "How hard is PFF fading Pinnacle?"
    limit      Pinnacle's posted limit, split at the sample median. Higher = sharper.

Each is split at zero (limit at its median) and tested as a two-way record with Wilson
intervals, Fisher exact, and a Spearman rank correlation on the continuous value. Holm
across the four. Only 2026 flags have a Pinnacle capture, so the 2023-25 history is not
in this test. Fixed before running (2026-09-17).

Run from repo root:
    python research/totals/scripts/pinnacle_shade.py [--out research/totals/docs]
    python research/totals/scripts/pinnacle_shade.py --self-check
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import math
import sys
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research" / "totals" / "scripts"))
from cfb_paths import INGEST  # noqa: E402
from greenline_season_review import BREAK_EVEN, mde, wilson  # noqa: E402

IN_DIR = INGEST / "pff_scoreboard"

FEATURES = [
    ("lean", "Pinnacle fair - Pinnacle line < 0 (juice leans under)", lambda r: r["pin_fair"] - r["pin_line"]),
    ("move", "Pinnacle line - PFF line < 0 (market already below PFF's number)", lambda r: r["pin_line"] - r["pff_line"]),
    ("disagree", "PFF proj - Pinnacle fair (split at median; more negative = harder fade)",
     lambda r: r["proj"] - r["pin_fair"]),
    ("limit", "Pinnacle limit (split at median; higher = sharper)", lambda r: r["pin_limit"]),
]
SPLIT_AT_MEDIAN = {"disagree", "limit"}


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load(season: int) -> list[dict]:
    res = IN_DIR / f"greenline_results_{season}.csv"
    graded = [r for r in csv.DictReader(res.open(encoding="utf-8"))
              if r["source"] == "pff" and r["market"] == "total" and r["side"] == "under" and r["result"] != "push"]
    pin = {}
    for p in IN_DIR.glob(f"greenline_vs_pinnacle_{season}_w*.csv"):
        wk = p.stem.rsplit("_w", 1)[1]
        for r in csv.DictReader(p.open(encoding="utf-8")):
            if r.get("band") != "under":
                continue
            pin[(wk, r["game"].replace(" ", ""))] = r
    out = []
    for g in graded:
        r = pin.get((g["week"], g["game"]))
        if not r:
            continue
        vals = {k: num(r.get(k)) for k in ("pff_line", "proj", "pin_line", "pin_fair", "pin_limit")}
        if any(vals[k] is None for k in ("pff_line", "proj", "pin_line", "pin_fair")):
            continue
        out.append({"week": g["week"], "game": g["game"], "win": g["result"] == "win", **vals})
    return out


def rec(rows: list[dict]) -> tuple[int, int]:
    w = sum(r["win"] for r in rows)
    return w, len(rows) - w


def fmt(w: int, l: int) -> str:
    n = w + l
    if not n:
        return "--"
    lo, hi = wilson(w, n)
    return f"{w}-{l} ({w / n * 100:.0f}%, {lo * 100:.0f}–{hi * 100:.0f}%)"


def holm(ps: list[float]) -> list[float]:
    order = sorted(range(len(ps)), key=lambda i: (math.isnan(ps[i]), ps[i]))
    out, m, run = [float("nan")] * len(ps), len(ps), 0.0
    for k, i in enumerate(order):
        if math.isnan(ps[i]):
            continue
        run = max(run, (m - k) * ps[i])
        out[i] = min(1.0, run)
    return out


def evaluate(rows: list[dict]) -> list[dict]:
    res = []
    for name, desc, fn in FEATURES:
        vals = [(r, fn(r)) for r in rows if fn(r) is not None]
        if not vals:
            res.append({"name": name, "desc": desc, "n": 0, "cut": float("nan"), "lo": (0, 0), "hi": (0, 0),
                        "p_fisher": float("nan"), "rho": float("nan"), "p_rho": float("nan"), "mde_lo": float("nan")})
            continue
        x = np.array([v for _, v in vals])
        cut = float(np.median(x)) if name in SPLIT_AT_MEDIAN else 0.0
        low = [r for r, v in vals if v < cut]
        high = [r for r, v in vals if v >= cut]
        lo, hi = rec(low), rec(high)
        p = stats.fisher_exact([[lo[0], lo[1]], [hi[0], hi[1]]])[1] if low and high else float("nan")
        won = np.array([r["win"] for r, _ in vals], dtype=float)
        rho, p_rho = (stats.spearmanr(x, won) if len(set(won)) > 1 and len(set(x)) > 1 and len(x) > 2
                      else (float("nan"), float("nan")))
        res.append({"name": name, "desc": desc, "n": len(vals), "cut": cut, "lo": lo, "hi": hi, "p_fisher": p,
                    "rho": float(rho), "p_rho": float(p_rho), "mde_lo": mde(sum(lo)) if sum(lo) else float("nan")})
    for r, ph in zip(res, holm([r["p_fisher"] for r in res])):
        r["p_holm"] = ph
    return res


def render(rows: list[dict], res: list[dict], season: int) -> str:
    w, l = rec(rows)
    weeks = ", ".join(sorted({r["week"] for r in rows}))
    L = [f"# Pinnacle shade on Greenline unders, {dt.date.today().isoformat()}", "",
         "Reproduce: `python research/totals/scripts/pinnacle_shade.py --out research/totals/docs`.", "",
         "## Question", "",
         "Does where Pinnacle sits at capture (its juice lean, its line relative to PFF's, its distance from",
         "PFF's projection, its limit) predict which Greenline under flags win?", "",
         "## Data", "",
         f"- {season} graded under flags with a Pinnacle capture: n = {len(rows)}, weeks {weeks or '--'}, "
         f"record {fmt(w, l)}." if rows else f"- No graded {season} under flags with a Pinnacle capture yet.",
         "- Pinnacle numbers from `greenline_vs_pinnacle_<season>_w<week>.csv` (captured with the flag, before kickoff).",
         "- The 2023-25 history has no Pinnacle capture and is not in this test.",
         f"- MDE for the whole sample: {mde(w + l) * 100:.1f}% against {BREAK_EVEN * 100:.2f}% break-even." if rows else "",
         "", "## Features, fixed before running", "", "| feature | rule |", "|---|---|"]
    L += [f"| {n} | {d} |" for n, d, _ in FEATURES]
    L += ["", "## Records: below the cut vs at or above", "",
          "| feature | n | cut | below | at/above | Fisher p | Holm p | Spearman rho | p | MDE below |",
          "|---|---:|---:|---|---|---:|---:|---:|---:|---:|"]
    for r in res:
        L.append(f"| {r['name']} | {r['n']} | {r['cut']:.2f} | {fmt(*r['lo'])} | {fmt(*r['hi'])} | "
                 f"{r['p_fisher']:.3f} | {r['p_holm']:.3f} | {r['rho']:+.2f} | {r['p_rho']:.3f} | "
                 f"{r['mde_lo'] * 100:.0f}% |")
    keep = [r for r in res if not math.isnan(r["p_holm"]) and r["p_holm"] < 0.05]
    L += ["", "## Reading", ""]
    L += ([f"- Survives Holm at 5%: {', '.join(r['name'] for r in keep)}."] if keep
          else ["- No Pinnacle feature survives Holm at 5%. None is a filter yet."])
    if rows:
        best = min((r for r in res if not math.isnan(r["p_fisher"])), key=lambda r: r["p_fisher"], default=None)
        if best:
            L.append(f"- Strongest raw split is `{best['name']}` (Fisher p {best['p_fisher']:.3f}): below "
                     f"{fmt(*best['lo'])} vs at/above {fmt(*best['hi'])}.")
    L += ["- For `lean` and `move`, 'below' is the half where Pinnacle already agrees with PFF's under. If that half",
          "  wins more, the market is confirming PFF; if the other half wins more, PFF is adding something the",
          "  market has not priced. Neither is readable until the sample clears its MDE.",
          "", "## What this does not support", "",
          "- Any rule on the live slate. This is one to two graded weeks of one vendor's flags.",
          "- Reading `limit` as anything but a proxy: Pinnacle limits scale with the game's profile, not with",
          "  how sharp the number is on that game.",
          "", "## What settles it", "",
          "- Rerun after each graded week; the join picks up new `greenline_vs_pinnacle_*` files automatically.",
          "- ~150 graded unders gives a halved split ~64% MDE per side."]
    return "\n".join(x for x in L if x is not None) + "\n"


def self_check() -> None:
    rows = []
    for i in range(40):
        rows.append({"week": "2", "game": f"A{i}@B{i}", "win": (i % 3 != 0) if i < 20 else (i % 2 == 0),
                     "pff_line": 55.5, "proj": 53.5, "pin_line": 55.5 - (i % 2), "pin_fair": 55.3 - (i % 2),
                     "pin_limit": 500.0 + i * 10})
    res = evaluate(rows)
    by = {r["name"]: r for r in res}
    assert all(r["n"] == 40 for r in res)
    assert by["lean"]["cut"] == 0.0 and sum(by["lean"]["lo"]) == 40      # every fair sits below its line here
    assert by["move"]["cut"] == 0.0 and sum(by["move"]["lo"]) == 20     # odd i -> Pinnacle a point under PFF
    assert by["limit"]["cut"] == 695.0 and sum(by["limit"]["lo"]) == 20
    assert math.isnan(by["lean"]["p_fisher"])                           # one-sided split has no Fisher p
    assert all(0 <= r["p_holm"] <= 1 for r in res if not math.isnan(r["p_holm"]))
    assert holm([0.01, 0.04, 0.03]) == [0.03, 0.06, 0.06]
    md = render(rows, res, 2026)
    assert "| move | 40 | 0.00 |" in md
    assert "No graded" in render([], evaluate([]), 2026)
    print("self-check ok")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--out", type=Path, help="directory for the .md write-up")
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args()
    if a.self_check:
        self_check()
        return
    rows = load(a.season)
    text = render(rows, evaluate(rows), a.season)
    if a.out:
        p = a.out / f"greenline-pinnacle-shade-{dt.date.today().isoformat()}.md"
        p.write_text(text, encoding="utf-8")
        print(f"wrote {p}")
    else:
        print(text)


if __name__ == "__main__":
    main()
