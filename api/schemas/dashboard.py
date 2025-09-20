from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

class BillStats(BaseModel):
    total_bills: int
    active_bills: int
    bills_by_status: Dict[str, int]
    bills_by_state: Dict[str, int]
    avg_relevance_score: float
    high_relevance_bills: int  # score >= 70

class AlertStats(BaseModel):
    total_alerts: int
    unread_alerts: int
    alerts_last_7_days: int
    alerts_by_priority: Dict[str, int]
    alerts_by_type: Dict[str, int]

class ChangeStats(BaseModel):
    changes_last_7_days: int
    changes_by_severity: Dict[str, int]
    stage_transitions_last_7_days: int
    bills_with_recent_activity: int

class UserActivityStats(BaseModel):
    tracked_bills: int
    total_alerts_received: int
    last_login: Optional[datetime] = None
    account_created: datetime

class TrendingBill(BaseModel):
    id: int
    bill_number: str
    title: str
    relevance_score: Optional[float]
    activity_score: float  # Based on recent changes, alerts, etc.
    recent_changes: int
    stage_transitions: int
    alerts_generated: int

class DashboardStats(BaseModel):
    bill_stats: BillStats
    alert_stats: AlertStats
    change_stats: ChangeStats
    user_activity: UserActivityStats
    trending_bills: List[TrendingBill]
    last_updated: datetime

class TrendingBillsResponse(BaseModel):
    bills: List[TrendingBill]
    period: str  # "24h", "7d", "30d"
    total: int

class SystemHealth(BaseModel):
    status: str  # "healthy", "degraded", "down"
    database: str
    redis: str
    last_check: datetime
    uptime_seconds: int