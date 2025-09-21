#!/usr/bin/env python3
"""
Run AI Analysis on All Existing Bills
Updates database with GPT-4 relevance analysis for all bills
"""

import sqlite3
import os
import json
from datetime import datetime
from bill_relevance_analyzer import BillRelevanceAnalyzer
from test_bill_relevance_mock import MockBillRelevanceAnalyzer

class BillAIAnalyzer:
    """Runs AI analysis on all bills in the database"""

    def __init__(self, use_mock=True):
        """Initialize the analyzer"""
        self.db_path = 'snflegtracker.db'
        self.use_mock = use_mock

        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"Database not found: {self.db_path}")

        # Initialize AI analyzer
        if use_mock or not os.getenv('OPENAI_API_KEY'):
            print("🎭 Using mock AI analyzer (no API key required)")
            self.analyzer = MockBillRelevanceAnalyzer()
        else:
            print("🤖 Using real GPT-4 analyzer")
            self.analyzer = BillRelevanceAnalyzer()

    def add_ai_analysis_fields(self):
        """Add AI analysis fields to bills table if they don't exist"""
        print("📋 ADDING AI ANALYSIS FIELDS TO DATABASE")
        print("=" * 45)

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check current table structure
            cursor.execute("PRAGMA table_info(bills)")
            existing_columns = [row[1] for row in cursor.fetchall()]

            fields_to_add = []

            # AI relevance score field
            if 'ai_relevance_score' not in existing_columns:
                fields_to_add.append(('ai_relevance_score', 'INTEGER', 'AI-determined relevance score (0-100)'))

            # AI impact type field
            if 'ai_impact_type' not in existing_columns:
                fields_to_add.append(('ai_impact_type', 'TEXT', 'AI-determined impact type: direct/competitive/financial/workforce'))

            # AI relevant flag
            if 'ai_relevant' not in existing_columns:
                fields_to_add.append(('ai_relevant', 'INTEGER', 'AI-determined relevance flag (1=relevant, 0=not relevant)'))

            # AI analysis explanation
            if 'ai_explanation' not in existing_columns:
                fields_to_add.append(('ai_explanation', 'TEXT', 'AI explanation for relevance determination'))

            # AI analysis timestamp
            if 'ai_analysis_timestamp' not in existing_columns:
                fields_to_add.append(('ai_analysis_timestamp', 'TEXT', 'Timestamp when AI analysis was performed'))

            if not fields_to_add:
                print("✅ All AI analysis fields already exist")
                conn.close()
                return True

            # Add each new field
            for field_name, field_type, description in fields_to_add:
                print(f"➕ Adding field: {field_name} ({field_type})")
                print(f"   📝 Description: {description}")

                cursor.execute(f"""
                    ALTER TABLE bills
                    ADD COLUMN {field_name} {field_type}
                """)

            # Create indexes for AI analysis queries
            print("\n🔍 Creating indexes for AI analysis queries...")
            index_queries = [
                "CREATE INDEX IF NOT EXISTS idx_bills_ai_relevance_score ON bills(ai_relevance_score)",
                "CREATE INDEX IF NOT EXISTS idx_bills_ai_impact_type ON bills(ai_impact_type)",
                "CREATE INDEX IF NOT EXISTS idx_bills_ai_relevant ON bills(ai_relevant)"
            ]

            for query in index_queries:
                cursor.execute(query)

            conn.commit()
            conn.close()

            print(f"\n✅ Successfully added {len(fields_to_add)} AI analysis fields")
            return True

        except Exception as e:
            print(f"❌ Failed to add AI analysis fields: {e}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            return False

    def analyze_all_bills(self):
        """Run AI analysis on all bills in the database"""
        print("\n🤖 RUNNING AI ANALYSIS ON ALL BILLS")
        print("=" * 40)

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get all bills
            cursor.execute("""
                SELECT id, title, summary, operational_area
                FROM bills
                ORDER BY id
            """)

            bills = cursor.fetchall()
            total_bills = len(bills)

            if total_bills == 0:
                print("❌ No bills found in database")
                conn.close()
                return {}

            print(f"📊 Found {total_bills} bills to analyze")
            print()

            # Track results
            results = {
                'total_analyzed': 0,
                'relevant_bills': 0,
                'irrelevant_bills': 0,
                'impact_types': {},
                'analysis_details': []
            }

            # Analyze each bill
            for i, (bill_id, title, summary, operational_area) in enumerate(bills, 1):
                print(f"🔍 Analyzing Bill {bill_id} ({i}/{total_bills}): {title[:50]}...")

                # Prepare content for analysis
                analysis_content = summary or title  # Use summary if available, otherwise title

                # Run AI analysis
                try:
                    ai_result = self.analyzer.analyze_bill_relevance(title, analysis_content)

                    # Update database with AI results
                    timestamp = datetime.now().isoformat()
                    cursor.execute("""
                        UPDATE bills
                        SET ai_relevance_score = ?,
                            ai_impact_type = ?,
                            ai_relevant = ?,
                            ai_explanation = ?,
                            ai_analysis_timestamp = ?
                        WHERE id = ?
                    """, (
                        ai_result['relevance_score'],
                        ai_result['impact_type'],
                        1 if ai_result['relevant'] else 0,
                        ai_result['explanation'],
                        timestamp,
                        bill_id
                    ))

                    # Track results
                    results['total_analyzed'] += 1
                    if ai_result['relevant']:
                        results['relevant_bills'] += 1
                    else:
                        results['irrelevant_bills'] += 1

                    # Track impact types
                    impact_type = ai_result['impact_type']
                    results['impact_types'][impact_type] = results['impact_types'].get(impact_type, 0) + 1

                    # Store details
                    results['analysis_details'].append({
                        'bill_id': bill_id,
                        'title': title,
                        'relevant': ai_result['relevant'],
                        'score': ai_result['relevance_score'],
                        'impact_type': ai_result['impact_type'],
                        'explanation': ai_result['explanation']
                    })

                    # Display result
                    relevance_emoji = "✅" if ai_result['relevant'] else "❌"
                    score_color = "🔴" if ai_result['relevance_score'] >= 70 else "🟡" if ai_result['relevance_score'] >= 40 else "🟢"

                    print(f"   {relevance_emoji} Relevant: {'YES' if ai_result['relevant'] else 'NO'}")
                    print(f"   📊 Impact: {ai_result['impact_type'].title()}")
                    print(f"   {score_color} Score: {ai_result['relevance_score']}/100")

                except Exception as e:
                    print(f"   ❌ Analysis failed: {e}")
                    continue

                print()

            # Commit all changes
            conn.commit()
            conn.close()

            print(f"✅ AI analysis completed for {results['total_analyzed']} bills")
            return results

        except Exception as e:
            print(f"❌ AI analysis failed: {e}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            return {}

    def generate_analysis_report(self, results):
        """Generate a comprehensive analysis report"""
        if not results:
            print("❌ No results to report")
            return

        print("📊 AI ANALYSIS RESULTS SUMMARY")
        print("=" * 35)

        # Overall statistics
        total = results['total_analyzed']
        relevant = results['relevant_bills']
        irrelevant = results['irrelevant_bills']

        print(f"📋 Total Bills Analyzed: {total}")
        print(f"✅ SNF-Relevant Bills: {relevant} ({relevant/total*100:.1f}%)")
        print(f"❌ Not Relevant Bills: {irrelevant} ({irrelevant/total*100:.1f}%)")
        print()

        # Impact type distribution
        print("🎯 IMPACT TYPE DISTRIBUTION:")
        impact_emojis = {
            'direct': '🎯',
            'financial': '💰',
            'competitive': '🏆',
            'workforce': '👥',
            'other': '📋'
        }

        for impact_type, count in sorted(results['impact_types'].items()):
            emoji = impact_emojis.get(impact_type, '📋')
            percentage = count / total * 100
            print(f"   {emoji} {impact_type.title()}: {count} bills ({percentage:.1f}%)")

        print()

        # High-impact bills
        high_impact_bills = [b for b in results['analysis_details'] if b['relevant'] and b['score'] >= 70]
        if high_impact_bills:
            print(f"🔴 HIGH-IMPACT BILLS (Score ≥ 70):")
            for bill in sorted(high_impact_bills, key=lambda x: x['score'], reverse=True):
                print(f"   📋 Bill {bill['bill_id']}: {bill['title'][:50]}...")
                print(f"       📊 {bill['impact_type'].title()} Impact - Score: {bill['score']}/100")
                print(f"       💭 {bill['explanation'][:80]}...")
                print()

        # Save detailed results to file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_filename = f"ai_analysis_report_{timestamp}.json"

        with open(report_filename, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"💾 Detailed results saved to: {report_filename}")

def main():
    """Main function to run AI analysis on all bills"""
    print("🤖 SNF BILL AI RELEVANCE ANALYZER")
    print("=" * 40)

    try:
        # Initialize analyzer
        analyzer = BillAIAnalyzer(use_mock=True)  # Set to False to use real GPT-4

        # Add AI analysis fields to database
        if not analyzer.add_ai_analysis_fields():
            print("❌ Failed to prepare database fields")
            return

        # Run AI analysis on all bills
        results = analyzer.analyze_all_bills()

        if results:
            # Generate comprehensive report
            analyzer.generate_analysis_report(results)
        else:
            print("❌ No analysis results to report")

    except Exception as e:
        print(f"❌ Main process failed: {e}")

if __name__ == "__main__":
    main()