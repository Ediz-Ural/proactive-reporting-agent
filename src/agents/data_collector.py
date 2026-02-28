"""
Data Collector Agent (Week 1 — pure Python, no LLM).

Responsibility: pull all raw data required for a given reporting period
from the database and package it into a single dict for downstream agents.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

import pandas as pd

from src.tools.sql_tools import (
    get_customer_metrics,
    get_region_performance,
    get_sales_by_category,
    get_sales_by_period,
    get_top_products,
    get_weekly_summary,
)

logger = logging.getLogger(__name__)


class DataCollectorAgent:
    """
    Collects all raw data for a reporting period.

    The output dict schema (all DataFrames are serialised to list-of-dicts
    so the LangGraph state can be serialised to JSON):

    {
        "period":           {"start": str, "end": str},
        "daily_sales":      list[dict],          # from get_sales_by_period
        "by_category":      list[dict],          # from get_sales_by_category
        "top_products":     list[dict],          # from get_top_products
        "customer_metrics": list[dict],          # from get_customer_metrics
        "region_performance": list[dict],        # from get_region_performance
        "weekly_summary":   dict,                # from get_weekly_summary
        "collected_at":     str,                 # ISO timestamp
    }
    """

    def __init__(self, top_products_limit: int = 10) -> None:
        self.top_products_limit = top_products_limit

    # ── Public API ────────────────────────────────────────────────────────────

    def collect(self, start_date: str | date, end_date: str | date) -> dict[str, Any]:
        """
        Fetch all data required for the report period.

        Args:
            start_date: Period start (ISO string or date object).
            end_date:   Period end (ISO string or date object).

        Returns:
            Dict containing all collected DataFrames (as list[dict]) and
            the weekly summary.

        Raises:
            RuntimeError: If a critical query fails.
        """
        start = str(start_date)
        end = str(end_date)
        logger.info("DataCollectorAgent: collecting data for %s → %s", start, end)

        result: dict[str, Any] = {
            "period": {"start": start, "end": end},
            "collected_at": datetime.utcnow().isoformat(),
        }
        errors: list[str] = []

        # Each fetch is wrapped individually so one failure doesn't block others
        result["daily_sales"] = self._fetch(
            "daily_sales", get_sales_by_period, start, end, errors
        )
        result["by_category"] = self._fetch(
            "by_category", get_sales_by_category, start, end, errors
        )
        result["top_products"] = self._fetch(
            "top_products",
            lambda s, e: get_top_products(s, e, limit=self.top_products_limit),
            start,
            end,
            errors,
        )
        result["customer_metrics"] = self._fetch(
            "customer_metrics", get_customer_metrics, start, end, errors
        )
        result["region_performance"] = self._fetch(
            "region_performance", get_region_performance, start, end, errors
        )

        try:
            result["weekly_summary"] = get_weekly_summary(start, end)
        except Exception as exc:
            logger.error("Failed to fetch weekly_summary: %s", exc)
            errors.append(f"weekly_summary: {exc}")
            result["weekly_summary"] = {}

        if errors:
            result["collection_errors"] = errors
            logger.warning("%d collection error(s): %s", len(errors), errors)
        else:
            logger.info(
                "Collection complete — %d daily rows, %d categories, %d top products",
                len(result["daily_sales"]),
                len(result["by_category"]),
                len(result["top_products"]),
            )

        return result

    # ── Private helpers ───────────────────────────────────────────────────────

    def _fetch(
        self,
        label: str,
        fn,
        start: str,
        end: str,
        errors: list[str],
    ) -> list[dict]:
        """Call a SQL tool function and convert the DataFrame to list[dict]."""
        try:
            df: pd.DataFrame = fn(start, end)
            return self._df_to_records(df)
        except Exception as exc:
            logger.error("Failed to fetch %s: %s", label, exc)
            errors.append(f"{label}: {exc}")
            return []

    @staticmethod
    def _df_to_records(df: pd.DataFrame) -> list[dict]:
        """Convert DataFrame to JSON-serialisable list of dicts."""
        if df.empty:
            return []
        # Convert date/datetime columns to ISO strings
        for col in df.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns:
            df[col] = df[col].dt.strftime("%Y-%m-%d")
        return df.to_dict(orient="records")
