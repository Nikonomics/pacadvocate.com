from sqlalchemy.orm import Session
from models.legislation import Bill, ImpactAnalysis, BillKeywordMatch
from typing import Optional, Dict, List
import openai
import os
import json
from datetime import datetime

class ImpactAnalyzer:
    def __init__(self, db: Session):
        self.db = db
        self.openai_client = None
        self._setup_openai()

    def _setup_openai(self):
        """Setup OpenAI client if API key is available"""
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            openai.api_key = api_key
            self.openai_client = openai

    def analyze_bill_impact(self, bill_id: int, user_id: Optional[int] = None) -> Optional[ImpactAnalysis]:
        """Generate AI-powered impact analysis for a bill"""
        bill = self.db.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            return None

        # Get keyword matches to understand relevance
        keyword_matches = self.db.query(BillKeywordMatch).filter(
            BillKeywordMatch.bill_id == bill_id
        ).all()

        # Generate analysis
        analysis_data = self._generate_analysis(bill, keyword_matches)

        if not analysis_data:
            return None

        # Create impact analysis record
        impact_analysis = ImpactAnalysis(
            bill_id=bill_id,
            analysis_version="1.0",
            impact_score=analysis_data.get('impact_score'),
            impact_category=analysis_data.get('impact_category'),
            summary=analysis_data.get('summary'),
            detailed_analysis=analysis_data.get('detailed_analysis'),
            key_provisions=analysis_data.get('key_provisions'),
            affected_areas=analysis_data.get('affected_areas'),
            recommendation=analysis_data.get('recommendation'),
            confidence_score=analysis_data.get('confidence_score'),
            model_used=analysis_data.get('model_used'),
            analysis_prompt=analysis_data.get('analysis_prompt'),
            created_by_user_id=user_id
        )

        self.db.add(impact_analysis)
        self.db.commit()
        self.db.refresh(impact_analysis)

        return impact_analysis

    def _generate_analysis(self, bill: Bill, keyword_matches: List[BillKeywordMatch]) -> Optional[Dict]:
        """Generate analysis using AI or rule-based approach"""
        if self.openai_client and hasattr(openai, 'ChatCompletion'):
            return self._generate_openai_analysis(bill, keyword_matches)
        else:
            return self._generate_rule_based_analysis(bill, keyword_matches)

    def _generate_openai_analysis(self, bill: Bill, keyword_matches: List[BillKeywordMatch]) -> Optional[Dict]:
        """Generate analysis using OpenAI"""
        try:
            # Prepare keyword context
            keyword_context = self._prepare_keyword_context(keyword_matches)

            # Create analysis prompt
            prompt = self._create_analysis_prompt(bill, keyword_context)

            # Call OpenAI
            response = self.openai_client.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert healthcare policy analyst specializing in skilled nursing facility (SNF) regulations and legislation."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=2000,
                temperature=0.3
            )

            # Parse response
            analysis_text = response.choices[0].message.content
            return self._parse_openai_response(analysis_text, prompt)

        except Exception as e:
            print(f"OpenAI analysis failed: {e}")
            return self._generate_rule_based_analysis(bill, keyword_matches)

    def _generate_rule_based_analysis(self, bill: Bill, keyword_matches: List[BillKeywordMatch]) -> Dict:
        """Generate analysis using rule-based approach"""
        # Calculate impact score based on keywords
        impact_score = self._calculate_rule_based_impact_score(keyword_matches)

        # Determine category based on keywords
        impact_category = self._determine_impact_category(keyword_matches)

        # Generate summary
        summary = self._generate_rule_based_summary(bill, keyword_matches, impact_score)

        return {
            'impact_score': impact_score,
            'impact_category': impact_category,
            'summary': summary,
            'detailed_analysis': self._generate_detailed_analysis(bill, keyword_matches),
            'key_provisions': self._identify_key_provisions(bill, keyword_matches),
            'affected_areas': self._identify_affected_areas(keyword_matches),
            'recommendation': self._generate_recommendation(impact_score, impact_category),
            'confidence_score': min(0.7, len(keyword_matches) * 0.1),  # Rule-based has lower confidence
            'model_used': 'rule-based',
            'analysis_prompt': 'Rule-based analysis using keyword matching and predefined rules'
        }

    def _prepare_keyword_context(self, keyword_matches: List[BillKeywordMatch]) -> str:
        """Prepare keyword context for AI analysis"""
        if not keyword_matches:
            return "No significant keywords detected."

        context_parts = []
        for match in keyword_matches:
            keyword = self.db.query(self.db.query(BillKeywordMatch).filter(
                BillKeywordMatch.id == match.id
            ).first().keyword).first()

            if keyword:
                context_parts.append(
                    f"- {keyword.term} ({keyword.category}): "
                    f"{match.match_count} matches, {match.confidence_score:.1%} confidence"
                )

        return "\n".join(context_parts)

    def _create_analysis_prompt(self, bill: Bill, keyword_context: str) -> str:
        """Create analysis prompt for AI"""
        return f"""
Analyze the following legislation for its potential impact on skilled nursing facilities (SNFs):

**Bill Information:**
- Number: {bill.bill_number}
- Title: {bill.title}
- Status: {bill.status}
- Sponsor: {bill.sponsor}
- Summary: {bill.summary or 'Not available'}

**Relevant Keywords Detected:**
{keyword_context}

**Analysis Request:**
Please provide a comprehensive analysis including:

1. **Impact Score (0-100)**: Rate the potential impact on SNFs
2. **Impact Category**: Primary area of impact (Financial, Operational, Regulatory, Quality, Staffing)
3. **Summary**: Brief 2-3 sentence overview of the bill's significance
4. **Key Provisions**: List the most important provisions affecting SNFs
5. **Affected Areas**: Specific SNF operations that would be impacted
6. **Recommendation**: Suggested action for SNF stakeholders
7. **Confidence**: Your confidence level (0-1) in this analysis

Format your response as structured text that can be parsed into these categories.
"""

    def _parse_openai_response(self, response: str, prompt: str) -> Dict:
        """Parse OpenAI response into structured data"""
        # This is a simplified parser - in production, you might use more sophisticated parsing
        lines = response.split('\n')

        analysis_data = {
            'model_used': 'gpt-4',
            'analysis_prompt': prompt,
            'detailed_analysis': response
        }

        # Extract specific sections (basic implementation)
        current_section = None
        for line in lines:
            line = line.strip()

            if 'impact score' in line.lower():
                # Extract numeric score
                import re
                scores = re.findall(r'\d+', line)
                if scores:
                    analysis_data['impact_score'] = min(100, max(0, int(scores[0])))

            elif 'impact category' in line.lower():
                # Extract category
                categories = ['Financial', 'Operational', 'Regulatory', 'Quality', 'Staffing']
                for category in categories:
                    if category.lower() in line.lower():
                        analysis_data['impact_category'] = category
                        break

            elif 'summary' in line.lower() and ':' in line:
                analysis_data['summary'] = line.split(':', 1)[1].strip()

        return analysis_data

    def _calculate_rule_based_impact_score(self, keyword_matches: List[BillKeywordMatch]) -> float:
        """Calculate impact score using rule-based approach"""
        if not keyword_matches:
            return 0.0

        # Weight by keyword importance and confidence
        weighted_score = 0
        total_weight = 0

        for match in keyword_matches:
            keyword = self.db.query(self.db.query(BillKeywordMatch).filter(
                BillKeywordMatch.id == match.id
            ).first().keyword).first()

            if keyword:
                weight = keyword.importance_weight * match.confidence_score
                weighted_score += weight * 20  # Scale to 0-100
                total_weight += weight

        if total_weight == 0:
            return 0.0

        impact_score = min(100.0, weighted_score / total_weight)
        return round(impact_score, 1)

    def _determine_impact_category(self, keyword_matches: List[BillKeywordMatch]) -> str:
        """Determine primary impact category"""
        category_weights = {}

        for match in keyword_matches:
            keyword = self.db.query(self.db.query(BillKeywordMatch).filter(
                BillKeywordMatch.id == match.id
            ).first().keyword).first()

            if keyword:
                category = keyword.category
                weight = match.confidence_score * keyword.importance_weight

                # Map keyword categories to impact categories
                impact_category = self._map_keyword_to_impact_category(category)
                category_weights[impact_category] = category_weights.get(impact_category, 0) + weight

        if not category_weights:
            return "Regulatory"

        return max(category_weights.items(), key=lambda x: x[1])[0]

    def _map_keyword_to_impact_category(self, keyword_category: str) -> str:
        """Map keyword category to impact category"""
        mapping = {
            'SNF': 'Operational',
            'Medicare': 'Financial',
            'Medicaid': 'Financial',
            'PDPM': 'Financial',
            'Staffing': 'Staffing',
            'Quality': 'Quality',
            'Regulatory': 'Regulatory',
            'Financial': 'Financial',
            'Safety': 'Quality',
            'Technology': 'Operational'
        }
        return mapping.get(keyword_category, 'Regulatory')

    def _generate_rule_based_summary(self, bill: Bill, keyword_matches: List[BillKeywordMatch], impact_score: float) -> str:
        """Generate a rule-based summary"""
        if impact_score > 70:
            impact_level = "high"
        elif impact_score > 40:
            impact_level = "moderate"
        else:
            impact_level = "low"

        keyword_count = len(keyword_matches)

        return f"This bill shows {impact_level} potential impact on SNFs with {keyword_count} relevant keywords identified. The legislation may affect SNF operations and should be monitored for developments."

    def _generate_detailed_analysis(self, bill: Bill, keyword_matches: List[BillKeywordMatch]) -> str:
        """Generate detailed analysis"""
        analysis_parts = []

        analysis_parts.append(f"Bill {bill.bill_number}: {bill.title}")

        if keyword_matches:
            analysis_parts.append("\nKey areas of relevance:")
            for match in keyword_matches[:5]:  # Top 5 matches
                keyword = self.db.query(self.db.query(BillKeywordMatch).filter(
                    BillKeywordMatch.id == match.id
                ).first().keyword).first()
                if keyword:
                    analysis_parts.append(f"- {keyword.term} ({match.confidence_score:.1%} confidence)")

        if bill.summary:
            analysis_parts.append(f"\nBill Summary: {bill.summary}")

        return "\n".join(analysis_parts)

    def _identify_key_provisions(self, bill: Bill, keyword_matches: List[BillKeywordMatch]) -> str:
        """Identify key provisions (simplified)"""
        provisions = []

        # This would be more sophisticated in a real implementation
        high_confidence_matches = [m for m in keyword_matches if m.confidence_score > 0.7]

        for match in high_confidence_matches[:3]:
            if match.context_snippet:
                provisions.append(match.context_snippet[:100] + "...")

        return json.dumps(provisions)

    def _identify_affected_areas(self, keyword_matches: List[BillKeywordMatch]) -> str:
        """Identify affected areas"""
        areas = set()

        for match in keyword_matches:
            keyword = self.db.query(self.db.query(BillKeywordMatch).filter(
                BillKeywordMatch.id == match.id
            ).first().keyword).first()
            if keyword:
                areas.add(keyword.category)

        return json.dumps(list(areas))

    def _generate_recommendation(self, impact_score: float, impact_category: str) -> str:
        """Generate recommendation based on impact"""
        if impact_score > 70:
            return f"High priority: This bill has significant {impact_category.lower()} implications for SNFs. Immediate review and stakeholder engagement recommended."
        elif impact_score > 40:
            return f"Monitor closely: This bill may have {impact_category.lower()} impacts on SNFs. Regular monitoring and preparation for potential changes advised."
        else:
            return f"Low priority: Limited {impact_category.lower()} impact expected. Periodic review sufficient."

    def get_bill_analysis(self, bill_id: int) -> Optional[ImpactAnalysis]:
        """Get the latest impact analysis for a bill"""
        return self.db.query(ImpactAnalysis).filter(
            ImpactAnalysis.bill_id == bill_id
        ).order_by(ImpactAnalysis.created_at.desc()).first()

    def get_high_impact_bills(self, min_score: float = 70.0, limit: int = 20) -> List[ImpactAnalysis]:
        """Get bills with high impact scores"""
        return self.db.query(ImpactAnalysis).filter(
            ImpactAnalysis.impact_score >= min_score
        ).order_by(ImpactAnalysis.impact_score.desc()).limit(limit).all()