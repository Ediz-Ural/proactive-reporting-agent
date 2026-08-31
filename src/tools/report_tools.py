"""
Report generation tools — Jinja2 rendering, markdown conversion, file output.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from html import escape
from pathlib import Path

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"


def markdown_to_html(markdown_text: str) -> str:
    """
    Convert markdown text to HTML, escaping any raw HTML in the source.

    Report text comes from database rows and LLM output, neither of which is
    trusted, and the result is rendered in the dashboard — so markup embedded in
    the source is escaped rather than passed through. Markdown syntax itself is
    unaffected; only literal <, > and & become entities.

    Uses the `markdown` library if available, otherwise falls back
    to a simple regex-based conversion.
    """
    safe_text = escape(markdown_text or "", quote=False)

    try:
        import markdown

        return markdown.markdown(
            safe_text,
            extensions=["tables", "fenced_code"],
        )
    except ImportError:
        logger.debug("markdown library not available — using simple regex conversion")
        return _simple_md_to_html(safe_text)


def render_report(
    draft_markdown: str,
    template_name: str = "report_template.html",
    context: dict | None = None,
) -> str:
    """
    Render the draft report into final HTML using Jinja2 template.

    Args:
        draft_markdown: Markdown report from WriterAgent.
        template_name: Jinja2 template filename.
        context: Extra template variables.

    Returns:
        Rendered HTML string.
    """
    from jinja2 import Environment, FileSystemLoader
    from markupsafe import Markup

    context = context or {}

    # Escaped by markdown_to_html, so it is the one value allowed through as markup.
    summary_html = Markup(markdown_to_html(draft_markdown))

    template_dir = str(TEMPLATE_DIR)
    env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)

    try:
        template = env.get_template(template_name)
    except Exception as exc:
        logger.error("Failed to load template %s: %s", template_name, exc)
        return f"<html><body>{summary_html}</body></html>"

    rendered = template.render(
        title=context.get("title", "Tedarikçi Performans Raporu"),
        period=context.get("period", ""),
        summary_html=summary_html,
        generated_at=context.get("generated_at", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")),
    )

    return rendered


def save_report_to_file(
    content: str,
    output_dir: str = "data/reports",
    filename: str | None = None,
    format: str = "md",
) -> str:
    """
    Save report content to file.

    Args:
        content: Report text (markdown or HTML).
        output_dir: Target directory.
        filename: Custom filename. Auto-generated if None.
        format: File extension ("md" or "html").

    Returns:
        Path of saved file.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    if filename is None:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"report_{ts}.{format}"

    filepath = out_path / filename
    filepath.write_text(content, encoding="utf-8")
    logger.info("Report saved to %s", filepath)
    return str(filepath)


# ── Simple fallback MD→HTML ──────────────────────────────────────────────────

def _simple_md_to_html(text: str) -> str:
    """
    Minimal markdown-to-HTML converter (no external deps).

    Expects text whose HTML has already been escaped by `markdown_to_html`.
    """
    html = text

    # Headers
    html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)

    # Bold / italic
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)

    # Unordered list items
    html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)

    # Numbered list items
    html = re.sub(r"^\d+\. (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)

    # Paragraphs — wrap bare lines
    lines = html.split("\n")
    result = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("<"):
            result.append(f"<p>{stripped}</p>")
        else:
            result.append(line)

    return "\n".join(result)
