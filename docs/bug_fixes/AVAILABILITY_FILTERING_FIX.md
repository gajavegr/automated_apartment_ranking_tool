# Availability Filtering in Analysis Tab - COMPLETE

## Changes Made

### ✅ Updated `/get_analysis_data` Endpoint
**File**: `web_app.py` (lines 1536-1566)

**Added filtering logic**:
```python
# Get availability column name
availability_col = config.SHEET_COLUMNS.get("availability_status")

for i, r in enumerate(records):
    address = r.get(config.SHEET_COLUMNS['address'], 'Unknown')
    
    # Skip if no address
    if not address or not address.strip():
        continue
    
    # Skip unavailable apartments
    if availability_col:
        status = r.get(availability_col, "").strip().lower()
        if status and status != "available":
            print(f"[DEBUG] Skipping unavailable apartment: {address} (status: {status})")
            continue
```

## What This Fixes

### Before:
- Apartments marked as "Rented", "Pending", or "Listing Removed" still appeared in:
  - ✅ Preferences evaluation tab (already fixed)
  - ❌ Analysis tab ranked apartments table
  - ❌ Scatter plot visualization
  - ❌ Comparison matrix
  - ❌ Apartment dropdown selector

### After:
- Unavailable apartments are now filtered out from:
  - ✅ Preferences evaluation tab
  - ✅ Analysis tab ranked apartments table
  - ✅ Scatter plot visualization
  - ✅ Comparison matrix
  - ✅ Apartment dropdown selector (uses same data source)

## How It Works

1. **Status Check**: Before processing each apartment, checks the "Availability Status" column
2. **Filter Logic**: Only includes apartments with:
   - No status set (defaults to "Available")
   - Explicit "Available" status
3. **Skip Others**: Apartments with "Rented", "Pending", or "Listing Removed" are skipped entirely
4. **Debug Logging**: Logs which apartments are being filtered for troubleshooting

## Testing

### To verify the fix works:

1. **Mark an apartment as unavailable**:
   ```
   - Open web app
   - Go to Entry tab
   - Load "1000 Pennsylvania Ave apt 6"
   - Change status to "Rented"
   - Save
   ```

2. **Check Analysis tab**:
   ```
   - Go to Analysis tab
   - Click "Refresh Data" or reload the page
   - Verify "1000 Pennsylvania Ave apt 6" is NOT in the ranked list
   - Verify it's NOT in the scatter plot
   - Verify it's NOT in the apartment selector dropdown
   ```

3. **Check Preferences tab**:
   ```
   - Go to Preferences → Evaluate
   - Run evaluation
   - Verify the apartment count shows it's excluded
   - Check response shows: unavailable_count: 1
   ```

4. **Re-enable apartment**:
   ```
   - Change status back to "Available"
   - Verify it reappears in all views
   ```

## Status Mapping

The filter treats these statuses as follows:

| Status | Displayed in Analysis? | Displayed in Preferences? |
|--------|----------------------|--------------------------|
| (empty/none) | ✅ Yes (default: Available) | ✅ Yes |
| Available | ✅ Yes | ✅ Yes |
| Pending | ❌ No | ❌ No |
| Rented | ❌ No | ❌ No |
| Listing Removed | ❌ No | ❌ No |

## Debug Output

When an apartment is filtered, you'll see in the console:
```
[DEBUG] Skipping unavailable apartment: 1000 Pennsylvania Ave apt 6, San Francisco, CA 94107, USA (status: rented)
```

## Notes

- **Case Insensitive**: Status comparison is case-insensitive (`"RENTED"` = `"rented"` = `"Rented"`)
- **Whitespace Tolerant**: Strips whitespace from status values
- **Backward Compatible**: Apartments without a status column default to "Available"
- **No Data Loss**: Unavailable apartments are still in the sheet, just hidden from views

## Related Files

- `web_app.py` - Analysis data endpoint (filtering logic)
- `preferences/web_routes.py` - Preferences evaluation endpoint (filtering logic)
- `templates/entry_form.html` - Availability status dropdown UI
- `config.py` - Availability status column definition

---

**Status**: ✅ COMPLETE

The issue where "1000 Pennsylvania Ave apt 6" appeared in the ranked apartments table even when marked as "Rented" is now fixed.

Generated: December 8, 2024

