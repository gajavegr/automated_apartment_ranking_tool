# Parking Enclosure Feature

## Summary

Added parking enclosure type as an additional field to differentiate between enclosed/covered/open parking. This helps assess weather protection, security, and overall parking quality.

## What Changed

### 1. Configuration (`config.py`)

**Added column:**
- `"parking_enclosure": "Parking Enclosure"`

**Added scoring bonuses:**
```python
"enclosure_bonuses": {
    "enclosed": 1.0,    # Garage/underground - best protection
    "covered": 0.5,     # Carport/overhang - some protection  
    "open": 0.0,        # Outdoor/exposed - no protection
    "": 0.0,            # Unknown/not specified
}
```

### 2. Web Interface (`templates/entry_form.html`)

**Added dropdown field:**
```html
<select id="parking_enclosure" name="parking_enclosure">
    <option value="">Unknown/Not Applicable</option>
    <option value="enclosed">Enclosed (Garage/Underground)</option>
    <option value="covered">Covered (Carport/Overhang)</option>
    <option value="open">Open (Outdoor/Exposed)</option>
</select>
```

**Helper text:** "Weather protection and security level"

### 3. Web App Backend (`web_app.py`)

- Extracts `parking_enclosure` from form
- Writes to Google Sheets in appropriate column

### 4. Terminal Interface (`manual_entry.py`)

- Prompts for parking enclosure after parking type (if applicable)
- Only asks if parking type is not 'none' or 'street_parking'
- Writes to Google Sheets

### 5. Scoring Engine (`analyzers/scoring_engine.py`)

**Updated `ParkingScore` class:**
- Added `parking_enclosure` field
- Applies enclosure bonus to final score
- Enclosure bonus only applies to dedicated parking (not street parking)

**Score calculation:**
```python
score = base_score + distance_penalty + enclosure_bonus
```

### 6. Main Analysis (`main.py`)

- Reads `parking_enclosure` from Google Sheets
- Displays in parking info output
- Passes to scoring engine

## Enclosure Types Explained

### Enclosed (Best - +1.0 bonus)
- **Examples:** Underground garage, fully enclosed garage, parking structure
- **Benefits:** 
  - Maximum weather protection (rain, sun, snow)
  - High security (locked, controlled access)
  - Vehicle stays cleaner
  - Temperature regulation (cooler in summer, warmer in winter)

### Covered (Good - +0.5 bonus)
- **Examples:** Carport, covered parking spot, overhang
- **Benefits:**
  - Partial weather protection (rain, sun)
  - Some security (more visible than enclosed)
  - Moderate vehicle protection

### Open (Basic - +0.0 bonus)
- **Examples:** Outdoor parking lot, driveway, uncovered spot
- **Benefits:**
  - Easy access
  - Often easier to find spot
- **Drawbacks:**
  - No weather protection
  - Less secure
  - Vehicle exposed to elements

## Scoring Impact

### Example Calculations:

**Single Garage (Enclosed):**
```
Base score: 10
Distance penalty: 0 (onsite)
Enclosure bonus: +1.0
Final: 10/10 (capped at 10)
```

**Dedicated Spot Car Only (Open):**
```
Base score: 7
Distance penalty: 0 (onsite)
Enclosure bonus: 0
Final: 7/10
```

**Dedicated Spot Car Only (Enclosed):**
```
Base score: 7
Distance penalty: 0 (onsite)
Enclosure bonus: +1.0
Final: 8/10
```

**Dedicated Spot Car Only (Covered, 5min walk):**
```
Base score: 7
Distance penalty: -1.5
Enclosure bonus: +0.5
Final: 6/10
```

### Why These Bonuses?

- **Enclosed (+1.0):** Significant quality of life improvement
  - In SF: Rain protection, security, motorcycle safety
  - Worth ~10% boost to parking score

- **Covered (+0.5):** Moderate benefit
  - Some weather protection
  - Better than nothing, not as good as enclosed

- **Open (0.0):** No bonus
  - This is the baseline/default
  - Already reflected in base parking type score

## Use Cases

### When Enclosure Matters Most:

1. **Motorcycle Parking**
   - Enclosed is much better for security
   - Open parking = higher theft risk

2. **Climate**
   - SF fog/rain → Enclosed keeps car dry
   - Summer sun → Covered prevents interior damage

3. **Vehicle Value**
   - Expensive car → Enclosed provides better protection
   - Older car → Open may be acceptable

4. **Work-from-Home**
   - If you rarely drive → Enclosure less important
   - Daily driver → Enclosure matters more

## Workflow Integration

### Web Interface:
1. Select parking type (e.g., "Dedicated Spot Car Only")
2. Select parking enclosure (e.g., "Enclosed")
3. Submit → Both saved to Google Sheets

### Analysis:
1. `main.py --analyze-new` reads both fields
2. Parking score calculated with enclosure bonus
3. Higher score for better protected parking

### Display:
```
Parking: dedicated_spot_car_only (enclosed)
Parking Score: 8.0/10
  - Base: 7.0
  - Distance: 0.0
  - Enclosure bonus: +1.0
```

## Examples from Real Listings

### Apartment A - "Garage Parking"
- **Type:** Single Garage
- **Enclosure:** Enclosed
- **Score:** 10/10
- **Why:** Best possible parking situation

### Apartment B - "Assigned Parking Space in Lot"
- **Type:** Dedicated Spot (Car Only)
- **Enclosure:** Open
- **Score:** 7/10
- **Why:** Guaranteed spot but exposed to weather

### Apartment C - "Covered Carport"
- **Type:** Dedicated Spot (Car Only)
- **Enclosure:** Covered
- **Score:** 7.5/10
- **Why:** Guaranteed spot with some weather protection

### Apartment D - "Underground Parking"
- **Type:** Dedicated Spot (Car + Motorcycle)
- **Enclosure:** Enclosed
- **Score:** 10/10
- **Why:** Room for both vehicles, fully protected

### Apartment E - "Street Parking Permit"
- **Type:** Street Parking
- **Enclosure:** N/A (open by definition)
- **Score:** 3-6/10 (depends on street_ease)
- **Why:** No enclosure bonus for street parking

## Technical Details

### Database Schema
- Column added to Google Sheets: "Parking Enclosure"
- Data type: String (enum)
- Optional field (can be empty)
- Only relevant for dedicated parking types

### Backward Compatibility
- Existing data without enclosure → Treated as unknown ("")
- Unknown gets 0 bonus (no penalty, no bonus)
- Old scores remain valid

### Validation
- Web form: Dropdown prevents invalid values
- Manual entry: Free text but validated on scoring
- Invalid values → Default to "" (0 bonus)

## Future Enhancements

Possible additions:
- **Security features:** Gate code, security cameras
- **Charging:** EV charging availability
- **Size:** Compact vs. standard vs. oversized
- **Tandem:** Whether it's tandem parking
- **Lighting:** Well-lit vs. poorly lit

---

**Bottom Line:** Parking enclosure helps differentiate parking quality beyond just "has parking" vs. "no parking". A covered or enclosed spot is worth more than an open-air spot, which is now reflected in the scoring! 🚗🏠

