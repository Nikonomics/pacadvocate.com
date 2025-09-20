from celery import Celery
import os

# Initialize Celery
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
celery_app = Celery('snflegtracker', broker=redis_url, backend=redis_url)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

@celery_app.task
def scrape_bills():
    """
    Celery task to scrape bills from various sources
    """
    from scrapers.federal.congress_scraper import CongressScraper
    from services.legislation.bill_service import BillService
    from models.database import SessionLocal
    from models.legislation import BillCreate

    db = SessionLocal()
    try:
        scraper = CongressScraper()
        bill_service = BillService(db)

        # Scrape federal bills
        bills = scraper.get_recent_bills()

        for bill_data in bills:
            existing_bill = bill_service.get_bill_by_number(bill_data['bill_number'])
            if not existing_bill:
                bill_create = BillCreate(**bill_data)
                bill_service.create_bill(bill_create)

        return f"Scraped {len(bills)} bills"

    except Exception as e:
        return f"Error scraping bills: {str(e)}"
    finally:
        db.close()

@celery_app.task
def analyze_bill_sentiment(bill_id: int):
    """
    Celery task to analyze bill sentiment using AI
    """
    # This would integrate with OpenAI or sentence-transformers
    # for sentiment analysis and categorization
    return f"Analyzed sentiment for bill {bill_id}"