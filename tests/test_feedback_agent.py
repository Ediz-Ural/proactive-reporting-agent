"""
Tests for the FeedbackAgent — metrics collection and JSONL output.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.feedback import FeedbackAgent


class TestFeedbackAgent:
    """Test suite for FeedbackAgent."""

    def _make_state(self, **overrides):
        state = {
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "report_type": "weekly",
            "recipients": [],
            "raw_data": None,
            "quality_report": None,
            "analysis_results": {
                "analysis_metadata": {
                    "analyses_completed": ["trends", "anomalies", "forecast"],
                    "analyses_failed": ["decomposition"],
                },
            },
            "analysis_plan": None,
            "writer_strategy": None,
            "historical_context": "Some past context",
            "draft_report": "Test report",
            "evaluation": {
                "approved": True,
                "overall_score": 0.85,
                "feedback": "Good report.",
            },
            "evaluator_iteration": 1,
            "final_report": "Test report",
            "delivery_status": {"sent": False, "saved_files": ["/tmp/r.md"]},
            "feedback_metrics": None,
            "errors": [],
            "current_agent": "delivery",
            "run_id": "test-run-001",
        }
        state.update(overrides)
        return state

    # ── Metrics collection ───────────────────────────────────────────────────

    def test_collects_basic_metrics(self, tmp_path):
        """FeedbackAgent collects all expected metric fields."""
        metrics_file = tmp_path / "metrics.jsonl"

        with patch("src.agents.feedback.METRICS_FILE", metrics_file):
            agent = FeedbackAgent()
            result = agent.collect(self._make_state())

        metrics = result["feedback_metrics"]
        assert metrics["run_id"] == "test-run-001"
        assert metrics["report_type"] == "weekly"
        assert metrics["quality_score"] == 0.85
        assert metrics["evaluator_iterations"] == 1
        assert metrics["approved_on_first_try"] is True
        assert metrics["delivery_sent"] is False
        assert metrics["error_count"] == 0
        assert "trends" in metrics["analyses_completed"]
        assert "decomposition" in metrics["analyses_failed"]
        assert metrics["had_historical_context"] is True

    def test_metrics_with_multiple_iterations(self, tmp_path):
        """approved_on_first_try=False when evaluator_iteration > 1."""
        metrics_file = tmp_path / "metrics.jsonl"

        with patch("src.agents.feedback.METRICS_FILE", metrics_file):
            agent = FeedbackAgent()
            result = agent.collect(self._make_state(evaluator_iteration=3))

        assert result["feedback_metrics"]["evaluator_iterations"] == 3
        assert result["feedback_metrics"]["approved_on_first_try"] is False

    def test_metrics_with_errors(self, tmp_path):
        """error_count reflects actual errors."""
        metrics_file = tmp_path / "metrics.jsonl"

        with patch("src.agents.feedback.METRICS_FILE", metrics_file):
            agent = FeedbackAgent()
            result = agent.collect(
                self._make_state(errors=["Error 1", "Error 2"])
            )

        assert result["feedback_metrics"]["error_count"] == 2

    def test_metrics_no_historical_context(self, tmp_path):
        """had_historical_context=False when historical_context is empty."""
        metrics_file = tmp_path / "metrics.jsonl"

        with patch("src.agents.feedback.METRICS_FILE", metrics_file):
            agent = FeedbackAgent()
            result = agent.collect(self._make_state(historical_context=""))

        assert result["feedback_metrics"]["had_historical_context"] is False

    # ── JSONL file output ────────────────────────────────────────────────────

    def test_saves_metrics_to_jsonl(self, tmp_path):
        """Metrics are appended to JSONL file."""
        metrics_file = tmp_path / "metrics.jsonl"

        with patch("src.agents.feedback.METRICS_FILE", metrics_file):
            agent = FeedbackAgent()
            agent.collect(self._make_state())

        assert metrics_file.exists()
        lines = metrics_file.read_text().strip().split("\n")
        assert len(lines) == 1

        data = json.loads(lines[0])
        assert data["run_id"] == "test-run-001"

    def test_appends_to_existing_jsonl(self, tmp_path):
        """Multiple runs append to the same JSONL file."""
        metrics_file = tmp_path / "metrics.jsonl"

        with patch("src.agents.feedback.METRICS_FILE", metrics_file):
            agent = FeedbackAgent()
            agent.collect(self._make_state(run_id="run-1"))
            agent.collect(self._make_state(run_id="run-2"))

        lines = metrics_file.read_text().strip().split("\n")
        assert len(lines) == 2

        data1 = json.loads(lines[0])
        data2 = json.loads(lines[1])
        assert data1["run_id"] == "run-1"
        assert data2["run_id"] == "run-2"

    def test_creates_parent_directory(self, tmp_path):
        """JSONL file parent directory is created if missing."""
        metrics_file = tmp_path / "nested" / "dir" / "metrics.jsonl"

        with patch("src.agents.feedback.METRICS_FILE", metrics_file):
            agent = FeedbackAgent()
            agent.collect(self._make_state())

        assert metrics_file.exists()

    # ── Graceful handling of missing state ───────────────────────────────────

    def test_missing_evaluation(self, tmp_path):
        """Missing evaluation dict → quality_score defaults to 0."""
        metrics_file = tmp_path / "metrics.jsonl"

        with patch("src.agents.feedback.METRICS_FILE", metrics_file):
            agent = FeedbackAgent()
            result = agent.collect(self._make_state(evaluation=None))

        assert result["feedback_metrics"]["quality_score"] == 0

    def test_missing_delivery_status(self, tmp_path):
        """Missing delivery_status → delivery_sent defaults to False."""
        metrics_file = tmp_path / "metrics.jsonl"

        with patch("src.agents.feedback.METRICS_FILE", metrics_file):
            agent = FeedbackAgent()
            result = agent.collect(self._make_state(delivery_status=None))

        assert result["feedback_metrics"]["delivery_sent"] is False

    def test_missing_analysis_results(self, tmp_path):
        """Missing analysis_results → empty analyses lists."""
        metrics_file = tmp_path / "metrics.jsonl"

        with patch("src.agents.feedback.METRICS_FILE", metrics_file):
            agent = FeedbackAgent()
            result = agent.collect(self._make_state(analysis_results=None))

        assert result["feedback_metrics"]["analyses_completed"] == []
        assert result["feedback_metrics"]["analyses_failed"] == []

    # ── current_agent field ──────────────────────────────────────────────────

    def test_sets_current_agent(self, tmp_path):
        """Feedback sets current_agent to 'feedback'."""
        metrics_file = tmp_path / "metrics.jsonl"

        with patch("src.agents.feedback.METRICS_FILE", metrics_file):
            agent = FeedbackAgent()
            result = agent.collect(self._make_state())

        assert result["current_agent"] == "feedback"

    def test_period_format(self, tmp_path):
        """Period string is formatted correctly."""
        metrics_file = tmp_path / "metrics.jsonl"

        with patch("src.agents.feedback.METRICS_FILE", metrics_file):
            agent = FeedbackAgent()
            result = agent.collect(self._make_state())

        assert result["feedback_metrics"]["period"] == "2024-01-01 to 2024-01-31"
