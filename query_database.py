#!/usr/bin/env python3
"""
Database Query Script
Shows all tables created and counts keywords in the database
"""

import sys
import os

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

try:
    from sqlalchemy import create_engine, text, inspect
    from sqlalchemy.orm import Session
    from models.database import DATABASE_URL
    from models.legislation import Keyword
    print("✓ Imports successful")
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)

def connect_to_database():
    """Connect to the database with fallback to SQLite"""
    try:
        if DATABASE_URL.startswith('postgresql'):
            engine = create_engine(DATABASE_URL)
            # Test the connection
            with engine.connect():
                pass
            db_type = 'PostgreSQL'
        else:
            raise Exception("Using SQLite fallback")
    except:
        # Fallback to SQLite
        engine = create_engine("sqlite:///./snflegtracker.db")
        db_type = 'SQLite'

    return engine, db_type

def show_all_tables():
    """Show all tables in the database"""
    print("📋 DATABASE STRUCTURE")
    print("=" * 50)

    engine, db_type = connect_to_database()
    print(f"📡 Connected to: {db_type}")
    print(f"📍 Database location: {engine.url}")

    try:
        # Get table information using SQLAlchemy inspector
        inspector = inspect(engine)
        table_names = inspector.get_table_names()

        print(f"\n🗃️  TABLES CREATED: {len(table_names)}")
        print("-" * 30)

        for i, table_name in enumerate(sorted(table_names), 1):
            # Get column information
            columns = inspector.get_columns(table_name)
            indexes = inspector.get_indexes(table_name)
            foreign_keys = inspector.get_foreign_keys(table_name)

            print(f"{i:2}. 📊 {table_name}")
            print(f"    • Columns: {len(columns)}")
            print(f"    • Indexes: {len(indexes)}")
            print(f"    • Foreign Keys: {len(foreign_keys)}")

            # Show column details
            print("    • Column Details:")
            for col in columns[:5]:  # Show first 5 columns
                col_type = str(col['type'])
                nullable = "NULL" if col['nullable'] else "NOT NULL"
                primary_key = " (PK)" if col.get('primary_key', False) else ""
                print(f"      - {col['name']}: {col_type} {nullable}{primary_key}")

            if len(columns) > 5:
                print(f"      ... and {len(columns) - 5} more columns")

            print()

        return table_names, engine

    except Exception as e:
        print(f"❌ Error querying tables: {e}")
        return [], engine

def count_table_records(engine, table_names):
    """Count records in each table"""
    print("📈 RECORD COUNTS")
    print("=" * 30)

    try:
        with Session(engine) as session:
            total_records = 0

            for table_name in sorted(table_names):
                try:
                    # Count records in each table
                    if 'sqlite' in str(engine.url):
                        result = session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                    else:
                        result = session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))

                    count = result.scalar()
                    total_records += count

                    # Add emoji based on table type
                    if 'user' in table_name:
                        emoji = "👥"
                    elif 'bill' in table_name:
                        emoji = "📄"
                    elif 'keyword' in table_name:
                        emoji = "🏷️"
                    elif 'alert' in table_name:
                        emoji = "🔔"
                    elif 'impact' in table_name:
                        emoji = "📊"
                    else:
                        emoji = "📋"

                    print(f"{emoji} {table_name:20} : {count:4} records")

                except Exception as e:
                    print(f"❌ {table_name:20} : Error - {e}")

            print("-" * 30)
            print(f"📊 TOTAL RECORDS     : {total_records:4}")

    except Exception as e:
        print(f"❌ Error counting records: {e}")

def analyze_keywords():
    """Detailed analysis of keywords table"""
    print("\n🏷️ KEYWORDS ANALYSIS")
    print("=" * 40)

    engine, _ = connect_to_database()

    try:
        with Session(engine) as session:
            # Total keyword count
            total_keywords = session.query(Keyword).count()
            active_keywords = session.query(Keyword).filter(Keyword.is_active == True).count()

            print(f"📊 Total Keywords: {total_keywords}")
            print(f"✅ Active Keywords: {active_keywords}")
            print(f"❌ Inactive Keywords: {total_keywords - active_keywords}")

            # Keywords by category
            from sqlalchemy import func
            category_stats = session.query(
                Keyword.category,
                func.count(Keyword.id).label('count'),
                func.avg(Keyword.importance_weight).label('avg_weight'),
                func.min(Keyword.importance_weight).label('min_weight'),
                func.max(Keyword.importance_weight).label('max_weight')
            ).group_by(Keyword.category).order_by(func.count(Keyword.id).desc()).all()

            print(f"\n📋 Keywords by Category:")
            print("-" * 60)
            print(f"{'Category':<20} {'Count':<6} {'Avg Weight':<12} {'Range':<10}")
            print("-" * 60)

            for category, count, avg_weight, min_weight, max_weight in category_stats:
                avg_str = f"{avg_weight:.1f}" if avg_weight else "N/A"
                range_str = f"{min_weight:.1f}-{max_weight:.1f}" if min_weight and max_weight else "N/A"
                print(f"{category:<20} {count:<6} {avg_str:<12} {range_str:<10}")

            # High importance keywords
            high_importance = session.query(Keyword).filter(
                Keyword.importance_weight >= 1.9
            ).order_by(Keyword.importance_weight.desc()).all()

            print(f"\n⭐ High-Importance Keywords (≥1.9):")
            print("-" * 50)
            for kw in high_importance:
                synonyms_count = 0
                if kw.synonyms:
                    try:
                        import json
                        synonyms = json.loads(kw.synonyms)
                        synonyms_count = len(synonyms)
                    except:
                        pass

                print(f"  • {kw.term:<25} (weight: {kw.importance_weight}, synonyms: {synonyms_count})")

            # Recent keywords (if timestamp available)
            print(f"\n🆕 All Keywords by Category:")
            print("-" * 40)

            all_keywords = session.query(Keyword).order_by(
                Keyword.category,
                Keyword.importance_weight.desc()
            ).all()

            current_category = None
            for kw in all_keywords:
                if kw.category != current_category:
                    current_category = kw.category
                    print(f"\n🏷️  {current_category}:")

                synonyms_count = 0
                if kw.synonyms:
                    try:
                        import json
                        synonyms = json.loads(kw.synonyms)
                        synonyms_count = len(synonyms)
                    except:
                        pass

                status = "✅" if kw.is_active else "❌"
                print(f"    {status} {kw.term} (weight: {kw.importance_weight}, synonyms: {synonyms_count})")

    except Exception as e:
        print(f"❌ Error analyzing keywords: {e}")

def show_database_info():
    """Show general database information"""
    print("\n💾 DATABASE INFO")
    print("=" * 25)

    engine, db_type = connect_to_database()

    # Check if database file exists (for SQLite)
    if 'sqlite' in str(engine.url):
        db_file = str(engine.url).replace('sqlite:///', '')
        if os.path.exists(db_file):
            file_size = os.path.getsize(db_file)
            print(f"📁 Database file: {db_file}")
            print(f"💽 File size: {file_size:,} bytes ({file_size/1024:.1f} KB)")
        else:
            print(f"❌ Database file not found: {db_file}")
    else:
        print(f"🐘 PostgreSQL database")
        print(f"🔗 Connection: {engine.url}")

    print(f"🔧 SQLAlchemy version: {__import__('sqlalchemy').__version__}")

def main():
    """Main function"""
    print("🔍 SNFLegTracker Database Query")
    print("=" * 50)

    # Show all tables
    table_names, engine = show_all_tables()

    if not table_names:
        print("❌ No tables found or database connection failed")
        return 1

    # Count records in each table
    count_table_records(engine, table_names)

    # Detailed keyword analysis
    analyze_keywords()

    # Database info
    show_database_info()

    print(f"\n✅ Database query completed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main())