from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class BillStatus(str, Enum):
    INTRODUCED = "introduced"
    COMMITTEE = "committee"
    FLOOR = "floor"
    PASSED = "passed"
    SIGNED = "signed"
    VETOED = "vetoed"
    DEAD = "dead"

class StateFilter(str, Enum):
    FEDERAL = "federal"
    ALL_STATES = "all"
    # Add specific states as needed
    CA = "CA"
    TX = "TX"
    NY = "NY"
    FL = "FL"

class BillBase(BaseModel):
    bill_number: str
    title: str
    summary: Optional[str] = None
    source: Optional[str] = None
    state_or_federal: str = "federal"
    status: Optional[str] = None
    sponsor: Optional[str] = None
    committee: Optional[str] = None
    chamber: Optional[str] = None
    # Risk tracking fields
    reimbursement_risk: Optional[int] = 0
    staffing_risk: Optional[int] = 0
    compliance_risk: Optional[int] = 0
    quality_risk: Optional[int] = 0
    total_risk_score: Optional[int] = 0
    risk_tags: Optional[str] = None

class BillCreate(BillBase):
    full_text: Optional[str] = None
    introduced_date: Optional[datetime] = None
    last_action_date: Optional[datetime] = None

class BillUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    full_text: Optional[str] = None
    status: Optional[str] = None
    sponsor: Optional[str] = None
    committee: Optional[str] = None
    last_action_date: Optional[datetime] = None

class BillResponse(BillBase):
    id: int
    relevance_score: Optional[float] = None
    introduced_date: Optional[datetime] = None
    last_action_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool

    class Config:
        from_attributes = True

class BillDetailResponse(BillResponse):
    full_text: Optional[str] = None
    ai_analysis: Optional[Dict[str, Any]] = None
    recent_changes: Optional[List[Dict[str, Any]]] = None
    stage_transitions: Optional[List[Dict[str, Any]]] = None
    is_tracked_by_user: bool = False

class BillListResponse(BaseModel):
    bills: List[BillResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

class BillFilters(BaseModel):
    state: Optional[str] = None
    status: Optional[str] = None
    min_relevance_score: Optional[float] = Field(None, ge=0, le=100)
    max_relevance_score: Optional[float] = Field(None, ge=0, le=100)
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    search: Optional[str] = None
    source: Optional[str] = None
    chamber: Optional[str] = None

class BillTrackingRequest(BaseModel):
    alert_on_changes: bool = True
    alert_on_stage_transitions: bool = True
    min_change_severity: str = "moderate"  # minor, moderate, significant, critical

class BillTrackingResponse(BaseModel):
    id: int
    bill_id: int
    user_id: int
    alert_on_changes: bool
    alert_on_stage_transitions: bool
    min_change_severity: str
    created_at: datetime

    class Config:
        from_attributes = True