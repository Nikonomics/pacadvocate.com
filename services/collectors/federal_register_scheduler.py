#!/usr/bin/env python3
"""
Federal Register Scheduled Collection System
Automated monitoring of CMS rules and regulations for SNF-related content
"""

import os
import sys
import time
import logging
import schedule
from datetime import datetime, timedelta
from typing import Dict, Any
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from services.collectors.federal_register_collector import FederalRegisterCollector

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('federal_register_scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class FederalRegisterScheduler:
    """Scheduled collection system for Federal Register documents"""

    def __init__(self):
        self.collector = FederalRegisterCollector()
        self.running = False
        self.last_daily_run = None
        self.last_weekly_run = None

        logger.info("Federal Register Scheduler initialized")

    def daily_collection(self):
        """Daily collection of recent CMS documents"""
        logger.info("🔄 Starting daily Federal Register collection...")

        try:
            # Collect recent SNF-relevant documents
            documents = self.collector.collect_cms_documents(
                year=None,  # Recent documents
                limit=25,   # Smaller daily limit
                snf_only=True
            )

            self.last_daily_run = datetime.utcnow()

            logger.info(f"✅ Daily collection completed: {len(documents)} documents processed")

            # Log summary
            if documents:
                relevant_count = sum(1 for doc in documents if doc.get('snf_relevance', {}).get('is_relevant'))
                logger.info(f"   📊 SNF-relevant documents: {relevant_count}")

        except Exception as e:
            logger.error(f"❌ Daily collection failed: {e}")

    def weekly_comprehensive_collection(self):
        """Weekly comprehensive collection of CMS documents"""
        logger.info("🔄 Starting weekly comprehensive Federal Register collection...")

        try:
            current_year = datetime.now().year

            # Collect comprehensive set of CMS documents
            documents = self.collector.collect_cms_documents(
                year=current_year,
                limit=100,  # Larger weekly limit
                snf_only=False  # Include all CMS documents, then filter
            )

            self.last_weekly_run = datetime.utcnow()

            logger.info(f"✅ Weekly collection completed: {len(documents)} documents processed")

            # Log detailed summary
            if documents:
                relevant_count = sum(1 for doc in documents if doc.get('snf_relevance', {}).get('is_relevant'))
                rule_count = sum(1 for doc in documents if doc.get('type') == 'RULE')
                proposed_count = sum(1 for doc in documents if doc.get('type') == 'PRORULE')

                logger.info(f"   📊 Summary:")
                logger.info(f"      • SNF-relevant: {relevant_count}")
                logger.info(f"      • Final rules: {rule_count}")
                logger.info(f"      • Proposed rules: {proposed_count}")

        except Exception as e:
            logger.error(f"❌ Weekly collection failed: {e}")

    def light_update(self):
        """Light update during business hours"""
        logger.info("🔄 Starting light Federal Register update...")

        try:
            # Very targeted collection - only highly relevant documents
            documents = self.collector.collect_cms_documents(
                year=None,
                limit=10,  # Small limit for frequent checks
                snf_only=True
            )

            if documents:
                logger.info(f"✅ Light update completed: {len(documents)} new documents")
            else:
                logger.debug("Light update: no new documents found")

        except Exception as e:
            logger.error(f"❌ Light update failed: {e}")

    def health_check(self):
        """Perform health check of the Federal Register system"""
        logger.info("🏥 Performing Federal Register system health check...")

        try:
            # Test API connection
            if not self.collector.test_connection():
                logger.error("❌ Federal Register API connection failed")
                return False

            # Check recent collection activity
            stats = self.collector.get_collection_stats()
            recent_count = stats.get('recent_documents_30_days', 0)

            if recent_count == 0:
                logger.warning("⚠️  No Federal Register documents collected in last 30 days")

            logger.info(f"✅ Health check passed - {recent_count} documents collected recently")
            return True

        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return False

    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get current scheduler status"""
        return {
            'running': self.running,
            'last_daily_run': self.last_daily_run.isoformat() if self.last_daily_run else None,
            'last_weekly_run': self.last_weekly_run.isoformat() if self.last_weekly_run else None,
            'next_daily_run': self._get_next_run_time('daily'),
            'next_weekly_run': self._get_next_run_time('weekly'),
            'system_health': 'healthy' if self.health_check() else 'unhealthy'
        }

    def _get_next_run_time(self, job_type: str) -> str:
        """Get next scheduled run time for a job type"""
        try:
            for job in schedule.jobs:
                if job_type in str(job.job_func):
                    return job.next_run.isoformat() if job.next_run else 'Not scheduled'
        except:
            pass
        return 'Unknown'

    def run_scheduler(self):
        """Run the scheduler with all configured jobs"""
        logger.info("🚀 Starting Federal Register collection scheduler...")

        # Schedule jobs
        schedule.every().day.at("09:00").do(self.daily_collection)  # Daily at 9 AM
        schedule.every().monday.at("06:00").do(self.weekly_comprehensive_collection)  # Weekly on Monday at 6 AM
        schedule.every(4).hours.do(self.light_update)  # Every 4 hours during active periods
        schedule.every().day.at("12:00").do(self.health_check)  # Daily health check at noon

        self.running = True

        # Initial health check
        self.health_check()

        logger.info("📅 Scheduler started with the following schedule:")
        logger.info("   • Daily collection: 9:00 AM")
        logger.info("   • Weekly comprehensive: Monday 6:00 AM")
        logger.info("   • Light updates: Every 4 hours")
        logger.info("   • Health checks: Daily 12:00 PM")

        try:
            while self.running:
                schedule.run_pending()
                time.sleep(60)  # Check every minute

        except KeyboardInterrupt:
            logger.info("🛑 Scheduler stopped by user")
            self.running = False

        except Exception as e:
            logger.error(f"❌ Scheduler error: {e}")
            self.running = False

    def run_once(self, task_type: str):
        """Run a single scheduled task"""
        logger.info(f"🔄 Running one-time {task_type} collection...")

        if task_type == 'daily':
            self.daily_collection()
        elif task_type == 'weekly':
            self.weekly_comprehensive_collection()
        elif task_type == 'light':
            self.light_update()
        elif task_type == 'health':
            self.health_check()
        else:
            logger.error(f"Unknown task type: {task_type}")

    def stop_scheduler(self):
        """Stop the scheduler"""
        self.running = False
        logger.info("🛑 Scheduler stop requested")

def main():
    """CLI interface for Federal Register scheduler"""
    parser = argparse.ArgumentParser(description='Federal Register Collection Scheduler')
    parser.add_argument('--run', action='store_true', help='Start the continuous scheduler')
    parser.add_argument('--once', choices=['daily', 'weekly', 'light', 'health'],
                       help='Run a single collection task')
    parser.add_argument('--status', action='store_true', help='Show scheduler status')
    parser.add_argument('--stop', action='store_true', help='Stop any running scheduler')

    args = parser.parse_args()

    scheduler = FederalRegisterScheduler()

    if args.status:
        print("📊 Federal Register Scheduler Status")
        print("=" * 50)
        status = scheduler.get_scheduler_status()
        for key, value in status.items():
            print(f"  {key}: {value}")
        return

    if args.once:
        scheduler.run_once(args.once)
        return

    if args.stop:
        scheduler.stop_scheduler()
        return

    if args.run:
        scheduler.run_scheduler()
        return

    # Default: show help
    parser.print_help()

if __name__ == "__main__":
    main()