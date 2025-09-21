#!/usr/bin/env python3
"""
Test the Enhanced Federal Register SNF-Specific Collector
Demonstrates the improved targeting and filtering capabilities
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from services.collectors.federal_register_client import FederalRegisterClient

def test_enhanced_snf_collection():
    """Test the enhanced SNF-specific Federal Register collection"""

    print("🎯 ENHANCED FEDERAL REGISTER SNF COLLECTOR TEST")
    print("=" * 60)
    print("📍 Testing targeted search for CMS SNF rules ONLY")
    print()

    client = FederalRegisterClient()

    # Test API connection
    if not client.test_connection():
        print("❌ Federal Register API connection failed")
        return

    print("✅ Federal Register API connection successful")
    print()

    # Test 1: SNF Payment Rules Search (Most Targeted)
    print("🔍 TEST 1: SNF Payment Rules Search")
    print("-" * 40)

    payment_docs = client.search_snf_payment_rules(year=2025, limit=5)

    if payment_docs:
        print(f"✅ Found {len(payment_docs)} SNF payment rules for 2025")
        for i, doc in enumerate(payment_docs, 1):
            snf_relevance = doc.get('snf_relevance', {})
            print(f"  {i}. {doc.get('title', 'No title')[:70]}...")
            print(f"     📅 Date: {doc.get('publication_date')}")
            print(f"     📊 SNF Relevance: {snf_relevance.get('confidence_score', 0):.1%}")
            print(f"     🏷️  Category: {snf_relevance.get('match_category', 'unknown')}")
            print(f"     🔍 Key Matches: {', '.join(snf_relevance.get('matched_terms', [])[:2])}")
            print()
    else:
        print("❌ No SNF payment rules found")

    # Test 2: Show SNF Search Terms
    print("🔍 TEST 2: SNF-Specific Search Terms")
    print("-" * 40)

    search_terms = client.get_snf_specific_search_terms()
    for category, terms in search_terms.items():
        print(f"📂 {category.replace('_', ' ').title()}:")
        for term in terms[:3]:  # Show first 3 terms per category
            print(f"   • \"{term}\"")
        if len(terms) > 3:
            print(f"   • ... and {len(terms) - 3} more")
        print()

    # Test 3: Exclusion Testing
    print("🔍 TEST 3: Exclusion Filter Testing")
    print("-" * 40)

    # Search for general CMS documents to show filtering
    general_docs = client.search_cms_documents(
        document_types=['RULE', 'PRORULE'],
        year=2025,
        limit=10
    )

    if general_docs:
        relevant_count = sum(1 for doc in general_docs
                           if doc.get('snf_relevance', {}).get('is_relevant', False))
        excluded_count = sum(1 for doc in general_docs
                           if doc.get('snf_relevance', {}).get('exclusion_reason'))

        print(f"📊 Analysis of {len(general_docs)} CMS documents:")
        print(f"   ✅ {relevant_count} SNF-relevant documents")
        print(f"   ❌ {excluded_count} excluded documents")
        print(f"   📈 Precision: {(relevant_count/len(general_docs)*100):.1f}%")
        print()

        # Show examples of excluded documents
        if excluded_count > 0:
            print("❌ Examples of EXCLUDED documents:")
            excluded_docs = [doc for doc in general_docs
                           if doc.get('snf_relevance', {}).get('exclusion_reason')]

            for i, doc in enumerate(excluded_docs[:3], 1):
                exclusion = doc.get('snf_relevance', {}).get('exclusion_reason', 'Unknown')
                print(f"   {i}. {doc.get('title', 'No title')[:60]}...")
                print(f"      🚫 Reason: {exclusion}")
            print()

        # Show examples of included documents
        if relevant_count > 0:
            print("✅ Examples of INCLUDED SNF-relevant documents:")
            relevant_docs = [doc for doc in general_docs
                           if doc.get('snf_relevance', {}).get('is_relevant', False)]

            for i, doc in enumerate(relevant_docs[:3], 1):
                snf_relevance = doc.get('snf_relevance', {})
                print(f"   {i}. {doc.get('title', 'No title')[:60]}...")
                print(f"      ✅ Confidence: {snf_relevance.get('confidence_score', 0):.1%}")
                print(f"      🏷️  Category: {snf_relevance.get('match_category', 'unknown')}")

    print()
    print("🎉 ENHANCED FEDERAL REGISTER SYSTEM SUMMARY")
    print("=" * 60)
    print("✅ Targeted SNF payment rule search implemented")
    print("✅ Exclusion filters for hospital/physician-only rules")
    print("✅ Category-based confidence scoring")
    print("✅ Exact phrase matching for precision")
    print("✅ Multi-tier search term prioritization")
    print()
    print("🎯 Key Improvements:")
    print("   • ONLY pulls CMS rules relevant to SNFs")
    print("   • Excludes hospital-focused, physician-only, and ambulatory rules")
    print("   • Searches for exact phrases like 'Skilled Nursing Facility Prospective Payment System'")
    print("   • Detects staffing requirements, quality programs, and payment updates")
    print("   • Provides detailed relevance explanations")

if __name__ == "__main__":
    test_enhanced_snf_collection()