import hashlib
import json
import logging
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models.change_detection import ChangeAlert, AlertPriority, ChangeSeverity
from models.legislation import Bill
import difflib

logger = logging.getLogger(__name__)

@dataclass
class DedupResult:
    """Result of deduplication analysis"""
    should_send: bool
    is_duplicate: bool
    similar_alerts: List[int]  # IDs of similar alerts
    dedup_hash: str
    similarity_score: float
    reasoning: str

@dataclass
class AlertGroup:
    """Group of similar alerts"""
    representative_alert_id: int
    similar_alert_ids: List[int]
    common_theme: str
    total_count: int
    priority: AlertPriority
    last_sent: Optional[datetime]

class AlertDeduplicationEngine:
    """Smart deduplication system to prevent alert fatigue"""

    def __init__(self, session: Session):
        self.session = session
        self.similarity_threshold = 0.75  # Threshold for considering alerts similar
        self.time_window_hours = 24  # Look back window for duplicates
        self.max_similar_alerts = 5   # Max alerts to group together

        # Keywords that should increase uniqueness
        self.uniqueness_keywords = [
            'emergency', 'urgent', 'deadline', 'immediate', 'critical',
            'new rate', 'payment change', 'effective date', 'implementation'
        ]

        # Fields to use for similarity comparison
        self.comparison_fields = ['title', 'message', 'alert_type']

    def analyze_alert_for_duplicates(self, user_id: int, bill_id: int, alert_type: str,
                                   title: str, message: str, priority: AlertPriority) -> DedupResult:
        """Analyze if an alert is a duplicate and should be suppressed or grouped"""

        try:
            # Generate hash for this alert
            alert_hash = self._generate_alert_hash(bill_id, alert_type, title, message)

            # Get recent similar alerts
            cutoff_time = datetime.utcnow() - timedelta(hours=self.time_window_hours)

            recent_alerts = self.session.query(ChangeAlert).filter(
                ChangeAlert.user_id == user_id,
                ChangeAlert.bill_id == bill_id,
                ChangeAlert.created_at >= cutoff_time,
                ChangeAlert.is_dismissed == False
            ).order_by(ChangeAlert.created_at.desc()).limit(20).all()

            if not recent_alerts:
                return DedupResult(
                    should_send=True,
                    is_duplicate=False,
                    similar_alerts=[],
                    dedup_hash=alert_hash,
                    similarity_score=0.0,
                    reasoning="No recent alerts to compare against"
                )

            # Check for exact duplicates first
            exact_duplicates = [alert for alert in recent_alerts if alert.dedup_hash == alert_hash]
            if exact_duplicates:
                return DedupResult(
                    should_send=False,
                    is_duplicate=True,
                    similar_alerts=[alert.id for alert in exact_duplicates],
                    dedup_hash=alert_hash,
                    similarity_score=1.0,
                    reasoning=f"Exact duplicate of alert sent {exact_duplicates[0].created_at}"
                )

            # Check for similar alerts
            similar_alerts, best_similarity = self._find_similar_alerts(
                title, message, alert_type, recent_alerts
            )

            # Determine if we should suppress based on similarity
            should_send = self._should_send_alert(
                title, message, priority, similar_alerts, best_similarity
            )

            reasoning = self._generate_dedup_reasoning(
                should_send, similar_alerts, best_similarity
            )

            return DedupResult(
                should_send=should_send,
                is_duplicate=best_similarity >= self.similarity_threshold,
                similar_alerts=[alert.id for alert in similar_alerts],
                dedup_hash=alert_hash,
                similarity_score=best_similarity,
                reasoning=reasoning
            )

        except Exception as e:
            logger.error(f"Error in alert deduplication: {e}")
            # Default to sending alert on error
            return DedupResult(
                should_send=True,
                is_duplicate=False,
                similar_alerts=[],
                dedup_hash=self._generate_alert_hash(bill_id, alert_type, title, message),
                similarity_score=0.0,
                reasoning=f"Deduplication error, defaulting to send: {str(e)}"
            )

    def group_similar_alerts(self, user_id: int, lookback_hours: int = 168) -> List[AlertGroup]:
        """Group similar alerts for digest/summary purposes"""

        cutoff_time = datetime.utcnow() - timedelta(hours=lookback_hours)

        alerts = self.session.query(ChangeAlert).filter(
            ChangeAlert.user_id == user_id,
            ChangeAlert.created_at >= cutoff_time,
            ChangeAlert.is_dismissed == False
        ).order_by(ChangeAlert.created_at.desc()).all()

        if not alerts:
            return []

        # Group alerts by similarity
        groups = []
        processed_alert_ids = set()

        for alert in alerts:
            if alert.id in processed_alert_ids:
                continue

            # Find similar alerts
            similar_alerts = []
            for other_alert in alerts:
                if (other_alert.id != alert.id and
                    other_alert.id not in processed_alert_ids and
                    other_alert.bill_id == alert.bill_id):

                    similarity = self._calculate_alert_similarity(alert, other_alert)
                    if similarity >= 0.6:  # Lower threshold for grouping
                        similar_alerts.append(other_alert)

            if similar_alerts:
                # Create group
                group = AlertGroup(
                    representative_alert_id=alert.id,
                    similar_alert_ids=[a.id for a in similar_alerts],
                    common_theme=self._extract_common_theme(alert, similar_alerts),
                    total_count=len(similar_alerts) + 1,
                    priority=self._determine_group_priority([alert] + similar_alerts),
                    last_sent=max([a.sent_at for a in [alert] + similar_alerts if a.sent_at])
                )
                groups.append(group)

                # Mark as processed
                processed_alert_ids.add(alert.id)
                for similar_alert in similar_alerts:
                    processed_alert_ids.add(similar_alert.id)

        return groups

    def update_similar_alert_counts(self, alert_id: int, similar_alert_ids: List[int]):
        """Update the similar_alert_count for grouped alerts"""
        try:
            if not similar_alert_ids:
                return

            # Update the main alert
            main_alert = self.session.query(ChangeAlert).filter(
                ChangeAlert.id == alert_id
            ).first()

            if main_alert:
                main_alert.similar_alert_count = len(similar_alert_ids) + 1
                self.session.commit()
                logger.info(f"Updated alert {alert_id} with similar_alert_count: {main_alert.similar_alert_count}")

        except Exception as e:
            logger.error(f"Error updating similar alert counts: {e}")
            self.session.rollback()

    def _generate_alert_hash(self, bill_id: int, alert_type: str, title: str, message: str) -> str:
        """Generate a hash for alert deduplication"""

        # Normalize text for hashing
        normalized_title = self._normalize_text(title)
        normalized_message = self._normalize_text(message)
        normalized_type = alert_type.lower().strip()

        # Create hash string
        hash_string = f"{bill_id}:{normalized_type}:{normalized_title}:{normalized_message}"

        return hashlib.sha256(hash_string.encode()).hexdigest()

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        if not text:
            return ""

        # Convert to lowercase and remove extra whitespace
        normalized = ' '.join(text.lower().split())

        # Remove common variations that don't affect meaning
        replacements = [
            ('bill', ''),
            ('legislation', ''),
            ('the', ''),
            ('a', ''),
            ('an', ''),
        ]

        for old, new in replacements:
            normalized = normalized.replace(old, new)

        return normalized.strip()

    def _find_similar_alerts(self, title: str, message: str, alert_type: str,
                           recent_alerts: List[ChangeAlert]) -> Tuple[List[ChangeAlert], float]:
        """Find alerts similar to the new one"""

        similar_alerts = []
        best_similarity = 0.0

        for alert in recent_alerts:
            similarity = self._calculate_text_similarity(
                title, message, alert_type,
                alert.title, alert.message, alert.alert_type
            )

            if similarity >= self.similarity_threshold:
                similar_alerts.append(alert)
                best_similarity = max(best_similarity, similarity)

        return similar_alerts, best_similarity

    def _calculate_text_similarity(self, title1: str, message1: str, type1: str,
                                 title2: str, message2: str, type2: str) -> float:
        """Calculate similarity between two alerts"""

        # Type must match for high similarity
        if type1 != type2:
            type_penalty = 0.3
        else:
            type_penalty = 0.0

        # Calculate title similarity
        title_sim = difflib.SequenceMatcher(
            None,
            self._normalize_text(title1),
            self._normalize_text(title2)
        ).ratio()

        # Calculate message similarity
        message_sim = difflib.SequenceMatcher(
            None,
            self._normalize_text(message1),
            self._normalize_text(message2)
        ).ratio()

        # Weighted average (title is more important)
        overall_similarity = (0.4 * title_sim + 0.6 * message_sim) - type_penalty

        # Check for uniqueness keywords that should prevent grouping
        combined_text1 = f"{title1} {message1}".lower()
        combined_text2 = f"{title2} {message2}".lower()

        for keyword in self.uniqueness_keywords:
            if keyword in combined_text1 or keyword in combined_text2:
                # Reduce similarity if uniqueness keywords are present
                overall_similarity *= 0.8
                break

        return max(0.0, overall_similarity)

    def _calculate_alert_similarity(self, alert1: ChangeAlert, alert2: ChangeAlert) -> float:
        """Calculate similarity between two alert objects"""
        return self._calculate_text_similarity(
            alert1.title, alert1.message, alert1.alert_type,
            alert2.title, alert2.message, alert2.alert_type
        )

    def _should_send_alert(self, title: str, message: str, priority: AlertPriority,
                         similar_alerts: List[ChangeAlert], similarity_score: float) -> bool:
        """Determine if an alert should be sent based on deduplication rules"""

        # Always send critical/urgent alerts
        if priority in [AlertPriority.URGENT, AlertPriority.HIGH]:
            return True

        # If no similar alerts, send it
        if not similar_alerts:
            return True

        # If similarity is below threshold, send it
        if similarity_score < self.similarity_threshold:
            return True

        # Check if we've already sent too many similar alerts recently
        recent_sent = [alert for alert in similar_alerts if alert.is_sent]
        if len(recent_sent) >= 3:  # Max 3 similar alerts in time window
            return False

        # Check time since last similar alert
        if recent_sent:
            last_sent = max([alert.sent_at for alert in recent_sent if alert.sent_at])
            if last_sent:
                time_since_last = datetime.utcnow() - last_sent
                if time_since_last.total_seconds() < 3600:  # 1 hour minimum gap
                    return False

        # Check for uniqueness indicators
        combined_text = f"{title} {message}".lower()
        for keyword in self.uniqueness_keywords:
            if keyword in combined_text:
                return True  # Send if it contains uniqueness keywords

        return False  # Default to not sending if very similar

    def _generate_dedup_reasoning(self, should_send: bool, similar_alerts: List[ChangeAlert],
                                similarity_score: float) -> str:
        """Generate reasoning for deduplication decision"""

        if should_send:
            if not similar_alerts:
                return "No similar recent alerts found"
            elif similarity_score < self.similarity_threshold:
                return f"Similarity below threshold ({similarity_score:.2f} < {self.similarity_threshold})"
            else:
                return f"Sending despite {len(similar_alerts)} similar alerts due to importance"
        else:
            return f"Suppressed due to {len(similar_alerts)} similar alerts (similarity: {similarity_score:.2f})"

    def _extract_common_theme(self, representative: ChangeAlert, similar_alerts: List[ChangeAlert]) -> str:
        """Extract common theme from grouped alerts"""

        all_alerts = [representative] + similar_alerts

        # Find common words in titles
        all_titles = [alert.title.lower() for alert in all_alerts]
        common_words = set(all_titles[0].split())

        for title in all_titles[1:]:
            common_words &= set(title.split())

        # Filter out stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with'}
        meaningful_words = [word for word in common_words if word not in stop_words and len(word) > 2]

        if meaningful_words:
            return f"Updates about {' '.join(sorted(meaningful_words)[:3])}"
        else:
            # Fallback to alert type
            return f"Multiple {representative.alert_type} alerts"

    def _determine_group_priority(self, alerts: List[ChangeAlert]) -> AlertPriority:
        """Determine priority for a group of alerts"""

        priorities = [alert.priority for alert in alerts]

        # Take the highest priority
        priority_order = [AlertPriority.LOW, AlertPriority.MEDIUM, AlertPriority.HIGH, AlertPriority.URGENT]

        max_priority = AlertPriority.LOW
        for priority in priorities:
            if priority_order.index(priority) > priority_order.index(max_priority):
                max_priority = priority

        return max_priority

    def cleanup_old_alerts(self, days_to_keep: int = 30):
        """Clean up old dismissed alerts to prevent database bloat"""

        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

            deleted_count = self.session.query(ChangeAlert).filter(
                ChangeAlert.is_dismissed == True,
                ChangeAlert.created_at < cutoff_date
            ).delete()

            self.session.commit()
            logger.info(f"Cleaned up {deleted_count} old dismissed alerts")

        except Exception as e:
            logger.error(f"Error cleaning up old alerts: {e}")
            self.session.rollback()

    def get_deduplication_stats(self, user_id: int, days: int = 7) -> Dict[str, any]:
        """Get deduplication statistics for analysis"""

        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            # Get all alerts in period
            all_alerts = self.session.query(ChangeAlert).filter(
                ChangeAlert.user_id == user_id,
                ChangeAlert.created_at >= cutoff_date
            ).count()

            # Get sent alerts
            sent_alerts = self.session.query(ChangeAlert).filter(
                ChangeAlert.user_id == user_id,
                ChangeAlert.created_at >= cutoff_date,
                ChangeAlert.is_sent == True
            ).count()

            # Get grouped alerts (those with similar_alert_count > 1)
            grouped_alerts = self.session.query(ChangeAlert).filter(
                ChangeAlert.user_id == user_id,
                ChangeAlert.created_at >= cutoff_date,
                ChangeAlert.similar_alert_count > 1
            ).count()

            suppression_rate = ((all_alerts - sent_alerts) / all_alerts * 100) if all_alerts > 0 else 0

            return {
                'total_alerts_created': all_alerts,
                'alerts_sent': sent_alerts,
                'alerts_suppressed': all_alerts - sent_alerts,
                'suppression_rate_percent': round(suppression_rate, 1),
                'grouped_alerts': grouped_alerts,
                'period_days': days
            }

        except Exception as e:
            logger.error(f"Error getting deduplication stats: {e}")
            return {
                'error': str(e),
                'total_alerts_created': 0,
                'alerts_sent': 0,
                'alerts_suppressed': 0,
                'suppression_rate_percent': 0,
                'grouped_alerts': 0,
                'period_days': days
            }