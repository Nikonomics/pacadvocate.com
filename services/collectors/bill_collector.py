"""
Bill Collector Service
Collects bills from Congress.gov API using seeded keywords and stores them in the database
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# Import our models and services
from models.database import SessionLocal
from models.legislation import Bill, Keyword, BillCreate
from services.legislation.bill_service import BillService
from services.analysis.keyword_matcher import KeywordMatcher
from services.alerts.alert_service import AlertService
from services.collectors.congress_api_client import CongressAPIClient
from services.collectors.healthcare_validator import HealthcareValidator, get_healthcare_search_terms

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BillCollector:
    """Collects bills from Congress.gov API and stores them in the database"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_client = CongressAPIClient(api_key)
        self.db_session = SessionLocal()
        self.bill_service = BillService(self.db_session)
        self.keyword_matcher = KeywordMatcher(self.db_session)
        self.alert_service = AlertService(self.db_session)
        self.healthcare_validator = HealthcareValidator(min_keyword_count=2, enable_strict_mode=True)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db_session.close()

    def get_search_keywords(self, categories: Optional[List[str]] = None,
                           min_importance: float = 1.5) -> List[str]:
        """
        Get healthcare-focused keywords from database to use for searching

        Args:
            categories: Filter by specific categories (e.g., ['SNF_Core', 'Medicare'])
            min_importance: Minimum importance weight
        """
        try:
            # Start with healthcare search terms as base
            healthcare_terms = get_healthcare_search_terms()

            # Get additional keywords from database
            query = self.db_session.query(Keyword).filter(
                Keyword.is_active == True,
                Keyword.importance_weight >= min_importance
            )

            if categories:
                query = query.filter(Keyword.category.in_(categories))

            keywords = query.order_by(Keyword.importance_weight.desc()).all()

            # Extract primary terms
            db_terms = [kw.term for kw in keywords]

            # Add important synonyms
            for keyword in keywords:
                if keyword.synonyms and keyword.importance_weight >= 1.8:
                    try:
                        synonyms = json.loads(keyword.synonyms)
                        # Add up to 2 most relevant synonyms for high-priority keywords
                        db_terms.extend(synonyms[:2])
                    except (json.JSONDecodeError, TypeError):
                        continue

            # Combine healthcare terms with database terms
            all_terms = healthcare_terms + db_terms

            # Remove duplicates while preserving order
            unique_terms = []
            seen = set()
            for term in all_terms:
                if term.lower() not in seen:
                    unique_terms.append(term)
                    seen.add(term.lower())

            logger.info(f"Using {len(unique_terms)} healthcare-focused search terms")
            return unique_terms

        except Exception as e:
            logger.error(f"Failed to get search keywords: {e}")
            # Enhanced fallback with healthcare focus
            return get_healthcare_search_terms()  # Use healthcare validator fallback

    def collect_bills_by_keywords(self, congress: int = 119, year: Optional[int] = None,
                                 limit_per_keyword: int = 50) -> Dict[str, Any]:
        """
        Collect bills using seeded keywords

        Args:
            congress: Congress number (119 for current)
            year: Filter by year (2024, 2025, etc.)
            limit_per_keyword: Max results per keyword search
        """
        results = {
            'total_api_calls': 0,
            'bills_found': 0,
            'bills_stored': 0,
            'bills_updated': 0,
            'bills_rejected': 0,
            'errors': [],
            'keywords_used': [],
            'rejection_summary': {}
        }

        try:
            # Get search keywords from database
            search_keywords = self.get_search_keywords()
            results['keywords_used'] = search_keywords

            if not search_keywords:
                logger.error("No search keywords found in database")
                return results

            logger.info(f"Starting bill collection with {len(search_keywords)} keywords")

            # Search for bills using keywords
            all_bills = self.api_client.search_by_keywords(
                keywords=search_keywords,
                congress=congress,
                limit=limit_per_keyword,
                year=year
            )

            results['total_api_calls'] = len(search_keywords)
            results['bills_found'] = len(all_bills)

            logger.info(f"Found {len(all_bills)} unique bills from API")

            # Process and store each bill
            for bill_data in all_bills:
                try:
                    stored = self._process_and_store_bill(bill_data, congress)
                    if stored == 'new':
                        results['bills_stored'] += 1
                    elif stored == 'updated':
                        results['bills_updated'] += 1
                    elif stored == 'rejected':
                        results['bills_rejected'] += 1

                except Exception as e:
                    error_msg = f"Failed to process bill {bill_data.get('number', 'unknown')}: {e}"
                    logger.error(error_msg)
                    results['errors'].append(error_msg)

            # Add rejection summary
            results['rejection_summary'] = self.healthcare_validator.get_rejection_summary()

            logger.info(f"Collection complete: {results['bills_stored']} new, {results['bills_updated']} updated, {results['bills_rejected']} rejected")
            return results

        except Exception as e:
            error_msg = f"Bill collection failed: {e}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
            return results

    def _process_and_store_bill(self, bill_data: Dict, congress: int) -> str:
        """
        Process a bill from API data and store it in database

        Returns:
            'new' if new bill was created
            'updated' if existing bill was updated
            'skipped' if no changes needed
        """
        try:
            # Extract bill information from API response
            bill_number = f"{bill_data.get('type', '').upper()}-{congress}-{bill_data.get('number', '')}"
            title = bill_data.get('title', '')

            # Validate healthcare content before processing
            summary = bill_data.get('summary', '')
            validation_result = self.healthcare_validator.validate_healthcare_content(
                title=title,
                summary=summary,
                bill_number=bill_number
            )

            if not validation_result['is_healthcare']:
                logger.info(f"REJECTED {bill_number}: {validation_result['rejection_reason']}")
                return 'rejected'

            # Get additional details if available
            introduction_date = None
            last_action_date = None
            status = "introduced"  # default
            sponsor = None

            # Parse dates if available
            if 'introducedDate' in bill_data:
                try:
                    introduction_date = datetime.fromisoformat(
                        bill_data['introducedDate'].replace('Z', '+00:00')
                    )
                except (ValueError, TypeError):
                    pass

            if 'latestAction' in bill_data:
                latest_action = bill_data['latestAction']
                if 'actionDate' in latest_action:
                    try:
                        last_action_date = datetime.fromisoformat(
                            latest_action['actionDate'].replace('Z', '+00:00')
                        )
                    except (ValueError, TypeError):
                        pass

                # Use latest action text as status
                if 'text' in latest_action:
                    status = latest_action['text'][:100]  # Truncate if too long

            # Get sponsor information
            if 'sponsors' in bill_data and bill_data['sponsors']:
                sponsor_info = bill_data['sponsors'][0]  # Primary sponsor
                sponsor = sponsor_info.get('firstName', '') + ' ' + sponsor_info.get('lastName', '')
                sponsor = sponsor.strip()

            # Check if bill already exists
            existing_bill = self.bill_service.get_bill_by_number(bill_number)

            if existing_bill:
                # Update existing bill if there are changes
                updates = {}

                if existing_bill.title != title:
                    updates['title'] = title
                if last_action_date and existing_bill.last_action_date != last_action_date:
                    updates['last_action_date'] = last_action_date
                if existing_bill.status != status:
                    updates['status'] = status
                if sponsor and existing_bill.sponsor != sponsor:
                    updates['sponsor'] = sponsor

                if updates:
                    self.bill_service.update_bill(existing_bill.id, updates)
                    logger.info(f"Updated bill: {bill_number}")
                    return 'updated'
                else:
                    return 'skipped'

            else:
                # Create new bill with healthcare validation score
                bill_create = BillCreate(
                    bill_number=bill_number,
                    title=title,
                    source="congress.gov",
                    state_or_federal="federal",
                    introduced_date=introduction_date,
                    last_action_date=last_action_date,
                    status=status,
                    sponsor=sponsor,
                    chamber=self._get_chamber_from_type(bill_data.get('type', '')),
                    # Use healthcare validation confidence as relevance score baseline
                    relevance_score=min(validation_result['confidence_score'] * 100, 100.0)
                )

                new_bill = self.bill_service.create_bill(bill_create)
                logger.info(f"Created new bill: {bill_number}")

                # Process keywords for the new bill (this is done automatically in bill_service)
                return 'new'

        except Exception as e:
            logger.error(f"Error processing bill data: {e}")
            raise

    def _get_chamber_from_type(self, bill_type: str) -> Optional[str]:
        """Determine chamber from bill type"""
        if not bill_type:
            return None

        bill_type_lower = bill_type.lower()
        if bill_type_lower.startswith('h'):
            return "House"
        elif bill_type_lower.startswith('s'):
            return "Senate"
        else:
            return None

    def collect_recent_bills(self, days: int = 30, congress: int = 119) -> Dict[str, Any]:
        """
        Collect bills from the last N days

        Args:
            days: Number of days back to search
            congress: Congress number
        """
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        logger.info(f"Collecting bills from {start_date.date()} to {end_date.date()}")

        return self.collect_bills_by_keywords(
            congress=congress,
            year=None  # Don't filter by year, use the recent date range
        )

    def collect_snf_bills(self, congress: int = 119, year: Optional[int] = None) -> Dict[str, Any]:
        """
        Specifically collect SNF-related bills using high-priority SNF keywords

        Args:
            congress: Congress number
            year: Filter by year
        """
        logger.info("Starting SNF-specific bill collection")

        # Get high-priority SNF keywords
        snf_keywords = self.get_search_keywords(
            categories=['SNF_Core', 'Medicare', 'Quality', 'Staffing'],
            min_importance=1.7
        )

        # Use the API client to search specifically for these terms
        all_bills = self.api_client.search_by_keywords(
            keywords=snf_keywords,
            congress=congress,
            limit=100,  # More comprehensive search for SNF bills
            year=year
        )

        results = {
            'total_api_calls': len(snf_keywords),
            'bills_found': len(all_bills),
            'bills_stored': 0,
            'bills_updated': 0,
            'errors': [],
            'keywords_used': snf_keywords
        }

        # Process and store bills
        for bill_data in all_bills:
            try:
                stored = self._process_and_store_bill(bill_data, congress)
                if stored == 'new':
                    results['bills_stored'] += 1
                elif stored == 'updated':
                    results['bills_updated'] += 1

            except Exception as e:
                error_msg = f"Failed to process SNF bill {bill_data.get('number', 'unknown')}: {e}"
                logger.error(error_msg)
                results['errors'].append(error_msg)

        logger.info(f"SNF bill collection complete: {results}")
        return results

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about collected bills"""
        try:
            total_bills = self.db_session.query(Bill).filter(Bill.is_active == True).count()
            federal_bills = self.db_session.query(Bill).filter(
                Bill.is_active == True,
                Bill.state_or_federal == 'federal'
            ).count()

            # Bills with keyword matches
            from models.legislation import BillKeywordMatch
            bills_with_keywords = self.db_session.query(Bill.id).join(BillKeywordMatch).distinct().count()

            # Recent bills (last 30 days)
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            recent_bills = self.db_session.query(Bill).filter(
                Bill.created_at >= cutoff_date
            ).count()

            return {
                'total_bills': total_bills,
                'federal_bills': federal_bills,
                'bills_with_keyword_matches': bills_with_keywords,
                'recent_bills_30_days': recent_bills,
                'collection_rate': f"{bills_with_keywords}/{total_bills}" if total_bills > 0 else "0/0"
            }

        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {'error': str(e)}

# Command-line interface
def main():
    """Main CLI function for bill collection"""
    import argparse

    parser = argparse.ArgumentParser(description='SNFLegTracker Bill Collector')
    parser.add_argument('--congress', type=int, default=119, help='Congress number (default: 119)')
    parser.add_argument('--year', type=int, help='Filter by year (e.g., 2024, 2025)')
    parser.add_argument('--days', type=int, help='Collect bills from last N days')
    parser.add_argument('--snf-only', action='store_true', help='Collect only SNF-related bills')
    parser.add_argument('--test', action='store_true', help='Test API connection')
    parser.add_argument('--stats', action='store_true', help='Show collection statistics')
    parser.add_argument('--api-key', help='Congress.gov API key')

    args = parser.parse_args()

    # Set API key if provided
    if args.api_key:
        os.environ['CONGRESS_API_KEY'] = args.api_key

    with BillCollector() as collector:
        if args.test:
            print("🧪 Testing API connection...")
            if collector.api_client.test_connection():
                print("✅ API connection successful")
            else:
                print("❌ API connection failed")
                return 1

        elif args.stats:
            print("📊 Collection Statistics:")
            stats = collector.get_collection_stats()
            for key, value in stats.items():
                print(f"  {key}: {value}")

        elif args.snf_only:
            print(f"🏥 Collecting SNF bills from Congress {args.congress}")
            results = collector.collect_snf_bills(congress=args.congress, year=args.year)
            print(f"Results: {json.dumps(results, indent=2)}")

        elif args.days:
            print(f"📅 Collecting bills from last {args.days} days")
            results = collector.collect_recent_bills(days=args.days, congress=args.congress)
            print(f"Results: {json.dumps(results, indent=2)}")

        else:
            print(f"🔍 Collecting bills using keywords from Congress {args.congress}")
            results = collector.collect_bills_by_keywords(congress=args.congress, year=args.year)
            print(f"Results: {json.dumps(results, indent=2)}")

if __name__ == "__main__":
    main()