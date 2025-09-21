#!/usr/bin/env python3
"""
Test GPT-4 Response Parsing
Verify the response parsing logic works correctly
"""

from bill_relevance_analyzer import BillRelevanceAnalyzer

def test_response_parsing():
    """Test various GPT-4 response formats"""
    print("🧪 TESTING GPT-4 RESPONSE PARSING")
    print("=" * 40)

    # Initialize analyzer (without API key for parsing tests)
    analyzer = BillRelevanceAnalyzer.__new__(BillRelevanceAnalyzer)

    # Test different response formats
    test_responses = [
        # Standard format
        {
            'name': 'Standard Format',
            'response': """RELEVANT: Yes
IMPACT_TYPE: Payment
RELEVANCE_SCORE: 85
EXPLANATION: This bill directly affects Medicare reimbursement rates for skilled nursing facilities, requiring updates to billing systems and financial projections."""
        },
        # Lowercase format
        {
            'name': 'Lowercase Format',
            'response': """relevant: yes
impact_type: quality
relevance_score: 72
explanation: New quality reporting requirements will impact SNF operations and compliance procedures."""
        },
        # Mixed case with extra text
        {
            'name': 'Mixed Case with Extra Text',
            'response': """Based on my analysis:

RELEVANT: No
IMPACT_TYPE: Other
RELEVANCE_SCORE: 15
EXPLANATION: This bill focuses on hospital operations and does not directly impact skilled nursing facilities.

Additional context: While healthcare-related, the scope is limited to acute care settings."""
        },
        # Minimal response
        {
            'name': 'Minimal Response',
            'response': """RELEVANT: Yes
IMPACT_TYPE: Staffing
RELEVANCE_SCORE: 90
EXPLANATION: Critical staffing requirements."""
        }
    ]

    for i, test in enumerate(test_responses, 1):
        print(f"\n🔍 Test {i}: {test['name']}")
        print(f"   📝 Response: {test['response'][:50]}...")

        # Parse the response
        result = analyzer._parse_gpt4_response(test['response'])

        # Display parsed results
        print(f"   ✅ Relevant: {result['relevant']}")
        print(f"   📊 Type: {result['impact_type']}")
        print(f"   📈 Score: {result['relevance_score']}")
        print(f"   💭 Explanation: {result['explanation'][:60]}...")

        # Validate parsing
        if result['relevance_score'] > 0 and result['explanation'] != 'No explanation provided':
            print(f"   ✅ Parsing: SUCCESS")
        else:
            print(f"   ❌ Parsing: FAILED")

    print(f"\n✅ Response parsing tests completed!")

if __name__ == "__main__":
    test_response_parsing()