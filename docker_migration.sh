#!/bin/bash

# SNFLegTracker Docker-based Database Migration
# This script uses Docker to run the migration without requiring local PostgreSQL client

set -e  # Exit on any error

echo "🐳 SNFLegTracker Docker Migration"
echo "=================================="

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    echo "   Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Database connection parameters
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_NAME=${DB_NAME:-snflegtracker}
DB_USER=${DB_USER:-snflegtracker}
DB_PASSWORD=${DB_PASSWORD:-password}

echo "🚀 Starting PostgreSQL database..."

# Start PostgreSQL container
docker run -d --name snf-postgres \
    -p ${DB_PORT}:5432 \
    -e POSTGRES_DB=${DB_NAME} \
    -e POSTGRES_USER=${DB_USER} \
    -e POSTGRES_PASSWORD=${DB_PASSWORD} \
    postgres:15 || echo "Container may already be running..."

echo "⏳ Waiting for database to be ready..."
sleep 5

# Test connection using Docker
echo "📡 Testing database connection..."
if docker run --rm --link snf-postgres:postgres postgres:15 \
    psql -h postgres -U ${DB_USER} -d ${DB_NAME} -c "SELECT 1;" > /dev/null 2>&1; then
    echo "✅ Database connection successful"
else
    echo "❌ Database connection failed. Waiting longer..."
    sleep 10

    # Try again
    if docker run --rm --link snf-postgres:postgres postgres:15 \
        psql -h postgres -U ${DB_USER} -d ${DB_NAME} -c "SELECT 1;" > /dev/null 2>&1; then
        echo "✅ Database connection successful"
    else
        echo "❌ Cannot connect to database. Please check Docker and try again."
        exit 1
    fi
fi

echo "📋 Creating database tables..."

# Run setup script using Docker
if docker run --rm --link snf-postgres:postgres -v "$(pwd):/scripts" postgres:15 \
    psql -h postgres -U ${DB_USER} -d ${DB_NAME} -f /scripts/setup_database.sql; then
    echo "✅ Database tables created successfully"
else
    echo "❌ Failed to create database tables"
    exit 1
fi

echo "🌱 Seeding keywords..."

# Run seed script using Docker
if docker run --rm --link snf-postgres:postgres -v "$(pwd):/scripts" postgres:15 \
    psql -h postgres -U ${DB_USER} -d ${DB_NAME} -f /scripts/seed_keywords.sql; then
    echo "✅ Keywords seeded successfully"
else
    echo "❌ Failed to seed keywords"
    exit 1
fi

echo "🔍 Verifying setup..."

# Verify tables exist and have data
docker run --rm --link snf-postgres:postgres postgres:15 \
    psql -h postgres -U ${DB_USER} -d ${DB_NAME} -c "
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
echo "📊 Database Details:"
echo "   Host: localhost:${DB_PORT}"
echo "   Database: ${DB_NAME}"
echo "   User: ${DB_USER}"
echo "   Password: ${DB_PASSWORD}"
echo ""
echo "🔌 Connection String:"
echo "   postgresql://${DB_USER}:${DB_PASSWORD}@localhost:${DB_PORT}/${DB_NAME}"
echo ""
echo "🚀 Next steps:"
echo "   1. Update your .env file with the database URL above"
echo "   2. Install Python dependencies: pip install -r requirements.txt"
echo "   3. Start the FastAPI application: uvicorn main:app --reload"
echo "   4. Access API docs: http://localhost:8000/docs"