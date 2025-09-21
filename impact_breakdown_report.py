#!/usr/bin/env python3
"""
Impact Breakdown Report
Generate comprehensive report showing all 4-category impact analysis
"""

import sqlite3
import json
from datetime import datetime

def generate_impact_breakdown_report():
    """Generate detailed impact breakdown report"""
    print("📊 SNF COMPREHENSIVE IMPACT BREAKDOWN REPORT")
    print("=" * 55)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    try:
        conn = sqlite3.connect('snflegtracker.db')
        cursor = conn.cursor()

        # Get all bills with impact breakdown
        cursor.execute("""
            SELECT id, title, ai_relevance_score, ai_impact_type,
                   impact_breakdown, rule_type, status
            FROM bills
            WHERE is_active = 1 AND impact_breakdown IS NOT NULL
            ORDER BY id
        """)

        bills = cursor.fetchall()
        conn.close()

        if not bills:
            print("❌ No bills with impact breakdown found")
            return

        print(f"📊 COMPREHENSIVE IMPACT ANALYSIS - {len(bills)} BILLS")
        print("=" * 55)

        # Category statistics
        financial_scores = []
        staffing_scores = []
        quality_scores = []
        compliance_scores = []
        overall_scores = []

        high_burden_by_category = {'financial': 0, 'staffing': 0, 'quality': 0, 'compliance': 0}
        moderate_burden_by_category = {'financial': 0, 'staffing': 0, 'quality': 0, 'compliance': 0}

        print(f"📋 DETAILED BILL ANALYSIS")
        print("-" * 40)

        for i, bill in enumerate(bills, 1):
            (bill_id, title, ai_score, ai_type, breakdown_json, rule_type, status) = bill

            try:
                breakdown = json.loads(breakdown_json)

                financial = breakdown['financial']
                staffing = breakdown['staffing']
                quality = breakdown['quality']
                compliance = breakdown['compliance']
                overall = breakdown['overall_score']

                # Collect scores
                financial_scores.append(financial['score'])
                staffing_scores.append(staffing['score'])
                quality_scores.append(quality['score'])
                compliance_scores.append(compliance['score'])
                overall_scores.append(overall)

                # Count burden levels
                for category, data in [('financial', financial), ('staffing', staffing),
                                     ('quality', quality), ('compliance', compliance)]:
                    if data['burden_level'] == 'high':
                        high_burden_by_category[category] += 1
                    elif data['burden_level'] == 'moderate':
                        moderate_burden_by_category[category] += 1

                print(f"{i:2d}. Bill {bill_id}: {title[:50]}...")
                print(f"    🎯 AI Score: {ai_score}/100 | Type: {ai_type} | Status: {status}")
                print(f"    📊 Overall Impact: {overall:.1f}/10")
                print(f"    💰 Financial: {financial['score']}/10 ({financial['burden_level']})")
                print(f"    👥 Staffing: {staffing['score']}/10 ({staffing['burden_level']})")
                print(f"    ⭐ Quality: {quality['score']}/10 ({quality['burden_level']})")
                print(f"    📋 Compliance: {compliance['score']}/10 ({compliance['burden_level']})")

                # Show key details
                if financial['rate_changes']:
                    rate_change = financial['rate_changes'][0]
                    print(f"        💸 Rate Change: {rate_change['type']} {abs(rate_change['percentage'])}%")

                if staffing['training_needs']:
                    print(f"        📚 Training: {len(staffing['training_needs'])} requirements")

                if quality['new_measures']:
                    print(f"        📏 Quality Measures: {len(quality['new_measures'])} new measures")

                if compliance['documentation_requirements']:
                    print(f"        📄 Documentation: {len(compliance['documentation_requirements'])} requirements")

                print()

            except (json.JSONDecodeError, KeyError) as e:
                print(f"    ❌ Error parsing breakdown for Bill {bill_id}: {e}")
                continue

        # Summary statistics
        print(f"📈 IMPACT CATEGORY STATISTICS")
        print("-" * 35)

        categories = [
            ('Financial', financial_scores, '💰'),
            ('Staffing', staffing_scores, '👥'),
            ('Quality', quality_scores, '⭐'),
            ('Compliance', compliance_scores, '📋')
        ]

        for name, scores, emoji in categories:
            if scores:
                avg_score = sum(scores) / len(scores)
                max_score = max(scores)
                min_score = min(scores)
                high_count = high_burden_by_category[name.lower()]
                moderate_count = moderate_burden_by_category[name.lower()]

                print(f"{emoji} {name} Impact:")
                print(f"   Average Score: {avg_score:.1f}/10")
                print(f"   Range: {min_score}-{max_score}/10")
                print(f"   High Burden: {high_count} bills")
                print(f"   Moderate Burden: {moderate_count} bills")
                print()

        # Overall impact ranking
        print(f"🏆 TOP 5 HIGHEST IMPACT BILLS (Overall)")
        print("-" * 40)

        bill_rankings = []
        for i, bill in enumerate(bills):
            try:
                breakdown = json.loads(bill[4])
                bill_rankings.append({
                    'id': bill[0],
                    'title': bill[1][:60] + "..." if len(bill[1]) > 60 else bill[1],
                    'overall_score': breakdown['overall_score'],
                    'breakdown': breakdown
                })
            except:
                continue

        sorted_bills = sorted(bill_rankings, key=lambda x: x['overall_score'], reverse=True)

        for i, bill in enumerate(sorted_bills[:5], 1):
            b = bill['breakdown']
            print(f"{i}. Bill {bill['id']}: {bill['overall_score']:.1f}/10")
            print(f"   {bill['title']}")
            print(f"   💰{b['financial']['score']} 👥{b['staffing']['score']} ⭐{b['quality']['score']} 📋{b['compliance']['score']}")
            print()

        # Category leaders
        print(f"🥇 HIGHEST IMPACT BY CATEGORY")
        print("-" * 30)

        category_leaders = {}
        for bill in bill_rankings:
            b = bill['breakdown']
            for cat_name, cat_data in [('Financial', 'financial'), ('Staffing', 'staffing'),
                                     ('Quality', 'quality'), ('Compliance', 'compliance')]:
                score = b[cat_data]['score']
                if cat_name not in category_leaders or score > category_leaders[cat_name]['score']:
                    category_leaders[cat_name] = {
                        'score': score,
                        'bill_id': bill['id'],
                        'title': bill['title']
                    }

        for cat_name, leader in category_leaders.items():
            emoji = {'Financial': '💰', 'Staffing': '👥', 'Quality': '⭐', 'Compliance': '📋'}[cat_name]
            print(f"{emoji} {cat_name}: Bill {leader['bill_id']} ({leader['score']}/10)")
            print(f"   {leader['title']}")
            print()

        print(f"✅ Impact breakdown analysis complete!")
        print(f"📊 {len(bills)} bills analyzed across 4 impact categories")
        print(f"🎯 Average overall impact: {sum(overall_scores)/len(overall_scores):.1f}/10")

        return {
            'total_bills': len(bills),
            'overall_scores': overall_scores,
            'category_stats': {
                'financial': financial_scores,
                'staffing': staffing_scores,
                'quality': quality_scores,
                'compliance': compliance_scores
            },
            'top_bills': sorted_bills[:5]
        }

    except Exception as e:
        print(f"❌ Report generation failed: {e}")
        return None

if __name__ == "__main__":
    generate_impact_breakdown_report()