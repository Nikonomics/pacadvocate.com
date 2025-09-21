"""
CMS Survey & Certification Client
Collects survey memos and enforcement guidance from CMS.gov
"""

import requests
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from urllib.parse import urljoin, urlencode
import json
from bs4 import BeautifulSoup
import re

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CMSSurveyRateLimiter:
    """Rate limiter for CMS website requests"""

    def __init__(self, requests_per_minute: int = 10):  # Conservative rate limit
        self.requests_per_minute = requests_per_minute
        self.requests = []
        self.min_interval = 60 / requests_per_minute  # seconds between requests

    def wait_if_needed(self):
        """Wait if necessary to respect rate limits"""
        now = time.time()

        # Remove requests older than 1 minute
        self.requests = [req_time for req_time in self.requests if now - req_time < 60]

        # If we're at the limit, wait
        if len(self.requests) >= self.requests_per_minute:
            sleep_time = self.requests[0] + 60 - now
            if sleep_time > 0:
                logger.info(f"Rate limit reached. Sleeping for {sleep_time:.2f} seconds")
                time.sleep(sleep_time)

        # Always wait minimum interval between requests
        if self.requests and now - self.requests[-1] < self.min_interval:
            sleep_time = self.min_interval - (now - self.requests[-1])
            logger.debug(f"Minimum interval wait: {sleep_time:.2f} seconds")
            time.sleep(sleep_time)

        self.requests.append(time.time())

class CMSSurveyClient:
    """Client for CMS Survey & Certification documents with rate limiting"""

    def __init__(self):
        self.base_url = "https://www.cms.gov"
        self.survey_base_url = "https://www.cms.gov/medicare/provider-enrollment-and-certification/surveycertificationgeninfo"
        self.rate_limiter = CMSSurveyRateLimiter()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'SNF Legislation Tracker - CMS Survey Document Collector',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })

    def get_survey_memos(self, days_back: int = 90) -> List[Dict]:
        """
        Get recent CMS Survey & Certification memos
        Args:
            days_back: Number of days back to search for memos
        Returns:
            List of memo documents with metadata
        """
        memos = []

        try:
            # Get the main survey page
            self.rate_limiter.wait_if_needed()
            response = self.session.get(self.survey_base_url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Look for memo links and documents
            memo_links = self._extract_memo_links(soup)

            cutoff_date = datetime.now() - timedelta(days=days_back)

            for link_info in memo_links:
                try:
                    # Get the individual memo
                    memo_data = self._process_memo_link(link_info)

                    if memo_data and self._is_snf_relevant(memo_data):
                        # Check if within date range
                        if memo_data.get('date'):
                            memo_date = datetime.strptime(memo_data['date'], '%Y-%m-%d')
                            if memo_date >= cutoff_date:
                                memos.append(memo_data)
                        else:
                            # Include if no date available (assume recent)
                            memos.append(memo_data)

                except Exception as e:
                    logger.warning(f"Error processing memo {link_info.get('url', 'unknown')}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error fetching survey memos: {e}")

        return memos

    def _extract_memo_links(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract memo links from the main survey page"""
        memo_links = []

        # Look for various patterns that indicate survey memos
        link_patterns = [
            'memo',
            'survey',
            'certification',
            'guidance',
            'enforcement',
            'snf',
            'nursing home',
            'skilled nursing'
        ]

        # Find all links that might be memos
        all_links = soup.find_all('a', href=True)

        for link in all_links:
            href = link.get('href', '')
            text = link.get_text(strip=True).lower()

            # Check if this looks like a survey memo
            if any(pattern in text for pattern in link_patterns) or any(pattern in href.lower() for pattern in link_patterns):
                if href.startswith('/'):
                    full_url = urljoin(self.base_url, href)
                elif href.startswith('http'):
                    full_url = href
                else:
                    continue

                memo_links.append({
                    'url': full_url,
                    'text': link.get_text(strip=True),
                    'href': href
                })

        return memo_links

    def _process_memo_link(self, link_info: Dict) -> Optional[Dict]:
        """Process an individual memo link and extract content"""
        try:
            self.rate_limiter.wait_if_needed()
            response = self.session.get(link_info['url'], timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract memo content and metadata
            memo_data = {
                'title': self._extract_title(soup, link_info['text']),
                'url': link_info['url'],
                'content': self._extract_content(soup),
                'date': self._extract_date(soup, link_info['text']),
                'memo_type': self._determine_memo_type(soup, link_info['text']),
                'source': 'cms_survey',
                'enforcement_topics': self._extract_enforcement_topics(soup)
            }

            return memo_data

        except Exception as e:
            logger.warning(f"Error processing memo link: {e}")
            return None

    def _extract_title(self, soup: BeautifulSoup, fallback_text: str) -> str:
        """Extract title from the memo page"""
        # Try various title selectors
        title_selectors = [
            'h1',
            '.page-title',
            '.content-title',
            'title',
            '.main-content h1',
            '.article-title'
        ]

        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                title = title_elem.get_text(strip=True)
                if title and len(title) > 10:  # Avoid short generic titles
                    return title

        return fallback_text or 'CMS Survey Memo'

    def _extract_content(self, soup: BeautifulSoup) -> str:
        """Extract main content from the memo"""
        # Try various content selectors
        content_selectors = [
            '.main-content',
            '.page-content',
            '.article-content',
            '#content',
            '.content',
            'main'
        ]

        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                # Remove script and style elements
                for script in content_elem(["script", "style"]):
                    script.decompose()
                return content_elem.get_text(strip=True)

        # Fallback: get all text from body
        if soup.body:
            return soup.body.get_text(strip=True)

        return ''

    def _extract_date(self, soup: BeautifulSoup, text: str) -> Optional[str]:
        """Extract date from memo content or filename"""
        # Look for dates in various formats
        date_patterns = [
            r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b',  # MM/DD/YYYY or MM-DD-YYYY
            r'\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b',    # YYYY-MM-DD
            r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b'
        ]

        # First try to find date in the page content
        page_text = soup.get_text()

        for pattern in date_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            if matches:
                match = matches[0]
                try:
                    if len(match) == 3 and isinstance(match[0], str) and not match[0].isdigit():
                        # Month name format
                        month_name, day, year = match
                        date_obj = datetime.strptime(f"{month_name} {day} {year}", "%B %d %Y")
                    else:
                        # Numeric format - try different arrangements
                        if len(match[0]) == 4:  # YYYY-MM-DD
                            date_obj = datetime(int(match[0]), int(match[1]), int(match[2]))
                        else:  # MM/DD/YYYY
                            year = int(match[2])
                            if year < 100:  # Handle 2-digit years
                                year += 2000
                            date_obj = datetime(year, int(match[0]), int(match[1]))

                    return date_obj.strftime('%Y-%m-%d')
                except (ValueError, IndexError):
                    continue

        return None

    def _determine_memo_type(self, soup: BeautifulSoup, text: str) -> str:
        """Determine the type of memo based on content"""
        text_lower = text.lower()
        content_lower = soup.get_text().lower()

        if any(term in text_lower or term in content_lower for term in ['enforcement', 'violation', 'immediate jeopardy', 'termination']):
            return 'enforcement'
        elif any(term in text_lower or term in content_lower for term in ['guidance', 'clarification', 'interpretation']):
            return 'guidance'
        elif any(term in text_lower or term in content_lower for term in ['survey', 'inspection', 'certification']):
            return 'survey'
        elif any(term in text_lower or term in content_lower for term in ['update', 'change', 'revision']):
            return 'update'
        else:
            return 'general'

    def _extract_enforcement_topics(self, soup: BeautifulSoup) -> List[str]:
        """Extract enforcement focus areas from memo content"""
        content = soup.get_text().lower()

        # SNF-specific enforcement topics
        enforcement_topics = []

        topic_keywords = {
            'infection_control': ['infection control', 'infection prevention', 'covid', 'outbreak', 'antibiotic resistance'],
            'staffing': ['staffing', 'nurse aide', 'rn', 'registered nurse', 'licensed nurse', '24-hour nursing'],
            'quality_care': ['quality of care', 'pressure ulcer', 'falls', 'medication error', 'resident safety'],
            'resident_rights': ['resident rights', 'dignity', 'privacy', 'abuse', 'neglect', 'mistreatment'],
            'pharmacy': ['pharmacy', 'medication', 'drug regimen', 'unnecessary drugs', 'psychotropic'],
            'dietary': ['dietary', 'nutrition', 'hydration', 'weight loss', 'malnutrition'],
            'activities': ['activities', 'social services', 'mental health', 'behavioral health'],
            'environment': ['environment', 'life safety', 'emergency preparedness', 'generator', 'fire safety'],
            'administration': ['administration', 'governance', 'medical director', 'administrator', 'compliance'],
            'admission_discharge': ['admission', 'discharge', 'transfer', 'readmission', 'bed hold']
        }

        for topic, keywords in topic_keywords.items():
            if any(keyword in content for keyword in keywords):
                enforcement_topics.append(topic)

        return enforcement_topics

    def _is_snf_relevant(self, memo_data: Dict) -> bool:
        """Check if memo is relevant to SNFs"""
        title = memo_data.get('title', '').lower()
        content = memo_data.get('content', '').lower()

        # SNF-specific terms
        snf_terms = [
            'skilled nursing',
            'nursing home',
            'snf',
            'long term care',
            'ltc',
            'nursing facility',
            'skilled nursing facility'
        ]

        # Check if memo mentions SNF-related terms
        relevant = any(term in title or term in content for term in snf_terms)

        # Also consider enforcement topics
        enforcement_topics = memo_data.get('enforcement_topics', [])
        if enforcement_topics:
            relevant = True  # Any enforcement memo is potentially relevant

        return relevant

    def get_current_enforcement_priorities(self) -> List[Dict]:
        """Get current CMS enforcement priority areas"""
        try:
            memos = self.get_survey_memos(days_back=180)  # Look back 6 months

            # Analyze enforcement topics frequency
            topic_frequency = {}
            enforcement_memos = []

            for memo in memos:
                if memo.get('memo_type') == 'enforcement':
                    enforcement_memos.append(memo)

                for topic in memo.get('enforcement_topics', []):
                    topic_frequency[topic] = topic_frequency.get(topic, 0) + 1

            # Sort by frequency to get current priorities
            priorities = []
            for topic, count in sorted(topic_frequency.items(), key=lambda x: x[1], reverse=True):
                priorities.append({
                    'topic': topic,
                    'frequency': count,
                    'priority_level': 'high' if count >= 3 else 'medium' if count >= 2 else 'low',
                    'recent_memos': len([m for m in enforcement_memos if topic in m.get('enforcement_topics', [])])
                })

            return priorities

        except Exception as e:
            logger.error(f"Error getting enforcement priorities: {e}")
            return []

    def calculate_survey_risk(self, bill_title: str, bill_content: str, enforcement_priorities: List[Dict]) -> Dict:
        """Calculate survey risk based on current enforcement priorities"""
        bill_text = f"{bill_title} {bill_content}".lower()

        risk_score = 0
        matched_topics = []

        for priority in enforcement_priorities:
            topic = priority['topic']
            frequency = priority['frequency']

            # Check if bill relates to this enforcement topic
            topic_keywords = {
                'infection_control': ['infection', 'control', 'prevention', 'covid', 'outbreak'],
                'staffing': ['staffing', 'nurse', 'nursing', 'staff', 'workforce'],
                'quality_care': ['quality', 'care', 'safety', 'pressure ulcer', 'falls'],
                'resident_rights': ['rights', 'dignity', 'privacy', 'abuse', 'neglect'],
                'pharmacy': ['pharmacy', 'medication', 'drug', 'pharmaceutical'],
                'dietary': ['dietary', 'nutrition', 'food', 'nutrition'],
                'activities': ['activities', 'social', 'mental health', 'behavioral'],
                'environment': ['environment', 'safety', 'emergency', 'fire'],
                'administration': ['administration', 'governance', 'compliance', 'management'],
                'admission_discharge': ['admission', 'discharge', 'transfer', 'readmission']
            }

            keywords = topic_keywords.get(topic, [topic.replace('_', ' ')])
            if any(keyword in bill_text for keyword in keywords):
                risk_score += frequency * (3 if priority['priority_level'] == 'high' else 2 if priority['priority_level'] == 'medium' else 1)
                matched_topics.append({
                    'topic': topic,
                    'priority_level': priority['priority_level'],
                    'frequency': frequency
                })

        # Determine risk level
        if risk_score >= 10:
            risk_level = 'high'
        elif risk_score >= 5:
            risk_level = 'medium'
        else:
            risk_level = 'low'

        return {
            'risk_level': risk_level,
            'risk_score': risk_score,
            'matched_topics': matched_topics,
            'explanation': f"Survey risk based on {len(matched_topics)} enforcement priority matches"
        }