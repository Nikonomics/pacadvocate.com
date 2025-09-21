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
    # SNF-specific operational scoring fields
    payment_impact: Optional[str] = None  # increase, decrease, neutral
    operational_area: Optional[str] = None  # Staffing, Quality, Documentation, Survey, Payment
    implementation_timeline: Optional[str] = None  # Immediate, Soon, Future
    operational_tags: Optional[str] = None  # JSON array of operational impact tags

    # Impact categorization fields
    impact_type: Optional[str] = None  # Direct, Financial, Competitive, Indirect
    impact_explanation: Optional[str] = None
    ma_impact: Optional[bool] = False

    # Comment period tracking fields
    comment_deadline: Optional[datetime] = None
    comment_url: Optional[str] = None
    has_comment_period: Optional[bool] = False
    comment_period_urgent: Optional[bool] = False
    days_until_deadline: Optional[int] = None

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

    # AI Analysis Fields
    ai_relevance_score: Optional[int] = None
    ai_impact_type: Optional[str] = None  # direct, financial, competitive, workforce
    ai_relevant: Optional[bool] = None
    ai_explanation: Optional[str] = None
    ai_analysis_timestamp: Optional[str] = None

    # Additional Dashboard Fields
    effective_date: Optional[datetime] = None
    rule_source_url: Optional[str] = None
    rule_type: Optional[str] = None  # Proposed Rule, Final Rule, Bill
    comment_period_urgent: Optional[bool] = None
    days_until_deadline: Optional[int] = None

    # Financial Impact Fields
    financial_impact_pbpy: Optional[int] = None  # Per bed per year financial impact
    financial_impact_details: Optional[str] = None  # JSON details of impact components

    # Rule Summary Fields
    executive_summary: Optional[str] = None  # Executive summary from Federal Register
    key_provisions: Optional[str] = None  # JSON array of key provisions
    implementation_timeline: Optional[str] = None  # JSON timeline with milestones
    snf_action_items: Optional[str] = None  # JSON array of what SNFs need to do

    # Impact Breakdown Field
    impact_breakdown: Optional[str] = None  # JSON comprehensive impact analysis (Financial/Staffing/Quality/Compliance)

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