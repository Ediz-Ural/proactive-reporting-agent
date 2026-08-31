"""
FastAPI application — API for triggering and monitoring the reporting pipeline.

v0.7.0: JWT authentication, multi-tenant company isolation, admin panel endpoints.
"""

import io
import json
import uuid
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

import pandas as pd
from fastapi import BackgroundTasks, Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import text

from src.auth import (
    TokenData,
    authenticate_user,
    create_access_token,
    get_current_user,
    hash_password,
    require_admin,
)


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
    version="0.7.0",
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


# ── Security headers ─────────────────────────────────────────────────────────

# The interactive docs load Swagger UI from a CDN, so they get their own policy;
# every other response is data and needs to load nothing at all.
_DOCS_PATHS = ("/docs", "/redoc", "/docs/oauth2-redirect")
_DOCS_CSP = (
    "default-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; "
    "script-src 'self' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' "
    "https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com"
)
_API_CSP = "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; sandbox"


@app.middleware("http")
async def security_headers(request, call_next):
    """
    Attach security headers to every response.

    Reports can carry markup that came from uploaded data, and browsers must
    never render an API response as a document: the sandbox CSP plus nosniff
    keeps a report body inert even if it is opened directly.
    """
    response = await call_next(request)

    is_docs = request.url.path in _DOCS_PATHS
    response.headers["Content-Security-Policy"] = _DOCS_CSP if is_docs else _API_CSP
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    return response


# ── Request / Response models ─────────────────────────────────────────────────

class PipelineRequest(BaseModel):
    start_date: str  # "2024-01-01"
    end_date: str  # "2024-01-31"
    report_type: str = "weekly"
    recipients: list[str] = []
    company_id: int | None = None  # admin can override


class PipelineResponse(BaseModel):
    run_id: str
    status: str
    message: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str
    company_id: int


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class CompanyCreate(BaseModel):
    name: str
    slug: str
    email_domain: str = ""
    segment: str


class AdminReportRequest(BaseModel):
    start_date: date
    end_date: date
    report_type: str = "monthly"
    company_id: int
    recipients: list[str] = []


class SendExistingReportRequest(BaseModel):
    report_filename: str
    company_id: int
    recipients: list[str] = []


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


# ══════════════════════════════════════════════════════════════════════════════
# AUTH ENDPOINTS (public — no token required)
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/auth/login", response_model=LoginResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login and get JWT token."""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(401, "Invalid email or password")

    token = create_access_token({
        "user_id": user["id"],
        "email": user["email"],
        "role": user["role"],
        "company_id": user["company_id"],
        "company_name": user["company_name"],
    })

    return LoginResponse(
        access_token=token,
        user={
            "id": user["id"],
            "email": user["email"],
            "full_name": user["full_name"],
            "role": user["role"],
            "company_id": user["company_id"],
            "company_name": user["company_name"],
        },
    )


@app.post("/auth/register")
async def register(req: RegisterRequest, admin: TokenData = Depends(require_admin)):
    """Register a new user (admin only)."""
    from src.tools.sql_tools import get_db_engine

    engine = get_db_engine()
    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": req.email},
        ).fetchone()
        if existing:
            raise HTTPException(400, "Email already registered")

        conn.execute(text("""
            INSERT INTO users (email, password_hash, full_name, role, company_id)
            VALUES (:email, :hash, :name, 'user', :cid)
        """), {
            "email": req.email,
            "hash": hash_password(req.password),
            "name": req.full_name,
            "cid": req.company_id,
        })

    return {"message": "User registered", "email": req.email}


@app.get("/auth/me")
async def get_me(current_user: TokenData = Depends(get_current_user)):
    """Get current user info."""
    return {
        "user_id": current_user.user_id,
        "email": current_user.email,
        "role": current_user.role,
        "company_id": current_user.company_id,
        "company_name": current_user.company_name,
    }


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE ENDPOINTS (authenticated)
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/run", response_model=PipelineResponse)
async def run_pipeline_endpoint(
    request: PipelineRequest,
    background_tasks: BackgroundTasks,
    current_user: TokenData = Depends(get_current_user),
    x_openai_key: str | None = Header(default=None),
    x_openai_model: str | None = Header(default=None),
):
    """
    Trigger the full reporting pipeline.

    The caller may pass their own OpenAI credentials in the X-OpenAI-Key and
    X-OpenAI-Model headers. They are used for this run only and never stored;
    without them the server falls back to OPENAI_API_KEY from the environment.
    """
    from src.graph.workflow import run_pipeline

    run_id = str(uuid.uuid4())
    cid = (request.company_id if request.company_id and current_user.role == "admin"
           else current_user.company_id)

    background_tasks.add_task(
        run_pipeline,
        start_date=request.start_date,
        end_date=request.end_date,
        report_type=request.report_type,
        recipients=request.recipients,
        company_id=cid,
        api_key=x_openai_key,
        model=x_openai_model,
    )

    return PipelineResponse(
        run_id=run_id,
        status="started",
        message=f"Pipeline started for {request.start_date} to {request.end_date}",
    )


@app.post("/run/monthly", response_model=PipelineResponse)
async def run_monthly_endpoint(
    background_tasks: BackgroundTasks,
    current_user: TokenData = Depends(get_current_user),
    x_openai_key: str | None = Header(default=None),
    x_openai_model: str | None = Header(default=None),
):
    """Manually trigger the monthly report for the previous month."""
    from src.graph.workflow import run_pipeline_with_retry
    from src.scheduler import get_previous_month_range

    start_date, end_date = get_previous_month_range()
    run_id = str(uuid.uuid4())

    background_tasks.add_task(
        run_pipeline_with_retry,
        start_date=start_date,
        end_date=end_date,
        report_type="monthly",
        company_id=current_user.company_id,
        api_key=x_openai_key,
        model=x_openai_model,
    )

    return PipelineResponse(
        run_id=run_id,
        status="started",
        message=f"Monthly pipeline started for {start_date} to {end_date}",
    )


@app.post("/run/sync")
async def run_pipeline_sync(
    request: PipelineRequest,
    current_user: TokenData = Depends(get_current_user),
    x_openai_key: str | None = Header(default=None),
    x_openai_model: str | None = Header(default=None),
):
    """Run the pipeline synchronously and return the full result."""
    from src.graph.workflow import run_pipeline

    cid = (request.company_id if request.company_id and current_user.role == "admin"
           else current_user.company_id)
    state = run_pipeline(
        start_date=request.start_date,
        end_date=request.end_date,
        report_type=request.report_type,
        recipients=request.recipients,
        company_id=cid,
        api_key=x_openai_key,
        model=x_openai_model,
    )

    qr = state.get("quality_report") or {}
    quality_failed = not qr.get("is_valid", True) and qr.get("errors")

    errors = state.get("errors", [])
    if quality_failed:
        errors = list(errors) + [f"Kalite kontrolu basarisiz: {e}" for e in qr["errors"]]

    return {
        "run_id": state.get("run_id"),
        "status": "quality_failed" if quality_failed else "completed",
        "weekly_summary": (state.get("raw_data") or {}).get("weekly_summary", {}),
        "analysis_results": state.get("analysis_results", {}),
        "draft_report": state.get("draft_report", ""),
        "evaluation": state.get("evaluation", {}),
        "delivery_status": state.get("delivery_status", {}),
        "errors": errors,
    }


# ══════════════════════════════════════════════════════════════════════════════
# HEALTH & MONITORING (public — /health; authenticated — others)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    """Health check with database status."""
    from config.settings import settings
    from src.tools.sql_tools import test_db_connection

    db_status = test_db_connection()

    return {
        "status": "ok" if db_status["connected"] else "degraded",
        "version": "0.7.0",
        "database": db_status,
        "scheduler_enabled": settings.SCHEDULER_ENABLED,
        "server_llm_key_configured": bool(settings.OPENAI_API_KEY),
        "default_model": settings.OPENAI_MODEL,
    }


@app.get("/runs")
async def list_runs(
    limit: int = 20,
    current_user: TokenData = Depends(get_current_user),
):
    """List recent pipeline runs for current user's company."""
    all_runs = _read_all_runs()
    company_runs = [
        r for r in all_runs
        if r.get("company_id", 1) == current_user.company_id
    ]
    runs = list(reversed(company_runs))[:limit]
    return {"runs": runs, "total": len(runs)}


@app.get("/runs/latest")
async def get_latest_run(current_user: TokenData = Depends(get_current_user)):
    """Return the most recent pipeline run with report content if available."""
    all_runs = _read_all_runs()
    company_runs = [
        r for r in all_runs
        if r.get("company_id", 1) == current_user.company_id
    ]
    if not company_runs:
        raise HTTPException(status_code=404, detail="No pipeline runs found")

    latest = company_runs[-1]

    report_content = None
    report_html = None
    reports_dir = Path(f"data/reports/{current_user.company_id}")
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
async def get_run_detail(
    run_id: str,
    current_user: TokenData = Depends(get_current_user),
):
    """Return details of a specific pipeline run by run_id."""
    all_runs = _read_all_runs()
    for run in all_runs:
        if run.get("run_id") == run_id and run.get("company_id", 1) == current_user.company_id:
            return {"run": run}
    raise HTTPException(status_code=404, detail=f"Run {run_id} not found")


# ── Reports endpoints ─────────────────────────────────────────────────────────

@app.get("/reports")
async def list_reports(
    company_id: int | None = None,
    current_user: TokenData = Depends(get_current_user),
):
    """List report files. Admin can filter by company_id or see all; users see own."""
    is_admin = current_user.role == "admin"

    if is_admin and company_id is None:
        company_dirs = sorted(Path("data/reports").iterdir()) if Path("data/reports").exists() else []
        company_dirs = [d for d in company_dirs if d.is_dir() and d.name.isdigit()]
    elif is_admin and company_id is not None:
        company_dirs = [Path(f"data/reports/{company_id}")]
    else:
        company_dirs = [Path(f"data/reports/{current_user.company_id}")]

    reports = []
    for cdir in company_dirs:
        if not cdir.exists():
            continue
        cid = int(cdir.name)
        for f in sorted(cdir.glob("*.md"), reverse=True):
            html_file = f.with_suffix(".html")
            reports.append({
                "filename": f.name,
                "company_id": cid,
                "created_at": f.stat().st_mtime,
                "size_bytes": f.stat().st_size,
                "has_html": html_file.exists(),
            })

    reports.sort(key=lambda r: r["created_at"], reverse=True)
    return {"reports": reports}


@app.get("/reports/{filename}")
async def get_report(
    filename: str,
    company_id: int | None = None,
    current_user: TokenData = Depends(get_current_user),
):
    """Return the content of a specific report file."""
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    is_admin = current_user.role == "admin"
    cid = company_id if (is_admin and company_id) else current_user.company_id

    md_path = Path(f"data/reports/{cid}") / filename
    if not md_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")

    content = md_path.read_text(encoding="utf-8")
    html_path = md_path.with_suffix(".html")
    html_content = html_path.read_text(encoding="utf-8") if html_path.exists() else None

    return {
        "filename": filename,
        "company_id": cid,
        "content_md": content,
        "content_html": html_content,
    }


# ── Database stats ────────────────────────────────────────────────────────────

@app.get("/db/stats")
async def db_stats(current_user: TokenData = Depends(get_current_user)):
    """Return database summary statistics. Admin sees all, users see own company."""
    from src.tools.sql_tools import execute_query

    is_admin = current_user.role == "admin"
    cid = current_user.company_id
    where = "" if is_admin else " WHERE company_id = :cid"
    params: dict = {} if is_admin else {"cid": cid}

    try:
        total = execute_query(f"SELECT COUNT(*) as cnt FROM orders{where}", params)
        date_range = execute_query(
            f"SELECT MIN(order_date) as min_date, MAX(order_date) as max_date FROM orders{where}",
            params,
        )
        categories = execute_query(
            f"SELECT category, COUNT(*) as cnt FROM orders{where} GROUP BY category",
            params,
        )

        return {
            "total_orders": int(total["cnt"].iloc[0]) if not total.empty else 0,
            "date_range": {
                "min": str(date_range["min_date"].iloc[0]) if not date_range.empty else "",
                "max": str(date_range["max_date"].iloc[0]) if not date_range.empty else "",
            },
            "categories": categories.to_dict("records") if not categories.empty else [],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database query failed: {exc}")


# ── Company comparison (admin) ────────────────────────────────────────────────

@app.get("/admin/company-stats")
async def company_stats(admin: TokenData = Depends(require_admin)):
    """Return per-company comparison metrics for admin dashboard."""
    from src.tools.sql_tools import execute_query

    df = execute_query("""
        SELECT
            c.id                                    AS company_id,
            c.name                                  AS company_name,
            COUNT(DISTINCT o.order_id)              AS total_orders,
            COUNT(DISTINCT o.customer_id)           AS unique_customers,
            ROUND(SUM(o.sales), 2)                  AS total_revenue,
            ROUND(SUM(o.profit), 2)                 AS total_profit,
            ROUND(SUM(o.profit) * 100.0 / NULLIF(SUM(o.sales), 0), 1) AS profit_margin_pct,
            ROUND(SUM(o.sales) / COUNT(DISTINCT o.order_id), 2) AS avg_order_value,
            ROUND(AVG(o.discount), 3)               AS avg_discount
        FROM orders o
        JOIN companies c ON o.company_id = c.id
        GROUP BY c.id, c.name
        ORDER BY total_revenue DESC
    """)

    companies = df.to_dict("records") if not df.empty else []

    totals = {
        "total_orders": int(df["total_orders"].sum()) if not df.empty else 0,
        "total_revenue": round(float(df["total_revenue"].sum()), 2) if not df.empty else 0,
        "total_profit": round(float(df["total_profit"].sum()), 2) if not df.empty else 0,
        "total_customers": int(df["unique_customers"].sum()) if not df.empty else 0,
    }

    return {"companies": companies, "totals": totals}


# ── RAG stats ─────────────────────────────────────────────────────────────────

@app.get("/rag/stats")
async def rag_stats(current_user: TokenData = Depends(get_current_user)):
    """Return ChromaDB collection statistics."""
    try:
        from src.tools.rag_tools import ReportVectorStore

        store = ReportVectorStore()
        stats = store.get_collection_stats()
        return {"status": "ok", **stats}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN ENDPOINTS (require admin role)
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/admin/upload-data")
async def upload_data(
    file: UploadFile = File(...),
    company_id: int = None,
    admin: TokenData = Depends(require_admin),
):
    """Upload CSV sales data for a company."""
    from src.tools.sql_tools import get_db_engine

    target_company = company_id or admin.company_id

    contents = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(contents), encoding="latin-1")
    except Exception:
        df = pd.read_csv(io.BytesIO(contents), encoding="utf-8")

    df.columns = [c.strip().lower().replace(" ", "_").replace("-", "_") for c in df.columns]

    required = {"order_id", "order_date", "sales", "quantity", "profit"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(400, f"Missing required columns: {missing}")

    df["company_id"] = target_company

    df["order_date"] = pd.to_datetime(df["order_date"], format="mixed").dt.date
    if "ship_date" in df.columns:
        df["ship_date"] = pd.to_datetime(df["ship_date"], format="mixed", errors="coerce").dt.date

    engine = get_db_engine()
    rows_before = pd.read_sql(
        text("SELECT COUNT(*) as cnt FROM orders WHERE company_id = :cid"),
        engine,
        params={"cid": target_company},
    ).iloc[0]["cnt"]

    df.to_sql("orders", engine, if_exists="append", index=False)

    rows_after = pd.read_sql(
        text("SELECT COUNT(*) as cnt FROM orders WHERE company_id = :cid"),
        engine,
        params={"cid": target_company},
    ).iloc[0]["cnt"]

    return {
        "message": f"Uploaded {len(df)} rows for company {target_company}",
        "rows_before": int(rows_before),
        "rows_after": int(rows_after),
        "new_rows": int(rows_after - rows_before),
    }


@app.post("/admin/companies")
async def create_company(
    req: CompanyCreate,
    admin: TokenData = Depends(require_admin),
):
    """Create a new company (admin only)."""
    from src.tools.sql_tools import get_db_engine

    engine = get_db_engine()
    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT id FROM companies WHERE slug = :slug"),
            {"slug": req.slug},
        ).fetchone()
        if existing:
            raise HTTPException(400, f"Company with slug '{req.slug}' already exists")

        conn.execute(text("""
            INSERT INTO companies (name, slug, email_domain, segment)
            VALUES (:name, :slug, :domain, :segment)
        """), {"name": req.name, "slug": req.slug, "domain": req.email_domain, "segment": req.segment})

    return {"message": f"Company '{req.name}' created"}


@app.get("/admin/companies")
async def list_companies(admin: TokenData = Depends(require_admin)):
    """List all companies (admin only)."""
    from src.tools.sql_tools import get_db_engine

    engine = get_db_engine()
    df = pd.read_sql(text("SELECT * FROM companies ORDER BY id"), engine)
    return {"companies": df.to_dict("records")}


@app.get("/admin/users")
async def list_users(admin: TokenData = Depends(require_admin)):
    """List all users (admin only)."""
    from src.tools.sql_tools import get_db_engine

    engine = get_db_engine()
    df = pd.read_sql(text("""
        SELECT u.id, u.email, u.full_name, u.role, u.company_id,
               c.name as company_name, u.created_at, u.is_active
        FROM users u JOIN companies c ON u.company_id = c.id
        ORDER BY u.id
    """), engine)
    return {"users": df.to_dict("records")}


@app.post("/admin/send-report")
async def admin_send_report(
    req: AdminReportRequest,
    admin: TokenData = Depends(require_admin),
    x_openai_key: str | None = Header(default=None),
    x_openai_model: str | None = Header(default=None),
):
    """Admin triggers report generation for any company."""
    from src.graph.workflow import run_pipeline

    state = run_pipeline(
        start_date=str(req.start_date),
        end_date=str(req.end_date),
        report_type=req.report_type,
        recipients=req.recipients,
        company_id=req.company_id,
        api_key=x_openai_key,
        model=x_openai_model,
    )

    return {
        "message": f"Report generated for company {req.company_id}",
        "recipients": req.recipients,
        "quality_score": (state.get("evaluation") or {}).get("overall_score"),
        "delivery_status": state.get("delivery_status"),
    }


@app.post("/admin/send-existing-report")
async def send_existing_report(
    req: SendExistingReportRequest,
    admin: TokenData = Depends(require_admin),
):
    """Send an already-generated report via email without re-running the pipeline."""
    from src.agents.delivery import DeliveryAgent
    from src.tools.sql_tools import get_db_engine

    if ".." in req.report_filename or "/" in req.report_filename:
        raise HTTPException(400, "Invalid filename")

    reports_dir = Path(f"data/reports/{req.company_id}")
    md_path = reports_dir / req.report_filename
    html_path = reports_dir / req.report_filename.replace(".md", ".html")

    if not md_path.exists() and not html_path.exists():
        raise HTTPException(404, f"Report not found: {req.report_filename}")

    report_content = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
    html_content = html_path.read_text(encoding="utf-8") if html_path.exists() else ""

    recipients = req.recipients
    if not recipients:
        engine = get_db_engine()
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT email FROM users WHERE company_id = :cid AND is_active = 1"),
                {"cid": req.company_id},
            )
            recipients = [row[0] for row in result.fetchall()]

    if not recipients:
        raise HTTPException(400, "No recipients found for this company")

    match = None
    import re
    match = re.search(r"(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})", req.report_filename)
    start_date = match.group(1) if match else ""
    end_date = match.group(2) if match else ""
    subject = f"Tedarikci Performans Raporu — {start_date} / {end_date}"

    delivery = DeliveryAgent()
    email_result = delivery._send_email(
        recipients=recipients,
        subject=subject,
        body_html=html_content or delivery._render_html(report_content, start_date, end_date),
        body_text=report_content,
    )

    return {
        "message": f"Report sent to {len(recipients)} recipient(s)",
        "recipients": recipients,
        "email_result": email_result,
    }
