"""
RAG Agent — Full implementation (Week 3, revised Week 6).

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

        # 1. General performance query
        queries.append("satış raporu gelir sipariş kâr performans")

        # 2. Anomaly query — collect anomalous columns
        anomalies = analysis_results.get("anomalies", [])
        if anomalies:
            anomaly_cols: set[str] = set()
            for a in anomalies[:3]:
                col = a.get("column", a.get("metric", ""))
                if col:
                    anomaly_cols.add(col.replace("total_", ""))
            if anomaly_cols:
                queries.append(f"anomali {' '.join(anomaly_cols)} beklenmedik değişim")

        # 3. Significant trend query (direction: "up" / "down")
        trends = analysis_results.get("trends", {})
        for metric, data in trends.items():
            if isinstance(data, dict):
                direction = data.get("direction", "stable")
                growth = abs(data.get("growth_rate_pct", 0))
                if direction in ("up", "down") and growth > 10:
                    label = "artış yükseliş" if direction == "up" else "düşüş azalma"
                    queries.append(f"{metric.replace('total_', '')} {label} trend")
                    break

        # 4. Period comparison — significant change
        comparison = analysis_results.get("period_comparison", {})
        sales_change = comparison.get("total_sales_change_pct", 0)
        if abs(sales_change) > 20:
            change_label = "düşüş gerileme" if sales_change < 0 else "artış büyüme"
            queries.append(f"satış {change_label} önceki dönem karşılaştırma")

        # 5. Loss-making categories
        cat_perf = analysis_results.get("category_performance", [])
        loss_cats = [
            c.get("sub_category", c.get("category", ""))
            for c in cat_perf
            if isinstance(c, dict) and c.get("profit_margin_pct", 0) < 0
        ]
        if loss_cats:
            queries.append(f"{' '.join(loss_cats[:2])} zarar negatif kâr marjı")

        return queries

    # ── Formatting ───────────────────────────────────────────────────────────

    def _format_context(self, chunks: list[dict[str, Any]]) -> str:
        """Format retrieved chunks into structured context for the Writer Agent."""
        if not chunks:
            return ""

        lines = ["## Geçmiş Rapor Bağlamı", ""]

        for i, chunk in enumerate(chunks[:6], 1):
            meta = chunk.get("metadata", {})
            content = chunk.get("content", "")
            distance = chunk.get("distance", 0)

            # Period info
            period_start = meta.get("period_start", "")
            period_end = meta.get("period_end", "")
            report_type = meta.get("report_type", "")
            quality = meta.get("quality_score", "")

            if period_start and period_end:
                period_label = f"{period_start} — {period_end}"
            else:
                period_label = "Tarih bilgisi yok"

            relevance = (
                "Yüksek" if distance < 0.5 else ("Orta" if distance < 1.0 else "Düşük")
            )

            lines.append(f"### Geçmiş Rapor #{i} ({period_label})")
            lines.append(f"*Tip: {report_type} | Benzerlik: {relevance}*")
            lines.append("")
            lines.append(content)
            lines.append("")

        lines.append("---")
        lines.append(
            f"*{len(chunks)} geçmiş rapor bölümünden derlenmiştir. "
            f"Bu bağlamı kullanarak dönemler arası karşılaştırma ve tutarlı öneriler üret.*"
        )

        return "\n".join(lines)
