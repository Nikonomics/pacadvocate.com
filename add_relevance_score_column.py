#!/usr/bin/env python3
"""
Add relevance_score column to the bills table
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def add_relevance_score_column():
    """Add relevance_score column to bills table if not already present"""
    print("🔄 Adding relevance_score column to bills table...")

    try:
        # Create database engine
        database_url = os.getenv('DATABASE_URL', 'sqlite:///./snflegtracker.db')
        engine = create_engine(database_url)

        with engine.connect() as conn:
            # Check if column already exists
            if 'sqlite' in database_url.lower():
                # SQLite approach
                result = conn.execute(text("PRAGMA table_info(bills)")).fetchall()
                columns = [row[1] for row in result]

                if 'relevance_score' not in columns:
                    # Add the column
                    conn.execute(text("ALTER TABLE bills ADD COLUMN relevance_score FLOAT DEFAULT NULL"))
                    conn.commit()
                    print("✅ Added relevance_score column to bills table")
                else:
                    print("✅ relevance_score column already exists")
            else:
                # PostgreSQL approach
                conn.execute(text("""
                    ALTER TABLE bills
                    ADD COLUMN IF NOT EXISTS relevance_score FLOAT DEFAULT NULL
                """))
                conn.commit()
                print("✅ Added relevance_score column to bills table")

            # Check the final structure
            if 'sqlite' in database_url.lower():
                result = conn.execute(text("PRAGMA table_info(bills)")).fetchall()
                print(f"📊 Bills table now has {len(result)} columns:")
                for row in result:
                    print(f"   • {row[1]} ({row[2]})")

        print("✅ Database schema update completed")

    except Exception as e:
        print(f"❌ Error adding relevance_score column: {e}")
        return False

    return True

if __name__ == "__main__":
    add_relevance_score_column()