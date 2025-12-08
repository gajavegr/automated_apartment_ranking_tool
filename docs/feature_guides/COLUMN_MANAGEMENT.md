# Sheet Column Management Guide

## Overview

The `manage_sheet_columns.py` tool automatically syncs your Google Sheet structure with the `config.py` SHEET_COLUMNS definition. This makes it easy to add, remove, or reorder columns without manual work or custom scripts.

## Quick Start

### Check for Differences

See what's different between your sheet and config:

```bash
python manage_sheet_columns.py --check
```

### Add Missing Columns

Automatically add any columns defined in config but missing from the sheet:

```bash
python manage_sheet_columns.py --sync
```

### Preview Changes (Dry Run)

See what would happen without making changes:

```bash
python manage_sheet_columns.py --sync --dry-run
```

## How It Works

### 1. **Check Mode** (`--check`)
- Compares current sheet columns with `config.py` definition
- Reports:
  - ❌ **Missing columns**: In config but not in sheet
  - ⚠️ **Extra columns**: In sheet but not in config
  - ⚠️ **Misplaced columns**: Present but in wrong order
- Safe to run anytime - makes no changes

### 2. **Sync Mode** (`--sync`)
- Adds missing columns in the correct positions
- Sets proper header formatting (blue background, white text, bold)
- Fills existing rows with sensible defaults (only for rows with addresses):
  - `0` for cost/score fields
  - Empty string for text fields
- **Preserves all existing data**
- **Smart defaults**: Only adds default values to rows with addresses (primary key), preventing hundreds of empty rows from being filled

### 3. **Dry Run Mode** (`--dry-run`)
- Shows exactly what would be done
- Makes no actual changes
- Use this to preview before syncing

## Workflow for Adding New Columns

### Step 1: Update Config

Add your new column to `config.py` SHEET_COLUMNS:

```python
SHEET_COLUMNS = {
    # ... existing columns ...
    "parking_cost": "Parking Cost ($/month)",
    # ... more columns ...
}
```

### Step 2: Update Column Order

Add the column to the expected order in `utils/google_sheets.py` `_initialize_main_sheet()`:

```python
headers = [
    # ... existing headers ...
    config.SHEET_COLUMNS["parking_distance"],
    config.SHEET_COLUMNS["parking_cost"],  # New column
    config.SHEET_COLUMNS["street_parking_ease"],
    # ... more headers ...
]
```

**OR** update the `get_expected_columns()` method in `manage_sheet_columns.py` to match.

### Step 3: Check Differences

```bash
python manage_sheet_columns.py --check
```

You should see your new column listed under "MISSING COLUMNS".

### Step 4: Preview the Sync

```bash
python manage_sheet_columns.py --sync --dry-run
```

Review the output to ensure it will add the column in the right place.

### Step 5: Sync the Sheet

```bash
python manage_sheet_columns.py --sync
```

Done! Your sheet now has the new column with proper formatting and default values (only for rows with addresses).

### Step 6: Update Your Code

Add the column to:
- Form fields in `templates/entry_form.html`
- Backend handlers in `web_app.py`
- Column mappings in `utils/google_sheets.py` `write_apartment_data()`
- Any other relevant places

## Example Output

### Check Mode
```
======================================================================
SHEET COLUMN ANALYSIS
======================================================================

Expected columns: 42
Current columns:  41

❌ MISSING COLUMNS (1):
   • Parking Cost ($/month)
     Should be after: Parking Distance

✅ No extra columns
✅ All columns in correct order

======================================================================

💡 TIP: Run with --sync to add missing columns
```

### Sync Mode
```
Adding 1 missing column(s)...

  Adding: Parking Cost ($/month)
    Position: 26 (column Z)
    ✓ Added successfully

✅ Successfully added 1 column(s)!
   Run with --check to verify changes.
```

## Safety Features

### ✅ What's Safe
- **Adding columns**: Inserts new columns without affecting existing data
- **Default values**: Automatically fills existing rows with sensible defaults
- **Multiple runs**: Safe to run multiple times (idempotent)
- **Dry run**: Preview changes before applying

### ⚠️ What to Be Careful With
- **Reordering**: Column reordering is intentionally not implemented for safety
  - Manually reorder in Google Sheets if needed
  - The tool will detect and report misplaced columns
- **Extra columns**: The tool reports but doesn't delete extra columns
  - Manually remove unused columns if desired

## Common Scenarios

### Scenario 1: Adding a New Feature Field

1. Add to `config.SHEET_COLUMNS`
2. Add to expected column order
3. Run `python manage_sheet_columns.py --sync`
4. Update form and backend code

### Scenario 2: Renaming a Column

1. Update the value in `config.SHEET_COLUMNS`
2. Run `--check` to see it as missing
3. Manually rename in Google Sheets (safer than delete + add)
4. Run `--check` again to verify

### Scenario 3: Removing a Column

1. Remove from `config.SHEET_COLUMNS`
2. Run `--check` to see it as extra
3. Manually delete from Google Sheets
4. Remove from all code references

### Scenario 4: Fresh Sheet Setup

If starting from scratch:
```bash
python main.py --init-sheets
```

This creates a new sheet with all columns in the correct order.

## Troubleshooting

### "Column not found in sheet"
- The sheet might be completely empty
- Run `python main.py --init-sheets` for a fresh setup

### "Extra columns detected"
- These are columns in your sheet not defined in config
- Likely old/deprecated columns
- Manually remove them if no longer needed

### "Misplaced columns"
- Columns exist but are in wrong order
- Usually not a problem for functionality
- Manually reorder in Google Sheets if desired

## Best Practices

1. **Always check first**: Run `--check` before `--sync`
2. **Use dry run**: Preview changes with `--dry-run`
3. **Backup your sheet**: Make a copy before major changes
4. **Update config first**: Always update config before syncing
5. **Test with one apartment**: After adding columns, test with one entry first

## Integration with Development Workflow

```bash
# 1. Pull latest code
git pull

# 2. Check if sheet needs updates
python manage_sheet_columns.py --check

# 3. Sync if needed
python manage_sheet_columns.py --sync

# 4. Continue development
python web_app.py
```

## Future Enhancements

Potential features for this tool:
- [ ] Column reordering (currently intentionally disabled)
- [ ] Automatic column type detection
- [ ] Migration scripts for data transformations
- [ ] Backup/restore functionality
- [ ] Column usage analytics

