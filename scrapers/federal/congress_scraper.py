import requests
from bs4 import BeautifulSoup
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class CongressScraper:
    def __init__(self):
        self.base_url = "https://www.congress.gov"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'SNFLegTracker/1.0 (Legislative Tracking Platform)'
        })

    def get_recent_bills(self, congress: str = "118", chamber: str = "house") -> List[Dict]:
        """
        Scrape recent bills from Congress.gov
        """
        try:
            url = f"{self.base_url}/search?q={{%22source%22:[%22legislation%22],%22congress%22:[%22{congress}%22],%22chamber%22:[%22{chamber}%22]}}"
            response = self.session.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            bills = []

            # Parse bill listings (this is a simplified example)
            bill_items = soup.find_all('li', class_='expanded')

            for item in bill_items[:10]:  # Limit to 10 for demo
                bill_data = self._parse_bill_item(item)
                if bill_data:
                    bills.append(bill_data)

            return bills

        except Exception as e:
            logger.error(f"Error scraping Congress.gov: {e}")
            return []

    def _parse_bill_item(self, item) -> Dict:
        """
        Parse individual bill item from search results
        """
        try:
            # This is a simplified parser - actual implementation would be more robust
            title_elem = item.find('span', class_='result-heading')
            title = title_elem.get_text(strip=True) if title_elem else "Unknown"

            # Extract bill number from title
            bill_number = "Unknown"
            if title_elem and title_elem.find('a'):
                bill_number = title_elem.find('a').get_text(strip=True)

            return {
                'bill_number': bill_number,
                'title': title,
                'chamber': 'house',  # This would be parsed from the data
                'status': 'introduced',  # This would be parsed from the data
                'source': 'congress.gov'
            }

        except Exception as e:
            logger.error(f"Error parsing bill item: {e}")
            return None