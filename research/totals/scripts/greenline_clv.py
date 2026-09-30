"""Closing-line value for the 2026 Greenline totals flags, overs and unders, against the
REST-backed book-median close.

    python research/totals/scripts/greenline_clv.py
    python research/totals/scripts/greenline_clv.py --out doc.md
    python research/totals/scripts/greenline_clv.py --self-check

WHY THIS EXISTS. Win/loss is a low-information signal: separating a 54% true rate from a
52.38% break-even needs roughly 5,900 graded picks, eight-plus seasons at this board's
volume. CLV is measured against a price rather than a coin flip, so it resolves in hundreds.
The review docs already report a CLV, but against PFF's OWN board close -- which asks
whether PFF agrees with itself. This asks whether PFF's flags lead the market.

THE CLOSE, re-pointed 2026-09-30. This script used to score against `provider_key =
'pinnacle'` in `core.fact_game_line`, gated against the other books' median. Those rows were
never Pinnacle: they were Action Network book 49, Caesars, mislabelled by the warehouse
loader until merge 48ae034c (all 362 `stg.game_lines` rows under that provider carried
`line_source = 'actionnetwork'`), and pre-dabec215 some held live in-game totals. After the
4212a8c4 rebuild no 'pinnacle' rows exist. Real Pinnacle lives only in the oddspapi
snapshots, pulled about once a day at 12Z with no Saturday pull in weeks 3-4, so there is no
Pinnacle close to score against. The close is the one `greenline_clv_all_eras.py` registered
-- median REST-backed book close, span gate (`book_closes` / `consensus`) -- so the unit has
one definition of "the close".

`greenline_clv_all_eras.py` owns the CLV verdict (pooled unders, date-clustered SE). This adds
the 2026 overs, the per-week split, and whether beating the close lines up with winning. Its
SE is iid, so its intervals are never wider than the all-eras rows; cite those for inference.

SIGN CONVENTION. Positive CLV means the market moved toward the side PFF flagged, so the
captured number was better than the close:

    under  ->  capture_line - close
    over   ->  close - capture_line
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
from cfb_paths import INGEST  # noqa: E402
from greenline_bet_log import _flag_cfbd_ids  # noqa: E402  -- the ledger owns the PFF->CFBD map
from greenline_season_review import wilson  # noqa: E402

GRADED = INGEST / "pff_scoreboard" / "greenline_graded.csv"
SEASON = 2026

# Half a point of total is worth roughly two points of win probability at these numbers --
# the unit's standing figure, used only to put CLV points on a familiar scale.
PP_PER_POINT = 0.04


def clv_points(side: str, capture_line: float, close: float) -> float:
    """Positive = the market moved toward the flagged side, so the capture beat the close."""
    return capture_line - close if side == "under" else close - capture_line


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
    """{(season, frozenset(team_ids)): [REST-backed book closes]} for the season."""
    from greenline_clv_all_eras import book_closes  # here, not at the top: it imports this module
    return book_closes((SEASON,))[1]


def scored(flags: list[dict], closes: dict) -> tuple[list[dict], dict]:
    from greenline_clv_all_eras import consensus
    kept, why = [], {}
    for f in flags:
        close, reason = consensus(closes.get((SEASON, f["teams"])))
        why[reason] = why.get(reason, 0) + 1
        if close is not None:
            kept.append(dict(f, close=close, clv=clv_points(f["side"], f["line"], close)))
    return kept, why


ONE_SIDED_80 = 1.645 + 0.84  # z_alpha(0.05, one-sided) + z_power(80%)


def clv_mde(se: float) -> float:
    """Smallest true mean CLV (pts) this n's SE would detect 80% of the time, one-sided."""
    return ONE_SIDED_80 * se if se == se else float("nan")  # se != se catches NaN (n <= 1)


def summarise(rows: list[dict], label: str) -> list[str]:
    if not rows:
        return [f"| {label} | 0 | -- | -- | -- | -- |"]
    c = [r["clv"] for r in rows]
    m = st.mean(c)
    se = st.stdev(c) / len(c) ** 0.5 if len(c) > 1 else float("nan")
    beat = sum(1 for x in c if x > 0)
    lost = sum(1 for x in c if x < 0)
    lo, hi = wilson(beat, beat + lost) if beat + lost else (0.0, 0.0)
    mde_str = f"{clv_mde(se):.2f}" if se == se else "--"
    return [f"| {label} | {len(rows)} | {m:+.2f} ± {1.96 * se:.2f} | {mde_str} "
            f"| {m * PP_PER_POINT * 100:+.1f}pp | {beat}-{lost}-{len(c) - beat - lost} "
            f"| {lo * 100:.0f}–{hi * 100:.0f}% |"]


def report(flags: list[dict], closes: dict) -> str:
    rows, why = scored(flags, closes)
    L = [f"`research/totals/scripts/greenline_clv.py`. {len(flags)} graded {SEASON} Greenline "
         "totals flags, scored against the median REST-backed book close rather than PFF's own "
         "board. Positive CLV means the market moved toward the flagged side.", "",
         "## What the gate kept and dropped", "",
         "| outcome | flags |", "| --- | ---: |"]
    for k in sorted(why, key=lambda k: (-why[k], k)):
        L.append(f"| {k} | {why[k]} |")
    L += ["", f"**{len(rows)} of {len(flags)} flags scored.** The close is the median "
          "`total_close` of the game's REST-backed books (`_source` ≠ `gql`), at least two, the "
          "game dropped if they span more than 3 pts -- the benchmark `greenline_clv_all_eras.py` "
          "registered.", "",
          "## Closing-line value", "",
          "SE is iid, not clustered by kickoff date, so these intervals are never wider than "
          "`greenline_clv_all_eras.py`'s; cite that script for inference. "
          "`mde` is the smallest true mean CLV (pts) this split's n would detect 80% of the time, "
          "one-sided. A mean inside its own mde is a bound on CLV, not a measurement of zero.", "",
          "| split | n | mean CLV (pts, 95%) | mde (pts) | ~win prob | beat-lost-flat | beat rate 95% |",
          "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
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


def self_check() -> None:
    # The sign is the thing to get wrong. Under 55.5 closing 53.5 is +2 for the bettor.
    assert clv_points("under", 55.5, 53.5) == 2.0
    assert clv_points("under", 55.5, 57.5) == -2.0
    assert clv_points("over", 44.0, 47.0) == 3.0
    assert clv_points("over", 44.0, 41.0) == -3.0
    assert clv_points("under", 50.0, 50.0) == 0.0

    # Closes are keyed (season, teams); a flag with no key or one book is not scored.
    one = {"teams": frozenset("ab"), "side": "over", "line": 50.0}
    rows, _ = scored([one], {(SEASON, frozenset("ab")): [51.0, 52.0]})
    assert rows[0]["clv"] == 1.5, rows
    assert scored([one], {(SEASON, frozenset("ab")): [51.0]})[0] == []
    assert scored([one], {(SEASON - 1, frozenset("ab")): [51.0, 52.0]})[0] == []

    flags = load_flags()
    closes = load_closes()
    assert closes, "no 2026 closes loaded"
    rows, why = scored(flags, closes)
    assert sum(why.values()) == len(flags), (sum(why.values()), len(flags))
    assert all(r["close"] == r["close"] for r in rows), "a NaN close reached scoring"
    print(f"self-check ok  ({len(rows)} of {len(flags)} flags scored)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args()
    if a.self_check:
        return self_check()
    flags, closes = load_flags(), load_closes()
    text = report(flags, closes)
    if a.out:
        a.out.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {a.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
