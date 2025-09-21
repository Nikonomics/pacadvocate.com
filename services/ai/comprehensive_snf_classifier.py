#!/usr/bin/env python3
"""
Comprehensive SNF Relevance Classification System
Combines direct SNF detection, Medicare Advantage impact, and indirect SNF impacts
"""

import logging
from typing import Dict, List, Tuple, NamedTuple, Optional
from dataclasses import dataclass

# Import our specialized systems
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from enhanced_relevance_classifier import EnhancedSNFRelevanceClassifier, RelevanceResult
from snf_impact_detector import SNFImpactDetector, ImpactResult

logger = logging.getLogger(__name__)

@dataclass
class ComprehensiveResult:
    """Complete SNF relevance analysis result"""
    final_score: float
    primary_category: str
    secondary_category: str
    confidence: float
    explanation: str
    ma_impact: bool
    indirect_impact: bool
    monitoring_priority: str
    context_notes: List[str]
    specific_impacts: List[str]
    recommended_actions: List[str]

class ComprehensiveSNFClassifier:
    """Comprehensive SNF legislation classification system"""

    def __init__(self):
        """Initialize the comprehensive classifier"""
        self.direct_classifier = EnhancedSNFRelevanceClassifier()
        self.impact_detector = SNFImpactDetector()

        # Priority scoring weights
        self.scoring_weights = {
            'direct_snf': 1.0,        # Direct SNF bills get full weight
            'ma_impact': 0.9,         # MA bills get 90% weight
            'indirect_critical': 0.8,  # Critical indirect impacts get 80%
            'indirect_moderate': 0.7,  # Moderate indirect impacts get 70%
            'indirect_minimal': 0.5    # Minimal indirect impacts get 50%
        }

        # Monitoring priority matrix
        self.priority_matrix = {
            ('direct_snf', 'High'): 'Critical',
            ('direct_snf', 'Moderate'): 'High',
            ('ma_payment', 'High'): 'Critical',
            ('ma_payment', 'Moderate'): 'High',
            ('payment_critical', 'High'): 'High',
            ('competition_direct', 'High'): 'High',
            ('workforce_critical', 'High'): 'High',
        }

        logger.info("Comprehensive SNF Classifier initialized")

    def analyze_comprehensive_relevance(self, title: str, summary: str = "", full_text: str = "") -> ComprehensiveResult:
        """
        Perform comprehensive SNF relevance analysis

        Args:
            title: Bill title
            summary: Bill summary
            full_text: Full bill text

        Returns:
            ComprehensiveResult with complete analysis
        """
        if not title:
            return self._create_empty_result("No title provided")

        # Run direct/MA classification
        direct_result = self.direct_classifier.analyze_relevance(title, summary, full_text)

        # Run indirect impact detection
        indirect_result = self.impact_detector.analyze_snf_impact(title, summary, full_text)

        # Determine primary classification
        primary_category, secondary_category = self._determine_categories(direct_result, indirect_result)

        # Calculate final score
        final_score = self._calculate_final_score(direct_result, indirect_result, primary_category)

        # Determine monitoring priority
        monitoring_priority = self._determine_priority(primary_category, direct_result, indirect_result)

        # Build comprehensive explanation
        explanation = self._build_explanation(direct_result, indirect_result, primary_category, final_score)

        # Collect all context notes and impacts
        context_notes = direct_result.context_notes.copy()
        if indirect_result.has_impact and indirect_result.specific_impacts:
            context_notes.extend(indirect_result.specific_impacts)

        # Generate recommended actions
        recommended_actions = self._generate_recommendations(primary_category, final_score, direct_result, indirect_result)

        # Determine confidence
        confidence = max(direct_result.confidence, indirect_result.confidence if indirect_result.has_impact else 0.5)

        return ComprehensiveResult(
            final_score=final_score,
            primary_category=primary_category,
            secondary_category=secondary_category,
            confidence=confidence,
            explanation=explanation,
            ma_impact=direct_result.ma_impact,
            indirect_impact=indirect_result.has_impact,
            monitoring_priority=monitoring_priority,
            context_notes=context_notes,
            specific_impacts=indirect_result.specific_impacts if indirect_result.has_impact else [],
            recommended_actions=recommended_actions
        )

    def _determine_categories(self, direct_result: RelevanceResult, indirect_result: ImpactResult) -> Tuple[str, str]:
        """Determine primary and secondary categories"""

        # Direct SNF legislation takes priority
        if direct_result.category == 'direct_snf':
            return 'direct_snf', indirect_result.impact_category if indirect_result.has_impact else 'none'

        # Medicare Advantage with high scores takes priority
        if direct_result.ma_impact and direct_result.score >= 60:
            return direct_result.category, indirect_result.impact_category if indirect_result.has_impact else 'none'

        # High indirect impact takes priority over low direct scores
        if indirect_result.has_impact and indirect_result.relevance_score >= 60 and direct_result.score < 50:
            return indirect_result.impact_category, direct_result.category

        # Medicare Advantage impact detected
        if direct_result.ma_impact:
            return direct_result.category, indirect_result.impact_category if indirect_result.has_impact else 'none'

        # Indirect impact detected
        if indirect_result.has_impact and indirect_result.relevance_score >= 40:
            return indirect_result.impact_category, direct_result.category

        # Default to direct classification
        return direct_result.category, indirect_result.impact_category if indirect_result.has_impact else 'none'

    def _calculate_final_score(self, direct_result: RelevanceResult, indirect_result: ImpactResult, primary_category: str) -> float:
        """Calculate final relevance score combining both analyses"""

        direct_score = direct_result.score
        indirect_score = indirect_result.relevance_score if indirect_result.has_impact else 0

        # Determine scoring approach based on primary category
        if primary_category == 'direct_snf':
            # Direct SNF: use direct score plus indirect boost
            base_score = direct_score
            boost = min(indirect_score * 0.2, 15)  # Up to 15 point boost
            final_score = min(base_score + boost, 100)

        elif primary_category.startswith('ma_'):
            # MA impact: use direct score plus indirect considerations
            base_score = direct_score
            boost = min(indirect_score * 0.15, 10)  # Up to 10 point boost
            final_score = min(base_score + boost, 95)

        elif primary_category in ['payment_critical', 'competition_direct', 'workforce_critical']:
            # Critical indirect impact: use indirect score plus direct considerations
            base_score = indirect_score
            boost = min(direct_score * 0.25, 15)  # Up to 15 point boost from direct
            final_score = min(base_score + boost, 85)

        elif indirect_result.has_impact:
            # Moderate indirect impact: weighted average
            weight_indirect = 0.7
            weight_direct = 0.3
            final_score = (indirect_score * weight_indirect) + (direct_score * weight_direct)

        else:
            # No indirect impact: use direct score
            final_score = direct_score

        return round(final_score, 1)

    def _determine_priority(self, primary_category: str, direct_result: RelevanceResult, indirect_result: ImpactResult) -> str:
        """Determine monitoring priority"""

        # Critical priorities
        if primary_category == 'direct_snf' and direct_result.score >= 85:
            return 'Critical'
        if primary_category == 'ma_payment' and direct_result.score >= 75:
            return 'Critical'
        if primary_category == 'payment_critical':
            return 'Critical'

        # High priorities
        if primary_category == 'direct_snf' and direct_result.score >= 70:
            return 'High'
        if direct_result.ma_impact and direct_result.score >= 60:
            return 'High'
        if primary_category in ['competition_direct', 'workforce_critical']:
            return 'High'

        # Moderate priorities
        if primary_category.startswith('ma_') or indirect_result.has_impact:
            return 'Moderate'

        # Low priority
        return 'Low'

    def _build_explanation(self, direct_result: RelevanceResult, indirect_result: ImpactResult,
                          primary_category: str, final_score: float) -> str:
        """Build comprehensive explanation"""

        explanations = []

        # Primary classification explanation
        if primary_category == 'direct_snf':
            explanations.append(f"Direct SNF legislation (Score: {final_score:.1f}/100)")
            explanations.append("Explicitly addresses skilled nursing facilities")
        elif primary_category.startswith('ma_'):
            explanations.append(f"Medicare Advantage impact (Score: {final_score:.1f}/100)")
            explanations.append("Affects SNF operations through MA plans (30-40% of SNF revenue)")
        elif primary_category == 'payment_critical':
            explanations.append(f"Critical payment impact (Score: {final_score:.1f}/100)")
            explanations.append("Affects SNF cash flow and financial operations")
        elif primary_category == 'competition_direct':
            explanations.append(f"Direct competitive impact (Score: {final_score:.1f}/100)")
            explanations.append("Changes affect SNF referral patterns and census")
        elif primary_category == 'workforce_critical':
            explanations.append(f"Critical workforce impact (Score: {final_score:.1f}/100)")
            explanations.append("SNFs face severe staffing shortages - workforce changes have major impact")

        # Add secondary impacts
        if indirect_result.has_impact and primary_category != indirect_result.impact_category:
            explanations.append(f"Additional {indirect_result.impact_category.replace('_', ' ')} detected")

        return " | ".join(explanations)

    def _generate_recommendations(self, primary_category: str, final_score: float,
                                 direct_result: RelevanceResult, indirect_result: ImpactResult) -> List[str]:
        """Generate recommended actions based on classification"""

        recommendations = []

        if primary_category == 'direct_snf' and final_score >= 85:
            recommendations.extend([
                "Monitor implementation timeline closely",
                "Assess impact on facility operations and compliance",
                "Prepare staff training if needed"
            ])

        elif primary_category == 'ma_payment' and final_score >= 75:
            recommendations.extend([
                "Track progress through relevant committees",
                "Assess impact on cash flow and working capital",
                "Monitor industry association advocacy efforts"
            ])

        elif primary_category == 'payment_critical':
            recommendations.extend([
                "Monitor for SNF-specific impacts",
                "Track payment timing requirements",
                "Assess cash flow implications"
            ])

        elif primary_category == 'competition_direct':
            recommendations.extend([
                "Monitor competitor payment rate changes",
                "Assess impact on referral patterns",
                "Review market positioning strategy"
            ])

        elif primary_category == 'workforce_critical':
            recommendations.extend([
                "Assess staffing recruitment impacts",
                "Monitor wage and benefit implications",
                "Review workforce development opportunities"
            ])

        elif final_score >= 50:
            recommendations.extend([
                "Quarterly monitoring sufficient",
                "Watch for SNF-specific amendments",
                "Monitor industry impact assessments"
            ])

        else:
            recommendations.append("Low priority - annual review adequate")

        return recommendations

    def _create_empty_result(self, reason: str) -> ComprehensiveResult:
        """Create empty result for invalid input"""
        return ComprehensiveResult(
            final_score=0.0,
            primary_category='invalid',
            secondary_category='none',
            confidence=0.1,
            explanation=reason,
            ma_impact=False,
            indirect_impact=False,
            monitoring_priority='None',
            context_notes=[],
            specific_impacts=[],
            recommended_actions=[]
        )

    def batch_analyze(self, bills: List[Dict]) -> List[ComprehensiveResult]:
        """Analyze multiple bills comprehensively"""
        results = []

        for bill in bills:
            try:
                result = self.analyze_comprehensive_relevance(
                    title=bill.get('title', ''),
                    summary=bill.get('summary', ''),
                    full_text=bill.get('full_text', '')
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Error analyzing bill {bill.get('title', 'Unknown')}: {e}")
                results.append(self._create_empty_result(f'Analysis error: {str(e)}'))

        return results

    def get_classification_summary(self) -> Dict:
        """Return summary of classification capabilities"""
        return {
            'direct_detection': {
                'capabilities': ['Explicit SNF mentions', 'SNF payment systems', 'Quality programs'],
                'score_range': '85-100',
                'priority': 'Critical-High'
            },
            'ma_impact_detection': {
                'capabilities': ['Payment timing', 'Prior authorization', 'Network adequacy', 'Quality programs'],
                'score_range': '45-95',
                'priority': 'Critical-Moderate',
                'revenue_context': '30-40% of SNF revenue from MA plans'
            },
            'indirect_impact_detection': {
                'capabilities': ['Payment/cash flow', 'Competition', 'Workforce', 'Regulatory'],
                'score_range': '30-85',
                'priority': 'High-Moderate',
                'context': 'Identifies bills that affect SNFs without mentioning them'
            }
        }


def test_comprehensive_classifier():
    """Test the comprehensive classification system"""
    classifier = ComprehensiveSNFClassifier()

    test_bills = [
        {
            'title': 'Medicare Program; Prospective Payment System and Consolidated Billing for Skilled Nursing Facilities',
            'summary': 'Updates SNF payment rates and quality reporting requirements',
            'expected': 'direct_snf'
        },
        {
            'title': 'A bill to require prompt payment by Medicare Advantage organizations',
            'summary': 'Establishes 30-day payment requirements for Medicare Advantage plans to pay providers',
            'expected': 'ma_payment'
        },
        {
            'title': 'Long-Term Care Hospital Payment System Reform Act',
            'summary': 'Modifies LTCH payment criteria and rates for complex patients',
            'expected': 'competition_direct'
        },
        {
            'title': 'Healthcare Worker Visa Relief Act',
            'summary': 'Provides immigration relief for foreign healthcare workers including nurses',
            'expected': 'workforce_critical'
        },
        {
            'title': 'Highway Infrastructure Investment Act',
            'summary': 'Provides federal funding for highway and bridge repairs',
            'expected': 'minimal_impact'
        }
    ]

    print("🔍 Testing Comprehensive SNF Classification System")
    print("=" * 60)

    for i, bill in enumerate(test_bills, 1):
        result = classifier.analyze_comprehensive_relevance(bill['title'], bill['summary'])

        print(f"\n{i}. {bill['title'][:50]}...")
        print(f"   Final Score: {result.final_score:.1f}/100")
        print(f"   Primary Category: {result.primary_category}")
        if result.secondary_category != 'none':
            print(f"   Secondary Category: {result.secondary_category}")
        print(f"   MA Impact: {'YES' if result.ma_impact else 'NO'}")
        print(f"   Indirect Impact: {'YES' if result.indirect_impact else 'NO'}")
        print(f"   Priority: {result.monitoring_priority}")
        print(f"   Expected: {bill['expected']}")
        print(f"   Explanation: {result.explanation}")
        if result.recommended_actions:
            print(f"   Actions: {', '.join(result.recommended_actions[:2])}")

    print(f"\n✅ Comprehensive SNF Classification System test completed!")


if __name__ == "__main__":
    test_comprehensive_classifier()