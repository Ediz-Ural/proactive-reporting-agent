"""
SQL query tools for the Data Collector Agent.

All functions return pandas DataFrames or plain dicts.
The DB engine is constructed from config/settings.py and cached at module level.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from functools import lru_cache

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from config.settings import settings

logger = logging.getLogger(__name__)


# ── Engine ────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_db_engine() -> Engine:
    """
    Create and cache a SQLAlchemy engine.

    Uses settings.database_url which switches between SQLite and MySQL
    based on the DB_TYPE environment variable.

    Returns:
        Cached SQLAlchemy Engine instance.
    """
    url = settings.database_url
    logger.info("Creating database engine: %s", url.split("@")[-1])  # hide credentials
    engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False,
    )
    return engine


# ── Connection test ───────────────────────────────────────────────────────────

def test_db_connection() -> dict:
    """
    Test the database connection and return status info.

    Returns:
        Dict with keys: connected (bool), db_type, message, and error (if any).
    """
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_type = settings.DB_TYPE
        return {
            "connected": True,
            "db_type": db_type,
            "message": f"Successfully connected to {db_type} database",
        }
    except Exception as exc:
        return {
            "connected": False,
            "db_type": settings.DB_TYPE,
            "message": "Connection failed",
            "error": str(exc),
        }


# ── Generic executor ──────────────────────────────────────────────────────────

def execute_query(query: str, params: dict | None = None) -> pd.DataFrame:
    """
    Execute a raw SQL query and return the result as a DataFrame.

    Args:
        query:  SQL string (may contain :named placeholders).
        params: Optional dict of bind parameters.

    Returns:
        Query result as a pandas DataFrame.

    Raises:
        RuntimeError: If the query fails.
    """
    engine = get_db_engine()
    try:
        with engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
        logger.debug("Query returned %d rows", len(df))
        return df
    except Exception as exc:
        logger.error("Query execution failed: %s\nQuery: %s", exc, query)
        raise RuntimeError(f"Database query failed: {exc}") from exc


# ── Domain queries ─────────────────────────────────────────────────────────────

def get_sales_by_period(start_date: str | date, end_date: str | date) -> pd.DataFrame:
    """
    Return daily aggregated sales for the given date range.

    Args:
        start_date: First day of the period (inclusive).
        end_date:   Last day of the period (inclusive).

    Returns:
        DataFrame with columns: [order_date, total_sales, total_profit,
        total_orders, total_quantity].
    """
    query = """
        SELECT
            order_date,
            ROUND(SUM(sales), 2)    AS total_sales,
            ROUND(SUM(profit), 2)   AS total_profit,
            COUNT(DISTINCT order_id) AS total_orders,
            SUM(quantity)           AS total_quantity
        FROM orders
        WHERE order_date BETWEEN :start_date AND :end_date
        GROUP BY order_date
        ORDER BY order_date
    """
    df = execute_query(query, {"start_date": str(start_date), "end_date": str(end_date)})
    if not df.empty:
        df["order_date"] = pd.to_datetime(df["order_date"])
    return df


def get_sales_by_category(start_date: str | date, end_date: str | date) -> pd.DataFrame:
    """
    Return aggregated sales broken down by category and sub-category.

    Args:
        start_date: First day of the period (inclusive).
        end_date:   Last day of the period (inclusive).

    Returns:
        DataFrame with columns: [category, sub_category, total_sales,
        total_profit, profit_margin_pct, order_count, avg_discount].
    """
    query = """
        SELECT
            category,
            sub_category,
            ROUND(SUM(sales), 2)                               AS total_sales,
            ROUND(SUM(profit), 2)                              AS total_profit,
            ROUND(SUM(profit) / NULLIF(SUM(sales), 0) * 100, 2) AS profit_margin_pct,
            COUNT(DISTINCT order_id)                           AS order_count,
            ROUND(AVG(discount), 3)                            AS avg_discount
        FROM orders
        WHERE order_date BETWEEN :start_date AND :end_date
        GROUP BY category, sub_category
        ORDER BY total_sales DESC
    """
    return execute_query(query, {"start_date": str(start_date), "end_date": str(end_date)})


def get_top_products(
    start_date: str | date,
    end_date: str | date,
    limit: int = 10,
) -> pd.DataFrame:
    """
    Return the top-selling products by revenue.

    Args:
        start_date: First day of the period (inclusive).
        end_date:   Last day of the period (inclusive).
        limit:      Number of top products to return.

    Returns:
        DataFrame with columns: [product_id, product_name, category,
        sub_category, total_sales, total_profit, total_quantity, order_count].
    """
    query = """
        SELECT
            product_id,
            product_name,
            category,
            sub_category,
            ROUND(SUM(sales), 2)    AS total_sales,
            ROUND(SUM(profit), 2)   AS total_profit,
            SUM(quantity)           AS total_quantity,
            COUNT(DISTINCT order_id) AS order_count
        FROM orders
        WHERE order_date BETWEEN :start_date AND :end_date
        GROUP BY product_id, product_name, category, sub_category
        ORDER BY total_sales DESC
        LIMIT :limit
    """
    return execute_query(
        query,
        {"start_date": str(start_date), "end_date": str(end_date), "limit": limit},
    )


def get_customer_metrics(start_date: str | date, end_date: str | date) -> pd.DataFrame:
    """
    Return per-segment and per-customer aggregated metrics.

    Args:
        start_date: First day of the period (inclusive).
        end_date:   Last day of the period (inclusive).

    Returns:
        DataFrame with columns: [segment, unique_customers, total_orders,
        total_revenue, avg_order_value, avg_revenue_per_customer].
    """
    query = """
        SELECT
            segment,
            COUNT(DISTINCT customer_id)                              AS unique_customers,
            COUNT(DISTINCT order_id)                                 AS total_orders,
            ROUND(SUM(sales), 2)                                     AS total_revenue,
            ROUND(SUM(sales) / NULLIF(COUNT(DISTINCT order_id), 0), 2) AS avg_order_value,
            ROUND(SUM(sales) / NULLIF(COUNT(DISTINCT customer_id), 0), 2) AS avg_revenue_per_customer
        FROM orders
        WHERE order_date BETWEEN :start_date AND :end_date
        GROUP BY segment
        ORDER BY total_revenue DESC
    """
    return execute_query(query, {"start_date": str(start_date), "end_date": str(end_date)})


def get_weekly_summary(start_date: str | date, end_date: str | date) -> dict:
    """
    Return a single-dict summary of the key KPIs for the period.

    Args:
        start_date: First day of the period (inclusive).
        end_date:   Last day of the period (inclusive).

    Returns:
        Dict with keys: period, total_revenue, total_profit,
        profit_margin_pct, total_orders, avg_order_value,
        unique_customers, total_quantity, top_category.
    """
    query = """
        SELECT
            ROUND(SUM(sales), 2)                                     AS total_revenue,
            ROUND(SUM(profit), 2)                                    AS total_profit,
            COUNT(DISTINCT order_id)                                 AS total_orders,
            SUM(quantity)                                            AS total_quantity,
            COUNT(DISTINCT customer_id)                              AS unique_customers,
            ROUND(SUM(sales) / NULLIF(COUNT(DISTINCT order_id), 0), 2) AS avg_order_value
        FROM orders
        WHERE order_date BETWEEN :start_date AND :end_date
    """
    df = execute_query(query, {"start_date": str(start_date), "end_date": str(end_date)})

    # Best-selling category
    cat_query = """
        SELECT category, SUM(sales) AS cat_sales
        FROM orders
        WHERE order_date BETWEEN :start_date AND :end_date
        GROUP BY category
        ORDER BY cat_sales DESC
        LIMIT 1
    """
    cat_df = execute_query(cat_query, {"start_date": str(start_date), "end_date": str(end_date)})
    top_category = cat_df["category"].iloc[0] if not cat_df.empty else "N/A"

    row = df.iloc[0] if not df.empty else {}
    total_revenue = float(row.get("total_revenue") or 0)
    total_profit = float(row.get("total_profit") or 0)

    return {
        "period": f"{start_date} to {end_date}",
        "total_revenue": total_revenue,
        "total_profit": total_profit,
        "profit_margin_pct": round(total_profit / total_revenue * 100, 2) if total_revenue else 0.0,
        "total_orders": int(row.get("total_orders") or 0),
        "total_quantity": int(row.get("total_quantity") or 0),
        "avg_order_value": float(row.get("avg_order_value") or 0),
        "unique_customers": int(row.get("unique_customers") or 0),
        "top_category": top_category,
    }


def get_region_performance(start_date: str | date, end_date: str | date) -> pd.DataFrame:
    """
    Return sales and profit aggregated by region.

    Args:
        start_date: First day of the period (inclusive).
        end_date:   Last day of the period (inclusive).

    Returns:
        DataFrame with columns: [region, total_sales, total_profit, order_count].
    """
    query = """
        SELECT
            region,
            ROUND(SUM(sales), 2)    AS total_sales,
            ROUND(SUM(profit), 2)   AS total_profit,
            COUNT(DISTINCT order_id) AS order_count
        FROM orders
        WHERE order_date BETWEEN :start_date AND :end_date
        GROUP BY region
        ORDER BY total_sales DESC
    """
    return execute_query(query, {"start_date": str(start_date), "end_date": str(end_date)})
