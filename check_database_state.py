#!/usr/bin/env python3
"""
Check Bills Database State
Analyze the current state of the bills database after cleanup
"""

import sqlite3
import os
from datetime import datetime

def check_database_state():
    """Check the current state of the bills database"""

    # Connect to database
    db_path = 'snflegtracker.db'
    if not os.path.exists(db_path):
        print(f"❌ Database file not found: {db_path}")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        print("📊 BILLS DATABASE STATE ANALYSIS")
        print("=" * 50)

        # 1. Total count of all bills in database
        cursor.execute("SELECT COUNT(*) FROM bills")
        total_bills = cursor.fetchone()[0]
        print(f"📋 Total bills in database: {total_bills}")

        # Active vs inactive bills
        cursor.execute("SELECT COUNT(*) FROM bills WHERE is_active = 1")
        active_bills = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM bills WHERE is_active = 0")
        inactive_bills = cursor.fetchone()[0]

        print(f"✅ Active bills: {active_bills}")
        print(f"❌ Inactive/deleted bills: {inactive_bills}")
        print()

        # 2. Count of bills with relevance_score > 0
        cursor.execute("SELECT COUNT(*) FROM bills WHERE relevance_score > 0")
        bills_with_relevance = cursor.fetchone()[0]
        print(f"📈 Bills with relevance_score > 0: {bills_with_relevance}")
        print()

        # 3. List all bills with their titles and relevance scores
        print("📋 ALL BILLS IN DATABASE:")
        print("-" * 40)

        cursor.execute("""
            SELECT id, title, relevance_score, is_active, source,
                   payment_impact, operational_area, implementation_timeline
            FROM bills
            ORDER BY is_active DESC, relevance_score DESC
        """)

        all_bills = cursor.fetchall()

        for bill in all_bills:
            (bill_id, title, relevance, is_active, source, payment, area, timeline) = bill
            status = "✅ ACTIVE" if is_active else "❌ DELETED"
            relevance_display = f"{relevance:.1f}" if relevance else "N/A"

            print(f"{status} | ID {bill_id}: {title[:60]}...")
            print(f"       📊 Relevance: {relevance_display} | 📄 Source: {source or 'Unknown'}")
            if payment or area or timeline:
                print(f"       💰 Payment: {payment} | 🏢 Area: {area} | ⏰ Timeline: {timeline}")
            print()

        # 4. Show which bills were deleted in the last cleanup
        print("🗑️  BILLS DELETED IN RECENT CLEANUP:")
        print("-" * 40)

        cursor.execute("""
            SELECT id, title, source
            FROM bills
            WHERE is_active = 0
            ORDER BY updated_at DESC
        """)

        deleted_bills = cursor.fetchall()

        if deleted_bills:
            for bill in deleted_bills:
                (bill_id, title, source) = bill
                print(f"❌ ID {bill_id}: {title[:70]}...")
                print(f"   📄 Source: {source or 'Unknown'}")
                print()
        else:
            print("ℹ️  No deleted bills found")

        # 5. Check if Federal Register SNF payment rules are still there
        print("🏛️  FEDERAL REGISTER SNF PAYMENT RULES STATUS:")
        print("-" * 50)

        cursor.execute("""
            SELECT id, title, relevance_score, is_active, payment_impact, operational_area
            FROM bills
            WHERE (source LIKE '%federal%' OR source LIKE '%register%')
               OR (title LIKE '%SNF%' OR title LIKE '%skilled nursing%' OR title LIKE '%nursing facility%')
            ORDER BY is_active DESC, relevance_score DESC
        """)

        snf_federal_bills = cursor.fetchall()

        if snf_federal_bills:
            for bill in snf_federal_bills:
                (bill_id, title, relevance, is_active, payment, area) = bill
                status = "✅ ACTIVE" if is_active else "❌ DELETED"
                relevance_display = f"{relevance:.1f}" if relevance else "N/A"

                print(f"{status} | ID {bill_id}: {title[:60]}...")
                print(f"       📊 Relevance: {relevance_display}")
                if payment and area:
                    print(f"       💰 Payment Impact: {payment} | 🏢 Area: {area}")
                print()
        else:
            print("⚠️  No Federal Register SNF payment rules found!")

        # Database statistics
        print("📊 DATABASE STATISTICS:")
        print("-" * 25)

        # By source
        cursor.execute("""
            SELECT source, COUNT(*) as count,
                   SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_count
            FROM bills
            GROUP BY source
            ORDER BY count DESC
        """)

        sources = cursor.fetchall()
        print("📄 By Source:")
        for source, total, active in sources:
            source_display = source or "Unknown"
            print(f"   {source_display}: {total} total ({active} active, {total-active} deleted)")

        print()

        # By operational area (active bills only)
        cursor.execute("""
            SELECT operational_area, COUNT(*) as count
            FROM bills
            WHERE is_active = 1 AND operational_area IS NOT NULL
            GROUP BY operational_area
            ORDER BY count DESC
        """)

        areas = cursor.fetchall()
        if areas:
            print("🏢 Active Bills by Operational Area:")
            for area, count in areas:
                print(f"   {area}: {count} bills")
        else:
            print("🏢 No operational area data available")

        print()

        # By payment impact (active bills only)
        cursor.execute("""
            SELECT payment_impact, COUNT(*) as count
            FROM bills
            WHERE is_active = 1 AND payment_impact IS NOT NULL
            GROUP BY payment_impact
            ORDER BY count DESC
        """)

        payments = cursor.fetchall()
        if payments:
            print("💰 Active Bills by Payment Impact:")
            for impact, count in payments:
                icon = {"increase": "↑", "decrease": "↓", "neutral": "→"}.get(impact, "?")
                print(f"   {icon} {impact.title()}: {count} bills")
        else:
            print("💰 No payment impact data available")

        conn.close()

        # Summary
        print()
        print("📊 SUMMARY:")
        print("-" * 15)
        cleanup_rate = (inactive_bills / total_bills * 100) if total_bills > 0 else 0
        print(f"🗃️  Database contains {total_bills} total bills")
        print(f"✅ {active_bills} bills are currently active")
        print(f"🧹 {inactive_bills} bills were removed in cleanup ({cleanup_rate:.1f}%)")

        if active_bills == 0:
            print("⚠️  WARNING: No active bills remain!")
        elif active_bills < 5:
            print(f"⚠️  WARNING: Only {active_bills} active bills remaining")
        else:
            print(f"✅ Database is focused with {active_bills} SNF-relevant bills")

        return True

    except Exception as e:
        print(f"❌ Database analysis failed: {e}")
        return False

if __name__ == "__main__":
    check_database_state()