"""
Pydantic schemas for the proactive reporting agent.
These models define the data contracts between agents.
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

# ── Input / Request ──────────────────────────────────────────────────────────

class ReportRequest(BaseModel):
    """Input parameters for triggering a report generation pipeline."""

    start_date: date
    end_date: date
    report_type: str = Field(default="weekly", pattern="^(weekly|monthly|quarterly)$")
    recipients: list[str] = Field(default_factory=list)

    @field_validator("end_date")
    @classmethod
    def end_date_after_start(cls, v: date, info) -> date:
        if "start_date" in info.data and v < info.data["start_date"]:
            raise ValueError("end_date must be after start_date")
        return v


# ── Data Layer ───────────────────────────────────────────────────────────────

class WeeklySummary(BaseModel):
    """Aggregated sales summary for a given period."""

    period: str
    total_revenue: float = Field(ge=0)
    total_orders: int = Field(ge=0)
    avg_order_value: float = Field(ge=0)
    unique_customers: int = Field(ge=0)
    total_profit: float
    profit_margin_pct: float
    revenue_change_pct: Optional[float] = None
    orders_change_pct: Optional[float] = None


class OrderRow(BaseModel):
    """Single order record as returned from the database."""

    order_id: str
    order_date: date
    ship_date: date
    ship_mode: str
    customer_id: str
    segment: str
    country: str
    city: str
    state: str
    region: str
    product_id: str
    category: str
    sub_category: str
    product_name: str
    sales: float = Field(ge=0)
    quantity: int = Field(ge=0)
    discount: float = Field(ge=0, le=1)
    profit: float


# ── Data Quality ──────────────────────────────────────────────────────────────

class DataQualityReport(BaseModel):
    """Output of the Data Quality Agent."""

    is_valid: bool
    total_rows: int = Field(ge=0)
    null_percentage: dict[str, float] = Field(default_factory=dict)
    duplicates: int = Field(ge=0)
    negative_values: dict[str, int] = Field(default_factory=dict)
    date_inconsistencies: int = Field(ge=0, default=0)
    outlier_count: int = Field(ge=0, default=0)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    checked_at: datetime = Field(default_factory=datetime.utcnow)


# ── Analysis ─────────────────────────────────────────────────────────────────

class TrendResult(BaseModel):
    """Output of trend analysis for a single metric."""

    metric: str
    direction: str = Field(pattern="^(up|down|stable)$")
    growth_rate_pct: float
    sma_7: Optional[float] = None
    sma_30: Optional[float] = None
    mannkendall_trend: Optional[str] = None


class AnomalyRecord(BaseModel):
    """A single detected anomaly."""

    date: Optional[date] = None
    column: str
    value: float
    z_score: Optional[float] = None
    method: str = Field(default="zscore", pattern="^(zscore|iqr)$")
    severity: str = Field(default="medium", pattern="^(low|medium|high)$")


class CategoryPerformance(BaseModel):
    """Performance metrics for a single category."""

    category: str
    total_sales: float
    total_profit: float
    profit_margin_pct: float
    order_count: int
    avg_discount: float
    sales_share_pct: float


class AnalysisResult(BaseModel):
    """Complete output of the Analyst Agent."""

    trends: dict[str, TrendResult]
    anomalies: list[AnomalyRecord]
    category_performance: list[CategoryPerformance]
    period_comparison: dict[str, float]
    top_products: list[dict]
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ── Evaluator ────────────────────────────────────────────────────────────────

class EvaluatorScore(BaseModel):
    """Quality assessment produced by the Evaluator Agent."""

    overall_score: float = Field(ge=0.0, le=1.0)
    numerical_accuracy: float = Field(ge=0.0, le=1.0)
    completeness: float = Field(ge=0.0, le=1.0)
    readability: float = Field(ge=0.0, le=1.0)
    actionability: float = Field(ge=0.0, le=1.0)
    feedback: str
    approved: bool
    iteration: int = Field(ge=1, default=1)


# ── Pipeline state snapshots ──────────────────────────────────────────────────

class PipelineRun(BaseModel):
    """Top-level record of a complete pipeline execution."""

    run_id: str
    request: ReportRequest
    quality_report: Optional[DataQualityReport] = None
    analysis: Optional[AnalysisResult] = None
    evaluation: Optional[EvaluatorScore] = None
    final_report: Optional[str] = None
    delivery_status: Optional[dict] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    errors: list[str] = Field(default_factory=list)
