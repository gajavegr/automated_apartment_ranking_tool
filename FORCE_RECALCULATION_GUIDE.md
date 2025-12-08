# Enhanced Force Recalculation Feature

## Overview
The Force Recalculation feature has been enhanced to give you granular control over which score components to recalculate, saving time and API calls.

## What Changed

### Old Behavior
- Could only recalculate "all", "gym_score", or "laundry_score"
- Always cleared entire scores even if you only wanted to update one aspect

### New Behavior
- Select multiple specific components to recalculate
- More granular options for targeted updates
- Clear gym walk AND bike times together when needed

## Available Components

You can now recalculate any combination of these components:

### 1. **gym** - Gym Scores & Travel Times
Clears:
- Gym Score
- Gym Walk Time (min)
- Gym Bike Time (min)  ← NEW!
- Gym Transport Mode  ← NEW!
- Gym Time Used for Score (min)  ← NEW!

**When to use:** After adding new gyms, when you want to calculate bike times for gyms >15 min walk

### 2. **laundry** - Laundry Scores
Clears:
- Laundry Score

**When to use:** After updating laundry type or scoring weights

### 3. **parking** - Parking Scores
Clears:
- Parking Score

**When to use:** After updating parking information

### 4. **happening** - Happening Scores & Amenities
Clears:
- Happening Score
- Restaurants Nearby
- Cafes Nearby
- Parks Nearby

**When to use:** After excluding places or when amenity data needs refresh

### 5. **safety** - Safety Scores
Clears:
- Safety Score (OpenData)
- Combined Safety

**When to use:** After updating manual safety ratings or when crime data updates

### 6. **commute** - Commute Data
Clears:
- Commute Time (You)
- Commute Route
- Commute Time (Partner)

**When to use:** When traffic patterns change or routes need recalculation

### 7. **wfh** - Work From Home Quality
Clears:
- WFH Quality Score

**When to use:** After updating WFH inputs (desk space, lighting, etc.)

### 8. **all** - Full Recalculation
Clears all of the above plus:
- Score Min/Max/Certainty
- Weighted Score

**When to use:** After major config changes or scoring weight updates

## API Usage

### Recalculate Specific Components

```javascript
// Recalculate only gym data for all apartments
fetch('/admin/force_recalculate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        components: ['gym'],
        addresses: 'all'
    })
});

// Recalculate gym AND parking for specific apartments
fetch('/admin/force_recalculate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        components: ['gym', 'parking'],
        addresses: ['123 Main St', '456 Oak Ave']
    })
});

// Full recalculation for one apartment
fetch('/admin/force_recalculate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        components: ['all'],
        addresses: ['123 Main St']
    })
});
```

### Response Format

```javascript
{
    success: true,
    cleared_count: 5,
    components: ['gym (walk/bike times)', 'parking'],
    columns: ['Gym Score', 'Gym Walk Time (min)', 'Gym Bike Time (min)', ...],
    cache_cleared: true,
    message: 'Cleared gym (walk/bike times), parking for 5 apartment(s). Run analysis to recalculate.'
}
```

## Use Cases

### Use Case 1: Add Bike Times to Existing Apartments
**Scenario:** You've added the gym biking feature and want to calculate bike times for apartments with gyms >15 min walk

**Steps:**
1. Click "Force Full Recalculation"
2. Select components: `['gym']`
3. Select apartments: `'all'` or specific ones
4. Click "Clear & Recalculate"
5. System will recalculate gym walk times and add bike times where applicable

**Result:** All apartments will have up-to-date gym data with bike times for distant gyms

### Use Case 2: Update Only Happening Scores
**Scenario:** You've excluded some restaurants and want to update happening scores

**Steps:**
1. Select components: `['happening']`
2. Addresses: `'all'`
3. Run analysis

**Result:** Only happening scores recalculated, gym/parking/etc. unchanged

### Use Case 3: Refresh Multiple Components
**Scenario:** You've updated parking AND gym information

**Steps:**
1. Select components: `['gym', 'parking']`
2. Run analysis

**Result:** Both gym and parking scores recalculated efficiently

## Benefits

1. **⚡ Faster:** Only recalculate what's needed
2. **💰 Cheaper:** Fewer API calls = lower Google Maps API costs
3. **🎯 Targeted:** Update specific data without affecting other scores
4. **🔄 Flexible:** Combine multiple components as needed
5. **📊 Transparent:** See exactly what was cleared in the response

## Notes

- Score ranges (min/max) and weighted scores are **always** cleared when any component changes
- Cache is **always** cleared to ensure fresh API calls
- After clearing, you must run "Run Analysis" to recalculate the cleared components
- Clearing is **irreversible** - make sure you want to recalculate before clearing

## For the Gym Biking Feature

To add bike times to your existing apartments:

```javascript
// Option 1: Recalculate all apartments
{
    components: ['gym'],
    addresses: 'all'
}

// Option 2: Only apartments with far gyms (you can check gym_walk_time_mins > 15)
{
    components: ['gym'],
    addresses: ['apt1', 'apt2', ...]  // List apartments with gym_walk_time_mins > 15
}
```

The system will:
1. Clear all gym-related columns
2. Recalculate walking times
3. Calculate biking times for gyms >15 min walk
4. Update scores accordingly
5. Set default transport mode (walk for ≤15min, user's choice for >15min)



