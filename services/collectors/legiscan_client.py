"""
LegiScan API Client
Handles communication with LegiScan API for state legislation tracking
"""

import requests
import time
import logging
import hashlib
import base64
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from urllib.parse import urlencode
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LegiScanRateLimiter:
    """Rate limiter for LegiScan API requests"""

    def __init__(self, requests_per_month: int = 30000):
        self.requests_per_month = requests_per_month
        self.requests = []
        # Conservative daily limit (assuming 30-day month)
        self.daily_limit = requests_per_month // 30
        self.min_interval = 86400 / self.daily_limit  # seconds between requests

    def wait_if_needed(self):
        """Wait if necessary to respect rate limits"""
        now = time.time()

        # Remove requests older than 24 hours
        self.requests = [req_time for req_time in self.requests if now - req_time < 86400]

        # If we're at the daily limit, wait
        if len(self.requests) >= self.daily_limit:
            sleep_time = self.requests[0] + 86400 - now
            if sleep_time > 0:
                logger.info(f"Daily rate limit reached. Sleeping for {sleep_time:.2f} seconds")
                time.sleep(sleep_time)

        # Always wait minimum interval between requests
        if self.requests and now - self.requests[-1] < self.min_interval:
            sleep_time = self.min_interval - (now - self.requests[-1])
            logger.debug(f"Minimum interval wait: {sleep_time:.2f} seconds")
            time.sleep(sleep_time)

        self.requests.append(time.time())

class LegiScanClient:
    """Client for LegiScan API with rate limiting and error handling"""

    # State ID mappings for LegiScan
    STATE_IDS = {
        'ID': 12,  # Idaho (corrected from API response)
        'CA': 5,   # California
        'TX': 44,  # Texas
        'FL': 10,  # Florida
        'NY': 32,  # New York
        'WA': 47,  # Washington
        'OR': 38,  # Oregon
        'NV': 29,  # Nevada
        'MT': 27,  # Montana
        'UT': 45,  # Utah
        'WY': 51,  # Wyoming
        # Add more states as needed - IDs should be verified against API
    }

    def __init__(self, api_key: str = None):
        self.api_key = api_key or self._get_api_key()
        if not self.api_key:
            raise ValueError("LegiScan API key required. Set LEGISCAN_API_KEY environment variable.")

        self.base_url = "https://api.legiscan.com/"
        self.rate_limiter = LegiScanRateLimiter()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'SNFLegTracker/1.0 (Legislative Tracking Platform)',
            'Accept': 'application/json'
        })

        logger.info(f"LegiScan client initialized with API key: {self.api_key[:8]}...")

    def _get_api_key(self) -> Optional[str]:
        """Get API key from environment or config"""
        import os
        return os.getenv('LEGISCAN_API_KEY')

    def _make_request(self, endpoint: str = '', params: Optional[Dict] = None) -> Optional[Dict]:
        """Make a rate-limited request to the LegiScan API"""
        # Wait for rate limiting
        self.rate_limiter.wait_if_needed()

        url = f"{self.base_url.rstrip('/')}"
        request_params = params or {}

        # Add API key to parameters
        request_params['key'] = self.api_key
        request_params['op'] = endpoint

        try:
            logger.debug(f"Making LegiScan request: {endpoint}")
            response = self.session.get(url, params=request_params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Check for API errors
            if 'status' in data and data['status'] != 'OK':
                logger.error(f"LegiScan API error: {data.get('alert', 'Unknown error')}")
                return None

            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return None

    def get_session_list(self, state: str) -> Optional[Dict]:
        """Get list of available sessions for a state"""
        state_id = self.STATE_IDS.get(state.upper())
        if not state_id:
            logger.error(f"Unknown state: {state}")
            return None

        params = {'state': state_id}
        return self._make_request('getSessionList', params)

    def get_master_list(self, state: str, session_id: int = None) -> Optional[Dict]:
        """Get master list of bills for a state session"""
        state_id = self.STATE_IDS.get(state.upper())
        if not state_id:
            logger.error(f"Unknown state: {state}")
            return None

        params = {'state': state_id}
        if session_id:
            params['id'] = session_id

        return self._make_request('getMasterList', params)

    def search_bills(self, state: str, query: str, year: int = None) -> Optional[Dict]:
        """Search for bills in a state by query"""
        # For search, try different approaches
        params = {
            'state': state.upper(),  # Try state abbreviation instead of ID
            'query': query
        }

        if year:
            params['year'] = year

        result = self._make_request('search', params)

        # If state abbreviation failed, try state ID
        if not result:
            state_id = self.STATE_IDS.get(state.upper())
            if state_id:
                params['state'] = state_id
                result = self._make_request('search', params)

        return result

    def get_bill(self, bill_id: int) -> Optional[Dict]:
        """Get detailed bill information"""
        params = {'id': bill_id}
        return self._make_request('getBill', params)

    def get_bill_text(self, doc_id: int) -> Optional[Dict]:
        """Get bill text document"""
        params = {'id': doc_id}
        return self._make_request('getBillText', params)

    def get_amendment(self, amendment_id: int) -> Optional[Dict]:
        """Get amendment information"""
        params = {'id': amendment_id}
        return self._make_request('getAmendment', params)

    def get_supplement(self, supplement_id: int) -> Optional[Dict]:
        """Get supplement information (votes, etc.)"""
        params = {'id': supplement_id}
        return self._make_request('getSupplement', params)

    def get_sponsor(self, people_id: int) -> Optional[Dict]:
        """Get sponsor/people information"""
        params = {'id': people_id}
        return self._make_request('getSponsor', params)

    def search_healthcare_bills(self,
                              state: str,
                              search_terms: List[str] = None,
                              year: int = None,
                              limit: int = 50) -> List[Dict]:
        """Search for healthcare-related bills in a state"""

        if not search_terms:
            search_terms = [
                "nursing facility", "skilled nursing", "assisted living",
                "Medicaid", "staffing", "long-term care", "nursing home",
                "Medicare", "healthcare", "health care"
            ]

        all_results = []

        for term in search_terms:
            if len(all_results) >= limit:
                break

            logger.info(f"Searching {state} for: {term}")

            results = self.search_bills(state, term, year)

            if not results or 'searchresult' not in results:
                logger.debug(f"No results for term: {term}")
                continue

            search_data = results['searchresult']
            if not search_data:
                continue

            # Extract bills from search results - LegiScan returns numbered entries
            bills = []
            i = 0
            while str(i) in search_data:
                bill_data = search_data[str(i)]
                if bill_data and isinstance(bill_data, dict):
                    bills.append(bill_data)
                i += 1

            if not bills:
                logger.debug(f"No bill data found in search results for: {term}")
                continue

            for bill in bills:
                if len(all_results) >= limit:
                    break

                # Add search context
                bill['search_term'] = term
                bill['search_timestamp'] = datetime.utcnow().isoformat()

                # Add state info
                bill['state'] = state.upper()
                bill['state_id'] = self.STATE_IDS.get(state.upper())

                all_results.append(bill)

            logger.info(f"Found {len(bills)} bills for term: {term}")

        # Remove duplicates based on bill_id
        seen_ids = set()
        unique_results = []
        for bill in all_results:
            bill_id = bill.get('bill_id')
            if bill_id and bill_id not in seen_ids:
                seen_ids.add(bill_id)
                unique_results.append(bill)

        logger.info(f"Total unique healthcare bills found in {state}: {len(unique_results)}")
        return unique_results[:limit]

    def get_detailed_bill_info(self, bill_id: int) -> Optional[Dict]:
        """Get comprehensive bill information including text and supplements"""
        logger.info(f"Fetching detailed info for bill ID: {bill_id}")

        # Get basic bill info
        bill_data = self.get_bill(bill_id)
        if not bill_data or 'bill' not in bill_data:
            return None

        bill = bill_data['bill']

        # Get bill text documents
        texts = []
        if 'texts' in bill:
            for text in bill['texts']:
                doc_id = text.get('doc_id')
                if doc_id:
                    text_data = self.get_bill_text(doc_id)
                    if text_data:
                        texts.append(text_data)

        # Get supplements (votes, committee actions, etc.)
        supplements = []
        if 'supplements' in bill:
            for supp in bill['supplements']:
                supp_id = supp.get('supplement_id')
                if supp_id:
                    supp_data = self.get_supplement(supp_id)
                    if supp_data:
                        supplements.append(supp_data)

        # Get sponsor details
        sponsors = []
        if 'sponsors' in bill:
            for sponsor in bill['sponsors']:
                people_id = sponsor.get('people_id')
                if people_id:
                    sponsor_data = self.get_sponsor(people_id)
                    if sponsor_data:
                        sponsors.append(sponsor_data)

        # Combine all data
        detailed_bill = {
            'bill': bill,
            'texts': texts,
            'supplements': supplements,
            'sponsors': sponsors,
            'retrieved_at': datetime.utcnow().isoformat()
        }

        return detailed_bill

    def test_connection(self) -> bool:
        """Test the API connection"""
        logger.info("Testing LegiScan API connection...")

        try:
            # Try to get general session list (no state parameter)
            result = self._make_request('getSessionList', {})

            if result and 'sessions' in result:
                # Check if Idaho sessions are available
                idaho_sessions = [s for s in result['sessions'] if s.get('state_abbr') == 'ID']
                if idaho_sessions:
                    logger.info(f"✅ LegiScan API connection successful - Found {len(idaho_sessions)} Idaho sessions")
                    return True
                else:
                    logger.warning("⚠️ LegiScan API connected but no Idaho sessions found")
                    return True  # API works, just no Idaho data
            else:
                logger.error("❌ LegiScan API connection failed")
                return False

        except Exception as e:
            logger.error(f"❌ LegiScan API connection failed: {e}")
            return False

    def get_rate_limit_status(self) -> Dict:
        """Get current rate limit status"""
        now = time.time()
        recent_requests = [req for req in self.rate_limiter.requests if now - req < 86400]

        return {
            'requests_in_last_24_hours': len(recent_requests),
            'daily_limit': self.rate_limiter.daily_limit,
            'requests_remaining_today': self.rate_limiter.daily_limit - len(recent_requests),
            'reset_time': max(recent_requests) + 86400 if recent_requests else now,
            'next_request_allowed': max(recent_requests) + self.rate_limiter.min_interval if recent_requests else now
        }

# Test function
def test_client():
    """Test the LegiScan client"""
    import os

    api_key = os.getenv('LEGISCAN_API_KEY')
    if not api_key:
        print("❌ No LEGISCAN_API_KEY found in environment variables")
        print("   Please set your LegiScan API key:")
        print("   export LEGISCAN_API_KEY='your_api_key_here'")
        return

    client = LegiScanClient(api_key)

    # Test connection
    if not client.test_connection():
        print("❌ API connection failed.")
        return

    print("\n🔍 Testing Idaho healthcare bill search...")

    # Test healthcare search
    healthcare_bills = client.search_healthcare_bills(
        state='ID',
        search_terms=['Medicaid', 'nursing facility'],
        year=2024,
        limit=5
    )

    if healthcare_bills:
        print(f"✅ Found {len(healthcare_bills)} healthcare bills in Idaho")
        for i, bill in enumerate(healthcare_bills[:3], 1):
            print(f"  {i}. {bill.get('title', 'No title')[:60]}...")
            print(f"     Number: {bill.get('bill_number')} | Status: {bill.get('status_desc', 'Unknown')}")
    else:
        print("❌ No healthcare bills found")

    # Show rate limit status
    status = client.get_rate_limit_status()
    print(f"\n📊 Rate limit status:")
    print(f"  • Requests today: {status['requests_in_last_24_hours']}")
    print(f"  • Daily limit: {status['daily_limit']}")
    print(f"  • Requests remaining: {status['requests_remaining_today']}")

if __name__ == "__main__":
    test_client()