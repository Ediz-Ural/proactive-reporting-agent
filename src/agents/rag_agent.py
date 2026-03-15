"""
RAG Agent — Full implementation (Week 3).

Retrieves relevant historical report context from ChromaDB
to help the Writer Agent produce contextually rich reports.
"""

from __future__ import annotations

import logging
from typing import Any

from src.graph.state import AgentState

logger = logging.getLogger(__name__)


class RAGAgent:
    """
    Retrieves historical context from the vector store.

    The agent:
    1. Takes the current analysis results
    2. Formulates search queries based on key findings
    3. Retrieves relevant past report chunks
    4. Formats the context for the Writer Agent
    """

    def __init__(self, persist_dir: str = "data/chroma"):
        self._persist_dir = persist_dir

    def retrieve(self, state: AgentState) -> dict:
        """
        Search historical reports for relevant context.

        Reads from state: analysis_results, start_date, end_date, report_type
        Writes to state: historical_context, current_agent

        Returns:
            Dict of state updates.
        """
        logger.info("RAGAgent: starting retrieval")

        try:
            from src.tools.rag_tools import ReportVectorStore

            store = ReportVectorStore(
                persist_dir=self._persist_dir,
                collection_name="reports",
            )
        except Exception as exc:
            logger.warning("RAGAgent: ChromaDB unavailable — %s", exc)
            return {"current_agent": "rag", "historical_context": ""}

        stats = store.get_collection_stats()
        if stats["total_chunks"] == 0:
            logger.info("RAGAgent: collection is empty — skipping retrieval")
            return {"current_agent": "rag", "historical_context": ""}

        analysis_results = state.get("analysis_results") or {}
        start_date = state.get("start_date", "")
        end_date = state.get("end_date", "")
        report_type = state.get("report_type", "weekly")

        queries = self._build_queries(analysis_results, start_date, end_date, report_type)

        # Execute all queries and collect unique chunks
        seen_ids: set[str] = set()
        all_chunks: list[dict[str, Any]] = []

        for query in queries:
            results = store.search(query=query, top_k=3)
            for r in results:
                chunk_id = r["metadata"].get("report_id", "") + str(
                    r["metadata"].get("chunk_index", "")
                )
                if chunk_id not in seen_ids:
                    seen_ids.add(chunk_id)
                    all_chunks.append(r)

        # Sort by relevance (lower distance = more relevant)
        all_chunks.sort(key=lambda c: c.get("distance", 999))

        # Format context
        context = self._format_context(all_chunks)

        logger.info(
            "RAGAgent: retrieved %d unique chunks from %d queries",
            len(all_chunks),
            len(queries),
        )

        return {"current_agent": "rag", "historical_context": context}

    # ── Query building ───────────────────────────────────────────────────────

    def _build_queries(
        self,
        analysis_results: dict[str, Any],
        start_date: str,
        end_date: str,
        report_type: str,
    ) -> list[str]:
        """Build multiple search queries based on analysis results."""
        queries = []

        # 1. General period query
        type_label = {
            "weekly": "Haftalık",
            "monthly": "Aylık",
            "quarterly": "Çeyreklik",
        }.get(report_type, "Haftalık")
        queries.append(f"{type_label} satış raporu {start_date} {end_date}")

        # 2. Anomaly query
        anomalies = analysis_results.get("anomalies", [])
        if anomalies:
            # Pick the first anomaly's category or metric
            first = anomalies[0] if isinstance(anomalies, list) and anomalies else {}
            cat = first.get("category", first.get("metric", "satış"))
            queries.append(f"satış düşüşü anomali {cat}")

        # 3. Trend query
        trends = analysis_results.get("trends", {})
        if isinstance(trends, dict):
            for metric, trend_data in trends.items():
                if isinstance(trend_data, dict):
                    direction = trend_data.get("direction", "")
                    if direction in ("increasing", "decreasing"):
                        tr_label = "artış" if direction == "increasing" else "düşüş"
                        queries.append(f"{metric} satış trendi {tr_label}")
                        break  # One trend query is enough

        # 4. Category query
        cat_perf = analysis_results.get("category_performance", [])
        if cat_perf and isinstance(cat_perf, list):
            # Best performing category
            best = cat_perf[0] if cat_perf else {}
            cat_name = best.get("category", "")
            if cat_name:
                queries.append(f"{cat_name} performansı satış gelir")

        return queries

    # ── Formatting ───────────────────────────────────────────────────────────

    def _format_context(self, chunks: list[dict[str, Any]]) -> str:
        """Format retrieved chunks into a readable context string."""
        if not chunks:
            return ""

        lines = ["## Geçmiş Rapor Bağlamı", ""]

        # Group: similar period reports vs anomaly/trend history
        period_chunks = []
        other_chunks = []

        for c in chunks:
            meta = c.get("metadata", {})
            if meta.get("report_type") == "weekly":
                period_chunks.append(c)
            else:
                other_chunks.append(c)

        # If all are weekly, split by index
        if not other_chunks and len(period_chunks) > 2:
            other_chunks = period_chunks[2:]
            period_chunks = period_chunks[:2]

        if period_chunks:
            lines.append("### Benzer Dönem Raporları")
            for c in period_chunks[:3]:
                meta = c.get("metadata", {})
                source = meta.get("report_id", "bilinmeyen")
                period = f"{meta.get('period_start', '?')} — {meta.get('period_end', '?')}"
                lines.append(f"[Kaynak: {source} | Dönem: {period}]")
                lines.append(c["content"])
                lines.append("")

        if other_chunks:
            lines.append("### İlgili Anomali/Trend Geçmişi")
            for c in other_chunks[:3]:
                meta = c.get("metadata", {})
                source = meta.get("report_id", "bilinmeyen")
                lines.append(f"[Kaynak: {source}]")
                lines.append(c["content"])
                lines.append("")

        total = len(period_chunks) + len(other_chunks)
        lines.append(f"Kaynak: {total} geçmiş rapor bölümünden derlenmiştir.")

        return "\n".join(lines)
