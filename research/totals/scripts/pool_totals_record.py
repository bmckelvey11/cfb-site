"""Pool every graded PFF Greenline totals pick across eras and ask what the pool says.

    python research/totals/scripts/pool_totals_record.py
    python research/totals/scripts/pool_totals_record.py --out doc.md
    python research/totals/scripts/pool_totals_record.py --self-check

Three graded corpora exist and each has been reported on its own, where every split sat
below the win rate its own n could detect. This concatenates them -- 2020 PFF_hist, the
2022-23 export slates, and the 2026 weekly captures through week 3 -- so the question
becomes whether the *pooled* n clears its own floor, and whether the three eras are even
consistent enough to pool.

WHAT IS AND IS NOT POOLED

  Every row is one Greenline totals pick, graded at the number in its own capture.
  Populations are flag boards, not published lists: the 2026 under lists (36 in week 2,
  22 in week 3) are a NESTED subset of the 2026 flags and are reported separately, never
  added in, or those picks would count twice.

  ROI IS NOT POOLED OVER EVERYTHING. The 2022-23 exports carry no price at all
  (`breakeven_prob` NULL on every row), which is an integrity-gate failure under
  `docs/model-evaluation-standard.md` -- a record is reportable, a return is not. So the
  record table spans all three eras and the money table spans the two that have a price,
  with the 2026 leg at an assumed -110 rather than an observed one.

SOURCES

  2020 and 2022-23 both come from `greenline_history_archive.csv`, graded from the CFBD
  finals carried on the archive rows. On 2020 that grading agrees with PFF's own published
  `bet_result` on all 131 picks, which is what licenses using the same rule on the exports,
  where PFF published no result. 2026 comes from `greenline_graded.csv` as
  `grade_greenline.py` wrote it, with kickoff dates joined from `pff_schedule_2026.csv`
  for the day clustering.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cfb_paths import INGEST  # noqa: E402
from greenline_season_review import BREAK_EVEN, mde, wilson  # noqa: E402
from greenline_bet_stats import beta_post, binom_p, bootstrap, clustered_se, heterogeneity  # noqa: E402

IN_DIR = INGEST / "pff_scoreboard"
ARCHIVE = IN_DIR / "greenline_history_archive.csv"
GRADED_2026 = IN_DIR / "greenline_graded.csv"
SCHEDULE_2026 = IN_DIR / "pff_schedule_2026.csv"
UNDERS_2026 = "greenline_unders_2026_w{week}.csv"

DASH = 100 / 110  # -110 payout per unit risked


def num(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


def grade(total: float, line: float, side: str) -> str:
    if total == line:
        return "push"
    return "win" if (total > line) == (side == "over") else "loss"


def archive_rows(snapshot: str, era: str) -> list[dict]:
    """Greenline totals picks from one archive snapshot, graded off the CFBD finals on the row."""
    out = []
    for r in csv.DictReader(ARCHIVE.open(encoding="utf-8")):
        if r["market"] != "total" or r["snapshot"] != snapshot or r["is_greenline_pick"] != "True":
            continue
        line, hp, ap = num(r["market_line"]), num(r["home_points"]), num(r["away_points"])
        if line is None or hp is None or ap is None:
            continue  # ungraded: no CFBD match, so no final
        be = num(r["breakeven_prob"])
        out.append({"era": era, "season": int(float(r["season"])) if r["season"] else None,
                    "date": (r["kickoff_utc"] or "")[:10], "side": r["side"], "line": line,
                    "value": num(r["difference"]), "result": grade(hp + ap, line, r["side"]),
                    "payout": (1 / be - 1) if be else None, "price_source":
                    "PFF break-even" if be else None})
    return out


def rows_2026() -> list[dict]:
    sched = {s["pff_game_id"]: s for s in csv.DictReader(SCHEDULE_2026.open(encoding="utf-8"))}
    out = []
    for r in csv.DictReader(GRADED_2026.open(encoding="utf-8")):
        g = sched.get(r["pff_game_id"], {})
        out.append({"era": "2026 flags", "season": int(r["season"]), "week": r["pff_week"],
                    "game_id": r["pff_game_id"], "date": (g.get("kickoff_raw") or "")[:10],
                    "side": r["side"], "line": num(r["line"]), "value": num(r["value"]),
                    "result": r["result"], "payout": DASH, "price_source": "assumed -110"})
    return out


def load() -> list[dict]:
    return (archive_rows("open_greenline", "2020 PFF_hist")
            + archive_rows("export", "2022-23 exports")
            + rows_2026())


def under_list_2026(pool: list[dict]) -> list[dict]:
    """The published under lists, as the nested subset of the 2026 flags that they are."""
    keep: set[tuple[str, str]] = set()
    for week in ("2", "3"):
        p = IN_DIR / UNDERS_2026.format(week=week)
        if not p.exists():
            continue
        for r in csv.DictReader(p.open(encoding="utf-8")):
            keep.add((week, r["game_id"]))
    return [r for r in pool if r["era"] == "2026 flags" and (r["week"], r["game_id"]) in keep]


def tally(rows: list[dict]) -> dict:
    w = sum(1 for r in rows if r["result"] == "win")
    l = sum(1 for r in rows if r["result"] == "loss")
    p = sum(1 for r in rows if r["result"] == "push")
    n = w + l
    lo, hi = wilson(w, n) if n else (0.0, 0.0)
    return {"w": w, "l": l, "push": p, "n": n, "hit": w / n if n else 0.0,
            "lo": lo, "hi": hi, "mde": mde(n) if n else float("nan")}


def rec_row(label: str, rows: list[dict]) -> str:
    t = tally(rows)
    if not t["n"]:
        return f"| {label} | 0 | -- | -- | -- | -- | -- |"
    verdict = "clears floor" if t["hit"] >= t["mde"] else "below floor"
    return (f"| {label} | {t['n']} | {t['w']}-{t['l']}"
            + (f" ({t['push']}P)" if t["push"] else "")
            + f" | {t['hit'] * 100:.1f}% | {t['lo'] * 100:.1f} – {t['hi'] * 100:.1f} | "
              f"{t['mde'] * 100:.1f}% | {verdict} |")


def money_row(label: str, rows: list[dict], flat: bool = False) -> str:
    """`flat` reprices every row at -110 instead of the price its source claims."""
    priced = [r for r in rows if r["payout"] is not None and r["result"] != "push"]
    if len(priced) < 5:
        return f"| {label} | {len(priced)} | -- | -- | -- |"
    for r in priced:
        r["net"] = (DASH if flat else r["payout"]) if r["result"] == "win" else -1.0
        r["win"] = r["result"] == "win"
    units = sum(r["net"] for r in priced)
    ulo, uhi, rlo, rhi = bootstrap(priced)
    return (f"| {label} | {len(priced)} | {units:+.2f}u ({ulo:+.1f} to {uhi:+.1f}) | "
            f"{units / len(priced) * 100:+.1f}% | {rlo * 100:+.1f} to {rhi * 100:+.1f} |")


def report(pool: list[dict]) -> str:
    eras = ["2020 PFF_hist", "2022-23 exports", "2026 flags"]
    by_era = {e: [r for r in pool if r["era"] == e] for e in eras}
    live = [r for r in pool if r["result"] != "push"]
    for r in live:
        r["win"] = r["result"] == "win"

    t = tally(pool)
    L = [f"`research/totals/scripts/pool_totals_record.py`. {len(pool)} graded Greenline totals "
         f"picks across three eras, each graded at the line in its own capture. Break-even is "
         f"{BREAK_EVEN * 100:.2f}% (-110 both ways); `mde%` is the smallest true win rate this n "
         f"could separate from break-even one-sided at alpha 0.05 with 80% power.", "",
         "## Record by era", "",
         "| population | n | W-L | hit% | Wilson 95% | mde% | verdict |",
         "| --- | ---: | ---: | ---: | ---: | ---: | --- |"]
    for e in eras:
        L.append(rec_row(e, by_era[e]))
    L.append(rec_row("**pooled**", pool))
    L.append("")

    # Are the eras consistent enough to pool at all?
    stat, p, df = heterogeneity({e: [r for r in by_era[e] if r["result"] != "push"] for e in eras})
    iid, cl, g = clustered_se(live)
    bp = binom_p(t["w"], t["n"])
    post, med, p5 = beta_post(t["w"], t["n"])
    L += ["## Is the pool one thing?", "",
          f"Chi-square across the three eras: {stat:.2f} on {df} df, p {p:.3f} -- "
          + ("the eras are consistent with a single win rate, so pooling them is defensible."
             if p >= 0.05 else
             "the eras differ more than one win rate explains, so the pooled number is an average "
             "of unlike things and should not be read as a single skill estimate."), "",
          f"Pooled win rate SE is {iid * 100:.2f}pp iid and {cl * 100:.2f}pp clustered by game day "
          f"({g} distinct days); same-day games share weather and slate-wide shocks, so the "
          f"clustered figure is the honest one.", "",
          f"One-sided exact binomial against break-even: p {bp:.3f}. Flat-prior posterior "
          f"probability the true rate beats break-even: {post * 100:.0f}% (median {med * 100:.1f}%, "
          f"5th percentile {p5 * 100:.1f}%).", ""]

    L += ["## Side and era splits", "",
          "| split | n | W-L | hit% | Wilson 95% | mde% | verdict |",
          "| --- | ---: | ---: | ---: | ---: | ---: | --- |"]
    for side in ("under", "over"):
        L.append(rec_row(f"all eras, {side}s", [r for r in pool if r["side"] == side]))
    for e in eras:
        for side in ("under", "over"):
            L.append(rec_row(f"{e}, {side}s", [r for r in by_era[e] if r["side"] == side]))
    L.append("")
    sstat, sp, sdf = heterogeneity({s: [r for r in live if r["side"] == s] for s in ("under", "over")})
    L += [f"Under vs over, chi-square {sstat:.2f} on {sdf} df, p {sp:.3f}.", ""]

    nested = under_list_2026(pool)
    L += ["## The published 2026 under lists (nested, not added)", "",
          "These picks are already counted in the 2026 flag row above. They are the subset PFF's "
          "positive-edge ranking published, so they answer the slate question rather than the "
          "board question, and they are shown separately for that reason only.", "",
          "| population | n | W-L | hit% | Wilson 95% | mde% | verdict |",
          "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
          rec_row("weeks 2-3 under list", nested),
          rec_row("week 2 under list", [r for r in nested if r["week"] == "2"]),
          rec_row("week 3 under list", [r for r in nested if r["week"] == "3"]), ""]

    priced = [r for r in pool if r["payout"] is not None]
    L += ["## Money, on the price-bearing rows only", "",
          f"{len(priced)} of {len(pool)} picks carry a price: 2020 at PFF's published break-even "
          "per bet, 2026 at an assumed -110. The 2022-23 exports carry none and are excluded from "
          "every number in this table -- reporting a return on them would be an integrity-gate "
          "failure, not a rounding choice. Bootstrap resamples bets, 4,000 reps.", "",
          "| population | n | units (95%) | ROI | ROI 95% |",
          "| --- | ---: | ---: | ---: | ---: |",
          money_row("priced pool", priced),
          money_row("2020 PFF_hist", by_era["2020 PFF_hist"]),
          money_row("2026 flags (assumed -110)", by_era["2026 flags"]),
          money_row("2026 under lists (nested)", nested), "",
          f"PFF's published 2020 break-evens run better than -110 on "
          f"{sum(1 for r in by_era['2020 PFF_hist'] if r['payout'] and r['payout'] > DASH)} of "
          f"{len(by_era['2020 PFF_hist'])} picks (median implied price about -107), so that leg's "
          "return is stated at the price PFF claimed, not one observed at a book. Repriced flat at "
          "-110 the same records give:", "",
          "| population | n | units (95%) | ROI | ROI 95% |",
          "| --- | ---: | ---: | ---: | ---: |",
          money_row("priced pool at flat -110", priced, flat=True),
          money_row("2020 PFF_hist at flat -110", by_era["2020 PFF_hist"], flat=True), ""]
    return "\n".join(L)


def self_check() -> None:
    assert grade(58.0, 52.5, "under") == "loss"
    assert grade(36.0, 57.5, "under") == "win"
    assert grade(44.0, 44.0, "over") == "push"
    assert grade(54.0, 50.5, "over") == "win"

    hist = archive_rows("open_greenline", "2020 PFF_hist")
    t = tally(hist)
    assert (t["w"], t["l"], t["push"]) == (71, 59, 1), t   # matches PFF's own bet_result column
    exp = tally(archive_rows("export", "2022-23 exports"))
    assert (exp["w"], exp["l"], exp["push"]) == (46, 42, 2), exp  # greenline-export-picks-graded-2026-09-21
    t26 = tally(rows_2026())
    assert (t26["w"], t26["l"]) == (58, 48), t26

    pool = load()
    nested = under_list_2026(pool)
    w2 = tally([r for r in nested if r["week"] == "2"])
    w3 = tally([r for r in nested if r["week"] == "3"])
    assert (w2["w"], w2["l"]) == (21, 15), w2   # greenline-w2-grade-2026-09-15
    assert (w3["w"], w3["l"]) == (11, 11), w3   # greenline-w3-grade-2026-09-21
    assert len(nested) < len([r for r in pool if r["era"] == "2026 flags"])  # nested, never additive

    assert all(r["payout"] is None for r in pool if r["era"] == "2022-23 exports")
    assert mde(325) < mde(106)  # a bigger pool has a lower floor
    print("self-check ok")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args()
    if a.self_check:
        return self_check()
    text = report(load())
    if a.out:
        a.out.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {a.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
