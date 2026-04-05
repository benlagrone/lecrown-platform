from __future__ import annotations

import argparse
from datetime import date

from app.core.database import SessionLocal, init_db
from app.services import gov_contract_service


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh and score ESBD government contract opportunities.")
    parser.add_argument("--window-days", type=int, default=7, help="How many days to include in the refresh window.")
    parser.add_argument("--start-date", type=date.fromisoformat, default=None, help="Optional ISO start date.")
    parser.add_argument("--end-date", type=date.fromisoformat, default=None, help="Optional ISO end date.")
    parser.add_argument("--limit", type=int, default=10, help="How many top matches to print.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    init_db()

    db = SessionLocal()
    try:
        run = gov_contract_service.refresh_contracts(
            db,
            start_date=args.start_date,
            end_date=args.end_date,
            window_days=args.window_days,
        )
        matches = gov_contract_service.list_contracts(db, limit=args.limit, matches_only=True, open_only=True)

        print(
            f"Run {run.id} imported {run.total_records} opportunities "
            f"({run.matched_records} matches, {run.open_records} open) "
            f"for {run.window_start.isoformat()} through {run.window_end.isoformat()}."
        )
        for index, match in enumerate(matches, start=1):
            due = match.due_date.isoformat() if match.due_date else "n/a"
            agency = match.agency_name or match.agency_number or "Unknown agency"
            print(
                f"{index}. [{match.fit_bucket.upper()}:{match.score}] {match.title} "
                f"| {agency} | due {due} | {match.source_url}"
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
