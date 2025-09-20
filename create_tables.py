#!/usr/bin/env python3
"""
Script to create database tables using SQLAlchemy
This script creates all tables without requiring Alembic
"""

import sys
import os

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import SQLAlchemyError
    print("✓ SQLAlchemy imported successfully")
except ImportError as e:
    print(f"✗ SQLAlchemy not available: {e}")
    print("Please install required packages: pip install sqlalchemy psycopg2-binary python-dotenv")
    sys.exit(1)

try:
    from models.database import Base, DATABASE_URL
    from models.legislation import (
        Bill, BillVersion, Keyword, BillKeywordMatch,
        User, Alert, ImpactAnalysis
    )
    print("✓ Models imported successfully")
except ImportError as e:
    print(f"✗ Failed to import models: {e}")
    sys.exit(1)

def create_database_tables():
    """Create all database tables"""
    try:
        print(f"Connecting to database: {DATABASE_URL}")

        # For demonstration purposes, we'll use SQLite if PostgreSQL is not available
        if "postgresql" in DATABASE_URL and ("localhost" in DATABASE_URL or "127.0.0.1" in DATABASE_URL):
            # Try to connect to PostgreSQL first
            try:
                engine = create_engine(DATABASE_URL)
                # Test the connection
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                print("✓ Connected to PostgreSQL database")
            except Exception as e:
                print(f"✗ PostgreSQL not available: {e}")
                print("Falling back to SQLite for demonstration...")
                # Use SQLite as fallback
                sqlite_url = "sqlite:///./snflegtracker.db"
                engine = create_engine(sqlite_url)
                print(f"✓ Using SQLite database: {sqlite_url}")
        else:
            engine = create_engine(DATABASE_URL)
            print("✓ Connected to database")

        # Create all tables
        print("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        print("✓ All tables created successfully!")

        # Verify tables were created
        print("\nVerifying tables...")
        with engine.connect() as conn:
            if "sqlite" in str(engine.url):
                result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
            else:
                result = conn.execute(text("""
                    SELECT tablename FROM pg_catalog.pg_tables
                    WHERE schemaname != 'information_schema'
                    AND schemaname != 'pg_catalog';
                """))

            tables = [row[0] for row in result]

        expected_tables = [
            'users', 'bills', 'bill_versions', 'keywords',
            'bill_keyword_matches', 'alerts', 'impact_analyses'
        ]

        print("Tables found:")
        for table in sorted(tables):
            if table in expected_tables:
                print(f"  ✓ {table}")
            else:
                print(f"  • {table}")

        missing_tables = [t for t in expected_tables if t not in tables]
        if missing_tables:
            print(f"\n✗ Missing tables: {missing_tables}")
            return False

        print(f"\n✓ All {len(expected_tables)} expected tables created successfully!")

        # Test basic operations
        print("\nTesting database operations...")
        test_basic_operations(engine)

        return True

    except SQLAlchemyError as e:
        print(f"✗ Database error: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

def test_basic_operations(engine):
    """Test basic database operations"""
    try:
        with engine.connect() as conn:
            # Test inserting a user
            conn.execute(text("""
                INSERT INTO users (email, full_name, role, is_active, is_verified)
                VALUES ('test@example.com', 'Test User', 'user', true, false)
                ON CONFLICT DO NOTHING;
            """))

            # Test inserting a keyword
            conn.execute(text("""
                INSERT INTO keywords (term, category, importance_weight, is_active)
                VALUES ('skilled nursing facility', 'SNF', 2.0, true)
                ON CONFLICT DO NOTHING;
            """))

            conn.commit()

        print("✓ Basic database operations successful")

    except Exception as e:
        print(f"⚠ Basic operations test failed: {e}")
        # This is non-fatal for table creation

def main():
    """Main function"""
    print("SNFLegTracker Database Setup")
    print("=" * 40)

    success = create_database_tables()

    if success:
        print("\n🎉 Database setup completed successfully!")
        print("\nNext steps:")
        print("1. Run the seed script: python seed_keywords.py")
        print("2. Start the FastAPI application: uvicorn main:app --reload")
        return 0
    else:
        print("\n❌ Database setup failed!")
        print("\nTroubleshooting:")
        print("1. Ensure PostgreSQL is running and accessible")
        print("2. Check database credentials in .env file")
        print("3. Install required packages: pip install -r requirements.txt")
        return 1

if __name__ == "__main__":
    sys.exit(main())