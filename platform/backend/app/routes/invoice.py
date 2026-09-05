from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_user
from app.models.user import User
from app.schemas.invoice import InvoiceDefaultsRead, InvoiceDraftRead, InvoiceRenderRequest
from app.services import invoice_service

router = APIRouter()


def _raise_invoice_http_error(exc: Exception) -> None:
    if isinstance(exc, invoice_service.InvoiceNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, invoice_service.InvoiceConfigurationError):
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if isinstance(exc, invoice_service.InvoiceValidationError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, invoice_service.InvoiceError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise exc


@router.get("/defaults", response_model=InvoiceDefaultsRead)
def get_invoice_defaults(
    company_key: str | None = Query(default=None),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        return invoice_service.get_invoice_defaults(company_key)
    except Exception as exc:  # noqa: BLE001
        _raise_invoice_http_error(exc)


@router.post("/render")
def render_invoice(
    payload: InvoiceRenderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> FileResponse:
    try:
        invoice = invoice_service.create_rendered_invoice(
            db,
            payload=payload,
            created_by=current_user,
        )
        path = invoice_service.get_download_path(invoice)
    except Exception as exc:  # noqa: BLE001
        _raise_invoice_http_error(exc)
    return FileResponse(path, media_type="application/pdf", filename=invoice.output_filename)


@router.post("/draft", response_model=InvoiceDraftRead)
def create_invoice_draft(
    payload: InvoiceRenderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> dict:
    try:
        invoice = invoice_service.create_invoice_draft(
            db,
            payload=payload,
            created_by=current_user,
        )
        response = invoice_service.serialize_draft_response(invoice)
    except Exception as exc:  # noqa: BLE001
        _raise_invoice_http_error(exc)
    response["download_url"] = f"/invoice/outputs/{invoice.id}"
    return response


@router.get("/outputs/{invoice_id}")
def download_generated_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> FileResponse:
    try:
        invoice = invoice_service.get_generated_invoice(db, invoice_id)
        path = invoice_service.get_download_path(invoice)
    except Exception as exc:  # noqa: BLE001
        _raise_invoice_http_error(exc)
    return FileResponse(path, media_type="application/pdf", filename=invoice.output_filename)
