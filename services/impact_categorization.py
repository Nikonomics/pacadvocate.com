#!/usr/bin/env python3
"""
Impact Categorization Helper
Maps comprehensive classifier results to dashboard-friendly categories
"""

from typing import Dict, Tuple
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from ai.comprehensive_snf_classifier import ComprehensiveSNFClassifier

def categorize_bill_impact(title: str, summary: str = "", full_text: str = "") -> Dict:
    """
    Categorize a bill's impact for dashboard display

    Returns:
        Dict with impact_type, impact_explanation, ma_impact, and color_class
    """
    classifier = ComprehensiveSNFClassifier()
    result = classifier.analyze_comprehensive_relevance(title, summary, full_text)

    # Map comprehensive categories to dashboard categories
    if result.primary_category == 'direct_snf':
        impact_type = "Direct"
        color_class = "impact-direct"  # green

    elif result.primary_category.startswith('ma_'):
        impact_type = "Financial"
        color_class = "impact-financial"  # red

    elif result.primary_category in ['payment_critical', 'payment_moderate']:
        impact_type = "Financial"
        color_class = "impact-financial"  # red

    elif result.primary_category in ['competition_direct', 'competition_indirect']:
        impact_type = "Competitive"
        color_class = "impact-competitive"  # orange

    elif result.primary_category in ['workforce_critical', 'workforce_moderate', 'regulatory_impact']:
        impact_type = "Indirect"
        color_class = "impact-indirect"  # yellow

    elif result.primary_category == 'ltc_related':
        impact_type = "Competitive"
        color_class = "impact-competitive"  # orange

    elif result.final_score >= 50:
        impact_type = "Indirect"
        color_class = "impact-indirect"  # yellow

    else:
        impact_type = "Minimal"
        color_class = "impact-minimal"  # gray

    return {
        'impact_type': impact_type,
        'impact_explanation': result.explanation,
        'ma_impact': result.ma_impact,
        'color_class': color_class,
        'final_score': result.final_score,
        'priority': result.monitoring_priority,
        'specific_impacts': result.specific_impacts[:3],  # Top 3 impacts
        'recommended_actions': result.recommended_actions[:2]  # Top 2 actions
    }

def get_impact_tooltip(impact_type: str, explanation: str, specific_impacts: list) -> str:
    """Generate tooltip text explaining why the bill matters to SNFs"""

    base_explanations = {
        'Direct': "Explicitly addresses skilled nursing facilities and their operations",
        'Financial': "Affects SNF revenue, cash flow, or payment systems (30-40% revenue from MA)",
        'Competitive': "Changes competitive landscape affecting SNF referrals and market share",
        'Indirect': "Impacts SNF operations through workforce, quality, or regulatory changes",
        'Minimal': "Limited or no impact on skilled nursing facility operations"
    }

    tooltip = base_explanations.get(impact_type, "Impact on SNF operations")

    if specific_impacts:
        tooltip += f" | Key impacts: {', '.join(specific_impacts)}"

    if explanation and len(explanation) > 0:
        # Extract key insight from explanation
        if "30-40%" in explanation:
            tooltip += " | Critical: 30-40% of SNF revenue dependency"
        elif "cash flow" in explanation.lower():
            tooltip += " | Critical: Affects SNF cash flow operations"
        elif "staffing" in explanation.lower():
            tooltip += " | Critical: SNFs face severe staffing shortages"

    return tooltip

def get_color_classes() -> Dict:
    """Return CSS color classes for impact types"""
    return {
        'impact-direct': 'bg-green-100 text-green-800 border-green-200',
        'impact-financial': 'bg-red-100 text-red-800 border-red-200',
        'impact-competitive': 'bg-orange-100 text-orange-800 border-orange-200',
        'impact-indirect': 'bg-yellow-100 text-yellow-800 border-yellow-200',
        'impact-minimal': 'bg-gray-100 text-gray-600 border-gray-200'
    }

# Test the categorization
if __name__ == "__main__":
    test_bills = [
        {
            'title': 'Medicare Program; Prospective Payment System and Consolidated Billing for Skilled Nursing Facilities',
            'summary': 'Updates SNF payment rates and quality reporting requirements'
        },
        {
            'title': 'A bill to require prompt payment by Medicare Advantage organizations',
            'summary': 'Establishes 30-day payment requirements for Medicare Advantage plans'
        }
    ]

    print("🎯 Testing Impact Categorization System")
    print("=" * 50)

    for bill in test_bills:
        result = categorize_bill_impact(bill['title'], bill['summary'])
        tooltip = get_impact_tooltip(result['impact_type'], result['impact_explanation'], result['specific_impacts'])

        print(f"\nTitle: {bill['title'][:50]}...")
        print(f"Impact Type: {result['impact_type']}")
        print(f"Color Class: {result['color_class']}")
        print(f"MA Impact: {result['ma_impact']}")
        print(f"Priority: {result['priority']}")
        print(f"Tooltip: {tooltip[:100]}...")