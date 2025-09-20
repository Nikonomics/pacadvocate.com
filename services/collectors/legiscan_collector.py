#!/usr/bin/env python3
"""
LegiScan State Legislation Collector
Monitors state legislation for skilled nursing and healthcare-related bills
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import argparse
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from services.collectors.legiscan_client import LegiScanClient
from services.collectors.healthcare_validator import HealthcareValidator, get_healthcare_search_terms
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from models.legislation import Bill, Keyword, BillKeywordMatch

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LegiScanCollector:
    """LegiScan state legislation collector for healthcare-related bills"""

    # State configuration for multi-state support
    STATE_CONFIG = {
        'ID': {
            'name': 'Idaho',
            'priority_keywords': [
                'nursing facility', 'skilled nursing', 'assisted living',
                'Medicaid', 'staffing', 'long-term care'
            ],
            'enabled': True
        },
        'CA': {
            'name': 'California',
            'priority_keywords': [
                'nursing facility', 'skilled nursing', 'assisted living',
                'Medicaid', 'Medi-Cal', 'staffing', 'long-term care'
            ],
            'enabled': False  # Disabled by default, enable as needed
        },
        'WA': {
            'name': 'Washington',
            'priority_keywords': [
                'nursing facility', 'skilled nursing', 'assisted living',
                'Medicaid', 'Apple Health', 'staffing', 'long-term care'
            ],
            'enabled': False
        }
        # Add more states as needed
    }

    def __init__(self, api_key: str = None, database_url: str = None):
        self.client = LegiScanClient(api_key)
        self.healthcare_validator = HealthcareValidator(min_keyword_count=2, enable_strict_mode=True)

        # Use provided database URL or default
        db_url = database_url or os.getenv('DATABASE_URL', 'sqlite:///./snflegtracker.db')
        self.engine = create_engine(db_url)

        logger.info("LegiScan Collector initialized")

    def get_healthcare_keywords(self) -> List[str]:
        """Get healthcare-related keywords from database"""
        try:
            # Start with healthcare search terms from validator
            healthcare_terms = get_healthcare_search_terms()

            with Session(self.engine) as session:
                keywords = session.query(Keyword).all()
                db_terms = [kw.term for kw in keywords]

                # Add state-specific healthcare terms
                state_terms = [
                    'nursing facility', 'skilled nursing', 'assisted living',
                    'Medicaid', 'Medicare', 'staffing', 'long-term care',
                    'nursing home', 'healthcare', 'health care', 'patient safety',
                    'quality assurance', 'certification', 'licensing'
                ]

                # Combine all terms and deduplicate
                all_terms = healthcare_terms + db_terms + state_terms
                return list(set(all_terms))

        except Exception as e:
            logger.error(f"Failed to get keywords from database: {e}")
            # Fallback to healthcare validator terms
            return get_healthcare_search_terms()

    def map_legiscan_to_bill(self, legiscan_bill: Dict, state: str, detailed_info: Dict = None) -> Dict:
        """Map LegiScan bill data to our Bills table structure"""
        try:
            # Extract basic information
            bill_number = legiscan_bill.get('bill_number', '')
            if not bill_number:
                bill_number = f"{state}-{legiscan_bill.get('bill_id', 'unknown')}"

            # Validate healthcare content before processing
            title = legiscan_bill.get('title', '')
            summary = legiscan_bill.get('description', '')
            full_text = self._extract_full_text(detailed_info) if detailed_info else None

            validation_result = self.healthcare_validator.validate_healthcare_content(
                title=title,
                summary=summary,
                full_text=full_text or '',
                bill_number=bill_number
            )

            if not validation_result['is_healthcare']:
                logger.info(f"REJECTED LegiScan bill {bill_number}: {validation_result['rejection_reason']}")
                return None

            # Map status
            status = legiscan_bill.get('status_desc', 'Unknown')

            # Extract dates
            introduced_date = self._parse_legiscan_date(legiscan_bill.get('introduced'))
            last_action_date = self._parse_legiscan_date(legiscan_bill.get('last_action_date'))

            # Get sponsor information
            sponsor_name = self._extract_sponsor_name(legiscan_bill, detailed_info)

            # Get committee information
            committee = self._extract_committee_info(legiscan_bill, detailed_info)

            # Determine chamber
            chamber = self._determine_chamber(bill_number)

            # Create bill data structure with healthcare validation score
            bill_data = {
                'bill_number': bill_number,
                'title': title,
                'summary': summary,
                'full_text': full_text,
                'source': 'legiscan',
                'state_or_federal': state.upper(),
                'introduced_date': introduced_date,
                'last_action_date': last_action_date,
                'status': status,
                'sponsor': sponsor_name,
                'committee': committee,
                'chamber': chamber,
                'relevance_score': min(validation_result['confidence_score'] * 100, 100.0),
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'is_active': True,
                'metadata': {
                    'legiscan_bill_id': legiscan_bill.get('bill_id'),
                    'session_id': legiscan_bill.get('session_id'),
                    'url': legiscan_bill.get('url', ''),
                    'state_link': legiscan_bill.get('state_link', ''),
                    'completed': legiscan_bill.get('completed'),
                    'progress': legiscan_bill.get('progress', []),
                    'search_term': legiscan_bill.get('search_term'),
                    'legiscan_data': legiscan_bill
                }
            }

            return bill_data

        except Exception as e:
            logger.error(f"Failed to map LegiScan bill data: {e}")
            return {}

    def _parse_legiscan_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse LegiScan date string to datetime object"""
        if not date_str:
            return None

        try:
            # LegiScan typically uses YYYY-MM-DD format
            if isinstance(date_str, str):
                if len(date_str) == 10:  # YYYY-MM-DD
                    return datetime.strptime(date_str, '%Y-%m-%d')
                elif len(date_str) == 8:   # YYYYMMDD
                    return datetime.strptime(date_str, '%Y%m%d')
            return None
        except:
            logger.debug(f"Could not parse date: {date_str}")
            return None

    def _extract_sponsor_name(self, bill: Dict, detailed_info: Dict = None) -> str:
        """Extract primary sponsor name"""
        try:
            # Try detailed sponsor info first
            if detailed_info and 'sponsors' in detailed_info:
                sponsors = detailed_info['sponsors']
                if sponsors and isinstance(sponsors, list):
                    for sponsor_data in sponsors:
                        if 'sponsor' in sponsor_data:
                            sponsor_info = sponsor_data['sponsor']
                            name = sponsor_info.get('name', '')
                            if name:
                                return name

            # Fall back to basic sponsor info
            sponsors = bill.get('sponsors', [])
            if sponsors and isinstance(sponsors, list):
                primary_sponsor = sponsors[0]
                return primary_sponsor.get('name', 'Unknown')

            return 'Unknown'

        except Exception as e:
            logger.debug(f"Error extracting sponsor: {e}")
            return 'Unknown'

    def _extract_committee_info(self, bill: Dict, detailed_info: Dict = None) -> str:
        """Extract committee assignment information"""
        try:
            # Look for committee info in progress/history
            progress = bill.get('progress', [])
            if progress:
                for action in progress:
                    event = action.get('event', '').lower()
                    if 'committee' in event or 'referred' in event:
                        return action.get('event', '')[:200]  # Limit length

            # Look in detailed supplements for committee info
            if detailed_info and 'supplements' in detailed_info:
                for supp in detailed_info['supplements']:
                    if 'supplement' in supp:
                        supp_data = supp['supplement']
                        if 'committee' in supp_data.get('type', '').lower():
                            return supp_data.get('title', '')[:200]

            return None

        except Exception as e:
            logger.debug(f"Error extracting committee: {e}")
            return None

    def _determine_chamber(self, bill_number: str) -> str:
        """Determine chamber based on bill number"""
        if not bill_number:
            return 'Unknown'

        bill_upper = bill_number.upper()
        if bill_upper.startswith('H') or 'HOUSE' in bill_upper:
            return 'House'
        elif bill_upper.startswith('S') or 'SENATE' in bill_upper:
            return 'Senate'
        elif bill_upper.startswith('A'):  # Assembly (some states)
            return 'Assembly'
        else:
            return 'Unknown'

    def _extract_full_text(self, detailed_info: Dict) -> Optional[str]:
        """Extract full text from detailed bill information"""
        try:
            if not detailed_info or 'texts' not in detailed_info:
                return None

            texts = detailed_info['texts']
            if not texts:
                return None

            # Get the most recent text version
            latest_text = None
            for text_data in texts:
                if 'text' in text_data:
                    text_info = text_data['text']
                    # Look for the actual text content
                    if 'doc' in text_info:
                        latest_text = text_info['doc']
                        break

            return latest_text

        except Exception as e:
            logger.debug(f"Error extracting full text: {e}")
            return None

    def store_bill(self, bill_data: Dict, session: Session) -> Optional[Bill]:
        """Store a bill in the database"""
        try:
            # Check if bill already exists
            existing = session.query(Bill).filter(
                Bill.bill_number == bill_data['bill_number']
            ).first()

            if existing:
                logger.debug(f"Bill {bill_data['bill_number']} already exists")
                return existing

            # Create new bill record
            metadata_json = json.dumps(bill_data.pop('metadata', {}), indent=2)

            bill = Bill(
                bill_number=bill_data['bill_number'],
                title=bill_data['title'],
                summary=bill_data['summary'],
                full_text=bill_data.get('full_text') or metadata_json,  # Store metadata if no full text
                source=bill_data['source'],
                state_or_federal=bill_data['state_or_federal'],
                introduced_date=bill_data.get('introduced_date'),
                last_action_date=bill_data.get('last_action_date'),
                status=bill_data['status'],
                sponsor=bill_data.get('sponsor'),
                committee=bill_data.get('committee'),
                chamber=bill_data['chamber'],
                created_at=bill_data['created_at'],
                updated_at=bill_data['updated_at'],
                is_active=bill_data.get('is_active', True)
            )

            session.add(bill)
            session.flush()  # Get ID without committing

            # Process keyword matches
            self._process_keyword_matches(bill, bill_data, session)

            logger.info(f"Stored LegiScan bill: {bill.bill_number}")
            return bill

        except Exception as e:
            logger.error(f"Failed to store bill: {e}")
            return None

    def _process_keyword_matches(self, bill: Bill, bill_data: Dict, session: Session):
        """Process and store keyword matches for a bill"""
        try:
            # Get keywords from database
            keywords = session.query(Keyword).all()
            keyword_dict = {kw.term.lower(): kw for kw in keywords}

            # Search text for keyword matches
            searchable_text = ' '.join([
                bill_data.get('title', ''),
                bill_data.get('summary', ''),
                bill_data.get('full_text', '')[:1000]  # Limit text length
            ]).lower()

            # Find matches
            for kw_term, keyword in keyword_dict.items():
                if kw_term in searchable_text:
                    # Calculate simple confidence based on keyword importance and location
                    confidence = self._calculate_keyword_confidence(
                        kw_term, bill_data, keyword.importance_weight or 1.0
                    )

                    # Create keyword match
                    match = BillKeywordMatch(
                        bill_id=bill.id,
                        keyword_id=keyword.id,
                        confidence_score=confidence,
                        created_at=datetime.utcnow()
                    )
                    session.add(match)
                    logger.debug(f"Added keyword match: {keyword.term} -> {bill.bill_number}")

        except Exception as e:
            logger.error(f"Failed to process keyword matches: {e}")

    def _calculate_keyword_confidence(self, term: str, bill_data: Dict, importance_weight: float) -> float:
        """Calculate confidence score for keyword match"""
        confidence = 0.1  # Base confidence

        title = bill_data.get('title', '').lower()
        summary = bill_data.get('summary', '').lower()

        # Higher confidence for title matches
        if term in title:
            confidence += 0.3 * importance_weight

        # Medium confidence for summary matches
        if term in summary:
            confidence += 0.2 * importance_weight

        # Bonus for exact phrase matches
        if f' {term} ' in f' {title} ' or f' {term} ' in f' {summary} ':
            confidence += 0.1

        return min(confidence, 1.0)

    def collect_state_bills(self,
                          state: str,
                          year: int = None,
                          limit: int = 20,
                          include_details: bool = False) -> List[Dict]:
        """Collect healthcare bills from a specific state"""

        if state.upper() not in self.STATE_CONFIG:
            logger.error(f"Unsupported state: {state}")
            return []

        state_config = self.STATE_CONFIG[state.upper()]
        if not state_config.get('enabled', False):
            logger.warning(f"State {state_config['name']} is not enabled for collection")
            return []

        logger.info(f"Starting LegiScan collection for {state_config['name']} ({year or 'current year'})")

        try:
            # Get search terms for this state
            search_terms = state_config.get('priority_keywords', [])

            detailed_bills = []
            stored_count = 0
            processed_count = 0

            # Process search terms in smaller batches with immediate storage
            with Session(self.engine) as session:
                for term_index, term in enumerate(search_terms):
                    if processed_count >= limit:
                        break

                    logger.info(f"Searching {state_config['name']} for '{term}' ({term_index + 1}/{len(search_terms)})...")

                    # Search with pagination (10 bills at a time)
                    page_size = 10
                    remaining_limit = min(page_size, limit - processed_count)

                    bills = self.client.search_healthcare_bills(
                        state=state,
                        search_terms=[term],  # One term at a time
                        year=year,
                        limit=remaining_limit
                    )

                    if not bills:
                        logger.debug(f"No bills found for term: {term}")
                        continue

                    logger.info(f"Found {len(bills)} bills for '{term}' - processing...")

                    # Process each bill immediately
                    for bill_index, bill in enumerate(bills):
                        if processed_count >= limit:
                            break

                        try:
                            logger.info(f"Processing bill {processed_count + 1}/{limit}: {bill.get('bill_number', 'Unknown')} - {bill.get('title', 'No title')[:50]}...")

                            # Get detailed info if requested
                            detailed_info = None
                            if include_details:
                                bill_id = bill.get('bill_id')
                                if bill_id:
                                    logger.debug(f"Fetching detailed info for bill {bill_id}...")
                                    detailed_info = self.client.get_detailed_bill_info(bill_id)

                            # Map to our bill structure
                            bill_data = self.map_legiscan_to_bill(bill, state, detailed_info)
                            if bill_data:
                                # Store in database immediately
                                stored_bill = self.store_bill(bill_data, session)
                                if stored_bill:
                                    stored_count += 1
                                    logger.info(f"✅ Stored: {stored_bill.bill_number}")
                                else:
                                    logger.debug(f"Bill already exists or failed to store: {bill_data['bill_number']}")

                                detailed_bills.append(bill_data)

                            processed_count += 1

                        except Exception as e:
                            logger.error(f"Failed to process bill {bill.get('bill_id', 'unknown')}: {e}")
                            processed_count += 1
                            continue

                    # Commit after each batch
                    session.commit()
                    logger.info(f"Committed batch - {stored_count} bills stored so far")

                logger.info(f"Collection complete: {processed_count} bills processed, {stored_count} new bills stored")

            return detailed_bills

        except Exception as e:
            logger.error(f"Collection failed for {state}: {e}")
            return []

    def get_collection_stats(self, state: str = None) -> Dict:
        """Get statistics about collected LegiScan bills"""
        try:
            with Session(self.engine) as session:
                query = session.query(Bill).filter(Bill.source == 'legiscan')

                if state:
                    query = query.filter(Bill.state_or_federal == state.upper())

                # Total LegiScan bills
                total_bills = query.count()

                # Recent bills (last 30 days)
                thirty_days_ago = datetime.utcnow() - timedelta(days=30)
                recent_bills = query.filter(Bill.created_at >= thirty_days_ago).count()

                # Bills with keyword matches
                bills_with_matches = query.join(BillKeywordMatch).distinct().count()

                # State breakdown
                state_counts = {}
                if not state:  # Only show breakdown if not filtering by state
                    from sqlalchemy import func
                    state_stats = session.query(
                        Bill.state_or_federal,
                        func.count(Bill.id)
                    ).filter(Bill.source == 'legiscan').group_by(Bill.state_or_federal).all()

                    for state_name, count in state_stats:
                        state_counts[state_name] = count

                return {
                    'total_legiscan_bills': total_bills,
                    'recent_bills_30_days': recent_bills,
                    'bills_with_keyword_matches': bills_with_matches,
                    'state_breakdown': state_counts,
                    'enabled_states': [s for s, config in self.STATE_CONFIG.items() if config.get('enabled')],
                    'last_updated': datetime.utcnow().isoformat()
                }

        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {}

    def test_connection(self) -> bool:
        """Test LegiScan API connection"""
        return self.client.test_connection()

def main():
    """CLI interface for LegiScan collector"""
    parser = argparse.ArgumentParser(description='LegiScan State Legislation Collector')
    parser.add_argument('--state', type=str, default='ID', help='State to collect from (e.g., ID, CA, WA)')
    parser.add_argument('--year', type=int, help='Year to search (e.g., 2024)')
    parser.add_argument('--limit', type=int, default=20, help='Maximum bills to collect')
    parser.add_argument('--details', action='store_true', help='Include detailed bill information')
    parser.add_argument('--test', action='store_true', help='Test API connection')
    parser.add_argument('--stats', action='store_true', help='Show collection statistics')
    parser.add_argument('--api-key', type=str, help='LegiScan API key')

    args = parser.parse_args()

    collector = LegiScanCollector(api_key=args.api_key)

    if args.test:
        print("🧪 Testing LegiScan API connection...")
        if collector.test_connection():
            print("✅ LegiScan API connection successful")
        else:
            print("❌ LegiScan API connection failed")
        return

    if args.stats:
        print("📊 LegiScan Collection Statistics")
        stats = collector.get_collection_stats(args.state if args.state != 'all' else None)
        for key, value in stats.items():
            print(f"  {key}: {value}")
        return

    # Main collection
    bills = collector.collect_state_bills(
        state=args.state,
        year=args.year,
        limit=args.limit,
        include_details=args.details
    )

    print(f"✅ Collected {len(bills)} bills from {args.state}")

    # Show sample results
    for i, bill in enumerate(bills[:3], 1):
        print(f"\n{i}. {bill.get('title', 'No title')[:80]}...")
        print(f"   Number: {bill.get('bill_number')} | Status: {bill.get('status')}")
        if bill.get('sponsor'):
            print(f"   Sponsor: {bill.get('sponsor')}")

if __name__ == "__main__":
    main()