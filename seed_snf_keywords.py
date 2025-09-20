#!/usr/bin/env python3
"""
SNF Keywords Seeding Script
Seeds the Keywords table with specific skilled nursing facility terms
"""

import sys
import os
import json

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session
    from models.database import Base, DATABASE_URL
    from models.legislation import Keyword
    print("✓ Imports successful")
except ImportError as e:
    print(f"✗ Import error: {e}")
    print("Please ensure the database migration has been run first")
    sys.exit(1)

def seed_snf_keywords():
    """Seed specific SNF keywords"""
    print("🌱 SNF Keywords Seeding")
    print("=" * 30)

    # Define the specific keywords requested
    snf_keywords = [
        {
            "term": "skilled nursing facility",
            "category": "SNF_Core",
            "importance_weight": 2.0,
            "synonyms": json.dumps(["SNF", "nursing facility", "skilled nursing", "skilled care facility"]),
            "is_active": True
        },
        {
            "term": "SNF",
            "category": "SNF_Core",
            "importance_weight": 2.0,
            "synonyms": json.dumps(["skilled nursing facility", "nursing facility", "skilled nursing"]),
            "is_active": True
        },
        {
            "term": "PDPM",
            "category": "Payment_Model",
            "importance_weight": 2.0,
            "synonyms": json.dumps(["Patient Driven Payment Model", "patient-driven payment model", "PDPM system"]),
            "is_active": True
        },
        {
            "term": "nursing home",
            "category": "SNF_Core",
            "importance_weight": 1.9,
            "synonyms": json.dumps(["SNF", "skilled nursing facility", "long-term care facility", "nursing facility"]),
            "is_active": True
        },
        {
            "term": "Medicare Part A",
            "category": "Medicare",
            "importance_weight": 1.9,
            "synonyms": json.dumps(["Medicare A", "Part A", "Medicare hospital insurance", "Medicare Part A coverage"]),
            "is_active": True
        },
        {
            "term": "Medicaid reimbursement",
            "category": "Medicaid",
            "importance_weight": 1.8,
            "synonyms": json.dumps(["Medicaid payment", "Medicaid funding", "state Medicaid", "Medicaid coverage"]),
            "is_active": True
        },
        {
            "term": "Five-Star Quality Rating",
            "category": "Quality",
            "importance_weight": 1.9,
            "synonyms": json.dumps(["5-star rating", "star rating", "CMS star rating", "quality rating", "five star"]),
            "is_active": True
        },
        {
            "term": "post-acute care",
            "category": "Care_Type",
            "importance_weight": 1.7,
            "synonyms": json.dumps(["post acute care", "PAC", "post-hospitalization care", "transitional care"]),
            "is_active": True
        },
        {
            "term": "long-term care",
            "category": "Care_Type",
            "importance_weight": 1.8,
            "synonyms": json.dumps(["LTC", "long term care", "extended care", "chronic care", "custodial care"]),
            "is_active": True
        },
        {
            "term": "staffing ratios",
            "category": "Staffing",
            "importance_weight": 1.9,
            "synonyms": json.dumps(["nurse-to-patient ratio", "staffing requirements", "minimum staffing", "nursing ratios", "staff-to-resident ratio"]),
            "is_active": True
        },
        {
            "term": "survey process",
            "category": "Regulatory",
            "importance_weight": 1.8,
            "synonyms": json.dumps(["state survey", "health inspection", "regulatory survey", "compliance inspection", "CMS survey"]),
            "is_active": True
        },
        {
            "term": "Quality Reporting Program",
            "category": "Quality",
            "importance_weight": 1.7,
            "synonyms": json.dumps(["QRP", "quality reporting", "quality measures", "SNF QRP", "performance reporting"]),
            "is_active": True
        }
    ]

    try:
        # Connect to database - use SQLite if PostgreSQL is not available
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

        print(f"📡 Connected to database: {db_type}")

        with Session(engine) as session:
            # Check existing keywords
            existing_keywords = session.query(Keyword.term).all()
            existing_terms = {kw.term for kw in existing_keywords}

            print(f"📊 Found {len(existing_terms)} existing keywords")

            # Add new keywords
            added_count = 0
            updated_count = 0
            skipped_count = 0

            for kw_data in snf_keywords:
                term = kw_data['term']

                # Check if keyword already exists
                existing_keyword = session.query(Keyword).filter(Keyword.term == term).first()

                if existing_keyword:
                    # Update existing keyword
                    for key, value in kw_data.items():
                        if key != 'term':  # Don't update the term itself
                            setattr(existing_keyword, key, value)
                    updated_count += 1
                    print(f"  ↻ Updated: {term}")
                else:
                    # Add new keyword
                    keyword = Keyword(**kw_data)
                    session.add(keyword)
                    added_count += 1
                    print(f"  + Added: {term}")

            # Commit changes
            session.commit()

            print(f"\n✅ Seeding completed!")
            print(f"   • Added: {added_count} new keywords")
            print(f"   • Updated: {updated_count} existing keywords")
            print(f"   • Total keywords in database: {session.query(Keyword).count()}")

            # Display keywords by category
            print(f"\n📋 Keywords by category:")
            categories = session.query(Keyword.category, session.query(Keyword).filter(Keyword.category == Keyword.category).count()).distinct().all()

            # Get category counts
            from sqlalchemy import func
            category_counts = session.query(
                Keyword.category,
                func.count(Keyword.id).label('count'),
                func.avg(Keyword.importance_weight).label('avg_weight')
            ).group_by(Keyword.category).order_by('count').all()

            for category, count, avg_weight in category_counts:
                print(f"   • {category}: {count} keywords (avg weight: {avg_weight:.1f})")

            return True

    except Exception as e:
        print(f"❌ Error seeding keywords: {e}")
        return False

def verify_keywords():
    """Verify the keywords were added successfully"""
    print(f"\n🔍 Verifying keywords...")

    try:
        # Use the same connection logic as the seeding function
        try:
            if DATABASE_URL.startswith('postgresql'):
                engine = create_engine(DATABASE_URL)
                with engine.connect():
                    pass
            else:
                raise Exception("Using SQLite fallback")
        except:
            engine = create_engine("sqlite:///./snflegtracker.db")

        with Session(engine) as session:
            # Get all keywords
            keywords = session.query(Keyword).order_by(Keyword.category, Keyword.term).all()

            print(f"📊 Total keywords: {len(keywords)}")
            print(f"\n📝 All keywords:")

            current_category = None
            for keyword in keywords:
                if keyword.category != current_category:
                    current_category = keyword.category
                    print(f"\n  🏷️  {current_category}:")

                synonyms_count = 0
                if keyword.synonyms:
                    try:
                        synonyms = json.loads(keyword.synonyms)
                        synonyms_count = len(synonyms)
                    except:
                        pass

                print(f"    • {keyword.term} (weight: {keyword.importance_weight}, synonyms: {synonyms_count})")

            return True

    except Exception as e:
        print(f"❌ Error verifying keywords: {e}")
        return False

def test_keyword_search():
    """Test keyword functionality with sample queries"""
    print(f"\n🧪 Testing keyword search functionality...")

    try:
        # Use the same connection logic as the seeding function
        try:
            if DATABASE_URL.startswith('postgresql'):
                engine = create_engine(DATABASE_URL)
                with engine.connect():
                    pass
            else:
                raise Exception("Using SQLite fallback")
        except:
            engine = create_engine("sqlite:///./snflegtracker.db")

        with Session(engine) as session:
            # Test 1: Find high-importance keywords
            high_importance = session.query(Keyword).filter(
                Keyword.importance_weight >= 1.9
            ).order_by(Keyword.importance_weight.desc()).all()

            print(f"  ✓ High-importance keywords (≥1.9): {len(high_importance)}")
            for kw in high_importance[:3]:
                print(f"    • {kw.term} ({kw.importance_weight})")

            # Test 2: Find keywords by category
            snf_core = session.query(Keyword).filter(
                Keyword.category == 'SNF_Core'
            ).all()

            print(f"  ✓ SNF_Core category keywords: {len(snf_core)}")

            # Test 3: Search for keywords containing specific terms
            medicare_keywords = session.query(Keyword).filter(
                Keyword.term.like('%Medicare%')
            ).all()

            print(f"  ✓ Keywords containing 'Medicare': {len(medicare_keywords)}")

            # Test 4: Active keywords count
            active_keywords = session.query(Keyword).filter(
                Keyword.is_active == True
            ).count()

            print(f"  ✓ Active keywords: {active_keywords}")

            return True

    except Exception as e:
        print(f"❌ Error testing keywords: {e}")
        return False

def main():
    """Main function"""
    print("🏥 SNF Keywords Seeding Script")
    print("=" * 40)

    # Step 1: Seed keywords
    if not seed_snf_keywords():
        print("❌ Failed to seed keywords")
        return 1

    # Step 2: Verify keywords
    if not verify_keywords():
        print("❌ Failed to verify keywords")
        return 1

    # Step 3: Test functionality
    if not test_keyword_search():
        print("❌ Failed to test keywords")
        return 1

    print(f"\n🎉 All SNF keywords have been successfully seeded!")
    print(f"\n🚀 Next steps:")
    print(f"   • Start the FastAPI app: uvicorn main:app --reload")
    print(f"   • Test keyword matching: Create a bill with SNF-related content")
    print(f"   • View API docs: http://localhost:8000/docs")

    return 0

if __name__ == "__main__":
    sys.exit(main())