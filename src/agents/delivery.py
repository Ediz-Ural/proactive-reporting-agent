"""
Delivery Agent — Week 5 implementation.

Sends the approved report via:
1. File save (always — as backup)
2. Email (SMTP, if configured)
3. WhatsApp (Twilio, if configured)

Each channel is independent — failure in one does not block the others.
"""

from __future__ import annotations

import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.graph.state import AgentState

logger = logging.getLogger(__name__)


class DeliveryAgent:
    """
    Sends the final report to recipients via multiple channels.

    Channels (all independent — failure in one does not affect others):
    1. File save (md + html) — always runs as backup
    2. SMTP email — if SMTP_HOST configured
    3. WhatsApp via Twilio — if TWILIO_ACCOUNT_SID configured
    """

    def deliver(self, state: AgentState) -> dict:
        """
        Send or save the final report.

        Reads from state: draft_report, recipients, start_date, end_date
        Writes to state: final_report, delivery_status, current_agent
        """
        draft_report = state.get("draft_report") or ""
        recipients = state.get("recipients") or []
        start_date = state.get("start_date", "")
        end_date = state.get("end_date", "")

        logger.info("DeliveryAgent: preparing delivery (recipients=%d)", len(recipients))

        final_report = draft_report
        result: dict = {"sent": False, "channels": {}}

        # 1. Always save to files as backup
        try:
            fallback = self._save_fallback(final_report, start_date, end_date)
            result["channels"]["file"] = {"success": True, **fallback}
        except Exception as exc:
            logger.error("DeliveryAgent: file save failed: %s", exc)
            result["channels"]["file"] = {"success": False, "error": str(exc)}

        # 2. Try SMTP email
        if recipients:
            subject = f"Satış Raporu — {start_date} / {end_date}"
            email_result = self._send_email(
                recipients=recipients,
                subject=subject,
                body_html=self._render_html(final_report, start_date, end_date),
                body_text=final_report,
            )
            result["channels"]["email"] = email_result
            if email_result.get("sent"):
                result["sent"] = True

        # 3. Try WhatsApp via Twilio
        whatsapp_result = self._send_whatsapp(final_report, start_date, end_date)
        if whatsapp_result:
            result["channels"]["whatsapp"] = whatsapp_result
            if whatsapp_result.get("sent"):
                result["sent"] = True

        # Backward compat: if neither email nor whatsapp sent, mark sent=False
        if not result["sent"]:
            result["reason"] = "No remote delivery succeeded — files saved as fallback"

        logger.info(
            "DeliveryAgent: delivery complete (sent=%s, channels=%s)",
            result["sent"],
            list(result["channels"].keys()),
        )

        return {
            "final_report": final_report,
            "delivery_status": result,
            "current_agent": "delivery",
        }

    # ── SMTP email ───────────────────────────────────────────────────────────

    def _send_email(
        self,
        recipients: list[str],
        subject: str,
        body_html: str,
        body_text: str,
    ) -> dict:
        """
        Send email via SMTP.

        Returns:
            Dict with sent status, recipients, timestamp, and error (if any).
        """
        from config.settings import settings

        if not settings.SMTP_HOST or not settings.SMTP_USER:
            logger.warning("SMTP not configured — skipping email delivery")
            return {"sent": False, "reason": "SMTP not configured"}

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_USER
        msg["To"] = ", ".join(recipients)

        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_USER, recipients, msg.as_string())

            logger.info("Email sent to %s", recipients)
            return {
                "sent": True,
                "recipients": recipients,
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as exc:
            logger.error("Email delivery failed: %s", exc)
            return {
                "sent": False,
                "reason": f"SMTP error: {exc}",
            }

    # ── WhatsApp via Twilio ───────────────────────────────────────────────────

    def _send_whatsapp(
        self, report_content: str, start_date: str, end_date: str
    ) -> dict | None:
        """
        Send a WhatsApp summary via Twilio.

        Returns None if Twilio is not configured, otherwise a result dict.
        """
        from config.settings import settings

        if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
            logger.debug("Twilio not configured — skipping WhatsApp delivery")
            return None

        wa_recipients = settings.whatsapp_recipients_list
        if not wa_recipients:
            logger.debug("No WhatsApp recipients — skipping")
            return None

        message_body = self._format_whatsapp_message(report_content, start_date, end_date)

        try:
            from twilio.rest import Client

            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            sent_to = []

            for recipient in wa_recipients:
                msg = client.messages.create(
                    body=message_body,
                    from_=settings.WHATSAPP_FROM,
                    to=recipient,
                )
                sent_to.append({"to": recipient, "sid": msg.sid})
                logger.info("WhatsApp sent to %s (sid=%s)", recipient, msg.sid)

            return {
                "sent": True,
                "recipients": sent_to,
                "timestamp": datetime.utcnow().isoformat(),
            }
        except ImportError:
            logger.warning("twilio package not installed — skipping WhatsApp")
            return {"sent": False, "reason": "twilio package not installed"}
        except Exception as exc:
            logger.error("WhatsApp delivery failed: %s", exc)
            return {"sent": False, "reason": f"Twilio error: {exc}"}

    @staticmethod
    def _format_whatsapp_message(
        report_content: str, start_date: str, end_date: str
    ) -> str:
        """
        Format the report as a short WhatsApp-friendly message (max 1600 chars).

        Extracts key sections and adds emoji indicators.
        """
        lines = report_content.strip().split("\n")

        parts = [
            f"📊 *Satış Raporu*",
            f"📅 {start_date} — {end_date}",
            "",
        ]

        # Extract summary indicators and key findings
        in_section = False
        section_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            # Capture bullet points and numbered items
            if stripped.startswith("- ") or (stripped[:2].replace(".", "").isdigit()):
                section_lines.append(stripped)
            elif stripped.startswith("###"):
                # Section headers
                header = stripped.lstrip("# ").strip()
                if section_lines:
                    parts.append("")
                section_lines = []
                parts.append(f"*{header}*")

        if section_lines:
            parts.extend(section_lines)

        message = "\n".join(parts)

        # Truncate to 1600 chars (WhatsApp limit)
        if len(message) > 1600:
            message = message[:1597] + "..."

        return message

    # ── File fallback ────────────────────────────────────────────────────────

    def _save_fallback(self, report_content: str, start_date: str, end_date: str) -> dict:
        """Save report to file when SMTP is unavailable."""
        from src.tools.report_tools import render_report, save_report_to_file

        # Save markdown version
        md_path = save_report_to_file(report_content, format="md")

        # Save HTML version
        html_content = render_report(
            report_content,
            context={
                "title": f"Satış Raporu — {start_date} / {end_date}",
                "period": f"{start_date} — {end_date}",
            },
        )
        html_path = save_report_to_file(html_content, format="html")

        return {
            "saved_files": [md_path, html_path],
            "reason": "Files saved as backup",
        }

    # ── HTML rendering helper ────────────────────────────────────────────────

    @staticmethod
    def _render_html(report_markdown: str, start_date: str, end_date: str) -> str:
        """Render markdown report to HTML for email body."""
        from src.tools.report_tools import render_report

        return render_report(
            report_markdown,
            context={
                "title": f"Satış Raporu — {start_date} / {end_date}",
                "period": f"{start_date} — {end_date}",
            },
        )
