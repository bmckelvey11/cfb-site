"""Closing-line value for every graded Greenline totals under, all three eras, one close.

    python research/totals/scripts/greenline_clv_all_eras.py
    python research/totals/scripts/greenline_clv_all_eras.py --out doc.md
    python research/totals/scripts/greenline_clv_all_eras.py --self-check

WHY. `greenline_clv.py` measures 2026 only (n=79 after its Pinnacle gate, mde 0.61 pts) and
the 2020 archive carries CLV only against PFF's own board. This scores the pooled unders --
the 2020 PFF_hist picks, the 2022-23 export picks and the 2026 flags, exactly the rows
`pool_totals_record.load()` pools -- against ONE benchmark that exists for all three: the
CFBD per-book closing total in `core.fact_game_line`.

ANALYSIS PLAN, fixed 2026-09-23 before any number was computed.

  Benchmark   the median `total_close` across the game's books (CFBD's "consensus" row
              counts as one book). Pinnacle is not used: it has no rows before late 2025,
              and one benchmark across eras is the point. At least MIN_BOOKS closes
              required. A game whose books span more than MAX_SPREAD points is dropped as a
              feed error; the sensitivity table reruns with the gate off.
              REVISED after the first run, before any conclusion was drawn: the benchmark
              is REST-backed books only (`book_closes(rest_only=True)`). The first run
              used every book and exposed that GraphQL-only rows hold IN-GAME totals on
              some 2026 games (see `book_closes`), so they are not a close at all. The
              test and its decision rule did not change; the all-books runs stay in the
              sensitivity table.
  Capture     the line the pick was graded at: 2020 `open_greenline` snapshot, 2022-23
              `export` snapshot, 2026 weekly capture.
  CLV         capture - close for an under, in points. Positive = the market moved toward
              the under after the pick. No price at close exists in CFBD, so this is point
              CLV; the ~win-prob column converts at the unit's 4 pp per point.
  Primary     pooled unders, mean CLV > 0, one-sided, alpha 0.05, SE clustered by kickoff
              date (one Saturday's slate shares market-wide news). ONE primary test.
  Secondary   per era; pick minus unpicked-lean drift where the era has unpicked rows
              (2020, 2022-23; 2026 has none -- the whole board is flagged); 2020 CFBD close vs
              PFF_hist's own close snapshot as a benchmark cross-check; 2026 against the
              Pinnacle-gated close `greenline_clv.py` uses. Reported, not tested for a verdict.
  Scale       at -110 an under needs 2.38 pp over a coin flip, which at 4 pp per point is
              BREAK_EVEN_CLV = 0.6 pts of CLV to pay for the vig on CLV alone.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bankroll" / "scripts"))
from cfb_paths import DB_PATH  # noqa: E402
from greenline_clv import PP_PER_POINT, clv_mde, load_flags  # noqa: E402
from greenline_clv import load_closes as load_closes_2026  # noqa: E402
from greenline_clv import scored as scored_2026  # noqa: E402
from greenline_season_review import wilson  # noqa: E402
from pool_totals_record import ARCHIVE, load, num  # noqa: E402

MIN_BOOKS = 2
MAX_SPREAD = 3.0          # points between the highest and lowest book close
BREAK_EVEN_CLV = (110 / 210 - 0.5) / PP_PER_POINT
Z95, Z_ONE = 1.96, 1.645


def book_closes(seasons: tuple[int, ...], rest_only: bool = True) -> tuple[dict, dict]:
    """({cfbd game_id: [closes]}, {(season, frozenset(team ids)): [closes]}).

    `rest_only` keeps rows CFBD's REST /lines feed backs (`_source` rest/both). Rows that
    exist only in the GraphQL feed carry IN-GAME totals on some 2026 games -- Western
    Kentucky at Georgia closes 52.5-56.0 at four REST-backed books and 78.0-82.5 at four
    GQL-only ones -- so they are not a close. Every 2020-23 row is REST-backed."""
    import duckdb

    con = duckdb.connect(str(DB_PATH), read_only=True)
    rows = con.execute(
        "select cast(g.game_id as varchar), g.season, cast(g.home_team_id as varchar), "
        "cast(g.away_team_id as varchar), l.total_close "
        "from core.fact_game g join core.fact_game_line l using(game_id) "
        f"where g.season in ({','.join(map(str, seasons))}) and l.total_close is not null "
        "and not isnan(l.total_close) and l.provider_key <> 'pinnacle'"
        + (" and l._source <> 'gql'" if rest_only else "")).fetchall()
    con.close()
    by_id, by_teams = {}, {}
    for gid, season, h, a, tc in rows:
        by_id.setdefault(gid, []).append(float(tc))
        by_teams.setdefault((season, frozenset((h, a))), []).append(float(tc))
    return by_id, by_teams


GATES = ("span", "none", "trim")
TRIM = 1.5  # points from the game median past which one book's close is discarded


def consensus(closes: list[float] | None, gate: str = "span") -> tuple[float | None, str]:
    """`span` (primary, registered): drop the game if its books disagree. `none`: trust all.
    `trim` (sensitivity, added 2026-09-23 AFTER the primary ran, once the 2026 feed showed
    Circa off by > 3 pts on 65 games): with 3+ books, discard only the books more than TRIM
    from the median and keep the game."""
    if not closes or len(closes) < MIN_BOOKS:
        return None, "dropped: fewer than 2 books"
    if gate == "trim" and len(closes) >= 3:
        m = st.median(closes)
        closes = [c for c in closes if abs(c - m) <= TRIM]
        if len(closes) < MIN_BOOKS:
            return None, "dropped: fewer than 2 books after trim"
    if gate != "none" and max(closes) - min(closes) > MAX_SPREAD:
        return None, f"dropped: books span > {MAX_SPREAD:g} pts"
    return st.median(closes), "scored"


def attach(rows: list[dict], by_id: dict, by_teams: dict, gate: str = "span") -> tuple[list[dict], dict]:
    """Score each row's capture against the consensus close. 2026 rows carry `teams`."""
    kept, why = [], {}
    for r in rows:
        closes = by_teams.get((r["season"], r["teams"])) if r.get("teams") else by_id.get(r["game_id"])
        close, reason = consensus(closes, gate)
        why[reason] = why.get(reason, 0) + 1
        if close is not None:
            kept.append(dict(r, close=close, clv=r["line"] - close))  # under: capture - close
    return kept, why


def unpicked(snapshot: str) -> list[dict]:
    """Archive rows PFF did NOT pick, any side: the market's own capture-to-close drift."""
    out = []
    for r in csv.DictReader(ARCHIVE.open(encoding="utf-8")):
        line = num(r["market_line"])
        if (r["market"] == "total" and r["snapshot"] == snapshot and r["is_greenline_pick"] == "False"
                and line is not None and r["game_id"]):
            out.append({"game_id": r["game_id"].split(".")[0], "line": line,
                        "date": (r["kickoff_utc"] or "")[:10], "season": int(float(r["season"]))})
    return out


def pff_close_2020() -> dict:
    return {r["game_id"].split(".")[0]: num(r["market_line"])
            for r in csv.DictReader(ARCHIVE.open(encoding="utf-8"))
            if r["market"] == "total" and r["snapshot"] == "close" and r["game_id"]
            and num(r["market_line"]) is not None}


def stats(c: list[float], dates: list[str]) -> dict:
    """Mean, iid and date-clustered SE, one-sided p against zero, beat/lost counts."""
    n = len(c)
    m = st.mean(c)
    iid = st.stdev(c) / math.sqrt(n) if n > 1 else float("nan")
    groups: dict[str, float] = {}
    for x, d in zip(c, dates):
        groups[d] = groups.get(d, 0.0) + (x - m)
    g = len(groups)
    cl = math.sqrt(sum(v * v for v in groups.values()) / n ** 2 * g / (g - 1)) if g > 1 else float("nan")
    se = max(iid, cl) if cl == cl else iid   # never let clustering claim more precision
    p = 0.5 * math.erfc(m / se / math.sqrt(2)) if se and se == se else float("nan")
    return {"n": n, "mean": m, "median": st.median(c), "se": se, "iid": iid, "g": g, "p": p,
            "beat": sum(x > 0 for x in c), "lost": sum(x < 0 for x in c)}


def row(label: str, s: dict) -> str:
    lo, hi = wilson(s["beat"], s["beat"] + s["lost"]) if s["beat"] + s["lost"] else (0, 0)
    return (f"| {label} | {s['n']} | {s['g']} | {s['mean']:+.2f} ± {Z95 * s['se']:.2f} | {s['median']:+.1f} "
            f"| {clv_mde(s['se']):.2f} | {s['p']:.3f} | {s['mean'] * PP_PER_POINT * 100:+.1f}pp "
            f"| {s['beat']}-{s['lost']}-{s['n'] - s['beat'] - s['lost']} | {lo * 100:.0f}–{hi * 100:.0f}% |")


def unders() -> list[dict]:
    """The pooled unders, 2026 rows given the CFBD team ids they join on."""
    teams = {f["pff_game_id"]: f["teams"] for f in load_flags()}
    out = []
    for r in load():
        if r["side"] != "under" or r["line"] is None:
            continue
        if r["era"] == "2026 flags":
            if r["game_id"] not in teams:
                continue
            r = dict(r, teams=teams[r["game_id"]])
        out.append(r)
    return out


ERAS = ("2020 PFF_hist", "2022-23 exports", "2026 flags")


def sensitivity(rows: list[dict]) -> list[str]:
    L = ["", "## Sensitivity: the close definition", "",
         "`rest` is REST-backed books only (the primary); `all` adds the GraphQL-only books, "
         "which carry in-game totals on some 2026 games. `span` drops a game whose books "
         "disagree by more than 3 pts; `none` trusts every book; `trim` discards single books "
         "more than 1.5 pts off the game median and was added after the first run.", "",
         "| books | gate | split | n | mean CLV (pts, 95%) | p (one-sided) | upper 95% vs break-even 0.60 |",
         "| --- | --- | --- | ---: | ---: | ---: | --- |"]
    closes = {src: book_closes((2020, 2022, 2023, 2026), src == "rest") for src in ("rest", "all")}
    for src, gate in (("rest", "span"), ("rest", "none"), ("all", "span"), ("all", "none"), ("all", "trim")):
        scored, _ = attach(rows, *closes[src], gate)
        for label, sub in [("pooled", scored)] + [(e, [r for r in scored if r["era"] == e]) for e in ERAS]:
            if len(sub) < 2:
                continue
            s = stats([r["clv"] for r in sub], [r["date"] for r in sub])
            hi = s["mean"] + Z95 * s["se"]
            L.append(f"| {src} | {gate} | {label} | {s['n']} | {s['mean']:+.2f} ± {Z95 * s['se']:.2f} | {s['p']:.3f} "
                     f"| {hi:+.2f} {'below' if hi < BREAK_EVEN_CLV else 'reaches'} |")
    return L


def report(gate: str = "span") -> str:
    rows = unders()
    by_id, by_teams = book_closes((2020, 2022, 2023, 2026))
    scored, why = attach(rows, by_id, by_teams, gate)
    eras = ERAS
    s_all = stats([r["clv"] for r in scored], [r["date"] for r in scored])

    L = [f"`research/totals/scripts/greenline_clv_all_eras.py`. {len(rows)} pooled Greenline totals "
         "unders, each scored at its graded capture against the median CFBD book close. "
         "Positive CLV = the market moved toward the under after the pick.", "",
         "## Coverage", "", "| outcome | unders |", "| --- | ---: |"]
    L += [f"| {k} | {v} |" for k, v in sorted(why.items(), key=lambda kv: -kv[1])]
    head = ["| split | n | dates | mean CLV (pts, 95%) | median | mde (pts) | p (one-sided) "
            "| ~win prob | beat-lost-flat | beat rate 95% |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    L += ["", "## Primary: pooled unders against the consensus close", "",
          f"SE is the larger of iid and date-clustered. `mde` is the smallest true mean CLV this "
          f"n detects 80% of the time, one-sided. Break-even CLV at -110 is "
          f"{BREAK_EVEN_CLV:.2f} pts.", ""] + head
    L.append(row("**all eras, unders**", s_all))
    per = {}
    for era in eras:
        sub = [r for r in scored if r["era"] == era]
        if len(sub) > 1:
            per[era] = stats([r["clv"] for r in sub], [r["date"] for r in sub])
            L.append(row(era, per[era]))
    a, b = per.get("2020 PFF_hist"), per.get("2026 flags")
    if a and b:
        d, se = b["mean"] - a["mean"], math.hypot(a["se"], b["se"])
        L += ["", f"**The pool mixes eras that disagree.** 2026 minus 2020: {d:+.2f} ± {Z95 * se:.2f} pts, "
              f"two-sided p {math.erfc(abs(d) / se / math.sqrt(2)):.3f}. The pooled mean is an "
              "average of an era with no CLV and an era with CLV, not one rate."]

    L += ["", "## Secondary: picks against the market's own drift", "",
          "The unpicked rows are games PFF leaned on without making a pick, captured at the same "
          "snapshot. Their capture-minus-close is what any under would have earned from the "
          "market's drift alone; the pick's CLV is only evidence of skill above that.", "",
          "| era | picks mean | unpicked drift mean (n) | excess (pts, 95%) |", "| --- | ---: | ---: | ---: |"]
    for era, snap in (("2020 PFF_hist", "open_greenline"), ("2022-23 exports", "export")):
        pk = [r["clv"] for r in scored if r["era"] == era]
        ctrl, _ = attach(unpicked(snap), by_id, by_teams, gate)
        cc = [r["clv"] for r in ctrl]
        if len(pk) > 1 and len(cc) > 1:
            d = st.mean(pk) - st.mean(cc)
            se = math.sqrt(st.variance(pk) / len(pk) + st.variance(cc) / len(cc))
            L.append(f"| {era} | {st.mean(pk):+.2f} | {st.mean(cc):+.2f} ({len(cc)}) | {d:+.2f} ± {Z95 * se:.2f} |")
    L.append("| 2026 flags | — | no unpicked rows: every priced game is flagged | — |")

    pc = pff_close_2020()
    both = [(r["close"], pc[r["game_id"]]) for r in scored if r["era"] == "2020 PFF_hist" and r["game_id"] in pc]
    if both:
        diffs = [a - b for a, b in both]
        pff_clv = [r["line"] - pc[r["game_id"]] for r in scored if r["era"] == "2020 PFF_hist" and r["game_id"] in pc]
        L += ["", "## Benchmark cross-checks", "",
              f"- **2020, CFBD close vs PFF_hist's own close snapshot** ({len(both)} games): mean "
              f"difference {st.mean(diffs):+.2f} pts, {sum(abs(x) <= 0.5 for x in diffs)} within half a point. "
              f"The same picks scored against PFF's close: mean CLV {st.mean(pff_clv):+.2f} pts."]
    flags26 = [f for f in load_flags() if f["side"] == "under"]
    pin, _ = scored_2026(flags26, load_closes_2026(), "drop")
    day = {r["game_id"]: r["date"] for r in rows if r["era"] == "2026 flags"}
    if len(pin) > 1:
        sp = stats([r["clv"] for r in pin], [day.get(r["pff_game_id"], "") for r in pin])
        L.append(f"- **2026, Pinnacle-gated close** (`greenline_clv.py --close drop`, unders only): "
                 f"n={sp['n']}, {sp['mean']:+.2f} ± {Z95 * sp['se']:.2f} pts. **Contaminated, not a "
                 "cross-check:** Pinnacle and the books its gate compares against are GraphQL-only "
                 "rows, which hold in-game totals on some games.")
    L += same_book_2026()
    L += sensitivity(rows)
    return "\n".join(L) + "\n"


# The odds-api snapshot nearest each 2026 board capture: week 2's board CSV was written
# 2026-09-09 23:11Z, week 3's dumps span 2026-09-16 16:02-18:26Z.
CAPTURE_SNAPSHOTS = {"2": "odds_americanfootball_ncaaf_20260909T200531Z.json",
                     "3": "odds_americanfootball_ncaaf_20260916T180004Z.json"}


def same_book_2026() -> list[str]:
    """DraftKings at capture vs DraftKings' own REST close, signed by the flag's side.

    Rules out the artifact a cross-source CLV cannot: flags are chosen on PFF's displayed
    line minus its projection, so a displayed number that is sometimes off the market
    over-samples too-high captures for unders and too-low for overs, and both regress to
    the close without PFF knowing anything. One book at both ends has no such noise."""
    import duckdb
    from datetime import datetime, timedelta, timezone
    from match_greenline_books import OA_DIR, is_placeholder, latest_snapshot, match, slug_names
    from pool_totals_record import SCHEDULE_2026

    con = duckdb.connect(str(DB_PATH), read_only=True)
    dk_close = {frozenset((str(h), str(a))): float(t) for h, a, t in con.execute(
        "select g.home_team_id, g.away_team_id, l.total_close from core.fact_game g "
        "join core.fact_game_line l using(game_id) where g.season = 2026 and "
        "l.provider_key = 'draftkings' and l._source <> 'gql' and not isnan(l.total_close)").fetchall()}
    con.close()
    sched = {s["pff_game_id"]: s for s in csv.DictReader(SCHEDULE_2026.open(encoding="utf-8"))}
    snaps = {wk: latest_snapshot(OA_DIR / name)[0] for wk, name in CAPTURE_SNAPSHOTS.items()}
    out = []
    for f in load_flags():
        g, oa = sched.get(f["pff_game_id"]), snaps.get(str(f["week"]))
        if not g or oa is None or f["teams"] not in dk_close:
            continue
        kick = datetime.fromisoformat(g["kickoff_raw"][:16]).replace(
            tzinfo=timezone(timedelta(hours=-4))).astimezone(timezone.utc)
        e = match(kick, *slug_names(g.get("matchup_path", "")), oa, is_placeholder(g["kickoff_raw"][:16]))
        if not e or "DraftKings" not in e["totals"]:
            continue
        at = e["totals"]["DraftKings"][0]
        move = at - dk_close[f["teams"]]
        out.append({"side": f["side"], "clv": move if f["side"] == "under" else -move,
                    "same": abs(at - f["line"]) < 0.01, "date": g["kickoff_raw"][:10]})
    L = ["", "## Same-book check: DraftKings at capture vs DraftKings' close (2026)", "",
         "Signed by the flag's side, so positive = DraftKings moved toward PFF after capture.", ""]
    L += ["| split | n | dates | mean CLV (pts, 95%) | median | mde (pts) | p (one-sided) "
          "| ~win prob | beat-lost-flat | beat rate 95% |",
          "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for label, sub in (("all flags", out), ("unders", [r for r in out if r["side"] == "under"]),
                       ("overs", [r for r in out if r["side"] == "over"]),
                       ("PFF's number = DK's", [r for r in out if r["same"]]),
                       ("PFF's number != DK's", [r for r in out if not r["same"]])):
        if len(sub) > 1:
            L.append(row(label, stats([r["clv"] for r in sub], [r["date"] for r in sub])))
    return L


def self_check() -> None:
    assert abs(BREAK_EVEN_CLV - 0.595) < 0.001, BREAK_EVEN_CLV
    assert consensus([50.5]) == (None, "dropped: fewer than 2 books")
    assert consensus([50.5, 51.5, 51.0]) == (51.0, "scored")
    assert consensus([50.5, 82.5])[0] is None                  # a feed-bug close is refused
    assert consensus([50.5, 82.5], gate="none")[0] == 66.5      # ...unless the gate is off
    assert consensus([50.5, 51.0, 82.5], gate="trim") == (50.75, "scored")  # trim drops the one bad book
    assert consensus([50.5, 51.0, 82.5])[0] is None             # span drops the whole game
    r, _ = attach([{"game_id": "1", "line": 52.5}], {"1": [51.5, 51.5]}, {})
    assert r[0]["clv"] == 1.0                                   # under captured above the close
    r, _ = attach([{"season": 2026, "teams": frozenset("ab"), "game_id": "x", "line": 50.0}],
                  {}, {(2026, frozenset("ab")): [51.0, 51.0]})
    assert r[0]["clv"] == -1.0                                  # 2026 joins on teams, not id
    s = stats([1.0, 1.0, -1.0, -1.0], ["a", "a", "b", "b"])
    assert s["mean"] == 0 and s["beat"] == 2 and s["g"] == 2
    assert s["se"] >= s["iid"]                                   # clustering never narrows
    print("self-check ok")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", help="write the report here as well")
    ap.add_argument("--gate", choices=GATES, default="span", help="close definition for the main tables")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        self_check()
        return
    text = report(gate=args.gate)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
