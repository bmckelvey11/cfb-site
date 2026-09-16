"""Write the week's positive-edge Greenline under list from the captured flags.

    python research/totals/scripts/greenline_unders.py --week 3
    python research/totals/scripts/greenline_unders.py --self-check

Reads `pff_greenline_<season>_w<week>.csv` (from `scripts/pull_pff_scoreboard.py`)
and writes `greenline_unders_<season>_w<week>.csv` plus a `.md` table, ranked by
PFF's own `value`. That CSV is what `match_greenline_books.py` reprices at a book,
`greenline_vs_pinnacle.py` compares to Pinnacle, and `grade_greenline.py` falls
back to for a line when the flag has none.

`value` is PFF's win probability minus the 52.38% break-even at -110. The band
record is YOUR under history 2023-08 -> 2025-12 in that total range, from the
personal bet-history join in `docs/bet-history-analysis-2023-2025.md` -- a fixed
window, so it is a constant here rather than recomputed. It is context, not PFF's
record: week 2 showed PFF's ranking and these bands do not agree on where the
edge sits.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from cfb_paths import INGEST  # noqa: E402

GL_DIR = INGEST / "pff_scoreboard"
BREAK_EVEN_110 = 110 / 210

# (label, lower, upper, record, roi, n) -- your unders 2023-08 -> 2025-12 by market total.
BANDS = [
    ("<45", None, 45, "10-3 (77%)", "+43.2%", 13),
    ("45-49.5", 45, 50, "8-4 (67%)", "+26.0%", 12),
    ("50-54.5", 50, 55, "6-11 (35%)", "-32.9%", 17),
    ("55-59.5", 55, 60, "50-32 (61%)", "+17.2%", 82),
    ("60-64.5", 60, 65, "30-30 (50%)", "-1.4%", 60),
    ("65+", 65, None, "10-8 (56%)", "+6.3%", 18),
]

COLUMNS = ["game_id", "kickoff", "away", "home", "line", "projection", "p_under", "value",
           "band", "band_record", "band_roi", "band_n"]


def num(v):
    return float(v) if v not in ("", None) else None


def band(line: float) -> tuple:
    for b in BANDS:
        if (b[1] is None or line >= b[1]) and (b[2] is None or line < b[2]):
            return b
    raise ValueError(line)


def unders(flags: list[dict]) -> list[dict]:
    out = []
    for f in flags:
        line, value = num(f.get("market_over_under")), num(f.get("total_best_value"))
        if f.get("total_best_side") != "under" or value is None or value <= 0 or line is None:
            continue
        b = band(line)
        out.append({"game_id": f["pff_game_id"], "kickoff": (f.get("kickoff_raw") or "")[:16],
                    "away": f.get("away_abbreviation"), "home": f.get("home_abbreviation"),
                    "line": line, "projection": num(f.get("greenline_total_projection")),
                    "p_under": num(f.get("under_cover_probability")), "value": value,
                    "band": b[0], "band_record": b[3], "band_roi": b[4], "band_n": b[5]})
    return sorted(out, key=lambda r: -r["value"])


def markdown(rows: list[dict], season: int, week: str, captured: str, n_flags: int) -> str:
    lines = [f"# PFF Greenline — positive-edge unders, {season} week {week}", "",
             f"Captured {captured} from a live PFF Pro session. {len(rows)} of {n_flags} flagged games. "
             "Lines are PFF's shown number at capture — reprice before betting.", "",
             "`value` = PFF's win probability minus the 52.38% break-even at -110. Band record is YOUR",
             "under history 2023-08 → 2025-12 in that total range, not PFF's.", "",
             "| # | kickoff | game | line | PFF proj | p(under) | edge | band | your record | band ROI |",
             "|---:|---|---|---:|---:|---:|---:|---|---|---:|"]
    for i, r in enumerate(rows, 1):
        lines.append(f"| {i} | {r['kickoff']} | {r['away']} @ {r['home']} | {r['line']} | {r['projection']} | "
                     f"{r['p_under'] * 100:.1f}% | **{r['value'] * 100:+.2f}%** | {r['band']} | "
                     f"{r['band_record']} | {r['band_roi']} |")
    lines += ["", "## By band", "", "| band | picks | your history | your ROI | n |", "|---|---:|---|---:|---:|"]
    for b in BANDS:
        k = sum(1 for r in rows if r["band"] == b[0])
        if k:
            lines.append(f"| {b[0]} | {k} | {b[3]} | {b[4]} | {b[5]} |")
    return "\n".join(lines) + "\n"


def self_check() -> None:
    flags = [
        {"pff_game_id": "1", "kickoff_raw": "2026-09-19T12:00:00", "away_abbreviation": "A",
         "home_abbreviation": "B", "market_over_under": "55.5", "greenline_total_projection": "53.0",
         "under_cover_probability": "0.58", "total_best_side": "under", "total_best_value": "0.03"},
        {"pff_game_id": "2", "kickoff_raw": "2026-09-19T15:30:00", "away_abbreviation": "C",
         "home_abbreviation": "D", "market_over_under": "44.5", "greenline_total_projection": "42.0",
         "under_cover_probability": "0.60", "total_best_side": "under", "total_best_value": "0.05"},
        {"pff_game_id": "3", "market_over_under": "50.5", "total_best_side": "over", "total_best_value": "0.04"},
        {"pff_game_id": "4", "market_over_under": "50.5", "total_best_side": "under", "total_best_value": "-0.01"},
        {"pff_game_id": "5", "market_over_under": "", "total_best_side": "under", "total_best_value": "0.02"},
    ]
    rows = unders(flags)
    assert [r["game_id"] for r in rows] == ["2", "1"], rows          # ranked by value, over/negative/no-line dropped
    assert rows[0]["band"] == "<45" and rows[1]["band"] == "55-59.5"
    assert band(45.0)[0] == "45-49.5" and band(64.5)[0] == "60-64.5" and band(65.0)[0] == "65+"
    md = markdown(rows, 2026, "3", "test", 5)
    assert "| 1 | 2026-09-19T15:30 | C @ D | 44.5 |" in md and "+5.00%" in md
    print("self-check ok")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--week", required=False)
    ap.add_argument("--captured", default="", help="capture timestamp for the .md header")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        self_check()
        return
    if not args.week:
        raise SystemExit("pass --week N")
    src = GL_DIR / f"pff_greenline_{args.season}_w{args.week}.csv"
    if not src.exists():
        raise SystemExit(f"{src} not found -- run scripts/pull_pff_scoreboard.py --greenline --week {args.week}")
    flags = list(csv.DictReader(src.open(encoding="utf-8")))
    rows = unders(flags)
    stem = GL_DIR / f"greenline_unders_{args.season}_w{args.week}"
    with stem.with_suffix(".csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    stem.with_suffix(".md").write_text(markdown(rows, args.season, args.week, args.captured or "n/a", len(flags)),
                                       encoding="utf-8")
    print(f"{len(rows)} positive-edge unders of {len(flags)} flags -> {stem}.csv / .md")
    for b in BANDS:
        k = sum(1 for r in rows if r["band"] == b[0])
        if k:
            print(f"  {b[0]:<8} {k:2d}   your history {b[3]:<12} {b[4]}")


if __name__ == "__main__":
    main()
