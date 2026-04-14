"""
Tests for RAG tools (ReportVectorStore) and RAG Agent.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── ReportVectorStore tests ──────────────────────────────────────────────────


class TestReportVectorStore:
    """Tests for ChromaDB vector store wrapper."""

    @pytest.fixture()
    def store(self, tmp_path):
        from src.tools.rag_tools import ReportVectorStore

        return ReportVectorStore(
            persist_dir=str(tmp_path / "chroma"),
            collection_name="test_reports",
        )

    def test_init_creates_collection(self, store):
        stats = store.get_collection_stats()
        assert stats["total_chunks"] == 0
        assert stats["total_reports"] == 0

    def test_store_report_basic(self, store):
        n = store.store_report(
            report_id="rpt_001",
            content="Bu bir test raporu. Toplam gelir 10000 TL olarak kaydedildi.",
            metadata={"report_type": "weekly", "report_date": "2024-01-07"},
        )
        assert n >= 1
        stats = store.get_collection_stats()
        assert stats["total_chunks"] == n
        assert "rpt_001" in stats["report_ids"]

    def test_store_report_chunking(self, store):
        long_content = (
            "## Bölüm Bir\n"
            + "Satır bir içerik.\n" * 30
            + "## Bölüm İki\n"
            + "Satır iki içerik.\n" * 30
            + "## Bölüm Üç\n"
            + "Satır üç içerik.\n" * 30
        )
        n = store.store_report(
            report_id="rpt_long",
            content=long_content,
            chunk_size=200,
        )
        assert n > 1

    def test_store_report_empty_content(self, store):
        n = store.store_report(report_id="rpt_empty", content="")
        assert n == 0

    def test_search_returns_results(self, store):
        store.store_report(
            report_id="rpt_search",
            content="Teknoloji kategorisinde satışlar %15 arttı. Mobilya kategorisi stabil.",
            metadata={"report_type": "weekly"},
        )
        results = store.search("teknoloji satış artışı", top_k=3)
        assert len(results) >= 1
        assert "content" in results[0]
        assert "metadata" in results[0]
        assert "distance" in results[0]

    def test_search_empty_collection(self, store):
        results = store.search("herhangi bir sorgu", top_k=5)
        assert results == []

    def test_search_with_metadata_filter(self, store):
        store.store_report(
            report_id="rpt_w",
            content="Haftalık rapor verisi burada.",
            metadata={"report_type": "weekly"},
        )
        store.store_report(
            report_id="rpt_m",
            content="Aylık rapor verisi burada.",
            metadata={"report_type": "monthly"},
        )
        results = store.search(
            "rapor",
            top_k=5,
            where={"report_type": "weekly"},
        )
        for r in results:
            assert r["metadata"]["report_type"] == "weekly"

    def test_get_collection_stats(self, store):
        store.store_report("rpt_a", "İçerik A", {"report_type": "weekly"})
        store.store_report("rpt_b", "İçerik B", {"report_type": "weekly"})
        stats = store.get_collection_stats()
        assert stats["total_reports"] == 2
        assert stats["total_chunks"] >= 2

    def test_upsert_overwrites(self, store):
        store.store_report("rpt_up", "Eski içerik")
        store.store_report("rpt_up", "Yeni içerik")
        stats = store.get_collection_stats()
        assert stats["total_reports"] == 1

    def test_clear_collection(self, store):
        store.store_report("rpt_c1", "## Bölüm\nİçerik bir burada.", {"report_type": "monthly"})
        store.store_report("rpt_c2", "## Bölüm\nİçerik iki burada.", {"report_type": "monthly"})
        assert store.get_collection_stats()["total_chunks"] >= 2
        store.clear_collection()
        assert store.get_collection_stats()["total_chunks"] == 0

    def test_split_by_sections(self, store):
        text = "## Başlık\nİçerik satırı 1\nİçerik satırı 2\n### Alt Bölüm\nAlt içerik burada."
        chunks = store._split_by_sections(text, max_chunk_size=2000)
        assert len(chunks) >= 2
        assert chunks[0].startswith("## Başlık")
        assert chunks[1].startswith("### Alt Bölüm")

    def test_split_by_sections_empty(self, store):
        assert store._split_by_sections("") == []
        assert store._split_by_sections("   ") == []

    def test_split_by_sections_no_headings_falls_back(self, store):
        text = "Paragraf bir.\n\nParagraf iki.\n\nParagraf üç."
        chunks = store._split_by_sections(text, max_chunk_size=2000)
        assert len(chunks) >= 1

    def test_split_by_sections_long_section(self, store):
        text = "## Uzun Bölüm\n" + ("Bu bir test cümlesidir.\n" * 50)
        chunks = store._split_by_sections(text, max_chunk_size=200)
        assert len(chunks) >= 2

    def test_split_text_legacy(self, store):
        chunks = store._split_text("abcdefghij", chunk_size=5, chunk_overlap=2)
        assert len(chunks) >= 2
        assert chunks[0] == "abcde"

    def test_split_text_empty(self, store):
        assert store._split_text("") == []


# ── RAGAgent tests ───────────────────────────────────────────────────────────


class TestRAGAgent:
    """Tests for RAG Agent retrieve() method."""

    @pytest.fixture()
    def populated_store_dir(self, tmp_path):
        """Create a ChromaDB store with some test data."""
        from src.tools.rag_tools import ReportVectorStore

        store = ReportVectorStore(
            persist_dir=str(tmp_path / "chroma"),
            collection_name="reports",
        )
        store.store_report(
            report_id="rpt_hist_01",
            content=(
                "Haftalık satış raporu. Technology kategorisi %12 büyüme kaydetti. "
                "Anomali: 15 Ocak'ta beklenmedik düşüş. Toplam gelir 45000 TL."
            ),
            metadata={
                "report_type": "weekly",
                "report_date": "2024-01-21",
                "period_start": "2024-01-15",
                "period_end": "2024-01-21",
            },
        )
        return str(tmp_path / "chroma")

    def _make_state(self, **overrides):
        """Create a minimal AgentState dict."""
        state = {
            "start_date": "2024-01-22",
            "end_date": "2024-01-28",
            "report_type": "weekly",
            "recipients": [],
            "raw_data": None,
            "quality_report": None,
            "analysis_results": {
                "trends": {
                    "total_sales": {"direction": "up", "growth_rate_pct": 15.0}
                },
                "anomalies": [{"column": "total_sales", "date": "2024-01-25"}],
                "category_performance": [{"category": "Technology", "total_sales": 20000}],
            },
            "analysis_plan": None,
            "writer_strategy": None,
            "historical_context": None,
            "draft_report": None,
            "evaluation": None,
            "evaluator_iteration": 0,
            "final_report": None,
            "delivery_status": None,
            "feedback_metrics": None,
            "errors": [],
            "current_agent": "analyst",
            "run_id": "test-run",
        }
        state.update(overrides)
        return state

    def test_retrieve_with_data(self, populated_store_dir):
        from src.agents.rag_agent import RAGAgent

        agent = RAGAgent(persist_dir=populated_store_dir)
        state = self._make_state()
        result = agent.retrieve(state)

        assert result["current_agent"] == "rag"
        assert isinstance(result["historical_context"], str)
        assert len(result["historical_context"]) > 0

    def test_retrieve_empty_collection(self, tmp_path):
        from src.agents.rag_agent import RAGAgent

        agent = RAGAgent(persist_dir=str(tmp_path / "empty_chroma"))
        state = self._make_state()
        result = agent.retrieve(state)

        assert result["current_agent"] == "rag"
        assert result["historical_context"] == ""

    def test_retrieve_no_analysis_results(self, populated_store_dir):
        from src.agents.rag_agent import RAGAgent

        agent = RAGAgent(persist_dir=populated_store_dir)
        state = self._make_state(analysis_results={})
        result = agent.retrieve(state)

        assert result["current_agent"] == "rag"
        # Should still return something from the general query
        assert isinstance(result["historical_context"], str)

    def test_retrieve_chromadb_failure_graceful(self):
        """If ChromaDB fails to initialize, agent returns empty context."""
        from src.agents.rag_agent import RAGAgent

        agent = RAGAgent(persist_dir="/nonexistent/path/that/should/fail")
        state = self._make_state()

        # This may or may not fail depending on ChromaDB version/permissions
        # but the agent should handle it gracefully
        result = agent.retrieve(state)
        assert result["current_agent"] == "rag"
        assert isinstance(result["historical_context"], str)

    def test_build_queries(self, populated_store_dir):
        from src.agents.rag_agent import RAGAgent

        agent = RAGAgent(persist_dir=populated_store_dir)
        queries = agent._build_queries(
            analysis_results={
                "trends": {"total_sales": {"direction": "up", "growth_rate_pct": 15.0}},
                "anomalies": [{"column": "total_sales"}],
                "category_performance": [
                    {"category": "Technology", "profit_margin_pct": 10}
                ],
            },
            start_date="2024-01-22",
            end_date="2024-01-28",
            report_type="weekly",
        )
        assert len(queries) >= 2  # At least general + anomaly/trend
        assert any("satış raporu" in q for q in queries)

    def test_build_queries_with_losses(self, populated_store_dir):
        from src.agents.rag_agent import RAGAgent

        agent = RAGAgent(persist_dir=populated_store_dir)
        queries = agent._build_queries(
            analysis_results={
                "trends": {},
                "anomalies": [],
                "category_performance": [
                    {"sub_category": "Tables", "profit_margin_pct": -5}
                ],
            },
            start_date="2024-01-22",
            end_date="2024-01-28",
            report_type="weekly",
        )
        assert any("zarar" in q for q in queries)

    def test_temporal_filtering_excludes_future_reports(self, tmp_path):
        """RAG Agent should only pull reports with period_end < current start_date."""
        from src.agents.rag_agent import RAGAgent
        from src.tools.rag_tools import ReportVectorStore

        persist_dir = str(tmp_path / "chroma_temporal")
        store = ReportVectorStore(persist_dir=persist_dir, collection_name="reports")

        store.store_report(
            report_id="rpt_2014_dec",
            content=(
                "## Aralık 2014 Aylık Rapor\n"
                "Toplam gelir 40000 TL. Technology kategorisi güçlü performans gösterdi. "
                "Önceki aya göre %8 büyüme kaydedildi."
            ),
            metadata={
                "report_type": "monthly",
                "period_start": "2014-12-01",
                "period_end": "2014-12-31",
            },
        )
        store.store_report(
            report_id="rpt_2015_jan",
            content=(
                "## Ocak 2015 Aylık Rapor\n"
                "Ocak ayı satışları stabil. Mobilya kategorisi zayıf kaldı. "
                "Toplam gelir 38000 TL olarak gerçekleşti."
            ),
            metadata={
                "report_type": "monthly",
                "period_start": "2015-01-01",
                "period_end": "2015-01-31",
            },
        )
        store.store_report(
            report_id="rpt_2017_jan",
            content=(
                "## Ocak 2017 Aylık Rapor\n"
                "2017 yılı güçlü başladı. Teknoloji segmentinde %20 büyüme. "
                "Toplam gelir 55000 TL."
            ),
            metadata={
                "report_type": "monthly",
                "period_start": "2017-01-01",
                "period_end": "2017-01-31",
            },
        )

        agent = RAGAgent(persist_dir=persist_dir)
        state = self._make_state(
            start_date="2015-01-01",
            end_date="2015-01-31",
            report_type="monthly",
        )
        result = agent.retrieve(state)
        context = result["historical_context"]

        assert "2014-12-31" in context
        assert "2015-01-31" not in context
        assert "2017-01-31" not in context

    def test_temporal_filtering_empty_when_no_prior_reports(self, tmp_path):
        """If only future reports exist, historical_context should be empty."""
        from src.agents.rag_agent import RAGAgent
        from src.tools.rag_tools import ReportVectorStore

        persist_dir = str(tmp_path / "chroma_future_only")
        store = ReportVectorStore(persist_dir=persist_dir, collection_name="reports")
        store.store_report(
            report_id="rpt_future",
            content="## Gelecek Rapor\nBu rapor gelecekten geldi. Toplam gelir 50000 TL.",
            metadata={
                "report_type": "monthly",
                "period_start": "2017-01-01",
                "period_end": "2017-01-31",
            },
        )

        agent = RAGAgent(persist_dir=persist_dir)
        state = self._make_state(
            start_date="2014-01-01",
            end_date="2014-01-31",
            report_type="monthly",
        )
        result = agent.retrieve(state)
        assert result["historical_context"] == ""

    def test_build_queries_minimal(self, populated_store_dir):
        from src.agents.rag_agent import RAGAgent

        agent = RAGAgent(persist_dir=populated_store_dir)
        queries = agent._build_queries(
            analysis_results={},
            start_date="2024-01-22",
            end_date="2024-01-28",
            report_type="weekly",
        )
        assert len(queries) >= 1  # At least the general query
        assert any("satış raporu" in q for q in queries)
