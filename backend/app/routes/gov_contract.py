from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.config import get_settings
from app.core.security import get_current_admin
from app.schemas.gov_contract import (
    GovContractAgencyPreferenceRead,
    GovContractAgencyPreferenceWrite,
    GovContractCapabilitiesRead,
    GovContractFunnelRequest,
    GovContractImportRunRead,
    GovContractKeywordRuleRead,
    GovContractKeywordRuleWrite,
    GovContractOpportunityRead,
    GovContractRefreshRequest,
)
from app.services import gov_contract_service

router = APIRouter()
settings = get_settings()


@router.get("/capabilities", response_model=GovContractCapabilitiesRead)
def get_contract_capabilities(_: dict = Depends(get_current_admin)) -> GovContractCapabilitiesRead:
    return GovContractCapabilitiesRead(
        gmail_rfq_sync_enabled=settings.gmail_rfq_feed_enabled,
        gmail_rfq_feed_label=settings.gmail_rfq_feed_label if settings.gmail_rfq_feed_enabled else None,
    )


@router.get("/keywords", response_model=list[GovContractKeywordRuleRead])
def get_keyword_rules(
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
) -> list[GovContractKeywordRuleRead]:
    return gov_contract_service.list_keyword_rules(db)


@router.get("/agency-preferences", response_model=list[GovContractAgencyPreferenceRead])
def get_agency_preferences(
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
) -> list[GovContractAgencyPreferenceRead]:
    return gov_contract_service.list_agency_preferences(db)


@router.post("/agency-preferences", response_model=GovContractAgencyPreferenceRead)
def create_agency_preference(
    payload: GovContractAgencyPreferenceWrite,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
) -> GovContractAgencyPreferenceRead:
    try:
        return gov_contract_service.create_agency_preference(
            db,
            agency_name=payload.agency_name,
            weight=payload.weight,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/agency-preferences/{agency_preference_id}", response_model=GovContractAgencyPreferenceRead)
def update_agency_preference(
    agency_preference_id: str,
    payload: GovContractAgencyPreferenceWrite,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
) -> GovContractAgencyPreferenceRead:
    try:
        return gov_contract_service.update_agency_preference(
            db,
            agency_preference_id,
            agency_name=payload.agency_name,
            weight=payload.weight,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/agency-preferences/{agency_preference_id}", status_code=204)
def delete_agency_preference(
    agency_preference_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
) -> Response:
    try:
        gov_contract_service.delete_agency_preference(db, agency_preference_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)


@router.post("/keywords", response_model=GovContractKeywordRuleRead)
def create_keyword_rule(
    payload: GovContractKeywordRuleWrite,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
) -> GovContractKeywordRuleRead:
    try:
        return gov_contract_service.create_keyword_rule(
            db,
            phrase=payload.phrase,
            weight=payload.weight,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/keywords/{keyword_rule_id}", response_model=GovContractKeywordRuleRead)
def update_keyword_rule(
    keyword_rule_id: str,
    payload: GovContractKeywordRuleWrite,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
) -> GovContractKeywordRuleRead:
    try:
        return gov_contract_service.update_keyword_rule(
            db,
            keyword_rule_id,
            phrase=payload.phrase,
            weight=payload.weight,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/keywords/{keyword_rule_id}", status_code=204)
def delete_keyword_rule(
    keyword_rule_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
) -> Response:
    try:
        gov_contract_service.delete_keyword_rule(db, keyword_rule_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)


@router.post("/refresh", response_model=GovContractImportRunRead)
def refresh_contracts(
    payload: GovContractRefreshRequest,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
) -> GovContractImportRunRead:
    try:
        return gov_contract_service.refresh_contracts(
            db,
            start_date=payload.start_date,
            end_date=payload.end_date,
            window_days=payload.window_days,
        )
    except gov_contract_service.GovContractSourceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/refresh-gmail", response_model=GovContractImportRunRead)
def refresh_gmail_contracts(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
) -> GovContractImportRunRead:
    try:
        return gov_contract_service.refresh_gmail_contracts(db, limit=limit)
    except gov_contract_service.GovContractSourceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/list", response_model=list[GovContractOpportunityRead])
def list_contracts(
    limit: int = Query(default=25, ge=1, le=200),
    matches_only: bool = Query(default=True),
    open_only: bool = Query(default=True),
    min_priority_score: int = Query(default=0, ge=0, le=100),
    source: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
) -> list[GovContractOpportunityRead]:
    return gov_contract_service.list_contracts(
        db,
        limit=limit,
        matches_only=matches_only,
        open_only=open_only,
        min_priority_score=min_priority_score,
        source=source,
    )


@router.post("/{contract_id}/funnel", response_model=GovContractOpportunityRead)
def funnel_contract(
    contract_id: str,
    payload: Optional[GovContractFunnelRequest] = None,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
) -> GovContractOpportunityRead:
    request = payload or GovContractFunnelRequest()
    try:
        return gov_contract_service.funnel_contract_to_crm(
            db,
            contract_id,
            notes=request.notes,
            force=request.force,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/runs", response_model=list[GovContractImportRunRead])
def list_contract_runs(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
) -> list[GovContractImportRunRead]:
    return gov_contract_service.list_import_runs(db, limit=limit)


@router.get("/export.csv")
def export_contracts_csv(
    window_days: int = Query(default=7, ge=1, le=90),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    _: dict = Depends(get_current_admin),
) -> Response:
    try:
        csv_text, resolved_start, resolved_end = gov_contract_service.export_contracts_csv(
            start_date=start_date,
            end_date=end_date,
            window_days=window_days,
        )
    except gov_contract_service.GovContractSourceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    filename = f"txsmartbuy-esbd-{resolved_start.isoformat()}-to-{resolved_end.isoformat()}.csv"
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
