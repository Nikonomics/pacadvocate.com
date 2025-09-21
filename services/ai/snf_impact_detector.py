#!/usr/bin/env python3
"""
SNF Impact Detection System
Identifies indirect effects on skilled nursing facilities from legislation
"""

import re
import logging
from typing import Dict, List, Tuple, NamedTuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ImpactResult:
    """Result from SNF impact analysis"""
    has_impact: bool
    impact_category: str
    relevance_score: float
    confidence: float
    explanation: str
    specific_impacts: List[str]
    monitoring_priority: str

class SNFImpactDetector:
    """Detects indirect SNF impacts from various types of legislation"""

    def __init__(self):
        """Initialize the impact detection system"""

        # Payment & Financial Impact Keywords
        self.payment_keywords = {
            'cash_flow_critical': [
                'prompt payment', 'payment timeline', 'payment delay', 'payment processing',
                'claims payment', 'reimbursement schedule', 'payment terms',
                'account receivable', 'collection timeline', 'payment acceleration'
            ],
            'bridge_financing': [
                'bridge financing', 'credit facility', 'line of credit', 'working capital',
                'receivables financing', 'factoring', 'cash advance', 'credit line',
                'short-term financing', 'interim financing'
            ],
            'medicare_payment': [
                'Medicare payment', 'Medicare reimbursement', 'Part A payment',
                'Medicare rate', 'CMS payment', 'federal reimbursement'
            ],
            'medicaid_payment': [
                'Medicaid payment', 'Medicaid reimbursement', 'state Medicaid',
                'Medicaid rate', 'Medicaid funding', 'state reimbursement'
            ]
        }

        # Competition & Market Impact Keywords
        self.competition_keywords = {
            'ltch_competition': [
                'long-term care hospital', 'LTCH', 'long term acute care',
                'LTAC', 'specialty hospital', 'long-stay hospital'
            ],
            'irf_competition': [
                'inpatient rehabilitation facility', 'IRF', 'rehabilitation hospital',
                'inpatient rehab', 'rehab facility', 'rehabilitation services'
            ],
            'home_health_competition': [
                'home health', 'home healthcare', 'home-based care',
                'community-based care', 'home care services', 'visiting nurse'
            ],
            'hospital_discharge': [
                'discharge planning', 'post-acute care', 'transition of care',
                'care coordination', 'hospital readmission', 'length of stay'
            ]
        }

        # Workforce & Staffing Impact Keywords
        self.workforce_keywords = {
            'healthcare_staffing': [
                'healthcare worker', 'nurse shortage', 'nursing shortage',
                'healthcare staffing', 'medical staffing', 'clinical staff',
                'certified nursing assistant', 'CNA', 'licensed practical nurse', 'LPN'
            ],
            'immigration_healthcare': [
                'healthcare immigration', 'foreign nurse', 'visa healthcare',
                'immigrant healthcare worker', 'H1-B healthcare', 'international nurse',
                'foreign healthcare professional'
            ],
            'workforce_development': [
                'workforce development', 'job training healthcare', 'nursing education',
                'healthcare training', 'clinical training', 'apprenticeship healthcare'
            ],
            'minimum_wage': [
                'minimum wage', 'wage increase', 'living wage', 'hourly wage',
                'pay raise', 'wage floor', 'salary increase'
            ]
        }

        # Quality & Regulatory Impact Keywords
        self.regulatory_keywords = {
            'quality_measures': [
                'quality reporting', 'patient safety', 'quality measures',
                'performance measures', 'outcome measures', 'quality indicators'
            ],
            'infection_control': [
                'infection control', 'infection prevention', 'antimicrobial',
                'antibiotic resistance', 'hospital-acquired infection', 'nosocomial'
            ],
            'emergency_preparedness': [
                'emergency preparedness', 'disaster planning', 'pandemic response',
                'emergency response', 'public health emergency'
            ]
        }

        # Impact scoring matrix
        self.impact_scores = {
            'payment_critical': {'base': 75, 'max': 95, 'priority': 'High'},
            'payment_moderate': {'base': 55, 'max': 75, 'priority': 'Moderate'},
            'competition_direct': {'base': 65, 'max': 85, 'priority': 'High'},
            'competition_indirect': {'base': 45, 'max': 65, 'priority': 'Moderate'},
            'workforce_critical': {'base': 60, 'max': 80, 'priority': 'High'},
            'workforce_moderate': {'base': 40, 'max': 60, 'priority': 'Moderate'},
            'regulatory_impact': {'base': 35, 'max': 55, 'priority': 'Moderate'},
            'minimal_impact': {'base': 15, 'max': 35, 'priority': 'Low'}
        }

        # SNF business context explanations
        self.snf_context = {
            'cash_flow': "SNFs operate on thin margins with 60-90 day payment cycles. Payment delays create immediate cash flow crises requiring expensive bridge financing.",
            'ltch_competition': "LTCHs compete directly with SNFs for complex, high-acuity patients. LTCH payment changes affect referral patterns and SNF census.",
            'irf_competition': "IRFs compete with SNFs for rehabilitation patients. Changes to IRF regulations affect which patients are referred to SNFs vs IRFs.",
            'home_health_competition': "Home health is a direct alternative to SNF care for many patients. Enhanced home health benefits reduce SNF admissions.",
            'staffing_shortage': "SNFs face severe staffing shortages with turnover rates of 75-100%. Any healthcare workforce changes significantly impact SNF operations.",
            'immigration_workforce': "SNFs rely heavily on immigrant healthcare workers, especially CNAs and LPNs. Immigration policy changes directly affect staffing ability.",
            'minimum_wage_impact': "Healthcare workers represent 60-70% of SNF costs. Wage increases have direct impact on operating margins.",
            'quality_reporting': "SNFs are subject to extensive quality reporting. New requirements create administrative burden and potential penalties."
        }

    def analyze_snf_impact(self, title: str, summary: str = "", full_text: str = "") -> ImpactResult:
        """
        Analyze legislation for indirect SNF impacts

        Args:
            title: Bill title
            summary: Bill summary
            full_text: Full bill text

        Returns:
            ImpactResult with impact assessment
        """
        combined_text = f"{title} {summary} {full_text}".lower()

        if not combined_text.strip():
            return ImpactResult(
                has_impact=False,
                impact_category="no_content",
                relevance_score=0.0,
                confidence=0.1,
                explanation="No content to analyze",
                specific_impacts=[],
                monitoring_priority="None"
            )

        # Analyze each impact category
        payment_impact = self._analyze_payment_impact(combined_text)
        competition_impact = self._analyze_competition_impact(combined_text)
        workforce_impact = self._analyze_workforce_impact(combined_text)
        regulatory_impact = self._analyze_regulatory_impact(combined_text)

        # Determine highest impact
        impacts = [payment_impact, competition_impact, workforce_impact, regulatory_impact]
        impacts.sort(key=lambda x: x['score'], reverse=True)

        top_impact = impacts[0]

        if top_impact['score'] < 30:
            return ImpactResult(
                has_impact=False,
                impact_category="minimal_impact",
                relevance_score=top_impact['score'],
                confidence=0.6,
                explanation="Minimal indirect SNF impact detected",
                specific_impacts=[],
                monitoring_priority="Low"
            )

        # Build comprehensive result
        all_specific_impacts = []
        for impact in impacts:
            all_specific_impacts.extend(impact['specifics'])

        return ImpactResult(
            has_impact=True,
            impact_category=top_impact['category'],
            relevance_score=top_impact['score'],
            confidence=top_impact['confidence'],
            explanation=top_impact['explanation'],
            specific_impacts=all_specific_impacts[:5],  # Top 5 impacts
            monitoring_priority=top_impact['priority']
        )

    def _analyze_payment_impact(self, text: str) -> Dict:
        """Analyze payment and financial impact"""
        score = 0
        specifics = []

        # Cash flow critical keywords
        for keyword in self.payment_keywords['cash_flow_critical']:
            if keyword in text:
                score += 15
                specifics.append(f"Payment timing: {keyword}")

        # Bridge financing keywords
        for keyword in self.payment_keywords['bridge_financing']:
            if keyword in text:
                score += 12
                specifics.append(f"Bridge financing: {keyword}")

        # Medicare payment keywords
        for keyword in self.payment_keywords['medicare_payment']:
            if keyword in text:
                score += 10
                specifics.append(f"Medicare payment: {keyword}")

        # Medicaid payment keywords
        for keyword in self.payment_keywords['medicaid_payment']:
            if keyword in text:
                score += 8
                specifics.append(f"Medicaid payment: {keyword}")

        if score >= 25:
            category = 'payment_critical'
            explanation = f"Critical payment impact (Score: {score}). {self.snf_context['cash_flow']}"
            confidence = 0.9
        elif score >= 15:
            category = 'payment_moderate'
            explanation = f"Moderate payment impact (Score: {score}). May affect SNF financial operations."
            confidence = 0.7
        else:
            category = 'minimal_impact'
            explanation = f"Minimal payment impact (Score: {score})."
            confidence = 0.6

        config = self.impact_scores.get(category, self.impact_scores['minimal_impact'])
        final_score = min(score * 2, config['max'])  # Scale up but cap at max

        return {
            'category': category,
            'score': final_score,
            'confidence': confidence,
            'explanation': explanation,
            'specifics': specifics,
            'priority': config['priority']
        }

    def _analyze_competition_impact(self, text: str) -> Dict:
        """Analyze competitive impact from other post-acute providers"""
        score = 0
        specifics = []

        # LTCH competition (direct)
        for keyword in self.competition_keywords['ltch_competition']:
            if keyword in text:
                score += 12
                specifics.append(f"LTCH competition: {keyword}")

        # IRF competition (direct)
        for keyword in self.competition_keywords['irf_competition']:
            if keyword in text:
                score += 10
                specifics.append(f"IRF competition: {keyword}")

        # Home health competition
        for keyword in self.competition_keywords['home_health_competition']:
            if keyword in text:
                score += 8
                specifics.append(f"Home health alternative: {keyword}")

        # Hospital discharge patterns
        for keyword in self.competition_keywords['hospital_discharge']:
            if keyword in text:
                score += 6
                specifics.append(f"Discharge planning: {keyword}")

        if score >= 20:
            category = 'competition_direct'
            explanation = f"Direct competitive impact (Score: {score}). Changes affect SNF referral patterns and census."
            confidence = 0.8
        elif score >= 10:
            category = 'competition_indirect'
            explanation = f"Indirect competitive impact (Score: {score}). May influence patient flow to SNFs."
            confidence = 0.7
        else:
            category = 'minimal_impact'
            explanation = f"Minimal competitive impact (Score: {score})."
            confidence = 0.6

        config = self.impact_scores.get(category, self.impact_scores['minimal_impact'])
        final_score = min(score * 2.5, config['max'])

        return {
            'category': category,
            'score': final_score,
            'confidence': confidence,
            'explanation': explanation,
            'specifics': specifics,
            'priority': config['priority']
        }

    def _analyze_workforce_impact(self, text: str) -> Dict:
        """Analyze workforce and staffing impact"""
        score = 0
        specifics = []

        # Healthcare staffing (critical for SNFs)
        for keyword in self.workforce_keywords['healthcare_staffing']:
            if keyword in text:
                score += 15
                specifics.append(f"Healthcare staffing: {keyword}")

        # Immigration healthcare workers
        for keyword in self.workforce_keywords['immigration_healthcare']:
            if keyword in text:
                score += 12
                specifics.append(f"Immigration workforce: {keyword}")

        # Minimum wage (major cost driver)
        for keyword in self.workforce_keywords['minimum_wage']:
            if keyword in text:
                score += 10
                specifics.append(f"Wage impact: {keyword}")

        # Workforce development
        for keyword in self.workforce_keywords['workforce_development']:
            if keyword in text:
                score += 8
                specifics.append(f"Workforce development: {keyword}")

        if score >= 25:
            category = 'workforce_critical'
            explanation = f"Critical workforce impact (Score: {score}). {self.snf_context['staffing_shortage']}"
            confidence = 0.8
        elif score >= 15:
            category = 'workforce_moderate'
            explanation = f"Moderate workforce impact (Score: {score}). May affect SNF staffing and costs."
            confidence = 0.7
        else:
            category = 'minimal_impact'
            explanation = f"Minimal workforce impact (Score: {score})."
            confidence = 0.6

        config = self.impact_scores.get(category, self.impact_scores['minimal_impact'])
        final_score = min(score * 2, config['max'])

        return {
            'category': category,
            'score': final_score,
            'confidence': confidence,
            'explanation': explanation,
            'specifics': specifics,
            'priority': config['priority']
        }

    def _analyze_regulatory_impact(self, text: str) -> Dict:
        """Analyze regulatory and quality impact"""
        score = 0
        specifics = []

        # Quality measures
        for keyword in self.regulatory_keywords['quality_measures']:
            if keyword in text:
                score += 8
                specifics.append(f"Quality reporting: {keyword}")

        # Infection control
        for keyword in self.regulatory_keywords['infection_control']:
            if keyword in text:
                score += 10
                specifics.append(f"Infection control: {keyword}")

        # Emergency preparedness
        for keyword in self.regulatory_keywords['emergency_preparedness']:
            if keyword in text:
                score += 8
                specifics.append(f"Emergency preparedness: {keyword}")

        if score >= 15:
            category = 'regulatory_impact'
            explanation = f"Regulatory impact (Score: {score}). {self.snf_context['quality_reporting']}"
            confidence = 0.7
        else:
            category = 'minimal_impact'
            explanation = f"Minimal regulatory impact (Score: {score})."
            confidence = 0.6

        config = self.impact_scores.get(category, self.impact_scores['minimal_impact'])
        final_score = min(score * 2.5, config['max'])

        return {
            'category': category,
            'score': final_score,
            'confidence': confidence,
            'explanation': explanation,
            'specifics': specifics,
            'priority': config['priority']
        }

    def get_impact_categories(self) -> Dict:
        """Return all impact categories with descriptions"""
        return {
            'payment_critical': {
                'description': 'Critical payment/cash flow impact',
                'score_range': '75-95',
                'examples': 'Prompt payment requirements, Medicare payment delays',
                'snf_relevance': self.snf_context['cash_flow']
            },
            'competition_direct': {
                'description': 'Direct competition from other post-acute providers',
                'score_range': '65-85',
                'examples': 'LTCH payment changes, IRF regulation updates',
                'snf_relevance': 'Affects patient referral patterns and census'
            },
            'workforce_critical': {
                'description': 'Critical staffing and workforce impacts',
                'score_range': '60-80',
                'examples': 'Healthcare worker shortages, immigration policy',
                'snf_relevance': self.snf_context['staffing_shortage']
            },
            'regulatory_impact': {
                'description': 'Quality and regulatory requirements',
                'score_range': '35-55',
                'examples': 'New quality measures, infection control standards',
                'snf_relevance': self.snf_context['quality_reporting']
            }
        }


def test_snf_impact_detector():
    """Test the SNF impact detection system"""
    detector = SNFImpactDetector()

    test_bills = [
        {
            'title': 'A bill to require prompt payment by Medicare Advantage organizations to healthcare providers',
            'summary': 'Establishes 30-day payment requirements for all Medicare Advantage plans',
            'expected_impact': 'payment_critical'
        },
        {
            'title': 'Long-Term Care Hospital Prospective Payment System Updates for FY 2026',
            'summary': 'Updates payment rates for long-term care hospitals and modifies patient criteria',
            'expected_impact': 'competition_direct'
        },
        {
            'title': 'Healthcare Worker Shortage Relief Act',
            'summary': 'Provides visa relief for foreign healthcare workers including nurses and CNAs',
            'expected_impact': 'workforce_critical'
        },
        {
            'title': 'Highway Infrastructure Investment Act',
            'summary': 'Provides funding for highway repairs and bridge construction',
            'expected_impact': 'minimal_impact'
        }
    ]

    print("🔍 Testing SNF Impact Detection System")
    print("=" * 50)

    for i, bill in enumerate(test_bills, 1):
        result = detector.analyze_snf_impact(bill['title'], bill['summary'])

        print(f"\n{i}. {bill['title'][:60]}...")
        print(f"   Impact Detected: {'YES' if result.has_impact else 'NO'}")
        print(f"   Category: {result.impact_category}")
        print(f"   Relevance Score: {result.relevance_score:.1f}/100")
        print(f"   Priority: {result.monitoring_priority}")
        print(f"   Confidence: {result.confidence:.2f}")
        print(f"   Expected: {bill['expected_impact']}")
        print(f"   Explanation: {result.explanation}")
        if result.specific_impacts:
            print(f"   Specific Impacts: {', '.join(result.specific_impacts[:3])}")

    print(f"\n✅ SNF Impact Detection System test completed!")


if __name__ == "__main__":
    test_snf_impact_detector()