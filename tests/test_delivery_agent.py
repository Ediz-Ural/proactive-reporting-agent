"""
Tests for the DeliveryAgent — SMTP mock and file fallback.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.delivery import DeliveryAgent


class TestDeliveryAgent:
    """Test suite for DeliveryAgent."""

    def _make_state(self, **overrides):
        state = {
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "report_type": "weekly",
            "recipients": [],
            "raw_data": None,
            "quality_report": None,
            "analysis_results": None,
            "analysis_plan": None,
            "writer_strategy": None,
            "historical_context": "",
            "draft_report": "## Test Report\n\nThis is a test report.",
            "evaluation": {"approved": True, "overall_score": 0.85, "feedback": "OK"},
            "evaluator_iteration": 1,
            "final_report": None,
            "delivery_status": None,
            "feedback_metrics": None,
            "errors": [],
            "current_agent": "evaluator",
            "run_id": "test-run-001",
        }
        state.update(overrides)
        return state

    # ── SMTP delivery (mocked) ───────────────────────────────────────────────

    def test_smtp_send_success(self):
        """SMTP configured + recipients → email sent."""
        mock_settings = MagicMock()
        mock_settings.SMTP_HOST = "smtp.test.com"
        mock_settings.SMTP_PORT = 587
        mock_settings.SMTP_USER = "user@test.com"
        mock_settings.SMTP_PASSWORD = "password"

        state = self._make_state(recipients=["recipient@test.com"])

        with patch("src.agents.delivery.smtplib.SMTP"), \
             patch("src.agents.delivery.DeliveryAgent._send_email") as mock_send:
            mock_send.return_value = {
                "sent": True,
                "recipients": ["recipient@test.com"],
                "timestamp": "2024-01-31T12:00:00",
            }

            agent = DeliveryAgent()
            result = agent.deliver(state)

        assert result["delivery_status"]["sent"] is True
        assert result["final_report"] is not None

    def test_smtp_not_configured_uses_fallback(self, tmp_path):
        """SMTP not configured → saves to files."""
        mock_settings = MagicMock()
        mock_settings.SMTP_HOST = ""
        mock_settings.SMTP_USER = ""

        state = self._make_state(recipients=["someone@example.com"])

        with patch("src.agents.delivery.DeliveryAgent._send_email") as mock_send, \
             patch("src.agents.delivery.DeliveryAgent._save_fallback") as mock_save, \
             patch("src.agents.delivery.DeliveryAgent._send_whatsapp", return_value=None):
            mock_send.return_value = {"sent": False, "reason": "SMTP not configured"}
            mock_save.return_value = {
                "saved_files": ["/tmp/report.md", "/tmp/report.html"],
                "reason": "SMTP not configured — saved to files",
            }

            agent = DeliveryAgent()
            result = agent.deliver(state)

        ds = result["delivery_status"]
        assert ds["sent"] is False
        assert "file" in ds["channels"]
        assert ds["channels"]["file"]["saved_files"] is not None

    def test_smtp_failure_uses_fallback(self):
        """SMTP send fails → fallback to files."""
        state = self._make_state(recipients=["user@test.com"])

        with patch("src.agents.delivery.DeliveryAgent._send_email") as mock_send, \
             patch("src.agents.delivery.DeliveryAgent._save_fallback") as mock_save:
            mock_send.return_value = {"sent": False, "reason": "SMTP error: connection refused"}
            mock_save.return_value = {
                "saved_files": ["/tmp/r.md", "/tmp/r.html"],
                "reason": "fallback",
            }

            agent = DeliveryAgent()
            result = agent.deliver(state)

        assert result["delivery_status"]["sent"] is False

    # ── Empty recipients ─────────────────────────────────────────────────────

    def test_no_recipients_skips_email(self):
        """No recipients → skips email, uses file fallback."""
        state = self._make_state(recipients=[])

        with patch("src.agents.delivery.DeliveryAgent._save_fallback") as mock_save:
            mock_save.return_value = {
                "saved_files": ["/tmp/r.md"],
                "reason": "fallback",
            }

            agent = DeliveryAgent()
            result = agent.deliver(state)

        ds = result["delivery_status"]
        assert ds["sent"] is False

    # ── File fallback ────────────────────────────────────────────────────────

    def test_save_fallback_creates_files(self, tmp_path):
        """File fallback saves md and html files."""
        with patch("src.tools.report_tools.save_report_to_file") as mock_save, \
             patch("src.tools.report_tools.render_report", return_value="<html>test</html>"):
            mock_save.side_effect = [
                str(tmp_path / "report.md"),
                str(tmp_path / "report.html"),
            ]

            agent = DeliveryAgent()
            result = agent._save_fallback("Test content", "2024-01-01", "2024-01-31")

        assert len(result["saved_files"]) == 2
        assert any("md" in f for f in result["saved_files"])
        assert any("html" in f for f in result["saved_files"])

    # ── Final report ─────────────────────────────────────────────────────────

    def test_sets_final_report(self):
        """Delivery sets final_report from draft_report."""
        state = self._make_state(
            draft_report="# Final Report Content",
            recipients=[],
        )

        with patch("src.agents.delivery.DeliveryAgent._save_fallback") as mock_save:
            mock_save.return_value = {"saved_files": [], "reason": "fallback"}

            agent = DeliveryAgent()
            result = agent.deliver(state)

        assert result["final_report"] == "# Final Report Content"

    def test_sets_current_agent(self):
        """Delivery sets current_agent to 'delivery'."""
        state = self._make_state(recipients=[])

        with patch("src.agents.delivery.DeliveryAgent._save_fallback") as mock_save:
            mock_save.return_value = {"saved_files": [], "reason": "fallback"}

            agent = DeliveryAgent()
            result = agent.deliver(state)

        assert result["current_agent"] == "delivery"

    # ── SMTP send_email internals ────────────────────────────────────────────

    def test_send_email_smtp_not_configured(self):
        """_send_email returns sent=False when SMTP host is empty."""
        mock_settings = MagicMock()
        mock_settings.SMTP_HOST = ""
        mock_settings.SMTP_USER = ""

        with patch("config.settings.settings", mock_settings):
            agent = DeliveryAgent()
            result = agent._send_email(
                recipients=["r@test.com"],
                subject="Test",
                body_html="<p>Test</p>",
                body_text="Test",
            )

        assert result["sent"] is False
        assert "SMTP not configured" in result.get("reason", "")

    def test_send_email_with_smtp_error(self):
        """_send_email handles SMTP exceptions gracefully."""
        agent = DeliveryAgent()

        mock_settings = MagicMock()
        mock_settings.SMTP_HOST = "smtp.test.com"
        mock_settings.SMTP_PORT = 587
        mock_settings.SMTP_USER = "user@test.com"
        mock_settings.SMTP_PASSWORD = "pass"

        with patch("src.agents.delivery.smtplib.SMTP", side_effect=Exception("Connection refused")), \
             patch("config.settings.settings", mock_settings):
            result = agent._send_email(
                recipients=["r@test.com"],
                subject="Test",
                body_html="<p>Test</p>",
                body_text="Test",
            )

        assert result["sent"] is False
        assert "SMTP error" in result.get("reason", "")
