"""Scrape the Sportsbook Reviews Online NCAAF odds archive into game-level lines.

Fills the pre-2013 hole in `core.fact_game_line`: CFBD serves no lines before 2013
(docs/cfbd-lines-coverage-2026-09-17.md) and the Prediction Tracker tape has spreads but
no totals (docs/pre-2013-lines-sources-2026-09-17.md). This archive has both, plus a
moneyline, from real books -- 2007 through 2012 inside the gap, 2013 as a validation
season that CFBD also covers.

Source shape: one HTML table per season, two rows per game (V/H, or N/N for bowls).
Within a pair, one row's Open/Close is the SPREAD and the other's is the game TOTAL, and
nothing in the markup says which. Magnitude resolves it -- a football total always exceeds
its spread -- with a plausibility guard and the moneyline as an independent cross-check.
The spread row's team is the favourite; the pair is oriented to CFBD's home team by SCORE,
because shared-prefix names (Florida / Florida International) defeat string similarity.

Validated against the Prediction Tracker tape over 5,037 shared games: bias -0.047,
median |diff| 0.50, 96.1% within 2 points, 29 sign disagreements (0.6%).

robots.txt (2026-09-17) disallows only /go/. The browser user agent is required -- the
site 404s unknown agents.

    python scripts/scrape_sbr_ncaaf_lines.py              # cached HTML if present
    python scripts/scrape_sbr_ncaaf_lines.py --refetch    # re-download

Out: $CFB_DATA_ROOT/ingest/sbr_ncaaf_lines.csv

`half2_*` is a HALFTIME price -- post-kickoff information. It is carried for completeness
but must be tagged `result_lookahead` and kept out of any pre-game feature.
"""
from __future__ import annotations

import argparse
import csv
import html
import re
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from cfb_paths import DATA_ROOT  # noqa: E402

BASE = "https://www.sportsbookreviewsonline.com/scoresoddsarchives/ncaa-football-{}"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
SEASONS = list(range(2007, 2014))  # 2013 is the validation season, not part of the gap
CACHE = DATA_ROOT / "raw" / "sbr"
OUT = DATA_ROOT / "ingest" / "sbr_ncaaf_lines.csv"
PT_LINES = DATA_ROOT / "ingest" / "prediction_tracker_lines.csv"
DELAY_S = 2.0

NO_LINE = {"", "nl", "n/l", "-", "--"}


# ---------------------------------------------------------------- fetch / parse

def season_slug(season: int) -> str:
    return f"{season}-{str(season + 1)[2:]}"


def fetch(season: int, refetch: bool) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"ncaa-football-{season_slug(season)}.html"
    if path.exists() and not refetch:
        return path.read_text(encoding="utf-8", errors="replace")
    req = urllib.request.Request(BASE.format(season_slug(season)), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        page = resp.read().decode("utf-8", errors="replace")
    path.write_text(page, encoding="utf-8")
    time.sleep(DELAY_S)
    return page


def parse_rows(page: str) -> tuple[list[dict], int]:
    """Table rows as dicts. Returns (rows, dropped) -- a dropped row shifts pairing."""
    raw_rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        cells = [
            " ".join(html.unescape(re.sub(r"<[^>]*>", " ", c)).split())
            for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)
        ]
        if cells:
            raw_rows.append(cells)
    if not raw_rows:
        return [], 0
    header = raw_rows[0]
    rows, dropped = [], 0
    for cells in raw_rows[1:]:
        if len(cells) != len(header):
            dropped += 1
            continue
        rows.append(dict(zip(header, cells)))
    return rows, dropped


def num(text: str) -> float | None:
    t = (text or "").strip().lower()
    if t in NO_LINE:
        return None
    if t in ("pk", "p", "pick", "ev", "even"):
        return 0.0
    try:
        return float(t.replace("+", "").replace(",", ""))
    except ValueError:
        return None


def sbr_date(season: int, mmdd: str) -> date | None:
    """'830' -> Aug 30 of `season`; '103' -> Jan 3 of season+1."""
    t = (mmdd or "").strip()
    if not t.isdigit() or len(t) not in (3, 4):
        return None
    month, day = int(t[:-2]), int(t[-2:])
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    try:
        return date(season + 1 if month <= 7 else season, month, day)
    except ValueError:
        return None


# ---------------------------------------------------------------- pair / assign

def pair_rows(rows: list[dict]) -> tuple[list[tuple[dict, dict]], int]:
    """Consecutive two-row games. A Rot discontinuity is fatal for that pair."""
    pairs, bad = [], 0
    for i in range(0, len(rows) - 1, 2):
        a, b = rows[i], rows[i + 1]
        ra, rb = num(a.get("Rot", "")), num(b.get("Rot", ""))
        if ra is not None and rb is not None and rb - ra != 1:
            bad += 1
            continue
        pairs.append((a, b))
    return pairs, bad


def assign(a: dict, b: dict) -> tuple[dict, dict, int, int]:
    """Return (spread_row, total_row, ml_disagrees, swapped). Spread row's team is favourite.

    Magnitude decides: a football game total (~30-90) always exceeds its spread (~0-50).
    That beats the moneyline rule, because SBR itself sometimes transposes the two MLs --
    2009 Boise State at Louisiana Tech has the winning favourite at +1150 and the losing
    home underdog at -850, which sends an ML-led rule to the wrong row. The ML is kept as
    an independent cross-check and its disagreements are reported, not silently dropped.
    """
    def level(row: dict) -> float | None:
        v = num(row.get("Close", ""))
        return v if v is not None else num(row.get("Open", ""))

    la, lb = level(a), level(b)
    if la is None or lb is None:
        # Only one row is priced at all; the priced one is the spread by convention.
        spread_row, total_row = (a, b) if la is not None else (b, a)
    elif abs(la) > abs(lb):
        spread_row, total_row = b, a
    else:
        spread_row, total_row = a, b

    # Magnitude fails when a big spread meets a low total (spread 45 vs total 40). Catch it
    # on plausibility: a real CFB total is 25-100 and a real spread is within 50. If the
    # assignment breaks that and the swap does not, take the swap.
    def plausible(sp_row: dict, tot_row: dict) -> bool:
        sp, tot = level(sp_row), level(tot_row)
        if sp is None or tot is None:
            return True
        # A real spread reaches 70: FBS-vs-FCS blowouts are extreme, e.g. Florida State
        # -67.5 over Savannah State in 2012 (final 55-0). 50 would reject 23 real rows.
        return abs(sp) <= 70.0 and 25.0 <= abs(tot) <= 100.0

    swapped = 0
    if not plausible(spread_row, total_row) and plausible(total_row, spread_row):
        spread_row, total_row = total_row, spread_row
        swapped = 1

    ml_s, ml_t = num(spread_row.get("ML", "")), num(total_row.get("ML", ""))
    # The favourite should be the cheaper price. Disagreement means SBR's ML is transposed
    # or missing, not that the magnitude call is wrong.
    disagrees = int(ml_s is not None and ml_t is not None and ml_s > ml_t)
    return spread_row, total_row, disagrees, swapped


# ---------------------------------------------------------------- CFBD join

def normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def sim(x: str, y: str) -> float:
    if not x or not y:
        return 0.0
    if x == y:
        return 1.0
    if x.startswith(y) or y.startswith(x):
        return 0.9
    return SequenceMatcher(None, x, y).ratio()


def pair_name_score(sbr_a: str, sbr_b: str, cfbd_home: str, cfbd_away: str) -> float:
    """Best of both orientations, so a V/H disagreement does not sink a real match."""
    na, nb = normalize(sbr_a), normalize(sbr_b)
    nh, aw = normalize(cfbd_home), normalize(cfbd_away)
    return max(sim(na, aw) + sim(nb, nh), sim(na, nh) + sim(nb, aw))


def load_cfbd(con: duckdb.DuckDBPyConnection) -> dict:
    """Index CFBD games by (season, frozenset of the two scores)."""
    rows = con.execute(
        """select gameId, season, cast(startDate as date) as gdate, homeTeam, awayTeam,
                  homePoints, awayPoints, neutralSite, seasonType, week
           from stg.game
           where season between ? and ?
             and homePoints is not null and awayPoints is not null""",
        [SEASONS[0], SEASONS[-1]],
    ).fetchall()
    index: dict = defaultdict(list)
    for gid, season, gdate, home, away, hp, ap, neutral, stype, week in rows:
        if gdate is None:
            continue
        index[(season, frozenset((int(hp), int(ap))))].append({
            "game_id": gid, "season": season, "date": gdate,
            "home_team": home, "away_team": away,
            "home_points": int(hp), "away_points": int(ap),
            "neutral_site": neutral, "season_type": stype, "week": week,
        })
    return index


def find_game(index: dict, season: int, gdate: date, pa: int, pb: int,
              team_a: str, team_b: str) -> tuple[dict | None, int]:
    """Season + score pair + date within one day. Names break ties."""
    cands = [
        c for c in index.get((season, frozenset((pa, pb))), [])
        if abs((c["date"] - gdate).days) <= 1
    ]
    if not cands:
        return None, 0
    if len(cands) == 1:
        return cands[0], 1
    best = max(cands, key=lambda c: pair_name_score(team_a, team_b, c["home_team"], c["away_team"]))
    return best, len(cands)


# ---------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refetch", action="store_true", help="re-download instead of using cache")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    con = duckdb.connect(str(DATA_ROOT / "cfb.duckdb"), read_only=True)
    index = load_cfbd(con)

    out_rows: list[dict] = []
    stats: dict[int, Counter] = {s: Counter() for s in SEASONS}

    for season in SEASONS:
        st = stats[season]
        rows, dropped = parse_rows(fetch(season, args.refetch))
        st["rows"], st["dropped_rows"] = len(rows), dropped
        pairs, bad_pairs = pair_rows(rows)
        st["pairs"], st["rot_breaks"] = len(pairs), bad_pairs

        for a, b in pairs:
            gdate = sbr_date(season, a.get("Date", ""))
            pa, pb = num(a.get("Final", "")), num(b.get("Final", ""))
            if gdate is None or pa is None or pb is None:
                st["unparsed"] += 1
                continue

            fav, dog, ml_disagrees, swapped = assign(a, b)
            st["ml_disagrees"] += ml_disagrees
            st["plausibility_swaps"] += swapped

            game, n_cands = find_game(index, season, gdate, int(pa), int(pb),
                                      a.get("Team", ""), b.get("Team", ""))
            if game is None:
                st["unmatched"] += 1
                continue
            st["matched"] += 1
            st["collisions"] += int(n_cands > 1)

            # SBR writes the spread positive on the favourite's row. This repo wants it
            # negative when CFBD's HOME team is favoured. Orient by SCORE, not by name:
            # shared-prefix names (Florida / Florida International, Miami / Miami (OH))
            # make string similarity pick the wrong side of the pair.
            fav_pts, dog_pts = num(fav.get("Final", "")), num(dog.get("Final", ""))
            if fav_pts is not None and dog_pts is not None and fav_pts != dog_pts:
                fav_is_home = int(fav_pts) == game["home_points"]
                st["oriented_by_score"] += 1
            else:
                # Tied game: the scores cannot tell the sides apart. Use SBR's own V/H
                # flag when it has one, else fall back to names.
                vh = (fav.get("VH", "") or "").strip().upper()
                if vh in ("H", "V"):
                    fav_is_home = vh == "H"
                    st["oriented_by_vh"] += 1
                else:
                    fav_n, dog_n = normalize(fav.get("Team", "")), normalize(dog.get("Team", ""))
                    home_n, away_n = normalize(game["home_team"]), normalize(game["away_team"])
                    fav_is_home = (sim(fav_n, home_n) + sim(dog_n, away_n)) >= (
                        sim(fav_n, away_n) + sim(dog_n, home_n)
                    )
                    st["oriented_by_name"] += 1
            sign = -1.0 if fav_is_home else 1.0

            def spread(col: str, _fav=fav, _sign=sign) -> float | None:
                v = num(_fav.get(col, ""))
                return None if v is None else _sign * abs(v)

            out_rows.append({
                "game_id": game["game_id"],
                "season": season,
                "week": game["week"],
                "season_type": game["season_type"],
                "start_date": game["date"].isoformat(),
                "sbr_date": gdate.isoformat(),
                "home_team": game["home_team"],
                "away_team": game["away_team"],
                "home_points": game["home_points"],
                "away_points": game["away_points"],
                "neutral_site": game["neutral_site"],
                "sbr_favorite": fav.get("Team", ""),
                "sbr_underdog": dog.get("Team", ""),
                "favorite_is_home": int(fav_is_home),
                "spread_open": spread("Open"),
                "spread_close": spread("Close"),
                "total_open": num(dog.get("Open", "")),
                "total_close": num(dog.get("Close", "")),
                "moneyline_fav": num(fav.get("ML", "")),
                "moneyline_dog": num(dog.get("ML", "")),
                "half2_fav": num(fav.get("2H", "")),   # halftime price: result_lookahead
                "half2_dog": num(dog.get("2H", "")),
                "ml_disagrees": ml_disagrees,
                "plausibility_swap": swapped,
                "name_candidates": n_cands,
            })

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fields = list(out_rows[0].keys()) if out_rows else []
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"wrote {len(out_rows)} games -> {args.out}\n")
    print("season  rows  drop  pairs  rotbrk  unparsed  matched  unmatch  collide  "
          "mldisagr  orient(score/vh/name)")
    for s in SEASONS:
        st = stats[s]
        print(f"  {s}  {st['rows']:5d} {st['dropped_rows']:5d} {st['pairs']:6d} "
              f"{st['rot_breaks']:7d} {st['unparsed']:9d} {st['matched']:8d} "
              f"{st['unmatched']:8d} {st['collisions']:8d} {st['ml_disagrees']:9d}  "
              f"{st['oriented_by_score']}/{st['oriented_by_vh']}/{st['oriented_by_name']}"
              f"  swap={st['plausibility_swaps']}")

    validate(con, args.out)


def validate(con: duckdb.DuckDBPyConnection, out_path: Path) -> None:
    """The gate: derived spread vs the Prediction Tracker spread on the same game_id."""
    if not PT_LINES.exists():
        print(f"\nPT tape missing at {PT_LINES} - cannot validate")
        return

    # read_csv paths cannot be prepared parameters inside CREATE VIEW.
    con.execute(
        "create or replace temp view sbr as select * from read_csv('"
        + out_path.as_posix() + "', header=true)"
    )
    con.execute(
        """create or replace temp view pt as
           select try_cast(game_id as bigint) as game_id,
                  -- PT spreads are oriented to PT's home team; undo the flip.
                  case when try_cast(orientation_flipped as int) = 1
                       then -try_cast(line as double) else try_cast(line as double) end as pt_line
           from read_csv('""" + PT_LINES.as_posix() + """', header=true, all_varchar=true)
           where line is not null and line <> ''"""
    )

    print("\n=== gate: SBR spread_close vs Prediction Tracker line ===")
    print("Two independent market snapshots, so exact agreement is NOT expected -- books")
    print("close half a point apart routinely. A defect would show as a non-zero bias, a")
    print("fat tail, or sign disagreement, not as a sub-point difference.\n")
    print("season     n     bias  med|d|   <=2.0  flips  | neutral    bias  med|d|")
    for row in con.execute(
        """select s.season,
                  count(*),
                  avg(s.spread_close - p.pt_line),
                  median(abs(s.spread_close - p.pt_line)),
                  sum((abs(s.spread_close - p.pt_line) <= 2.0)::int),
                  -- a sign flip reads as SBR ~= -PT, not merely as a big difference
                  sum((abs(s.spread_close + p.pt_line) <= 0.5
                       and abs(s.spread_close - p.pt_line) > 2.0)::int),
                  avg(case when s.neutral_site then s.spread_close - p.pt_line end),
                  median(case when s.neutral_site then abs(s.spread_close - p.pt_line) end)
           from sbr s join pt p on p.game_id = s.game_id
           where s.spread_close is not null
           group by 1 order by 1"""
    ).fetchall():
        season, n, bias, med, within, flips, n_bias, n_med = row
        print(f"  {season}  {n:5d}  {bias:+7.3f}   {med:5.2f}  {100.0 * within / n:5.1f}%  "
              f"{flips:5d}  | {n_bias:+11.3f}  {n_med:5.2f}")

    n, bias, med, within, flips = con.execute(
        """select count(*), avg(s.spread_close - p.pt_line),
                  median(abs(s.spread_close - p.pt_line)),
                  sum((abs(s.spread_close - p.pt_line) <= 2.0)::int),
                  sum((abs(s.spread_close + p.pt_line) <= 0.5
                       and abs(s.spread_close - p.pt_line) > 2.0)::int)
           from sbr s join pt p on p.game_id = s.game_id
           where s.spread_close is not null"""
    ).fetchone()
    print(f"\noverall  n={n}  bias={bias:+.4f}  median|diff|={med:.2f}  "
          f"within 2.0={100.0 * within / n:.1f}%  sign flips={flips}")

    # Independent of PT: the spread must anti-correlate with home margin (repo convention
    # is negative when the home team is favoured), and the total must track points scored.
    corr_s, mean_s, mean_m = con.execute(
        """select corr(spread_close, home_points - away_points),
                  avg(spread_close), avg(home_points - away_points)
           from sbr where spread_close is not null"""
    ).fetchone()
    print(f"\nspread sign:  corr(spread_close, home margin) = {corr_s:+.3f}   "
          f"mean spread {mean_s:+.2f} vs mean margin {mean_m:+.2f}")
    corr_t, mean_t, mean_a, n_t = con.execute(
        """select corr(total_close, home_points + away_points),
                  avg(total_close), avg(home_points + away_points), count(*)
           from sbr where total_close is not null"""
    ).fetchone()
    print(f"total level:  corr(total_close, points) = {corr_t:+.3f}   "
          f"mean total {mean_t:.2f} vs mean actual {mean_a:.2f}   n={n_t}")


if __name__ == "__main__":
    main()
