"""
Orchestrator Agent — Week 5 implementation.

Coordinates the analysis pipeline by examining raw data and creating
an analysis plan. Supports both rule-based and LLM-based routing.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.graph.state import AgentState

logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """
    Coordinates the analysis pipeline.

    Modes:
    - Rule-based (default): Deterministic routing based on data characteristics.
    - LLM-based (use_llm=True): LLM examines data summary and decides analyses.
      Falls back to rule-based if LLM is unavailable or returns invalid output.
    """

    def __init__(self, use_llm: bool = False):
        self.use_llm = use_llm

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
        logger.info("OrchestratorAgent: creating analysis plan (use_llm=%s)", self.use_llm)

        raw_data: dict[str, Any] = state.get("raw_data") or {}

        if self.use_llm:
            analysis_plan = self._llm_plan(raw_data)
            if analysis_plan is not None:
                logger.info("Analysis plan (LLM): %s", analysis_plan)
                return {
                    "analysis_plan": analysis_plan,
                    "current_agent": "orchestrator",
                }
            logger.info("LLM planning failed — falling back to rule-based")

        analysis_plan = self._rule_based_plan(raw_data)
        logger.info("Analysis plan (rule-based): %s", analysis_plan)

        return {
            "analysis_plan": analysis_plan,
            "current_agent": "orchestrator",
        }

    # ── Rule-based planning ──────────────────────────────────────────────────

    def _rule_based_plan(self, raw_data: dict[str, Any]) -> list[str]:
        """Deterministic analysis plan based on data characteristics."""
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

        # Sector comparison — always include for supplier benchmarking
        analysis_plan.append("sector_comparison")

        return analysis_plan

    # ── LLM-based planning ───────────────────────────────────────────────────

    AVAILABLE_ANALYSES = [
        "trends",
        "anomalies",
        "period_comparison",
        "category_performance",
        "forecast",
        "decomposition",
        "rfm_segments",
        "sector_comparison",
    ]

    LLM_SYSTEM_PROMPT = """Sen bir veri analisti koordinatörüsün.
Sana verilen veri özetine bakarak hangi analizlerin çalıştırılması gerektiğine karar ver.

MEVCUT ANALİZLER:
- trends: Satış trendlerini analiz eder
- anomalies: Anormal değerleri tespit eder
- period_comparison: Dönem karşılaştırması yapar
- category_performance: Kategori performansını analiz eder
- forecast: Gelecek tahminleri üretir (en az 14 günlük veri gerekir)
- decomposition: Zaman serisi ayrıştırması yapar (en az 14 günlük veri gerekir)
- rfm_segments: Müşteri segmentasyonu yapar (müşteri verisi gerekir)
- sector_comparison: Sektör karşılaştırması yapar (tedarikçi benchmarking)

KURALLAR:
- trends, anomalies, period_comparison, category_performance her zaman çalıştırılmalı
- forecast ve decomposition sadece yeterli veri varsa
- rfm_segments sadece müşteri verisi varsa
- sector_comparison her zaman çalıştırılmalı (tedarikçi kıyaslama)

JSON YANIT FORMATI (sadece analiz listesi):
["trends", "anomalies", "period_comparison", "category_performance", "forecast", "sector_comparison"]
"""

    def _llm_plan(self, raw_data: dict[str, Any]) -> list[str] | None:
        """
        Use LLM to decide which analyses to run.

        Returns None if LLM is unavailable or returns invalid output.
        """
        from src.tools.llm_tools import call_llm_with_retry

        # Build a concise data summary for the LLM
        daily_count = len(raw_data.get("daily_sales", []))
        has_customers = bool(raw_data.get("customer_metrics", []))
        categories = len(raw_data.get("by_category", []))

        summary = raw_data.get("weekly_summary", {})
        prompt = f"""VERİ ÖZETİ:
- Günlük veri noktası sayısı: {daily_count}
- Müşteri verisi mevcut: {"Evet" if has_customers else "Hayır"}
- Kategori sayısı: {categories}
- Toplam gelir: {summary.get('total_revenue', 'N/A')}
- Toplam sipariş: {summary.get('total_orders', 'N/A')}

Hangi analizler çalıştırılmalı? JSON listesi olarak yanıtla:"""

        response = call_llm_with_retry(
            prompt=prompt,
            system_prompt=self.LLM_SYSTEM_PROMPT,
            temperature=0.0,
        )

        if response is None:
            return None

        return self._parse_llm_plan(response)

    def _parse_llm_plan(self, response_text: str) -> list[str] | None:
        """Parse LLM response into a validated analysis plan."""
        import re

        # Strip markdown fences
        text = re.sub(r"```json\s*", "", response_text)
        text = re.sub(r"```\s*", "", text)
        text = text.strip()

        try:
            plan = json.loads(text)
        except (json.JSONDecodeError, ValueError, TypeError):
            logger.warning("OrchestratorAgent: failed to parse LLM plan as JSON")
            return None

        if not isinstance(plan, list):
            logger.warning("OrchestratorAgent: LLM plan is not a list")
            return None

        # Filter to valid analyses only
        valid = [a for a in plan if a in self.AVAILABLE_ANALYSES]

        # Core analyses must always be present
        core = ["trends", "anomalies", "period_comparison", "category_performance"]
        for analysis in core:
            if analysis not in valid:
                valid.insert(0, analysis)

        if not valid:
            return None

        return valid
