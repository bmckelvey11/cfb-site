"""Scrape Massey Ratings college-football composite rankings.

Two-step per page: GET the HTML (it carries an obfuscated `stamp.jsonURL`
token plus `stamp.obfu`), decrypt the token to the real /json/ranks.php URL,
GET that, then de-obfuscate the numeric columns flagged `gfac`.

Commands
  discover  one request per season -> the exact list of edition dates
  fetch     one edition per date   -> full ~75-system ranking table
  update    discover the current season, fetch what is missing (weekly task)
  selftest  offline decstr check + on-disk CMP permutation check
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://masseyratings.com"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
DATA_ROOT = Path(os.environ.get("CFB_DATA_ROOT", Path(__file__).resolve().parent.parent / "data"))
OUT_DIR = DATA_ROOT / "ingest" / "massey"

_TOKEN_RE = re.compile(r'stamp\.jsonURL = "([^"]*)"')
_OBFU_RE = re.compile(r'stamp\.obfu = "([^"]*)"')


def decstr(s: str, seed: int = 2021) -> str:
    """Mirror of the site's decstr(): base64url + a 1-byte LCG stream cipher."""
    raw = base64.b64decode(s.replace("-", "+").replace("_", "/").replace(".", "="))
    out = bytearray()
    for c in raw:
        seed = (8121 * seed + 1234) % 256
        out.append((c - seed + 256) % 256)
    return out.decode("latin-1")


def deobfuscate(payload: dict, obfu: str) -> dict:
    """Undo the per-column `gfac` scrambling, in place.

    The key is a single LCG stream shared across all gfac columns (columns
    outer, rows inner) and it advances on EVERY cell -- including nulls, which
    pass through untouched. Skipping the advance on a null desyncs every value
    after it, silently.
    """
    key = int(obfu[32:])
    for ci, col in enumerate(payload["CI"]):
        gfac = col.get("gfac")
        if not gfac:
            continue
        for row in payload["DI"]:
            key = (8121 * key + 1234) % 1024
            cell = row[ci]
            boxed = isinstance(cell, list)
            v = cell[0] if boxed else cell
            if v is None:
                pass
            elif gfac == 1:
                v = v - key
            elif gfac == 2:
                v = v / (key + 1)
            else:
                v = decstr(v, key)
            if boxed:
                row[ci][0] = v
            else:
                row[ci] = v
    return payload


def _get(url: str, delay: float) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": BASE + "/"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read()
            time.sleep(delay)
            return body
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503) or attempt == 3:
                raise
            time.sleep(5 * 2 ** attempt)
    raise RuntimeError("unreachable")


def fetch_page(path: str, delay: float = 1.0) -> dict:
    """Fetch one Massey page and return its decoded JSON payload."""
    html = _get(BASE + path, delay).decode("utf-8", "replace")
    token = _TOKEN_RE.search(html)
    obfu = _OBFU_RE.search(html)
    if not token or not obfu:
        raise RuntimeError("no stamp token on " + path + " (Cloudflare block?)")
    payload = json.loads(_get(BASE + decstr(token.group(1)), delay))
    return deobfuscate(payload, obfu.group(1))


def season_editions(year: int, delay: float = 1.0) -> list:
    """Edition dates (YYYYMMDD) for one season, from the weekly archive page.

    Column titles are MM-DD with the year dropped; month >= 8 belongs to the
    season year, month <= 7 to the following calendar year (bowl/final polls).
    """
    payload = fetch_page("/ranks?s=cf%d&sym=cmp" % year, delay)
    dates = []
    for col in payload["CI"]:
        m = re.fullmatch(r"(\d{2})-(\d{2})", col["title"])
        if m:
            mm, dd = int(m.group(1)), int(m.group(2))
            dates.append("%04d%02d%02d" % (year if mm >= 8 else year + 1, mm, dd))
    return dates


def cmd_discover(args: argparse.Namespace) -> int:
    index = {}
    for year in range(args.start, args.end + 1):
        try:
            dates = season_editions(year, args.delay)
        except Exception as exc:  # one bad season must not kill the sweep
            print("%d: ERROR %s" % (year, exc), file=sys.stderr)
            continue
        if not dates:
            print("%d: none" % year)
            continue
        index[str(year)] = dates
        print("%d: %2d editions  %s .. %s" % (year, len(dates), dates[0], dates[-1]))
        print("        " + " ".join(dates))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "editions.json"
    out.write_text(json.dumps(index, indent=1), encoding="utf-8")
    total = sum(len(v) for v in index.values())
    print("\n%d editions across %d seasons -> %s" % (total, len(index), out))
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    idx_path = OUT_DIR / "editions.json"
    if args.date:
        dates = args.date
    elif idx_path.exists():
        dates = [d for v in json.loads(idx_path.read_text()).values() for d in v]
    else:
        print("run `discover` first, or pass --date", file=sys.stderr)
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for date in dates:
        dest = OUT_DIR / ("ranks_%s.json" % date)
        if dest.exists() and not args.force:
            continue
        try:
            payload = fetch_page("/ranks?s=cf&d=%s" % date, args.delay)
        except Exception as exc:
            print("%s: ERROR %s" % (date, exc), file=sys.stderr)
            continue
        rows = len(payload["DI"])
        systems = sum(1 for c in payload["CI"] if c.get("fulltitle"))
        if not rows:
            print("%s: EMPTY (no edition on this date)" % date)
            continue
        dest.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        print("%s: %d teams x %d systems -> %s" % (date, rows, systems, dest.name))
    return 0


def current_season(today: dt.date | None = None) -> int:
    """Massey season for a date: Aug-Dec belong to that year, Jan-Jul to the prior one."""
    today = today or dt.date.today()
    return today.year if today.month >= 8 else today.year - 1


def cmd_update(args: argparse.Namespace) -> int:
    """Refresh editions.json for the current season and fetch any edition not on disk."""
    season = args.season or current_season()
    dates = season_editions(season, args.delay)
    if not dates:
        print("%d: no editions published yet" % season)
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    idx_path = OUT_DIR / "editions.json"
    index = json.loads(idx_path.read_text()) if idx_path.exists() else {}
    index[str(season)] = dates
    idx_path.write_text(json.dumps(index, indent=1), encoding="utf-8")
    missing = [d for d in dates if not (OUT_DIR / ("ranks_%s.json" % d)).exists()]
    print("%d: %d editions, %d missing" % (season, len(dates), len(missing)))
    if not missing:
        return 0
    return cmd_fetch(argparse.Namespace(date=missing, force=False, delay=args.delay))


def cmd_selftest(args: argparse.Namespace) -> int:
    token = (
        "flOmHEVgrdbN5LZrVym7RNB7ukM0n7MF-fHdwnxUnWjAfaUjfcK--QsTusydNf25B8HohmQCyy8sL_LPfXkhkv"
        "_LI5PPBSYuOWv3C76xHds29T6nqCI0fXhdUxG_2R_dQuJY4A1jcp5zsWxm88VtP5YMi8XsUlOXs8WUlzf3mz59"
        "D6cOSpx439LosQ.."
    )
    expected = (
        "/json/ranks.php?argv=NXpzXzeus2C1T26fQCDlZ7Ov4rtXxUy-q0ZmVO26Xv-0bpfxTk9Zr4NWpRVGlkZ1QYhy"
        "Dp48x4839esvrwiTxiiLDbzgCx85A8BtlqzpVpY.&task=json"
    )
    assert decstr(token) == expected, "decstr broken"
    print("decstr: ok")

    files = sorted(OUT_DIR.glob("ranks_*.json"))
    if not files:
        print("no fetched editions on disk; skipped deobfuscation check")
        return 0
    checked = files[: args.limit]
    for path in checked:
        payload = json.loads(path.read_text())
        ci = next(i for i, c in enumerate(payload["CI"]) if c["title"] == "CMP")
        ranks = sorted(r[ci] for r in payload["DI"])
        assert ranks == list(range(1, len(ranks) + 1)), path.name + ": CMP is not a 1..N permutation"
    print("CMP permutation: ok (%d editions)" % len(checked))
    return 0


def main(argv: list | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--delay", type=float, default=1.0, help="seconds between HTTP calls")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("discover", help="list every edition date, one request per season")
    d.add_argument("--start", type=int, default=1996)
    d.add_argument("--end", type=int, default=2025)
    d.set_defaults(func=cmd_discover)

    f = sub.add_parser("fetch", help="download full per-system tables for edition dates")
    f.add_argument("--date", nargs="*", help="YYYYMMDD (default: everything in editions.json)")
    f.add_argument("--force", action="store_true", help="re-download existing files")
    f.set_defaults(func=cmd_fetch)

    u = sub.add_parser("update", help="discover the current season and fetch missing editions")
    u.add_argument("--season", type=int, help="override the season (default: by today's date)")
    u.set_defaults(func=cmd_update)

    s = sub.add_parser("selftest", help="verify decoding")
    s.add_argument("--limit", type=int, default=5)
    s.set_defaults(func=cmd_selftest)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
