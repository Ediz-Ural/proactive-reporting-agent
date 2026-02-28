"""RAG tools — stub for Week 1. ChromaDB integration in Week 3."""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


def search_similar_reports(query: str, top_k: int = 5) -> list[dict]:
    """Search ChromaDB for historically similar report sections (Week 3)."""
    logger.debug("rag_tools.search_similar_reports: stub")
    return []


def store_report(report_id: str, content: str, metadata: dict | None = None) -> None:
    """Store a completed report in ChromaDB (Week 3)."""
    logger.debug("rag_tools.store_report: stub")
