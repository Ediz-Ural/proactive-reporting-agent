"""
Tests for the Orchestrator Agent.

Validates that the rule-based analysis plan logic works correctly
based on the amount and type of available data.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.orchestrator import OrchestratorAgent


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_state(daily_sales_count: int, has_customer_metrics: bool = True) -> dict:
    """Build a minimal state dict with configurable data sizes."""
    daily_sales = [
        {"order_date": f"2024-01-{d+1:02d}", "total_sales": 100.0 + d}
        for d in range(daily_sales_count)
    ]
    customer_metrics = (
        [{"segment": "Consumer", "unique_customers": 10}]
        if has_customer_metrics
        else []
    )
    return {
        "raw_data": {
            "daily_sales": daily_sales,
            "by_category": [{"category": "Tech", "total_sales": 500}],
            "customer_metrics": customer_metrics,
        },
        "start_date": "2024-01-01",
        "end_date": "2024-01-31",
        "report_type": "weekly",
    }


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestOrchestratorPlan:
    def setup_method(self):
        self.agent = OrchestratorAgent()

    def test_returns_dict_with_plan(self):
        state = _make_state(daily_sales_count=20)
        result = self.agent.plan(state)
        assert isinstance(result, dict)
        assert "analysis_plan" in result
        assert isinstance(result["analysis_plan"], list)

    def test_current_agent_set(self):
        result = self.agent.plan(_make_state(20))
        assert result["current_agent"] == "orchestrator"

    def test_core_analyses_always_present(self):
        result = self.agent.plan(_make_state(5))
        plan = result["analysis_plan"]
        for analysis in ["trends", "anomalies", "period_comparison", "category_performance"]:
            assert analysis in plan, f"{analysis} should always be in the plan"

    def test_forecast_included_with_enough_data(self):
        """20+ days should include forecast and decomposition."""
        result = self.agent.plan(_make_state(20))
        plan = result["analysis_plan"]
        assert "forecast" in plan
        assert "decomposition" in plan

    def test_forecast_excluded_with_insufficient_data(self):
        """5 days should NOT include forecast or decomposition."""
        result = self.agent.plan(_make_state(5))
        plan = result["analysis_plan"]
        assert "forecast" not in plan
        assert "decomposition" not in plan

    def test_forecast_boundary_14_days(self):
        """Exactly 14 days should include forecast."""
        result = self.agent.plan(_make_state(14))
        plan = result["analysis_plan"]
        assert "forecast" in plan
        assert "decomposition" in plan

    def test_forecast_boundary_13_days(self):
        """13 days should NOT include forecast."""
        result = self.agent.plan(_make_state(13))
        plan = result["analysis_plan"]
        assert "forecast" not in plan

    def test_rfm_included_with_customer_data(self):
        result = self.agent.plan(_make_state(20, has_customer_metrics=True))
        assert "rfm_segments" in result["analysis_plan"]

    def test_rfm_excluded_without_customer_data(self):
        result = self.agent.plan(_make_state(20, has_customer_metrics=False))
        assert "rfm_segments" not in result["analysis_plan"]

    def test_empty_raw_data(self):
        """Should still return core analyses even with empty data."""
        state = {"raw_data": {}, "start_date": "2024-01-01", "end_date": "2024-01-31"}
        result = self.agent.plan(state)
        plan = result["analysis_plan"]
        assert "trends" in plan
        assert "forecast" not in plan
        assert "rfm_segments" not in plan

    def test_none_raw_data(self):
        """Handle missing raw_data gracefully."""
        state = {"start_date": "2024-01-01", "end_date": "2024-01-31"}
        result = self.agent.plan(state)
        assert "analysis_plan" in result
