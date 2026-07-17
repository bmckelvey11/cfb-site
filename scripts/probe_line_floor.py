"""Bounded, token-safe live CFBD betting-line coverage probe (DATA-01).

Re-confirms the historical betting-line floor against the *live* CFBD API,
upgrading the dated on-disk evidence (2013 floor, snapshot 2026-06-13).

For each season in 2008..2013 it calls ``BettingApi.get_lines(year, provider="consensus")``
and counts games that carry a *usable* line -- matching ``normalize._select_line``:
a game is usable if any of its ``lines`` has a non-None ``spread`` OR ``overUnder``.
The earliest season with a usable count > 0 is the confirmed floor.

Security: the API token is resolved ONLY via ``find_cfbd_token`` and is never
printed, logged, or written anywhere. Output is season numbers + counts only.

Run from the repo root::

    python scripts/probe_line_floor.py

Requires the vendored ``cfbd-python`` clone restored and a pydantic v1 runtime
(the client pins ``pydantic >=1.10.5, <2``); ``_load_cfbd_module`` path-injects it.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Running as `python scripts/probe_line_floor.py` puts scripts/ on sys.path,
# not the repo root -- add the repo root so `cfb_system_maker` imports resolve.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from cfb_system_maker.cfbd_client import _load_cfbd_module, find_cfbd_token  # noqa: E402

PROBE_SEASONS = range(2008, 2014)  # 2008..2013 inclusive
PROVIDER = "consensus"


def _line_usable(line) -> bool:
    """A line is usable if it carries a spread or an over/under (mirrors _select_line)."""
    spread = getattr(line, "spread", None)
    over_under = getattr(line, "over_under", None)
    if over_under is None:
        over_under = getattr(line, "overUnder", None)
    return spread is not None or over_under is not None


def _usable_game_count(betting_games) -> int:
    """Count games with at least one usable line (game-level, matching normalize)."""
    count = 0
    for game in betting_games:
        lines = getattr(game, "lines", None) or []
        if any(_line_usable(line) for line in lines):
            count += 1
    return count


def main() -> int:
    cfbd = _load_cfbd_module()
    configuration = cfbd.Configuration(access_token=find_cfbd_token())

    earliest_usable = None
    print(f"CFBD line-coverage probe (provider={PROVIDER}) seasons 2008-2013")
    with cfbd.ApiClient(configuration) as api_client:
        betting_api = cfbd.BettingApi(api_client)
        for season in PROBE_SEASONS:
            try:
                betting_games = betting_api.get_lines(year=season, provider=PROVIDER)
                count = _usable_game_count(betting_games)
            except Exception as exc:  # noqa: BLE001 - one season must not abort the sweep
                print(f"  {season} -> SKIP ({type(exc).__name__}: {exc})")
                continue
            print(f"  {season} -> {count} usable-line games")
            if count > 0 and earliest_usable is None:
                earliest_usable = season

    if earliest_usable is None:
        print("earliest usable-line season: NONE (no usable lines found in probed range)")
    else:
        print(f"earliest usable-line season: {earliest_usable}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
