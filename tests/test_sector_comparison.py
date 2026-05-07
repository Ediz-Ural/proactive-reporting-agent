"""
Tests for sector comparison functionality.

Tests the calculate_sector_comparison tool and the analyst agent's
_run_sector_comparison method.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tools.analysis_tools import calculate_sector_comparison


def _mock_execute_query(query: str, params: dict | None = None) -> pd.DataFrame:
    """Mock execute_query to return predictable data for sector comparison tests."""
    query_lower = query.lower().strip()

    if "c.id, c.name, c.segment" in query_lower:
        return pd.DataFrame([{"id": 1, "name": "TechVision Elektronik A.S.", "segment": "Consumer"}])

    if "c.id, c.name" in query_lower and "c.segment" in query_lower:
        return pd.DataFrame([
            {"id": 1, "name": "TechVision Elektronik A.S."},
            {"id": 2, "name": "OfisPro Kirtasiye Ltd."},
            {"id": 3, "name": "Anadolu Mobilya A.S."},
            {"id": 4, "name": "Akdeniz Perakende Ltd."},
        ])

    if "sum(sales)" in query_lower:
        return pd.DataFrame([
            {"company_id": 1, "total_revenue": 50000.0, "total_profit": 5000.0, "total_orders": 100, "unique_customers": 50},
            {"company_id": 2, "total_revenue": 60000.0, "total_profit": 7200.0, "total_orders": 120, "unique_customers": 55},
            {"company_id": 3, "total_revenue": 40000.0, "total_profit": 2000.0, "total_orders": 80, "unique_customers": 40},
            {"company_id": 4, "total_revenue": 30000.0, "total_profit": -500.0, "total_orders": 60, "unique_customers": 30},
        ])

    return pd.DataFrame()


class TestSectorComparison:
    """Tests for calculate_sector_comparison."""

    @patch("src.tools.sql_tools.execute_query", side_effect=_mock_execute_query)
    def test_basic_structure(self, mock_eq):
        result = calculate_sector_comparison(1, "2024-01-01", "2024-01-31")

        assert "sector_segment" in result
        assert "company_rank" in result
        assert "total_in_sector" in result
        assert "company_kpis" in result
        assert "sector_avg" in result
        assert "peers" in result

    @patch("src.tools.sql_tools.execute_query", side_effect=_mock_execute_query)
    def test_correct_ranking(self, mock_eq):
        result = calculate_sector_comparison(1, "2024-01-01", "2024-01-31")

        assert result["total_in_sector"] == 4
        assert result["company_rank"] == 2  # company 1 has 50k, company 2 has 60k

    @patch("src.tools.sql_tools.execute_query", side_effect=_mock_execute_query)
    def test_anonymized_peers(self, mock_eq):
        result = calculate_sector_comparison(1, "2024-01-01", "2024-01-31")

        peers = result["peers"]
        assert len(peers) == 3  # 4 total minus the target company
        labels = [p["label"] for p in peers]
        assert "Firma A" in labels
        assert "Firma B" in labels
        assert "Firma C" in labels
        for peer in peers:
            assert "TechVision" not in peer["label"]
            assert "OfisPro" not in peer["label"]

    @patch("src.tools.sql_tools.execute_query", side_effect=_mock_execute_query)
    def test_company_kpis(self, mock_eq):
        result = calculate_sector_comparison(1, "2024-01-01", "2024-01-31")

        kpis = result["company_kpis"]
        assert kpis["total_revenue"] == 50000.0
        assert kpis["total_profit"] == 5000.0
        assert kpis["total_orders"] == 100
        assert kpis["unique_customers"] == 50

    @patch("src.tools.sql_tools.execute_query", side_effect=_mock_execute_query)
    def test_sector_averages(self, mock_eq):
        result = calculate_sector_comparison(1, "2024-01-01", "2024-01-31")

        avg = result["sector_avg"]
        assert avg["avg_revenue"] == 45000.0  # (50k + 60k + 40k + 30k) / 4
        assert "avg_profit" in avg
        assert "avg_margin_pct" in avg

    @patch("src.tools.sql_tools.execute_query", side_effect=_mock_execute_query)
    def test_segment_label(self, mock_eq):
        result = calculate_sector_comparison(1, "2024-01-01", "2024-01-31")
        assert result["sector_segment"] == "Consumer"

    @patch("src.tools.sql_tools.execute_query", return_value=pd.DataFrame())
    def test_unknown_company_returns_empty(self, mock_eq):
        result = calculate_sector_comparison(999, "2024-01-01", "2024-01-31")
        assert result == {}

    @patch("src.tools.sql_tools.execute_query")
    def test_single_peer_returns_note(self, mock_eq):
        def side_effect(query, params=None):
            if "c.id, c.name, c.segment" in query.lower():
                return pd.DataFrame([{"id": 1, "name": "Test", "segment": "Consumer"}])
            if "c.id, c.name" in query.lower():
                return pd.DataFrame([{"id": 1, "name": "Test"}])  # only 1 peer
            return pd.DataFrame()

        mock_eq.side_effect = side_effect
        result = calculate_sector_comparison(1, "2024-01-01", "2024-01-31")
        assert "note" in result

    @patch("src.tools.sql_tools.execute_query", side_effect=_mock_execute_query)
    def test_profit_margin_calculated(self, mock_eq):
        result = calculate_sector_comparison(1, "2024-01-01", "2024-01-31")

        kpis = result["company_kpis"]
        assert "profit_margin_pct" in kpis
        assert kpis["profit_margin_pct"] == 10.0  # 5000/50000 * 100

    @patch("src.tools.sql_tools.execute_query", side_effect=_mock_execute_query)
    def test_peer_ranking_order(self, mock_eq):
        result = calculate_sector_comparison(1, "2024-01-01", "2024-01-31")

        peers = result["peers"]
        revenues = [p["total_revenue"] for p in peers]
        assert revenues == sorted(revenues, reverse=True)


class TestAnalystSectorComparison:
    """Tests for the analyst agent's sector comparison integration."""

    @patch("src.tools.sql_tools.execute_query", side_effect=_mock_execute_query)
    def test_analyst_runs_sector_comparison(self, mock_eq):
        from src.agents.analyst import AnalystAgent

        agent = AnalystAgent()
        result, ok = agent._run_sector_comparison(1, "2024-01-01", "2024-01-31")
        assert ok is True
        assert "company_rank" in result

    @patch("src.tools.sql_tools.execute_query", side_effect=Exception("DB error"))
    def test_analyst_handles_failure_gracefully(self, mock_eq):
        from src.agents.analyst import AnalystAgent

        agent = AnalystAgent()
        result, ok = agent._run_sector_comparison(1, "2024-01-01", "2024-01-31")
        assert ok is False
        assert result == {}

    @patch("src.tools.sql_tools.execute_query", side_effect=_mock_execute_query)
    def test_sector_comparison_in_analysis_plan(self, mock_eq):
        """When sector_comparison is in the plan, analyst includes it in results."""
        from src.agents.analyst import AnalystAgent

        agent = AnalystAgent()
        state = {
            "raw_data": {"daily_sales": [], "by_category": []},
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "report_type": "monthly",
            "company_id": 1,
            "analysis_plan": ["sector_comparison"],
        }
        result = agent.analyse(state)
        assert "sector_comparison" in result["analysis_results"]
        assert "sector_comparison" in result["analysis_results"]["analysis_metadata"]["analyses_completed"]
