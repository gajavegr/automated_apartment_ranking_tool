# Terrain-Aware Scoring Feature

## Overview

The terrain-aware scoring feature uses Google Maps Elevation API to detect hills and adjust apartment scores based on how elevation affects:

1. **Parking Safety**: Open parking on steep hills is safer (more secluded, less traffic)
2. **Gym Accessibility**: Gyms feel farther away when there's significant elevation gain
3. **Commute Difficulty**: Tucked-away hill locations add time to reach highways

## Core Concept

Hills create tradeoffs that affect different aspects of apartment livability:

**Benefits:**
- ✅ Increased privacy and security for open parking
- ✅ Quieter, more secluded environment

**Drawbacks:**
- ❌ Gym proximity feels reduced (steep climb)
- ❌ Commute time effectively increased (harder highway access)

**Example: 39 Seward St #2 (Castro Hill)**
- **Elevation**: 57.9m above nearby areas
- **Parking**: Open parking gets safety bonus (+0.5 to +1.2 points)
- **Gym**: 1 mile gym feels farther due to 57.9m climb (-1.8 points)
- **Commute**: Tucked away location adds ~2 min effective time

## How It Works

### 1. Elevation Detection

The system uses Google Maps Elevation API to:
- Get absolute elevation of the apartment
- Calculate elevation gain to work, gym, and major streets
- Determine hill steepness (moderate: >20m, steep: >40m)

### 2. Scoring Adjustments

#### Parking Score Modification

For **open or covered parking**, the system adds a terrain safety bonus:

- **Moderate hill** (30-50m elevation): +0.5 points
- **Steep hill** (>50m elevation): +1.2 points
- **Scaled by neighborhood safety**: Higher base safety = smaller bonus

```python
# Example calculation
apartment_elevation = 57.9  # meters (like 39 Seward St)
base_parking_score = 3.0  # open parking, dedicated spot
terrain_bonus = 1.2  # steep hill bonus
safety_scale = 0.7  # moderate base safety (7/10)
final_bonus = 1.2 * 0.7 = 0.84

final_parking_score = 3.0 + 0.84 = 3.84 / 10
```

**Rationale**: Open parking on a hill is inherently safer due to:
- Reduced foot traffic (fewer random passersby)
- Less accessible to opportunistic thieves
- Typically residential-only access

#### Gym Score Modification

For **apartments with nearby gyms**, the system applies a hill penalty:

- **Moderate hill** (20-40m elevation gain): -0.8 points
- **Steep hill** (>40m elevation gain): -1.8 points

```python
# Example calculation
gym_score = 10.0  # nearby good gym
elevation_gain_to_gym = 57.9  # meters uphill
hill_penalty = -1.8  # steep hill penalty

final_gym_score = 10.0 - 1.8 = 8.2 / 10
```

**Rationale**: A gym that's "10 minutes away" on flat ground feels much farther when you have to climb 50+ meters each way. The penalty reflects reduced likelihood of regular use.

#### Commute Score Modification

For **apartments on steep hills**, the system adds time to the effective commute:

- **Steep hill**: +2 minutes (harder to reach highway)

```python
# Example calculation
actual_commute = 28  # minutes
on_steep_hill = True
effective_commute = 28 + 2 = 30  # minutes

# Score calculated using effective time
```

**Rationale**: Hill locations often require winding through residential streets before reaching main arteries, effectively extending the commute.

## Configuration

All terrain scoring is configured in `config.py`:

```python
TERRAIN_SCORING = {
    "elevation_thresholds": {
        "moderate_hill": 20,  # meters elevation gain
        "steep_hill": 40,     # meters elevation gain
    },
    "parking_safety_bonus": {
        "enabled": True,
        "moderate_hill": 0.5,  # +0.5 points
        "steep_hill": 1.2,     # +1.2 points
        "scale_by_safety": True,
    },
    "gym_distance_penalty": {
        "enabled": True,
        "moderate_hill_multiplier": 1.3,  # 30% farther feeling
        "steep_hill_multiplier": 1.6,     # 60% farther feeling
    },
    "commute_time_adjustment": {
        "enabled": True,
        "hill_access_penalty": 2,  # +2 minutes
    }
}
```

You can adjust these values to match your priorities.

## Manual Override

The web interface includes a **Hilliness Override** slider (0-10):

- **5 (default)**: Use API auto-detection
- **0-4**: Manually reduce hilliness impact
- **6-10**: Manually increase hilliness impact

**When to use**: If you have local knowledge (e.g., you know the specific street is flatter than the API suggests, or there's an elevator making the gym accessible).

## Data Sources

### Google Maps Elevation API

- **What it provides**: Elevation in meters for any lat/lng coordinate
- **Accuracy**: ~10-20m in urban areas
- **Cost**: $5 per 1,000 requests (after free tier)
- **Caching**: All elevation queries are cached to minimize costs

### Calculation Methods

1. **Apartment Elevation**: Direct API query for apartment coordinates
2. **Elevation Gain to Gym**: Difference between apartment and nearest gym elevation
3. **Elevation Gain to Work**: Difference between apartment and work location elevation
4. **Hill Detection**: Based on absolute elevation > 30m or > 50m (simplified heuristic)

**Note**: The current implementation uses a simplified heuristic (absolute elevation) rather than elevation relative to immediate surroundings. This works well for San Francisco's geography but may need refinement for other cities.

## Google Sheets Integration

The system writes elevation data to your Google Sheet:

| Column | Description |
|--------|-------------|
| `Apartment Elevation (m)` | Absolute elevation in meters |
| `Elevation Gain to Gym (m)` | Elevation change to nearest gym |
| `Elevation Gain to Work (m)` | Elevation change to work location |
| `Hilliness Override (0-10)` | Manual override value (if set) |

## Impact on Scores

Terrain adjustments are **subtle but material**:

- **Range**: 0.5 to 2 points per category (out of 10)
- **Total impact**: Can shift final score by 2-5 points (out of 100)
- **Philosophy**: Hills create genuine tradeoffs, not dealbreakers

**Before vs. After Example:**

```
Apartment A (Steep Hill):
Before Terrain:
  - Parking (open): 3.0/10
  - Gym (1 mi): 10.0/10
  - Commute: 8.0/10
  Total: 75/100

After Terrain:
  - Parking (open + hill): 3.8/10  (+0.8)
  - Gym (1 mi + 57.9m): 8.2/10    (-1.8)
  - Commute (+ hill access): 7.5/10 (-0.5)
  Total: 73/100                    (-2)

Net: -2 points, but you understand WHY
```

## Usage

### Web Interface

1. Enter apartment address
2. (Optional) Adjust "Hilliness Override" slider if needed
3. Submit form
4. Run `python main.py --analyze-new` to calculate scores

### Manual Entry

The hilliness override can be manually added to the Google Sheet:

1. Find the `Hilliness Override (0-10)` column
2. Enter a value (0-10)
3. Leave blank or enter 5 for auto-detection

### Analysis

The system automatically:
1. Fetches elevation data from Google Maps API
2. Calculates elevation gains
3. Applies terrain adjustments to scores
4. Writes results to Google Sheet

## Troubleshooting

### Elevation API Errors

**Error**: `"Error getting elevation: ..."`

**Cause**: Google Maps API key missing or Elevation API not enabled

**Fix**: 
1. Ensure `GOOGLE_MAPS_API_KEY` is set in `.env`
2. Enable "Elevation API" in Google Cloud Console
3. Add API restrictions (recommended)

### Unexpected Scores

**Issue**: Parking/gym scores seem wrong

**Debug**:
1. Check elevation columns in Google Sheet
2. Verify apartment is actually on a hill (Google Maps satellite view)
3. Use manual override if API data is incorrect

**Note**: The system uses absolute elevation as a proxy for "hilliness". In rare cases, this may not accurately reflect the local terrain (e.g., elevated plateau vs. steep slope).

### Performance

**Issue**: Analysis taking longer after terrain feature

**Cause**: Each apartment now makes 2-3 additional API calls (elevation queries)

**Mitigation**:
- Caching reduces redundant calls
- Batch analysis is still fast (<10s for 20 apartments)
- Consider disabling terrain scoring in `config.py` if not needed

## Technical Details

### Files Modified

- `config.py`: Added `TERRAIN_SCORING` configuration
- `analyzers/location_analyzer.py`: Added elevation API methods
- `analyzers/scoring_engine.py`: Modified `ParkingScore`, `GymScore`, `CommuteScore`
- `main.py`: Pass terrain data to scoring engine
- `web_app.py`: Extract and store hilliness override
- `templates/entry_form.html`: Added hilliness slider
- `static/style.css`: Styled range input

### API Calls Per Apartment

With terrain scoring enabled:

1. **Geocoding**: 1 call (apartment address)
2. **Elevation**: 1 call (apartment coords)
3. **Elevation**: 1 call (gym coords, if applicable)
4. **Elevation**: 1 call (work coords, cached across apartments)
5. **Other APIs**: Distance Matrix, Places, etc. (unchanged)

**Total new calls**: ~2-3 per apartment (elevation queries)

**Cost estimate** (after free tier):
- $5 per 1,000 elevation requests
- ~20 apartments = 40-60 requests
- Cost: <$0.50 total (first analysis)
- Subsequent analyses: Free (cached)

## Future Enhancements

Potential improvements for future versions:

1. **Relative Elevation**: Compare apartment elevation to surrounding blocks (more accurate hill detection)
2. **Slope Analysis**: Use multiple elevation points to calculate actual slope
3. **Route-Based Elevation**: Get elevation profile along commute/gym routes
4. **Elevation Visualization**: Add elevation contour lines to map view
5. **Per-Category Overrides**: Allow separate overrides for parking vs. gym effects

## Example Use Cases

### Case 1: Hill Apartment with Open Parking

**Address**: 39 Seward St #2, San Francisco, CA 94114

**Analysis**:
- Elevation: ~57.9m
- Open parking spot
- Gym 1 mile away (2145 Market St)

**Terrain Impact**:
- Parking: +0.8 points (safer due to hill)
- Gym: -1.8 points (steep climb from gym level)
- Commute: -0.5 points (tucked away)

**Decision**: Hill makes parking better but gym less accessible. Good for someone who doesn't use gym daily but values parking security.

### Case 2: Flat Location

**Address**: 1200 Market St, San Francisco, CA 94102

**Analysis**:
- Elevation: ~15m (flat)
- Open parking spot
- Gym 0.3 miles away

**Terrain Impact**:
- Parking: +0 points (no hill bonus)
- Gym: +0 points (no penalty)
- Commute: +0 points (easy highway access)

**Decision**: No terrain effects. Score based purely on amenities and location.

### Case 3: Manual Override

**Address**: Apartment on gradual slope

**Issue**: API shows 60m elevation, but street has gradual incline (not steep)

**Solution**:
1. Set "Hilliness Override" to 3 (below default 5)
2. System reduces terrain adjustments proportionally
3. Score better reflects actual experience

## Conclusion

The terrain-aware scoring system provides a more nuanced evaluation of apartments by accounting for how hills affect daily life. The adjustments are subtle (0.5-2 points per category) but meaningful, helping you understand the real tradeoffs of hill living.

**Key Takeaway**: Hills aren't good or bad—they create tradeoffs. This feature quantifies those tradeoffs so you can make informed decisions based on your priorities.

