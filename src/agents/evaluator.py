"""Evaluator Agent — stub for Week 1. Full implementation in Week 4."""
from __future__ import annotations
import logging
from src.graph.state import AgentState

logger = logging.getLogger(__name__)


class EvaluatorAgent:
    """Scores report quality and decides approve/revise (Week 4 implementation)."""

    def evaluate(self, state: AgentState) -> AgentState:
        logger.info("EvaluatorAgent: stub — auto-approving")
        evaluation = {"approved": True, "overall_score": 1.0, "feedback": "stub"}
        return {**state, "current_agent": "evaluator", "evaluation": evaluation}
