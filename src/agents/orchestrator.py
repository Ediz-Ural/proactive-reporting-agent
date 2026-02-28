"""Orchestrator Agent — stub for Week 1. Full implementation in Week 2."""
from __future__ import annotations
import logging
from src.graph.state import AgentState

logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """Routes and coordinates all downstream agents (Week 2 implementation)."""

    def run(self, state: AgentState) -> AgentState:
        logger.info("OrchestratorAgent: stub — passing state through")
        return {**state, "current_agent": "orchestrator"}
