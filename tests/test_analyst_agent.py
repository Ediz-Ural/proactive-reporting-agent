"""
Tests for the Analyst Agent.

Uses an in-memory SQLite database (same pattern as test_data_collector.py)
because the Analyst needs DB access for period comparison and RFM.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.analyst import AnalystAgent


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def analyst_engine():
    """In-memory SQLite with 30+ days of data for analysis."""
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
        import random
        random.seed(42)
        cols = [
            "order_id", "order_date", "ship_date", "ship_mode", "customer_id",
            "segment", "country", "city", "state", "region", "product_id",
            "category", "sub_category", "product_name",
            "sales", "quantity", "discount", "profit",
        ]
        categories = {
            "Technology": ["Phones", "Accessories"],
            "Furniture": ["Chairs", "Tables"],
            "Office Supplies": ["Paper", "Binders"],
        }
        segments = ["Consumer", "Corporate", "Home Office"]
        regions = ["East", "West", "Central", "South"]

        for i in range(60):
            day = (i % 28) + 1
            order_date = f"2024-01-{day:02d}"
            ship_date = f"2024-02-{min(day + 3, 28):02d}"
            cat = list(categories.keys())[i % 3]
            subcat = categories[cat][i % len(categories[cat])]
            row = (
                f"ORD-{i+1:03d}", order_date, ship_date, "Standard",
                f"CUST-{(i % 15) + 1:02d}", segments[i % 3], "US", "City", "ST",
                regions[i % 4], f"PRD-{(i % 10) + 1:03d}", cat, subcat,
                f"Product {i+1}",
                round(random.uniform(20, 500), 2),
                random.randint(1, 10),
                round(random.uniform(0, 0.3), 2),
                round(random.uniform(-50, 150), 2),
            )
            conn.execute(
                text("""INSERT INTO orders VALUES (
                    :order_id,:order_date,:ship_date,:ship_mode,:customer_id,
                    :segment,:country,:city,:state,:region,:product_id,
                    :category,:sub_category,:product_name,
                    :sales,:quantity,:discount,:profit
                )"""),
                dict(zip(cols, row)),
            )
        conn.commit()
    return engine


@pytest.fixture(autouse=True)
def patch_engine(analyst_engine):
    """Redirect all DB calls to the in-memory engine."""
    with patch("src.tools.sql_tools.get_db_engine", return_value=analyst_engine):
        from src.tools import sql_tools
        if hasattr(sql_tools.get_db_engine, "cache_clear"):
            sql_tools.get_db_engine.cache_clear()
        yield


def _build_mock_state(daily_count: int = 20, with_categories: bool = True) -> dict:
    """Build a mock AgentState with synthetic raw_data."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2024-01-01", periods=daily_count, freq="D")
    daily_sales = [
        {
            "order_date": str(d.date()),
            "total_sales": round(float(100 + i * 5 + rng.normal(0, 10)), 2),
            "total_profit": round(float(20 + i * 2 + rng.normal(0, 5)), 2),
            "total_orders": int(5 + rng.integers(0, 5)),
            "total_quantity": int(10 + rng.integers(0, 10)),
        }
        for i, d in enumerate(dates)
    ]

    by_category = [
        {"category": "Technology", "sub_category": "Phones",
         "total_sales": 5000.0, "total_profit": 1000.0, "order_count": 50, "avg_discount": 0.1},
        {"category": "Furniture", "sub_category": "Chairs",
         "total_sales": 3000.0, "total_profit": -300.0, "order_count": 20, "avg_discount": 0.2},
        {"category": "Office Supplies", "sub_category": "Paper",
         "total_sales": 2000.0, "total_profit": 400.0, "order_count": 80, "avg_discount": 0.05},
    ] if with_categories else []

    customer_metrics = [
        {"segment": "Consumer", "unique_customers": 10, "total_orders": 30},
    ]

    return {
        "raw_data": {
            "daily_sales": daily_sales,
            "by_category": by_category,
            "top_products": [{"product_id": "P1", "total_sales": 500}],
            "customer_metrics": customer_metrics,
            "weekly_summary": {"total_revenue": 10000},
            "period": {"start": "2024-01-01", "end": "2024-01-31"},
        },
        "start_date": "2024-01-01",
        "end_date": "2024-01-31",
        "report_type": "weekly",
        "analysis_plan": [
            "trends", "anomalies", "period_comparison",
            "category_performance", "forecast", "decomposition",
            "rfm_segments",
        ],
    }


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestAnalystAgent:
    def setup_method(self):
        self.agent = AnalystAgent()

    def test_returns_dict(self):
        state = _build_mock_state()
        result = self.agent.analyse(state)
        assert isinstance(result, dict)

    def test_has_analysis_results(self):
        state = _build_mock_state()
        result = self.agent.analyse(state)
        assert "analysis_results" in result
        assert isinstance(result["analysis_results"], dict)

    def test_current_agent_set(self):
        state = _build_mock_state()
        result = self.agent.analyse(state)
        assert result["current_agent"] == "analyst"

    def test_trends_present(self):
        state = _build_mock_state()
        result = self.agent.analyse(state)
        ar = result["analysis_results"]
        assert "trends" in ar
        assert "total_sales" in ar["trends"]
        assert "direction" in ar["trends"]["total_sales"]

    def test_anomalies_is_list(self):
        state = _build_mock_state()
        result = self.agent.analyse(state)
        assert isinstance(result["analysis_results"]["anomalies"], list)

    def test_period_comparison_present(self):
        state = _build_mock_state()
        result = self.agent.analyse(state)
        assert "period_comparison" in result["analysis_results"]

    def test_category_performance_present(self):
        state = _build_mock_state()
        result = self.agent.analyse(state)
        cp = result["analysis_results"]["category_performance"]
        assert isinstance(cp, list)
        assert len(cp) == 3  # Technology, Furniture, Office Supplies

    def test_forecast_present(self):
        state = _build_mock_state()
        result = self.agent.analyse(state)
        forecast = result["analysis_results"]["forecast"]
        assert isinstance(forecast, dict)
        if forecast:
            assert "method" in forecast

    def test_metadata_present(self):
        state = _build_mock_state()
        result = self.agent.analyse(state)
        meta = result["analysis_results"]["analysis_metadata"]
        assert "analysed_at" in meta
        assert "period" in meta
        assert "analyses_completed" in meta
        assert "analyses_failed" in meta

    def test_does_not_crash_with_empty_data(self):
        state = {
            "raw_data": {},
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "report_type": "weekly",
            "analysis_plan": ["trends", "anomalies"],
        }
        result = self.agent.analyse(state)
        assert "analysis_results" in result
        assert result["analysis_results"]["analysis_metadata"]["total_rows_analysed"] == 0

    def test_respects_analysis_plan(self):
        """Only analyses in the plan should run."""
        state = _build_mock_state()
        state["analysis_plan"] = ["trends"]
        result = self.agent.analyse(state)
        ar = result["analysis_results"]
        assert "trends" in ar
        assert "anomalies" not in ar
        assert "forecast" not in ar

    def test_rfm_segments_present(self):
        state = _build_mock_state()
        result = self.agent.analyse(state)
        rfm = result["analysis_results"].get("rfm_segments", {})
        assert "total_customers" in rfm

    def test_analyses_completed_tracking(self):
        state = _build_mock_state()
        result = self.agent.analyse(state)
        meta = result["analysis_results"]["analysis_metadata"]
        assert "trends" in meta["analyses_completed"]
        assert "anomalies" in meta["analyses_completed"]
