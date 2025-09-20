#!/usr/bin/env python3
"""
Healthcare Content Validator
Shared utility for validating that bills contain healthcare-related content
"""

import logging
import re
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class HealthcareValidator:
    """Validates that bills contain sufficient healthcare-related keywords"""

    # Core healthcare keywords - must match at least 2 of these
    HEALTHCARE_KEYWORDS = {
        'medicare', 'medicaid', 'health', 'nursing', 'medical', 'care',
        'facility', 'hospital', 'patient', 'cms', 'hhs', 'skilled',
        'assisted living', 'hospice', 'therapy', 'rehabilitation',
        'quality reporting', 'payment system', 'reimbursement'
    }

    # Additional healthcare terms for scoring
    EXTENDED_HEALTHCARE_TERMS = {
        'healthcare', 'health care', 'clinical', 'physician', 'doctor',
        'nurse', 'nursing home', 'long-term care', 'post-acute care',
        'snf', 'alf', 'ltc', 'pdpm', 'rug-iv', 'mds', 'star rating',
        'survey', 'certification', 'licensing', 'compliance', 'quality measures',
        'patient safety', 'staffing', 'minimum staffing', 'nurse-to-patient',
        'geriatric', 'elder care', 'chronic care', 'palliative care',
        'wound care', 'medication management', 'discharge planning'
    }

    # Non-healthcare terms that indicate irrelevant content
    NON_HEALTHCARE_EXCLUSIONS = {
        'palestine', 'israel', 'foreign policy', 'defense', 'military',
        'immigration', 'border', 'agriculture', 'farming', 'energy',
        'oil', 'gas', 'mining', 'transportation', 'infrastructure',
        'education', 'school', 'student', 'teacher', 'environmental',
        'climate', 'wildlife', 'forestry', 'telecommunications', 'broadband',
        'cybersecurity', 'digital asset', 'cryptocurrency', 'blockchain',
        'tax', 'taxation', 'trade', 'tariff', 'commerce', 'business',
        'small business', 'housing', 'real estate', 'mortgage', 'banking',
        'finance', 'securities', 'investment', 'pension', 'retirement',
        'social security', 'unemployment', 'labor', 'employment',
        'civil rights', 'discrimination', 'voting rights', 'election',
        'campaign finance', 'lobbying', 'ethics', 'judicial', 'court',
        'crime', 'justice', 'law enforcement', 'prison', 'drug policy',
        'immigration', 'refugee', 'asylum', 'visa', 'citizenship'
    }

    def __init__(self, min_keyword_count: int = 2, enable_strict_mode: bool = True):
        """
        Initialize healthcare validator

        Args:
            min_keyword_count: Minimum healthcare keywords required (default: 2)
            enable_strict_mode: If True, exclude bills with non-healthcare terms
        """
        self.min_keyword_count = min_keyword_count
        self.enable_strict_mode = enable_strict_mode
        self.rejected_bills = []  # Track rejected bills for logging

    def validate_healthcare_content(self, title: str, summary: str = "",
                                  full_text: str = "", bill_number: str = "") -> Dict:
        """
        Validate that content contains sufficient healthcare keywords

        Args:
            title: Bill title
            summary: Bill summary/description
            full_text: Full bill text (optional)
            bill_number: Bill identifier for logging

        Returns:
            Dict with validation results:
            {
                'is_healthcare': bool,
                'keyword_count': int,
                'matched_keywords': list,
                'confidence_score': float,
                'rejection_reason': str (if rejected)
            }
        """
        try:
            # Combine all text
            combined_text = f"{title} {summary} {full_text}".lower()

            if not combined_text.strip():
                result = {
                    'is_healthcare': False,
                    'keyword_count': 0,
                    'matched_keywords': [],
                    'confidence_score': 0.0,
                    'rejection_reason': 'Empty content'
                }
                self._log_rejection(bill_number, result)
                return result

            # Check for exclusionary terms if strict mode enabled
            if self.enable_strict_mode:
                exclusion_matches = self._find_exclusionary_terms(combined_text)
                if exclusion_matches:
                    result = {
                        'is_healthcare': False,
                        'keyword_count': 0,
                        'matched_keywords': [],
                        'confidence_score': 0.0,
                        'rejection_reason': f'Contains non-healthcare terms: {", ".join(exclusion_matches[:3])}'
                    }
                    self._log_rejection(bill_number, result)
                    return result

            # Find healthcare keywords
            matched_keywords = self._find_healthcare_keywords(combined_text)
            keyword_count = len(matched_keywords)

            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(
                combined_text, matched_keywords, title, summary
            )

            # Determine if passes validation
            is_healthcare = keyword_count >= self.min_keyword_count

            result = {
                'is_healthcare': is_healthcare,
                'keyword_count': keyword_count,
                'matched_keywords': matched_keywords,
                'confidence_score': confidence_score
            }

            if not is_healthcare:
                result['rejection_reason'] = f'Only {keyword_count}/{self.min_keyword_count} healthcare keywords found'
                self._log_rejection(bill_number, result)

            return result

        except Exception as e:
            logger.error(f"Error validating healthcare content for {bill_number}: {e}")
            return {
                'is_healthcare': False,
                'keyword_count': 0,
                'matched_keywords': [],
                'confidence_score': 0.0,
                'rejection_reason': f'Validation error: {str(e)}'
            }

    def _find_healthcare_keywords(self, text: str) -> List[str]:
        """Find healthcare keywords in text"""
        matched = []

        # Check core keywords
        for keyword in self.HEALTHCARE_KEYWORDS:
            if self._keyword_in_text(keyword, text):
                matched.append(keyword)

        # Check extended terms (count as 0.5 each)
        extended_matches = []
        for term in self.EXTENDED_HEALTHCARE_TERMS:
            if self._keyword_in_text(term, text):
                extended_matches.append(term)

        # Add extended matches (up to 2 additional matches)
        matched.extend(extended_matches[:4])  # Allow more extended terms

        return list(set(matched))  # Remove duplicates

    def _find_exclusionary_terms(self, text: str) -> List[str]:
        """Find non-healthcare exclusionary terms"""
        found = []
        for term in self.NON_HEALTHCARE_EXCLUSIONS:
            if self._keyword_in_text(term, text):
                found.append(term)
        return found

    def _keyword_in_text(self, keyword: str, text: str) -> bool:
        """Check if keyword exists in text with word boundaries"""
        # Handle multi-word phrases
        if ' ' in keyword:
            return keyword in text

        # Use word boundaries for single words
        pattern = r'\b' + re.escape(keyword) + r'\b'
        return bool(re.search(pattern, text, re.IGNORECASE))

    def _calculate_confidence_score(self, text: str, matched_keywords: List[str],
                                  title: str, summary: str) -> float:
        """Calculate confidence score based on matches and context"""
        if not matched_keywords:
            return 0.0

        # Base score from keyword count
        base_score = min(len(matched_keywords) * 0.15, 0.8)  # Max 0.8 from keywords

        # Bonus for title matches
        title_matches = sum(1 for kw in matched_keywords if self._keyword_in_text(kw, title.lower()))
        title_bonus = title_matches * 0.1

        # Bonus for high-priority terms
        high_priority_terms = {'medicare', 'medicaid', 'skilled nursing', 'nursing home', 'snf', 'cms'}
        priority_matches = sum(1 for kw in matched_keywords if kw in high_priority_terms)
        priority_bonus = priority_matches * 0.05

        # Text length penalty for very short content
        text_length = len(text.strip())
        length_penalty = 0.0 if text_length > 100 else 0.1

        final_score = base_score + title_bonus + priority_bonus - length_penalty
        return min(max(final_score, 0.0), 1.0)  # Clamp between 0 and 1

    def _log_rejection(self, bill_number: str, result: Dict):
        """Log rejected bill for review"""
        rejection_info = {
            'bill_number': bill_number,
            'reason': result.get('rejection_reason', 'Unknown'),
            'keyword_count': result.get('keyword_count', 0),
            'matched_keywords': result.get('matched_keywords', [])
        }
        self.rejected_bills.append(rejection_info)

        logger.info(f"REJECTED: {bill_number} - {rejection_info['reason']}")

    def get_healthcare_search_terms(self) -> List[str]:
        """Get healthcare terms suitable for API search queries"""
        # Return most important terms for initial API filtering
        search_terms = [
            'Medicare', 'Medicaid', 'health', 'healthcare', 'nursing',
            'medical', 'hospital', 'patient care', 'skilled nursing',
            'nursing home', 'assisted living', 'long-term care', 'hospice',
            'CMS', 'HHS', 'quality reporting', 'reimbursement'
        ]
        return search_terms

    def get_rejection_summary(self) -> Dict:
        """Get summary of rejected bills"""
        if not self.rejected_bills:
            return {'total_rejected': 0, 'rejection_reasons': {}}

        reason_counts = {}
        for rejection in self.rejected_bills:
            reason = rejection['reason']
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

        return {
            'total_rejected': len(self.rejected_bills),
            'rejection_reasons': reason_counts,
            'sample_rejected_bills': self.rejected_bills[:10]  # First 10 for review
        }

    def clear_rejection_log(self):
        """Clear the rejection log"""
        self.rejected_bills = []

# Create a default instance for easy import
default_validator = HealthcareValidator()

def validate_bill_healthcare_content(title: str, summary: str = "",
                                   full_text: str = "", bill_number: str = "") -> Dict:
    """Convenience function using default validator"""
    return default_validator.validate_healthcare_content(title, summary, full_text, bill_number)

def get_healthcare_search_terms() -> List[str]:
    """Get healthcare search terms for API queries"""
    return default_validator.get_healthcare_search_terms()