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
    if date_col and date_col in anomalies.columns:
        anomalies = anomalies.sort_values(date_col)

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
    if date_col and date_col in anomalies.columns:
        anomalies = anomalies.sort_values(date_col)

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
    prev_rows = len(previous_df)
    insufficient = prev_rows < 3

    for col in cols:
        curr_val = _sum(current_df, col)
        prev_val = _sum(previous_df, col)
        if prev_val == 0:
            pct = 100.0 if curr_val > 0 else 0.0
        else:
            pct = (curr_val - prev_val) / abs(prev_val) * 100

        if abs(pct) > 500:
            comparison[f"{col}_change_pct"] = None  # type: ignore[assignment]
        else:
            comparison[f"{col}_change_pct"] = round(pct, 2)
        comparison[f"{col}_current"] = round(curr_val, 2)
        comparison[f"{col}_previous"] = round(prev_val, 2)

    comparison["previous_period_rows"] = prev_rows
    if insufficient:
        comparison["insufficient_previous_data"] = True

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


# ── Isolation Forest anomaly detection ───────────────────────────────────────

def detect_anomalies_isolation_forest(
    df: pd.DataFrame,
    value_cols: list[str],
    contamination: float = 0.05,
    date_col: str | None = None,
) -> pd.DataFrame:
    """
    Scikit-learn Isolation Forest ile çok değişkenli anomali tespiti.

    Args:
        df: Analiz edilecek DataFrame.
        value_cols: Anomali tespitinde kullanılacak kolonlar (örn. ["total_sales", "total_profit"]).
        contamination: Beklenen anomali oranı (0.01-0.5).
        date_col: Opsiyonel tarih kolonu (çıktıya eklenir).

    Returns:
        Anomali olarak işaretlenen satırları içeren DataFrame.
        Eklenen kolonlar: anomaly_score, is_anomaly.
    """
    if df.empty or len(df) < 10:
        logger.debug("detect_anomalies_isolation_forest: insufficient data (%d rows)", len(df))
        return pd.DataFrame()

    missing = [c for c in value_cols if c not in df.columns]
    if missing:
        logger.warning("Isolation Forest: missing columns %s", missing)
        return pd.DataFrame()

    from sklearn.ensemble import IsolationForest

    X = df[value_cols].apply(pd.to_numeric, errors="coerce").fillna(0)

    model = IsolationForest(
        contamination=contamination,
        random_state=42,
        n_estimators=100,
    )
    predictions = model.fit_predict(X)
    scores = model.decision_function(X)

    mask = predictions == -1
    anomalies = df[mask].copy()
    anomalies["anomaly_score"] = np.round(scores[mask], 4)
    anomalies["is_anomaly"] = True

    if date_col and date_col in anomalies.columns:
        anomalies = anomalies.sort_values(date_col)

    logger.info(
        "Isolation Forest: %d anomalies out of %d rows (contamination=%.2f)",
        len(anomalies), len(df), contamination,
    )
    return anomalies


# ── Prophet forecast ─────────────────────────────────────────────────────────

def forecast_with_prophet(
    df: pd.DataFrame,
    date_col: str,
    value_col: str,
    periods: int = 7,
    include_history: bool = False,
) -> dict[str, Any]:
    """
    Facebook Prophet ile zaman serisi tahmini.

    Args:
        df: Tarih ve değer kolonları içeren DataFrame.
        date_col: Tarih kolonu adı.
        value_col: Tahmin edilecek değer kolonu.
        periods: Kaç gün ileriye tahmin yapılacak.
        include_history: Geçmiş tahminleri de dahil et.

    Returns:
        Dict: {
            "forecast": [{"date": ..., "predicted": ..., "lower": ..., "upper": ...}],
            "trend_direction": "up" | "down" | "stable",
            "weekly_seasonality": bool,
            "model_metrics": {"mape": float, "rmse": float},
            "method": "prophet" | "linear_regression",
        }
    """
    if df.empty or date_col not in df.columns or value_col not in df.columns:
        return {}

    work = df[[date_col, value_col]].copy()
    work.columns = ["ds", "y"]
    work["ds"] = pd.to_datetime(work["ds"])
    work["y"] = pd.to_numeric(work["y"], errors="coerce")
    work = work.dropna().sort_values("ds")

    if len(work) < 10:
        logger.debug("forecast_with_prophet: not enough data (%d rows)", len(work))
        return {}

    try:
        from prophet import Prophet

        import logging as _logging
        _logging.getLogger("prophet").setLevel(_logging.WARNING)
        _logging.getLogger("cmdstanpy").setLevel(_logging.WARNING)

        model = Prophet(
            weekly_seasonality=True,
            daily_seasonality=False,
            yearly_seasonality=False,
        )
        model.fit(work)

        future = model.make_future_dataframe(periods=periods)
        forecast_df = model.predict(future)

        result_df = forecast_df if include_history else forecast_df.tail(periods)

        predictions = []
        for _, row in result_df.iterrows():
            predictions.append({
                "date": str(row["ds"].date()),
                "predicted": round(float(row["yhat"]), 2),
                "lower": round(float(row["yhat_lower"]), 2),
                "upper": round(float(row["yhat_upper"]), 2),
            })

        # MAPE on in-sample predictions
        in_sample = forecast_df.head(len(work))
        actual = work["y"].values
        predicted = in_sample["yhat"].values
        non_zero = actual != 0
        if non_zero.any():
            mape = float(
                np.mean(np.abs((actual[non_zero] - predicted[non_zero]) / actual[non_zero])) * 100
            )
        else:
            mape = None

        residuals = actual - predicted
        rmse = float(np.sqrt(np.mean(residuals ** 2)))

        # Trend direction from last 7 yhat values
        last_n = forecast_df.tail(min(7, len(forecast_df)))["yhat"].values
        if len(last_n) >= 2:
            slope = (last_n[-1] - last_n[0]) / len(last_n)
            pct_change = slope / abs(last_n[0]) * 100 if last_n[0] != 0 else 0
            trend_direction = "up" if pct_change > 1 else ("down" if pct_change < -1 else "stable")
        else:
            trend_direction = "stable"

        weekly_seasonality = bool("weekly" in model.seasonalities)

        logger.info("Prophet forecast: %d periods, trend=%s", periods, trend_direction)
        return {
            "forecast": predictions,
            "trend_direction": trend_direction,
            "weekly_seasonality": weekly_seasonality,
            "model_metrics": {
                "mape": round(mape, 2) if mape is not None else None,
                "rmse": round(rmse, 2),
            },
            "method": "prophet",
        }

    except ImportError:
        logger.warning("Prophet not installed — falling back to linear forecast")
        fallback = calculate_simple_forecast(df, date_col, value_col, periods)
        if fallback.empty:
            return {}
        predictions = []
        for _, row in fallback.iterrows():
            d = row["date"]
            predictions.append({
                "date": str(d.date()) if hasattr(d, "date") else str(d),
                "predicted": round(float(row["forecast"]), 2),
                "lower": round(float(row["lower_bound"]), 2),
                "upper": round(float(row["upper_bound"]), 2),
            })

        if len(predictions) >= 2:
            td = "up" if predictions[-1]["predicted"] > predictions[0]["predicted"] * 1.01 else (
                "down" if predictions[-1]["predicted"] < predictions[0]["predicted"] * 0.99 else "stable"
            )
        else:
            td = "stable"

        return {
            "forecast": predictions,
            "trend_direction": td,
            "weekly_seasonality": False,
            "model_metrics": {"mape": None, "rmse": None},
            "method": "linear_regression",
        }


# ── STL Decomposition ───────────────────────────────────────────────────────

def decompose_time_series(
    df: pd.DataFrame,
    date_col: str,
    value_col: str,
    period: int = 7,
) -> dict[str, Any]:
    """
    STL (Seasonal-Trend Decomposition using Loess) ile zaman serisi ayrıştırma.

    Args:
        df: Tarih ve değer kolonları içeren DataFrame.
        date_col: Tarih kolonu adı.
        value_col: Ayrıştırılacak değer kolonu.
        period: Mevsimsel periyot (gün, varsayılan 7).

    Returns:
        Dict: {
            "trend": list[float],
            "seasonal": list[float],
            "residual": list[float],
            "is_seasonal": bool,
            "trend_direction": str,
            "seasonal_strength": float,
        }
    """
    if df.empty or date_col not in df.columns or value_col not in df.columns:
        return {}

    work = df[[date_col, value_col]].copy()
    work[date_col] = pd.to_datetime(work[date_col])
    work[value_col] = pd.to_numeric(work[value_col], errors="coerce")
    work = work.dropna().sort_values(date_col)

    if len(work) < 2 * period:
        logger.warning(
            "STL decomposition: insufficient data (%d rows, need %d)",
            len(work), 2 * period,
        )
        return {}

    from statsmodels.tsa.seasonal import STL

    series = work.set_index(date_col)[value_col]
    # Handle duplicate dates by averaging
    series = series.groupby(level=0).mean()
    # Ensure daily frequency with no gaps
    full_range = pd.date_range(series.index.min(), series.index.max(), freq="D")
    series = series.reindex(full_range).interpolate(method="linear").ffill().bfill()

    if len(series) < 2 * period:
        return {}

    stl = STL(series, period=period, robust=True)
    result = stl.fit()

    trend = result.trend.values
    seasonal = result.seasonal.values
    residual = result.resid.values

    # Seasonal strength: 1 - var(residual) / var(seasonal + residual)
    var_resid = np.var(residual)
    var_seasonal_resid = np.var(seasonal + residual)
    seasonal_strength = float(
        max(0.0, 1.0 - var_resid / var_seasonal_resid)
        if var_seasonal_resid > 0
        else 0.0
    )

    # Trend direction
    if len(trend) >= 2 and abs(trend[0]) > 0:
        growth = (trend[-1] - trend[0]) / abs(trend[0]) * 100
        trend_direction = "up" if growth > 1 else ("down" if growth < -1 else "stable")
    else:
        trend_direction = "stable"

    logger.info(
        "STL decomposition: seasonal_strength=%.3f, trend=%s",
        seasonal_strength, trend_direction,
    )
    return {
        "trend": [round(float(v), 2) for v in trend],
        "seasonal": [round(float(v), 2) for v in seasonal],
        "residual": [round(float(v), 2) for v in residual],
        "is_seasonal": seasonal_strength > 0.1,
        "trend_direction": trend_direction,
        "seasonal_strength": round(seasonal_strength, 4),
    }


# ── RFM Segmentation ────────────────────────────────────────────────────────

def calculate_sector_comparison(
    company_id: int,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """
    Compare a company's KPIs against anonymized sector peers (same segment).

    Queries all companies sharing the same segment, calculates KPIs per company,
    ranks the target company, and anonymizes peer names (Firma A, B, C...).

    Args:
        company_id: The target company to benchmark.
        start_date: Period start date (ISO).
        end_date: Period end date (ISO).

    Returns:
        Dict with keys: company_rank, total_in_sector, company_kpis,
        sector_avg, peers (anonymized list), sector_segment.
    """
    from src.tools.sql_tools import execute_query

    # Find the target company's segment
    seg_df = execute_query(
        """
        SELECT c.id, c.name, c.segment
        FROM companies c
        WHERE c.id = :cid
        """,
        {"cid": company_id},
    )
    if seg_df.empty:
        logger.warning("calculate_sector_comparison: company %d not found", company_id)
        return {}

    segment = seg_df.iloc[0]["segment"]

    # Get all companies in same segment
    peers_df = execute_query(
        """
        SELECT c.id, c.name
        FROM companies c
        WHERE c.segment = :segment AND c.is_active = 1
        """,
        {"segment": segment},
    )
    if peers_df.empty or len(peers_df) < 2:
        logger.info("calculate_sector_comparison: not enough peers for segment '%s'", segment)
        return {"note": f"Sektörde yeterli karşılaştırma firması yok ({segment})"}

    peer_ids = peers_df["id"].tolist()

    # Calculate KPIs for all companies in segment
    placeholders = ", ".join(str(pid) for pid in peer_ids)
    kpi_df = execute_query(
        f"""
        SELECT
            company_id,
            SUM(sales) as total_revenue,
            SUM(profit) as total_profit,
            COUNT(DISTINCT order_id) as total_orders,
            COUNT(DISTINCT customer_id) as unique_customers
        FROM orders
        WHERE order_date BETWEEN :start AND :end
          AND company_id IN ({placeholders})
        GROUP BY company_id
        """,
        {"start": start_date, "end": end_date},
    )

    if kpi_df.empty:
        return {"note": "Sektör verileri bulunamadı"}

    for col in ["total_revenue", "total_profit"]:
        kpi_df[col] = pd.to_numeric(kpi_df[col], errors="coerce").fillna(0)
    kpi_df["profit_margin_pct"] = np.where(
        kpi_df["total_revenue"] > 0,
        (kpi_df["total_profit"] / kpi_df["total_revenue"] * 100).round(2),
        0.0,
    )
    kpi_df["avg_order_value"] = np.where(
        kpi_df["total_orders"] > 0,
        (kpi_df["total_revenue"] / kpi_df["total_orders"]).round(2),
        0.0,
    )

    # Rank by revenue
    kpi_df = kpi_df.sort_values("total_revenue", ascending=False).reset_index(drop=True)
    kpi_df["rank"] = range(1, len(kpi_df) + 1)

    # Extract target company KPIs
    target_row = kpi_df[kpi_df["company_id"] == company_id]
    if target_row.empty:
        company_kpis = {"note": "Bu dönemde firma verisi yok"}
        company_rank = None
    else:
        row = target_row.iloc[0]
        company_kpis = {
            "total_revenue": round(float(row["total_revenue"]), 2),
            "total_profit": round(float(row["total_profit"]), 2),
            "total_orders": int(row["total_orders"]),
            "unique_customers": int(row["unique_customers"]),
            "profit_margin_pct": round(float(row["profit_margin_pct"]), 2),
            "avg_order_value": round(float(row["avg_order_value"]), 2),
        }
        company_rank = int(row["rank"])

    # Sector averages
    sector_avg = {
        "avg_revenue": round(float(kpi_df["total_revenue"].mean()), 2),
        "avg_profit": round(float(kpi_df["total_profit"].mean()), 2),
        "avg_orders": round(float(kpi_df["total_orders"].mean()), 1),
        "avg_margin_pct": round(float(kpi_df["profit_margin_pct"].mean()), 2),
    }

    # Anonymized peers (exclude target company)
    peer_rows = kpi_df[kpi_df["company_id"] != company_id]
    labels = iter("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    peers = []
    for _, pr in peer_rows.iterrows():
        peers.append({
            "label": f"Firma {next(labels)}",
            "total_revenue": round(float(pr["total_revenue"]), 2),
            "total_profit": round(float(pr["total_profit"]), 2),
            "total_orders": int(pr["total_orders"]),
            "profit_margin_pct": round(float(pr["profit_margin_pct"]), 2),
            "rank": int(pr["rank"]),
        })

    logger.info(
        "Sector comparison: company %d ranked %s/%d in segment '%s'",
        company_id, company_rank, len(kpi_df), segment,
    )

    return {
        "sector_segment": segment,
        "company_rank": company_rank,
        "total_in_sector": len(kpi_df),
        "company_kpis": company_kpis,
        "sector_avg": sector_avg,
        "peers": peers,
    }


def calculate_rfm_segments(
    df: pd.DataFrame,
    customer_col: str = "customer_id",
    date_col: str = "order_date",
    revenue_col: str = "sales",
    reference_date: str | None = None,
) -> pd.DataFrame:
    """
    RFM (Recency, Frequency, Monetary) müşteri segmentasyonu.

    Args:
        df: Müşteri siparişlerini içeren DataFrame.
        customer_col: Müşteri ID kolonu.
        date_col: Sipariş tarih kolonu.
        revenue_col: Gelir kolonu.
        reference_date: Referans tarih (varsayılan: max tarih + 1 gün).

    Returns:
        DataFrame: customer_id, recency_days, frequency, monetary,
                   r_score, f_score, m_score, rfm_segment, segment_label
    """
    required = {customer_col, date_col, revenue_col}
    if df.empty or not required.issubset(df.columns):
        logger.warning(
            "calculate_rfm_segments: missing columns %s",
            required - set(df.columns) if not df.empty else required,
        )
        return pd.DataFrame()

    work = df.copy()
    work[date_col] = pd.to_datetime(work[date_col])
    work[revenue_col] = pd.to_numeric(work[revenue_col], errors="coerce").fillna(0)

    if reference_date:
        ref = pd.to_datetime(reference_date)
    else:
        ref = work[date_col].max() + pd.Timedelta(days=1)

    rfm = work.groupby(customer_col).agg(
        recency_days=(date_col, lambda x: (ref - x.max()).days),
        frequency=(date_col, "count"),
        monetary=(revenue_col, "sum"),
    ).reset_index()

    if len(rfm) < 5:
        # Not enough customers for quantile-based scoring
        rfm["r_score"] = 3
        rfm["f_score"] = 3
        rfm["m_score"] = 3
    else:
        # Use rank(method="first") to guarantee unique values for qcut
        rfm["r_score"] = pd.qcut(
            rfm["recency_days"].rank(method="first"), q=5, labels=[5, 4, 3, 2, 1],
        ).astype(int)
        rfm["f_score"] = pd.qcut(
            rfm["frequency"].rank(method="first"), q=5, labels=[1, 2, 3, 4, 5],
        ).astype(int)
        rfm["m_score"] = pd.qcut(
            rfm["monetary"].rank(method="first"), q=5, labels=[1, 2, 3, 4, 5],
        ).astype(int)

    rfm["rfm_segment"] = (
        rfm["r_score"].astype(str) + rfm["f_score"].astype(str) + rfm["m_score"].astype(str)
    )

    def _label(row: pd.Series) -> str:
        r, f, m = row["r_score"], row["f_score"], row["m_score"]
        if r >= 4 and f >= 4 and m >= 4:
            return "Champions"
        if r >= 3 and f >= 3 and m >= 3:
            return "Loyal"
        if r >= 4 and f <= 2:
            return "New"
        if r <= 2 and f >= 3:
            return "At Risk"
        if r <= 2 and f <= 2:
            return "Lost"
        return "Potential"

    rfm["segment_label"] = rfm.apply(_label, axis=1)
    rfm["recency_days"] = rfm["recency_days"].astype(int)
    rfm["frequency"] = rfm["frequency"].astype(int)
    rfm["monetary"] = rfm["monetary"].round(2)

    logger.info(
        "RFM segmentation: %d customers across %d segments",
        len(rfm), rfm["segment_label"].nunique(),
    )
    return rfm
