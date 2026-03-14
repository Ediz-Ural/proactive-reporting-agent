"""
LangGraph shared state definition.

All agents in the pipeline read from and write to this TypedDict.
Keys follow the pipeline order: input → collect → quality → analyse → rag
→ write → evaluate → deliver → feedback.
"""

from typing import Annotated, Optional, TypedDict
import operator


class AgentState(TypedDict):
    # ── Pipeline input ────────────────────────────────────────────────────────
    start_date: str           # ISO format: "2024-01-01"
    end_date: str             # ISO format: "2024-01-07"
    report_type: str          # "weekly" | "monthly" | "quarterly"
    recipients: list[str]     # destination email addresses

    # ── Data Collector output ─────────────────────────────────────────────────
    raw_data: Optional[dict]
    # {
    #   "period": {...},
    #   "by_category": <serialised DataFrame>,
    #   "top_products": <serialised DataFrame>,
    #   "customer_metrics": <serialised DataFrame>,
    #   "weekly_summary": {...}
    # }

    # ── Data Quality output ───────────────────────────────────────────────────
    quality_report: Optional[dict]
    # DataQualityReport serialised to dict

    # ── Analyst output ────────────────────────────────────────────────────────
    analysis_results: Optional[dict]
    # AnalysisResult serialised to dict

    # ── RAG output ────────────────────────────────────────────────────────────
    historical_context: Optional[str]
    # Relevant excerpts from past reports (plain text / markdown)

    # ── Writer output ─────────────────────────────────────────────────────────
    draft_report: Optional[str]
    # Markdown / HTML report draft

    # ── Evaluator output ──────────────────────────────────────────────────────
    evaluation: Optional[dict]
    # EvaluatorScore serialised to dict
    evaluator_iteration: int  # 0-based counter, max = settings.MAX_EVALUATOR_ITERATIONS

    # ── Final outputs ─────────────────────────────────────────────────────────
    final_report: Optional[str]
    delivery_status: Optional[dict]
    # {"sent_to": [...], "timestamp": "...", "message_id": "..."}

    # ── Feedback / personalisation ────────────────────────────────────────────
    feedback_metrics: Optional[dict]
    # {"opens": int, "clicks": int, "read_time_seconds": int}

    # ── Orchestrator output ──────────────────────────────────────────────────
    analysis_plan: Optional[list[str]]
    # e.g. ["trends", "anomalies", "forecast", "decomposition", "rfm_segments"]

    # ── Metadata ──────────────────────────────────────────────────────────────
    # Use Annotated + operator.add so multiple agents can append errors
    errors: Annotated[list[str], operator.add]
    current_agent: str
    run_id: str
