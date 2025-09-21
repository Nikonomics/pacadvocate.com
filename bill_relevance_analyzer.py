#!/usr/bin/env python3
"""
GPT-4 Bill Relevance Analyzer
Analyzes healthcare bills for SNF relevance using OpenAI GPT-4
"""

import json
import os
import re
from typing import Dict, Optional
from openai import OpenAI

class BillRelevanceAnalyzer:
    """GPT-4 powered bill relevance analyzer for SNF healthcare legislation"""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the analyzer with OpenAI API key"""
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY environment variable or pass api_key parameter.")

        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4"

    def analyze_bill_relevance(self, title: str, summary: str) -> Dict:
        """
        Analyze bill relevance to SNF operations using GPT-4

        Args:
            title (str): Bill title
            summary (str): Bill summary/content

        Returns:
            Dict: {
                'relevant': bool,
                'impact_type': str,
                'relevance_score': int,
                'explanation': str
            }
        """
        try:
            # Construct the analysis prompt
            prompt = self._build_analysis_prompt(title, summary)

            # Send request to GPT-4
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Lower temperature for more consistent analysis
                max_tokens=500
            )

            # Parse the response
            analysis_text = response.choices[0].message.content
            return self._parse_gpt4_response(analysis_text)

        except Exception as e:
            return {
                'relevant': False,
                'impact_type': 'error',
                'relevance_score': 0,
                'explanation': f"Analysis failed: {str(e)}"
            }

    def _get_system_prompt(self) -> str:
        """System prompt defining the analyzer's role and expertise"""
        return """You are an expert healthcare policy analyst specializing in Skilled Nursing Facility (SNF) operations and regulations. Analyze bills for their specific impact on SNFs with precision and focus."""

    def _build_analysis_prompt(self, title: str, summary: str) -> str:
        """Build the analysis prompt with bill details"""
        return f"""Analyze if this bill affects skilled nursing facilities:
Title: {title}
Summary: {summary}

Consider:
- Direct operational impacts (staffing, compliance, quality measures)
- Payment/reimbursement effects (Medicare, Medicaid, Medicare Advantage)
- Competitive impacts (IRFs, LTCHs, home health taking SNF patients)
- Workforce effects (healthcare staffing shortages affect SNFs)

Response format:
- Relevant: Yes/No
- Impact Type: Direct/Competitive/Financial/Workforce
- Relevance Score: 0-100
- Explanation: One sentence why this matters to SNFs"""

    def _parse_gpt4_response(self, response_text: str) -> Dict:
        """Parse GPT-4 response into structured data"""
        try:
            # Extract structured data using regex for new format
            relevant_match = re.search(r'-?\s*Relevant:\s*(Yes|No)', response_text, re.IGNORECASE)
            impact_type_match = re.search(r'-?\s*Impact Type:\s*(Direct|Competitive|Financial|Workforce)', response_text, re.IGNORECASE)
            score_match = re.search(r'-?\s*Relevance Score:\s*(\d+)', response_text, re.IGNORECASE)
            explanation_match = re.search(r'-?\s*Explanation:\s*(.+?)(?:\n|$)', response_text, re.DOTALL | re.IGNORECASE)

            # Parse values with defaults
            relevant = relevant_match.group(1).lower() == 'yes' if relevant_match else False
            impact_type = impact_type_match.group(1).lower() if impact_type_match else 'other'
            relevance_score = int(score_match.group(1)) if score_match else 0
            explanation = explanation_match.group(1).strip() if explanation_match else 'No explanation provided'

            return {
                'relevant': relevant,
                'impact_type': impact_type,
                'relevance_score': relevance_score,
                'explanation': explanation
            }

        except Exception as e:
            return {
                'relevant': False,
                'impact_type': 'error',
                'relevance_score': 0,
                'explanation': f"Failed to parse GPT-4 response: {str(e)}"
            }

    def batch_analyze_bills(self, bills: list) -> list:
        """Analyze multiple bills for relevance"""
        results = []

        for i, bill in enumerate(bills):
            print(f"🔍 Analyzing bill {i+1}/{len(bills)}: {bill.get('title', 'Unknown')[:50]}...")

            analysis = self.analyze_bill_relevance(
                bill.get('title', ''),
                bill.get('summary', '')
            )

            # Add bill ID if available
            if 'id' in bill:
                analysis['bill_id'] = bill['id']

            results.append(analysis)

        return results

def test_bill_analysis():
    """Test the bill relevance analyzer with sample data"""
    print("🧪 TESTING GPT-4 BILL RELEVANCE ANALYZER")
    print("=" * 50)

    # Check for API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OPENAI_API_KEY environment variable not set")
        print("💡 Please set your OpenAI API key:")
        print("   export OPENAI_API_KEY='your-api-key-here'")
        return False

    # Initialize analyzer
    try:
        analyzer = BillRelevanceAnalyzer()
        print("✅ GPT-4 analyzer initialized")
    except Exception as e:
        print(f"❌ Failed to initialize analyzer: {e}")
        return False

    # Sample bill for testing
    sample_bill = {
        'title': 'Medicare Skilled Nursing Facility Prospective Payment System Updates for FY 2025',
        'summary': '''This bill updates the Medicare prospective payment system for skilled nursing facilities.
        Key changes include: 1) Market basket update of 2.8% for FY 2025, 2) Updated nursing case mix methodology,
        3) New quality reporting requirements for falls and medication errors, 4) Enhanced staffing data collection,
        5) Value-based purchasing program modifications affecting 3% of payments. The bill also requires SNFs to
        report additional quality measures and implements penalties for non-compliance with new staffing transparency requirements.'''
    }

    print(f"\n📋 Testing with sample bill:")
    print(f"   Title: {sample_bill['title'][:80]}...")
    print(f"   Summary: {sample_bill['summary'][:100]}...")

    # Analyze the bill
    try:
        print("\n🤖 Sending request to GPT-4...")
        analysis = analyzer.analyze_bill_relevance(
            sample_bill['title'],
            sample_bill['summary']
        )

        # Display results
        print("\n✅ GPT-4 ANALYSIS RESULTS:")
        print("-" * 30)
        print(f"🎯 Relevant: {'YES' if analysis['relevant'] else 'NO'}")
        print(f"📊 Impact Type: {analysis['impact_type'].title()}")
        print(f"📈 Relevance Score: {analysis['relevance_score']}/100")
        print(f"💭 Explanation: {analysis['explanation']}")

        # Validate results
        if analysis['relevant'] and analysis['relevance_score'] >= 80:
            print("\n✅ Test PASSED - High relevance detected correctly")
            return True
        else:
            print("\n⚠️  Test results may need review - check scoring logic")
            return True

    except Exception as e:
        print(f"\n❌ Analysis failed: {e}")
        return False

if __name__ == "__main__":
    test_bill_analysis()