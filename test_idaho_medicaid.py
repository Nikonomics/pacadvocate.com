#!/usr/bin/env python3
"""
Quick test of Idaho Medicaid bill collection
"""

import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from services.collectors.legiscan_collector import LegiScanCollector

def test_idaho_medicaid_collection():
    """Test collecting Idaho Medicaid bills from 2025"""
    print("🧪 Testing Idaho Medicaid Bill Collection (2025)")
    print("=" * 60)

    try:
        # Create collector
        collector = LegiScanCollector()
        print("✅ LegiScan Collector initialized")

        # Test API connection first
        if not collector.test_connection():
            print("❌ API connection failed")
            return

        print("✅ API connection successful")

        # Override state config to just search for Medicaid
        original_config = collector.STATE_CONFIG['ID']['priority_keywords']
        collector.STATE_CONFIG['ID']['priority_keywords'] = ['Medicaid']

        print("\n🔍 Starting Idaho Medicaid collection...")
        print(f"   Search terms: {collector.STATE_CONFIG['ID']['priority_keywords']}")
        print(f"   Year: 2025")
        print(f"   Limit: 5 bills")

        # Collect bills
        start_time = datetime.now()
        bills = collector.collect_state_bills(
            state='ID',
            year=2025,
            limit=5,
            include_details=False
        )
        end_time = datetime.now()

        duration = (end_time - start_time).total_seconds()

        print(f"\n📊 Collection Results:")
        print(f"   Duration: {duration:.1f} seconds")
        print(f"   Bills found: {len(bills)}")

        if bills:
            print(f"\n📋 Sample Bills:")
            for i, bill in enumerate(bills[:3], 1):
                print(f"   {i}. {bill.get('bill_number', 'Unknown')}")
                print(f"      Title: {bill.get('title', 'No title')[:70]}...")
                print(f"      Status: {bill.get('status', 'Unknown')}")
                print(f"      Sponsor: {bill.get('sponsor', 'Unknown')}")
                print()

            # Show collection stats
            print("📈 Collection Statistics:")
            stats = collector.get_collection_stats('ID')
            print(f"   Total LegiScan bills in DB: {stats.get('total_legiscan_bills', 0)}")
            print(f"   Bills with keyword matches: {stats.get('bills_with_keyword_matches', 0)}")
        else:
            print("   No bills found for search criteria")

        # Restore original config
        collector.STATE_CONFIG['ID']['priority_keywords'] = original_config

        print("\n✅ Test completed successfully!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_idaho_medicaid_collection()