"""
APScheduler-based monthly report scheduler.

Triggers the pipeline on the 1st of each month at the configured hour,
generating a report for the previous month.
"""

from __future__ import annotations

import calendar
import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)


def get_previous_month_range() -> tuple[str, str]:
    """
    Return the start and end dates of the previous month as ISO strings.

    Example:
        If today is 2026-03-01 → ("2026-02-01", "2026-02-28")
        If today is 2026-01-15 → ("2025-12-01", "2025-12-31")
    """
    today = date.today()
    first_of_this_month = today.replace(day=1)
    last_of_prev_month = first_of_this_month - timedelta(days=1)
    first_of_prev_month = last_of_prev_month.replace(day=1)
    return first_of_prev_month.isoformat(), last_of_prev_month.isoformat()


def monthly_report_job() -> None:
    """
    Scheduler job: generate a report for the previous month.

    Called automatically by APScheduler on the 1st of each month.
    """
    from src.graph.workflow import run_pipeline_with_retry

    start_date, end_date = get_previous_month_range()
    logger.info(
        "Scheduler: starting monthly report job for %s → %s",
        start_date, end_date,
    )

    try:
        state = run_pipeline_with_retry(
            start_date=start_date,
            end_date=end_date,
            report_type="monthly",
        )
        logger.info(
            "Scheduler: monthly report completed (run_id=%s)",
            state.get("run_id", "unknown"),
        )
    except Exception as exc:
        logger.error("Scheduler: monthly report job failed: %s", exc)


def start_scheduler():
    """
    Start the APScheduler background scheduler.

    Runs monthly_report_job on the 1st of each month at the configured time.
    Returns the scheduler instance (for shutdown), or None if disabled.
    """
    from config.settings import settings

    if not settings.SCHEDULER_ENABLED:
        logger.info("Scheduler disabled (SCHEDULER_ENABLED=false)")
        return None

    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = BackgroundScheduler()
    trigger = CronTrigger(
        day=1,
        hour=settings.SCHEDULER_HOUR,
        minute=settings.SCHEDULER_MINUTE,
    )

    scheduler.add_job(
        monthly_report_job,
        trigger=trigger,
        id="monthly_report",
        name="Monthly Report Generator",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "Scheduler started — monthly job at day=1, %02d:%02d",
        settings.SCHEDULER_HOUR,
        settings.SCHEDULER_MINUTE,
    )
    return scheduler
