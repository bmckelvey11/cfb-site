"""Render the seed-bankroll proposal to PDF and an 8-slide deck.

    python research/bankroll/scripts/build_proposal_deliverables.py
    python research/bankroll/scripts/build_proposal_deliverables.py --self-check

Inputs: docs/seed-bankroll-proposal-2026-09-17.md, the two figures in docs/figs/,
and the sweep CSV. Outputs, next to the markdown:
    seed-bankroll-proposal-2026-09-17.pdf     markdown -> HTML -> Chrome headless print
    seed-bankroll-proposal-2026-09-17.pptx    python-pptx, numbers read from the CSV

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

DOCS = Path(__file__).resolve().parents[1] / "docs"
STEM = "seed-bankroll-proposal-2026-09-17"
SWEEP = DOCS / "bankroll-config-sweep-2026-09-17.csv"
FIG_MC = DOCS / "figs" / "mc-combined-totals-2026-09-17.png"
FIG_SWEEP = DOCS / "figs" / "bankroll-config-sweep-2026-09-17.png"
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
    """Recommended (0.5%) and 1% rows at supported coverage, keyed by (prior, unit)."""
    out = {}
    for r in csv.DictReader(open(SWEEP, encoding="utf-8")):
        if r["supported"] == "True" and float(r["gl_unit"]) in (0.005, 0.01):
            out[(r["prior"], float(r["gl_unit"]))] = {k: float(v) for k, v in r.items()
                                                        if k not in ("prior", "supported", "passes_a")}
    assert len(out) == 4, out.keys()
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
    rec_p, rec_n = rows[("pooled", 0.005)], rows[("n49", 0.005)]
    up_p, up_n = rows[("pooled", 0.01)], rows[("n49", 0.01)]

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
    text(s, 0.8, 2.2, 11.5, 1.2, "Seed bankroll: $20,000 for the rest of the 2026 season", 36, True)
    text(s, 0.8, 3.5, 11.5, 1.5, [
        "A gift that funds a betting bankroll. Nothing is owed back.",
        "Not an investment, not a loan, not a security.",
        "Every number here comes from a script in the repository and carries its uncertainty.",
    ], 18, color=MUTED)
    text(s, 0.8, 6.4, 11.5, 0.5, "Prepared September 17, 2026", 12, color=MUTED)

    # 2 the ask
    s = slide("The ask")
    table(s, 0.6, 1.6, 12, [
        ["item", "value"],
        ["amount", "$20,000"],
        ["horizon", "weeks 4–15 of the 2026 regular season, Sept 24 to Dec 12 (12 weeks)"],
        ["what it funds", "two totals strategies already running, flat stakes off the starting bankroll"],
        ["expected bets", "~99: ~88 Greenline unders, ~11 over-zero overs"],
        ["recommended stake", "Greenline $100 per bet (0.5%), over-zero $200 per bet (1%)"],
        ["afterwards", "bankroll and profit stay in the operation for 2027"],
    ], col_w=[3, 9], size=14)

    # 3 two legs
    s = slide("What gets bet: two legs, one bankroll",
              "Win rates are shown with their 95% intervals. Break-even is 52.4% at −110, 54.5% at −120.")
    table(s, 0.6, 1.7, 12.1, [
        ["", "Over-zero (floor-bias OVERs)", "Greenline totals (PFF flags, ~85% unders)"],
        ["what it is", "in-house model: totals pinned too low against heavy favorites", "vendor projection disagreeing with the market"],
        ["record", "151–83, 64.5% (58.2–70.4%), walk-forward 2016–25", "27–22, 55.1% (41–68%), 2026 wk 2; + 114–87 personal unders 2023–25"],
        ["planning win rate", "58.2%, the interval floor", "bracket: 55.0% (2026 only) to 56.4% (pooled)"],
        ["price", "−120 or better", "−110"],
        ["bets left in 2026", "~11, median +$133", "~13% of each week's flags, ~7 a week, ~88 total"],
        ["role", "better evidence, nearly spent for 2026; matters in 2027", "carries the whole 2026 projection"],
    ], col_w=[2.3, 4.9, 4.9], size=12)
    text(s, 0.6, 5.6, 12, 1.2, [
        "Conflict rule: same game flagged on opposite sides → Greenline takes it, over-zero skips it.",
        "Excluded: the spread model (research, not a bet); Greenline spreads and moneylines (21–28 and 21–25 in week 2).",
    ], 13, color=MUTED)

    # 4 projection
    s = slide("The projection: bracketed, not resolved",
              "100,000 paths, win rates drawn per path from each record. Two panels = the two defensible Greenline priors.")
    s.shapes.add_picture(str(FIG_MC), Inches(0.5), Inches(1.6), height=Inches(5.7))

    # 5 sweep + recommendation
    s = slide("Choosing the stake",
              "Largest median gain such that ≤1% of paths end down 25% and none go to zero, under both priors.")
    s.shapes.add_picture(str(FIG_SWEEP), Inches(0.4), Inches(1.6), height=Inches(5.6))
    text(s, 8.7, 1.7, 4.3, 5.5, [
        "Recommended: Greenline 0.5% ($100), over-zero 1% ($200).",
        f"Median {money(rec_p['median'])} pooled / {money(rec_n['median'])} 2026-only.",
        f"5th pct {money(rec_p['p5'])} / {money(rec_n['p5'])}. P(−25%) 0% under both.",
        "",
        "1% ($200) passes only under the pooled prior "
        f"(median {money(up_p['median'])} / {money(up_n['median'])}; P(−25%) "
        f"{up_p['p_m25']:.1%} / {up_n['p_m25']:.1%}). Upgrade path once four more weeks are graded.",
        "",
        "Stake does not change the downside ratio. Coverage does, and coverage is the unproven assumption. Conditional rows are shown, not recommended.",
    ], 13)

    # 6 risk
    s = slide("Risk, stated plainly", "At the recommended $100 / $200 stakes. Flat stakes, no stop-loss.")
    table(s, 0.6, 1.7, 8, [
        ["measure", "pooled prior", "2026-only prior"],
        ["P(season ends below $20,000)", f"{rec_p['p_down']:.1%}", f"{rec_n['p_down']:.1%}"],
        ["P(ends below $15,000)", f"{rec_p['p_m25']:.1%}", f"{rec_n['p_m25']:.1%}"],
        ["P(passes through $0)", f"{rec_p['p_bust']:.1%}", f"{rec_n['p_bust']:.1%}"],
        ["median ending bankroll", money(rec_p["median"]), money(rec_n["median"])],
        ["5th percentile", money(rec_p["p5"]), money(rec_n["p5"])],
        ["95th percentile", money(rec_p["p95"]), money(rec_n["p95"])],
        ["worst single week, median", money(rec_p["worst_week_med"]), money(rec_n["worst_week_med"])],
        ["total staked, 12 weeks", money(rec_p["staked"]), money(rec_n["staked"])],
    ], col_w=[3.6, 2.2, 2.2], size=14)
    text(s, 9.0, 1.8, 3.9, 5, [
        "Roughly one season in three ends below $20,000. That is mostly not knowing the true win rate, which a 12-week season cannot average away.",
        "",
        "One season in twenty ends worse than about −$1,900.",
        "",
        "Same-Saturday correlation is assumed (ρ = 0.10), not measured. It moves the tail by a few hundred dollars and the median not at all.",
    ], 13)

    # 7 does not support
    s = slide("What the numbers do not support")
    text(s, 0.6, 1.5, 12, 5.5, [
        "• Greenline as independently validated. n=49 in 2026, interval 41–68%. The pooled record is 80% the same signal bet in earlier seasons.",
        "• The pooled prior transferring in full. The 201 past unders sat ~6 points higher in total than the 2026 flags. Pooling probably overstates.",
        "• Any coverage above 13%. Every 'bet more flags' row assumes the picked-flag win rate applies to flags that were passed on.",
        "• A reproducible selection rule. 'Bet ~6 of 49 a week' is a volume assumption; no script picks which six.",
        "• A 2027 projection. Not modeled yet. Needs over-zero at full-season volume and a full graded Greenline season.",
        "• Compounded returns. Simultaneous kickoffs make them unachievable; everything here is flat-staked.",
    ], 15)

    # 8 cadence
    s = slide("What the money does each week")
    table(s, 0.6, 1.6, 12, [
        ["day", "step"],
        ["Wednesday", "capture Greenline flags; seed the bet ledger"],
        ["Thursday–Saturday", "bet ~6 unders at −110 or better; over-zero board at −120 or better"],
        ["Monday", "grade flags; mark which were bet; rerun the projection with the new record"],
    ], col_w=[2.5, 9.5], size=15)
    text(s, 0.6, 3.6, 12, 3, [
        "Marking which flags get bet is the one manual step and the one that resolves the biggest open question (coverage).",
        "Four more graded weeks puts the 2026 flags at n≈250 on their own. The prior stops doing the work and the stake decision gets revisited then.",
    ], 15)

    out = DOCS / f"{STEM}.pptx"
    prs.save(out)
    return out


def self_check() -> None:
    rows = sweep_rows()
    rec = rows[("pooled", 0.005)], rows[("n49", 0.005)]
    assert all(r["p_m25"] <= 0.01 and r["p_bust"] == 0 for r in rec), rec
    assert all(r["median"] > 20_000 for r in rec)
    assert FIG_MC.exists() and FIG_SWEEP.exists()
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
