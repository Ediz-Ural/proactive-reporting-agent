"""
Tests for the FastAPI application endpoints.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def client():
    """Create a FastAPI test client with scheduler disabled."""
    mock_settings = MagicMock()
    mock_settings.SCHEDULER_ENABLED = False

    with patch("config.settings.settings", mock_settings), \
         patch("src.scheduler.start_scheduler", return_value=None):
        from src.api import app
        from fastapi.testclient import TestClient
        return TestClient(app)


class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_health_returns_ok(self, client):
        """Health check returns 200 with status."""
        with patch("src.tools.sql_tools.test_db_connection", return_value={
            "connected": True, "db_type": "sqlite", "message": "ok"
        }), patch("config.settings.settings") as mock_s:
            mock_s.SCHEDULER_ENABLED = False
            response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.5.0"

    def test_health_includes_db_status(self, client):
        """Health check includes database connection info."""
        with patch("src.tools.sql_tools.test_db_connection", return_value={
            "connected": True, "db_type": "sqlite", "message": "ok"
        }), patch("config.settings.settings") as mock_s:
            mock_s.SCHEDULER_ENABLED = False
            response = client.get("/health")

        data = response.json()
        assert "database" in data
        assert data["database"]["connected"] is True

    def test_health_degraded_when_db_down(self, client):
        """Health returns 'degraded' when DB connection fails."""
        with patch("src.tools.sql_tools.test_db_connection", return_value={
            "connected": False, "db_type": "mysql", "message": "fail", "error": "timeout"
        }), patch("config.settings.settings") as mock_s:
            mock_s.SCHEDULER_ENABLED = False
            response = client.get("/health")

        data = response.json()
        assert data["status"] == "degraded"


class TestRunEndpoint:
    """Tests for POST /run."""

    def test_run_returns_started(self, client):
        """POST /run returns run_id and status=started."""
        with patch("src.graph.workflow.run_pipeline") as mock_pipeline:
            mock_pipeline.return_value = {}
            response = client.post("/run", json={
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
            })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert "run_id" in data

    def test_run_accepts_custom_params(self, client):
        """POST /run accepts report_type and recipients."""
        with patch("src.graph.workflow.run_pipeline"):
            response = client.post("/run", json={
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "report_type": "monthly",
                "recipients": ["a@b.com"],
            })

        assert response.status_code == 200

    def test_run_missing_dates_returns_422(self, client):
        """POST /run without dates → validation error."""
        response = client.post("/run", json={})
        assert response.status_code == 422


class TestRunMonthlyEndpoint:
    """Tests for POST /run/monthly."""

    def test_monthly_returns_started(self, client):
        """POST /run/monthly returns status=started."""
        with patch("src.scheduler.get_previous_month_range", return_value=("2026-02-01", "2026-02-28")), \
             patch("src.graph.workflow.run_pipeline_with_retry") as mock_pipeline:
            mock_pipeline.return_value = {}
            response = client.post("/run/monthly")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert "2026-02" in data["message"]

    def test_monthly_uses_previous_month(self, client):
        """POST /run/monthly includes previous month dates in message."""
        with patch("src.scheduler.get_previous_month_range", return_value=("2026-01-01", "2026-01-31")), \
             patch("src.graph.workflow.run_pipeline_with_retry"):
            response = client.post("/run/monthly")

        data = response.json()
        assert "2026-01-01" in data["message"]
        assert "2026-01-31" in data["message"]


class TestRunsEndpoint:
    """Tests for GET /runs."""

    def test_runs_empty_when_no_file(self, client):
        """GET /runs returns empty list when no metrics file."""
        with patch("src.api.Path") as mock_path_cls:
            mock_path = MagicMock()
            mock_path.exists.return_value = False
            mock_path_cls.return_value = mock_path
            response = client.get("/runs")

        assert response.status_code == 200
        data = response.json()
        assert data["runs"] == []

    def test_runs_returns_entries(self, client, tmp_path):
        """GET /runs returns metrics entries."""
        metrics_file = tmp_path / "pipeline_runs.jsonl"
        metrics_file.write_text(
            json.dumps({"run_id": "r1", "quality_score": 0.8}) + "\n"
            + json.dumps({"run_id": "r2", "quality_score": 0.9}) + "\n"
        )

        with patch("src.api.Path", return_value=metrics_file):
            response = client.get("/runs")

        assert response.status_code == 200
        data = response.json()
        assert len(data["runs"]) == 2
        # Most recent first
        assert data["runs"][0]["run_id"] == "r2"

    def test_runs_respects_limit(self, client, tmp_path):
        """GET /runs?limit=1 returns at most 1 entry."""
        metrics_file = tmp_path / "pipeline_runs.jsonl"
        lines = [json.dumps({"run_id": f"r{i}"}) + "\n" for i in range(5)]
        metrics_file.write_text("".join(lines))

        with patch("src.api.Path", return_value=metrics_file):
            response = client.get("/runs?limit=1")

        data = response.json()
        assert len(data["runs"]) == 1


class TestRagStatsEndpoint:
    """Tests for GET /rag/stats."""

    def test_rag_stats_returns_info(self, client):
        """GET /rag/stats returns collection stats."""
        mock_store = MagicMock()
        mock_store.get_collection_stats.return_value = {
            "total_chunks": 15,
            "total_reports": 3,
            "report_ids": ["r1", "r2", "r3"],
        }

        with patch("src.tools.rag_tools.ReportVectorStore", return_value=mock_store):
            response = client.get("/rag/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["total_chunks"] == 15

    def test_rag_stats_error_handling(self, client):
        """GET /rag/stats handles ChromaDB errors gracefully."""
        with patch("src.tools.rag_tools.ReportVectorStore", side_effect=Exception("ChromaDB down")):
            response = client.get("/rag/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
