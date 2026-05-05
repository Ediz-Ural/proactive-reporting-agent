"""
End-to-end pipeline test.
Seeds an in-memory DB, runs the full LangGraph pipeline,
and verifies that data flows correctly through all 9 nodes (Week 4).
"""

from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="module")
def e2e_engine():
    """Create an in-memory SQLite engine with 60+ rows of synthetic data."""
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

        categories = {
            "Technology": ["Phones", "Accessories", "Machines"],
            "Furniture": ["Chairs", "Tables", "Bookcases"],
            "Office Supplies": ["Paper", "Binders", "Storage"],
        }
        segments = ["Consumer", "Corporate", "Home Office"]
        regions = ["East", "West", "Central", "South"]
        cols = [
            "order_id", "order_date", "ship_date", "ship_mode", "customer_id",
            "segment", "country", "city", "state", "region", "product_id",
            "category", "sub_category", "product_name",
            "sales", "quantity", "discount", "profit",
        ]

        rng = random.Random(42)

        for i in range(70):
            day = (i % 28) + 1
            order_date = datetime(2024, 1, 1) + timedelta(days=day - 1)
            ship_date = order_date + timedelta(days=rng.randint(2, 7))
            cat = list(categories.keys())[i % 3]
            subcat = categories[cat][i % len(categories[cat])]
            segment = segments[i % 3]
            region = regions[i % 4]

            row = (
                f"ORD-E2E-{i+1:03d}",
                order_date.strftime("%Y-%m-%d"),
                ship_date.strftime("%Y-%m-%d"),
                "Standard Class",
                f"CUST-{(i % 20) + 1:02d}",
                segment, "US", "City", "ST", region,
                f"PRD-E2E-{(i % 15) + 1:03d}",
                cat, subcat,
                f"Product {subcat} {i+1}",
                round(rng.uniform(20, 500), 2),
                rng.randint(1, 10),
                round(rng.uniform(0, 0.3), 2),
                round(rng.uniform(-50, 200), 2),
            )
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


class TestPipelineE2E:
    """Run the full LangGraph pipeline and verify output."""

    def _run(self, engine, start="2024-01-01", end="2024-01-31"):
        with patch("src.tools.sql_tools.get_db_engine", return_value=engine):
            from src.tools import sql_tools
            if hasattr(sql_tools.get_db_engine, "cache_clear"):
                sql_tools.get_db_engine.cache_clear()

            from src.graph.workflow import run_pipeline
            return run_pipeline(start, end)

    def test_pipeline_completes(self, e2e_engine):
        state = self._run(e2e_engine)
        assert state is not None

    def test_raw_data_populated(self, e2e_engine):
        state = self._run(e2e_engine)
        raw = state.get("raw_data")
        assert raw is not None
        assert len(raw.get("daily_sales", [])) > 0

    def test_quality_report_valid(self, e2e_engine):
        state = self._run(e2e_engine)
        qr = state.get("quality_report")
        assert qr is not None
        assert qr["is_valid"] is True

    def test_analysis_results_populated(self, e2e_engine):
        state = self._run(e2e_engine)
        ar = state.get("analysis_results")
        assert ar is not None
        assert isinstance(ar, dict)

    def test_trends_present(self, e2e_engine):
        state = self._run(e2e_engine)
        ar = state["analysis_results"]
        assert "trends" in ar
        assert len(ar["trends"]) >= 1

    def test_anomalies_is_list(self, e2e_engine):
        state = self._run(e2e_engine)
        ar = state["analysis_results"]
        assert "anomalies" in ar
        assert isinstance(ar["anomalies"], list)

    def test_category_performance_populated(self, e2e_engine):
        state = self._run(e2e_engine)
        ar = state["analysis_results"]
        assert "category_performance" in ar
        assert len(ar["category_performance"]) > 0

    def test_forecast_present(self, e2e_engine):
        state = self._run(e2e_engine)
        ar = state["analysis_results"]
        assert "forecast" in ar

    def test_analysis_metadata(self, e2e_engine):
        state = self._run(e2e_engine)
        meta = state["analysis_results"]["analysis_metadata"]
        assert "analyses_completed" in meta
        assert "trends" in meta["analyses_completed"]
        assert "anomalies" in meta["analyses_completed"]

    def test_analysis_plan_set(self, e2e_engine):
        state = self._run(e2e_engine)
        plan = state.get("analysis_plan")
        assert plan is not None
        assert "trends" in plan

    def test_historical_context_set(self, e2e_engine):
        state = self._run(e2e_engine)
        hc = state.get("historical_context")
        # May be empty string (no ChromaDB data) but should not be None
        assert hc is not None
        assert isinstance(hc, str)

    def test_draft_report_populated(self, e2e_engine):
        state = self._run(e2e_engine)
        dr = state.get("draft_report")
        assert dr is not None
        assert isinstance(dr, str)
        assert len(dr) > 0

    def test_evaluator_iteration_incremented(self, e2e_engine):
        state = self._run(e2e_engine)
        assert state.get("evaluator_iteration", 0) >= 1

    def test_no_pipeline_errors(self, e2e_engine):
        state = self._run(e2e_engine)
        errors = state.get("errors", [])
        # Filter out any expected non-critical issues
        critical_errors = [e for e in errors if "failed" in e.lower()]
        # Allow non-critical failures (e.g., decomposition with sparse data)
        assert len(critical_errors) == 0, f"Pipeline had critical errors: {critical_errors}"

    # ── Week 4: Evaluator, Delivery, Feedback tests ──────────────────────────

    def test_evaluation_populated(self, e2e_engine):
        """Evaluator produces a valid evaluation dict."""
        state = self._run(e2e_engine)
        ev = state.get("evaluation")
        assert ev is not None
        assert isinstance(ev, dict)
        assert "overall_score" in ev
        assert "approved" in ev

    def test_evaluation_approved(self, e2e_engine):
        """Report is approved (rule-based fallback on good data)."""
        state = self._run(e2e_engine)
        ev = state["evaluation"]
        assert ev["approved"] is True

    def test_delivery_status_populated(self, e2e_engine):
        """Delivery produces a delivery_status dict."""
        state = self._run(e2e_engine)
        ds = state.get("delivery_status")
        assert ds is not None
        assert isinstance(ds, dict)

    def test_final_report_set(self, e2e_engine):
        """Final report is set after delivery."""
        state = self._run(e2e_engine)
        fr = state.get("final_report")
        assert fr is not None
        assert isinstance(fr, str)
        assert len(fr) > 0

    def test_feedback_metrics_populated(self, e2e_engine):
        """Feedback collects pipeline metrics."""
        state = self._run(e2e_engine)
        fm = state.get("feedback_metrics")
        assert fm is not None
        assert isinstance(fm, dict)
        assert "quality_score" in fm
        assert "evaluator_iterations" in fm
        assert "run_id" in fm

    def test_all_agents_ran(self, e2e_engine):
        """Verify the pipeline touched all 9 agents by checking their outputs."""
        state = self._run(e2e_engine)
        assert state.get("raw_data") is not None           # data_collector
        assert state.get("quality_report") is not None      # data_quality
        assert state.get("analysis_plan") is not None       # orchestrator
        assert state.get("analysis_results") is not None    # analyst
        assert state.get("historical_context") is not None  # rag
        assert state.get("draft_report") is not None        # writer
        assert state.get("evaluation") is not None          # evaluator
        assert state.get("delivery_status") is not None     # delivery
        assert state.get("feedback_metrics") is not None    # feedback
