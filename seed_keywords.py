"""
Seed script to populate the keywords table with SNF-related terms
Run this after the initial migration to populate default keywords
"""

import sys
import os

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy.orm import Session
from models.database import SessionLocal, engine
from models.legislation import Keyword, Base
import json

def create_default_keywords():
    """Create default keywords for SNF tracking"""

    keywords_data = [
        # SNF Core Terms
        {"term": "skilled nursing facility", "category": "SNF", "importance_weight": 2.0,
         "synonyms": json.dumps(["SNF", "nursing home", "long-term care facility", "LTC facility"])},
        {"term": "skilled nursing", "category": "SNF", "importance_weight": 1.8,
         "synonyms": json.dumps(["nursing care", "skilled care", "SNF care"])},
        {"term": "nursing home", "category": "SNF", "importance_weight": 1.9,
         "synonyms": json.dumps(["SNF", "skilled nursing facility", "long-term care facility"])},
        {"term": "long-term care", "category": "SNF", "importance_weight": 1.7,
         "synonyms": json.dumps(["LTC", "extended care", "chronic care"])},

        # Medicare & Reimbursement
        {"term": "Medicare Part A", "category": "Medicare", "importance_weight": 1.9,
         "synonyms": json.dumps(["Medicare A", "Part A", "hospital insurance"])},
        {"term": "Medicare", "category": "Medicare", "importance_weight": 1.8,
         "synonyms": json.dumps(["CMS", "Centers for Medicare & Medicaid Services"])},
        {"term": "Medicaid", "category": "Medicaid", "importance_weight": 1.8,
         "synonyms": json.dumps(["state Medicaid", "Medicaid program"])},
        {"term": "reimbursement", "category": "Financial", "importance_weight": 1.6,
         "synonyms": json.dumps(["payment", "compensation", "funding"])},

        # PDPM & MDS
        {"term": "PDPM", "category": "PDPM", "importance_weight": 2.0,
         "synonyms": json.dumps(["Patient Driven Payment Model", "patient-driven payment model"])},
        {"term": "Patient Driven Payment Model", "category": "PDPM", "importance_weight": 2.0,
         "synonyms": json.dumps(["PDPM"])},
        {"term": "MDS", "category": "Assessment", "importance_weight": 1.8,
         "synonyms": json.dumps(["Minimum Data Set", "MDS 3.0", "resident assessment"])},
        {"term": "Minimum Data Set", "category": "Assessment", "importance_weight": 1.8,
         "synonyms": json.dumps(["MDS", "MDS 3.0"])},

        # Staffing & Quality
        {"term": "staffing ratios", "category": "Staffing", "importance_weight": 1.9,
         "synonyms": json.dumps(["nurse-to-patient ratio", "staffing requirements", "minimum staffing"])},
        {"term": "nurse staffing", "category": "Staffing", "importance_weight": 1.8,
         "synonyms": json.dumps(["nursing staff", "RN staffing", "LPN staffing"])},
        {"term": "CNA", "category": "Staffing", "importance_weight": 1.5,
         "synonyms": json.dumps(["certified nursing assistant", "nursing assistant", "aide"])},
        {"term": "registered nurse", "category": "Staffing", "importance_weight": 1.7,
         "synonyms": json.dumps(["RN", "staff nurse", "charge nurse"])},
        {"term": "licensed practical nurse", "category": "Staffing", "importance_weight": 1.6,
         "synonyms": json.dumps(["LPN", "LVN", "licensed vocational nurse"])},

        # Quality Measures
        {"term": "star rating", "category": "Quality", "importance_weight": 1.7,
         "synonyms": json.dumps(["five-star rating", "CMS star rating", "quality rating"])},
        {"term": "quality measures", "category": "Quality", "importance_weight": 1.6,
         "synonyms": json.dumps(["quality indicators", "performance measures", "QMs"])},
        {"term": "deficiency", "category": "Quality", "importance_weight": 1.8,
         "synonyms": json.dumps(["citation", "violation", "non-compliance"])},
        {"term": "survey", "category": "Quality", "importance_weight": 1.5,
         "synonyms": json.dumps(["inspection", "state survey", "health inspection"])},

        # Financial & Operations
        {"term": "cost reporting", "category": "Financial", "importance_weight": 1.4,
         "synonyms": json.dumps(["cost report", "Medicare cost report"])},
        {"term": "bad debt", "category": "Financial", "importance_weight": 1.3,
         "synonyms": json.dumps(["uncollectible debt", "unpaid bills"])},
        {"term": "charity care", "category": "Financial", "importance_weight": 1.2,
         "synonyms": json.dumps(["free care", "uncompensated care"])},
        {"term": "admission", "category": "Operations", "importance_weight": 1.4,
         "synonyms": json.dumps(["intake", "enrollment", "admission process"])},
        {"term": "discharge", "category": "Operations", "importance_weight": 1.4,
         "synonyms": json.dumps(["release", "transition", "discharge planning"])},

        # Regulatory & Compliance
        {"term": "42 CFR", "category": "Regulatory", "importance_weight": 1.8,
         "synonyms": json.dumps(["Code of Federal Regulations", "CFR 42"])},
        {"term": "483", "category": "Regulatory", "importance_weight": 1.9,
         "synonyms": json.dumps(["42 CFR 483", "nursing home regulations"])},
        {"term": "F-tag", "category": "Regulatory", "importance_weight": 1.7,
         "synonyms": json.dumps(["F tag", "regulatory tag", "compliance tag"])},
        {"term": "life safety", "category": "Safety", "importance_weight": 1.6,
         "synonyms": json.dumps(["fire safety", "emergency preparedness", "safety requirements"])},

        # COVID-19 & Pandemic
        {"term": "COVID-19", "category": "Pandemic", "importance_weight": 1.8,
         "synonyms": json.dumps(["coronavirus", "pandemic", "SARS-CoV-2"])},
        {"term": "infection control", "category": "Safety", "importance_weight": 1.7,
         "synonyms": json.dumps(["infection prevention", "disease control", "IPC"])},
        {"term": "PPE", "category": "Safety", "importance_weight": 1.5,
         "synonyms": json.dumps(["personal protective equipment", "protective equipment"])},

        # Technology & Innovation
        {"term": "telehealth", "category": "Technology", "importance_weight": 1.4,
         "synonyms": json.dumps(["telemedicine", "remote care", "virtual care"])},
        {"term": "electronic health record", "category": "Technology", "importance_weight": 1.3,
         "synonyms": json.dumps(["EHR", "electronic medical record", "EMR"])},

        # Workforce & Training
        {"term": "workforce", "category": "Staffing", "importance_weight": 1.5,
         "synonyms": json.dumps(["staff", "employees", "personnel"])},
        {"term": "training", "category": "Education", "importance_weight": 1.3,
         "synonyms": json.dumps(["education", "competency", "certification"])},
        {"term": "turnover", "category": "Staffing", "importance_weight": 1.6,
         "synonyms": json.dumps(["staff turnover", "employee turnover", "retention"])},
    ]

    db = SessionLocal()
    try:
        # Check if keywords already exist
        existing_count = db.query(Keyword).count()
        if existing_count > 0:
            print(f"Keywords table already has {existing_count} entries. Skipping seed.")
            return

        # Create keywords
        for keyword_data in keywords_data:
            keyword = Keyword(**keyword_data)
            db.add(keyword)

        db.commit()
        print(f"Successfully created {len(keywords_data)} default keywords")

        # Print summary by category
        categories = {}
        for kw in keywords_data:
            cat = kw["category"]
            categories[cat] = categories.get(cat, 0) + 1

        print("\nKeywords by category:")
        for category, count in sorted(categories.items()):
            print(f"  {category}: {count}")

    except Exception as e:
        db.rollback()
        print(f"Error creating keywords: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)

    # Seed keywords
    create_default_keywords()