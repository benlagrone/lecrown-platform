from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.backoffice import Document, DocumentVersion, Transaction
from app.models.user import User
from app.services import audit_service, authorization_service
from app.utils.helpers import new_uuid

settings = get_settings()
ALLOWED_MEDIA_TYPES = {"application/pdf"}


def _store_immutable(content: bytes, digest: str) -> str:
    relative_key = f"sha256/{digest[:2]}/{digest}"
    target = settings.document_storage_path / relative_key
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise RuntimeError("Stored object digest mismatch")
        return relative_key
    fd, temporary_name = tempfile.mkstemp(prefix="upload-", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_name, 0o440)
        os.replace(temporary_name, target)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
    return relative_key


def upload(
    db: Session,
    *,
    actor: User,
    brokerage_id: str,
    name: str,
    media_type: str,
    content: bytes,
    transaction_id: str | None = None,
    classification: str = "brokerage_confidential",
) -> tuple[Document, DocumentVersion]:
    authorization_service.require_permission(
        db, user=actor, brokerage_id=brokerage_id, permission="documents.prepare"
    )
    if media_type not in ALLOWED_MEDIA_TYPES:
        raise ValueError("Only PDF documents are accepted in this phase")
    if not content:
        raise ValueError("Document is empty")
    if len(content) > settings.document_max_bytes:
        raise ValueError("Document exceeds configured size limit")
    if not content.startswith(b"%PDF-"):
        raise ValueError("Document content is not a PDF")
    if transaction_id:
        transaction = db.get(Transaction, transaction_id)
        if transaction is None or transaction.brokerage_id != brokerage_id:
            raise LookupError("Transaction not found in brokerage")
    digest = hashlib.sha256(content).hexdigest()
    storage_key = _store_immutable(content, digest)
    document = Document(
        id=new_uuid(),
        brokerage_id=brokerage_id,
        transaction_id=transaction_id,
        name=name.strip(),
        classification=classification,
        created_by_user_id=actor.id,
    )
    if not document.name:
        raise ValueError("Document name is required")
    version = DocumentVersion(
        id=new_uuid(),
        document_id=document.id,
        version_number=1,
        sha256=digest,
        storage_key=storage_key,
        media_type=media_type,
        size_bytes=len(content),
        scan_status="pending",
        render_status="pending",
        uploaded_by_user_id=actor.id,
    )
    db.add_all([document, version])
    audit_service.record(
        db,
        actor=actor,
        action="document.uploaded",
        resource_type="document",
        resource_id=document.id,
        brokerage_id=brokerage_id,
        next_state="pending_scan",
        metadata={"sha256": digest, "size_bytes": len(content), "version": 1},
    )
    db.commit()
    db.refresh(document)
    db.refresh(version)
    return document, version


def resolve_path(version: DocumentVersion) -> Path:
    root = settings.document_storage_path.resolve()
    path = (root / version.storage_key).resolve()
    if root not in path.parents:
        raise RuntimeError("Invalid storage key")
    return path
