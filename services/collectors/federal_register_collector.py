#!/usr/bin/env python3
"""
Federal Register Document Collector
Monitors CMS proposed and final rules related to skilled nursing facilities
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from services.collectors.federal_register_client import FederalRegisterClient
from services.collectors.healthcare_validator import HealthcareValidator, get_healthcare_search_terms
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from models.legislation import Bill, Keyword, BillKeywordMatch

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FederalRegisterCollector:
    """Federal Register document collector for CMS SNF-related rules"""

    def __init__(self, database_url: str = None):
        self.client = FederalRegisterClient()
        self.healthcare_validator = HealthcareValidator(min_keyword_count=2, enable_strict_mode=True)

        # Use provided database URL or default
        db_url = database_url or os.getenv('DATABASE_URL', 'sqlite:///./snflegtracker.db')
        self.engine = create_engine(db_url)

        logger.info("Federal Register Collector initialized")

    def get_snf_keywords(self) -> List[str]:
        """Get healthcare and SNF-related keywords from database"""
        try:
            # Start with healthcare search terms
            healthcare_terms = get_healthcare_search_terms()

            # Get additional keywords from database
            with Session(self.engine) as session:
                keywords = session.query(Keyword).all()
                db_terms = [kw.term for kw in keywords]

            # Combine and deduplicate
            all_terms = healthcare_terms + db_terms
            unique_terms = list(set(all_terms))
            return unique_terms

        except Exception as e:
            logger.error(f"Failed to get keywords from database: {e}")
            # Fallback to healthcare validator terms
            return get_healthcare_search_terms()

    def store_document_as_bill(self, doc: Dict, session: Session) -> Optional[Bill]:
        """Store a Federal Register document as a bill in the database"""
        try:
            # Create unique bill number for Federal Register docs
            bill_number = f"FR-{doc.get('document_number', 'unknown')}"

            # Check if already exists
            existing = session.query(Bill).filter(Bill.bill_number == bill_number).first()
            if existing:
                logger.debug(f"Document {bill_number} already exists")
                return existing

            # Validate healthcare content before storing
            title = doc.get('title', '')
            summary = doc.get('abstract', '')
            validation_result = self.healthcare_validator.validate_healthcare_content(
                title=title,
                summary=summary,
                bill_number=bill_number
            )

            if not validation_result['is_healthcare']:
                logger.info(f"REJECTED FR document {bill_number}: {validation_result['rejection_reason']}")
                return None

            # Create new bill record
            bill = Bill(
                bill_number=bill_number,
                title=title,
                summary=summary,
                status=self._get_document_status(doc),
                source='federal_register',
                state_or_federal='federal',
                chamber='executive',  # Federal Register is executive branch
                sponsor=self._get_document_agency(doc),
                introduced_date=self._parse_date(doc.get('publication_date')),
                last_action_date=self._parse_date(doc.get('effective_date')),
                relevance_score=min(validation_result['confidence_score'] * 100, 100.0),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            # Store additional Federal Register data in full_text field
            metadata = {
                'document_type': doc.get('type'),
                'document_number': doc.get('document_number'),
                'agencies': [agency.get('name') for agency in doc.get('agencies', [])],
                'topics': doc.get('topics', []),
                'html_url': doc.get('html_url', ''),
                'pdf_url': doc.get('pdf_url', ''),
                'comment_info': doc.get('comment_info', {}),
                'snf_relevance': doc.get('snf_relevance', {})
            }

            # Store URLs and metadata in full_text field as JSON
            import json
            bill.full_text = json.dumps(metadata, indent=2)

            session.add(bill)
            session.flush()  # Get ID without committing

            # Match keywords if SNF relevant
            self._process_keyword_matches(bill, doc, session)

            logger.info(f"Stored Federal Register document: {bill_number}")
            return bill

        except Exception as e:
            logger.error(f"Failed to store document as bill: {e}")
            return None

    def _get_document_status(self, doc: Dict) -> str:
        """Determine document status based on type"""
        doc_type = doc.get('type', '').upper()
        if 'RULE' in doc_type:
            return 'Final Rule' if doc_type == 'RULE' else 'Proposed Rule'
        elif 'NOTICE' in doc_type:
            return 'Notice'
        return 'Published'

    def _get_document_agency(self, doc: Dict) -> str:
        """Get primary agency name"""
        agencies = doc.get('agencies', [])
        if agencies:
            return agencies[0].get('name', 'Unknown Agency')
        return 'Centers for Medicare & Medicaid Services'

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime object"""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00')).replace(tzinfo=None)
        except:
            try:
                return datetime.strptime(date_str, '%Y-%m-%d')
            except:
                return None

    def _process_keyword_matches(self, bill: Bill, doc: Dict, session: Session):
        """Process and store keyword matches for a bill"""
        try:
            snf_relevance = doc.get('snf_relevance', {})
            if not snf_relevance.get('is_relevant'):
                return

            # Get keywords from database
            keywords = session.query(Keyword).all()
            keyword_dict = {kw.term.lower(): kw for kw in keywords}

            # Match found terms with database keywords
            matched_terms = snf_relevance.get('matched_terms', [])
            confidence = snf_relevance.get('confidence_score', 0.0)

            for term in matched_terms:
                # Try exact match first
                if term.lower() in keyword_dict:
                    keyword = keyword_dict[term.lower()]
                    self._create_keyword_match(bill, keyword, confidence, session)
                else:
                    # Try partial matches
                    for kw_term, keyword in keyword_dict.items():
                        if term.lower() in kw_term or kw_term in term.lower():
                            self._create_keyword_match(bill, keyword, confidence * 0.8, session)
                            break

        except Exception as e:
            logger.error(f"Failed to process keyword matches: {e}")

    def _create_keyword_match(self, bill: Bill, keyword: Keyword, confidence: float, session: Session):
        """Create a keyword match record"""
        try:
            # Check if match already exists
            existing = session.query(BillKeywordMatch).filter(
                BillKeywordMatch.bill_id == bill.id,
                BillKeywordMatch.keyword_id == keyword.id
            ).first()

            if not existing:
                match = BillKeywordMatch(
                    bill_id=bill.id,
                    keyword_id=keyword.id,
                    confidence_score=confidence,
                    created_at=datetime.utcnow()
                )
                session.add(match)
                logger.debug(f"Added keyword match: {keyword.term} -> {bill.bill_number}")

        except Exception as e:
            logger.error(f"Failed to create keyword match: {e}")

    def collect_snf_payment_documents(self,
                                    year: int = None,
                                    limit: int = 20) -> List[Dict]:
        """Collect SNF payment system documents specifically"""
        logger.info(f"Starting targeted SNF payment document collection for {year or 'current'} year")

        try:
            # Use the specialized SNF payment rules search
            documents = self.client.search_snf_payment_rules(year=year, limit=limit)

            if not documents:
                logger.warning("No SNF payment documents found")
                return []

            logger.info(f"Found {len(documents)} SNF payment documents")

            # Store documents in database
            stored_bills = []
            with Session(self.engine) as session:
                for doc in documents:
                    bill = self.store_document_as_bill(doc, session)
                    if bill:
                        stored_bills.append(bill)

                session.commit()
                logger.info(f"Successfully stored {len(stored_bills)} SNF payment documents as bills")

            return documents

        except Exception as e:
            logger.error(f"SNF payment document collection failed: {e}")
            return []

    def collect_cms_documents(self,
                            year: int = None,
                            limit: int = 50,
                            snf_only: bool = True) -> List[Dict]:
        """Collect CMS documents and store as bills"""
        logger.info(f"Starting Federal Register collection for {year or 'recent'} CMS documents")

        try:
            # Get SNF-related search terms
            search_terms = self.get_snf_keywords() if snf_only else None

            # Search for CMS documents
            documents = self.client.search_cms_documents(
                search_terms=search_terms,
                document_types=['RULE', 'PRORULE', 'NOTICE'],
                year=year,
                limit=limit
            )

            if not documents:
                logger.warning("No documents found")
                return []

            # Filter for SNF relevant documents if requested
            if snf_only:
                relevant_docs = [doc for doc in documents if doc.get('snf_relevance', {}).get('is_relevant', False)]
                logger.info(f"Found {len(relevant_docs)} SNF-relevant out of {len(documents)} total documents")
                documents = relevant_docs

            # Store documents in database
            stored_bills = []
            with Session(self.engine) as session:
                for doc in documents:
                    bill = self.store_document_as_bill(doc, session)
                    if bill:
                        stored_bills.append(bill)

                session.commit()
                logger.info(f"Successfully stored {len(stored_bills)} Federal Register documents as bills")

            return documents

        except Exception as e:
            logger.error(f"Collection failed: {e}")
            return []

    def get_collection_stats(self) -> Dict:
        """Get statistics about collected Federal Register documents"""
        try:
            with Session(self.engine) as session:
                # Total Federal Register bills
                fr_bills = session.query(Bill).filter(Bill.source == 'federal_register').count()

                # Recent FR bills (last 30 days)
                thirty_days_ago = datetime.utcnow() - timedelta(days=30)
                recent_fr_bills = session.query(Bill).filter(
                    Bill.source == 'federal_register',
                    Bill.created_at >= thirty_days_ago
                ).count()

                # FR bills with keyword matches
                fr_bills_with_matches = session.query(Bill).filter(
                    Bill.source == 'federal_register'
                ).join(BillKeywordMatch).distinct().count()

                return {
                    'total_federal_register_documents': fr_bills,
                    'recent_documents_30_days': recent_fr_bills,
                    'documents_with_keyword_matches': fr_bills_with_matches,
                    'last_updated': datetime.utcnow().isoformat()
                }

        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {}

    def test_connection(self) -> bool:
        """Test Federal Register API connection"""
        return self.client.test_connection()

def main():
    """CLI interface for Federal Register collector"""
    parser = argparse.ArgumentParser(description='Federal Register CMS Document Collector')
    parser.add_argument('--year', type=int, help='Year to search (e.g., 2025)')
    parser.add_argument('--limit', type=int, default=50, help='Maximum documents to collect')
    parser.add_argument('--all-cms', action='store_true', help='Collect all CMS documents, not just SNF-relevant')
    parser.add_argument('--payment-rules', action='store_true', help='Collect SNF payment rules only (most targeted)')
    parser.add_argument('--test', action='store_true', help='Test API connection')
    parser.add_argument('--stats', action='store_true', help='Show collection statistics')

    args = parser.parse_args()

    collector = FederalRegisterCollector()

    if args.test:
        print("🧪 Testing Federal Register API connection...")
        if collector.test_connection():
            print("✅ Federal Register API connection successful")
        else:
            print("❌ Federal Register API connection failed")
        return

    if args.stats:
        print("📊 Federal Register Collection Statistics")
        stats = collector.get_collection_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
        return

    # Main collection
    if args.payment_rules:
        print("🎯 Collecting SNF payment rules specifically...")
        documents = collector.collect_snf_payment_documents(
            year=args.year,
            limit=args.limit
        )
    else:
        snf_only = not args.all_cms
        documents = collector.collect_cms_documents(
            year=args.year,
            limit=args.limit,
            snf_only=snf_only
        )

    print(f"✅ Collected {len(documents)} Federal Register documents")

    # Show sample results
    for i, doc in enumerate(documents[:3], 1):
        print(f"\n{i}. {doc.get('title', 'No title')[:80]}...")
        print(f"   Type: {doc.get('type')} | Date: {doc.get('publication_date')}")
        if doc.get('snf_relevance', {}).get('is_relevant'):
            confidence = doc['snf_relevance'].get('confidence_score', 0)
            print(f"   SNF Relevance: {confidence:.1%}")

if __name__ == "__main__":
    main()