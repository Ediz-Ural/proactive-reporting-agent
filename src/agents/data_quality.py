"""
Data Quality Agent (Week 1 — pure Python, no LLM).

Responsibility: validate the collected raw data and produce a structured
quality report that downstream agents can act on.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class DataQualityAgent:
    """
    Validates raw data collected by the DataCollectorAgent.

    Checks performed:
    1. Missing value (null) percentage per column
    2. Negative values in sales / quantity (should be non-negative)
    3. Date consistency: ship_date must not precede order_date
    4. Duplicate rows on (order_id, product_id)
    5. Numeric type validation
    6. Statistical outlier detection (Z-score > threshold)

    Output format:
    {
        "is_valid":            bool,
        "total_rows":          int,
        "null_percentage":     {col: pct},
        "duplicates":          int,
        "negative_values":     {col: count},
        "date_inconsistencies": int,
        "outlier_count":       int,
        "warnings":            [str, ...],
        "errors":              [str, ...],
        "checked_at":          str,
    }
    """

    # Columns that should never be negative
    NON_NEGATIVE_COLS = ["sales", "quantity"]
    # Columns checked for statistical outliers
    OUTLIER_COLS = ["sales", "profit"]
    # Z-score threshold for outlier flagging
    ZSCORE_THRESHOLD: float = 3.0
    # Maximum allowed null percentage before a warning is raised
    NULL_WARNING_PCT: float = 5.0
    # Maximum allowed null percentage before an error is raised
    NULL_ERROR_PCT: float = 20.0

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Validate the raw data dict produced by DataCollectorAgent.

        Args:
            data: Output dict from DataCollectorAgent.collect().

        Returns:
            Quality report dict.
        """
        logger.info("DataQualityAgent: starting validation")
        warnings: list[str] = []
        errors: list[str] = []

        # Build a combined DataFrame from daily_sales + by_category for structural checks
        # The primary validation target is the orders table via the collected records.
        # We reconstruct a flat DataFrame from the daily_sales and category views,
        # but for the most complete check we also query the DB directly when available.
        combined_df = self._build_combined_df(data)

        if combined_df.empty:
            errors.append("No data available for the requested period.")
            return self._build_report(
                is_valid=False,
                total_rows=0,
                null_percentage={},
                duplicates=0,
                negative_values={},
                date_inconsistencies=0,
                outlier_count=0,
                warnings=warnings,
                errors=errors,
            )

        total_rows = len(combined_df)
        logger.debug("Validating %d rows", total_rows)

        # ── 1. Null check ─────────────────────────────────────────────────────
        null_percentage = self._check_nulls(combined_df, warnings, errors)

        # ── 2. Negative value check ───────────────────────────────────────────
        negative_values = self._check_negatives(combined_df, warnings, errors)

        # ── 3. Date consistency ───────────────────────────────────────────────
        date_inconsistencies = self._check_date_consistency(data, warnings, errors)

        # ── 4. Duplicate check ────────────────────────────────────────────────
        duplicates = self._check_duplicates(data, warnings, errors)

        # ── 5. Numeric type validation ────────────────────────────────────────
        self._check_numeric_types(combined_df, warnings, errors)

        # ── 6. Outlier detection ──────────────────────────────────────────────
        outlier_count = self._check_outliers(combined_df, warnings)

        # ── Determine overall validity ────────────────────────────────────────
        is_valid = len(errors) == 0
        logger.info(
            "Validation complete — valid=%s, warnings=%d, errors=%d",
            is_valid, len(warnings), len(errors)
        )

        return self._build_report(
            is_valid=is_valid,
            total_rows=total_rows,
            null_percentage=null_percentage,
            duplicates=duplicates,
            negative_values=negative_values,
            date_inconsistencies=date_inconsistencies,
            outlier_count=outlier_count,
            warnings=warnings,
            errors=errors,
        )

    # ── Check implementations ─────────────────────────────────────────────────

    def _check_nulls(
        self,
        df: pd.DataFrame,
        warnings: list[str],
        errors: list[str],
    ) -> dict[str, float]:
        null_pct: dict[str, float] = {}
        for col in df.columns:
            pct = df[col].isna().mean() * 100
            null_pct[col] = round(pct, 2)
            if pct >= self.NULL_ERROR_PCT:
                errors.append(f"Column '{col}' has {pct:.1f}% null values (threshold: {self.NULL_ERROR_PCT}%)")
            elif pct >= self.NULL_WARNING_PCT:
                warnings.append(f"Column '{col}' has {pct:.1f}% null values")
        return null_pct

    def _check_negatives(
        self,
        df: pd.DataFrame,
        warnings: list[str],
        errors: list[str],
    ) -> dict[str, int]:
        negative_counts: dict[str, int] = {}
        for col in self.NON_NEGATIVE_COLS:
            if col not in df.columns:
                continue
            numeric = pd.to_numeric(df[col], errors="coerce")
            n_neg = int((numeric < 0).sum())
            negative_counts[col] = n_neg
            if n_neg > 0:
                errors.append(f"Column '{col}' has {n_neg} negative value(s)")
        return negative_counts

    def _check_date_consistency(
        self,
        data: dict[str, Any],
        warnings: list[str],
        errors: list[str],
    ) -> int:
        """Check that ship_date >= order_date using a direct DB query."""
        try:
            from src.tools.sql_tools import execute_query
            period = data.get("period", {})
            start = period.get("start", "1970-01-01")
            end = period.get("end", "2099-12-31")
            df = execute_query(
                """
                SELECT COUNT(*) AS cnt
                FROM orders
                WHERE ship_date < order_date
                  AND order_date BETWEEN :start_date AND :end_date
                """,
                {"start_date": start, "end_date": end},
            )
            count = int(df["cnt"].iloc[0]) if not df.empty else 0
            if count > 0:
                errors.append(f"{count} row(s) have ship_date before order_date")
            return count
        except Exception as exc:
            warnings.append(f"Date consistency check skipped: {exc}")
            return 0

    def _check_duplicates(
        self,
        data: dict[str, Any],
        warnings: list[str],
        errors: list[str],
    ) -> int:
        """Check for duplicate (order_id, product_id) pairs via DB query."""
        try:
            from src.tools.sql_tools import execute_query

            period = data.get("period", {})
            start = period.get("start", "1970-01-01")
            end = period.get("end", "2099-12-31")
            df = execute_query(
                """
                SELECT order_id, product_id, COUNT(*) as cnt
                FROM orders
                WHERE order_date BETWEEN :start_date AND :end_date
                GROUP BY order_id, product_id
                HAVING cnt > 1
                """,
                {"start_date": start, "end_date": end},
            )
            dupes = len(df)
            if dupes > 0:
                warnings.append(
                    f"{dupes} duplicate (order_id, product_id) pair(s) found in orders"
                )
            return dupes
        except Exception as exc:
            warnings.append(f"Duplicate check skipped: {exc}")
            return 0

    def _check_numeric_types(
        self,
        df: pd.DataFrame,
        warnings: list[str],
        errors: list[str],
    ) -> None:
        numeric_cols = ["total_sales", "total_profit", "total_orders"]
        for col in numeric_cols:
            if col not in df.columns:
                continue
            non_numeric = pd.to_numeric(df[col], errors="coerce").isna().sum()
            if non_numeric > 0:
                errors.append(f"Column '{col}' has {non_numeric} non-numeric value(s)")

    def _check_outliers(self, df: pd.DataFrame, warnings: list[str]) -> int:
        total_outliers = 0
        for col in self.OUTLIER_COLS:
            if col not in df.columns:
                continue
            numeric = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(numeric) < 10:
                continue
            mean, std = numeric.mean(), numeric.std()
            if std == 0:
                continue
            z_scores = np.abs((numeric - mean) / std)
            n_outliers = int((z_scores > self.ZSCORE_THRESHOLD).sum())
            if n_outliers > 0:
                warnings.append(
                    f"Column '{col}' has {n_outliers} statistical outlier(s) "
                    f"(|Z| > {self.ZSCORE_THRESHOLD})"
                )
                total_outliers += n_outliers
        return total_outliers

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_combined_df(self, data: dict[str, Any]) -> pd.DataFrame:
        """Merge available record lists into one wide DataFrame for validation."""
        frames = []
        for key in ("daily_sales", "by_category"):
            records = data.get(key, [])
            if records:
                frames.append(pd.DataFrame(records))
        if not frames:
            return pd.DataFrame()
        # Use the largest frame as the primary target
        return max(frames, key=len)

    @staticmethod
    def _build_report(
        is_valid: bool,
        total_rows: int,
        null_percentage: dict,
        duplicates: int,
        negative_values: dict,
        date_inconsistencies: int,
        outlier_count: int,
        warnings: list[str],
        errors: list[str],
    ) -> dict[str, Any]:
        return {
            "is_valid": is_valid,
            "total_rows": total_rows,
            "null_percentage": null_percentage,
            "duplicates": duplicates,
            "negative_values": negative_values,
            "date_inconsistencies": date_inconsistencies,
            "outlier_count": outlier_count,
            "warnings": warnings,
            "errors": errors,
            "checked_at": datetime.utcnow().isoformat(),
        }
