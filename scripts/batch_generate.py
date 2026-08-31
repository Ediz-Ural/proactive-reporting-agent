"""
Batch report generation script.

Runs the pipeline for all active companies across a date range,
generating monthly reports chronologically.

Usage:
    python scripts/batch_generate.py                    # 2017 only (default)
    python scripts/batch_generate.py --start 2014-01    # full range from 2014
    python scripts/batch_generate.py --companies 1,2,3  # specific companies only
    python scripts/batch_generate.py --dry-run           # show plan without running
"""

import argparse
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.logging_config import setup_logging

setup_logging()

import logging

logger = logging.getLogger(__name__)


def get_month_ranges(start_year: int, start_month: int, end_year: int, end_month: int):
    """Generate (start_date, end_date) tuples for each month in range."""
    months = []
    y, m = start_year, start_month
    while (y, m) <= (end_year, end_month):
        first_day = date(y, m, 1)
        if m == 12:
            last_day = date(y, 12, 31)
        else:
            last_day = date(y, m + 1, 1) - timedelta(days=1)
        months.append((str(first_day), str(last_day)))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def main():
    parser = argparse.ArgumentParser(description="Batch generate reports")
    parser.add_argument("--start", default="2017-01", help="Start year-month (default: 2017-01)")
    parser.add_argument("--end", default="2017-12", help="End year-month (default: 2017-12)")
    parser.add_argument("--companies", default=None, help="Comma-separated company IDs (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Show plan only")
    args = parser.parse_args()

    start_parts = args.start.split("-")
    end_parts = args.end.split("-")
    start_y, start_m = int(start_parts[0]), int(start_parts[1])
    end_y, end_m = int(end_parts[0]), int(end_parts[1])

    months = get_month_ranges(start_y, start_m, end_y, end_m)

    from src.tools.sql_tools import execute_query
    if args.companies:
        company_ids = [int(x) for x in args.companies.split(",")]
        companies = execute_query(
            f"SELECT id, name FROM companies WHERE id IN ({','.join(str(c) for c in company_ids)}) ORDER BY id"
        )
    else:
        companies = execute_query("SELECT id, name FROM companies WHERE is_active = 1 ORDER BY id")

    total = len(companies) * len(months)
    print(f"\n{'='*60}")
    print("BATCH REPORT GENERATION")
    print(f"{'='*60}")
    print(f"Companies: {len(companies)}")
    print(f"Months:    {len(months)} ({args.start} — {args.end})")
    print(f"Total:     {total} reports")
    print(f"{'='*60}\n")

    for _, c in companies.iterrows():
        print(f"  [{c['id']:2d}] {c['name']}")
    print()

    if args.dry_run:
        print("DRY RUN — no reports generated.")
        for start_date, end_date in months:
            for _, c in companies.iterrows():
                print(f"  Would run: company={c['id']} ({c['name']}) period={start_date}/{end_date}")
        return

    from src.graph.workflow import run_pipeline

    succeeded = 0
    failed = 0
    errors = []
    t0 = time.time()

    for i, (start_date, end_date) in enumerate(months):
        for j, (_, company) in enumerate(companies.iterrows()):
            cid = int(company["id"])
            cname = company["name"]
            idx = i * len(companies) + j + 1

            print(f"[{idx:3d}/{total}] {cname} | {start_date} — {end_date} ... ", end="", flush=True)
            t1 = time.time()

            try:
                state = run_pipeline(
                    start_date=start_date,
                    end_date=end_date,
                    report_type="monthly",
                    company_id=cid,
                )

                elapsed = time.time() - t1
                eval_data = state.get("evaluation") or {}
                score = eval_data.get("overall_score", 0)
                approved = eval_data.get("approved", False)

                draft = state.get("draft_report") or ""
                report_len = len(draft)

                if report_len > 0:
                    marker = "OK" if approved else "LOW"
                    print(f"{marker} (score={score:.2f}, {report_len} chars, {elapsed:.1f}s)")
                    succeeded += 1
                else:
                    qr = state.get("quality_report") or {}
                    if not qr.get("is_valid", True):
                        print(f"SKIP — no data ({elapsed:.1f}s)")
                        succeeded += 1
                    else:
                        print(f"EMPTY ({elapsed:.1f}s)")
                        failed += 1
                        errors.append(f"{cname} {start_date}: empty report")

            except Exception as exc:
                elapsed = time.time() - t1
                print(f"FAIL ({elapsed:.1f}s) — {exc}")
                failed += 1
                errors.append(f"{cname} {start_date}: {exc}")

    total_time = time.time() - t0
    print(f"\n{'='*60}")
    print(f"DONE in {total_time:.0f}s ({total_time/60:.1f} min)")
    print(f"Succeeded: {succeeded}/{total}")
    print(f"Failed:    {failed}/{total}")
    if errors:
        print("\nErrors:")
        for e in errors[:20]:
            print(f"  - {e}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
