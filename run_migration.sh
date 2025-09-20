#!/bin/bash

# SNFLegTracker Database Migration Script
# This script sets up the database for the SNFLegTracker application

set -e  # Exit on any error

echo "🏗️  SNFLegTracker Database Setup"
echo "=================================="

# Database connection parameters
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_NAME=${DB_NAME:-snflegtracker}
DB_USER=${DB_USER:-snflegtracker}
DB_PASSWORD=${DB_PASSWORD:-password}

# Check if PostgreSQL client is available
if ! command -v psql &> /dev/null; then
    echo "❌ psql command not found. Please install PostgreSQL client."
    echo "   macOS: brew install postgresql"
    echo "   Ubuntu: sudo apt-get install postgresql-client"
    exit 1
fi

echo "📡 Testing database connection..."

# Test connection
if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" &> /dev/null; then
    echo "✅ Database connection successful"
else
    echo "❌ Cannot connect to database"
    echo "   Host: $DB_HOST:$DB_PORT"
    echo "   Database: $DB_NAME"
    echo "   User: $DB_USER"
    echo ""
    echo "   Make sure PostgreSQL is running and credentials are correct."
    echo "   You can start PostgreSQL with Docker using:"
    echo "   docker run -d --name snf-postgres -p 5432:5432 \\"
    echo "     -e POSTGRES_DB=snflegtracker \\"
    echo "     -e POSTGRES_USER=snflegtracker \\"
    echo "     -e POSTGRES_PASSWORD=password \\"
    echo "     postgres:15"
    exit 1
fi

echo "📋 Creating database tables..."

# Run the setup script
if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f setup_database.sql; then
    echo "✅ Database tables created successfully"
else
    echo "❌ Failed to create database tables"
    exit 1
fi

echo "🌱 Seeding keywords..."

# Run the seed script
if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f seed_keywords.sql; then
    echo "✅ Keywords seeded successfully"
else
    echo "❌ Failed to seed keywords"
    exit 1
fi

echo "🔍 Verifying setup..."

# Verify tables exist and have data
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
SELECT
    schemaname,
    tablename,
    n_tup_ins as inserts,
    n_tup_upd as updates,
    n_tup_del as deletes
FROM pg_stat_user_tables
ORDER BY tablename;
"

echo ""
echo "🎉 Database setup completed successfully!"
echo ""
echo "📊 Summary:"
echo "   • 7 database tables created"
echo "   • 40+ SNF-related keywords seeded"
echo "   • Database indexes optimized for search performance"
echo "   • Default admin user created (admin@snflegtracker.com)"
echo ""
echo "🚀 Next steps:"
echo "   1. Start the FastAPI application:"
echo "      uvicorn main:app --reload"
echo ""
echo "   2. Access the API documentation:"
echo "      http://localhost:8000/docs"
echo ""
echo "   3. Test the health endpoint:"
echo "      curl http://localhost:8000/api/v1/health"
echo ""
echo "   4. View database with any PostgreSQL client using:"
echo "      Host: $DB_HOST, Port: $DB_PORT"
echo "      Database: $DB_NAME, User: $DB_USER"