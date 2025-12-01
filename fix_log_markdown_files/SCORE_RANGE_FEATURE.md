# Score Range & Multi-Select Feature

## Overview

This feature allows you to handle uncertain apartment data by selecting multiple options for key attributes. The system calculates minimum and maximum scores based on the best and worst-case scenarios, helping you identify apartments worth touring even when complete information isn't available.

## Key Concepts

### Multi-Select Fields

All dropdown fields now support multiple selections:
- **Parking Type**: Single garage, dedicated spot, street parking, etc.
- **Parking Enclosure**: Enclosed, covered, or open
- **Laundry Type**: In-unit, shared good/poor ratio, or none
- **Neighborhoods**: Select all neighborhoods that might apply

### Score Ranges

When multiple options are selected for a field:
- **Min Score**: Calculated assuming the worst-case option
- **Max Score**: Calculated assuming the best-case option  
- **Average Score**: Midpoint between min and max
- **Certainty**: Percentage of fields with single (certain) values

### Tour Questions

Mark fields as "tour questions" to track what you need to verify during a visit. These appear in a dedicated "Tour Questions" column in your Google Sheet.

## How It Works

### 1. Web Interface

**Multi-Select with Checkboxes:**
```
Parking Type *
☐ Single Garage
☐ Dedicated Spot (Car + Motorcycle)
☑ Dedicated Spot (Car Only)
☑ Street Parking
☐ No Parking

☑ Mark as tour question
```

**What this means:**
- You're uncertain if it has dedicated parking or just street parking
- The system will calculate:
  - **Min Score**: Street parking scenario (lower score)
  - **Max Score**: Dedicated spot scenario (higher score)
- Marked as tour question so you remember to verify

### 2. Scoring Logic

**Example: Parking**
```
Base Scores:
- Dedicated spot (car only): 7/10
- Street parking: 3-6/10 (varies by ease)

Selected: Both options

Calculation:
- Min Score: 3/10 (worst street parking)
- Max Score: 7/10 (dedicated spot)
- Average: 5/10
- Range: 4 points
```

**Impact on Total Score:**
```
Overall apartment score with uncertain parking:
- Min Total: 72/100 (if parking is bad)
- Max Total: 80/100 (if parking is good)
- Display: 76 ± 4 points

Certainty: 85% (most fields are certain, parking is uncertain)
```

### 3. Visualization

**Google Sheets Scatter Plot:**
- Points show average score
- Error bars show min/max range
- Wider bars = more uncertainty
- Helpful for comparing "potential" of apartments

**Example:**
```
Apartment A: 75/100 (certain) → Single point
Apartment B: 70-85/100 (uncertain) → Point with error bar
Apartment C: 80/100 (certain) → Single point

Apartment B might be better than A if best-case, worth touring!
```

## Use Cases

### Case 1: Unclear Laundry Situation

**Zillow says:** "Shared laundry on-site"

**Problem:** Can't tell if there are 2 machines for 50 units (poor) or 10 machines for 20 units (good)

**Solution:**
```
Select both:
☑ Shared (Good Ratio)
☑ Shared (Poor Ratio)
☑ Mark as tour question
```

**Result:** Score range shows best/worst case, reminds you to count machines during tour

### Case 2: Parking Confusion

**Zillow says:** "Parking available"

**Problem:** Could mean anything from guaranteed garage to street-only

**Solution:**
```
Select likely options:
☑ Dedicated Spot (Car Only)
☑ Street Parking
☑ Mark as tour question
```

**Result:** Score accounts for both possibilities, flagged for verification

### Case 3: Neighborhood Boundary

**Address:** "Near Mission & Castro"

**Problem:** Could be in either neighborhood, different vibes

**Solution:**
```
Select both:
☑ Mission
☑ Castro
(No tour question needed - you can see this yourself)
```

**Result:** Google Sheets shows both neighborhoods, you know the location

## Neighborhoods Feature

### Auto-Fill from Address

When you enter an address:
1. Google Maps API detects neighborhood(s)
2. Checkboxes auto-select
3. You can adjust if needed

### Multi-Neighborhood Selection

Some apartments sit on boundaries:
- "Mission/Potrero Hill border"
- "Inner/Outer Sunset edge"  
- "SOMA/South Beach overlap"

Select all that apply for better location context.

### Searchable List

```
Neighborhoods
[Search: miss___]

Results:
☐ Mission
☐ Mission Bay
```

All 45 SF neighborhoods available, searchable for quick selection.

## Tour Questions Column

### What It Shows

```
Tour Questions
--------------
Parking type, Laundry type
Parking enclosure
(none)
Laundry type
```

### How to Use

1. **Before Tours:** Review this column to prepare questions
2. **During Tours:** Ask about flagged items
3. **After Tours:** Update sheet with certain values
4. **Re-analyze:** Get updated score with certain data

### Certainty Percentage

```
Score Certainty: 100% → All fields have single values (fully certain)
Score Certainty: 80%  → 1-2 fields uncertain
Score Certainty: 60%  → Many fields uncertain
Score Certainty: 40%  → Very uncertain, needs verification
```

**How It's Calculated:**
```
Certainty = (Certain Fields / Total Weighted Fields) × 100%

Example:
- 8 scoring components total
- 6 have single values (certain)
- 2 have multiple values (uncertain)
- Certainty: (6/8) × 100% = 75%
```

### Score vs Theoretical Max

**New Metric:** Shows how well the apartment performs relative to a perfect score, given the data available.

```
Score vs Max: 72.5% of theoretical maximum
```

**What It Means:**
- **Theoretical Max**: Perfect 10/10 score for every category with data
- **Actual Score**: What the apartment actually scored
- **Percentage**: Actual ÷ Theoretical Max

**Example Calculation:**
```
Apartment with data in 8 categories (weighted):
- Theoretical Max: 100 points (if everything was perfect 10/10)
- Actual Score: 72.5 points
- Score vs Max: 72.5 / 100 = 72.5%

This means the apartment achieved 72.5% of the best possible score
given the categories where you have information.
```

**Why This Matters:**

**Compare apples-to-apples:**
```
Apartment A: 75/100, but missing gym data
  Score vs Max: 75/90 = 83.3%
  
Apartment B: 70/100, has all data
  Score vs Max: 70/100 = 70.0%
  
Apartment A is actually performing better relative to its available data!
```

**Identify high performers:**
```
85%+ → Excellent, meets criteria very well
70-84% → Good, solid performance
55-69% → Fair, some compromises
<55% → Poor, consider if location/price justify
```

**When to Use:**

**Comparing apartments with different amounts of data:**
- One has WFH space data, another doesn't
- One has gym info, another doesn't
- Use "Score vs Max %" to normalize the comparison

**Evaluating incomplete data:**
- 65/100 score might seem low
- But 81% vs max means it's good at what you know
- Worth touring to fill in missing data

**Setting expectations:**
- 90% vs max = Very hard to beat, tour ASAP
- 50% vs max = Mediocre even with known data, reconsider

### Certainty Percentage (Revisited)

**How It's Calculated:**

**High Certainty (80-100%):**
- Good for final rankings
- Confident in comparisons
- Ready for application decisions

**Medium Certainty (60-79%):**
- Good for tour scheduling
- Need to verify 1-2 things
- Ballpark comparisons valid

**Low Certainty (40-59%):**
- Schedule tour first
- Gather more info before deciding
- Compare potential only

### Using Both Metrics Together

**Ideal Combination Matrix:**

```
High Score vs Max + High Certainty = TOUR IMMEDIATELY
├─ 85% vs max, 95% certain → Apartment is great and you know it
└─ Apply/tour ASAP

High Score vs Max + Low Certainty = HIGH POTENTIAL
├─ 82% vs max, 60% certain → Could be excellent
└─ Tour to verify unknowns

Low Score vs Max + High Certainty = KNOWN MEDIOCRE
├─ 58% vs max, 100% certain → You know it's not great
└─ Reconsider or only if price is very low

Low Score vs Max + Low Certainty = RISKY
├─ 55% vs max, 50% certain → Not performing well even with limited data
└─ Likely to stay mediocre, skip unless desperate
```

**Example Decision Tree:**

```
Apartment X:
- Score: 68/100
- Score vs Max: 76%
- Certainty: 70%

Analysis:
→ 76% vs max = Good performance on known attributes
→ 70% certain = A few unknowns to verify
→ Decision: Worth touring, has good fundamentals

Apartment Y:
- Score: 72/100
- Score vs Max: 58%
- Certainty: 100%

Analysis:
→ 58% vs max = Mediocre performance
→ 100% certain = You have all the data
→ Decision: Pass unless price exceptional
```

## Workflow

### 1. Initial Entry (Uncertain Data)

```
1. Find apartment on Zillow
2. Open web interface
3. Select MULTIPLE options where uncertain:
   - Parking: ☑ Dedicated ☑ Street
   - Laundry: ☑ Shared Good ☑ Shared Poor
4. Check "Mark as tour question" for each
5. Submit
```

**Result:** Apartment added with score range

### 2. Analysis

```
$ python main.py --analyze-new

Analyzing: 123 Mission St
...
✓ Scores calculated
  Range: 68.5 - 81.2 (certainty: 75%)
  Tour Questions: Parking type, Laundry type
```

**Google Sheet shows:**
- Score: 74.9
- Min: 68.5
- Max: 81.2
- Certainty: 75%
- Tour Questions: "Parking type, Laundry type"

### 3. Review & Prioritize Tours

Sort by:
1. Max score (high potential)
2. Score range (bigger range = more to verify)
3. Your gut feeling

### 4. Tour & Verify

Bring your phone with Google Sheet open:
- Check "Tour Questions" column
- Ask landlord/verify in person
- Take notes

### 5. Update with Certain Data

After tour:
1. Open web form again (or edit sheet directly)
2. Enter same apartment
3. Select SINGLE option for verified fields:
   - Parking: ☑ Street Parking (uncheck others)
4. Uncheck "Mark as tour question"
5. Re-submit

### 6. Re-Analyze

```
$ python main.py --analyze-new

Analyzing: 123 Mission St (updated)
...
✓ Scores calculated
  Score: 70.3 (certainty: 100%)
```

**Google Sheet shows:**
- Score: 70.3 (no range)
- Certainty: 100%
- Tour Questions: (none)

Now you have the true score!

## Technical Details

### JSON Storage

Multi-select values stored as JSON arrays in Google Sheets:
```
Parking Type column: ["dedicated_spot_car_only", "street_parking"]
Laundry Type column: ["shared_good", "shared_poor"]
Neighborhoods column: ["Mission", "Potrero Hill"]
```

### Score Calculation

```python
# Single value (certain)
parking_score = calculate_score("dedicated_spot") → 7.0

# Multiple values (uncertain)
options = ["dedicated_spot", "street_parking"]
scores = [calculate_score(opt) for opt in options]
min_score = min(scores)  # 3.0
max_score = max(scores)  # 7.0
avg_score = (min + max) / 2  # 5.0
```

### Weighted Impact

Uncertainty in high-weight categories impacts total score more:
```
Parking (weight: 0.15):
- Range: 3-7 points
- Total impact: 4 × 0.15 × 10 = 6 points on 100-point scale

Safety (weight: 0.25):
- Range: 4-8 points  
- Total impact: 4 × 0.25 × 10 = 10 points on 100-point scale
```

## Tips

### When to Use Multi-Select

**Good reasons:**
- ✅ Zillow description ambiguous
- ✅ Photos don't show clearly
- ✅ Need to verify in person
- ✅ Landlord hasn't responded yet

**Bad reasons:**
- ❌ "I don't want to look it up"
- ❌ Too lazy to check photos
- ❌ Haven't read the listing

**Remember:** More certainty = better rankings!

### Selecting Options

**Be realistic:**
```
Bad:  Select all 5 parking options "just in case"
Good: Select 2-3 most likely based on listing
```

**Use common sense:**
```
If listing says "garage parking":
☑ Single Garage
☑ Dedicated Spot
☐ Street Parking (unlikely)
```

### Neighborhoods

**When uncertain:**
- Google Maps shows "Near X and Y" → Select both
- Address is on border → Select both
- Listing mentions multiple → Select all mentioned

**When certain:**
- Address clearly in one neighborhood → Select one
- You know the area → Select one

## Limitations

1. **Combinatorial Explosion:** Only varies one field at a time (parking type OR enclosure, not both simultaneously)
2. **Independent Scores:** Assumes uncertain fields don't interact
3. **Manual Re-Entry:** Need to manually update after tours (could be automated with form pre-fill)

## Future Enhancements

Possible improvements:
- **Auto-detection:** LLM analyzes Zillow text to suggest options
- **Smart defaults:** Learn common uncertainties per building/neighborhood
- **Tour checklist:** Generate printable checklist from tour questions
- **Update mode:** Pre-fill form with existing data for easy updates
- **Confidence weights:** Weight options by likelihood (60% dedicated, 40% street)

---

**This feature helps you make better decisions with incomplete data. Tour the high-potential apartments, verify details, and rank with confidence!**

