"""One day's spread board: market consensus vs Glicko P1 and the Prediction Tracker panel.

For every FBS game kicking off on an Eastern-time date, joins

* the market -- the median home spread across the books in one the-odds-api snapshot, plus
  the best number on each side;
* Glicko P1 (`data/processed/ratings/glicko_ratings_<season>.csv`, from
  `scripts/glicko_ratings_table.py` on feat/glicko-ratings): home margin
  r_home - r_away + 2 (no home edge at a neutral site), forecast SD
  sqrt(rd_home^2 + rd_away^2 + 13.5^2);
* the Prediction Tracker panel from `weekly_slate_latest.csv` (consensus and E4), where PT
  covers the game.

Convention throughout: spreads are the **home** line, negative = home favoured (the book
convention). Model lines are converted to that convention.

This is a display, not a bet signal. Glicko P1 failed the encompassing gate against the open
(docs/glicko-ratings-2026-09-24.md on feat/glicko-ratings), and the slate's served `edge` is
mostly the market's own move sign-flipped (research/spread/docs/actionable-picks-2026-09-17.md).

    python research/spread/scripts/daily_spread_breakdown.py --date 2026-10-17 \
        --odds data/ingest/oddsapi/odds_americanfootball_ncaaf_<stamp>.json \
        --games data/raw/games_2026.json \
        --glicko data/processed/ratings/glicko_ratings_2026.csv \
        --slate data/processed/weekly_slate_latest.csv --out spread_board_2026-10-17.csv
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import unicodedata
from datetime import date, datetime, timedelta, timezone

import pandas as pd

HFA = 2.0          # FROZEN_P1 params["hfa"]
SIGMA_PRED = 13.5  # SIGMA_PRED_P1
ET = timezone(timedelta(hours=-4))  # EDT; good through early November

# CFBD name -> the head the-odds-api uses once the mascot is stripped, where they differ.
ALIASES = {
    "app state": ["appalachian state"],
    "massachusetts": ["umass"],
    "southern miss": ["southern mississippi"],
    "uconn": ["connecticut"],
    "hawaii": ["hawaii rainbow"],
    "florida international": ["fiu", "florida intl"],
    "sam houston": ["sam houston state"],
    "louisiana": ["louisiana ragin", "louisiana lafayette"],
    "ul monroe": ["louisiana monroe", "ul monroe"],
    "utsa": ["ut san antonio", "utsa"],
    "miami": ["miami"],
    "miami oh": ["miami oh", "miami ohio"],
    "san jose state": ["san jose state"],
    "nc state": ["north carolina state", "nc state"],
    "southern methodist": ["smu"],
}

# Prediction Tracker spellings -> CFBD, for the slate join.
PT_ALIASES = {
    "miami fla": "miami", "miami ohio": "miami oh", "west va": "west virginia",
    "troy st": "troy", "louisiana lafayette": "louisiana", "louisiana monroe": "ul monroe",
    "texas san antonio": "utsa", "florida intl": "florida international",
    "middle tenn": "middle tennessee", "southern miss": "southern miss",
    "appalachian st": "app state", "massachusetts": "massachusetts", "kent": "kent state",
    "san jose st": "san jose state", "hawaii": "hawaii", "connecticut": "uconn",
    "sam houston st": "sam houston", "nc state": "nc state", "north carolina st": "nc state",
    "mississippi": "ole miss", "southern miss.": "southern miss",
}


def norm(name: str) -> str:
    folded = unicodedata.normalize("NFKD", str(name).lower())
    folded = "".join(c for c in folded if not unicodedata.combining(c)).replace("'", "")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", folded)).strip()


def pt_norm(name: str) -> str:
    s = norm(name)
    s = PT_ALIASES.get(s, s)
    s = re.sub(r"\bst\b", "state", s)
    s = re.sub(r"\bmich\b", "michigan", s)
    s = re.sub(r"\bill\b", "illinois", s)
    return PT_ALIASES.get(s, s)


def heads(odds_name: str) -> list[str]:
    """The odds name with 0, 1, or 2 trailing mascot tokens stripped."""
    parts = odds_name.split()
    return [norm(" ".join(parts[:k])) for k in range(len(parts), max(0, len(parts) - 3), -1)]


def names_match(cfbd: str, odds_name: str) -> bool:
    targets = {norm(cfbd), *ALIASES.get(norm(cfbd), [])}
    return any(h in targets for h in heads(odds_name))


def market(event: dict, home_odds: str) -> dict:
    points, best_home, best_away = [], None, None
    for book in event["bookmakers"]:
        for m in book["markets"]:
            if m["key"] != "spreads":
                continue
            for o in m["outcomes"]:
                if o["name"] == home_odds:
                    points.append(o["point"])
                    if best_home is None or o["point"] > best_home[0]:
                        best_home = (o["point"], book["title"], o["price"])
                elif best_away is None or o["point"] > best_away[0]:
                    best_away = (o["point"], book["title"], o["price"])
    if not points:
        return {}
    return {
        "mkt_spread": statistics.median(points), "n_books": len(points),
        "mkt_lo": min(points), "mkt_hi": max(points),
        "best_home": f"{best_home[0]:+g} {best_home[1]} {best_home[2]:+d}",
        "best_away": f"{best_away[0]:+g} {best_away[1]} {best_away[2]:+d}" if best_away else "",
    }


def phi(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def build(day: date, odds: dict, games: list, glicko: pd.DataFrame, slate: pd.DataFrame | None):
    rating = {norm(t): (r, rd, sub) for t, r, rd, sub in
              zip(glicko.team, glicko.rating, glicko.rd, glicko.subdivision)}
    pt = {}
    if slate is not None:
        for _, s in slate.iterrows():
            pt[(pt_norm(s.road), pt_norm(s.home))] = s
    events = [(datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00")), e)
              for e in odds["events"]]
    rows = []
    for g in games:
        kick = datetime.fromisoformat(g["startDate"].replace("Z", "+00:00"))
        if kick.astimezone(ET).date() != day:
            continue
        if "fbs" not in (g["homeClassification"], g["awayClassification"]):
            continue
        home, away, neutral = g["homeTeam"], g["awayTeam"], bool(g["neutralSite"])
        row = {"kick_et": kick.astimezone(ET).strftime("%a %I:%M%p"), "away": away, "home": home,
               "neutral": neutral, "fcs_game": g["homeClassification"] != g["awayClassification"]}
        ev = next((e for t, e in events if abs((t - kick).total_seconds()) <= 6 * 3600
                   and names_match(home, e["home_team"]) and names_match(away, e["away_team"])),
                  None)
        flipped = False
        if ev is None:  # the feed sometimes lists neutral-site games the other way round
            ev = next((e for t, e in events if abs((t - kick).total_seconds()) <= 6 * 3600
                       and names_match(home, e["away_team"]) and names_match(away, e["home_team"])),
                      None)
            flipped = ev is not None
        if ev is not None:
            m = market(ev, ev["away_team"] if flipped else ev["home_team"])
            row.update(m)
        rh, ra = rating.get(norm(home)), rating.get(norm(away))
        if rh and ra:
            margin = rh[0] - ra[0] + (0.0 if neutral else HFA)
            sd = math.sqrt(rh[1] ** 2 + ra[1] ** 2 + SIGMA_PRED ** 2)
            row.update(glicko_spread=round(-margin, 1), glicko_sd=round(sd, 1))
            if "mkt_spread" in row:
                row["glicko_edge"] = round(row["mkt_spread"] - row["glicko_spread"], 1)
                row["glicko_p_home_cover"] = round(phi((margin + row["mkt_spread"]) / sd), 3)
        s = pt.get((norm(away), norm(home))) if pt else None
        if s is None and pt:
            s = next((v for (r_, h_), v in pt.items()
                      if {r_, h_} == {norm(away), norm(home)}), None)
        if s is not None:
            sign = 1 if pt_norm(s.home) == norm(home) else -1  # slate is positive = home favoured
            row.update(pt_consensus=round(-sign * s.consensus, 1), pt_e4=round(-sign * s.E4, 1),
                       pt_open=round(-sign * s.open_pt, 1) if pd.notna(s.open_pt) else None)
            if "mkt_spread" in row:
                row["pt_edge"] = round(row["mkt_spread"] - row["pt_consensus"], 1)
        rows.append(row)
    df = pd.DataFrame(rows)
    return df.sort_values(["kick_et", "home"], key=lambda c: c if c.name != "kick_et" else
                          pd.to_datetime(c.str[4:], format="%I:%M%p")).reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, type=date.fromisoformat)
    ap.add_argument("--odds", required=True)
    ap.add_argument("--games", required=True)
    ap.add_argument("--glicko", required=True)
    ap.add_argument("--slate")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    odds = json.load(open(a.odds))
    games = json.load(open(a.games))
    glicko = pd.read_csv(a.glicko)
    slate = pd.read_csv(a.slate) if a.slate else None
    df = build(a.date, odds, games, glicko, slate)
    df.to_csv(a.out, index=False)
    print(f"odds pulled {odds['pulled_at']}; {len(df)} FBS games on {a.date}; "
          f"{df.mkt_spread.notna().sum()} with a market, {df.glicko_spread.notna().sum()} Glicko, "
          f"{df.pt_consensus.notna().sum() if 'pt_consensus' in df else 0} PT")
    print(df[df.mkt_spread.isna()][["away", "home"]].to_string())


if __name__ == "__main__":
    main()
