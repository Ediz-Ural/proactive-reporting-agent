"""Report generation tools — stub for Week 1. Jinja2 rendering in Week 3."""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


def render_html_report(context: dict) -> str:
    """Render the Jinja2 HTML report template (Week 3)."""
    logger.debug("report_tools.render_html_report: stub")
    return "<html><body>Report stub</body></html>"


def export_docx(html_content: str, output_path: str) -> str:
    """Export HTML report to .docx format (Week 3)."""
    logger.debug("report_tools.export_docx: stub")
    return output_path
