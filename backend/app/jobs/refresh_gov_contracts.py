from __future__ import annotations

import argparse
from datetime import date

from app.core.database import SessionLocal, init_db
from app.services import gov_contract_service


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh and score government contract opportunities.")
    parser.add_argument("--window-days", type=int, default=7, help="How many days to include in the refresh window.")
    parser.add_argument("--start-date", type=date.fromisoformat, default=None, help="Optional ISO start date.")
    parser.add_argument("--end-date", type=date.fromisoformat, default=None, help="Optional ISO end date.")
    parser.add_argument(
        "--skip-esbd",
        action="store_true",
        help="Skip the Texas ESBD refresh.",
    )
    parser.add_argument(
        "--skip-federal",
        action="store_true",
        help="Skip the federal forecast refresh.",
    )
    parser.add_argument(
        "--skip-grants",
        action="store_true",
        help="Skip the Grants.gov refresh.",
    )
    parser.add_argument(
        "--skip-sba",
        action="store_true",
        help="Skip the SBA SUBNet refresh.",
    )
    parser.add_argument(
        "--include-gmail",
        action="store_true",
        help="Also sync Gmail RFQs if that feed is configured.",
    )
    parser.add_argument(
        "--skip-tracked-sources",
        action="store_true",
        help="Skip the tracked municipal, county, and regional procurement sources.",
    )
    parser.add_argument(
        "--gmail-limit",
        type=int,
        default=50,
        help="How many Gmail RFQs to pull when --include-gmail is set.",
    )
    parser.add_argument("--limit", type=int, default=10, help="How many top matches to print.")
    args = parser.parse_args()
    if (
        args.skip_esbd
        and args.skip_federal
        and args.skip_grants
        and args.skip_sba
        and args.skip_tracked_sources
        and not args.include_gmail
    ):
        parser.error("No opportunity sources selected. Remove a skip flag or add --include-gmail.")
    return args


def main() -> None:
    args = parse_args()
    init_db()

    db = SessionLocal()
    try:
        runs = []
        failures: list[tuple[str, str]] = []

        def run_step(label: str, func) -> None:
            try:
                result = func()
                if isinstance(result, list):
                    runs.extend(result)
                else:
                    runs.append(result)
            except gov_contract_service.GovContractSourceError as exc:
                failures.append((label, str(exc)))

        if not args.skip_esbd:
            run_step(
                "txsmartbuy_esbd",
                lambda: gov_contract_service.refresh_contracts(
                    db,
                    start_date=args.start_date,
                    end_date=args.end_date,
                    window_days=args.window_days,
                ),
            )
        if not args.skip_federal:
            run_step("federal_forecast", lambda: gov_contract_service.refresh_federal_contracts(db))
        if not args.skip_grants:
            run_step("grants_gov", lambda: gov_contract_service.refresh_grants_contracts(db))
        if not args.skip_sba:
            run_step("sba_subnet", lambda: gov_contract_service.refresh_sba_subnet_contracts(db))
        if not args.skip_tracked_sources:
            run_step("tracked_sources", lambda: gov_contract_service.refresh_tracked_procurement_sources(db))
        if args.include_gmail:
            run_step("gmail_rfqs", lambda: gov_contract_service.refresh_gmail_contracts(db, limit=args.gmail_limit))

        matches = gov_contract_service.list_contracts(db, limit=args.limit, matches_only=True, open_only=True)

        for run in runs:
            print(
                f"[{run.source}] Run {run.id} imported {run.total_records} opportunities "
                f"({run.matched_records} matches, {run.open_records} open) "
                f"for {run.window_start.isoformat()} through {run.window_end.isoformat()}."
            )
            if run.status not in {"completed", "running"} and run.error_message:
                print(f"    status={run.status} detail={run.error_message}")

        if failures:
            print("Source failures:")
            for label, detail in failures:
                print(f"- [{label}] {detail}")

        print(f"Top {min(args.limit, len(matches))} current matches across all enabled sources:")
        for index, match in enumerate(matches, start=1):
            due = match.due_date.isoformat() if match.due_date else "n/a"
            agency = match.agency_name or match.agency_number or "Unknown agency"
            print(
                f"{index}. [{match.source}][{match.fit_bucket.upper()}:{match.score}|priority:{match.priority_score}] {match.title} "
                f"| {agency} | due {due} | {match.source_url}"
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
