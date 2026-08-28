"""Flatten data/raw/1H-raw/history_*.json (ActionNetwork odds snapshots) into
one clean CSV, one row per book/period/bet-type/side line.

Run: python data/raw/1H-raw/combine_to_csv.py
"""

import csv
import json
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent
OUT_CSV = RAW_DIR.parent.parent / "processed" / "1h_lines.csv"

COLUMNS = [
    "event_id", "book_id", "period", "type", "side", "team_id",
    "value", "odds", "odds_coefficient_score", "line_status", "is_live",
    "market_id", "outcome_id",
]


def rows_from_file(path):
    data = json.loads(path.read_text())
    for book_id, periods in data.items():
        for period, bet_types in periods.items():
            for bet_type, records in bet_types.items():
                for rec in records:
                    yield {
                        "event_id": rec.get("event_id"),
                        "book_id": rec.get("book_id", book_id),
                        "period": period,
                        "type": bet_type,
                        "side": rec.get("side"),
                        "team_id": rec.get("team_id"),
                        "value": rec.get("value"),
                        "odds": rec.get("odds"),
                        "odds_coefficient_score": rec.get("odds_coefficient_score"),
                        "line_status": rec.get("line_status"),
                        "is_live": rec.get("is_live"),
                        "market_id": rec.get("market_id"),
                        "outcome_id": rec.get("outcome_id"),
                    }


def main():
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(RAW_DIR.glob("history_*.json"))
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        n = 0
        for path in files:
            for row in rows_from_file(path):
                writer.writerow(row)
                n += 1
    print(f"wrote {n} rows from {len(files)} files -> {OUT_CSV}")


if __name__ == "__main__":
    main()
