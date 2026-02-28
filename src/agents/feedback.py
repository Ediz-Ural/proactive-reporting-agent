"""Feedback Agent — stub for Week 1. Full implementation in Week 5."""
from __future__ import annotations
import logging
from src.graph.state import AgentState

logger = logging.getLogger(__name__)


class FeedbackAgent:
    """Collects open/click metrics and personalises future reports (Week 5 implementation)."""

    def collect(self, state: AgentState) -> AgentState:
        logger.info("FeedbackAgent: stub — no feedback collected")
        return {**state, "current_agent": "feedback", "feedback_metrics": {}}
