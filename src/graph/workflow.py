"""
LangGraph workflow definition (Week 5 — production-ready).

All 9 nodes fully implemented. Monthly scheduler, retry mechanism,
WhatsApp delivery, LLM orchestrator, and auto-RAG storage added.

Pipeline:
    START → data_collector → data_quality → [quality gate]
              → orchestrator → analyst → rag → writer
              → evaluator → [eval loop ≤3] → delivery → feedback → END
"""

import uuid
from langgraph.graph import END, START, StateGraph

from src.graph.state import AgentState
from config.logging_config import get_logger

logger = get_logger(__name__)


# ── Routing functions ─────────────────────────────────────────────────────────

def route_after_quality(state: AgentState) -> str:
    """Abort the pipeline if data quality is critically bad."""
    qr = state.get("quality_report") or {}
    if not qr.get("is_valid", True) and qr.get("errors"):
        logger.warning("Data quality check FAILED — aborting pipeline")
        return "end_with_error"
    return "orchestrator"


def route_after_evaluator(state: AgentState) -> str:
    """Re-run the writer if the report score is below threshold."""
    from config.settings import settings

    evaluation = state.get("evaluation") or {}
    iteration = state.get("evaluator_iteration", 0)

    if evaluation.get("approved", True):
        return "delivery"
    if iteration >= settings.MAX_EVALUATOR_ITERATIONS:
        logger.warning("Max evaluator iterations reached — accepting current draft")
        return "delivery"
    return "writer"


# ── Node functions (lazy imports to avoid circular imports) ───────────────────

def data_collector_node(state: AgentState) -> dict:
    """Run the Data Collector Agent to fetch raw data."""
    from src.agents.data_collector import DataCollectorAgent

    agent = DataCollectorAgent()
    result = agent.collect(state["start_date"], state["end_date"])
    return {"raw_data": result, "current_agent": "data_collector"}


def data_quality_node(state: AgentState) -> dict:
    from src.agents.data_quality import DataQualityAgent

    agent = DataQualityAgent()
    raw_data = state.get("raw_data") or {}
    report = agent.validate(raw_data)
    return {"quality_report": report, "current_agent": "data_quality"}


def orchestrator_node(state: AgentState) -> dict:
    """Run the Orchestrator Agent to create an analysis plan."""
    from src.agents.orchestrator import OrchestratorAgent

    use_llm = state.get("use_llm_orchestrator", False)
    agent = OrchestratorAgent(use_llm=use_llm)
    return agent.plan(state)


def analyst_node(state: AgentState) -> dict:
    """Run the Analyst Agent to produce analysis results."""
    from src.agents.analyst import AnalystAgent

    agent = AnalystAgent()
    return agent.analyse(state)


def rag_node(state: AgentState) -> dict:
    """Run the RAG Agent to retrieve historical report context."""
    from src.agents.rag_agent import RAGAgent

    agent = RAGAgent()
    return agent.retrieve(state)


def writer_node(state: AgentState) -> dict:
    """Run the Writer Agent to generate the executive summary report."""
    from src.agents.writer import WriterAgent

    strategy = state.get("writer_strategy") or "few_shot"
    agent = WriterAgent(strategy=strategy)
    return agent.write(state)


def evaluator_node(state: AgentState) -> dict:
    """Run the Evaluator Agent to score the draft report."""
    from src.agents.evaluator import EvaluatorAgent

    agent = EvaluatorAgent()
    return agent.evaluate(state)


def delivery_node(state: AgentState) -> dict:
    """Run the Delivery Agent to send or save the final report."""
    from src.agents.delivery import DeliveryAgent

    agent = DeliveryAgent()
    return agent.deliver(state)


def feedback_node(state: AgentState) -> dict:
    """Run the Feedback Agent to record pipeline metrics."""
    from src.agents.feedback import FeedbackAgent

    agent = FeedbackAgent()
    return agent.collect(state)


# ── Graph construction ────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """Assemble and compile the full LangGraph DAG."""
    graph = StateGraph(AgentState)

    # Register nodes — all 9 are real implementations
    graph.add_node("data_collector", data_collector_node)
    graph.add_node("data_quality", data_quality_node)
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("rag", rag_node)
    graph.add_node("writer", writer_node)
    graph.add_node("evaluator", evaluator_node)
    graph.add_node("delivery", delivery_node)
    graph.add_node("feedback", feedback_node)

    # Linear edges
    graph.add_edge(START, "data_collector")
    graph.add_edge("data_collector", "data_quality")

    # Conditional: quality gate
    graph.add_conditional_edges(
        "data_quality",
        route_after_quality,
        {"orchestrator": "orchestrator", "end_with_error": END},
    )

    graph.add_edge("orchestrator", "analyst")
    graph.add_edge("analyst", "rag")
    graph.add_edge("rag", "writer")
    graph.add_edge("writer", "evaluator")

    # Conditional: evaluator loop
    graph.add_conditional_edges(
        "evaluator",
        route_after_evaluator,
        {"delivery": "delivery", "writer": "writer"},
    )

    graph.add_edge("delivery", "feedback")
    graph.add_edge("feedback", END)

    return graph.compile()


# ── Convenience runner ────────────────────────────────────────────────────────

def run_pipeline(
    start_date: str,
    end_date: str,
    report_type: str = "weekly",
    recipients: list[str] | None = None,
) -> AgentState:
    """
    Execute the full reporting pipeline.

    Args:
        start_date: ISO date string, e.g. "2024-01-01".
        end_date:   ISO date string, e.g. "2024-01-07".
        report_type: "weekly" | "monthly" | "quarterly".
        recipients: List of email addresses.

    Returns:
        Final AgentState after all nodes have executed.
    """
    graph = build_graph()

    initial_state: AgentState = {
        "start_date": start_date,
        "end_date": end_date,
        "report_type": report_type,
        "recipients": recipients or [],
        "raw_data": None,
        "quality_report": None,
        "analysis_results": None,
        "analysis_plan": None,
        "writer_strategy": None,
        "historical_context": None,
        "draft_report": None,
        "evaluation": None,
        "evaluator_iteration": 0,
        "final_report": None,
        "delivery_status": None,
        "feedback_metrics": None,
        "errors": [],
        "current_agent": "start",
        "run_id": str(uuid.uuid4()),
    }

    logger.info(
        "Starting pipeline | run_id=%s | period=%s → %s",
        initial_state["run_id"],
        start_date,
        end_date,
    )

    final_state = graph.invoke(initial_state)
    logger.info("Pipeline completed | run_id=%s", initial_state["run_id"])
    return final_state


# ── Retry wrapper ────────────────────────────────────────────────────────────

def run_pipeline_with_retry(
    start_date: str,
    end_date: str,
    report_type: str = "weekly",
    recipients: list[str] | None = None,
    max_retries: int = 2,
) -> AgentState:
    """
    Execute the pipeline with exponential backoff retry.

    Args:
        start_date: ISO date string.
        end_date:   ISO date string.
        report_type: Report type.
        recipients: Email addresses.
        max_retries: Number of retries after first failure.

    Returns:
        Final AgentState.

    Raises:
        RuntimeError: If all attempts fail.
    """
    import time

    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            state = run_pipeline(
                start_date=start_date,
                end_date=end_date,
                report_type=report_type,
                recipients=recipients,
            )
            return state
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                wait = 2 ** attempt  # 1s, 2s, 4s ...
                logger.warning(
                    "Pipeline attempt %d/%d failed: %s — retrying in %ds",
                    attempt + 1, max_retries + 1, exc, wait,
                )
                time.sleep(wait)
            else:
                logger.error(
                    "Pipeline failed after %d attempts: %s",
                    max_retries + 1, exc,
                )

    raise RuntimeError(f"Pipeline failed after {max_retries + 1} attempts: {last_exc}")
