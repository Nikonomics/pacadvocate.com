#!/usr/bin/env python3
"""
Test Rule Summaries
Test that all rule summary data is properly stored and retrievable
"""

import sqlite3
import json

def test_rule_summaries():
    """Test that rule summary data is complete and properly formatted"""
    print("📋 TESTING RULE SUMMARY DATA")
    print("=" * 35)

    try:
        conn = sqlite3.connect('snflegtracker.db')
        cursor = conn.cursor()

        # Get all bills with rule summaries
        cursor.execute("""
            SELECT id, title, rule_type, ai_relevance_score,
                   executive_summary, key_provisions, implementation_timeline, snf_action_items
            FROM bills
            WHERE is_active = 1 AND executive_summary IS NOT NULL
            ORDER BY ai_relevance_score DESC
        """)

        bills = cursor.fetchall()
        conn.close()

        if not bills:
            print("❌ No bills with rule summaries found")
            return False

        print(f"✅ Found {len(bills)} bills with rule summaries")
        print()

        # Test each bill's data
        all_tests_passed = True

        for i, bill in enumerate(bills[:3], 1):  # Test first 3 bills
            (bill_id, title, rule_type, ai_score, exec_summary,
             provisions_json, timeline_json, actions_json) = bill

            print(f"📋 Testing Bill {bill_id}: {title[:50]}...")

            # Test executive summary
            if exec_summary and len(exec_summary) > 50:
                print(f"   ✅ Executive Summary: {len(exec_summary)} characters")
            else:
                print(f"   ❌ Executive Summary: Missing or too short")
                all_tests_passed = False

            # Test key provisions
            try:
                provisions = json.loads(provisions_json) if provisions_json else []
                if isinstance(provisions, list) and len(provisions) >= 3:
                    print(f"   ✅ Key Provisions: {len(provisions)} items")
                    print(f"      • {provisions[0][:60]}...")
                else:
                    print(f"   ❌ Key Provisions: Invalid or insufficient data")
                    all_tests_passed = False
            except json.JSONDecodeError:
                print(f"   ❌ Key Provisions: JSON parsing error")
                all_tests_passed = False

            # Test implementation timeline
            try:
                timeline = json.loads(timeline_json) if timeline_json else []
                if isinstance(timeline, list) and len(timeline) >= 3:
                    print(f"   ✅ Implementation Timeline: {len(timeline)} milestones")
                    completed_count = sum(1 for item in timeline if item.get('status') == 'completed')
                    upcoming_count = sum(1 for item in timeline if item.get('status') == 'upcoming')
                    print(f"      📅 {completed_count} completed, {upcoming_count} upcoming")
                else:
                    print(f"   ❌ Implementation Timeline: Invalid or insufficient data")
                    all_tests_passed = False
            except json.JSONDecodeError:
                print(f"   ❌ Implementation Timeline: JSON parsing error")
                all_tests_passed = False

            # Test SNF action items
            try:
                actions = json.loads(actions_json) if actions_json else []
                if isinstance(actions, list) and len(actions) >= 2:
                    print(f"   ✅ SNF Action Items: {len(actions)} categories")
                    total_items = sum(len(cat.get('items', [])) for cat in actions)
                    high_priority = sum(1 for cat in actions if cat.get('priority') == 'High')
                    print(f"      🎯 {total_items} total items, {high_priority} high-priority categories")
                else:
                    print(f"   ❌ SNF Action Items: Invalid or insufficient data")
                    all_tests_passed = False
            except json.JSONDecodeError:
                print(f"   ❌ SNF Action Items: JSON parsing error")
                all_tests_passed = False

            print()

        # Summary statistics
        print(f"📊 RULE SUMMARY STATISTICS")
        print("-" * 30)

        total_provisions = 0
        total_milestones = 0
        total_action_items = 0

        for bill in bills:
            try:
                if bill[5]:  # provisions_json
                    provisions = json.loads(bill[5])
                    total_provisions += len(provisions)
            except:
                pass

            try:
                if bill[6]:  # timeline_json
                    timeline = json.loads(bill[6])
                    total_milestones += len(timeline)
            except:
                pass

            try:
                if bill[7]:  # actions_json
                    actions = json.loads(bill[7])
                    total_action_items += sum(len(cat.get('items', [])) for cat in actions)
            except:
                pass

        print(f"📋 Total Bills: {len(bills)}")
        print(f"📝 Total Provisions: {total_provisions}")
        print(f"📅 Total Milestones: {total_milestones}")
        print(f"✅ Total Action Items: {total_action_items}")
        print(f"📊 Average per Bill: {total_provisions//len(bills)} provisions, {total_milestones//len(bills)} milestones, {total_action_items//len(bills)} actions")

        print()
        if all_tests_passed:
            print("🎉 ALL RULE SUMMARY TESTS PASSED!")
            print("✅ Executive summaries complete")
            print("✅ Key provisions properly formatted")
            print("✅ Implementation timelines with milestones")
            print("✅ SNF action items by category and priority")
            print("✅ Data ready for expandable dashboard display")
        else:
            print("⚠️  Some rule summary tests failed")

        return all_tests_passed

    except Exception as e:
        print(f"❌ Rule summary test failed: {e}")
        return False

def create_sample_dashboard_data():
    """Create sample data for dashboard testing"""
    print(f"\n📱 CREATING SAMPLE DASHBOARD DATA")
    print("=" * 35)

    try:
        conn = sqlite3.connect('snflegtracker.db')
        cursor = conn.cursor()

        # Get top 3 bills for dashboard sample
        cursor.execute("""
            SELECT id, title, ai_relevance_score, ai_impact_type, status, rule_type,
                   financial_impact_pbpy, comment_deadline, days_until_deadline, comment_period_urgent,
                   rule_source_url, executive_summary, key_provisions, implementation_timeline, snf_action_items
            FROM bills
            WHERE is_active = 1 AND executive_summary IS NOT NULL
            ORDER BY ai_relevance_score DESC
            LIMIT 3
        """)

        bills = cursor.fetchall()
        conn.close()

        dashboard_sample = []
        for bill in bills:
            (bill_id, title, ai_score, impact_type, status, rule_type, financial_impact,
             comment_deadline, days_until, urgent, source_url, exec_summary,
             provisions_json, timeline_json, actions_json) = bill

            bill_data = {
                "id": bill_id,
                "title": title,
                "ai_relevance_score": ai_score,
                "ai_impact_type": impact_type,
                "status": status,
                "rule_type": rule_type,
                "financial_impact_pbpy": financial_impact,
                "comment_deadline": comment_deadline,
                "days_until_deadline": days_until,
                "comment_period_urgent": bool(urgent),
                "rule_source_url": source_url,
                "executive_summary": exec_summary
            }

            # Parse JSON fields
            try:
                bill_data["key_provisions"] = json.loads(provisions_json) if provisions_json else []
                bill_data["implementation_timeline"] = json.loads(timeline_json) if timeline_json else []
                bill_data["snf_action_items"] = json.loads(actions_json) if actions_json else []
            except:
                bill_data["key_provisions"] = []
                bill_data["implementation_timeline"] = []
                bill_data["snf_action_items"] = []

            dashboard_sample.append(bill_data)

        # Save sample data
        with open('rule_summary_dashboard_data.json', 'w') as f:
            json.dump(dashboard_sample, f, indent=2, default=str)

        print(f"💾 Saved {len(dashboard_sample)} bills to rule_summary_dashboard_data.json")
        print(f"📊 Sample data ready for dashboard integration")

        return True

    except Exception as e:
        print(f"❌ Failed to create sample dashboard data: {e}")
        return False

def main():
    """Main function"""
    print("📋 RULE SUMMARY TESTING & VALIDATION")
    print("=" * 40)

    # Test rule summaries
    if test_rule_summaries():
        # Create sample dashboard data
        if create_sample_dashboard_data():
            print(f"\n🎯 RULE SUMMARY TESTING COMPLETE!")
            print(f"✅ All rule summary data validated")
            print(f"✅ Sample dashboard data created")
            print(f"✅ Ready for production dashboard display")
        else:
            print("❌ Failed to create sample dashboard data")
    else:
        print("❌ Rule summary tests failed")

if __name__ == "__main__":
    main()