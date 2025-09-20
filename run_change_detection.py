#!/usr/bin/env python3
"""
Main runner for the SNF Legislation Change Detection System

This script provides different modes of operation:
1. Run scheduler (automated 4-hour checking)
2. Run one-time change detection
3. Send test email
4. Show system status
"""

import os
import sys
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

def run_scheduler():
    """Run the automated scheduler"""
    print("🚀 Starting Change Detection Scheduler...")
    from services.change_detection.scheduler import ChangeDetectionScheduler

    scheduler = ChangeDetectionScheduler()

    try:
        scheduler.start()
        print("✅ Scheduler started successfully")
        print("📋 Active tasks:")

        status = scheduler.get_status()
        for task in status.tasks:
            if task.enabled:
                print(f"   - {task.name}: every {task.interval_hours}h")

        print("\nPress Ctrl+C to stop the scheduler")

        # Keep running
        import time
        while scheduler.running:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n⏹️  Stopping scheduler...")
        scheduler.stop()
        print("✅ Scheduler stopped")
    except Exception as e:
        print(f"❌ Scheduler error: {e}")
        scheduler.stop()

def run_one_time_check():
    """Run change detection once"""
    print("🔍 Running one-time change detection...")

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from services.change_detection.change_detection_service import ChangeDetectionService

    database_url = os.getenv('DATABASE_URL', 'sqlite:///./snflegtracker.db')
    engine = create_engine(database_url)

    with Session(engine) as session:
        service = ChangeDetectionService(session)

        start_time = datetime.now()
        result = service.check_all_bills_for_changes()
        end_time = datetime.now()

        print(f"✅ Change detection completed in {(end_time - start_time).total_seconds():.1f} seconds")
        print(f"📊 Results:")
        print(f"   Bills checked: {result.bills_checked}")
        print(f"   Changes detected: {result.changes_detected}")
        print(f"   Stage transitions: {result.stage_transitions}")
        print(f"   Alerts created: {result.alerts_created}")

        if result.errors:
            print(f"   Errors: {len(result.errors)}")
            for error in result.errors[:3]:
                print(f"     - {error}")

        if result.summary:
            print(f"   Success rate: {result.summary.get('success_rate', 0):.1%}")

def send_test_email():
    """Send a test email"""
    print("📧 Sending test email...")

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from services.change_detection.email_notifier import EmailNotifier
    from models.legislation import User, Bill
    from models.change_detection import ChangeAlert, AlertPriority

    database_url = os.getenv('DATABASE_URL', 'sqlite:///./snflegtracker.db')
    engine = create_engine(database_url)

    with Session(engine) as session:
        # Get or create test user
        test_user = session.query(User).filter(User.email == "test@example.com").first()

        if not test_user:
            print("❌ No test user found. Run test_change_detection.py first to create test data.")
            return

        # Get or create test bill
        test_bill = session.query(Bill).filter(Bill.bill_number.like("TEST-%")).first()

        if not test_bill:
            print("❌ No test bill found. Run test_change_detection.py first to create test data.")
            return

        # Create test alert
        test_alert = ChangeAlert(
            bill_id=test_bill.id,
            user_id=test_user.id,
            alert_type='test',
            priority=AlertPriority.MEDIUM,
            title=f"Test Alert: {test_bill.bill_number}",
            message=f"This is a test alert for bill {test_bill.bill_number}. If you receive this, the email system is working correctly.",
            dedup_hash="test_alert_hash"
        )

        session.add(test_alert)
        session.commit()

        # Send email
        notifier = EmailNotifier(session)
        result = notifier.send_single_alert(test_alert, test_user, test_bill)

        if result.success:
            print(f"✅ Test email sent successfully to {test_user.email}")
            if os.getenv('EMAIL_TEST_MODE', 'true').lower() == 'true':
                print("ℹ️  Email was displayed in test mode (not actually sent)")
        else:
            print(f"❌ Failed to send test email: {result.message}")
            if result.errors:
                for error in result.errors:
                    print(f"   Error: {error}")

def show_status():
    """Show system status"""
    print("📈 System Status")
    print("-" * 40)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from services.change_detection.change_detection_service import ChangeDetectionService

    database_url = os.getenv('DATABASE_URL', 'sqlite:///./snflegtracker.db')
    engine = create_engine(database_url)

    with Session(engine) as session:
        service = ChangeDetectionService(session)

        # Get system stats
        stats = service.get_system_stats(days=7)

        if 'error' in stats:
            print(f"❌ Error getting stats: {stats['error']}")
            return

        print("📊 Last 7 Days:")
        print(f"   Changes detected: {stats['changes']['total']}")
        print(f"   Stage transitions: {stats['stage_transitions']}")
        print(f"   Alerts created: {stats['alerts']['total']}")
        print(f"   Alerts sent: {stats['alerts']['sent']}")

        # Show change breakdown
        if stats['changes']['by_severity']:
            print("\n   Changes by severity:")
            for severity, count in stats['changes']['by_severity'].items():
                if count > 0:
                    print(f"     {severity}: {count}")

        # Show alert breakdown
        if stats['alerts']['by_priority']:
            print("\n   Alerts by priority:")
            for priority, count in stats['alerts']['by_priority'].items():
                if count > 0:
                    print(f"     {priority}: {count}")

        # Show deduplication stats
        if 'deduplication' in stats and 'suppression_rate_percent' in stats['deduplication']:
            print(f"\n   Alert suppression rate: {stats['deduplication']['suppression_rate_percent']}%")

def setup_database():
    """Set up database tables"""
    print("🛠️  Setting up database...")

    from sqlalchemy import create_engine
    from models.database import Base
    # Import all models to ensure they're registered
    from models.legislation import Bill, User, BillVersion, Keyword, BillKeywordMatch, Alert, ImpactAnalysis
    from models.change_detection import (
        BillChange, StageTransition, ChangeAlert, AlertPreferences, ChangeDetectionConfig
    )

    database_url = os.getenv('DATABASE_URL', 'sqlite:///./snflegtracker.db')
    engine = create_engine(database_url)

    try:
        # Create all tables
        Base.metadata.create_all(engine)
        print("✅ Database tables created/updated successfully")

        # List created tables
        from sqlalchemy import inspect
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        print(f"📋 Tables in database: {len(table_names)}")
        change_detection_tables = [name for name in table_names if name in [
            'bill_changes', 'stage_transitions', 'change_alerts', 'alert_preferences'
        ]]
        if change_detection_tables:
            print(f"   Change detection tables: {', '.join(change_detection_tables)}")

    except Exception as e:
        print(f"❌ Database setup failed: {e}")

def main():
    """Main function with argument parsing"""
    parser = argparse.ArgumentParser(
        description="SNF Legislation Change Detection System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s scheduler          # Run automated scheduler (4-hour intervals)
  %(prog)s check             # Run one-time change detection
  %(prog)s test-email        # Send a test email
  %(prog)s status            # Show system status
  %(prog)s setup-db          # Set up database tables
        """
    )

    parser.add_argument('command', choices=[
        'scheduler', 'check', 'test-email', 'status', 'setup-db'
    ], help='Command to run')

    args = parser.parse_args()

    print("🏥 SNF Legislation Change Detection System")
    print("=" * 50)

    if args.command == 'scheduler':
        run_scheduler()
    elif args.command == 'check':
        run_one_time_check()
    elif args.command == 'test-email':
        send_test_email()
    elif args.command == 'status':
        show_status()
    elif args.command == 'setup-db':
        setup_database()

if __name__ == "__main__":
    main()