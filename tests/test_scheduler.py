"""
Tests for the scheduler module — monthly report scheduling.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scheduler import get_previous_month_range, monthly_report_job, start_scheduler


class TestGetPreviousMonthRange:
    """Tests for get_previous_month_range()."""

    def test_march_returns_february(self):
        """March 1 → Feb 1 - Feb 28."""
        with patch("src.scheduler.date") as mock_date:
            mock_date.today.return_value = date(2026, 3, 1)
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
            start, end = get_previous_month_range()

        assert start == "2026-02-01"
        assert end == "2026-02-28"

    def test_january_returns_december(self):
        """January 1 → Dec 1 - Dec 31 of previous year."""
        with patch("src.scheduler.date") as mock_date:
            mock_date.today.return_value = date(2026, 1, 1)
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
            start, end = get_previous_month_range()

        assert start == "2025-12-01"
        assert end == "2025-12-31"

    def test_leap_year_march(self):
        """March 2024 → Feb has 29 days (leap year)."""
        with patch("src.scheduler.date") as mock_date:
            mock_date.today.return_value = date(2024, 3, 1)
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
            start, end = get_previous_month_range()

        assert start == "2024-02-01"
        assert end == "2024-02-29"

    def test_mid_month_still_works(self):
        """Even if called mid-month, returns previous month."""
        with patch("src.scheduler.date") as mock_date:
            mock_date.today.return_value = date(2026, 3, 15)
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
            start, end = get_previous_month_range()

        assert start == "2026-02-01"
        assert end == "2026-02-28"

    def test_may_returns_april(self):
        """May → April (30 days)."""
        with patch("src.scheduler.date") as mock_date:
            mock_date.today.return_value = date(2026, 5, 1)
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
            start, end = get_previous_month_range()

        assert start == "2026-04-01"
        assert end == "2026-04-30"

    def test_returns_iso_strings(self):
        """Return type is tuple of strings."""
        with patch("src.scheduler.date") as mock_date:
            mock_date.today.return_value = date(2026, 6, 1)
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
            start, end = get_previous_month_range()

        assert isinstance(start, str)
        assert isinstance(end, str)


class TestMonthlyReportJob:
    """Tests for the monthly_report_job() function."""

    def test_calls_pipeline_with_previous_month(self):
        """Job calls run_pipeline_with_retry with correct dates."""
        with patch("src.graph.workflow.run_pipeline_with_retry") as mock_pipeline, \
             patch("src.scheduler.get_previous_month_range", return_value=("2026-02-01", "2026-02-28")):
            mock_pipeline.return_value = {"run_id": "test-123"}
            monthly_report_job()

        mock_pipeline.assert_called_once_with(
            start_date="2026-02-01",
            end_date="2026-02-28",
            report_type="monthly",
        )

    def test_handles_pipeline_failure_gracefully(self):
        """Job catches exceptions without crashing."""
        with patch("src.graph.workflow.run_pipeline_with_retry", side_effect=RuntimeError("fail")), \
             patch("src.scheduler.get_previous_month_range", return_value=("2026-02-01", "2026-02-28")):
            # Should not raise
            monthly_report_job()

    def test_uses_monthly_report_type(self):
        """Job uses 'monthly' as report_type."""
        with patch("src.graph.workflow.run_pipeline_with_retry") as mock_pipeline, \
             patch("src.scheduler.get_previous_month_range", return_value=("2026-01-01", "2026-01-31")):
            mock_pipeline.return_value = {"run_id": "test-456"}
            monthly_report_job()

        call_kwargs = mock_pipeline.call_args[1]
        assert call_kwargs["report_type"] == "monthly"


class TestStartScheduler:
    """Tests for start_scheduler()."""

    def test_disabled_returns_none(self):
        """SCHEDULER_ENABLED=false → returns None."""
        mock_settings = MagicMock()
        mock_settings.SCHEDULER_ENABLED = False

        with patch("config.settings.settings", mock_settings):
            result = start_scheduler()

        assert result is None

    def test_enabled_starts_scheduler(self):
        """SCHEDULER_ENABLED=true → starts and returns scheduler."""
        mock_settings = MagicMock()
        mock_settings.SCHEDULER_ENABLED = True
        mock_settings.SCHEDULER_HOUR = 8
        mock_settings.SCHEDULER_MINUTE = 0

        mock_scheduler = MagicMock()

        with patch("config.settings.settings", mock_settings), \
             patch("apscheduler.schedulers.background.BackgroundScheduler", return_value=mock_scheduler), \
             patch("apscheduler.triggers.cron.CronTrigger"):
            result = start_scheduler()

        assert result is not None
        mock_scheduler.start.assert_called_once()

    def test_scheduler_job_registered(self):
        """Scheduler registers the monthly_report job."""
        mock_settings = MagicMock()
        mock_settings.SCHEDULER_ENABLED = True
        mock_settings.SCHEDULER_HOUR = 9
        mock_settings.SCHEDULER_MINUTE = 30

        mock_scheduler = MagicMock()

        with patch("config.settings.settings", mock_settings), \
             patch("apscheduler.schedulers.background.BackgroundScheduler", return_value=mock_scheduler), \
             patch("apscheduler.triggers.cron.CronTrigger"):
            result = start_scheduler()

        assert result is not None
        mock_scheduler.add_job.assert_called_once()
        call_kwargs = mock_scheduler.add_job.call_args
        assert call_kwargs[1]["id"] == "monthly_report"
