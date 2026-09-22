"""Search the pooled Greenline totals for a bettable edge x band rule, and test the winner honestly.

    python research/totals/scripts/totals_rule_search.py
    python research/totals/scripts/totals_rule_search.py --out doc.md
    python research/totals/scripts/totals_rule_search.py --reps 5000
    python research/totals/scripts/totals_rule_search.py --self-check

The question is "what edge threshold and market-total band should I bet, over and under".
The pool is 324 graded picks (`pool_totals_record.py`), and a 2 x 6 x 5 grid over it is 60
cells, so the search WILL produce a cell near 65%. Everything here exists to decide whether
that cell means anything.

TWO DESIGN CHOICES THAT DECIDE THE ANSWER

  BANDS ARE PRE-REGISTERED, NOT REUSED. `greenline_unders.BANDS` is tempting and wrong: its
  boundaries carry the personal 2023-25 under record in the table itself, and those
  boundaries were drawn looking at that record. Since the personal unders overlap the
  Greenline board (7 of 12 where checkable -- greenline-totals-pooled-2026-09-22.md), reusing
  them is a threshold chosen partly on the evaluation sample, which
  `docs/model-evaluation-standard.md` treats as invalidating. Fixed round 5-point bins here,
  chosen for being round.

  EDGE IS RANKED WITHIN ERA, NOT CUT AT RAW VALUES. PFF's `value` is not on one scale across
  eras: 2020 tops out at 0.029 while 2026 reaches 0.053, so a raw "4%+" bin is 22 of 24 a
  2026 week-2-3 result wearing an edge label. Raw bins are printed as description with their
  era counts visible; the inference runs on within-era quintiles.

THE TESTS THAT DECIDE IT

  MAX-CELL PERMUTATION. Shuffling results within era preserves each era's win rate and every
  cell size, so the null is "no cell carries signal" with the pool's real structure intact.
  The observed best cell is scored against the distribution of the best cell under that null.
  A best cell that a shuffle beats half the time is a number, not a rule.

  WALK-FORWARD BOTH WAYS. Pick the rule on 2020+exports, bet it in 2026; then pick it on 2026
  and bet it backwards. A rule that only survives in the half it was chosen on is the search,
  not the game.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from greenline_bet_stats import heterogeneity  # noqa: E402
from greenline_season_review import BREAK_EVEN, mde, wilson  # noqa: E402
from pool_totals_record import DASH, load  # noqa: E402

ERAS = ["2020 PFF_hist", "2022-23 exports", "2026 flags"]

# Round 5-point bins, deliberately NOT greenline_unders.BANDS -- see the module docstring.
BANDS = [("<45", None, 45), ("45-49.5", 45, 50), ("50-54.5", 50, 55),
         ("55-59.5", 55, 60), ("60-64.5", 60, 65), ("65+", 65, None)]

# Descriptive only. The inference uses within-era quintiles.
RAW_BINS = [("<1%", None, 0.01), ("1-2%", 0.01, 0.02), ("2-3%", 0.02, 0.03),
            ("3-4%", 0.03, 0.04), ("4%+", 0.04, None)]

MIN_CELL = 20   # a cell smaller than this is not a candidate rule, whatever it hit

# The one hypothesis this search registers, frozen 2026-09-22. Quintiles cannot BE the rule:
# a quintile boundary is recomputed from whatever picks exist when it is scored, so a pick
# that is Q5 at kickoff can be Q4 by December and the record has no fixed referent. The 2026
# weeks 2-3 Q5 cut fell at value 0.040035, which is PFF's displayed 4.0%; freezing that raw
# number makes a week-4 pick classifiable from its own capture row before kickoff.
REGISTERED_CUT = 0.04
REGISTERED_N = 56      # prospective above-cut unders before the first look -- see report()


def band_of(line: float) -> str:
    for lab, lo, hi in BANDS:
        if (lo is None or line >= lo) and (hi is None or line < hi):
            return lab
    raise ValueError(line)


def raw_bin(v: float) -> str:
    for lab, lo, hi in RAW_BINS:
        if (lo is None or v >= lo) and (hi is None or v < hi):
            return lab
    raise ValueError(v)


def rows() -> list[dict]:
    """Graded, priced-side-known picks with an edge, tagged with band and within-era quintile."""
    out = [dict(r, band=band_of(r["line"]), raw=raw_bin(r["value"]), win=r["result"] == "win")
           for r in load() if r["result"] != "push" and r["value"] is not None
           and r["line"] is not None]
    for era in ERAS:                     # quintile of PFF's edge WITHIN its own era
        e = sorted((r for r in out if r["era"] == era), key=lambda r: r["value"])
        for i, r in enumerate(e):
            r["q"] = f"Q{min(5, 1 + i * 5 // len(e))}"
    return out


def rec(rs: list[dict]) -> tuple[int, int, float]:
    w = sum(r["win"] for r in rs)
    return w, len(rs) - w, (w / len(rs) if rs else 0.0)


def line_of(label: str, rs: list[dict], pad: int = 22) -> str:
    w, l, h = rec(rs)
    if not rs:
        return f"| {label} | 0 | -- | -- | -- |"
    lo, hi = wilson(w, len(rs))
    return (f"| {label} | {len(rs)} | {w}-{l} | {h * 100:.1f}% | {lo * 100:.1f} – {hi * 100:.1f} "
            f"| {mde(len(rs)) * 100:.1f}% |")


def cells(rs: list[dict], keys=("side", "band", "q")) -> dict:
    out: dict[tuple, list[dict]] = {}
    for r in rs:
        out.setdefault(tuple(r[k] for k in keys), []).append(r)
    return out


def best_cell(rs: list[dict], min_n: int = MIN_CELL) -> tuple:
    """The highest-hitting cell of at least `min_n` picks, plus its record."""
    best = None
    for key, v in cells(rs).items():
        if len(v) < min_n:
            continue
        w, l, h = rec(v)
        if best is None or h > best[1]:
            best = (key, h, w, l)
    return best


def permutation(rs: list[dict], reps: int, seed: int = 11) -> tuple[float, float, float]:
    """Best-cell hit rate under 'no cell carries signal', shuffling results within era.

    Returns (observed best, null median best, p). Era win rates and every cell size are
    preserved, so the null is the search itself rather than a coin flip.
    """
    obs = best_cell(rs)
    if obs is None:
        return float("nan"), float("nan"), float("nan")
    rnd = random.Random(seed)
    by_era = {e: [r for r in rs if r["era"] == e] for e in ERAS}
    nulls = []
    for _ in range(reps):
        for e, v in by_era.items():
            wins = [r["win"] for r in v]
            rnd.shuffle(wins)
            for r, w in zip(v, wins):
                r["win"] = w
        b = best_cell(rs)
        nulls.append(b[1] if b else 0.0)
    for r in rs:                          # restore the real results
        r["win"] = r["result"] == "win"
    nulls.sort()
    p = sum(1 for x in nulls if x >= obs[1]) / len(nulls)
    return obs[1], nulls[len(nulls) // 2], p


def walk_forward(rs: list[dict], train_eras: list[str], label: str) -> str:
    train = [r for r in rs if r["era"] in train_eras]
    test = [r for r in rs if r["era"] not in train_eras]
    b = best_cell(train)
    if b is None or not test:
        return f"| {label} | no cell reaches n={MIN_CELL} | -- | -- | -- |"
    key = b[0]
    held = [r for r in test if (r["side"], r["band"], r["q"]) == key]
    tw, tl, th = rec(held)
    return (f"| {label} | {' / '.join(key)} | {b[2]}-{b[3]} ({b[1] * 100:.1f}%) | "
            + (f"{tw}-{tl} ({th * 100:.1f}%)" if held else "0 picks")
            + f" | {len(held)} |")


# The only splits allowed a verdict. Four, named before looking, so Holm has a real
# denominator instead of one chosen after the grid was read.
MARGINALS = [("PFF's top edge quintile vs the rest", lambda r: r["q"] == "Q5"),
             ("the middle quintiles Q3+Q4 vs the rest", lambda r: r["q"] in ("Q3", "Q4")),
             ("market total 55+ vs below 55", lambda r: r["line"] >= 55),
             ("raw edge 4%+ vs below 4%", lambda r: r["value"] >= 0.04)]


def cmh(groups: list[tuple]) -> tuple[float, float]:
    """Cochran-Mantel-Haenszel on 2x2 tables stratified by era, continuity corrected.

    Stratifying is the whole point: a split that is really the era composition cancels here,
    where a pooled chi-square would report it as a finding.
    """
    from scipy.stats import chi2
    num = den = 0.0
    for a, b, c, d in groups:
        n = a + b + c + d
        if n < 2:
            continue
        num += a - (a + b) * (a + c) / n
        den += (a + b) * (c + d) * (a + c) * (b + d) / (n * n * (n - 1))
    stat = (abs(num) - 0.5) ** 2 / den if den > 0 else 0.0
    return stat, float(1 - chi2.cdf(stat, 1))


def strata(rs: list[dict], pred) -> list[tuple]:
    g = []
    for e in ERAS:
        s = [r for r in rs if r["era"] == e]
        t = [r for r in s if pred(r)]
        c = [r for r in s if not pred(r)]
        g.append((sum(r["win"] for r in t), len(t) - sum(r["win"] for r in t),
                  sum(r["win"] for r in c), len(c) - sum(r["win"] for r in c)))
    return g


def holm(ps: list[float]) -> list[float]:
    """Holm-adjusted p-values, returned in the input order."""
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    out = [0.0] * len(ps)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, ps[i] * (len(ps) - rank)))
        out[i] = running
    return out


def roi(rs: list[dict], flat: bool = False) -> str:
    """ROI over the price-bearing rows only. The exports carry no price at all."""
    p = [r for r in rs if r["payout"] is not None]
    if not p:
        return "no price"
    u = sum(((DASH if flat else r["payout"]) if r["win"] else -1.0) for r in p)
    return f"{u:+.2f}u, {u / len(p) * 100:+.1f}% ({len(p)})"


def named_cells(unders: list[dict]) -> list[str]:
    """The intersection people actually ask about, with the era breakdown that reads it.

    `55+ and under 4%` is not one of the four pre-registered splits -- it is the INTERSECTION
    of two of them, asked for after the grid was read. It is reported because it gets asked,
    with the one table that settles it.
    """
    cell = [r for r in unders if r["line"] >= 55 and r["value"] < REGISTERED_CUT]
    comp = [("market total 55+", [r for r in unders if r["line"] >= 55]),
            ("edge below 4%", [r for r in unders if r["value"] < REGISTERED_CUT]),
            ("**both: 55+ and below 4%**", cell),
            ("all unders, for contrast", unders)]
    L = ["", "## The 55+ and sub-4% unders, asked for by name", "",
         "| population | n | W-L | hit% | Wilson 95% | mde% | ROI (priced n) |",
         "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for lab, s in comp:
        w, l, h = rec(s)
        lo, hi = wilson(w, len(s))
        L.append(f"| {lab} | {len(s)} | {w}-{l} | {h * 100:.1f}% | {lo * 100:.1f} – {hi * 100:.1f} "
                 f"| {mde(len(s)) * 100:.1f}% | {roi(s)} |")
    stat, p, df = heterogeneity({e: [r for r in cell if r["era"] == e] for e in ERAS})
    L += ["", "### The same cell, era by era", "",
          "| era | n | W-L | hit% | ROI (priced n) |", "| --- | ---: | ---: | ---: | ---: |"]
    for e in ERAS:
        s = [r for r in cell if r["era"] == e]
        w, l, h = rec(s)
        L.append(f"| {e} | {len(s)} | {w}-{l} | {h * 100:.1f}% | {roi(s)} |")
    L += ["", f"**Chi-square across eras: {stat:.2f} on {df} df, p {p:.3f}.** The pooled board "
          "passes this same test at p 0.91 — it really is one thing across six years. This cell "
          "does not. Its headline rate is an average over eras that differ, so quoting it as a "
          "rate is quoting a number that describes none of them.", "",
          f"Its return is in the same place: the ROI is carried by the {len([r for r in cell if r['era'] == '2026 flags'])} "
          "2026 picks, and the 2020 rows underneath it are priced at PFF's own published "
          "break-even rather than a book's.", ""]
    return L


def report(rs: list[dict], reps: int) -> str:
    hdr = "| split | n | W-L | hit% | Wilson 95% | mde% |\n| --- | ---: | ---: | ---: | ---: | ---: |"
    L = [f"`research/totals/scripts/totals_rule_search.py`. {len(rs)} graded Greenline totals "
         f"picks with an edge and a line. Break-even {BREAK_EVEN * 100:.2f}%. A cell must hold "
         f"at least {MIN_CELL} picks to count as a candidate rule.", "",
         "## The diagnostic that comes first", "",
         "PFF's `value` is not one scale across eras and the market totals PFF flags move with "
         "the era too, so before any grid: who is actually in each bin.", "",
         "| raw edge bin | " + " | ".join(ERAS) + " | total |",
         "| --- | ---: | ---: | ---: | ---: |"]
    for lab, _, _ in RAW_BINS:
        c = [sum(1 for r in rs if r["raw"] == lab and r["era"] == e) for e in ERAS]
        L.append(f"| {lab} | " + " | ".join(str(x) for x in c) + f" | {sum(c)} |")
    L += ["", "| market-total band | " + " | ".join(ERAS) + " | total |",
          "| --- | ---: | ---: | ---: | ---: |"]
    for lab, _, _ in BANDS:
        c = [sum(1 for r in rs if r["band"] == lab and r["era"] == e) for e in ERAS]
        L.append(f"| {lab} | " + " | ".join(str(x) for x in c) + f" | {sum(c)} |")
    L += ["", "**Read this before the records below.** The raw 3-4% and 4%+ bins hold no 2020 "
          "picks at all, and 22 of the 24 picks above 4% are 2026 weeks 2-3. The 60-64.5 band "
          "is 53 of 76 2020 and the 45-54.5 bands are mostly 2026. Any raw-edge or band "
          "ordering below is therefore partly an era contrast wearing an edge label, which is "
          "why the inference runs on within-era quintiles.", ""]

    for side in ("under", "over"):
        S = [r for r in rs if r["side"] == side]
        L += [f"## {side.capitalize()}s — n={len(S)}", "",
              "### By within-era edge quintile (Q5 = PFF's strongest edges that era)", "", hdr]
        for q in ("Q1", "Q2", "Q3", "Q4", "Q5"):
            L.append(line_of(q, [r for r in S if r["q"] == q]))
        L += ["", "### By market-total band (pre-registered 5-point bins)", "", hdr]
        for lab, _, _ in BANDS:
            L.append(line_of(lab, [r for r in S if r["band"] == lab]))
        L += ["", "### By raw edge bin (descriptive — see the era counts above)", "", hdr]
        for lab, _, _ in RAW_BINS:
            L.append(line_of(lab, [r for r in S if r["raw"] == lab]))
        L.append("")

    L += ["## The 2 x 6 x 5 grid, printed and not interpreted", "",
          f"60 cells over {len(rs)} picks. Cells at or above n={MIN_CELL} are marked `*` and are "
          "the only ones the search may pick.", "",
          "| side | band | Q1 | Q2 | Q3 | Q4 | Q5 |", "| --- | --- | --- | --- | --- | --- | --- |"]
    g = cells(rs)
    for side in ("under", "over"):
        for lab, _, _ in BANDS:
            row = []
            for q in ("Q1", "Q2", "Q3", "Q4", "Q5"):
                v = g.get((side, lab, q), [])
                w, l, h = rec(v)
                row.append("—" if not v else
                           f"{w}-{l}{'*' if len(v) >= MIN_CELL else ''}")
            L.append(f"| {side} | {lab} | " + " | ".join(row) + " |")

    obs, null_med, p = permutation(rs, reps)
    b = best_cell(rs)
    L += ["", "## Does the best cell survive the search that found it?", ""]
    if b is None:
        L += [f"**No cell in the grid reaches n={MIN_CELL}.** The grid is too thin to name a "
              "rule at all; that is the answer, not a step toward one.", ""]
    else:
        L += [f"Best qualifying cell: **{' / '.join(b[0])}**, {b[2]}-{b[3]} "
              f"({obs * 100:.1f}%), n={b[2] + b[3]}.", "",
              f"Shuffling results within era {reps:,} times — which holds each era's win rate "
              f"and every cell size fixed, so the only thing destroyed is the cell-level signal "
              f"— the best cell is typically **{null_med * 100:.1f}%**, and reaches "
              f"{obs * 100:.1f}% or better in **{p * 100:.1f}%** of shuffles "
              f"(**p {p:.3f}**).", "",
              ("**A search over this grid finds a cell this good about as often when there is "
               "nothing there.** The best cell is the search, not a rule."
               if p >= 0.05 else
               "**The best cell beats what the search alone produces.** That is necessary, not "
               "sufficient — see the walk-forward below."), ""]

    U = [r for r in rs if r["side"] == "under"]
    stats = [(lab, strata(U, fn)) for lab, fn in MARGINALS]
    ps = [cmh(g)[1] for _, g in stats]
    adj = holm(ps)
    L += ["", "## Pre-registered marginal splits, stratified by era", "",
          "Four splits, on the unders only because the overs cannot carry one. Each is tested "
          "with Cochran-Mantel-Haenszel across the three eras rather than pooled, so a split "
          "that is really era composition cancels instead of reporting itself as a finding. "
          "Holm across the four.", "",
          "| split | takes | leaves | CMH p | Holm p |",
          "| --- | ---: | ---: | ---: | ---: |"]
    for (lab, g), p, q in zip(stats, ps, adj):
        a, b = sum(x[0] for x in g), sum(x[1] for x in g)
        c, d = sum(x[2] for x in g), sum(x[3] for x in g)
        L.append(f"| {lab} | {a}-{b} ({a / (a + b) * 100:.1f}%) | {c}-{d} "
                 f"({c / (c + d) * 100:.1f}%) | {p:.3f} | {q:.3f} |")
    survivors = [lab for (lab, _), q in zip(stats, adj) if q < 0.05]
    L += ["", (f"**Nothing survives Holm** (smallest adjusted p {min(adj):.3f}). "
               "The strongest raw split is the one the edge-cap doc already dropped in "
               "September on a ninth of the sample, and it is still short of significance "
               "with the sample tripled."
               if not survivors else
               f"**Survives Holm: {', '.join(survivors)}.**"), ""]

    L += named_cells(U)

    L += ["## Walk-forward — does the rule survive being chosen elsewhere?", "",
          "| direction | rule chosen | on the training half | on the held-out half | held-out n |",
          "| --- | --- | ---: | ---: | ---: |",
          walk_forward(rs, ["2020 PFF_hist", "2022-23 exports"], "2020+exports → 2026"),
          walk_forward(rs, ["2026 flags"], "2026 → 2020+exports"), ""]

    above = [r for r in U if r["value"] >= REGISTERED_CUT]
    below = [r for r in U if r["value"] < REGISTERED_CUT]
    aw, al, ah = rec(above)
    bw, bl, bh = rec(below)
    q5cut = min((r["value"] for r in rs if r["era"] == "2026 flags" and r["q"] == "Q5"),
                default=float("nan"))
    L += ["## The one hypothesis this registers", "",
          f"**Unders with PFF `total_best_value` >= {REGISTERED_CUT} lose to unders below it.** "
          f"The 2026 weeks 2-3 top-quintile boundary sits at {q5cut:.6f}, i.e. PFF's displayed "
          f"4.0%, so the quintile split and this raw cut are the same line — and the raw cut is "
          "the one that can be applied to a capture row before kickoff. A quintile cannot be "
          "the rule: its boundary is recomputed from whatever picks exist when it is scored, so "
          "a pick that is Q5 in September can be Q4 in December.", "",
          f"Prior (not part of the test): {aw}-{al} ({ah * 100:.1f}%) at or above the cut "
          f"against {bw}-{bl} ({bh * 100:.1f}%) below, over all three eras.", "",
          f"**Stopping rule: no look until {REGISTERED_N} prospective above-cut unders have "
          "graded**, counting from 2026 week 4 forward and excluding everything above. That n "
          f"powers the observed {(bh - ah) * 100:.0f}-point gap at 80% with the roughly 2:1 "
          "below:above split the board produces. If the true gap is 10 points rather than 20 "
          "it needs about 300 above-cut picks and this season cannot settle it — that is the "
          "honest ceiling, not a reason to peek sooner.", ""]

    O = [r for r in rs if r["side"] == "over"]
    big = max((len(v) for k, v in cells(rs).items() if k[0] == "over"), default=0)
    L += ["## Overs are not answerable", "",
          f"{len(O)} graded over picks, largest grid cell {big}. A single over cell would need "
          f"about {mde(big) * 100:.0f}% to be distinguishable from break-even at that size, and "
          f"the whole over set needs {mde(len(O)) * 100:.1f}%. No overs rule is estimable here. "
          "The honest output is that bound, not a rule with a caveat attached, because a rule "
          "with a caveat gets bet.", ""]
    return "\n".join(L)


def self_check() -> None:
    assert band_of(44.5) == "<45" and band_of(45) == "45-49.5" and band_of(65) == "65+"
    assert raw_bin(0.0) == "<1%" and raw_bin(0.04) == "4%+" and raw_bin(0.039) == "3-4%"

    rs = rows()
    assert len(rs) == 324, len(rs)
    for era in ERAS:                      # quintiles are within-era and roughly even
        n = [sum(1 for r in rs if r["era"] == era and r["q"] == q) for q in
             ("Q1", "Q2", "Q3", "Q4", "Q5")]
        assert max(n) - min(n) <= 1, (era, n)
        vals = {q: [r["value"] for r in rs if r["era"] == era and r["q"] == q]
                for q in ("Q1", "Q5")}
        assert max(vals["Q1"]) <= min(vals["Q5"]), era   # Q5 really is the strong end

    # The permutation must restore the real results, or every later number is shuffled.
    before = [r["win"] for r in rs]
    permutation(rs, 20)
    assert [r["win"] for r in rs] == before

    # A planted cell must be detectable, or the test proves nothing by failing to fire.
    biggest = max(cells(rs).items(), key=lambda kv: len(kv[1]))[0]
    planted = [dict(r, win=True) if (r["side"], r["band"], r["q"]) == biggest else dict(r)
               for r in rs]
    b = best_cell(planted)
    assert b and b[0] == biggest and b[1] == 1.0, (b, biggest)

    assert best_cell(rs, min_n=10_000) is None   # nothing qualifies at an absurd floor

    # The registered cut must stay where it was frozen, and must still be the 2026 Q5
    # boundary rounded to PFF's displayed precision. A reparse that moves either fails here
    # rather than silently redefining the hypothesis.
    q5 = min(r["value"] for r in rs if r["era"] == "2026 flags" and r["q"] == "Q5")
    assert REGISTERED_CUT == 0.04 and abs(q5 - 0.040035076) < 1e-9, (REGISTERED_CUT, q5)
    ua = [r for r in rs if r["side"] == "under" and r["value"] >= REGISTERED_CUT]
    assert (sum(r["win"] for r in ua), len(ua)) == (8, 24), (sum(r["win"] for r in ua), len(ua))

    U = [r for r in rs if r["side"] == "under"]
    cell = [r for r in U if r["line"] >= 55 and r["value"] < REGISTERED_CUT]
    w = sum(r["win"] for r in cell)
    assert (w, len(cell)) == (110, 191), (w, len(cell))
    e26 = [r for r in cell if r["era"] == "2026 flags"]
    assert (sum(r["win"] for r in e26), len(e26)) == (24, 31)   # the cell IS 2026
    assert heterogeneity({e: [r for r in cell if r["era"] == e] for e in ERAS})[1] < 0.05

    assert holm([0.01, 0.04]) == [0.02, 0.04]
    assert holm([0.5, 0.5, 0.5]) == [1.0, 1.0, 1.0]
    # CMH must cancel a split that is purely era composition: two eras, different base
    # rates, the split perfectly confounded with era and carrying no within-era signal.
    flat = [(10, 10, 0, 0), (0, 0, 6, 14)]
    assert cmh(flat)[1] > 0.5, cmh(flat)
    # ...and must fire on the same effect present inside both strata.
    real = [(18, 2, 10, 10), (18, 2, 10, 10)]
    assert cmh(real)[1] < 0.01, cmh(real)
    print("self-check ok")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--reps", type=int, default=4000)
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args()
    if a.self_check:
        return self_check()
    text = report(rows(), a.reps)
    if a.out:
        a.out.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {a.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
