"""Render the seed-bankroll proposal to PDF and a 9-slide deck.

    python research/bankroll/scripts/build_proposal_deliverables.py
    python research/bankroll/scripts/build_proposal_deliverables.py --self-check

Inputs: docs/seed-bankroll-proposal-2026-09-21.md, the two figures in docs/figs/,
and the sweep CSV. Outputs, next to the markdown:
    seed-bankroll-proposal-2026-09-21.pdf     markdown -> HTML -> Chrome headless print
    seed-bankroll-proposal-2026-09-21.pptx    python-pptx, numbers read from the CSV

Needs `markdown` and `python-pptx` (system Python has both; the repo .venv does not)
and Chrome (or Edge) for the PDF step.
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mc_combined_totals import (GL_BETS_RANGE, GL_FLAGS_BY_WEEK, OZ_WEEK4PLUS_HISTORY,  # noqa: E402
                                kelly_unit, planning_p_gl)

GL_UNIT_TODAY = 0.01   # the rule's answer today: min(quarter Kelly 1.31%, 3% cap -> 1%)

OZ_TOTAL = sum(OZ_WEEK4PLUS_HISTORY) / len(OZ_WEEK4PLUS_HISTORY)  # ~10.6 bets, weeks 4-15
DOCS = Path(__file__).resolve().parents[1] / "docs"
STEM = "seed-bankroll-proposal-2026-09-21"
SWEEP = DOCS / "bankroll-config-sweep-2026-09-21.csv"
FIG_GROWTH = DOCS / "figs" / "pooled-bankroll-growth-2026-09-21.png"
FIG_SWEEP = DOCS / "figs" / "bankroll-config-sweep-2026-09-21.png"
# Chrome first: Edge headless on this machine intermittently prints a 1-page stray
# render instead of the URL, even with an isolated profile. Chrome has not.
BROWSERS = (Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"))

INK, MUTED, BLUE, GREEN, RED = "1A1D24", "6B7280", "2B5D8A", "3E7D5A", "A9384A"

CSS = """
body{font-family:Segoe UI,Arial,sans-serif;font-size:11pt;color:#1a1d24;max-width:7.2in;margin:0 auto;line-height:1.45}
h1{font-size:20pt;margin:0 0 .3em}h2{font-size:14pt;color:#2b5d8a;margin:1.2em 0 .3em;border-bottom:1px solid #d8dce3}
h3{font-size:12pt;margin:1em 0 .3em}table{border-collapse:collapse;font-size:9.5pt;margin:.5em 0;width:100%}
th,td{border:1px solid #d8dce3;padding:3px 6px;text-align:left}th{background:#f3f4f6}
code{font-size:9pt;background:#f3f4f6;padding:0 3px}pre{font-size:8.5pt;background:#f3f4f6;padding:6px}
img{max-width:100%}hr{border:0;border-top:1px solid #d8dce3}
"""


def sweep_rows() -> dict[tuple[str, float], dict]:
    """0.5% and 1% rows for every prior, keyed by (prior, unit)."""
    out = {}
    for r in csv.DictReader(open(SWEEP, encoding="utf-8")):
        if r["supported"] == "True" and float(r["gl_unit"]) in (0.005, 0.01):
            out[(r["prior"], float(r["gl_unit"]))] = {k: float(v) for k, v in r.items()
                                                        if k not in ("prior", "supported", "passes_a")}
    assert len(out) == 6, out.keys()
    return out


def build_pdf() -> Path:
    import markdown
    md = (DOCS / f"{STEM}.md").read_text(encoding="utf-8")
    html = markdown.markdown(md, extensions=["tables", "fenced_code"])
    html_path = DOCS / f"{STEM}.html"
    html_path.write_text(f"<html><head><meta charset='utf-8'><style>{CSS}</style></head>"
                         f"<body>{html}</body></html>", encoding="utf-8")
    pdf = DOCS / f"{STEM}.pdf"
    # An isolated profile is required: without it the browser hands the job to any
    # running instance, exits 0, and writes nothing.
    browser = next(b for b in BROWSERS if b.exists())
    profile = Path(tempfile.mkdtemp(prefix="pdf-profile-"))
    pdf.unlink(missing_ok=True)
    subprocess.run([str(browser), "--headless=new", "--disable-gpu", "--no-first-run",
                    "--no-pdf-header-footer", f"--user-data-dir={profile}",
                    f"--print-to-pdf={pdf}", html_path.as_uri()], check=True, timeout=120)
    html_path.unlink()
    # a stray render is 1 page; the proposal is several and carries one figure
    pages = len(re.findall(rb"/Type\s*/Page[^s]", pdf.read_bytes()))
    assert pages >= 3, f"{browser.name} wrote a {pages}-page PDF; expected the multi-page proposal"
    return pdf


def build_pptx() -> Path:
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.util import Inches, Pt

    rows = sweep_rows()
    plan10, plan05 = rows[("k0.5", 0.01)], rows[("k0.5", 0.005)]
    n49_10, pooled10 = rows[("n58", 0.01)], rows[("pooled", 0.01)]
    p_plan = planning_p_gl(0.5)
    qk = kelly_unit(p_plan, -110)

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    blank = prs.slide_layouts[6]

    def rgb(h):
        return RGBColor.from_string(h)

    def text(slide, x, y, w, h, s, size=16, bold=False, color=INK):
        tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = tb.text_frame
        tf.word_wrap = True
        lines = s if isinstance(s, list) else [s]
        for i, line in enumerate(lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = line
            p.font.size = Pt(size)
            p.font.bold = bold
            p.font.color.rgb = rgb(color)
            p.space_after = Pt(6)
        return tb

    def slide(title, sub=None):
        s = prs.slides.add_slide(blank)
        text(s, 0.6, 0.35, 12, 0.8, title, 28, True)
        if sub:
            text(s, 0.6, 1.05, 12, 0.5, sub, 14, color=MUTED)
        return s

    def table(slide, x, y, w, data, col_w=None, size=12):
        n_r, n_c = len(data), len(data[0])
        shp = slide.shapes.add_table(n_r, n_c, Inches(x), Inches(y), Inches(w), Inches(0.4 * n_r))
        t = shp.table
        if col_w:
            for i, cw in enumerate(col_w):
                t.columns[i].width = Inches(cw)
        for i, row in enumerate(data):
            for j, val in enumerate(row):
                cell = t.cell(i, j)
                cell.text = str(val)
                for p in cell.text_frame.paragraphs:
                    p.font.size = Pt(size)
                    p.font.bold = i == 0
                    p.font.color.rgb = rgb(INK)
        return t

    def money(v):
        return f"−${abs(v):,.0f}" if v < 0 else f"${v:,.0f}"

    # 1 title
    s = prs.slides.add_slide(blank)
    text(s, 0.8, 2.2, 11.5, 1.2, "Seed bankroll: $20,000 to grow across seasons", 36, True)
    text(s, 0.8, 3.5, 11.5, 1.5, [
        "A gift that seeds a betting bankroll meant to compound: the rest of 2026, all of 2027, golf once graded. Nothing is owed back.",
        "Not an investment, not a loan, not a security.",
        "Every number here comes from a script in the repository and carries its uncertainty.",
    ], 18, color=MUTED)
    text(s, 0.8, 6.4, 11.5, 0.5, "Prepared September 21, 2026", 12, color=MUTED)

    # 2 the ask
    s = slide("The ask")
    table(s, 0.6, 1.6, 12, [
        ["item", "value"],
        ["amount", "$20,000"],
        ["horizon", "rest of 2026 (Sept 24 to Dec 12), then 2027 and onward. Bowls excluded"],
        ["what it funds", "two totals strategies already running, units re-sized off the bankroll each Monday; golf once graded"],
        ["expected bets", "rest of 2026 ~118 (6–12 Greenline unders a week + ~11 over-zero); 2027 ~250"],
        ["unit today", f"Greenline {GL_UNIT_TODAY:.0%} of bankroll per bet (${20000 * GL_UNIT_TODAY:,.0f} at the start), over-zero 1%. Re-derived each Monday"],
        ["profit", "stays in the bankroll"],
    ], col_w=[3, 9], size=14)

    # 3 two legs
    s = slide("What gets bet: two legs, one bankroll",
              "Win rates are shown with their 95% intervals. Break-even is 52.4% at −110, 54.5% at −120.")
    table(s, 0.6, 1.7, 12.1, [
        ["", "Over-zero (floor-bias OVERs)", "Greenline totals (PFF flags, ~85% unders)"],
        ["what it is", "in-house model: totals pinned too low against heavy favorites", "vendor projection disagreeing with the market"],
        ["record", "151–83, 64.5% (58.2–70.4%), walk-forward 2016–25; 21–9 on the 2026 board", "32–26, 55.2% (42.5–67.3%), published 2026 under list wks 2–3; + 114–87 personal unders 2023–25"],
        ["planning win rate", "58.2%, the interval's lower endpoint", f"{p_plan:.1%}: published under list + 2023–25 unders at half weight. Bracket 55.1% to 56.4%"],
        ["price", "−120 or better", "−110"],
        ["bets left in 2026", "~11, median +$133; 30–51 in a full season", "6–12 a week by plan, ~107 in 2026, ~134 in 2027"],
        ["role", "better evidence, nearly spent for 2026; ~a third of 2027's profit", "carries the 2026 projection"],
    ], col_w=[2.3, 4.9, 4.9], size=12)
    text(s, 0.6, 5.6, 12, 1.2, [
        "Conflict rule: same game flagged on opposite sides → over-zero takes it, Greenline skips it.",
        "Excluded: the pred-tracker-model (research, not a bet); Greenline spreads and moneylines (21–28 and 21–25 in week 2).",
    ], 13, color=MUTED)

    # 3b bets per week
    lo_b, hi_b = GL_BETS_RANGE
    s = slide("Bets per week",
              f"Plan: {lo_b}–{hi_b} Greenline unders a week, capped by that week's FBS-vs-FBS slate "
              "(Greenline flags every such game). Over-zero ~11 bets spread across the span.")
    rows_w = [["week", "FBS games (= flags)", "Greenline unders", "over-zero bets", "staked at today's units"]]
    gl_dollars = 20000 * GL_UNIT_TODAY
    oz_per_week = OZ_TOTAL / len(GL_FLAGS_BY_WEEK)
    gl_tot = 0.0
    for i, flags in enumerate(GL_FLAGS_BY_WEEK):
        mean = sum(min(k, flags) for k in range(lo_b, hi_b + 1)) / (hi_b - lo_b + 1)
        gl_tot += mean
        rng_txt = f"{lo_b}–{hi_b} (mean {mean:.0f})" if flags >= hi_b else f"{min(lo_b, flags)}–{flags} (mean {mean:.0f})"
        rows_w.append([str(4 + i), str(flags), rng_txt, f"{oz_per_week:.1f}",
                       money(mean * gl_dollars + oz_per_week * 200)])
    rows_w.append(["total", str(sum(GL_FLAGS_BY_WEEK)), f"~{gl_tot:.0f}", f"~{OZ_TOTAL:.0f}",
                   money(gl_tot * gl_dollars + OZ_TOTAL * 200)])
    table(s, 0.6, 1.7, 8.6, rows_w, col_w=[1.0, 2.2, 2.2, 1.6, 1.6], size=11)
    text(s, 9.6, 1.8, 3.5, 5, [
        f"{lo_b} to {hi_b} unders plus about 1 over-zero over in a typical week. "
        "Championship week has only 9 games, so 6 to 9.",
        "",
        "Each week's count is drawn uniformly from the range, so volume is the plan, not a forecast.",
        "",
        f"A typical week stakes about ${9 * gl_dollars + 200:,.0f} at today's units; units re-size each Monday. "
        "Weeks 14 and 15 use 2025's schedule.",
    ], 13)

    # 4 projection
    s = slide("The projection: rest of 2026 and through 2027",
              "100,000 paths, win rate drawn per path from the planning prior. Top row re-sized weekly, bottom row flat. Week 12 = end of 2026.")
    s.shapes.add_picture(str(FIG_GROWTH), Inches(0.5), Inches(1.6), height=Inches(5.7))

    # 5 sweep + recommendation
    s = slide("Choosing the unit",
              "Rule: the smaller of quarter Kelly off the planning prior and the largest unit at which ≤3% of seasons end down 25%. 6–12 unders a week, re-sized weekly.")
    s.shapes.add_picture(str(FIG_SWEEP), Inches(0.4), Inches(2.4), width=Inches(8.4))
    text(s, 8.7, 1.7, 4.3, 5.5, [
        f"Quarter Kelly off the planning prior ({p_plan:.1%}), shrunk for 9 simultaneous bets: {qk:.2%}.",
        f"The 3% cap binds first: 1% has P(−25%) {plan10['p_m25']:.1%}; 1.5% fails at 3.8%. Unit today: 1%.",
        "",
        f"At 1%: median {money(plan10['median'])} planning / {money(n49_10['median'])} n58 / {money(pooled10['median'])} pooled. "
        f"5th pct {money(plan10['p5'])}. P(−25%) {plan10['p_m25']:.1%} / {n49_10['p_m25']:.1%} / {pooled10['p_m25']:.1%}.",
        "",
        f"0.5% is the all-weather fallback: median {money(plan05['median'])}, P(−25%) {plan05['p_m25']:.2%}.",
        "",
        "Unit size does not change the downside ratio; volume does. The unit is re-derived every Monday and heads toward 1.3% if the 2026 record holds.",
    ], 13)

    # 6 risk
    s = slide("Risk, stated plainly", "At 1% / 1% units, re-sized weekly, rest of 2026. No stop-loss.")
    table(s, 0.6, 1.7, 8.4, [
        ["measure", "planning prior", "n58 bracket", "pooled bracket"],
        ["P(season ends below $20,000)", f"{plan10['p_down']:.1%}", f"{n49_10['p_down']:.1%}", f"{pooled10['p_down']:.1%}"],
        ["P(ends below $15,000)", f"{plan10['p_m25']:.1%}", f"{n49_10['p_m25']:.1%}", f"{pooled10['p_m25']:.1%}"],
        ["P(passes through $0)", "0 of 50,000", "0 of 50,000", "0 of 50,000"],
        ["median ending bankroll", money(plan10["median"]), money(n49_10["median"]), money(pooled10["median"])],
        ["5th percentile", money(plan10["p5"]), money(n49_10["p5"]), money(pooled10["p5"])],
        ["95th percentile", money(plan10["p95"]), money(n49_10["p95"]), money(pooled10["p95"])],
        ["worst single week, median", money(plan10["worst_week_med"]), money(n49_10["worst_week_med"]), money(pooled10["worst_week_med"])],
        ["total staked, 12 weeks", money(plan10["staked"]), money(n49_10["staked"]), money(pooled10["staked"])],
    ], col_w=[3.2, 1.8, 1.7, 1.7], size=13)
    text(s, 9.3, 1.8, 3.7, 5, [
        "About three seasons in ten end below $20,000. That is mostly not knowing the true win rate, which one season cannot average away.",
        "",
        "A 10% mid-season drawdown happens in about a third of seasons at 1%; a 20% drawdown in one in twenty.",
        "",
        "Same-Saturday correlation is assumed (ρ = 0.10), not measured.",
        "",
        "Stress-tested under the 3% cap: 1% passes 15 of 25 skeptical scenarios and the combined case on the planning prior; 0.5% passes all 25.",
    ], 13)

    # 7 does not support
    s = slide("What the numbers do not support")
    text(s, 0.6, 1.5, 12, 5.5, [
        "• Greenline as independently validated. n=58 in 2026, interval 42.5–67.3%. The planning prior is half personal history of the same signal.",
        "• The 2027 numbers as a forecast. They assume the edge persists unchanged on 2025's schedule.",
        "• Golf. No record, no price, no volume. A placeholder leg until graded.",
        "• A reproducible selection rule. 'Bet 6–12 of the week's flags' is a volume plan; no script picks which ones.",
        "• Kelly as today's rule. Quarter Kelly is 1.3%; the 3% drawdown cap binds at 1%. That is where the unit is headed if the record holds.",
        "• The negative cross-leg correlation as a hedge. A common model-or-market failure that hurts both legs is not modeled.",
    ], 15)

    # 8 cadence
    s = slide("What the money does each week")
    table(s, 0.6, 1.6, 12, [
        ["day", "step"],
        ["Wednesday", "capture Greenline flags; seed the bet ledger"],
        ["Thursday–Saturday", "bet 6–12 unders at −110 or better; over-zero board at −120 or better"],
        ["Monday", "grade flags; mark which were bet; re-derive the unit (min of quarter Kelly and the 3% cap); re-size off the bankroll"],
    ], col_w=[2.5, 9.5], size=15)
    text(s, 0.6, 3.6, 12, 3, [
        "The planning prior is fixed: 2026 flags plus the 2023–25 unders at half weight. The unit moves only by the Monday rule. Golf enters with a graded record, at the same rule.",
        "Marking which flags get bet is the one manual step. It turns '6–12 a week' from a plan into evidence.",
    ], 15)

    out = DOCS / f"{STEM}.pptx"
    prs.save(out)
    return out


def self_check() -> None:
    rows = sweep_rows()
    rec = rows[("pooled", 0.005)], rows[("n58", 0.005)]
    assert all(r["p_m25"] <= 0.01 and r["p_bust"] == 0 for r in rec), rec
    assert all(r["median"] > 20_000 for r in rec)
    assert FIG_GROWTH.exists() and FIG_SWEEP.exists()
    assert "gift" in (DOCS / f"{STEM}.md").read_text(encoding="utf-8").lower()
    print("self-check OK")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-check", action="store_true")
    ap.add_argument("--no-pdf", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        self_check()
        return
    print("wrote", build_pptx())
    if not args.no_pdf:
        print("wrote", build_pdf())


if __name__ == "__main__":
    sys.exit(main())
