#!/usr/bin/env python3
"""
Database Migration: Replace Risk Scoring with SNF Operational Scoring
Adds SNF-specific operational fields and removes generic risk scoring fields
"""

import sqlite3
import os
from datetime import datetime
import json

def migrate_operational_scoring():
    """Replace risk scoring with SNF operational scoring fields"""

    # Connect to database
    db_path = 'snflegtracker.db'
    if not os.path.exists(db_path):
        print(f"❌ Database file not found: {db_path}")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        print("🔄 Migrating to SNF Operational Scoring System...")
        print("=" * 60)

        # Check current table structure
        cursor.execute("PRAGMA table_info(bills)")
        columns = cursor.fetchall()
        existing_columns = [col[1] for col in columns]

        print(f"📊 Current bills table has {len(existing_columns)} columns")

        # Step 1: Add new operational scoring columns
        print("\n🔄 Step 1: Adding new operational scoring fields...")

        new_columns = [
            ('payment_impact', 'VARCHAR(20)'),           # increase, decrease, neutral
            ('operational_area', 'VARCHAR(50)'),         # Staffing, Quality, Documentation, Survey, Payment
            ('implementation_timeline', 'VARCHAR(20)'),  # Immediate, Soon, Future
            ('operational_tags', 'TEXT')                 # JSON array of operational impact tags
        ]

        for column_name, column_type in new_columns:
            if column_name not in existing_columns:
                alter_sql = f"ALTER TABLE bills ADD COLUMN {column_name} {column_type}"
                cursor.execute(alter_sql)
                print(f"✅ Added column: {column_name}")
            else:
                print(f"⚠️  Column already exists: {column_name}")

        # Step 2: Create indexes for new operational fields
        print("\n🔄 Step 2: Creating indexes for operational fields...")

        indexes_to_create = [
            "CREATE INDEX IF NOT EXISTS idx_bills_payment_impact ON bills(payment_impact)",
            "CREATE INDEX IF NOT EXISTS idx_bills_operational_area ON bills(operational_area)",
            "CREATE INDEX IF NOT EXISTS idx_bills_implementation_timeline ON bills(implementation_timeline)"
        ]

        for index_sql in indexes_to_create:
            cursor.execute(index_sql)
            index_name = index_sql.split(' ')[-3]
            print(f"✅ Created index: {index_name}")

        # Step 3: Migrate existing data from risk scoring to operational scoring
        print("\n🔄 Step 3: Migrating existing bills to operational scoring...")

        # Get all bills with existing risk data
        cursor.execute("""
            SELECT id, title, summary, reimbursement_risk, staffing_risk,
                   compliance_risk, quality_risk, total_risk_score, risk_tags
            FROM bills
            WHERE payment_impact IS NULL
        """)

        bills_to_migrate = cursor.fetchall()
        print(f"📋 Found {len(bills_to_migrate)} bills to migrate")

        migrated_count = 0
        for bill in bills_to_migrate:
            (bill_id, title, summary, reimb_risk, staff_risk,
             comp_risk, qual_risk, total_risk, risk_tags) = bill

            # Determine payment impact based on old risk scores
            payment_impact = "neutral"
            operational_area = "Payment"  # Default
            implementation_timeline = "Future"  # Default

            # Analyze title and summary for operational insights
            text_content = f"{title or ''} {summary or ''}".lower()

            # Determine payment impact from content
            if any(term in text_content for term in ['increase', 'higher', 'raise', 'additional']):
                payment_impact = "increase"
            elif any(term in text_content for term in ['decrease', 'reduce', 'lower', 'cut']):
                payment_impact = "decrease"

            # Determine operational area from content and old risk scores
            if staff_risk and staff_risk > 0:
                operational_area = "Staffing"
            elif qual_risk and qual_risk > 0:
                operational_area = "Quality"
            elif any(term in text_content for term in ['survey', 'inspection', 'certification']):
                operational_area = "Survey"
            elif any(term in text_content for term in ['document', 'record', 'report']):
                operational_area = "Documentation"
            elif any(term in text_content for term in ['payment', 'reimbursement', 'pdpm']):
                operational_area = "Payment"

            # Determine implementation timeline from total risk score
            if total_risk and total_risk > 70:
                implementation_timeline = "Immediate"
            elif total_risk and total_risk > 40:
                implementation_timeline = "Soon"

            # Create operational tags from old risk tags
            operational_tags = []
            if risk_tags:
                try:
                    old_tags = json.loads(risk_tags) if isinstance(risk_tags, str) else risk_tags
                    if isinstance(old_tags, list):
                        operational_tags = [tag for tag in old_tags if tag]
                except:
                    pass

            # Add operational insights based on content analysis
            if 'staffing' in text_content:
                operational_tags.append('staffing-requirements')
            if 'quality' in text_content:
                operational_tags.append('quality-measures')
            if 'payment' in text_content or 'pdpm' in text_content:
                operational_tags.append('payment-system')
            if 'survey' in text_content:
                operational_tags.append('survey-readiness')

            operational_tags_json = json.dumps(operational_tags) if operational_tags else None

            # Update the bill with new operational scoring
            cursor.execute("""
                UPDATE bills
                SET payment_impact = ?,
                    operational_area = ?,
                    implementation_timeline = ?,
                    operational_tags = ?
                WHERE id = ?
            """, (payment_impact, operational_area, implementation_timeline,
                  operational_tags_json, bill_id))

            migrated_count += 1

        print(f"✅ Migrated {migrated_count} bills to operational scoring")

        # Step 4: Remove old risk scoring columns (optional - commented out for safety)
        print("\n🔄 Step 4: Marking old risk columns for removal...")
        print("ℹ️  Old risk columns retained for safety - can be dropped manually later:")

        old_risk_columns = [
            'reimbursement_risk', 'staffing_risk', 'compliance_risk',
            'quality_risk', 'total_risk_score', 'risk_tags'
        ]

        for col in old_risk_columns:
            if col in existing_columns:
                print(f"   📋 {col} - marked for future removal")

        # Step 5: Commit changes and verify
        conn.commit()

        # Verify the migration
        cursor.execute("""
            SELECT payment_impact, operational_area, implementation_timeline,
                   COUNT(*) as count
            FROM bills
            WHERE payment_impact IS NOT NULL
            GROUP BY payment_impact, operational_area, implementation_timeline
            ORDER BY count DESC
        """)

        results = cursor.fetchall()

        print(f"\n📊 Migration Results:")
        print("-" * 40)
        for payment, area, timeline, count in results:
            print(f"  {payment} | {area} | {timeline}: {count} bills")

        # Show sample of migrated bills
        cursor.execute("""
            SELECT title, payment_impact, operational_area, implementation_timeline, operational_tags
            FROM bills
            WHERE payment_impact IS NOT NULL
            LIMIT 5
        """)

        sample_bills = cursor.fetchall()
        print(f"\n📋 Sample Migrated Bills:")
        print("-" * 40)
        for i, (title, payment, area, timeline, tags) in enumerate(sample_bills, 1):
            print(f"  {i}. {title[:50]}...")
            print(f"     💰 Payment: {payment} | 🏢 Area: {area} | ⏰ Timeline: {timeline}")
            if tags:
                try:
                    tag_list = json.loads(tags)
                    print(f"     🏷️  Tags: {', '.join(tag_list[:3])}")
                except:
                    pass
            print()

        conn.close()
        print("🎉 Operational scoring migration completed successfully!")
        return True

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    print("🏥 SNF OPERATIONAL SCORING - Database Migration")
    print("=" * 60)
    success = migrate_operational_scoring()
    if success:
        print("\n✅ Database migration completed successfully")
        print("\n🎯 New Operational Scoring System:")
        print("   💰 Payment Impact: increase, decrease, neutral")
        print("   🏢 Operational Area: Staffing, Quality, Documentation, Survey, Payment")
        print("   ⏰ Implementation Timeline: Immediate, Soon, Future")
        print("   🏷️  Operational Tags: JSON array of impact tags")
    else:
        print("\n❌ Database migration failed")