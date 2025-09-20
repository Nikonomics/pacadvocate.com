# 🏛️ LegiScan API Integration for State Legislation

## Overview

The SNFLegTracker now includes a comprehensive LegiScan API integration that automatically searches for and collects state legislation using your seeded keywords. The system focuses on Idaho legislation initially but is designed for easy multi-state expansion.

## 🔧 Features

### ✅ LegiScan API Client
- **Rate Limiting**: Respects 30,000 requests/month basic plan (1,000/day)
- **Authentication**: API key management
- **Multi-State Support**: Currently configured for Idaho (ID=23) with easy expansion
- **Error Handling**: Robust error recovery and logging
- **Search Capabilities**: Healthcare-specific keyword searches

### ✅ Idaho Legislature Focus
- **Targeted Keywords**: "nursing facility", "skilled nursing", "assisted living", "Medicaid", "staffing", "long-term care"
- **Bill Details**: Full text, sponsors, committee assignments, vote history
- **Database Storage**: Stores bills with source='legiscan' and state_or_federal='ID'
- **Keyword Matching**: Automatic matching with existing SNF keywords

### ✅ Multi-State Configuration
- **Easy Expansion**: Pre-configured for CA, WA, OR, NV, MT, UT, WY
- **State-Specific Keywords**: Customizable search terms per state
- **Enable/Disable**: Individual state monitoring control
- **Scalable Architecture**: Ready for nationwide expansion

## 🚀 Setup Instructions

### 1. Get LegiScan API Key

1. **Sign up** at: https://legiscan.com/legiscan
2. **Choose API plan**: Basic (30,000 requests/month) or higher
3. **Receive API key** via email
4. **Verify access** to state data

### 2. Configure API Key

```bash
# Option 1: Environment Variable (Recommended)
export LEGISCAN_API_KEY="your_api_key_here"

# Option 2: Add to .env file
echo "LEGISCAN_API_KEY=your_api_key_here" >> .env

# Option 3: Pass directly to scripts
python services/collectors/legiscan_collector.py --api-key "your_api_key_here"
```

### 3. Test the Connection

```bash
# Test API connection and basic functionality
python3 services/collectors/legiscan_collector.py --test

# Test Idaho healthcare bill search
python3 services/collectors/legiscan_collector.py --state ID --limit 5
```

## 📊 Usage Examples

### Manual Bill Collection

```bash
# Collect Idaho SNF-related bills from 2024
python3 services/collectors/legiscan_collector.py --state ID --year 2024 --limit 25

# Collect with full details (text, sponsors, votes)
python3 services/collectors/legiscan_collector.py --state ID --details --limit 10

# Show collection statistics
python3 services/collectors/legiscan_collector.py --stats
```

### Scheduled Collection

```bash
# Start continuous scheduler (runs in background)
python3 services/collectors/legiscan_scheduler.py --run

# Run single collection tasks
python3 services/collectors/legiscan_scheduler.py --once daily
python3 services/collectors/legiscan_scheduler.py --once weekly

# Check scheduler status
python3 services/collectors/legiscan_scheduler.py --status
```

### Multi-State Management

```bash
# Add California to monitoring
python3 services/collectors/legiscan_scheduler.py --add-state CA

# Remove state from monitoring
python3 services/collectors/legiscan_scheduler.py --remove-state CA
```

## 🎯 Search Keywords Used

The system uses targeted healthcare keywords for each state:

### Idaho Priority Keywords
- **nursing facility**
- **skilled nursing**
- **assisted living**
- **Medicaid**
- **staffing**
- **long-term care**

### Additional Healthcare Terms
- nursing home, healthcare, patient safety
- quality assurance, certification, licensing
- Medicare, reimbursement

## 📋 Data Collection Workflow

### 1. **Search Process**
```
LegiScan API Search → Rate Limited Requests → Parse Results → Filter Healthcare Bills
```

### 2. **Data Mapping**
```
LegiScan Bill Data → Bills Table Mapping → Database Storage → Keyword Matching
```

### 3. **Bill Processing**
```
Basic Info → Full Text → Sponsors → Committees → Vote History → Storage
```

## 🔍 LegiScan Data Structure Mapping

| LegiScan Field | Bills Table Field | Notes |
|----------------|-------------------|-------|
| `bill_number` | `bill_number` | Direct mapping |
| `title` | `title` | Bill title |
| `description` | `summary` | Bill description/summary |
| `bill_id` | Stored in metadata | LegiScan unique ID |
| `session_id` | Stored in metadata | Legislative session |
| `url` | Stored in metadata | LegiScan bill URL |
| `state_link` | Stored in metadata | State legislature URL |
| `sponsors` | `sponsor` | Primary sponsor name |
| `progress` | `status` | Current status |
| `introduced` | `introduced_date` | Introduction date |
| `last_action_date` | `last_action_date` | Last action date |
| N/A | `source` | Set to 'legiscan' |
| N/A | `state_or_federal` | Set to state code (e.g., 'ID') |
| N/A | `chamber` | Determined from bill number |

## 🎯 API Rate Limits & Performance

- **Rate Limit**: 30,000 requests/month basic plan (~1,000/day)
- **Automatic Rate Limiting**: Built-in throttling to stay within limits
- **Request Optimization**: Efficient keyword searching
- **Duplicate Prevention**: Smart deduplication by bill_id

### Expected Performance:
- **~6 keywords** per search cycle for Idaho
- **~10-50 bills** per keyword (varies by topic)
- **~60-300 bills** per full collection
- **~30-60 minutes** for comprehensive weekly collection

## 📊 Monitoring & Logging

### Log Files
```bash
# View collection logs
tail -f legiscan_scheduler.log

# Check for errors
grep "ERROR" legiscan_scheduler.log
```

### Database Statistics
```bash
# Get current stats
python3 services/collectors/legiscan_collector.py --stats

# Check Idaho bills specifically
python3 services/collectors/legiscan_collector.py --stats --state ID
```

## 🔧 Multi-State Configuration

### Currently Supported States
- **Idaho (ID)**: Enabled by default
- **California (CA)**: Configured, disabled
- **Washington (WA)**: Configured, disabled
- **Oregon (OR)**: Configured, disabled
- **Nevada (NV)**: Configured, disabled
- **Montana (MT)**: Configured, disabled
- **Utah (UT)**: Configured, disabled
- **Wyoming (WY)**: Configured, disabled

### Adding New States

```python
# In legiscan_collector.py, add to STATE_CONFIG
'TX': {
    'name': 'Texas',
    'priority_keywords': [
        'nursing facility', 'skilled nursing', 'assisted living',
        'Medicaid', 'staffing', 'long-term care'
    ],
    'enabled': True
}
```

### State-Specific Keywords

```python
# Customize keywords per state in STATE_CONFIG
'CA': {
    'name': 'California',
    'priority_keywords': [
        'nursing facility', 'skilled nursing', 'assisted living',
        'Medicaid', 'Medi-Cal',  # California-specific
        'staffing', 'long-term care'
    ],
    'enabled': False
}
```

## 📅 Scheduled Collection

### Daily Collection (8:00 AM)
- Recent healthcare bills
- Small batch size (10 bills per state)
- Basic information only
- All monitored states

### Weekly Comprehensive (Monday 7:00 AM)
- Full year's legislation
- Larger batch size (50 bills per state)
- Complete details including full text
- Sponsors, committees, vote history

### Monthly Multi-State Scan
- Scans non-monitored states
- Identifies expansion opportunities
- No database storage, just analysis

## 🧪 Testing & Validation

### Test Without API Key
```bash
python3 services/collectors/legiscan_collector.py --test
# Shows expected workflow and error handling
```

### Test With API Key
```bash
export LEGISCAN_API_KEY="your_key"
python3 services/collectors/legiscan_collector.py --test
# Tests actual API calls and functionality
```

### Sample Idaho Healthcare Bill Search
```bash
# Search for Medicaid bills in Idaho
python3 services/collectors/legiscan_collector.py --state ID --year 2024 --limit 5
```

## 🚨 Troubleshooting

### Common Issues

**API Key Not Working:**
```bash
# Verify key is set
echo $LEGISCAN_API_KEY

# Test connection manually
curl "https://api.legiscan.com/?key=$LEGISCAN_API_KEY&op=getSessionList&state=23"
```

**Rate Limit Errors:**
- System automatically handles rate limits
- Check logs for rate limit status
- Consider upgrading API plan if needed

**No Bills Found:**
- Verify keywords are appropriate for state
- Check if legislature is in session
- Try different years or broader terms

**Database Errors:**
- Check database connection in `.env`
- Verify Bills table exists
- Run migrations if needed

## 🎯 Sample Expected Results

With your API key, the system will search Idaho for bills like:

**Example: "Medicaid" search in Idaho might return:**
- H.B. 123: "Medicaid Provider Enrollment and Revalidation Act"
- S.B. 456: "Long-term Care Services and Supports Amendment"
- H.B. 789: "Nursing Facility Quality Assurance Program"

Each bill gets:
- ✅ Stored in database with source='legiscan'
- ✅ Matched against all SNF keywords
- ✅ Full metadata including sponsors and committees
- ✅ Integration with existing alert system

## 🔍 API Endpoints Used

| Endpoint | Purpose | Rate Impact |
|----------|---------|-------------|
| `getSessionList` | Get available sessions | Low (1 per state) |
| `search` | Search bills by keyword | Medium (1 per keyword) |
| `getBill` | Get detailed bill info | High (1 per bill) |
| `getBillText` | Get bill full text | High (1 per text version) |
| `getSupplement` | Get votes/committees | Medium (1 per supplement) |
| `getSponsor` | Get sponsor details | Low (1 per unique sponsor) |

## 🚀 Next Steps

1. **Get API Key**: https://legiscan.com/legiscan
2. **Test Connection**: `python3 services/collectors/legiscan_collector.py --test`
3. **Run First Collection**: `python3 services/collectors/legiscan_collector.py --state ID`
4. **Enable Additional States**: Modify STATE_CONFIG as needed
5. **Start Scheduler**: `python3 services/collectors/legiscan_scheduler.py --run`
6. **Monitor Results**: Check logs and database

Your SNFLegTracker is now ready to automatically collect and analyze Idaho state legislation related to skilled nursing facilities! 🎉

## 💡 Advanced Configuration

### Custom Keyword Sets
Create state-specific keyword profiles based on local terminology and legislative patterns.

### Rate Limit Optimization
- Monitor API usage patterns
- Adjust collection frequency based on legislative calendar
- Implement priority queuing for high-importance bills

### Data Enhancement
- Cross-reference with federal legislation
- Track bill relationships and amendments
- Analyze voting patterns and sponsor networks

The LegiScan integration provides a solid foundation for comprehensive state-level legislative monitoring with room for sophisticated enhancements as your needs grow.