"""
FastAPI application — API for triggering and monitoring the reporting pipeline.

Week 5: Added scheduler lifespan, /run/monthly, /runs, /rag/stats,
         enhanced /health with DB status.
"""

import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start scheduler on startup, shut down on exit."""
    from src.scheduler import start_scheduler

    scheduler = start_scheduler()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="Proactive Reporting Agent",
    version="0.5.0",
    lifespan=lifespan,
)


# ── Request / Response models ─────────────────────────────────────────────────

class PipelineRequest(BaseModel):
    start_date: str  # "2024-01-01"
    end_date: str  # "2024-01-31"
    report_type: str = "weekly"
    recipients: list[str] = []


class PipelineResponse(BaseModel):
    run_id: str
    status: str
    message: str


# ── Pipeline endpoints ────────────────────────────────────────────────────────

@app.post("/run", response_model=PipelineResponse)
async def run_pipeline_endpoint(
    request: PipelineRequest,
    background_tasks: BackgroundTasks,
):
    """Trigger the full reporting pipeline."""
    from src.graph.workflow import run_pipeline

    run_id = str(uuid.uuid4())

    background_tasks.add_task(
        run_pipeline,
        start_date=request.start_date,
        end_date=request.end_date,
        report_type=request.report_type,
        recipients=request.recipients,
    )

    return PipelineResponse(
        run_id=run_id,
        status="started",
        message=f"Pipeline started for {request.start_date} to {request.end_date}",
    )


@app.post("/run/monthly", response_model=PipelineResponse)
async def run_monthly_endpoint(background_tasks: BackgroundTasks):
    """Manually trigger the monthly report for the previous month."""
    from src.scheduler import get_previous_month_range
    from src.graph.workflow import run_pipeline_with_retry

    start_date, end_date = get_previous_month_range()
    run_id = str(uuid.uuid4())

    background_tasks.add_task(
        run_pipeline_with_retry,
        start_date=start_date,
        end_date=end_date,
        report_type="monthly",
    )

    return PipelineResponse(
        run_id=run_id,
        status="started",
        message=f"Monthly pipeline started for {start_date} to {end_date}",
    )


# ── Health & monitoring ───────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check with database status."""
    from src.tools.sql_tools import test_db_connection
    from config.settings import settings

    db_status = test_db_connection()

    return {
        "status": "ok" if db_status["connected"] else "degraded",
        "version": "0.5.0",
        "database": db_status,
        "scheduler_enabled": settings.SCHEDULER_ENABLED,
    }


@app.get("/runs")
async def list_runs(limit: int = 20):
    """List recent pipeline runs from the JSONL metrics file."""
    metrics_path = Path("data/metrics/pipeline_runs.jsonl")

    if not metrics_path.exists():
        return {"runs": [], "total": 0}

    runs = []
    try:
        lines = metrics_path.read_text(encoding="utf-8").strip().split("\n")
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                runs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if len(runs) >= limit:
                break
    except Exception:
        return {"runs": [], "total": 0, "error": "Failed to read metrics file"}

    return {"runs": runs, "total": len(runs)}


@app.get("/rag/stats")
async def rag_stats():
    """Return ChromaDB collection statistics."""
    try:
        from src.tools.rag_tools import ReportVectorStore

        store = ReportVectorStore()
        stats = store.get_collection_stats()
        return {"status": "ok", **stats}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
