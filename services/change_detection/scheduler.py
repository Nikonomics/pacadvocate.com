import schedule
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv
import signal
import sys

load_dotenv()
logger = logging.getLogger(__name__)

@dataclass
class ScheduledTask:
    """Represents a scheduled task"""
    name: str
    function: Callable
    interval_hours: int
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    enabled: bool = True
    error_count: int = 0
    max_errors: int = 3

@dataclass
class SchedulerStatus:
    """Status of the scheduler"""
    is_running: bool
    start_time: Optional[datetime]
    tasks: List[ScheduledTask]
    total_runs: int
    total_errors: int
    last_check: Optional[datetime]

class ChangeDetectionScheduler:
    """Automated scheduler for change detection tasks"""

    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL', 'sqlite:///./snflegtracker.db')
        self.engine = create_engine(self.database_url)

        self.running = False
        self.start_time = None
        self.total_runs = 0
        self.total_errors = 0
        self.last_check = None

        # Scheduled tasks
        self.tasks = []
        self._setup_scheduled_tasks()

        # Thread for running scheduler
        self.scheduler_thread = None
        self.stop_event = threading.Event()

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info("Change Detection Scheduler initialized")

    def _setup_scheduled_tasks(self):
        """Setup all scheduled tasks"""

        # Main change detection task (every 4 hours)
        self.tasks.append(ScheduledTask(
            name="bill_change_detection",
            function=self._run_change_detection,
            interval_hours=4
        ))

        # Alert processing task (every hour)
        self.tasks.append(ScheduledTask(
            name="alert_processing",
            function=self._process_pending_alerts,
            interval_hours=1
        ))

        # Daily digest task (once daily at 8 AM)
        self.tasks.append(ScheduledTask(
            name="daily_digest",
            function=self._send_daily_digests,
            interval_hours=24
        ))

        # Weekly summary (once weekly on Sunday at 9 AM)
        self.tasks.append(ScheduledTask(
            name="weekly_summary",
            function=self._send_weekly_summaries,
            interval_hours=168  # 7 days * 24 hours
        ))

        # Cleanup task (once daily)
        self.tasks.append(ScheduledTask(
            name="cleanup",
            function=self._cleanup_old_data,
            interval_hours=24
        ))

        # Health check (every 30 minutes)
        self.tasks.append(ScheduledTask(
            name="health_check",
            function=self._health_check,
            interval_hours=0.5
        ))

    def start(self):
        """Start the scheduler"""
        if self.running:
            logger.warning("Scheduler already running")
            return

        self.running = True
        self.start_time = datetime.utcnow()
        self.stop_event.clear()

        logger.info("Starting Change Detection Scheduler...")

        # Schedule tasks
        for task in self.tasks:
            if task.enabled:
                schedule.every(task.interval_hours).hours.do(self._run_task, task)
                task.next_run = datetime.utcnow() + timedelta(hours=task.interval_hours)

        # Start scheduler in separate thread
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()

        logger.info(f"Scheduler started with {len([t for t in self.tasks if t.enabled])} active tasks")

    def stop(self):
        """Stop the scheduler"""
        if not self.running:
            return

        logger.info("Stopping Change Detection Scheduler...")

        self.running = False
        self.stop_event.set()

        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=10)

        schedule.clear()
        logger.info("Scheduler stopped")

    def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.running and not self.stop_event.is_set():
            try:
                self.last_check = datetime.utcnow()
                schedule.run_pending()
                time.sleep(60)  # Check every minute

            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                self.total_errors += 1
                time.sleep(60)

    def _run_task(self, task: ScheduledTask):
        """Run a scheduled task with error handling"""
        if not task.enabled:
            return

        logger.info(f"Running scheduled task: {task.name}")

        try:
            task.last_run = datetime.utcnow()
            task.function()
            task.error_count = 0  # Reset error count on success
            self.total_runs += 1

            logger.info(f"Task {task.name} completed successfully")

        except Exception as e:
            logger.error(f"Error in task {task.name}: {e}")
            task.error_count += 1
            self.total_errors += 1

            # Disable task if too many errors
            if task.error_count >= task.max_errors:
                task.enabled = False
                logger.error(f"Task {task.name} disabled due to repeated errors")

        # Update next run time
        task.next_run = datetime.utcnow() + timedelta(hours=task.interval_hours)

    def _run_change_detection(self):
        """Main change detection task"""
        from services.change_detection.change_detection_service import ChangeDetectionService

        with Session(self.engine) as session:
            service = ChangeDetectionService(session)
            result = service.check_all_bills_for_changes()

            logger.info(f"Change detection completed: {result.get('bills_checked', 0)} bills checked, "
                       f"{result.get('changes_detected', 0)} changes detected")

    def _process_pending_alerts(self):
        """Process pending alerts for sending"""
        from services.change_detection.email_notifier import EmailNotifier
        from models.change_detection import ChangeAlert
        from models.legislation import User, Bill

        with Session(self.engine) as session:
            # Get pending alerts
            pending_alerts = session.query(ChangeAlert).filter(
                ChangeAlert.is_sent == False,
                ChangeAlert.is_dismissed == False
            ).limit(100).all()  # Process in batches

            if not pending_alerts:
                logger.info("No pending alerts to process")
                return

            logger.info(f"Processing {len(pending_alerts)} pending alerts")

            notifier = EmailNotifier(session)
            processed_count = 0
            error_count = 0

            for alert in pending_alerts:
                try:
                    # Get user and bill
                    user = session.query(User).filter(User.id == alert.user_id).first()
                    bill = session.query(Bill).filter(Bill.id == alert.bill_id).first()

                    if not user or not bill:
                        logger.warning(f"Alert {alert.id}: Missing user or bill")
                        continue

                    # Send notification
                    result = notifier.send_single_alert(alert, user, bill)
                    if result.success:
                        processed_count += 1
                    else:
                        error_count += 1
                        logger.warning(f"Failed to send alert {alert.id}: {result.message}")

                except Exception as e:
                    logger.error(f"Error processing alert {alert.id}: {e}")
                    error_count += 1

            logger.info(f"Alert processing completed: {processed_count} sent, {error_count} errors")

    def _send_daily_digests(self):
        """Send daily digest emails"""
        from services.change_detection.email_notifier import EmailNotifier
        from models.change_detection import ChangeAlert, AlertPreferences
        from models.legislation import User, Bill

        with Session(self.engine) as session:
            # Get users who want daily digests
            users_for_digest = session.query(User).join(AlertPreferences).filter(
                AlertPreferences.email_enabled == True,
                AlertPreferences.email_frequency == 'daily'
            ).all()

            if not users_for_digest:
                logger.info("No users configured for daily digests")
                return

            logger.info(f"Sending daily digests to {len(users_for_digest)} users")

            notifier = EmailNotifier(session)
            cutoff_time = datetime.utcnow() - timedelta(hours=24)

            sent_count = 0
            error_count = 0

            for user in users_for_digest:
                try:
                    # Get user's alerts from last 24 hours
                    user_alerts = session.query(ChangeAlert, Bill).join(Bill).filter(
                        ChangeAlert.user_id == user.id,
                        ChangeAlert.created_at >= cutoff_time,
                        ChangeAlert.is_dismissed == False
                    ).all()

                    if user_alerts:
                        result = notifier.send_digest_email(user, user_alerts, 1)
                        if result.success:
                            sent_count += 1
                        else:
                            error_count += 1
                            logger.warning(f"Failed to send digest to {user.email}: {result.message}")

                except Exception as e:
                    logger.error(f"Error sending digest to user {user.id}: {e}")
                    error_count += 1

            logger.info(f"Daily digest completed: {sent_count} sent, {error_count} errors")

    def _send_weekly_summaries(self):
        """Send weekly summary emails"""
        from services.change_detection.email_notifier import EmailNotifier
        from models.change_detection import AlertPreferences
        from models.legislation import User, Bill

        with Session(self.engine) as session:
            # Get all active users (weekly summary is opt-out)
            users = session.query(User).filter(User.is_active == True).all()

            if not users:
                logger.info("No active users for weekly summaries")
                return

            logger.info(f"Sending weekly summaries to {len(users)} users")

            notifier = EmailNotifier(session)
            cutoff_time = datetime.utcnow() - timedelta(days=7)

            # Generate summary data
            summary_data = self._generate_weekly_summary_data(session, cutoff_time)

            sent_count = 0
            error_count = 0

            for user in users:
                try:
                    # Check if user has opted out of weekly summaries
                    preferences = session.query(AlertPreferences).filter(
                        AlertPreferences.user_id == user.id
                    ).first()

                    if preferences and not preferences.email_enabled:
                        continue

                    result = notifier.send_weekly_summary(user, summary_data)
                    if result.success:
                        sent_count += 1
                    else:
                        error_count += 1
                        logger.warning(f"Failed to send weekly summary to {user.email}: {result.message}")

                except Exception as e:
                    logger.error(f"Error sending weekly summary to user {user.id}: {e}")
                    error_count += 1

            logger.info(f"Weekly summary completed: {sent_count} sent, {error_count} errors")

    def _generate_weekly_summary_data(self, session: Session, cutoff_time: datetime) -> Dict:
        """Generate data for weekly summary"""
        from models.change_detection import BillChange, StageTransition
        from models.legislation import Bill

        # Count new bills
        new_bills = session.query(Bill).filter(
            Bill.created_at >= cutoff_time
        ).count()

        # Count status changes
        status_changes = session.query(StageTransition).filter(
            StageTransition.transition_date >= cutoff_time
        ).count()

        # Get high relevance updates
        high_relevance_updates = session.query(BillChange).join(Bill).filter(
            BillChange.detected_at >= cutoff_time,
            Bill.relevance_score >= 70
        ).count()

        # Get top bills by activity
        top_bills = session.query(Bill).join(BillChange).filter(
            BillChange.detected_at >= cutoff_time
        ).order_by(Bill.relevance_score.desc()).limit(5).all()

        return {
            'new_bills': new_bills,
            'status_changes': status_changes,
            'high_relevance_updates': high_relevance_updates,
            'top_bills': top_bills,
            'period_start': cutoff_time,
            'period_end': datetime.utcnow()
        }

    def _cleanup_old_data(self):
        """Clean up old data to prevent database bloat"""
        from models.change_detection import ChangeAlert, BillChange

        with Session(self.engine) as session:
            cutoff_date = datetime.utcnow() - timedelta(days=90)  # Keep 90 days

            # Clean up old dismissed alerts
            deleted_alerts = session.query(ChangeAlert).filter(
                ChangeAlert.is_dismissed == True,
                ChangeAlert.created_at < cutoff_date
            ).delete()

            # Clean up old minor changes
            deleted_changes = session.query(BillChange).filter(
                BillChange.change_severity == 'minor',
                BillChange.detected_at < cutoff_date
            ).delete()

            session.commit()

            logger.info(f"Cleanup completed: {deleted_alerts} alerts, {deleted_changes} changes removed")

    def _health_check(self):
        """Perform health check of the system"""
        try:
            with Session(self.engine) as session:
                # Test database connection
                session.execute("SELECT 1").fetchone()

                # Check for stuck tasks
                stuck_tasks = [task for task in self.tasks
                              if task.enabled and task.last_run and
                              (datetime.utcnow() - task.last_run).total_seconds() >
                              task.interval_hours * 3600 * 2]  # 2x interval

                if stuck_tasks:
                    logger.warning(f"Detected {len(stuck_tasks)} potentially stuck tasks")

                # Log system status
                active_tasks = len([t for t in self.tasks if t.enabled])
                logger.info(f"Health check: {active_tasks} active tasks, "
                           f"{self.total_runs} total runs, {self.total_errors} errors")

        except Exception as e:
            logger.error(f"Health check failed: {e}")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)

    def get_status(self) -> SchedulerStatus:
        """Get current scheduler status"""
        return SchedulerStatus(
            is_running=self.running,
            start_time=self.start_time,
            tasks=self.tasks.copy(),
            total_runs=self.total_runs,
            total_errors=self.total_errors,
            last_check=self.last_check
        )

    def enable_task(self, task_name: str) -> bool:
        """Enable a specific task"""
        for task in self.tasks:
            if task.name == task_name:
                task.enabled = True
                task.error_count = 0
                logger.info(f"Task {task_name} enabled")
                return True
        return False

    def disable_task(self, task_name: str) -> bool:
        """Disable a specific task"""
        for task in self.tasks:
            if task.name == task_name:
                task.enabled = False
                logger.info(f"Task {task_name} disabled")
                return True
        return False

    def run_task_now(self, task_name: str) -> bool:
        """Run a specific task immediately"""
        for task in self.tasks:
            if task.name == task_name and task.enabled:
                logger.info(f"Running task {task_name} immediately")
                self._run_task(task)
                return True
        return False

def main():
    """Main function to run the scheduler standalone"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    scheduler = ChangeDetectionScheduler()

    try:
        scheduler.start()
        logger.info("Scheduler started successfully. Press Ctrl+C to stop.")

        # Keep main thread alive
        while scheduler.running:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Scheduler error: {e}")
    finally:
        scheduler.stop()

if __name__ == "__main__":
    main()