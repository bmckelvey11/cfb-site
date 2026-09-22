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

  Every pooled row is one Greenline totals pick, graded at the number in its own capture.
  Populations are flag boards, not published lists: the 2026 under lists (36 in week 2,
  22 in week 3) are a NESTED subset of the 2026 flags and are reported separately, never
  added in, or those picks would count twice.

  THE 2023-25 PERSONAL UNDERS ARE A COMPARISON STRATUM, NOT A POOL MEMBER. They have long
  been described as mostly the same Greenline flags taken as bets. `overlap()` measures
  that for the first time, on the only days where both a Greenline board and a book bet
  exist, and it comes back 7 of 12 -- with 3 of the 12 betting the side Greenline flagged
  AGAINST. A bet opposing the vendor is not that vendor's pick at a different price, so
  adding the set to the pool would average vendor skill with a different selector's and
  would make the homogeneity test test the wrong hypothesis. It gets its own record, its
  own interval, and a head-to-head against the pool.

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
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bankroll" / "scripts"))
from cfb_paths import DB_PATH, INGEST  # noqa: E402
from greenline_bet_log import book_totals  # noqa: E402  -- the ledger owns the team resolver
from greenline_season_review import BREAK_EVEN, decimal, mde, personal_totals, wilson  # noqa: E402
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
                    "game_id": (r["game_id"] or "").split(".")[0],
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


def personal_unders() -> list[dict]:
    """The 2023-25 book unders, in the same row shape. NOT a pool member -- see `overlap()`.

    These carry the price actually paid, so unlike the exports they can carry a return.
    The 30 personal overs in the same seasons are excluded: the question asked of this set
    has always been about the unders.
    """
    out = []
    for season in (2023, 2024, 2025):
        for r in personal_totals(season):
            if r["side"] != "under" or r["price"] is None:
                continue
            out.append({"era": "2023-25 personal unders", "season": season, "date": r["date"],
                        "game": r["game"], "side": "under", "line": r["line"], "value": None,
                        "result": r["result"], "win": r["result"] == "win",
                        "payout": decimal(r["price"]) - 1, "price_source": "book odds paid"})
    return out


def overlap(personal: list[dict], greenline: list[dict]) -> dict:
    """How much of the personal set is actually a Greenline pick, on the days both cover.

    The only slates where this is checkable are the three 2022-23 export days, because no
    Greenline flag archive exists for 2024 or 2025. Both sides resolve to a CFBD team-id
    pair -- `book_totals()` from the ledger for the book export, `core.fact_game` for the
    archive -- because the two sources disagree on dozens of abbreviations.
    """
    import duckdb

    board_days = {r["date"] for r in greenline}
    ids = [r["game_id"] for r in greenline if r["game_id"]]
    con = duckdb.connect(str(DB_PATH), read_only=True)
    teams = {str(g): frozenset((str(h), str(a))) for g, h, a in con.execute(
        "select game_id, home_team_id, away_team_id from core.fact_game where game_id in "
        f"({','.join(ids) or 'null'})").fetchall()}
    con.close()
    board = {}
    for r in greenline:
        t = teams.get(r["game_id"])
        if t:
            board[(r["date"], t)] = r

    book = {(b["date"], b["game"]): b["teams"] for b in book_totals()}
    same = opposite = absent = unresolved = 0
    for r in personal:
        if r["date"] not in board_days:
            continue
        t = book.get((r["date"], r["game"]))
        if t is None:
            unresolved += 1     # abbreviation the ledger's alias map cannot resolve
            continue
        g = board.get((r["date"], t))
        if g is None:
            absent += 1         # bet a game Greenline never flagged
        elif g["side"] == r["side"]:
            same += 1
        else:
            opposite += 1       # bet the side Greenline flagged against
    checkable = same + opposite + absent + unresolved
    return {"checkable": checkable, "same": same, "opposite": opposite, "absent": absent,
            "unresolved": unresolved, "days": len(board_days)}


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
    src = [r for r in rows if r["payout"] is not None and r["result"] != "push"]
    if len(src) < 5:
        return f"| {label} | {len(src)} | -- | -- | -- |"
    # net onto fresh dicts, never onto the pooled rows: the flat and as-priced calls share them
    priced = [dict(r, win=r["result"] == "win",
                   net=(DASH if flat else r["payout"]) if r["result"] == "win" else -1.0)
              for r in src]
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

    # The 2023-25 book unders, as a fourth stratum -- compared, never pooled in.
    per = personal_unders()
    ov = overlap(per, by_era["2022-23 exports"])
    pt, pp, pdf = heterogeneity({"greenline pool": live,
                                 "personal unders": [r for r in per if r["result"] != "push"]})
    four = heterogeneity(dict({e: [r for r in by_era[e] if r["result"] != "push"] for e in eras},
                              **{"2023-25 personal unders": [r for r in per if r["result"] != "push"]}))
    L += ["## Fourth stratum — the 2023-25 personal unders", "",
          "Kept out of the pooled row on purpose, and the overlap check below is why. This is a "
          "comparison stratum: its own record, its own interval, and a head-to-head against the "
          "Greenline pool, not a fourth era added to it. The 30 personal *overs* in the same "
          "seasons are excluded; the standing question about this set is an unders question.", "",
          "| population | n | W-L | hit% | Wilson 95% | mde% | verdict |",
          "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
          rec_row("2023-25 personal unders", per),
          rec_row("Greenline pool (for comparison)", pool),
          rec_row("Greenline pool, unders only", [r for r in pool if r["side"] == "under"]), "",
          f"Personal unders vs the Greenline pool: chi-square {pt:.2f} on {pdf} df, p {pp:.3f}. "
          f"All four strata together: chi-square {four[0]:.2f} on {four[2]} df, p {four[1]:.3f}.", "",
          "### How much of this set is even a Greenline pick?", "",
          f"Measured, not assumed, and measurable on {ov['days']} slate days only -- the three "
          "2022-23 export slates are the only pre-2026 days where a Greenline board and a book "
          "bet both exist. 2024 and 2025 have no flag archive at all, so nothing there is "
          "checkable in either direction. Both sides resolve to a CFBD team-id pair before "
          "comparing, because the book and PFF disagree on dozens of abbreviations.", "",
          f"| of the {ov['checkable']} personal unders on those days | n |", "| --- | ---: |",
          f"| Greenline flagged the same side | {ov['same']} |",
          f"| Greenline flagged the **opposite** side | {ov['opposite']} |",
          f"| Greenline never flagged the game | {ov['absent']} |",
          f"| team abbreviation unresolvable | {ov['unresolved']} |", "",
          f"So on the only slates where it can be checked, {ov['same']} of {ov['checkable']} "
          f"personal unders are a Greenline pick taken at a book price, {ov['opposite']} are a bet "
          f"*against* what Greenline flagged, and {ov['absent']} are games Greenline left alone. "
          "That is a sample of a dozen on one season and it settles nothing about 2024-25, but it "
          "is the first direct measurement of an overlap that has been asserted without one.", ""]

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
          f"{len(priced)} of {len(pool)} pooled picks carry a price: 2020 at PFF's published "
          "break-even per bet, 2026 at an assumed -110. The personal unders carry the price "
          "actually paid and are shown for contrast, outside the pool. "
          "The 2022-23 exports carry none and are excluded from "
          "every number in this table -- reporting a return on them would be an integrity-gate "
          "failure, not a rounding choice. Bootstrap resamples bets, 4,000 reps.", "",
          "| population | n | units (95%) | ROI | ROI 95% |",
          "| --- | ---: | ---: | ---: | ---: |",
          money_row("priced pool", priced),
          money_row("2020 PFF_hist", by_era["2020 PFF_hist"]),
          money_row("2026 flags (assumed -110)", by_era["2026 flags"]),
          money_row("2026 under lists (nested)", nested),
          money_row("2023-25 personal unders (not pooled)", per), "",
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

    # The line choice is the thing being validated, so pin where it actually bites: the 2020
    # rows whose market_line and greenline_line grade differently. market_line must win all of
    # them against PFF's published result, or the same rule cannot be carried to the exports.
    disc = 0
    for r in csv.DictReader(ARCHIVE.open(encoding="utf-8")):
        if r["market"] != "total" or r["snapshot"] != "open_greenline" or r["is_greenline_pick"] != "True":
            continue
        m, g = num(r["market_line"]), num(r["greenline_line"])
        hp, ap = num(r["home_points"]), num(r["away_points"])
        if None in (m, g, hp, ap) or m == g:
            continue
        if grade(hp + ap, m, r["side"]) != grade(hp + ap, g, r["side"]):
            disc += 1
            assert grade(hp + ap, m, r["side"])[0].upper() == r["bet_result"], r
    assert disc == 3, disc

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

    per = personal_unders()
    tp = tally(per)
    assert (tp["w"], tp["l"]) == (114, 87), tp
    assert all(r["side"] == "under" for r in per)          # overs excluded by scope
    assert all(r["payout"] is not None for r in per)       # real book odds, so ROI is legitimate
    assert not any(r["era"] == "2023-25 personal unders" for r in pool), "never a pool member"
    ov = overlap(per, archive_rows("export", "2022-23 exports"))
    assert ov["same"] + ov["opposite"] + ov["absent"] + ov["unresolved"] == ov["checkable"]
    # The standing caveat says these were "mostly the same Greenline flags". Where it is
    # checkable it is 7 of 12, with 3 taking the side Greenline flagged against.
    assert (ov["same"], ov["opposite"], ov["absent"], ov["checkable"]) == (7, 3, 2, 12), ov
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
