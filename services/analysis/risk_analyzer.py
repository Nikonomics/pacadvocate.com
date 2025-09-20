#!/usr/bin/env python3
"""
Bill Risk Analyzer
Analyzes bill text to calculate risk scores for skilled nursing facilities
"""

import re
import logging
from typing import Dict, List, Tuple, Optional
import json

logger = logging.getLogger(__name__)

class BillRiskAnalyzer:
    """Analyzes bill text to calculate risk scores for SNF operations"""

    def __init__(self):
        # Define risk keywords by category with severity weights
        # Higher weight = higher risk/severity

        self.reimbursement_keywords = {
            # High severity (8-10)
            'payment cut': 10,
            'rate reduction': 10,
            'reimbursement decrease': 10,
            'funding reduction': 9,
            'budget cut': 9,
            'payment reduction': 9,
            'lower payment': 8,
            'reduced reimbursement': 8,
            'payment freeze': 8,

            # Medium severity (5-7)
            'payment adjustment': 7,
            'rate adjustment': 7,
            'reimbursement change': 6,
            'payment methodology': 6,
            'rate setting': 5,
            'payment system': 5,

            # Lower severity (2-4)
            'payment update': 3,
            'rate update': 3,
            'reimbursement reform': 4,
            'pdpm': 3,
            'payment bundling': 4
        }

        self.staffing_keywords = {
            # High severity (8-10)
            'minimum staffing': 10,
            'nurse ratio': 9,
            'required hours': 8,
            'staffing requirement': 9,
            'mandatory staffing': 10,
            'nurse-to-patient ratio': 9,
            'staffing standard': 8,

            # Medium severity (5-7)
            'staffing level': 6,
            'nursing hours': 6,
            'direct care': 5,
            'registered nurse': 5,
            'licensed practical nurse': 4,
            'certified nursing assistant': 4,
            'staffing adequacy': 7,

            # Lower severity (2-4)
            'staffing data': 2,
            'workforce': 3,
            'employee': 2,
            'staff training': 4,
            'nursing staff': 3
        }

        self.compliance_keywords = {
            # High severity (8-10)
            'reporting requirement': 9,
            'new regulation': 8,
            'documentation requirement': 8,
            'mandatory reporting': 9,
            'compliance audit': 8,
            'regulatory oversight': 8,
            'inspection requirement': 9,

            # Medium severity (5-7)
            'quality reporting': 6,
            'data submission': 5,
            'record keeping': 5,
            'documentation': 4,
            'reporting': 4,
            'compliance': 5,
            'survey': 6,
            'certification': 6,

            # Lower severity (2-4)
            'data collection': 3,
            'information sharing': 2,
            'transparency': 3,
            'disclosure': 3,
            'notification': 2
        }

        self.quality_keywords = {
            # High severity (8-10)
            'quality measure': 8,
            'star rating': 9,
            'penalty': 10,
            'qapi': 7,
            'quality assurance': 7,
            'performance improvement': 6,
            'quality indicator': 8,
            'readmission penalty': 10,

            # Medium severity (5-7)
            'quality reporting': 6,
            'quality standard': 7,
            'quality metric': 6,
            'outcome measure': 6,
            'performance measure': 6,
            'quality improvement': 5,

            # Lower severity (2-4)
            'quality data': 3,
            'quality information': 3,
            'best practice': 2,
            'quality initiative': 4,
            'care quality': 3
        }

        # Risk multipliers for context
        self.context_multipliers = {
            'increase': 1.3,
            'require': 1.2,
            'mandate': 1.4,
            'penalty': 1.5,
            'fine': 1.4,
            'sanction': 1.3,
            'reduce': 1.2,
            'cut': 1.3,
            'decrease': 1.2,
            'eliminate': 1.5,
            'new': 1.1,
            'additional': 1.1,
            'expanded': 1.1
        }

    def analyze_bill_risk(self, title: str, summary: str = "", full_text: str = "") -> Dict:
        """
        Analyze bill text and calculate risk scores

        Args:
            title: Bill title
            summary: Bill summary
            full_text: Full bill text

        Returns:
            Dictionary with individual risk scores, total score, and analysis details
        """
        try:
            # Combine all text for analysis
            combined_text = f"{title} {summary} {full_text}".lower().strip()

            if not combined_text:
                return self._empty_risk_result("Empty text provided")

            # Calculate individual risk scores
            reimbursement_score, reimbursement_details = self._calculate_category_risk(
                combined_text, self.reimbursement_keywords, "reimbursement", max_score=40
            )

            staffing_score, staffing_details = self._calculate_category_risk(
                combined_text, self.staffing_keywords, "staffing", max_score=30
            )

            compliance_score, compliance_details = self._calculate_category_risk(
                combined_text, self.compliance_keywords, "compliance", max_score=20
            )

            quality_score, quality_details = self._calculate_category_risk(
                combined_text, self.quality_keywords, "quality", max_score=10
            )

            # Calculate total risk score
            total_risk_score = reimbursement_score + staffing_score + compliance_score + quality_score

            # Generate risk tags
            risk_tags = self._generate_risk_tags(
                reimbursement_score, staffing_score, compliance_score, quality_score,
                reimbursement_details, staffing_details, compliance_details, quality_details
            )

            # Determine risk level
            risk_level = self._determine_risk_level(total_risk_score)

            return {
                'reimbursement_risk': reimbursement_score,
                'staffing_risk': staffing_score,
                'compliance_risk': compliance_score,
                'quality_risk': quality_score,
                'total_risk_score': total_risk_score,
                'risk_tags': json.dumps(risk_tags),
                'risk_level': risk_level,
                'analysis_details': {
                    'reimbursement': reimbursement_details,
                    'staffing': staffing_details,
                    'compliance': compliance_details,
                    'quality': quality_details,
                    'text_length': len(combined_text),
                    'total_keywords_found': (
                        len(reimbursement_details.get('matched_keywords', [])) +
                        len(staffing_details.get('matched_keywords', [])) +
                        len(compliance_details.get('matched_keywords', [])) +
                        len(quality_details.get('matched_keywords', []))
                    )
                }
            }

        except Exception as e:
            logger.error(f"Error in risk analysis: {e}")
            return self._empty_risk_result(f"Analysis error: {str(e)}")

    def _calculate_category_risk(self, text: str, keywords: Dict[str, int],
                               category: str, max_score: int) -> Tuple[int, Dict]:
        """Calculate risk score for a specific category"""
        matched_keywords = []
        total_weighted_score = 0
        keyword_frequencies = {}

        for keyword, severity_weight in keywords.items():
            # Use word boundaries for better matching
            pattern = r'\b' + re.escape(keyword) + r'\b'
            matches = re.findall(pattern, text, re.IGNORECASE)

            if matches:
                frequency = len(matches)
                keyword_frequencies[keyword] = frequency
                matched_keywords.append(keyword)

                # Calculate base score (frequency * severity weight)
                base_score = frequency * severity_weight

                # Apply context multipliers
                context_multiplier = self._get_context_multiplier(text, keyword)
                adjusted_score = base_score * context_multiplier

                total_weighted_score += adjusted_score

        # Normalize to max_score range
        if total_weighted_score > 0:
            # Use a logarithmic scaling to prevent extreme scores
            import math
            normalized_score = min(max_score, int(math.log(total_weighted_score + 1) * (max_score / 4)))
        else:
            normalized_score = 0

        details = {
            'matched_keywords': matched_keywords,
            'keyword_frequencies': keyword_frequencies,
            'raw_weighted_score': round(total_weighted_score, 2),
            'normalized_score': normalized_score,
            'max_possible_score': max_score,
            'keywords_found_count': len(matched_keywords)
        }

        return normalized_score, details

    def _get_context_multiplier(self, text: str, keyword: str) -> float:
        """Get context multiplier based on surrounding words"""
        # Find the keyword in context (50 chars before/after)
        pattern = r'.{0,50}\b' + re.escape(keyword) + r'\b.{0,50}'
        context_matches = re.findall(pattern, text, re.IGNORECASE)

        multiplier = 1.0

        for context in context_matches:
            context_lower = context.lower()
            for context_word, mult in self.context_multipliers.items():
                if context_word in context_lower:
                    multiplier = max(multiplier, mult)

        return multiplier

    def _generate_risk_tags(self, reimbursement_score: int, staffing_score: int,
                           compliance_score: int, quality_score: int,
                           reimb_details: Dict, staff_details: Dict,
                           comp_details: Dict, qual_details: Dict) -> List[str]:
        """Generate risk tags based on scores and matched keywords"""
        tags = []

        # Risk level tags
        if reimbursement_score >= 30:
            tags.append("high_reimbursement_risk")
        elif reimbursement_score >= 15:
            tags.append("moderate_reimbursement_risk")
        elif reimbursement_score > 0:
            tags.append("low_reimbursement_risk")

        if staffing_score >= 20:
            tags.append("high_staffing_risk")
        elif staffing_score >= 10:
            tags.append("moderate_staffing_risk")
        elif staffing_score > 0:
            tags.append("low_staffing_risk")

        if compliance_score >= 15:
            tags.append("high_compliance_risk")
        elif compliance_score >= 8:
            tags.append("moderate_compliance_risk")
        elif compliance_score > 0:
            tags.append("low_compliance_risk")

        if quality_score >= 8:
            tags.append("high_quality_risk")
        elif quality_score >= 4:
            tags.append("moderate_quality_risk")
        elif quality_score > 0:
            tags.append("low_quality_risk")

        # Specific concern tags based on keywords
        reimb_keywords = reimb_details.get('matched_keywords', [])
        if any(kw in reimb_keywords for kw in ['payment cut', 'rate reduction', 'funding reduction']):
            tags.append("payment_cuts")
        if any(kw in reimb_keywords for kw in ['payment freeze', 'reimbursement decrease']):
            tags.append("reimbursement_concerns")

        staff_keywords = staff_details.get('matched_keywords', [])
        if any(kw in staff_keywords for kw in ['minimum staffing', 'nurse ratio', 'staffing requirement']):
            tags.append("staffing_mandates")
        if any(kw in staff_keywords for kw in ['required hours', 'mandatory staffing']):
            tags.append("staffing_requirements")

        comp_keywords = comp_details.get('matched_keywords', [])
        if any(kw in comp_keywords for kw in ['reporting requirement', 'mandatory reporting']):
            tags.append("reporting_burden")
        if any(kw in comp_keywords for kw in ['new regulation', 'regulatory oversight']):
            tags.append("regulatory_changes")

        qual_keywords = qual_details.get('matched_keywords', [])
        if any(kw in qual_keywords for kw in ['penalty', 'readmission penalty']):
            tags.append("quality_penalties")
        if any(kw in qual_keywords for kw in ['star rating', 'quality measure']):
            tags.append("quality_reporting")

        # Overall risk tags
        total_score = reimbursement_score + staffing_score + compliance_score + quality_score
        if total_score >= 70:
            tags.append("critical_risk")
        elif total_score >= 40:
            tags.append("high_risk")
        elif total_score >= 20:
            tags.append("moderate_risk")
        elif total_score > 0:
            tags.append("low_risk")
        else:
            tags.append("minimal_risk")

        return list(set(tags))  # Remove duplicates

    def _determine_risk_level(self, total_score: int) -> str:
        """Determine overall risk level based on total score"""
        if total_score >= 70:
            return "CRITICAL"
        elif total_score >= 40:
            return "HIGH"
        elif total_score >= 20:
            return "MODERATE"
        elif total_score > 0:
            return "LOW"
        else:
            return "MINIMAL"

    def _empty_risk_result(self, reason: str = "No analysis performed") -> Dict:
        """Return empty risk result"""
        return {
            'reimbursement_risk': 0,
            'staffing_risk': 0,
            'compliance_risk': 0,
            'quality_risk': 0,
            'total_risk_score': 0,
            'risk_tags': json.dumps(["minimal_risk"]),
            'risk_level': "MINIMAL",
            'analysis_details': {
                'reason': reason,
                'reimbursement': {'matched_keywords': [], 'normalized_score': 0},
                'staffing': {'matched_keywords': [], 'normalized_score': 0},
                'compliance': {'matched_keywords': [], 'normalized_score': 0},
                'quality': {'matched_keywords': [], 'normalized_score': 0}
            }
        }

    def get_keyword_categories(self) -> Dict[str, List[str]]:
        """Return all keyword categories for reference"""
        return {
            'reimbursement': list(self.reimbursement_keywords.keys()),
            'staffing': list(self.staffing_keywords.keys()),
            'compliance': list(self.compliance_keywords.keys()),
            'quality': list(self.quality_keywords.keys())
        }

# Convenience function for easy import
def analyze_bill_risk(title: str, summary: str = "", full_text: str = "") -> Dict:
    """
    Analyze bill risk using default analyzer

    Args:
        title: Bill title
        summary: Bill summary (optional)
        full_text: Full bill text (optional)

    Returns:
        Risk analysis results with scores and details
    """
    analyzer = BillRiskAnalyzer()
    return analyzer.analyze_bill_risk(title, summary, full_text)


def test_risk_analyzer():
    """Test the risk analyzer with sample bills"""
    print("🧪 Testing Bill Risk Analyzer")
    print("=" * 50)

    analyzer = BillRiskAnalyzer()

    # Test cases
    test_bills = [
        {
            'title': 'Medicare Part A Payment Cut for Skilled Nursing Facilities',
            'summary': 'This bill reduces Medicare reimbursement rates by 10% and establishes new minimum staffing requirements for SNFs.',
            'full_text': 'The Centers for Medicare & Medicaid Services shall implement a payment cut of 10% for all skilled nursing facilities. Additionally, facilities must maintain minimum staffing ratios of 1 registered nurse per 20 patients and report quality measures monthly.',
            'expected_risk': 'HIGH'
        },
        {
            'title': 'Nursing Home Quality Reporting Enhancement Act',
            'summary': 'Expands quality reporting requirements and establishes new documentation standards.',
            'full_text': 'All nursing homes must submit additional quality measures to CMS including star rating components and QAPI documentation. New reporting requirements take effect January 1, 2025.',
            'expected_risk': 'MODERATE'
        },
        {
            'title': 'Highway Infrastructure Improvement Act',
            'summary': 'Provides funding for highway and bridge improvements.',
            'full_text': 'This legislation allocates $50 billion for highway infrastructure improvements and bridge repairs across the United States.',
            'expected_risk': 'MINIMAL'
        }
    ]

    for i, bill in enumerate(test_bills, 1):
        print(f"\n📋 Test Bill {i}: {bill['title'][:50]}...")

        result = analyzer.analyze_bill_risk(
            title=bill['title'],
            summary=bill['summary'],
            full_text=bill['full_text']
        )

        print(f"   Risk Level: {result['risk_level']} (Expected: {bill['expected_risk']})")
        print(f"   Total Score: {result['total_risk_score']}/100")
        print(f"   Breakdown:")
        print(f"     Reimbursement: {result['reimbursement_risk']}/40")
        print(f"     Staffing: {result['staffing_risk']}/30")
        print(f"     Compliance: {result['compliance_risk']}/20")
        print(f"     Quality: {result['quality_risk']}/10")

        risk_tags = json.loads(result['risk_tags'])
        print(f"   Risk Tags: {', '.join(risk_tags[:5])}{'...' if len(risk_tags) > 5 else ''}")

        # Show matched keywords
        details = result['analysis_details']
        total_keywords = sum(
            len(details[cat].get('matched_keywords', []))
            for cat in ['reimbursement', 'staffing', 'compliance', 'quality']
        )
        print(f"   Keywords Found: {total_keywords}")

    print(f"\n✅ Risk analyzer test completed!")


if __name__ == "__main__":
    test_risk_analyzer()