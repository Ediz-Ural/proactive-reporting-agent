"""
Orchestrator Agent — Week 2 implementation.

Coordinates the analysis pipeline by examining raw data and creating
an analysis plan. Currently uses rule-based routing; LLM-based dynamic
routing will be added in Week 4+.
"""

from __future__ import annotations

import logging
from typing import Any

from src.graph.state import AgentState

logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """
    Coordinates the analysis pipeline.

    Week 2: Rule-based routing (deterministic).
    Week 4+: LLM-based dynamic routing.
    """

    def plan(self, state: AgentState) -> dict:
        """
        Examine the raw_data and create an analysis plan.

        Reads from state: raw_data
        Writes to state: analysis_plan, current_agent

        Returns:
            Dict with state updates:
            - analysis_plan: list of analyses to run
            - current_agent: "orchestrator"
        """
        logger.info("OrchestratorAgent: creating analysis plan")

        raw_data: dict[str, Any] = state.get("raw_data") or {}
        analysis_plan: list[str] = []

        # Always run these core analyses
        analysis_plan.extend([
            "trends",
            "anomalies",
            "period_comparison",
            "category_performance",
        ])

        # Forecast & decomposition require sufficient daily data (>= 14 days)
        daily_sales = raw_data.get("daily_sales", [])
        if len(daily_sales) >= 14:
            analysis_plan.append("forecast")
            analysis_plan.append("decomposition")
        else:
            logger.info(
                "Skipping forecast/decomposition: only %d daily data points (need 14)",
                len(daily_sales),
            )

        # RFM segmentation requires customer data
        customer_metrics = raw_data.get("customer_metrics", [])
        if customer_metrics:
            analysis_plan.append("rfm_segments")
        else:
            logger.info("Skipping RFM segmentation: no customer metrics available")

        logger.info("Analysis plan: %s", analysis_plan)

        return {
            "analysis_plan": analysis_plan,
            "current_agent": "orchestrator",
        }
