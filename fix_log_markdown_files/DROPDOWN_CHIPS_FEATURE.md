# Google Sheets Dropdown Chips Feature

## Overview

The Google Sheets initialization now automatically sets up **dropdown data validation with chips** for columns that store multi-select data from the web form. This provides a cleaner, more user-friendly interface for viewing and editing apartment data directly in the spreadsheet.

## What Are Dropdown Chips?

Dropdown chips are Google Sheets' visual representation of dropdown fields. When you click on a cell with dropdown validation:
- A dropdown arrow appears
- You can select from predefined values
- The selected value appears as a clean, styled chip
- You can still enter custom values (like comma-separated lists)

## Columns with Dropdown Validation

The following columns now have dropdown chips configured:

### 1. **Parking Type** (Column X)
Options:
- `single_garage`
- `dedicated_spot_car_and_motorcycle`
- `dedicated_spot_car_only`
- `street_parking`
- `none`

### 2. **Parking Enclosure** (Column Y)
Options:
- `enclosed` (Garage/Underground)
- `covered` (Carport/Overhang)
- `open` (Outdoor/Exposed)

### 3. **Laundry Type** (Column AB)
Options:
- `in_unit`
- `shared_good`
- `shared_poor`
- `none`

### 4. **Floor Level** (Column AC)
Options:
- `ground`
- `mid`
- `high`

### 5. **Study Door Type** (Column R)
Options:
- `hinged`
- `sliding`
- `none`

## Data Format

### Display Format
When data is entered via the web app, it's stored in a clean, comma-separated format:

**Example:**
```
dedicated_spot_car_only, street_parking
```

Instead of the old JSON format:
```
["dedicated_spot_car_only", "street_parking"]
```

### Editing in Google Sheets

You can edit these fields directly in Google Sheets:

1. **Single Selection**: Click the cell → Select from dropdown
2. **Multiple Values**: Type comma-separated values manually
   - Example: `shared_good, shared_poor`
   - The dropdown will still show available options for reference

### Validation Settings

The dropdown validation is configured as:
- **Type**: List of items
- **Show dropdown**: Yes (displays chip UI)
- **Reject invalid input**: No (allows custom values like comma-separated lists)
- **Show validation help text**: No

This flexible configuration allows:
✅ Quick selection of common values via dropdown  
✅ Manual entry of multiple values (comma-separated)  
✅ Custom values if needed  
✅ Clean visual presentation with chips

## Benefits

1. **Cleaner Display**: No more ugly JSON brackets and quotes
2. **User-Friendly**: Visual dropdown chips are intuitive
3. **Data Validation**: Helps prevent typos and inconsistencies
4. **Flexible**: Still allows custom entries for edge cases
5. **Backward Compatible**: Existing data with JSON format still works

## How It Works

### Initialization
When you run `python main.py init-sheets`, the script:

1. Creates the main data sheet with headers
2. Applies formatting (bold, gray background, freeze header)
3. Calls `_add_dropdown_validations()` which:
   - Finds the column index for each dropdown field
   - Uses Google Sheets API to set data validation rules
   - Configures the dropdown to show as chips
   - Sets `strict=False` to allow custom values

### Code Location

**File**: `utils/google_sheets.py`

**Methods**:
- `_initialize_main_sheet()` - Main initialization
- `_add_dropdown_validations()` - Sets up dropdowns
- `_col_index_to_letter()` - Helper for column conversion

### API Request Format

The dropdowns are created using Google Sheets API's `setDataValidation` request:

```python
{
    "setDataValidation": {
        "range": {
            "sheetId": sheet.id,
            "startRowIndex": 1,  # Row 2 onwards
            "startColumnIndex": col_index,
            "endColumnIndex": col_index + 1
        },
        "rule": {
            "condition": {
                "type": "ONE_OF_LIST",
                "values": [{"userEnteredValue": v} for v in values]
            },
            "showCustomUi": True,  # Enable chip UI
            "strict": False  # Allow custom values
        }
    }
}
```

## Parsing Logic

The scoring engine automatically handles both formats:

**File**: `analyzers/scoring_engine.py`

**Function**: `parse_multi_select(value)`

This function:
1. Checks if value is already a list → returns it
2. Tries parsing as JSON (for old data) → returns parsed list
3. Falls back to comma-separated parsing → splits and trims
4. Returns empty list if all else fails

```python
def parse_multi_select(value: Any) -> List[str]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            # Try JSON parsing (backward compatibility)
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
            return [parsed]
        except (json.JSONDecodeError, ValueError):
            # Parse as comma-separated string
            if ',' in value:
                return [item.strip() for item in value.split(',') if item.strip()]
            return [value] if value else []
    return []
```

## Usage Examples

### Example 1: Uncertain Parking Type
**Scenario**: Listing shows "parking available" but unclear if dedicated or street

**Web Form Entry**:
- Check: ✅ Dedicated Spot (Car Only)
- Check: ✅ Street Parking
- Check: ✅ Mark as tour question

**Google Sheet Display**:
```
Column X (Parking Type): dedicated_spot_car_only, street_parking
Column [Tour Questions]: Parking type
```

**Dropdown View**: 
- Click cell → See dropdown with all options
- Can select from list or edit manually

### Example 2: Shared Laundry Ratio Unknown
**Scenario**: Listing shows shared laundry but no machine count

**Web Form Entry**:
- Check: ✅ Shared (Good Ratio)
- Check: ✅ Shared (Poor Ratio)
- Check: ✅ Mark as tour question

**Google Sheet Display**:
```
Column AB (Laundry Type): shared_good, shared_poor
Column [Tour Questions]: Laundry type
```

### Example 3: Single Value Selection
**Scenario**: Listing clearly shows in-unit laundry

**Web Form Entry**:
- Check: ✅ In-Unit

**Google Sheet Display**:
```
Column AB (Laundry Type): in_unit
```

**Dropdown View**: Shows as a single chip

## Re-initializing Sheets

If you want to add dropdown validation to existing sheets:

1. The script checks if a sheet is already initialized (by checking first row)
2. It will **skip** re-initialization to preserve data
3. To force re-initialization with dropdowns:
   - Manually delete the sheet in Google Sheets
   - Run `python main.py init-sheets` again

**Note**: This will preserve all other sheets (Scatter Plot, Criteria Matrix, Approved Gyms)

## Troubleshooting

### Dropdowns Not Showing
**Cause**: Sheet may have been initialized before this feature was added

**Solution**: 
1. Back up your data (copy the sheet)
2. Delete the "Apartment Data" sheet
3. Run `python main.py init-sheets`
4. Restore your data by pasting back

### Custom Values Not Working
**Cause**: Validation might be set to `strict=True`

**Solution**: 
- Re-run init script
- Or manually edit validation in Google Sheets:
  - Data → Data validation → Reject input: OFF

### Comma-Separated Values Not Parsing
**Cause**: Extra spaces or special characters

**Solution**: 
- Ensure format is: `value1, value2` (with spaces after commas)
- No special characters except commas
- No trailing commas

## Future Enhancements

Potential improvements for this feature:

1. **Multi-Select Chips**: Google Sheets doesn't natively support selecting multiple chips from a dropdown, but we could add a custom UI
2. **Conditional Validation**: Different dropdown options based on other column values
3. **Color-Coded Chips**: Visual indicators for different types of values
4. **Auto-Complete**: Suggest previously used combinations
5. **Validation Hints**: Show helper text in cells with dropdown validation

## Technical Notes

- **API Quota**: Each dropdown creation uses 1 write request
- **Performance**: Validation is applied to entire columns (rows 2-1000)
- **Sheet ID**: Retrieved automatically via gspread
- **Column Detection**: Uses header matching to find column indices
- **Error Handling**: Graceful fallback if column not found or API fails

## Related Documentation

- [SCORE_RANGE_FEATURE.md](SCORE_RANGE_FEATURE.md) - How score ranges work with multi-select data
- [WEB_INTERFACE_GUIDE.md](WEB_INTERFACE_GUIDE.md) - How to use the web form
- [README.md](README.md) - General setup and usage

