"""Season-to-date review of PFF Greenline picks: all three markets, all captured weeks.

    python research/totals/scripts/greenline_season_review.py
    python research/totals/scripts/greenline_season_review.py --season 2026 --out research/totals/docs/x.md
    python research/totals/scripts/greenline_season_review.py --self-check

Reads every `pff_greenline_<season>_w<week>.csv` capture plus the refreshed PFF
schedule, grades each flag's chosen side on totals, spreads and moneylines
against the final, and reports records with Wilson intervals, units, closing-line
value against the schedule's last posted number, and calibration of PFF's own
stated cover probabilities. Weeks not yet played are summarised as a pending
slate. Rerun after each Monday's schedule refresh. Every graded row (one per
flag per market) is also written to `greenline_results_<season>.csv` next to the
captures, so the results survive as a flat file. Your own full-game NCAAF totals
from the prior season's bet history (`data/ingest/bet_history/history.csv`, the
book export behind `docs/bet-history-analysis-2023-2025.md`) ride along in the
same file and as a baseline row, tagged `source=personal`, so PFF's flags sit
next to what you actually bet at the same prices.

Conventions (checked against week 2 rows): `market_spread` is the HOME spread,
negative when the home side is favoured; `greenline_spread` is PFF's home
spread on the same sign. Home covers when home - away + spread > 0. Units are
-110 on spreads and totals and the captured market price on moneylines. Pushes
return the stake and are left out of win% and calibration.

Closing-line value uses the schedule's current `point_spread` / `over_under`,
which after kickoff is the last number PFF displayed -- a close by PFF's board,
not a sharp book's. Positive CLV means the number moved toward the flagged side.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics as st
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cfb_paths import INGEST  # noqa: E402
from grade_greenline import BANDS, VALUE_BUCKETS, capture_lines, num, pff_final, warehouse_final, warehouse_finals  # noqa: E402

IN_DIR = INGEST / "pff_scoreboard"
BREAK_EVEN = 110 / 210
RESULT_COLUMNS = ["source", "season", "week", "date", "game", "market", "side", "line", "price", "result",
                  "p", "value", "clv", "p_market"]
HISTORY = INGEST / "bet_history" / "history.csv"


def wilson(w: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if not n:
        return (float("nan"), float("nan"))
    p = w / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def decimal(american: float) -> float:
    return 1 + american / 100 if american > 0 else 1 + 100 / -american


def devig(a: float, b: float) -> float:
    """Vig-free probability of side a from the pair of American prices."""
    pa, pb = 1 / decimal(a), 1 / decimal(b)
    return pa / (pa + pb)


def grade_flag(f: dict, g: dict, finals: list[dict], lines: dict) -> list[dict]:
    """One row per market PFF took a side on. Empty when the game has no final."""
    final = pff_final(g) or warehouse_final(g, finals)
    if final is None:
        return []
    away, home = final
    base = {"source": "pff", "season": int(f.get("season") or 0), "week": f["pff_week"],
            "date": (f.get("kickoff_raw") or "")[:10], "game": f"{f['away_abbreviation']}@{f['home_abbreviation']}"}
    out = []

    line = num(f.get("market_over_under"))
    if line is None:
        line = lines.get(f["pff_game_id"])
    side = f.get("total_best_side")
    if side and line is not None:
        total, close = away + home, num(g.get("over_under"))
        res = "push" if total == line else ("win" if (total > line) == (side == "over") else "loss")
        clv = None if close is None else (line - close if side == "under" else close - line)
        out.append(dict(base, market="total", side=side, line=line, result=res, price=-110,
                        p=num(f.get(f"{side}_cover_probability")), value=num(f.get("total_best_value")),
                        clv=clv, p_market=0.5))

    spread, side = num(f.get("market_spread")), f.get("spread_best_side")
    if side and spread is not None:
        margin, close = home - away + spread, num(g.get("point_spread"))
        res = "push" if margin == 0 else ("win" if (margin > 0) == (side == "home") else "loss")
        clv = None if close is None else (spread - close if side == "home" else close - spread)
        out.append(dict(base, market="spread", side=side, line=spread, result=res, price=-110,
                        p=num(f.get(f"spread_{side}_cover_probability")), value=num(f.get("spread_best_value")),
                        clv=clv, p_market=0.5))

    side = f.get("money_line_best_side")
    pa, ph = num(f.get("market_money_line_away")), num(f.get("market_money_line_home"))
    if side and pa is not None and ph is not None:
        winner = "home" if home > away else ("away" if away > home else None)
        res = "push" if winner is None else ("win" if winner == side else "loss")
        out.append(dict(base, market="moneyline", side=side, line=(pa if side == "away" else ph), result=res,
                        price=(pa if side == "away" else ph),
                        p=num(f.get(f"money_line_{side}_cover_probability")),
                        value=num(f.get("money_line_best_value")), clv=None,
                        p_market=devig(pa, ph) if side == "away" else devig(ph, pa)))
    return out


def tally(rows: list[dict]) -> dict:
    w = [r for r in rows if r["result"] == "win"]
    l = [r for r in rows if r["result"] == "loss"]
    p = sum(1 for r in rows if r["result"] == "push")
    units = sum(decimal(r["price"]) - 1 for r in w) - len(l)
    n = len(w) + len(l)
    lo, hi = wilson(len(w), n)
    return {"n": len(rows), "w": len(w), "l": len(l), "p": p, "pct": len(w) / n if n else float("nan"),
            "lo": lo, "hi": hi, "units": units, "roi": units / n if n else float("nan")}


def fmt(t: dict) -> str:
    if not t["n"]:
        return "--"
    push = f"-{t['p']}" if t["p"] else ""
    return (f"{t['w']}-{t['l']}{push} | {t['pct'] * 100:.1f}% | {t['lo'] * 100:.0f}–{t['hi'] * 100:.0f}% | "
            f"{t['units']:+.2f}u | {t['roi'] * 100:+.1f}%")


def mde(n: int, p0: float = BREAK_EVEN, alpha_z: float = 1.645, power_z: float = 0.84) -> float:
    """Smallest true win rate a one-sided test at n would detect 80% of the time."""
    return p0 + (alpha_z + power_z) * math.sqrt(0.25 / n) if n else float("nan")


def brier(rows: list[dict], key: str) -> float | None:
    xs = [(r[key], 1.0 if r["result"] == "win" else 0.0) for r in rows if r["result"] != "push" and r.get(key) is not None]
    return st.mean((p - y) ** 2 for p, y in xs) if xs else None


def clv_line(rows: list[dict]) -> str:
    xs = [r["clv"] for r in rows if r["clv"] is not None]
    if not xs:
        return "--"
    m = st.mean(xs)
    se = st.stdev(xs) / math.sqrt(len(xs)) if len(xs) > 1 else float("nan")
    beat, lost = sum(1 for x in xs if x > 0), sum(1 for x in xs if x < 0)
    return f"mean {m:+.2f} ± {1.96 * se:.2f} pts (n={len(xs)}); beat close {beat}, lost {lost}, flat {len(xs) - beat - lost}"


def personal_totals(season: int, path: Path = HISTORY) -> list[dict]:
    """Your full-game NCAAF over/unders for one season, in the graded-row shape.

    The export's first line is a `data:text/csv` prefix, not a header. A season runs
    August through the following January, so `season` is the August year."""
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    out = []
    for r in csv.DictReader(lines[1:]):
        t = r.get("Start Time") or ""
        if r.get("League") != "ncaaf" or r.get("Type") not in ("over", "under") or r.get("Period") != "game":
            continue
        if not (f"{season}-08-01" <= t < f"{season + 1}-02-01") or r.get("Result") not in ("win", "loss", "push"):
            continue
        out.append({"source": "personal", "season": season, "week": "", "date": t[:10], "game": r["Game"],
                    "market": "total", "side": r["Type"], "line": num(r["Odds/Spread/Total"]),
                    "price": num(r["Odds"]), "result": r["Result"], "p": None, "value": None, "clv": None,
                    "p_market": 0.5})
    return out


def load(season: int):
    sched = {x["pff_game_id"]: x for x in csv.DictReader((IN_DIR / f"pff_schedule_{season}.csv").open(encoding="utf-8"))}
    finals = warehouse_finals(season)
    graded, pending = [], {}
    for p in sorted(IN_DIR.glob(f"pff_greenline_{season}_w*.csv")):
        wk = p.stem.rsplit("_w", 1)[1]
        lines = capture_lines(season, wk)
        for f in csv.DictReader(p.open(encoding="utf-8")):
            g = sched.get(f["pff_game_id"])
            if not g:
                continue
            rows = grade_flag(f, g, finals, lines)
            if rows:
                graded.extend(rows)
            else:
                pending.setdefault(wk, []).append(f)
    return graded, pending


def totals_section(graded: list[dict], personal: list[dict]) -> list[str]:
    """Totals-only splits: week, side, market-total band, PFF value bucket. Accumulate, do not act."""
    T = [r for r in graded if r["market"] == "total"]
    U = [r for r in T if r["side"] == "under"]
    L = ["## Totals in depth", "", "| split | record | win% | 95% CI | units | ROI |", "|---|---|---:|---|---:|---:|"]
    for wk in sorted({r["week"] for r in T}):
        L.append(f"| week {wk} | {fmt(tally([r for r in T if r['week'] == wk]))} |")
    L.append(f"| all weeks | {fmt(tally(T))} |")
    if personal:
        yr = personal[0]["season"]
        L.append(f"| your {yr} totals (baseline) | {fmt(tally(personal))} |")
        L.append(f"| your {yr} unders | {fmt(tally([r for r in personal if r['side'] == 'under']))} |")
        L.append(f"| your {yr} overs | {fmt(tally([r for r in personal if r['side'] == 'over']))} |")
    L += ["", "| under flags by market total | record | win% | 95% CI | units | ROI |", "|---|---|---:|---|---:|---:|"]
    for lab, fn in BANDS:
        L.append(f"| {lab} | {fmt(tally([r for r in U if fn(r['line'])]))} |")
    L += ["", "| under flags by PFF value | record | win% | 95% CI | units | ROI |", "|---|---|---:|---|---:|---:|"]
    for lab, fn in VALUE_BUCKETS:
        L.append(f"| {lab} | {fmt(tally([r for r in U if r['value'] is not None and fn(r['value'])]))} |")
    L.append("")
    return L


def report(graded: list[dict], pending: dict, season: int, totals_only: bool = False,
           personal: list[dict] = ()) -> str:
    if totals_only:
        graded = [r for r in graded if r["market"] == "total"]
    L = [f"# PFF Greenline {'totals' if totals_only else 'picks'}, {season} season to date", "",
         f"Generated {date.today().isoformat()} by `research/totals/scripts/greenline_season_review.py`. "
         "Graded at the line in the capture, -110 on spreads and totals, market price on moneylines. "
         "Intervals are 95% Wilson. Pushes excluded from win% and calibration.", ""]
    weeks = sorted({r["week"] for r in graded})
    L += [f"**Graded weeks:** {', '.join(weeks) or 'none'}. **Pending:** " +
          (", ".join(f"week {k} ({len(v)} flags)" for k, v in sorted(pending.items())) or "none"), ""]

    L += ["## Record by market", "", "| market | record | win% | 95% CI | units | ROI |", "|---|---|---:|---|---:|---:|"]
    markets = [m for m in ("total", "spread", "moneyline") if any(r["market"] == m for r in graded)]
    for m in markets:
        L.append(f"| {m} | {fmt(tally([r for r in graded if r['market'] == m]))} |")
    if len(markets) > 1:
        L.append(f"| all | {fmt(tally(graded))} |")
    n_tot = sum(1 for r in graded if r["result"] != "push")
    L += ["", f"Break-even at -110 is 52.4%. At n={n_tot} pooled, the smallest true win rate a one-sided test "
          f"would reliably detect is {mde(n_tot) * 100:.0f}%; per market it is "
          + ", ".join(f"{m} {mde(sum(1 for r in graded if r['market'] == m and r['result'] != 'push')) * 100:.0f}%"
                      for m in markets) + ". Anything short of that is not evidence either way.", ""]

    L += ["## By side", "", "| market | side | record | win% | 95% CI | units | ROI |", "|---|---|---|---:|---|---:|---:|"]
    for m in markets:
        for s in sorted({r["side"] for r in graded if r["market"] == m}):
            L.append(f"| {m} | {s} | {fmt(tally([r for r in graded if r['market'] == m and r['side'] == s]))} |")

    L += ["", "## Closing-line value (PFF board close)", ""]
    for m in [m for m in ("total", "spread") if m in markets]:
        L.append(f"- **{m}**: {clv_line([r for r in graded if r['market'] == m])}")
    L += ["", "Positive means the number moved toward PFF's side after the capture. This is the board PFF "
          "shows, not Pinnacle, so it measures whether PFF's flags lead their own displayed market.", ""]

    L += ["## Does PFF's own ranking work?", "", "| market | top half by value | bottom half |", "|---|---|---|"]
    for m in markets:
        rs = sorted([r for r in graded if r["market"] == m and r["value"] is not None], key=lambda r: -r["value"])
        h = len(rs) // 2
        L.append(f"| {m} | {fmt(tally(rs[:h]))} | {fmt(tally(rs[h:]))} |")

    L += ["", "## Calibration of PFF's stated probabilities", "",
          "| market | n | mean stated p | actual win% | Brier (PFF) | Brier (market) |", "|---|---:|---:|---:|---:|---:|"]
    for m in markets:
        rs = [r for r in graded if r["market"] == m and r["result"] != "push" and r["p"] is not None]
        if not rs:
            continue
        L.append(f"| {m} | {len(rs)} | {st.mean(r['p'] for r in rs) * 100:.1f}% | "
                 f"{st.mean(1.0 if r['result'] == 'win' else 0.0 for r in rs) * 100:.1f}% | "
                 f"{brier(rs, 'p'):.4f} | {brier(rs, 'p_market'):.4f} |")
    L += ["", "Market Brier uses 0.5 for spreads and totals (a flag is a bet against a -110 line) and the "
          "vig-free price for moneylines. PFF beating the market column means its stated probabilities carry "
          "information; a stated-p above the actual win% means the numbers are overconfident.", ""]

    if totals_only:
        L += totals_section(graded, list(personal))

    for wk, flags in sorted(pending.items()):
        L += [f"## Pending: week {wk}", ""]
        tot = [f for f in flags if f.get("total_best_side")]
        sp = [f for f in flags if f.get("spread_best_side")]
        ml = [f for f in flags if f.get("money_line_best_side")]
        L += [f"- {len(flags)} flagged games; totals {sum(1 for f in tot if f['total_best_side'] == 'under')} under / "
              f"{sum(1 for f in tot if f['total_best_side'] == 'over')} over; spreads "
              f"{sum(1 for f in sp if f['spread_best_side'] == 'away')} away / {sum(1 for f in sp if f['spread_best_side'] == 'home')} home; "
              f"moneylines {sum(1 for f in ml if f['money_line_best_side'] == 'away')} away / {sum(1 for f in ml if f['money_line_best_side'] == 'home')} home.",
              f"- mean stated edge: totals {st.mean(num(f['total_best_value']) for f in tot) * 100:+.2f}%, "
              f"spreads {st.mean(num(f['spread_best_value']) for f in sp) * 100:+.2f}%." if tot and sp else "", ""]
    return "\n".join(L)


def self_check() -> None:
    f = {"pff_game_id": "1", "pff_week": "2", "away_abbreviation": "A", "home_abbreviation": "H",
         "market_over_under": "50.5", "total_best_side": "under", "under_cover_probability": "0.56", "total_best_value": "0.03",
         "market_spread": "-3.5", "spread_best_side": "away", "spread_away_cover_probability": "0.58", "spread_best_value": "0.05",
         "market_money_line_away": "139", "market_money_line_home": "-166", "money_line_best_side": "away",
         "money_line_away_cover_probability": "0.48", "money_line_best_value": "0.06"}
    g = {"is_over": "True", "away_score": "21", "home_score": "28", "over_under": "53.5", "point_spread": "-3.0"}
    rows = {r["market"]: r for r in grade_flag(f, g, [], {})}
    assert rows["total"]["result"] == "win" and rows["total"]["clv"] == -3.0          # 49 < 50.5; close went UP: under lost CLV
    assert rows["spread"]["result"] == "loss" and rows["spread"]["clv"] == 0.5        # home by 7 covers -3.5; close -3.0 favours away
    assert rows["moneyline"]["result"] == "loss" and abs(rows["moneyline"]["p_market"] - 0.399) < 0.01
    home = grade_flag(dict(f, spread_best_side="home", spread_home_cover_probability="0.6"), g, [], {})
    assert [r for r in home if r["market"] == "spread"][0]["clv"] == -0.5
    push = grade_flag(dict(f, market_spread="-7"), g, [], {})
    assert [r for r in push if r["market"] == "spread"][0]["result"] == "push"
    assert grade_flag(f, {"is_over": "False"}, [], {}) == []
    t = tally([dict(result="win", price=-110), dict(result="loss", price=-110), dict(result="push", price=-110)])
    assert (t["w"], t["l"], t["p"]) == (1, 1, 1) and abs(t["units"] - (100 / 110 - 1)) < 1e-9
    import tempfile
    hist = Path(tempfile.mkdtemp()) / "history.csv"
    hist.write_text("data:text/csv;charset=utf-8,\n"
                    "League,Start Time,Game,Pick Desc,Type,Period,Odds,Odds/Spread/Total,Result,Units Wagered,Units Net,Money Wagered,Money Net,Tag\n"
                    "ncaaf,2025-09-06T23:00:00.000Z,A @ B,A @ B: u55.5 -110,under,game,-110,55.5,win,1,0.9091,1000,909,\n"
                    "ncaaf,2025-09-06T23:00:00.000Z,A @ B,A +3 -110,spread_away,game,-110,3,win,1,0.9091,1000,909,\n"
                    "ncaaf,2025-09-06T23:00:00.000Z,C @ D,C @ D: o50 -105,over,firsthalf,-105,50,loss,1,-1,1000,-1000,\n"
                    "ncaaf,2026-01-01T23:00:00.000Z,E @ F,E @ F: u40 -115,under,game,-115,40,loss,1,-1,1000,-1000,\n"
                    "ncaaf,2026-08-30T23:00:00.000Z,G @ H,G @ H: u40 -110,under,game,-110,40,win,1,0.9,1000,900,\n"
                    "ncaab,2025-11-06T23:00:00.000Z,X @ Y,X @ Y: u140 -110,under,game,-110,140,win,1,0.9,1000,900,\n",
                    encoding="utf-8")
    pt = personal_totals(2025, hist)
    assert [(r["game"], r["side"], r["price"], r["result"]) for r in pt] == [("A @ B", "under", -110.0, "win"),
                                                                             ("E @ F", "under", -115.0, "loss")], pt
    assert personal_totals(2024, hist) == []
    lo, hi = wilson(21, 36)
    assert 0.41 < lo < 0.43 and 0.72 < hi < 0.74, (lo, hi)
    assert abs(mde(40) - 0.72) < 0.01
    print("self-check ok")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--out", type=Path, help="markdown path; printed only when omitted")
    ap.add_argument("--totals", action="store_true", help="totals only, with week/band/value splits")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        self_check()
        return
    graded, pending = load(args.season)
    personal = personal_totals(args.season - 1)
    md = report(graded, pending, args.season, totals_only=args.totals, personal=personal)
    print(md)
    results = IN_DIR / f"greenline_results_{args.season}.csv"
    rows = sorted(graded, key=lambda r: (int(r["week"]), r["game"], r["market"])) + sorted(personal, key=lambda r: r["date"])
    with results.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=RESULT_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {len(graded)} PFF rows + {len(personal)} personal {args.season - 1} totals -> {results}")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(md, encoding="utf-8")
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
