"""
Tests for analysis_tools.py.

No database required — all tests use in-memory DataFrames.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tools.analysis_tools import (
    calculate_category_performance,
    calculate_period_comparison,
    calculate_rfm_segments,
    calculate_simple_forecast,
    calculate_trend,
    decompose_time_series,
    detect_anomalies_iqr,
    detect_anomalies_isolation_forest,
    detect_anomalies_zscore,
    forecast_with_prophet,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def upward_sales_df() -> pd.DataFrame:
    """20-day linearly increasing daily sales."""
    dates = pd.date_range("2024-01-01", periods=20, freq="D")
    sales = np.linspace(100, 300, 20) + np.random.default_rng(0).normal(0, 5, 20)
    return pd.DataFrame({"order_date": dates, "total_sales": sales})


@pytest.fixture
def flat_sales_df() -> pd.DataFrame:
    """20-day constant sales (no trend)."""
    dates = pd.date_range("2024-01-01", periods=20, freq="D")
    return pd.DataFrame({"order_date": dates, "total_sales": np.full(20, 200.0)})


@pytest.fixture
def sales_with_anomaly_df() -> pd.DataFrame:
    """20-day sales with one extreme outlier."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2024-01-01", periods=20, freq="D")
    sales = rng.normal(200, 10, 20)
    sales[10] = 5000.0   # extreme outlier
    return pd.DataFrame({"order_date": dates, "total_sales": sales})


@pytest.fixture
def category_df() -> pd.DataFrame:
    return pd.DataFrame({
        "category": ["Technology", "Furniture", "Office Supplies"],
        "total_sales": [5000.0, 3000.0, 2000.0],
        "total_profit": [1000.0, -300.0, 400.0],
        "order_count": [50, 20, 80],
        "avg_discount": [0.1, 0.2, 0.05],
    })


# ── calculate_trend ───────────────────────────────────────────────────────────

class TestCalculateTrend:
    def test_returns_dict(self, upward_sales_df):
        result = calculate_trend(upward_sales_df, "order_date", "total_sales")
        assert isinstance(result, dict)

    def test_upward_direction(self, upward_sales_df):
        result = calculate_trend(upward_sales_df, "order_date", "total_sales")
        assert result["direction"] == "up"

    def test_positive_growth_rate(self, upward_sales_df):
        result = calculate_trend(upward_sales_df, "order_date", "total_sales")
        assert result["growth_rate_pct"] > 0

    def test_stable_direction(self, flat_sales_df):
        result = calculate_trend(flat_sales_df, "order_date", "total_sales")
        assert result["direction"] == "stable"

    def test_sma_keys_present(self, upward_sales_df):
        result = calculate_trend(upward_sales_df, "order_date", "total_sales", sma_windows=(7,))
        assert "sma_7" in result

    def test_empty_df(self):
        result = calculate_trend(pd.DataFrame(), "order_date", "total_sales")
        assert result["direction"] == "stable"
        assert result["growth_rate_pct"] == 0.0

    def test_missing_column(self, upward_sales_df):
        result = calculate_trend(upward_sales_df, "order_date", "nonexistent_col")
        assert result["direction"] == "stable"


# ── detect_anomalies_zscore ───────────────────────────────────────────────────

class TestDetectAnomaliesZscore:
    def test_detects_known_outlier(self, sales_with_anomaly_df):
        anomalies = detect_anomalies_zscore(
            sales_with_anomaly_df, "total_sales", threshold=2.5
        )
        assert not anomalies.empty
        # The seeded outlier should be among them
        assert anomalies["total_sales"].max() > 1000

    def test_no_anomalies_in_normal_data(self, flat_sales_df):
        # Constant data has zero std — function should return empty
        anomalies = detect_anomalies_zscore(flat_sales_df, "total_sales", threshold=2.5)
        assert anomalies.empty

    def test_returns_dataframe(self, sales_with_anomaly_df):
        result = detect_anomalies_zscore(sales_with_anomaly_df, "total_sales")
        assert isinstance(result, pd.DataFrame)

    def test_zscore_column_added(self, sales_with_anomaly_df):
        result = detect_anomalies_zscore(sales_with_anomaly_df, "total_sales", threshold=2.5)
        if not result.empty:
            assert "z_score" in result.columns

    def test_empty_df(self):
        result = detect_anomalies_zscore(pd.DataFrame(), "total_sales")
        assert result.empty


# ── detect_anomalies_iqr ──────────────────────────────────────────────────────

class TestDetectAnomaliesIqr:
    def test_detects_outlier(self, sales_with_anomaly_df):
        result = detect_anomalies_iqr(sales_with_anomaly_df, "total_sales")
        assert not result.empty

    def test_fence_columns_added(self, sales_with_anomaly_df):
        result = detect_anomalies_iqr(sales_with_anomaly_df, "total_sales")
        if not result.empty:
            assert "lower_fence" in result.columns
            assert "upper_fence" in result.columns

    def test_empty_df(self):
        result = detect_anomalies_iqr(pd.DataFrame(), "total_sales")
        assert result.empty


# ── calculate_period_comparison ───────────────────────────────────────────────

class TestCalculatePeriodComparison:
    def test_returns_dict(self):
        curr = pd.DataFrame({"total_sales": [1200.0], "total_profit": [300.0], "total_orders": [10]})
        prev = pd.DataFrame({"total_sales": [1000.0], "total_profit": [250.0], "total_orders": [8]})
        result = calculate_period_comparison(curr, prev)
        assert isinstance(result, dict)

    def test_positive_growth(self):
        curr = pd.DataFrame({"total_sales": [1200.0], "total_profit": [300.0], "total_orders": [10]})
        prev = pd.DataFrame({"total_sales": [1000.0], "total_profit": [250.0], "total_orders": [8]})
        result = calculate_period_comparison(curr, prev)
        assert result["total_sales_change_pct"] == pytest.approx(20.0, rel=0.01)

    def test_negative_growth(self):
        curr = pd.DataFrame({"total_sales": [800.0], "total_profit": [200.0], "total_orders": [6]})
        prev = pd.DataFrame({"total_sales": [1000.0], "total_profit": [250.0], "total_orders": [8]})
        result = calculate_period_comparison(curr, prev)
        assert result["total_sales_change_pct"] == pytest.approx(-20.0, rel=0.01)

    def test_empty_dfs(self):
        result = calculate_period_comparison(pd.DataFrame(), pd.DataFrame())
        assert result == {}

    def test_custom_metrics(self):
        curr = pd.DataFrame({"revenue": [500.0]})
        prev = pd.DataFrame({"revenue": [400.0]})
        result = calculate_period_comparison(curr, prev, metrics=["revenue"])
        assert "revenue_change_pct" in result


# ── calculate_category_performance ───────────────────────────────────────────

class TestCalculateCategoryPerformance:
    def test_returns_dataframe(self, category_df):
        result = calculate_category_performance(category_df)
        assert isinstance(result, pd.DataFrame)

    def test_sales_share_sums_to_100(self, category_df):
        result = calculate_category_performance(category_df)
        assert result["sales_share_pct"].sum() == pytest.approx(100.0, abs=0.1)

    def test_performance_rank_column(self, category_df):
        result = calculate_category_performance(category_df)
        assert "performance_rank" in result.columns

    def test_technology_ranks_first(self, category_df):
        result = calculate_category_performance(category_df)
        top = result[result["performance_rank"] == 1]["category"].iloc[0]
        assert top == "Technology"

    def test_empty_df(self):
        result = calculate_category_performance(pd.DataFrame())
        assert result.empty

    def test_profit_margin_calculated(self, category_df):
        result = calculate_category_performance(category_df)
        assert "profit_margin_pct" in result.columns
        tech_margin = result[result["category"] == "Technology"]["profit_margin_pct"].iloc[0]
        assert tech_margin == pytest.approx(20.0, rel=0.01)


# ── calculate_simple_forecast ─────────────────────────────────────────────────

class TestCalculateSimpleForecast:
    def test_returns_dataframe(self, upward_sales_df):
        result = calculate_simple_forecast(upward_sales_df, "order_date", "total_sales", periods=7)
        assert isinstance(result, pd.DataFrame)

    def test_correct_number_of_periods(self, upward_sales_df):
        result = calculate_simple_forecast(upward_sales_df, "order_date", "total_sales", periods=5)
        assert len(result) == 5

    def test_required_columns(self, upward_sales_df):
        result = calculate_simple_forecast(upward_sales_df, "order_date", "total_sales", periods=7)
        assert set(result.columns) >= {"date", "forecast", "lower_bound", "upper_bound"}

    def test_forecast_after_last_date(self, upward_sales_df):
        last_date = upward_sales_df["order_date"].max()
        result = calculate_simple_forecast(upward_sales_df, "order_date", "total_sales", periods=3)
        assert result["date"].min() > last_date

    def test_empty_df(self):
        result = calculate_simple_forecast(pd.DataFrame(), "order_date", "total_sales")
        assert result.empty


# ── Fixtures for new tests ───────────────────────────────────────────────────

@pytest.fixture
def seasonal_sales_df() -> pd.DataFrame:
    """30-day sales with weekly seasonality pattern."""
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    # Base trend + weekly pattern
    base = np.linspace(100, 200, 30)
    seasonal = 30 * np.sin(2 * np.pi * np.arange(30) / 7)
    noise = np.random.default_rng(42).normal(0, 5, 30)
    sales = base + seasonal + noise
    return pd.DataFrame({"order_date": dates, "total_sales": sales, "total_profit": sales * 0.2})


@pytest.fixture
def customer_orders_df() -> pd.DataFrame:
    """Simulated per-order customer data for RFM testing."""
    rng = np.random.default_rng(42)
    n = 100
    return pd.DataFrame({
        "customer_id": [f"CUST-{rng.integers(1, 21):02d}" for _ in range(n)],
        "order_date": pd.date_range("2024-01-01", periods=n, freq="D")[:n],
        "sales": rng.uniform(10, 500, n).round(2),
    })


# ── detect_anomalies_isolation_forest ────────────────────────────────────────

class TestDetectAnomaliesIsolationForest:
    def test_detects_known_anomaly(self, sales_with_anomaly_df):
        result = detect_anomalies_isolation_forest(
            sales_with_anomaly_df, ["total_sales"], contamination=0.1,
        )
        assert not result.empty
        assert result["total_sales"].max() > 1000

    def test_returns_dataframe(self, sales_with_anomaly_df):
        result = detect_anomalies_isolation_forest(
            sales_with_anomaly_df, ["total_sales"],
        )
        assert isinstance(result, pd.DataFrame)

    def test_has_anomaly_score_column(self, sales_with_anomaly_df):
        result = detect_anomalies_isolation_forest(
            sales_with_anomaly_df, ["total_sales"],
        )
        if not result.empty:
            assert "anomaly_score" in result.columns
            assert "is_anomaly" in result.columns

    def test_multivariate(self, seasonal_sales_df):
        result = detect_anomalies_isolation_forest(
            seasonal_sales_df, ["total_sales", "total_profit"],
        )
        assert isinstance(result, pd.DataFrame)

    def test_empty_df(self):
        result = detect_anomalies_isolation_forest(pd.DataFrame(), ["total_sales"])
        assert result.empty

    def test_insufficient_data(self):
        df = pd.DataFrame({"total_sales": [1, 2, 3]})
        result = detect_anomalies_isolation_forest(df, ["total_sales"])
        assert result.empty

    def test_missing_columns(self, sales_with_anomaly_df):
        result = detect_anomalies_isolation_forest(
            sales_with_anomaly_df, ["nonexistent"],
        )
        assert result.empty


# ── forecast_with_prophet ────────────────────────────────────────────────────

class TestForecastWithProphet:
    def test_returns_dict(self, upward_sales_df):
        result = forecast_with_prophet(upward_sales_df, "order_date", "total_sales", periods=3)
        assert isinstance(result, dict)

    def test_has_forecast_key(self, upward_sales_df):
        result = forecast_with_prophet(upward_sales_df, "order_date", "total_sales", periods=3)
        assert "forecast" in result
        assert len(result["forecast"]) == 3

    def test_has_method_key(self, upward_sales_df):
        result = forecast_with_prophet(upward_sales_df, "order_date", "total_sales", periods=3)
        assert "method" in result
        assert result["method"] in ("prophet", "linear_regression")

    def test_has_trend_direction(self, upward_sales_df):
        result = forecast_with_prophet(upward_sales_df, "order_date", "total_sales", periods=3)
        assert result["trend_direction"] in ("up", "down", "stable")

    def test_has_model_metrics(self, upward_sales_df):
        result = forecast_with_prophet(upward_sales_df, "order_date", "total_sales", periods=5)
        assert "model_metrics" in result

    def test_forecast_entries_have_keys(self, upward_sales_df):
        result = forecast_with_prophet(upward_sales_df, "order_date", "total_sales", periods=3)
        for entry in result["forecast"]:
            assert "date" in entry
            assert "predicted" in entry
            assert "lower" in entry
            assert "upper" in entry

    def test_empty_df(self):
        result = forecast_with_prophet(pd.DataFrame(), "order_date", "total_sales")
        assert result == {}

    def test_insufficient_data(self):
        df = pd.DataFrame({
            "order_date": pd.date_range("2024-01-01", periods=3),
            "total_sales": [100, 200, 300],
        })
        result = forecast_with_prophet(df, "order_date", "total_sales")
        assert result == {}


# ── decompose_time_series ────────────────────────────────────────────────────

class TestDecomposeTimeSeries:
    def test_returns_dict(self, seasonal_sales_df):
        result = decompose_time_series(seasonal_sales_df, "order_date", "total_sales", period=7)
        assert isinstance(result, dict)

    def test_has_components(self, seasonal_sales_df):
        result = decompose_time_series(seasonal_sales_df, "order_date", "total_sales", period=7)
        assert "trend" in result
        assert "seasonal" in result
        assert "residual" in result

    def test_seasonal_strength_calculated(self, seasonal_sales_df):
        result = decompose_time_series(seasonal_sales_df, "order_date", "total_sales", period=7)
        assert "seasonal_strength" in result
        assert 0 <= result["seasonal_strength"] <= 1

    def test_trend_direction(self, seasonal_sales_df):
        result = decompose_time_series(seasonal_sales_df, "order_date", "total_sales", period=7)
        assert result["trend_direction"] in ("up", "down", "stable")

    def test_is_seasonal_flag(self, seasonal_sales_df):
        result = decompose_time_series(seasonal_sales_df, "order_date", "total_sales", period=7)
        assert isinstance(result["is_seasonal"], bool)

    def test_empty_df(self):
        result = decompose_time_series(pd.DataFrame(), "order_date", "total_sales")
        assert result == {}

    def test_insufficient_data(self):
        df = pd.DataFrame({
            "order_date": pd.date_range("2024-01-01", periods=5),
            "total_sales": [100, 200, 150, 180, 120],
        })
        result = decompose_time_series(df, "order_date", "total_sales", period=7)
        assert result == {}

    def test_components_same_length(self, seasonal_sales_df):
        result = decompose_time_series(seasonal_sales_df, "order_date", "total_sales", period=7)
        if result:
            assert len(result["trend"]) == len(result["seasonal"]) == len(result["residual"])


# ── calculate_rfm_segments ───────────────────────────────────────────────────

class TestCalculateRfmSegments:
    def test_returns_dataframe(self, customer_orders_df):
        result = calculate_rfm_segments(customer_orders_df)
        assert isinstance(result, pd.DataFrame)

    def test_has_required_columns(self, customer_orders_df):
        result = calculate_rfm_segments(customer_orders_df)
        for col in ["customer_id", "recency_days", "frequency", "monetary",
                     "r_score", "f_score", "m_score", "rfm_segment", "segment_label"]:
            assert col in result.columns, f"Missing column: {col}"

    def test_scores_in_range(self, customer_orders_df):
        result = calculate_rfm_segments(customer_orders_df)
        for col in ["r_score", "f_score", "m_score"]:
            assert result[col].between(1, 5).all(), f"{col} values not in 1-5 range"

    def test_segment_labels_valid(self, customer_orders_df):
        result = calculate_rfm_segments(customer_orders_df)
        valid_labels = {"Champions", "Loyal", "New", "At Risk", "Lost", "Potential"}
        assert set(result["segment_label"].unique()).issubset(valid_labels)

    def test_unique_customers(self, customer_orders_df):
        result = calculate_rfm_segments(customer_orders_df)
        assert len(result) == customer_orders_df["customer_id"].nunique()

    def test_empty_df(self):
        result = calculate_rfm_segments(pd.DataFrame())
        assert result.empty

    def test_missing_columns(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        result = calculate_rfm_segments(df)
        assert result.empty

    def test_custom_reference_date(self, customer_orders_df):
        result = calculate_rfm_segments(
            customer_orders_df, reference_date="2024-06-01",
        )
        assert not result.empty
        assert (result["recency_days"] >= 0).all()
