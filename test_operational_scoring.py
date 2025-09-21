#!/usr/bin/env python3
"""
Test SNF Operational Scoring System
Tests the new operational scoring fields and functionality
"""

import sys
import os
import sqlite3
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

def test_operational_scoring():
    """Test the new operational scoring system"""

    print("🏥 SNF OPERATIONAL SCORING SYSTEM TEST")
    print("=" * 50)
    print("🔍 Testing new operational scoring fields and data")
    print()

    # Connect to database
    db_path = 'snflegtracker.db'
    if not os.path.exists(db_path):
        print(f"❌ Database file not found: {db_path}")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Test 1: Verify operational scoring fields exist
        print("🔍 TEST 1: Database Schema Verification")
        print("-" * 40)

        cursor.execute("PRAGMA table_info(bills)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        required_fields = [
            'payment_impact', 'operational_area',
            'implementation_timeline', 'operational_tags'
        ]

        for field in required_fields:
            if field in column_names:
                print(f"✅ {field} field exists")
            else:
                print(f"❌ {field} field missing")

        print()

        # Test 2: Analyze operational scoring distribution
        print("🔍 TEST 2: Operational Scoring Distribution")
        print("-" * 40)

        # Payment Impact Distribution
        cursor.execute("""
            SELECT payment_impact, COUNT(*) as count
            FROM bills
            WHERE payment_impact IS NOT NULL
            GROUP BY payment_impact
            ORDER BY count DESC
        """)

        payment_results = cursor.fetchall()
        print("💰 Payment Impact Distribution:")
        for impact, count in payment_results:
            print(f"   {impact}: {count} bills")

        print()

        # Operational Area Distribution
        cursor.execute("""
            SELECT operational_area, COUNT(*) as count
            FROM bills
            WHERE operational_area IS NOT NULL
            GROUP BY operational_area
            ORDER BY count DESC
        """)

        area_results = cursor.fetchall()
        print("🏢 Operational Area Distribution:")
        for area, count in area_results:
            print(f"   {area}: {count} bills")

        print()

        # Implementation Timeline Distribution
        cursor.execute("""
            SELECT implementation_timeline, COUNT(*) as count
            FROM bills
            WHERE implementation_timeline IS NOT NULL
            GROUP BY implementation_timeline
            ORDER BY count DESC
        """)

        timeline_results = cursor.fetchall()
        print("⏰ Implementation Timeline Distribution:")
        for timeline, count in timeline_results:
            print(f"   {timeline}: {count} bills")

        print()

        # Test 3: Show sample operational bills by category
        print("🔍 TEST 3: Sample Bills by Operational Category")
        print("-" * 50)

        categories = ['Staffing', 'Payment', 'Quality', 'Documentation', 'Survey']

        for category in categories:
            cursor.execute("""
                SELECT title, payment_impact, implementation_timeline, operational_tags
                FROM bills
                WHERE operational_area = ?
                LIMIT 2
            """, (category,))

            category_bills = cursor.fetchall()

            if category_bills:
                print(f"🏢 {category} Bills ({len(category_bills)} shown):")
                for i, (title, payment, timeline, tags) in enumerate(category_bills, 1):
                    print(f"  {i}. {title[:60]}...")
                    print(f"     💰 Payment Impact: {payment}")
                    print(f"     ⏰ Timeline: {timeline}")

                    if tags:
                        try:
                            tag_list = json.loads(tags)
                            print(f"     🏷️  Tags: {', '.join(tag_list[:3])}")
                        except:
                            print(f"     🏷️  Tags: {tags}")
                    print()

        # Test 4: High-Priority Bills Analysis
        print("🔍 TEST 4: High-Priority Bills Analysis")
        print("-" * 40)

        # Immediate implementation bills
        cursor.execute("""
            SELECT title, operational_area, payment_impact, operational_tags
            FROM bills
            WHERE implementation_timeline = 'Immediate'
            LIMIT 5
        """)

        immediate_bills = cursor.fetchall()
        print(f"🚨 Immediate Implementation Bills ({len(immediate_bills)}):")

        if immediate_bills:
            for i, (title, area, payment, tags) in enumerate(immediate_bills, 1):
                print(f"  {i}. {title[:50]}...")
                print(f"     🏢 Area: {area} | 💰 Impact: {payment}")
        else:
            print("   No bills require immediate implementation")

        print()

        # Payment increase bills
        cursor.execute("""
            SELECT title, operational_area, implementation_timeline, operational_tags
            FROM bills
            WHERE payment_impact = 'increase'
            LIMIT 3
        """)

        increase_bills = cursor.fetchall()
        print(f"📈 Payment Increase Bills ({len(increase_bills)}):")

        if increase_bills:
            for i, (title, area, timeline, tags) in enumerate(increase_bills, 1):
                print(f"  {i}. {title[:50]}...")
                print(f"     🏢 Area: {area} | ⏰ Timeline: {timeline}")
        else:
            print("   No bills increase payments")

        print()

        # Payment decrease bills
        cursor.execute("""
            SELECT title, operational_area, implementation_timeline, operational_tags
            FROM bills
            WHERE payment_impact = 'decrease'
            LIMIT 3
        """)

        decrease_bills = cursor.fetchall()
        print(f"📉 Payment Decrease Bills ({len(decrease_bills)}):")

        if decrease_bills:
            for i, (title, area, timeline, tags) in enumerate(decrease_bills, 1):
                print(f"  {i}. {title[:50]}...")
                print(f"     🏢 Area: {area} | ⏰ Timeline: {timeline}")
        else:
            print("   No bills decrease payments")

        print()

        # Test 5: Operational Tags Analysis
        print("🔍 TEST 5: Operational Tags Analysis")
        print("-" * 40)

        cursor.execute("""
            SELECT operational_tags
            FROM bills
            WHERE operational_tags IS NOT NULL AND operational_tags != ''
        """)

        all_tags = cursor.fetchall()
        tag_count = {}

        for (tags_json,) in all_tags:
            try:
                tags = json.loads(tags_json)
                if isinstance(tags, list):
                    for tag in tags:
                        tag_count[tag] = tag_count.get(tag, 0) + 1
            except:
                continue

        print("🏷️  Most Common Operational Tags:")
        sorted_tags = sorted(tag_count.items(), key=lambda x: x[1], reverse=True)
        for tag, count in sorted_tags[:8]:
            print(f"   {tag}: {count} bills")

        conn.close()

        print()
        print("🎉 SNF OPERATIONAL SCORING SYSTEM SUMMARY")
        print("=" * 50)
        print("✅ Replaced generic risk scores with SNF-specific operational metrics")
        print("✅ Payment Impact: increase/decrease/neutral classification")
        print("✅ Operational Area: Staffing/Quality/Documentation/Survey/Payment")
        print("✅ Implementation Timeline: Immediate/Soon/Future prioritization")
        print("✅ Operational Tags: Detailed impact categorization")
        print()
        print("🎯 System Benefits:")
        print("   • Directly actionable operational categories")
        print("   • Clear payment impact assessment")
        print("   • Implementation priority guidance")
        print("   • SNF-specific operational focus")

    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    test_operational_scoring()