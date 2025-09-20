#!/usr/bin/env python3
"""
LegiScan Scheduled Collection System
Automated monitoring of state legislation for healthcare-related bills
"""

import os
import sys
import time
import logging
import schedule
from datetime import datetime, timedelta
from typing import Dict, Any, List
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from services.collectors.legiscan_collector import LegiScanCollector

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('legiscan_scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class LegiScanScheduler:
    """Scheduled collection system for LegiScan state legislation"""

    def __init__(self, api_key: str = None):
        self.collector = LegiScanCollector(api_key)
        self.running = False
        self.last_daily_run = None
        self.last_weekly_run = None

        # States to monitor (can be configured)
        self.monitored_states = ['ID']  # Start with Idaho, add more as needed

        logger.info("LegiScan Scheduler initialized")

    def daily_collection(self):
        """Daily collection of recent state healthcare bills"""
        logger.info("🔄 Starting daily LegiScan collection...")

        total_collected = 0

        try:
            for state in self.monitored_states:
                logger.info(f"Collecting daily updates for {state}...")

                # Collect recent bills (smaller daily limit)
                bills = self.collector.collect_state_bills(
                    state=state,
                    year=None,  # Current year
                    limit=10,   # Small daily limit
                    include_details=False  # Skip details for daily runs
                )

                total_collected += len(bills)
                logger.info(f"   {state}: {len(bills)} bills collected")

            self.last_daily_run = datetime.utcnow()

            logger.info(f"✅ Daily collection completed: {total_collected} bills processed across {len(self.monitored_states)} states")

        except Exception as e:
            logger.error(f"❌ Daily collection failed: {e}")

    def weekly_comprehensive_collection(self):
        """Weekly comprehensive collection with full details"""
        logger.info("🔄 Starting weekly comprehensive LegiScan collection...")

        total_collected = 0

        try:
            current_year = datetime.now().year

            for state in self.monitored_states:
                logger.info(f"Comprehensive collection for {state}...")

                # Collect with full details
                bills = self.collector.collect_state_bills(
                    state=state,
                    year=current_year,
                    limit=50,   # Larger weekly limit
                    include_details=True  # Include full details for weekly runs
                )

                total_collected += len(bills)

                # Log detailed summary
                if bills:
                    healthcare_count = sum(1 for bill in bills
                                         if any(term in bill.get('title', '').lower()
                                              for term in ['health', 'medic', 'nursing', 'care']))

                    logger.info(f"   {state}: {len(bills)} bills collected, {healthcare_count} healthcare-related")

            self.last_weekly_run = datetime.utcnow()

            logger.info(f"✅ Weekly collection completed: {total_collected} bills processed")

        except Exception as e:
            logger.error(f"❌ Weekly collection failed: {e}")

    def monthly_multi_state_scan(self):
        """Monthly scan of additional states for expansion opportunities"""
        logger.info("🔄 Starting monthly multi-state scan...")

        # States to scan for potential monitoring
        scan_states = ['CA', 'WA', 'OR', 'NV', 'MT', 'UT', 'WY']

        try:
            for state in scan_states:
                if state in self.monitored_states:
                    continue

                logger.info(f"Scanning {state} for healthcare legislation...")

                # Light scan - just search, don't store
                bills = self.collector.client.search_healthcare_bills(
                    state=state,
                    search_terms=['Medicaid', 'nursing facility', 'long-term care'],
                    year=datetime.now().year,
                    limit=5
                )

                if bills:
                    logger.info(f"   {state}: Found {len(bills)} relevant bills - consider enabling collection")
                else:
                    logger.info(f"   {state}: No relevant bills found")

        except Exception as e:
            logger.error(f"❌ Monthly scan failed: {e}")

    def health_check(self):
        """Perform health check of the LegiScan system"""
        logger.info("🏥 Performing LegiScan system health check...")

        try:
            # Test API connection
            if not self.collector.test_connection():
                logger.error("❌ LegiScan API connection failed")
                return False

            # Check recent collection activity
            stats = self.collector.get_collection_stats()
            recent_count = stats.get('recent_bills_30_days', 0)

            if recent_count == 0:
                logger.warning("⚠️  No LegiScan bills collected in last 30 days")

            # Check rate limit status
            rate_status = self.collector.client.get_rate_limit_status()
            requests_today = rate_status.get('requests_in_last_24_hours', 0)
            daily_limit = rate_status.get('daily_limit', 1000)

            if requests_today > daily_limit * 0.9:
                logger.warning(f"⚠️  High API usage: {requests_today}/{daily_limit} requests today")

            logger.info(f"✅ Health check passed - {recent_count} bills collected recently")
            return True

        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return False

    def add_monitored_state(self, state: str):
        """Add a state to the monitoring list"""
        if state.upper() not in self.collector.STATE_CONFIG:
            logger.error(f"Unknown state: {state}")
            return False

        if state.upper() not in self.monitored_states:
            self.monitored_states.append(state.upper())
            logger.info(f"Added {state.upper()} to monitored states")
            return True

        logger.info(f"{state.upper()} already being monitored")
        return True

    def remove_monitored_state(self, state: str):
        """Remove a state from the monitoring list"""
        if state.upper() in self.monitored_states:
            self.monitored_states.remove(state.upper())
            logger.info(f"Removed {state.upper()} from monitored states")
            return True

        logger.info(f"{state.upper()} not in monitored states")
        return False

    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get current scheduler status"""
        return {
            'running': self.running,
            'monitored_states': self.monitored_states,
            'last_daily_run': self.last_daily_run.isoformat() if self.last_daily_run else None,
            'last_weekly_run': self.last_weekly_run.isoformat() if self.last_weekly_run else None,
            'next_daily_run': self._get_next_run_time('daily'),
            'next_weekly_run': self._get_next_run_time('weekly'),
            'system_health': 'healthy' if self.health_check() else 'unhealthy',
            'rate_limit_status': self.collector.client.get_rate_limit_status()
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
        logger.info("🚀 Starting LegiScan collection scheduler...")

        # Schedule jobs based on API rate limits (30,000/month = ~1000/day)
        schedule.every().day.at("08:00").do(self.daily_collection)  # Daily at 8 AM
        schedule.every().monday.at("07:00").do(self.weekly_comprehensive_collection)  # Weekly on Monday at 7 AM
        schedule.every().day.at("14:00").do(self.health_check)  # Daily health check at 2 PM
        schedule.every(30).days.do(self.monthly_multi_state_scan)  # Monthly state scan

        self.running = True

        # Initial health check
        self.health_check()

        logger.info("📅 Scheduler started with the following schedule:")
        logger.info("   • Daily collection: 8:00 AM")
        logger.info("   • Weekly comprehensive: Monday 7:00 AM")
        logger.info("   • Health checks: Daily 2:00 PM")
        logger.info("   • Multi-state scan: Monthly")
        logger.info(f"   • Monitoring states: {', '.join(self.monitored_states)}")

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
        elif task_type == 'monthly':
            self.monthly_multi_state_scan()
        elif task_type == 'health':
            self.health_check()
        else:
            logger.error(f"Unknown task type: {task_type}")

    def stop_scheduler(self):
        """Stop the scheduler"""
        self.running = False
        logger.info("🛑 Scheduler stop requested")

def main():
    """CLI interface for LegiScan scheduler"""
    parser = argparse.ArgumentParser(description='LegiScan Collection Scheduler')
    parser.add_argument('--run', action='store_true', help='Start the continuous scheduler')
    parser.add_argument('--once', choices=['daily', 'weekly', 'monthly', 'health'],
                       help='Run a single collection task')
    parser.add_argument('--status', action='store_true', help='Show scheduler status')
    parser.add_argument('--add-state', type=str, help='Add state to monitoring list')
    parser.add_argument('--remove-state', type=str, help='Remove state from monitoring list')
    parser.add_argument('--api-key', type=str, help='LegiScan API key')
    parser.add_argument('--stop', action='store_true', help='Stop any running scheduler')

    args = parser.parse_args()

    scheduler = LegiScanScheduler(api_key=args.api_key)

    if args.status:
        print("📊 LegiScan Scheduler Status")
        print("=" * 50)
        status = scheduler.get_scheduler_status()
        for key, value in status.items():
            if key == 'rate_limit_status':
                print(f"  Rate Limit:")
                for sub_key, sub_value in value.items():
                    print(f"    {sub_key}: {sub_value}")
            else:
                print(f"  {key}: {value}")
        return

    if args.add_state:
        scheduler.add_monitored_state(args.add_state)
        return

    if args.remove_state:
        scheduler.remove_monitored_state(args.remove_state)
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