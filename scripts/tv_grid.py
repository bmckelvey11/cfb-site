"""Weekly TV grid: network rows x kickoff-time columns, one card per FBS game.

Reads the warehouse (`stg.games`, `stg.media`, `core.fact_game_line`, `stg.weather`,
`stg.venue_orientation`, `stg.rankings__polls__polls_ranks`, `stg.massey_editions`)
plus the Action Network scoreboard JSON already on disk (logos, team colours) and
writes one static HTML file per week:

    python scripts/tv_grid.py                 # current season, next unplayed week
    python scripts/tv_grid.py --season 2026 --week 3

Output: data/exports/tv_grid_<season>_wk<NN>.html, logos cached in data/exports/logos/.
Run `scripts/tv_grid.cmd` instead to refresh weather + media first.

Decisions (2026-09-17, see docs/tv-grid-2026-09-17.md): FBS-home games only; network
from CFBD media (tv row; web-only games in a compact STREAMING band); line is the
median across books (`normalize.median_line`); rank shows AP then Massey composite;
weather is the CFBD forecast with the wind arrow pointing where the wind blows *to*.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import duckdb

REPO = next(p for p in Path(__file__).resolve().parents if (p / "cfb_paths.py").is_file())
sys.path.insert(0, str(REPO))
import cfb_paths  # noqa: E402
from cfb_system_maker.normalize import median_line  # noqa: E402
from cfb_system_maker.wind import cardinal8, derive, orientation_is_usable  # noqa: E402

# ---------------------------------------------------------------- networks

BROADCAST = ("ABC", "CBS", "CW", "FOX", "NBC")
ESPN_TIER = ("ESPN", "ESPN2", "ESPNU")
CABLE = ("ACCN", "BTN", "CBSSN", "FS1", "SECN", "TNT", "USA")
KNOWN_TV = BROADCAST + ESPN_TIER + CABLE
STREAMING = "STREAMING"

NETWORK_ALIASES = {
    "SEC NETWORK": "SECN",
    "ACC NETWORK": "ACCN",
    "BIG TEN NETWORK": "BTN",
    "CBS SPORTS NETWORK": "CBSSN",
    "USA NET": "USA",
    "USA NETWORK": "USA",
    "THE CW NETWORK": "CW",
    "FOX SPORTS 1": "FS1",
    "FOX SPORTS 2": "FS2",
    "ESPN NEWS": "ESPNEWS",
}


def normalize_network(outlet: str) -> str:
    """CFBD outlet string -> short row label (`SEC Network` -> `SECN`)."""
    clean = re.sub(r"\s+", " ", outlet.strip())
    return NETWORK_ALIASES.get(clean.upper(), clean)


def row_order(labels: set[str]) -> list[str]:
    """Broadcast, ESPN family, cable, then unknown tv outlets alphabetically. STREAMING last."""
    ordered = [n for n in KNOWN_TV if n in labels]
    ordered += sorted(n for n in labels if n not in KNOWN_TV and n != STREAMING)
    if STREAMING in labels:
        ordered.append(STREAMING)
    return ordered


def pick_network(media: list[tuple[str, str]]) -> tuple[str, list[str]]:
    """(row label, extra badges) from CFBD media rows of (outlet, mediaType).

    A game with any tv outlet sits in that row and carries its streamers as badges
    (`NBC / Peacock`). Web-only games go to the STREAMING band with the streamer named.
    """
    tv = [normalize_network(o) for o, t in media if t == "tv"]
    web = [normalize_network(o) for o, t in media if t == "web"]
    tv = list(dict.fromkeys(tv))
    web = list(dict.fromkeys(w for w in web if w not in tv))
    if tv:
        # Two tv outlets is CFBD listing the same channel twice under different names.
        return tv[0], [t for t in tv[1:] if t != tv[0]] + web
    if web:
        return STREAMING, web
    return STREAMING, []


# ---------------------------------------------------------------- card text


def format_matchup(home_spread: float | None) -> dict[str, str]:
    """Spread tag beside the favourite; the other side stays blank.

    `home_spread` is CFBD's sign convention: negative when the home team is favoured.
    The total is not a side tag -- it goes in the card footer with the kickoff time.
    """
    if home_spread is None:
        return {"away": "", "home": ""}
    if home_spread == 0:
        return {"away": "", "home": "PK"}
    fav_tag = f"{-abs(home_spread):g}"
    if home_spread < 0:
        return {"away": "", "home": fav_tag}
    return {"away": fav_tag, "home": ""}


def total_text(total: float | None) -> str:
    return f"O/U {total:g}" if total is not None else ""


def rank_label(ap: int | None, massey: int | None, classification: str,
               fcs_rank: int | None) -> str:
    """`#7 · M5` for FBS (AP omitted when unranked), `FCS #6` for a ranked FCS team."""
    if classification != "fbs":
        return f"FCS #{fcs_rank}" if fcs_rank else ""
    parts = []
    if ap:
        parts.append(f"#{ap}")
    if massey:
        parts.append(f"M{massey}")
    return " · ".join(parts)


def pack_rows(intervals: list[tuple[int, int]]) -> list[int]:
    """Greedy sub-row index per interval so no two overlapping cards share a row."""
    ends: list[int] = []
    rows: list[int] = []
    order = sorted(range(len(intervals)), key=lambda i: intervals[i])
    for i in order:
        start, end = intervals[i]
        for r, row_end in enumerate(ends):
            if row_end <= start:
                ends[r] = end
                rows.append((i, r))
                break
        else:
            ends.append(end)
            rows.append((i, len(ends) - 1))
    out = [0] * len(intervals)
    for i, r in rows:
        out[i] = r
    return out


def wind_arrow_deg(direction_from: float) -> float:
    """CSS rotation for an up-arrow so it points where the wind blows *to*."""
    return (float(direction_from) + 180.0) % 360.0


def weather_text(w: dict[str, Any] | None, azimuth: float | None, indoors: bool) -> str:
    """`77°F · 0.15" · S 6 mph <arrow> · Crosswind`; `DOME` indoors; '' with no row."""
    if indoors:
        return "DOME"
    if not w or w.get("temperature") is None:
        return ""
    parts = [f"{round(w['temperature'])}°F"]
    precip = w.get("precipitation")
    if precip is not None:
        parts.append(f'{precip:.2f}"' if precip else '0"')
    speed, direction = w.get("windSpeed"), w.get("windDirection")
    if speed is not None and direction is not None:
        arrow = (f'<span class="arrow" style="transform:rotate({wind_arrow_deg(direction):g}deg)">'
                 f"&#8593;</span>")
        wind = f"{cardinal8(direction)} {round(speed)} mph {arrow}"
        rel = derive(wind_direction_deg=direction, wind_speed_mph=speed,
                     azimuth_deg=azimuth, indoors=False)["wind_relative"]
        if rel and rel != "Calm":
            wind += f" · {rel}"
        parts.append(wind)
    return " · ".join(parts)


# ---------------------------------------------------------------- data


def default_week(con: duckdb.DuckDBPyConnection, season: int) -> int:
    row = con.execute(
        "select min(week) from stg.games where season=? and seasonType='regular' "
        "and homeClassification='fbs' and not completed", [season]).fetchone()
    if row is None or row[0] is None:
        raise SystemExit(f"no unplayed FBS game in {season}; pass --week")
    return int(row[0])


def load_games(con: duckdb.DuckDBPyConnection, season: int, week: int) -> list[dict[str, Any]]:
    cols = ["gameId", "startDate", "homeTeam", "awayTeam", "homeClassification",
            "awayClassification", "neutralSite", "venueId", "dome", "azimuth_deg",
            "pitch_dist_m", "osm_sport"]
    rows = con.execute(f"""
        select g.gameId, g.startDate, g.homeTeam, g.awayTeam, g.homeClassification,
               g.awayClassification, g.neutralSite, g.venueId, v.dome,
               o.azimuth_deg, o.pitch_dist_m, o.osm_sport
        from stg.games g
        left join stg.venues v using (venueId)
        left join stg.venue_orientation o on o.venue_id = g.venueId
        where g.season=? and g.week=? and g.seasonType='regular'
          and g.homeClassification='fbs'
        order by g.startDate, g.homeTeam""", [season, week]).fetchall()
    return [dict(zip(cols, r)) for r in rows]


def load_media(con, ids: list[int]) -> dict[int, list[tuple[str, str]]]:
    out: dict[int, list[tuple[str, str]]] = {}
    for gid, outlet, kind in con.execute(
            "select gameId, outlet, mediaType from stg.media where gameId in (select unnest(?))",
            [ids]).fetchall():
        out.setdefault(gid, []).append((outlet, kind))
    return out


def load_lines(con, ids: list[int]) -> dict[int, dict[str, Any] | None]:
    by_game: dict[int, list[dict[str, Any]]] = {}
    for gid, key, spread, total in con.execute(
            "select game_id, provider_key, spread_close, total_close from core.fact_game_line "
            "where game_id in (select unnest(?))", [ids]).fetchall():
        by_game.setdefault(gid, []).append({"provider": key, "spread": spread, "overUnder": total})
    return {gid: median_line(rows) for gid, rows in by_game.items()}


def load_weather(con, ids: list[int]) -> dict[int, dict[str, Any]]:
    cols = ["temperature", "precipitation", "windSpeed", "windDirection", "gameIndoors"]
    rows = con.execute(
        f"select gameId, {', '.join(cols)} from stg.weather where gameId in (select unnest(?))",
        [ids]).fetchall()
    return {r[0]: dict(zip(cols, r[1:])) for r in rows}


def load_poll(con, season: int, week: int, poll: str) -> dict[str, int]:
    return dict(con.execute(
        "select polls_ranks_school, polls_ranks_rank from stg.rankings__polls__polls_ranks "
        "where season=? and week=? and seasonType='regular' and polls_poll=?",
        [season, week, poll]).fetchall())


def load_massey(con, season: int, before: dt.datetime) -> tuple[dict[str, int], dt.date | None]:
    """Composite rank from the latest edition dated before the week's first kickoff."""
    edition = con.execute(
        "select max(date) from stg.massey_editions where season=? and date < ?",
        [season, before.date()]).fetchone()[0]
    if edition is None:
        return {}, None
    ranks = dict(con.execute(
        "select cfbd_team, cmp_rank from stg.massey_editions where season=? and date=?",
        [season, edition]).fetchall())
    return ranks, edition


# ---------------------------------------------------------------- Action Network logos

AN_NAME_ALIASES = {
    "Massachusetts": "UMass",
    "Miami": "Miami (FL)",
    "Florida International": "FIU",
    "UL Monroe": "LA-Monroe",
    "Louisiana": "Louisiana",
    "Hawai'i": "Hawaii",
    "San José State": "San Jose St",
    "UT San Antonio": "UTSA",
    "Appalachian State": "App State",
    "Connecticut": "UConn",
    "Southern Mississippi": "Southern Miss",
    "Sam Houston": "Sam Houston",
}


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _an_matches(cfbd_name: str, team: dict[str, Any]) -> bool:
    cands = {cfbd_name, AN_NAME_ALIASES.get(cfbd_name, cfbd_name)}
    for c in cands:
        n = _norm(c)
        for k in ("display_name", "location", "full_name", "abbr"):
            v = team.get(k)
            if v and (_norm(v) == n or _norm(v).startswith(n)):
                return True
    return False


def load_an_teams(season: int, week: int) -> dict[dt.datetime, list[tuple[dict, dict]]]:
    """Kickoff (UTC) -> [(home team, away team), ...] from the AN scoreboard on disk."""
    path = cfb_paths.RAW / "actionnetwork" / f"scoreboard_{season}_wk{week}.json"
    if not path.is_file():
        print(f"warning: no AN scoreboard at {path}; cards render without logos")
        return {}
    games = json.loads(path.read_text(encoding="utf-8")).get("games", [])
    out: dict[dt.datetime, list[tuple[dict, dict]]] = {}
    for g in games:
        start = dt.datetime.fromisoformat(g["start_time"].replace("Z", "+00:00"))
        teams = {t["id"]: t for t in g.get("teams", [])}
        home, away = teams.get(g["home_team_id"]), teams.get(g["away_team_id"])
        if home and away:
            out.setdefault(start, []).append((home, away))
    return out


def match_an(an: dict, kickoff: dt.datetime, home: str, away: str) -> tuple[dict | None, dict | None]:
    start = kickoff.astimezone(dt.timezone.utc)
    for h, a in an.get(start, []):
        if _an_matches(home, h) or _an_matches(away, a):
            return h, a
    return None, None


def cache_logo(team: dict[str, Any] | None, logo_dir: Path) -> str:
    if not team or not team.get("logo"):
        return ""
    ext = Path(team["logo"].split("?")[0]).suffix or ".png"
    target = logo_dir / f"{team['id']}{ext}"
    if not target.is_file():
        try:
            urllib.request.urlretrieve(team["logo"], target)
        except Exception as exc:  # noqa: BLE001 - a missing logo must not kill the grid
            print(f"warning: logo {team['logo']}: {exc}")
            return ""
    return f"logos/{target.name}"


# ---------------------------------------------------------------- network logos

# Wikimedia Commons file titles (Category:Logos of television channels in the United
# States by name). BTN has no network logo on Commons; the conference mark stands in.
NETWORK_LOGOS = {
    "ABC": "ABC-2021-LOGO.svg",
    "CBS": "CBS logo (2020).svg",
    "CW": "The CW 2024.svg",
    "FOX": "Fox Broadcasting Company logo (2019).svg",
    "NBC": "NBC logo 2022.svg",
    "ESPN": "ESPN wordmark.svg",
    "ESPN2": "ESPN2 logo.svg",
    "ESPNU": "ESPN U logo.svg",
    "ACCN": "ACC Network logo fc db.svg",
    "BTN": "Big Ten Conference logo.svg",
    "CBSSN": "CBS Sports Network 2021.svg",
    "FS1": "2015 Fox Sports 1 logo.svg",
    "SECN": "SEC Network (2024).svg",
    "TNT": "TNT Logo 2016.svg",
    "USA": "USA Network logo (2016).svg",
}
COMMONS_FILEPATH = "https://commons.wikimedia.org/wiki/Special:FilePath/"
USER_AGENT = "cfb-tv-grid/0.1 (https://github.com/bmckelvey11)"


def cache_network_logo(label: str, logo_dir: Path) -> str:
    """Relative path to the cached Commons SVG for a network row, '' when none."""
    title = NETWORK_LOGOS.get(label)
    if not title:
        return ""
    target = logo_dir / "net" / f"{label}.svg"
    if not target.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(COMMONS_FILEPATH + urllib.parse.quote(title),
                                     headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                target.write_bytes(resp.read())
        except Exception as exc:  # noqa: BLE001 - fall back to the text label
            print(f"warning: network logo {title}: {exc}")
            return ""
    return f"logos/net/{target.name}"


# ---------------------------------------------------------------- render

SLOT_MIN = 15
CARD_SLOTS = 14  # 3.5 h
STREAM_SLOTS = 8  # 2 h: streaming cards are compact so the band packs tighter
LABEL_W = 96

CSS = """
:root { color-scheme: dark; }
body { margin:0; background:#0b1a2e; color:#eef3fa; font:12px/1.25 Inter, Arial, sans-serif; }
h1 { margin:14px 16px 4px; font-size:18px; }
h2 { margin:18px 16px 6px; font-size:14px; color:#9db4d0; text-transform:uppercase; letter-spacing:.08em; }
.meta { margin:0 16px 8px; color:#7f95b3; }
.day { overflow-x:auto; padding:0 16px 8px; }
.grid { display:grid; position:relative; min-width:100%; }
.grid > .t { grid-row:1; text-align:left; font-size:10px; color:#8ea3c0; border-left:1px solid #1e3352; padding:2px 3px; white-space:nowrap; }
.net { grid-column:1; position:sticky; left:0; z-index:2; background:#102440; border-top:1px solid #1e3352;
       display:flex; align-items:center; justify-content:center; font-weight:700; font-size:13px; text-align:center; padding:4px; }
.net img { width:72px; height:34px; object-fit:contain; background:#fff; border-radius:4px; padding:3px 5px; }
.band { border-top:1px solid #1e3352; grid-column:2 / -1; }
.card { margin:3px 1px; border-radius:4px; overflow:hidden; background:#16305a; display:flex; flex-direction:column; min-width:0; box-shadow:0 1px 2px #0006; }
.top { display:flex; align-items:stretch; height:32px; }
.side { flex:1 1 0; display:flex; align-items:center; gap:5px; padding:0 6px; min-width:0; font-weight:700; text-transform:uppercase; font-size:11px; white-space:nowrap; overflow:hidden; }
.side.home { justify-content:flex-end; text-align:right; }
.side img { width:24px; height:24px; object-fit:contain; background:#fff; border-radius:3px; padding:1px; flex:none; }
.side .rk { font-weight:400; font-size:10px; opacity:.85; }
.side .tag { font-weight:400; font-size:11px; opacity:.95; }
.sep { flex:none; padding:0 4px; display:flex; align-items:center; font-size:11px; color:#c9d6e8; background:#0f223f; }
.foot { display:flex; justify-content:space-between; gap:8px; padding:2px 6px; font-size:10px; color:#c3d0e2; background:#0f223f; white-space:nowrap; overflow:hidden; }
.arrow { display:inline-block; font-weight:700; }
.card.streaming { background:#122744; flex-direction:row; }
.card.streaming .top { height:26px; flex:1 1 0; min-width:0; }
.card.streaming .foot { flex:0 0 auto; flex-direction:column; justify-content:center; gap:0; padding:0 5px; font-size:9px; }
.card.streaming .side { font-size:10px; }
.card.streaming .side img { width:18px; height:18px; }
"""


def _slot(t: dt.datetime, axis_start: dt.datetime) -> int:
    return int((t - axis_start).total_seconds() // (SLOT_MIN * 60))


def render_day(day: dt.date, games: list[dict[str, Any]], net_logos: dict[str, str]) -> str:
    kicks = [g["kickoff"] for g in games]
    first = min(kicks).replace(minute=(min(kicks).minute // 30) * 30, second=0, microsecond=0)
    axis_start = first - dt.timedelta(minutes=30)
    axis_end = max(kicks) + dt.timedelta(hours=4)
    n_slots = _slot(axis_end, axis_start) + 1
    cols = f"{LABEL_W}px repeat({n_slots}, minmax(30px, 1fr))"

    parts = [f'<div class="grid" style="grid-template-columns:{cols}">']
    t = axis_start
    while t <= axis_end:
        col = _slot(t, axis_start) + 2
        parts.append(f'<div class="t" style="grid-column:{col} / span 2">{t.strftime("%I:%M %p").lstrip("0")}</div>')
        t += dt.timedelta(minutes=30)

    by_net: dict[str, list[dict[str, Any]]] = {}
    for g in games:
        by_net.setdefault(g["network"], []).append(g)

    row = 2
    for net in row_order(set(by_net)):
        items = by_net[net]
        span = STREAM_SLOTS if net == STREAMING else CARD_SLOTS
        intervals = [(_slot(g["kickoff"], axis_start), _slot(g["kickoff"], axis_start) + span)
                     for g in items]
        sub = pack_rows(intervals)
        n_sub = max(sub) + 1
        cls = "streaming" if net == STREAMING else ""
        logo = net_logos.get(net)
        label = f'<img src="{html.escape(logo)}" alt="{html.escape(net)}" title="{html.escape(net)}">' if logo else html.escape(net)
        parts.append(f'<div class="net {cls}" style="grid-row:{row} / span {n_sub}">{label}</div>')
        parts.append(f'<div class="band" style="grid-row:{row} / span {n_sub}"></div>')
        for g, (start, _), r in zip(items, intervals, sub):
            parts.append(
                f'<div class="card {cls}" style="grid-row:{row + r}; grid-column:{start + 2} / span {span}">'
                f"{render_card(g)}</div>")
        row += n_sub
    parts.append("</div>")
    return f"<h2>{day.strftime('%A %b %d')}</h2><div class=\"day\">{''.join(parts)}</div>"


def _side(g: dict[str, Any], side: str) -> str:
    name = html.escape(g[f"{side}_name"])
    rank = html.escape(g[f"{side}_rank"])
    tag = html.escape(g["tags"][side])
    logo = g[f"{side}_logo"]
    img = f'<img src="{html.escape(logo)}" alt="">' if logo else ""
    colour = g[f"{side}_color"]
    style = f' style="background:#{colour}"' if colour else ""
    inner = ((f'<span class="rk">{rank}</span> ' if rank else "") + name
             + (f' <span class="tag">{tag}</span>' if tag else ""))
    if side == "home":
        return f'<div class="side home"{style}>{inner}{img}</div>'
    return f'<div class="side away"{style}>{img}{inner}</div>'


def render_card(g: dict[str, Any]) -> str:
    sep = "vs." if g["neutral"] else "@"
    badge = " / ".join([g["network"]] + g["badges"]) if g["network"] != STREAMING else " / ".join(g["badges"])
    kick = g["kickoff"].strftime("%I:%M %p").lstrip("0")
    foot = " · ".join(x for x in (kick, g["total"], g["weather"]) if x)
    return (f'<div class="top">{_side(g, "away")}<div class="sep">{sep}</div>{_side(g, "home")}</div>'
            f'<div class="foot"><span>{foot}</span><span>{html.escape(badge)}</span></div>')


def render_html(season: int, week: int, games: list[dict[str, Any]], meta: str,
                net_logos: dict[str, str]) -> str:
    days: dict[dt.date, list[dict[str, Any]]] = {}
    for g in games:
        days.setdefault(g["kickoff"].date(), []).append(g)
    body = "".join(render_day(d, days[d], net_logos) for d in sorted(days))
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>CFB TV grid {season} wk{week}</title><style>{CSS}</style></head><body>"
            f"<h1>{season} week {week} · kickoff ET</h1><p class='meta'>{html.escape(meta)}</p>"
            f"{body}</body></html>")


# ---------------------------------------------------------------- main


def build(season: int, week: int | None, out_dir: Path) -> Path:
    con = duckdb.connect(str(cfb_paths.DB_PATH), read_only=True)
    if week is None:
        week = default_week(con, season)
    games = load_games(con, season, week)
    if not games:
        raise SystemExit(f"no FBS games for {season} week {week}")
    ids = [g["gameId"] for g in games]
    media, lines, weather = load_media(con, ids), load_lines(con, ids), load_weather(con, ids)
    ap = load_poll(con, season, week, "AP Top 25")
    fcs = load_poll(con, season, week, "FCS Coaches Poll")
    massey, edition = load_massey(con, season, min(g["startDate"] for g in games))
    an = load_an_teams(season, week)
    logo_dir = out_dir / "logos"
    logo_dir.mkdir(parents=True, exist_ok=True)

    cards: list[dict[str, Any]] = []
    missing_weather = missing_logo = missing_line = 0
    for g in games:
        gid = g["gameId"]
        net, badges = pick_network(media.get(gid, []))
        line = lines.get(gid) or {}
        if not line:
            missing_line += 1
        w = weather.get(gid)
        if w is None:
            missing_weather += 1
        indoors = bool(g["dome"]) or bool(w and w.get("gameIndoors"))
        azimuth = g["azimuth_deg"] if orientation_is_usable(g) else None
        h_an, a_an = match_an(an, g["startDate"], g["homeTeam"], g["awayTeam"])
        if an and (h_an is None or a_an is None):
            missing_logo += 1
            print(f"  no AN match: {g['awayTeam']} @ {g['homeTeam']} {g['startDate']:%a %I:%M%p}")
        cards.append({
            "kickoff": g["startDate"],
            "network": net,
            "badges": badges,
            "neutral": bool(g["neutralSite"]),
            "home_name": g["homeTeam"], "away_name": g["awayTeam"],
            "home_rank": rank_label(ap.get(g["homeTeam"]), massey.get(g["homeTeam"]),
                                    g["homeClassification"], fcs.get(g["homeTeam"])),
            "away_rank": rank_label(ap.get(g["awayTeam"]), massey.get(g["awayTeam"]),
                                    g["awayClassification"] or "", fcs.get(g["awayTeam"])),
            "tags": format_matchup(line.get("spread")),
            "total": total_text(line.get("overUnder")),
            "weather": weather_text(w, azimuth, indoors),
            "home_logo": cache_logo(h_an, logo_dir), "away_logo": cache_logo(a_an, logo_dir),
            "home_color": (h_an or {}).get("primary_color", ""),
            "away_color": (a_an or {}).get("primary_color", ""),
        })

    meta = (f"{len(cards)} FBS games · line = median across books · rank = AP wk{week}"
            f"{' · Massey ' + edition.isoformat() if edition else ' · Massey n/a'}"
            f" · weather = CFBD forecast · generated {dt.datetime.now():%Y-%m-%d %H:%M}")
    out = out_dir / f"tv_grid_{season}_wk{week:02d}.html"
    net_logos = {n: cache_network_logo(n, logo_dir) for n in {c["network"] for c in cards}}
    net_logos = {n: p for n, p in net_logos.items() if p}
    out.write_text(render_html(season, week, cards, meta, net_logos), encoding="utf-8")
    for label, n in (("weather", missing_weather), ("line", missing_line), ("logo", missing_logo)):
        if n:
            print(f"warning: {n} game(s) without {label}")
    if edition is None:
        print("warning: no Massey edition for this season in stg.massey_editions")
    print(out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--season", type=int, default=cfb_paths.current_season())
    ap.add_argument("--week", type=int)
    ap.add_argument("--out-dir", type=Path, default=cfb_paths.DATA_ROOT / "exports")
    args = ap.parse_args()
    build(args.season, args.week, args.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
