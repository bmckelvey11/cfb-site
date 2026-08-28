"""T5: the two season types must never share a row, and their union must be complete.

Row counts prove nothing. Identity is the whole row (json with sorted keys), which is
strictly stronger than any single id field and needs no per-endpoint schema knowledge.
"""
import json, sys
from pathlib import Path

RAW = Path(r"C:\Users\mckel\dev\cfb-site\data\raw")
SIX = ["plays", "play_stats", "ppa_players_games", "game_player_stats",
       "game_team_stats", "player_success_game"]
SEASONS = range(2012, 2026)

def load(p):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
def ident(rows):
    return {json.dumps(r, sort_keys=True, default=str) for r in rows}

fail = []
print(f"{'endpoint':<22}{'post files':>11}{'post rows':>11}{'weeks seen':>26}  overlap")
print("-" * 84)
for name in SIX:
    files = rows = 0
    weeks = set()
    overlaps = []
    for s in SEASONS:
        for w in range(1, 16):
            post = load(RAW / f"{name}_{s}_post_wk{w}.json")
            if post is None:
                continue
            files += 1; rows += len(post); weeks.add(w)
            reg = load(RAW / f"{name}_{s}_wk{w}.json")
            if reg is None:
                continue
            shared = ident(reg) & ident(post)
            if shared:
                overlaps.append(f"{s} wk{w}: {len(shared)} shared rows")
    if overlaps:
        fail.append(f"{name}: " + "; ".join(overlaps[:3]))
    print(f"{name:<22}{files:>11}{rows:>11}{str(sorted(weeks)):>26}  "
          f"{'none' if not overlaps else 'OVERLAP'}")

# Ground truth: regular wk1 + postseason wk1 must equal what the API returns for `both`.
print("-" * 84)
sys.path.insert(0, r"C:\Users\mckel\dev\cfb-site")
from cfb_system_maker.cfbd_client import _load_cfbd_module, _to_dict, find_cfbd_token
cfbd = _load_cfbd_module()
cfg = cfbd.Configuration(access_token=find_cfbd_token(r"C:\Users\mckel\dev\cfb-site\env.env"))
with cfbd.ApiClient(cfg) as c:
    live = [_to_dict(x) for x in cfbd.GamesApi(c).get_game_team_stats(
        year=2024, week=1, season_type="both")]
reg = load(RAW / "game_team_stats_2024_wk1.json") or []
post = load(RAW / "game_team_stats_2024_post_wk1.json") or []
lid = {r.get("id") for r in live}
did = {r.get("id") for r in reg} | {r.get("id") for r in post}
print(f"game_team_stats 2024 wk1: disk regular={len(reg)} + postseason={len(post)} = {len(did)} ids")
print(f"                          live season_type=both = {len(lid)} ids")
print(f"                          union == live: {did == lid}")
if did != lid:
    fail.append(f"union mismatch: only_disk={len(did-lid)}, only_live={len(lid-did)}")

print("-" * 84)
for f in fail: print("FAIL:", f)
print("PASS - season types disjoint, union complete" if not fail else f"FAILED: {len(fail)}")
sys.exit(1 if fail else 0)
