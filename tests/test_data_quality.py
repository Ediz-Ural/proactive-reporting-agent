"""
Tests for the Data Quality Agent.

Uses synthetic dicts that mimic DataCollectorAgent output.
No database connection required for most tests.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.data_quality import DataQualityAgent

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_clean_data() -> dict:
    """Return a clean raw_data dict (should pass all checks)."""
    daily_sales = [
        {"order_date": "2024-01-05", "total_sales": 250.0, "total_profit": 50.0, "total_orders": 1},
        {"order_date": "2024-01-10", "total_sales": 45.0, "total_profit": 12.0, "total_orders": 1},
        {"order_date": "2024-01-15", "total_sales": 650.0, "total_profit": 130.0, "total_orders": 1},
        {"order_date": "2024-01-20", "total_sales": 35.0, "total_profit": 15.0, "total_orders": 1},
        {"order_date": "2024-01-25", "total_sales": 20.0, "total_profit": 8.0, "total_orders": 1},
    ]
    by_category = [
        {"category": "Technology", "sub_category": "Phones",
         "total_sales": 550.0, "total_profit": 130.0, "order_count": 3, "avg_discount": 0.05},
        {"category": "Furniture", "sub_category": "Chairs",
         "total_sales": 650.0, "total_profit": 130.0, "order_count": 1, "avg_discount": 0.2},
        {"category": "Office Supplies", "sub_category": "Binders",
         "total_sales": 65.0, "total_profit": 20.0, "order_count": 2, "avg_discount": 0.0},
    ]
    return {
        "period": {"start": "2024-01-01", "end": "2024-01-31"},
        "daily_sales": daily_sales,
        "by_category": by_category,
        "top_products": [{"product_id": "PRD-001", "total_sales": 550.0}],
        "weekly_summary": {"total_revenue": 1000.0, "total_orders": 5},
    }


def _make_data_with_nulls() -> dict:
    """Return data where some sales values are None."""
    data = _make_clean_data()
    daily_sales = data["daily_sales"].copy()
    daily_sales[0]["total_sales"] = None
    daily_sales[1]["total_sales"] = None
    data["daily_sales"] = daily_sales
    return data


def _make_data_with_negatives() -> dict:
    """Return data with negative sales values."""
    data = _make_clean_data()
    # For negative check we use the by_category frame (has sales column)
    by_cat = data["by_category"].copy()
    by_cat[0]["total_sales"] = -500.0
    data["by_category"] = by_cat
    return data


# ── Tests: clean data ─────────────────────────────────────────────────────────

class TestCleanData:
    def setup_method(self):
        self.agent = DataQualityAgent()

    def _run(self, data):
        # Patch out the DB-dependent date check
        with patch.object(self.agent, "_check_date_consistency", return_value=0):
            return self.agent.validate(data)

    def test_is_valid_true(self):
        report = self._run(_make_clean_data())
        assert report["is_valid"] is True

    def test_no_errors(self):
        report = self._run(_make_clean_data())
        assert len(report["errors"]) == 0

    def test_total_rows_positive(self):
        report = self._run(_make_clean_data())
        assert report["total_rows"] > 0

    def test_report_has_required_keys(self):
        report = self._run(_make_clean_data())
        for key in ("is_valid", "total_rows", "null_percentage", "duplicates",
                    "warnings", "errors", "checked_at"):
            assert key in report, f"Missing key: {key}"

    def test_null_percentage_dict(self):
        report = self._run(_make_clean_data())
        assert isinstance(report["null_percentage"], dict)

    def test_empty_data_is_invalid(self):
        report = self._run({})
        assert report["is_valid"] is False
        assert len(report["errors"]) > 0


# ── Tests: data with nulls ─────────────────────────────────────────────────────

class TestNullData:
    def setup_method(self):
        self.agent = DataQualityAgent()

    def _run(self, data):
        with patch.object(self.agent, "_check_date_consistency", return_value=0):
            return self.agent.validate(data)

    def test_null_percentage_captured(self):
        report = self._run(_make_data_with_nulls())
        # At least one column should have a non-zero null percentage
        assert any(v > 0 for v in report["null_percentage"].values())

    def test_warning_or_error_raised(self):
        report = self._run(_make_data_with_nulls())
        # 40% nulls in total_sales should trigger at least a warning or error
        has_feedback = len(report["warnings"]) > 0 or len(report["errors"]) > 0
        assert has_feedback


# ── Tests: data with negative values ─────────────────────────────────────────

class TestNegativeData:
    def setup_method(self):
        self.agent = DataQualityAgent()

    def _run(self, data):
        with patch.object(self.agent, "_check_date_consistency", return_value=0):
            return self.agent.validate(data)

    def test_negative_values_detected(self):
        """Inject negatives into the primary frame (daily_sales) that the agent picks."""
        data = _make_clean_data()
        # Add a 'sales' column to daily_sales (the larger frame — picked by _build_combined_df)
        daily = data["daily_sales"].copy()
        for row in daily:
            row["sales"] = abs(row["total_sales"])  # positive
        daily[0]["sales"] = -999.0   # force one negative
        data["daily_sales"] = daily

        # Temporarily tell the agent to check the 'sales' column
        original_cols = DataQualityAgent.NON_NEGATIVE_COLS
        DataQualityAgent.NON_NEGATIVE_COLS = ["sales"]
        try:
            report = self._run(data)
            assert len(report["errors"]) > 0
            assert not report["is_valid"]
        finally:
            DataQualityAgent.NON_NEGATIVE_COLS = original_cols

    def test_invalid_when_errors_present(self):
        """Any error must make is_valid=False."""
        data = _make_clean_data()
        daily = data["daily_sales"].copy()
        for row in daily:
            row["sales"] = -abs(row["total_sales"])  # all negative
        data["daily_sales"] = daily

        original_cols = DataQualityAgent.NON_NEGATIVE_COLS
        DataQualityAgent.NON_NEGATIVE_COLS = ["sales"]
        try:
            report = self._run(data)
            assert report["is_valid"] is False
        finally:
            DataQualityAgent.NON_NEGATIVE_COLS = original_cols
