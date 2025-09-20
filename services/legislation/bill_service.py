from sqlalchemy.orm import Session
from models.legislation import Bill, BillCreate, BillVersion, BillVersionCreate
from services.analysis.keyword_matcher import KeywordMatcher
from services.alerts.alert_service import AlertService
from typing import List, Optional
from datetime import datetime

class BillService:
    def __init__(self, db: Session):
        self.db = db
        self.keyword_matcher = KeywordMatcher(db)
        self.alert_service = AlertService(db)

    def create_bill(self, bill: BillCreate) -> Bill:
        db_bill = Bill(**bill.dict())
        self.db.add(db_bill)
        self.db.commit()
        self.db.refresh(db_bill)

        # Process keywords for the new bill
        try:
            self.keyword_matcher.process_bill_keywords(db_bill.id)
        except Exception as e:
            print(f"Warning: Failed to process keywords for bill {db_bill.id}: {e}")

        return db_bill

    def get_bill(self, bill_id: int) -> Optional[Bill]:
        return self.db.query(Bill).filter(Bill.id == bill_id).first()

    def get_bills(self, skip: int = 0, limit: int = 100) -> List[Bill]:
        return self.db.query(Bill).filter(Bill.is_active == True).offset(skip).limit(limit).all()

    def get_bill_by_number(self, bill_number: str) -> Optional[Bill]:
        return self.db.query(Bill).filter(Bill.bill_number == bill_number).first()

    def update_bill(self, bill_id: int, bill_update: dict) -> Optional[Bill]:
        bill = self.get_bill(bill_id)
        if bill:
            old_status = bill.status

            # Create version before updating if significant changes
            if self._should_create_version(bill_update):
                self.create_bill_version(bill)

            for key, value in bill_update.items():
                setattr(bill, key, value)

            self.db.commit()
            self.db.refresh(bill)

            # Check for status changes and create alerts
            if 'status' in bill_update and old_status != bill.status:
                try:
                    self.alert_service.create_bill_status_alert(
                        bill_id, old_status, bill.status
                    )
                except Exception as e:
                    print(f"Warning: Failed to create status change alert: {e}")

            # Reprocess keywords if content changed
            if any(key in bill_update for key in ['title', 'summary', 'full_text']):
                try:
                    self.keyword_matcher.process_bill_keywords(bill_id)
                except Exception as e:
                    print(f"Warning: Failed to reprocess keywords: {e}")

        return bill

    def delete_bill(self, bill_id: int) -> bool:
        bill = self.get_bill(bill_id)
        if bill:
            bill.is_active = False
            self.db.commit()
            return True
        return False

    def create_bill_version(self, bill: Bill, version_number: str = None) -> BillVersion:
        """Create a version snapshot of a bill"""
        if not version_number:
            # Auto-generate version number
            latest_version = self.db.query(BillVersion).filter(
                BillVersion.bill_id == bill.id
            ).order_by(BillVersion.created_at.desc()).first()

            if latest_version and latest_version.version_number:
                try:
                    # Extract numeric part and increment
                    parts = latest_version.version_number.split('.')
                    major = int(parts[0])
                    minor = int(parts[1]) if len(parts) > 1 else 0
                    version_number = f"{major}.{minor + 1}"
                except (ValueError, IndexError):
                    version_number = "2.0"
            else:
                version_number = "1.0"

        # Mark previous versions as not current
        self.db.query(BillVersion).filter(
            BillVersion.bill_id == bill.id,
            BillVersion.is_current == True
        ).update({BillVersion.is_current: False})

        # Create new version
        bill_version = BillVersion(
            bill_id=bill.id,
            version_number=version_number,
            title=bill.title,
            summary=bill.summary,
            full_text=bill.full_text,
            introduced_date=bill.introduced_date,
            last_action_date=bill.last_action_date,
            status=bill.status,
            sponsor=bill.sponsor,
            committee=bill.committee,
            is_current=True
        )

        self.db.add(bill_version)
        self.db.commit()
        self.db.refresh(bill_version)

        return bill_version

    def _should_create_version(self, bill_update: dict) -> bool:
        """Determine if changes warrant creating a new version"""
        significant_fields = ['title', 'summary', 'full_text', 'status']
        return any(field in bill_update for field in significant_fields)

    def get_bill_versions(self, bill_id: int) -> List[BillVersion]:
        """Get all versions of a bill"""
        return self.db.query(BillVersion).filter(
            BillVersion.bill_id == bill_id
        ).order_by(BillVersion.created_at.desc()).all()

    def get_current_bill_version(self, bill_id: int) -> Optional[BillVersion]:
        """Get the current version of a bill"""
        return self.db.query(BillVersion).filter(
            BillVersion.bill_id == bill_id,
            BillVersion.is_current == True
        ).first()

    def search_bills(self, query: str = None, state_or_federal: str = None,
                    status: str = None, keywords: List[str] = None,
                    skip: int = 0, limit: int = 100) -> List[Bill]:
        """Search bills with various filters"""
        db_query = self.db.query(Bill).filter(Bill.is_active == True)

        if query:
            # Search in title and summary
            search_filter = Bill.title.ilike(f"%{query}%") | \
                           Bill.summary.ilike(f"%{query}%")
            db_query = db_query.filter(search_filter)

        if state_or_federal:
            db_query = db_query.filter(Bill.state_or_federal == state_or_federal)

        if status:
            db_query = db_query.filter(Bill.status == status)

        if keywords:
            # Search bills that match any of the given keywords
            from models.legislation import BillKeywordMatch, Keyword
            keyword_ids = self.db.query(Keyword.id).filter(
                Keyword.term.in_(keywords)
            ).subquery()

            bill_ids_with_keywords = self.db.query(BillKeywordMatch.bill_id).filter(
                BillKeywordMatch.keyword_id.in_(keyword_ids)
            ).subquery()

            db_query = db_query.filter(Bill.id.in_(bill_ids_with_keywords))

        return db_query.order_by(Bill.last_action_date.desc()).offset(skip).limit(limit).all()

    def get_bills_by_keyword(self, keyword_term: str, min_confidence: float = 0.5) -> List[Bill]:
        """Get bills that match a specific keyword"""
        from models.legislation import BillKeywordMatch, Keyword

        # Find the keyword
        keyword = self.db.query(Keyword).filter(Keyword.term == keyword_term).first()
        if not keyword:
            return []

        # Get bills with high confidence matches
        matches = self.db.query(BillKeywordMatch).filter(
            BillKeywordMatch.keyword_id == keyword.id,
            BillKeywordMatch.confidence_score >= min_confidence
        ).order_by(BillKeywordMatch.confidence_score.desc()).all()

        bill_ids = [match.bill_id for match in matches]
        return self.db.query(Bill).filter(Bill.id.in_(bill_ids)).all()

    def get_recent_bills(self, days: int = 30, limit: int = 50) -> List[Bill]:
        """Get recently introduced or updated bills"""
        from datetime import datetime, timedelta

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        return self.db.query(Bill).filter(
            Bill.is_active == True,
            Bill.last_action_date >= cutoff_date
        ).order_by(Bill.last_action_date.desc()).limit(limit).all()

    def get_bill_statistics(self) -> dict:
        """Get statistics about bills in the system"""
        total_bills = self.db.query(Bill).filter(Bill.is_active == True).count()

        # Count by status
        from sqlalchemy import func
        status_counts = self.db.query(
            Bill.status,
            func.count(Bill.id)
        ).filter(Bill.is_active == True).group_by(Bill.status).all()

        # Count by state/federal
        jurisdiction_counts = self.db.query(
            Bill.state_or_federal,
            func.count(Bill.id)
        ).filter(Bill.is_active == True).group_by(Bill.state_or_federal).all()

        return {
            'total_bills': total_bills,
            'status_distribution': dict(status_counts),
            'jurisdiction_distribution': dict(jurisdiction_counts)
        }