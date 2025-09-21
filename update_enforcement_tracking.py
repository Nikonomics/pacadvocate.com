#!/usr/bin/env python3
"""
Update Bills with CMS Enforcement Tracking
Test CMS Survey collector and update bills with enforcement risk data
"""

import sqlite3
import os
import sys
import json
from datetime import datetime

# Add the project root to the path so we can import our modules
sys.path.append('/Users/nikolashulewsky')

try:
    from services.collectors.cms_survey_client import CMSSurveyClient
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("📝 Note: CMS Survey client may need dependencies like BeautifulSoup4")
    print("Run: pip install beautifulsoup4 requests")
    sys.exit(1)

def update_enforcement_tracking():
    """Update bills with current CMS enforcement priorities and survey risk data"""

    # Connect to database
    db_path = 'snflegtracker.db'
    if not os.path.exists(db_path):
        print(f"❌ Database file not found: {db_path}")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        print("🔍 UPDATING CMS ENFORCEMENT TRACKING")
        print("=" * 50)
        print("🎯 Collecting CMS survey enforcement data and updating bill risk profiles")
        print()

        # Initialize CMS Survey client
        print("📡 Initializing CMS Survey & Certification client...")
        client = CMSSurveyClient()

        # Get current enforcement priorities
        print("🚨 Collecting current enforcement priorities...")
        try:
            enforcement_priorities = client.get_current_enforcement_priorities()
            print(f"✅ Found {len(enforcement_priorities)} enforcement priority areas")

            if enforcement_priorities:
                print("\n🎯 Current CMS Enforcement Priorities:")
                for i, priority in enumerate(enforcement_priorities[:5], 1):  # Show top 5
                    topic = priority['topic'].replace('_', ' ').title()
                    level = priority['priority_level'].upper()
                    freq = priority['frequency']
                    print(f"   {i}. {topic} ({level} - {freq} recent memos)")
            else:
                print("⚠️  No enforcement priorities found - using default priorities")
                # Set default priorities for testing
                enforcement_priorities = [
                    {'topic': 'infection_control', 'priority_level': 'high', 'frequency': 3},
                    {'topic': 'staffing', 'priority_level': 'high', 'frequency': 2},
                    {'topic': 'quality_care', 'priority_level': 'medium', 'frequency': 2},
                    {'topic': 'resident_rights', 'priority_level': 'medium', 'frequency': 1},
                    {'topic': 'pharmacy', 'priority_level': 'low', 'frequency': 1}
                ]
        except Exception as e:
            print(f"⚠️  Error collecting enforcement priorities: {e}")
            print("📝 Using simulated enforcement priorities for testing")
            # Use simulated data for testing
            enforcement_priorities = [
                {'topic': 'infection_control', 'priority_level': 'high', 'frequency': 5},
                {'topic': 'staffing', 'priority_level': 'high', 'frequency': 4},
                {'topic': 'quality_care', 'priority_level': 'medium', 'frequency': 3},
                {'topic': 'resident_rights', 'priority_level': 'medium', 'frequency': 2},
                {'topic': 'pharmacy', 'priority_level': 'low', 'frequency': 2}
            ]

        print()

        # Get all active bills
        cursor.execute("""
            SELECT id, title, summary, operational_area, implementation_timeline
            FROM bills
            WHERE is_active = 1
        """)

        bills = cursor.fetchall()
        print(f"📊 Updating enforcement data for {len(bills)} active bills...")
        print()

        updated_bills = 0

        for bill in bills:
            bill_id, title, summary, operational_area, timeline = bill
            summary = summary or ""

            print(f"🔍 Processing Bill {bill_id}: {title[:50]}...")

            # Calculate survey risk using the CMS client
            try:
                survey_risk_data = client.calculate_survey_risk(
                    title, summary, enforcement_priorities
                )

                risk_level = survey_risk_data['risk_level']
                risk_score = survey_risk_data['risk_score']
                matched_topics = survey_risk_data['matched_topics']

                # Determine enforcement priority based on matched topics and current priorities
                if any(topic['priority_level'] == 'high' for topic in matched_topics):
                    enforcement_priority = 'high'
                elif any(topic['priority_level'] == 'medium' for topic in matched_topics):
                    enforcement_priority = 'medium'
                else:
                    enforcement_priority = 'low'

                # Extract just the topic names for storage
                topic_names = [topic['topic'] for topic in matched_topics]

                # Update the bill with enforcement data
                cursor.execute("""
                    UPDATE bills
                    SET enforcement_priority = ?,
                        survey_risk = ?,
                        survey_risk_score = ?,
                        enforcement_topics = ?,
                        survey_memo_references = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (
                    enforcement_priority,
                    risk_level,
                    risk_score,
                    json.dumps(topic_names),
                    json.dumps([]),  # Will be populated when we collect actual memos
                    datetime.utcnow(),
                    bill_id
                ))

                updated_bills += 1

                # Display results
                risk_emoji = "🔴" if risk_level == "high" else "🟡" if risk_level == "medium" else "🟢"
                priority_emoji = "🚨" if enforcement_priority == "high" else "⚠️" if enforcement_priority == "medium" else "ℹ️"

                print(f"   {risk_emoji} Survey Risk: {risk_level.upper()} (Score: {risk_score})")
                print(f"   {priority_emoji} Enforcement Priority: {enforcement_priority.upper()}")

                if topic_names:
                    print(f"   🏷️ Topics: {', '.join(topic_names)}")
                else:
                    print(f"   🏷️ Topics: None matched")

            except Exception as e:
                print(f"   ❌ Error calculating risk: {e}")
                continue

            print()

        # Commit all changes
        conn.commit()
        conn.close()

        print("✅ ENFORCEMENT TRACKING UPDATE COMPLETE")
        print("=" * 45)
        print(f"📊 Bills processed: {len(bills)}")
        print(f"✅ Bills updated: {updated_bills}")
        print()

        # Show summary statistics
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Risk level distribution
        cursor.execute("""
            SELECT survey_risk, COUNT(*) as count
            FROM bills
            WHERE is_active = 1 AND survey_risk IS NOT NULL
            GROUP BY survey_risk
            ORDER BY
                CASE survey_risk
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    WHEN 'low' THEN 3
                END
        """)

        risk_distribution = cursor.fetchall()

        print("📊 SURVEY RISK DISTRIBUTION:")
        for risk_level, count in risk_distribution:
            emoji = "🔴" if risk_level == "high" else "🟡" if risk_level == "medium" else "🟢"
            print(f"   {emoji} {risk_level.title()}: {count} bills")

        print()

        # Enforcement priority distribution
        cursor.execute("""
            SELECT enforcement_priority, COUNT(*) as count
            FROM bills
            WHERE is_active = 1 AND enforcement_priority IS NOT NULL
            GROUP BY enforcement_priority
            ORDER BY
                CASE enforcement_priority
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    WHEN 'low' THEN 3
                END
        """)

        priority_distribution = cursor.fetchall()

        print("📊 ENFORCEMENT PRIORITY DISTRIBUTION:")
        for priority_level, count in priority_distribution:
            emoji = "🚨" if priority_level == "high" else "⚠️" if priority_level == "medium" else "ℹ️"
            print(f"   {emoji} {priority_level.title()}: {count} bills")

        print()

        # Show high-risk bills
        cursor.execute("""
            SELECT id, title, survey_risk, survey_risk_score, enforcement_topics
            FROM bills
            WHERE is_active = 1 AND survey_risk = 'high'
            ORDER BY survey_risk_score DESC
        """)

        high_risk_bills = cursor.fetchall()

        if high_risk_bills:
            print("🔴 HIGH SURVEY RISK BILLS:")
            for bill_id, title, risk, score, topics_json in high_risk_bills:
                topics = json.loads(topics_json or '[]')
                print(f"   📋 ID {bill_id}: {title[:50]}...")
                print(f"       📊 Risk Score: {score} | 🏷️ Topics: {', '.join(topics) if topics else 'None'}")
        else:
            print("✅ No high survey risk bills identified")

        conn.close()

        print()
        print("🎯 NEXT STEPS:")
        print("   1. 📊 Review survey risk assignments in dashboard")
        print("   2. 🚨 Focus on high-risk bills for compliance preparation")
        print("   3. 📋 Monitor CMS enforcement memos for updates")
        print("   4. 🔄 Re-run this script monthly to update priorities")

        return True

    except Exception as e:
        print(f"❌ Enforcement tracking update failed: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    update_enforcement_tracking()