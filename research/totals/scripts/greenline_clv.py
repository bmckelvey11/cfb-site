"""Closing-line value for the 2026 Greenline totals flags, against a real market close.

    python research/totals/scripts/greenline_clv.py
    python research/totals/scripts/greenline_clv.py --close consensus
    python research/totals/scripts/greenline_clv.py --tolerance 2.0 --out doc.md
    python research/totals/scripts/greenline_clv.py --self-check

WHY THIS EXISTS. Win/loss is a low-information signal: separating a 54% true rate from a
52.38% break-even needs roughly 5,900 graded picks, eight-plus seasons at this board's
volume. CLV is measured against a price rather than a coin flip, so it resolves in hundreds.
The review docs already report a CLV, but against PFF's OWN board close -- which asks
whether PFF agrees with itself. This asks whether PFF's flags lead the market.

THE DATA GATE. `core.fact_game_line` carries a Pinnacle `total_close` from the CFBD GraphQL
feed, and roughly one row in nine is corrupt: against the median close of the six or seven
other books on the same game, 160 of 193 agree within a point but 22 are off by more than 3.
Western Kentucky at Georgia reads an 82.5 total with a -66.5 spread. The game joins are
correct, so this is a feed problem, not a matching problem, and an unfiltered CLV over these
rows would measure the feed's bugs rather than PFF's skill. Every close therefore goes
through `usable_close()` before it is allowed to score anything, and the run reports what it
dropped. See greenline-findings.md, "Open question A".

SIGN CONVENTION. Positive CLV means the market moved toward the side PFF flagged, so the
captured number was better than the close:

    under  ->  capture_line - close
    over   ->  close - capture_line

COVERAGE. Pinnacle closes exist for 2026 weeks 1-3 and sparsely for late 2025. Nothing for
2020 or 2022-23, so this is a 2026-forward test and says nothing about the archive eras.
"""

from __future__ import annotations

import argparse
import csv
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bankroll" / "scripts"))
from cfb_paths import DB_PATH, INGEST  # noqa: E402
from greenline_bet_log import _flag_cfbd_ids  # noqa: E402  -- the ledger owns the PFF->CFBD map
from greenline_season_review import wilson  # noqa: E402

GRADED = INGEST / "pff_scoreboard" / "greenline_graded.csv"
SEASON = 2026
TOLERANCE = 1.0   # points of total a Pinnacle close may differ from the book median
MIN_BOOKS = 2     # other books needed before their median can judge anything

# Half a point of total is worth roughly two points of win probability at these numbers --
# the unit's standing figure, used only to put CLV points on a familiar scale.
PP_PER_POINT = 0.04


def clv_points(side: str, capture_line: float, close: float) -> float:
    """Positive = the market moved toward the flagged side, so the capture beat the close."""
    return capture_line - close if side == "under" else close - capture_line


POLICIES = ("none", "drop", "substitute", "consensus")


def usable_close(pin: float | None, others: list[float],
                 policy: str = "drop", tolerance: float | None = None) -> tuple[float | None, str]:
    """Decide which closing number, if any, this game may be scored against.

    `pin` is Pinnacle's `total_close` (None when the feed has no row or a null), `others` is
    every other book's close for the same game. Returns (close_to_use, reason), where reason
    is a short tag the report counts.

    The policy is an argument rather than a constant because whether the gate is needed at
    all is an empirical question, answered by running all four and comparing -- see
    `compare()` and the doc it writes. They differ only in what they do with a Pinnacle close
    the other books contradict:

      none        trust every Pinnacle close. The unfiltered baseline.
      drop        exclude the game. Smaller n, but every scored row is a real Pinnacle close.
      substitute  fall back to the book median. Keeps n, mixes two definitions of "close".
      consensus   never use Pinnacle at all; the book median is the close.
    """
    tol = TOLERANCE if tolerance is None else tolerance
    med = st.median(others) if others else None

    if policy == "consensus":
        if med is None or len(others) < MIN_BOOKS:
            return None, "dropped: too few books"
        return med, "consensus"

    if pin is None:
        # 9 of the 106 flags have no Pinnacle number at all. Nothing to validate, so the
        # only question is whether a consensus close is an acceptable stand-in.
        if policy == "substitute" and med is not None and len(others) >= MIN_BOOKS:
            return med, "consensus (no pinnacle row)"
        return None, "dropped: no pinnacle close"

    if policy == "none":
        return pin, "pinnacle (ungated)"

    if med is None or len(others) < MIN_BOOKS:
        # Too little evidence to convict Pinnacle. Trusting it here is deliberate: dropping
        # would throw away games for the sin of being thinly covered, which is not a reason
        # to think the number is wrong.
        return pin, "pinnacle (unchecked, too few books)"

    if abs(pin - med) <= tol:
        return pin, "pinnacle"
    if policy == "substitute":
        return med, "consensus (pinnacle rejected)"
    return None, "dropped: pinnacle disagrees with books"


def load_flags() -> list[dict]:
    ids = _flag_cfbd_ids()
    out = []
    for r in csv.DictReader(GRADED.open(encoding="utf-8")):
        teams = ids.get(r["pff_game_id"])
        if not teams:
            continue
        out.append({"pff_game_id": r["pff_game_id"], "week": r["pff_week"], "teams": teams,
                    "side": r["side"], "line": float(r["line"]), "result": r["result"],
                    "value": float(r["value"]) if r["value"] else None,
                    "matchup": f"{r['away_abbreviation']} @ {r['home_abbreviation']}"})
    return out


def load_closes() -> dict:
    """{frozenset(team_ids): {"pinnacle": float|None, "others": [float, ...]}} for the season."""
    import duckdb

    con = duckdb.connect(str(DB_PATH), read_only=True)
    rows = con.execute(
        "select cast(g.home_team_id as varchar), cast(g.away_team_id as varchar), "
        "       l.provider_key, l.total_close "
        "from core.fact_game g join core.fact_game_line l using(game_id) "
        f"where g.season = {SEASON} and l.total_close is not null").fetchall()
    con.close()
    out: dict = {}
    for h, a, prov, tc in rows:
        tc = float(tc)
        if tc != tc:                       # stg_gql numerics arrive as NaN, not NULL
            continue
        slot = out.setdefault(frozenset((h, a)), {"pinnacle": None, "others": []})
        if prov == "pinnacle":
            slot["pinnacle"] = tc
        else:
            slot["others"].append(tc)
    return out


def scored(flags: list[dict], closes: dict, prefer: str = "drop") -> tuple[list[dict], dict]:
    kept, why = [], {}
    for f in flags:
        slot = closes.get(f["teams"])
        if slot is None:
            why["dropped: no line row"] = why.get("dropped: no line row", 0) + 1
            continue
        close, reason = usable_close(slot["pinnacle"], slot["others"], prefer)
        why[reason] = why.get(reason, 0) + 1
        if close is None:
            continue
        kept.append(dict(f, close=close, close_source=reason,
                         clv=clv_points(f["side"], f["line"], close)))
    return kept, why


def summarise(rows: list[dict], label: str) -> list[str]:
    if not rows:
        return [f"| {label} | 0 | -- | -- | -- | -- |"]
    c = [r["clv"] for r in rows]
    m = st.mean(c)
    se = st.stdev(c) / len(c) ** 0.5 if len(c) > 1 else float("nan")
    beat = sum(1 for x in c if x > 0)
    lost = sum(1 for x in c if x < 0)
    lo, hi = wilson(beat, beat + lost) if beat + lost else (0.0, 0.0)
    return [f"| {label} | {len(rows)} | {m:+.2f} ± {1.96 * se:.2f} | {m * PP_PER_POINT * 100:+.1f}pp "
            f"| {beat}-{lost}-{len(c) - beat - lost} | {lo * 100:.0f}–{hi * 100:.0f}% |"]


def report(flags: list[dict], closes: dict, prefer: str) -> str:
    rows, why = scored(flags, closes, prefer)
    L = [f"`research/totals/scripts/greenline_clv.py --close {prefer}`. {len(flags)} graded "
         f"{SEASON} Greenline totals flags, scored against a market close rather than PFF's own "
         "board. Positive CLV means the market moved toward the flagged side.", "",
         "## What the gate kept and dropped", "",
         "| outcome | flags |", "| --- | ---: |"]
    for k in sorted(why, key=lambda k: (-why[k], k)):
        L.append(f"| {k} | {why[k]} |")
    L += ["", f"**{len(rows)} of {len(flags)} flags scored.** A Pinnacle close is only trusted "
          f"when it sits within {TOLERANCE} point(s) of the median of at least {MIN_BOOKS} other "
          "books on the same game; roughly one Pinnacle row in nine is corrupt in the CFBD "
          "GraphQL feed, so an unfiltered run would be scoring the feed's bugs.", "",
          "## Closing-line value", "",
          "| split | n | mean CLV (pts, 95%) | ~win prob | beat-lost-flat | beat rate 95% |",
          "| --- | ---: | ---: | ---: | ---: | ---: |"]
    L += summarise(rows, "**all flags**")
    for side in ("under", "over"):
        L += summarise([r for r in rows if r["side"] == side], f"{side}s")
    for wk in sorted({r["week"] for r in rows}):
        L += summarise([r for r in rows if r["week"] == wk], f"week {wk}")
    L += ["", "The `~win prob` column applies the unit's standing conversion — half a point of "
          "total is worth about two points of win probability — and is a scale aid, not a "
          "measurement.", "",
          "## Does beating the close predict winning the bet?", ""]
    beat = [r for r in rows if r["clv"] > 0]
    lost = [r for r in rows if r["clv"] < 0]
    for lab, s in (("flags that beat the close", beat), ("flags that lost to the close", lost)):
        if not s:
            continue
        w = sum(1 for r in s if r["result"] == "win")
        n = sum(1 for r in s if r["result"] in ("win", "loss"))
        lo, hi = wilson(w, n) if n else (0, 0)
        L.append(f"- **{lab}**: {w}-{n - w} ({w / n * 100:.1f}%, {lo * 100:.0f}–{hi * 100:.0f}%)"
                 if n else f"- {lab}: none graded")
    L += ["", "CLV and results are two views of the same picks, so this is a consistency check, "
          "not independent evidence. A board with real CLV and a losing record usually means "
          "the prices taken were worse than the numbers captured.", ""]
    return "\n".join(L)


def compare(flags: list[dict], closes: dict) -> str:
    """Does the gate change the answer? Run every policy, and tolerances, side by side.

    A gate that costs n and moves nothing is not worth having. A gate that moves the mean is
    load-bearing, and then the question is which direction is the artefact.
    """
    L = ["`research/totals/scripts/greenline_clv.py --compare`. The same 106 flags under every "
         "gate policy. If the mean CLV is stable across rows, the gate is not doing the work "
         "and the simplest policy wins; if it is not, the gate is the finding.", "",
         "| policy | scored | mean CLV (pts, 95%) | beat-lost-flat | beat rate | worst single CLV |",
         "| --- | ---: | ---: | ---: | ---: | ---: |"]
    runs = {}
    for pol in POLICIES:
        rows, _ = scored(flags, closes, pol)
        runs[pol] = rows
        if not rows:
            L.append(f"| {pol} | 0 | -- | -- | -- | -- |")
            continue
        c = [r["clv"] for r in rows]
        m = st.mean(c)
        se = st.stdev(c) / len(c) ** 0.5 if len(c) > 1 else float("nan")
        beat = sum(1 for x in c if x > 0)
        lost = sum(1 for x in c if x < 0)
        lo, hi = wilson(beat, beat + lost) if beat + lost else (0.0, 0.0)
        worst = max(c, key=abs)
        L.append(f"| `{pol}` | {len(rows)} | {m:+.2f} ± {1.96 * se:.2f} | "
                 f"{beat}-{lost}-{len(c) - beat - lost} | {beat / (beat + lost) * 100:.0f}% "
                 f"({lo * 100:.0f}–{hi * 100:.0f}) | {worst:+.1f} |")

    L += ["", "### The ungated rows the gate removes", ""]
    kept = {r["pff_game_id"] for r in runs["drop"]}
    removed = [r for r in runs["none"] if r["pff_game_id"] not in kept]
    if removed:
        L += ["| matchup | side | capture | pinnacle close | book median | CLV it would score |",
              "| --- | --- | ---: | ---: | ---: | ---: |"]
        for r in sorted(removed, key=lambda r: -abs(r["clv"]))[:10]:
            others = closes[r["teams"]]["others"]
            med = st.median(others) if others else float("nan")
            L.append(f"| {r['matchup']} | {r['side']} | {r['line']:.1f} | {r['close']:.1f} "
                     f"| {med:.1f} | {r['clv']:+.1f} |")
        c = [r["clv"] for r in removed]
        L += ["", f"{len(removed)} flags, mean CLV {st.mean(c):+.2f}, spanning {min(c):+.1f} to "
              f"{max(c):+.1f}. A total does not move that far; these are the feed's bugs "
              "wearing the shape of enormous line value.", ""]
    else:
        L += ["The gate removes nothing on this data.", ""]

    L += ["### Tolerance sensitivity (`drop` policy)", "",
          "| tolerance | scored | mean CLV | beat rate |", "| ---: | ---: | ---: | ---: |"]
    saved = TOLERANCE
    for tol in (0.5, 1.0, 2.0, 3.0, 5.0):
        globals()["TOLERANCE"] = tol
        rows, _ = scored(flags, closes, "drop")
        c = [r["clv"] for r in rows]
        beat = sum(1 for x in c if x > 0)
        lost = sum(1 for x in c if x < 0)
        L.append(f"| {tol} | {len(rows)} | {st.mean(c):+.2f} | "
                 f"{beat / (beat + lost) * 100:.0f}% |" if c else f"| {tol} | 0 | -- | -- |")
    globals()["TOLERANCE"] = saved
    return "\n".join(L)


def self_check() -> None:
    # The sign is the thing to get wrong. Under 55.5 closing 53.5 is +2 for the bettor.
    assert clv_points("under", 55.5, 53.5) == 2.0
    assert clv_points("under", 55.5, 57.5) == -2.0
    assert clv_points("over", 44.0, 47.0) == 3.0
    assert clv_points("over", 44.0, 41.0) == -3.0
    assert clv_points("under", 50.0, 50.0) == 0.0

    # A clean Pinnacle close is used by every policy that is allowed to use Pinnacle.
    for pol in ("none", "drop", "substitute"):
        assert usable_close(55.0, [55.5, 55.0, 54.5], pol)[0] == 55.0, pol
    # The Western Kentucky at Georgia shape: only the ungated policy may ever score it.
    assert usable_close(82.5, [56.0, 55.5, 56.5], "none")[0] == 82.5
    assert usable_close(82.5, [56.0, 55.5, 56.5], "drop")[0] is None
    assert usable_close(82.5, [56.0, 55.5, 56.5], "substitute")[0] == 56.0
    assert usable_close(82.5, [56.0, 55.5, 56.5], "consensus")[0] == 56.0
    # Too few books to convict: the number stands rather than being thrown away.
    assert usable_close(55.0, [], "drop")[0] == 55.0
    assert usable_close(55.0, [], "consensus")[0] is None
    # No Pinnacle row at all.
    assert usable_close(None, [55.5, 55.0], "drop")[0] is None
    assert usable_close(None, [55.5, 55.0], "substitute")[0] == 55.25
    assert abs(usable_close(56.0, [55.5, 55.0, 56.5], "drop")[0] - 56.0) < 1e-9  # inside tol

    flags = load_flags()
    assert len(flags) == 106, len(flags)
    closes = load_closes()
    assert closes, "no 2026 closes loaded"
    rows, why = scored(flags, closes, "pinnacle")
    assert sum(why.values()) == len(flags), (sum(why.values()), len(flags))
    assert all(r["close"] == r["close"] for r in rows), "a NaN close reached scoring"
    print(f"self-check ok  ({len(rows)} of {len(flags)} flags scored)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--close", choices=POLICIES, default="drop")
    ap.add_argument("--tolerance", type=float, default=TOLERANCE)
    ap.add_argument("--compare", action="store_true",
                    help="run every gate policy side by side and report whether the gate matters")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args()
    if a.self_check:
        return self_check()
    globals()["TOLERANCE"] = a.tolerance
    flags, closes = load_flags(), load_closes()
    text = compare(flags, closes) if a.compare else report(flags, closes, a.close)
    if a.out:
        a.out.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {a.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
