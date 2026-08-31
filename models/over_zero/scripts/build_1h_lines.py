"""Build 2025 first-half line rows from local Action Network warehouse payloads."""

import csv
import json
import sys
from pathlib import Path

import duckdb


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "cfb_paths.py").is_file():
            return parent
    raise RuntimeError("Cannot locate repository root containing cfb_paths.py")


sys.path.insert(0, str(_repo_root()))
from cfb_paths import DB_PATH, PROCESSED  # noqa: E402


OUT_CSV = PROCESSED / "over_zero" / "1h_lines.csv"
COLUMNS = [
    "event_id", "book_id", "period", "type", "side", "team_id",
    "value", "odds", "odds_coefficient_score", "line_status", "is_live",
    "market_id", "outcome_id",
]


def rows_from_payload(payload):
    data = json.loads(payload)
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


def history_payloads(connection, season=2025):
    return connection.execute(
        """
        WITH season_events AS (
            SELECT DISTINCT CAST(json_extract_string(game.value, '$.id') AS BIGINT) event_id
            FROM raw.actionnetwork_scoreboard scoreboard,
                 json_each(scoreboard.payload, '$.games') game
            WHERE scoreboard.season = ?
        )
        SELECT history.payload, history.source_file
        FROM raw.actionnetwork_history history
        JOIN season_events
          ON TRY_CAST(
              regexp_extract(history.source_file, 'history_([0-9]+)[.]json', 1)
              AS BIGINT
          ) = season_events.event_id
        ORDER BY history.source_file
        """,
        [season],
    ).fetchall()


def main():
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(DB_PATH), read_only=True) as connection:
        payloads = history_payloads(connection)

    with OUT_CSV.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=COLUMNS)
        writer.writeheader()
        count = 0
        for payload, _source_file in payloads:
            for row in rows_from_payload(payload):
                writer.writerow(row)
                count += 1
    print(f"wrote {count} rows from {len(payloads)} warehouse payloads -> {OUT_CSV}")


if __name__ == "__main__":
    main()
