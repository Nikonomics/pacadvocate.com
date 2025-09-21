"""
Federal Register API Client
Handles communication with Federal Register API for CMS rules and regulations
"""

import requests
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from urllib.parse import urlencode
import json

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FederalRegisterRateLimiter:
    """Rate limiter for Federal Register API requests"""

    def __init__(self, requests_per_hour: int = 1000):  # Conservative rate limit
        self.requests_per_hour = requests_per_hour
        self.requests = []
        self.min_interval = 3600 / requests_per_hour  # seconds between requests

    def wait_if_needed(self):
        """Wait if necessary to respect rate limits"""
        now = time.time()

        # Remove requests older than 1 hour
        self.requests = [req_time for req_time in self.requests if now - req_time < 3600]

        # If we're at the limit, wait
        if len(self.requests) >= self.requests_per_hour:
            sleep_time = self.requests[0] + 3600 - now
            if sleep_time > 0:
                logger.info(f"Rate limit reached. Sleeping for {sleep_time:.2f} seconds")
                time.sleep(sleep_time)

        # Always wait minimum interval between requests (avoid overwhelming server)
        if self.requests and now - self.requests[-1] < self.min_interval:
            sleep_time = self.min_interval - (now - self.requests[-1])
            logger.debug(f"Minimum interval wait: {sleep_time:.2f} seconds")
            time.sleep(sleep_time)

        self.requests.append(time.time())

class FederalRegisterClient:
    """Client for Federal Register API with rate limiting and error handling"""

    def __init__(self):
        self.base_url = "https://www.federalregister.gov/api/v1"
        self.rate_limiter = FederalRegisterRateLimiter()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'SNFLegTracker/1.0 (Legislative Tracking Platform)',
            'Accept': 'application/json'
        })

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make a rate-limited request to the Federal Register API"""
        # Wait for rate limiting
        self.rate_limiter.wait_if_needed()

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        request_params = params or {}

        try:
            logger.debug(f"Making request to: {url}")
            response = self.session.get(url, params=request_params, timeout=30)
            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return None

    def search_documents(self,
                        agencies: Optional[List[str]] = None,
                        terms: Optional[str] = None,
                        document_types: Optional[List[str]] = None,
                        publication_date_from: Optional[str] = None,
                        publication_date_to: Optional[str] = None,
                        per_page: int = 100,
                        page: int = 1) -> Optional[Dict]:
        """
        Search Federal Register documents

        Args:
            agencies: List of agency names/codes (e.g., ['centers-for-medicare-medicaid-services'])
            terms: Search terms
            document_types: List of document types (e.g., ['RULE', 'PRORULE'])
            publication_date_from: Start date (YYYY-MM-DD)
            publication_date_to: End date (YYYY-MM-DD)
            per_page: Results per page (max 1000)
            page: Page number
        """
        endpoint = "documents.json"

        params = {
            'per_page': min(per_page, 1000),
            'page': page,
            'order': 'newest'
        }

        # Add search filters
        if agencies:
            params['conditions[agencies][]'] = agencies
        if terms:
            params['conditions[term]'] = terms
        if document_types:
            params['conditions[type][]'] = document_types
        if publication_date_from:
            params['conditions[publication_date][gte]'] = publication_date_from
        if publication_date_to:
            params['conditions[publication_date][lte]'] = publication_date_to

        return self._make_request(endpoint, params)

    def get_document_details(self, document_number: str) -> Optional[Dict]:
        """Get detailed information about a specific document"""
        endpoint = f"documents/{document_number}.json"
        return self._make_request(endpoint)

    def get_document_full_text(self, document_number: str) -> Optional[str]:
        """Get the full text of a document"""
        endpoint = f"documents/{document_number}"

        try:
            self.rate_limiter.wait_if_needed()
            url = f"{self.base_url}/{endpoint}"

            # Request HTML version for full text
            response = self.session.get(url, params={'format': 'html'}, timeout=60)
            response.raise_for_status()

            return response.text

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get document full text: {e}")
            return None

    def extract_comment_periods(self, document_data: Dict) -> Dict:
        """Extract comprehensive comment period information from document data"""
        from datetime import datetime, date
        import re

        comment_info = {
            'comment_start_date': None,
            'comment_end_date': None,
            'comment_url': None,
            'has_comment_period': False,
            'days_until_deadline': None,
            'is_urgent': False,
            'regulations_gov_url': None
        }

        # Check if document has comments
        if document_data.get('comment_url'):
            comment_info['comment_url'] = document_data['comment_url']
            comment_info['has_comment_period'] = True

        # Extract dates from various fields
        dates = document_data.get('dates', {})
        if isinstance(dates, dict):
            if 'comments' in dates:
                comment_info['comment_end_date'] = dates['comments']
                comment_info['has_comment_period'] = True

        # Check regulation info for comment periods
        if document_data.get('regulation_id_number_info'):
            reg_info = document_data['regulation_id_number_info']
            if isinstance(reg_info, dict) and reg_info.get('comments_close_on'):
                comment_info['comment_end_date'] = reg_info['comments_close_on']
                comment_info['has_comment_period'] = True

        # Look for comment period in document text/summary
        summary = document_data.get('abstract', '') or ''
        if 'comment' in summary.lower() and ('period' in summary.lower() or 'due' in summary.lower()):
            comment_info['has_comment_period'] = True

        # Create regulations.gov URL from document metadata
        if comment_info['has_comment_period']:
            # Try to get docket ID from various fields
            docket_id = None

            # Check regulation_id_number_info first
            if document_data.get('regulation_id_number_info'):
                reg_info = document_data['regulation_id_number_info']
                if isinstance(reg_info, dict):
                    docket_id = reg_info.get('docket_id') or reg_info.get('regulation_id_number')

            # Check agencies for CMS docket patterns
            if not docket_id and document_data.get('agencies'):
                agencies = document_data['agencies']
                if isinstance(agencies, list) and agencies:
                    agency = agencies[0]
                    if isinstance(agency, dict):
                        # Look for CMS docket pattern in document number
                        doc_number = document_data.get('document_number', '')
                        if doc_number and 'CMS' in str(agency.get('name', '')):
                            # Format as CMS docket ID
                            docket_id = f"CMS-{doc_number}"

            # Create regulations.gov URL if we have a docket ID
            if docket_id:
                comment_info['regulations_gov_url'] = f"https://www.regulations.gov/docket/{docket_id}/comments"

        # Calculate days until deadline if we have an end date
        if comment_info['comment_end_date']:
            try:
                # Parse the date string (Federal Register uses ISO format)
                if isinstance(comment_info['comment_end_date'], str):
                    end_date = datetime.fromisoformat(comment_info['comment_end_date'].replace('Z', '+00:00')).date()
                elif isinstance(comment_info['comment_end_date'], datetime):
                    end_date = comment_info['comment_end_date'].date()
                elif isinstance(comment_info['comment_end_date'], date):
                    end_date = comment_info['comment_end_date']
                else:
                    end_date = None

                if end_date:
                    today = date.today()
                    days_remaining = (end_date - today).days
                    comment_info['days_until_deadline'] = days_remaining

                    # Flag as urgent if less than 30 days remaining
                    comment_info['is_urgent'] = days_remaining < 30 and days_remaining >= 0

            except (ValueError, TypeError) as e:
                # If date parsing fails, log but don't crash
                print(f"Warning: Could not parse comment deadline date: {comment_info['comment_end_date']}")

        return comment_info

    def extract_effective_date(self, document_data: Dict) -> Optional[str]:
        """Extract effective date from document data"""
        # Check multiple possible fields for effective date
        dates = document_data.get('dates', {})
        if isinstance(dates, dict):
            if 'effective_on' in dates:
                return dates['effective_on']
            if 'publication' in dates:
                return dates['publication']

        # Check other date fields
        if document_data.get('effective_on'):
            return document_data['effective_on']

        if document_data.get('publication_date'):
            return document_data['publication_date']

        return None

    def get_snf_specific_search_terms(self) -> Dict[str, List[str]]:
        """Get SNF-specific search terms organized by priority and type"""
        return {
            'high_priority_exact': [
                "Skilled Nursing Facility Prospective Payment System",
                "SNF Quality Reporting Program",
                "SNF Prospective Payment System"
            ],
            'staffing_requirements': [
                "minimum staffing",
                "nurse staffing requirements",
                "nursing home staffing",
                "SNF staffing standards"
            ],
            'cms_operations': [
                "State Operations Manual SNF",
                "State Operations Manual skilled nursing",
                "Survey and Certification nursing home",
                "Survey and Certification SNF"
            ],
            'payment_systems': [
                "PDPM",
                "RUG-IV",
                "Medicare Part A SNF",
                "consolidated billing SNF"
            ],
            'quality_programs': [
                "Five-Star Quality Rating",
                "SNF Quality Reporting",
                "nursing home compare",
                "SNF star ratings"
            ]
        }

    def is_snf_relevant(self, document_data: Dict, snf_terms: List[str] = None) -> Dict:
        """Check if document is relevant to skilled nursing facilities using targeted criteria"""

        # Get SNF-specific search terms if not provided
        if not snf_terms:
            snf_search_terms = self.get_snf_specific_search_terms()
            snf_terms = []
            for category_terms in snf_search_terms.values():
                snf_terms.extend(category_terms)

        relevance_info = {
            'is_relevant': False,
            'matched_terms': [],
            'confidence_score': 0.0,
            'match_locations': [],
            'exclusion_reason': None,
            'match_category': None
        }

        # Combine searchable text
        title = document_data.get('title', '')
        abstract = document_data.get('abstract', '')
        topics = ' '.join(document_data.get('topics', []))
        agencies = ' '.join([agency.get('name', '') for agency in document_data.get('agencies', [])])

        searchable_text = f"{title} {abstract} {topics} {agencies}".lower()

        # EXCLUSION CRITERIA - Rules to exclude documents that are NOT SNF-relevant
        exclusion_terms = [
            ('hospital', ['skilled nursing', 'nursing facility', 'SNF']),  # Skip if hospital-focused unless also mentions SNF
            ('physician', ['skilled nursing', 'nursing facility', 'SNF']),  # Skip physician-only rules
            ('ambulatory', ['skilled nursing', 'nursing facility', 'SNF']),  # Skip ambulatory care
            ('outpatient', ['skilled nursing', 'nursing facility', 'SNF']),  # Skip outpatient-only
            ('emergency department', []),  # Skip ED-focused rules
            ('dialysis', ['skilled nursing', 'nursing facility', 'SNF']),  # Skip dialysis unless mentions SNF
        ]

        # Check exclusions
        for exclusion_term, exceptions in exclusion_terms:
            if exclusion_term in searchable_text:
                # Check if any exception terms are present
                has_exception = any(exception.lower() in searchable_text for exception in exceptions)
                if not has_exception:
                    relevance_info['exclusion_reason'] = f"Excluded: {exclusion_term}-focused rule"
                    return relevance_info

        # INCLUSION CRITERIA - Look for specific SNF-relevant terms
        snf_search_terms = self.get_snf_specific_search_terms()
        matched_terms = []
        match_locations = []
        confidence_weights = {
            'high_priority_exact': 1.0,
            'staffing_requirements': 0.9,
            'cms_operations': 0.8,
            'payment_systems': 0.8,
            'quality_programs': 0.7
        }

        highest_confidence = 0.0
        primary_match_category = None

        # Check each category of terms
        for category, terms in snf_search_terms.items():
            category_matches = []
            category_confidence = 0.0

            for term in terms:
                if term.lower() in searchable_text:
                    category_matches.append(term)
                    matched_terms.append(term)

                    # Track match locations
                    if term.lower() in title.lower():
                        match_locations.append('title')
                    if term.lower() in abstract.lower():
                        match_locations.append('abstract')
                    if term.lower() in topics.lower():
                        match_locations.append('topics')

            # Calculate confidence for this category
            if category_matches:
                base_weight = confidence_weights.get(category, 0.5)
                match_bonus = min(len(category_matches) * 0.2, 0.4)
                title_bonus = 0.3 if any(term.lower() in title.lower() for term in category_matches) else 0

                category_confidence = base_weight + match_bonus + title_bonus

                if category_confidence > highest_confidence:
                    highest_confidence = category_confidence
                    primary_match_category = category

        # Determine if document is relevant
        if matched_terms and highest_confidence >= 0.5:
            relevance_info['is_relevant'] = True
            relevance_info['matched_terms'] = matched_terms
            relevance_info['match_locations'] = list(set(match_locations))
            relevance_info['confidence_score'] = min(highest_confidence, 1.0)
            relevance_info['match_category'] = primary_match_category
        else:
            relevance_info['exclusion_reason'] = f"Insufficient SNF relevance (confidence: {highest_confidence:.2f})"

        return relevance_info

    def search_cms_documents(self,
                           search_terms: List[str] = None,
                           document_types: List[str] = None,
                           year: int = None,
                           limit: int = 100) -> List[Dict]:
        """
        Search specifically for CMS documents

        Args:
            search_terms: List of terms to search for
            document_types: Types of documents ['RULE', 'PRORULE', 'NOTICE']
            year: Filter by year
            limit: Maximum results to return
        """
        all_results = []

        # CMS agency identifiers
        cms_agencies = [
            'centers-for-medicare-medicaid-services',
            'health-and-human-services-department'
        ]

        # Default document types if not specified
        if not document_types:
            document_types = ['RULE', 'PRORULE', 'NOTICE']

        # Set date range if year specified
        publication_date_from = None
        publication_date_to = None
        if year:
            publication_date_from = f"{year}-01-01"
            publication_date_to = f"{year}-12-31"

        # Use SNF-specific search terms if none provided
        if not search_terms:
            snf_search_terms = self.get_snf_specific_search_terms()
            search_terms = []
            # Prioritize high-priority exact matches first
            search_terms.extend(snf_search_terms['high_priority_exact'])
            search_terms.extend(snf_search_terms['staffing_requirements'])
            search_terms.extend(snf_search_terms['payment_systems'])

        # Create targeted search queries
        search_queries = []

        # Use exact phrase searches for better precision
        if search_terms:
            for term in search_terms[:8]:  # Limit queries to avoid rate limits
                # Use quotes for exact phrase matching
                if '"' not in term and ' ' in term:
                    search_queries.append(f'"{term}"')
                else:
                    search_queries.append(term)
        else:
            # Fallback to broad SNF search
            search_queries = ['"skilled nursing facility"', '"nursing home"', 'PDPM', 'SNF']

        logger.info(f"Using {len(search_queries)} targeted SNF search queries")

        for query in search_queries:
            if len(all_results) >= limit:
                break

            logger.info(f"Searching CMS documents for: {query or 'all CMS documents'}")

            page = 1
            while len(all_results) < limit:
                results = self.search_documents(
                    agencies=cms_agencies,
                    terms=query,
                    document_types=document_types,
                    publication_date_from=publication_date_from,
                    publication_date_to=publication_date_to,
                    per_page=min(100, limit - len(all_results)),
                    page=page
                )

                if not results or 'results' not in results:
                    break

                documents = results['results']
                if not documents:
                    break

                # Add search context and process each document
                for doc in documents:
                    doc['search_query'] = query
                    doc['search_timestamp'] = datetime.utcnow().isoformat()

                    # Extract comment periods and effective dates
                    doc['comment_info'] = self.extract_comment_periods(doc)
                    doc['effective_date'] = self.extract_effective_date(doc)

                    # Check SNF relevance
                    doc['snf_relevance'] = self.is_snf_relevant(doc)

                all_results.extend(documents)
                logger.info(f"Found {len(documents)} documents (total: {len(all_results)})")

                # Check if we have more pages
                if len(documents) < 100 or len(all_results) >= limit:
                    break

                page += 1

        # Remove duplicates based on document number
        seen_docs = set()
        unique_results = []
        for doc in all_results:
            doc_num = doc.get('document_number')
            if doc_num and doc_num not in seen_docs:
                seen_docs.add(doc_num)
                unique_results.append(doc)

        logger.info(f"Total unique CMS documents found: {len(unique_results)}")
        return unique_results[:limit]

    def search_snf_payment_rules(self, year: int = None, limit: int = 20) -> List[Dict]:
        """
        Search specifically for SNF payment system rules and updates

        Args:
            year: Year to search (defaults to current year)
            limit: Maximum results to return

        Returns:
            List of relevant SNF payment rule documents
        """
        if not year:
            year = datetime.now().year

        logger.info(f"Searching for SNF payment rules for {year}...")

        # Specific search terms for SNF payment rules
        payment_search_terms = [
            '"Skilled Nursing Facility Prospective Payment System"',
            '"SNF Prospective Payment System"',
            '"PDPM"',
            '"Patient-Driven Payment Model"',
            '"SNF Quality Reporting Program"',
            '"Medicare Program" "skilled nursing"',
            '"consolidated billing" SNF',
            '"Part A payment" "skilled nursing"'
        ]

        results = []

        # Search for each payment term
        for search_term in payment_search_terms:
            if len(results) >= limit:
                break

            logger.info(f"Searching for: {search_term}")

            docs = self.search_cms_documents(
                search_terms=[search_term.replace('"', '')],
                document_types=['RULE', 'PRORULE'],
                year=year,
                limit=limit - len(results)
            )

            if docs:
                # Filter for high-relevance SNF payment documents
                for doc in docs:
                    snf_relevance = doc.get('snf_relevance', {})
                    if (snf_relevance.get('is_relevant', False) and
                        snf_relevance.get('confidence_score', 0) >= 0.7 and
                        snf_relevance.get('match_category') in ['high_priority_exact', 'payment_systems']):
                        results.append(doc)

        # Remove duplicates and sort by relevance
        seen_docs = set()
        unique_results = []
        for doc in results:
            doc_num = doc.get('document_number')
            if doc_num and doc_num not in seen_docs:
                seen_docs.add(doc_num)
                unique_results.append(doc)

        # Sort by publication date (newest first)
        unique_results.sort(key=lambda x: x.get('publication_date', ''), reverse=True)

        logger.info(f"Found {len(unique_results)} SNF payment rules for {year}")
        return unique_results[:limit]

    def get_agencies(self) -> Optional[Dict]:
        """Get list of all agencies"""
        return self._make_request("agencies.json")

    def test_connection(self) -> bool:
        """Test the API connection"""
        logger.info("Testing Federal Register API connection...")

        try:
            # Try a simple search
            result = self.search_documents(per_page=1)

            if result and 'results' in result:
                logger.info("✅ Federal Register API connection successful")
                return True
            else:
                logger.error("❌ Federal Register API connection failed")
                return False

        except Exception as e:
            logger.error(f"❌ Federal Register API connection failed: {e}")
            return False

    def get_rate_limit_status(self) -> Dict:
        """Get current rate limit status"""
        now = time.time()
        recent_requests = [req for req in self.rate_limiter.requests if now - req < 3600]

        return {
            'requests_in_last_hour': len(recent_requests),
            'requests_remaining': self.rate_limiter.requests_per_hour - len(recent_requests),
            'reset_time': max(recent_requests) + 3600 if recent_requests else now,
            'next_request_allowed': max(recent_requests) + self.rate_limiter.min_interval if recent_requests else now
        }

# Test function
def test_client():
    """Test the Federal Register client"""
    client = FederalRegisterClient()

    # Test connection
    if not client.test_connection():
        print("❌ API connection failed.")
        return

    print("\n🔍 Testing SNF-specific document search...")

    # Test SNF payment rules search
    snf_payment_docs = client.search_snf_payment_rules(year=2025, limit=5)

    if snf_payment_docs:
        print(f"✅ Found {len(snf_payment_docs)} SNF payment rules for 2025")
        for i, doc in enumerate(snf_payment_docs, 1):
            snf_relevance = doc.get('snf_relevance', {})
            print(f"  {i}. {doc.get('title', 'No title')[:80]}...")
            print(f"     Type: {doc.get('type')} | Date: {doc.get('publication_date')}")
            print(f"     SNF Relevance: {snf_relevance.get('confidence_score', 0):.1%}")
            print(f"     Category: {snf_relevance.get('match_category', 'unknown')}")
            if snf_relevance.get('matched_terms'):
                print(f"     Matches: {', '.join(snf_relevance['matched_terms'][:3])}")
    else:
        print("❌ No SNF payment rules found for 2025")

    # Test general CMS search with exclusions
    print("\n🔍 Testing general CMS search with exclusions...")
    cms_docs = client.search_cms_documents(
        document_types=['RULE', 'PRORULE'],
        year=2025,
        limit=10
    )

    if cms_docs:
        relevant_docs = [doc for doc in cms_docs if doc.get('snf_relevance', {}).get('is_relevant', False)]
        excluded_docs = [doc for doc in cms_docs if doc.get('snf_relevance', {}).get('exclusion_reason')]

        print(f"✅ Found {len(cms_docs)} total CMS documents")
        print(f"   📋 {len(relevant_docs)} SNF-relevant documents")
        print(f"   ❌ {len(excluded_docs)} excluded documents")

        if relevant_docs:
            print("\n📋 SNF-Relevant Documents:")
            for i, doc in enumerate(relevant_docs[:3], 1):
                snf_relevance = doc.get('snf_relevance', {})
                print(f"  {i}. {doc.get('title', 'No title')[:60]}...")
                print(f"     Confidence: {snf_relevance.get('confidence_score', 0):.1%}")

        if excluded_docs:
            print("\n❌ Excluded Documents (examples):")
            for i, doc in enumerate(excluded_docs[:2], 1):
                exclusion = doc.get('snf_relevance', {}).get('exclusion_reason', 'Unknown')
                print(f"  {i}. {doc.get('title', 'No title')[:60]}...")
                print(f"     Reason: {exclusion}")
    else:
        print("❌ No CMS documents found")

    # Show rate limit status
    status = client.get_rate_limit_status()
    print(f"\n📊 Rate limit status:")
    print(f"  • Requests in last hour: {status['requests_in_last_hour']}")
    print(f"  • Requests remaining: {status['requests_remaining']}")

if __name__ == "__main__":
    test_client()