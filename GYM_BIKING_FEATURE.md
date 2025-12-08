# Gym Biking Feature

## Overview

This feature adds biking as an alternative transportation mode for gyms that are more than 15 minutes walking distance. Users can now choose between walking and biking for gym commutes, and the system will automatically calculate both times when applicable.

## What Changed

### 1. Travel Time Calculation (`analyzers/location_analyzer.py`)

**New Methods:**
- `_get_travel_times()`: Generic method to get travel times for any transport mode (walking or biking)
- `_get_biking_times()`: Specifically gets biking times using Google Maps Directions API
- `_get_walking_times()`: Refactored to use the generic `_get_travel_times()` method

**Key Features:**
- Uses Google Maps Directions API with `mode='bicycling'` for accurate bike route times
- Automatically triggered when walking time > 15 minutes
- Returns duration in minutes and distance in miles

### 2. Gym Analysis Logic (`main.py`)

**Enhanced Gym Processing:**
- Lines 270-320: Updated gym analysis to:
  1. Calculate walking times for all selected gyms
  2. Find the nearest gym by walking time
  3. If walking time > 15 min, also calculate biking time
  4. Store both times and let user choose preferred mode
  5. Default to walking if it's <= 15 min or faster than biking

**New Fields Stored:**
- `gym_walk_time_mins`: Walking time in minutes (always calculated)
- `gym_bike_time_mins`: Biking time in minutes (calculated when walk > 15 min)
- `gym_transport_mode`: User's preferred mode ('walk' or 'bike')
- `gym_effective_time_mins`: The time used for scoring based on user preference

### 3. Scoring Engine (`analyzers/scoring_engine.py`)

**Updated GymScore Component (lines 390-481):**
- Now accepts bike time, transport mode, and effective time parameters
- Uses `gym_effective_time_mins` for scoring (based on user's transport mode preference)
- Displays both walk and bike times in score details
- Score formula remains: `score = 10 × (1 - time / 20)`
  - Where `time` is either walk or bike time based on user preference

**Scoring Details Include:**
- Walking time (always shown)
- Biking time (shown if >15 min walk)
- Transport mode being used for scoring
- Effective time used in calculation

### 4. Configuration (`config.py`)

**New Constants:**
```python
GYM_BIKE_THRESHOLD_MINS = 15.0  # If walking time > this, also calculate biking time
```

**New Sheet Columns:**
- `"gym_walk_time_mins"`: `"Gym Walk Time (min)"`
- `"gym_bike_time_mins"`: `"Gym Bike Time (min)"`
- `"gym_transport_mode"`: `"Gym Transport Mode"`
- `"gym_effective_time_mins"`: `"Gym Time Used for Score (min)"`

### 5. Web Interface (`templates/entry_form.html`)

**New UI Elements (lines 1021-1061):**
- Walking time display (always visible)
- Biking time display (visible when bike time is available)
- Transport mode dropdown selector (🚶 Walking / 🚴 Biking)
- Effective time indicator showing which time is used for scoring
- Real-time score recalculation when transport mode changes

**JavaScript Function:**
- `updateGymTransportMode()`: Handles transport mode changes
  - Updates effective time display
  - Saves preference to Google Sheets
  - Triggers score recalculation
  - Reloads apartment data to show updated score

**Updated Display Logic (lines 3645-3681):**
- Shows bike time row only if bike time exists
- Shows transport mode selector only if bike time exists
- Updates effective time based on selected mode
- Maintains sync with backend data

### 6. Backend API (`web_app.py`)

**New Endpoint:**
```python
POST /update_gym_transport_mode/<row_number>
```

**Parameters:**
- `transport_mode`: 'walk' or 'bike'
- `effective_time`: The time to use for scoring

**Functionality:**
- Updates apartment data with new transport mode preference
- Recalculates total weighted score
- Writes changes back to Google Sheets
- Returns updated score to frontend

**Updated Data Normalization (lines 209-218):**
- Reads and parses gym bike time, transport mode, and effective time from sheet
- Ensures all gym-related fields are properly loaded for scoring

## How It Works

### Workflow

1. **Data Entry/Analysis:**
   - User adds apartment and selects gyms
   - System calculates walking time to nearest selected gym
   - If walking time > 15 min, system also calculates biking time
   - Both times are stored in Google Sheets

2. **Score Display:**
   - Entry form loads apartment data
   - If bike time exists, shows transport mode selector
   - Default mode is whatever was last selected (or walk for new entries)

3. **User Selection:**
   - User can switch between walk and bike modes using dropdown
   - Selection instantly triggers:
     - Update effective time display
     - Save preference to sheet via API
     - Recalculate total score
     - Reload updated data

4. **Scoring:**
   - GymScore component uses `gym_effective_time_mins` for calculation
   - Score scales linearly: 0 min = 10 pts, 20 min = 0 pts
   - Example:
     - 18 min walk → 1.0/10 if walking selected
     - 8 min bike → 6.0/10 if biking selected (for same gym)

### Example Scenarios

**Scenario 1: Close Gym (≤15 min walk)**
```
Gym A: 10 min walk
→ Only walking time calculated
→ No transport mode selector shown
→ Score: 5.0/10 (using 10 min walk)
```

**Scenario 2: Far Gym (>15 min walk)**
```
Gym B: 18 min walk, 8 min bike
→ Both times calculated and shown
→ Transport mode selector appears
→ User can choose:
   - Walking: 1.0/10 (using 18 min)
   - Biking: 6.0/10 (using 8 min)
```

**Scenario 3: Very Far Gym**
```
Gym C: 25 min walk, 12 min bike
→ Both times calculated
→ Walking: 0.0/10 (over 20 min threshold)
→ Biking: 4.0/10 (using 12 min)
→ Biking is much better option!
```

## User Benefits

1. **More Accurate Scoring:** Reflects real-world transportation options
2. **Flexibility:** Users can choose their preferred mode based on personal preferences
3. **Better Differentiation:** Gyms that are walkable vs bikeable are properly distinguished
4. **Personal Choice:** Some users prefer walking even if it's slower; others prefer biking
5. **San Francisco Terrain:** Especially useful in hilly areas where biking routes may be flatter

## API Rate Limiting

- Each gym analysis now makes 1 additional API call if walking > 15 min
- Rate limiting is handled by existing `rate_limiter` in `location_analyzer`
- Google Maps API quota: 100 calls/min for Directions API
- Typical apartment with 2-3 selected gyms: 2-6 API calls total

## Testing

To test this feature:

1. **Add/reanalyze an apartment** with a gym >15 min walk away
2. **Check the logs** to see biking time calculation triggered
3. **View in entry form** to see transport mode selector
4. **Switch modes** and observe score change
5. **Verify Google Sheets** has all 4 new gym columns populated

## Future Enhancements

Potential improvements:
- Add transit time option (for gyms >20 min away)
- Consider terrain/elevation for biking difficulty
- Add user preference profiles (e.g., "I always bike" vs "I always walk")
- Show route details (bike lanes, hills, etc.)
- Calculate per-trip cost for different modes



