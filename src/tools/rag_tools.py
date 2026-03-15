"""
RAG tools — ChromaDB integration for historical report storage and retrieval.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ReportVectorStore:
    """
    Manages ChromaDB collection for historical reports.

    Singleton-style: one instance per persist_dir + collection_name pair.
    """

    def __init__(
        self,
        persist_dir: str = "data/chroma",
        collection_name: str = "reports",
    ):
        """
        Args:
            persist_dir: ChromaDB persistence directory.
            collection_name: Collection name.
        """
        import chromadb

        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "ReportVectorStore initialised — collection=%s, docs=%d",
            collection_name,
            self._collection.count(),
        )

    # ── Store ────────────────────────────────────────────────────────────────

    def store_report(
        self,
        report_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
    ) -> int:
        """
        Split report into chunks and store in ChromaDB.

        Args:
            report_id: Unique report ID (e.g. "report_2024_w01").
            content: Full report text.
            metadata: Extra metadata (date, period, type).
            chunk_size: Chunk size in characters.
            chunk_overlap: Overlap between chunks.

        Returns:
            Number of chunks stored.
        """
        metadata = metadata or {}
        chunks = self._split_text(content, chunk_size, chunk_overlap)

        if not chunks:
            logger.warning("No chunks produced for report %s", report_id)
            return 0

        ids = []
        documents = []
        metadatas = []

        for idx, chunk in enumerate(chunks):
            chunk_id = f"{report_id}_chunk_{idx}"
            chunk_meta = {
                **metadata,
                "report_id": report_id,
                "chunk_index": idx,
            }
            ids.append(chunk_id)
            documents.append(chunk)
            metadatas.append(chunk_meta)

        self._collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

        logger.info("Stored %d chunks for report %s", len(chunks), report_id)
        return len(chunks)

    # ── Search ───────────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Semantic search for the most relevant report chunks.

        Args:
            query: Natural language search query.
            top_k: Max number of results.
            where: Metadata filter (e.g. {"report_type": "weekly"}).

        Returns:
            List of dicts: [{"content": str, "metadata": dict, "distance": float}]
        """
        kwargs: dict[str, Any] = {
            "query_texts": [query],
            "n_results": min(top_k, max(self._collection.count(), 1)),
        }
        if where:
            kwargs["where"] = where

        try:
            results = self._collection.query(**kwargs)
        except Exception as exc:
            logger.error("ChromaDB search failed: %s", exc)
            return []

        if not results or not results.get("documents"):
            return []

        output = []
        docs = results["documents"][0]
        metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
        dists = results["distances"][0] if results.get("distances") else [0.0] * len(docs)

        for doc, meta, dist in zip(docs, metas, dists):
            output.append({"content": doc, "metadata": meta, "distance": dist})

        return output

    # ── Stats ────────────────────────────────────────────────────────────────

    def get_collection_stats(self) -> dict[str, Any]:
        """Return total document and chunk counts."""
        count = self._collection.count()
        # Distinct report IDs
        report_ids: set[str] = set()
        if count > 0:
            try:
                all_meta = self._collection.get(include=["metadatas"])
                for m in (all_meta.get("metadatas") or []):
                    if m and "report_id" in m:
                        report_ids.add(m["report_id"])
            except Exception:
                pass

        return {
            "total_chunks": count,
            "total_reports": len(report_ids),
            "report_ids": sorted(report_ids),
        }

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _split_text(
        text: str,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
    ) -> list[str]:
        """Split text into overlapping chunks."""
        if not text:
            return []

        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk.strip())
            start += chunk_size - chunk_overlap

        return chunks
