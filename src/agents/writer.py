"""Writer Agent — stub for Week 1. Full implementation in Week 3."""
from __future__ import annotations
import logging
from src.graph.state import AgentState

logger = logging.getLogger(__name__)


class WriterAgent:
    """Generates executive summary reports (Week 3 implementation)."""

    def write(self, state: AgentState) -> AgentState:
        logger.info("WriterAgent: stub — passing state through")
        return {**state, "current_agent": "writer", "draft_report": ""}
