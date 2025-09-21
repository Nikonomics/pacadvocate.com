from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, func
from typing import Optional, List
from datetime import datetime
import math

from models.database import get_db
from models.legislation import Bill, User, ImpactAnalysis
from models.change_detection import BillChange, StageTransition, ChangeAlert
from api.schemas.bills import (
    BillResponse, BillDetailResponse, BillListResponse, BillFilters,
    BillTrackingRequest, BillTrackingResponse, BillCreate, BillUpdate
)
from api.auth.dependencies import get_current_user, get_optional_current_user
from api.middleware.caching import cached, get_cache_config, cache_key_for_bill
from services.ai.bill_analysis_service import BillAnalysisService

router = APIRouter(prefix="/bills", tags=["Bills"])

def handle_null_risk_scores(bill_data: dict) -> dict:
    """Convert null risk scores to 0 and null risk_tags to empty array"""
    risk_fields = ['reimbursement_risk', 'staffing_risk', 'compliance_risk', 'quality_risk', 'total_risk_score']
    for field in risk_fields:
        if bill_data.get(field) is None:
            bill_data[field] = 0
    if bill_data.get('risk_tags') is None:
        bill_data['risk_tags'] = '[]'
    return bill_data

@router.get("/", response_model=BillListResponse)
# @cached(**get_cache_config("bills_list"))
async def get_bills(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Page size"),
    state: Optional[str] = Query(None, description="Filter by state (federal, CA, TX, etc.)"),
    status: Optional[str] = Query(None, description="Filter by bill status"),
    min_ai_relevance: Optional[float] = Query(50, ge=0, le=100, description="Minimum AI relevance score (default: 50)"),
    max_ai_relevance: Optional[float] = Query(None, ge=0, le=100, description="Maximum AI relevance score"),
    date_from: Optional[datetime] = Query(None, description="Filter by date from"),
    date_to: Optional[datetime] = Query(None, description="Filter by date to"),
    search: Optional[str] = Query(None, description="Search in title and summary"),
    source: Optional[str] = Query(None, description="Filter by source"),
    chamber: Optional[str] = Query(None, description="Filter by chamber"),
    sort_by: str = Query("ai_relevance_score", description="Sort field"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    db: Session = Depends(get_db)
):
    """
    Get paginated list of bills with filtering and sorting options

    **AI-Based Filtering (NEW):**
    - Bills are now filtered by AI relevance score (default: >50) instead of keyword matching
    - **min_ai_relevance**: Minimum AI relevance score (default: 50, shows only SNF-relevant bills)
    - **max_ai_relevance**: Maximum AI relevance score

    **Other Filters:**
    - **state**: Filter by state or federal level
    - **status**: Filter by bill status
    - **date_from/date_to**: Filter by last action date range
    - **search**: Search in bill title and summary
    - **source**: Filter by data source
    - **chamber**: Filter by legislative chamber

    **Sorting:**
    - **sort_by**: Field to sort by (ai_relevance_score, last_action_date, created_at, title)
    - **sort_order**: asc or desc
    """

    # Build query - now using AI relevance filtering by default
    query = db.query(Bill).filter(Bill.is_active == True)

    # Apply AI relevance filtering (replaces old keyword-based filtering)
    if min_ai_relevance is not None:
        query = query.filter(Bill.ai_relevance_score >= min_ai_relevance)

    if max_ai_relevance is not None:
        query = query.filter(Bill.ai_relevance_score <= max_ai_relevance)

    # Apply other filters
    if state:
        query = query.filter(Bill.state_or_federal == state)

    if status:
        query = query.filter(Bill.status.ilike(f"%{status}%"))

    if date_from:
        query = query.filter(Bill.last_action_date >= date_from)

    if date_to:
        query = query.filter(Bill.last_action_date <= date_to)

    if search:
        search_filter = or_(
            Bill.title.ilike(f"%{search}%"),
            Bill.summary.ilike(f"%{search}%"),
            Bill.bill_number.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)

    if source:
        query = query.filter(Bill.source == source)

    if chamber:
        query = query.filter(Bill.chamber == chamber)

    # Apply sorting
    sort_column = getattr(Bill, sort_by, Bill.relevance_score)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc().nullslast())
    else:
        query = query.order_by(sort_column.asc().nullsfirst())

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    bills = query.offset(offset).limit(page_size).all()

    # Calculate pagination info
    total_pages = math.ceil(total / page_size)

    # Convert bills to response format with null risk handling
    bill_responses = []
    for bill in bills:
        bill_data = BillResponse.from_orm(bill).__dict__.copy()
        bill_responses.append(handle_null_risk_scores(bill_data))

    return BillListResponse(
        bills=bill_responses,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )

@router.get("/{bill_id}", response_model=BillDetailResponse)
# @cached(**get_cache_config("bill_detail"))
async def get_bill(
    bill_id: int,
    include_ai_analysis: bool = Query(True, description="Include AI analysis"),
    include_recent_changes: bool = Query(True, description="Include recent changes"),
    include_stage_transitions: bool = Query(True, description="Include stage transitions"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Get detailed information about a specific bill

    **Includes:**
    - Full bill details
    - AI analysis (if requested and available)
    - Recent changes and amendments
    - Stage transition history
    - User tracking status (if authenticated)
    """

    # Get bill with relationships
    bill = db.query(Bill).options(
        joinedload(Bill.impact_analyses),
        joinedload(Bill.changes),
    ).filter(Bill.id == bill_id, Bill.is_active == True).first()

    if not bill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bill not found"
        )

    # Build response with null risk score handling
    response_model = BillDetailResponse.from_orm(bill)
    response_data = response_model.__dict__.copy()
    response_data = handle_null_risk_scores(response_data)

    # Add AI analysis if requested
    if include_ai_analysis:
        latest_analysis = db.query(ImpactAnalysis).filter(
            ImpactAnalysis.bill_id == bill_id
        ).order_by(ImpactAnalysis.created_at.desc()).first()

        if latest_analysis:
            response_data["ai_analysis"] = {
                "summary": latest_analysis.summary,
                "detailed_analysis": latest_analysis.detailed_analysis,
                "key_provisions": latest_analysis.key_provisions,
                "recommendation": latest_analysis.recommendation,
                "confidence_score": latest_analysis.confidence_score,
                "model_used": latest_analysis.model_used,
                "created_at": latest_analysis.created_at
            }

    # Add recent changes if requested
    if include_recent_changes:
        recent_changes = db.query(BillChange).filter(
            BillChange.bill_id == bill_id
        ).order_by(BillChange.detected_at.desc()).limit(5).all()

        response_data["recent_changes"] = [
            {
                "id": change.id,
                "change_type": change.change_type.value,
                "change_severity": change.change_severity.value,
                "diff_summary": change.diff_summary,
                "change_description": change.change_description,
                "detected_at": change.detected_at,
                "confidence_score": change.confidence_score
            }
            for change in recent_changes
        ]

    # Add stage transitions if requested
    if include_stage_transitions:
        stage_transitions = db.query(StageTransition).filter(
            StageTransition.bill_id == bill_id
        ).order_by(StageTransition.transition_date.desc()).limit(10).all()

        response_data["stage_transitions"] = [
            {
                "id": transition.id,
                "from_stage": transition.from_stage.value if transition.from_stage else None,
                "to_stage": transition.to_stage.value if transition.to_stage else None,
                "transition_date": transition.transition_date,
                "committee_name": transition.committee_name,
                "vote_count": transition.vote_count,
                "passage_likelihood": transition.passage_likelihood,
                "notes": transition.notes
            }
            for transition in stage_transitions
        ]

    # Check if user is tracking this bill
    if current_user:
        # Check if user is tracking this bill (would need a UserBillTracking model)
        # For now, assume not tracked
        response_data["is_tracked_by_user"] = False

    return BillDetailResponse(**response_data)

@router.post("/{bill_id}/track", response_model=BillTrackingResponse)
async def track_bill(
    bill_id: int,
    tracking_request: BillTrackingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Subscribe to updates for a specific bill

    **Options:**
    - **alert_on_changes**: Receive alerts when bill text changes
    - **alert_on_stage_transitions**: Receive alerts when bill moves through stages
    - **min_change_severity**: Minimum severity for change alerts (minor, moderate, significant, critical)
    """

    # Check if bill exists
    bill = db.query(Bill).filter(Bill.id == bill_id, Bill.is_active == True).first()
    if not bill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bill not found"
        )

    # For this implementation, we'll store tracking preferences in alert preferences
    # In a full implementation, you'd create a UserBillTracking model

    # Create response (mock for now)
    return BillTrackingResponse(
        id=1,  # Would be actual tracking record ID
        bill_id=bill_id,
        user_id=current_user.id,
        alert_on_changes=tracking_request.alert_on_changes,
        alert_on_stage_transitions=tracking_request.alert_on_stage_transitions,
        min_change_severity=tracking_request.min_change_severity,
        created_at=datetime.utcnow()
    )

@router.delete("/{bill_id}/track")
async def untrack_bill(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Stop tracking a bill"""

    # Check if bill exists
    bill = db.query(Bill).filter(Bill.id == bill_id, Bill.is_active == True).first()
    if not bill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bill not found"
        )

    # Remove tracking (implementation would remove from UserBillTracking table)

    return {"message": "Bill tracking removed successfully"}

@router.post("/{bill_id}/analyze")
async def analyze_bill(
    bill_id: int,
    force_refresh: bool = Query(False, description="Force new analysis even if cached"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Trigger AI analysis for a specific bill

    **Note:** This endpoint requires authentication and may have usage limits
    """

    # Check if bill exists
    bill = db.query(Bill).filter(Bill.id == bill_id, Bill.is_active == True).first()
    if not bill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bill not found"
        )

    try:
        # Initialize analysis service
        analysis_service = BillAnalysisService()

        # Analyze the bill
        analysis, metrics = analysis_service.analyze_bill_from_db(
            bill_id, force_refresh=force_refresh
        )

        return {
            "message": "Analysis completed successfully",
            "analysis": {
                "one_line_summary": analysis.one_line_summary,
                "key_provisions_snf": analysis.key_provisions_snf,
                "financial_impact": analysis.financial_impact,
                "implementation_timeline": analysis.implementation_timeline,
                "action_required": analysis.action_required,
                "analysis_confidence": analysis.analysis_confidence,
                "model_used": analysis.model_used,
                "tokens_used": analysis.tokens_used,
                "estimated_cost": analysis.estimated_cost
            },
            "metrics": {
                "response_time": metrics.response_time,
                "cache_hit": metrics.cache_hit,
                "total_tokens": metrics.total_tokens
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
        )

# Admin endpoints
@router.post("/", response_model=BillResponse)
async def create_bill(
    bill_data: BillCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # Could add admin check
):
    """Create a new bill (Admin only)"""

    # Check if bill already exists
    existing_bill = db.query(Bill).filter(
        Bill.bill_number == bill_data.bill_number
    ).first()

    if existing_bill:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bill with this number already exists"
        )

    # Create new bill
    bill = Bill(**bill_data.dict())
    db.add(bill)
    db.commit()
    db.refresh(bill)

    return BillResponse.from_orm(bill)

@router.put("/{bill_id}", response_model=BillResponse)
async def update_bill(
    bill_id: int,
    bill_update: BillUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # Could add admin check
):
    """Update a bill (Admin only)"""

    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    if not bill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bill not found"
        )

    # Update fields
    for field, value in bill_update.dict(exclude_unset=True).items():
        setattr(bill, field, value)

    bill.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(bill)

    return BillResponse.from_orm(bill)