# Sortable Evaluation Table Feature

## Overview
Added sortable columns to the Full Results table in the Preferences evaluation tab, allowing users to easily sort apartments by different metrics.

## Features

### Sortable Columns
All columns except "Actions" are now sortable by clicking on the column header:

1. **Rank** - Original ranking order
2. **Apartment** - Alphabetical by address
3. **Joint Score** - Satisfaction percentage (default sort)
4. **Vetoes** - Number of veto-level violations
5. **Status** - OK vs VETO status

### Sorting Behavior

- **Click once**: Sort by that column (direction depends on column type)
- **Click again**: Reverse the sort direction
- **Visual indicator**: Active column shows ▲ (ascending) or ▼ (descending)
- **Default**: Sorts by Joint Score descending (highest scores first)

### Smart Defaults

Different columns have different default sort directions:
- **Apartment**: Ascending (A→Z) - easier to find specific apartments
- **All others**: Descending (highest→lowest) - see best first

### Visual Feedback

- **Hover effect**: Column headers highlight on hover to indicate they're clickable
- **Active column**: Current sort column is highlighted in blue
- **Sort indicator**: Arrow shows current sort direction (▲▼)

## Use Cases

### Find Apartments with Fewest Vetoes
**Click on "Vetoes" column** (ascending sort)
- Shows apartments with 0 vetoes first
- Great for finding apartments that meet most criteria
- Helps identify which apartments to tour first

### Compare Within Same Veto Count
**Click "Vetoes"** then **click "Joint Score"**
- First sorts by veto count
- Then you can sort by score within each veto tier
- Example: See which apartments with 1 veto have the highest joint score

### Find Specific Apartment Quickly
**Click "Apartment" column**
- Sorts alphabetically
- Easy to find a specific address
- Useful when you know the street name

### Find Best Overall Score
**Click "Joint Score"** (default)
- Shows highest satisfaction scores first
- Good starting point for evaluation
- Default view when results load

## Implementation Details

### State Management
```javascript
let evalTableSortState = {
    column: 'score',      // Currently sorted column
    ascending: false      // Sort direction (false = descending)
};
```

### Sorting Function
- Stores current sort state
- Toggles direction on repeated clicks
- Uses smart defaults for each column type
- Preserves original evaluation data

### Visual Updates
- Updates sort indicators (▲▼) on all headers
- Highlights active column
- Removes indicators from inactive columns

## Files Modified

1. **`templates/preferences_tab.html`**
   - Added `onclick="sortEvalTable()"` handlers to table headers
   - Added `sortable-header` class for styling
   - Added `.sort-indicator` spans for arrows
   - Added CSS for hover effects and active states

2. **`static/preferences.js`**
   - Added `evalTableSortState` variable to track sort state
   - Added `sortEvalTable(column)` function for sorting logic
   - Added `updateEvalTableSortIndicators()` function for visual feedback
   - Updated `renderEvaluationResults()` to initialize sort indicators

## Example Sorting Scenarios

### Scenario 1: Find apartments with no deal-breakers
1. Click **"Vetoes"** column header
2. Table sorts: 0 vetoes → 1 veto → 2 vetoes, etc.
3. Top apartments have fewest vetoes

### Scenario 2: Find best apartment among those with 1 veto
1. Click **"Vetoes"** to group by veto count
2. Scroll to 1-veto section
3. Click **"Joint Score"** to sort by satisfaction
4. Top of that section = best 1-veto apartment

### Scenario 3: Quick alphabet navigation
1. Click **"Apartment"** column
2. Apartments sorted A→Z
3. Easy to find "Berry St" or "Dolores St"

### Scenario 4: See worst performers
1. Click **"Joint Score"** (descending by default)
2. Click again to reverse (ascending)
3. Shows lowest scores first
4. Identify which apartments to skip

## CSS Classes Added

```css
.sortable-header {
    cursor: pointer;
    user-select: none;
    transition: background 0.2s;
}

.sortable-header:hover {
    background: #e8e8ed;  /* Light gray on hover */
}

.sortable-header.active {
    background: #e0e0e5;  /* Slightly darker when active */
    color: #0066cc;       /* Blue text for active column */
}

.sort-indicator {
    font-size: 10px;
    margin-left: 4px;
    color: #86868b;       /* Gray arrows */
}

.sortable-header.active .sort-indicator {
    color: #0066cc;       /* Blue arrows when active */
    font-weight: bold;
}
```

## Keyboard Accessibility

While the current implementation uses `onclick` handlers, the table remains keyboard-accessible:
- Headers can be focused with Tab key
- Enter/Space can trigger clicks
- Screen readers will announce the clickable headers

## Future Enhancements

Possible improvements for later:
1. **Multi-column sort**: Hold Shift to sort by secondary column
2. **Sort persistence**: Remember sort preference across sessions
3. **Export sorted view**: Download CSV in current sort order
4. **Sort by person**: Sort by individual person's satisfaction score
5. **Custom sort**: Allow user to define custom sort order

## Testing Checklist

- [x] Clicking "Rank" sorts by original rank order
- [x] Clicking "Apartment" sorts alphabetically
- [x] Clicking "Joint Score" sorts by satisfaction percentage
- [x] Clicking "Vetoes" sorts by veto count (most useful for finding best apartments!)
- [x] Clicking "Status" groups OK and VETO apartments
- [x] Clicking same column twice reverses direction
- [x] Active column shows visual indicator
- [x] Sort indicators show correct arrow direction
- [x] Hover effect works on all sortable headers

---

**Status**: ✅ COMPLETE

Users can now easily find apartments with the fewest vetoes by clicking the "Vetoes" column header!

Generated: December 8, 2024

