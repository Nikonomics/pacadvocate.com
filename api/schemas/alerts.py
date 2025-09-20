from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class AlertType(str, Enum):
    CHANGE = "change"
    STAGE_TRANSITION = "stage_transition"
    DEADLINE = "deadline"
    CUSTOM = "custom"

class AlertPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class AlertBase(BaseModel):
    title: str
    message: str
    alert_type: AlertType
    priority: AlertPriority

class AlertResponse(AlertBase):
    id: int
    bill_id: int
    bill_number: Optional[str] = None
    bill_title: Optional[str] = None
    is_read: bool
    is_dismissed: bool
    created_at: datetime
    read_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class AlertListResponse(BaseModel):
    alerts: List[AlertResponse]
    total: int
    unread_count: int
    page: int
    page_size: int

class AlertUpdateRequest(BaseModel):
    is_read: Optional[bool] = None
    is_dismissed: Optional[bool] = None

class AlertPreferencesBase(BaseModel):
    email_enabled: bool = True
    email_frequency: str = "immediate"  # immediate, daily, weekly
    min_priority: AlertPriority = AlertPriority.MEDIUM
    min_relevance_score: float = 40.0
    monitor_text_changes: bool = True
    monitor_stage_transitions: bool = True
    monitor_status_changes: bool = True
    alert_on_minor: bool = False
    alert_on_moderate: bool = True
    alert_on_significant: bool = True
    alert_on_critical: bool = True

class AlertPreferencesCreate(AlertPreferencesBase):
    pass

class AlertPreferencesUpdate(BaseModel):
    email_enabled: Optional[bool] = None
    email_frequency: Optional[str] = None
    min_priority: Optional[AlertPriority] = None
    min_relevance_score: Optional[float] = None
    monitor_text_changes: Optional[bool] = None
    monitor_stage_transitions: Optional[bool] = None
    monitor_status_changes: Optional[bool] = None
    alert_on_minor: Optional[bool] = None
    alert_on_moderate: Optional[bool] = None
    alert_on_significant: Optional[bool] = None
    alert_on_critical: Optional[bool] = None

class AlertPreferencesResponse(AlertPreferencesBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True