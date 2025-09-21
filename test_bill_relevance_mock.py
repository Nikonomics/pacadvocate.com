#!/usr/bin/env python3
"""
Mock Test for GPT-4 Bill Relevance Analyzer
Demonstrates functionality without requiring API key
"""

import json
from bill_relevance_analyzer import BillRelevanceAnalyzer

class MockBillRelevanceAnalyzer(BillRelevanceAnalyzer):
    """Mock version that simulates GPT-4 responses for testing"""

    def __init__(self):
        # Skip API key initialization for mock testing
        self.model = "gpt-4-mock"
        pass

    def analyze_bill_relevance(self, title: str, summary: str) -> dict:
        """Mock analysis that simulates realistic GPT-4 responses"""

        # Simulate different types of bill analysis
        title_lower = title.lower()
        summary_lower = summary.lower()

        # High relevance - SNF payment/quality bills
        if any(keyword in title_lower for keyword in ['snf', 'skilled nursing', 'nursing facility', 'prospective payment']):
            return {
                'relevant': True,
                'impact_type': 'direct',
                'relevance_score': 95,
                'explanation': 'Directly impacts SNF Medicare payments, quality measures, and operational requirements.'
            }

        # Medium relevance - Medicare/Medicaid general
        elif any(keyword in title_lower + summary_lower for keyword in ['medicare', 'medicaid', 'cms', 'quality reporting', 'staffing']):
            if 'staff' in title_lower + summary_lower:
                return {
                    'relevant': True,
                    'impact_type': 'workforce',
                    'relevance_score': 75,
                    'explanation': 'Healthcare staffing changes directly impact SNF workforce requirements and operational procedures.'
                }
            elif 'payment' in title_lower + summary_lower or 'reimbursement' in title_lower + summary_lower:
                return {
                    'relevant': True,
                    'impact_type': 'financial',
                    'relevance_score': 70,
                    'explanation': 'Payment changes may affect SNF reimbursement rates and financial planning.'
                }
            else:
                return {
                    'relevant': True,
                    'impact_type': 'direct',
                    'relevance_score': 60,
                    'explanation': 'Healthcare regulation that may have direct effects on SNF operations and compliance.'
                }

        # Low relevance - Other healthcare with competitive impact
        elif any(keyword in title_lower for keyword in ['hospital', 'home health', 'ltch', 'irf', 'rehabilitation']):
            return {
                'relevant': True,
                'impact_type': 'competitive',
                'relevance_score': 40,
                'explanation': 'Changes to competing healthcare providers may affect SNF patient referrals and market position.'
            }

        # No relevance - Non-healthcare
        else:
            return {
                'relevant': False,
                'impact_type': 'other',
                'relevance_score': 5,
                'explanation': 'Not healthcare-related. No impact on SNF operations or compliance.'
            }

def test_with_multiple_bills():
    """Test the analyzer with various bill types"""
    print("🧪 TESTING GPT-4 BILL RELEVANCE ANALYZER (MOCK VERSION)")
    print("=" * 60)
    print("🎭 Using simulated GPT-4 responses for demonstration")
    print()

    # Initialize mock analyzer
    analyzer = MockBillRelevanceAnalyzer()

    # Test bills of different relevance levels
    test_bills = [
        {
            'title': 'Medicare Skilled Nursing Facility Prospective Payment System Updates for FY 2025',
            'summary': 'Updates Medicare PPS for SNFs including market basket update of 2.8%, nursing case mix methodology, new quality reporting requirements for falls and medication errors, enhanced staffing data collection, and value-based purchasing program modifications.'
        },
        {
            'title': 'Healthcare Quality Reporting Enhancement Act',
            'summary': 'Expands quality reporting requirements for Medicare providers, including new patient safety measures, infection control protocols, and performance benchmarking across healthcare settings.'
        },
        {
            'title': 'Hospital Readmission Reduction Program Extension',
            'summary': 'Extends and modifies the Hospital Readmission Reduction Program with new penalties for excessive readmissions and coordination requirements with post-acute care providers.'
        },
        {
            'title': 'Infrastructure Investment and Jobs Act Transportation Section',
            'summary': 'Authorizes federal spending on highway construction, bridge repairs, and public transportation systems. Includes provisions for rural road improvements and electric vehicle charging stations.'
        },
        {
            'title': 'Medicare Staffing Transparency and Accountability Act',
            'summary': 'Requires nursing homes and long-term care facilities to report detailed staffing information including RN hours per resident day, aide turnover rates, and administrative overhead costs.'
        }
    ]

    print(f"📊 Testing {len(test_bills)} bills with varying relevance levels:")
    print()

    results = []
    for i, bill in enumerate(test_bills, 1):
        print(f"🔍 Bill {i}: {bill['title'][:60]}...")

        analysis = analyzer.analyze_bill_relevance(bill['title'], bill['summary'])
        results.append({**bill, **analysis})

        # Display results
        relevance_emoji = "✅" if analysis['relevant'] else "❌"
        score_color = "🔴" if analysis['relevance_score'] >= 80 else "🟡" if analysis['relevance_score'] >= 50 else "🟢"

        print(f"   {relevance_emoji} Relevant: {'YES' if analysis['relevant'] else 'NO'}")
        print(f"   📊 Type: {analysis['impact_type'].title()}")
        print(f"   {score_color} Score: {analysis['relevance_score']}/100")
        print(f"   💭 {analysis['explanation'][:80]}...")
        print()

    # Summary statistics
    relevant_bills = [r for r in results if r['relevant']]
    high_impact = [r for r in results if r['relevance_score'] >= 70]

    print("📈 ANALYSIS SUMMARY:")
    print("-" * 30)
    print(f"📋 Total bills analyzed: {len(results)}")
    print(f"✅ SNF-relevant bills: {len(relevant_bills)}")
    print(f"🔴 High-impact bills (≥70): {len(high_impact)}")
    print()

    # Impact type distribution
    impact_types = {}
    for result in relevant_bills:
        impact_type = result['impact_type']
        impact_types[impact_type] = impact_types.get(impact_type, 0) + 1

    print("🎯 IMPACT TYPE DISTRIBUTION:")
    for impact_type, count in impact_types.items():
        print(f"   📊 {impact_type.title()}: {count} bills")

    print()
    print("✅ Mock testing completed successfully!")
    print("🔑 To use with real GPT-4, set OPENAI_API_KEY environment variable")

    return results

if __name__ == "__main__":
    test_with_multiple_bills()