# Database Setup Guide

This guide explains how to set up and manage the database for the SNFLegTracker system.

## Database Schema Overview

The system uses PostgreSQL with the following main tables:

### Core Tables

1. **users** - User management and authentication
2. **bills** - Legislative bills with comprehensive tracking
3. **bill_versions** - Historical versions of bills for change tracking
4. **keywords** - SNF-related terms for content matching
5. **bill_keyword_matches** - Many-to-many relationship between bills and keywords
6. **alerts** - User notifications for bill changes
7. **impact_analyses** - AI-generated analysis of bill impacts

### Key Relationships

- Bills → BillVersions (One-to-Many)
- Bills ↔ Keywords (Many-to-Many via BillKeywordMatches)
- Users → Alerts (One-to-Many)
- Bills → Alerts (One-to-Many)
- Bills → ImpactAnalyses (One-to-Many)

## Setup Instructions

### 1. Using Docker (Recommended)

```bash
# Start the database with docker-compose
docker-compose up -d db

# The database will be available at localhost:5432
# Default credentials:
# - Database: snflegtracker
# - User: snflegtracker
# - Password: password
```

### 2. Manual PostgreSQL Setup

```bash
# Install PostgreSQL (Ubuntu/Debian)
sudo apt-get install postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql
CREATE DATABASE snflegtracker;
CREATE USER snflegtracker WITH PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE snflegtracker TO snflegtracker;
\q
```

### 3. Run Migrations

Since Alembic may not be available in all environments, you can either:

**Option A: Use the pre-created migration script**
```bash
# Connect to your PostgreSQL database and run:
psql -h localhost -U snflegtracker -d snflegtracker -f alembic/versions/001_initial_migration.py
```

**Option B: Use SQLAlchemy to create tables directly**
```python
# Run this Python script to create all tables
from models.database import engine, Base
from models.legislation import *  # Import all models

# Create all tables
Base.metadata.create_all(bind=engine)
print("All tables created successfully!")
```

### 4. Seed Default Keywords

```bash
# Run the keyword seeding script
python seed_keywords.py
```

This will populate the `keywords` table with 50+ SNF-related terms including:
- Core SNF terms (skilled nursing facility, nursing home, etc.)
- Medicare/Medicaid terms
- PDPM and MDS assessment terms
- Staffing and quality measures
- Regulatory compliance terms

## Database Indexes for Performance

The schema includes optimized indexes for common query patterns:

### Bills Table Indexes
- `idx_bill_search` - Composite index on title and summary for text search
- `idx_bill_date_status` - For filtering by date and status
- `idx_bill_sponsor_committee` - For sponsor/committee searches

### Alert Indexes
- `idx_user_alerts_unread` - For quickly finding unread alerts per user
- `idx_bill_alerts` - For finding alerts by bill and type

### Keyword Match Indexes
- `idx_bill_keyword_unique` - Ensures one match per bill-keyword pair
- `idx_bill_keyword_score` - For ranking matches by confidence

### Impact Analysis Indexes
- `idx_impact_score` - For finding high-impact bills
- `idx_bill_impact_latest` - For getting the latest analysis per bill

## Sample Queries

### Find high-confidence SNF-related bills
```sql
SELECT b.bill_number, b.title, bkm.confidence_score, k.term
FROM bills b
JOIN bill_keyword_matches bkm ON b.id = bkm.bill_id
JOIN keywords k ON bkm.keyword_id = k.id
WHERE k.category = 'SNF'
  AND bkm.confidence_score > 0.8
ORDER BY bkm.confidence_score DESC;
```

### Get recent high-impact bills
```sql
SELECT b.bill_number, b.title, ia.impact_score, ia.impact_category
FROM bills b
JOIN impact_analyses ia ON b.id = ia.bill_id
WHERE ia.impact_score > 70
  AND b.last_action_date > NOW() - INTERVAL '30 days'
ORDER BY ia.impact_score DESC;
```

### Find bills affecting staffing
```sql
SELECT DISTINCT b.bill_number, b.title, b.status
FROM bills b
JOIN bill_keyword_matches bkm ON b.id = bkm.bill_id
JOIN keywords k ON bkm.keyword_id = k.id
WHERE k.category = 'Staffing'
  AND bkm.confidence_score > 0.6
ORDER BY b.last_action_date DESC;
```

## Maintenance

### Regular Tasks

1. **Update Bill Keywords**: Run keyword matching periodically for new bills
```python
from services.analysis.keyword_matcher import KeywordMatcher
from models.database import SessionLocal

db = SessionLocal()
matcher = KeywordMatcher(db)

# Process all bills without keyword matches
bills_without_keywords = db.query(Bill).outerjoin(BillKeywordMatch).filter(
    BillKeywordMatch.id.is_(None)
).all()

for bill in bills_without_keywords:
    matcher.process_bill_keywords(bill.id)
```

2. **Generate Impact Analyses**: Periodically analyze high-priority bills
```python
from services.analysis.impact_analyzer import ImpactAnalyzer

analyzer = ImpactAnalyzer(db)

# Analyze bills with high keyword confidence but no analysis
high_confidence_bills = db.query(Bill).join(BillKeywordMatch).filter(
    BillKeywordMatch.confidence_score > 0.8
).outerjoin(ImpactAnalysis).filter(
    ImpactAnalysis.id.is_(None)
).limit(10).all()

for bill in high_confidence_bills:
    analyzer.analyze_bill_impact(bill.id)
```

3. **Clean up old alerts**: Remove old, read alerts
```sql
DELETE FROM alerts
WHERE is_read = true
  AND triggered_at < NOW() - INTERVAL '90 days';
```

### Backup Strategy

```bash
# Daily backup
pg_dump -h localhost -U snflegtracker snflegtracker > backup_$(date +%Y%m%d).sql

# Restore from backup
psql -h localhost -U snflegtracker snflegtracker < backup_20250121.sql
```

## Monitoring

Key metrics to monitor:
- Number of active bills
- Keyword match accuracy
- Alert delivery performance
- Database query performance (especially for search operations)
- Storage growth (bill full_text can be large)

## Troubleshooting

### Common Issues

1. **Slow keyword matching**: Ensure proper indexes on bill content
2. **High memory usage**: Consider archiving old bill versions
3. **Alert spam**: Tune keyword confidence thresholds
4. **Large database size**: Implement data retention policies

### Performance Tuning

1. **Enable query logging**:
```sql
-- In postgresql.conf
log_statement = 'all'
log_min_duration_statement = 1000  -- Log queries taking > 1 second
```

2. **Analyze table statistics**:
```sql
ANALYZE bills;
ANALYZE bill_keyword_matches;
ANALYZE alerts;
```

3. **Monitor index usage**:
```sql
SELECT schemaname, tablename, indexname, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_tup_read DESC;
```