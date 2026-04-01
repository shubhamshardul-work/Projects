"""
Lightweight JSON-file-based document inventory tracker.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.config import REGISTRY_FILE
from app.models.schemas import DocumentRecord


def _load_registry() -> list[dict]:
    p = Path(REGISTRY_FILE)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return []


def _save_registry(records: list[dict]) -> None:
    p = Path(REGISTRY_FILE)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")


def register_document(
    file_path: str,
    client_name: str | None = None,
    project_name: str | None = None,
) -> DocumentRecord:
    """Register a new document and return its record."""
    records = _load_registry()
    doc_id = f"DOC-{uuid.uuid4().hex[:8].upper()}"
    ext = Path(file_path).suffix.lower().lstrip(".")

    record = DocumentRecord(
        document_id=doc_id,
        file_name=Path(file_path).name,
        file_path=str(Path(file_path).resolve()),
        file_type=ext,
        client_name=client_name,
        project_name=project_name,
        upload_date=datetime.now(timezone.utc).isoformat(),
        status="pending",
    )
    records.append(record.model_dump())
    _save_registry(records)
    return record


def update_status(
    document_id: str,
    status: str,
    document_type: str | None = None,
) -> None:
    """Update status (and optionally document_type) of a registered document."""
    records = _load_registry()
    for r in records:
        if r["document_id"] == document_id:
            r["status"] = status
            if document_type:
                r["document_type"] = document_type
            break
    _save_registry(records)


def get_pending_documents() -> list[DocumentRecord]:
    records = _load_registry()
    return [DocumentRecord(**r) for r in records if r["status"] == "pending"]
