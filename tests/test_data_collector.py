"""
Tests for the Data Collector Agent and SQL tools.

These tests use an in-memory SQLite database seeded with synthetic data
so they run without any external services.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from sqlalchemy import create_engine, text

# Make sure the project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def in_memory_engine():
    """Create an in-memory SQLite engine with sample orders data."""
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
                PRIMARY KEY (order_id, product_id)
            )
        """))
        # Insert 20 sample rows spanning two months
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
            ("ORD-009", "2024-02-20", "2024-02-23", "Standard Class",
             "CUST-03", "Home Office", "US", "Los Angeles", "CA", "West",
             "PRD-008", "Technology", "Machines", "Printer H", 450.0, 1, 0.2, 90.0),
            ("ORD-010", "2024-02-25", "2024-02-27", "Same Day",
             "CUST-01", "Consumer", "US", "New York", "NY", "East",
             "PRD-002", "Office Supplies", "Binders", "Binder B", 60.0, 6, 0.0, 18.0),
        ]
        for row in rows:
            conn.execute(
                text("""INSERT INTO orders VALUES (
                    :order_id,:order_date,:ship_date,:ship_mode,:customer_id,
                    :segment,:country,:city,:state,:region,:product_id,
                    :category,:sub_category,:product_name,
                    :sales,:quantity,:discount,:profit
                )"""),
                dict(zip(
                    ["order_id","order_date","ship_date","ship_mode","customer_id",
                     "segment","country","city","state","region","product_id",
                     "category","sub_category","product_name",
                     "sales","quantity","discount","profit"],
                    row
                )),
            )
        conn.commit()
    return engine


@pytest.fixture(autouse=True)
def patch_engine(in_memory_engine):
    """Redirect all DB calls to the in-memory engine."""
    with patch("src.tools.sql_tools.get_db_engine", return_value=in_memory_engine):
        # Also clear the lru_cache so our mock takes effect
        from src.tools import sql_tools
        sql_tools.get_db_engine.cache_clear() if hasattr(sql_tools.get_db_engine, "cache_clear") else None
        yield


# ── SQL tool tests ─────────────────────────────────────────────────────────────

class TestGetSalesByPeriod:
    def test_returns_dataframe(self):
        from src.tools.sql_tools import get_sales_by_period
        df = get_sales_by_period("2024-01-01", "2024-01-31")
        assert isinstance(df, pd.DataFrame)

    def test_correct_columns(self):
        from src.tools.sql_tools import get_sales_by_period
        df = get_sales_by_period("2024-01-01", "2024-01-31")
        assert not df.empty
        assert "total_sales" in df.columns
        assert "total_orders" in df.columns

    def test_january_data(self):
        from src.tools.sql_tools import get_sales_by_period
        df = get_sales_by_period("2024-01-01", "2024-01-31")
        assert df["total_sales"].sum() > 0

    def test_empty_range(self):
        from src.tools.sql_tools import get_sales_by_period
        df = get_sales_by_period("2020-01-01", "2020-01-31")
        assert df.empty


class TestGetSalesByCategory:
    def test_returns_categories(self):
        from src.tools.sql_tools import get_sales_by_category
        df = get_sales_by_category("2024-01-01", "2024-12-31")
        assert not df.empty
        assert "category" in df.columns

    def test_technology_present(self):
        from src.tools.sql_tools import get_sales_by_category
        df = get_sales_by_category("2024-01-01", "2024-12-31")
        assert "Technology" in df["category"].values


class TestGetTopProducts:
    def test_limit_respected(self):
        from src.tools.sql_tools import get_top_products
        df = get_top_products("2024-01-01", "2024-12-31", limit=3)
        assert len(df) <= 3

    def test_sorted_by_sales(self):
        from src.tools.sql_tools import get_top_products
        df = get_top_products("2024-01-01", "2024-12-31", limit=5)
        if len(df) > 1:
            assert df["total_sales"].iloc[0] >= df["total_sales"].iloc[1]


class TestGetWeeklySummary:
    def test_returns_dict(self):
        from src.tools.sql_tools import get_weekly_summary
        result = get_weekly_summary("2024-01-01", "2024-01-31")
        assert isinstance(result, dict)

    def test_required_keys(self):
        from src.tools.sql_tools import get_weekly_summary
        result = get_weekly_summary("2024-01-01", "2024-12-31")
        for key in ("total_revenue", "total_orders", "avg_order_value", "unique_customers"):
            assert key in result, f"Missing key: {key}"

    def test_revenue_positive(self):
        from src.tools.sql_tools import get_weekly_summary
        result = get_weekly_summary("2024-01-01", "2024-12-31")
        assert result["total_revenue"] > 0

    def test_order_count_correct(self):
        from src.tools.sql_tools import get_weekly_summary
        result = get_weekly_summary("2024-01-01", "2024-12-31")
        assert result["total_orders"] == 10  # exactly 10 distinct orders seeded

    def test_empty_period(self):
        from src.tools.sql_tools import get_weekly_summary
        result = get_weekly_summary("2020-01-01", "2020-01-07")
        assert result["total_revenue"] == 0.0
        assert result["total_orders"] == 0


# ── DataCollectorAgent tests ──────────────────────────────────────────────────

class TestDataCollectorAgent:
    def test_collect_returns_dict(self):
        from src.agents.data_collector import DataCollectorAgent
        agent = DataCollectorAgent()
        result = agent.collect("2024-01-01", "2024-12-31")
        assert isinstance(result, dict)

    def test_collect_has_all_keys(self):
        from src.agents.data_collector import DataCollectorAgent
        agent = DataCollectorAgent()
        result = agent.collect("2024-01-01", "2024-12-31")
        for key in ("period", "daily_sales", "by_category", "top_products",
                    "customer_metrics", "weekly_summary"):
            assert key in result, f"Missing key: {key}"

    def test_collect_daily_sales_non_empty(self):
        from src.agents.data_collector import DataCollectorAgent
        agent = DataCollectorAgent()
        result = agent.collect("2024-01-01", "2024-12-31")
        assert len(result["daily_sales"]) > 0

    def test_collect_weekly_summary_values(self):
        from src.agents.data_collector import DataCollectorAgent
        agent = DataCollectorAgent()
        result = agent.collect("2024-01-01", "2024-12-31")
        summary = result["weekly_summary"]
        assert summary["total_orders"] == 10
        assert summary["total_revenue"] > 0

    def test_collect_period_metadata(self):
        from src.agents.data_collector import DataCollectorAgent
        agent = DataCollectorAgent()
        result = agent.collect("2024-01-01", "2024-01-31")
        assert result["period"]["start"] == "2024-01-01"
        assert result["period"]["end"] == "2024-01-31"
