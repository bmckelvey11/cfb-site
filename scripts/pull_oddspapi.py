"""Pull one oddspapi.io snapshot of Pinnacle NCAA spreads into `data/ingest/oddspapi/`.

    python scripts/pull_oddspapi.py
    python scripts/pull_oddspapi.py --bookmakers pinnacle,circasports

One request per run via /v4/odds-by-tournaments (the per-fixture endpoint costs one request
per game; the free plan is 250 a month). Each run writes a new timestamped file; snapshots are
never overwritten, because the difference between two of them IS the line movement.

Key: ODDSPAPI_API in the environment, else in .env / env.env at the repo root.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents if (p / "cfb_paths.py").is_file())
sys.path.insert(0, str(REPO))
import cfb_paths  # noqa: E402

BASE_URL = "https://api.oddspapi.io/v4"
NCAA_REGULAR_SEASON = 27653      # tournamentId from /v4/tournaments?sportId=14 (2026-09-09)
DEFAULT_BOOKMAKERS = "pinnacle"
OUT_DIR = cfb_paths.INGEST / "oddspapi"
# Cloudflare fronting the API returns 403 (error 1010) to urllib's default User-Agent.
HEADERS = {"User-Agent": "Mozilla/5.0 cfb-research/1.0", "Accept": "application/json"}


def find_token() -> str:
    for k in ("ODDSPAPI_API", "ODDSPAPI_API_KEY"):
        if os.environ.get(k):
            return os.environ[k]
    for name in (".env", "env.env"):
        path = REPO / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and line.split("=", 1)[0].strip() in ("ODDSPAPI_API", "ODDSPAPI_API_KEY"):
                return line.split("=", 1)[1].strip().strip("\"'")
    raise RuntimeError("oddspapi key not found: set ODDSPAPI_API or put it in .env")


def fetch(token: str, tournament_ids: str, bookmakers: str) -> list[dict]:
    q = urllib.parse.urlencode({"tournamentIds": tournament_ids, "bookmakers": bookmakers,
                                "oddsFormat": "american", "verbosity": 3, "apiKey": token})
    req = urllib.request.Request(f"{BASE_URL}/odds-by-tournaments?{q}", headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")[:300].replace(token, "***")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from None


def is_full_game_spread(market: dict) -> bool:
    """Pinnacle's market path is `line/<...>/<period>/spreads`; period 0 is the full game.
    `altLine/...` entries are alternate numbers and periods 1+ are halves and quarters."""
    parts = (market.get("bookmakerMarketId") or "").split("/")
    return parts[0] == "line" and parts[-1] == "spreads" and parts[-2] == "0"


def main_spreads(fixtures: list[dict]) -> int:
    """How many fixtures carry an active full-game main-line spread from any requested book."""
    n = 0
    for f in fixtures:
        for b in (f.get("bookmakerOdds") or {}).values():
            for m in (b.get("markets") or {}).values():
                if is_full_game_spread(m) and any(
                        pl.get("mainLine") and pl.get("active")
                        for o in m["outcomes"].values() for pl in o["players"].values()):
                    n += 1
                    break
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tournaments", default=str(NCAA_REGULAR_SEASON))
    ap.add_argument("--bookmakers", default=DEFAULT_BOOKMAKERS)
    args = ap.parse_args()

    token = find_token()
    print(f"=== pull oddspapi tournaments={args.tournaments} bookmakers={args.bookmakers} (1 request) ===")
    try:
        fixtures = fetch(token, args.tournaments, args.bookmakers)
    except Exception as exc:
        print(f"  FAILED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    now = datetime.now(timezone.utc)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"oddspapi_ncaa_{args.bookmakers.replace(',', '+')}_{now:%Y%m%dT%H%M%SZ}.json"
    out.write_text(json.dumps({"pulled_at": now.isoformat(), "tournament_ids": args.tournaments,
                               "bookmakers": args.bookmakers, "fixtures": fixtures}), encoding="utf-8")
    print(f"  {len(fixtures)} fixtures, {main_spreads(fixtures)} with an active main-line spread -> {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
