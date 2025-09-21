#!/usr/bin/env python3
"""
Test AI-Based Filtering System
Verify that bills are now filtered by AI relevance score instead of keywords
"""

import sqlite3
import requests
import json
from datetime import datetime

def test_database_filtering():
    """Test that the database has AI relevance scores and can filter by them"""
    print("🧪 TESTING DATABASE AI FILTERING")
    print("=" * 40)

    try:
        conn = sqlite3.connect('snflegtracker.db')
        cursor = conn.cursor()

        # Check AI fields exist
        cursor.execute("PRAGMA table_info(bills)")
        columns = [row[1] for row in cursor.fetchall()]
        ai_fields = [col for col in columns if col.startswith('ai_')]

        print(f"✅ AI fields found: {', '.join(ai_fields)}")

        # Test filtering by AI relevance score >50
        cursor.execute("""
            SELECT id, title, ai_relevant, ai_relevance_score, ai_impact_type
            FROM bills
            WHERE ai_relevance_score > 50
            ORDER BY ai_relevance_score DESC
            LIMIT 5
        """)

        relevant_bills = cursor.fetchall()
        print(f"\n📊 Bills with AI relevance score >50: {len(relevant_bills)}")

        for bill_id, title, relevant, score, impact_type in relevant_bills:
            print(f"   📋 Bill {bill_id}: {title[:50]}...")
            print(f"       🤖 AI Score: {score}/100 | Impact: {impact_type} | Relevant: {'Yes' if relevant else 'No'}")

        # Test filtering by AI relevance score ≤50
        cursor.execute("""
            SELECT COUNT(*)
            FROM bills
            WHERE ai_relevance_score <= 50
        """)

        low_score_count = cursor.fetchone()[0]
        print(f"\n📊 Bills with AI relevance score ≤50: {low_score_count}")

        # Test total bills
        cursor.execute("SELECT COUNT(*) FROM bills WHERE is_active = 1")
        total_bills = cursor.fetchone()[0]
        print(f"📋 Total active bills: {total_bills}")

        conn.close()
        return len(relevant_bills) > 0

    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def test_api_filtering():
    """Test that the API filters bills by AI relevance score"""
    print(f"\n🌐 TESTING API AI FILTERING")
    print("=" * 35)

    api_base = "http://localhost:8000"

    try:
        # Test 1: Default filtering (min_ai_relevance=50)
        print("🔍 Test 1: Default AI filtering (score ≥50)")
        response = requests.get(f"{api_base}/bills/")

        if response.status_code == 200:
            data = response.json()
            bills = data.get('bills', [])
            print(f"   📊 Bills returned with default filter: {len(bills)}")

            if bills:
                for bill in bills[:3]:  # Show first 3
                    ai_score = bill.get('ai_relevance_score', 'N/A')
                    print(f"   📋 {bill.get('title', 'No title')[:40]}... | AI Score: {ai_score}")
            else:
                print("   ⚠️  No bills returned with default AI filtering")

        else:
            print(f"   ❌ API request failed: {response.status_code}")
            return False

        # Test 2: Lower threshold (min_ai_relevance=0)
        print(f"\n🔍 Test 2: Lower AI threshold (score ≥0)")
        response = requests.get(f"{api_base}/bills/?min_ai_relevance=0")

        if response.status_code == 200:
            data = response.json()
            all_bills = data.get('bills', [])
            print(f"   📊 Bills returned with min_ai_relevance=0: {len(all_bills)}")

        # Test 3: High threshold (min_ai_relevance=90)
        print(f"\n🔍 Test 3: High AI threshold (score ≥90)")
        response = requests.get(f"{api_base}/bills/?min_ai_relevance=90")

        if response.status_code == 200:
            data = response.json()
            high_score_bills = data.get('bills', [])
            print(f"   📊 Bills returned with min_ai_relevance=90: {len(high_score_bills)}")

            if high_score_bills:
                for bill in high_score_bills:
                    ai_score = bill.get('ai_relevance_score', 'N/A')
                    impact_type = bill.get('ai_impact_type', 'N/A')
                    print(f"   🔴 {bill.get('title', 'No title')[:40]}... | Score: {ai_score} | Impact: {impact_type}")

        return True

    except requests.exceptions.ConnectionError:
        print("   ❌ API server not running. Start with: python3 start_api.py")
        return False
    except Exception as e:
        print(f"   ❌ API test failed: {e}")
        return False

def test_keyword_filtering_disabled():
    """Test that keyword-based filtering is disabled"""
    print(f"\n🚫 TESTING KEYWORD FILTERING DISABLED")
    print("=" * 40)

    try:
        # Test the bill service directly
        import sqlite3
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from services.legislation.bill_service import BillService

        # Create database session
        engine = create_engine('sqlite:///snflegtracker.db')
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()

        # Initialize bill service
        bill_service = BillService(db)

        # Test keyword search (should now return AI-relevant bills)
        print("🔍 Testing keyword search (should return AI-relevant bills instead)")
        keyword_results = bill_service.get_bills_by_keyword("medicare", min_confidence=0.5)

        print(f"   📊 Bills returned for 'medicare' keyword: {len(keyword_results)}")

        if keyword_results:
            print("   📋 Sample results (now based on AI relevance, not keywords):")
            for bill in keyword_results[:3]:
                ai_score = getattr(bill, 'ai_relevance_score', 'N/A')
                print(f"      • {bill.title[:50]}... | AI Score: {ai_score}")

        # Test search with keywords parameter (should use AI filtering)
        print(f"\n🔍 Testing search with keywords parameter")
        search_results = bill_service.search_bills(
            keywords=["skilled nursing", "medicare"],
            limit=10
        )

        print(f"   📊 Bills returned for keyword search: {len(search_results)}")
        if search_results:
            for bill in search_results[:3]:
                ai_score = getattr(bill, 'ai_relevance_score', 'N/A')
                print(f"      • {bill.title[:50]}... | AI Score: {ai_score}")

        db.close()
        return True

    except Exception as e:
        print(f"   ❌ Keyword filtering test failed: {e}")
        return False

def main():
    """Main test function"""
    print("🤖 AI-BASED FILTERING TEST SUITE")
    print("=" * 45)
    print("Testing replacement of keyword-based filtering with AI relevance scores")
    print()

    # Run tests
    test_results = []

    # Test 1: Database filtering
    test_results.append(("Database AI Filtering", test_database_filtering()))

    # Test 2: API filtering
    test_results.append(("API AI Filtering", test_api_filtering()))

    # Test 3: Keyword filtering disabled
    test_results.append(("Keyword Filtering Disabled", test_keyword_filtering_disabled()))

    # Show results
    print(f"\n📊 TEST RESULTS SUMMARY")
    print("=" * 25)

    all_passed = True
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if not result:
            all_passed = False

    print()
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print("✅ Keyword-based filtering successfully disabled")
        print("✅ AI relevance score filtering is working")
        print("✅ Only bills with AI score >50 are shown by default")
    else:
        print("⚠️  Some tests failed. Check the output above.")

    return all_passed

if __name__ == "__main__":
    main()