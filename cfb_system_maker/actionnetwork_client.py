"""Scraper over the Action Network web API — college football odds.

Two stages, mirroring the CFBD scrapers' resume-by-file pattern:

1. **scoreboard** — ``/web/v2/scoreboard/ncaaf?season={Y}&week={W}`` enumerates a
   week's games (event ids, scores, full-game embedded markets). One file per week.
2. **history** — ``/web/v2/markets/event/{id}/history?periods=...`` pulls per-book
   period odds (1H / 1Q spreads & totals) for each event id. One file per event.

Output lands in ``data/raw/actionnetwork/`` (kept separate from CFBD ``data/raw/``
because the row shapes differ). ``fetch_fn`` is injectable so tests run network-free.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

SCOREBOARD_URL = "https://api.actionnetwork.com/web/v2/scoreboard/ncaaf"
HISTORY_URL = "https://api.actionnetwork.com/web/v2/markets/event/{event_id}/history"

# Action Network periods. Full game lives in the scoreboard's embedded markets, so
# the per-event history pull only needs the period markets that aren't embedded.
#
# CAVEAT: the scoreboard's embedded full-game markets are a SNAPSHOT, not history, so
# this default means no full-game line history is ever written. The history endpoint
# does serve it -- the full-game period is named "event" (not "game", which returns an
# empty payload). `research/spread/scripts/collect_line_timing.py` pulls that separately, into
# history_event_{id}.json so it can't collide with the firsthalf/firstquarter files
# this module writes. See research/spread/docs/prediction-tracker-model-eval.md section 8.
DEFAULT_PERIODS: tuple[str, ...] = ("firsthalf", "firstquarter")
FULL_GAME_PERIOD = "event"

# Cloudflare 403s urllib's default User-Agent; a browser UA is required.
_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

Fetcher = Callable[[str, dict[str, Any]], Any]


@dataclass(frozen=True)
class AnReport:
    name: str
    files: int       # files written this run
    events: int      # games/events seen this run
    skipped: int = 0  # files already present, skipped (resume)
    errors: int = 0  # per-item failures (week/event) that were skipped, not fatal
    error: str | None = None  # last error message when errors > 0


def actionnetwork_scrape(
    seasons: list[int],
    *,
    data_dir: str | Path = "data",
    season_type: str = "reg",
    weeks: range = range(1, 16),
    periods: tuple[str, ...] = DEFAULT_PERIODS,
    only: set[str] | None = None,
    delay: float = 1.0,
    resume: bool = True,
    fetch_fn: Fetcher | None = None,
) -> list[AnReport]:
    """Pull scoreboards then per-event period odds. ``fetch_fn`` injectable for tests."""
    fetch = fetch_fn or _make_fetcher()
    reports: list[AnReport] = []
    for season in seasons:
        event_ids: list[int] = []
        if only is None or "scoreboard" in only:
            report, event_ids = _scrape_scoreboard(
                fetch, season, season_type, weeks, data_dir, delay, resume
            )
            reports.append(report)
        else:
            event_ids = _event_ids_from_disk(data_dir, season)
        if only is None or "history" in only:
            reports.append(
                _scrape_history(fetch, season, event_ids, periods, data_dir, delay, resume)
            )
    return reports


def _scrape_scoreboard(
    fetch: Fetcher,
    season: int,
    season_type: str,
    weeks: range,
    data_dir: str | Path,
    delay: float,
    resume: bool,
) -> tuple[AnReport, list[int]]:
    files = 0
    skipped = 0
    games = 0
    errors = 0
    last_error: str | None = None
    event_ids: list[int] = []
    for week in weeks:
        filename = f"scoreboard_{season}_wk{week}.json"
        if resume and _exists(data_dir, filename):
            skipped += 1
            event_ids.extend(_event_ids(_read(data_dir, filename)))
            continue
        try:  # one failing week must not abort the rest of the season
            payload = _call(fetch, SCOREBOARD_URL, {"season": season, "week": week, "seasonType": season_type}, delay)
        except Exception as exc:
            errors += 1
            last_error = f"wk{week}: {type(exc).__name__}: {exc}"
            continue
        week_games = payload.get("games", [])
        if not week_games:  # empty week — don't write, re-probe next run
            continue
        _write(data_dir, filename, payload)
        files += 1
        games += len(week_games)
        event_ids.extend(_event_ids(payload))
    return AnReport(f"scoreboard_{season}", files, games, skipped, errors, last_error), event_ids


def _scrape_history(
    fetch: Fetcher,
    season: int,
    event_ids: list[int],
    periods: tuple[str, ...],
    data_dir: str | Path,
    delay: float,
    resume: bool,
) -> AnReport:
    files = 0
    skipped = 0
    errors = 0
    last_error: str | None = None
    period_param = ",".join(periods)
    for event_id in event_ids:
        filename = f"history_{event_id}.json"
        if resume and _exists(data_dir, filename):
            skipped += 1
            continue
        try:  # one failing event must not abort the rest
            url = HISTORY_URL.format(event_id=event_id)
            payload = _call(fetch, url, {"periods": period_param}, delay)
        except Exception as exc:
            errors += 1
            last_error = f"event {event_id}: {type(exc).__name__}: {exc}"
            continue
        _write(data_dir, filename, payload)
        files += 1
    return AnReport(f"history_{season}", files, len(event_ids), skipped, errors, last_error)


def _event_ids(payload: dict[str, Any]) -> list[int]:
    return [int(g["id"]) for g in payload.get("games", []) if g.get("id") is not None]


def _event_ids_from_disk(data_dir: str | Path, season: int) -> list[int]:
    """Collect event ids from already-scraped scoreboard files (history-only runs)."""
    folder = Path(data_dir) / "raw" / "actionnetwork"
    ids: list[int] = []
    for path in sorted(folder.glob(f"scoreboard_{season}_wk*.json")):
        ids.extend(_event_ids(json.loads(path.read_text(encoding="utf-8"))))
    return ids


def _call(fetch: Fetcher, url: str, params: dict[str, Any], delay: float) -> dict[str, Any]:
    """Fetch with rate-limit retry (429 -> exponential backoff 5/10/20s)."""
    time.sleep(delay)
    for attempt in range(3):
        try:
            return fetch(url, params)
        except Exception as exc:
            if "429" in str(exc) and attempt < 2:
                time.sleep(5.0 * (2 ** attempt))
                continue
            raise
    raise RuntimeError("max retries exceeded")


def _make_fetcher() -> Fetcher:
    def fetch(url: str, params: dict[str, Any]) -> Any:
        query = urllib.parse.urlencode(params)
        request = urllib.request.Request(
            f"{url}?{query}" if query else url,
            headers={"User-Agent": _USER_AGENT},
        )
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read())

    return fetch


def _exists(data_dir: str | Path, filename: str) -> bool:
    return (Path(data_dir) / "raw" / "actionnetwork" / filename).exists()


def _read(data_dir: str | Path, filename: str) -> dict[str, Any]:
    return json.loads((Path(data_dir) / "raw" / "actionnetwork" / filename).read_text(encoding="utf-8"))


def _write(data_dir: str | Path, filename: str, payload: Any) -> Path:
    path = Path(data_dir) / "raw" / "actionnetwork" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, default=str, indent=2, sort_keys=True), encoding="utf-8")
    return path
