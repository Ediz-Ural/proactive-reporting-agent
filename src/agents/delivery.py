"""Delivery Agent — stub for Week 1. Full implementation in Week 4."""
from __future__ import annotations
import logging
from src.graph.state import AgentState

logger = logging.getLogger(__name__)


class DeliveryAgent:
    """Sends reports via SMTP / WhatsApp (Week 4 implementation)."""

    def deliver(self, state: AgentState) -> AgentState:
        logger.info("DeliveryAgent: stub — no delivery performed")
        return {**state, "current_agent": "delivery", "delivery_status": {"sent": False}}
