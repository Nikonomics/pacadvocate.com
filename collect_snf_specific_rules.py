#!/usr/bin/env python3
"""
Collect SNF-Specific Federal Register Rules
Run targeted searches for high-priority SNF regulations
"""

import sqlite3
import os
import asyncio
import sys
from datetime import datetime

# Add the project root to the path so we can import our modules
sys.path.append('/Users/nikolashulewsky')

from services.collectors.federal_register_client import FederalRegisterClient

def collect_snf_specific_rules():
    """Collect Federal Register rules for specific SNF topics"""

    # Initialize client
    client = FederalRegisterClient()

    # Connect to database
    db_path = 'snflegtracker.db'
    if not os.path.exists(db_path):
        print(f"❌ Database file not found: {db_path}")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        print("🏛️  COLLECTING SNF-SPECIFIC FEDERAL REGISTER RULES")
        print("=" * 60)
        print("🎯 Running targeted searches for high-priority SNF regulations")
        print()

        # Get count before collection
        cursor.execute("SELECT COUNT(*) FROM bills WHERE is_active = 1")
        initial_active = cursor.fetchone()[0]
        print(f"📊 Active bills before collection: {initial_active}")
        print()

        all_collected_rules = []
        search_categories = []

        # 1. SNF Quality Reporting Program
        print("🔍 SEARCH 1: SNF Quality Reporting Program")
        print("-" * 45)

        search_phrase = "SNF Quality Reporting Program"
        print(f"🔎 Searching Federal Register for: '{search_phrase}'")

        try:
            qrp_response = client.search_documents(
                agencies=['centers-for-medicare-medicaid-services'],
                terms=search_phrase,
                document_types=['RULE', 'PRORULE'],
                per_page=10
            )
            if qrp_response and 'results' in qrp_response:
                qrp_results = qrp_response['results']
                print(f"✅ Found {len(qrp_results)} QRP documents")
                for doc in qrp_results:
                    print(f"   📋 {doc.get('title', 'No title')[:70]}...")
                    print(f"       📅 Published: {doc.get('publication_date', 'Unknown')}")
                all_collected_rules.extend(qrp_results)
                search_categories.append(("SNF Quality Reporting Program", len(qrp_results)))
            else:
                print("❌ No QRP documents found")
        except Exception as e:
            print(f"❌ QRP search failed: {e}")

        print()

        # 2. SNF Value-Based Purchasing
        print("🔍 SEARCH 2: SNF Value-Based Purchasing")
        print("-" * 40)

        search_phrase = "SNF Value-Based Purchasing"
        print(f"🔎 Searching Federal Register for: '{search_phrase}'")

        try:
            vbp_response = client.search_documents(
                agencies=['centers-for-medicare-medicaid-services'],
                terms=search_phrase,
                document_types=['RULE', 'PRORULE'],
                per_page=10
            )
            if vbp_response and 'results' in vbp_response:
                vbp_results = vbp_response['results']
                print(f"✅ Found {len(vbp_results)} VBP documents")
                for doc in vbp_results:
                    print(f"   📋 {doc.get('title', 'No title')[:70]}...")
                    print(f"       📅 Published: {doc.get('publication_date', 'Unknown')}")
                all_collected_rules.extend(vbp_results)
                search_categories.append(("SNF Value-Based Purchasing", len(vbp_results)))
            else:
                print("❌ No VBP documents found")
        except Exception as e:
            print(f"❌ VBP search failed: {e}")

        print()

        # 3. Minimum staffing requirements with nursing
        print("🔍 SEARCH 3: Minimum staffing requirements + nursing")
        print("-" * 50)

        search_phrase = "minimum staffing requirements nursing"
        print(f"🔎 Searching Federal Register for: '{search_phrase}'")

        try:
            staffing_response = client.search_documents(
                agencies=['centers-for-medicare-medicaid-services'],
                terms=search_phrase,
                document_types=['RULE', 'PRORULE'],
                per_page=10
            )
            if staffing_response and 'results' in staffing_response:
                staffing_results = staffing_response['results']
                print(f"✅ Found {len(staffing_results)} staffing documents")
                for doc in staffing_results:
                    print(f"   📋 {doc.get('title', 'No title')[:70]}...")
                    print(f"       📅 Published: {doc.get('publication_date', 'Unknown')}")
                all_collected_rules.extend(staffing_results)
                search_categories.append(("Minimum staffing + nursing", len(staffing_results)))
            else:
                print("❌ No staffing documents found")
        except Exception as e:
            print(f"❌ Staffing search failed: {e}")

        print()

        # Remove duplicates and process for database insertion
        unique_rules = []
        seen_titles = set()

        for rule in all_collected_rules:
            title = rule.get('title', '')
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_rules.append(rule)

        if unique_rules:
            print(f"🔄 PROCESSING: Found {len(unique_rules)} unique documents to process")
            print("-" * 60)

            # Process each document for SNF relevance and database insertion
            newly_added = 0
            for doc in unique_rules:
                try:
                    title = doc.get('title', '')
                    summary = doc.get('abstract', '') or doc.get('summary', '')
                    publication_date = doc.get('publication_date', '')
                    document_number = doc.get('document_number', '')
                    html_url = doc.get('html_url', '')

                    # Check if already exists
                    cursor.execute("SELECT id FROM bills WHERE title = ?", (title,))
                    if cursor.fetchone():
                        print(f"⚠️  Skipping duplicate: {title[:50]}...")
                        continue

                    # Calculate SNF relevance score using the document data
                    doc_data = {'title': title, 'abstract': summary}
                    relevance_info = client.is_snf_relevant(doc_data)
                    relevance_score = relevance_info.get('confidence_score', 0.0) * 100  # Convert to 0-100 scale

                    # Only add if relevant (score > 50)
                    if relevance_score >= 50:
                        # Extract comment period information
                        comment_info = client.extract_comment_periods(doc)

                        # Insert into database
                        cursor.execute("""
                            INSERT INTO bills (
                                title, summary, source, relevance_score, is_active,
                                created_at, updated_at, comment_deadline, comment_url,
                                has_comment_period, comment_period_urgent,
                                payment_impact, operational_area, implementation_timeline,
                                operational_tags
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            title,
                            summary,
                            'federal_register',
                            relevance_score,
                            1,  # is_active
                            datetime.utcnow(),
                            datetime.utcnow(),
                            comment_info.get('deadline'),
                            html_url if html_url else comment_info.get('url'),
                            comment_info.get('has_comment_period', False),
                            comment_info.get('is_urgent', False),
                            'neutral',  # Default payment impact
                            'Quality',  # Default operational area
                            'Soon',     # Default timeline
                            '["federal-register", "snf-specific", "new-collection"]'
                        ))

                        newly_added += 1
                        print(f"✅ Added: {title[:60]}... (Score: {relevance_score:.1f})")
                    else:
                        print(f"❌ Rejected: {title[:50]}... (Score: {relevance_score:.1f} < 50)")

                except Exception as e:
                    print(f"❌ Error processing document: {e}")

            print(f"\n✅ Successfully added {newly_added} new SNF-relevant rules to database")

        else:
            print("❌ No unique documents found to process")

        # Get final count
        cursor.execute("SELECT COUNT(*) FROM bills WHERE is_active = 1")
        final_active = cursor.fetchone()[0]

        # Commit changes
        conn.commit()
        conn.close()

        collected_count = final_active - initial_active

        print()
        print("🎉 FEDERAL REGISTER COLLECTION COMPLETE")
        print("=" * 50)
        print(f"📊 Bills before collection: {initial_active}")
        print(f"📊 Bills after collection: {final_active}")
        print(f"✅ New SNF rules collected: {collected_count}")
        print()

        if collected_count > 0:
            print("🎯 Collection Breakdown by Search Category:")
            for category, count in search_categories:
                print(f"   🏛️  {category}: {count} documents found")

            print()
            print("💡 Benefits of These SNF-Specific Rules:")
            print("   📊 Quality Reporting Program: Track mandatory quality measures")
            print("   💰 Value-Based Purchasing: Monitor payment adjustments")
            print("   👥 Staffing Requirements: Prepare for workforce mandates")
            print("   🎯 All rules directly impact SNF operations and compliance")
        else:
            print("⚠️  No new SNF-specific rules were collected")
            print("💡 This could indicate:")
            print("   • No recent Federal Register activity on these topics")
            print("   • All relevant rules already in database")
            print("   • Search terms may need refinement")

        return True

    except Exception as e:
        print(f"❌ Collection failed: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    collect_snf_specific_rules()