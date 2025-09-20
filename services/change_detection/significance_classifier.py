import openai
import json
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from services.change_detection.diff_engine import DiffResult
from models.change_detection import ChangeSeverity, ChangeType
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

@dataclass
class ChangeClassification:
    """Result of change significance classification"""
    severity: ChangeSeverity
    change_type: ChangeType
    confidence: float
    reasoning: str
    key_changes: List[str]
    impact_areas: List[str]
    reimbursement_impact: bool
    regulatory_impact: bool
    implementation_urgency: str  # immediate, short_term, long_term

class SignificanceClassifier:
    """AI-powered classifier for determining change significance"""

    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

        # SNF-specific impact keywords with weights
        self.impact_keywords = {
            # High impact - reimbursement
            "reimbursement": 1.0,
            "payment rate": 1.0,
            "prospective payment": 1.0,
            "pdpm": 1.0,
            "case mix": 0.9,
            "medicare rate": 1.0,
            "medicaid rate": 0.8,

            # High impact - quality
            "star rating": 0.9,
            "quality measure": 0.8,
            "cms five star": 0.9,
            "survey": 0.8,
            "deficiency": 0.9,
            "penalty": 1.0,

            # High impact - staffing
            "staffing requirement": 1.0,
            "minimum staffing": 1.0,
            "nurse staffing": 0.9,
            "cna requirement": 0.8,
            "rn hour": 0.9,

            # Medium impact - operational
            "quality reporting": 0.7,
            "documentation": 0.6,
            "assessment": 0.7,
            "discharge planning": 0.6,
            "care planning": 0.6,

            # Medium impact - compliance
            "infection control": 0.7,
            "medication management": 0.7,
            "resident rights": 0.6,
            "privacy": 0.5,
            "hipaa": 0.6,

            # Lower impact - administrative
            "reporting requirement": 0.5,
            "notice requirement": 0.4,
            "record keeping": 0.4,
            "training": 0.5,
        }

        self.stage_priorities = {
            "introduced": 0.3,
            "committee": 0.5,
            "committee_passed": 0.7,
            "floor_vote": 0.8,
            "passed_chamber": 0.9,
            "conference": 0.9,
            "final_passage": 1.0,
            "signed": 1.0
        }

    def classify_change(self, diff_result: DiffResult, bill_context: Dict[str, Any],
                       old_status: str = "", new_status: str = "") -> ChangeClassification:
        """Classify the significance of a bill change"""

        try:
            # Determine change type
            change_type = self._determine_change_type(diff_result, old_status, new_status)

            # Get AI classification
            ai_classification = self._get_ai_classification(diff_result, bill_context, change_type)

            # Combine with rule-based classification
            rule_based_severity = self._rule_based_classification(diff_result, bill_context)

            # Final severity decision
            final_severity = self._combine_classifications(ai_classification.get('severity'), rule_based_severity)

            # Extract other details
            confidence = min(ai_classification.get('confidence', 0.7), 1.0)
            reasoning = ai_classification.get('reasoning', 'Automated classification')
            key_changes = ai_classification.get('key_changes', diff_result.significant_changes)
            impact_areas = ai_classification.get('impact_areas', [])

            # Determine specific impacts
            reimbursement_impact = self._has_reimbursement_impact(diff_result, bill_context)
            regulatory_impact = self._has_regulatory_impact(diff_result, bill_context)
            implementation_urgency = self._assess_implementation_urgency(diff_result, bill_context)

            return ChangeClassification(
                severity=final_severity,
                change_type=change_type,
                confidence=confidence,
                reasoning=reasoning,
                key_changes=key_changes[:5],  # Limit to top 5
                impact_areas=impact_areas,
                reimbursement_impact=reimbursement_impact,
                regulatory_impact=regulatory_impact,
                implementation_urgency=implementation_urgency
            )

        except Exception as e:
            logger.error(f"Error in change classification: {e}")
            # Return conservative fallback classification
            return ChangeClassification(
                severity=ChangeSeverity.MODERATE,
                change_type=ChangeType.TEXT_AMENDMENT,
                confidence=0.5,
                reasoning=f"Error in classification, defaulted to moderate: {str(e)}",
                key_changes=diff_result.significant_changes[:3],
                impact_areas=["unknown"],
                reimbursement_impact=False,
                regulatory_impact=False,
                implementation_urgency="long_term"
            )

    def _determine_change_type(self, diff_result: DiffResult, old_status: str, new_status: str) -> ChangeType:
        """Determine the primary type of change"""
        if old_status != new_status:
            return ChangeType.STATUS_CHANGE

        if len(diff_result.sections_changed) > 0:
            return ChangeType.TEXT_AMENDMENT

        return ChangeType.TEXT_AMENDMENT

    def _get_ai_classification(self, diff_result: DiffResult, bill_context: Dict[str, Any],
                              change_type: ChangeType) -> Dict[str, Any]:
        """Get AI-powered classification of change significance"""

        try:
            # Prepare context for AI
            context = self._prepare_ai_context(diff_result, bill_context, change_type)

            prompt = f"""Analyze this bill change for a skilled nursing facility (SNF) legislation tracker.

BILL CONTEXT:
{context}

CHANGE DETAILS:
- Change Summary: {diff_result.summary}
- Significant Changes: {', '.join(diff_result.significant_changes[:5])}
- Sections Changed: {', '.join(diff_result.sections_changed[:3])}
- Change Percentage: {diff_result.change_percentage:.1f}%

Classify this change and return JSON with:
1. severity: "minor", "moderate", "significant", or "critical"
2. confidence: float 0-1
3. reasoning: brief explanation
4. key_changes: list of top 3 most important changes
5. impact_areas: list of areas affected (e.g., "reimbursement", "quality", "staffing", "compliance")
6. financial_impact: boolean - affects SNF payments/costs
7. timeline_impact: "immediate", "short_term" (1-6 months), or "long_term" (6+ months)

Focus on SNF operational and financial impacts. Consider:
- Payment rate changes (CRITICAL)
- Staffing requirements (SIGNIFICANT)
- Quality measures (SIGNIFICANT)
- Compliance requirements (MODERATE-SIGNIFICANT)
- Administrative changes (MINOR-MODERATE)

Return only JSON, no other text."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Use faster model for classification
                messages=[
                    {"role": "system", "content": "You are an expert in healthcare legislation analysis, specifically for skilled nursing facilities. Provide accurate, concise classification of bill changes."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Low temperature for consistent classification
                max_tokens=500
            )

            result_text = response.choices[0].message.content.strip()

            # Clean JSON if wrapped in markdown
            if result_text.startswith('```json'):
                result_text = result_text[7:-3].strip()
            elif result_text.startswith('```'):
                result_text = result_text[3:-3].strip()

            result = json.loads(result_text)
            logger.info(f"AI classification: {result.get('severity')} (confidence: {result.get('confidence', 0):.2f})")

            return result

        except Exception as e:
            logger.error(f"AI classification failed: {e}")
            return {
                'severity': 'moderate',
                'confidence': 0.3,
                'reasoning': f'AI classification failed: {str(e)}',
                'key_changes': diff_result.significant_changes[:3],
                'impact_areas': ['unknown']
            }

    def _rule_based_classification(self, diff_result: DiffResult, bill_context: Dict[str, Any]) -> ChangeSeverity:
        """Rule-based classification as fallback/supplement"""

        # Combine all text for keyword analysis
        all_text = ' '.join([
            diff_result.summary,
            ' '.join(diff_result.significant_changes),
            ' '.join(diff_result.minor_changes),
            bill_context.get('title', ''),
            bill_context.get('summary', '')
        ]).lower()

        # Calculate weighted impact score
        impact_score = 0.0
        matched_keywords = []

        for keyword, weight in self.impact_keywords.items():
            if keyword.lower() in all_text:
                impact_score += weight
                matched_keywords.append(keyword)

        logger.info(f"Rule-based impact score: {impact_score:.2f} (keywords: {matched_keywords[:3]})")

        # Adjust for change magnitude
        magnitude_multiplier = min(diff_result.change_percentage / 100.0, 1.0)
        final_score = impact_score * (0.5 + 0.5 * magnitude_multiplier)

        # Classification thresholds
        if final_score >= 2.0:
            return ChangeSeverity.CRITICAL
        elif final_score >= 1.0:
            return ChangeSeverity.SIGNIFICANT
        elif final_score >= 0.3:
            return ChangeSeverity.MODERATE
        else:
            return ChangeSeverity.MINOR

    def _combine_classifications(self, ai_severity: str, rule_severity: ChangeSeverity) -> ChangeSeverity:
        """Combine AI and rule-based classifications"""

        # Convert AI severity to enum
        severity_map = {
            'critical': ChangeSeverity.CRITICAL,
            'significant': ChangeSeverity.SIGNIFICANT,
            'moderate': ChangeSeverity.MODERATE,
            'minor': ChangeSeverity.MINOR
        }

        ai_enum = severity_map.get(ai_severity, ChangeSeverity.MODERATE)

        # Take the higher severity (more conservative approach)
        severity_order = [ChangeSeverity.MINOR, ChangeSeverity.MODERATE,
                         ChangeSeverity.SIGNIFICANT, ChangeSeverity.CRITICAL]

        ai_level = severity_order.index(ai_enum)
        rule_level = severity_order.index(rule_severity)

        return severity_order[max(ai_level, rule_level)]

    def _prepare_ai_context(self, diff_result: DiffResult, bill_context: Dict[str, Any],
                          change_type: ChangeType) -> str:
        """Prepare context information for AI analysis"""

        context_parts = [
            f"Bill: {bill_context.get('bill_number', 'Unknown')}",
            f"Title: {bill_context.get('title', 'Unknown')[:100]}...",
            f"Source: {bill_context.get('source', 'Unknown')}",
            f"Current Status: {bill_context.get('status', 'Unknown')}",
            f"Relevance Score: {bill_context.get('relevance_score', 'Unknown')}/100"
        ]

        if bill_context.get('summary'):
            context_parts.append(f"Summary: {bill_context['summary'][:200]}...")

        return '\n'.join(context_parts)

    def _has_reimbursement_impact(self, diff_result: DiffResult, bill_context: Dict[str, Any]) -> bool:
        """Determine if changes affect SNF reimbursement"""
        reimbursement_terms = [
            'payment', 'reimbursement', 'rate', 'pdpm', 'prospective payment',
            'medicare', 'medicaid', 'case mix', 'snf pps', 'wage index'
        ]

        all_text = (diff_result.summary + ' ' + ' '.join(diff_result.significant_changes) +
                   ' ' + bill_context.get('title', '') + ' ' + bill_context.get('summary', '')).lower()

        return any(term in all_text for term in reimbursement_terms)

    def _has_regulatory_impact(self, diff_result: DiffResult, bill_context: Dict[str, Any]) -> bool:
        """Determine if changes affect SNF regulatory requirements"""
        regulatory_terms = [
            'requirement', 'mandate', 'must', 'shall', 'prohibited', 'compliance',
            'survey', 'inspection', 'deficiency', 'penalty', 'certification',
            'quality measure', 'staffing requirement', 'standard of care'
        ]

        all_text = (diff_result.summary + ' ' + ' '.join(diff_result.significant_changes) +
                   ' ' + bill_context.get('title', '') + ' ' + bill_context.get('summary', '')).lower()

        return any(term in all_text for term in regulatory_terms)

    def _assess_implementation_urgency(self, diff_result: DiffResult, bill_context: Dict[str, Any]) -> str:
        """Assess how urgently changes need to be implemented"""

        # Check for immediate implementation keywords
        immediate_terms = ['immediate', 'effective immediately', 'upon passage', 'within 30 days']
        short_term_terms = ['within 6 months', 'fiscal year', 'by january', 'by october']

        all_text = (diff_result.summary + ' ' + ' '.join(diff_result.significant_changes) +
                   ' ' + bill_context.get('title', '') + ' ' + bill_context.get('summary', '')).lower()

        if any(term in all_text for term in immediate_terms):
            return "immediate"
        elif any(term in all_text for term in short_term_terms):
            return "short_term"
        else:
            return "long_term"

    def classify_stage_transition(self, from_stage: str, to_stage: str,
                                bill_context: Dict[str, Any]) -> ChangeClassification:
        """Classify the significance of a stage transition"""

        # Calculate transition importance
        from_priority = self.stage_priorities.get(from_stage.lower(), 0.3)
        to_priority = self.stage_priorities.get(to_stage.lower(), 0.3)
        transition_significance = to_priority - from_priority

        # Determine severity based on transition
        if to_priority >= 0.9:  # Near passage or passed
            severity = ChangeSeverity.CRITICAL
        elif to_priority >= 0.7:  # Significant progress
            severity = ChangeSeverity.SIGNIFICANT
        elif transition_significance >= 0.2:  # Notable progress
            severity = ChangeSeverity.MODERATE
        else:
            severity = ChangeSeverity.MINOR

        # Assess impact based on bill relevance
        relevance_score = bill_context.get('relevance_score', 0)
        if relevance_score >= 70 and to_priority >= 0.7:
            # High relevance bill making significant progress
            severity = ChangeSeverity.CRITICAL

        reasoning = f"Bill transitioned from {from_stage} to {to_stage}. " \
                   f"Relevance: {relevance_score}/100. Passage likelihood increased to {to_priority:.0%}."

        return ChangeClassification(
            severity=severity,
            change_type=ChangeType.STAGE_TRANSITION,
            confidence=0.9,  # High confidence in stage classifications
            reasoning=reasoning,
            key_changes=[f"Stage transition: {from_stage} → {to_stage}"],
            impact_areas=["legislative_progress"],
            reimbursement_impact=self._has_reimbursement_impact_from_context(bill_context),
            regulatory_impact=self._has_regulatory_impact_from_context(bill_context),
            implementation_urgency="short_term" if to_priority >= 0.8 else "long_term"
        )

    def _has_reimbursement_impact_from_context(self, bill_context: Dict[str, Any]) -> bool:
        """Check if bill context suggests reimbursement impact"""
        text = (bill_context.get('title', '') + ' ' + bill_context.get('summary', '')).lower()
        reimbursement_terms = ['payment', 'reimbursement', 'rate', 'medicare', 'medicaid']
        return any(term in text for term in reimbursement_terms)

    def _has_regulatory_impact_from_context(self, bill_context: Dict[str, Any]) -> bool:
        """Check if bill context suggests regulatory impact"""
        text = (bill_context.get('title', '') + ' ' + bill_context.get('summary', '')).lower()
        regulatory_terms = ['requirement', 'compliance', 'standard', 'quality', 'staffing']
        return any(term in text for term in regulatory_terms)