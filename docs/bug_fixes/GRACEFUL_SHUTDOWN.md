# Graceful Shutdown Feature

## Problem

When running expensive API operations (gym recalculation, full analysis), users had no safe way to stop the process without:
- ❌ Using Ctrl+C (potentially corrupting data)
- ❌ Wasting API quota on unnecessary calls
- ❌ Waiting for the entire operation to complete (could be 2-3 minutes)

## Solution

Added **two methods** to safely stop analysis operations:

### Method 1: Ctrl+C in Terminal (Graceful)

When you press Ctrl+C once:
```
⚠️  Shutdown requested! Finishing current apartment, then stopping...
⚠️  Press Ctrl+C again to force quit (may corrupt data)
```

**Behavior:**
- ✅ Finishes processing the current apartment
- ✅ Saves data for completed apartments
- ✅ Stops before starting the next apartment
- ✅ No data corruption

Press Ctrl+C **twice** to force quit immediately (not recommended).

### Method 2: Stop Button in Web UI

A **"⏹️ Stop Analysis"** button appears during recalculation:

```
[🔄 Clear Selected & Recalculate]  [⏹️ Stop Analysis]
```

**Behavior:**
- ✅ Visible only during active analysis
- ✅ Sends graceful shutdown signal
- ✅ Finishes current apartment
- ✅ Shows status: "⏹️ Stopping..."

## Implementation Details

### 1. Global Shutdown Flag

**File:** `web_app.py`

```python
# Global flag for graceful shutdown
shutdown_requested = False

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    global shutdown_requested
    if not shutdown_requested:
        shutdown_requested = True
        print("\n\n⚠️  Shutdown requested! Finishing current apartment, then stopping...")
        print("⚠️  Press Ctrl+C again to force quit (may corrupt data)")
    else:
        print("\n\n❌ Force quit requested. Exiting immediately.")
        sys.exit(1)

# Register signal handler
signal.signal(signal.SIGINT, signal_handler)
```

### 2. Shutdown Check in Loop

**File:** `web_app.py` (in `admin_force_recalculate`)

```python
for record in records:
    # Check if shutdown was requested
    global shutdown_requested
    if shutdown_requested:
        print(f"\n⚠️  Shutdown requested. Stopping after {analyzed_count} apartments.")
        message = f'⚠️ Interrupted: Recalculated for {analyzed_count}/{len(records)} apartment(s).'
        break
    
    # ... process apartment ...
    # Data is written here before moving to next apartment
    sheets_client.write_apartment_data(row_num, result)
```

### 3. REST API Endpoint

**File:** `web_app.py`

```python
@app.route('/admin/request_shutdown', methods=['POST'])
def admin_request_shutdown():
    """Request graceful shutdown of current analysis"""
    global shutdown_requested
    shutdown_requested = True
    return jsonify({
        'success': True,
        'message': 'Shutdown requested. Finishing current apartment...'
    })
```

### 4. UI Stop Button

**File:** `templates/entry_form.html`

```html
<button id="stopRecalcBtn" class="btn btn-danger" onclick="requestShutdown()" 
        style="display: none;">
    ⏹️ Stop Analysis
</button>
```

```javascript
// Show stop button during analysis
stopBtn.style.display = 'inline-block';

// Handle stop button click
async function requestShutdown() {
    const confirmed = confirm(
        '⚠️ Stop the current analysis?\n\n' +
        'The current apartment will finish processing, then analysis will stop.'
    );
    
    if (!confirmed) return;
    
    const response = await fetch('/admin/request_shutdown', { method: 'POST' });
    // ... update UI ...
}
```

### 5. Flag Reset

After analysis completes or is interrupted:

```python
# Reset shutdown flag after completion
shutdown_requested = False
```

## Data Safety Guarantees

### What's Safe ✅

1. **Data is written after each apartment:**
   ```python
   for apartment in apartments:
       result = analyze_apartment(apartment)  # API calls happen here
       write_to_sheet(result)                 # ✅ Data saved!
       # Check shutdown flag here (before next apartment)
   ```

2. **Completed apartments are always saved:**
   - Apartment 1: ✅ Analyzed & saved
   - Apartment 2: ✅ Analyzed & saved
   - Apartment 3: 🔄 Currently processing
   - Apartment 4: ⏸️ Shutdown requested, skipped
   - Result: First 3 apartments are safely saved

3. **Partial data never written:**
   - Analysis completes fully for each apartment before writing
   - No half-finished data in the sheet

### What Happens on Shutdown

**Scenario:** Recalculating gym for 14 apartments, shutdown after 5

```
Processing apartment 1/14... ✅ Done (saved)
Processing apartment 2/14... ✅ Done (saved)
Processing apartment 3/14... ✅ Done (saved)
Processing apartment 4/14... ✅ Done (saved)
Processing apartment 5/14... ✅ Done (saved)
Processing apartment 6/14... 🔄 In progress...

[User presses Ctrl+C or Stop button]

⚠️ Shutdown requested! Finishing current apartment...
Processing apartment 6/14... ✅ Done (saved)

⚠️ Stopped after 6 apartments.
Apartments 7-14: Not processed (existing data preserved)
```

**Result:**
- Apartments 1-6: ✅ New gym data
- Apartments 7-14: ✅ Old gym data preserved
- No corruption: ✅
- Partial progress saved: ✅

## When to Use Each Method

### Use Ctrl+C When:
- Running from terminal/command line
- Quick shutdown needed
- Want to see terminal feedback

### Use Stop Button When:
- Using web interface
- Want UI confirmation
- Prefer GUI interaction

### Force Quit (Ctrl+C twice) When:
- Process is hung/frozen
- Absolutely must stop immediately
- Willing to risk losing current apartment's data

**⚠️ Force quit should be last resort!**

## User Experience

### Before

```
User: "Oh no, I selected the wrong component!"
→ Watches helplessly as system analyzes all 14 apartments
→ Wastes 2+ minutes
→ Wastes 150+ API calls
→ Can't stop it safely
→ User frustrated 😞
```

### After (Ctrl+C)

```
User: "Oh no, I selected the wrong component!"
→ Presses Ctrl+C
→ System: "⚠️ Shutdown requested! Finishing current apartment..."
→ Stops after current apartment (5 seconds)
→ 5 apartments saved, 9 skipped
→ Saved 1.5 minutes and 100+ API calls
→ User happy 😊
```

### After (Stop Button)

```
User: "Oh no, I selected the wrong component!"
→ Clicks "⏹️ Stop Analysis" button
→ Confirms in dialog
→ UI shows: "⚠️ Shutdown requested. Finishing current apartment..."
→ Button changes to "⏹️ Stopping..." (disabled)
→ Stops gracefully
→ UI shows: "⚠️ Interrupted: Recalculated gym for 5/14 apartment(s)."
→ User happy 😊
```

## Testing

Test scenarios:
1. ✅ Ctrl+C during gym recalc → Stops gracefully after current apartment
2. ✅ Stop button during happening recalc → Stops gracefully
3. ✅ Ctrl+C twice → Force quits immediately
4. ✅ Stop button with confirm cancel → Analysis continues
5. ✅ Shutdown flag resets after completion
6. ✅ Data integrity maintained (no corruption)
7. ✅ Partial progress saved correctly

## Files Modified

1. **`web_app.py`**
   - Lines 1-38: Added signal handler and shutdown flag
   - Lines 1947-1957: Added `/admin/request_shutdown` endpoint
   - Lines 2062-2069: Added shutdown check in recalc loop
   - Line 2103: Reset flag after completion

2. **`templates/entry_form.html`**
   - Lines 1282-1284: Added Stop button HTML
   - Lines 5128-5132: Show/hide stop button during analysis
   - Lines 5150-5177: Added `requestShutdown()` JavaScript function

## Technical Details

### Signal Handling

Python's `signal` module intercepts Ctrl+C:
- First Ctrl+C: Sets flag, allows graceful shutdown
- Second Ctrl+C: Calls `sys.exit(1)` for immediate termination

### Thread Safety

The `shutdown_requested` flag is:
- ✅ Checked at safe points (between apartments)
- ✅ Simple boolean (atomic in Python GIL)
- ✅ Reset after operations complete

### UI State Management

Stop button visibility:
```javascript
// Show during analysis
stopBtn.style.display = 'inline-block';

// Hide when done
stopBtn.style.display = 'none';
```

## Best Practices

### For Users

1. **Use graceful shutdown first:** Ctrl+C once or Stop button
2. **Wait for confirmation:** "Finishing current apartment..."
3. **Check results:** UI shows how many apartments were completed
4. **Force quit only if needed:** Ctrl+C twice as last resort

### For Developers

1. **Check flag at safe points:** Between loops, not mid-operation
2. **Always reset flag:** After completion or interruption
3. **Write data frequently:** After each significant unit of work
4. **Provide feedback:** Print/display shutdown progress

## Benefits

1. ✅ **Safe shutdown** - No data corruption
2. ✅ **Saves money** - Stop unnecessary API calls
3. ✅ **Saves time** - Don't wait for full completion
4. ✅ **User control** - Two convenient methods
5. ✅ **Partial progress preserved** - Work isn't wasted
6. ✅ **Clear feedback** - Know what's happening
7. ✅ **Recoverable** - Can resume later if needed

## Edge Cases Handled

1. **Shutdown during API call:** Current apartment completes, then stops
2. **Shutdown on last apartment:** Completes normally
3. **Multiple shutdowns:** Second press forces quit
4. **Shutdown while writing:** Write completes, then stops
5. **Network errors during shutdown:** Error handling still works

## Future Enhancements

Possible improvements:
- Progress bar showing apartments completed
- Ability to pause and resume
- Save "checkpoint" to resume from specific apartment
- Estimate time remaining
- Cancel specific components mid-analysis

---

**Status: ✅ Implemented and ready to use!**

You can now safely stop analysis operations without worrying about data corruption or wasted API calls.











