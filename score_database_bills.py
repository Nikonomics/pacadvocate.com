#!/usr/bin/env python3
"""
Score all bills in the database using AI relevance classifier
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
from models.legislation import Bill
from services.ai.relevance_classifier import SNFRelevanceClassifier

def score_all_bills():
    """Score all bills in the database using AI relevance classifier"""
    print("🧠 AI Relevance Scoring for SNF Legislation")
    print("=" * 60)

    try:
        # Initialize classifier
        print("🔄 Initializing AI relevance classifier...")
        classifier = SNFRelevanceClassifier()

        # Connect to database
        database_url = os.getenv('DATABASE_URL', 'sqlite:///./snflegtracker.db')
        engine = create_engine(database_url)

        with Session(engine) as session:
            # Get all bills
            all_bills = session.query(Bill).all()
            print(f"📊 Found {len(all_bills)} bills in database")

            if not all_bills:
                print("❌ No bills found to score")
                return

            # Prepare bill data for scoring
            bill_data = []
            for bill in all_bills:
                bill_data.append({
                    'id': bill.id,
                    'bill_number': bill.bill_number,
                    'title': bill.title or '',
                    'summary': bill.summary or '',
                    'full_text': bill.full_text or '',
                    'source': bill.source,
                    'state_or_federal': bill.state_or_federal
                })

            # Progress callback
            def progress_callback(current, total, score):
                if current % 5 == 0 or current == total:
                    print(f"   Progress: {current}/{total} bills scored (last score: {score:.1f})")

            print("\n🔄 Starting AI relevance scoring...")
            start_time = datetime.now()

            # Score bills in batch
            scored_bills = classifier.batch_score_bills(bill_data, progress_callback)

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            print(f"\n⏱️  Scoring completed in {duration:.1f} seconds")

            # Update database with scores
            print("\n🔄 Updating database with relevance scores...")
            updated_count = 0

            for scored_bill in scored_bills:
                bill_id = scored_bill['id']
                relevance_score = scored_bill['ai_relevance']['relevance_score']

                # Find the bill and update its relevance score
                bill = session.query(Bill).filter(Bill.id == bill_id).first()
                if bill:
                    bill.relevance_score = relevance_score
                    updated_count += 1

            # Commit updates
            session.commit()
            print(f"✅ Updated {updated_count} bills with relevance scores")

            # Show statistics
            print("\n📈 Scoring Statistics:")
            highly_relevant = [b for b in scored_bills if b['ai_relevance']['relevance_score'] >= 70]
            moderately_relevant = [b for b in scored_bills if 40 <= b['ai_relevance']['relevance_score'] < 70]
            somewhat_relevant = [b for b in scored_bills if 20 <= b['ai_relevance']['relevance_score'] < 40]
            not_relevant = [b for b in scored_bills if b['ai_relevance']['relevance_score'] < 20]

            print(f"   📊 Highly Relevant (≥70): {len(highly_relevant)} bills")
            print(f"   📊 Moderately Relevant (40-69): {len(moderately_relevant)} bills")
            print(f"   📊 Somewhat Relevant (20-39): {len(somewhat_relevant)} bills")
            print(f"   📊 Not Relevant (<20): {len(not_relevant)} bills")

            # Show top 10 most relevant bills
            print(f"\n🏆 TOP 10 MOST RELEVANT BILLS:")
            print("-" * 80)

            top_bills = sorted(scored_bills,
                             key=lambda x: x['ai_relevance']['relevance_score'],
                             reverse=True)[:10]

            for i, bill in enumerate(top_bills, 1):
                score = bill['ai_relevance']['relevance_score']
                category = bill['ai_relevance']['category']

                print(f"\n{i:2}. {bill['bill_number']} - Score: {score:.1f}/100 ({category})")
                print(f"    📝 {bill['title'][:70]}...")
                print(f"    🏛️  Source: {bill['source']} | State: {bill['state_or_federal']}")

                # Show breakdown
                breakdown = bill['ai_relevance']['breakdown']
                print(f"    📊 Breakdown: Title({breakdown['title']['score']:.1f}) | "
                      f"Summary({breakdown['summary']['score']:.1f}) | "
                      f"Text({breakdown['full_text']['score']:.1f})")

            # Show highly relevant bills with details
            if highly_relevant:
                print(f"\n⭐ HIGHLY RELEVANT BILLS (Score ≥ 70):")
                print("-" * 60)
                for bill in highly_relevant:
                    score = bill['ai_relevance']['relevance_score']
                    print(f"• {bill['bill_number']}: {score:.1f}/100")
                    print(f"  {bill['title'][:60]}...")

            print(f"\n✅ AI relevance scoring completed successfully!")
            print(f"📊 {len(highly_relevant)} bills flagged as highly relevant to skilled nursing facilities")

    except Exception as e:
        print(f"❌ Error during scoring: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    score_all_bills()