"""Does any postseason game sort BEFORE a regular game of the same team+season?

That is the only mechanism by which a bowl can enter a regular game's
strictly-prior window. Two ways it could happen:
  1. a postseason game with no startDate falls back to `{season}-w{week:02d}`,
     and postseason weeks restart at 1
  2. an actual startDate that precedes a regular-season game
"""
import json, sys
from pathlib import Path
from collections import defaultdict
sys.path.insert(0, r"C:\Users\mckel\dev\cfb-site")

RAW = Path(r"C:\Users\mckel\dev\cfb-site\data\raw")

missing_date_post = 0
leaks = []
for season in range(2012, 2026):
    rows = json.loads((RAW / f"games_{season}.json").read_text(encoding="utf-8"))
    by_team = defaultdict(list)
    for g in rows:
        stype = g.get("seasonType") or g.get("season_type")
        sd = g.get("startDate") or g.get("start_date")
        key = sd or f"{season:04d}-w{g.get('week', 0):02d}"
        if stype == "postseason" and not sd:
            missing_date_post += 1
        for t in (g.get("homeTeam") or g.get("home_team"), g.get("awayTeam") or g.get("away_team")):
            by_team[t].append((key, stype, g.get("id"), sd is not None))
    for team, entries in by_team.items():
        entries.sort(key=lambda e: e[0])
        seen_post = None
        for key, stype, gid, has_date in entries:
            if stype == "postseason" and seen_post is None:
                seen_post = (key, gid, has_date)
            elif stype == "regular" and seen_post is not None:
                leaks.append((season, team, seen_post, (key, gid)))
                break

print(f"postseason games with NO startDate (would fall back to week number): {missing_date_post}")
print(f"team-seasons where a postseason game sorts before a regular game: {len(leaks)}")
for s, t, p, r in leaks[:10]:
    print(f"  {s} {t}: post {p[1]} key={p[0]} has_date={p[2]}  <  regular {r[1]} key={r[0]}")
