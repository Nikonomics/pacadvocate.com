from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, or_
from datetime import datetime, timedelta
from typing import Optional

from models.database import get_db
from models.legislation import User, Bill
from models.change_detection import (
    ChangeAlert, AlertPreferences, BillChange, StageTransition, AlertPriority
)
from api.schemas.dashboard import (
    DashboardStats, BillStats, AlertStats, ChangeStats,
    UserActivityStats, TrendingBill, TrendingBillsResponse, SystemHealth
)
from api.auth.dependencies import get_current_user, get_optional_current_user
from api.middleware.caching import cached, get_cache_config
from api.middleware.redis_client import redis_client

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/stats", response_model=DashboardStats)
@cached(**get_cache_config("dashboard"))
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive dashboard statistics for the user

    **Includes:**
    - Bill statistics (total, by status, by state, etc.)
    - Alert statistics (unread, by priority, recent activity)
    - Change statistics (recent changes, stage transitions)
    - User activity metrics
    - Trending bills
    """

    now = datetime.utcnow()
    last_7_days = now - timedelta(days=7)
    last_30_days = now - timedelta(days=30)

    # Bill Statistics
    bill_stats = _get_bill_stats(db)

    # Alert Statistics
    alert_stats = _get_alert_stats(db, current_user.id, last_7_days)

    # Change Statistics
    change_stats = _get_change_stats(db, last_7_days)

    # User Activity Statistics
    user_activity = _get_user_activity_stats(db, current_user, last_30_days)

    # Trending Bills
    trending_bills = _get_trending_bills(db, limit=5)

    return DashboardStats(
        bill_stats=bill_stats,
        alert_stats=alert_stats,
        change_stats=change_stats,
        user_activity=user_activity,
        trending_bills=trending_bills,
        last_updated=now
    )

@router.get("/trending", response_model=TrendingBillsResponse)
@cached(**get_cache_config("trending"))
async def get_trending_bills(
    period: str = Query("7d", regex="^(24h|7d|30d)$", description="Time period"),
    limit: int = Query(20, ge=1, le=100, description="Number of bills to return"),
    min_relevance_score: float = Query(0, ge=0, le=100, description="Minimum relevance score"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Get trending bills based on recent activity

    **Activity includes:**
    - Text changes and amendments
    - Stage transitions
    - Generated alerts
    - User engagement

    **Periods:**
    - **24h**: Last 24 hours
    - **7d**: Last 7 days
    - **30d**: Last 30 days
    """

    # Convert period to days
    period_days = {"24h": 1, "7d": 7, "30d": 30}[period]
    cutoff_date = datetime.utcnow() - timedelta(days=period_days)

    trending_bills = _get_trending_bills(
        db,
        cutoff_date=cutoff_date,
        limit=limit,
        min_relevance_score=min_relevance_score
    )

    return TrendingBillsResponse(
        bills=trending_bills,
        period=period,
        total=len(trending_bills)
    )

@router.get("/health", response_model=SystemHealth)
async def get_system_health(
    db: Session = Depends(get_db)
):
    """
    Get system health status

    **Checks:**
    - Database connectivity
    - Redis connectivity
    - System uptime
    """

    health_data = {
        "status": "healthy",
        "database": "unknown",
        "redis": "unknown",
        "last_check": datetime.utcnow(),
        "uptime_seconds": 0  # Would track actual uptime
    }

    # Test database
    try:
        db.execute("SELECT 1").fetchone()
        health_data["database"] = "healthy"
    except Exception:
        health_data["database"] = "down"
        health_data["status"] = "degraded"

    # Test Redis
    try:
        client = await redis_client.get_client()
        await client.ping()
        health_data["redis"] = "healthy"
    except Exception:
        health_data["redis"] = "down"
        health_data["status"] = "degraded"

    return SystemHealth(**health_data)

# Helper functions
def _get_bill_stats(db: Session) -> BillStats:
    """Calculate bill statistics"""

    # Total and active bills
    total_bills = db.query(Bill).count()
    active_bills = db.query(Bill).filter(Bill.is_active == True).count()

    # Bills by status
    status_counts = db.query(
        Bill.status, func.count(Bill.id)
    ).filter(Bill.is_active == True).group_by(Bill.status).all()

    bills_by_status = {status or "unknown": count for status, count in status_counts}

    # Bills by state
    state_counts = db.query(
        Bill.state_or_federal, func.count(Bill.id)
    ).filter(Bill.is_active == True).group_by(Bill.state_or_federal).all()

    bills_by_state = {state or "unknown": count for state, count in state_counts}

    # Average relevance score
    avg_relevance = db.query(func.avg(Bill.relevance_score)).filter(
        Bill.is_active == True,
        Bill.relevance_score.isnot(None)
    ).scalar() or 0.0

    # High relevance bills (score >= 70)
    high_relevance_bills = db.query(Bill).filter(
        Bill.is_active == True,
        Bill.relevance_score >= 70
    ).count()

    return BillStats(
        total_bills=total_bills,
        active_bills=active_bills,
        bills_by_status=bills_by_status,
        bills_by_state=bills_by_state,
        avg_relevance_score=round(avg_relevance, 1),
        high_relevance_bills=high_relevance_bills
    )

def _get_alert_stats(db: Session, user_id: int, last_7_days: datetime) -> AlertStats:
    """Calculate alert statistics for a user"""

    base_query = db.query(ChangeAlert).filter(ChangeAlert.user_id == user_id)

    # Total and unread alerts
    total_alerts = base_query.count()
    unread_alerts = base_query.filter(ChangeAlert.is_read == False).count()

    # Alerts in last 7 days
    alerts_last_7_days = base_query.filter(
        ChangeAlert.created_at >= last_7_days
    ).count()

    # Alerts by priority
    priority_counts = db.query(
        ChangeAlert.priority, func.count(ChangeAlert.id)
    ).filter(ChangeAlert.user_id == user_id).group_by(ChangeAlert.priority).all()

    alerts_by_priority = {priority.value: count for priority, count in priority_counts}

    # Alerts by type
    type_counts = db.query(
        ChangeAlert.alert_type, func.count(ChangeAlert.id)
    ).filter(ChangeAlert.user_id == user_id).group_by(ChangeAlert.alert_type).all()

    alerts_by_type = {alert_type: count for alert_type, count in type_counts}

    return AlertStats(
        total_alerts=total_alerts,
        unread_alerts=unread_alerts,
        alerts_last_7_days=alerts_last_7_days,
        alerts_by_priority=alerts_by_priority,
        alerts_by_type=alerts_by_type
    )

def _get_change_stats(db: Session, last_7_days: datetime) -> ChangeStats:
    """Calculate change statistics"""

    # Changes in last 7 days
    changes_last_7_days = db.query(BillChange).filter(
        BillChange.detected_at >= last_7_days
    ).count()

    # Changes by severity
    severity_counts = db.query(
        BillChange.change_severity, func.count(BillChange.id)
    ).filter(
        BillChange.detected_at >= last_7_days
    ).group_by(BillChange.change_severity).all()

    changes_by_severity = {severity.value: count for severity, count in severity_counts}

    # Stage transitions in last 7 days
    stage_transitions_last_7_days = db.query(StageTransition).filter(
        StageTransition.transition_date >= last_7_days
    ).count()

    # Bills with recent activity
    bills_with_recent_activity = db.query(BillChange.bill_id).filter(
        BillChange.detected_at >= last_7_days
    ).distinct().count()

    return ChangeStats(
        changes_last_7_days=changes_last_7_days,
        changes_by_severity=changes_by_severity,
        stage_transitions_last_7_days=stage_transitions_last_7_days,
        bills_with_recent_activity=bills_with_recent_activity
    )

def _get_user_activity_stats(db: Session, user: User, last_30_days: datetime) -> UserActivityStats:
    """Calculate user activity statistics"""

    # Tracked bills (would need UserBillTracking model)
    tracked_bills = 0  # Placeholder

    # Total alerts received
    total_alerts_received = db.query(ChangeAlert).filter(
        ChangeAlert.user_id == user.id
    ).count()

    return UserActivityStats(
        tracked_bills=tracked_bills,
        total_alerts_received=total_alerts_received,
        last_login=user.last_login,
        account_created=user.created_at
    )

def _get_trending_bills(
    db: Session,
    cutoff_date: Optional[datetime] = None,
    limit: int = 20,
    min_relevance_score: float = 0
) -> list[TrendingBill]:
    """Calculate trending bills based on recent activity"""

    if cutoff_date is None:
        cutoff_date = datetime.utcnow() - timedelta(days=7)

    # Subquery for recent changes per bill
    changes_subquery = db.query(
        BillChange.bill_id,
        func.count(BillChange.id).label('recent_changes')
    ).filter(
        BillChange.detected_at >= cutoff_date
    ).group_by(BillChange.bill_id).subquery()

    # Subquery for stage transitions per bill
    transitions_subquery = db.query(
        StageTransition.bill_id,
        func.count(StageTransition.id).label('stage_transitions')
    ).filter(
        StageTransition.transition_date >= cutoff_date
    ).group_by(StageTransition.bill_id).subquery()

    # Subquery for alerts per bill
    alerts_subquery = db.query(
        ChangeAlert.bill_id,
        func.count(ChangeAlert.id).label('alerts_generated')
    ).filter(
        ChangeAlert.created_at >= cutoff_date
    ).group_by(ChangeAlert.bill_id).subquery()

    # Main query with activity scoring
    query = db.query(
        Bill,
        func.coalesce(changes_subquery.c.recent_changes, 0).label('recent_changes'),
        func.coalesce(transitions_subquery.c.stage_transitions, 0).label('stage_transitions'),
        func.coalesce(alerts_subquery.c.alerts_generated, 0).label('alerts_generated'),
        (
            func.coalesce(changes_subquery.c.recent_changes, 0) * 2 +
            func.coalesce(transitions_subquery.c.stage_transitions, 0) * 3 +
            func.coalesce(alerts_subquery.c.alerts_generated, 0) * 1
        ).label('activity_score')
    ).select_from(Bill).outerjoin(
        changes_subquery, Bill.id == changes_subquery.c.bill_id
    ).outerjoin(
        transitions_subquery, Bill.id == transitions_subquery.c.bill_id
    ).outerjoin(
        alerts_subquery, Bill.id == alerts_subquery.c.bill_id
    ).filter(
        Bill.is_active == True,
        or_(
            Bill.relevance_score.is_(None),
            Bill.relevance_score >= min_relevance_score
        )
    ).order_by(
        desc('activity_score'),
        desc(Bill.relevance_score),
        desc(Bill.updated_at)
    ).limit(limit)

    results = query.all()

    trending_bills = []
    for (bill, recent_changes, stage_transitions, alerts_generated, activity_score) in results:
        trending_bills.append(TrendingBill(
            id=bill.id,
            bill_number=bill.bill_number,
            title=bill.title,
            relevance_score=bill.relevance_score,
            activity_score=float(activity_score),
            recent_changes=recent_changes,
            stage_transitions=stage_transitions,
            alerts_generated=alerts_generated
        ))

    return trending_bills