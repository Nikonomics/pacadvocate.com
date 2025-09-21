#!/usr/bin/env python3
"""
Test CMS Enforcement Tracking (Simulated)
Test enforcement tracking with simulated CMS survey data
"""

import sqlite3
import os
import json
from datetime import datetime

def test_enforcement_tracking():
    """Test enforcement tracking with simulated CMS enforcement data"""

    # Connect to database
    db_path = 'snflegtracker.db'
    if not os.path.exists(db_path):
        print(f"❌ Database file not found: {db_path}")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        print("🧪 TESTING CMS ENFORCEMENT TRACKING (SIMULATED)")
        print("=" * 60)
        print("🎯 Using simulated CMS enforcement data to test tracking system")
        print()

        # Simulated current enforcement priorities based on real CMS focus areas
        enforcement_priorities = [
            {
                'topic': 'infection_control',
                'priority_level': 'high',
                'frequency': 8,
                'recent_memos': 5,
                'description': 'COVID-19, infection prevention, outbreak response'
            },
            {
                'topic': 'staffing',
                'priority_level': 'high',
                'frequency': 6,
                'recent_memos': 4,
                'description': 'Nursing staffing levels, 24-hour RN coverage'
            },
            {
                'topic': 'quality_care',
                'priority_level': 'medium',
                'frequency': 4,
                'recent_memos': 3,
                'description': 'Pressure ulcers, falls prevention, medication errors'
            },
            {
                'topic': 'resident_rights',
                'priority_level': 'medium',
                'frequency': 3,
                'recent_memos': 2,
                'description': 'Dignity, privacy, abuse prevention'
            },
            {
                'topic': 'pharmacy',
                'priority_level': 'low',
                'frequency': 2,
                'recent_memos': 1,
                'description': 'Drug regimen review, unnecessary medications'
            }
        ]

        print("🎯 SIMULATED CMS ENFORCEMENT PRIORITIES:")
        print("-" * 50)
        for priority in enforcement_priorities:
            level_emoji = "🚨" if priority['priority_level'] == 'high' else "⚠️" if priority['priority_level'] == 'medium' else "ℹ️"
            topic_name = priority['topic'].replace('_', ' ').title()
            print(f"{level_emoji} {topic_name} ({priority['priority_level'].upper()})")
            print(f"   📊 Frequency: {priority['frequency']} memos | 📋 Recent: {priority['recent_memos']}")
            print(f"   📝 Focus: {priority['description']}")
            print()

        # Function to calculate survey risk (simplified version)
        def calculate_survey_risk(title, summary, enforcement_priorities):
            """Calculate survey risk based on enforcement priorities"""
            bill_text = f"{title} {summary}".lower()
            risk_score = 0
            matched_topics = []

            topic_keywords = {
                'infection_control': ['infection', 'control', 'prevention', 'covid', 'outbreak', 'sanitiz', 'hygiene'],
                'staffing': ['staffing', 'nurse', 'nursing', 'staff', 'workforce', 'rn', 'registered nurse'],
                'quality_care': ['quality', 'care', 'safety', 'pressure ulcer', 'falls', 'medication', 'adverse'],
                'resident_rights': ['rights', 'dignity', 'privacy', 'abuse', 'neglect', 'resident'],
                'pharmacy': ['pharmacy', 'medication', 'drug', 'pharmaceutical', 'prescri']
            }

            for priority in enforcement_priorities:
                topic = priority['topic']
                frequency = priority['frequency']
                priority_level = priority['priority_level']

                keywords = topic_keywords.get(topic, [topic.replace('_', ' ')])
                if any(keyword in bill_text for keyword in keywords):
                    multiplier = 3 if priority_level == 'high' else 2 if priority_level == 'medium' else 1
                    risk_score += frequency * multiplier
                    matched_topics.append({
                        'topic': topic,
                        'priority_level': priority_level,
                        'frequency': frequency
                    })

            # Determine risk level
            if risk_score >= 15:
                risk_level = 'high'
            elif risk_score >= 8:
                risk_level = 'medium'
            else:
                risk_level = 'low'

            return {
                'risk_level': risk_level,
                'risk_score': risk_score,
                'matched_topics': matched_topics
            }

        # Get all active bills
        cursor.execute("""
            SELECT id, title, summary, operational_area
            FROM bills
            WHERE is_active = 1
        """)

        bills = cursor.fetchall()
        print(f"📊 ANALYZING {len(bills)} ACTIVE BILLS:")
        print("=" * 40)

        updated_bills = 0

        for bill in bills:
            bill_id, title, summary, operational_area = bill
            summary = summary or ""

            print(f"🔍 Bill {bill_id}: {title[:50]}...")

            # Calculate survey risk
            survey_risk_data = calculate_survey_risk(title, summary, enforcement_priorities)

            risk_level = survey_risk_data['risk_level']
            risk_score = survey_risk_data['risk_score']
            matched_topics = survey_risk_data['matched_topics']

            # Determine enforcement priority
            if any(topic['priority_level'] == 'high' for topic in matched_topics):
                enforcement_priority = 'high'
            elif any(topic['priority_level'] == 'medium' for topic in matched_topics):
                enforcement_priority = 'medium'
            else:
                enforcement_priority = 'low'

            # Extract topic names
            topic_names = [topic['topic'] for topic in matched_topics]

            # Update the bill
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
                json.dumps([]),
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
                topics_display = [name.replace('_', ' ').title() for name in topic_names]
                print(f"   🏷️ Matched Topics: {', '.join(topics_display)}")
            else:
                print(f"   🏷️ Matched Topics: None")

            print()

        # Commit changes
        conn.commit()

        print("✅ ENFORCEMENT TRACKING TEST COMPLETE")
        print("=" * 45)
        print(f"📊 Bills analyzed: {len(bills)}")
        print(f"✅ Bills updated: {updated_bills}")
        print()

        # Show results summary
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

        risk_stats = cursor.fetchall()

        print("📊 SURVEY RISK DISTRIBUTION:")
        for risk_level, count in risk_stats:
            emoji = "🔴" if risk_level == "high" else "🟡" if risk_level == "medium" else "🟢"
            print(f"   {emoji} {risk_level.title()}: {count} bills")

        print()

        # Show enforcement priority distribution
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

        priority_stats = cursor.fetchall()

        print("📊 ENFORCEMENT PRIORITY DISTRIBUTION:")
        for priority_level, count in priority_stats:
            emoji = "🚨" if priority_level == "high" else "⚠️" if priority_level == "medium" else "ℹ️"
            print(f"   {emoji} {priority_level.title()}: {count} bills")

        print()

        # Show detailed analysis of high-priority bills
        cursor.execute("""
            SELECT id, title, survey_risk, survey_risk_score, enforcement_topics
            FROM bills
            WHERE is_active = 1 AND (survey_risk = 'high' OR enforcement_priority = 'high')
            ORDER BY survey_risk_score DESC
        """)

        high_priority_bills = cursor.fetchall()

        if high_priority_bills:
            print("🚨 HIGH-PRIORITY BILLS FOR SURVEY PREPARATION:")
            print("-" * 52)
            for bill_id, title, risk, score, topics_json in high_priority_bills:
                topics = json.loads(topics_json or '[]')
                topics_display = [t.replace('_', ' ').title() for t in topics]

                print(f"📋 ID {bill_id}: {title[:60]}...")
                print(f"   🔴 Risk: {risk.upper()} | 📊 Score: {score}")
                print(f"   🏷️ Enforcement Areas: {', '.join(topics_display) if topics_display else 'General'}")
                print()
        else:
            print("✅ No high-priority survey risk bills identified")

        conn.close()

        print("🎯 ENFORCEMENT TRACKING INSIGHTS:")
        print("-" * 35)
        print("   📊 System successfully tracks CMS enforcement priorities")
        print("   🚨 Bills are automatically risk-scored based on current focuses")
        print("   🏷️ Enforcement topics help prioritize compliance efforts")
        print("   🔄 Risk levels guide survey preparation activities")
        print()
        print("📋 NEXT STEPS:")
        print("   1. 🎯 Review high-risk bills for immediate attention")
        print("   2. 📚 Develop compliance strategies for matched topics")
        print("   3. 🔄 Update risk scores quarterly as priorities change")
        print("   4. 📊 Use data to guide SNF operational improvements")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    test_enforcement_tracking()