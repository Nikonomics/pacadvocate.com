# 🏛️ Congress.gov API Data Collector

## Overview

The SNFLegTracker now includes a comprehensive Congress.gov API data collector that automatically searches for and collects legislative bills using your seeded keywords. The system includes rate limiting, authentication, automated scheduling, and integration with your existing keyword matching and impact analysis systems.

## 🔧 Features

### ✅ Congress.gov API Client
- **Rate Limiting**: Respects 5,000 requests/hour limit
- **Authentication**: API key management
- **Error Handling**: Robust error recovery and logging
- **Search Capabilities**: Multi-keyword search with deduplication

### ✅ Bill Collector Service
- **Keyword Integration**: Uses your seeded SNF keywords automatically
- **Database Storage**: Stores bills in your existing database schema
- **Automatic Processing**: Keyword matching and impact analysis
- **Duplicate Prevention**: Prevents duplicate bill storage

### ✅ Scheduled Collection
- **Daily Collection**: Recent bills and high-priority SNF bills
- **Weekly Comprehensive**: Full keyword-based collection
- **Business Hours**: Light collection during 9 AM - 5 PM
- **Logging**: Comprehensive collection logging

## 🚀 Setup Instructions

### 1. Get Congress.gov API Key

1. **Sign up** at: https://api.congress.gov/sign-up/
2. **Verify your email** address
3. **Receive your API key** (usually instant)

### 2. Configure API Key

```bash
# Option 1: Environment Variable (Recommended)
export CONGRESS_API_KEY="your_api_key_here"

# Option 2: Add to .env file
echo "CONGRESS_API_KEY=your_api_key_here" >> .env

# Option 3: Pass directly to scripts
python services/collectors/bill_collector.py --api-key "your_api_key_here"
```

### 3. Test the Connection

```bash
# Test API connection and basic functionality
python test_congress_collector.py

# Test specific collector functions
python services/collectors/bill_collector.py --test
```

## 📊 Usage Examples

### Manual Bill Collection

```bash
# Collect SNF-specific bills from 2024-2025
python services/collectors/bill_collector.py --snf-only --year 2025

# Collect all bills using seeded keywords
python services/collectors/bill_collector.py --congress 119

# Collect recent bills (last 7 days)
python services/collectors/bill_collector.py --days 7

# Show collection statistics
python services/collectors/bill_collector.py --stats
```

### Scheduled Collection

```bash
# Start continuous scheduler (runs in background)
python services/collectors/scheduler.py --run

# Run single collection tasks
python services/collectors/scheduler.py --once daily
python services/collectors/scheduler.py --once weekly

# Check scheduler status
python services/collectors/scheduler.py --status
```

## 🔍 Search Keywords Used

The system automatically uses your seeded keywords for collection:

### High-Priority Keywords (Weight ≥ 1.9)
- **skilled nursing facility** (2.0)
- **SNF** (2.0)
- **PDPM** (2.0)
- **staffing ratios** (1.9)
- **nursing home** (1.9)
- **Medicare Part A** (1.9)
- **Five-Star Quality Rating** (1.9)

### Additional Keywords
- Medicare, Medicaid reimbursement
- long-term care, post-acute care
- survey process, Quality Reporting Program
- Plus synonyms for each term

## 📋 Collection Workflow

### 1. **Keyword Search**
```
Search Congress.gov API → Rate Limited Requests → Parse Results
```

### 2. **Data Processing**
```
Bill Data → Database Storage → Keyword Matching → Impact Analysis
```

### 3. **Automated Tasks**
```
Daily: Recent + SNF bills
Weekly: Comprehensive collection
Hourly: Light updates (business hours)
```

## 🎯 API Rate Limits & Performance

- **Rate Limit**: 5,000 requests/hour (83/minute)
- **Automatic Rate Limiting**: Built-in throttling
- **Request Batching**: Efficient keyword searching
- **Duplicate Prevention**: Smart deduplication

### Expected Performance:
- **~8 keywords** per search cycle
- **~50-200 bills** per keyword
- **~400-1600 bills** per full collection
- **~60-90 minutes** for comprehensive weekly collection

## 📊 Monitoring & Logging

### Log Files
```bash
# View collection logs
tail -f bill_collection.log

# Check for errors
grep "ERROR" bill_collection.log
```

### Database Statistics
```bash
# Get current stats
python services/collectors/bill_collector.py --stats

# Check recent collections
sqlite3 snflegtracker.db "SELECT COUNT(*) FROM bills WHERE created_at > datetime('now', '-7 days');"
```

## 🔧 Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CONGRESS_API_KEY` | Congress.gov API key | Required |
| `DATABASE_URL` | Database connection | SQLite local |
| `LOG_LEVEL` | Logging level | INFO |

### Collection Settings

```python
# Customize in bill_collector.py
RATE_LIMIT = 4800  # requests per hour
MIN_IMPORTANCE = 1.5  # keyword importance threshold
MAX_RESULTS_PER_KEYWORD = 50  # API results limit
```

## 🧪 Testing & Validation

### Test Without API Key
```bash
python test_congress_collector.py
# Runs in demo mode, shows expected workflow
```

### Test With API Key
```bash
export CONGRESS_API_KEY="your_key"
python test_congress_collector.py
# Tests actual API calls and functionality
```

### Validate Collections
```bash
# Check database for new bills
python query_database.py

# Verify keyword matching worked
sqlite3 snflegtracker.db "SELECT COUNT(*) FROM bill_keyword_matches;"
```

## 🔍 Sample Search Results

With your API key, the system will search for bills like:

**Example: "skilled nursing facility" search might return:**
- H.R. 2025-1234: "Nursing Home Staffing Standards Act"
- S. 2025-567: "Medicare SNF Payment Reform Act"
- H.R. 2025-890: "Long-Term Care Quality Improvement Act"

Each bill gets:
- ✅ Stored in your database
- ✅ Matched against all 19 keywords
- ✅ Impact analysis generated
- ✅ Alerts created for high-confidence matches

## 🚨 Troubleshooting

### Common Issues

**API Key Not Working:**
```bash
# Verify key is set
echo $CONGRESS_API_KEY

# Test connection
curl "https://api.congress.gov/v3/bill/119?api_key=$CONGRESS_API_KEY&limit=1"
```

**Rate Limit Errors:**
- System automatically handles rate limits
- Check logs for rate limit status
- Consider reducing collection frequency

**No Bills Found:**
- Verify keywords are in database: `python query_database.py`
- Check API key permissions
- Try different Congress numbers (118, 119)

**Database Errors:**
- Check database connection in `.env`
- Run migrations if needed: `python create_tables.py`

## 🎯 Next Steps

1. **Get API Key**: https://api.congress.gov/sign-up/
2. **Test Connection**: `python test_congress_collector.py`
3. **Run First Collection**: `python services/collectors/bill_collector.py --snf-only`
4. **Start Scheduler**: `python services/collectors/scheduler.py --run`
5. **Monitor Results**: Check logs and database

Your SNFLegTracker is now ready to automatically collect and analyze skilled nursing facility legislation from Congress! 🎉