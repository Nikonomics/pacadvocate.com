#!/usr/bin/env python3
"""
Python-based database migration script
This creates tables using SQLAlchemy without requiring external PostgreSQL tools
"""

import sys
import os
import subprocess
import time

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

def install_requirements():
    """Install required packages if not available"""
    print("📦 Checking Python dependencies...")

    required_packages = [
        'sqlalchemy',
        'psycopg2-binary',
        'python-dotenv',
        'pydantic[email]',
        'fastapi'
    ]

    missing_packages = []

    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"  ✓ {package}")
        except ImportError:
            missing_packages.append(package)
            print(f"  ✗ {package}")

    if missing_packages:
        print(f"\n📥 Installing missing packages: {', '.join(missing_packages)}")
        try:
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install'
            ] + missing_packages)
            print("✅ Packages installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install packages: {e}")
            return False

    return True

def run_migration():
    """Run the database migration"""
    print("🏗️  SNFLegTracker Python Migration")
    print("==================================")

    # Install requirements first
    if not install_requirements():
        return False

    try:
        # Now import after installation
        from sqlalchemy import create_engine, text
        from sqlalchemy.exc import SQLAlchemyError

        # Import models
        from models.database import Base
        from models.legislation import (
            Bill, BillVersion, Keyword, BillKeywordMatch,
            User, Alert, ImpactAnalysis
        )

        print("✅ All imports successful")

    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

    # Database URL - try PostgreSQL first, fallback to SQLite
    database_urls = [
        "postgresql://snflegtracker:password@localhost:5432/snflegtracker",
        "sqlite:///./snflegtracker.db"
    ]

    engine = None
    for db_url in database_urls:
        try:
            print(f"📡 Trying connection to: {db_url.split('@')[0]}@...")
            engine = create_engine(db_url)

            # Test connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            print(f"✅ Connected to database: {'PostgreSQL' if 'postgresql' in db_url else 'SQLite'}")
            break

        except Exception as e:
            print(f"⚠️  Connection failed: {e}")
            if db_url == database_urls[-1]:  # Last URL failed
                print("❌ All database connections failed")
                return False
            continue

    try:
        print("📋 Creating database tables...")

        # Create all tables
        Base.metadata.create_all(bind=engine)
        print("✅ Tables created successfully")

        # Verify tables
        print("🔍 Verifying tables...")
        with engine.connect() as conn:
            if 'sqlite' in str(engine.url):
                result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"))
            else:
                result = conn.execute(text("""
                    SELECT tablename FROM pg_catalog.pg_tables
                    WHERE schemaname = 'public'
                    ORDER BY tablename
                """))

            tables = [row[0] for row in result]

        expected_tables = [
            'users', 'bills', 'bill_versions', 'keywords',
            'bill_keyword_matches', 'alerts', 'impact_analyses'
        ]

        print("Tables created:")
        for table in tables:
            if table in expected_tables:
                print(f"  ✓ {table}")
            else:
                print(f"  • {table}")

        missing = [t for t in expected_tables if t not in tables]
        if missing:
            print(f"❌ Missing tables: {missing}")
            return False

        # Seed keywords
        print("🌱 Seeding keywords...")
        success = seed_keywords(engine)
        if success:
            print("✅ Keywords seeded successfully")
        else:
            print("⚠️  Keyword seeding had issues (non-fatal)")

        print("\n🎉 Migration completed successfully!")
        print(f"📊 Database: {engine.url}")
        print(f"📋 Tables: {len(expected_tables)} created")

        return True

    except SQLAlchemyError as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def seed_keywords(engine):
    """Seed the keywords table"""
    from models.legislation import Keyword
    from sqlalchemy.orm import Session
    import json

    keywords_data = [
        {"term": "skilled nursing facility", "category": "SNF", "importance_weight": 2.0,
         "synonyms": '["SNF", "nursing home", "long-term care facility"]'},
        {"term": "Medicare", "category": "Medicare", "importance_weight": 1.8,
         "synonyms": '["CMS", "Centers for Medicare & Medicaid Services"]'},
        {"term": "PDPM", "category": "PDPM", "importance_weight": 2.0,
         "synonyms": '["Patient Driven Payment Model"]'},
        {"term": "staffing ratios", "category": "Staffing", "importance_weight": 1.9,
         "synonyms": '["nurse-to-patient ratio", "staffing requirements"]'},
        {"term": "star rating", "category": "Quality", "importance_weight": 1.7,
         "synonyms": '["five-star rating", "CMS star rating"]'},
        {"term": "42 CFR", "category": "Regulatory", "importance_weight": 1.8,
         "synonyms": '["Code of Federal Regulations"]'},
        {"term": "COVID-19", "category": "Pandemic", "importance_weight": 1.8,
         "synonyms": '["coronavirus", "pandemic"]'},
        {"term": "infection control", "category": "Safety", "importance_weight": 1.7,
         "synonyms": '["infection prevention", "disease control"]'},
        {"term": "telehealth", "category": "Technology", "importance_weight": 1.4,
         "synonyms": '["telemedicine", "remote care"]'},
        {"term": "workforce", "category": "Staffing", "importance_weight": 1.5,
         "synonyms": '["staff", "employees", "personnel"]'},
    ]

    try:
        with Session(engine) as session:
            # Check if keywords already exist
            existing_count = session.query(Keyword).count()
            if existing_count > 0:
                print(f"  Keywords table already has {existing_count} entries")
                return True

            # Add keywords
            for kw_data in keywords_data:
                keyword = Keyword(**kw_data)
                session.add(keyword)

            session.commit()

            final_count = session.query(Keyword).count()
            print(f"  Added {final_count} keywords")
            return True

    except Exception as e:
        print(f"  Keyword seeding error: {e}")
        return False

if __name__ == "__main__":
    success = run_migration()
    if success:
        print("\n🚀 Ready to start your application:")
        print("   uvicorn main:app --reload")
        print("   http://localhost:8000/docs")
        sys.exit(0)
    else:
        print("\n❌ Migration failed!")
        sys.exit(1)