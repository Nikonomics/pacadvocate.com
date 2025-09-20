"""
Congress.gov API Client
Handles communication with Congress.gov API with rate limiting and authentication
"""

import requests
import time
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from urllib.parse import urlencode
import json

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RateLimiter:
    """Simple rate limiter for API requests"""

    def __init__(self, requests_per_hour: int = 4800):  # Conservative limit (5000/hour max)
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

        # Always wait minimum interval between requests
        if self.requests and now - self.requests[-1] < self.min_interval:
            sleep_time = self.min_interval - (now - self.requests[-1])
            logger.debug(f"Minimum interval wait: {sleep_time:.2f} seconds")
            time.sleep(sleep_time)

        self.requests.append(time.time())

class CongressAPIClient:
    """Client for Congress.gov API with rate limiting and error handling"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('CONGRESS_API_KEY')
        self.base_url = "https://api.congress.gov/v3"
        self.rate_limiter = RateLimiter()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'SNFLegTracker/1.0 (Legislative Tracking Platform)'
        })

        if not self.api_key:
            logger.warning("No Congress.gov API key found. Set CONGRESS_API_KEY environment variable.")
            logger.info("Sign up for an API key at: https://api.congress.gov/sign-up/")

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make a rate-limited request to the Congress.gov API"""
        if not self.api_key:
            logger.error("No API key available. Cannot make request.")
            return None

        # Wait for rate limiting
        self.rate_limiter.wait_if_needed()

        # Add API key to parameters
        request_params = params or {}
        request_params['api_key'] = self.api_key
        request_params['format'] = 'json'

        url = f"{self.base_url}/{endpoint.lstrip('/')}"

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

    def search_bills(self, congress: int = 119, query: Optional[str] = None,
                    limit: int = 250, offset: int = 0,
                    bill_type: Optional[str] = None,
                    from_date: Optional[str] = None,
                    to_date: Optional[str] = None) -> Optional[Dict]:
        """
        Search for bills in Congress

        Args:
            congress: Congress number (119 for current, 118 for previous)
            query: Search query text
            limit: Number of results (max 250)
            offset: Pagination offset
            bill_type: Type of bill (hr, s, hjres, sjres, hconres, sconres)
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
        """
        endpoint = f"bill/{congress}"

        params = {
            'limit': min(limit, 250),
            'offset': offset
        }

        # Add search parameters
        if query:
            params['q'] = query
        if bill_type:
            params['billType'] = bill_type
        if from_date:
            params['fromDateTime'] = from_date
        if to_date:
            params['toDateTime'] = to_date

        return self._make_request(endpoint, params)

    def get_bill_details(self, congress: int, bill_type: str, bill_number: int) -> Optional[Dict]:
        """Get detailed information about a specific bill"""
        endpoint = f"bill/{congress}/{bill_type.lower()}/{bill_number}"
        return self._make_request(endpoint)

    def get_bill_text(self, congress: int, bill_type: str, bill_number: int) -> Optional[Dict]:
        """Get the text of a specific bill"""
        endpoint = f"bill/{congress}/{bill_type.lower()}/{bill_number}/text"
        return self._make_request(endpoint)

    def get_bill_actions(self, congress: int, bill_type: str, bill_number: int) -> Optional[Dict]:
        """Get actions taken on a specific bill"""
        endpoint = f"bill/{congress}/{bill_type.lower()}/{bill_number}/actions"
        return self._make_request(endpoint)

    def search_by_keywords(self, keywords: List[str], congress: int = 119,
                          limit: int = 250, year: Optional[int] = None) -> List[Dict]:
        """
        Search for bills using multiple keywords

        Args:
            keywords: List of search terms
            congress: Congress number
            limit: Total results limit
            year: Filter by year (2024, 2025, etc.)
        """
        all_results = []

        # Set date range if year is specified
        from_date = None
        to_date = None
        if year:
            from_date = f"{year}-01-01"
            to_date = f"{year}-12-31"

        for keyword in keywords:
            logger.info(f"Searching for keyword: '{keyword}'")

            # Search for this keyword
            results = self.search_bills(
                congress=congress,
                query=keyword,
                limit=min(limit, 250),
                from_date=from_date,
                to_date=to_date
            )

            if results and 'bills' in results:
                bills = results['bills']
                logger.info(f"Found {len(bills)} bills for keyword '{keyword}'")

                # Add keyword information to each bill
                for bill in bills:
                    bill['matched_keyword'] = keyword
                    bill['search_timestamp'] = datetime.utcnow().isoformat()

                all_results.extend(bills)
            else:
                logger.info(f"No results found for keyword '{keyword}'")

        # Remove duplicates based on bill number
        seen_bills = set()
        unique_results = []

        for bill in all_results:
            bill_id = f"{bill.get('congress', '')}-{bill.get('type', '')}-{bill.get('number', '')}"
            if bill_id not in seen_bills:
                seen_bills.add(bill_id)
                unique_results.append(bill)

        logger.info(f"Total unique bills found: {len(unique_results)}")
        return unique_results

    def get_current_congress(self) -> int:
        """Get the current Congress number"""
        # 119th Congress: January 3, 2025 – January 3, 2027
        # 118th Congress: January 3, 2023 – January 3, 2025
        now = datetime.now()

        if now.year >= 2025:
            return 119
        elif now.year >= 2023:
            return 118
        else:
            # Calculate based on the fact that 118th Congress started in 2023
            return 118 - ((2023 - now.year) // 2)

    def test_connection(self) -> bool:
        """Test the API connection and authentication"""
        logger.info("Testing Congress.gov API connection...")

        if not self.api_key:
            logger.error("No API key configured")
            return False

        # Try a simple request
        result = self.search_bills(congress=119, limit=1)

        if result:
            logger.info("✅ API connection successful")
            return True
        else:
            logger.error("❌ API connection failed")
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
    """Test the Congress API client"""
    client = CongressAPIClient()

    # Test connection
    if not client.test_connection():
        print("❌ API connection failed. Please check your API key.")
        return

    # Test search
    print("\n🔍 Testing bill search...")
    results = client.search_bills(congress=119, query="Medicare", limit=5)

    if results and 'bills' in results:
        print(f"✅ Found {len(results['bills'])} bills")
        for bill in results['bills'][:3]:
            print(f"  • {bill.get('type', 'Unknown').upper()} {bill.get('number', 'N/A')}: {bill.get('title', 'No title')[:100]}...")
    else:
        print("❌ No bills found")

    # Show rate limit status
    status = client.get_rate_limit_status()
    print(f"\n📊 Rate limit status:")
    print(f"  • Requests in last hour: {status['requests_in_last_hour']}")
    print(f"  • Requests remaining: {status['requests_remaining']}")

if __name__ == "__main__":
    test_client()