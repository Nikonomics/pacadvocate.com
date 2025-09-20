#!/usr/bin/env python3
"""
AI Relevance Classifier for Skilled Nursing Legislation
Uses sentence-transformers to score bill relevance to skilled nursing facilities
"""

import os
import sys
import numpy as np
import logging
from typing import List, Dict, Optional, Tuple
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Import healthcare validator for initial screening
try:
    from services.collectors.healthcare_validator import validate_bill_healthcare_content
    HEALTHCARE_VALIDATOR_AVAILABLE = True
except ImportError:
    HEALTHCARE_VALIDATOR_AVAILABLE = False
    logging.warning("Healthcare validator not available - scores may include non-healthcare bills")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SNFRelevanceClassifier:
    """AI classifier for skilled nursing facility legislation relevance"""

    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        """
        Initialize the relevance classifier

        Args:
            model_name: SentenceTransformer model to use for embeddings
        """
        self.model_name = model_name
        self.model = None

        # SNF-specific keywords and phrases for enhanced matching
        self.snf_keywords = {
            'high_priority': [
                'skilled nursing facility', 'skilled nursing facilities', 'SNF', 'SNFs',
                'nursing home', 'nursing homes', 'long-term care facility',
                'post-acute care', 'Medicare Part A', 'PDPM', 'RUG-IV',
                'Five-Star Quality Rating', 'CMS Quality Reporting'
            ],
            'medium_priority': [
                'Medicaid', 'Medicare', 'CMS', 'Centers for Medicare',
                'staffing ratio', 'nurse-to-patient ratio', 'minimum staffing',
                'quality measures', 'patient safety', 'healthcare quality',
                'long-term care', 'assisted living', 'rehabilitation services'
            ],
            'contextual': [
                'nursing', 'healthcare', 'patient care', 'medical facility',
                'health services', 'elder care', 'geriatric', 'rehabilitation',
                'therapy', 'clinical', 'medical', 'health insurance',
                'reimbursement', 'payment system', 'healthcare provider'
            ]
        }

        # Reference texts for semantic similarity
        self.reference_texts = [
            "Skilled nursing facility quality standards and patient safety regulations",
            "Medicare reimbursement for skilled nursing facility services and care",
            "Nursing home staffing requirements and minimum nurse-to-patient ratios",
            "Long-term care facility licensing and certification requirements",
            "Post-acute care services and Medicare Part A coverage",
            "PDPM payment system for skilled nursing facility reimbursement",
            "Five-Star Quality Rating system for nursing home quality measures",
            "CMS quality reporting requirements for skilled nursing facilities",
            "Medicaid coverage for long-term care and nursing home services",
            "Healthcare worker staffing and training requirements in nursing facilities"
        ]

        # Scoring weights
        self.weights = {
            'title': 0.4,     # 40% weight for title
            'summary': 0.3,   # 30% weight for summary
            'full_text': 0.3  # 30% weight for full text
        }

        logger.info(f"SNF Relevance Classifier initialized with model: {model_name}")

    def _load_model(self):
        """Load the sentence transformer model"""
        if self.model is None:
            logger.info("Loading sentence transformer model...")
            self.model = SentenceTransformer(self.model_name)
            logger.info("Model loaded successfully")

    def _preprocess_text(self, text: str) -> str:
        """Clean and preprocess text for analysis"""
        if not text:
            return ""

        # Convert to lowercase
        text = text.lower()

        # Remove extra whitespace and normalize
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()

        # Remove very short texts (less than 10 characters)
        if len(text) < 10:
            return ""

        return text

    def _calculate_keyword_score(self, text: str) -> float:
        """Calculate relevance score based on keyword matching"""
        if not text:
            return 0.0

        text = self._preprocess_text(text)
        score = 0.0

        # High priority keywords (higher weight)
        for keyword in self.snf_keywords['high_priority']:
            if keyword.lower() in text:
                score += 3.0  # High weight for exact matches

        # Medium priority keywords
        for keyword in self.snf_keywords['medium_priority']:
            if keyword.lower() in text:
                score += 2.0  # Medium weight

        # Contextual keywords (lower weight)
        for keyword in self.snf_keywords['contextual']:
            if keyword.lower() in text:
                score += 1.0  # Lower weight

        # Normalize score (rough normalization)
        max_possible_score = len(self.snf_keywords['high_priority']) * 3.0 + \
                           len(self.snf_keywords['medium_priority']) * 2.0 + \
                           len(self.snf_keywords['contextual']) * 1.0

        normalized_score = min(score / max_possible_score, 1.0) if max_possible_score > 0 else 0.0

        return normalized_score

    def _calculate_semantic_score(self, text: str) -> float:
        """Calculate semantic similarity score using sentence embeddings"""
        if not text or len(self._preprocess_text(text)) < 10:
            return 0.0

        self._load_model()

        try:
            # Get embeddings for the text and reference texts
            text_embedding = self.model.encode([self._preprocess_text(text)])
            reference_embeddings = self.model.encode(self.reference_texts)

            # Calculate cosine similarities
            similarities = cosine_similarity(text_embedding, reference_embeddings)[0]

            # Take the maximum similarity as the semantic score
            max_similarity = np.max(similarities)

            # Convert from [-1, 1] to [0, 1] range
            semantic_score = (max_similarity + 1) / 2

            return float(semantic_score)

        except Exception as e:
            logger.error(f"Error calculating semantic score: {e}")
            return 0.0

    def _calculate_component_score(self, text: str, weight: float) -> Tuple[float, Dict]:
        """Calculate score for a single component (title, summary, or full_text)"""
        if not text:
            return 0.0, {'keyword_score': 0.0, 'semantic_score': 0.0}

        # Calculate both keyword and semantic scores
        keyword_score = self._calculate_keyword_score(text)
        semantic_score = self._calculate_semantic_score(text)

        # Combine keyword and semantic scores (60% keyword, 40% semantic)
        combined_score = (keyword_score * 0.6) + (semantic_score * 0.4)

        # Apply weight
        weighted_score = combined_score * weight

        return weighted_score, {
            'keyword_score': keyword_score,
            'semantic_score': semantic_score,
            'combined_score': combined_score,
            'weighted_score': weighted_score
        }

    def score_bill_relevance(self, bill_data: Dict) -> Dict:
        """
        Score a bill's relevance to skilled nursing facilities

        Args:
            bill_data: Dictionary containing bill information with keys:
                      'title', 'summary', 'full_text'

        Returns:
            Dictionary with relevance score and detailed breakdown
        """
        title = bill_data.get('title', '')
        summary = bill_data.get('summary', '')
        full_text = bill_data.get('full_text', '')

        # First, validate if this is healthcare-related content
        if HEALTHCARE_VALIDATOR_AVAILABLE:
            bill_number = bill_data.get('bill_number', 'unknown')
            validation_result = validate_bill_healthcare_content(
                title=title,
                summary=summary,
                full_text=full_text,
                bill_number=bill_number
            )

            if not validation_result['is_healthcare']:
                logger.info(f"Scoring non-healthcare bill {bill_number} as 0 relevance")
                return {
                    'relevance_score': 0.0,
                    'category': "non_healthcare",
                    'is_highly_relevant': False,
                    'healthcare_validation': validation_result,
                    'breakdown': {
                        'title': {'score': 0.0, 'weight': self.weights['title'], 'reason': 'non-healthcare'},
                        'summary': {'score': 0.0, 'weight': self.weights['summary'], 'reason': 'non-healthcare'},
                        'full_text': {'score': 0.0, 'weight': self.weights['full_text'], 'reason': 'non-healthcare'}
                    }
                }

        # Calculate scores for each component
        title_score, title_details = self._calculate_component_score(title, self.weights['title'])
        summary_score, summary_details = self._calculate_component_score(summary, self.weights['summary'])
        full_text_score, full_text_details = self._calculate_component_score(full_text, self.weights['full_text'])

        # Calculate total relevance score (0-1 scale)
        total_score = title_score + summary_score + full_text_score

        # Convert to 0-100 scale
        relevance_score = total_score * 100

        # Determine relevance category
        if relevance_score >= 70:
            category = "highly_relevant"
        elif relevance_score >= 40:
            category = "moderately_relevant"
        elif relevance_score >= 20:
            category = "somewhat_relevant"
        else:
            category = "not_relevant"

        return {
            'relevance_score': round(relevance_score, 2),
            'category': category,
            'is_highly_relevant': relevance_score >= 70,
            'breakdown': {
                'title': {
                    'score': round(title_score * 100, 2),
                    'weight': self.weights['title'],
                    **title_details
                },
                'summary': {
                    'score': round(summary_score * 100, 2),
                    'weight': self.weights['summary'],
                    **summary_details
                },
                'full_text': {
                    'score': round(full_text_score * 100, 2),
                    'weight': self.weights['full_text'],
                    **full_text_details
                }
            },
            'total_weighted_score': round(total_score, 4)
        }

    def batch_score_bills(self, bills: List[Dict], progress_callback=None) -> List[Dict]:
        """
        Score multiple bills in batch

        Args:
            bills: List of bill dictionaries
            progress_callback: Optional callback function for progress updates

        Returns:
            List of dictionaries with bill data and relevance scores
        """
        results = []

        logger.info(f"Starting batch scoring of {len(bills)} bills...")

        for i, bill in enumerate(bills):
            try:
                # Score the bill
                score_result = self.score_bill_relevance(bill)

                # Combine bill data with score
                result = {
                    **bill,
                    'ai_relevance': score_result
                }

                results.append(result)

                # Progress callback
                if progress_callback:
                    progress_callback(i + 1, len(bills), score_result['relevance_score'])

                if (i + 1) % 10 == 0:
                    logger.info(f"Processed {i + 1}/{len(bills)} bills")

            except Exception as e:
                logger.error(f"Error scoring bill {bill.get('id', 'unknown')}: {e}")
                # Add bill with error score
                results.append({
                    **bill,
                    'ai_relevance': {
                        'relevance_score': 0.0,
                        'category': 'error',
                        'error': str(e)
                    }
                })

        logger.info(f"Batch scoring complete: {len(results)} bills scored")

        # Sort by relevance score (highest first)
        results.sort(key=lambda x: x.get('ai_relevance', {}).get('relevance_score', 0), reverse=True)

        return results

    def get_model_info(self) -> Dict:
        """Get information about the loaded model"""
        return {
            'model_name': self.model_name,
            'model_loaded': self.model is not None,
            'reference_texts_count': len(self.reference_texts),
            'keyword_categories': {k: len(v) for k, v in self.snf_keywords.items()},
            'scoring_weights': self.weights
        }

def test_classifier():
    """Test the classifier with sample data"""
    print("🧪 Testing SNF Relevance Classifier")
    print("=" * 50)

    # Initialize classifier
    classifier = SNFRelevanceClassifier()

    # Test with sample bills
    test_bills = [
        {
            'id': 1,
            'title': 'Medicare Part A Payment Reform for Skilled Nursing Facilities',
            'summary': 'A bill to reform Medicare Part A payment system for skilled nursing facilities and establish new quality measures.',
            'full_text': 'This legislation addresses the Medicare Part A payment system for skilled nursing facilities (SNFs) and establishes comprehensive quality measures for post-acute care services...'
        },
        {
            'id': 2,
            'title': 'Highway Infrastructure Improvement Act',
            'summary': 'A bill to improve highway infrastructure and transportation systems.',
            'full_text': 'This act provides funding for highway improvements, bridge repairs, and transportation infrastructure development across the state...'
        },
        {
            'id': 3,
            'title': 'Nursing Home Staffing Standards Act',
            'summary': 'Establishes minimum staffing ratios for nursing homes and skilled nursing facilities.',
            'full_text': 'This legislation requires nursing homes and skilled nursing facilities to maintain minimum nurse-to-patient ratios to ensure quality care and patient safety...'
        }
    ]

    # Score the bills
    results = classifier.batch_score_bills(test_bills)

    print("\n📊 Test Results:")
    for result in results:
        ai_score = result['ai_relevance']
        print(f"\nBill ID {result['id']}: {ai_score['relevance_score']}/100 ({ai_score['category']})")
        print(f"   Title: {result['title'][:60]}...")
        print(f"   Breakdown:")
        print(f"     Title: {ai_score['breakdown']['title']['score']:.1f}")
        print(f"     Summary: {ai_score['breakdown']['summary']['score']:.1f}")
        print(f"     Full Text: {ai_score['breakdown']['full_text']['score']:.1f}")
        print(f"   Highly Relevant: {'Yes' if ai_score['is_highly_relevant'] else 'No'}")

    print(f"\n🤖 Model Info:")
    info = classifier.get_model_info()
    for key, value in info.items():
        print(f"   {key}: {value}")

if __name__ == "__main__":
    test_classifier()