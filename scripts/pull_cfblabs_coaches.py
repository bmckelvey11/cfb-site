"""Pull the full CFB 27 coaches dataset (HC/OC/DC) from CFB Labs' backing API.

The /coaches page is a Next.js app whose cards are hydrated from a single
GraphQL call to a Netlify function -- no per-team scraping needed. See the
network request the page fires on load: GET .netlify/functions/cfb27-coaches.

    python scripts/pull_cfblabs_coaches.py
    python scripts/pull_cfblabs_coaches.py --out data/cfblabs_coaches.csv
"""

import argparse
import csv
import urllib.parse
from pathlib import Path

import requests

import sys
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from cfb_paths import DATA_ROOT  # noqa: E402

ENDPOINT = "https://www.cfblabs.com/.netlify/functions/cfb27-coaches"
QUERY = """{
  coaches {
    team
    coach_type
    name
    prestige
    level
    archetype
    job_security
    off_scheme
    def_scheme
    alma_mater
    cost
    career_record
    cw_pct
    win_seasons
    record_vs_rivals
    bowl_record
    record_vs_top25
    playoff_record
    pw_pct
    natl_champs
    conf_titles
    first_round_picks
    draft_picks
    t5_recruiting
    card_image
    head_image
    card_url
    head_url
    __typename
  }
}"""

FIELDS = [
    "team", "coach_type", "name", "prestige", "level", "archetype",
    "job_security", "off_scheme", "def_scheme", "alma_mater", "cost",
    "career_record", "cw_pct", "win_seasons", "record_vs_rivals",
    "bowl_record", "record_vs_top25", "playoff_record", "pw_pct",
    "natl_champs", "conf_titles", "first_round_picks", "draft_picks",
    "t5_recruiting",
]


def fetch():
    url = ENDPOINT + "?" + urllib.parse.urlencode({"query": QUERY, "variables": "{}"})
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    r.raise_for_status()
    return r.json()["data"]["coaches"]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DATA_ROOT / "cfblabs_coaches.csv")
    args = ap.parse_args()

    coaches = fetch()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for c in coaches:
            w.writerow({k: c.get(k) for k in FIELDS})

    print(f"{len(coaches)} coaches -> {args.out}")


if __name__ == "__main__":
    main()
