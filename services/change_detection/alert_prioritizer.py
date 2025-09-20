import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models.change_detection import AlertPriority, ChangeSeverity, ChangeType, BillStage
from models.legislation import Bill
from services.change_detection.significance_classifier import ChangeClassification
from services.change_detection.stage_detector import StageTransitionResult
import json

logger = logging.getLogger(__name__)

@dataclass
class PriorityFactors:
    """Factors that influence alert priority"""
    reimbursement_impact: float       # 0-1: Direct financial impact
    implementation_speed: float       # 0-1: How quickly SNFs need to act
    passage_likelihood: float         # 0-1: Probability of becoming law
    bill_relevance: float            # 0-1: How relevant to SNFs
    change_severity: float           # 0-1: Magnitude of change
    regulatory_impact: float         # 0-1: New compliance requirements
    time_sensitivity: float          # 0-1: Urgency based on deadlines

@dataclass
class PriorityResult:
    """Result of priority analysis"""
    priority: AlertPriority
    confidence: float
    reasoning: str
    priority_score: float  # Raw calculated score (0-100)
    factors: PriorityFactors
    recommendations: List[str]

class AlertPrioritizer:
    """Engine for determining alert priority based on multiple factors"""

    def __init__(self):
        # Priority calculation weights
        self.weights = {
            'reimbursement_impact': 0.25,    # Highest weight - direct financial impact
            'implementation_speed': 0.20,    # How quickly they need to respond
            'passage_likelihood': 0.15,      # How likely to actually happen
            'bill_relevance': 0.15,         # How relevant to SNFs
            'change_severity': 0.10,        # Magnitude of change
            'regulatory_impact': 0.10,       # New compliance requirements
            'time_sensitivity': 0.05         # Deadline urgency
        }

        # Priority thresholds (out of 100)
        self.priority_thresholds = {
            AlertPriority.URGENT: 85,
            AlertPriority.HIGH: 65,
            AlertPriority.MEDIUM: 35,
            AlertPriority.LOW: 0
        }

        # Reimbursement impact keywords (with impact scores)
        self.reimbursement_keywords = {
            'payment rate': 1.0,
            'reimbursement': 1.0,
            'pdpm': 0.95,
            'prospective payment': 0.9,
            'medicare rate': 0.9,
            'case mix': 0.8,
            'wage index': 0.8,
            'medicaid rate': 0.7,
            'bad debt': 0.7,
            'snf pps': 0.9,
            'market basket': 0.8,
            'rebasing': 0.85,
            'payment adjustment': 0.8
        }

        # Implementation speed keywords (urgency scores)
        self.implementation_keywords = {
            'immediate': 1.0,
            'effective immediately': 1.0,
            'within 30 days': 0.9,
            'within 60 days': 0.8,
            'within 90 days': 0.7,
            'by january': 0.8,
            'by october': 0.7,
            'fiscal year': 0.6,
            'next year': 0.4,
            'phase in': 0.3
        }

        # Regulatory impact keywords
        self.regulatory_keywords = {
            'staffing requirement': 0.95,
            'minimum staffing': 0.9,
            'quality measure': 0.8,
            'star rating': 0.85,
            'survey requirement': 0.8,
            'compliance': 0.7,
            'certification': 0.8,
            'penalty': 0.9,
            'deficiency': 0.8,
            'inspection': 0.7
        }

    def calculate_priority(self, bill: Bill, change_classification: ChangeClassification,
                         stage_transition: Optional[StageTransitionResult] = None,
                         user_preferences: Optional[Dict] = None) -> PriorityResult:
        """Calculate alert priority based on multiple factors"""

        try:
            # Calculate individual factors
            factors = self._calculate_priority_factors(
                bill, change_classification, stage_transition, user_preferences
            )

            # Calculate weighted priority score
            priority_score = self._calculate_weighted_score(factors)

            # Determine priority level
            priority = self._score_to_priority(priority_score)

            # Apply user preference adjustments
            if user_preferences:
                priority, priority_score = self._apply_user_preferences(
                    priority, priority_score, change_classification, user_preferences
                )

            # Generate reasoning and recommendations
            reasoning = self._generate_reasoning(factors, priority_score, change_classification, stage_transition)
            recommendations = self._generate_recommendations(factors, change_classification, stage_transition)

            # Calculate confidence based on data quality
            confidence = self._calculate_confidence(bill, change_classification, stage_transition)

            return PriorityResult(
                priority=priority,
                confidence=confidence,
                reasoning=reasoning,
                priority_score=priority_score,
                factors=factors,
                recommendations=recommendations
            )

        except Exception as e:
            logger.error(f"Error calculating priority: {e}")
            # Return conservative default
            return self._create_default_priority_result(str(e))

    def _calculate_priority_factors(self, bill: Bill, change_classification: ChangeClassification,
                                  stage_transition: Optional[StageTransitionResult],
                                  user_preferences: Optional[Dict]) -> PriorityFactors:
        """Calculate individual priority factors"""

        # Reimbursement impact
        reimbursement_impact = self._assess_reimbursement_impact(bill, change_classification)

        # Implementation speed (how quickly SNFs need to respond)
        implementation_speed = self._assess_implementation_speed(bill, change_classification)

        # Passage likelihood
        passage_likelihood = self._assess_passage_likelihood(bill, stage_transition)

        # Bill relevance to SNFs
        bill_relevance = self._assess_bill_relevance(bill)

        # Change severity
        change_severity = self._assess_change_severity(change_classification)

        # Regulatory impact
        regulatory_impact = self._assess_regulatory_impact(bill, change_classification)

        # Time sensitivity
        time_sensitivity = self._assess_time_sensitivity(bill, change_classification, stage_transition)

        return PriorityFactors(
            reimbursement_impact=reimbursement_impact,
            implementation_speed=implementation_speed,
            passage_likelihood=passage_likelihood,
            bill_relevance=bill_relevance,
            change_severity=change_severity,
            regulatory_impact=regulatory_impact,
            time_sensitivity=time_sensitivity
        )

    def _assess_reimbursement_impact(self, bill: Bill, change_classification: ChangeClassification) -> float:
        """Assess direct financial/reimbursement impact"""

        if change_classification.reimbursement_impact:
            base_score = 0.8
        else:
            base_score = 0.0

        # Check for specific reimbursement keywords
        all_text = ' '.join([
            bill.title or '',
            bill.summary or '',
            ' '.join(change_classification.key_changes),
            change_classification.reasoning
        ]).lower()

        keyword_score = 0.0
        for keyword, impact in self.reimbursement_keywords.items():
            if keyword in all_text:
                keyword_score = max(keyword_score, impact)

        # Combine base score and keyword score
        final_score = max(base_score, keyword_score)

        # Boost for critical severity changes involving reimbursement
        if (change_classification.severity == ChangeSeverity.CRITICAL and
            ('payment' in all_text or 'reimbursement' in all_text)):
            final_score = min(final_score * 1.2, 1.0)

        return final_score

    def _assess_implementation_speed(self, bill: Bill, change_classification: ChangeClassification) -> float:
        """Assess how quickly SNFs need to implement changes"""

        urgency = change_classification.implementation_urgency
        base_scores = {
            'immediate': 1.0,
            'short_term': 0.7,
            'long_term': 0.3
        }

        base_score = base_scores.get(urgency, 0.5)

        # Check for specific timing keywords
        all_text = ' '.join([
            bill.title or '',
            bill.summary or '',
            ' '.join(change_classification.key_changes)
        ]).lower()

        keyword_score = 0.0
        for keyword, speed in self.implementation_keywords.items():
            if keyword in all_text:
                keyword_score = max(keyword_score, speed)

        return max(base_score, keyword_score)

    def _assess_passage_likelihood(self, bill: Bill, stage_transition: Optional[StageTransitionResult]) -> float:
        """Assess likelihood of bill becoming law"""

        if stage_transition:
            return stage_transition.passage_likelihood

        # Fallback to basic stage assessment
        status = (bill.status or '').lower()

        if any(term in status for term in ['signed', 'enacted', 'law']):
            return 1.0
        elif any(term in status for term in ['passed both', 'conference', 'final passage']):
            return 0.9
        elif any(term in status for term in ['passed', 'floor']):
            return 0.7
        elif any(term in status for term in ['committee reported', 'markup']):
            return 0.5
        elif 'committee' in status:
            return 0.3
        elif 'introduced' in status:
            return 0.1
        else:
            return 0.2  # Unknown status

    def _assess_bill_relevance(self, bill: Bill) -> float:
        """Assess how relevant the bill is to SNFs"""

        if bill.relevance_score is not None:
            return bill.relevance_score / 100.0

        # Fallback assessment based on content
        all_text = ' '.join([
            bill.title or '',
            bill.summary or '',
            bill.full_text or ''
        ]).lower()

        snf_terms = [
            'skilled nursing', 'snf', 'nursing home', 'long-term care',
            'medicare part a', 'post-acute', 'rehabilitation'
        ]

        relevance_score = 0.0
        for term in snf_terms:
            if term in all_text:
                relevance_score += 0.2

        return min(relevance_score, 1.0)

    def _assess_change_severity(self, change_classification: ChangeClassification) -> float:
        """Convert change severity to numeric score"""

        severity_scores = {
            ChangeSeverity.CRITICAL: 1.0,
            ChangeSeverity.SIGNIFICANT: 0.8,
            ChangeSeverity.MODERATE: 0.5,
            ChangeSeverity.MINOR: 0.2
        }

        return severity_scores.get(change_classification.severity, 0.5)

    def _assess_regulatory_impact(self, bill: Bill, change_classification: ChangeClassification) -> float:
        """Assess regulatory/compliance impact"""

        if change_classification.regulatory_impact:
            base_score = 0.7
        else:
            base_score = 0.0

        # Check for specific regulatory keywords
        all_text = ' '.join([
            bill.title or '',
            bill.summary or '',
            ' '.join(change_classification.key_changes)
        ]).lower()

        keyword_score = 0.0
        for keyword, impact in self.regulatory_keywords.items():
            if keyword in all_text:
                keyword_score = max(keyword_score, impact)

        return max(base_score, keyword_score)

    def _assess_time_sensitivity(self, bill: Bill, change_classification: ChangeClassification,
                               stage_transition: Optional[StageTransitionResult]) -> float:
        """Assess time-based urgency factors"""

        time_score = 0.0

        # Check for urgent stage transitions
        if stage_transition:
            if stage_transition.to_stage in [BillStage.SIGNED_INTO_LAW, BillStage.SENT_TO_PRESIDENT]:
                time_score = max(time_score, 0.9)
            elif stage_transition.to_stage == BillStage.PASSED_BOTH_CHAMBERS:
                time_score = max(time_score, 0.8)

        # Check for deadline keywords
        all_text = ' '.join([
            bill.title or '',
            bill.summary or '',
            ' '.join(change_classification.key_changes)
        ]).lower()

        deadline_terms = ['deadline', 'expires', 'sunset', 'by december', 'end of year']
        for term in deadline_terms:
            if term in all_text:
                time_score = max(time_score, 0.7)

        return time_score

    def _calculate_weighted_score(self, factors: PriorityFactors) -> float:
        """Calculate weighted priority score"""

        score = (
            factors.reimbursement_impact * self.weights['reimbursement_impact'] +
            factors.implementation_speed * self.weights['implementation_speed'] +
            factors.passage_likelihood * self.weights['passage_likelihood'] +
            factors.bill_relevance * self.weights['bill_relevance'] +
            factors.change_severity * self.weights['change_severity'] +
            factors.regulatory_impact * self.weights['regulatory_impact'] +
            factors.time_sensitivity * self.weights['time_sensitivity']
        )

        return score * 100  # Convert to 0-100 scale

    def _score_to_priority(self, score: float) -> AlertPriority:
        """Convert numeric score to priority level"""

        if score >= self.priority_thresholds[AlertPriority.URGENT]:
            return AlertPriority.URGENT
        elif score >= self.priority_thresholds[AlertPriority.HIGH]:
            return AlertPriority.HIGH
        elif score >= self.priority_thresholds[AlertPriority.MEDIUM]:
            return AlertPriority.MEDIUM
        else:
            return AlertPriority.LOW

    def _apply_user_preferences(self, priority: AlertPriority, score: float,
                              change_classification: ChangeClassification,
                              user_preferences: Dict) -> Tuple[AlertPriority, float]:
        """Apply user preference adjustments"""

        try:
            # Check minimum priority preference
            min_priority = user_preferences.get('min_priority', 'medium')
            min_priority_enum = getattr(AlertPriority, min_priority.upper(), AlertPriority.MEDIUM)

            priority_order = [AlertPriority.LOW, AlertPriority.MEDIUM, AlertPriority.HIGH, AlertPriority.URGENT]

            if priority_order.index(priority) < priority_order.index(min_priority_enum):
                priority = min_priority_enum
                score = self.priority_thresholds[min_priority_enum]

            # Check keyword preferences
            important_keywords = user_preferences.get('important_keywords', [])
            if isinstance(important_keywords, str):
                important_keywords = json.loads(important_keywords)

            all_text = ' '.join(change_classification.key_changes + [change_classification.reasoning]).lower()

            for keyword in important_keywords:
                if keyword.lower() in all_text:
                    # Boost priority for important keywords
                    score = min(score * 1.2, 100)
                    if priority != AlertPriority.URGENT:
                        new_priority_index = min(priority_order.index(priority) + 1, len(priority_order) - 1)
                        priority = priority_order[new_priority_index]
                    break

            # Check excluded keywords
            excluded_keywords = user_preferences.get('excluded_keywords', [])
            if isinstance(excluded_keywords, str):
                excluded_keywords = json.loads(excluded_keywords)

            for keyword in excluded_keywords:
                if keyword.lower() in all_text:
                    # Reduce priority for excluded keywords
                    score = max(score * 0.8, 0)
                    if priority != AlertPriority.LOW:
                        new_priority_index = max(priority_order.index(priority) - 1, 0)
                        priority = priority_order[new_priority_index]
                    break

        except Exception as e:
            logger.error(f"Error applying user preferences: {e}")

        return priority, score

    def _calculate_confidence(self, bill: Bill, change_classification: ChangeClassification,
                            stage_transition: Optional[StageTransitionResult]) -> float:
        """Calculate confidence in priority assessment"""

        confidence_factors = []

        # Bill data quality
        if bill.title and bill.summary:
            confidence_factors.append(0.3)
        elif bill.title or bill.summary:
            confidence_factors.append(0.2)
        else:
            confidence_factors.append(0.1)

        # Change classification confidence
        confidence_factors.append(change_classification.confidence * 0.4)

        # Stage transition confidence
        if stage_transition:
            confidence_factors.append(stage_transition.confidence * 0.3)
        else:
            confidence_factors.append(0.1)  # Lower confidence without stage info

        return sum(confidence_factors)

    def _generate_reasoning(self, factors: PriorityFactors, score: float,
                          change_classification: ChangeClassification,
                          stage_transition: Optional[StageTransitionResult]) -> str:
        """Generate human-readable reasoning for the priority decision"""

        reasoning_parts = []

        # Primary factor identification
        primary_factors = []
        if factors.reimbursement_impact >= 0.7:
            primary_factors.append("high reimbursement impact")
        if factors.implementation_speed >= 0.7:
            primary_factors.append("urgent implementation timeline")
        if factors.passage_likelihood >= 0.8:
            primary_factors.append("high passage likelihood")
        if factors.regulatory_impact >= 0.7:
            primary_factors.append("significant regulatory changes")

        if primary_factors:
            reasoning_parts.append(f"Priority elevated due to {', '.join(primary_factors)}")

        # Severity context
        severity_text = change_classification.severity.value
        reasoning_parts.append(f"Change classified as {severity_text}")

        # Stage context
        if stage_transition and stage_transition.has_transition:
            reasoning_parts.append(f"Bill transitioned to {stage_transition.to_stage.value}")

        # Score context
        reasoning_parts.append(f"Overall priority score: {score:.0f}/100")

        return ". ".join(reasoning_parts) + "."

    def _generate_recommendations(self, factors: PriorityFactors,
                                change_classification: ChangeClassification,
                                stage_transition: Optional[StageTransitionResult]) -> List[str]:
        """Generate actionable recommendations"""

        recommendations = []

        # Reimbursement impact recommendations
        if factors.reimbursement_impact >= 0.8:
            recommendations.append("Review impact on facility reimbursement rates")
            recommendations.append("Update financial projections and budgets")

        # Implementation speed recommendations
        if factors.implementation_speed >= 0.8:
            recommendations.append("Begin immediate implementation planning")
            recommendations.append("Assign dedicated staff to manage compliance")
        elif factors.implementation_speed >= 0.5:
            recommendations.append("Add to implementation roadmap")

        # Regulatory impact recommendations
        if factors.regulatory_impact >= 0.7:
            recommendations.append("Review compliance policies and procedures")
            recommendations.append("Plan staff training for new requirements")

        # Stage-specific recommendations
        if stage_transition and stage_transition.passage_likelihood >= 0.8:
            recommendations.append("Monitor for final passage and signing")
            recommendations.append("Prepare for implementation")

        # General recommendations based on severity
        if change_classification.severity == ChangeSeverity.CRITICAL:
            recommendations.append("Escalate to executive leadership")
        elif change_classification.severity == ChangeSeverity.SIGNIFICANT:
            recommendations.append("Involve relevant department heads")

        return recommendations[:5]  # Limit to top 5 recommendations

    def _create_default_priority_result(self, error_message: str) -> PriorityResult:
        """Create a default priority result when calculation fails"""

        return PriorityResult(
            priority=AlertPriority.MEDIUM,
            confidence=0.3,
            reasoning=f"Priority calculation failed, defaulting to medium: {error_message}",
            priority_score=50.0,
            factors=PriorityFactors(
                reimbursement_impact=0.0,
                implementation_speed=0.0,
                passage_likelihood=0.0,
                bill_relevance=0.0,
                change_severity=0.5,
                regulatory_impact=0.0,
                time_sensitivity=0.0
            ),
            recommendations=["Review bill manually for impact assessment"]
        )

    def batch_prioritize_alerts(self, alert_data: List[Dict]) -> List[PriorityResult]:
        """Prioritize multiple alerts in batch"""

        results = []
        for data in alert_data:
            try:
                result = self.calculate_priority(
                    data['bill'],
                    data['change_classification'],
                    data.get('stage_transition'),
                    data.get('user_preferences')
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Error in batch prioritization: {e}")
                results.append(self._create_default_priority_result(str(e)))

        return results

    def get_priority_distribution(self, priority_results: List[PriorityResult]) -> Dict[str, int]:
        """Get distribution of priorities for analysis"""

        distribution = {
            'urgent': 0,
            'high': 0,
            'medium': 0,
            'low': 0
        }

        for result in priority_results:
            distribution[result.priority.value] += 1

        return distribution