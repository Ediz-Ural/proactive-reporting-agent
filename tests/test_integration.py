"""
Integration test: DataCollectorAgent -> DataQualityAgent pipeline.

Verifies that the data flows correctly from collection to validation
using an in-memory SQLite database.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="module")
def integration_engine():
    """Create an in-memory SQLite engine with synthetic data for integration testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE orders (
                order_id     TEXT    NOT NULL,
                order_date   TEXT    NOT NULL,
                ship_date    TEXT,
                ship_mode    TEXT,
                customer_id  TEXT,
                segment      TEXT,
                country      TEXT,
                city         TEXT,
                state        TEXT,
                region       TEXT,
                product_id   TEXT    NOT NULL,
                category     TEXT,
                sub_category TEXT,
                product_name TEXT,
                sales        REAL    NOT NULL DEFAULT 0,
                quantity     INTEGER NOT NULL DEFAULT 0,
                discount     REAL    NOT NULL DEFAULT 0,
                profit       REAL    NOT NULL DEFAULT 0,
                company_id   INTEGER DEFAULT 1,
                PRIMARY KEY (order_id, product_id)
            )
        """))
        rows = [
            ("ORD-001", "2024-01-05", "2024-01-08", "Standard Class",
             "CUST-01", "Consumer", "US", "New York", "NY", "East",
             "PRD-001", "Technology", "Phones", "Phone A", 250.0, 2, 0.1, 50.0),
            ("ORD-002", "2024-01-10", "2024-01-13", "Second Class",
             "CUST-02", "Corporate", "US", "Chicago", "IL", "Central",
             "PRD-002", "Office Supplies", "Binders", "Binder B", 45.0, 5, 0.0, 12.0),
            ("ORD-003", "2024-01-15", "2024-01-17", "First Class",
             "CUST-03", "Home Office", "US", "Los Angeles", "CA", "West",
             "PRD-003", "Furniture", "Chairs", "Chair C", 650.0, 1, 0.2, -30.0),
            ("ORD-004", "2024-01-20", "2024-01-22", "Standard Class",
             "CUST-01", "Consumer", "US", "New York", "NY", "East",
             "PRD-004", "Technology", "Accessories", "Cable D", 35.0, 3, 0.0, 15.0),
            ("ORD-005", "2024-01-25", "2024-01-28", "Same Day",
             "CUST-04", "Corporate", "US", "Houston", "TX", "South",
             "PRD-005", "Office Supplies", "Paper", "Paper E", 20.0, 10, 0.0, 8.0),
            ("ORD-006", "2024-02-02", "2024-02-04", "Standard Class",
             "CUST-05", "Consumer", "US", "Seattle", "WA", "West",
             "PRD-001", "Technology", "Phones", "Phone A", 300.0, 1, 0.0, 80.0),
            ("ORD-007", "2024-02-10", "2024-02-12", "Second Class",
             "CUST-02", "Corporate", "US", "Chicago", "IL", "Central",
             "PRD-006", "Furniture", "Tables", "Table F", 900.0, 1, 0.1, -100.0),
            ("ORD-008", "2024-02-15", "2024-02-18", "First Class",
             "CUST-06", "Home Office", "US", "Phoenix", "AZ", "West",
             "PRD-007", "Office Supplies", "Storage", "Box G", 75.0, 4, 0.0, 25.0),
        ]
        cols = [
            "order_id", "order_date", "ship_date", "ship_mode", "customer_id",
            "segment", "country", "city", "state", "region", "product_id",
            "category", "sub_category", "product_name",
            "sales", "quantity", "discount", "profit",
        ]
        for row in rows:
            conn.execute(
                text("""INSERT INTO orders (order_id, order_date, ship_date, ship_mode, customer_id,
                    segment, country, city, state, region, product_id,
                    category, sub_category, product_name,
                    sales, quantity, discount, profit)
                VALUES (
                    :order_id,:order_date,:ship_date,:ship_mode,:customer_id,
                    :segment,:country,:city,:state,:region,:product_id,
                    :category,:sub_category,:product_name,
                    :sales,:quantity,:discount,:profit
                )"""),
                dict(zip(cols, row)),
            )
        conn.commit()
    return engine


class TestCollectorToQualityPipeline:
    """End-to-end test from DataCollector through DataQuality."""

    def test_pipeline_produces_valid_report(self, integration_engine):
        """Collector output should pass quality checks."""
        with patch("src.tools.sql_tools.get_db_engine", return_value=integration_engine):
            from src.agents.data_collector import DataCollectorAgent
            from src.agents.data_quality import DataQualityAgent

            collector = DataCollectorAgent()
            raw_data = collector.collect("2024-01-01", "2024-02-28")

            assert raw_data["daily_sales"], "daily_sales should not be empty"
            assert raw_data["by_category"], "by_category should not be empty"
            assert raw_data["top_products"], "top_products should not be empty"

            quality = DataQualityAgent()
            report = quality.validate(raw_data)

            assert report["is_valid"] is True
            assert report["total_rows"] > 0
            assert len(report["errors"]) == 0

    def test_raw_data_has_expected_keys(self, integration_engine):
        """Collector output should contain all expected keys."""
        with patch("src.tools.sql_tools.get_db_engine", return_value=integration_engine):
            from src.agents.data_collector import DataCollectorAgent

            collector = DataCollectorAgent()
            raw_data = collector.collect("2024-01-01", "2024-02-28")

            expected_keys = [
                "period", "daily_sales", "by_category", "top_products",
                "customer_metrics", "region_performance", "weekly_summary",
            ]
            for key in expected_keys:
                assert key in raw_data, f"Missing key: {key}"

    def test_quality_report_structure(self, integration_engine):
        """Quality report should have all required fields."""
        with patch("src.tools.sql_tools.get_db_engine", return_value=integration_engine):
            from src.agents.data_collector import DataCollectorAgent
            from src.agents.data_quality import DataQualityAgent

            collector = DataCollectorAgent()
            raw_data = collector.collect("2024-01-01", "2024-02-28")

            quality = DataQualityAgent()
            report = quality.validate(raw_data)

            required_keys = [
                "is_valid", "total_rows", "null_percentage", "duplicates",
                "negative_values", "date_inconsistencies", "outlier_count",
                "warnings", "errors", "checked_at",
            ]
            for key in required_keys:
                assert key in report, f"Missing key in quality report: {key}"
