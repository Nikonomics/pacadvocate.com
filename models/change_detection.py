from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Float, Enum, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List, Dict, Any
from models.database import Base
import enum

class ChangeType(enum.Enum):
    TEXT_AMENDMENT = "text_amendment"
    STATUS_CHANGE = "status_change"
    STAGE_TRANSITION = "stage_transition"
    SPONSOR_CHANGE = "sponsor_change"
    COMMITTEE_ASSIGNMENT = "committee_assignment"
    VOTING_OUTCOME = "voting_outcome"

class ChangeSeverity(enum.Enum):
    MINOR = "minor"          # Typo fixes, formatting
    MODERATE = "moderate"    # Small text changes, date adjustments
    SIGNIFICANT = "significant"  # New provisions, policy changes
    CRITICAL = "critical"    # Major amendments, complete rewrites

class AlertPriority(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class BillStage(enum.Enum):
    INTRODUCED = "introduced"
    COMMITTEE_REVIEW = "committee_review"
    COMMITTEE_MARKUP = "committee_markup"
    COMMITTEE_REPORTED = "committee_reported"
    FLOOR_CONSIDERATION = "floor_consideration"
    PASSED_CHAMBER = "passed_chamber"
    SENT_TO_OTHER_CHAMBER = "sent_to_other_chamber"
    OTHER_CHAMBER_COMMITTEE = "other_chamber_committee"
    OTHER_CHAMBER_FLOOR = "other_chamber_floor"
    PASSED_BOTH_CHAMBERS = "passed_both_chambers"
    SENT_TO_PRESIDENT = "sent_to_president"
    SIGNED_INTO_LAW = "signed_into_law"
    VETOED = "vetoed"
    WITHDRAWN = "withdrawn"
    DIED = "died"

class BillChange(Base):
    __tablename__ = "bill_changes"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=False, index=True)
    change_type = Column(Enum(ChangeType), nullable=False, index=True)
    change_severity = Column(Enum(ChangeSeverity), nullable=False, index=True)

    # Change details
    old_value = Column(Text)  # JSON or text of old state
    new_value = Column(Text)  # JSON or text of new state
    diff_summary = Column(Text)  # Human-readable summary of changes
    diff_details = Column(Text)  # Technical diff output

    # Context
    field_changed = Column(String(100))  # title, summary, full_text, status, etc.
    change_description = Column(Text)    # AI-generated description
    impact_assessment = Column(Text)     # Assessment of change impact

    # Metadata
    detected_at = Column(DateTime, default=func.now(), index=True)
    confidence_score = Column(Float)     # AI confidence in change significance
    word_count_delta = Column(Integer)   # Change in word count

    # Relationships
    bill = relationship("Bill", back_populates="changes")
    alerts = relationship("ChangeAlert", back_populates="bill_change", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_bill_change_severity', 'bill_id', 'change_severity'),
        Index('idx_change_detection_time', 'detected_at', 'change_type'),
    )

class StageTransition(Base):
    __tablename__ = "stage_transitions"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=False, index=True)

    # Stage information
    from_stage = Column(Enum(BillStage), index=True)
    to_stage = Column(Enum(BillStage), nullable=False, index=True)
    transition_date = Column(DateTime, default=func.now(), index=True)

    # Transition details
    committee_name = Column(String(200))
    vote_count = Column(String(50))      # e.g., "23-17", "voice vote"
    notes = Column(Text)                 # Additional details about transition

    # Predictive analytics
    passage_likelihood = Column(Float)    # 0-1 probability of final passage
    estimated_timeline = Column(String(100))  # e.g., "2-4 weeks"
    next_expected_stage = Column(Enum(BillStage))

    # Relationships
    bill = relationship("Bill")
    alerts = relationship("ChangeAlert", back_populates="stage_transition", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_stage_transition_bill', 'bill_id', 'transition_date'),
        Index('idx_stage_current', 'to_stage', 'transition_date'),
    )

class ChangeAlert(Base):
    __tablename__ = "change_alerts"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Alert content
    alert_type = Column(String(50), nullable=False, index=True)  # change, transition, threshold
    priority = Column(Enum(AlertPriority), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)

    # References
    bill_change_id = Column(Integer, ForeignKey("bill_changes.id"), index=True)
    stage_transition_id = Column(Integer, ForeignKey("stage_transitions.id"), index=True)

    # Status
    is_sent = Column(Boolean, default=False, index=True)
    is_read = Column(Boolean, default=False, index=True)
    is_dismissed = Column(Boolean, default=False, index=True)

    # Deduplication
    dedup_hash = Column(String(64), index=True)  # Hash to prevent duplicate alerts
    similar_alert_count = Column(Integer, default=1)  # Count of similar alerts grouped

    # Timing
    created_at = Column(DateTime, default=func.now(), index=True)
    sent_at = Column(DateTime, index=True)
    read_at = Column(DateTime)

    # Relationships
    bill = relationship("Bill")
    user = relationship("User")
    bill_change = relationship("BillChange", back_populates="alerts")
    stage_transition = relationship("StageTransition", back_populates="alerts")

    __table_args__ = (
        Index('idx_alert_user_unread', 'user_id', 'is_read', 'priority'),
        Index('idx_alert_dedup', 'dedup_hash', 'bill_id'),
        Index('idx_alert_sending', 'is_sent', 'created_at'),
    )

class AlertPreferences(Base):
    __tablename__ = "alert_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)

    # Notification settings
    email_enabled = Column(Boolean, default=True)
    email_frequency = Column(String(20), default="immediate")  # immediate, daily, weekly

    # Alert filtering
    min_priority = Column(Enum(AlertPriority), default=AlertPriority.MEDIUM)
    min_relevance_score = Column(Float, default=40.0)  # Minimum bill relevance score

    # Change types to monitor
    monitor_text_changes = Column(Boolean, default=True)
    monitor_stage_transitions = Column(Boolean, default=True)
    monitor_status_changes = Column(Boolean, default=True)
    monitor_voting = Column(Boolean, default=True)

    # Severity filtering
    alert_on_minor = Column(Boolean, default=False)
    alert_on_moderate = Column(Boolean, default=True)
    alert_on_significant = Column(Boolean, default=True)
    alert_on_critical = Column(Boolean, default=True)

    # Keywords for custom filtering (JSON array)
    important_keywords = Column(Text)    # JSON list of keywords that upgrade priority
    excluded_keywords = Column(Text)     # JSON list of keywords that suppress alerts

    # Timing preferences
    quiet_hours_start = Column(String(5))  # e.g., "22:00"
    quiet_hours_end = Column(String(5))    # e.g., "08:00"
    timezone = Column(String(50), default="UTC")

    # Relationships
    user = relationship("User", back_populates="alert_preferences")

class ChangeDetectionConfig(Base):
    __tablename__ = "change_detection_config"

    id = Column(Integer, primary_key=True, index=True)

    # Detection settings
    check_interval_hours = Column(Integer, default=4)
    diff_algorithm = Column(String(50), default="unified")  # unified, context, semantic

    # Thresholds
    minor_change_threshold = Column(Float, default=0.1)      # % of text changed
    moderate_change_threshold = Column(Float, default=0.25)
    significant_change_threshold = Column(Float, default=0.5)

    # AI settings
    use_ai_classification = Column(Boolean, default=True)
    ai_confidence_threshold = Column(Float, default=0.7)

    # Deduplication settings
    dedup_window_hours = Column(Integer, default=24)
    max_similar_alerts = Column(Integer, default=5)

    # System settings
    last_check_at = Column(DateTime)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

# Pydantic models for API
class BillChangeResponse(BaseModel):
    id: int
    bill_id: int
    change_type: ChangeType
    change_severity: ChangeSeverity
    diff_summary: str
    change_description: Optional[str]
    detected_at: datetime
    confidence_score: Optional[float]

    class Config:
        from_attributes = True

class StageTransitionResponse(BaseModel):
    id: int
    bill_id: int
    from_stage: Optional[BillStage]
    to_stage: BillStage
    transition_date: datetime
    committee_name: Optional[str]
    vote_count: Optional[str]
    passage_likelihood: Optional[float]

    class Config:
        from_attributes = True

class ChangeAlertResponse(BaseModel):
    id: int
    bill_id: int
    alert_type: str
    priority: AlertPriority
    title: str
    message: str
    is_sent: bool
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

class AlertPreferencesCreate(BaseModel):
    email_enabled: bool = True
    email_frequency: str = "immediate"
    min_priority: AlertPriority = AlertPriority.MEDIUM
    min_relevance_score: float = 40.0
    monitor_text_changes: bool = True
    monitor_stage_transitions: bool = True
    monitor_status_changes: bool = True
    monitor_voting: bool = True
    alert_on_minor: bool = False
    alert_on_moderate: bool = True
    alert_on_significant: bool = True
    alert_on_critical: bool = True