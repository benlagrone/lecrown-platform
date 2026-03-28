from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.tenant import ensure_properties_tenant
from app.models.inquiry import Inquiry
from app.schemas.inquiry import InquiryCreate
from app.utils.helpers import new_uuid


def create(db: Session, payload: InquiryCreate) -> Inquiry:
    ensure_properties_tenant(payload.tenant)
    inquiry = Inquiry(
        id=new_uuid(),
        tenant=payload.tenant,
        asset_type=payload.asset_type,
        location=payload.location,
        problem=payload.problem,
        contact_name=payload.contact_name,
        email=payload.email,
        phone=payload.phone,
    )
    db.add(inquiry)
    db.commit()
    db.refresh(inquiry)
    return inquiry


def list_for_properties(db: Session) -> list[Inquiry]:
    statement = select(Inquiry).where(Inquiry.tenant == "properties").order_by(desc(Inquiry.created_at))
    return list(db.scalars(statement).all())
