"""
Miscellaneous utility functions.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta


def generate_run_id() -> str:
    """Generate a unique run identifier."""
    return str(uuid.uuid4())


def get_previous_period(start_date: date, end_date: date) -> tuple[date, date]:
    """
    Return the equivalent previous period (same length, immediately before start_date).

    Args:
        start_date: Current period start.
        end_date:   Current period end.

    Returns:
        Tuple of (prev_start, prev_end).
    """
    delta = end_date - start_date
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - delta
    return prev_start, prev_end


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Return numerator / denominator, or *default* when denominator is zero."""
    return numerator / denominator if denominator != 0 else default


def format_currency(value: float, symbol: str = "$") -> str:
    """Format a float as a currency string."""
    return f"{symbol}{value:,.2f}"


def format_percentage(value: float, decimals: int = 1) -> str:
    """Format a float as a percentage string."""
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.{decimals}f}%"
