#!/usr/bin/env python3
"""
Analyze the top 5 highest-scoring bills using OpenAI GPT-4
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from models.legislation import Bill, ImpactAnalysis
from services.ai.bill_analysis_service import BillAnalysisService

def analyze_top_bills():
    """Analyze the top 5 highest-scoring bills using OpenAI GPT-4"""
    print("🧠 OpenAI GPT-4 Bill Analysis")
    print("=" * 60)

    try:
        # Initialize analysis service
        print("🔄 Initializing OpenAI analysis service...")
        service = BillAnalysisService()
        print("✅ Service initialized successfully")

        # Connect to database
        database_url = os.getenv('DATABASE_URL', 'sqlite:///./snflegtracker.db')
        engine = create_engine(database_url)

        with Session(engine) as session:
            # Get top 5 bills by relevance score
            top_bills = session.query(Bill).filter(
                Bill.relevance_score.isnot(None)
            ).order_by(Bill.relevance_score.desc()).limit(5).all()

            if not top_bills:
                print("❌ No bills with relevance scores found")
                return

            print(f"\n📊 Found {len(top_bills)} top-scoring bills to analyze")

            total_cost = 0.0
            total_tokens = 0
            analyses_completed = 0

            for i, bill in enumerate(top_bills, 1):
                print(f"\n{'='*80}")
                print(f"ANALYZING BILL {i}/5: {bill.bill_number}")
                print(f"{'='*80}")

                print(f"📋 Bill Details:")
                print(f"   Title: {bill.title[:80]}...")
                print(f"   Source: {bill.source}")
                print(f"   State: {bill.state_or_federal}")
                print(f"   Relevance Score: {bill.relevance_score:.1f}/100")

                # Check if we have content to analyze
                bill_content = ""
                if bill.title:
                    bill_content += f"TITLE: {bill.title}\n\n"
                if bill.summary:
                    bill_content += f"SUMMARY: {bill.summary}\n\n"
                if bill.full_text:
                    # Limit full text to prevent token overflow
                    full_text = bill.full_text[:5000] if len(bill.full_text) > 5000 else bill.full_text
                    bill_content += f"FULL TEXT: {full_text}\n"

                if len(bill_content.strip()) < 50:
                    print("   ⚠️  Insufficient content for analysis - skipping")
                    continue

                try:
                    print(f"\n🔄 Starting GPT-4 analysis...")
                    start_time = datetime.now()

                    # Analyze the bill
                    analysis, metrics = service.analyze_bill_from_db(bill.id)

                    end_time = datetime.now()
                    duration = (end_time - start_time).total_seconds()

                    print(f"✅ Analysis completed in {duration:.1f} seconds")

                    # Display results
                    print(f"\n📊 Analysis Metrics:")
                    print(f"   Model Used: {analysis.model_used}")
                    print(f"   Tokens Used: {analysis.tokens_used:,}")
                    print(f"   Estimated Cost: ${analysis.estimated_cost:.4f}")
                    print(f"   Confidence: {analysis.analysis_confidence:.1%}")
                    print(f"   Response Time: {duration:.1f}s")

                    print(f"\n📋 Analysis Results:")
                    print(f"   Summary: {analysis.one_line_summary}")

                    print(f"\n   Key SNF Provisions ({len(analysis.key_provisions_snf)} items):")
                    for j, provision in enumerate(analysis.key_provisions_snf[:3], 1):
                        print(f"      {j}. {provision}")
                    if len(analysis.key_provisions_snf) > 3:
                        print(f"      ... and {len(analysis.key_provisions_snf) - 3} more")

                    print(f"\n   Financial Impact:")
                    print(f"      {analysis.financial_impact[:150]}{'...' if len(analysis.financial_impact) > 150 else ''}")

                    print(f"\n   Implementation Timeline:")
                    print(f"      {analysis.implementation_timeline[:150]}{'...' if len(analysis.implementation_timeline) > 150 else ''}")

                    print(f"\n   Required Actions ({len(analysis.action_required)} items):")
                    for j, action in enumerate(analysis.action_required[:2], 1):
                        print(f"      {j}. {action}")
                    if len(analysis.action_required) > 2:
                        print(f"      ... and {len(analysis.action_required) - 2} more")

                    # Track totals
                    total_cost += analysis.estimated_cost
                    total_tokens += analysis.tokens_used
                    analyses_completed += 1

                except Exception as e:
                    print(f"❌ Analysis failed: {e}")
                    continue

            # Display summary statistics
            print(f"\n{'='*80}")
            print(f"ANALYSIS SUMMARY")
            print(f"{'='*80}")

            print(f"📊 Overall Statistics:")
            print(f"   Bills Analyzed: {analyses_completed}/5")
            print(f"   Total Tokens Used: {total_tokens:,}")
            print(f"   Total Estimated Cost: ${total_cost:.4f}")
            print(f"   Average Cost per Bill: ${total_cost/max(analyses_completed, 1):.4f}")

            # Get service statistics
            stats = service.get_analysis_stats()
            if stats:
                print(f"\n📈 Service Statistics:")
                print(f"   Total Analyses in DB: {stats.get('total_analyses', 0)}")
                print(f"   Recent Analyses (30 days): {stats.get('recent_analyses_30_days', 0)}")
                print(f"   Total Service Cost: ${stats.get('total_estimated_cost', 0.0):.4f}")
                print(f"   Model Usage: {stats.get('model_usage', {})}")
                print(f"   Cache Size: {stats.get('cache_size', 0)}")

            print(f"\n✅ Bill analysis completed successfully!")

    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()

def show_analysis_results():
    """Show stored analysis results from database"""
    print("\n🔍 Stored Analysis Results")
    print("-" * 60)

    try:
        database_url = os.getenv('DATABASE_URL', 'sqlite:///./snflegtracker.db')
        engine = create_engine(database_url)

        with Session(engine) as session:
            # Get recent analyses with bill information
            analyses = session.query(ImpactAnalysis, Bill).join(Bill).order_by(
                ImpactAnalysis.created_at.desc()
            ).limit(5).all()

            for analysis, bill in analyses:
                print(f"\n📋 {bill.bill_number} (Score: {bill.relevance_score:.1f}/100)")
                print(f"   Summary: {analysis.summary}")
                print(f"   Confidence: {analysis.confidence_score:.1%}")
                print(f"   Created: {analysis.created_at.strftime('%Y-%m-%d %H:%M')}")

                if analysis.analysis_prompt:
                    try:
                        import json
                        summary_data = json.loads(analysis.analysis_prompt)
                        model_used = summary_data.get('model_used', 'unknown')
                        cost = summary_data.get('estimated_cost', 0.0)
                        print(f"   Model: {model_used} | Cost: ${cost:.4f}")
                    except:
                        pass

    except Exception as e:
        print(f"❌ Error showing results: {e}")

if __name__ == "__main__":
    analyze_top_bills()
    show_analysis_results()