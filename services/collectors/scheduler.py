"""
Bill Collection Scheduler
Manages scheduled tasks for automated bill collection from Congress.gov
"""

import os
import sys
import schedule
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from services.collectors.bill_collector import BillCollector

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bill_collection.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BillCollectionScheduler:
    """Manages scheduled bill collection tasks"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('CONGRESS_API_KEY')
        self.is_running = False
        self.last_collection_time = None
        self.collection_stats = {}

    def daily_collection_task(self):
        """Daily task: Collect recent bills and high-priority SNF bills"""
        logger.info("Starting daily collection task")

        try:
            with BillCollector(self.api_key) as collector:
                # Test API connection first
                if not collector.api_client.test_connection():
                    logger.error("API connection failed, skipping collection")
                    return

                # Collect recent bills (last 7 days)
                logger.info("Collecting recent bills...")
                recent_results = collector.collect_recent_bills(days=7)

                # Collect SNF-specific bills
                logger.info("Collecting SNF-specific bills...")
                snf_results = collector.collect_snf_bills(year=datetime.now().year)

                # Update stats
                self.collection_stats = {
                    'last_run': datetime.now().isoformat(),
                    'recent_bills': recent_results,
                    'snf_bills': snf_results,
                    'status': 'success'
                }

                logger.info(f"Daily collection completed: {self.collection_stats}")
                self.last_collection_time = datetime.now()

        except Exception as e:
            error_msg = f"Daily collection task failed: {e}"
            logger.error(error_msg)
            self.collection_stats = {
                'last_run': datetime.now().isoformat(),
                'status': 'error',
                'error': error_msg
            }

    def weekly_comprehensive_collection(self):
        """Weekly task: Comprehensive collection of all relevant bills"""
        logger.info("Starting weekly comprehensive collection")

        try:
            with BillCollector(self.api_key) as collector:
                if not collector.api_client.test_connection():
                    logger.error("API connection failed, skipping weekly collection")
                    return

                # Comprehensive keyword-based collection
                results = collector.collect_bills_by_keywords(
                    congress=119,
                    year=datetime.now().year,
                    limit_per_keyword=100  # More comprehensive search
                )

                # Get collection statistics
                stats = collector.get_collection_stats()

                logger.info(f"Weekly collection completed: {results}")
                logger.info(f"Database stats: {stats}")

                # Store results
                self.collection_stats.update({
                    'last_weekly_run': datetime.now().isoformat(),
                    'weekly_results': results,
                    'database_stats': stats
                })

        except Exception as e:
            error_msg = f"Weekly collection task failed: {e}"
            logger.error(error_msg)
            self.collection_stats.update({
                'last_weekly_run': datetime.now().isoformat(),
                'weekly_status': 'error',
                'weekly_error': error_msg
            })

    def setup_schedule(self):
        """Set up the collection schedule"""
        logger.info("Setting up collection schedule")

        # Daily collection at 6:00 AM
        schedule.every().day.at("06:00").do(self.daily_collection_task)

        # Weekly comprehensive collection on Sundays at 2:00 AM
        schedule.every().sunday.at("02:00").do(self.weekly_comprehensive_collection)

        # Optional: Hourly light collection during business hours (9 AM - 5 PM EST)
        for hour in range(9, 18):  # 9 AM to 5 PM
            schedule.every().day.at(f"{hour:02d}:00").do(self.light_collection_task)

        logger.info("Schedule configured:")
        logger.info("  • Daily collection: 6:00 AM")
        logger.info("  • Weekly comprehensive: Sunday 2:00 AM")
        logger.info("  • Light collection: Every hour 9 AM - 5 PM")

    def light_collection_task(self):
        """Light collection task for business hours"""
        logger.info("Starting light collection task")

        try:
            with BillCollector(self.api_key) as collector:
                # Only collect if there have been no collections in the last 2 hours
                if (self.last_collection_time and
                    datetime.now() - self.last_collection_time < timedelta(hours=2)):
                    logger.info("Recent collection found, skipping light collection")
                    return

                # Quick SNF-focused collection
                results = collector.collect_snf_bills(year=datetime.now().year)

                if results['bills_stored'] > 0 or results['bills_updated'] > 0:
                    logger.info(f"Light collection found updates: {results}")
                else:
                    logger.debug("Light collection: no new bills found")

                self.last_collection_time = datetime.now()

        except Exception as e:
            logger.error(f"Light collection task failed: {e}")

    def run_scheduler(self):
        """Run the scheduler continuously"""
        if not self.api_key:
            logger.error("No Congress.gov API key found. Set CONGRESS_API_KEY environment variable.")
            return

        logger.info("Starting Bill Collection Scheduler")
        logger.info("Press Ctrl+C to stop")

        self.is_running = True
        self.setup_schedule()

        try:
            while self.is_running:
                schedule.run_pending()
                time.sleep(60)  # Check every minute

        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
            self.is_running = False

        except Exception as e:
            logger.error(f"Scheduler error: {e}")
            self.is_running = False

    def run_once(self, task_type: str = 'daily'):
        """Run a single collection task"""
        logger.info(f"Running single {task_type} collection task")

        if task_type == 'daily':
            self.daily_collection_task()
        elif task_type == 'weekly':
            self.weekly_comprehensive_collection()
        elif task_type == 'light':
            self.light_collection_task()
        else:
            logger.error(f"Unknown task type: {task_type}")

    def get_status(self) -> Dict[str, Any]:
        """Get current scheduler status"""
        next_runs = []
        for job in schedule.jobs:
            next_runs.append({
                'job': str(job.job_func),
                'next_run': job.next_run.isoformat() if job.next_run else None
            })

        return {
            'is_running': self.is_running,
            'last_collection_time': self.last_collection_time.isoformat() if self.last_collection_time else None,
            'collection_stats': self.collection_stats,
            'scheduled_jobs': next_runs,
            'api_key_configured': bool(self.api_key)
        }

def main():
    """CLI interface for the scheduler"""
    import argparse

    parser = argparse.ArgumentParser(description='SNFLegTracker Bill Collection Scheduler')
    parser.add_argument('--run', action='store_true', help='Start the scheduler')
    parser.add_argument('--once', choices=['daily', 'weekly', 'light'],
                       help='Run a single collection task')
    parser.add_argument('--status', action='store_true', help='Show scheduler status')
    parser.add_argument('--api-key', help='Congress.gov API key')

    args = parser.parse_args()

    # Set API key if provided
    if args.api_key:
        os.environ['CONGRESS_API_KEY'] = args.api_key

    scheduler = BillCollectionScheduler()

    if args.run:
        scheduler.run_scheduler()
    elif args.once:
        scheduler.run_once(args.once)
    elif args.status:
        status = scheduler.get_status()
        print("📊 Scheduler Status:")
        print(json.dumps(status, indent=2, default=str))
    else:
        print("📋 SNFLegTracker Bill Collection Scheduler")
        print("Usage:")
        print("  --run          Start continuous scheduler")
        print("  --once daily   Run single daily collection")
        print("  --once weekly  Run single weekly collection")
        print("  --status       Show current status")
        print("  --api-key KEY  Set API key")

if __name__ == "__main__":
    main()