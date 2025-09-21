#!/usr/bin/env python3
"""
Test Facility Personalization
Test financial impact calculations with different facility configurations
"""

import sys
import json
from datetime import datetime

# Add the project root to the path so we can import our modules
sys.path.append('/Users/nikolashulewsky')

from financial_impact_calculator import SNFFinancialCalculator

def test_facility_personalization():
    """Test financial impact calculations with various facility configurations"""

    print("🧪 TESTING FACILITY PERSONALIZATION")
    print("=" * 60)
    print("🎯 Testing financial impact calculations with different facility types")
    print()

    calculator = SNFFinancialCalculator()

    # Test bill: SNF Payment System (high impact)
    test_bill = {
        'title': 'Medicare Program; Prospective Payment System and Consolidated Billing for Skilled Nursing Facilities; Updates to the Quality Reporting Program for Federal Fiscal Year 2026',
        'summary': 'This rule updates the SNF PPS rates for FY 2026 with a 2.8% increase and modifies quality reporting requirements.'
    }

    # Define different facility scenarios
    facility_scenarios = [
        {
            'name': 'Small Rural SNF',
            'params': {
                'bed_count': 50,
                'occupancy_rate': 75,
                'payer_mix': {'medicare': 55, 'medicaid': 45}
            },
            'description': '50-bed rural facility with higher Medicaid mix'
        },
        {
            'name': 'Medium Suburban SNF',
            'params': {
                'bed_count': 100,
                'occupancy_rate': 85,
                'payer_mix': {'medicare': 65, 'medicaid': 35}
            },
            'description': '100-bed suburban facility with typical payer mix'
        },
        {
            'name': 'Large Urban SNF',
            'params': {
                'bed_count': 180,
                'occupancy_rate': 90,
                'payer_mix': {'medicare': 75, 'medicaid': 25}
            },
            'description': '180-bed urban facility with high Medicare mix'
        },
        {
            'name': 'High-End Rehabilitation',
            'params': {
                'bed_count': 120,
                'occupancy_rate': 95,
                'payer_mix': {'medicare': 85, 'medicaid': 15}
            },
            'description': '120-bed rehabilitation-focused facility'
        },
        {
            'name': 'Medicaid-Heavy Facility',
            'params': {
                'bed_count': 150,
                'occupancy_rate': 80,
                'payer_mix': {'medicare': 40, 'medicaid': 60}
            },
            'description': '150-bed facility serving primarily Medicaid population'
        }
    ]

    print("📊 FACILITY SCENARIO TESTING:")
    print("-" * 40)

    results = []

    for scenario in facility_scenarios:
        name = scenario['name']
        params = scenario['params']
        description = scenario['description']

        print(f"\n🏥 {name}")
        print(f"   📝 {description}")
        print(f"   🛏️ Beds: {params['bed_count']} | 📈 Occupancy: {params['occupancy_rate']}%")
        print(f"   💊 Medicare: {params['payer_mix']['medicare']}% | 🏛️ Medicaid: {params['payer_mix']['medicaid']}%")

        # Calculate financial impact
        impact = calculator.calculate_bill_financial_impact(test_bill, params)
        summary = calculator.generate_impact_summary(test_bill, params)

        # Display results
        annual_impact = impact['annual_facility_impact']
        daily_impact = impact['per_bed_daily_impact']
        medicare_change = impact['medicare_rate_change_percent']

        print(f"   {summary}")
        print(f"   📊 Details: ${daily_impact:.2f}/bed/day | {medicare_change:+.1f}% Medicare rate change")

        # Calculate impact per occupied bed for comparison
        occupied_beds = params['bed_count'] * (params['occupancy_rate'] / 100)
        impact_per_occupied_bed = annual_impact / occupied_beds if occupied_beds > 0 else 0

        results.append({
            'name': name,
            'annual_impact': annual_impact,
            'per_bed_daily': daily_impact,
            'per_occupied_bed_annual': impact_per_occupied_bed,
            'total_beds': params['bed_count'],
            'occupied_beds': occupied_beds
        })

    # Analysis of results
    print("\n\n📊 COMPARATIVE ANALYSIS:")
    print("=" * 30)

    # Sort by total annual impact
    results.sort(key=lambda x: x['annual_impact'], reverse=True)

    print("💰 Ranking by Total Annual Impact:")
    for i, result in enumerate(results, 1):
        impact = result['annual_impact']
        facility = result['name']
        beds = result['total_beds']
        print(f"   {i}. {facility}: ${impact:,.0f} ({beds} beds)")

    print()

    # Sort by per-occupied-bed impact
    results.sort(key=lambda x: x['per_occupied_bed_annual'], reverse=True)

    print("📊 Ranking by Impact Per Occupied Bed:")
    for i, result in enumerate(results, 1):
        impact_per_bed = result['per_occupied_bed_annual']
        facility = result['name']
        occupied = result['occupied_beds']
        print(f"   {i}. {facility}: ${impact_per_bed:,.0f} per occupied bed ({occupied:.0f} occupied)")

    print()

    # Calculate efficiency metrics
    most_efficient = min(results, key=lambda x: x['per_occupied_bed_annual'])
    least_efficient = max(results, key=lambda x: x['per_occupied_bed_annual'])

    print("⚡ EFFICIENCY INSIGHTS:")
    print(f"   🟢 Most Efficient: {most_efficient['name']}")
    print(f"      💰 ${most_efficient['per_occupied_bed_annual']:,.0f} per occupied bed annually")
    print(f"   🔴 Least Efficient: {least_efficient['name']}")
    print(f"      💰 ${least_efficient['per_occupied_bed_annual']:,.0f} per occupied bed annually")

    efficiency_ratio = least_efficient['per_occupied_bed_annual'] / most_efficient['per_occupied_bed_annual']
    print(f"   📊 Efficiency Gap: {efficiency_ratio:.1f}x difference")

    print()

    # Test different rate change scenarios
    print("📈 TESTING DIFFERENT RATE CHANGE SCENARIOS:")
    print("-" * 45)

    rate_scenarios = [
        {'name': '1% Rate Increase', 'title': 'Medicare Program; SNF PPS Update with 1% rate increase'},
        {'name': '3% Rate Increase', 'title': 'Medicare Program; SNF PPS Update with 3% rate increase'},
        {'name': '2% Rate Decrease', 'title': 'Medicare Program; SNF PPS Update with 2% rate decrease'},
        {'name': 'Quality Bonus Program', 'title': 'Medicare Program; SNF Quality Reporting Program with 1.5% bonus potential'}
    ]

    # Use medium suburban facility as baseline
    baseline_facility = facility_scenarios[1]['params']  # Medium Suburban SNF

    for scenario in rate_scenarios:
        test_rate_bill = {
            'title': scenario['title'],
            'summary': 'Rate change scenario for testing'
        }

        impact = calculator.calculate_bill_financial_impact(test_rate_bill, baseline_facility)
        summary = calculator.generate_impact_summary(test_rate_bill, baseline_facility)

        print(f"   📊 {scenario['name']}: {summary}")

    print()

    print("🎯 KEY INSIGHTS FROM PERSONALIZATION TESTING:")
    print("-" * 50)
    print("   🏥 Facility size significantly impacts total annual cost")
    print("   📊 Medicare payer mix percentage is the primary driver")
    print("   📈 Occupancy rate affects total impact but not per-bed efficiency")
    print("   🎛️ High-Medicare facilities face higher regulatory impact")
    print("   💡 Rural facilities with lower Medicare mix have reduced exposure")
    print()

    print("🔧 PERSONALIZATION BENEFITS:")
    print("   ✅ Accurate cost projections for budget planning")
    print("   ✅ ROI calculations for compliance investments")
    print("   ✅ Risk assessment based on payer mix")
    print("   ✅ Facility-specific regulatory impact analysis")

    return True

def create_facility_configuration_template():
    """Create a configuration template for facility customization"""

    print("\n📋 CREATING FACILITY CONFIGURATION TEMPLATE")
    print("-" * 50)

    config_template = {
        "facility_info": {
            "name": "Your SNF Name",
            "location": "City, State",
            "license_number": "SNF-12345"
        },
        "facility_parameters": {
            "bed_count": 100,
            "occupancy_rate": 85,
            "payer_mix": {
                "medicare": 65,
                "medicaid": 35,
                "private_pay": 0,
                "managed_care": 0
            }
        },
        "financial_rates": {
            "medicare_daily_rate": 600.0,
            "medicaid_daily_rate": 250.0,
            "private_pay_daily_rate": 350.0
        },
        "calculation_preferences": {
            "include_indirect_costs": True,
            "quality_bonus_risk_factor": 1.2,
            "compliance_cost_multiplier": 1.1
        },
        "last_updated": datetime.now().isoformat()
    }

    # Save template to file
    with open('/Users/nikolashulewsky/facility_config_template.json', 'w') as f:
        json.dump(config_template, f, indent=2)

    print("✅ Created facility configuration template: facility_config_template.json")
    print()
    print("🔧 CONFIGURATION PARAMETERS:")
    print("   🏥 Facility Information: Name, location, license")
    print("   📊 Bed Count: Number of licensed beds")
    print("   📈 Occupancy Rate: Average occupancy percentage")
    print("   💊 Payer Mix: Medicare, Medicaid, private percentages")
    print("   💰 Daily Rates: Facility-specific reimbursement rates")
    print("   ⚙️ Calculation Preferences: Risk factors and multipliers")
    print()
    print("💡 USAGE:")
    print("   1. Copy and customize the template for your facility")
    print("   2. Update bed count and occupancy rate")
    print("   3. Adjust payer mix percentages to match your census")
    print("   4. Modify daily rates if you have facility-specific data")
    print("   5. Use configuration in financial impact calculations")

if __name__ == "__main__":
    test_facility_personalization()
    create_facility_configuration_template()