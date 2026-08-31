"""
Tests for the FastAPI application endpoints.
Updated for v0.7.0 — auth-protected routes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def _make_mock_settings():
    mock_settings = MagicMock()
    mock_settings.SCHEDULER_ENABLED = False
    mock_settings.JWT_SECRET_KEY = "test-secret-key"
    mock_settings.JWT_ALGORITHM = "HS256"
    mock_settings.JWT_EXPIRE_MINUTES = 480
    return mock_settings


@pytest.fixture
def client():
    """Create a FastAPI test client with scheduler disabled."""
    mock_settings = _make_mock_settings()

    with patch("config.settings.settings", mock_settings), \
         patch("src.auth.settings", mock_settings), \
         patch("src.scheduler.start_scheduler", return_value=None):
        from fastapi.testclient import TestClient

        from src.api import app
        return TestClient(app)


@pytest.fixture
def auth_headers(client):
    """Generate a valid JWT token for testing authenticated endpoints."""
    from src.auth import create_access_token
    mock_settings = _make_mock_settings()

    with patch("src.auth.settings", mock_settings):
        token = create_access_token({
            "user_id": 1,
            "email": "test@test.com",
            "role": "admin",
            "company_id": 1,
            "company_name": "Test Co",
        })
    return {"Authorization": f"Bearer {token}"}


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
        assert data["version"] == "0.7.0"

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

    def test_run_returns_started(self, client, auth_headers):
        """POST /run returns run_id and status=started."""
        with patch("src.graph.workflow.run_pipeline") as mock_pipeline:
            mock_pipeline.return_value = {}
            response = client.post("/run", json={
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
            }, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert "run_id" in data

    def test_run_accepts_custom_params(self, client, auth_headers):
        """POST /run accepts report_type and recipients."""
        with patch("src.graph.workflow.run_pipeline"):
            response = client.post("/run", json={
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "report_type": "monthly",
                "recipients": ["a@b.com"],
            }, headers=auth_headers)

        assert response.status_code == 200

    def test_run_missing_dates_returns_422(self, client, auth_headers):
        """POST /run without dates -> validation error."""
        response = client.post("/run", json={}, headers=auth_headers)
        assert response.status_code == 422


class TestRunMonthlyEndpoint:
    """Tests for POST /run/monthly."""

    def test_monthly_returns_started(self, client, auth_headers):
        """POST /run/monthly returns status=started."""
        with patch("src.scheduler.get_previous_month_range", return_value=("2026-02-01", "2026-02-28")), \
             patch("src.graph.workflow.run_pipeline_with_retry") as mock_pipeline:
            mock_pipeline.return_value = {}
            response = client.post("/run/monthly", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert "2026-02" in data["message"]

    def test_monthly_uses_previous_month(self, client, auth_headers):
        """POST /run/monthly includes previous month dates in message."""
        with patch("src.scheduler.get_previous_month_range", return_value=("2026-01-01", "2026-01-31")), \
             patch("src.graph.workflow.run_pipeline_with_retry"):
            response = client.post("/run/monthly", headers=auth_headers)

        data = response.json()
        assert "2026-01-01" in data["message"]
        assert "2026-01-31" in data["message"]


class TestRunsEndpoint:
    """Tests for GET /runs."""

    def test_runs_empty_when_no_file(self, client, auth_headers):
        """GET /runs returns empty list when no metrics file."""
        with patch.object(Path, "exists", return_value=False):
            response = client.get("/runs", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["runs"] == []

    def test_runs_returns_entries(self, client, auth_headers, tmp_path):
        """GET /runs returns metrics entries for user's company."""
        metrics_file = tmp_path / "pipeline_runs.jsonl"
        metrics_file.write_text(
            json.dumps({"run_id": "r1", "quality_score": 0.8, "company_id": 1}) + "\n"
            + json.dumps({"run_id": "r2", "quality_score": 0.9, "company_id": 1}) + "\n"
        )

        with patch("src.api.METRICS_PATH", metrics_file):
            response = client.get("/runs", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["runs"]) == 2
        assert data["runs"][0]["run_id"] == "r2"

    def test_runs_respects_limit(self, client, auth_headers, tmp_path):
        """GET /runs?limit=1 returns at most 1 entry."""
        metrics_file = tmp_path / "pipeline_runs.jsonl"
        lines = [json.dumps({"run_id": f"r{i}", "company_id": 1}) + "\n" for i in range(5)]
        metrics_file.write_text("".join(lines))

        with patch("src.api.METRICS_PATH", metrics_file):
            response = client.get("/runs?limit=1", headers=auth_headers)

        data = response.json()
        assert len(data["runs"]) == 1


class TestRagStatsEndpoint:
    """Tests for GET /rag/stats."""

    def test_rag_stats_returns_info(self, client, auth_headers):
        """GET /rag/stats returns collection stats."""
        mock_store = MagicMock()
        mock_store.get_collection_stats.return_value = {
            "total_chunks": 15,
            "total_reports": 3,
            "report_ids": ["r1", "r2", "r3"],
        }

        with patch("src.tools.rag_tools.ReportVectorStore", return_value=mock_store):
            response = client.get("/rag/stats", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["total_chunks"] == 15

    def test_rag_stats_error_handling(self, client, auth_headers):
        """GET /rag/stats handles ChromaDB errors gracefully."""
        with patch("src.tools.rag_tools.ReportVectorStore", side_effect=Exception("ChromaDB down")):
            response = client.get("/rag/stats", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"


class TestLatestRunEndpoint:
    """Tests for GET /runs/latest."""

    def test_latest_run_returns_data(self, client, auth_headers, tmp_path):
        """GET /runs/latest returns the most recent run."""
        metrics_file = tmp_path / "pipeline_runs.jsonl"
        metrics_file.write_text(
            json.dumps({"run_id": "r1", "quality_score": 0.8, "company_id": 1}) + "\n"
            + json.dumps({"run_id": "r2", "quality_score": 0.9, "company_id": 1}) + "\n"
        )

        with patch("src.api.METRICS_PATH", metrics_file), \
             patch("src.api.Path") as mock_path_cls:
            mock_reports_dir = MagicMock()
            mock_reports_dir.exists.return_value = False
            mock_path_cls.side_effect = lambda p: mock_reports_dir if "data/reports" in str(p) else Path(p)

            response = client.get("/runs/latest", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["run"]["run_id"] == "r2"

    def test_latest_run_404_when_empty(self, client, auth_headers, tmp_path):
        """GET /runs/latest returns 404 when no runs exist."""
        metrics_file = tmp_path / "pipeline_runs.jsonl"

        with patch("src.api.METRICS_PATH", metrics_file):
            response = client.get("/runs/latest", headers=auth_headers)

        assert response.status_code == 404


class TestRunDetailEndpoint:
    """Tests for GET /runs/{run_id}."""

    def test_run_detail_found(self, client, auth_headers, tmp_path):
        """GET /runs/{run_id} returns the matching run."""
        metrics_file = tmp_path / "pipeline_runs.jsonl"
        metrics_file.write_text(
            json.dumps({"run_id": "abc-123", "quality_score": 0.85, "company_id": 1}) + "\n"
        )

        with patch("src.api.METRICS_PATH", metrics_file):
            response = client.get("/runs/abc-123", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["run"]["run_id"] == "abc-123"

    def test_run_detail_not_found(self, client, auth_headers, tmp_path):
        """GET /runs/{run_id} returns 404 for unknown run."""
        metrics_file = tmp_path / "pipeline_runs.jsonl"
        metrics_file.write_text(json.dumps({"run_id": "other", "company_id": 1}) + "\n")

        with patch("src.api.METRICS_PATH", metrics_file):
            response = client.get("/runs/nonexistent", headers=auth_headers)

        assert response.status_code == 404


class TestReportsEndpoint:
    """Tests for GET /reports."""

    def test_reports_list(self, client, auth_headers, tmp_path):
        """GET /reports returns file list for admin (all companies)."""
        base = tmp_path / "reports"
        (base / "1").mkdir(parents=True)
        (base / "1" / "report_a.md").write_text("# A")
        (base / "1" / "report_b.md").write_text("# B")
        (base / "1" / "report_b.html").write_text("<h1>B</h1>")

        with patch("src.api.Path", side_effect=lambda p: base if p == "data/reports" else Path(p)):
            response = client.get("/reports", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["reports"]) == 2
        assert all("company_id" in r for r in data["reports"])

    def test_reports_filter_by_company(self, client, auth_headers, tmp_path):
        """GET /reports?company_id=2 returns only that company's reports."""
        base = tmp_path / "reports"
        (base / "1").mkdir(parents=True)
        (base / "2").mkdir(parents=True)
        (base / "1" / "r1.md").write_text("# 1")
        (base / "2" / "r2.md").write_text("# 2")

        def mock_path(p):
            if p == "data/reports":
                return base
            if "data/reports/" in p:
                cid = p.split("/")[-1]
                return base / cid
            return Path(p)

        with patch("src.api.Path", side_effect=mock_path):
            response = client.get("/reports?company_id=2", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["reports"]) == 1
        assert data["reports"][0]["company_id"] == 2

    def test_reports_empty_dir(self, client, auth_headers, tmp_path):
        """GET /reports returns empty list when no reports exist."""
        base = tmp_path / "empty_reports"
        base.mkdir()

        with patch("src.api.Path", side_effect=lambda p: base if p == "data/reports" else Path(p)):
            response = client.get("/reports", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["reports"] == []


class TestReportDetailEndpoint:
    """Tests for GET /reports/{filename}."""

    def test_report_path_traversal_blocked(self, client, auth_headers):
        """GET /reports/{filename} blocks path traversal attempts."""
        response = client.get("/reports/..%2F..%2Fetc%2Fpasswd", headers=auth_headers)
        assert response.status_code in (400, 404)


class TestDbStatsEndpoint:
    """Tests for GET /db/stats."""

    def test_db_stats_returns_data(self, client, auth_headers):
        """GET /db/stats returns database statistics."""
        with patch("src.tools.sql_tools.execute_query") as mock_query:
            mock_query.side_effect = [
                pd.DataFrame({"cnt": [9986]}),
                pd.DataFrame({"min_date": ["2014-01-03"], "max_date": ["2017-12-30"]}),
                pd.DataFrame({
                    "category": ["Furniture", "Office Supplies", "Technology"],
                    "cnt": [2001, 6026, 1847],
                }),
            ]
            response = client.get("/db/stats", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total_orders"] == 9986
        assert data["date_range"]["min"] == "2014-01-03"
        assert data["date_range"]["max"] == "2017-12-30"
        assert len(data["categories"]) == 3

    def test_db_stats_handles_error(self, client, auth_headers):
        """GET /db/stats returns 500 on database error."""
        with patch("src.tools.sql_tools.execute_query", side_effect=RuntimeError("DB down")):
            response = client.get("/db/stats", headers=auth_headers)

        assert response.status_code == 500


class TestRunSyncEndpoint:
    """Tests for POST /run/sync."""

    def test_sync_returns_results(self, client, auth_headers):
        """POST /run/sync returns full pipeline results."""
        mock_state = {
            "run_id": "sync-123",
            "raw_data": {"weekly_summary": {"total_revenue": 1000}},
            "analysis_results": {"trends": []},
            "draft_report": "# Report",
            "evaluation": {"overall_score": 0.85, "approved": True},
            "delivery_status": {"file": True},
            "errors": [],
        }

        with patch("src.graph.workflow.run_pipeline", return_value=mock_state):
            response = client.post("/run/sync", json={
                "start_date": "2017-01-01",
                "end_date": "2017-01-31",
                "report_type": "monthly",
            }, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["run_id"] == "sync-123"
        assert data["weekly_summary"]["total_revenue"] == 1000
        assert data["draft_report"] == "# Report"
        assert data["evaluation"]["approved"] is True

    def test_sync_missing_dates_returns_422(self, client, auth_headers):
        """POST /run/sync without dates -> validation error."""
        response = client.post("/run/sync", json={}, headers=auth_headers)
        assert response.status_code == 422


class TestCORSHeaders:
    """Tests for CORS middleware."""

    def test_cors_allows_localhost_5173(self, client):
        """CORS preflight allows React dev server origin."""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"

    def test_cors_allows_localhost_3000(self, client):
        """CORS preflight allows production frontend origin."""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
