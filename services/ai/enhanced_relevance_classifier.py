#!/usr/bin/env python3
"""
Enhanced AI Relevance Classifier for Skilled Nursing Legislation
Includes Medicare Advantage impact detection and specialized SNF scoring
"""

import os
import sys
import numpy as np
import logging
import re
from typing import List, Dict, Optional, Tuple, NamedTuple
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RelevanceResult(NamedTuple):
    """Results from relevance analysis"""
    score: float
    category: str
    confidence: float
    explanation: str
    ma_impact: bool
    context_notes: List[str]

class EnhancedSNFRelevanceClassifier:
    """Enhanced AI classifier for skilled nursing facility legislation relevance"""

    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        """
        Initialize the enhanced relevance classifier

        Args:
            model_name: SentenceTransformer model to use for embeddings
        """
        self.model_name = model_name
        self.model = None

        # Direct SNF keywords (highest priority)
        self.direct_snf_keywords = {
            'explicit': [
                'skilled nursing facility', 'skilled nursing facilities', 'SNF', 'SNFs',
                'nursing home', 'nursing homes', 'nursing facility', 'nursing facilities'
            ],
            'payment_systems': [
                'PDPM', 'RUG-IV', 'Medicare Part A', 'SNF PPS', 'consolidated billing'
            ],
            'quality_programs': [
                'Five-Star Quality Rating', 'SNF Quality Reporting Program',
                'CMS Five Star', 'nursing home compare'
            ]
        }

        # Medicare Advantage keywords and impact categories
        self.medicare_advantage_keywords = {
            'explicit_ma': [
                'Medicare Advantage', 'MA plan', 'MA plans', 'Medicare Part C',
                'Medicare+Choice', 'managed care organization', 'MCO'
            ],
            'payment_impact': [
                'prompt payment', 'payment timeline', 'payment delay', 'provider payment',
                'reimbursement schedule', 'claims payment', 'payment processing'
            ],
            'prior_authorization': [
                'prior authorization', 'preauthorization', 'pre-authorization',
                'utilization review', 'medical necessity', 'coverage determination'
            ],
            'network_adequacy': [
                'network adequacy', 'provider network', 'network participation',
                'provider access', 'network standards', 'adequate network'
            ],
            'quality_programs': [
                'Star Ratings', 'MA Star Ratings', 'bonus payment', 'quality bonus',
                'performance measures', 'HEDIS', 'HOS', 'CAHPS'
            ]
        }

        # Long-term care and post-acute keywords
        self.ltc_keywords = {
            'facilities': [
                'long-term care', 'post-acute care', 'rehabilitation facility',
                'assisted living', 'continuing care', 'subacute care'
            ],
            'services': [
                'physical therapy', 'occupational therapy', 'speech therapy',
                'wound care', 'IV therapy', 'ventilator care', 'dialysis'
            ],
            'regulatory': [
                'CMS', 'Centers for Medicare', 'survey', 'certification',
                'licensing', 'state agency', 'federal oversight'
            ]
        }

        # Context for scoring explanations
        self.ma_impact_explanations = {
            'payment_impact': "30-40% of SNF revenue comes from Medicare Advantage plans. Payment delays severely impact SNF cash flow and operations.",
            'prior_authorization': "MA prior authorization changes affect SNF admission patterns and length of stay decisions.",
            'network_adequacy': "Network participation requirements determine SNF ability to serve MA beneficiaries in their market.",
            'quality_programs': "MA Star Ratings affect plan bonus payments and can influence referral patterns to SNFs."
        }

        # Scoring matrices for different bill types
        self.scoring_matrix = {
            'direct_snf': {
                'base_score': 85,
                'max_score': 100,
                'priority': 1
            },
            'ma_payment': {
                'base_score': 75,
                'max_score': 95,
                'priority': 2,
                'explanation': self.ma_impact_explanations['payment_impact']
            },
            'ma_prior_auth': {
                'base_score': 65,
                'max_score': 85,
                'priority': 2,
                'explanation': self.ma_impact_explanations['prior_authorization']
            },
            'ma_network': {
                'base_score': 55,
                'max_score': 75,
                'priority': 3,
                'explanation': self.ma_impact_explanations['network_adequacy']
            },
            'ma_quality': {
                'base_score': 45,
                'max_score': 65,
                'priority': 3,
                'explanation': self.ma_impact_explanations['quality_programs']
            },
            'ltc_related': {
                'base_score': 35,
                'max_score': 55,
                'priority': 3
            },
            'medicare_general': {
                'base_score': 25,
                'max_score': 45,
                'priority': 4
            },
            'healthcare_general': {
                'base_score': 15,
                'max_score': 35,
                'priority': 5
            }
        }

        logger.info(f"Enhanced SNF Relevance Classifier initialized with MA detection")

    def _load_model(self):
        """Load the sentence transformer model"""
        if self.model is None:
            try:
                logger.info("Loading sentence transformer model...")
                self.model = SentenceTransformer(self.model_name)
                logger.info("Model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
                self.model = None

    def _preprocess_text(self, text: str) -> str:
        """Clean and preprocess text for analysis"""
        if not text:
            return ""

        # Convert to lowercase and normalize whitespace
        text = re.sub(r'\s+', ' ', text.lower().strip())

        # Remove very short texts
        if len(text) < 10:
            return ""

        return text

    def _detect_bill_category(self, title: str, summary: str = "", full_text: str = "") -> Tuple[str, List[str]]:
        """
        Detect the primary category of the bill and context notes

        Returns:
            Tuple of (category, context_notes)
        """
        combined_text = f"{title} {summary} {full_text}".lower()
        context_notes = []

        # Check for direct SNF mentions
        for keyword in self.direct_snf_keywords['explicit']:
            if keyword.lower() in combined_text:
                context_notes.append(f"Explicitly mentions: {keyword}")
                return 'direct_snf', context_notes

        # Check for SNF-specific systems
        for keyword in self.direct_snf_keywords['payment_systems']:
            if keyword.lower() in combined_text:
                context_notes.append(f"References SNF payment system: {keyword}")
                return 'direct_snf', context_notes

        # Check for Medicare Advantage categories
        ma_detected = any(kw.lower() in combined_text for kw in self.medicare_advantage_keywords['explicit_ma'])

        if ma_detected:
            context_notes.append("Medicare Advantage legislation detected")

            # Determine MA subcategory
            if any(kw.lower() in combined_text for kw in self.medicare_advantage_keywords['payment_impact']):
                context_notes.append("Addresses provider payment timelines - critical for SNF cash flow")
                return 'ma_payment', context_notes

            elif any(kw.lower() in combined_text for kw in self.medicare_advantage_keywords['prior_authorization']):
                context_notes.append("Affects prior authorization - impacts SNF admission patterns")
                return 'ma_prior_auth', context_notes

            elif any(kw.lower() in combined_text for kw in self.medicare_advantage_keywords['network_adequacy']):
                context_notes.append("Network adequacy requirements - affects SNF market participation")
                return 'ma_network', context_notes

            elif any(kw.lower() in combined_text for kw in self.medicare_advantage_keywords['quality_programs']):
                context_notes.append("MA quality programs - may affect referral patterns to SNFs")
                return 'ma_quality', context_notes

        # Check for LTC-related content
        ltc_keywords_found = [kw for kw in self.ltc_keywords['facilities'] if kw.lower() in combined_text]
        if ltc_keywords_found:
            context_notes.append(f"Long-term care related: {', '.join(ltc_keywords_found)}")
            return 'ltc_related', context_notes

        # Check for general Medicare (including Social Security Act references)
        if ('medicare' in combined_text or 'social security act' in combined_text) and 'medicaid' not in combined_text:
            context_notes.append("General Medicare legislation")
            return 'medicare_general', context_notes

        # Check for general healthcare
        if any(term in combined_text for term in ['health', 'medical', 'healthcare', 'patient']):
            context_notes.append("General healthcare legislation")
            return 'healthcare_general', context_notes

        return 'non_healthcare', context_notes

    def _calculate_enhanced_score(self, category: str, title: str, summary: str = "", full_text: str = "") -> Tuple[float, float]:
        """
        Calculate enhanced relevance score based on category and content analysis

        Returns:
            Tuple of (score, confidence)
        """
        if category not in self.scoring_matrix:
            return 0.0, 0.1

        config = self.scoring_matrix[category]
        base_score = config['base_score']
        max_score = config['max_score']

        # Calculate content richness multiplier
        combined_text = f"{title} {summary} {full_text}"
        text_length = len(combined_text)

        # Confidence based on text length and category
        if text_length > 1000:
            confidence = 0.9
            content_multiplier = 1.0
        elif text_length > 500:
            confidence = 0.8
            content_multiplier = 0.95
        elif text_length > 100:
            confidence = 0.7
            content_multiplier = 0.9
        else:
            confidence = 0.6
            content_multiplier = 0.8

        # Calculate final score
        final_score = min(base_score * content_multiplier, max_score)

        return final_score, confidence

    def analyze_relevance(self, title: str, summary: str = "", full_text: str = "") -> RelevanceResult:
        """
        Analyze the relevance of a bill to skilled nursing facilities

        Args:
            title: Bill title
            summary: Bill summary (optional)
            full_text: Full bill text (optional)

        Returns:
            RelevanceResult with score, category, and explanation
        """
        if not title:
            return RelevanceResult(0.0, 'invalid', 0.1, 'No title provided', False, [])

        # Detect bill category
        category, context_notes = self._detect_bill_category(title, summary, full_text)

        # Calculate score
        score, confidence = self._calculate_enhanced_score(category, title, summary, full_text)

        # Determine if this is MA-related
        ma_impact = category.startswith('ma_')

        # Generate explanation
        explanation = self._generate_explanation(category, score, context_notes)

        return RelevanceResult(
            score=score,
            category=category,
            confidence=confidence,
            explanation=explanation,
            ma_impact=ma_impact,
            context_notes=context_notes
        )

    def _generate_explanation(self, category: str, score: float, context_notes: List[str]) -> str:
        """Generate human-readable explanation for the score"""

        explanations = {
            'direct_snf': f"Direct SNF legislation (Score: {score:.1f}/100) - Explicitly addresses skilled nursing facilities",
            'ma_payment': f"Medicare Advantage payment legislation (Score: {score:.1f}/100) - High SNF impact due to cash flow dependency",
            'ma_prior_auth': f"Medicare Advantage prior authorization (Score: {score:.1f}/100) - Affects SNF admission patterns",
            'ma_network': f"Medicare Advantage network requirements (Score: {score:.1f}/100) - Impacts SNF market participation",
            'ma_quality': f"Medicare Advantage quality programs (Score: {score:.1f}/100) - May influence SNF referral patterns",
            'ltc_related': f"Long-term care related (Score: {score:.1f}/100) - Indirect SNF relevance",
            'medicare_general': f"General Medicare legislation (Score: {score:.1f}/100) - Potential SNF impact",
            'healthcare_general': f"General healthcare legislation (Score: {score:.1f}/100) - Minimal SNF relevance",
            'non_healthcare': f"Non-healthcare legislation (Score: {score:.1f}/100) - No SNF relevance"
        }

        base_explanation = explanations.get(category, f"Unknown category (Score: {score:.1f}/100)")

        if context_notes:
            base_explanation += f" | Context: {'; '.join(context_notes)}"

        return base_explanation

    def batch_analyze(self, bills: List[Dict]) -> List[RelevanceResult]:
        """
        Analyze multiple bills for relevance

        Args:
            bills: List of bill dictionaries with 'title', 'summary', 'full_text' keys

        Returns:
            List of RelevanceResult objects
        """
        results = []

        for bill in bills:
            try:
                result = self.analyze_relevance(
                    title=bill.get('title', ''),
                    summary=bill.get('summary', ''),
                    full_text=bill.get('full_text', '')
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Error analyzing bill {bill.get('title', 'Unknown')}: {e}")
                results.append(RelevanceResult(0.0, 'error', 0.1, f'Analysis error: {str(e)}', False, []))

        return results

    def get_scoring_guidelines(self) -> Dict:
        """Return scoring guidelines for different bill categories"""
        guidelines = {}

        for category, config in self.scoring_matrix.items():
            guidelines[category] = {
                'score_range': f"{config['base_score']}-{config['max_score']}",
                'priority': config['priority'],
                'explanation': config.get('explanation', 'Standard healthcare legislation scoring')
            }

        return guidelines


def test_enhanced_classifier():
    """Test the enhanced classifier with sample bills"""
    classifier = EnhancedSNFRelevanceClassifier()

    test_bills = [
        {
            'title': 'Medicare Program; Prospective Payment System and Consolidated Billing for Skilled Nursing Facilities; Updates to the Quality Reporting Program for Federal Fiscal Year 2026',
            'summary': 'This final rule finalizes changes and updates to the policies and payment rates used under the Skilled Nursing Facility (SNF) Prospective Payment System'
        },
        {
            'title': 'A bill to amend title XVIII of the Social Security Act to apply improved prompt payment requirements to Medicare Advantage organizations.',
            'summary': 'Requires Medicare Advantage plans to pay providers within specified timeframes'
        },
        {
            'title': 'A bill to establish a national emergency medical services foundation',
            'summary': 'Creates commemorative work for emergency medical services'
        }
    ]

    print("🧪 Testing Enhanced SNF Relevance Classifier")
    print("=" * 50)

    for i, bill in enumerate(test_bills, 1):
        result = classifier.analyze_relevance(bill['title'], bill['summary'])
        print(f"\n{i}. {bill['title'][:60]}...")
        print(f"   Score: {result.score:.1f}/100")
        print(f"   Category: {result.category}")
        print(f"   MA Impact: {'Yes' if result.ma_impact else 'No'}")
        print(f"   Confidence: {result.confidence:.1f}")
        print(f"   Explanation: {result.explanation}")
        if result.context_notes:
            print(f"   Notes: {'; '.join(result.context_notes)}")


if __name__ == "__main__":
    test_enhanced_classifier()