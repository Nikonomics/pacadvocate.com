#!/usr/bin/env python3
"""
SNF Financial Impact Calculator
Calculate personalized financial impacts for SNF bills based on facility characteristics
"""

import sqlite3
import os
import json
import re
from datetime import datetime
from typing import Dict, Optional, List, Tuple

class SNFFinancialCalculator:
    """Calculate financial impacts for SNF legislation based on facility parameters"""

    def __init__(self):
        # Standard Medicare and Medicaid daily rates (national averages)
        self.medicare_daily_rate = 600.0  # Average Medicare SNF daily rate
        self.medicaid_daily_rate = 250.0  # Average Medicaid SNF daily rate

        # Default payer mix percentages
        self.default_payer_mix = {
            'medicare': 65,  # Typical SNF Medicare percentage
            'medicaid': 35   # Typical SNF Medicaid percentage
        }

        # Standard facility parameters
        self.default_bed_count = 100
        self.default_occupancy_rate = 85  # 85% occupancy

    def calculate_bill_financial_impact(self, bill_data: Dict, facility_params: Dict = None) -> Dict:
        """
        Calculate comprehensive financial impact for a bill

        Args:
            bill_data: Dictionary with bill information (title, summary, etc.)
            facility_params: Dictionary with facility-specific parameters

        Returns:
            Dictionary with detailed financial impact calculations
        """
        if not facility_params:
            facility_params = {
                'bed_count': self.default_bed_count,
                'occupancy_rate': self.default_occupancy_rate,
                'payer_mix': self.default_payer_mix.copy()
            }

        # Extract rate changes from bill content
        rate_changes = self._extract_rate_changes(bill_data)

        # Determine impact category
        impact_category = self._determine_impact_category(bill_data)

        # Calculate base financial metrics
        financial_impact = self._calculate_base_impact(
            rate_changes, impact_category, facility_params
        )

        # Add bill-specific adjustments
        financial_impact.update(self._calculate_bill_specific_adjustments(
            bill_data, facility_params
        ))

        return financial_impact

    def _extract_rate_changes(self, bill_data: Dict) -> Dict:
        """Extract rate change information from bill title and summary"""
        title = bill_data.get('title', '').lower()
        summary = bill_data.get('summary', '').lower()
        text = f"{title} {summary}"

        rate_changes = {
            'medicare_percent': 0.0,
            'medicaid_percent': 0.0,
            'quality_bonus_percent': 0.0,
            'compliance_cost_percent': 0.0
        }

        # Look for specific rate change patterns
        rate_patterns = [
            (r'(\d+\.?\d*)\s*percent.*increase', 'positive'),
            (r'(\d+\.?\d*)\%.*increase', 'positive'),
            (r'increase.*(\d+\.?\d*)\s*percent', 'positive'),
            (r'(\d+\.?\d*)\s*percent.*decrease', 'negative'),
            (r'(\d+\.?\d*)\%.*decrease', 'negative'),
            (r'decrease.*(\d+\.?\d*)\s*percent', 'negative'),
            (r'update.*(\d+\.?\d*)\s*percent', 'neutral'),
            (r'(\d+\.?\d*)\%.*update', 'neutral')
        ]

        for pattern, direction in rate_patterns:
            matches = re.findall(pattern, text)
            if matches:
                try:
                    rate = float(matches[0])
                    if direction == 'negative':
                        rate = -rate

                    # Assign to appropriate category based on bill content
                    if 'medicare' in text and 'skilled nursing' in text:
                        rate_changes['medicare_percent'] = rate
                    elif 'medicaid' in text:
                        rate_changes['medicaid_percent'] = rate
                    elif 'quality' in text:
                        rate_changes['quality_bonus_percent'] = rate
                    else:
                        rate_changes['medicare_percent'] = rate  # Default to Medicare
                    break
                except ValueError:
                    continue

        # Use estimated rates if no specific rates found
        if not any(rate_changes.values()):
            rate_changes.update(self._estimate_rate_changes(bill_data))

        return rate_changes

    def _estimate_rate_changes(self, bill_data: Dict) -> Dict:
        """Estimate rate changes based on bill type and content"""
        title = bill_data.get('title', '').lower()

        # SNF payment system updates - typically 2-4% annually
        if 'skilled nursing' in title and 'payment' in title:
            return {'medicare_percent': 2.8}  # Historical average

        # Quality reporting programs - potential 1-2% bonus/penalty
        elif 'quality' in title:
            return {'quality_bonus_percent': 1.5}

        # Competitive facility changes - minimal direct impact
        elif any(facility in title for facility in ['rehabilitation', 'psychiatric', 'hospice']):
            return {'medicare_percent': 0.1}

        # Medicare Advantage changes - moderate impact
        elif 'medicare advantage' in title:
            return {'medicare_percent': 1.0}

        return {'medicare_percent': 0.5}  # Default minimal impact

    def _determine_impact_category(self, bill_data: Dict) -> str:
        """Determine the category of financial impact"""
        title = bill_data.get('title', '').lower()

        if 'quality' in title or 'reporting' in title:
            return 'quality_bonus'
        elif 'compliance' in title or 'requirement' in title:
            return 'compliance_cost'
        elif any(term in title for term in ['payment', 'rate', 'prospective']):
            return 'rate_change'
        elif any(facility in title for facility in ['rehabilitation', 'psychiatric', 'hospice']):
            return 'competitive_effect'
        else:
            return 'rate_change'

    def _calculate_base_impact(self, rate_changes: Dict, impact_category: str, facility_params: Dict) -> Dict:
        """Calculate base financial impact using facility parameters"""
        bed_count = facility_params['bed_count']
        occupancy_rate = facility_params['occupancy_rate'] / 100
        payer_mix = facility_params['payer_mix']

        # Calculate occupied beds by payer
        total_occupied_beds = bed_count * occupancy_rate
        medicare_beds = total_occupied_beds * (payer_mix['medicare'] / 100)
        medicaid_beds = total_occupied_beds * (payer_mix['medicaid'] / 100)

        # Calculate daily impact per bed
        medicare_daily_impact = (rate_changes.get('medicare_percent', 0) / 100) * self.medicare_daily_rate
        medicaid_daily_impact = (rate_changes.get('medicaid_percent', 0) / 100) * self.medicaid_daily_rate
        quality_daily_impact = (rate_changes.get('quality_bonus_percent', 0) / 100) * self.medicare_daily_rate

        # Total daily impact for facility
        total_daily_impact = (
            (medicare_daily_impact * medicare_beds) +
            (medicaid_daily_impact * medicaid_beds) +
            (quality_daily_impact * medicare_beds)  # Quality bonuses typically apply to Medicare
        )

        # Calculate per-bed daily impact (average across all beds)
        per_bed_daily_impact = total_daily_impact / bed_count if bed_count > 0 else 0

        # Annual impact
        annual_facility_impact = total_daily_impact * 365

        return {
            'per_bed_daily_impact': round(per_bed_daily_impact, 2),
            'annual_facility_impact': round(annual_facility_impact, 0),
            'medicare_rate_change_percent': rate_changes.get('medicare_percent', 0),
            'medicaid_rate_change_percent': rate_changes.get('medicaid_percent', 0),
            'financial_impact_category': impact_category,
            'payer_mix_assumption': json.dumps(payer_mix),
            'calculation_details': {
                'medicare_beds': round(medicare_beds, 1),
                'medicaid_beds': round(medicaid_beds, 1),
                'medicare_daily_impact_per_bed': round(medicare_daily_impact, 2),
                'medicaid_daily_impact_per_bed': round(medicaid_daily_impact, 2),
                'quality_daily_impact_per_bed': round(quality_daily_impact, 2)
            }
        }

    def _calculate_bill_specific_adjustments(self, bill_data: Dict, facility_params: Dict) -> Dict:
        """Calculate bill-specific adjustments and explanations"""
        title = bill_data.get('title', '').lower()

        adjustments = {}

        # SNF-specific bills get higher impact
        if 'skilled nursing' in title:
            adjustments['snf_specific_multiplier'] = 1.0
            adjustments['impact_explanation'] = "Direct SNF impact - affects all Medicare days"

        # Quality bills have bonus/penalty potential
        elif 'quality' in title:
            adjustments['quality_risk_multiplier'] = 1.2  # 20% higher due to penalty risk
            adjustments['impact_explanation'] = "Quality program - potential for bonuses or penalties"

        # Competitive facility bills have indirect impact
        elif any(facility in title for facility in ['rehabilitation', 'psychiatric']):
            adjustments['competitive_multiplier'] = 0.3  # Reduced impact
            adjustments['impact_explanation'] = "Indirect impact through referral pattern changes"

        else:
            adjustments['impact_explanation'] = "General Medicare regulation impact"

        return adjustments

    def generate_impact_summary(self, bill_data: Dict, facility_params: Dict = None) -> str:
        """Generate a human-readable impact summary"""
        impact = self.calculate_bill_financial_impact(bill_data, facility_params)

        bed_count = facility_params['bed_count'] if facility_params else self.default_bed_count
        annual_impact = impact['annual_facility_impact']
        per_bed_impact = impact['per_bed_daily_impact']

        # Determine if impact is positive (cost) or negative (savings)
        if annual_impact > 0:
            impact_verb = "cost"
            impact_emoji = "💸"
        elif annual_impact < 0:
            impact_verb = "save"
            impact_emoji = "💰"
            annual_impact = abs(annual_impact)
        else:
            return f"📊 This bill has minimal financial impact on your {bed_count}-bed facility."

        return (f"{impact_emoji} This will {impact_verb} your {bed_count}-bed facility "
                f"${annual_impact:,.0f} per year (${per_bed_impact:.2f} per bed daily)")

def update_all_bills_financial_impact():
    """Update financial impact calculations for all bills in the database"""

    db_path = 'snflegtracker.db'
    if not os.path.exists(db_path):
        print(f"❌ Database file not found: {db_path}")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        print("💰 CALCULATING FINANCIAL IMPACTS FOR ALL BILLS")
        print("=" * 60)
        print("🎯 Using SNF Financial Calculator with standard facility parameters")
        print()

        calculator = SNFFinancialCalculator()

        # Standard facility parameters (100-bed facility)
        facility_params = {
            'bed_count': 100,
            'occupancy_rate': 85,
            'payer_mix': {'medicare': 65, 'medicaid': 35}
        }

        print("📊 FACILITY PARAMETERS:")
        print(f"   🏥 Bed Count: {facility_params['bed_count']} beds")
        print(f"   📈 Occupancy Rate: {facility_params['occupancy_rate']}%")
        print(f"   💊 Medicare Mix: {facility_params['payer_mix']['medicare']}%")
        print(f"   🏛️ Medicaid Mix: {facility_params['payer_mix']['medicaid']}%")
        print(f"   💵 Medicare Rate: ${calculator.medicare_daily_rate}/day")
        print(f"   💴 Medicaid Rate: ${calculator.medicaid_daily_rate}/day")
        print()

        # Get all active bills
        cursor.execute("""
            SELECT id, title, summary
            FROM bills
            WHERE is_active = 1
            ORDER BY relevance_score DESC
        """)

        bills = cursor.fetchall()
        print(f"📋 CALCULATING IMPACTS FOR {len(bills)} BILLS:")
        print("=" * 50)

        updated_bills = 0

        for bill_id, title, summary in bills:
            bill_data = {
                'title': title,
                'summary': summary or ''
            }

            print(f"💰 Bill {bill_id}: {title[:50]}...")

            # Calculate financial impact
            financial_impact = calculator.calculate_bill_financial_impact(
                bill_data, facility_params
            )

            # Generate impact summary
            impact_summary = calculator.generate_impact_summary(bill_data, facility_params)

            # Update database
            cursor.execute("""
                UPDATE bills
                SET per_bed_daily_impact = ?,
                    annual_facility_impact = ?,
                    medicare_rate_change_percent = ?,
                    medicaid_rate_change_percent = ?,
                    payer_mix_assumption = ?,
                    financial_impact_category = ?,
                    updated_at = ?
                WHERE id = ?
            """, (
                financial_impact['per_bed_daily_impact'],
                financial_impact['annual_facility_impact'],
                financial_impact['medicare_rate_change_percent'],
                financial_impact['medicaid_rate_change_percent'],
                financial_impact['payer_mix_assumption'],
                financial_impact['financial_impact_category'],
                datetime.utcnow(),
                bill_id
            ))

            updated_bills += 1

            # Display results
            annual_impact = financial_impact['annual_facility_impact']
            daily_impact = financial_impact['per_bed_daily_impact']
            category = financial_impact['financial_impact_category'].replace('_', ' ').title()

            if annual_impact > 1000:
                impact_emoji = "💸"
                impact_color = "red"
            elif annual_impact < -1000:
                impact_emoji = "💰"
                impact_color = "green"
            else:
                impact_emoji = "📊"
                impact_color = "blue"

            print(f"   {impact_emoji} {impact_summary}")
            print(f"   🏷️ Category: {category}")

            if financial_impact.get('medicare_rate_change_percent'):
                medicare_change = financial_impact['medicare_rate_change_percent']
                print(f"   📈 Medicare Rate Change: {medicare_change:+.1f}%")

            print()

        # Commit changes
        conn.commit()

        # Generate summary statistics
        cursor.execute("""
            SELECT financial_impact_category,
                   COUNT(*) as count,
                   AVG(annual_facility_impact) as avg_annual,
                   SUM(annual_facility_impact) as total_annual
            FROM bills
            WHERE is_active = 1 AND annual_facility_impact IS NOT NULL
            GROUP BY financial_impact_category
            ORDER BY avg_annual DESC
        """)

        category_summary = cursor.fetchall()

        cursor.execute("""
            SELECT SUM(annual_facility_impact) as total_portfolio_impact
            FROM bills
            WHERE is_active = 1
        """)

        total_impact = cursor.fetchone()[0] or 0

        conn.close()

        print("✅ FINANCIAL IMPACT CALCULATION COMPLETE")
        print("=" * 50)
        print(f"📊 Bills calculated: {len(bills)}")
        print(f"✅ Bills updated: {updated_bills}")
        print()

        print("💰 IMPACT BY CATEGORY:")
        for category, count, avg_annual, total_annual in category_summary:
            category_name = category.replace('_', ' ').title()
            impact_emoji = "💸" if avg_annual > 0 else "💰" if avg_annual < 0 else "📊"
            print(f"   {impact_emoji} {category_name}: {count} bills")
            print(f"       📊 Average Impact: ${avg_annual:,.0f} per year")
            print(f"       📈 Category Total: ${total_annual:,.0f} per year")

        print()
        print(f"🎯 TOTAL PORTFOLIO IMPACT: ${total_impact:,.0f} per year")

        if total_impact > 0:
            print(f"💸 Combined legislation will COST your facility ${total_impact:,.0f} annually")
        elif total_impact < 0:
            print(f"💰 Combined legislation will SAVE your facility ${abs(total_impact):,.0f} annually")
        else:
            print("📊 Combined legislation has neutral financial impact")

        print()
        print("🎯 PERSONALIZATION OPTIONS:")
        print("   🏥 Adjust bed count for your facility size")
        print("   📈 Update occupancy rate for your census")
        print("   💊 Modify payer mix for your patient population")
        print("   🔄 Re-run calculations with custom parameters")

        return True

    except Exception as e:
        print(f"❌ Financial impact calculation failed: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    update_all_bills_financial_impact()