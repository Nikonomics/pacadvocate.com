from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, desc
from typing import Optional
import math

from models.database import get_db
from models.legislation import User, Bill
from models.change_detection import ChangeAlert, AlertPreferences, AlertPriority
from api.schemas.alerts import (
    AlertResponse, AlertListResponse, AlertUpdateRequest,
    AlertPreferencesCreate, AlertPreferencesUpdate, AlertPreferencesResponse
)
from api.auth.dependencies import get_current_user
from api.middleware.caching import cached, get_cache_config, invalidate_user_cache

router = APIRouter(prefix="/alerts", tags=["Alerts"])

@router.get("/", response_model=AlertListResponse)
@cached(**get_cache_config("user_alerts"))
async def get_user_alerts(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    unread_only: bool = Query(False, description="Show only unread alerts"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    alert_type: Optional[str] = Query(None, description="Filter by alert type"),
    bill_id: Optional[int] = Query(None, description="Filter by bill ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get user's alert history with filtering and pagination

    **Filters:**
    - **unread_only**: Show only unread alerts
    - **priority**: Filter by priority (low, medium, high, urgent)
    - **alert_type**: Filter by type (change, stage_transition, deadline, custom)
    - **bill_id**: Filter by specific bill

    **Returns:**
    - Paginated list of alerts
    - Total count and unread count
    """

    # Build query
    query = db.query(ChangeAlert).options(
        joinedload(ChangeAlert.bill)
    ).filter(
        ChangeAlert.user_id == current_user.id,
        ChangeAlert.is_dismissed == False
    )

    # Apply filters
    if unread_only:
        query = query.filter(ChangeAlert.is_read == False)

    if priority:
        try:
            priority_enum = AlertPriority(priority)
            query = query.filter(ChangeAlert.priority == priority_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid priority: {priority}"
            )

    if alert_type:
        query = query.filter(ChangeAlert.alert_type == alert_type)

    if bill_id:
        query = query.filter(ChangeAlert.bill_id == bill_id)

    # Order by created_at descending
    query = query.order_by(desc(ChangeAlert.created_at))

    # Get total and unread counts
    total = query.count()
    unread_query = db.query(ChangeAlert).filter(
        ChangeAlert.user_id == current_user.id,
        ChangeAlert.is_read == False,
        ChangeAlert.is_dismissed == False
    )
    unread_count = unread_query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    alerts = query.offset(offset).limit(page_size).all()

    # Build response
    alert_responses = []
    for alert in alerts:
        alert_data = AlertResponse.from_orm(alert).__dict__
        if alert.bill:
            alert_data["bill_number"] = alert.bill.bill_number
            alert_data["bill_title"] = alert.bill.title
        alert_responses.append(AlertResponse(**alert_data))

    return AlertListResponse(
        alerts=alert_responses,
        total=total,
        unread_count=unread_count,
        page=page,
        page_size=page_size
    )

@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get specific alert details"""

    alert = db.query(ChangeAlert).options(
        joinedload(ChangeAlert.bill)
    ).filter(
        ChangeAlert.id == alert_id,
        ChangeAlert.user_id == current_user.id
    ).first()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )

    # Mark as read if not already
    if not alert.is_read:
        alert.is_read = True
        alert.read_at = datetime.utcnow()
        db.commit()

        # Invalidate cache
        await invalidate_user_cache(current_user.id)

    # Build response
    alert_data = AlertResponse.from_orm(alert).__dict__
    if alert.bill:
        alert_data["bill_number"] = alert.bill.bill_number
        alert_data["bill_title"] = alert.bill.title

    return AlertResponse(**alert_data)

@router.patch("/{alert_id}")
async def update_alert(
    alert_id: int,
    update_data: AlertUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update alert status (mark as read/unread, dismiss)"""

    alert = db.query(ChangeAlert).filter(
        ChangeAlert.id == alert_id,
        ChangeAlert.user_id == current_user.id
    ).first()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )

    # Update fields
    if update_data.is_read is not None:
        alert.is_read = update_data.is_read
        if update_data.is_read:
            alert.read_at = datetime.utcnow()
        else:
            alert.read_at = None

    if update_data.is_dismissed is not None:
        alert.is_dismissed = update_data.is_dismissed

    db.commit()

    # Invalidate cache
    await invalidate_user_cache(current_user.id)

    return {"message": "Alert updated successfully"}

@router.post("/mark-all-read")
async def mark_all_alerts_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark all user alerts as read"""

    # Update all unread alerts
    db.query(ChangeAlert).filter(
        ChangeAlert.user_id == current_user.id,
        ChangeAlert.is_read == False,
        ChangeAlert.is_dismissed == False
    ).update({
        "is_read": True,
        "read_at": datetime.utcnow()
    })

    db.commit()

    # Invalidate cache
    await invalidate_user_cache(current_user.id)

    return {"message": "All alerts marked as read"}

@router.delete("/cleanup")
async def cleanup_old_alerts(
    days: int = Query(30, ge=1, le=365, description="Delete dismissed alerts older than X days"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Clean up old dismissed alerts"""

    from datetime import timedelta
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # Delete old dismissed alerts
    deleted_count = db.query(ChangeAlert).filter(
        ChangeAlert.user_id == current_user.id,
        ChangeAlert.is_dismissed == True,
        ChangeAlert.created_at < cutoff_date
    ).delete()

    db.commit()

    # Invalidate cache
    await invalidate_user_cache(current_user.id)

    return {"message": f"Cleaned up {deleted_count} old alerts"}

# Alert Preferences endpoints
@router.get("/preferences", response_model=AlertPreferencesResponse)
async def get_alert_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get user's alert preferences"""

    preferences = db.query(AlertPreferences).filter(
        AlertPreferences.user_id == current_user.id
    ).first()

    if not preferences:
        # Return default preferences
        return AlertPreferencesResponse(
            id=0,
            user_id=current_user.id,
            email_enabled=True,
            email_frequency="immediate",
            min_priority=AlertPriority.MEDIUM,
            min_relevance_score=40.0,
            monitor_text_changes=True,
            monitor_stage_transitions=True,
            monitor_status_changes=True,
            alert_on_minor=False,
            alert_on_moderate=True,
            alert_on_significant=True,
            alert_on_critical=True
        )

    return AlertPreferencesResponse.from_orm(preferences)

@router.post("/preferences", response_model=AlertPreferencesResponse)
async def create_alert_preferences(
    preferences_data: AlertPreferencesCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create or update user alert preferences"""

    # Check if preferences already exist
    existing_preferences = db.query(AlertPreferences).filter(
        AlertPreferences.user_id == current_user.id
    ).first()

    if existing_preferences:
        # Update existing preferences
        for field, value in preferences_data.dict().items():
            setattr(existing_preferences, field, value)

        db.commit()
        db.refresh(existing_preferences)

        # Invalidate cache
        await invalidate_user_cache(current_user.id)

        return AlertPreferencesResponse.from_orm(existing_preferences)
    else:
        # Create new preferences
        preferences = AlertPreferences(
            user_id=current_user.id,
            **preferences_data.dict()
        )

        db.add(preferences)
        db.commit()
        db.refresh(preferences)

        # Invalidate cache
        await invalidate_user_cache(current_user.id)

        return AlertPreferencesResponse.from_orm(preferences)

@router.put("/preferences", response_model=AlertPreferencesResponse)
async def update_alert_preferences(
    preferences_update: AlertPreferencesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update user alert preferences"""

    preferences = db.query(AlertPreferences).filter(
        AlertPreferences.user_id == current_user.id
    ).first()

    if not preferences:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert preferences not found. Create preferences first."
        )

    # Update fields
    for field, value in preferences_update.dict(exclude_unset=True).items():
        setattr(preferences, field, value)

    db.commit()
    db.refresh(preferences)

    # Invalidate cache
    await invalidate_user_cache(current_user.id)

    return AlertPreferencesResponse.from_orm(preferences)

# Statistics endpoint
@router.get("/stats")
@cached(expire=300)  # 5 minutes cache
async def get_alert_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get user's alert statistics"""

    from datetime import timedelta

    # Get various time periods
    now = datetime.utcnow()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    # Base query
    base_query = db.query(ChangeAlert).filter(
        ChangeAlert.user_id == current_user.id
    )

    stats = {
        "total_alerts": base_query.count(),
        "unread_alerts": base_query.filter(ChangeAlert.is_read == False).count(),
        "alerts_last_24h": base_query.filter(ChangeAlert.created_at >= last_24h).count(),
        "alerts_last_7d": base_query.filter(ChangeAlert.created_at >= last_7d).count(),
        "alerts_last_30d": base_query.filter(ChangeAlert.created_at >= last_30d).count(),
    }

    # Alerts by priority
    stats["by_priority"] = {}
    for priority in AlertPriority:
        count = base_query.filter(ChangeAlert.priority == priority).count()
        stats["by_priority"][priority.value] = count

    # Alerts by type
    types = ["change", "stage_transition", "deadline", "custom"]
    stats["by_type"] = {}
    for alert_type in types:
        count = base_query.filter(ChangeAlert.alert_type == alert_type).count()
        stats["by_type"][alert_type] = count

    return stats

from datetime import datetime