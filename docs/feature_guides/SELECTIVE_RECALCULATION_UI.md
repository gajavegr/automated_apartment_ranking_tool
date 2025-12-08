# Selective Recalculation UI - Implementation Summary

## Overview
Added a user-friendly interface for selectively recalculating specific score components, giving users granular control over what to recalculate.

## What Was Added

### 1. New UI Component (Admin Tab)
**Location:** Admin tab → Data Recalculation section

**Features:**
- ✅ Checkbox grid for selecting components
- ✅ "All" checkbox that disables others when selected
- ✅ Visual component guide with descriptions
- ✅ Status display showing progress

**Component Options:**
- 🔄 **All** - Full recalculation (disables others when checked)
- 🏋️ **Gym** - Walk/bike times and scores
- 🧺 **Laundry** - Laundry scores
- 🚗 **Parking** - Parking scores  
- 🎉 **Happening** - Restaurant/cafe/park data
- 🛡️ **Safety** - Safety scores
- 🚗 **Commute** - Commute times
- 💻 **WFH Quality** - Work from home scores

### 2. JavaScript Functions

#### `toggleRecalcComponents(allCheckbox)`
- Manages "All" checkbox behavior
- Disables individual component checkboxes when "All" is selected
- Re-enables them when "All" is unchecked

#### `forceSelectedRecalculation()`
- Validates at least one component is selected
- Builds confirmation message with selected components
- Calls `/admin/force_recalculate` with component array
- Runs analysis after clearing
- Shows progress and results

### 3. Backend Support
The backend was already updated to support:
- Array of components: `components: ['gym', 'parking']`
- Backward compatibility with old format
- Detailed response with what was cleared

## User Workflow

### Step 1: Select Components
User checks one or more components:
```
☑️ Gym (Walk/Bike)
☐ Laundry
☑️ Parking
☐ Happening
```

### Step 2: Confirm
Clicks "Clear Selected & Recalculate" button

Shows confirmation:
```
⚠️ This will clear and recalculate: 
Gym (walk/bike times), Parking

For ALL apartments in your sheet.

Manual entries will be preserved.

Are you sure you want to continue?
```

### Step 3: Process
1. Clears selected components for all apartments
2. Runs full analysis to recalculate
3. Shows progress and results

### Step 4: View Results
```
✅ Cleared: gym (walk/bike times), parking
✅ Successfully analyzed 15 apartment(s)
Done! Selected components have been recalculated. Refresh the page to see updates.
```

## Use Cases

### Add Bike Times to Existing Apartments
**Steps:**
1. Check only "Gym" checkbox
2. Click "Clear Selected & Recalculate"
3. Wait for completion
4. Refresh page

**Result:** All apartments now have bike times calculated for gyms >15 min walk

### Update Happening Scores After Excluding Places
**Steps:**
1. Exclude unwanted restaurants/cafes
2. Check only "Happening" checkbox
3. Click "Clear Selected & Recalculate"

**Result:** Happening scores updated without touching other scores

### Multiple Component Update
**Steps:**
1. Check "Gym", "Parking", and "Safety"
2. Click "Clear Selected & Recalculate"

**Result:** Only those three components recalculated

## Benefits

1. **⚡ Faster** - Recalculate only what's needed
2. **💰 Cost-Effective** - Fewer API calls
3. **🎯 Targeted** - Precise control over what changes
4. **👤 User-Friendly** - Clear visual interface
5. **✅ Safe** - Confirmation dialog prevents accidents
6. **📊 Transparent** - Shows exactly what's happening

## Technical Details

### API Call Format
```javascript
{
    components: ['gym', 'parking'],  // Array of component names
    addresses: 'all'                 // Always all for now
}
```

### Response Format
```javascript
{
    success: true,
    cleared_count: 15,
    components: ['gym (walk/bike times)', 'parking'],
    columns: ['Gym Score', 'Gym Walk Time (min)', ...],
    cache_cleared: true,
    message: 'Cleared gym (walk/bike times), parking for 15 apartment(s)...'
}
```

## Gym Score Issue Resolution

### The Problem
Gym scores showing 0.0 because:
1. New gym columns were added but data not recalculated
2. Old column names vs new column names mismatch

### The Solution
1. **Manual rename** (preserves existing data):
   - `Gym Within 20min Walk` → `Gym Within 20min`
   - `Time to Nearest Gym (min)` → `Gym Walk Time (min)`

2. **Use Schema Manager** to add new columns:
   - `Gym Bike Time (min)`
   - `Gym Transport Mode`
   - `Gym Time Used for Score (min)`

3. **Use Selective Recalculation**:
   - Check "Gym" checkbox
   - Click "Clear Selected & Recalculate"
   - System will:
     - Recalculate walking times
     - Add bike times for gyms >15 min walk
     - Set default transport modes
     - Update all gym scores

### After Recalculation
- All apartments will have correct gym scores
- Apartments with gyms >15 min walk will have bike times
- Users can choose walk/bike transport mode
- Scores will reflect chosen transport mode

## Files Modified

1. **templates/entry_form.html**
   - Added checkbox UI for component selection
   - Added `toggleRecalcComponents()` function
   - Updated `forceSelectedRecalculation()` function (new)
   - Updated `forceFullRecalculation()` to use new API format

2. **web_app.py** (already completed)
   - Enhanced `/admin/force_recalculate` endpoint
   - Support for component arrays
   - Granular component clearing

3. **utils/google_sheets.py** (already completed)
   - Added new gym column mappings

4. **manage_sheet_columns.py** (already completed)
   - Added new gym columns to expected schema

## Next Steps for User

1. ✅ Rename the 2 gym columns manually
2. ✅ Run "Sync Schema" to add 3 new columns
3. ✅ Check "Gym" in selective recalculation
4. ✅ Click "Clear Selected & Recalculate"
5. ✅ Wait for completion
6. ✅ Refresh page and verify gym scores are correct
7. ✅ Check apartments with far gyms now show bike times

This gives you full control over when and what to recalculate!





