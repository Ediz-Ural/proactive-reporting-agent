"""
Tests for WhatsApp delivery via Twilio in DeliveryAgent.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.delivery import DeliveryAgent


def _mock_twilio_module():
    """Create a mock twilio module for tests when twilio is not installed."""
    mock_twilio = MagicMock()
    mock_rest = MagicMock()
    mock_twilio.rest = mock_rest
    return {"twilio": mock_twilio, "twilio.rest": mock_rest}


class TestWhatsAppDelivery:
    """Test suite for WhatsApp delivery via Twilio."""

    def _make_state(self, **overrides):
        state = {
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "report_type": "monthly",
            "recipients": [],
            "raw_data": None,
            "quality_report": None,
            "analysis_results": None,
            "analysis_plan": None,
            "writer_strategy": None,
            "historical_context": "",
            "draft_report": "## Test Report\n\n### Özet Göstergeler\n- Toplam gelir: 50000 TL\n\n### Önemli Bulgular\n- Satışlar arttı\n\n### Aksiyon Önerileri\n1. Stok artırın",
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

    # ── Twilio not configured ─────────────────────────────────────────────────

    def test_whatsapp_skipped_when_not_configured(self):
        """No Twilio credentials → WhatsApp skipped, returns None."""
        mock_settings = MagicMock()
        mock_settings.TWILIO_ACCOUNT_SID = ""
        mock_settings.TWILIO_AUTH_TOKEN = ""

        with patch("config.settings.settings", mock_settings):
            agent = DeliveryAgent()
            result = agent._send_whatsapp("Test report", "2024-01-01", "2024-01-31")

        assert result is None

    def test_whatsapp_skipped_no_recipients(self):
        """Twilio configured but no recipients → skipped."""
        mock_settings = MagicMock()
        mock_settings.TWILIO_ACCOUNT_SID = "ACxxxxx"
        mock_settings.TWILIO_AUTH_TOKEN = "token"
        mock_settings.whatsapp_recipients_list = []

        with patch("config.settings.settings", mock_settings):
            agent = DeliveryAgent()
            result = agent._send_whatsapp("Test report", "2024-01-01", "2024-01-31")

        assert result is None

    # ── Twilio send success ───────────────────────────────────────────────────

    def test_whatsapp_send_success(self):
        """Twilio configured + recipients → sends messages."""
        mock_settings = MagicMock()
        mock_settings.TWILIO_ACCOUNT_SID = "ACxxxxx"
        mock_settings.TWILIO_AUTH_TOKEN = "token"
        mock_settings.WHATSAPP_FROM = "whatsapp:+14155238886"
        mock_settings.whatsapp_recipients_list = ["whatsapp:+905551234567"]

        mock_msg = MagicMock()
        mock_msg.sid = "SM12345"

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg

        mock_twilio_modules = _mock_twilio_module()
        mock_twilio_modules["twilio.rest"].Client.return_value = mock_client

        with patch("config.settings.settings", mock_settings), \
             patch.dict("sys.modules", mock_twilio_modules):
            agent = DeliveryAgent()
            result = agent._send_whatsapp("Test report", "2024-01-01", "2024-01-31")

        assert result is not None
        assert result["sent"] is True
        assert len(result["recipients"]) == 1
        assert result["recipients"][0]["sid"] == "SM12345"

    def test_whatsapp_multiple_recipients(self):
        """Sends to multiple WhatsApp recipients."""
        mock_settings = MagicMock()
        mock_settings.TWILIO_ACCOUNT_SID = "ACxxxxx"
        mock_settings.TWILIO_AUTH_TOKEN = "token"
        mock_settings.WHATSAPP_FROM = "whatsapp:+14155238886"
        mock_settings.whatsapp_recipients_list = [
            "whatsapp:+905551111111",
            "whatsapp:+905552222222",
        ]

        mock_msg = MagicMock()
        mock_msg.sid = "SM99999"

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg

        mock_twilio_modules = _mock_twilio_module()
        mock_twilio_modules["twilio.rest"].Client.return_value = mock_client

        with patch("config.settings.settings", mock_settings), \
             patch.dict("sys.modules", mock_twilio_modules):
            agent = DeliveryAgent()
            result = agent._send_whatsapp("Test", "2024-01-01", "2024-01-31")

        assert result["sent"] is True
        assert len(result["recipients"]) == 2

    # ── Twilio failure ────────────────────────────────────────────────────────

    def test_whatsapp_twilio_error(self):
        """Twilio API error → sent=False, error message."""
        mock_settings = MagicMock()
        mock_settings.TWILIO_ACCOUNT_SID = "ACxxxxx"
        mock_settings.TWILIO_AUTH_TOKEN = "token"
        mock_settings.WHATSAPP_FROM = "whatsapp:+14155238886"
        mock_settings.whatsapp_recipients_list = ["whatsapp:+905551234567"]

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("Twilio API error")

        mock_twilio_modules = _mock_twilio_module()
        mock_twilio_modules["twilio.rest"].Client.return_value = mock_client

        with patch("config.settings.settings", mock_settings), \
             patch.dict("sys.modules", mock_twilio_modules):
            agent = DeliveryAgent()
            result = agent._send_whatsapp("Test", "2024-01-01", "2024-01-31")

        assert result["sent"] is False
        assert "Twilio error" in result["reason"]

    def test_whatsapp_import_error(self):
        """twilio not installed → sent=False."""
        mock_settings = MagicMock()
        mock_settings.TWILIO_ACCOUNT_SID = "ACxxxxx"
        mock_settings.TWILIO_AUTH_TOKEN = "token"
        mock_settings.WHATSAPP_FROM = "whatsapp:+14155238886"
        mock_settings.whatsapp_recipients_list = ["whatsapp:+905551234567"]

        with patch("config.settings.settings", mock_settings), \
             patch.dict("sys.modules", {"twilio": None, "twilio.rest": None}):
            agent = DeliveryAgent()
            result = agent._send_whatsapp("Test", "2024-01-01", "2024-01-31")

        assert result is not None
        assert result["sent"] is False

    # ── Message formatting ────────────────────────────────────────────────────

    def test_format_whatsapp_message_contains_emoji(self):
        """WhatsApp message contains report emoji."""
        agent = DeliveryAgent()
        msg = agent._format_whatsapp_message(
            "## Report\n\n### Özet\n- Revenue: 50000\n\n### Bulgular\n- Sales up",
            "2024-01-01",
            "2024-01-31",
        )
        assert "📊" in msg
        assert "📅" in msg

    def test_format_whatsapp_message_contains_dates(self):
        """WhatsApp message includes the report period."""
        agent = DeliveryAgent()
        msg = agent._format_whatsapp_message("Test", "2024-01-01", "2024-01-31")
        assert "2024-01-01" in msg
        assert "2024-01-31" in msg

    def test_format_whatsapp_message_max_length(self):
        """WhatsApp message is truncated to 1600 chars."""
        agent = DeliveryAgent()
        long_report = "- " + "A" * 2000 + "\n" * 100
        msg = agent._format_whatsapp_message(long_report, "2024-01-01", "2024-01-31")
        assert len(msg) <= 1600

    def test_format_whatsapp_empty_report(self):
        """Empty report still produces a message with header."""
        agent = DeliveryAgent()
        msg = agent._format_whatsapp_message("", "2024-01-01", "2024-01-31")
        assert "📊" in msg

    # ── Integration with deliver() ────────────────────────────────────────────

    def test_deliver_includes_whatsapp_channel(self):
        """deliver() includes whatsapp in channels when configured."""
        state = self._make_state()

        agent = DeliveryAgent()

        with patch.object(agent, "_save_fallback") as mock_save, \
             patch.object(agent, "_send_whatsapp") as mock_wa:
            mock_save.return_value = {"saved_files": ["/tmp/r.md"], "reason": "backup"}
            mock_wa.return_value = {
                "sent": True,
                "recipients": [{"to": "whatsapp:+905551234567", "sid": "SM777"}],
                "timestamp": "2024-01-31T12:00:00",
            }
            result = agent.deliver(state)

        ds = result["delivery_status"]
        assert "whatsapp" in ds["channels"]
        assert ds["channels"]["whatsapp"]["sent"] is True

    def test_deliver_whatsapp_failure_doesnt_block_file(self):
        """WhatsApp failure does not prevent file save."""
        state = self._make_state()

        with patch("src.agents.delivery.DeliveryAgent._send_whatsapp") as mock_wa, \
             patch("src.agents.delivery.DeliveryAgent._save_fallback") as mock_save:
            mock_wa.return_value = {"sent": False, "reason": "error"}
            mock_save.return_value = {"saved_files": ["/tmp/r.md"], "reason": "backup"}

            agent = DeliveryAgent()
            result = agent.deliver(state)

        ds = result["delivery_status"]
        assert "file" in ds["channels"]
        assert ds["channels"]["file"]["success"] is True
