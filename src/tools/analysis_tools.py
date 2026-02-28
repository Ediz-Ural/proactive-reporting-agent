"""
Statistical analysis tools for the Analyst Agent.

All functions are pure Python / pandas / numpy / scipy — no LLM calls.
They will be wired into the Analyst Agent in Week 2.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


# ── Trend analysis ────────────────────────────────────────────────────────────

def calculate_trend(
    df: pd.DataFrame,
    date_col: str,
    value_col: str,
    sma_windows: tuple[int, ...] = (7, 30),
) -> dict[str, Any]:
    """
    Calculate simple moving averages, overall growth rate, and trend direction.

    Args:
        df:          DataFrame containing the date and value columns.
        date_col:    Name of the date column.
        value_col:   Name of the numeric column to analyse.
        sma_windows: Rolling window sizes for SMA calculation.

    Returns:
        Dict with keys: metric, direction, growth_rate_pct, sma_{n} for each window,
        first_value, last_value, min_value, max_value, mean_value, mannkendall_trend.
    """
    if df.empty or value_col not in df.columns:
        logger.warning("calculate_trend: empty DataFrame or missing column '%s'", value_col)
        return {"metric": value_col, "direction": "stable", "growth_rate_pct": 0.0}

    df = df.sort_values(date_col).copy()
    series = pd.to_numeric(df[value_col], errors="coerce").dropna()

    if len(series) < 2:
        return {"metric": value_col, "direction": "stable", "growth_rate_pct": 0.0}

    first_val = float(series.iloc[0])
    last_val = float(series.iloc[-1])
    growth_rate = ((last_val - first_val) / abs(first_val) * 100) if first_val != 0 else 0.0

    result: dict[str, Any] = {
        "metric": value_col,
        "direction": "up" if growth_rate > 1 else ("down" if growth_rate < -1 else "stable"),
        "growth_rate_pct": round(growth_rate, 2),
        "first_value": round(first_val, 2),
        "last_value": round(last_val, 2),
        "min_value": round(float(series.min()), 2),
        "max_value": round(float(series.max()), 2),
        "mean_value": round(float(series.mean()), 2),
    }

    # Simple Moving Averages
    for window in sma_windows:
        if len(series) >= window:
            sma = float(series.rolling(window).mean().iloc[-1])
            result[f"sma_{window}"] = round(sma, 2)
        else:
            result[f"sma_{window}"] = None

    # Mann-Kendall trend test (requires pymannkendall; fall back gracefully)
    try:
        import pymannkendall as mk
        mk_result = mk.original_test(series.values)
        result["mannkendall_trend"] = mk_result.trend   # "increasing", "decreasing", "no trend"
        result["mannkendall_p"] = round(float(mk_result.p), 4)
    except ImportError:
        logger.debug("pymannkendall not installed — skipping Mann-Kendall test")
        result["mannkendall_trend"] = None
        result["mannkendall_p"] = None

    return result


# ── Anomaly detection ─────────────────────────────────────────────────────────

def detect_anomalies_zscore(
    df: pd.DataFrame,
    value_col: str,
    threshold: float = 2.5,
    date_col: str | None = None,
) -> pd.DataFrame:
    """
    Flag rows where the absolute Z-score exceeds *threshold*.

    Args:
        df:         DataFrame to analyse.
        value_col:  Column to compute Z-scores on.
        threshold:  Z-score cutoff (default 2.5).
        date_col:   Optional date column to include in the output.

    Returns:
        DataFrame of anomalous rows with an added 'z_score' column.
        Returns empty DataFrame if the input is too small.
    """
    if df.empty or value_col not in df.columns:
        return pd.DataFrame()

    series = pd.to_numeric(df[value_col], errors="coerce")
    if series.std() == 0 or len(series.dropna()) < 5:
        logger.debug("detect_anomalies_zscore: insufficient data for '%s'", value_col)
        return pd.DataFrame()

    z_scores = np.abs(stats.zscore(series.fillna(series.median())))
    mask = z_scores > threshold
    anomalies = df[mask].copy()
    anomalies["z_score"] = np.round(z_scores[mask], 3)
    anomalies["method"] = "zscore"
    anomalies["column"] = value_col

    logger.info("Z-score anomaly: %d outlier(s) in '%s' (threshold=%.1f)", len(anomalies), value_col, threshold)
    return anomalies


def detect_anomalies_iqr(
    df: pd.DataFrame,
    value_col: str,
    date_col: str | None = None,
) -> pd.DataFrame:
    """
    Flag rows outside the [Q1 - 1.5*IQR, Q3 + 1.5*IQR] fence.

    Args:
        df:         DataFrame to analyse.
        value_col:  Column to apply IQR method on.
        date_col:   Optional date column to include in the output.

    Returns:
        DataFrame of anomalous rows with added 'lower_fence' and 'upper_fence' columns.
    """
    if df.empty or value_col not in df.columns:
        return pd.DataFrame()

    series = pd.to_numeric(df[value_col], errors="coerce").dropna()
    if len(series) < 5:
        return pd.DataFrame()

    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    lower_fence = q1 - 1.5 * iqr
    upper_fence = q3 + 1.5 * iqr

    numeric_series = pd.to_numeric(df[value_col], errors="coerce")
    mask = (numeric_series < lower_fence) | (numeric_series > upper_fence)
    anomalies = df[mask].copy()
    anomalies["lower_fence"] = round(lower_fence, 2)
    anomalies["upper_fence"] = round(upper_fence, 2)
    anomalies["method"] = "iqr"
    anomalies["column"] = value_col

    logger.info("IQR anomaly: %d outlier(s) in '%s'", len(anomalies), value_col)
    return anomalies


# ── Period comparison ─────────────────────────────────────────────────────────

def calculate_period_comparison(
    current_df: pd.DataFrame,
    previous_df: pd.DataFrame,
    metrics: list[str] | None = None,
) -> dict[str, float]:
    """
    Calculate percentage change for each metric between two periods.

    Args:
        current_df:  Aggregated metrics for the current period.
        previous_df: Aggregated metrics for the comparison period.
        metrics:     List of column names to compare. Defaults to
                     [total_sales, total_profit, total_orders].

    Returns:
        Dict mapping metric → percentage_change. Returns empty dict if either
        DataFrame is empty.
    """
    if current_df.empty or previous_df.empty:
        logger.warning("calculate_period_comparison: one or both DataFrames are empty")
        return {}

    default_metrics = ["total_sales", "total_profit", "total_orders"]
    cols = metrics or default_metrics

    def _sum(df: pd.DataFrame, col: str) -> float:
        if col not in df.columns:
            return 0.0
        return float(pd.to_numeric(df[col], errors="coerce").sum())

    comparison: dict[str, float] = {}
    for col in cols:
        curr_val = _sum(current_df, col)
        prev_val = _sum(previous_df, col)
        if prev_val == 0:
            pct = 100.0 if curr_val > 0 else 0.0
        else:
            pct = (curr_val - prev_val) / abs(prev_val) * 100
        comparison[f"{col}_change_pct"] = round(pct, 2)
        comparison[f"{col}_current"] = round(curr_val, 2)
        comparison[f"{col}_previous"] = round(prev_val, 2)

    return comparison


# ── Category performance ──────────────────────────────────────────────────────

def calculate_category_performance(df: pd.DataFrame) -> pd.DataFrame:
    """
    Produce a summary of performance metrics per category.

    Args:
        df: DataFrame with at least [category, total_sales, total_profit,
            order_count] columns (as returned by get_sales_by_category).

    Returns:
        DataFrame with added columns: sales_share_pct, profit_margin_pct,
        performance_rank (1 = best).
        Returns empty DataFrame if input is empty or missing required columns.
    """
    required = {"category", "total_sales", "total_profit"}
    if df.empty or not required.issubset(df.columns):
        logger.warning("calculate_category_performance: missing required columns")
        return pd.DataFrame()

    out = df.copy()
    for col in ("total_sales", "total_profit"):
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)

    total_sales = out["total_sales"].sum()
    out["sales_share_pct"] = (
        (out["total_sales"] / total_sales * 100).round(2)
        if total_sales > 0
        else 0.0
    )
    out["profit_margin_pct"] = (
        (out["total_profit"] / out["total_sales"].replace(0, np.nan) * 100)
        .round(2)
        .fillna(0.0)
    )
    out["performance_rank"] = out["total_sales"].rank(ascending=False, method="min").astype(int)
    return out.sort_values("performance_rank")


# ── Forecasting helper ────────────────────────────────────────────────────────

def calculate_simple_forecast(
    df: pd.DataFrame,
    date_col: str,
    value_col: str,
    periods: int = 7,
) -> pd.DataFrame:
    """
    Naive linear-regression forecast for the next *periods* days.

    Args:
        df:         Historical data with date and value columns.
        date_col:   Name of the date column.
        value_col:  Column to forecast.
        periods:    Number of future periods to predict.

    Returns:
        DataFrame with columns [date, forecast, lower_bound, upper_bound].
    """
    if df.empty or len(df) < 5:
        return pd.DataFrame()

    df = df.sort_values(date_col).copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df["_x"] = (df[date_col] - df[date_col].min()).dt.days

    y = pd.to_numeric(df[value_col], errors="coerce").fillna(0).values
    x = df["_x"].values

    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

    last_day = int(x.max())
    future_x = np.arange(last_day + 1, last_day + periods + 1)
    future_dates = pd.date_range(
        df[date_col].max() + pd.Timedelta(days=1), periods=periods
    )

    forecast = intercept + slope * future_x
    residuals = y - (intercept + slope * x)
    rmse = np.sqrt(np.mean(residuals ** 2))

    result = pd.DataFrame({
        "date": future_dates,
        "forecast": np.round(forecast, 2),
        "lower_bound": np.round(forecast - 1.96 * rmse, 2),
        "upper_bound": np.round(forecast + 1.96 * rmse, 2),
    })
    logger.info("Forecast generated for %d periods (R²=%.3f)", periods, r_value ** 2)
    return result
