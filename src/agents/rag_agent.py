"""RAG Agent — stub for Week 1. Full implementation in Week 3."""
from __future__ import annotations
import logging
from src.graph.state import AgentState

logger = logging.getLogger(__name__)


class RAGAgent:
    """Retrieves historical report context from ChromaDB (Week 3 implementation)."""

    def retrieve(self, state: AgentState) -> AgentState:
        logger.info("RAGAgent: stub — passing state through")
        return {**state, "current_agent": "rag", "historical_context": ""}
