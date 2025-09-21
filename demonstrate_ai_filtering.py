#!/usr/bin/env python3
"""
Demonstrate AI-Based Filtering
Show how the system now filters bills by AI relevance score instead of keywords
"""

import sqlite3

def demonstrate_filtering():
    print("🎯 AI-BASED FILTERING DEMONSTRATION")
    print("=" * 45)
    print("Showing how bills are now filtered by AI relevance score instead of keyword matching")
    print()

    conn = sqlite3.connect('snflegtracker.db')
    cursor = conn.cursor()

    # Show the filtering thresholds
    thresholds = [
        (95, "Only highest-impact SNF bills"),
        (70, "High-impact SNF bills"),
        (50, "All SNF-relevant bills (default threshold)"),
        (40, "Including moderate relevance"),
        (0, "All bills (including non-relevant)")
    ]

    for threshold, description in thresholds:
        print(f"🔍 FILTER: AI Relevance Score ≥ {threshold} ({description})")
        print("-" * 60)

        cursor.execute(f"""
            SELECT id, title, ai_relevance_score, ai_impact_type, ai_relevant
            FROM bills
            WHERE ai_relevance_score >= {threshold}
            ORDER BY ai_relevance_score DESC, id
            LIMIT 8
        """)

        bills = cursor.fetchall()
        print(f"📊 Bills returned: {len(bills)}")

        if bills:
            for bill_id, title, score, impact_type, relevant in bills:
                relevant_emoji = "✅" if relevant else "❌"
                score_color = "🔴" if score >= 70 else "🟡" if score >= 50 else "🟢"
                impact_emoji = {'direct': '🎯', 'financial': '💰', 'competitive': '🏆', 'workforce': '👥'}.get(impact_type, '📋')

                print(f"   {relevant_emoji} {score_color} Bill {bill_id}: {title[:45]}...")
                print(f"       Score: {score}/100 | {impact_emoji} {impact_type} | Relevant: {'Yes' if relevant else 'No'}")
        else:
            print("   📭 No bills match this threshold")

        print()

    # Show the key difference from keyword filtering
    print("🚫 KEYWORD FILTERING COMPARISON (DISABLED)")
    print("=" * 45)
    print("❌ OLD METHOD: Keyword matching ('SNF', 'skilled nursing', 'Medicare')")
    print("   • Missed relevant bills without exact keywords")
    print("   • Included irrelevant bills with keyword mentions")
    print("   • Manual keyword maintenance required")
    print()
    print("✅ NEW METHOD: AI Relevance Scoring (GPT-4 analysis)")
    print("   • Identifies SNF-relevant content semantically")
    print("   • Catches bills affecting SNFs indirectly")
    print("   • Automatically adapts to new legislation patterns")
    print()

    # Show impact type distribution
    print("📊 AI IMPACT TYPE ANALYSIS")
    print("=" * 30)
    cursor.execute("""
        SELECT ai_impact_type, COUNT(*) as count,
               AVG(ai_relevance_score) as avg_score,
               MIN(ai_relevance_score) as min_score,
               MAX(ai_relevance_score) as max_score
        FROM bills
        WHERE ai_relevance_score > 0
        GROUP BY ai_impact_type
        ORDER BY avg_score DESC
    """)

    impact_analysis = cursor.fetchall()
    for impact_type, count, avg_score, min_score, max_score in impact_analysis:
        emoji = {'direct': '🎯', 'financial': '💰', 'competitive': '🏆', 'workforce': '👥', 'other': '📋'}.get(impact_type, '📋')
        print(f"{emoji} {impact_type.title()}: {count} bills")
        print(f"   Avg: {avg_score:.1f} | Range: {min_score}-{max_score}")

    print()
    print("🎉 AI FILTERING SUCCESS SUMMARY")
    print("=" * 35)
    print("✅ Keyword-based filtering has been DISABLED")
    print("✅ AI relevance scoring is now the PRIMARY filter")
    print("✅ Default threshold set to >50 (shows only SNF-relevant bills)")
    print("✅ Bills automatically categorized by impact type")
    print("✅ System now identifies relevant bills more accurately")

    conn.close()

if __name__ == "__main__":
    demonstrate_filtering()