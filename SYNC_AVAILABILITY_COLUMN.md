# Syncing Availability Status Column to Google Sheet

## Summary
The `Availability Status` column has been added to the codebase but needs to be added to your Google Sheet.

## Current Status
✅ **Code Updated**:
- `config.py` - Column definition added
- `utils/google_sheets.py` - Column included in sheet initialization
- `manage_sheet_columns.py` - Column added to expected columns list
- `templates/entry_form.html` - Form field added
- `web_app.py` - Backend handling added
- `preferences/web_routes.py` - Filtering logic added

❌ **Google Sheet**: Column not yet added (detected by `manage_sheet_columns.py --check`)

## How to Sync

### Option 1: Preview Changes First (Recommended)
```bash
python manage_sheet_columns.py --sync --dry-run
```
This will show you what will be done without making any changes.

### Option 2: Add the Column
```bash
python manage_sheet_columns.py --sync
```
This will:
1. Add the "Availability Status" column after the "Address" column (Column C)
2. Set default value of "Available" for all existing apartments
3. Format the header with bold text and blue background

### Option 3: Verify After Sync
```bash
python manage_sheet_columns.py --check
```
This will confirm that all columns are now in sync.

## What Happens When You Sync

1. **New Column Created**: "Availability Status" will be inserted as Column C
2. **Existing Data Preserved**: All your apartment data will remain intact
3. **Default Values Set**: All existing apartments will be marked as "Available"
4. **Column Formatted**: Header will be formatted to match other columns

## Column Details

- **Name**: Availability Status
- **Position**: Column C (after Address, before Price)
- **Values**: 
  - ✅ Available (default)
  - ⏳ Pending
  - ❌ Rented
  - 🚫 Listing Removed
- **Purpose**: Track which apartments are still on the market

## Testing After Sync

1. **Verify Column Exists**:
   - Open your Google Sheet
   - Check that "Availability Status" appears as Column C
   - Verify all existing apartments show "Available"

2. **Test Form Entry**:
   - Start the web app: `python web_app.py`
   - Go to the Entry tab
   - Load an existing apartment
   - You should see the "Availability Status" dropdown
   - Change the status and save
   - Verify the change appears in the Google Sheet

3. **Test Evaluation Filtering**:
   - Mark one apartment as "Rented"
   - Go to Preferences tab → Evaluate
   - Run an evaluation
   - Verify the rented apartment is NOT included in results
   - Check the API response shows:
     - `total_apartments`: Total count (e.g., 14)
     - `available_apartments`: Count excluding unavailable (e.g., 13)
     - `unavailable_count`: Count of unavailable apartments (e.g., 1)

## Troubleshooting

### If sync fails:
1. Check your internet connection
2. Verify Google Sheets credentials are valid
3. Ensure you have edit permissions on the sheet
4. Try running with `--dry-run` first to see if there are any errors

### If column appears in wrong position:
- The tool should insert it correctly as Column C
- If it's in the wrong place, you can manually move it in Google Sheets
- Then run `--check` again to verify

### If existing apartments don't have default values:
- The sync tool only sets defaults for rows with addresses
- Empty rows are skipped
- You can manually set values in Google Sheets if needed

## Notes

- **Safe Operation**: The sync tool only adds missing columns, it doesn't delete or modify existing data
- **Idempotent**: You can run sync multiple times safely - it won't duplicate columns
- **Column Order**: The new column follows the order defined in `config.py` and `_initialize_main_sheet()`

---

**Ready to sync?** Run: `python manage_sheet_columns.py --sync`

Generated: December 8, 2024

