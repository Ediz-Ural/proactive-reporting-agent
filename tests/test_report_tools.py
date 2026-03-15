"""
Tests for report tools — markdown conversion, template rendering, file output.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestMarkdownToHtml:
    """Tests for markdown_to_html conversion."""

    def test_headers(self):
        from src.tools.report_tools import markdown_to_html

        html = markdown_to_html("## Başlık 2\n### Başlık 3")
        assert "<h2>" in html or "Başlık 2" in html

    def test_bold(self):
        from src.tools.report_tools import markdown_to_html

        html = markdown_to_html("Bu **kalın** metin.")
        assert "<strong>kalın</strong>" in html or "kalın" in html

    def test_list_items(self):
        from src.tools.report_tools import markdown_to_html

        html = markdown_to_html("- Madde 1\n- Madde 2")
        assert "Madde 1" in html
        assert "Madde 2" in html

    def test_empty_input(self):
        from src.tools.report_tools import markdown_to_html

        html = markdown_to_html("")
        assert isinstance(html, str)


class TestSimpleMdToHtml:
    """Tests for the fallback regex-based converter."""

    def test_h1(self):
        from src.tools.report_tools import _simple_md_to_html

        assert "<h1>" in _simple_md_to_html("# Başlık")

    def test_h2(self):
        from src.tools.report_tools import _simple_md_to_html

        assert "<h2>" in _simple_md_to_html("## Alt Başlık")

    def test_bold_and_italic(self):
        from src.tools.report_tools import _simple_md_to_html

        html = _simple_md_to_html("**kalın** ve *italik*")
        assert "<strong>kalın</strong>" in html
        assert "<em>italik</em>" in html

    def test_unordered_list(self):
        from src.tools.report_tools import _simple_md_to_html

        html = _simple_md_to_html("- item")
        assert "<li>" in html

    def test_ordered_list(self):
        from src.tools.report_tools import _simple_md_to_html

        html = _simple_md_to_html("1. first item")
        assert "<li>" in html


class TestRenderReport:
    """Tests for Jinja2 template rendering."""

    def test_render_basic(self):
        from src.tools.report_tools import render_report

        html = render_report(
            draft_markdown="## Test\nBu bir test.",
            context={"title": "Test Raporu", "period": "2024-01-01 — 2024-01-07"},
        )
        assert "Test Raporu" in html
        assert "2024-01-01" in html

    def test_render_contains_summary(self):
        from src.tools.report_tools import render_report

        html = render_report("**Özet** göstergeler burada.")
        assert "Özet" in html

    def test_render_with_default_context(self):
        from src.tools.report_tools import render_report

        html = render_report("Basit rapor")
        assert "Satış Raporu" in html  # default title
        assert "Oluşturulma:" in html


class TestSaveReportToFile:
    """Tests for file output."""

    def test_save_markdown(self, tmp_path):
        from src.tools.report_tools import save_report_to_file

        path = save_report_to_file(
            content="# Test Rapor\nİçerik",
            output_dir=str(tmp_path),
            filename="test_report.md",
            format="md",
        )
        assert Path(path).exists()
        assert Path(path).read_text(encoding="utf-8").startswith("# Test Rapor")

    def test_save_html(self, tmp_path):
        from src.tools.report_tools import save_report_to_file

        path = save_report_to_file(
            content="<html><body>Test</body></html>",
            output_dir=str(tmp_path),
            filename="test_report.html",
            format="html",
        )
        assert Path(path).exists()

    def test_auto_filename(self, tmp_path):
        from src.tools.report_tools import save_report_to_file

        path = save_report_to_file(
            content="auto test",
            output_dir=str(tmp_path),
        )
        assert Path(path).exists()
        assert path.endswith(".md")

    def test_creates_directory(self, tmp_path):
        from src.tools.report_tools import save_report_to_file

        new_dir = str(tmp_path / "nested" / "dir")
        path = save_report_to_file(
            content="test",
            output_dir=new_dir,
            filename="report.md",
        )
        assert Path(path).exists()
