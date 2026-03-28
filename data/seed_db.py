"""
Seed script: load Superstore Sales CSV into the database.

Usage:
    python data/seed_db.py                          # loads data/raw/superstore.csv
    python data/seed_db.py --csv path/to/file.csv  # custom path
    python data/seed_db.py --generate               # generate synthetic data (no CSV needed)
"""

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

# Allow running as a script from the project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.logging_config import setup_logging
from config.settings import settings
from src.tools.sql_tools import get_db_engine

setup_logging()
logger = logging.getLogger(__name__)


# ── Synthetic data generator ──────────────────────────────────────────────────

def generate_sample_data(n_rows: int = 5000) -> pd.DataFrame:
    """
    Generate a realistic Superstore-like dataset.

    Args:
        n_rows: Number of order-line rows to generate.

    Returns:
        DataFrame with the same schema as the real Superstore CSV.
    """
    rng = np.random.default_rng(42)

    segments = ["Consumer", "Corporate", "Home Office"]
    regions = ["East", "West", "Central", "South"]
    categories = {
        "Furniture": ["Bookcases", "Chairs", "Furnishings", "Tables"],
        "Office Supplies": ["Appliances", "Art", "Binders", "Envelopes",
                            "Fasteners", "Labels", "Paper", "Storage", "Supplies"],
        "Technology": ["Accessories", "Copiers", "Machines", "Phones"],
    }
    ship_modes = ["First Class", "Second Class", "Standard Class", "Same Day"]
    cities_by_state = {
        "California": ["Los Angeles", "San Francisco", "San Diego"],
        "New York": ["New York City", "Buffalo", "Rochester"],
        "Texas": ["Houston", "Dallas", "Austin"],
        "Washington": ["Seattle", "Spokane", "Tacoma"],
        "Illinois": ["Chicago", "Aurora", "Naperville"],
    }

    order_dates = pd.date_range("2021-01-01", "2024-12-31", periods=n_rows)
    order_dates = pd.to_datetime(
        rng.choice(order_dates.astype(np.int64), n_rows)
    ).normalize()
    ship_delays = pd.to_timedelta(rng.integers(1, 8, n_rows), unit="D")
    ship_dates = order_dates + ship_delays

    states = rng.choice(list(cities_by_state.keys()), n_rows)
    cities = [
        rng.choice(cities_by_state[s]) for s in states
    ]

    cat_names = rng.choice(list(categories.keys()), n_rows)
    sub_cats = [
        rng.choice(categories[c]) for c in cat_names
    ]

    customer_ids = [f"CUS-{rng.integers(1000, 9999):04d}" for _ in range(n_rows)]
    order_ids = [f"CA-{d.year}-{rng.integers(100000, 999999)}"
                 for d in order_dates]
    product_ids = [f"PRD-{rng.integers(100, 999):03d}" for _ in range(n_rows)]

    base_sales = rng.lognormal(4.5, 1.2, n_rows)
    quantities = rng.integers(1, 15, n_rows)
    discounts = rng.choice([0.0, 0.1, 0.2, 0.3, 0.4, 0.5], n_rows,
                            p=[0.5, 0.2, 0.15, 0.08, 0.05, 0.02])
    profits = base_sales * rng.uniform(-0.2, 0.4, n_rows)

    df = pd.DataFrame({
        "order_id": order_ids,
        "order_date": order_dates,
        "ship_date": ship_dates,
        "ship_mode": rng.choice(ship_modes, n_rows),
        "customer_id": customer_ids,
        "customer_name": [f"Customer {cid}" for cid in customer_ids],
        "segment": rng.choice(segments, n_rows),
        "country": "United States",
        "city": cities,
        "state": states,
        "postal_code": rng.integers(10000, 99999, n_rows).astype(str),
        "region": rng.choice(regions, n_rows),
        "product_id": product_ids,
        "category": cat_names,
        "sub_category": sub_cats,
        "product_name": [f"{sc} Model {rng.integers(100, 999)}" for sc in sub_cats],
        "sales": np.round(base_sales, 2),
        "quantity": quantities,
        "discount": discounts,
        "profit": np.round(profits, 2),
    })

    # Inject a few intentional anomalies for testing
    df.loc[rng.integers(0, n_rows, 5), "sales"] = rng.uniform(5000, 20000, 5)
    df.loc[rng.integers(0, n_rows, 3), "profit"] = rng.uniform(-3000, -1000, 3)

    logger.info("Generated %d synthetic rows", len(df))
    return df


# ── CSV loader ────────────────────────────────────────────────────────────────

def load_csv(csv_path: str) -> pd.DataFrame:
    """
    Load and normalise the Kaggle Superstore CSV.

    Args:
        csv_path: Path to the CSV file.

    Returns:
        Cleaned DataFrame ready for DB insertion.
    """
    logger.info("Reading CSV: %s", csv_path)
    try:
        df = pd.read_csv(csv_path, encoding="latin-1")
    except UnicodeDecodeError:
        df = pd.read_csv(csv_path, encoding="utf-8")

    # Normalise column names
    df.columns = (
        df.columns
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("-", "_")
    )

    # Map common Kaggle Superstore column names
    rename_map = {
        "row_id": "row_id",
        "order_id": "order_id",
        "order_date": "order_date",
        "ship_date": "ship_date",
        "ship_mode": "ship_mode",
        "customer_id": "customer_id",
        "customer_name": "customer_name",
        "segment": "segment",
        "country": "country",
        "city": "city",
        "state": "state",
        "postal_code": "postal_code",
        "region": "region",
        "product_id": "product_id",
        "category": "category",
        "sub_category": "sub_category",
        "sub.category": "sub_category",
        "product_name": "product_name",
        "sales": "sales",
        "quantity": "quantity",
        "discount": "discount",
        "profit": "profit",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # Parse dates
    for col in ("order_date", "ship_date"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], dayfirst=False, errors="coerce")

    logger.info("Loaded %d rows from CSV", len(df))
    return df


# ── Database writer ───────────────────────────────────────────────────────────

REQUIRED_COLS = [
    "order_id", "order_date", "ship_date", "ship_mode",
    "customer_id", "segment", "country", "city", "state", "region",
    "product_id", "category", "sub_category", "product_name",
    "sales", "quantity", "discount", "profit",
]

DDL = """
CREATE TABLE IF NOT EXISTS orders (
    order_id        VARCHAR(30)     NOT NULL,
    order_date      DATE            NOT NULL,
    ship_date       DATE,
    ship_mode       VARCHAR(50),
    customer_id     VARCHAR(30),
    customer_name   VARCHAR(100),
    segment         VARCHAR(30),
    country         VARCHAR(60),
    city            VARCHAR(60),
    state           VARCHAR(60),
    postal_code     VARCHAR(10),
    region          VARCHAR(20),
    product_id      VARCHAR(30)     NOT NULL,
    category        VARCHAR(60),
    sub_category    VARCHAR(60),
    product_name    VARCHAR(250),
    sales           DECIMAL(12, 2)  NOT NULL DEFAULT 0,
    quantity        INT             NOT NULL DEFAULT 0,
    discount        DECIMAL(5, 2)   NOT NULL DEFAULT 0,
    profit          DECIMAL(12, 2)  NOT NULL DEFAULT 0,
    PRIMARY KEY (order_id, product_id)
)
"""

def _get_index_statements(db_type: str) -> list[str]:
    """Return CREATE INDEX statements compatible with the target DB engine."""
    indexes = [
        ("idx_order_date", "orders", "order_date"),
        ("idx_category", "orders", "category"),
        ("idx_customer", "orders", "customer_id"),
        ("idx_region", "orders", "region"),
        ("idx_segment", "orders", "segment"),
    ]
    if db_type == "mysql":
        # MySQL: CREATE INDEX ... ON ... — drop first if exists
        stmts = []
        for name, table, col in indexes:
            stmts.append(
                f"CREATE INDEX {name} ON {table}({col})"
            )
        return stmts
    # SQLite supports IF NOT EXISTS
    return [
        f"CREATE INDEX IF NOT EXISTS {name} ON {table}({col})"
        for name, table, col in indexes
    ]


# Keep legacy INDEXES for backward compat (used in tests that import it)
INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_order_date   ON orders(order_date)",
    "CREATE INDEX IF NOT EXISTS idx_category      ON orders(category)",
    "CREATE INDEX IF NOT EXISTS idx_customer      ON orders(customer_id)",
    "CREATE INDEX IF NOT EXISTS idx_region        ON orders(region)",
    "CREATE INDEX IF NOT EXISTS idx_segment       ON orders(segment)",
]


def seed_database(df: pd.DataFrame) -> None:
    """
    Create the orders table and bulk-insert the DataFrame.

    Args:
        df: Cleaned DataFrame with at least all REQUIRED_COLS present.
    """
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame is missing required columns: {missing}")

    # Keep only the columns we want to insert
    optional_cols = ["customer_name", "postal_code"]
    cols_to_insert = REQUIRED_COLS + [c for c in optional_cols if c in df.columns]
    df = df[cols_to_insert].copy()

    # Coerce types
    df["order_date"] = pd.to_datetime(df["order_date"]).dt.date
    df["ship_date"] = pd.to_datetime(df["ship_date"]).dt.date
    df["sales"] = pd.to_numeric(df["sales"], errors="coerce").fillna(0).round(2)
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
    df["discount"] = pd.to_numeric(df["discount"], errors="coerce").fillna(0).round(2)
    df["profit"] = pd.to_numeric(df["profit"], errors="coerce").fillna(0).round(2)

    # Drop duplicates on PK columns
    before = len(df)
    df = df.drop_duplicates(subset=["order_id", "product_id"])
    if len(df) < before:
        logger.warning("Dropped %d duplicate (order_id, product_id) pairs", before - len(df))

    engine = get_db_engine()
    with engine.connect() as conn:
        conn.execute(text(DDL))
        index_stmts = _get_index_statements(settings.DB_TYPE)
        for idx_sql in index_stmts:
            try:
                conn.execute(text(idx_sql))
            except Exception:
                pass  # Index may already exist (MySQL)
        conn.commit()

    df.to_sql("orders", engine, if_exists="replace", index=False, chunksize=500)
    logger.info("Inserted %d rows into 'orders' table", len(df))

    with engine.connect() as conn:
        row_count = conn.execute(text("SELECT COUNT(*) FROM orders")).scalar()
    logger.info("Verification: orders table contains %d rows", row_count)


# ── CLI entrypoint ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the reporting agent database")
    parser.add_argument("--csv", type=str, default="data/raw/superstore.csv",
                        help="Path to Superstore CSV file")
    parser.add_argument("--generate", action="store_true",
                        help="Generate synthetic data instead of loading a CSV")
    parser.add_argument("--rows", type=int, default=5000,
                        help="Number of synthetic rows to generate (default: 5000)")
    args = parser.parse_args()

    if args.generate:
        logger.info("Generating synthetic dataset with %d rows", args.rows)
        df = generate_sample_data(args.rows)
    else:
        csv_path = Path(args.csv)
        if not csv_path.exists():
            # Try the original spaced filename as fallback
            alt_path = Path("data/raw/Sample - Superstore.csv")
            if alt_path.exists():
                csv_path = alt_path
                logger.info("Using alternate CSV path: %s", csv_path)
            else:
                logger.warning(
                    "CSV not found at '%s'. Falling back to synthetic data (--rows %d).",
                    csv_path, args.rows,
                )
                df = generate_sample_data(args.rows)
                csv_path = None
        if csv_path is not None:
            df = load_csv(str(csv_path))

    seed_database(df)
    logger.info("Database seeded successfully. DB: %s", settings.database_url)


if __name__ == "__main__":
    main()
