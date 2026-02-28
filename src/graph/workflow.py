"""
LangGraph workflow definition (skeleton for Week 1).

The graph wires together all 9 agents. In Week 1 only the data_collector
and data_quality nodes have real implementations; the rest are stubs that
pass state through unchanged.

Full pipeline:
    START
      └─► orchestrator
            └─► data_collector
                  └─► data_quality ──► [invalid?] ──► END (error)
                        └─► analyst
                              └─► rag
                                    └─► writer
                                          └─► evaluator ──► [score low?] ──► writer
                                                └─► delivery
                                                      └─► feedback
                                                            └─► END
"""

import uuid
from datetime import date
from langgraph.graph import END, START, StateGraph

from src.graph.state import AgentState
from config.logging_config import get_logger

logger = get_logger(__name__)


# ── Stub node helpers ─────────────────────────────────────────────────────────

def _stub(name: str):
    """Return a pass-through node function for not-yet-implemented agents."""

    def node(state: AgentState) -> dict:
        logger.debug("Stub node reached: %s", name)
        return {"current_agent": name}

    node.__name__ = name
    return node


# ── Routing functions ─────────────────────────────────────────────────────────

def route_after_quality(state: AgentState) -> str:
    """Abort the pipeline if data quality is critically bad."""
    qr = state.get("quality_report") or {}
    if not qr.get("is_valid", True) and qr.get("errors"):
        logger.warning("Data quality check FAILED — aborting pipeline")
        return "end_with_error"
    return "analyst"


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


# ── Real node imports (lazy, to avoid circular imports) ───────────────────────

def data_collector_node(state: AgentState) -> dict:
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


# ── Graph construction ────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """Assemble and compile the full LangGraph DAG."""
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("orchestrator", _stub("orchestrator"))
    graph.add_node("data_collector", data_collector_node)
    graph.add_node("data_quality", data_quality_node)
    graph.add_node("analyst", _stub("analyst"))
    graph.add_node("rag", _stub("rag"))
    graph.add_node("writer", _stub("writer"))
    graph.add_node("evaluator", _stub("evaluator"))
    graph.add_node("delivery", _stub("delivery"))
    graph.add_node("feedback", _stub("feedback"))

    # Linear edges
    graph.add_edge(START, "orchestrator")
    graph.add_edge("orchestrator", "data_collector")
    graph.add_edge("data_collector", "data_quality")

    # Conditional: quality gate
    graph.add_conditional_edges(
        "data_quality",
        route_after_quality,
        {"analyst": "analyst", "end_with_error": END},
    )

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
