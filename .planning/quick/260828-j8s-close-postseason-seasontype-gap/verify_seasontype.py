"""T4: did postseason arrive WITHOUT disturbing a single regular-season row?

A total row count answers neither question. Every file on disk before this
re-scrape was regular-only, so each baseline `total` IS that file's regular count.
"""
import json, sys
from pathlib import Path
from collections import Counter

RAW = Path(r"C:\Users\mckel\dev\cfb-site\data\raw")
BASE = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
SEASONS = [str(s) for s in range(2012, 2026)]

TYPED = ["games","lines","media","weather","rankings","pregame_win_prob",
         "ppa_games","advanced_game_stats","game_havoc_stats"]   # carry seasonType per row
BY_GAME = ["drives"]                                             # no seasonType; join on gameId
AGG = ["elo","player_season_stats","player_success_season"]      # season aggregates

def stype(r):
    return (r.get("seasonType") or r.get("season_type")) if isinstance(r, dict) else None

def rows(name, s):
    p = RAW / f"{name}_{s}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

fail, warn = [], []
print(f"{'endpoint':<23}{'regular':>10}{'baseline':>10}{'post':>8}  verdict")
print("-" * 66)

# regular-season game ids per season, for the drives join
reg_ids = {}
for s in SEASONS:
    g = rows("games", s) or []
    reg_ids[s] = {r["id"] for r in g if stype(r) == "regular"}

for name in TYPED:
    reg_t = post_t = base_t = 0
    bad = []
    for s in SEASONS:
        b = BASE[name].get(s)
        r = rows(name, s)
        if b is None and r is None:
            continue
        if r is None:
            fail.append(f"{name} {s}: file vanished"); continue
        # 2025 games/lines already carried postseason before this re-scrape, so the
        # baseline's regular count is not always its total.
        b_reg = b["by_season_type"].get("regular", b["total"])
        b_post = b["by_season_type"].get("postseason", 0)
        c = Counter(stype(x) for x in r)
        reg, post = c.get("regular", 0), c.get("postseason", 0)
        reg_t += reg; post_t += post; base_t += b_reg
        if reg != b_reg:
            bad.append(f"{s}: regular {b_reg}->{reg}")
        if post < b_post:
            bad.append(f"{s}: postseason lost {b_post}->{post}")
    verdict = "OK" if not bad else "REGRESSION " + "; ".join(bad)
    if bad: fail.append(f"{name}: " + "; ".join(bad))
    if not bad and post_t == 0: warn.append(f"{name}: no postseason rows arrived")
    print(f"{name:<23}{reg_t:>10}{base_t:>10}{post_t:>8}  {verdict}")

for name in BY_GAME:
    reg_t = post_t = base_t = 0
    bad = []
    for s in SEASONS:
        b = BASE[name].get(s); r = rows(name, s)
        if b is None and r is None: continue
        if r is None: fail.append(f"{name} {s}: file vanished"); continue
        reg = sum(1 for x in r if x.get("gameId") in reg_ids[s])
        reg_t += reg; post_t += len(r) - reg; base_t += b["total"]
        if reg != b["total"]:
            bad.append(f"{s}: regular {b['total']}->{reg}")
    if bad: fail.append(f"{name}: " + "; ".join(bad))
    print(f"{name:<23}{reg_t:>10}{base_t:>10}{post_t:>8}  {'OK' if not bad else 'REGRESSION'}")

print("-" * 66)
print("season aggregates (no per-row season type; values shift by design):")
for name in AGG:
    new_t = base_t = 0
    for s in SEASONS:
        b = BASE[name].get(s); r = rows(name, s)
        if b is None and r is None: continue
        if r is None: fail.append(f"{name} {s}: file vanished"); continue
        new_t += len(r); base_t += b["total"]
        if len(r) < b["total"]:
            fail.append(f"{name} {s}: rows lost {b['total']}->{len(r)}")
    print(f"  {name:<21}{new_t:>10}{base_t:>10}  delta {new_t - base_t:+}")

print("-" * 66)
for w in warn: print("WARN:", w)
for f in fail: print("FAIL:", f)
print(("FAILED: %d" % len(fail)) if fail else "PASS - no regular-season row disturbed")
sys.exit(1 if fail else 0)
