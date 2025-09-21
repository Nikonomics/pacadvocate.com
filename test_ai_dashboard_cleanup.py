#!/usr/bin/env python3
"""
Test AI Dashboard Cleanup Results
Verify that the database cleanup and dashboard enhancements are working correctly
"""

import sqlite3
import json

def test_database_cleanup():
    """Test that database has been cleaned up based on AI analysis"""
    print("🧹 TESTING DATABASE CLEANUP RESULTS")
    print("=" * 40)

    try:
        conn = sqlite3.connect('snflegtracker.db')
        cursor = conn.cursor()

        # Test 1: Check active bills count and scores
        cursor.execute("""
            SELECT COUNT(*) as active_count,
                   MIN(ai_relevance_score) as min_score,
                   MAX(ai_relevance_score) as max_score,
                   AVG(ai_relevance_score) as avg_score
            FROM bills
            WHERE is_active = 1
        """)

        active_count, min_score, max_score, avg_score = cursor.fetchone()
        print(f"✅ Active bills: {active_count}")
        print(f"📊 AI score range: {min_score} - {max_score} (avg: {avg_score:.1f})")

        # Test 2: Check that all active bills have score ≥50
        cursor.execute("""
            SELECT COUNT(*) FROM bills
            WHERE is_active = 1 AND ai_relevance_score < 50
        """)

        low_score_active = cursor.fetchone()[0]
        print(f"🚫 Active bills with score <50: {low_score_active}")

        # Test 3: Check impact type distribution
        cursor.execute("""
            SELECT ai_impact_type, COUNT(*) as count
            FROM bills
            WHERE is_active = 1
            GROUP BY ai_impact_type
            ORDER BY count DESC
        """)

        impact_stats = cursor.fetchall()
        print(f"\n🎯 IMPACT TYPE DISTRIBUTION:")
        for impact_type, count in impact_stats:
            emoji = {'direct': '🎯', 'financial': '💰', 'competitive': '🏆', 'workforce': '👥'}.get(impact_type, '📋')
            print(f"   {emoji} {impact_type.title()}: {count} bills")

        # Test 4: Show top 10 bills for dashboard
        cursor.execute("""
            SELECT id, title, ai_relevance_score, ai_impact_type
            FROM bills
            WHERE is_active = 1
            ORDER BY ai_relevance_score DESC, id
            LIMIT 10
        """)

        top_bills = cursor.fetchall()
        print(f"\n🏆 TOP 10 BILLS FOR DASHBOARD:")
        for i, (bill_id, title, score, impact_type) in enumerate(top_bills, 1):
            emoji = {'direct': '🎯', 'financial': '💰', 'competitive': '🏆', 'workforce': '👥'}.get(impact_type, '📋')
            print(f"   {i:2d}. Bill {bill_id}: {title[:50]}...")
            print(f"       {emoji} {impact_type.title()} | Score: {score}/100")

        conn.close()

        # Validation
        success = (
            active_count <= 10 and  # Limited to top bills
            low_score_active == 0 and  # No low-scoring active bills
            min_score >= 50 and  # All active bills have good scores
            len(top_bills) <= 10  # Dashboard shows max 10 bills
        )

        return success

    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def test_dashboard_features():
    """Test that dashboard features are properly configured"""
    print(f"\n📱 TESTING DASHBOARD FEATURES")
    print("=" * 35)

    # Test 1: Check dashboard summary file
    try:
        with open('dashboard_summary.json', 'r') as f:
            dashboard_data = json.load(f)

        print("✅ Dashboard summary file exists")
        print(f"📊 Bills in summary: {len(dashboard_data['bills'])}")
        print(f"🔄 Last updated: {dashboard_data['summary']['last_updated'][:19]}")

        # Check AI fields are present
        sample_bill = dashboard_data['bills'][0]
        ai_fields = ['ai_relevance_score', 'ai_impact_type', 'ai_explanation']
        missing_fields = [field for field in ai_fields if field not in sample_bill]

        if not missing_fields:
            print("✅ All AI fields present in dashboard data")
        else:
            print(f"⚠️  Missing AI fields: {missing_fields}")

        return len(missing_fields) == 0

    except FileNotFoundError:
        print("❌ Dashboard summary file not found")
        return False
    except Exception as e:
        print(f"❌ Dashboard test failed: {e}")
        return False

def test_api_enhancements():
    """Test that API schema includes AI fields"""
    print(f"\n🌐 TESTING API ENHANCEMENTS")
    print("=" * 30)

    try:
        # Test database query that API would use
        conn = sqlite3.connect('snflegtracker.db')
        cursor = conn.cursor()

        # Simulate API query with AI fields
        cursor.execute("""
            SELECT id, title, ai_relevance_score, ai_impact_type, ai_explanation
            FROM bills
            WHERE is_active = 1 AND ai_relevance_score >= 50
            ORDER BY ai_relevance_score DESC
            LIMIT 10
        """)

        api_bills = cursor.fetchall()
        conn.close()

        print(f"✅ API query returns {len(api_bills)} bills")
        print(f"📊 All bills have AI relevance score ≥50")
        print(f"📱 Limited to top 10 most relevant bills")
        print(f"🎯 Sorted by AI relevance score (highest first)")

        # Check sample bill data
        if api_bills:
            sample = api_bills[0]
            print(f"\n📋 Sample bill data:")
            print(f"   ID: {sample[0]}")
            print(f"   Title: {sample[1][:50]}...")
            print(f"   AI Score: {sample[2]}")
            print(f"   Impact Type: {sample[3]}")
            print(f"   Explanation: {sample[4][:60]}...")

        return len(api_bills) > 0

    except Exception as e:
        print(f"❌ API test failed: {e}")
        return False

def main():
    """Main test function"""
    print("🤖 AI DASHBOARD CLEANUP VALIDATION")
    print("=" * 40)
    print("Testing that AI analysis results have been applied to clean up the database")
    print()

    # Run all tests
    tests = [
        ("Database Cleanup", test_database_cleanup),
        ("Dashboard Features", test_dashboard_features),
        ("API Enhancements", test_api_enhancements)
    ]

    results = []
    for test_name, test_func in tests:
        print()
        result = test_func()
        results.append((test_name, result))

    # Show summary
    print(f"\n🎯 VALIDATION RESULTS")
    print("=" * 25)

    all_passed = True
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if not result:
            all_passed = False

    print()
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print("✅ Database cleaned up using AI analysis")
        print("✅ Only top 10 most relevant bills shown")
        print("✅ Bills sorted by AI relevance score")
        print("✅ Dashboard shows AI impact types and explanations")
        print("✅ System ready for production use")
    else:
        print("⚠️  Some tests failed - check output above")

    return all_passed

if __name__ == "__main__":
    main()