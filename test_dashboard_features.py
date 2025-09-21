#!/usr/bin/env python3
"""
Test Dashboard Features
Tests the new SNF operator-focused dashboard features
"""

import sqlite3
import json
from datetime import datetime, timedelta

def create_test_data():
    """Create test data to demonstrate dashboard features"""

    db_path = 'snflegtracker.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Update the existing SNF bill with realistic data
    cursor.execute("SELECT id FROM bills WHERE is_active = 1 LIMIT 1")
    result = cursor.fetchone()

    if result:
        bill_id = result[0]

        # Set up a test scenario with urgent comment deadline
        urgent_deadline = (datetime.now() + timedelta(days=15)).isoformat()

        cursor.execute("""
            UPDATE bills
            SET payment_impact = 'increase',
                operational_area = 'Quality',
                implementation_timeline = 'Soon',
                operational_tags = '["quality-measures", "payment-system", "snf-qrp"]',
                comment_deadline = ?,
                comment_url = 'https://www.regulations.gov/comment/CMS-2025-0001-0001',
                has_comment_period = 1,
                comment_period_urgent = 1,
                source = 'federal_register'
            WHERE id = ?
        """, (urgent_deadline, bill_id))

        conn.commit()
        conn.close()

        print("✅ Updated test bill with dashboard features:")
        print(f"   💰 Payment Impact: INCREASE")
        print(f"   🏢 Operational Area: Quality")
        print(f"   ⏰ Implementation: Soon (30-90 days)")
        print(f"   📅 Comment Deadline: {urgent_deadline[:10]} (15 days - URGENT!)")
        print(f"   🔗 Federal Register link available")
        print()
        print("🎯 Dashboard Features to Test:")
        print("   1. ⚠️ Red urgent banner should appear at top")
        print("   2. 📊 Payment Impact column shows ↑ Increase")
        print("   3. ⏰ Implementation shows countdown timer")
        print("   4. 🚨 Comment deadline shows urgent countdown")
        print("   5. 🔗 'View Full Rule' button available")
        print("   6. 📋 Bill sorted to top by urgency")

        return True
    else:
        print("❌ No active bills found to update")
        return False

def verify_dashboard_data():
    """Verify the dashboard will display correctly"""

    db_path = 'snflegtracker.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, title, payment_impact, operational_area, implementation_timeline,
               comment_deadline, has_comment_period, comment_period_urgent,
               source
        FROM bills
        WHERE is_active = 1
    """)

    bills = cursor.fetchall()

    print("📊 Dashboard Data Verification:")
    print("-" * 40)

    for bill in bills:
        (bill_id, title, payment, area, timeline, deadline, has_comment, urgent, source) = bill

        print(f"Bill {bill_id}: {title[:50]}...")
        print(f"   💰 Payment: {payment}")
        print(f"   🏢 Area: {area}")
        print(f"   ⏰ Timeline: {timeline}")

        if deadline:
            deadline_date = datetime.fromisoformat(deadline.replace('Z', ''))
            days_remaining = (deadline_date - datetime.now()).days
            urgency = "🚨 URGENT" if days_remaining < 30 else "📅"
            print(f"   {urgency} Comment Deadline: {deadline[:10]} ({days_remaining} days)")
        else:
            print(f"   📅 No comment deadline")

        if source and 'federal' in source.lower():
            print(f"   🔗 Federal Register link: Available")
        else:
            print(f"   🔗 Federal Register link: Not available")

        print()

    conn.close()

    # Check for urgent bills
    urgent_count = sum(1 for bill in bills if bill[6] and bill[7])  # has_comment_period and urgent
    if urgent_count > 0:
        print(f"🚨 {urgent_count} urgent bills will trigger red banner!")
    else:
        print("ℹ️  No urgent bills - banner will not appear")

if __name__ == "__main__":
    print("🧪 DASHBOARD FEATURES TEST")
    print("=" * 50)
    print("🔧 Setting up test data for SNF operator dashboard...")
    print()

    if create_test_data():
        print()
        verify_dashboard_data()
        print()
        print("🎉 Test Setup Complete!")
        print("📖 Open dashboard.html to see the new SNF operator features:")
        print("   • Urgent comment deadline banner")
        print("   • Payment impact arrows (↑↓→)")
        print("   • Implementation countdown timers")
        print("   • Federal Register 'View Full Rule' buttons")
        print("   • Urgency-based sorting")
    else:
        print("❌ Test setup failed - no bills to update")