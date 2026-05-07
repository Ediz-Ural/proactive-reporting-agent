"""
Analyst Agent — Full implementation (Week 2).

Runs the complete analysis pipeline:
1. Trend analysis on daily sales
2. Anomaly detection (Z-Score + IQR + Isolation Forest)
3. Period-over-period comparison
4. Category performance ranking
5. Time series forecasting (Prophet or linear fallback)
6. STL decomposition (if enough data)
7. Customer RFM segmentation (if customer data available)

The Analyst Agent does NOT call any LLM. It runs pure Python analysis
tools and writes structured results to the AgentState.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

import pandas as pd

from src.graph.state import AgentState
from src.tools.analysis_tools import (
    calculate_category_performance,
    calculate_period_comparison,
    calculate_rfm_segments,
    calculate_sector_comparison,
    calculate_trend,
    decompose_time_series,
    detect_anomalies_iqr,
    detect_anomalies_isolation_forest,
    detect_anomalies_zscore,
    forecast_with_prophet,
)
from src.utils.helpers import get_previous_period

logger = logging.getLogger(__name__)


class AnalystAgent:
    """
    Stateless analysis agent. Accepts raw_data from DataCollectorAgent,
    runs all relevant analysis tools, and writes structured results
    to the AgentState.
    """

    def analyse(self, state: AgentState) -> dict:
        """
        Run the full analysis pipeline.

        Reads from state: raw_data, start_date, end_date, report_type, analysis_plan, company_id
        Writes to state: analysis_results, current_agent, errors

        Returns:
            Dict of state updates (NOT the full state — LangGraph merges it).
        """
        logger.info("AnalystAgent: starting analysis pipeline")

        raw_data: dict = state.get("raw_data") or {}
        start_date: str = state.get("start_date", "")
        end_date: str = state.get("end_date", "")
        report_type: str = state.get("report_type", "weekly")
        company_id: int = state.get("company_id", 1)
        analysis_plan: list[str] = state.get("analysis_plan") or [
            "trends", "anomalies", "period_comparison",
            "category_performance", "forecast", "decomposition",
            "rfm_segments",
        ]

        results: dict[str, Any] = {}
        completed: list[str] = []
        failed: list[str] = []

        # Convert raw_data lists to DataFrames
        daily_sales = pd.DataFrame(raw_data.get("daily_sales", []))
        by_category = pd.DataFrame(raw_data.get("by_category", []))

        if not daily_sales.empty and "order_date" in daily_sales.columns:
            daily_sales["order_date"] = pd.to_datetime(daily_sales["order_date"])

        total_rows = len(daily_sales)

        # ── 1. Trend analysis ────────────────────────────────────────────────
        if "trends" in analysis_plan:
            if total_rows >= 7:
                results["trends"], ok = self._run_trends(daily_sales)
            else:
                results["trends"] = {"note": f"Trend analizi için yeterli veri yok ({total_rows} gün). En az 7 gün gerekli."}
                ok = True
            (completed if ok else failed).append("trends")

        # ── 2. Anomaly detection ─────────────────────────────────────────────
        if "anomalies" in analysis_plan:
            if total_rows >= 7:
                results["anomalies"], ok = self._run_anomalies(daily_sales)
            else:
                results["anomalies"] = []
                ok = True
            (completed if ok else failed).append("anomalies")

        # ── 3. Period comparison ─────────────────────────────────────────────
        if "period_comparison" in analysis_plan:
            results["period_comparison"], ok = self._run_period_comparison(
                daily_sales, start_date, end_date, report_type, company_id,
            )
            (completed if ok else failed).append("period_comparison")

        # ── 4. Category performance ──────────────────────────────────────────
        if "category_performance" in analysis_plan:
            results["category_performance"], ok = self._run_category_performance(by_category)
            (completed if ok else failed).append("category_performance")

        # ── 5. Forecasting ───────────────────────────────────────────────────
        if "forecast" in analysis_plan:
            results["forecast"], ok = self._run_forecast(daily_sales)
            (completed if ok else failed).append("forecast")

        # ── 6. STL Decomposition ─────────────────────────────────────────────
        if "decomposition" in analysis_plan:
            results["decomposition"], ok = self._run_decomposition(daily_sales)
            (completed if ok else failed).append("decomposition")

        # ── 7. RFM Segmentation ──────────────────────────────────────────────
        if "rfm_segments" in analysis_plan:
            results["rfm_segments"], ok = self._run_rfm(start_date, end_date, company_id)
            (completed if ok else failed).append("rfm_segments")

        # ── 8. Sector Comparison ─────────────────────────────────────────────
        if "sector_comparison" in analysis_plan:
            results["sector_comparison"], ok = self._run_sector_comparison(
                company_id, start_date, end_date,
            )
            (completed if ok else failed).append("sector_comparison")

        # ── Metadata ─────────────────────────────────────────────────────────
        results["analysis_metadata"] = {
            "analysed_at": datetime.utcnow().isoformat(),
            "period": f"{start_date} to {end_date}",
            "total_rows_analysed": total_rows,
            "analyses_completed": completed,
            "analyses_failed": failed,
        }

        logger.info(
            "AnalystAgent: completed=%s, failed=%s",
            completed, failed,
        )

        return {
            "analysis_results": results,
            "current_agent": "analyst",
            "errors": [f"analyst: {f}" for f in failed] if failed else [],
        }

    # ── Private analysis runners ──────────────────────────────────────────────

    def _run_trends(
        self, daily_sales: pd.DataFrame,
    ) -> tuple[dict, bool]:
        """Run trend analysis on each numeric metric."""
        try:
            trends: dict[str, Any] = {}
            for col in ["total_sales", "total_profit", "total_orders"]:
                if col in daily_sales.columns:
                    trends[col] = calculate_trend(daily_sales, "order_date", col)
            logger.info("Trend analysis complete: %d metrics", len(trends))
            return trends, True
        except Exception as exc:
            logger.error("Trend analysis failed: %s", exc)
            return {}, False

    def _run_anomalies(
        self, daily_sales: pd.DataFrame,
    ) -> tuple[list[dict], bool]:
        """Run Z-score, IQR, and Isolation Forest anomaly detection."""
        try:
            anomalies: list[dict] = []
            value_cols = ["total_sales", "total_profit"]

            for col in value_cols:
                if col not in daily_sales.columns:
                    continue

                # Z-score
                zs = detect_anomalies_zscore(
                    daily_sales, col, threshold=2.5, date_col="order_date",
                )
                for _, row in zs.iterrows():
                    anomalies.append({
                        "date": str(row.get("order_date", "")),
                        "column": col,
                        "value": float(row[col]),
                        "z_score": float(row["z_score"]),
                        "method": "zscore",
                    })

                # IQR
                iqr = detect_anomalies_iqr(
                    daily_sales, col, date_col="order_date",
                )
                for _, row in iqr.iterrows():
                    anomalies.append({
                        "date": str(row.get("order_date", "")),
                        "column": col,
                        "value": float(row[col]),
                        "method": "iqr",
                    })

            # Isolation Forest (multivariate)
            available_cols = [c for c in value_cols if c in daily_sales.columns]
            if available_cols:
                iso = detect_anomalies_isolation_forest(
                    daily_sales, available_cols, date_col="order_date",
                )
                for _, row in iso.iterrows():
                    anomalies.append({
                        "date": str(row.get("order_date", "")),
                        "column": available_cols[0],
                        "value": float(row[available_cols[0]]),
                        "anomaly_score": float(row.get("anomaly_score", 0)),
                        "method": "isolation_forest",
                    })

            logger.info("Anomaly detection complete: %d anomalies found", len(anomalies))
            return anomalies, True
        except Exception as exc:
            logger.error("Anomaly detection failed: %s", exc)
            return [], False

    def _run_period_comparison(
        self,
        daily_sales: pd.DataFrame,
        start_date: str,
        end_date: str,
        report_type: str,
        company_id: int = 1,
    ) -> tuple[dict, bool]:
        """Fetch previous period data and calculate period-over-period change."""
        try:
            from src.tools.sql_tools import get_sales_by_period

            prev_start, prev_end = get_previous_period(
                date.fromisoformat(start_date),
                date.fromisoformat(end_date),
                report_type=report_type,
            )
            prev_data = get_sales_by_period(str(prev_start), str(prev_end), company_id=company_id)
            comparison = calculate_period_comparison(daily_sales, prev_data)
            logger.info("Period comparison complete")
            return comparison, True
        except Exception as exc:
            logger.error("Period comparison failed: %s", exc)
            return {}, False

    def _run_category_performance(
        self, by_category: pd.DataFrame,
    ) -> tuple[list[dict], bool]:
        """Rank categories by performance."""
        try:
            perf = calculate_category_performance(by_category)
            if perf.empty:
                return [], True
            records = perf.to_dict(orient="records")
            logger.info("Category performance: %d categories ranked", len(records))
            return records, True
        except Exception as exc:
            logger.error("Category performance failed: %s", exc)
            return [], False

    def _run_forecast(
        self, daily_sales: pd.DataFrame,
    ) -> tuple[dict, bool]:
        """Run Prophet (or fallback linear) forecast."""
        try:
            result = forecast_with_prophet(
                daily_sales, "order_date", "total_sales", periods=7,
            )
            if result:
                logger.info("Forecast complete (method=%s)", result.get("method"))
            else:
                logger.info("Forecast skipped — insufficient data")
            return result, True
        except Exception as exc:
            logger.error("Forecast failed: %s", exc)
            return {}, False

    def _run_decomposition(
        self, daily_sales: pd.DataFrame,
    ) -> tuple[dict, bool]:
        """Run STL time series decomposition."""
        try:
            result = decompose_time_series(
                daily_sales, "order_date", "total_sales", period=7,
            )
            if result:
                logger.info(
                    "STL decomposition complete: seasonal_strength=%.3f",
                    result.get("seasonal_strength", 0),
                )
            else:
                logger.info("STL decomposition skipped — insufficient data")
            return result, True
        except Exception as exc:
            logger.error("STL decomposition failed: %s", exc)
            return {}, False

    def _run_rfm(
        self, start_date: str, end_date: str, company_id: int = 1,
    ) -> tuple[dict, bool]:
        """Query DB for per-customer orders and run RFM segmentation."""
        try:
            from src.tools.sql_tools import execute_query

            orders_df = execute_query(
                """
                SELECT customer_id, order_date, sales
                FROM orders
                WHERE order_date BETWEEN :start_date AND :end_date
                  AND company_id = :company_id
                """,
                {"start_date": start_date, "end_date": end_date, "company_id": company_id},
            )
            if orders_df.empty:
                logger.info("RFM skipped — no customer data")
                return {"total_customers": 0, "segments": {}}, True

            rfm_df = calculate_rfm_segments(
                orders_df,
                customer_col="customer_id",
                date_col="order_date",
                revenue_col="sales",
                reference_date=end_date,
            )
            if rfm_df.empty:
                return {"total_customers": 0, "segments": {}}, True

            segments_summary = rfm_df["segment_label"].value_counts().to_dict()
            logger.info("RFM segmentation: %d customers", len(rfm_df))
            return {
                "total_customers": len(rfm_df),
                "segments": segments_summary,
            }, True
        except Exception as exc:
            logger.error("RFM segmentation failed: %s", exc)
            return {}, False

    def _run_sector_comparison(
        self, company_id: int, start_date: str, end_date: str,
    ) -> tuple[dict, bool]:
        """Compare company KPIs against anonymized sector peers."""
        try:
            result = calculate_sector_comparison(company_id, start_date, end_date)
            if result:
                logger.info(
                    "Sector comparison: rank %s/%s",
                    result.get("company_rank"),
                    result.get("total_in_sector"),
                )
            return result, True
        except Exception as exc:
            logger.error("Sector comparison failed: %s", exc)
            return {}, False
