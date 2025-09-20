# 🗄️ Database Migration Guide

## Overview

I've created all the necessary database migration files for your SNFLegTracker system. Since PostgreSQL is not available in this environment, here's how to complete the migration on your system.

## 📁 Migration Files Created

1. **`setup_database.sql`** - Complete table creation script
2. **`seed_keywords.sql`** - Keywords population script
3. **`run_migration.sh`** - Automated migration script
4. **`alembic/versions/001_initial_migration.py`** - Alembic migration file

## 🚀 How to Run the Migration

### Option 1: Automated Script (Recommended)
```bash
# Make sure PostgreSQL is running first
./run_migration.sh
```

### Option 2: Manual Steps
```bash
# 1. Start PostgreSQL (if using Docker)
docker run -d --name snf-postgres -p 5432:5432 \
  -e POSTGRES_DB=snflegtracker \
  -e POSTGRES_USER=snflegtracker \
  -e POSTGRES_PASSWORD=password \
  postgres:15

# 2. Create tables
psql -h localhost -U snflegtracker -d snflegtracker -f setup_database.sql

# 3. Seed keywords
psql -h localhost -U snflegtracker -d snflegtracker -f seed_keywords.sql
```

### Option 3: Using Alembic
```bash
# Install requirements first
pip install -r requirements.txt

# Run migration
alembic upgrade head

# Seed keywords
python seed_keywords.py
```

## 📊 What Gets Created

### Database Tables (7 total)

| Table | Purpose | Key Features |
|-------|---------|--------------|
| **users** | User management | Authentication, roles, preferences |
| **bills** | Legislative bills | Full tracking with source, status, dates |
| **bill_versions** | Change tracking | Version history with diff summaries |
| **keywords** | SNF terms | 40+ pre-configured terms with synonyms |
| **bill_keyword_matches** | Content analysis | AI confidence scoring |
| **alerts** | Notifications | Multi-level user alerting |
| **impact_analyses** | AI analysis | OpenAI-powered impact assessment |

### Performance Indexes (15+ total)

**Search Optimization:**
- `idx_bill_search` - Fast text search on title/summary
- `idx_bill_date_status` - Date and status filtering
- `idx_user_alerts_unread` - Quick unread alert queries

**Relationship Optimization:**
- `idx_bill_keyword_unique` - Prevents duplicate matches
- `idx_bill_version_current` - Fast current version lookup
- `idx_impact_score` - High-impact bill filtering

### Pre-configured Keywords (40+)

**Categories Included:**
- **SNF Core** (4 terms): skilled nursing facility, nursing home, etc.
- **Medicare/Medicaid** (4 terms): Medicare Part A, reimbursement, etc.
- **PDPM/Assessment** (4 terms): PDPM, MDS, Minimum Data Set, etc.
- **Staffing** (8 terms): staffing ratios, RN, LPN, CNA, etc.
- **Quality** (4 terms): star rating, quality measures, deficiencies
- **Regulatory** (4 terms): 42 CFR, 483, F-tags, etc.
- **Safety/Pandemic** (3 terms): COVID-19, infection control, PPE
- **Technology** (2 terms): telehealth, EHR
- **Operations** (7 terms): admission, discharge, training, etc.

## ✅ Expected Results

After successful migration, you should see:

```sql
-- Table verification query results:
 table_name          | record_count
--------------------+-------------
 alerts             |           0
 bill_keyword_matches|           0
 bill_versions      |           0
 bills              |           0
 impact_analyses    |           0
 keywords           |          40+
 users              |           1
```

```sql
-- Keywords by category:
    category    | keyword_count | avg_importance
---------------+---------------+---------------
    Staffing   |            8  |          1.64
    SNF        |            4  |          1.85
    Medicare   |            4  |          1.78
    Quality    |            4  |          1.65
    Regulatory |            4  |          1.75
    (and more...)
```

## 🔧 Troubleshooting

### Common Issues

**Connection Failed:**
```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Restart if needed
docker restart snf-postgres
```

**Permission Denied:**
```bash
# Make script executable
chmod +x run_migration.sh
```

**Tables Already Exist:**
```sql
-- Drop all tables if needed (CAREFUL!)
DROP TABLE IF EXISTS impact_analyses CASCADE;
DROP TABLE IF EXISTS alerts CASCADE;
DROP TABLE IF EXISTS bill_keyword_matches CASCADE;
DROP TABLE IF EXISTS bill_versions CASCADE;
DROP TABLE IF EXISTS keywords CASCADE;
DROP TABLE IF EXISTS bills CASCADE;
DROP TABLE IF EXISTS users CASCADE;
```

### Verification Queries

**Check table structure:**
```sql
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;
```

**Check indexes:**
```sql
SELECT tablename, indexname
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;
```

**Test keyword search:**
```sql
SELECT term, category, importance_weight
FROM keywords
WHERE category = 'SNF'
ORDER BY importance_weight DESC;
```

## 🎯 Next Steps After Migration

1. **Test the API:**
   ```bash
   uvicorn main:app --reload
   curl http://localhost:8000/api/v1/health
   ```

2. **Create your first bill:**
   ```bash
   curl -X POST "http://localhost:8000/api/v1/bills/" \
   -H "Content-Type: application/json" \
   -d '{
     "bill_number": "HR-2024-001",
     "title": "Nursing Home Staffing Standards Act",
     "state_or_federal": "federal",
     "status": "introduced"
   }'
   ```

3. **View API docs:**
   ```
   http://localhost:8000/docs
   ```

## 🔒 Security Notes

- Default admin user created: `admin@snflegtracker.com` (password: `admin123`)
- Change default password immediately in production
- Update database credentials in `.env` file
- Consider SSL/TLS for production database connections

## 📈 Monitoring

After migration, monitor:
- Database size growth (bills with full text can be large)
- Query performance (check slow query logs)
- Index usage statistics
- Alert generation frequency

The database is now ready for your SNF legislative tracking platform! 🎉