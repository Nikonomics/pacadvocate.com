#!/usr/bin/env python3
"""
Simplified Transaction Analysis using built-in Python libraries
"""

import csv
from collections import defaultdict, Counter
from datetime import datetime

def analyze_transactions(file_path):
    """Analyze transaction data for cost savings and fraud indicators"""
    
    transactions = []
    facility_totals = defaultdict(float)
    category_totals = defaultdict(float)
    category_counts = defaultdict(int)
    facility_transactions = defaultdict(list)
    daily_transactions = defaultdict(list)
    
    # Read and parse data
    with open(file_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # Clean amount field - handle spaces in column names
                net_amount = float(row[' NET '].replace(',', '').strip())
                facility = row['Facility'].strip()
                category = row['Account Description'].strip()
                date = row['TRX Date'].strip()
                
                transactions.append({
                    'facility': facility,
                    'category': category, 
                    'amount': net_amount,
                    'date': date,
                    'vendor': row['Originating Master Name'].strip()
                })
                
                facility_totals[facility] += net_amount
                category_totals[category] += net_amount
                category_counts[category] += 1
                facility_transactions[facility].append(net_amount)
                daily_transactions[f"{facility}_{date}"].append(net_amount)
                
            except (ValueError, KeyError):
                continue
    
    print("=== TRANSACTION ANALYSIS REPORT ===")
    print(f"Total transactions analyzed: {len(transactions):,}")
    print(f"Total spending: ${sum(t['amount'] for t in transactions):,.2f}")
    print(f"Number of facilities: {len(facility_totals)}")
    print(f"Date range: {min(t['date'] for t in transactions)} to {max(t['date'] for t in transactions)}")
    
    # 1. SPENDING BY FACILITY
    print(f"\n=== TOP 10 FACILITIES BY SPENDING ===")
    sorted_facilities = sorted(facility_totals.items(), key=lambda x: x[1], reverse=True)
    for i, (facility, total) in enumerate(sorted_facilities[:10], 1):
        count = len([t for t in transactions if t['facility'] == facility])
        avg = total / count if count > 0 else 0
        print(f"{i:2d}. Facility {facility}: ${total:,.2f} ({count} transactions, ${avg:.2f} avg)")
    
    # 2. SPENDING BY CATEGORY
    print(f"\n=== TOP 15 CATEGORIES BY SPENDING ===")
    sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
    for i, (category, total) in enumerate(sorted_categories[:15], 1):
        count = category_counts[category]
        avg = total / count if count > 0 else 0
        facilities_using = len(set(t['facility'] for t in transactions if t['category'] == category))
        print(f"{i:2d}. {category}")
        print(f"     ${total:,.2f} ({count} transactions, ${avg:.2f} avg, {facilities_using} facilities)")
    
    # 3. HIGH-FREQUENCY PURCHASES (Master Contract Candidates)
    print(f"\n=== MASTER CONTRACT OPPORTUNITIES ===")
    print("Categories with high volume and multiple facilities:")
    master_contract_candidates = []
    for category, total in sorted_categories:
        count = category_counts[category]
        facilities_using = len(set(t['facility'] for t in transactions if t['category'] == category))
        if count >= 20 and facilities_using >= 3 and total >= 500:  # Thresholds for bulk buying
            master_contract_candidates.append((category, total, count, facilities_using))
    
    for i, (category, total, count, facilities) in enumerate(master_contract_candidates[:10], 1):
        print(f"{i:2d}. {category}")
        print(f"     ${total:,.2f} ({count} transactions across {facilities} facilities)")
        print(f"     Potential 15% savings: ${total * 0.15:,.2f}")
    
    # 4. FRAUD INDICATORS
    print(f"\n=== POTENTIAL FRAUD INDICATORS ===")
    
    # High-value transactions (outliers)
    amounts = [t['amount'] for t in transactions]
    amounts.sort()
    p99 = amounts[int(len(amounts) * 0.99)] if amounts else 0
    
    high_value_txns = [t for t in transactions if t['amount'] > p99]
    print(f"\nHigh-Value Transactions (>99th percentile: ${p99:.2f}):")
    print(f"Found {len(high_value_txns)} suspicious high-value transactions:")
    for txn in sorted(high_value_txns, key=lambda x: x['amount'], reverse=True)[:10]:
        print(f"  Facility {txn['facility']}: ${txn['amount']:,.2f} - {txn['category']}")
    
    # Round number transactions
    round_amounts = [t for t in transactions if t['amount'] >= 50 and t['amount'] % 50 == 0]
    print(f"\nLarge Round-Number Transactions (potential red flags):")
    print(f"Found {len(round_amounts)} transactions with suspicious round amounts >= $50:")
    for txn in sorted(round_amounts, key=lambda x: x['amount'], reverse=True)[:10]:
        print(f"  Facility {txn['facility']}: ${txn['amount']:,.2f} - {txn['category']}")
    
    # Multiple transactions same day per facility
    multiple_daily = {}
    for key, txn_list in daily_transactions.items():
        if len(txn_list) > 5:  # More than 5 transactions same day
            facility, date = key.split('_', 1)
            total = sum(txn_list)
            multiple_daily[key] = (facility, date, len(txn_list), total)
    
    print(f"\nMultiple Same-Day Transactions (potential transaction splitting):")
    print(f"Found {len(multiple_daily)} facility-date combinations with >5 transactions:")
    for key, (facility, date, count, total) in sorted(multiple_daily.items(), 
                                                      key=lambda x: x[1][2], reverse=True)[:10]:
        print(f"  Facility {facility} on {date}: {count} transactions totaling ${total:,.2f}")
    
    # 5. COST-SAVING SUMMARY
    print(f"\n=== COST-SAVING RECOMMENDATIONS ===")
    total_amazon_spend = sum(t['amount'] for t in transactions)
    
    print(f"Current Amazon spending: ${total_amazon_spend:,.2f}")
    print(f"Estimated potential savings with master contracts:")
    
    # Calculate savings potential for master contract candidates
    total_contractable_spend = sum(candidate[1] for candidate in master_contract_candidates)
    estimated_savings = total_contractable_spend * 0.15  # 15% savings estimate
    
    print(f"  Spending eligible for master contracts: ${total_contractable_spend:,.2f}")
    print(f"  Potential annual savings (15%): ${estimated_savings:,.2f}")
    print(f"  Remaining Amazon spend: ${total_amazon_spend - total_contractable_spend:,.2f}")
    
    # Top facilities for training/oversight
    print(f"\nFacilities requiring procurement training/oversight:")
    for facility, total in sorted_facilities[:5]:
        pct_of_total = (total / total_amazon_spend) * 100
        print(f"  Facility {facility}: ${total:,.2f} ({pct_of_total:.1f}% of total Amazon spend)")
    
    print(f"\n=== EXECUTIVE SUMMARY ===")
    print(f"• Analyzed {len(transactions):,} Amazon transactions totaling ${total_amazon_spend:,.2f}")
    print(f"• Identified {len(master_contract_candidates)} categories for master contract negotiations")
    print(f"• Potential annual savings: ${estimated_savings:,.2f} ({(estimated_savings/total_amazon_spend)*100:.1f}%)")
    print(f"• Found {len(high_value_txns)} high-value transactions needing review")
    print(f"• Found {len(round_amounts)} suspicious round-number transactions")
    print(f"• Identified {len(multiple_daily)} instances of potential transaction splitting")

if __name__ == "__main__":
    file_path = "/Users/nikolashulewsky/Downloads/Amazon 2025.xlsx - 2025 Data (1).csv"
    analyze_transactions(file_path)