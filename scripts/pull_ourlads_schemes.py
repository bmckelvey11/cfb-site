"""Scrape team/coach/offensive-defensive scheme labels from Ourlads' NCAA
depth-chart roster pages (one row per FBS team).

Team list (slug + id pairs) was pulled from the roster.aspx links on
https://www.ourlads.com/ncaa-football-depth-charts/default.aspx and is
hardcoded below -- the site has no API and the team list changes rarely
enough that re-scraping the index isn't worth automating.

    python scripts/pull_ourlads_schemes.py
    python scripts/pull_ourlads_schemes.py --out data/ourlads_schemes.csv
"""

import argparse
import csv
import re
import time
from pathlib import Path

import requests

import sys
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from cfb_paths import DATA_ROOT  # noqa: E402

BASE = "https://www.ourlads.com/ncaa-football-depth-charts/roster.aspx?s={slug}&id={id}"

# (slug, id) pairs scraped from default.aspx's roster.aspx links.
TEAMS = [
    ("army", "90038"), ("charlotte", "92936"), ("east-carolina", "90452"),
    ("florida-atlantic", "90521"), ("memphis", "91050"), ("navy", "91257"),
    ("north-texas", "92660"), ("rice", "91740"), ("south-florida", "91855"),
    ("temple", "91970"), ("tulane", "92131"), ("tulsa", "92154"),
    ("uab", "92177"), ("utsa", "92683"),
    ("boston-college", "90153"), ("california", "90245"), ("clemson", "90314"),
    ("duke", "90406"), ("florida-state", "90544"), ("georgia-tech", "90613"),
    ("louisville", "90958"), ("miami", "91073"), ("north-carolina", "91395"),
    ("nc-state", "91280"), ("pittsburgh", "91694"), ("smu", "91809"),
    ("stanford", "91901"), ("syracuse", "91924"), ("virginia", "92384"),
    ("virginia-tech", "92407"), ("wake-forest", "92430"),
    ("illinois", "90705"), ("indiana", "90728"), ("iowa", "90751"),
    ("maryland", "91027"), ("michigan", "91119"), ("michigan-state", "91142"),
    ("minnesota", "91188"), ("nebraska", "91303"), ("northwestern", "91464"),
    ("ohio-state", "91533"), ("oregon", "91625"), ("penn-state", "91671"),
    ("purdue", "91717"), ("rutgers", "91763"), ("ucla", "92223"),
    ("usc", "92269"), ("washington", "92453"), ("wisconsin", "92545"),
    ("arizona", "89946"), ("arizona-state", "89969"), ("baylor", "90107"),
    ("brigham-young", "90222"), ("central-florida", "92200"),
    ("cincinnati", "90291"), ("colorado", "90337"), ("houston", "90659"),
    ("iowa-state", "90774"), ("kansas", "90797"), ("kansas-state", "90820"),
    ("oklahoma-state", "91579"), ("tcu", "91947"), ("texas-tech", "92062"),
    ("utah", "92292"), ("west-virginia", "92499"),
    ("delaware", "93097"), ("florida-international", "90475"),
    ("jacksonville-state", "93028"), ("kennesaw-state", "93074"),
    ("liberty", "92982"), ("middle-tennessee", "91165"),
    ("missouri-state", "93120"), ("new-mexico-state", "91372"),
    ("sam-houston", "93051"), ("wku", "92775"),
    ("connecticut", "90383"), ("notre-dame", "91487"),
    ("akron", "89900"), ("ball-state", "90084"), ("bowling-green", "90176"),
    ("buffalo", "90199"), ("central-michigan", "90268"),
    ("eastern-michigan", "90429"), ("kent-state", "90843"),
    ("umass", "92706"), ("miami-university", "91096"), ("ohio", "91510"),
    ("sacramento-state", "93166"), ("toledo", "92085"),
    ("western-michigan", "92522"),
    ("air-force", "89877"), ("hawaii", "90636"), ("nevada", "91326"),
    ("new-mexico", "91349"), ("north-dakota-state", "93143"),
    ("northern-illinois", "91441"), ("san-jose-state", "92729"),
    ("unlv", "92246"), ("utep", "92338"), ("wyoming", "92568"),
    ("boise-state", "90130"), ("colorado-state", "90360"),
    ("fresno-state", "90567"), ("oregon-state", "91648"),
    ("san-diego-state", "91786"), ("texas-state", "92821"),
    ("utah state", "92315"), ("washington-state", "92476"),
    ("alabama", "89923"), ("arkansas", "89992"), ("auburn", "90061"),
    ("florida", "90498"), ("georgia", "90590"), ("kentucky", "90866"),
    ("lsu", "90981"), ("ole-miss", "91602"), ("mississippi-state", "91211"),
    ("missouri", "91234"), ("oklahoma", "91556"), ("south-carolina", "91832"),
    ("tennessee", "91993"), ("texas", "92016"), ("texas-am", "92039"),
    ("vanderbilt", "92361"),
    ("appalacian-state", "92913"), ("arkansas-state", "90015"),
    ("coastal-carolina", "92959"), ("georgia-southern", "92890"),
    ("georgia-state", "92752"), ("james-madison", "93005"),
    ("louisiana", "90912"), ("louisiana-tech", "90889"),
    ("louisiana-monroe", "90935"), ("marshall", "91004"),
    ("old-dominion", "92867"), ("south-alabama", "92798"),
    ("southern-miss", "91878"), ("troy", "92108"),
]

TITLE_RE = re.compile(r"<title>\s*2026\s*(.*?)\s*Football Roster\s*\|", re.S)
HC_RE = re.compile(r'liHC"[^>]*>Head Coach:\s*(.*?)</li>', re.S)
OFF_RE = re.compile(r'liOFF"[^>]*>Offensive Schemes:\s*(.*?)</li>', re.S)
DEF_RE = re.compile(r'liDEF"[^>]*>Defensive Schemes:\s*(.*?)</li>', re.S)

DELAY_S = 1.0


def scrape_one(session, slug, team_id):
    url = BASE.format(slug=slug, id=team_id)
    r = session.get(url, timeout=20)
    r.raise_for_status()
    html = r.text

    def grab(pattern):
        m = pattern.search(html)
        return m.group(1).strip() if m else ""

    return {
        "slug": slug,
        "team": grab(TITLE_RE),
        "coach": grab(HC_RE),
        "offensive_scheme": grab(OFF_RE),
        "defensive_scheme": grab(DEF_RE),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DATA_ROOT / "ourlads_schemes.csv")
    args = ap.parse_args()

    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"

    rows = []
    failures = []
    for n, (slug, team_id) in enumerate(TEAMS, 1):
        try:
            rows.append(scrape_one(session, slug, team_id))
        except Exception as exc:
            failures.append((slug, str(exc)[:120]))
        print(f"[{n}/{len(TEAMS)}] {slug}", flush=True)
        time.sleep(DELAY_S)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["slug", "team", "coach", "offensive_scheme", "defensive_scheme"])
        w.writeheader()
        w.writerows(rows)

    print(f"\n{len(rows)} written, {len(failures)} failed -> {args.out}")
    for slug, err in failures:
        print(f"  FAIL {slug}: {err}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
