"""
In-memory and file-backed registry for parsed documents.

Allows index_documents(document_ids) to retrieve parsed document structures
by document_id without forcing callers to pass around large in-memory objects.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.ingestion.document_parser import DocumentParseResult

logger = logging.getLogger(__name__)

_DEFAULT_STORAGE_DIR = Path("./data/documents")


class DocumentRegistry:
    """Thread-safe document registry with optional JSON persistence."""

    def __init__(self, storage_dir: Path | str | None = None) -> None:
        self._lock = Lock()
        self._documents: dict[str, Any] = {}
        self._storage_dir = Path(storage_dir) if storage_dir else _DEFAULT_STORAGE_DIR

    def register(self, doc: DocumentParseResult) -> None:
        """Register a parsed document in memory and persist it to disk."""
        with self._lock:
            self._documents[doc.document_id] = doc
            self._persist_document(doc)

    def get(self, document_id: str) -> DocumentParseResult | None:
        """Retrieve a document by ID."""
        with self._lock:
            if document_id in self._documents:
                return self._documents[document_id]
            # Try to load from disk if not in memory
            return self._load_from_disk(document_id)

    def list_all(self) -> list[DocumentParseResult]:
        """Return all registered documents."""
        with self._lock:
            return list(self._documents.values())

    def clear(self) -> None:
        """Clear the in-memory registry (used in tests)."""
        with self._lock:
            self._documents.clear()

    def _persist_document(self, doc: DocumentParseResult) -> None:
        try:
            self._storage_dir.mkdir(parents=True, exist_ok=True)
            target = self._storage_dir / f"{doc.document_id}.json"
            data = asdict(doc)
            target.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to persist document %s: %s", doc.document_id, exc)

    def _load_from_disk(self, document_id: str) -> DocumentParseResult | None:
        try:
            target = self._storage_dir / f"{document_id}.json"
            if not target.exists():
                return None
            data = json.loads(target.read_text(encoding="utf-8"))
            from app.ingestion.document_parser import DocumentParseResult, ParsedPage

            pages = [ParsedPage(**p) for p in data.get("pages", [])]
            data["pages"] = pages
            doc = DocumentParseResult(**data)
            self._documents[document_id] = doc
            return doc
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to load document %s from disk: %s", document_id, exc)
            return None


# Global default instance
registry = DocumentRegistry()
