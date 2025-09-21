#!/usr/bin/env python3
"""
Apply Comprehensive SNF Classification System to Database
Updates bills with comprehensive relevance analysis including indirect impacts
"""

import sqlite3
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from services.ai.comprehensive_snf_classifier import ComprehensiveSNFClassifier

def apply_comprehensive_classifier():
    """Apply comprehensive classification to all active bills"""

    print("🔄 APPLYING COMPREHENSIVE SNF IMPACT DETECTION")
    print("=" * 55)
    print("📍 Detecting: Direct SNF | MA Impact | Indirect Effects")
    print()

    # Initialize classifier
    classifier = ComprehensiveSNFClassifier()

    # Connect to database
    conn = sqlite3.connect('snflegtracker.db')
    cursor = conn.cursor()

    # Get all active bills
    cursor.execute("""
        SELECT id, bill_number, title, summary, full_text, relevance_score
        FROM bills
        WHERE is_active = 1
        ORDER BY bill_number
    """)

    bills = cursor.fetchall()

    if not bills:
        print("❌ No active bills found in database")
        return

    print(f"📊 Analyzing {len(bills)} bills with comprehensive system...")
    print()

    results = []

    # Analyze each bill
    for bill in bills:
        id_, bill_number, title, summary, full_text, current_score = bill

        try:
            result = classifier.analyze_comprehensive_relevance(
                title=title or "",
                summary=summary or "",
                full_text=full_text or ""
            )

            results.append({
                'id': id_,
                'bill_number': bill_number,
                'title': title,
                'current_score': current_score or 0,
                'new_score': result.final_score,
                'primary_category': result.primary_category,
                'secondary_category': result.secondary_category,
                'ma_impact': result.ma_impact,
                'indirect_impact': result.indirect_impact,
                'priority': result.monitoring_priority,
                'explanation': result.explanation,
                'context_notes': result.context_notes,
                'specific_impacts': result.specific_impacts,
                'recommended_actions': result.recommended_actions
            })

        except Exception as e:
            print(f"❌ Error analyzing {bill_number}: {e}")
            continue

    # Sort by new score descending
    results.sort(key=lambda x: x['new_score'], reverse=True)

    # Display comprehensive results
    print("🎯 COMPREHENSIVE CLASSIFICATION RESULTS")
    print("=" * 55)

    critical_bills = []
    high_impact_bills = []
    ma_impact_bills = []
    indirect_impact_bills = []

    for result in results:
        current = result['current_score']
        new = result['new_score']
        change = new - current

        # Determine display icon
        if result['priority'] == 'Critical':
            icon = "🚨"
            critical_bills.append(result)
        elif result['priority'] == 'High':
            icon = "⚠️"
            high_impact_bills.append(result)
        elif result['ma_impact']:
            icon = "🎯"
            ma_impact_bills.append(result)
        elif result['indirect_impact']:
            icon = "🔄"
            indirect_impact_bills.append(result)
        elif new > 50:
            icon = "📋"
        elif change > 10:
            icon = "📈"
        elif change < -10:
            icon = "📉"
        else:
            icon = "➡️"

        print(f"{icon} {result['bill_number']}")
        print(f"   Score: {current:.1f} → {new:.1f} ({change:+.1f})")
        print(f"   Category: {result['primary_category']}")
        if result['secondary_category'] != 'none':
            print(f"   Secondary: {result['secondary_category']}")
        print(f"   Priority: {result['priority']}")

        # Special impact flags
        impacts = []
        if result['ma_impact']:
            impacts.append("MA Impact")
        if result['indirect_impact']:
            impacts.append("Indirect Impact")
        if impacts:
            print(f"   🔍 Special: {', '.join(impacts)}")

        print(f"   Explanation: {result['explanation']}")

        # Show specific impacts for high-priority bills
        if result['specific_impacts'] and result['priority'] in ['Critical', 'High']:
            print(f"   Impacts: {'; '.join(result['specific_impacts'][:3])}")

        # Show recommendations for top bills
        if result['recommended_actions'] and new >= 60:
            print(f"   Actions: {'; '.join(result['recommended_actions'][:2])}")

        print()

    # Summary statistics
    print("📊 COMPREHENSIVE ANALYSIS SUMMARY")
    print("-" * 40)

    print(f"🚨 Critical Priority Bills: {len(critical_bills)}")
    for bill in critical_bills[:5]:
        print(f"   • {bill['bill_number']}: {bill['new_score']:.1f}/100")

    print(f"\n⚠️ High Impact Bills: {len(high_impact_bills)}")
    for bill in high_impact_bills[:5]:
        print(f"   • {bill['bill_number']}: {bill['new_score']:.1f}/100")

    print(f"\n🎯 Medicare Advantage Impact: {len(ma_impact_bills)}")
    for bill in ma_impact_bills:
        print(f"   • {bill['bill_number']}: {bill['new_score']:.1f}/100 (30-40% revenue impact)")

    print(f"\n🔄 Indirect Impact Detected: {len(indirect_impact_bills)}")
    for bill in indirect_impact_bills[:5]:
        impacts = ', '.join(bill['specific_impacts'][:2]) if bill['specific_impacts'] else 'Various'
        print(f"   • {bill['bill_number']}: {bill['new_score']:.1f}/100 ({impacts})")

    # Category breakdown
    print(f"\n📂 CATEGORY BREAKDOWN:")
    categories = {}
    for result in results:
        cat = result['primary_category']
        categories[cat] = categories.get(cat, 0) + 1

    for category, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        print(f"   {category}: {count} bills")

    # Impact type summary
    print(f"\n🎯 IMPACT TYPE SUMMARY:")
    print(f"   Total Bills Analyzed: {len(results)}")
    print(f"   Direct SNF Relevance: {len([r for r in results if r['primary_category'] == 'direct_snf'])}")
    print(f"   Medicare Advantage Impact: {len(ma_impact_bills)}")
    print(f"   Indirect Impact Detected: {len(indirect_impact_bills)}")
    print(f"   High Priority (≥60 score): {len([r for r in results if r['new_score'] >= 60])}")
    print(f"   Significant Changes (>10 pts): {len([r for r in results if abs(r['new_score'] - r['current_score']) > 10])}")

    # Database update options
    print("\n" + "="*55)
    print("💾 DATABASE UPDATE OPTIONS:")
    print("1. Update all bills with comprehensive scores")
    print("2. Update only Critical and High priority bills")
    print("3. Update only bills with MA or Indirect impact")
    print("4. Update only significant score changes (>15 points)")
    print("5. Preview only - don't update database")

    choice = input("\nSelect option (1-5): ").strip()

    if choice == '1':
        update_bills = results
        print("🔄 Updating all bills...")
    elif choice == '2':
        update_bills = [r for r in results if r['priority'] in ['Critical', 'High']]
        print(f"🔄 Updating {len(update_bills)} Critical/High priority bills...")
    elif choice == '3':
        update_bills = [r for r in results if r['ma_impact'] or r['indirect_impact']]
        print(f"🔄 Updating {len(update_bills)} MA/Indirect impact bills...")
    elif choice == '4':
        update_bills = [r for r in results if abs(r['new_score'] - r['current_score']) >= 15]
        print(f"🔄 Updating {len(update_bills)} bills with significant changes...")
    else:
        print("👁️ Preview only - no database changes made")
        conn.close()
        return len(results), len(critical_bills), len(ma_impact_bills), len(indirect_impact_bills)

    # Perform updates
    updated_count = 0
    for result in update_bills:
        try:
            cursor.execute("""
                UPDATE bills
                SET relevance_score = ?
                WHERE id = ?
            """, (result['new_score'], result['id']))

            updated_count += 1
            print(f"✅ {result['bill_number']}: {result['new_score']:.1f} ({result['primary_category']})")

        except Exception as e:
            print(f"❌ Failed to update {result['bill_number']}: {e}")

    # Commit changes
    conn.commit()
    conn.close()

    print(f"\n🎉 Successfully updated {updated_count} bills!")

    # Final summary
    print("\n📈 SYSTEM IMPROVEMENTS:")
    print("✅ Direct SNF detection with enhanced scoring")
    print("✅ Medicare Advantage impact detection (30-40% revenue dependency)")
    print("✅ Indirect impact detection (payment, competition, workforce)")
    print("✅ Priority-based monitoring recommendations")
    print("✅ Actionable insights for each high-impact bill")

    return len(results), len(critical_bills), len(ma_impact_bills), len(indirect_impact_bills)

if __name__ == "__main__":
    try:
        total, critical, ma_impact, indirect = apply_comprehensive_classifier()
        print(f"\n📊 Final Stats: {total} analyzed, {critical} critical, {ma_impact} MA impact, {indirect} indirect")
    except KeyboardInterrupt:
        print("\n⚠️ Analysis interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")