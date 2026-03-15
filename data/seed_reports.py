"""
Seed script — load sample reports into ChromaDB.

Usage:
    python data/seed_reports.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.logging_config import get_logger

logger = get_logger(__name__)

SAMPLE_DIR = Path(__file__).parent / "sample_reports"

REPORT_METADATA = {
    "report_2024_w01.md": {
        "report_id": "report_2024_w01",
        "report_type": "weekly",
        "report_date": "2024-01-07",
        "period_start": "2024-01-01",
        "period_end": "2024-01-07",
    },
    "report_2024_w02.md": {
        "report_id": "report_2024_w02",
        "report_type": "weekly",
        "report_date": "2024-01-14",
        "period_start": "2024-01-08",
        "period_end": "2024-01-14",
    },
    "report_2024_w03.md": {
        "report_id": "report_2024_w03",
        "report_type": "weekly",
        "report_date": "2024-01-21",
        "period_start": "2024-01-15",
        "period_end": "2024-01-21",
    },
}


def seed_reports(persist_dir: str = "data/chroma") -> int:
    """
    Read sample report files and store them in ChromaDB.

    Returns:
        Total number of chunks stored.
    """
    from src.tools.rag_tools import ReportVectorStore

    store = ReportVectorStore(persist_dir=persist_dir)
    total_chunks = 0

    for filename, meta in REPORT_METADATA.items():
        filepath = SAMPLE_DIR / filename
        if not filepath.exists():
            logger.warning("Sample report not found: %s", filepath)
            continue

        content = filepath.read_text(encoding="utf-8")
        report_id = meta["report_id"]

        n_chunks = store.store_report(
            report_id=report_id,
            content=content,
            metadata=meta,
        )
        total_chunks += n_chunks
        logger.info("Loaded %s → %d chunks", filename, n_chunks)

    stats = store.get_collection_stats()
    logger.info(
        "Seeding complete — %d reports, %d total chunks",
        stats["total_reports"],
        stats["total_chunks"],
    )
    return total_chunks


if __name__ == "__main__":
    total = seed_reports()
    print(f"Seeded {total} chunks into ChromaDB")
