#!/usr/bin/env python3
"""
Apply Enhanced Relevance Classifier to Database Bills
Updates relevance scores using the new Medicare Advantage detection system
"""

import sqlite3
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from services.ai.enhanced_relevance_classifier import EnhancedSNFRelevanceClassifier

def apply_enhanced_classifier_to_database():
    """Apply the enhanced classifier to all active bills in the database"""

    print("🔄 APPLYING ENHANCED SNF RELEVANCE CLASSIFIER")
    print("=" * 50)

    # Initialize classifier
    classifier = EnhancedSNFRelevanceClassifier()

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

    print(f"📊 Found {len(bills)} active bills to analyze")
    print()

    updates = []
    analysis_results = []

    for bill in bills:
        id_, bill_number, title, summary, full_text, current_score = bill

        try:
            # Analyze with enhanced classifier
            result = classifier.analyze_relevance(
                title=title or "",
                summary=summary or "",
                full_text=full_text or ""
            )

            # Store for updates
            updates.append({
                'id': id_,
                'bill_number': bill_number,
                'new_score': result.score,
                'current_score': current_score,
                'category': result.category,
                'ma_impact': result.ma_impact,
                'explanation': result.explanation,
                'context_notes': result.context_notes
            })

            analysis_results.append(result)

        except Exception as e:
            print(f"❌ Error analyzing {bill_number}: {e}")
            continue

    # Display analysis results
    print("📋 ENHANCED CLASSIFICATION RESULTS")
    print("-" * 50)

    # Sort by new score descending
    updates.sort(key=lambda x: x['new_score'], reverse=True)

    for update in updates:
        current = update['current_score'] or 0
        new = update['new_score']
        change = new - current
        change_indicator = "📈" if change > 5 else "📉" if change < -5 else "➡️"

        print(f"{change_indicator} {update['bill_number']}")
        print(f"   Score: {current:.1f} → {new:.1f} ({change:+.1f})")
        print(f"   Category: {update['category']}")
        if update['ma_impact']:
            print(f"   🎯 MA IMPACT: This affects SNF Medicare Advantage operations")
        print(f"   Explanation: {update['explanation']}")
        if update['context_notes']:
            print(f"   Notes: {'; '.join(update['context_notes'])}")
        print()

    # Show category breakdown
    print("📊 CATEGORY BREAKDOWN")
    print("-" * 30)

    categories = {}
    ma_bills = []

    for update in updates:
        cat = update['category']
        categories[cat] = categories.get(cat, 0) + 1
        if update['ma_impact']:
            ma_bills.append(update)

    for category, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        print(f"  {category}: {count} bills")

    print(f"\n🎯 Medicare Advantage Impact Bills: {len(ma_bills)}")
    for ma_bill in ma_bills:
        print(f"  • {ma_bill['bill_number']}: {ma_bill['new_score']:.1f}/100")

    # Ask for confirmation to update database
    print("\n" + "="*50)
    print("💾 DATABASE UPDATE OPTIONS:")
    print("1. Update all relevance scores")
    print("2. Update only MA impact bills")
    print("3. Update only scores that changed significantly (>10 point change)")
    print("4. Preview only - don't update")

    choice = input("\nSelect option (1-4): ").strip()

    if choice == '1':
        update_bills = updates
        print("🔄 Updating all bills...")
    elif choice == '2':
        update_bills = [u for u in updates if u['ma_impact']]
        print(f"🔄 Updating {len(update_bills)} MA impact bills...")
    elif choice == '3':
        update_bills = [u for u in updates if abs(u['new_score'] - (u['current_score'] or 0)) >= 10]
        print(f"🔄 Updating {len(update_bills)} bills with significant changes...")
    else:
        print("👁️ Preview only - no database changes made")
        conn.close()
        return

    # Perform updates
    updated_count = 0
    for update in update_bills:
        try:
            cursor.execute("""
                UPDATE bills
                SET relevance_score = ?
                WHERE id = ?
            """, (update['new_score'], update['id']))

            updated_count += 1
            print(f"✅ Updated {update['bill_number']}: {update['new_score']:.1f}")

        except Exception as e:
            print(f"❌ Failed to update {update['bill_number']}: {e}")

    # Commit changes
    conn.commit()
    conn.close()

    print(f"\n🎉 Successfully updated {updated_count} bills with enhanced relevance scores!")

    # Summary of key improvements
    print("\n📈 KEY IMPROVEMENTS:")
    print("✅ Medicare Advantage bills now properly detected and scored")
    print("✅ Context notes explain WHY each bill matters to SNFs")
    print("✅ Scoring reflects SNF operational impact (cash flow, admissions, etc.)")
    print("✅ MA bills flagged for special attention (30-40% of SNF revenue)")

    return updated_count, len(ma_bills)

if __name__ == "__main__":
    apply_enhanced_classifier_to_database()