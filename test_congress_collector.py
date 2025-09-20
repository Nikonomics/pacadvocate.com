#!/usr/bin/env python3
"""
Test script for Congress.gov bill collector
Tests the API connection and searches for skilled nursing facility bills
"""

import os
import sys
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from services.collectors.congress_api_client import CongressAPIClient
from services.collectors.bill_collector import BillCollector

def test_api_connection():
    """Test the basic API connection"""
    print("🧪 TESTING CONGRESS.GOV API CONNECTION")
    print("=" * 50)

    # Check for API key
    api_key = os.getenv('CONGRESS_API_KEY')
    if not api_key:
        print("❌ No API key found!")
        print("   Set CONGRESS_API_KEY environment variable")
        print("   Sign up at: https://api.congress.gov/sign-up/")
        print("\n   For testing without API key, we'll use demo mode")
        return False

    # Test connection
    client = CongressAPIClient(api_key)
    if client.test_connection():
        print("✅ API connection successful!")

        # Show rate limit status
        status = client.get_rate_limit_status()
        print(f"📊 Rate limit: {status['requests_in_last_hour']}/5000 used")
        return True
    else:
        print("❌ API connection failed!")
        return False

def test_keyword_search():
    """Test searching for bills with specific keywords"""
    print("\n🔍 TESTING KEYWORD SEARCH")
    print("=" * 50)

    try:
        client = CongressAPIClient()

        # Test keywords from our database
        test_keywords = [
            "skilled nursing facility",
            "Medicare",
            "nursing home",
            "PDPM"
        ]

        for keyword in test_keywords:
            print(f"\n📋 Searching for: '{keyword}'")

            # Search current Congress (119th)
            results = client.search_bills(
                congress=119,
                query=keyword,
                limit=5
            )

            if results and 'bills' in results:
                bills = results['bills']
                print(f"   Found: {len(bills)} bills")

                for i, bill in enumerate(bills[:3], 1):
                    title = bill.get('title', 'No title')[:80] + "..." if len(bill.get('title', '')) > 80 else bill.get('title', 'No title')
                    bill_num = f"{bill.get('type', 'UNK').upper()}-{bill.get('number', 'N/A')}"
                    print(f"   {i}. {bill_num}: {title}")

            else:
                print("   No results found")

    except Exception as e:
        print(f"❌ Keyword search failed: {e}")

def test_bill_collector():
    """Test the full bill collector functionality"""
    print("\n🏥 TESTING SNF BILL COLLECTOR")
    print("=" * 50)

    try:
        with BillCollector() as collector:
            # Test getting search keywords from database
            print("📋 Getting search keywords from database...")
            keywords = collector.get_search_keywords()
            print(f"   Found {len(keywords)} keywords: {keywords[:5]}...")

            # Test collection stats
            print("\n📊 Current database stats:")
            stats = collector.get_collection_stats()
            for key, value in stats.items():
                print(f"   {key}: {value}")

            # Test API connection through collector
            print(f"\n🔌 Testing API connection...")
            if collector.api_client.test_connection():
                print("   ✅ Ready for bill collection")

                # Ask user if they want to run actual collection
                response = input("\n❓ Run actual bill collection? (y/N): ").strip().lower()
                if response == 'y':
                    print("\n🚀 Running SNF bill collection...")
                    results = collector.collect_snf_bills(congress=119, year=2024)
                    print(f"📊 Collection Results:")
                    print(json.dumps(results, indent=2))
                else:
                    print("   Skipping actual collection (demo mode)")
            else:
                print("   ❌ API connection failed")

    except Exception as e:
        print(f"❌ Bill collector test failed: {e}")

def demo_without_api():
    """Demo the system without actual API calls"""
    print("\n🎭 DEMO MODE (No API Key)")
    print("=" * 50)

    print("📋 This is what the system would do with an API key:")
    print("   1. Search Congress.gov for bills containing SNF keywords")
    print("   2. Rate-limit requests (5000/hour max)")
    print("   3. Parse bill data and store in database")
    print("   4. Run keyword matching on bill text")
    print("   5. Generate alerts for high-confidence matches")
    print("   6. Schedule automated collections")

    print(f"\n🏷️  Would search for these keywords:")
    keywords = [
        "skilled nursing facility", "SNF", "Medicare Part A",
        "nursing home", "PDPM", "Five-Star Quality Rating",
        "staffing ratios", "long-term care"
    ]
    for i, kw in enumerate(keywords, 1):
        print(f"   {i:2}. {kw}")

    print(f"\n📊 Expected workflow:")
    print(f"   • Search 119th Congress (2025-2027)")
    print(f"   • Filter by 2024-2025 date range")
    print(f"   • Process ~50-200 bills per keyword")
    print(f"   • Store unique bills in database")
    print(f"   • Automatically match against all {len(keywords)} SNF keywords")
    print(f"   • Generate impact analysis for high-priority bills")

def main():
    """Main test function"""
    print("🏛️  SNFLegTracker Congress.gov API Tester")
    print("=" * 60)

    # Test 1: API Connection
    api_connected = test_api_connection()

    if api_connected:
        # Test 2: Keyword Search
        test_keyword_search()

        # Test 3: Full Collector
        test_bill_collector()

    else:
        # Demo mode
        demo_without_api()

    print(f"\n✅ Testing completed!")
    print(f"\n🚀 To start collecting bills:")
    print(f"   1. Get API key: https://api.congress.gov/sign-up/")
    print(f"   2. Set environment: export CONGRESS_API_KEY='your_key'")
    print(f"   3. Run collector: python services/collectors/bill_collector.py --snf-only")
    print(f"   4. Start scheduler: python services/collectors/scheduler.py --run")

if __name__ == "__main__":
    main()