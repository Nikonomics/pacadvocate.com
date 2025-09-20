#!/usr/bin/env python3
"""
LegiScan Integration Demo Test
Demonstrates the LegiScan system functionality with mock data
"""

import os
import sys
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from services.collectors.legiscan_collector import LegiScanCollector
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from models.legislation import Bill

def create_mock_legiscan_data():
    """Create mock LegiScan API responses for testing"""
    return [
        {
            'bill_id': 2024001,
            'bill_number': 'H.B. 123',
            'title': 'Medicaid Long-Term Care Services and Skilled Nursing Facility Quality Standards',
            'description': 'A bill to establish quality standards for skilled nursing facilities participating in the Medicaid program and to enhance long-term care services.',
            'status_desc': 'Introduced',
            'introduced': '2024-01-15',
            'last_action_date': '2024-02-01',
            'session_id': 2024,
            'url': 'https://legiscan.com/ID/bill/HB123/2024',
            'state_link': 'https://legislature.idaho.gov/bill/H0123',
            'sponsors': [
                {'name': 'Rep. Jane Smith', 'people_id': 12345}
            ],
            'progress': [
                {'event': 'Introduced in House', 'date': '2024-01-15'},
                {'event': 'Referred to House Health and Welfare Committee', 'date': '2024-01-16'},
                {'event': 'Committee hearing scheduled', 'date': '2024-02-01'}
            ],
            'search_term': 'Medicaid',
            'search_timestamp': datetime.utcnow().isoformat()
        },
        {
            'bill_id': 2024002,
            'bill_number': 'S.B. 456',
            'title': 'Nursing Home Staffing Requirements and Patient Safety Act',
            'description': 'A bill to establish minimum staffing ratios for nursing homes and skilled nursing facilities to ensure patient safety and quality care.',
            'status_desc': 'Passed House, In Senate',
            'introduced': '2024-01-20',
            'last_action_date': '2024-03-15',
            'session_id': 2024,
            'url': 'https://legiscan.com/ID/bill/SB456/2024',
            'state_link': 'https://legislature.idaho.gov/bill/S0456',
            'sponsors': [
                {'name': 'Sen. John Davis', 'people_id': 67890}
            ],
            'progress': [
                {'event': 'Introduced in Senate', 'date': '2024-01-20'},
                {'event': 'Referred to Senate Health and Welfare Committee', 'date': '2024-01-21'},
                {'event': 'Committee approved', 'date': '2024-02-15'},
                {'event': 'Passed Senate', 'date': '2024-03-01'},
                {'event': 'Sent to House', 'date': '2024-03-15'}
            ],
            'search_term': 'staffing',
            'search_timestamp': datetime.utcnow().isoformat()
        },
        {
            'bill_id': 2024003,
            'bill_number': 'H.B. 789',
            'title': 'Assisted Living Facility Licensing and Regulation Updates',
            'description': 'A bill to update licensing requirements for assisted living facilities and enhance regulatory oversight.',
            'status_desc': 'Signed by Governor',
            'introduced': '2024-02-01',
            'last_action_date': '2024-04-10',
            'session_id': 2024,
            'url': 'https://legiscan.com/ID/bill/HB789/2024',
            'state_link': 'https://legislature.idaho.gov/bill/H0789',
            'sponsors': [
                {'name': 'Rep. Mary Johnson', 'people_id': 13579}
            ],
            'progress': [
                {'event': 'Introduced in House', 'date': '2024-02-01'},
                {'event': 'Committee approved', 'date': '2024-02-20'},
                {'event': 'Passed House', 'date': '2024-03-05'},
                {'event': 'Passed Senate', 'date': '2024-03-25'},
                {'event': 'Signed by Governor', 'date': '2024-04-10'}
            ],
            'search_term': 'assisted living',
            'search_timestamp': datetime.utcnow().isoformat()
        }
    ]

def demo_legiscan_system():
    """Demonstrate LegiScan system functionality with mock data"""
    print("🧪 LegiScan Integration Demo")
    print("=" * 60)

    # Create collector instance
    print("\n1. Initializing LegiScan Collector...")
    try:
        collector = LegiScanCollector()
        print("✅ LegiScan Collector initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize collector: {e}")
        return

    # Show state configuration
    print("\n2. Multi-State Configuration:")
    print(f"   Supported States: {', '.join(collector.STATE_CONFIG.keys())}")
    enabled_states = [state for state, config in collector.STATE_CONFIG.items() if config.get('enabled')]
    print(f"   Enabled States: {', '.join(enabled_states)}")

    # Test API client initialization
    print("\n3. API Client Features:")
    print(f"   Rate Limiting: {collector.client.rate_limiter.daily_limit} requests/day")
    print(f"   Base URL: {collector.client.base_url}")
    print(f"   State ID Mapping: ID = {collector.client.STATE_IDS.get('ID', 'Unknown')}")

    # Demonstrate data mapping
    print("\n4. Data Mapping Demo:")
    mock_bills = create_mock_legiscan_data()

    mapped_bills = []
    for mock_bill in mock_bills:
        print(f"\n   Processing: {mock_bill['bill_number']}")
        mapped_bill = collector.map_legiscan_to_bill(mock_bill, 'ID')

        if mapped_bill:
            mapped_bills.append(mapped_bill)
            print(f"   ✅ Mapped to Bills table format")
            print(f"      Title: {mapped_bill.get('title', '')[:60]}...")
            print(f"      Status: {mapped_bill.get('status')}")
            print(f"      Source: {mapped_bill.get('source')}")
            print(f"      State: {mapped_bill.get('state_or_federal')}")
            print(f"      Sponsor: {mapped_bill.get('sponsor')}")
        else:
            print(f"   ❌ Failed to map bill data")

    # Simulate database storage
    print("\n5. Database Storage Demo:")
    try:
        with Session(collector.engine) as session:
            stored_count = 0

            for mapped_bill in mapped_bills:
                # Create a mock bill object for demo (don't actually store)
                print(f"   • {mapped_bill['bill_number']}: Ready for database storage")
                print(f"     Keywords to match: {len(collector.get_healthcare_keywords())} terms")
                stored_count += 1

            print(f"   ✅ {stored_count} bills ready for storage with source='legiscan'")

    except Exception as e:
        print(f"   ❌ Database demo failed: {e}")

    # Show keyword matching capability
    print("\n6. Keyword Matching Demo:")
    healthcare_keywords = collector.get_healthcare_keywords()
    print(f"   Available keywords: {len(healthcare_keywords)}")

    for mapped_bill in mapped_bills[:2]:  # Test first 2 bills
        title = mapped_bill.get('title', '').lower()
        summary = mapped_bill.get('summary', '').lower()
        search_text = f"{title} {summary}"

        matches = []
        for keyword in healthcare_keywords[:10]:  # Test subset
            if keyword.lower() in search_text:
                matches.append(keyword)

        print(f"   • {mapped_bill['bill_number']}: {len(matches)} keyword matches")
        if matches:
            print(f"     Matched terms: {', '.join(matches[:3])}{'...' if len(matches) > 3 else ''}")

    # Show rate limiting
    print("\n7. Rate Limiting Demo:")
    rate_status = collector.client.get_rate_limit_status()
    print(f"   Daily limit: {rate_status['daily_limit']} requests")
    print(f"   Current usage: {rate_status['requests_in_last_24_hours']} requests today")
    print(f"   Remaining: {rate_status['requests_remaining_today']} requests")

    # Show collection statistics
    print("\n8. Collection Statistics Demo:")
    try:
        stats = collector.get_collection_stats('ID')
        print(f"   Total LegiScan bills in database: {stats.get('total_legiscan_bills', 0)}")
        print(f"   Recent bills (30 days): {stats.get('recent_bills_30_days', 0)}")
        print(f"   Bills with keyword matches: {stats.get('bills_with_keyword_matches', 0)}")

        if stats.get('enabled_states'):
            print(f"   Enabled states: {', '.join(stats['enabled_states'])}")
    except Exception as e:
        print(f"   ❌ Stats demo failed: {e}")

    # Show scheduler configuration
    print("\n9. Scheduled Collection Demo:")
    try:
        from services.collectors.legiscan_scheduler import LegiScanScheduler
        scheduler = LegiScanScheduler()

        print(f"   Monitored states: {', '.join(scheduler.monitored_states)}")
        print(f"   Daily collection: ✅ Configured")
        print(f"   Weekly comprehensive: ✅ Configured")
        print(f"   Monthly multi-state scan: ✅ Configured")

    except Exception as e:
        print(f"   ❌ Scheduler demo failed: {e}")

    print("\n" + "=" * 60)
    print("✅ LegiScan Integration Demo Complete!")
    print("\nNext Steps:")
    print("1. Get LegiScan API key from https://legiscan.com/legiscan")
    print("2. Set LEGISCAN_API_KEY environment variable")
    print("3. Run: python3 services/collectors/legiscan_collector.py --test")
    print("4. Start collection: python3 services/collectors/legiscan_collector.py --state ID")

def show_sample_bill_data():
    """Show sample of how LegiScan data maps to our system"""
    print("\n📋 Sample LegiScan Bill Data Mapping")
    print("=" * 60)

    mock_bill = create_mock_legiscan_data()[0]

    print("LegiScan API Response:")
    print(json.dumps({k: v for k, v in mock_bill.items() if k not in ['progress']}, indent=2))

    print("\nMapped to Bills Table:")
    collector = LegiScanCollector()
    mapped = collector.map_legiscan_to_bill(mock_bill, 'ID')

    display_fields = {
        'bill_number': mapped.get('bill_number'),
        'title': mapped.get('title'),
        'source': mapped.get('source'),
        'state_or_federal': mapped.get('state_or_federal'),
        'status': mapped.get('status'),
        'sponsor': mapped.get('sponsor'),
        'chamber': mapped.get('chamber'),
        'introduced_date': mapped.get('introduced_date').strftime('%Y-%m-%d') if mapped.get('introduced_date') else None
    }

    print(json.dumps(display_fields, indent=2, default=str))

if __name__ == "__main__":
    demo_legiscan_system()
    show_sample_bill_data()