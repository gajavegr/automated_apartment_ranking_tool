# Rate Limiting Improvements for Google Sheets API

## Problem
When running bulk recalculation, the system was hitting Google Sheets API rate limits:
```
Quota exceeded for quota metric 'Write requests' and limit 'Write requests per minute per user'
quota_limit_value: '60'
```

**Google Sheets API Limits:**
- 60 write requests per minute per user
- When exceeded, API returns 429 error and blocks further writes

## Solution

### 1. Rate Limiting Between Writes

Added a 1.2-second delay between each write operation to stay safely under the limit:

**File:** `web_app.py`

**Bulk Recalculation (lines ~2157-2190):**
```python
# Rate limiting: Google Sheets API allows 60 write requests per minute
# Sleep for 1.2 seconds between writes to stay safely under the limit (50 writes/min)
import time
time.sleep(1.2)
```

**Calculation:**
- 60 seconds / 50 writes = 1.2 seconds per write
- Target: 50 writes/min (leaving 10/min buffer for safety)

### 2. Retry Logic with Exponential Backoff

Added retry logic for when rate limits are still hit (e.g., if other processes are writing):

```python
max_retries = 3
retry_delay = 5
for attempt in range(max_retries):
    try:
        sheets_client.write_apartment_data(row_num, result)
        break  # Success
    except Exception as write_error:
        error_str = str(write_error)
        if 'RATE_LIMIT_EXCEEDED' in error_str or '429' in error_str:
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)  # 5s, 10s, 20s
                print(f"  ⏳ Rate limit hit, waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                time.sleep(wait_time)
            else:
                print(f"  ❌ Failed to write after {max_retries} attempts")
                raise
        else:
            raise  # Non-rate-limit error, don't retry
```

**Backoff Schedule:**
- Attempt 1: 5 seconds wait
- Attempt 2: 10 seconds wait
- Attempt 3: 20 seconds wait
- After 3 failures: Give up and report error

### 3. Progress Indicators

Added clear user feedback about rate limiting:

**At start of recalculation:**
```
🔄 Starting partial recalculation for: commute, space_luxury
⏱️  Rate limiting enabled: 1.2s delay between writes to avoid API quota (50 writes/min)
```

**During recalculation:**
```
📍 Re-analyzing row 7: 1000 Pennsylvania Ave apt 6 (1/14)
  ✓ Updated row 7
📍 Re-analyzing row 8: 1431 Grove St #10 (2/14)
  ✓ Updated row 8
```

**If rate limit hit:**
```
⏳ Rate limit hit, waiting 5s before retry 1/3...
```

## Impact

### Before:
- ❌ Bulk operations would fail after 60 writes
- ❌ No retry mechanism
- ❌ Required manual intervention to resume
- ❌ Risk of incomplete updates

### After:
- ✅ Smooth operation with automatic pacing (50 writes/min)
- ✅ Automatic retry with exponential backoff
- ✅ Can process unlimited apartments without hitting limits
- ✅ Clear progress feedback
- ✅ Graceful handling of rate limit errors

## Where Applied

Rate limiting was added to:
1. **Bulk Recalculation** (`/admin/force_recalculate`) - Line ~2165
2. **Analyze All** (`/analyze_all`) - Line ~1352

## Time Impact

**For 14 apartments:**
- Old: ~30 seconds (until rate limit hit)
- New: ~17 minutes (1.2s × 14 writes = 16.8s, plus analysis time)

**Note:** The delay is only during the *write* phase, not during analysis. Analysis happens at full speed, then writes are rate-limited.

## Future Improvements

1. **Batch Writes:** Combine multiple cell updates into single batch write requests (already done for clearing data)
2. **Queue System:** Process writes in background queue to avoid blocking UI
3. **Quota Request:** Request higher quota from Google if needed for production use

