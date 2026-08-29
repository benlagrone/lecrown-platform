from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_privileged_token
from app.models.user import User
from app.schemas.backoffice import (
    AgentProfileCreate,
    AgentProfileRead,
    BrokerageCreate,
    BrokerageRead,
    RepresentationCreate,
    RepresentationRead,
    RoleAssignmentRead,
    RoleGrant,
    TransactionCreate,
    TransactionRead,
)
from app.services import backoffice_service

router = APIRouter()


def _translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@router.post("/brokerages", response_model=BrokerageRead)
def create_brokerage(
    payload: BrokerageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_privileged_token),
) -> BrokerageRead:
    try:
        result = backoffice_service.create_brokerage(
            db,
            actor=current_user,
            legal_name=payload.legal_name,
            license_number=payload.license_number,
            designated_broker_user_id=payload.designated_broker_user_id,
        )
    except (PermissionError, LookupError, ValueError) as exc:
        raise _translate_error(exc) from exc
    return BrokerageRead.model_validate(result)


@router.post("/brokerages/{brokerage_id}/roles", response_model=RoleAssignmentRead)
def grant_role(
    brokerage_id: str,
    payload: RoleGrant,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_privileged_token),
) -> RoleAssignmentRead:
    try:
        result = backoffice_service.grant_role(
            db, actor=current_user, brokerage_id=brokerage_id, user_id=payload.user_id, role=payload.role
        )
    except (PermissionError, LookupError, ValueError) as exc:
        raise _translate_error(exc) from exc
    return RoleAssignmentRead.model_validate(result)


@router.post("/brokerages/{brokerage_id}/agents", response_model=AgentProfileRead)
def create_agent_profile(
    brokerage_id: str,
    payload: AgentProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_privileged_token),
) -> AgentProfileRead:
    try:
        result = backoffice_service.create_agent_profile(
            db,
            actor=current_user,
            brokerage_id=brokerage_id,
            user_id=payload.user_id,
            license_number=payload.license_number,
        )
    except (PermissionError, LookupError, ValueError) as exc:
        raise _translate_error(exc) from exc
    return AgentProfileRead.model_validate(result)


@router.post(
    "/brokerages/{brokerage_id}/agents/{profile_id}/activate",
    response_model=AgentProfileRead,
)
def activate_agent_profile(
    brokerage_id: str,
    profile_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_privileged_token),
) -> AgentProfileRead:
    try:
        result = backoffice_service.activate_agent_profile(
            db,
            actor=current_user,
            brokerage_id=brokerage_id,
            profile_id=profile_id,
        )
    except (PermissionError, LookupError, ValueError) as exc:
        raise _translate_error(exc) from exc
    return AgentProfileRead.model_validate(result)


@router.post("/brokerages/{brokerage_id}/representations", response_model=RepresentationRead)
def create_representation(
    brokerage_id: str,
    payload: RepresentationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RepresentationRead:
    try:
        result = backoffice_service.create_representation(
            db,
            actor=current_user,
            brokerage_id=brokerage_id,
            client_name=payload.client_name,
            client_crm_reference=payload.client_crm_reference,
            representation_type=payload.representation_type,
            responsible_agent_user_id=payload.responsible_agent_user_id,
        )
    except (PermissionError, LookupError, ValueError) as exc:
        raise _translate_error(exc) from exc
    return RepresentationRead.model_validate(result)


@router.post("/brokerages/{brokerage_id}/transactions", response_model=TransactionRead)
def create_transaction(
    brokerage_id: str,
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TransactionRead:
    try:
        result = backoffice_service.create_transaction(
            db,
            actor=current_user,
            brokerage_id=brokerage_id,
            representation_id=payload.representation_id,
            property_reference=payload.property_reference,
            transaction_type=payload.transaction_type,
            responsible_agent_user_id=payload.responsible_agent_user_id,
        )
    except (PermissionError, LookupError, ValueError) as exc:
        raise _translate_error(exc) from exc
    return TransactionRead.model_validate(result)
