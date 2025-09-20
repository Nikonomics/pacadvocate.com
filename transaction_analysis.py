#!/usr/bin/env python3
"""
Skilled Nursing Facility Transaction Analysis
Identifies cost-saving opportunities and potential fraud indicators
"""

import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns
from collections import defaultdict

def load_and_clean_data(file_path):
    """Load and clean transaction data"""
    df = pd.read_csv(file_path)
    
    # Clean column names
    df.columns = df.columns.str.strip()
    
    # Convert amounts to numeric
    df['Debit Amount'] = pd.to_numeric(df['Debit Amount'].str.replace(',', ''), errors='coerce')
    df['NET'] = pd.to_numeric(df['NET'].str.replace(',', ''), errors='coerce')
    
    # Convert date
    df['TRX Date'] = pd.to_datetime(df['TRX Date'])
    
    # Clean facility numbers
    df['Facility'] = df['Facility'].astype(str)
    
    return df

def analyze_spending_patterns(df):
    """Analyze spending patterns by facility and category"""
    print("=== SPENDING ANALYSIS ===")
    
    # Total spending by facility
    facility_spending = df.groupby('Facility')['NET'].agg(['sum', 'count', 'mean']).round(2)
    facility_spending.columns = ['Total_Spent', 'Transaction_Count', 'Avg_Transaction']
    facility_spending = facility_spending.sort_values('Total_Spent', ascending=False)
    
    print("\nTop 10 Facilities by Total Spending:")
    print(facility_spending.head(10))
    
    # Spending by account category
    category_spending = df.groupby('Account Description')['NET'].agg(['sum', 'count', 'mean']).round(2)
    category_spending.columns = ['Total_Spent', 'Transaction_Count', 'Avg_Transaction']
    category_spending = category_spending.sort_values('Total_Spent', ascending=False)
    
    print("\nTop 15 Categories by Total Spending:")
    print(category_spending.head(15))
    
    return facility_spending, category_spending

def identify_high_frequency_items(df):
    """Identify frequently purchased categories that could benefit from master contracts"""
    print("\n=== HIGH-FREQUENCY PURCHASE ANALYSIS ===")
    
    # Categories with high transaction frequency
    freq_analysis = df.groupby('Account Description').agg({
        'NET': ['sum', 'count', 'mean', 'std'],
        'Facility': 'nunique'
    }).round(2)
    
    freq_analysis.columns = ['Total_Spent', 'Transactions', 'Avg_Amount', 'Std_Dev', 'Facilities_Using']
    freq_analysis['Cost_per_Facility'] = freq_analysis['Total_Spent'] / freq_analysis['Facilities_Using']
    
    # Sort by transaction count to find high-frequency purchases
    high_freq = freq_analysis.sort_values('Transactions', ascending=False)
    
    print("\nMost Frequently Purchased Categories (Good candidates for master contracts):")
    print(high_freq.head(15))
    
    return high_freq

def detect_fraud_indicators(df):
    """Identify potential fraud indicators"""
    print("\n=== FRAUD DETECTION ANALYSIS ===")
    
    fraud_flags = []
    
    # 1. Unusually high transactions (outliers)
    q99 = df['NET'].quantile(0.99)
    high_amount_txns = df[df['NET'] > q99]
    
    print(f"\nHigh-Value Transactions (>99th percentile: ${q99:.2f}):")
    print(f"Found {len(high_amount_txns)} transactions")
    for _, txn in high_amount_txns.head(10).iterrows():
        print(f"  Facility {txn['Facility']}: ${txn['NET']:.2f} - {txn['Account Description']}")
    
    # 2. Suspicious round numbers (potential fake transactions)
    round_amounts = df[df['NET'] % 50 == 0]  # Amounts ending in 00 or 50
    large_round = round_amounts[round_amounts['NET'] >= 100]
    
    print(f"\nLarge Round Number Transactions (potential red flag):")
    print(f"Found {len(large_round)} transactions >= $100 with round amounts")
    for _, txn in large_round.head(10).iterrows():
        print(f"  Facility {txn['Facility']}: ${txn['NET']:.2f} - {txn['Account Description']}")
    
    # 3. Facilities with unusual spending patterns
    facility_stats = df.groupby('Facility')['NET'].agg(['mean', 'std', 'count'])
    facility_stats['cv'] = facility_stats['std'] / facility_stats['mean']  # Coefficient of variation
    
    # High coefficient of variation might indicate inconsistent spending
    high_cv = facility_stats[facility_stats['cv'] > 2].sort_values('cv', ascending=False)
    
    print(f"\nFacilities with High Spending Variability (potential oversight needed):")
    for facility in high_cv.head(5).index:
        cv = high_cv.loc[facility, 'cv']
        avg = high_cv.loc[facility, 'mean']
        print(f"  Facility {facility}: CV={cv:.2f}, Avg=${avg:.2f}")
    
    # 4. Same-day multiple transactions (potential splitting to avoid oversight)
    df['date_facility'] = df['TRX Date'].dt.date.astype(str) + '_' + df['Facility']
    same_day_counts = df['date_facility'].value_counts()
    multiple_same_day = same_day_counts[same_day_counts > 5]  # More than 5 transactions same day
    
    print(f"\nFacilities with >5 transactions on same day (potential transaction splitting):")
    print(f"Found {len(multiple_same_day)} facility-date combinations")
    for facility_date in multiple_same_day.head(10).index:
        count = multiple_same_day[facility_date]
        facility = facility_date.split('_')[1]
        date = facility_date.split('_')[0]
        daily_total = df[(df['TRX Date'].dt.date.astype(str) == date) & 
                        (df['Facility'] == facility)]['NET'].sum()
        print(f"  Facility {facility} on {date}: {count} transactions, Total: ${daily_total:.2f}")
    
    return {
        'high_amount_txns': high_amount_txns,
        'round_amounts': large_round,
        'high_variability': high_cv,
        'multiple_same_day': multiple_same_day
    }

def cost_saving_recommendations(df, high_freq, facility_spending):
    """Generate cost-saving recommendations"""
    print("\n=== COST-SAVING RECOMMENDATIONS ===")
    
    # 1. Categories with high spending that could benefit from bulk contracts
    bulk_candidates = high_freq[
        (high_freq['Transactions'] >= 50) & 
        (high_freq['Total_Spent'] >= 1000) &
        (high_freq['Facilities_Using'] >= 3)
    ].sort_values('Total_Spent', ascending=False)
    
    print("\nTop Categories for Master Contract Negotiations:")
    print("(High volume, high spend, multiple facilities)")
    for category in bulk_candidates.head(10).index:
        total = bulk_candidates.loc[category, 'Total_Spent']
        facilities = bulk_candidates.loc[category, 'Facilities_Using']
        transactions = bulk_candidates.loc[category, 'Transactions']
        print(f"  {category}: ${total:,.2f} across {facilities} facilities ({transactions} transactions)")
    
    # 2. Emergency purchase patterns
    print(f"\nTotal Amazon Spending: ${df['NET'].sum():,.2f}")
    print(f"Average transaction size: ${df['NET'].mean():.2f}")
    print(f"Median transaction size: ${df['NET'].median():.2f}")
    
    # 3. Facilities with highest Amazon dependency
    high_amazon_facilities = facility_spending.head(10)
    print(f"\nFacilities with Highest Amazon Spending (potential training targets):")
    for facility in high_amazon_facilities.index:
        total = high_amazon_facilities.loc[facility, 'Total_Spent']
        count = high_amazon_facilities.loc[facility, 'Transaction_Count']
        avg = high_amazon_facilities.loc[facility, 'Avg_Transaction']
        print(f"  Facility {facility}: ${total:,.2f} ({count} transactions, ${avg:.2f} avg)")
    
    # 4. Calculate potential savings
    total_spend = df['NET'].sum()
    estimated_savings_rate = 0.15  # Assume 15% savings with master contracts
    potential_savings = total_spend * estimated_savings_rate
    
    print(f"\nPOTENTIAL COST SAVINGS:")
    print(f"Current Amazon spending: ${total_spend:,.2f}")
    print(f"Estimated savings with master contracts (15%): ${potential_savings:,.2f}")
    
    return bulk_candidates

def generate_summary_report(df):
    """Generate executive summary"""
    print("\n" + "="*60)
    print("EXECUTIVE SUMMARY")
    print("="*60)
    
    total_facilities = df['Facility'].nunique()
    total_transactions = len(df)
    total_spending = df['NET'].sum()
    date_range = f"{df['TRX Date'].min().strftime('%Y-%m-%d')} to {df['TRX Date'].max().strftime('%Y-%m-%d')}"
    
    print(f"Analysis Period: {date_range}")
    print(f"Total Facilities: {total_facilities}")
    print(f"Total Transactions: {total_transactions:,}")
    print(f"Total Amazon Spending: ${total_spending:,.2f}")
    print(f"Average per Facility: ${total_spending/total_facilities:,.2f}")
    print(f"Average Transaction: ${total_spending/total_transactions:.2f}")
    
    # Key categories
    top_categories = df.groupby('Account Description')['NET'].sum().sort_values(ascending=False).head(5)
    print(f"\nTop 5 Spending Categories:")
    for category, amount in top_categories.items():
        pct = (amount/total_spending)*100
        print(f"  {category}: ${amount:,.2f} ({pct:.1f}%)")

def main():
    """Main analysis function"""
    file_path = "/Users/nikolashulewsky/Downloads/Amazon 2025.xlsx - 2025 Data (1).csv"
    
    print("Loading transaction data...")
    df = load_and_clean_data(file_path)
    
    print(f"Loaded {len(df):,} transactions")
    
    # Run analyses
    facility_spending, category_spending = analyze_spending_patterns(df)
    high_freq = identify_high_frequency_items(df)
    fraud_indicators = detect_fraud_indicators(df)
    bulk_candidates = cost_saving_recommendations(df, high_freq, facility_spending)
    
    generate_summary_report(df)
    
    print(f"\nAnalysis complete. Review the results above for cost-saving opportunities and fraud indicators.")

if __name__ == "__main__":
    main()