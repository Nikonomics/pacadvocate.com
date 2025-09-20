#!/usr/bin/env python3
"""
Show collected bills from the Congress.gov API
"""

import os
import sys
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from models.legislation import Bill, BillKeywordMatch, Keyword
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

def show_collected_bills():
    """Show recently collected bills with their keyword matches"""
    print("📄 COLLECTED BILLS FROM CONGRESS.GOV")
    print("=" * 60)

    try:
        engine = create_engine("sqlite:///./snflegtracker.db")

        with Session(engine) as session:
            # Get total count
            total_bills = session.query(Bill).count()
            print(f"📊 Total bills in database: {total_bills}")

            # Get recent bills (last 10)
            recent_bills = session.query(Bill).order_by(
                Bill.created_at.desc()
            ).limit(10).all()

            print(f"\n📋 Recent bills collected:")
            print("-" * 60)

            for i, bill in enumerate(recent_bills, 1):
                print(f"\n{i:2}. {bill.bill_number}")
                if bill.title:
                    title = bill.title[:100] + "..." if len(bill.title) > 100 else bill.title
                    print(f"    📝 {title}")

                print(f"    🏛️  Chamber: {bill.chamber or 'Unknown'}")
                print(f"    📅 Status: {bill.status or 'Unknown'}")
                if bill.sponsor:
                    print(f"    👤 Sponsor: {bill.sponsor}")

                # Check for keyword matches
                matches = session.query(BillKeywordMatch).filter(
                    BillKeywordMatch.bill_id == bill.id
                ).all()

                if matches:
                    print(f"    🏷️  Keywords matched: {len(matches)}")
                    for match in matches:
                        keyword = session.query(Keyword).filter(
                            Keyword.id == match.keyword_id
                        ).first()
                        if keyword:
                            confidence = f"{match.confidence_score:.1%}" if match.confidence_score else "N/A"
                            print(f"       • {keyword.term} ({confidence} confidence)")

            # Show keyword match statistics
            print(f"\n🔍 KEYWORD MATCH STATISTICS")
            print("-" * 60)

            # Bills with keyword matches
            bills_with_matches = session.query(Bill).join(BillKeywordMatch).distinct().all()
            print(f"📊 Bills with keyword matches: {len(bills_with_matches)}")

            if bills_with_matches:
                print(f"\n🎯 Top matched bills:")
                for i, bill in enumerate(bills_with_matches[:5], 1):
                    matches = session.query(BillKeywordMatch).filter(
                        BillKeywordMatch.bill_id == bill.id
                    ).all()

                    avg_confidence = sum(m.confidence_score for m in matches if m.confidence_score) / len(matches)
                    title = bill.title[:60] + "..." if bill.title and len(bill.title) > 60 else (bill.title or "No title")

                    print(f"  {i}. {bill.bill_number}: {title}")
                    print(f"     {len(matches)} keywords, {avg_confidence:.1%} avg confidence")

            # Show keyword performance
            print(f"\n📈 KEYWORD PERFORMANCE")
            print("-" * 60)

            from sqlalchemy import func
            keyword_stats = session.query(
                Keyword.term,
                Keyword.category,
                func.count(BillKeywordMatch.id).label('match_count'),
                func.avg(BillKeywordMatch.confidence_score).label('avg_confidence')
            ).outerjoin(BillKeywordMatch).group_by(Keyword.id).order_by(
                func.count(BillKeywordMatch.id).desc()
            ).all()

            print("Keyword performance (matches found):")
            for kw_term, kw_category, match_count, avg_conf in keyword_stats[:10]:
                conf_str = f"{avg_conf:.1%}" if avg_conf else "N/A"
                print(f"  • {kw_term:<25} ({kw_category}): {match_count} matches, {conf_str} avg")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    show_collected_bills()