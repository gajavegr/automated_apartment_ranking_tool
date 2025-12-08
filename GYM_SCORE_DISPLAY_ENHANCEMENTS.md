# Gym Score Enhancements - Summary

## Overview

Enhanced the gym score display in the Analysis tab to show detailed breakdown of gym data including selected gyms, walk/bike times, transport mode, and score calculation details.

## What Changed

### 1. Analysis Tab - Enhanced Gym Score Display

**Location:** `templates/entry_form.html` - Analysis Tab (lines ~1027-1065)

Added the following information to the gym score section:

#### New Fields:

1. **Selected Gyms** - Shows which gyms the user selected for this apartment
   ```
   Selected gyms: Live Fit Gym • Castro, FITNESS SF - Castro, Live Fit Gym - Mission
   ```

2. **Score Breakdown** - Shows the exact calculation used for the gym score
   ```
   Score Calculation:
   Time: 7.0 min (walk)
   Score = 10 × (1 - 7.0 / 20) = 6.5 points
   ```
   
   Or for biking:
   ```
   Score Calculation:
   Time: 14.3 min (bike)
   Score = 10 × (1 - 14.3 / 20) = 2.8 points
   ```

#### Existing Fields (Already Working):

- **Walking time** - Shows walking time to nearest selected gym
- **Biking time** - Shows biking time (if walk > 15 min)
- **Transport mode selector** - Dropdown to choose walk or bike (updates score in real-time)
- **Within 20 min** - Boolean indicator
- **Formula explanation** - How the score is calculated

### 2. Visual Layout

The gym score section now displays:

```
┌─────────────────────────────────────────────┐
│ 🏋️ Gym Nearby                    6.5 / 10  │
├─────────────────────────────────────────────┤
│ Selected gyms: Live Fit Gym • Castro,      │
│                FITNESS SF - Castro          │
│                                             │
│ Walking time: 7.0 min                       │
│                                             │
│ ╔═══════════════════════════════════════╗  │
│ ║ Score Calculation:                    ║  │
│ ║ Time: 7.0 min (walk)                  ║  │
│ ║ Score = 10 × (1 - 7.0 / 20) = 6.5    ║  │
│ ╚═══════════════════════════════════════╝  │
│                                             │
│ Within 20 min: Yes                          │
│                                             │
│ How it's calculated: Score scales linearly  │
│ with travel time...                         │
└─────────────────────────────────────────────┘
```

For apartments with biking option:

```
┌─────────────────────────────────────────────┐
│ 🏋️ Gym Nearby                    2.8 / 10  │
├─────────────────────────────────────────────┤
│ Selected gyms: SoulCycle Castro            │
│                                             │
│ Walking time: 36.8 min                      │
│ Biking time: 14.3 min                       │
│                                             │
│ Transport mode for scoring:                 │
│ [🚴 Biking ▼] (using 14.3 min for score)   │
│                                             │
│ ╔═══════════════════════════════════════╗  │
│ ║ Score Calculation:                    ║  │
│ ║ Time: 14.3 min (bike)                 ║  │
│ ║ Score = 10 × (1 - 14.3 / 20) = 2.8   ║  │
│ ╚═══════════════════════════════════════╝  │
│                                             │
│ Within 20 min: Yes                          │
│                                             │
│ How it's calculated: Score scales linearly  │
│ with travel time...                         │
└─────────────────────────────────────────────┘
```

## Technical Implementation

### JavaScript Changes

**File:** `templates/entry_form.html` (lines ~3700-3770)

1. **Show Selected Gyms:**
   ```javascript
   const selectedGyms = data['Selected Gyms'];
   if (selectedGyms) {
       document.getElementById('gymSelected').textContent = selectedGyms;
   }
   ```

2. **Display Score Breakdown:**
   ```javascript
   const gymScore = components['gym_nearby']?.score || 0;
   const maxTime = 20.0;
   const scoreFormula = `Time: ${parseFloat(effectiveTime).toFixed(1)} min (${gymTransportMode})
   Score = 10 × (1 - ${parseFloat(effectiveTime).toFixed(1)} / ${maxTime}) = ${gymScore.toFixed(1)} points`;
   document.getElementById('gymScoreDetails').textContent = scoreFormula;
   ```

3. **Conditional Display:**
   - Score breakdown shows for both walking-only and biking apartments
   - Biking row and transport selector only show when bike time is available
   - Formula uses the effective time (either walk or bike based on selection)

### Data Flow

1. **Data Source:** Google Sheets columns
   - `Selected Gyms` - Comma-separated list of gym names
   - `Gym Walk Time (min)` - Walking time to nearest gym
   - `Gym Bike Time (min)` - Biking time (if calculated)
   - `Gym Transport Mode` - Current selection ('walk' or 'bike')
   - `Gym Score` - Calculated score

2. **Display Logic:**
   - Always show: Selected gyms, walk time, formula
   - Conditionally show: Bike time, transport selector (only if bike time exists)
   - Score breakdown: Shows calculation with effective time and mode

3. **Real-time Updates:**
   - When user changes transport mode, the score recalculates
   - Effective time and score breakdown update immediately
   - New data is saved to Google Sheets via `/update_gym_transport_mode` endpoint

## User Experience

### Before

```
Gym Nearby: 6.5/10
Walking time: 7.0 min
Within 20 min: Yes
```

Users couldn't see:
- Which gyms were selected
- How the score was calculated
- The exact formula used

### After

```
Gym Nearby: 6.5/10
Selected gyms: Live Fit Gym • Castro, FITNESS SF - Castro
Walking time: 7.0 min

Score Calculation:
Time: 7.0 min (walk)
Score = 10 × (1 - 7.0 / 20) = 6.5 points

Within 20 min: Yes
```

Users can now see:
✅ Which gyms they selected
✅ The exact calculation formula
✅ How the score was derived
✅ Which time is being used for scoring

### For Biking Apartments

```
Gym Nearby: 2.8/10
Selected gyms: SoulCycle Castro
Walking time: 36.8 min
Biking time: 14.3 min

Transport mode for scoring:
[🚴 Biking ▼] (using 14.3 min for score)

Score Calculation:
Time: 14.3 min (bike)
Score = 10 × (1 - 14.3 / 20) = 2.8 points

Within 20 min: Yes
```

Users can:
✅ See both walk and bike times
✅ Choose their preferred transport mode
✅ See the score update in real-time
✅ Understand which time was used for the score

## Entry Form (No Changes)

The Entry form (gym selection during apartment entry) remains unchanged. This was intentional because:

1. **Walk/bike times aren't known yet** - They're calculated during analysis, not during entry
2. **User can adjust later** - After analysis, user can change transport mode in Analysis tab
3. **Automatic optimization** - System calculates both times and suggests the better option
4. **Simpler workflow** - Entry form just selects gyms, Analysis tab handles optimization

## Score Calculation Formula

The gym score is calculated as:

```
Score = 10 × (1 - effective_time / 20)
```

Where:
- `effective_time` = Walk time OR bike time (user's choice)
- Maximum score: 10 points (at 0 minutes)
- Minimum score: 0 points (at 20 minutes or more)
- Linear scaling in between

Examples:
- 0 min → 10.0 points
- 5 min → 7.5 points
- 7 min → 6.5 points
- 10 min → 5.0 points
- 14.3 min → 2.85 points
- 15 min → 2.5 points
- 20 min → 0.0 points
- >20 min → 0.0 points

Office-only gyms get -5 point penalty.

## Testing

To test the changes:

1. **Refresh the browser** to load the new HTML/JS
2. **Navigate to Analysis tab**
3. **Select an apartment** with gym data
4. **Verify you see:**
   - Selected gyms list
   - Walk time
   - Bike time (if available)
   - Transport mode selector (if bike available)
   - Score breakdown box with formula
   - Score updates when changing transport mode

## Files Modified

1. **`templates/entry_form.html`**
   - Lines ~1027-1065: Added HTML for new gym score fields
   - Lines ~3700-3770: Updated JavaScript to populate new fields and calculate score breakdown
   - Lines ~2129-2174: Reverted unnecessary changes to gym card (no transport mode selector in entry form)

2. **`web_app.py`**
   - Lines 1-38: Added graceful shutdown handling (separate feature)
   - Lines 917-952: Reverted unnecessary gym transport preference collection (not needed)

3. **`GRACEFUL_SHUTDOWN.md`**
   - New documentation file for graceful shutdown feature

## Benefits

1. ✅ **Transparency** - Users see exactly how gym scores are calculated
2. ✅ **Debugging** - Easier to understand why a score is what it is
3. ✅ **Trust** - Formula is visible, no black box
4. ✅ **Control** - Users can see and change transport mode with immediate feedback
5. ✅ **Context** - See which gyms were selected, not just the score
6. ✅ **Education** - Learn how the scoring system works

## Future Enhancements

Possible improvements:
- Show distance in miles/km in addition to time
- Show elevation gain for walking/biking
- Visual indicator (icons) for walk vs bike mode
- Show all selected gyms with their individual times (not just nearest)
- Map view showing gym locations relative to apartment
- Gym quality indicators (equipment, crowding, hours)

---

**Status:** ✅ Complete and ready to use!

Refresh your browser and check out the enhanced gym score display in the Analysis tab.










