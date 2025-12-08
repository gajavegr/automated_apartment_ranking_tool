# Gym Score Recalculation Guide

## What Changed

**OLD METHOD (Distance-based + Rating):**
- Used Haversine distance (straight-line "as-the-crow-flies")
- Assumed 1 mile = 20 minutes walking
- Score based on Google Maps rating: 10 for 4.5+ stars, 6 for lower ratings, 0 for >20 min
- Ignored hills, street layout, barriers

**NEW METHOD (Walking Time-based, Linear Scale):**
- Uses Google Directions API for actual walking routes
- Accounts for hills, streets, detours, public stairways
- **Score scales linearly with walking time**: 0 min = 10 points, 20 min = 0 points
- Google Maps rating is **ignored** (you already selected gyms you'd go to)
- Much more accurate for San Francisco's irregular terrain

## Scoring Formula

The gym score now scales **smoothly** based on walking time:

```
score = 10 × (1 - walk_time / 20)
```

**Examples:**
- 0 min walk → 10.0/10 (on-site gym)
- 5 min walk → 7.5/10
- 10 min walk → 5.0/10
- 15 min walk → 2.5/10
- 20+ min walk → 0.0/10

**Special case:**
- No suitable gyms (office gym only) → -5.0/10 (penalty)

## Why This Matters

### Old System Was Too Coarse

**Before:**
- 0-20 min walk with 4.5+ star rating → 10/10
- 0-20 min walk with <4.5 star rating → 6/10
- 20+ min walk → 0/10

All apartments with gyms <20 min got the same score (10), even if one was 5 min and another was 19 min!

### New System Is Granular

**Now:**
- 5 min walk → 7.5/10
- 10 min walk → 5.0/10
- 15 min walk → 2.5/10

Apartments with closer gyms are **properly rewarded** with higher scores.

## Why This Matters

In SF, straight-line distance is misleading:
- **Hills**: A gym 0.3 mi away up a steep hill = 20+ min walk → 0/10
- **Street layout**: Irregular grid means longer actual routes
- **Barriers**: Parks, freeways, private property force detours
- **Stairs**: Public stairways slow walking speed

**Real example:**
```
Gym A: 0.4 mi (haversine) → 22 min walk (uphill) → Score: 0.0/10 ❌
Gym B: 0.6 mi (haversine) → 15 min walk (flat) → Score: 2.5/10 ✓
Gym C: 0.3 mi (haversine) → 8 min walk (direct) → Score: 6.0/10 ⭐
```

Gym C is the best choice despite not being the absolute closest in distance!

## How to Recalculate All Gym Scores

### Method 1: Automatic Detection (Recommended)

The analysis will now automatically detect gym scores that need updating:
- Gym scores of exactly `10.0` are flagged as outdated (likely distance-based)
- Missing or `None` gym scores trigger recalculation
- Analysis logs will show: `❌ Gym score = 10.0, likely outdated (distance-based)`

**Just run the analysis:**
1. Go to Analysis tab
2. Click "Run Analysis"
3. Check logs for `gym score needs recalculation` messages
4. Scores will be recalculated with walking time

### Method 2: Force Clear (Nuclear Option)

If automatic detection doesn't work, use the force recalculation script:

```bash
# Make sure web app is running first
python force_gym_recalc.py
```

This will:
1. Clear `gym_score` column for all apartments
2. Force analysis to recalculate from scratch
3. Then run "Run Analysis" to populate new scores

### Method 3: API Endpoint (Advanced)

For programmatic control:

```bash
# Clear gym scores for all apartments
curl -X POST http://127.0.0.1:5000/admin/force_recalculate \
  -H "Content-Type: application/json" \
  -d '{"component": "gym_score", "addresses": "all"}'

# Clear gym scores for specific apartments
curl -X POST http://127.0.0.1:5000/admin/force_recalculate \
  -H "Content-Type: application/json" \
  -d '{"component": "gym_score", "addresses": ["407 Sanchez St apt 2320, San Francisco, CA 94114", "240 Dolores St apt 126, San Francisco, CA 94103"]}'

# Clear ALL scores (gym, laundry, score ranges)
curl -X POST http://127.0.0.1:5000/admin/force_recalculate \
  -H "Content-Type: application/json" \
  -d '{"component": "all", "addresses": "all"}'
```

## What Gets Recalculated

When gym scores are recalculated, the analysis:

1. **Reads selected gyms** from your entry form
2. **Gets approved gyms** from the "Approved Gyms" sheet
3. **Calculates walking time** to each selected gym using Directions API
4. **Finds nearest gym** by walking time (not distance)
5. **Assigns score linearly**: `score = 10 × (1 - walk_time / 20)`
   - Example: 8 min walk → 10 × (1 - 8/20) = 10 × 0.6 = **6.0/10**
   - Example: 18 min walk → 10 × (1 - 18/20) = 10 × 0.1 = **1.0/10**

## Expected Results

After recalculation, you'll likely see:

### Wider Score Range 📊
**Before:** Most gyms scored 10/10 (all within 20 min got same score)
**After:** Scores distributed based on actual walk time

**Example distribution:**
- Apartment A: 8 min walk → **6.0/10**
- Apartment B: 12 min walk → **4.0/10**
- Apartment C: 18 min walk → **1.0/10**
- Apartment D: 22 min walk → **0.0/10**

### Better Differentiation ✨
- Apartments with truly convenient gyms (5-10 min) will have **higher scores**
- Apartments with marginally acceptable gyms (15-19 min) will have **lower scores**
- Apartments with slightly-too-far gyms (20+ min) will have **zero score**

## Debugging

If a gym score looks wrong, check the analysis logs:

```
Using selected gyms: Live Fit Gym - Mission, 24 Hour Fitness
Found 12 approved gyms in sheet
  Live Fit Gym - Mission: 12 min walk
  24 Hour Fitness: 18 min walk
  Gold's Gym: 25 min walk
✓ Nearest selected gym: 24 Hour Fitness (18 min walk, within 20min: True)
  Gym Score: 1.0/10 (linear scale: 18 min = 1.0)
```

**Breakdown:**
- 18 min walk
- Score = 10 × (1 - 18/20) = 10 × 0.1 = **1.0/10**

This shows:
- Which gyms were selected
- Walking time to each
- Which one was chosen as nearest
- The calculated score based on that walking time

## Files Modified

### `main.py` (Lines 142-185)
- Changed from `haversine_distance()` to `get_commute_time(mode='walking')`
- Now iterates through selected gyms and gets actual walk times
- Picks gym with shortest walk time (not shortest distance)

### `utils/google_sheets.py` (Lines 489-502)
- Added check: `gym_score == 10.0` triggers recalculation
- Logs: `❌ Gym score = 10.0, likely outdated (distance-based)`

### `web_app.py` (Lines 1558-1638)
- New `/admin/force_recalculate` endpoint
- Allows clearing specific score components
- Supports filtering by apartment addresses

### `force_gym_recalc.py` (New file)
- Quick script to trigger gym score recalculation
- Wraps the API endpoint for convenience

## API Rate Limiting

Each walking time calculation uses **1 Google Directions API call**.

For an apartment with 3 selected gyms:
- 3 API calls (one per gym)
- Rate limiter ensures we stay within quota
- Cached to avoid redundant calls

With 4 apartments × 3 gyms = 12 API calls total.

At 50 requests/second limit, this completes in < 1 second.

## Next Steps

1. **Run analysis** to trigger automatic recalculation
2. **Check logs** to see which apartments are being recalculated
3. **Review gym scores** in the comparison table
4. **Verify in Google Sheet** that `Gym Score` column has updated values

The gym scores should now accurately reflect **real-world walking accessibility**! 🚶‍♂️

