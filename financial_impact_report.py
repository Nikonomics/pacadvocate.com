#!/usr/bin/env python3
"""
Financial Impact Report
Generate detailed report of all financial impact calculations
"""

import sqlite3
import json
from datetime import datetime

def generate_financial_impact_report():
    """Generate comprehensive financial impact report"""
    print("💰 SNF FINANCIAL IMPACT ANALYSIS REPORT")
    print("=" * 50)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    try:
        conn = sqlite3.connect('snflegtracker.db')
        cursor = conn.cursor()

        # Get all bills with financial impact
        cursor.execute("""
            SELECT id, title, ai_relevance_score, ai_impact_type, ai_explanation,
                   financial_impact_pbpy, financial_impact_details,
                   status, rule_type, effective_date, comment_deadline
            FROM bills
            WHERE is_active = 1 AND financial_impact_pbpy IS NOT NULL
            ORDER BY ABS(financial_impact_pbpy) DESC
        """)

        bills = cursor.fetchall()
        conn.close()

        if not bills:
            print("❌ No bills with financial impact found")
            return

        # Calculate summary statistics
        total_bills = len(bills)
        impacts = [b[5] for b in bills]
        total_impact = sum(impacts)
        avg_impact = total_impact / total_bills
        max_impact = max(impacts)
        min_impact = min(impacts)

        print(f"📊 SUMMARY STATISTICS")
        print(f"   Total Bills Analyzed: {total_bills}")
        print(f"   Average Impact PBPY: ${avg_impact:,.0f}")
        print(f"   Total Combined PBPY: ${total_impact:,.0f}")
        print(f"   Highest Impact: ${max_impact:,.0f} PBPY")
        print(f"   Lowest Impact: ${min_impact:,.0f} PBPY")
        print()

        # Impact distribution
        high_impact = [b for b in bills if abs(b[5]) >= 2500]
        medium_impact = [b for b in bills if 1500 <= abs(b[5]) < 2500]
        low_impact = [b for b in bills if abs(b[5]) < 1500]

        print(f"📈 IMPACT DISTRIBUTION")
        print(f"   🔴 High Impact (≥$2.5K PBPY): {len(high_impact)} bills")
        print(f"   🟡 Medium Impact ($1.5K-$2.5K PBPY): {len(medium_impact)} bills")
        print(f"   🟢 Low Impact (<$1.5K PBPY): {len(low_impact)} bills")
        print()

        # Impact by type
        impact_types = {}
        for bill in bills:
            impact_type = bill[3] or 'unknown'
            if impact_type not in impact_types:
                impact_types[impact_type] = []
            impact_types[impact_type].append(bill[5])

        print(f"🎯 IMPACT BY TYPE")
        for impact_type, type_impacts in impact_types.items():
            avg_type_impact = sum(type_impacts) / len(type_impacts)
            print(f"   {impact_type.title()}: {len(type_impacts)} bills, Avg ${avg_type_impact:,.0f} PBPY")
        print()

        # Detailed bill analysis
        print(f"📋 DETAILED BILL ANALYSIS")
        print("-" * 80)

        for i, bill in enumerate(bills, 1):
            (bill_id, title, ai_score, impact_type, explanation,
             financial_impact, details, status, rule_type, effective_date, comment_deadline) = bill

            print(f"{i:2d}. Bill {bill_id}: {title[:60]}{'...' if len(title) > 60 else ''}")
            print(f"    💰 Financial Impact: ${financial_impact:,} per bed per year")
            print(f"    🎯 AI Score: {ai_score}/100 | Impact Type: {impact_type}")
            print(f"    📊 Status: {status} | Rule Type: {rule_type}")

            if effective_date:
                print(f"    📅 Effective Date: {effective_date[:10]}")

            if comment_deadline:
                print(f"    💬 Comment Deadline: {comment_deadline[:10]}")

            # Show impact details if available
            if details:
                try:
                    components = json.loads(details)
                    if components:
                        print(f"    🔍 Impact Components:")
                        for comp in components:
                            comp_impact = comp.get('annual_impact_pbpy', 0)
                            comp_desc = comp.get('description', 'Unknown component')
                            print(f"        • {comp_desc}: ${comp_impact:,} PBPY")
                except:
                    pass

            print(f"    💡 AI Explanation: {explanation[:80]}{'...' if len(explanation) > 80 else ''}")
            print()

        # Sample facility calculations
        print(f"🏥 SAMPLE FACILITY IMPACT CALCULATIONS")
        print("-" * 40)

        facility_sizes = [50, 120, 200, 300]

        for beds in facility_sizes:
            facility_total = total_impact * beds
            print(f"   {beds:3d}-bed facility: ${facility_total:,}/year total impact")
            print(f"                       (${facility_total/12:,.0f}/month average)")

        print()
        print(f"💡 CALCULATION METHODOLOGY")
        print(f"   • Payment Changes: (% change × $600/day × 365 days)")
        print(f"   • Staffing Mandates: (Additional FTE × $75,000/year)")
        print(f"   • Compliance Costs: $800-$2,500 PBPY depending on requirements")
        print(f"   • System Upgrades: ~$2,500 PBPY for technology implementations")
        print(f"   • Documentation: ~$1,200 PBPY for additional reporting requirements")
        print()

        print(f"✅ Financial impact analysis complete!")
        print(f"📊 {total_bills} bills analyzed with total PBPY impact of ${total_impact:,}")

        return {
            'total_bills': total_bills,
            'total_impact': total_impact,
            'avg_impact': avg_impact,
            'bills': bills
        }

    except Exception as e:
        print(f"❌ Report generation failed: {e}")
        return None

if __name__ == "__main__":
    generate_financial_impact_report()