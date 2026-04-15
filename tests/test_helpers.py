"""
Tests for utility helpers — get_previous_period, safe_divide, etc.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.helpers import get_previous_period


class TestGetPreviousPeriodWeekly:
    """Default (weekly) behaviour — day-based delta."""

    def test_weekly_same_length(self):
        prev_start, prev_end = get_previous_period(
            date(2017, 2, 1), date(2017, 2, 7), report_type="weekly"
        )
        assert prev_end == date(2017, 1, 31)
        delta_current = date(2017, 2, 7) - date(2017, 2, 1)
        delta_prev = prev_end - prev_start
        assert delta_current == delta_prev

    def test_weekly_default_param(self):
        """report_type defaults to weekly."""
        a, b = get_previous_period(date(2017, 3, 1), date(2017, 3, 7))
        c, d = get_previous_period(date(2017, 3, 1), date(2017, 3, 7), report_type="weekly")
        assert (a, b) == (c, d)


class TestGetPreviousPeriodMonthly:
    """Monthly mode — previous calendar month."""

    def test_feb_returns_full_january(self):
        """Feb 2017 → Jan 1–31 (not Jan 4–31)."""
        prev_start, prev_end = get_previous_period(
            date(2017, 2, 1), date(2017, 2, 28), report_type="monthly"
        )
        assert prev_start == date(2017, 1, 1)
        assert prev_end == date(2017, 1, 31)

    def test_jan_returns_december_prev_year(self):
        prev_start, prev_end = get_previous_period(
            date(2017, 1, 1), date(2017, 1, 31), report_type="monthly"
        )
        assert prev_start == date(2016, 12, 1)
        assert prev_end == date(2016, 12, 31)

    def test_march_leap_year(self):
        prev_start, prev_end = get_previous_period(
            date(2024, 3, 1), date(2024, 3, 31), report_type="monthly"
        )
        assert prev_start == date(2024, 2, 1)
        assert prev_end == date(2024, 2, 29)

    def test_march_non_leap_year(self):
        prev_start, prev_end = get_previous_period(
            date(2023, 3, 1), date(2023, 3, 31), report_type="monthly"
        )
        assert prev_start == date(2023, 2, 1)
        assert prev_end == date(2023, 2, 28)

    def test_may_returns_april(self):
        prev_start, prev_end = get_previous_period(
            date(2017, 5, 1), date(2017, 5, 31), report_type="monthly"
        )
        assert prev_start == date(2017, 4, 1)
        assert prev_end == date(2017, 4, 30)

    def test_monthly_always_starts_on_first(self):
        """Even with odd start_date, monthly should use calendar month."""
        prev_start, prev_end = get_previous_period(
            date(2017, 6, 1), date(2017, 6, 30), report_type="monthly"
        )
        assert prev_start.day == 1


class TestGetPreviousPeriodQuarterly:
    """Quarterly mode — previous calendar quarter."""

    def test_q2_returns_q1(self):
        prev_start, prev_end = get_previous_period(
            date(2017, 4, 1), date(2017, 6, 30), report_type="quarterly"
        )
        assert prev_start == date(2017, 1, 1)
        assert prev_end == date(2017, 3, 31)

    def test_q1_returns_q4_prev_year(self):
        prev_start, prev_end = get_previous_period(
            date(2017, 1, 1), date(2017, 3, 31), report_type="quarterly"
        )
        assert prev_start == date(2016, 10, 1)
        assert prev_end == date(2016, 12, 31)

    def test_q3_returns_q2(self):
        prev_start, prev_end = get_previous_period(
            date(2017, 7, 1), date(2017, 9, 30), report_type="quarterly"
        )
        assert prev_start == date(2017, 4, 1)
        assert prev_end == date(2017, 6, 30)
