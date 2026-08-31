from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ClientPortalConfigRead(BaseModel):
    ready: bool
    keycloak_url: str
    realm: str
    client_id: str | None
    required_roles: list[str]


class ClientPortalGrantCreate(BaseModel):
    representation_id: str
    email: str = Field(min_length=3, max_length=240)


class ClientPortalGrantRead(BaseModel):
    id: str
    brokerage_id: str
    representation_id: str
    email: str
    keycloak_subject: str | None
    status: str
    last_authenticated_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ClientPortalIdentityRead(BaseModel):
    subject: str
    email: str
    name: str


class ClientRepresentationRead(BaseModel):
    id: str
    client_name: str
    representation_type: str
    status: str
    effective_at: datetime | None
    expires_at: datetime | None

    model_config = {"from_attributes": True}


class ClientTransactionRead(BaseModel):
    id: str
    representation_id: str
    property_reference: str | None
    transaction_type: str
    status: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class ClientDocumentRead(BaseModel):
    id: str
    transaction_id: str
    name: str
    version: int
    media_type: str
    size_bytes: int
    created_at: datetime


class ClientPortalSessionRead(BaseModel):
    identity: ClientPortalIdentityRead
    representations: list[ClientRepresentationRead]
    transactions: list[ClientTransactionRead]
    documents: list[ClientDocumentRead]
