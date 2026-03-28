from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

PropertiesTenant = Literal["properties"]


class InquiryCreate(BaseModel):
    tenant: PropertiesTenant = "properties"
    asset_type: str = Field(min_length=1)
    location: str = Field(min_length=1)
    problem: str = Field(min_length=1)
    contact_name: str = Field(min_length=1)
    email: str = Field(min_length=1)
    phone: str = Field(min_length=1)


class InquiryRead(BaseModel):
    id: str
    tenant: PropertiesTenant
    asset_type: str
    location: str
    problem: str
    contact_name: str
    email: str
    phone: str
    created_at: datetime

    model_config = {"from_attributes": True}
