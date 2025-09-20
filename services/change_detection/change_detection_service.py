import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
import hashlib
import json

# Import our components
from services.change_detection.diff_engine import DiffEngine, BillSnapshot
from services.change_detection.significance_classifier import SignificanceClassifier
from services.change_detection.stage_detector import StageDetector
from services.change_detection.alert_deduplication import AlertDeduplicationEngine
from services.change_detection.alert_prioritizer import AlertPrioritizer
from services.change_detection.email_notifier import EmailNotifier

# Import models
from models.legislation import Bill, User
from models.change_detection import (
    BillChange, StageTransition, ChangeAlert, AlertPreferences,
    ChangeType, ChangeSeverity, AlertPriority, BillStage
)

logger = logging.getLogger(__name__)

@dataclass
class ChangeDetectionResult:
    """Result of change detection operation"""
    bills_checked: int
    changes_detected: int
    stage_transitions: int
    alerts_created: int
    alerts_sent: int
    errors: List[str]
    processing_time: float
    summary: Dict[str, Any]

@dataclass
class BillCheckResult:
    """Result of checking a single bill"""
    bill_id: int
    has_changes: bool
    has_stage_transition: bool
    change_count: int
    alerts_created: int
    error: Optional[str] = None

class ChangeDetectionService:
    """Main service for detecting and processing bill changes"""

    def __init__(self, session: Session):
        self.session = session

        # Initialize components
        self.diff_engine = DiffEngine()
        self.classifier = SignificanceClassifier()
        self.stage_detector = StageDetector()
        self.deduplication_engine = AlertDeduplicationEngine(session)
        self.prioritizer = AlertPrioritizer()
        self.email_notifier = EmailNotifier(session)

        # Cache for bill snapshots
        self.snapshot_cache = {}

        logger.info("Change Detection Service initialized")

    def check_all_bills_for_changes(self, limit: Optional[int] = None) -> ChangeDetectionResult:
        """Check all bills for changes and generate alerts"""

        start_time = datetime.utcnow()
        results = ChangeDetectionResult(
            bills_checked=0,
            changes_detected=0,
            stage_transitions=0,
            alerts_created=0,
            alerts_sent=0,
            errors=[],
            processing_time=0.0,
            summary={}
        )

        try:
            # Get bills to check (prioritize recently updated and high relevance)
            bills_query = self.session.query(Bill).filter(Bill.is_active == True).order_by(
                Bill.relevance_score.desc().nullslast(),
                Bill.updated_at.desc()
            )

            if limit:
                bills_query = bills_query.limit(limit)

            bills = bills_query.all()

            logger.info(f"Checking {len(bills)} bills for changes")

            bill_results = []
            for bill in bills:
                try:
                    result = self.check_bill_for_changes(bill)
                    bill_results.append(result)

                    results.bills_checked += 1
                    if result.has_changes:
                        results.changes_detected += result.change_count
                    if result.has_stage_transition:
                        results.stage_transitions += 1
                    results.alerts_created += result.alerts_created

                except Exception as e:
                    error_msg = f"Error checking bill {bill.id}: {str(e)}"
                    results.errors.append(error_msg)
                    logger.error(error_msg)

            # Generate summary
            results.summary = self._generate_change_summary(bill_results)

            # Calculate processing time
            end_time = datetime.utcnow()
            results.processing_time = (end_time - start_time).total_seconds()

            logger.info(f"Change detection completed: {results.bills_checked} bills checked, "
                       f"{results.changes_detected} changes detected, "
                       f"{results.stage_transitions} stage transitions")

            return results

        except Exception as e:
            error_msg = f"Error in change detection: {str(e)}"
            results.errors.append(error_msg)
            logger.error(error_msg)
            return results

    def check_bill_for_changes(self, bill: Bill) -> BillCheckResult:
        """Check a specific bill for changes"""

        try:
            # Create current snapshot
            current_snapshot = self.diff_engine.create_snapshot(
                bill.id, bill.title or '', bill.summary or '',
                bill.full_text or '', bill.status or '',
                bill.sponsor or '', bill.committee or ''
            )

            # Get previous snapshot
            previous_snapshot = self._get_previous_snapshot(bill.id)

            result = BillCheckResult(
                bill_id=bill.id,
                has_changes=False,
                has_stage_transition=False,
                change_count=0,
                alerts_created=0
            )

            if not previous_snapshot:
                # First time seeing this bill - store snapshot but don't alert
                self._store_snapshot(bill.id, current_snapshot)
                logger.info(f"Initial snapshot stored for bill {bill.id}")
                return result

            # Compare snapshots
            diff_result = self.diff_engine.compare_snapshots(previous_snapshot, current_snapshot)

            if diff_result.has_changes:
                result.has_changes = True

                # Process text/content changes
                text_changes = self._process_text_changes(bill, diff_result, previous_snapshot, current_snapshot)
                result.change_count += len(text_changes)

                # Create alerts for changes
                for change in text_changes:
                    alerts_created = self._create_alerts_for_change(bill, change, diff_result)
                    result.alerts_created += alerts_created

            # Check for stage transitions
            old_status = previous_snapshot.status
            new_status = current_snapshot.status

            if old_status != new_status:
                stage_transition = self._process_stage_transition(bill, old_status, new_status)
                if stage_transition:
                    result.has_stage_transition = True
                    alerts_created = self._create_alerts_for_stage_transition(bill, stage_transition)
                    result.alerts_created += alerts_created

            # Update snapshot
            self._store_snapshot(bill.id, current_snapshot)

            return result

        except Exception as e:
            return BillCheckResult(
                bill_id=bill.id,
                has_changes=False,
                has_stage_transition=False,
                change_count=0,
                alerts_created=0,
                error=str(e)
            )

    def _process_text_changes(self, bill: Bill, diff_result, previous_snapshot: BillSnapshot,
                            current_snapshot: BillSnapshot) -> List[BillChange]:
        """Process and store text changes"""

        changes = []

        try:
            # Classify the change
            bill_context = {
                'bill_number': bill.bill_number,
                'title': bill.title,
                'summary': bill.summary,
                'source': bill.source,
                'relevance_score': bill.relevance_score
            }

            classification = self.classifier.classify_change(diff_result, bill_context)

            # Create BillChange record
            bill_change = BillChange(
                bill_id=bill.id,
                change_type=ChangeType.TEXT_AMENDMENT,
                change_severity=classification.severity,
                old_value=json.dumps({
                    'title': previous_snapshot.title,
                    'summary': previous_snapshot.summary,
                    'full_text': previous_snapshot.full_text[:1000] + '...' if len(previous_snapshot.full_text) > 1000 else previous_snapshot.full_text
                }),
                new_value=json.dumps({
                    'title': current_snapshot.title,
                    'summary': current_snapshot.summary,
                    'full_text': current_snapshot.full_text[:1000] + '...' if len(current_snapshot.full_text) > 1000 else current_snapshot.full_text
                }),
                diff_summary=diff_result.summary,
                diff_details=diff_result.unified_diff[:2000] + '...' if len(diff_result.unified_diff) > 2000 else diff_result.unified_diff,
                field_changed='multiple',
                change_description=classification.reasoning,
                impact_assessment=json.dumps({
                    'reimbursement_impact': classification.reimbursement_impact,
                    'regulatory_impact': classification.regulatory_impact,
                    'implementation_urgency': classification.implementation_urgency,
                    'key_changes': classification.key_changes,
                    'impact_areas': classification.impact_areas
                }),
                confidence_score=classification.confidence,
                word_count_delta=diff_result.word_count_delta
            )

            self.session.add(bill_change)
            self.session.commit()
            changes.append(bill_change)

            logger.info(f"Text change recorded for bill {bill.id}: {classification.severity.value}")

        except Exception as e:
            logger.error(f"Error processing text changes for bill {bill.id}: {e}")
            self.session.rollback()

        return changes

    def _process_stage_transition(self, bill: Bill, old_status: str, new_status: str) -> Optional[StageTransition]:
        """Process and store stage transition"""

        try:
            bill_context = {
                'bill_number': bill.bill_number,
                'title': bill.title,
                'summary': bill.summary,
                'source': bill.source,
                'relevance_score': bill.relevance_score
            }

            transition_result = self.stage_detector.detect_stage_transition(
                old_status, new_status, bill_context
            )

            if not transition_result.has_transition:
                return None

            # Create StageTransition record
            stage_transition = StageTransition(
                bill_id=bill.id,
                from_stage=transition_result.from_stage,
                to_stage=transition_result.to_stage,
                transition_date=datetime.utcnow(),
                committee_name=transition_result.committee_name,
                vote_count=transition_result.vote_details,
                notes=transition_result.notes,
                passage_likelihood=transition_result.passage_likelihood,
                estimated_timeline=self.stage_detector.get_stage_timeline_estimate(
                    transition_result.to_stage, bill_context
                ) if transition_result.to_stage else None,
                next_expected_stage=self._predict_next_stage(transition_result.to_stage)
            )

            self.session.add(stage_transition)
            self.session.commit()

            logger.info(f"Stage transition recorded for bill {bill.id}: "
                       f"{transition_result.from_stage} → {transition_result.to_stage}")

            return stage_transition

        except Exception as e:
            logger.error(f"Error processing stage transition for bill {bill.id}: {e}")
            self.session.rollback()
            return None

    def _create_alerts_for_change(self, bill: Bill, change: BillChange, diff_result) -> int:
        """Create alerts for bill changes"""

        alerts_created = 0

        try:
            # Get all users who should be alerted about this bill
            users = self._get_users_for_bill_alerts(bill)

            for user in users:
                # Check user preferences
                if not self._should_alert_user(user, change, bill):
                    continue

                # Create alert
                alert_title = self._generate_change_alert_title(bill, change)
                alert_message = self._generate_change_alert_message(bill, change, diff_result)

                # Calculate priority
                bill_context = {
                    'bill_number': bill.bill_number,
                    'title': bill.title,
                    'summary': bill.summary,
                    'relevance_score': bill.relevance_score
                }

                classification = self.classifier.classify_change(diff_result, bill_context)
                user_prefs = self._get_user_preferences_dict(user)

                priority_result = self.prioritizer.calculate_priority(
                    bill, classification, None, user_prefs
                )

                # Check for duplicates
                dedup_result = self.deduplication_engine.analyze_alert_for_duplicates(
                    user.id, bill.id, 'change', alert_title, alert_message, priority_result.priority
                )

                if not dedup_result.should_send:
                    logger.info(f"Alert suppressed for user {user.id}, bill {bill.id}: {dedup_result.reasoning}")
                    continue

                # Create alert
                alert = ChangeAlert(
                    bill_id=bill.id,
                    user_id=user.id,
                    alert_type='change',
                    priority=priority_result.priority,
                    title=alert_title,
                    message=alert_message,
                    bill_change_id=change.id,
                    dedup_hash=dedup_result.dedup_hash,
                    similar_alert_count=len(dedup_result.similar_alerts) + 1 if dedup_result.similar_alerts else 1
                )

                self.session.add(alert)
                alerts_created += 1

                # Update similar alert counts
                if dedup_result.similar_alerts:
                    self.deduplication_engine.update_similar_alert_counts(
                        alert.id, dedup_result.similar_alerts
                    )

            self.session.commit()
            logger.info(f"Created {alerts_created} alerts for bill {bill.id} change")

        except Exception as e:
            logger.error(f"Error creating alerts for bill {bill.id} change: {e}")
            self.session.rollback()

        return alerts_created

    def _create_alerts_for_stage_transition(self, bill: Bill, stage_transition: StageTransition) -> int:
        """Create alerts for stage transitions"""

        alerts_created = 0

        try:
            users = self._get_users_for_bill_alerts(bill)

            for user in users:
                # Check if user wants stage transition alerts
                preferences = self.session.query(AlertPreferences).filter(
                    AlertPreferences.user_id == user.id
                ).first()

                if preferences and not preferences.monitor_stage_transitions:
                    continue

                # Create alert
                alert_title = self._generate_stage_alert_title(bill, stage_transition)
                alert_message = self._generate_stage_alert_message(bill, stage_transition)

                # Calculate priority
                bill_context = {
                    'bill_number': bill.bill_number,
                    'title': bill.title,
                    'summary': bill.summary,
                    'relevance_score': bill.relevance_score
                }

                classification = self.classifier.classify_stage_transition(
                    stage_transition.from_stage.value if stage_transition.from_stage else 'unknown',
                    stage_transition.to_stage.value if stage_transition.to_stage else 'unknown',
                    bill_context
                )

                user_prefs = self._get_user_preferences_dict(user)
                priority_result = self.prioritizer.calculate_priority(
                    bill, classification, None, user_prefs
                )

                # Check for duplicates
                dedup_result = self.deduplication_engine.analyze_alert_for_duplicates(
                    user.id, bill.id, 'stage_transition', alert_title, alert_message, priority_result.priority
                )

                if not dedup_result.should_send:
                    continue

                # Create alert
                alert = ChangeAlert(
                    bill_id=bill.id,
                    user_id=user.id,
                    alert_type='stage_transition',
                    priority=priority_result.priority,
                    title=alert_title,
                    message=alert_message,
                    stage_transition_id=stage_transition.id,
                    dedup_hash=dedup_result.dedup_hash,
                    similar_alert_count=len(dedup_result.similar_alerts) + 1 if dedup_result.similar_alerts else 1
                )

                self.session.add(alert)
                alerts_created += 1

            self.session.commit()
            logger.info(f"Created {alerts_created} alerts for bill {bill.id} stage transition")

        except Exception as e:
            logger.error(f"Error creating stage transition alerts for bill {bill.id}: {e}")
            self.session.rollback()

        return alerts_created

    def _get_users_for_bill_alerts(self, bill: Bill) -> List[User]:
        """Get users who should receive alerts for this bill"""

        # For now, alert all active users
        # In a real system, this would be based on user preferences, subscriptions, etc.
        return self.session.query(User).filter(User.is_active == True).all()

    def _should_alert_user(self, user: User, change: BillChange, bill: Bill) -> bool:
        """Check if user should be alerted about this change"""

        preferences = self.session.query(AlertPreferences).filter(
            AlertPreferences.user_id == user.id
        ).first()

        if not preferences:
            return True  # Default to alerting

        # Check minimum relevance score
        if bill.relevance_score is not None and bill.relevance_score < preferences.min_relevance_score:
            return False

        # Check severity preferences
        severity_prefs = {
            ChangeSeverity.MINOR: preferences.alert_on_minor,
            ChangeSeverity.MODERATE: preferences.alert_on_moderate,
            ChangeSeverity.SIGNIFICANT: preferences.alert_on_significant,
            ChangeSeverity.CRITICAL: preferences.alert_on_critical
        }

        return severity_prefs.get(change.change_severity, True)

    def _get_user_preferences_dict(self, user: User) -> Optional[Dict]:
        """Get user preferences as dictionary"""

        preferences = self.session.query(AlertPreferences).filter(
            AlertPreferences.user_id == user.id
        ).first()

        if not preferences:
            return None

        return {
            'min_priority': preferences.min_priority.value,
            'important_keywords': preferences.important_keywords,
            'excluded_keywords': preferences.excluded_keywords
        }

    def _generate_change_alert_title(self, bill: Bill, change: BillChange) -> str:
        """Generate title for change alert"""

        severity_labels = {
            ChangeSeverity.CRITICAL: "Critical Change",
            ChangeSeverity.SIGNIFICANT: "Significant Change",
            ChangeSeverity.MODERATE: "Change",
            ChangeSeverity.MINOR: "Minor Change"
        }

        severity_label = severity_labels.get(change.change_severity, "Change")
        return f"{severity_label}: {bill.bill_number} - {(bill.title or 'Unknown Title')[:60]}..."

    def _generate_change_alert_message(self, bill: Bill, change: BillChange, diff_result) -> str:
        """Generate message for change alert"""

        message_parts = [
            f"Bill {bill.bill_number} has been updated.",
            f"Change Summary: {change.diff_summary}",
        ]

        if diff_result.significant_changes:
            message_parts.append(f"Key Changes: {'; '.join(diff_result.significant_changes[:3])}")

        if change.change_description:
            message_parts.append(f"Impact: {change.change_description}")

        return " ".join(message_parts)

    def _generate_stage_alert_title(self, bill: Bill, stage_transition: StageTransition) -> str:
        """Generate title for stage transition alert"""

        to_stage_name = stage_transition.to_stage.value.replace('_', ' ').title() if stage_transition.to_stage else 'Unknown'
        return f"Stage Update: {bill.bill_number} - {to_stage_name}"

    def _generate_stage_alert_message(self, bill: Bill, stage_transition: StageTransition) -> str:
        """Generate message for stage transition alert"""

        from_stage = stage_transition.from_stage.value.replace('_', ' ').title() if stage_transition.from_stage else 'Unknown'
        to_stage = stage_transition.to_stage.value.replace('_', ' ').title() if stage_transition.to_stage else 'Unknown'

        message_parts = [
            f"Bill {bill.bill_number} has moved from {from_stage} to {to_stage}.",
        ]

        if stage_transition.vote_count:
            message_parts.append(f"Vote: {stage_transition.vote_count}")

        if stage_transition.committee_name:
            message_parts.append(f"Committee: {stage_transition.committee_name}")

        if stage_transition.passage_likelihood:
            likelihood_percent = int(stage_transition.passage_likelihood * 100)
            message_parts.append(f"Passage Likelihood: {likelihood_percent}%")

        if stage_transition.notes:
            message_parts.append(f"Notes: {stage_transition.notes}")

        return " ".join(message_parts)

    def _predict_next_stage(self, current_stage: Optional[BillStage]) -> Optional[BillStage]:
        """Predict the next likely stage"""

        if not current_stage:
            return None

        stage_progression = {
            BillStage.INTRODUCED: BillStage.COMMITTEE_REVIEW,
            BillStage.COMMITTEE_REVIEW: BillStage.COMMITTEE_MARKUP,
            BillStage.COMMITTEE_MARKUP: BillStage.COMMITTEE_REPORTED,
            BillStage.COMMITTEE_REPORTED: BillStage.FLOOR_CONSIDERATION,
            BillStage.FLOOR_CONSIDERATION: BillStage.PASSED_CHAMBER,
            BillStage.PASSED_CHAMBER: BillStage.SENT_TO_OTHER_CHAMBER,
            BillStage.SENT_TO_OTHER_CHAMBER: BillStage.OTHER_CHAMBER_COMMITTEE,
            BillStage.OTHER_CHAMBER_COMMITTEE: BillStage.OTHER_CHAMBER_FLOOR,
            BillStage.OTHER_CHAMBER_FLOOR: BillStage.PASSED_BOTH_CHAMBERS,
            BillStage.PASSED_BOTH_CHAMBERS: BillStage.SENT_TO_PRESIDENT,
            BillStage.SENT_TO_PRESIDENT: BillStage.SIGNED_INTO_LAW
        }

        return stage_progression.get(current_stage)

    def _get_previous_snapshot(self, bill_id: int) -> Optional[BillSnapshot]:
        """Get previous snapshot for a bill"""

        # Check cache first
        if bill_id in self.snapshot_cache:
            return self.snapshot_cache[bill_id]

        # In a real implementation, this would load from a snapshots table
        # For now, we'll just return None for first-time bills
        return None

    def _store_snapshot(self, bill_id: int, snapshot: BillSnapshot):
        """Store snapshot for future comparison"""

        # Store in cache
        self.snapshot_cache[bill_id] = snapshot

        # In a real implementation, this would persist to database
        # For now, we just cache in memory

    def _generate_change_summary(self, bill_results: List[BillCheckResult]) -> Dict[str, Any]:
        """Generate summary of change detection results"""

        summary = {
            'bills_with_changes': len([r for r in bill_results if r.has_changes]),
            'bills_with_stage_transitions': len([r for r in bill_results if r.has_stage_transition]),
            'total_changes': sum(r.change_count for r in bill_results),
            'total_alerts': sum(r.alerts_created for r in bill_results),
            'error_count': len([r for r in bill_results if r.error]),
            'success_rate': len([r for r in bill_results if not r.error]) / len(bill_results) if bill_results else 0
        }

        return summary

    def get_system_stats(self, days: int = 7) -> Dict[str, Any]:
        """Get system statistics"""

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        try:
            stats = {}

            # Bill change stats
            stats['changes'] = {
                'total': self.session.query(BillChange).filter(
                    BillChange.detected_at >= cutoff_date
                ).count(),
                'by_severity': {}
            }

            for severity in ChangeSeverity:
                count = self.session.query(BillChange).filter(
                    BillChange.detected_at >= cutoff_date,
                    BillChange.change_severity == severity
                ).count()
                stats['changes']['by_severity'][severity.value] = count

            # Stage transition stats
            stats['stage_transitions'] = self.session.query(StageTransition).filter(
                StageTransition.transition_date >= cutoff_date
            ).count()

            # Alert stats
            stats['alerts'] = {
                'total': self.session.query(ChangeAlert).filter(
                    ChangeAlert.created_at >= cutoff_date
                ).count(),
                'sent': self.session.query(ChangeAlert).filter(
                    ChangeAlert.created_at >= cutoff_date,
                    ChangeAlert.is_sent == True
                ).count(),
                'by_priority': {}
            }

            for priority in AlertPriority:
                count = self.session.query(ChangeAlert).filter(
                    ChangeAlert.created_at >= cutoff_date,
                    ChangeAlert.priority == priority
                ).count()
                stats['alerts']['by_priority'][priority.value] = count

            # Deduplication stats
            dedup_stats = self.deduplication_engine.get_deduplication_stats(None, days)
            stats['deduplication'] = dedup_stats

            return stats

        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {'error': str(e)}