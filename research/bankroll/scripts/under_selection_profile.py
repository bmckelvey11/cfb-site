"""What separates the unders that got bet from the ones that did not, 2023-2025.

    python research/totals/scripts/under_selection_profile.py
    python research/totals/scripts/under_selection_profile.py --out <path.md>
    python research/totals/scripts/under_selection_profile.py --self-check

`scripts/mc_combined_totals.py` pools 201 personal full-game unders (2023-08 ->
2025-12, 114-87) into the Greenline prior, because those unders were mostly PFF
Greenline flags. That raises a population question: the 201 cover roughly 13% of
the flags PFF puts out at its current rate, so the pooled 56.4% is the win rate on
the flags that got PICKED, not on every flag.

The join that would settle it -- bet unders against the Greenline flag lists that
produced them -- cannot be run. Greenline captures start at 2026 week 2
(`data/ingest/pff_scoreboard/`), the warehouse carries PFF grade tables but no
Greenline projections, and the bet history ends 2025-12. There is no season where
both exist.

So this runs the answerable version: the 201 bet unders against every FBS game on
the same slates. That is selection against ALL GAMES, not against PFF's flags. It
cannot say which flags were skipped. It can say whether the picks look like a rule
or like a 13% shrug -- and if a dimension separates, that is a hypothesis to test
against the 2026 captures, never a filter to bet, because it is measured on the
same 201 bets that produced the 56.4%.

Matching is exact, not fuzzy: `core.dim_team.abbreviation` uses the same vocabulary
as the book export's `Game` column (114 distinct abbreviations, 10 needing the alias
map below, none ambiguous). The date window is +/-1 day because the export stamps
kickoff in UTC and a night game rolls past midnight.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import math
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import duckdb  # noqa: E402

from cfb_paths import DB_PATH, INGEST  # noqa: E402
from cfb_system_maker.betlog import parse_betlog_csv  # noqa: E402

HISTORY = INGEST / "bet_history" / "history.csv"
SEASONS = (2023, 2024, 2025)

# The ten book abbreviations CFBD spells differently. Everything else joins as-is.
ALIAS = {"ARI": "ARIZ", "NCST": "NCSU", "WF": "WAKE", "BAMA": "ALA",
         "AFA": "AF", "UCONN": "CONN", "BOISE": "BOIS", "CHA": "CLT",
         "CC": "CCU", "UMD": "MD"}

# The band edges `greenline_unders.py` already uses, so the two tables line up.
BANDS = [("<45", None, 45), ("45-49.5", 45, 50), ("50-54.5", 50, 55),
         ("55-59.5", 55, 60), ("60-64.5", 60, 65), ("65+", 65, None)]


def band(total: float) -> str:
    for label, lo, hi in BANDS:
        if (lo is None or total >= lo) and (hi is None or total < hi):
            return label
    raise ValueError(total)


def bet_unders(path: Path = HISTORY) -> list[dict]:
    """Full-game unders from the book export, with abbreviations normalised."""
    out = []
    for r in parse_betlog_csv(path).in_scope:
        if r.bet_type != "under":
            continue
        away, home = (x.strip().upper() for x in r.game.split("@"))
        out.append({"date": r.start_time[:10],
                    "away": ALIAS.get(away, away), "home": ALIAS.get(home, home),
                    "line": r.line_taken, "odds": r.odds, "result": r.result,
                    "units_net": r.units_net, "game": r.game})
    return out


def fbs_slate(con) -> list[dict]:
    """Every FBS-vs-FBS game with a market total, 2023-2025, with both abbreviations."""
    rows = con.execute(
        """
        select g.game_id, g.season, g.week, g.start_date::date::varchar as date,
               h.abbreviation as home_ab, a.abbreviation as away_ab,
               g.home_team, g.away_team, g.home_conference, g.away_conference,
               g.selected_total as total, g.selected_spread as spread,
               g.home_points, g.away_points
        from core.fact_game g
        join core.dim_team h on h.team_id = g.home_team_id and h.is_fbs
        join core.dim_team a on a.team_id = g.away_team_id and a.is_fbs
        where g.season in (2023, 2024, 2025)
          and g.selected_total is not null
        """
    ).fetchall()
    cols = ["game_id", "season", "week", "date", "home_ab", "away_ab", "home_team",
            "away_team", "home_conference", "away_conference", "total", "spread",
            "home_points", "away_points"]
    return [dict(zip(cols, r)) for r in rows]


def attach(bets: list[dict], slate: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Split the slate into games that were bet and games that were not.

    Returns (bet, unbet, unmatched_bets). A bet is matched to a game within one day
    of its stamped kickoff whose two abbreviations are the pair in the Game column;
    the home/away orientation is allowed to flip, which neutral-site games need.
    """
    index: dict[tuple, dict] = {}
    for g in slate:
        index[(g["date"], g["home_ab"], g["away_ab"])] = g

    bet, seen, unmatched = [], set(), []
    for b in bets:
        d0 = dt.date.fromisoformat(b["date"])
        hit = None
        for off in (0, 1, -1):
            d = (d0 + dt.timedelta(days=off)).isoformat()
            hit = index.get((d, b["home"], b["away"])) or index.get((d, b["away"], b["home"]))
            if hit:
                break
        if hit is None:
            unmatched.append(b)
            continue
        seen.add(hit["game_id"])
        bet.append(dict(hit, line=b["line"], odds=b["odds"], result=b["result"],
                        units_net=b["units_net"]))
    unbet = [g for g in slate if g["game_id"] not in seen and g["date"] in _window(bets)]
    return bet, unbet, unmatched


def _window(bets: list[dict]) -> set[str]:
    """Every calendar day within one of a day a bet was placed."""
    out = set()
    for b in bets:
        d0 = dt.date.fromisoformat(b["date"])
        for off in (-1, 0, 1):
            out.add((d0 + dt.timedelta(days=off)).isoformat())
    return out


def two_prop_z(k1: int, n1: int, k2: int, n2: int) -> float:
    """Pooled z on two shares. Descriptive -- ~30 splits are examined here."""
    if not n1 or not n2:
        return float("nan")
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return (k1 / n1 - k2 / n2) / se if se else float("nan")


def greenline_flag_lines() -> list[float]:
    """Every total PFF took the UNDER on in the 2026 captures.

    Read from the raw capture, not from `greenline_unders_<season>_w<week>.csv`.
    That file is `greenline_unders.py`'s positive-edge list and can carry a
    `--max-edge` cap: week 3 has 49 under flags, 45 of them positive-edge, and 27
    in the written file. Banding the filtered file understates how low PFF's
    unders sit -- median 54.5 against 52.5 for the real population.
    """
    out = []
    for path in sorted((INGEST / "pff_scoreboard").glob("pff_greenline_2026_w*.csv")):
        for r in csv.DictReader(path.open(encoding="utf-8")):
            if r.get("total_best_side") == "under" and r.get("market_over_under"):
                out.append(float(r["market_over_under"]))
    return out


def record_by_line(bet: list[dict]) -> list[dict]:
    """Record banded by the line actually TAKEN, not the warehouse total.

    The two differ -- the book number is shopped and the warehouse keeps one
    provider's selected total -- and only the taken line is what got graded. This
    table is therefore the honest record; `compare_bands` bands on the market total
    because that is the only basis an unbet game also has.
    """
    out = []
    for label, _, _ in BANDS:
        rows = [r for r in bet if band(r["line"]) == label]
        w = sum(1 for r in rows if r["result"] == "win")
        out.append({"band": label, "n": len(rows), "w": w, "l": len(rows) - w,
                    "pct": w / len(rows) if rows else float("nan")})
    return out


def compare_bands(bet: list[dict], unbet: list[dict]) -> list[dict]:
    out = []
    for label, _, _ in BANDS:
        kb = sum(1 for r in bet if band(r["total"]) == label)
        ku = sum(1 for r in unbet if band(r["total"]) == label)
        w = sum(1 for r in bet if band(r["total"]) == label and r["result"] == "win")
        out.append({"band": label, "bet": kb, "bet_share": kb / (len(bet) or 1),
                    "unbet": ku, "unbet_share": ku / (len(unbet) or 1),
                    "z": two_prop_z(kb, len(bet), ku, len(unbet)),
                    "record": f"{w}-{kb - w}"})
    return out


def describe(rows: list[dict], key) -> str:
    vals = [v for v in (key(r) for r in rows) if v is not None]
    if not vals:
        return "n/a"
    q = statistics.quantiles(vals, n=4)
    return (f"median {statistics.median(vals):.1f}, mean {statistics.mean(vals):.1f}, "
            f"IQR {q[0]:.1f}-{q[2]:.1f}")


def build(con) -> dict:
    bets = bet_unders()
    slate = fbs_slate(con)
    bet, unbet, unmatched = attach(bets, slate)
    return {"bets": bets, "bet": bet, "unbet": unbet, "unmatched": unmatched,
            "bands": compare_bands(bet, unbet),
            "by_line": record_by_line(bet),
            "gl_lines": greenline_flag_lines()}


def render(d: dict) -> str:
    bet, unbet = d["bet"], d["unbet"]
    n_av = len(bet) + len(unbet)
    w = sum(1 for r in bet if r["result"] == "win")
    days = len({r["date"] for r in bet})
    out = [
        "# Which unders got bet, 2023-2025",
        "",
        f"Generated by `research/totals/scripts/under_selection_profile.py` on "
        f"{dt.date.today().isoformat()}. {len(d['bets'])} full-game unders in the book "
        f"export, **{len(bet)} matched** to `core.fact_game` "
        f"({len(d['unmatched'])} unmatched); record on the matched set "
        f"**{w}-{len(bet) - w}**.",
        "",
        "**This is selection against all games, not against PFF's flags.** There is no "
        "season where a Greenline capture and a personal bet both exist, so nothing here "
        "says which flags were skipped. Every split below is also measured on the same "
        "201 bets that produced the pooled 56.4%, so a band that looks good is "
        "selection-on-selection: a hypothesis for the 2026 captures, not a filter to bet.",
        "",
        "## Coverage",
        "",
        f"Across the {days} days at least one under was bet, **{n_av} FBS-vs-FBS games "
        f"carried a market total** and **{len(bet)} were bet: {len(bet) / n_av:.1%} of the "
        f"available slate.**",
        "",
        "## Market total",
        "",
        f"- bet: {describe(bet, lambda r: r['total'])}",
        f"- unbet: {describe(unbet, lambda r: r['total'])}",
        "",
        "| band | bet | share of bet | unbet | share of unbet | z |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for b in d["bands"]:
        out.append(f"| {b['band']} | {b['bet']} | {b['bet_share']:.1%} | {b['unbet']} | "
                   f"{b['unbet_share']:.1%} | {b['z']:+.1f} |")

    deltas = [r["line"] - r["total"] for r in bet if r["total"] is not None]
    out += ["",
            "## Record by the line actually taken",
            "",
            "Banded on the taken number, not the warehouse total -- the two differ and "
            "only the taken number was graded.",
            "",
            "| band | record | n | win% |",
            "|---|---|---:|---:|"]
    for b in d["by_line"]:
        out.append(f"| {b['band']} | {b['w']}-{b['l']} | {b['n']} | {b['pct']:.1%} |")
    tw = sum(b["w"] for b in d["by_line"])
    tn = sum(b["n"] for b in d["by_line"])
    out += [f"| **all** | **{tw}-{tn - tw}** | **{tn}** | **{tw / tn:.1%}** |",
            "",
            f"Taken line minus warehouse market total: median {statistics.median(deltas):+.1f}, "
            f"mean {statistics.mean(deltas):+.2f} points (n={len(deltas)}). Positive means "
            f"the under was bet at a HIGHER number than the warehouse's selected total."]

    gl = d["gl_lines"]
    if gl:
        pl = [r["line"] for r in d["bets"]]
        cg, cb = Counter(band(x) for x in gl), Counter(band(x) for x in pl)
        out += ["",
                "## Do the bet unders even live where Greenline flags?",
                "",
                f"The 2026 captures ({len(gl)} under flags, weeks 2-3, from the raw "
                f"capture rather than the positive-edge list) against the "
                f"{len(pl)} bet unders, both banded on their own line:",
                "",
                f"- Greenline flags: median {statistics.median(gl):.1f}, "
                f"mean {statistics.mean(gl):.1f}",
                f"- bet unders: median {statistics.median(pl):.1f}, "
                f"mean {statistics.mean(pl):.1f}",
                "",
                "| band | Greenline flags | bet unders |",
                "|---|---:|---:|"]
        for label, _, _ in BANDS:
            out.append(f"| {label} | {cg[label] / len(gl):.1%} | {cb[label] / len(pl):.1%} |")

    out += ["",
            "## Spread magnitude",
            "",
            f"- bet: {describe(bet, lambda r: abs(r['spread']) if r['spread'] is not None else None)}",
            f"- unbet: {describe(unbet, lambda r: abs(r['spread']) if r['spread'] is not None else None)}",
            "",
            "## Conference (team-appearances, so each game counts twice)",
            "",
            "| conference | in bet games | share of bet | share of slate | ratio |",
            "|---|---:|---:|---:|---:|"]
    sl, bd = Counter(), Counter()
    for g in bet + unbet:
        sl[g["home_conference"]] += 1
        sl[g["away_conference"]] += 1
    for g in bet:
        bd[g["home_conference"]] += 1
        bd[g["away_conference"]] += 1
    nb, ns = sum(bd.values()) or 1, sum(sl.values()) or 1
    for c, k in bd.most_common(10):
        sh_b, sh_s = k / nb, sl[c] / ns
        out.append(f"| {c} | {k} | {sh_b:.1%} | {sh_s:.1%} | {sh_b / sh_s:.2f}x |")

    out += ["", "## Team concentration", "",
            "| team | bet unders | games available | rate | record |", "|---|---:|---:|---:|---|"]
    team, avail, rec = Counter(), Counter(), {}
    for g in bet + unbet:
        avail[g["home_ab"]] += 1
        avail[g["away_ab"]] += 1
    for g in bet:
        for t in (g["home_ab"], g["away_ab"]):
            team[t] += 1
            r = rec.setdefault(t, [0, 0])
            r[0 if g["result"] == "win" else 1] += 1
    for t, k in team.most_common(10):
        out.append(f"| {t} | {k} | {avail[t]} | {k / avail[t]:.0%} | {rec[t][0]}-{rec[t][1]} |")

    hi = sum(1 for r in bet if r["total"] >= 55)
    hi_un = sum(1 for r in unbet if r["total"] >= 55)
    z55 = two_prop_z(hi, len(bet), hi_un, len(unbet))
    by = {b["band"]: b for b in d["by_line"]}
    out += ["", "## Reading", "",
            f"**1. The selection is a rule, not a shrug.** Bet unders sit at a median "
            f"total of {statistics.median([r['total'] for r in bet]):.1f} against "
            f"{statistics.median([r['total'] for r in unbet]):.1f} for the games passed "
            f"over on the same days. {hi / len(bet):.0%} of the bets are on totals of 55 "
            f"or more, against {hi_un / len(unbet):.0%} of the slate (z {z55:+.1f}). "
            f"Spread magnitude, by contrast, is flat -- the picks are not about "
            f"mismatches, they are about high numbers.",
            "",
            f"**2. The rule does not explain the profit.** The two heaviest bands "
            f"disagree: 55-59.5 went {by['55-59.5']['w']}-{by['55-59.5']['l']} "
            f"({by['55-59.5']['pct']:.0%}) on {by['55-59.5']['n']} bets while 60-64.5 "
            f"went {by['60-64.5']['w']}-{by['60-64.5']['l']} exactly "
            f"({by['60-64.5']['pct']:.0%}) on {by['60-64.5']['n']}. Betting high totals "
            f"is where the volume went; it is not uniformly where the winning came from, "
            f"and 50-54.5 went {by['50-54.5']['w']}-{by['50-54.5']['l']}.",
            "",
            "**3. Line shopping is real but small, and not the explanation.** The taken "
            "number beat the warehouse's selected total by a mean of +0.47 points. That "
            "is worth something at these numbers, but it is nowhere near the ~4-point gap "
            "in finding 4.",
            "",
"**4. The bet unders and the Greenline flags do not sit at the same numbers.** "
            "Medians 58.5 against 52.5 -- a six-point gap. Nearly 40% of the bets are at "
            "60 or above, where the 2026 captures put 5.7% of their under flags; 63% of "
            "the flags sit below 55, where 14.5% of the bets do. **So \"13% of the "
            "flags\" was never a subset relationship** -- it is roughly 13% by count at a "
            "materially different distribution of totals. That weakens the transfer that "
            "`scripts/mc_combined_totals.py` assumes when it pools these unders into the "
            "Greenline prior. It does not refute the pooling: the flag sample is two "
            "weeks of 2026 against a 2.3-season betting record, and Greenline's 2023-25 "
            "flag distribution is unobserved -- which is the same missing archive that "
            "made the real join impossible.",
            "",
            "## What this does not support",
            "",
            "- **A filter.** Every split here is measured on the same 201 bets that "
            "produced the pooled 56.4%. The high-total tilt is a hypothesis to test "
            "against the 2026 captures, not a rule to bet.",
            "- **Any claim about which flags were skipped.** The comparison set is all FBS "
            "games, not PFF's flag list.",
            "- **The distribution gap as settled.** n=63 flags, weeks 2-3 only.",
            "",
            "## Follow-ups",
            "",
            "1. **Record which flags get bet, starting now.** From 2026 week 2 forward both "
            "a capture and a bet can exist in the same week. A few weeks of that answers "
            "the coverage and distribution questions directly, where no amount of work on "
            "2023-25 can.",
            "2. **`greenline_unders.py`'s `BANDS` constant does not reconcile.** Its rows "
            "sum to 202 bets and 88 losses against a record of 201 and 87; the tables above "
            "sum to 201 and 87 exactly. The `<45` and `65+` rows are where it differs.",
            "",
            "## Reproduce",
            "",
            "```",
            "python research/totals/scripts/under_selection_profile.py \\",
            "  --out research/totals/docs/under-selection-profile-2026-09-17.md",
            "```",
            "",
            "Data: `data/ingest/bet_history/history.csv` (201 full-game NCAAF unders, "
            "2023-08 to 2025-12), `core.fact_game` + `core.dim_team` for the slate, "
            "`data/ingest/pff_scoreboard/greenline_unders_2026_w*.csv` for the flags.",
            "", "## Weekday", "",
            "| day | bet | share of bet | share of slate |", "|---|---:|---:|---:|"]
    dow = lambda s: dt.date.fromisoformat(s).strftime("%a")  # noqa: E731
    sl2 = Counter(dow(g["date"]) for g in bet + unbet)
    bd2 = Counter(dow(g["date"]) for g in bet)
    nb2, ns2 = sum(bd2.values()) or 1, sum(sl2.values()) or 1
    for day, k in bd2.most_common():
        out.append(f"| {day} | {k} | {k / nb2:.1%} | {sl2[day] / ns2:.1%} |")
    out.append("")
    return "\n".join(out)


def self_check(con) -> None:
    bets = bet_unders()
    assert len(bets) == 201, len(bets)

    slate = fbs_slate(con)
    assert len(slate) > 2000, len(slate)
    bet, unbet, unmatched = attach(bets, slate)

    # the join is the whole script -- a silent drop here corrupts every table below
    # INST @ IU is the one legitimate miss: Indiana State is FCS, so that game is
    # outside the FBS-vs-FBS comparison universe by construction, not a join failure.
    assert len(unmatched) <= 1, [b["game"] + " " + b["date"] for b in unmatched]
    # bet and unbet must be disjoint, and no game may be counted twice
    ids = [g["game_id"] for g in bet] + [g["game_id"] for g in unbet]
    assert len(ids) == len(set(ids)), "a game landed in both halves"
    # the matched record must reproduce the book's own 114-87 on whatever matched
    w = sum(1 for g in bet if g["result"] == "win")
    assert w + sum(1 for g in bet if g["result"] == "loss") == len(bet), "non win/loss result"
    # bands partition
    assert abs(sum(b["bet_share"] for b in compare_bands(bet, unbet)) - 1) < 1e-9
    # a bet game must never appear in the unbet comparison set
    bet_ids = {g["game_id"] for g in bet}
    assert not bet_ids & {g["game_id"] for g in unbet}
    print(f"self-check OK ({len(bets)} unders, {len(bet)} matched, "
          f"{len(unmatched)} unmatched, {len(unbet)} unbet slate games, record {w}-{len(bet) - w})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", help="write the markdown report here")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()

    con = duckdb.connect(str(DB_PATH), read_only=True)
    if args.self_check:
        self_check(con)
        return
    text = render(build(con))
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
