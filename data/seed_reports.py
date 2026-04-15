"""
Seed script — load sample reports into ChromaDB.

Usage:
    python data/seed_reports.py
    python data/seed_reports.py --clear       # clear existing data, then seed samples
    python data/seed_reports.py --clear-only  # clear only, seed nothing
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.logging_config import get_logger

logger = get_logger(__name__)

SAMPLE_DIR = Path(__file__).parent / "sample_reports"

REPORT_METADATA = {
    "report_2016_dec.md": {
        "report_id": "report_2016_dec",
        "report_type": "monthly",
        "report_date": "2016-12-31",
        "period_start": "2016-12-01",
        "period_end": "2016-12-31",
    },
    "report_2017_jan.md": {
        "report_id": "report_2017_jan",
        "report_type": "monthly",
        "report_date": "2017-01-31",
        "period_start": "2017-01-01",
        "period_end": "2017-01-31",
    },
    "report_2017_feb.md": {
        "report_id": "report_2017_feb",
        "report_type": "monthly",
        "report_date": "2017-02-28",
        "period_start": "2017-02-01",
        "period_end": "2017-02-28",
    },
}


def seed_reports(persist_dir: str = "data/chroma", clear: bool = False) -> int:
    """
    Read sample report files and store them in ChromaDB.

    Args:
        persist_dir: ChromaDB persistence directory.
        clear: If True, clear existing collection before seeding.

    Returns:
        Total number of chunks stored.
    """
    from src.tools.rag_tools import ReportVectorStore

    store = ReportVectorStore(persist_dir=persist_dir)

    if clear:
        store.clear_collection()
        logger.info("Cleared existing ChromaDB collection")

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


def clear_only(persist_dir: str = "data/chroma") -> None:
    """Clear the ChromaDB collection without seeding any sample reports."""
    from src.tools.rag_tools import ReportVectorStore

    store = ReportVectorStore(persist_dir=persist_dir)
    store.clear_collection()
    stats = store.get_collection_stats()
    logger.info(
        "ChromaDB cleared. No samples seeded. (chunks=%d, reports=%d)",
        stats["total_chunks"],
        stats["total_reports"],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed sample reports into ChromaDB")
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing ChromaDB collection before seeding",
    )
    parser.add_argument(
        "--clear-only",
        action="store_true",
        help="Clear the collection without seeding any sample reports",
    )
    args = parser.parse_args()

    if args.clear_only:
        clear_only()
        print("ChromaDB cleared. No samples seeded.")
        print("Collection is now empty.")
    else:
        total = seed_reports(clear=args.clear)
        print(f"Seeded {total} chunks into ChromaDB")
