from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class GovContractRefreshRequest(BaseModel):
    window_days: int = Field(default=7, ge=1, le=90)
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    @model_validator(mode="after")
    def validate_window(self) -> "GovContractRefreshRequest":
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        return self


class GovContractFunnelRequest(BaseModel):
    notes: Optional[str] = None
    force: bool = False


class GovContractCapabilitiesRead(BaseModel):
    gmail_rfq_sync_enabled: bool
    gmail_rfq_feed_label: Optional[str] = None


class GovContractKeywordRuleWrite(BaseModel):
    phrase: str = Field(min_length=1, max_length=120)
    weight: int = Field(default=3, ge=1, le=25)


class GovContractKeywordRuleRead(BaseModel):
    id: str
    phrase: str
    weight: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GovContractAgencyPreferenceWrite(BaseModel):
    agency_name: str = Field(min_length=1, max_length=160)
    weight: int = Field(default=5, ge=1, le=10)


class GovContractAgencyPreferenceRead(BaseModel):
    id: str
    agency_name: str
    weight: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GovContractOpportunityRead(BaseModel):
    id: str
    source: str
    source_key: str
    source_url: str
    title: str
    solicitation_id: str
    agency_name: Optional[str] = None
    agency_number: Optional[str] = None
    status_code: Optional[str] = None
    status_name: Optional[str] = None
    due_date: Optional[date] = None
    due_time: Optional[str] = None
    posting_date: Optional[date] = None
    source_created_at: Optional[datetime] = None
    source_last_modified_at: Optional[datetime] = None
    nigp_codes: Optional[str] = None
    score: int
    priority_score: int
    fit_bucket: str
    is_match: bool
    is_open: bool
    matched_keywords: list[str] = Field(default_factory=list)
    opportunity_categories: list[str] = Field(default_factory=list)
    auto_tags: list[str] = Field(default_factory=list)
    score_breakdown: Optional[dict[str, Any]] = None
    funnel_status: str
    funnel_submission_id: Optional[str] = None
    funnel_delivery_target: Optional[str] = None
    funnel_delivery_status: Optional[str] = None
    funnel_record_id: Optional[str] = None
    funnel_payload: Optional[dict[str, Any]] = None
    funnel_response: Optional[dict[str, Any]] = None
    funneled_at: Optional[datetime] = None
    first_seen_at: datetime
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GovContractImportRunRead(BaseModel):
    id: str
    source: str
    status: str
    window_start: date
    window_end: date
    source_total_records: int
    total_records: int
    matched_records: int
    open_records: int
    csv_bytes: int
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
