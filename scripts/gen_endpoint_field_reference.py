"""Generate docs/cfbd-endpoint-field-reference.md from the vendored cfbd-python client.

CFBD's OpenAPI spec has field-level descriptions on request *parameters* only (see
`Field(description=...)` in `cfbd-python/cfbd/api/*.py`) — response models never carry
one (confirmed: only 2 of 194 model files under `cfbd-python/cfbd/models/` use
`description=`, and neither is a real field). So this script pulls the endpoint ->
response-model -> field/type structure straight from the vendored client, and every
description in the output is authored here (the COMMON/MODEL_BLURB dicts below), not
copied from upstream.

    python scripts/gen_endpoint_field_reference.py

Rerun after bumping the vendored `cfbd-python` client (new/renamed fields show up
automatically; only genuinely new jargon needs a COMMON/MODEL_BLURB addition).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))  # run as `python scripts/...`

API_DIR = REPO / "cfbd-python" / "cfbd" / "api"
MODEL_DIR = REPO / "cfbd-python" / "cfbd" / "models"
OUT = REPO / "docs" / "cfbd-endpoint-field-reference.md"

from cfb_system_maker.scrapers import (  # noqa: E402
    ENDPOINTS, ONCE, SEASON, SEASON_WEEK, GRID, PER_GAME, PER_PLAYER, ON_DEMAND,
)

API_FILE_MAP = {
    "AdjustedMetricsApi": "adjusted_metrics_api.py", "BettingApi": "betting_api.py",
    "CoachesApi": "coaches_api.py", "ConferencesApi": "conferences_api.py",
    "DraftApi": "draft_api.py", "DrivesApi": "drives_api.py", "GamesApi": "games_api.py",
    "InfoApi": "info_api.py", "MetricsApi": "metrics_api.py", "PlayersApi": "players_api.py",
    "PlaysApi": "plays_api.py", "PlayoffsApi": "playoffs_api.py", "RankingsApi": "rankings_api.py",
    "RatingsApi": "ratings_api.py", "RecruitingApi": "recruiting_api.py", "StatsApi": "stats_api.py",
    "TeamsApi": "teams_api.py", "VenuesApi": "venues_api.py",
}

MODE_LABEL = {
    ONCE: "once (no params)", SEASON: "per season", SEASON_WEEK: "per season x week",
    GRID: "down x distance grid", PER_GAME: "per game (fan-out, opt-in)",
    PER_PLAYER: "per player (fan-out, opt-in)", ON_DEMAND: "on-demand (not bulk-scraped)",
}

CATEGORY_FOR_API = {
    "AdjustedMetricsApi": "Adjusted metrics (EPA, weighted, opponent-adjusted)",
    "BettingApi": "Betting lines",
    "CoachesApi": "Coaches",
    "ConferencesApi": "Conferences",
    "DraftApi": "NFL draft",
    "DrivesApi": "Drives",
    "GamesApi": "Games",
    "InfoApi": "Info / account",
    "MetricsApi": "Advanced metrics (PPA, win probability, predicted points)",
    "PlayersApi": "Players",
    "PlaysApi": "Plays",
    "PlayoffsApi": "College Football Playoff (CFP)",
    "RankingsApi": "Rankings / polls",
    "RatingsApi": "Ratings (SP+, FPI, Elo, SRS)",
    "RecruitingApi": "Recruiting",
    "StatsApi": "Stats",
    "TeamsApi": "Teams",
    "VenuesApi": "Venues",
}


def snake(name: str) -> str:
    s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def find_return_type(api_file: Path, method: str) -> str | None:
    text = api_file.read_text(encoding="utf-8")
    m = re.search(rf"def {re.escape(method)}\(", text)
    if not m:
        return None
    depth = 0
    i = m.end() - 1
    while i < len(text):
        if text[i] == '(':
            depth += 1
        elif text[i] == ')':
            depth -= 1
            if depth == 0:
                break
        i += 1
    rest = text[i + 1:i + 200]
    m2 = re.match(r'\s*->\s*([^\:]+):', rest)
    return m2.group(1).strip() if m2 else None


def model_file_for(model_name: str) -> Path | None:
    p = MODEL_DIR / (snake(model_name) + ".py")
    return p if p.exists() else None


FIELD_RE = re.compile(r'^(\w+):\s*(.+?)\s*=\s*Field\((.*)\)\s*$')


def parse_model_fields(model_name: str):
    p = model_file_for(model_name)
    if p is None:
        return None  # not a model we can introspect (e.g. plain str)
    text = p.read_text(encoding="utf-8")
    m = re.search(rf"class {re.escape(model_name)}\(BaseModel\):(.*?)\n\n    class Config", text, re.S)
    if not m:
        m = re.search(rf"class {re.escape(model_name)}\(BaseModel\):(.*)", text, re.S)
    body = m.group(1) if m else ""
    fields = []
    for line in body.splitlines():
        line = line.strip()
        mm = FIELD_RE.match(line)
        if not mm:
            continue
        pyname, typ, args = mm.groups()
        alias_m = re.search(r'alias="([^"]+)"', args)
        alias = alias_m.group(1) if alias_m else pyname
        fields.append((pyname, alias, typ.strip()))
    return fields


def is_enum(model_name: str) -> tuple[bool, list[str]]:
    p = model_file_for(model_name)
    if p is None:
        return False, []
    text = p.read_text(encoding="utf-8")
    if "(str, Enum)" not in text and "(Enum)" not in text:
        return False, []
    vals = re.findall(r'^\s*\w+\s*=\s*[\'"]([^\'"]+)[\'"]', text, re.M)
    return True, vals


def resolve_type_model(typ: str) -> str | None:
    inner = typ
    changed = True
    while changed:
        changed = False
        for wrapper in ("Optional[", "List[", "conlist("):
            if inner.startswith(wrapper):
                inner = inner[len(wrapper):]
                inner = inner.rstrip("]")
                if wrapper == "conlist(":
                    inner = inner.split(",")[0]
                changed = True
    inner = inner.strip()
    if re.match(r'^[A-Z][A-Za-z0-9]*$', inner) and inner not in (
        "StrictInt", "StrictStr", "StrictFloat", "StrictBool", "Union", "List", "Dict"
    ):
        return inner
    return None


def simplify_type(typ: str) -> str:
    m = re.match(r'^Optional\[(.*)\]$', typ)
    core = m.group(1) if m else typ
    core = re.sub(r'conlist\(([^,\)]+).*\)', r'List[\1]', core)
    core = core.replace("StrictInt", "int").replace("StrictStr", "str")
    core = core.replace("StrictFloat", "float").replace("StrictBool", "bool")
    core = core.replace("Union[float, int]", "float").replace("Union[StrictFloat, StrictInt]", "float")
    return core


def humanize(alias: str) -> str:
    s = re.sub(r'(?<!^)(?=[A-Z])', ' ', alias)
    s = s.replace('_', ' ')
    s = re.sub(r'\s+', ' ', s).strip().lower()
    s = s.replace("epa", "EPA").replace("ppa", "PPA").replace("sp ", "SP+ ").replace(" id", " ID")
    s = s.replace("fpi", "FPI").replace("srs", "SRS").replace("elo", "Elo").replace("gsis", "GSIS")
    return s[0].upper() + s[1:] if s else s


# Exact-alias overrides — used across every model, since these names repeat everywhere.
COMMON = {
    "id": "Unique identifier for the record.",
    "season": "Season year.",
    "year": "Season year.",
    "week": "Week number within the season.",
    "seasonType": "`regular` or `postseason`.",
    "startDate": "Kickoff date/time (UTC).",
    "startTimeTBD": "True if kickoff time was not yet announced.",
    "completed": "True once the game has finished.",
    "neutralSite": "True if played at a neutral (non-home) site.",
    "conferenceGame": "True if both teams share a conference.",
    "attendance": "Reported attendance.",
    "venueId": "Venue identifier, joins to the venues endpoint.",
    "venue": "Venue name.",
    "homeId": "Home team identifier.",
    "homeTeam": "Home team name.",
    "homeConference": "Home team's conference at the time of the game.",
    "homeClassification": "Home team's division (FBS/FCS/etc).",
    "homePoints": "Home team's final score.",
    "homeLineScores": "Home team's score by quarter/period.",
    "homePostgameWinProbability": "Model-estimated home win probability after the game.",
    "homePregameElo": "Home team's Elo rating entering the game.",
    "homePostgameElo": "Home team's Elo rating after the game.",
    "awayId": "Away team identifier.",
    "awayTeam": "Away team name.",
    "awayConference": "Away team's conference at the time of the game.",
    "awayClassification": "Away team's division (FBS/FCS/etc).",
    "awayPoints": "Away team's final score.",
    "awayLineScores": "Away team's score by quarter/period.",
    "awayPostgameWinProbability": "Model-estimated away win probability after the game.",
    "awayPregameElo": "Away team's Elo rating entering the game.",
    "awayPostgameElo": "Away team's Elo rating after the game.",
    "excitementIndex": "CFBD's game-excitement metric, derived from win-probability swings.",
    "highlights": "Highlight video URL, if available.",
    "notes": "Free-text notes about the game (e.g. bowl name).",
    "playoff": "Playoff context for the game (round/bracket), if applicable.",
    "team": "Team name.",
    "teamId": "Team identifier.",
    "conference": "Conference name.",
    "conferenceId": "Conference identifier, joins to the conferences endpoint.",
    "school": "School/team name.",
    "opponent": "Opponent team name.",
    "gameId": "Game identifier, joins to the games endpoint.",
    "wins": "Win count.",
    "losses": "Loss count.",
    "ties": "Tie count.",
    "classification": "Division classification (FBS/FCS/II/III).",
    "division": "Conference division (e.g. East/West), if applicable.",
    "abbreviation": "Short abbreviation.",
    "shortDisplayName": "Short display name.",
    "displayName": "Full display name.",
    "color": "Primary brand color (hex).",
    "altColor": "Secondary brand color (hex).",
    "logos": "Logo image URLs.",
    "mascot": "Team mascot name.",
    "twitter": "Twitter/X handle.",
    "location": "Location details (city/state/lat/lon).",
    "city": "City name.",
    "state": "State/province abbreviation.",
    "zip": "Postal code.",
    "countryCode": "ISO country code.",
    "timezone": "IANA timezone name.",
    "latitude": "Latitude in decimal degrees.",
    "longitude": "Longitude in decimal degrees.",
    "elevation": "Elevation in feet.",
    "capacity": "Stadium capacity.",
    "constructionYear": "Year the venue was built.",
    "grass": "True if natural grass (false = turf).",
    "dome": "True if an enclosed/domed venue.",
    "name": "Name.",
    "firstName": "First name.",
    "lastName": "Last name.",
    "position": "Position abbreviation.",
    "height": "Height in inches.",
    "weight": "Weight in pounds.",
    "jersey": "Jersey number.",
    "homeAway": "`home` or `away`, which side of the game this row describes.",
    "spread": "Closing point spread (negative = favorite by that many points), home-team perspective unless noted.",
    "overUnder": "Total (over/under) line.",
    "provider": "Sportsbook/line provider name.",
    "formattedSpread": "Spread formatted as a display string (e.g. \"Team -3.5\").",
    "moneylineHome": "Home team moneyline odds.",
    "moneylineAway": "Away team moneyline odds.",
    "epa": "Expected Points Added — value of a play/drive/game in expected-points terms.",
    "epaAllowed": "Expected Points Added allowed (defensive perspective).",
    "ppa": "Predicted Points Added — CFBD's play-value metric, similar to EPA.",
    "rating": "Composite rating score.",
    "ranking": "Rank (1 = best) within the given scope.",
    "offense": "Offensive-side breakdown.",
    "defense": "Defensive-side breakdown.",
    "specialTeams": "Special-teams breakdown.",
    "overall": "Overall (combined) rating.",
    "rank": "Rank (1 = best) within the given scope.",
    "points": "Points value for this rating component.",
    "secondOrderWins": "Second-order (efficiency-based expected) win total.",
    "sos": "Strength of schedule rating.",
    "stuffRate": "Share of opponent run plays stopped at or behind the line of scrimmage.",
    "lineYards": "Yards attributable to the offensive line on run plays (Football Outsiders-style stat).",
    "secondLevelYards": "Run yards gained 5-10 yards past the line of scrimmage.",
    "openFieldYards": "Run yards gained 10+ yards past the line of scrimmage.",
    "havoc": "Havoc rate — share of defensive plays with a TFL, forced fumble, pass breakup, or interception.",
    "success": "Success rate — share of plays gaining enough yardage to be an on-schedule down (per Football Outsiders rules).",
    "explosiveness": "Average PPA on successful plays — a measure of big-play ability.",
    "plays": "Number of plays.",
    "drives": "Number of drives.",
    "ppaAvg": "Average PPA per play.",
    "totalPPA": "Sum of PPA across plays.",
    "cumulativePPA": "Running total of PPA.",
    "predicted": "Model-predicted value.",
    "down": "Down number (1-4).",
    "distance": "Yards to go for a first down.",
    "yardLine": "Yard line (0-100, own end zone to opponent's).",
    "yardsToGoal": "Yards remaining to the opponent's goal line.",
    "yardsGained": "Yards gained on the play.",
    "playType": "Play type (run/pass/punt/etc).",
    "playText": "Human-readable play description.",
    "period": "Quarter/period number.",
    "clock": "Game clock at the time of the play/event.",
    "offenseTeam": "Team on offense.",
    "defenseTeam": "Team on defense.",
    "offenseConference": "Offense team's conference.",
    "defenseConference": "Defense team's conference.",
    "offenseScore": "Offense team's score at the time of the play.",
    "defenseScore": "Defense team's score at the time of the play.",
    "scoring": "True if the play resulted in points.",
    "wallclock": "Real-world timestamp of the event.",
    "athleteId": "Player identifier.",
    "athleteName": "Player name.",
    "statType": "Category of statistic being recorded.",
    "stat": "Statistic value.",
    "category": "Statistic category/group.",
    "conferenceAbbreviation": "Conference abbreviation.",
    "shortConferenceName": "Short conference name.",
    "recruitType": "Recruit type (HighSchool/JUCO/PrepSchool/Transfer).",
    "stars": "Recruit star rating (1-5).",
    "rating_247": "247Sports composite recruit rating.",
    "committedTo": "School the recruit committed to.",
    "hometownInfo": "Recruit's hometown details.",
    "eligibility": "Player eligibility/class status.",
    "usage": "Share of team plays/snaps the player was involved in, by situation.",
    "returning": "Returning-production metric.",
    "totalPPAReturning": "Share of prior-season PPA production returning this season.",
    "percentPPAReturning": "Percent of prior-season PPA production returning this season.",
    "roundNum": "Draft round number.",
    "pick": "Overall draft pick number.",
    "collegeAthleteId": "College player identifier.",
    "collegeTeam": "College the player was drafted from.",
    "collegeConference": "College conference the player was drafted from.",
    "nflAthleteId": "NFL.com player identifier.",
    "nflTeam": "NFL team that drafted the player.",
    "overallPick": "Overall draft pick number.",
    "coach": "Coach name.",
    "hireDate": "Date the coach was hired.",
    "games": "Games coached.",
    "preseasonRank": "Preseason poll rank.",
    "postseasonRank": "Final/postseason poll rank.",
    "firstPlaceVotes": "Number of first-place votes received.",
    "points_poll": "Poll points.",
    "pollType": "Poll name (AP Top 25, Coaches Poll, etc).",
    "wepa": "Weighted EPA — EPA contribution weighted by the game's leverage/importance.",
    "paar": "Points Above Average Replacement on field goal attempts.",
    "pace": "Plays run per minute of possession (tempo).",
    "db": "Havoc rate credited to defensive backs specifically.",
    "dl": "Havoc rate credited to defensive linemen specifically.",
    "lb": "Havoc rate credited to linebackers specifically.",
    "front7": "Havoc rate credited to the front seven (DL + LB combined).",
}

# Model-level intro blurbs for the trickier stat models.
MODEL_BLURB = {
    "TeamSP": "Bill Connelly's SP+ rating: predictive team strength on a scale where 0 is average.",
    "ConferenceSP": "SP+ averaged to the conference level.",
    "TeamFPI": "ESPN's Football Power Index rating.",
    "TeamElo": "Elo rating (chess-style rating updated after each game).",
    "TeamSRS": "Simple Rating System: margin-of-victory rating adjusted for strength of schedule.",
    "ExpandedTeamSRS": "SRS including FCS opponents, with additional sub-components.",
    "TeamCoreRating": "CFBD's blended \"core\" rating combining multiple underlying models.",
    "GameHavocStats": "Havoc-rate breakdown (TFL/FF/PBU/INT share) for a game.",
    "AdvancedGameStat": "Per-game advanced efficiency stats (PPA, success rate, explosiveness, line yards, havoc) split by offense/defense and situation (standard downs / passing downs / rushing / passing).",
    "AdvancedSeasonStat": "Season-aggregated version of AdvancedGameStat.",
    "KickerPAAR": "Points Above Average Replacement for kickers on field goals.",
    "AdjustedTeamMetrics": "Opponent-adjusted EPA/success-rate metrics at the team-season level.",
    "PlayerWeightedEPA": "Player EPA weighted by game importance/leverage.",
    "TeamGamePredictedPointsAdded": "PPA aggregated to team-game level, split offense/defense.",
    "TeamSeasonPredictedPointsAdded": "PPA aggregated to team-season level, split offense/defense.",
    "PlayerGamePredictedPointsAdded": "PPA aggregated to player-game level.",
    "PlayerSeasonPredictedPointsAdded": "PPA aggregated to player-season level.",
    "PregameWinProbability": "Pregame win-probability model output for a game.",
    "PlayWinProbability": "Live win probability after each play in a game.",
    "PredictedPointsValue": "Expected points value for a given down/distance (predicted-points model lookup table).",
    "FieldGoalEP": "Expected points value of attempting a field goal, by distance.",
}


def get_field_desc(alias: str) -> str:
    if alias in COMMON:
        return COMMON[alias]
    return humanize(alias) + "."


visited_nested: dict[str, list | tuple] = {}


def collect_nested(model_name: str, depth: int = 0) -> None:
    if model_name in visited_nested or depth > 2:
        return
    fields = parse_model_fields(model_name)
    if fields is None:
        return
    visited_nested[model_name] = fields
    for _, _, typ in fields:
        nested = resolve_type_model(typ)
        if nested and nested not in visited_nested:
            enum, vals = is_enum(nested)
            if enum:
                visited_nested[nested] = ("ENUM", vals)
            else:
                collect_nested(nested, depth + 1)


def render_fields_table(fields) -> str:
    lines = ["| Field | Type | Description |", "|---|---|---|"]
    for _pyname, alias, typ in fields:
        nested = resolve_type_model(typ)
        disp_type = simplify_type(typ)
        note = ""
        if nested:
            enum, vals = is_enum(nested)
            if enum:
                note = f" (`{'`, `'.join(vals)}`)"
            else:
                note = f" — see [{nested}](#{nested.lower()})"
        desc = get_field_desc(alias) + note
        lines.append(f"| `{alias}` | {disp_type} | {desc} |")
    return "\n".join(lines)


def main() -> None:
    seen_endpoint_keys = set()
    sections_by_cat: dict[str, list[str]] = {}

    for e in ENDPOINTS:
        key = (e.api, e.method)
        cat = CATEGORY_FOR_API[e.api]
        api_file = API_DIR / API_FILE_MAP[e.api]
        ret = find_return_type(api_file, e.method)
        model = resolve_type_model(ret) if ret else None

        if key in seen_endpoint_keys:
            # _ngt variant of an already-documented endpoint — same schema, different filter.
            block = (
                f"### `{e.name}`\n\n"
                f"- **CFBD method:** `{e.api}.{e.method}`\n"
                f"- **Scrape mode:** {MODE_LABEL[e.mode]}\n\n"
                "Same schema as its base endpoint above. `excludeGarbageTime=true` — drops "
                "garbage-time plays before aggregating, so values differ from the unfiltered twin.\n"
            )
            sections_by_cat.setdefault(cat, []).append(block)
            continue
        seen_endpoint_keys.add(key)

        block_lines = [f"### `{e.name}`", ""]
        block_lines.append(f"- **CFBD method:** `{e.api}.{e.method}`")
        block_lines.append(f"- **Scrape mode:** {MODE_LABEL[e.mode]}")
        if e.min_season:
            block_lines.append(f"- **Data floor:** no data before {e.min_season}")
        block_lines.append("")

        if model is None:
            block_lines.append(f"Returns `{ret}` — a plain list of values, no object fields.")
        else:
            fields = parse_model_fields(model)
            if fields is None:
                block_lines.append(f"Returns `{ret}` (opaque/unmapped type — see vendored client).")
            else:
                if model in MODEL_BLURB:
                    block_lines.append(f"_{MODEL_BLURB[model]}_")
                    block_lines.append("")
                block_lines.append(render_fields_table(fields))
                collect_nested(model)
        block_lines.append("")
        sections_by_cat.setdefault(cat, []).append("\n".join(block_lines))

    out = []
    out.append("# CFBD endpoint field reference\n")
    out.append(
        "Auto-generated from the vendored `cfbd-python` client "
        "(spec version pinned in `cfbd-python/README.md`) by "
        "[`scripts/gen_endpoint_field_reference.py`](../scripts/gen_endpoint_field_reference.py). "
        "Every field description below is authored by us — CFBD's OpenAPI spec ships descriptions "
        "for request *parameters* only (see `cfbd/api/*.py`), never for response fields, so nothing "
        "here is copied from upstream docs. Regenerate after bumping the vendored client; verify "
        "names against the model source under `cfbd-python/cfbd/models/` if in doubt.\n"
    )
    out.append(
        "Endpoint list mirrors the `ENDPOINTS` registry in "
        "[`cfb_system_maker/scrapers.py`](../cfb_system_maker/scrapers.py) — see "
        "[`docs/data-coverage.md`](data-coverage.md) for which endpoints are actually scraped, "
        "on what cadence, and known data floors/gaps.\n"
    )
    out.append("## Glossary\n")
    out.append(
        "- **EPA / PPA** — Expected Points Added / Predicted Points Added: value of a play in expected-points "
        "terms. CFBD calls its own implementation PPA; EPA appears on a few adjusted-metrics models.\n"
        "- **SP+** — Bill Connelly's predictive team-strength rating.\n"
        "- **FPI** — ESPN's Football Power Index.\n"
        "- **SRS** — Simple Rating System (margin of victory, strength-of-schedule adjusted).\n"
        "- **Elo** — Chess-style rating updated after each game result.\n"
        "- **Havoc rate** — share of defensive plays with a TFL, forced fumble, pass breakup, or interception.\n"
        "- **Success rate** — share of plays gaining enough yardage to stay \"on schedule\" (Football Outsiders rules: "
        "50% of yards to go on 1st down, 70% on 2nd, 100% on 3rd/4th).\n"
        "- **Line yards / second-level yards / open-field yards** — run yardage split by how far past the line of "
        "scrimmage it was gained (offensive-line credit vs. runner credit).\n"
        "- **`excludeGarbageTime` (`_ngt` endpoints)** — drops blowout garbage-time plays before aggregating, so "
        "values differ from the unfiltered endpoint rather than being a strict subset.\n"
    )

    for cat in CATEGORY_FOR_API.values():
        if cat not in sections_by_cat:
            continue
        out.append(f"## {cat}\n")
        out.extend(sections_by_cat[cat])

    out.append("## Not bulk-scraped\n")
    out.append(
        "`/info/usage` (`InfoApi.get_usage`) is registered in the live spec but has no scraper entry — it reports "
        "API account metering (request counts), not football data. See `docs/data-coverage.md` for the full "
        "rationale.\n"
    )

    out.append("## Nested / shared types\n")
    out.append(
        "Object and enum types referenced by the response fields above, expanded once here instead of repeating "
        "inline.\n"
    )
    for nested_name, val in sorted(visited_nested.items()):
        out.append(f"### {nested_name}\n")
        if isinstance(val, tuple) and val[0] == "ENUM":
            out.append(f"Enum values: {', '.join(f'`{v}`' for v in val[1])}\n")
        else:
            out.append(render_fields_table(val))
            out.append("")

    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {OUT} ({len(visited_nested)} nested types, endpoints={len(seen_endpoint_keys)})")


if __name__ == "__main__":
    main()
