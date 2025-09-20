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
        """Extract comment period information from document data"""
        comment_info = {
            'comment_start_date': None,
            'comment_end_date': None,
            'comment_url': None,
            'has_comment_period': False
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

    def is_snf_relevant(self, document_data: Dict, snf_terms: List[str] = None) -> Dict:
        """Check if document is relevant to skilled nursing facilities"""
        if not snf_terms:
            snf_terms = [
                'skilled nursing facility', 'skilled nursing facilities', 'SNF', 'SNFs',
                'nursing home', 'nursing homes', 'long-term care', 'post-acute care',
                'Medicare Part A', 'PDPM', 'RUG', 'staffing ratio', 'star rating',
                'five star quality rating', 'quality reporting program', 'survey',
                'certification', 'reimbursement', 'payment system'
            ]

        relevance_info = {
            'is_relevant': False,
            'matched_terms': [],
            'confidence_score': 0.0,
            'match_locations': []
        }

        # Combine searchable text
        searchable_text = ' '.join([
            document_data.get('title', ''),
            document_data.get('abstract', ''),
            ' '.join(document_data.get('topics', [])),
            ' '.join([agency.get('name', '') for agency in document_data.get('agencies', [])]),
        ]).lower()

        matched_terms = []
        match_locations = []

        for term in snf_terms:
            if term.lower() in searchable_text:
                matched_terms.append(term)
                if 'title' in document_data and term.lower() in document_data['title'].lower():
                    match_locations.append('title')
                if 'abstract' in document_data and term.lower() in document_data.get('abstract', '').lower():
                    match_locations.append('abstract')

        if matched_terms:
            relevance_info['is_relevant'] = True
            relevance_info['matched_terms'] = matched_terms
            relevance_info['match_locations'] = list(set(match_locations))

            # Simple confidence scoring based on matches
            base_score = min(len(matched_terms) * 0.15, 0.9)
            title_bonus = 0.1 if 'title' in match_locations else 0
            relevance_info['confidence_score'] = min(base_score + title_bonus, 1.0)

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

        # Search with different term combinations
        search_queries = []
        if search_terms:
            # Search each term individually for broader coverage
            search_queries.extend(search_terms)
            # Also try combined search
            search_queries.append(' '.join(search_terms[:3]))  # Limit to avoid too long queries
        else:
            # If no terms specified, search for general CMS documents
            search_queries = [None]

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

    print("\n🔍 Testing CMS document search...")

    # Test CMS search
    cms_docs = client.search_cms_documents(
        search_terms=['Medicare', 'skilled nursing'],
        document_types=['RULE', 'PRORULE'],
        year=2024,
        limit=5
    )

    if cms_docs:
        print(f"✅ Found {len(cms_docs)} CMS documents")
        for i, doc in enumerate(cms_docs[:3], 1):
            print(f"  {i}. {doc.get('title', 'No title')[:80]}...")
            print(f"     Type: {doc.get('type')} | Date: {doc.get('publication_date')}")
    else:
        print("❌ No CMS documents found")

    # Show rate limit status
    status = client.get_rate_limit_status()
    print(f"\n📊 Rate limit status:")
    print(f"  • Requests in last hour: {status['requests_in_last_hour']}")
    print(f"  • Requests remaining: {status['requests_remaining']}")

if __name__ == "__main__":
    test_client()