#!/usr/bin/env python3
"""
OpenAI GPT-4 Bill Analysis Service
Generates structured analysis of legislation for skilled nursing facilities
"""

import os
import sys
import json
import hashlib
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, asdict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import openai
import tiktoken
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from models.legislation import Bill, ImpactAnalysis

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class BillAnalysis:
    """Structured bill analysis result"""
    one_line_summary: str
    key_provisions_snf: List[str]
    financial_impact: str
    implementation_timeline: str
    action_required: List[str]
    analysis_confidence: float = 0.0
    model_used: str = ""
    tokens_used: int = 0
    estimated_cost: float = 0.0

@dataclass
class AnalysisMetrics:
    """Analysis performance metrics"""
    tokens_input: int = 0
    tokens_output: int = 0
    total_tokens: int = 0
    model_used: str = ""
    response_time: float = 0.0
    estimated_cost: float = 0.0
    cache_hit: bool = False

class BillAnalysisService:
    """OpenAI-powered bill analysis service with caching and cost tracking"""

    # Model pricing (per 1k tokens as of 2024)
    MODEL_PRICING = {
        'gpt-4o': {'input': 0.0025, 'output': 0.01},
        'gpt-4o-mini': {'input': 0.00015, 'output': 0.0006},
        'gpt-4-turbo': {'input': 0.01, 'output': 0.03},
        'gpt-3.5-turbo': {'input': 0.0015, 'output': 0.002}
    }

    def __init__(self, api_key: str = None, database_url: str = None):
        """
        Initialize the bill analysis service

        Args:
            api_key: OpenAI API key
            database_url: Database connection URL
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY environment variable.")

        # Initialize OpenAI client
        openai.api_key = self.api_key
        self.client = openai.OpenAI(api_key=self.api_key)

        # Database setup
        db_url = database_url or os.getenv('DATABASE_URL', 'sqlite:///./snflegtracker.db')
        self.engine = create_engine(db_url)

        # Initialize tokenizer for GPT-4
        self.tokenizer = tiktoken.encoding_for_model("gpt-4o")

        # Cache for analysis results
        self.cache = {}
        self.cache_expiry = timedelta(days=7)  # Cache for 7 days

        # System prompt for analysis
        self.system_prompt = """You are an expert healthcare policy analyst specializing in skilled nursing facility (SNF) regulations and legislation.

Analyze the provided bill text and generate a structured analysis focused on how it affects skilled nursing facilities.

Respond ONLY with a valid JSON object containing these exact fields:
{
    "one_line_summary": "Brief one-sentence summary of the bill",
    "key_provisions_snf": ["List of key provisions that directly affect skilled nursing facilities"],
    "financial_impact": "Description of potential financial impact on SNFs (costs, savings, reimbursement changes)",
    "implementation_timeline": "Timeline for implementation and key dates",
    "action_required": ["List of specific actions SNFs may need to take"],
    "analysis_confidence": 0.85
}

Focus on:
- Medicare/Medicaid reimbursement changes
- Quality reporting requirements
- Staffing mandates
- Regulatory compliance
- Patient safety standards
- Long-term care provisions

If the bill has minimal relevance to SNFs, indicate this clearly but still provide the structured analysis."""

        logger.info("Bill Analysis Service initialized")

    def _calculate_text_hash(self, text: str) -> str:
        """Calculate hash of text for caching"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        try:
            return len(self.tokenizer.encode(text))
        except Exception as e:
            logger.error(f"Error counting tokens: {e}")
            # Fallback estimation: ~4 characters per token
            return len(text) // 4

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate estimated cost for API call"""
        if model not in self.MODEL_PRICING:
            model = 'gpt-4o'  # Default fallback

        pricing = self.MODEL_PRICING[model]
        input_cost = (input_tokens / 1000) * pricing['input']
        output_cost = (output_tokens / 1000) * pricing['output']

        return input_cost + output_cost

    def _get_cached_analysis(self, text_hash: str) -> Optional[BillAnalysis]:
        """Get cached analysis if available and not expired"""
        if text_hash in self.cache:
            cached_data = self.cache[text_hash]
            if datetime.now() - cached_data['timestamp'] < self.cache_expiry:
                logger.info("Using cached analysis")
                return BillAnalysis(**cached_data['analysis'])
        return None

    def _cache_analysis(self, text_hash: str, analysis: BillAnalysis):
        """Cache analysis result"""
        self.cache[text_hash] = {
            'analysis': asdict(analysis),
            'timestamp': datetime.now()
        }

    def _call_openai_api(self, bill_text: str, model: str = "gpt-4o") -> Tuple[Dict, AnalysisMetrics]:
        """
        Call OpenAI API with error handling and metrics tracking

        Args:
            bill_text: Bill text to analyze
            model: OpenAI model to use

        Returns:
            Tuple of (analysis_dict, metrics)
        """
        start_time = time.time()

        # Count input tokens
        user_prompt = f"Analyze this bill:\n\n{bill_text}"
        input_tokens = self._count_tokens(self.system_prompt + user_prompt)

        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )

            # Extract response and count tokens
            response_text = response.choices[0].message.content
            output_tokens = response.usage.completion_tokens if response.usage else self._count_tokens(response_text)
            total_tokens = response.usage.total_tokens if response.usage else input_tokens + output_tokens

            # Calculate metrics
            response_time = time.time() - start_time
            cost = self._calculate_cost(model, input_tokens, output_tokens)

            metrics = AnalysisMetrics(
                tokens_input=input_tokens,
                tokens_output=output_tokens,
                total_tokens=total_tokens,
                model_used=model,
                response_time=response_time,
                estimated_cost=cost,
                cache_hit=False
            )

            # Parse JSON response (handle markdown code blocks)
            try:
                # Clean up response (remove markdown code blocks if present)
                clean_response = response_text.strip()
                if clean_response.startswith('```json'):
                    clean_response = clean_response[7:]
                if clean_response.endswith('```'):
                    clean_response = clean_response[:-3]
                clean_response = clean_response.strip()

                analysis_dict = json.loads(clean_response)
                return analysis_dict, metrics
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response from {model}: {e}")
                logger.error(f"Raw response: {response_text}")
                raise

        except Exception as e:
            logger.error(f"OpenAI API call failed with {model}: {e}")
            raise

    def analyze_bill(self, bill_text: str, bill_id: int = None, force_refresh: bool = False) -> Tuple[BillAnalysis, AnalysisMetrics]:
        """
        Analyze a bill with caching and fallback mechanisms

        Args:
            bill_text: Full text of the bill to analyze
            bill_id: Optional bill ID for database operations
            force_refresh: Force new analysis even if cached

        Returns:
            Tuple of (BillAnalysis, AnalysisMetrics)
        """
        logger.info(f"Starting analysis for bill {bill_id or 'unknown'}")

        # Check cache first (unless force refresh)
        text_hash = self._calculate_text_hash(bill_text)
        if not force_refresh:
            cached_analysis = self._get_cached_analysis(text_hash)
            if cached_analysis:
                metrics = AnalysisMetrics(cache_hit=True)
                return cached_analysis, metrics

        # Truncate bill text if too long (keep first 10k tokens worth)
        max_chars = 40000  # ~10k tokens worth of text
        if len(bill_text) > max_chars:
            bill_text = bill_text[:max_chars] + "\n\n[Text truncated due to length]"
            logger.warning(f"Bill text truncated to {max_chars} characters")

        # Try GPT-4o first
        models_to_try = ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]

        for model in models_to_try:
            try:
                logger.info(f"Attempting analysis with {model}")
                analysis_dict, metrics = self._call_openai_api(bill_text, model)

                # Create BillAnalysis object
                analysis = BillAnalysis(
                    one_line_summary=analysis_dict.get('one_line_summary', ''),
                    key_provisions_snf=analysis_dict.get('key_provisions_snf', []),
                    financial_impact=analysis_dict.get('financial_impact', ''),
                    implementation_timeline=analysis_dict.get('implementation_timeline', ''),
                    action_required=analysis_dict.get('action_required', []),
                    analysis_confidence=analysis_dict.get('analysis_confidence', 0.0),
                    model_used=model,
                    tokens_used=metrics.total_tokens,
                    estimated_cost=metrics.estimated_cost
                )

                # Cache successful analysis
                self._cache_analysis(text_hash, analysis)

                logger.info(f"Analysis completed successfully with {model}")
                logger.info(f"Cost: ${metrics.estimated_cost:.4f}, Tokens: {metrics.total_tokens}")

                return analysis, metrics

            except Exception as e:
                logger.error(f"Analysis failed with {model}: {e}")
                if model == models_to_try[-1]:  # Last model failed
                    raise Exception(f"All models failed. Last error: {e}")
                continue

        # Should not reach here, but just in case
        raise Exception("No models available for analysis")

    def store_analysis_in_db(self, bill_id: int, analysis: BillAnalysis, metrics: AnalysisMetrics) -> bool:
        """
        Store analysis results in the ImpactAnalysis table

        Args:
            bill_id: Bill ID to associate with
            analysis: Analysis results
            metrics: Performance metrics

        Returns:
            True if stored successfully
        """
        try:
            with Session(self.engine) as session:
                # Check if analysis already exists
                existing = session.query(ImpactAnalysis).filter(
                    ImpactAnalysis.bill_id == bill_id
                ).first()

                if existing:
                    # Update existing analysis
                    existing.summary = analysis.one_line_summary
                    existing.key_provisions = json.dumps(analysis.key_provisions_snf)
                    existing.detailed_analysis = f"Financial Impact: {analysis.financial_impact}\n\nImplementation Timeline: {analysis.implementation_timeline}"
                    existing.recommendation = "\n".join(analysis.action_required)
                    existing.confidence_score = analysis.analysis_confidence

                    # Store metrics in analysis_prompt field as JSON
                    existing.analysis_prompt = json.dumps({
                        'model_used': analysis.model_used,
                        'tokens_used': analysis.tokens_used,
                        'estimated_cost': analysis.estimated_cost,
                        'cache_hit': metrics.cache_hit,
                        'response_time': metrics.response_time
                    })

                    logger.info(f"Updated existing analysis for bill {bill_id}")

                else:
                    # Create new analysis
                    impact_analysis = ImpactAnalysis(
                        bill_id=bill_id,
                        summary=analysis.one_line_summary,
                        key_provisions=json.dumps(analysis.key_provisions_snf),
                        detailed_analysis=f"Financial Impact: {analysis.financial_impact}\n\nImplementation Timeline: {analysis.implementation_timeline}",
                        recommendation="\n".join(analysis.action_required),
                        confidence_score=analysis.analysis_confidence,
                        model_used=analysis.model_used,
                        analysis_prompt=json.dumps({
                            'model_used': analysis.model_used,
                            'tokens_used': analysis.tokens_used,
                            'estimated_cost': analysis.estimated_cost,
                            'cache_hit': metrics.cache_hit,
                            'response_time': metrics.response_time
                        })
                    )

                    session.add(impact_analysis)
                    logger.info(f"Created new analysis for bill {bill_id}")

                session.commit()
                return True

        except Exception as e:
            logger.error(f"Failed to store analysis in database: {e}")
            return False

    def analyze_bill_from_db(self, bill_id: int, force_refresh: bool = False) -> Tuple[BillAnalysis, AnalysisMetrics]:
        """
        Analyze a bill by fetching it from the database

        Args:
            bill_id: Bill ID to analyze
            force_refresh: Force new analysis even if cached

        Returns:
            Tuple of (BillAnalysis, AnalysisMetrics)
        """
        with Session(self.engine) as session:
            bill = session.query(Bill).filter(Bill.id == bill_id).first()

            if not bill:
                raise ValueError(f"Bill with ID {bill_id} not found")

            # Combine title, summary, and full_text
            bill_text = f"TITLE: {bill.title or ''}\n\n"
            if bill.summary:
                bill_text += f"SUMMARY: {bill.summary}\n\n"
            if bill.full_text:
                bill_text += f"FULL TEXT: {bill.full_text}"

            # Analyze the bill
            analysis, metrics = self.analyze_bill(bill_text, bill_id, force_refresh)

            # Store results in database
            self.store_analysis_in_db(bill_id, analysis, metrics)

            return analysis, metrics

    def get_analysis_stats(self) -> Dict:
        """Get analysis statistics from database"""
        try:
            with Session(self.engine) as session:
                total_analyses = session.query(ImpactAnalysis).count()

                # Get recent analyses (last 30 days)
                thirty_days_ago = datetime.utcnow() - timedelta(days=30)
                recent_analyses = session.query(ImpactAnalysis).filter(
                    ImpactAnalysis.created_at >= thirty_days_ago
                ).count()

                # Calculate total estimated costs
                analyses_with_costs = session.query(ImpactAnalysis).all()
                total_cost = 0.0
                model_usage = {}

                for analysis in analyses_with_costs:
                    if analysis.analysis_prompt:
                        try:
                            summary_data = json.loads(analysis.analysis_prompt)
                            cost = summary_data.get('estimated_cost', 0.0)
                            model = summary_data.get('model_used', 'unknown')

                            total_cost += cost
                            model_usage[model] = model_usage.get(model, 0) + 1
                        except:
                            continue

                return {
                    'total_analyses': total_analyses,
                    'recent_analyses_30_days': recent_analyses,
                    'total_estimated_cost': round(total_cost, 4),
                    'model_usage': model_usage,
                    'cache_size': len(self.cache),
                    'last_updated': datetime.utcnow().isoformat()
                }

        except Exception as e:
            logger.error(f"Failed to get analysis stats: {e}")
            return {}

def test_analysis_service():
    """Test the bill analysis service"""
    print("🧪 Testing Bill Analysis Service")
    print("=" * 60)

    try:
        # Initialize service
        service = BillAnalysisService()
        print("✅ Service initialized successfully")

        # Test with sample bill text
        sample_bill = """
        TITLE: Medicare Part A Payment Reform for Skilled Nursing Facilities

        SUMMARY: A bill to reform Medicare Part A payment system for skilled nursing facilities
        and establish new quality measures for post-acute care services.

        FULL TEXT: This legislation addresses the Medicare Part A payment system for skilled
        nursing facilities (SNFs) and establishes comprehensive quality measures for post-acute
        care services. The bill mandates minimum staffing ratios of 2.8 hours of nursing care
        per resident per day, with implementation required within 12 months of enactment.
        Facilities must achieve 4-star quality ratings to receive full reimbursement rates.
        The legislation also establishes a $500 million fund for workforce development and
        requires quarterly reporting on patient outcomes and safety metrics.
        """

        print("\n🔄 Testing analysis...")
        analysis, metrics = service.analyze_bill(sample_bill)

        print(f"\n📊 Analysis Results:")
        print(f"Model Used: {analysis.model_used}")
        print(f"Tokens Used: {analysis.tokens_used}")
        print(f"Estimated Cost: ${analysis.estimated_cost:.4f}")
        print(f"Confidence: {analysis.analysis_confidence:.1%}")

        print(f"\n📋 Analysis Content:")
        print(f"Summary: {analysis.one_line_summary}")
        print(f"Key Provisions: {len(analysis.key_provisions_snf)} items")
        print(f"Financial Impact: {analysis.financial_impact[:100]}...")
        print(f"Action Items: {len(analysis.action_required)} items")

        print("\n✅ Bill Analysis Service test completed successfully!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_analysis_service()