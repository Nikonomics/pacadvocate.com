#!/usr/bin/env python3
"""
Startup script for the SNF Legislation Tracker API
Handles initialization, database setup, and server startup
"""

import os
import sys
import asyncio
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

def setup_database():
    """Set up database tables"""
    print("🛠️  Setting up database...")

    try:
        from sqlalchemy import create_engine
        from models.database import Base
        # Import all models to ensure they're registered
        from models.legislation import Bill, User, BillVersion, Keyword, BillKeywordMatch, Alert, ImpactAnalysis
        from models.change_detection import (
            BillChange, StageTransition, ChangeAlert, AlertPreferences, ChangeDetectionConfig
        )
        from api.config import settings

        engine = create_engine(settings.database_url)

        # Create all tables
        Base.metadata.create_all(engine)
        print("✅ Database tables created/updated successfully")

        # List created tables
        from sqlalchemy import inspect
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        print(f"📋 Tables in database: {len(table_names)}")

        return True

    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        return False

def test_connections():
    """Test database and Redis connections"""
    print("🔍 Testing connections...")

    # Test database
    try:
        from sqlalchemy import create_engine, text
        from api.config import settings

        engine = create_engine(settings.database_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ Database connection: OK")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

    # Test Redis
    try:
        import redis
        from api.config import settings

        redis_client = redis.from_url(settings.redis_url)
        redis_client.ping()
        print("✅ Redis connection: OK")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        print("ℹ️  Redis is required for caching and rate limiting")
        return False

    return True

def create_sample_data():
    """Create sample data for testing"""
    print("📊 Creating sample data...")

    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from models.legislation import Bill, User
        from api.config import settings
        from api.auth.jwt_handler import jwt_handler

        engine = create_engine(settings.database_url)

        with Session(engine) as session:
            # Check if sample data already exists
            existing_bills = session.query(Bill).filter(
                Bill.bill_number.like('SAMPLE-%')
            ).count()

            if existing_bills > 0:
                print(f"✅ Sample data already exists: {existing_bills} sample bills")
                return True

            # Create sample user
            existing_user = session.query(User).filter(
                User.email == "demo@example.com"
            ).first()

            if not existing_user:
                demo_user = User(
                    email="demo@example.com",
                    hashed_password=jwt_handler.get_password_hash("demo123"),
                    full_name="Demo User",
                    organization="Demo SNF",
                    is_active=True,
                    is_verified=True
                )
                session.add(demo_user)

            # Create sample bills
            sample_bills = [
                {
                    'bill_number': 'SAMPLE-001',
                    'title': 'Sample Medicare SNF Payment Enhancement Act',
                    'summary': 'A sample bill to demonstrate API functionality with SNF payment improvements',
                    'status': 'Introduced in House',
                    'source': 'sample_data',
                    'state_or_federal': 'federal',
                    'sponsor': 'Rep. Sample Sponsor',
                    'chamber': 'House',
                    'relevance_score': 85.0
                },
                {
                    'bill_number': 'SAMPLE-002',
                    'title': 'Sample SNF Quality Reporting Modernization Act',
                    'summary': 'A sample bill requiring enhanced quality reporting from skilled nursing facilities',
                    'status': 'Committee Review',
                    'source': 'sample_data',
                    'state_or_federal': 'federal',
                    'sponsor': 'Sen. Quality Advocate',
                    'chamber': 'Senate',
                    'relevance_score': 75.0
                },
                {
                    'bill_number': 'SAMPLE-003',
                    'title': 'Sample Nursing Home Staffing Standards Act',
                    'summary': 'A sample bill establishing minimum staffing requirements for nursing homes',
                    'status': 'Passed House',
                    'source': 'sample_data',
                    'state_or_federal': 'federal',
                    'sponsor': 'Rep. Staff Advocate',
                    'chamber': 'House',
                    'relevance_score': 92.0
                }
            ]

            for bill_data in sample_bills:
                bill = Bill(**bill_data)
                session.add(bill)

            session.commit()
            print(f"✅ Created sample data: {len(sample_bills)} bills and demo user")
            print("📧 Demo user: demo@example.com / demo123")

        return True

    except Exception as e:
        print(f"❌ Sample data creation failed: {e}")
        return False

def start_server(host="0.0.0.0", port=8000, reload=False):
    """Start the FastAPI server"""
    print(f"🚀 Starting SNF Legislation Tracker API on {host}:{port}")

    try:
        import uvicorn
        from api.config import settings

        uvicorn.run(
            "api.main:app",
            host=host,
            port=port,
            reload=reload or settings.debug,
            log_level="info" if settings.debug else "warning",
            access_log=settings.debug
        )

    except KeyboardInterrupt:
        print("\n⏹️  Server stopped by user")
    except Exception as e:
        print(f"❌ Server startup failed: {e}")

def main():
    """Main function with command line arguments"""
    parser = argparse.ArgumentParser(
        description="SNF Legislation Tracker API Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Start server with default settings
  %(prog)s --setup-db               # Set up database tables
  %(prog)s --test-connections       # Test database and Redis connections
  %(prog)s --create-sample-data     # Create sample data for testing
  %(prog)s --host 127.0.0.1 --port 8080  # Custom host and port
  %(prog)s --reload                 # Enable auto-reload for development
        """
    )

    parser.add_argument(
        "--setup-db",
        action="store_true",
        help="Set up database tables"
    )

    parser.add_argument(
        "--test-connections",
        action="store_true",
        help="Test database and Redis connections"
    )

    parser.add_argument(
        "--create-sample-data",
        action="store_true",
        help="Create sample data for testing"
    )

    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind server to (default: 0.0.0.0)"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind server to (default: 8000)"
    )

    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )

    args = parser.parse_args()

    print("🏥 SNF Legislation Tracker API")
    print("=" * 40)
    print(f"🕐 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    success = True

    # Handle individual commands
    if args.setup_db:
        success &= setup_database()

    if args.test_connections:
        success &= test_connections()

    if args.create_sample_data:
        success &= create_sample_data()

    # If no specific commands, run full startup sequence
    if not any([args.setup_db, args.test_connections, args.create_sample_data]):
        print("🔧 Running startup sequence...")

        # Set up database
        if not setup_database():
            print("❌ Database setup failed. Exiting.")
            sys.exit(1)

        # Test connections
        if not test_connections():
            print("⚠️  Connection tests failed. Some features may not work.")

        # Create sample data if none exists
        create_sample_data()

        print("\n📖 API Documentation:")
        print(f"   Swagger UI: http://{args.host}:{args.port}/docs")
        print(f"   ReDoc: http://{args.host}:{args.port}/redoc")
        print(f"   OpenAPI spec: http://{args.host}:{args.port}/openapi.json")

        print("\n🔑 Test Endpoints:")
        print(f"   Health: http://{args.host}:{args.port}/health")
        print(f"   API Info: http://{args.host}:{args.port}/info")
        print(f"   Bills: http://{args.host}:{args.port}/api/v1/bills/")

        print("\n👤 Demo Account:")
        print("   Email: demo@example.com")
        print("   Password: demo123")

        # Start server
        start_server(args.host, args.port, args.reload)

    if not success:
        print("❌ Some operations failed. Check the logs above.")
        sys.exit(1)

if __name__ == "__main__":
    main()