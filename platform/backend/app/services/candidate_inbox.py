"""Durable candidate snapshots and write-ahead receipts for explicit CRM promotion."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings
from app.services import espocrm_service

settings = get_settings()


class CandidateInboxError(RuntimeError):
    pass


class FitFeedbackConflict(CandidateInboxError):
    pass


def configured() -> bool:
    return bool(settings.procurement_candidate_json_path.strip())


def candidate_id(source_key: str) -> str:
    return hashlib.sha256(source_key.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def collection_lock():
    if not configured():
        yield
        return
    path = Path(settings.procurement_candidate_json_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(f"{path}.collection.lock", "a+", encoding="utf-8") as lock:
        os.chmod(lock.name, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise CandidateInboxError("A source collection batch is already running; try again after it completes") from exc
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


@contextmanager
def _locked():
    if not configured():
        raise CandidateInboxError("The candidate JSON inbox is not configured")
    path = Path(settings.procurement_candidate_json_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(f"{path}.lock", "a+", encoding="utf-8") as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (ValueError, OSError) as exc:
                    raise CandidateInboxError("Candidate inbox is unreadable; existing file was not replaced") from exc
                if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("candidates"), dict):
                    raise CandidateInboxError("Candidate inbox has an unsupported format; existing file was not replaced")
            else:
                data = {"version": 1, "candidates": {}}
            yield path, data
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _save(path: Path, data: dict) -> None:
    data["updated_at"] = _now()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False) as stream:
            temporary = stream.name
            os.chmod(temporary, 0o600)
            json.dump(data, stream, ensure_ascii=True, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def capture(records: list[dict]) -> None:
    if not configured():
        return
    with _locked() as (path, data):
        for record in records:
            key = candidate_id(record["source_key"])
            previous = data["candidates"].get(key, {})
            data["candidates"][key] = {
                "candidate_id": key,
                "first_captured_at": previous.get("first_captured_at", _now()),
                "last_captured_at": _now(),
                "candidate": record,
                "promotion": previous.get("promotion", {"status": "unselected"}),
                "fit_feedback": previous.get("fit_feedback", {"rating": None, "version": 0}),
                "fit_feedback_history": previous.get("fit_feedback_history", []),
            }
        _save(path, data)


def snapshot() -> dict:
    with _locked() as (_, data):
        return data


def set_fit_feedback(source_key: str, *, rating: str | None, reviewed_by: str, expected_version: int) -> dict:
    if rating not in {"high", "low", None}:
        raise ValueError("Fit rating must be high, low, or null")
    with _locked() as (path, data):
        entry = data["candidates"].get(candidate_id(source_key))
        if entry is None:
            raise CandidateInboxError("Candidate is not present in the JSON inbox")
        current = entry.get("fit_feedback", {"rating": None, "version": 0})
        if current.get("version", 0) != expected_version:
            raise FitFeedbackConflict("This rating changed in another session. Refresh before rating it again.")
        if current.get("rating") == rating:
            return dict(current)
        feedback = {"rating": rating, "version": expected_version + 1,
                    "reviewed_by": reviewed_by, "reviewed_at": _now()}
        entry["fit_feedback"] = feedback
        entry.setdefault("fit_feedback_history", []).append(dict(feedback))
        _save(path, data)
        return dict(feedback)


def promote(source_key: str, payload: dict) -> dict:
    """Only called by an explicitly confirmed promotion, never by collection."""
    with _locked() as (path, data):
        key = candidate_id(source_key)
        entry = data["candidates"].get(key)
        if entry is None:
            raise CandidateInboxError("Candidate is not present in the JSON inbox")
        receipt = entry["promotion"]
        marker = f"ProcurementCandidate: {key}"
        record_id = receipt.get("crm_record_id")
        try:
            if not record_id:
                found = espocrm_service.find_opportunity(marker)
                if found:
                    record_id = found["id"]
                elif receipt.get("status") in {"creating", "uncertain"}:
                    raise CandidateInboxError("The previous CRM write is uncertain. No duplicate was created; reconcile this candidate in EspoCRM before retrying.")
                else:
                    payload = {**payload, "description": f"{marker}\n{payload.get('description', '')}"}
                    receipt.update(status="creating", requested_at=_now(), payload=payload)
                    _save(path, data)
                    try:
                        created = espocrm_service.create_opportunity(payload)
                    except espocrm_service.EspoCRMError as exc:
                        receipt["status"] = "failed" if exc.status_code and 400 <= exc.status_code < 500 else "uncertain"
                        _save(path, data)
                        raise
                    record_id = created["id"]
            receipt.update(status="verification_pending", crm_record_id=record_id)
            _save(path, data)
            verified = espocrm_service.get_opportunity(record_id)
            if marker not in str(verified.get("description") or ""):
                raise CandidateInboxError("CRM record verification did not match this candidate; no additional record was created")
            receipt.update(status="promoted", verified_at=_now())
            _save(path, data)
            return dict(receipt)
        except espocrm_service.EspoCRMError as exc:
            raise CandidateInboxError(str(exc)) from exc
