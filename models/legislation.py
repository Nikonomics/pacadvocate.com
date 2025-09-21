from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Float, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List
from models.database import Base

class Bill(Base):
    __tablename__ = "bills"

    id = Column(Integer, primary_key=True, index=True)
    bill_number = Column(String(50), unique=True, index=True)
    title = Column(String(500), index=True)
    summary = Column(Text)
    full_text = Column(Text)
    source = Column(String(100))  # congress.gov, state legislature, etc.
    state_or_federal = Column(String(20), index=True)  # 'federal' or state abbreviation
    introduced_date = Column(DateTime, index=True)
    last_action_date = Column(DateTime, index=True)
    status = Column(String(100), index=True)
    sponsor = Column(String(200))
    committee = Column(String(200))
    chamber = Column(String(20))  # House, Senate
    created_at = Column(DateTime, default=func.now(), index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True, index=True)
    relevance_score = Column(Float, index=True)  # AI-generated relevance score (0-100)

    # SNF-specific operational scoring fields
    payment_impact = Column(String(20), index=True)  # increase, decrease, neutral
    operational_area = Column(String(50), index=True)  # Staffing, Quality, Documentation, Survey, Payment
    implementation_timeline = Column(String(20), index=True)  # Immediate (<30 days), Soon (30-90), Future (90+)
    operational_tags = Column(Text)  # JSON array of operational impact tags

    # Comment period tracking fields
    comment_deadline = Column(DateTime, index=True)  # When public comments are due
    comment_url = Column(String(500))                # Direct link to regulations.gov or comment portal
    has_comment_period = Column(Boolean, default=False, index=True)  # Whether bill has active comment period
    comment_period_urgent = Column(Boolean, default=False, index=True)  # <30 days remaining

    # Relationships
    versions = relationship("BillVersion", back_populates="bill", cascade="all, delete-orphan")
    keyword_matches = relationship("BillKeywordMatch", back_populates="bill", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="bill", cascade="all, delete-orphan")
    impact_analyses = relationship("ImpactAnalysis", back_populates="bill", cascade="all, delete-orphan")
    changes = relationship("BillChange", back_populates="bill", cascade="all, delete-orphan")

    # Indexes for search performance
    __table_args__ = (
        Index('idx_bill_search', 'title', 'summary'),
        Index('idx_bill_date_status', 'last_action_date', 'status'),
        Index('idx_bill_sponsor_committee', 'sponsor', 'committee'),
    )

class BillCreate(BaseModel):
    bill_number: str
    title: str
    summary: Optional[str] = None
    full_text: Optional[str] = None
    source: Optional[str] = None
    state_or_federal: str = "federal"
    introduced_date: Optional[datetime] = None
    last_action_date: Optional[datetime] = None
    status: Optional[str] = None
    sponsor: Optional[str] = None
    committee: Optional[str] = None
    chamber: Optional[str] = None
    payment_impact: Optional[str] = None
    operational_area: Optional[str] = None
    implementation_timeline: Optional[str] = None
    operational_tags: Optional[str] = None

class BillResponse(BaseModel):
    id: int
    bill_number: str
    title: str
    summary: Optional[str]
    source: Optional[str]
    state_or_federal: str
    introduced_date: Optional[datetime]
    last_action_date: Optional[datetime]
    status: Optional[str]
    sponsor: Optional[str]
    committee: Optional[str]
    chamber: Optional[str]
    created_at: datetime
    updated_at: datetime
    is_active: bool
    relevance_score: Optional[float]
    payment_impact: Optional[str]
    operational_area: Optional[str]
    implementation_timeline: Optional[str]
    operational_tags: Optional[str]

    class Config:
        from_attributes = True


class BillVersion(Base):
    __tablename__ = "bill_versions"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=False, index=True)
    version_number = Column(String(20))  # e.g., "1.0", "2.1", "Enrolled"
    title = Column(String(500))
    summary = Column(Text)
    full_text = Column(Text)
    introduced_date = Column(DateTime)
    last_action_date = Column(DateTime)
    status = Column(String(100))
    sponsor = Column(String(200))
    committee = Column(String(200))
    changes_summary = Column(Text)  # Summary of what changed in this version
    created_at = Column(DateTime, default=func.now())
    is_current = Column(Boolean, default=False, index=True)

    # Relationships
    bill = relationship("Bill", back_populates="versions")

    __table_args__ = (
        Index('idx_bill_version_current', 'bill_id', 'is_current'),
        Index('idx_bill_version_date', 'bill_id', 'created_at'),
    )


class Keyword(Base):
    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True, index=True)
    term = Column(String(200), unique=True, index=True)
    category = Column(String(100), index=True)  # e.g., "SNF", "Medicare", "Staffing", "PDPM"
    synonyms = Column(Text)  # JSON array of synonyms
    importance_weight = Column(Float, default=1.0)  # Weight for scoring matches
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=func.now())
    created_by_user_id = Column(Integer, ForeignKey("users.id"))

    # Relationships
    keyword_matches = relationship("BillKeywordMatch", back_populates="keyword", cascade="all, delete-orphan")
    created_by = relationship("User", back_populates="created_keywords")


class BillKeywordMatch(Base):
    __tablename__ = "bill_keyword_matches"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=False, index=True)
    keyword_id = Column(Integer, ForeignKey("keywords.id"), nullable=False, index=True)
    match_count = Column(Integer, default=1)  # Number of times keyword appears
    match_locations = Column(Text)  # JSON array of where matches were found
    confidence_score = Column(Float)  # AI confidence in the match relevance
    context_snippet = Column(Text)  # Brief context around the match
    created_at = Column(DateTime, default=func.now())

    # Relationships
    bill = relationship("Bill", back_populates="keyword_matches")
    keyword = relationship("Keyword", back_populates="keyword_matches")

    __table_args__ = (
        Index('idx_bill_keyword_unique', 'bill_id', 'keyword_id', unique=True),
        Index('idx_bill_keyword_score', 'bill_id', 'confidence_score'),
    )


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True)
    hashed_password = Column(String(255))
    full_name = Column(String(200))
    organization = Column(String(200))
    role = Column(String(50), default="user")  # user, admin, analyst
    is_active = Column(Boolean, default=True, index=True)
    is_verified = Column(Boolean, default=False)
    preferences = Column(Text)  # JSON preferences for alerts, keywords, etc.
    created_at = Column(DateTime, default=func.now())
    last_login = Column(DateTime)

    # Relationships
    alerts = relationship("Alert", back_populates="user", cascade="all, delete-orphan")
    created_keywords = relationship("Keyword", back_populates="created_by")
    alert_preferences = relationship("AlertPreferences", back_populates="user", uselist=False, cascade="all, delete-orphan")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=False, index=True)
    alert_type = Column(String(50), index=True)  # status_change, new_version, keyword_match
    message = Column(Text)
    is_read = Column(Boolean, default=False, index=True)
    severity = Column(String(20), default="medium")  # low, medium, high, critical
    triggered_at = Column(DateTime, default=func.now(), index=True)
    read_at = Column(DateTime)

    # Relationships
    user = relationship("User", back_populates="alerts")
    bill = relationship("Bill", back_populates="alerts")

    __table_args__ = (
        Index('idx_user_alerts_unread', 'user_id', 'is_read', 'triggered_at'),
        Index('idx_bill_alerts', 'bill_id', 'alert_type'),
    )


class ImpactAnalysis(Base):
    __tablename__ = "impact_analyses"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=False, index=True)
    analysis_version = Column(String(20), default="1.0")
    impact_score = Column(Float, index=True)  # 0-100 score of potential impact
    impact_category = Column(String(100))  # Financial, Operational, Regulatory, etc.
    summary = Column(Text)
    detailed_analysis = Column(Text)
    key_provisions = Column(Text)  # JSON array of key bill provisions
    affected_areas = Column(Text)  # JSON array of areas this bill affects
    recommendation = Column(Text)
    confidence_score = Column(Float)  # AI confidence in the analysis
    model_used = Column(String(100))  # GPT-4, Claude, etc.
    analysis_prompt = Column(Text)  # The prompt used for analysis
    created_at = Column(DateTime, default=func.now())
    created_by_user_id = Column(Integer, ForeignKey("users.id"))

    # Relationships
    bill = relationship("Bill", back_populates="impact_analyses")
    created_by = relationship("User")

    __table_args__ = (
        Index('idx_impact_score', 'impact_score'),
        Index('idx_impact_category', 'impact_category'),
        Index('idx_bill_impact_latest', 'bill_id', 'created_at'),
    )


# Pydantic schemas for additional models
class BillVersionCreate(BaseModel):
    bill_id: int
    version_number: str
    title: Optional[str] = None
    summary: Optional[str] = None
    full_text: Optional[str] = None
    introduced_date: Optional[datetime] = None
    last_action_date: Optional[datetime] = None
    status: Optional[str] = None
    sponsor: Optional[str] = None
    committee: Optional[str] = None
    changes_summary: Optional[str] = None
    is_current: bool = False


class KeywordCreate(BaseModel):
    term: str
    category: str
    synonyms: Optional[str] = None
    importance_weight: float = 1.0


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    organization: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    organization: Optional[str]
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


class AlertResponse(BaseModel):
    id: int
    bill_id: int
    alert_type: str
    message: str
    is_read: bool
    severity: str
    triggered_at: datetime
    read_at: Optional[datetime]

    class Config:
        from_attributes = True


class ImpactAnalysisResponse(BaseModel):
    id: int
    bill_id: int
    analysis_version: str
    impact_score: Optional[float]
    impact_category: Optional[str]
    summary: Optional[str]
    recommendation: Optional[str]
    confidence_score: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True