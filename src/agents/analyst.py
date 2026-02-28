"""Analyst Agent — stub for Week 1. Full implementation in Week 2."""
from __future__ import annotations
import logging
from src.graph.state import AgentState

logger = logging.getLogger(__name__)


class AnalystAgent:
    """Runs trend, anomaly, and forecasting analysis (Week 2 implementation)."""

    def analyse(self, state: AgentState) -> AgentState:
        logger.info("AnalystAgent: stub — passing state through")
        return {**state, "current_agent": "analyst"}
