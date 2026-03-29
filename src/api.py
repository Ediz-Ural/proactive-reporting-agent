"""
FastAPI application — API for triggering and monitoring the reporting pipeline.

Week 6: Added CORS, /runs/latest, /runs/{run_id}, /run/sync, /reports,
         /reports/{filename}, /db/stats endpoints for React dashboard.
"""

import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
    version="0.6.0",
    lifespan=lifespan,
)

# ── CORS middleware ──────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


# ── Helper: read JSONL runs ──────────────────────────────────────────────────

METRICS_PATH = Path("data/metrics/pipeline_runs.jsonl")


def _read_all_runs() -> list[dict]:
    """Read all runs from the JSONL metrics file."""
    if not METRICS_PATH.exists():
        return []
    runs = []
    try:
        lines = METRICS_PATH.read_text(encoding="utf-8").strip().split("\n")
        for line in lines:
            if not line.strip():
                continue
            try:
                runs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except Exception:
        return []
    return runs


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


@app.post("/run/sync")
async def run_pipeline_sync(request: PipelineRequest):
    """
    Run the pipeline synchronously and return the full result.
    Used by the dashboard for live results.
    """
    from src.graph.workflow import run_pipeline

    state = run_pipeline(
        start_date=request.start_date,
        end_date=request.end_date,
        report_type=request.report_type,
        recipients=request.recipients,
    )

    return {
        "run_id": state.get("run_id"),
        "status": "completed",
        "weekly_summary": (state.get("raw_data") or {}).get("weekly_summary", {}),
        "analysis_results": state.get("analysis_results", {}),
        "draft_report": state.get("draft_report", ""),
        "evaluation": state.get("evaluation", {}),
        "delivery_status": state.get("delivery_status", {}),
        "errors": state.get("errors", []),
    }


# ── Health & monitoring ───────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check with database status."""
    from src.tools.sql_tools import test_db_connection
    from config.settings import settings

    db_status = test_db_connection()

    return {
        "status": "ok" if db_status["connected"] else "degraded",
        "version": "0.6.0",
        "database": db_status,
        "scheduler_enabled": settings.SCHEDULER_ENABLED,
    }


@app.get("/runs")
async def list_runs(limit: int = 20):
    """List recent pipeline runs from the JSONL metrics file."""
    all_runs = _read_all_runs()
    runs = list(reversed(all_runs))[:limit]
    return {"runs": runs, "total": len(runs)}


@app.get("/runs/latest")
async def get_latest_run():
    """Return the most recent pipeline run with report content if available."""
    all_runs = _read_all_runs()
    if not all_runs:
        raise HTTPException(status_code=404, detail="No pipeline runs found")

    latest = all_runs[-1]

    # Try to find the most recent report file
    report_content = None
    report_html = None
    reports_dir = Path("data/reports")
    if reports_dir.exists():
        md_files = sorted(reports_dir.glob("*.md"), reverse=True)
        if md_files:
            try:
                report_content = md_files[0].read_text(encoding="utf-8")
                html_file = md_files[0].with_suffix(".html")
                if html_file.exists():
                    report_html = html_file.read_text(encoding="utf-8")
            except Exception:
                pass

    return {
        "run": latest,
        "report_content": report_content,
        "report_html": report_html,
    }


@app.get("/runs/{run_id}")
async def get_run_detail(run_id: str):
    """Return details of a specific pipeline run by run_id."""
    all_runs = _read_all_runs()
    for run in all_runs:
        if run.get("run_id") == run_id:
            return {"run": run}
    raise HTTPException(status_code=404, detail=f"Run {run_id} not found")


# ── Reports endpoints ─────────────────────────────────────────────────────────

@app.get("/reports")
async def list_reports():
    """List report files in data/reports/."""
    reports_dir = Path("data/reports")
    if not reports_dir.exists():
        return {"reports": []}

    reports = []
    for f in sorted(reports_dir.glob("*.md"), reverse=True):
        html_file = f.with_suffix(".html")
        reports.append({
            "filename": f.name,
            "created_at": f.stat().st_mtime,
            "size_bytes": f.stat().st_size,
            "has_html": html_file.exists(),
        })
    return {"reports": reports}


@app.get("/reports/{filename}")
async def get_report(filename: str):
    """Return the content of a specific report file."""
    # Prevent path traversal
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    md_path = Path("data/reports") / filename
    if not md_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")

    content = md_path.read_text(encoding="utf-8")
    html_path = md_path.with_suffix(".html")
    html_content = html_path.read_text(encoding="utf-8") if html_path.exists() else None

    return {
        "filename": filename,
        "content_md": content,
        "content_html": html_content,
    }


# ── Database stats ────────────────────────────────────────────────────────────

@app.get("/db/stats")
async def db_stats():
    """Return database summary statistics."""
    from src.tools.sql_tools import execute_query

    try:
        total = execute_query("SELECT COUNT(*) as cnt FROM orders")
        date_range = execute_query(
            "SELECT MIN(order_date) as min_date, MAX(order_date) as max_date FROM orders"
        )
        categories = execute_query(
            "SELECT category, COUNT(*) as cnt FROM orders GROUP BY category"
        )

        return {
            "total_orders": int(total["cnt"].iloc[0]),
            "date_range": {
                "min": str(date_range["min_date"].iloc[0]),
                "max": str(date_range["max_date"].iloc[0]),
            },
            "categories": categories.to_dict("records"),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database query failed: {exc}")


# ── RAG stats ─────────────────────────────────────────────────────────────────

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
